"""Operator setup with fake downloads/models, temporary files, no native audio."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis.voice import Voice
from jarvis.voice_data import VoiceConfig, load_config


def script(name):
    path = Path(__file__).resolve().parents[1] / "scripts" / name
    spec = importlib.util.spec_from_file_location("voice_operator_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--download-small-en"],
        ["--approved"],
        ["--approved", "--download-small-en", "--download-base-en"],
    ],
)
def test_setup_requires_one_explicit_approved_download(monkeypatch, arguments, tmp_path):
    module = script("Setup-JarvisVoice.py")
    monkeypatch.setattr(sys, "argv", ["setup", *arguments])
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 2
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("changed_during_download", [False, True])
def test_small_setup_pins_revision_preserves_base_and_owner_voice_choices(
    monkeypatch, tmp_path, changed_during_download
):
    module = script("Setup-JarvisVoice.py")
    root = tmp_path / "Jarvis"
    original = VoiceConfig(
        input_device="owner input",
        output_device="owner output",
        tts_provider="kokoro",
        neural_voice="am_michael",
        wake_call="Computer",
        wake_silence_seconds=1.0,
        volume=37,
    )
    owner = Voice(root, lambda *a: None, lambda *a: False)
    owner.save(original)
    base = root / "speech/base.en"
    base.mkdir(parents=True)
    (base / "model.bin").write_bytes(b"preserved base")

    def download(repository, *, revision, local_dir, allow_patterns):
        assert repository == "Systran/faster-whisper-small.en"
        assert revision == "d1d751a5f8271d482d14ca55d9e2deeebbae577f"
        assert set(allow_patterns) == {
            "model.bin",
            "config.json",
            "tokenizer.json",
            "vocabulary.txt",
        }
        local_dir.mkdir(parents=True)
        for name in allow_patterns:
            (local_dir / name).write_bytes(b"synthetic asset " + name.encode())
        if changed_during_download:
            owner.save(original.model_copy(update={"volume": 23}))

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["setup", "--download-small-en", "--approved", "--select"])
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(HfApi=lambda: None, snapshot_download=download),
    )
    monkeypatch.setitem(
        sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=lambda *a, **k: None)
    )
    if changed_during_download:
        with pytest.raises(ValueError, match="changed during setup"):
            module.main()
        assert load_config(root) == original.model_copy(update={"volume": 23})
    else:
        module.main()
        assert load_config(root) == original.model_copy(
            update={"model_directory": "speech/small.en"}
        )
        backups = list(root.glob("voice.before-recognition-*.toml"))
        assert len(backups) == 1 and 'wake_call = "Computer"' in backups[0].read_text()
    assert (base / "model.bin").read_bytes() == b"preserved base"
    manifest = json.loads((root / "speech/small.en/jarvis-model.json").read_text())
    assert manifest["revision"] == "d1d751a5f8271d482d14ca55d9e2deeebbae577f"
    owner.close()


def test_frozen_recognition_score_counts_missing_negation_and_number_formatting():
    score = script("Evaluate-JarvisRecognition.py").score
    assert score("Do not close it.", "Do close it.") == {
        "exact": False,
        "word_errors": 1,
        "reference_words": 4,
    }
    assert score("sleep six hours", "sleep 6 hours")["exact"] is False
    assert score("Open Notepad.", "open notepad")["exact"] is True


def test_attended_diagnostics_explain_errors_without_changing_the_exact_gate():
    diagnostic = script("Test-JarvisRecognition.py").diagnostic
    assert diagnostic("What is your name?", "What's your name?") == "CONTRACTION_ONLY"
    assert diagnostic("What is your name?", "is your name") == "LEADING_WORDS_MISSING"
    assert diagnostic("What is your name?", "What is your") == "TRAILING_WORDS_MISSING"
    assert diagnostic("six hours", "6 hours") == "NUMBER_FORMAT_ONLY"
    assert diagnostic("Fav Jpop", "Fab J-pop") == "WORDS_DIFFER"
