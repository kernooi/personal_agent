"""Owner-authorized startup of existing local infrastructure, never model-callable."""

import hashlib
import json
import os
import shutil
import subprocess
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from pydantic import Field

from jarvis.bootstrap import load_profile
from jarvis.models import StrictRecord
from jarvis.web_data import load_web_config


class StartupConfig(StrictRecord):
    ollama_executable: str
    ollama_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    ollama_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    docker_context: str = Field(default="desktop-linux", pattern=r"^(desktop-linux|default)$")
    container_name: str = Field(default="jarvis-searxng", pattern=r"^jarvis-[a-z0-9_.-]{1,60}$")
    searxng_image: str = Field(pattern=r"^docker\.io/searxng/searxng@sha256:[a-f0-9]{64}$")


class StartupCancelled(ValueError):
    pass


class StartupServices:
    def __init__(self, private_root, *, client=None, run=subprocess.run, popen=subprocess.Popen):
        self.root = Path(private_root)
        self.client = client
        self.run, self.popen = run, popen
        self.runtime_process = None

    def check(self, cancel):
        if cancel.is_set():
            raise StartupCancelled("Startup cancelled.")

    def prepare(self, command, notify, cancel):
        try:
            self._prepare(command, notify, cancel)
        except (httpx.HTTPError, subprocess.SubprocessError) as exc:
            raise ValueError(
                "Local service startup couldn't finish. Please retry connecting."
            ) from exc

    def _prepare(self, command, notify, cancel):
        self.check(cancel)
        config = StartupConfig.model_validate(
            tomllib.loads((self.root / "gui-startup.toml").read_text(encoding="utf-8-sig")),
            strict=True,
        )
        profile = load_profile(Path(command[command.index("--profile") + 1]), allow_ollama=True)
        web = load_web_config(Path(command[command.index("--web-config") + 1]))
        # No proxy inheritance, redirects, cloud fallback or public/private fetch tool here.
        with (
            httpx.Client(trust_env=False, follow_redirects=False)
            if self.client is None
            else (self.client) as client
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                model = pool.submit(self.ollama, config, profile, client, notify, cancel)
                search = pool.submit(self.searxng, config, web, client, notify, cancel)
                model.result()  # No chat without the configured local model.
                try:
                    search.result()
                except StartupCancelled:
                    raise
                except (OSError, ValueError, httpx.HTTPError, subprocess.SubprocessError) as exc:
                    notify("Web search couldn't start. You can still chat locally.", warning=True)
                    notify(str(exc), diagnostic=True)
        self.check(cancel)

    @staticmethod
    def request(client, method, url, *, timeout=2, **kwargs):
        with client.stream(method, url, timeout=timeout, **kwargs) as response:
            response.raise_for_status()
            raw = bytearray()
            for chunk in response.iter_bytes():
                raw.extend(chunk)
                if len(raw) > 1048576:
                    raise ValueError("Startup health response was too large.")
            return bytes(raw)

    def json_request(self, client, method, url, **kwargs):
        data = json.loads(self.request(client, method, url, **kwargs))
        if not isinstance(data, dict):
            raise ValueError("Unexpected local service response.")
        return data

    def ollama(self, config, profile, client, notify, cancel):
        self.check(cancel)
        if getattr(profile, "base_url", "") != "http://127.0.0.1:11434":
            raise ValueError("Automatic startup requires the configured local Ollama profile.")
        if not profile.cloud_disabled_verified:
            raise ValueError("The local profile needs cloud-disabled setup evidence first.")
        executable = Path(config.ollama_executable).resolve()
        if not executable.is_relative_to((self.root / "runtime").resolve()):
            raise ValueError("Ollama must be the approved project-local standalone runtime.")
        with executable.open("rb") as binary:
            actual_hash = hashlib.file_digest(binary, "sha256").hexdigest()
        if actual_hash != config.ollama_sha256:
            raise ValueError("The registered Ollama executable changed. No server was launched.")
        base = profile.base_url
        try:
            version = self.json_request(client, "GET", base + "/api/version")
        except (httpx.HTTPError, ValueError):
            notify("Starting local model server…")
            self.check(cancel)
            logs = self.root / "logs"
            logs.mkdir(exist_ok=True)
            logfile = logs / ("gui-ollama-" + uuid4().hex + ".log")
            env = dict(os.environ)
            env.update(
                OLLAMA_NO_CLOUD="1",
                OLLAMA_HOST="127.0.0.1:11434",
                OLLAMA_MODELS=str(self.root / "models"),
                OLLAMA_CONTEXT_LENGTH=str(profile.context_tokens),
                OLLAMA_DEBUG_LOG_REQUESTS="false",
            )
            with logfile.open("wb") as output:
                self.runtime_process = self.popen(
                    [str(executable), "serve"],
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    env=env,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
                    )
                    if os.name == "nt"
                    else 0,
                )
            deadline = time.monotonic() + 30
            while True:
                self.check(cancel)
                if self.runtime_process.poll() is not None:
                    raise ValueError(
                        "Ollama could not start. Its private startup log is in Jarvis/logs."
                    ) from None
                try:
                    version = self.json_request(client, "GET", base + "/api/version")
                    log = logfile.read_text(encoding="utf-8", errors="replace")
                    if "Ollama cloud disabled: true" in log:
                        notify(
                            "Local server startup log confirms cloud is disabled.", diagnostic=True
                        )
                        break
                except (httpx.HTTPError, ValueError):
                    pass
                if time.monotonic() >= deadline:
                    raise ValueError(
                        "Ollama startup or cloud-disabled verification timed out."
                    ) from None
                cancel.wait(0.25)
        if version.get("version") != config.ollama_version:
            raise ValueError(
                "A different Ollama runtime occupies port 11434; it was left untouched."
            )
        self.check(cancel)
        installed = self.json_request(client, "GET", base + "/api/tags")
        models = installed.get("models", [])
        if not isinstance(models, list) or not any(
            isinstance(m, dict) and m.get("name") == profile.model_identity for m in models
        ):
            raise ValueError("The configured model is not installed. No model was downloaded.")
        notify("Loading local model…")
        loaded = self.json_request(
            client,
            "POST",
            base + "/api/generate",
            timeout=60,
            json={
                "model": profile.model_identity,
                "prompt": "",
                "stream": False,
                "keep_alive": profile.provider_options.keep_alive,
                "options": {"num_ctx": profile.context_tokens},
            },
        )
        if loaded.get("done") is not True:
            raise ValueError("The configured model did not finish loading.")
        running = self.json_request(client, "GET", base + "/api/ps")
        running_models = running.get("models", [])
        if not isinstance(running_models, list) or not any(
            isinstance(model, dict) and model.get("name") == profile.model_identity
            for model in running_models
        ):
            raise ValueError("The configured model wasn't observed loaded after startup.")
        self.check(cancel)
        notify("Local model ready.", diagnostic=True)

    def docker(self, executable, context, *args, timeout=15, check=True):
        result = self.run(
            [str(executable), "--context", context, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if check and result.returncode:
            raise ValueError("Docker couldn't complete the local SearXNG startup step.")
        return result

    @staticmethod
    def container_record(raw, image_id, port, settings, data):
        try:
            records = json.loads(raw)
            if not isinstance(records, list) or len(records) != 1:
                raise ValueError
            record = records[0]
            bindings = {"8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": port}]}
            mounts = {mount["Destination"]: mount for mount in record["Mounts"]}
            if (
                record["Image"] != image_id
                or record["HostConfig"]["PortBindings"] != bindings
                or record["HostConfig"]["RestartPolicy"]["Name"] not in {"", "no"}
                or record["HostConfig"]["Privileged"] is not False
                or record["HostConfig"]["NetworkMode"] not in {"default", "bridge"}
                or set(mounts) != {"/etc/searxng", "/var/cache/searxng"}
                or len(record["Mounts"]) != 2
            ):
                raise ValueError
            for target, path in (("/etc/searxng", settings), ("/var/cache/searxng", data)):
                expected = str(path.resolve()).replace("\\", "/").casefold().rstrip("/")
                aliases = {expected}
                if len(expected) > 2 and expected[1] == ":":
                    mapped = expected[0] + expected[2:]
                    aliases.update({"/run/desktop/mnt/host/" + mapped, "/host_mnt/" + mapped})
                source = mounts[target]["Source"].replace("\\", "/").casefold().rstrip("/")
                if mounts[target]["Type"] != "bind" or source not in aliases:
                    raise ValueError
            if type(record["State"]["Running"]) is not bool:
                raise ValueError
            if record["State"]["Running"] and record["NetworkSettings"]["Ports"] != bindings:
                raise ValueError
            return record
        except (KeyError, TypeError, ValueError, IndexError, AttributeError) as exc:
            raise ValueError(
                "The named SearXNG container doesn't match the approved local setup."
            ) from exc

    def searxng(self, config, web, client, notify, cancel):
        if not web.enabled or not web.local_search_authorized or web.provider != "searxng":
            return
        self.check(cancel)
        executable = shutil.which("docker")
        if not executable:
            raise ValueError("Docker Desktop is not installed; no installation was attempted.")
        context = config.docker_context
        endpoint = self.docker(
            executable,
            context,
            "context",
            "inspect",
            context,
            "--format",
            "{{json .Endpoints.docker.Host}}",
        )
        if json.loads(endpoint.stdout) not in {
            "npipe:////./pipe/dockerDesktopLinuxEngine",
            "npipe:////./pipe/docker_engine",
        }:
            raise ValueError("Automatic startup only supports the local Docker Desktop engine.")
        info = self.docker(executable, context, "info", "--format", "{{.OSType}}", check=False)
        if info.returncode:
            notify("Starting Docker Desktop…")
            self.check(cancel)
            # Installed Docker Desktop's documented command; no OS startup setting.
            self.run(
                [executable, "desktop", "start", "--detach"],
                capture_output=True,
                timeout=20,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            deadline = time.monotonic() + 90
            while True:
                self.check(cancel)
                info = self.docker(
                    executable, context, "info", "--format", "{{.OSType}}", check=False
                )
                if info.returncode == 0:
                    break
                if time.monotonic() >= deadline:
                    raise ValueError("Docker Desktop didn't become ready in time.")
                cancel.wait(0.5)
        if info.stdout.strip() != "linux":
            raise ValueError("SearXNG needs the existing local Linux Docker engine.")
        notify("Starting local web search…")
        image = self.docker(
            executable,
            context,
            "image",
            "inspect",
            config.searxng_image,
            "--format",
            "{{.Id}}",
            check=False,
        )
        if image.returncode:
            raise ValueError(
                "The approved cached SearXNG image is missing. No image was downloaded."
            )
        port = str(urlsplit(web.search_endpoint).port)
        search_root = self.root / "searxng"
        settings, data = search_root / "config", search_root / "data"
        if not (settings / "settings.yml").is_file() or not data.is_dir():
            raise ValueError("Existing private SearXNG configuration/data is missing.")
        existing = self.docker(
            executable, context, "container", "inspect", config.container_name, check=False
        )
        self.check(cancel)
        if existing.returncode:
            self.docker(
                executable,
                context,
                "run",
                "--pull",
                "never",
                "--name",
                config.container_name,
                "--rm",
                "-d",
                "--publish",
                f"127.0.0.1:{port}:8080",
                "--mount",
                f"type=bind,source={settings},target=/etc/searxng",
                "--mount",
                f"type=bind,source={data},target=/var/cache/searxng",
                config.searxng_image,
            )
            existing = self.docker(
                executable, context, "container", "inspect", config.container_name
            )
        record = self.container_record(existing.stdout, image.stdout.strip(), port, settings, data)
        if not record["State"]["Running"]:
            self.check(cancel)
            self.docker(executable, context, "start", record["Id"])
        live = self.docker(executable, context, "container", "inspect", record["Id"])
        record = self.container_record(live.stdout, image.stdout.strip(), port, settings, data)
        deadline = time.monotonic() + 30
        health = web.search_endpoint.removesuffix("/search") + "/healthz"
        while True:
            self.check(cancel)
            try:
                self.request(client, "GET", health)
                notify("Local web search ready.", diagnostic=True)
                return
            except httpx.HTTPError:
                if time.monotonic() >= deadline:
                    raise ValueError(
                        "SearXNG started but its local health check timed out."
                    ) from None
                cancel.wait(0.25)
