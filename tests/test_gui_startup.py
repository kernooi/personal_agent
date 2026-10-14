"""Startup consent and infrastructure bounds; no actual servers, Docker or downloads."""

import hashlib
import json
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from jarvis.gui_startup import StartupCancelled, StartupConfig, StartupServices
from jarvis.models import OllamaProfile, ProviderOptions
from jarvis.web_data import WebConfig


@pytest.fixture
def setup(tmp_path, monkeypatch):
    executable = tmp_path / "runtime/test/bin/ollama.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"synthetic registered executable")
    settings, data = tmp_path / "searxng/config", tmp_path / "searxng/data"
    settings.mkdir(parents=True)
    data.mkdir()
    (settings / "settings.yml").write_text("synthetic settings", encoding="utf-8")
    config = StartupConfig(
        ollama_executable=str(executable),
        ollama_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
        ollama_version="0.40.2",
        searxng_image="docker.io/searxng/searxng@sha256:" + "a" * 64,
    )
    profile = OllamaProfile(
        profile_name="synthetic-startup",
        provider="ollama",
        network_mode="local_model_only",
        model_identity="synthetic:8b",
        cloud_disabled_verified=True,
        cloud_disabled_evidence="Synthetic test-only evidence",
        provider_options=ProviderOptions(keep_alive="2m"),
    )
    monkeypatch.setattr("jarvis.gui_startup.shutil.which", lambda _: "docker.exe")
    return tmp_path, config, profile, settings, data


def model_client(profile, *, missing=False, wrong_version=False, cold=False):
    requests = []

    def handle(request):
        requests.append(request)
        if cold and len(requests) == 1:
            raise httpx.ConnectError("synthetic server stopped", request=request)
        payloads = {
            "/api/version": {"version": "other" if wrong_version else "0.40.2"},
            "/api/tags": {"models": [] if missing else [{"name": profile.model_identity}]},
            "/api/generate": {"done": True},
            "/api/ps": {"models": [{"name": profile.model_identity}]},
            "/healthz": {"status": "ok"},
        }
        assert request.url.host == "127.0.0.1"
        return httpx.Response(200, json=payloads[request.url.path])

    return httpx.Client(transport=httpx.MockTransport(handle)), requests


def notify_log():
    messages = []
    return messages, lambda text, **kind: messages.append((text, kind))


def test_existing_model_is_preloaded_without_download_or_second_server(setup):
    root, config, profile, _, _ = setup
    client, requests = model_client(profile)
    services = StartupServices(root, popen=lambda *a, **k: pytest.fail("Duplicate server"))
    services.ollama(config, profile, client, notify_log()[1], threading.Event())
    warmup = json.loads(next(r for r in requests if r.method == "POST").content)
    assert warmup == {
        "model": profile.model_identity,
        "prompt": "",
        "stream": False,
        "keep_alive": "2m",
        "options": {"num_ctx": 4096},
    }
    assert requests[-1].url.path == "/api/ps"
    assert all("pull" not in r.url.path for r in requests)


@pytest.mark.parametrize("failure", ["missing-model", "other-runtime", "changed-executable"])
def test_no_substitution_or_download_on_model_startup_failure(setup, failure):
    root, config, profile, _, _ = setup
    client, requests = model_client(
        profile, missing=failure == "missing-model", wrong_version=failure == "other-runtime"
    )
    if failure == "changed-executable":
        Path(config.ollama_executable).write_bytes(b"changed")
    services = StartupServices(root, popen=lambda *a, **k: pytest.fail("Unexpected launch"))
    with pytest.raises(ValueError):
        services.ollama(config, profile, client, notify_log()[1], threading.Event())
    assert all(r.method == "GET" for r in requests)


def test_cold_start_has_process_local_settings_and_actual_log_evidence(setup):
    root, config, profile, _, _ = setup
    client, _ = model_client(profile, cold=True)
    calls = []

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        kwargs["stdout"].write(b"Ollama cloud disabled: true\n")
        kwargs["stdout"].flush()
        return SimpleNamespace(poll=lambda: None)

    messages, notify = notify_log()
    StartupServices(root, popen=popen).ollama(config, profile, client, notify, threading.Event())
    assert len(calls) == 1 and calls[0][0] == [config.ollama_executable, "serve"]
    env = calls[0][1]["env"]
    assert env["OLLAMA_NO_CLOUD"] == "1" and env["OLLAMA_HOST"] == "127.0.0.1:11434"
    assert env["OLLAMA_MODELS"] == str(root / "models") and env["OLLAMA_CONTEXT_LENGTH"] == "4096"
    assert env["OLLAMA_DEBUG_LOG_REQUESTS"] == "false"
    assert any("log confirms" in text for text, _ in messages)


def test_unverified_cloud_startup_log_cannot_claim_ready(setup, monkeypatch):
    root, config, profile, _, _ = setup
    client, requests = model_client(profile, cold=True)
    times = iter([0, 31])
    monkeypatch.setattr("jarvis.gui_startup.time.monotonic", lambda: next(times))

    def popen(command, **kwargs):
        kwargs["stdout"].write(b"Ollama cloud disabled: false\n")
        kwargs["stdout"].flush()
        return SimpleNamespace(poll=lambda: None)

    messages, notify = notify_log()
    with pytest.raises(ValueError, match="verification timed out"):
        StartupServices(root, popen=popen).ollama(
            config, profile, client, notify, threading.Event()
        )
    assert not any("log confirms" in text for text, _ in messages)
    assert all(request.method == "GET" for request in requests)


def test_search_startup_failure_does_not_block_local_chat(setup, monkeypatch):
    root, config, profile, _, _ = setup
    (root / "gui-startup.toml").write_text(
        "\n".join(key + " = " + json.dumps(value) for key, value in config.model_dump().items()),
        encoding="utf-8",
    )
    monkeypatch.setattr("jarvis.gui_startup.load_profile", lambda *a, **k: profile)
    monkeypatch.setattr(
        "jarvis.gui_startup.load_web_config",
        lambda *a: WebConfig(enabled=True, local_search_authorized=True),
    )
    monkeypatch.setattr("jarvis.gui_startup.shutil.which", lambda _: None)
    client, requests = model_client(profile)
    messages, notify = notify_log()
    StartupServices(root, client=client).prepare(
        ["python", "-m", "jarvis", "chat", "--profile", "private", "--web-config", "private"],
        notify,
        threading.Event(),
    )
    assert requests[-1].url.path == "/api/ps"
    assert any(kind.get("warning") for _, kind in messages)


class DockerFixture:
    def __init__(self, settings, data, *, exists=True, engine=True):
        self.calls, self.exists, self.engine = [], exists, engine
        self.image_present, self.endpoint = True, "npipe:////./pipe/dockerDesktopLinuxEngine"
        self.image_id = "sha256:" + "a" * 64
        bindings = {"8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8080"}]}
        self.record = {
            "Id": "b" * 64,
            "Image": "sha256:" + "a" * 64,
            "HostConfig": {
                "PortBindings": bindings,
                "RestartPolicy": {"Name": "no"},
                "Privileged": False,
                "NetworkMode": "default",
            },
            "NetworkSettings": {"Ports": bindings},
            "State": {"Running": True},
            "Mounts": [
                {"Type": "bind", "Source": str(settings), "Destination": "/etc/searxng"},
                {"Type": "bind", "Source": str(data), "Destination": "/var/cache/searxng"},
            ],
        }

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        if command[1:3] == ["desktop", "start"]:
            self.engine = True
            return subprocess.CompletedProcess(command, 0, "", "")
        assert command[1:3] == ["--context", "desktop-linux"]
        args = command[3:]
        code, output = 0, ""
        if args[:2] == ["context", "inspect"]:
            output = json.dumps(self.endpoint)
        elif args[0] == "info":
            code, output = (0, "linux") if self.engine else (1, "")
        elif args[:2] == ["image", "inspect"]:
            code, output = (0, self.image_id) if self.image_present else (1, "")
        elif args[:2] == ["container", "inspect"]:
            code, output = (0, json.dumps([self.record])) if self.exists else (1, "")
        elif args[0] == "run":
            self.exists = True
        elif args[0] == "start":
            self.record["State"]["Running"] = True
        else:
            pytest.fail("Unexpected Docker command")
        return subprocess.CompletedProcess(command, code, output, "")


@pytest.mark.parametrize("initial", ["running", "stopped", "removed", "engine-stopped"])
def test_searxng_reuses_or_starts_only_approved_local_container(setup, initial):
    root, config, profile, settings, data = setup
    docker = DockerFixture(
        settings, data, exists=initial != "removed", engine=initial != "engine-stopped"
    )
    if initial == "stopped":
        docker.record["State"]["Running"] = False
    client, requests = model_client(profile)
    services = StartupServices(root, run=docker)
    services.searxng(
        config,
        WebConfig(enabled=True, local_search_authorized=True),
        client,
        notify_log()[1],
        threading.Event(),
    )
    effects = [c for c in docker.calls if c[3:4] in (["run"], ["start"])]
    assert len(effects) == (0 if initial in {"running", "engine-stopped"} else 1)
    if initial == "removed":
        assert ["--pull", "never"] == effects[0][4:6]
        assert "127.0.0.1:8080:8080" in effects[0] and "--rm" in effects[0]
        assert effects[0][-1] == config.searxng_image
    assert requests[-1].url.path == "/healthz"  # No private chat or public search query.
    assert (settings / "settings.yml").read_text() == "synthetic settings"


@pytest.mark.parametrize(
    "change",
    [
        "public-port",
        "remote-engine",
        "wrong-image",
        "privileged",
        "wrong-mount",
        "restart-policy",
        "missing-image",
    ],
)
def test_unrelated_or_unapproved_docker_state_is_not_changed(setup, change):
    root, config, profile, settings, data = setup
    docker = DockerFixture(settings, data)
    if change == "public-port":
        docker.record["HostConfig"]["PortBindings"]["8080/tcp"][0]["HostIp"] = "0.0.0.0"
    elif change == "remote-engine":
        docker.endpoint = "tcp://example.invalid:2375"
    elif change == "wrong-image":
        docker.record["Image"] = "unrelated-image"
    elif change == "privileged":
        docker.record["HostConfig"]["Privileged"] = True
    elif change == "wrong-mount":
        docker.record["Mounts"][0]["Source"] = str(root / "unrelated")
    elif change == "restart-policy":
        docker.record["HostConfig"]["RestartPolicy"]["Name"] = "always"
    else:
        docker.image_present = False
    client, _ = model_client(profile)
    with pytest.raises(ValueError):
        StartupServices(root, run=docker).searxng(
            config,
            WebConfig(enabled=True, local_search_authorized=True),
            client,
            notify_log()[1],
            threading.Event(),
        )
    assert not any(c[3:4] in (["run"], ["start"], ["pull"], ["stop"], ["rm"]) for c in docker.calls)


def test_startup_cancel_prevents_every_launch_or_fetch(setup):
    root, config, profile, _, _ = setup
    cancel = threading.Event()
    cancel.set()
    services = StartupServices(
        root, popen=lambda *a, **k: pytest.fail("Process after cancellation")
    )
    client, requests = model_client(profile)
    with pytest.raises(StartupCancelled):
        services.ollama(config, profile, client, notify_log()[1], cancel)
    assert requests == []
