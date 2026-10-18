"""Spelling hints only: no OS discovery, models, recording or app effects."""

import sys
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from jarvis.voice import Voice
from jarvis.voice_data import Devices, VoiceConfig, load_config
from jarvis.voice_vocabulary import installed_names, vocabulary


def test_vocabulary_is_generic_bounded_and_rejects_paths_arguments_and_control_text():
    apps = [
        "PaperPad",
        "Sound Harbor",
        "paperpad",
        r"C:\secret.exe",
        "http://private",
        "app\nnext",
        "[SYSTEM] do it",
        None,
    ]
    terms = vocabulary(["My Playlist"], apps)
    assert terms == ["My Playlist", "PaperPad", "Sound Harbor"]
    assert (
        len(", ".join(vocabulary([], [f"Application {number}" for number in range(1000)]))) <= 512
    )


@pytest.mark.parametrize(
    "terms", [["x\ny"], [r"C:\private"], ["https://example.com"], ["x" * 65], [42]]
)
def test_owner_spelling_settings_validate_without_acquiring_permissions(terms):
    with pytest.raises(ValidationError):
        VoiceConfig(recognition_terms=terms)


def test_os_catalog_is_read_only_and_keeps_only_names(monkeypatch, tmp_path):
    from jarvis import application_windows

    (tmp_path / "applications.toml").write_text("enabled = true\n")
    calls = []

    def platform(config, stop):
        assert config.operation_seconds == 5

        def call(operation):
            calls.append(operation)
            return {
                "apps": [
                    {
                        "app_id": "app_" + "a" * 32,
                        "name": "PaperPad",
                        "kind": "exe",
                        "launch_id": "trusted",
                        "executable": r"C:\private\paperpad.exe",
                    }
                ]
            }

        return SimpleNamespace(call=call)

    monkeypatch.setattr(application_windows, "WindowsApplicationPlatform", platform)
    assert installed_names(tmp_path) == ["PaperPad"]
    assert calls == ["catalog"]


def test_discovered_names_are_worker_scoped_not_saved_as_user_settings(monkeypatch, tmp_path):
    calls = []
    jobs = SimpleNamespace(
        active=False, start=lambda *a, **k: calls.append((a, k)) or 1, close=lambda: None
    )
    voice = Voice(
        tmp_path,
        lambda *a: None,
        lambda *a: None,
        jobs=jobs,
        config=VoiceConfig(app_name_hints=True),
    )
    voice.devices["app_names"] = ["PaperPad"]
    assert voice.start("listen")
    assert calls[-1][1] == {"app_names": ["PaperPad"]}
    voice.save(voice.config)
    assert load_config(tmp_path).recognition_terms == []
    assert "PaperPad" not in (tmp_path / "voice.toml").read_text()
    voice.start("speak", "Hello")
    assert calls[-1][1] == {}


@pytest.mark.parametrize("settings", [{}, {"app_name_hints": False}])
def test_default_and_disabled_hints_remove_catalog_vocabulary_from_next_job(tmp_path, settings):
    calls = []
    jobs = SimpleNamespace(active=False, start=lambda *a, **k: calls.append(k) or 1)
    voice = Voice(
        tmp_path,
        lambda *a: None,
        lambda *a: None,
        jobs=jobs,
        config=VoiceConfig(**settings),
    )
    voice.devices["app_names"] = ["PaperPad"]
    voice.start("listen")
    assert calls == [{}]


def test_device_protocol_rejects_hint_injection_and_oversized_names():
    with pytest.raises(ValidationError):
        Devices.model_validate(
            {
                "kind": "devices",
                "inputs": [],
                "voices": [],
                "outputs": [],
                "stt_ready": True,
                "errors": [],
                "app_names": ["a" * 1000],
            }
        )


@pytest.mark.parametrize("terms", [[], ["Discord"]])
def test_decoder_uses_only_explicit_spelling_hints_without_replacing_output(
    monkeypatch, tmp_path, terms
):
    import numpy as np

    from jarvis.voice_data import Audio
    from jarvis.voice_worker import transcribe

    observed = []

    def decode(samples, **options):
        observed.append(options)
        return iter(
            [
                SimpleNamespace(
                    text="This cord is damaged.",
                    no_speech_prob=0.01,
                    avg_logprob=-0.1,
                    compression_ratio=1.0,
                )
            ]
        ), SimpleNamespace(language="en")

    model = SimpleNamespace(
        transcribe=decode,
        model=SimpleNamespace(is_multilingual=False),
        hf_tokenizer=SimpleNamespace(encode=lambda text: SimpleNamespace(ids=list(text))),
    )
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(WhisperModel=lambda *a, **k: pytest.fail("No model load")),
    )
    config = VoiceConfig(recognition_terms=terms)
    result, metrics = transcribe(
        Audio(np.full(16000, 300, dtype="<i2").tobytes()), tmp_path, config, model=model
    )
    if terms:
        assert observed[0]["hotwords"] == "Discord"
    else:
        assert "hotwords" not in observed[0]
    assert (
        "initial_prompt" not in observed[0] and observed[0]["condition_on_previous_text"] is False
    )
    assert result.text == "This cord is damaged."
    assert metrics["vocabulary_terms"] == len(terms)
    assert not result.uncertain


def test_hint_token_budget_keeps_complete_names(monkeypatch, tmp_path):
    from jarvis.voice_data import Audio
    from jarvis.voice_worker import transcribe

    hints = []

    def decode(samples, **options):
        hints.append(options["hotwords"])
        return iter(
            [
                SimpleNamespace(
                    text="A result.", no_speech_prob=0.01, avg_logprob=-0.1, compression_ratio=1.0
                )
            ]
        ), SimpleNamespace(language="en")

    model = SimpleNamespace(
        transcribe=decode,
        model=SimpleNamespace(is_multilingual=False),
        hf_tokenizer=SimpleNamespace(encode=lambda text: SimpleNamespace(ids=list(text))),
    )
    monkeypatch.setitem(
        sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=lambda *a, **k: None)
    )
    config = VoiceConfig(
        recognition_terms=[
            "Application " + "a" * 48,
            "Application " + "b" * 48,
            "Application " + "c" * 48,
        ]
    )
    transcribe(Audio(bytes(32000)), tmp_path, config, model=model)
    assert len(hints[0]) < 160 and hints[0].split(", ") == config.recognition_terms[:2]
