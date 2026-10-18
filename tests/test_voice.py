"""No recording, speakers, model inference, tool effects or real audio processes."""

import io
import json
import queue
import sys
import threading
from types import SimpleNamespace

import pytest

from jarvis.voice import Voice
from jarvis.voice_data import (
    Audio,
    Transcript,
    VoiceConfig,
    VoiceState,
    load_config,
    needs_review,
    request_text,
    spoken_text,
)
from jarvis.voice_presentation import PREFIX, parse_control
from jarvis.voice_runtime import AudioJobs


class Jobs:
    def __init__(self):
        self.events = queue.Queue()
        self.active = False
        self.generation = 0
        self.cancelled = False
        self.calls = []

    def start(self, operation, config, text=""):
        assert not self.active
        self.active = True
        self.generation += 1
        self.calls.append((operation, config, text))
        return self.generation

    def cancel(self):
        self.cancelled = True

    def finish(self):
        self.finish_requested = True

    def emit(self, kind, **data):
        if kind == "finished":
            self.active = False
        self.events.put((self.generation, {"kind": kind, **data}))

    def close(self):
        self.closed = True
        self.cancel()


@pytest.fixture
def voice(tmp_path):
    jobs, events, submitted = Jobs(), [], []
    v = Voice(
        tmp_path, lambda *x: events.append(x), lambda *x: submitted.append(x) or True, jobs=jobs
    )
    v.devices["stt_ready"] = True
    return v, jobs, events, submitted


def transcript(text="Jarvis, open Notepad.", uncertain=False):
    return Transcript(text=text, language="en", uncertain=uncertain, seconds=1.0)


def recognized(v, jobs, text="Jarvis, open Notepad.", uncertain=False):
    v.microphone()
    jobs.emit("stage", state="LISTENING")
    v.poll()
    jobs.emit("stage", state="TRANSCRIBING")
    jobs.emit("transcript", transcript=transcript(text, uncertain).model_dump())
    jobs.emit("finished")
    v.poll()


def test_no_startup_recording_or_automatic_loop_and_same_submission(voice):
    v, jobs, events, submitted = voice
    assert not jobs.calls and v.state == VoiceState.IDLE
    recognized(v, jobs)
    assert submitted == [("open Notepad.", "Jarvis, open Notepad.")]
    assert v.state == VoiceState.PROCESSING
    v.reply("The selected Notepad window is open and ready.")
    assert [c[0] for c in jobs.calls] == ["listen"]
    v.ready()
    assert jobs.calls[-1][0] == "speak"
    assert v.state != VoiceState.SPEAKING  # Actual playback has not started.
    jobs.emit("stage", state="SPEAKING")
    v.poll()
    assert v.state == VoiceState.SPEAKING
    v.microphone()
    assert jobs.cancelled and len(submitted) == 1  # Half-duplex, no self-trigger.
    jobs.emit("finished")
    v.poll()
    assert v.state == VoiceState.IDLE
    assert [c[0] for c in jobs.calls].count("listen") == 1
    assert [e[1] for e in events if e[0] == "state"][:3] == [
        VoiceState.LISTENING,
        VoiceState.TRANSCRIBING,
        VoiceState.SUBMITTING,
    ]


@pytest.mark.parametrize(
    "text,uncertain",
    [
        ("open Notepad", True),
        ("/quit", False),
        ("yes", False),
        ("approve", False),
        ("yes.", False),
        ("go ahead!", False),
    ],
)
def test_unclear_and_approval_transcripts_are_drafts_not_self_authorization(voice, text, uncertain):
    v, jobs, events, submitted = voice
    recognized(v, jobs, text, uncertain)
    assert submitted == []
    assert any(e[0] == "transcript" and e[1]["review"] for e in events)
    assert v.state == VoiceState.IDLE


def test_review_all_option_and_no_overlapping_recordings(voice):
    v, jobs, _, submitted = voice
    v.config = VoiceConfig(review_transcript=True)
    v.microphone()
    v.microphone()
    assert len(jobs.calls) == 1
    jobs.emit("stage", state="LISTENING")
    v.poll()
    v.microphone()
    assert jobs.finish_requested
    jobs.emit("stage", state="TRANSCRIBING")
    jobs.emit("transcript", transcript=transcript().model_dump())
    jobs.emit("finished")
    v.poll()
    assert not submitted


@pytest.mark.parametrize("state", ["LISTENING", "TRANSCRIBING", "SPEAKING"])
def test_cancel_rejects_late_transcript_and_queued_speech(voice, state):
    v, jobs, _, submitted = voice
    v.start("listen" if state != "SPEAKING" else "speak", "Hello")
    v.transition(state)
    v.pending_reply = "outdated"
    v.cancel()
    jobs.emit("transcript", transcript=transcript().model_dump())
    jobs.emit("finished")
    v.poll()
    v.ready()
    assert not submitted and v.pending_reply is None
    assert v.state == VoiceState.IDLE


def test_typing_during_recognition_cancels_preserves_draft_and_no_late_submit(voice):
    v, jobs, _, submitted = voice
    v.microphone()
    v.edited()
    jobs.emit("transcript", transcript=transcript().model_dump())
    jobs.emit("finished")
    v.poll()
    assert jobs.cancelled and not submitted


def test_typed_turn_discards_previous_voice_and_speaks_its_own_reply(voice):
    v, jobs, _, submitted = voice
    v.microphone()
    v.begin_request()
    jobs.emit("transcript", transcript=transcript("close something").model_dump())
    v.reply("A new answer.")
    v.ready()
    assert len(jobs.calls) == 1
    jobs.emit("finished")
    v.poll()
    assert not submitted and jobs.calls[-1][2] == "A new answer."


def test_stop_speech_is_not_backend_task_cancellation(voice):
    v, jobs, _, _ = voice
    v.begin_request(voice=True)
    v.stop_speaking()
    assert v.state == VoiceState.PROCESSING and not jobs.cancelled
    v.reply("A completed result.")
    v.ready()
    assert not jobs.calls  # Stop speaking also suppresses the current queued reply.
    v.begin_request(voice=True)
    v.reply("The next requested result.")
    v.ready()
    v.stop_speaking()
    assert jobs.cancelled


@pytest.mark.parametrize(
    "failure",
    [
        "MICROPHONE_UNAVAILABLE_OR_DENIED",
        "NO_SPEECH_DETECTED",
        "STT_MODEL_MISSING",
        "VOICE_TIMEOUT",
        "SPEECH_TIMEOUT",
    ],
)
def test_failure_is_voice_only_no_transcript_or_retry(voice, failure):
    v, jobs, events, submitted = voice
    v.start("listen")
    jobs.emit("error", code=failure)
    jobs.emit("finished")
    v.poll()
    assert v.state == VoiceState.ERROR and not submitted
    assert any(failure in str(e) for e in events)
    assert len(jobs.calls) == 1


@pytest.mark.parametrize(
    "result",
    [
        None,
        {"text": "hello"},
        {"text": "", "language": "en", "uncertain": False, "seconds": 1},
        {"text": "open", "language": "en", "uncertain": 0, "seconds": 1},
    ],
)
def test_invalid_transcript_cannot_submit(voice, result):
    v, jobs, _, submitted = voice
    v.start("listen")
    jobs.emit("stage", state="LISTENING")
    jobs.emit("stage", state="TRANSCRIBING")
    jobs.emit("transcript", transcript=result)
    jobs.emit("finished")
    v.poll()
    assert not submitted and v.state == VoiceState.ERROR


def test_old_generation_and_closed_session_ignored(voice):
    v, jobs, _, submitted = voice
    v.start("listen")
    jobs.events.put((0, {"kind": "transcript", "transcript": transcript().model_dump()}))
    v.close()
    jobs.emit("finished")
    v.poll()
    assert not submitted and jobs.closed


def test_missing_model_discovery_and_disabled_voice_never_capture(voice):
    v, jobs, _, _ = voice
    v.devices["stt_ready"] = False
    v.microphone()
    assert not jobs.calls
    v.config = VoiceConfig(enabled=False)
    v.microphone()
    assert not jobs.calls


def test_persisted_settings_are_private_portable_and_strict(voice, tmp_path):
    v, _, _, _ = voice
    config = VoiceConfig(language=None, input_device='device "one"', volume=33)
    v.save(config)
    assert load_config(tmp_path) == config
    assert not list(tmp_path.glob("*.wav"))
    with pytest.raises(ValueError):
        VoiceConfig(recording_seconds=100000)


@pytest.mark.parametrize(
    "audio",
    [
        Audio(b""),
        Audio(b"x" * 6399),
        Audio(b"x" * 6400, sample_rate=48000),
        Audio(b"x" * 6400, channels=2),
        Audio(b"x" * 6400, sample_width=4),
        Audio(b"x" * 64001),
    ],
)
def test_audio_bounds_and_format(audio):
    with pytest.raises(ValueError):
        audio.validate(2)


@pytest.mark.parametrize("text", ["", "Jarvis", "hello\x00close", "x" * 4097])
def test_transcript_cannot_inject_protocol_or_empty_request(text):
    with pytest.raises(ValueError):
        request_text(text)


def test_speech_format_preserves_failures_and_warning_avoids_urls_or_invention():
    text = "I couldn't verify closure. No replay. [Source](https://example.com)."
    result = spoken_text(text)
    assert "couldn't verify" in result and "No replay" in result and "https" not in result
    assert "limitations" in spoken_text("Fine. " * 500 + "UNSAVED WORK")
    assert "full response" in spoken_text("```python\nsecret\n```").lower()
    assert needs_review(transcript("/review-media task manually-handled"), VoiceConfig())


@pytest.mark.parametrize(
    "payload",
    [
        "{}",
        '{"sequence":true,"state":"LISTENING"}',
        '{"sequence":1,"state":"open"}',
        '{"sequence":1,"state":"IDLE","text":"secret"}',
        '{"sequence":1,"sequence":2,"state":"IDLE"}',
    ],
)
def test_presentation_frames_are_strict_non_action_metadata(payload):
    with pytest.raises(ValueError):
        parse_control(PREFIX + payload)


def test_voice_control_never_enters_terminal_request_queue():
    from jarvis.terminal import TerminalInput

    reader = TerminalInput(io.StringIO(), lambda _: None)
    events = []
    reader.presentation = events.append
    frame = PREFIX + json.dumps({"sequence": 1, "state": "LISTENING"})
    assert reader._deliver(frame)
    assert events == [frame] and reader.lines.empty()
    reader._deliver("open Notepad")
    assert reader.lines.get_nowait()[1] == "open Notepad"


def test_worker_model_path_cannot_download_or_escape_private_root(tmp_path):
    from jarvis.voice_worker import model_path

    with pytest.raises(ValueError):
        model_path(tmp_path, VoiceConfig(model_directory="../outside"))
    with pytest.raises(ValueError):
        model_path(tmp_path, VoiceConfig())


def test_incomplete_model_never_enables_microphone(tmp_path):
    from jarvis.voice_worker import model_path

    directory = tmp_path / "speech" / "base.en"
    directory.mkdir(parents=True)
    for name in ("model.bin", "config.json", "tokenizer.json"):
        (directory / name).touch()
    with pytest.raises(ValueError, match="STT_MODEL_MISSING"):
        model_path(tmp_path, VoiceConfig())
    (directory / "vocabulary.txt").touch()
    assert model_path(tmp_path, VoiceConfig()) == directory


def test_sapi_is_plain_text_async_and_purged_after_stop(monkeypatch):
    from jarvis import voice_worker as worker

    cancelled = threading.Event()
    calls = []

    class Native:
        def GetVoices(self):
            return SimpleNamespace(Count=0)

        def GetAudioOutputs(self):
            return SimpleNamespace(Count=0)

        def Speak(self, text, flags):
            calls.append((text, flags))
            return 7

        def GetEvents(self, count):
            return None, 0

        def WaitUntilDone(self, timeout):
            cancelled.set()
            return False

    monkeypatch.setattr(worker, "sapi", Native)
    monkeypatch.setattr(worker, "sapi_event_source", lambda voice: voice)
    monkeypatch.setattr(worker, "emit", lambda *a, **k: None)
    worker.speak("<not executable SSML>", VoiceConfig(), cancelled)
    assert calls == [("<not executable SSML>", 19), ("", 3)]


def test_audio_job_is_single_flight_and_shutdown_does_not_wait_for_native_job(tmp_path):
    jobs = AudioJobs(tmp_path)
    jobs.active = True
    with pytest.raises(ValueError):
        jobs.start("listen", VoiceConfig())
    jobs.close()
    assert jobs.cancelled.is_set() and jobs.closed


def test_recording_failure_never_claims_listening(monkeypatch):
    from jarvis import voice_worker as worker

    events = []
    monkeypatch.setattr(worker, "emit", lambda *a, **k: events.append((a, k)))

    class DeniedStream:
        def __init__(self, **kwargs):
            raise RuntimeError("not permitted")

    fake = SimpleNamespace(
        check_input_settings=lambda **k: None,
        RawInputStream=DeniedStream,
        PortAudioError=RuntimeError,
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    with pytest.raises(ValueError, match="MICROPHONE_UNAVAILABLE_OR_DENIED"):
        worker.record(VoiceConfig(), threading.Event())
    assert not events


@pytest.mark.parametrize(
    "rate,status,silent", [(48000, False, False), (16000, True, False), (16000, False, True)]
)
def test_capture_resampling_disconnect_silence_and_native_cleanup(
    monkeypatch, rate, status, silent
):
    import numpy as np

    from jarvis import voice_worker as worker

    closed, events = [], []
    monkeypatch.setattr(worker, "emit", lambda *a, **k: events.append((a, k)))

    class DeviceError(Exception):
        pass

    class Abort(Exception):
        pass

    class Stop(Exception):
        pass

    def check(**kwargs):
        if rate != 16000:
            raise DeviceError()

    class Stream:
        active = False

        def __init__(self, **kwargs):
            self.callback = kwargs["callback"]

        def __enter__(self):
            data = (
                np.zeros(rate // 2, dtype=np.int16)
                if silent
                else np.full(rate // 2, 400, dtype=np.int16)
            )
            try:
                self.callback(data.tobytes(), len(data), None, status)
            except (Abort, Stop):
                pass
            return self

        def __exit__(self, *args):
            closed.append(True)

    fake = SimpleNamespace(
        check_input_settings=check,
        RawInputStream=Stream,
        PortAudioError=DeviceError,
        CallbackAbort=Abort,
        CallbackStop=Stop,
        query_devices=lambda *a: {"default_samplerate": rate},
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    if status or silent:
        with pytest.raises(ValueError, match="DISCONNECTED|NO_SPEECH"):
            worker.record(VoiceConfig(), threading.Event())
    else:
        audio = worker.record(VoiceConfig(), threading.Event())
        audio.validate()
        assert len(audio.pcm) == 16000 and audio.sample_rate == 16000
    assert closed == [True]
    assert events[0][1]["state"] == "LISTENING"


def test_cancelled_recording_does_not_open_stream(monkeypatch):
    from jarvis import voice_worker as worker

    stop = threading.Event()
    stop.set()
    monkeypatch.setitem(sys.modules, "sounddevice", SimpleNamespace())
    with pytest.raises(ValueError, match="VOICE_CANCELLED"):
        worker.record(VoiceConfig(), stop)


def test_error_then_late_valid_transcript_does_not_submit(voice):
    v, jobs, _, submitted = voice
    v.microphone()
    jobs.emit("stage", state="LISTENING")
    jobs.emit("stage", state="TRANSCRIBING")
    jobs.emit("error", code="VOICE_TIMEOUT")
    jobs.emit("transcript", transcript=transcript().model_dump())
    jobs.emit("finished")
    v.poll()
    assert v.state == VoiceState.ERROR and not submitted


def test_microphone_startup_progress_never_claims_listening_and_level_is_validated(voice):
    v, jobs, notices, submitted = voice
    v.microphone()
    jobs.emit("opening", step="opening_stream")
    v.poll()
    assert v.state == VoiceState.IDLE and not submitted
    jobs.emit("stage", state="LISTENING")
    jobs.emit("level", value=0.1)
    v.poll()
    assert v.state == VoiceState.LISTENING
    assert ("level", 0.1) in notices
    jobs.emit("level", value=float("nan"))
    v.poll()
    assert v.state == VoiceState.ERROR and not submitted and jobs.cancelled


def test_start_timeout_is_explained_and_late_audio_cannot_submit(voice):
    v, jobs, notices, submitted = voice
    v.microphone()
    jobs.emit("error", code="MICROPHONE_START_TIMEOUT")
    jobs.emit("stage", state="LISTENING")
    jobs.emit("finished")
    v.poll()
    assert v.state == VoiceState.ERROR and not submitted
    assert any("8 seconds" in text for kind, text in notices if kind == "notice")


def test_worker_preloads_native_audio_before_starting_control_reader(monkeypatch, tmp_path):
    from jarvis import voice_worker as worker

    order = []
    request = {"operation": "listen", "root": str(tmp_path), "config": VoiceConfig().model_dump()}
    monkeypatch.setattr(
        worker.sys,
        "stdin",
        SimpleNamespace(buffer=io.BytesIO(json.dumps(request).encode() + b"\n")),
    )
    monkeypatch.setattr(
        worker, "prepare", lambda operation, config: order.append("prepare_" + operation)
    )
    monkeypatch.setattr(
        worker.threading,
        "Thread",
        lambda **k: SimpleNamespace(start=lambda: order.append("reader")),
    )
    monkeypatch.setattr(worker, "model_path", lambda *a: tmp_path)
    monkeypatch.setattr(worker, "emit", lambda *a, **k: None)
    monkeypatch.setattr(worker, "record", lambda *a: Audio(bytes(32000)))
    monkeypatch.setattr(
        worker,
        "FasterWhisperSTT",
        lambda *a: SimpleNamespace(transcribe=lambda *a: (transcript(), {})),
    )
    worker.main()
    assert order == ["prepare_listen", "reader"]


def test_supervisor_applies_startup_deadline_before_recording_timeout(monkeypatch, tmp_path):
    from jarvis import voice_runtime

    monkeypatch.setattr(voice_runtime, "MICROPHONE_START_SECONDS", 0)

    class Process:
        stdin = io.BytesIO()
        stdout = io.BytesIO()

        def poll(self):
            return 0

        def wait(self, timeout):
            pass

    process = Process()
    jobs = AudioJobs(tmp_path, popen=lambda *a, **k: process)
    jobs.active = True
    jobs.run(1, {"operation": "listen", "config": {}, "root": str(tmp_path)}, VoiceConfig())
    events = []
    while not jobs.events.empty():
        events.append(jobs.events.get_nowait()[1])
    assert {"kind": "error", "code": "MICROPHONE_START_TIMEOUT"} in events
    assert events[-1] == {"kind": "finished"}
    assert not jobs.active and process.stdin.closed and process.stdout.closed


@pytest.mark.parametrize("late_delivery", [False, True])
def test_sapi_actual_start_event_drives_speaking_not_command_acceptance(monkeypatch, late_delivery):
    from jarvis import voice_worker as worker

    queued, pending, events, calls = [], [], [], []

    class Native:
        def GetVoices(self):
            return SimpleNamespace(Count=0)

        def GetAudioOutputs(self):
            return SimpleNamespace(Count=0)

        def Speak(self, text, flags):
            calls.append((text, flags))
            if text:
                assert not events
                # The entire short stream finishes before the worker polls.
                target = pending if late_delivery else queued
                target.extend(SimpleNamespace(eEventId=kind, ulStreamNum=7) for kind in (1, 2))
            return 7

        def GetEvents(self, count):
            assert count == 1
            return (queued.pop(0), 1) if queued else (None, 0)

        def GetStatus(self):
            return SimpleNamespace(hrLastResult=0), None

        def WaitUntilDone(self, timeout):
            queued.extend(pending)
            pending.clear()
            return True

    monkeypatch.setattr(worker, "sapi", Native)
    monkeypatch.setattr(worker, "sapi_event_source", lambda voice: voice)
    monkeypatch.setattr(worker, "emit", lambda kind, **data: events.append((kind, data)))
    worker.speak("A verified result.", VoiceConfig(), threading.Event())
    assert [kind for kind, _ in events] == ["stage", "done"]
    assert events[0][1] == {"state": "SPEAKING"}
    assert calls[-1] == ("", 3)


@pytest.mark.parametrize(
    ("queued", "result", "expected"),
    [
        ([], 0, "SPEECH_PLAYBACK_NOT_STARTED"),
        ([(1, 6), (2, 6)], 0, "SPEECH_PLAYBACK_NOT_STARTED"),
        ([(2, 7)], 0, "SPEECH_PLAYBACK_NOT_STARTED"),
        ([(1, 7)], 0, "SPEECH_TIMEOUT"),
        ([(1, 7), (2, 7)], -1, "SPEECH_OUTPUT_FAILED"),
    ],
)
def test_sapi_receipt_or_other_stream_never_proves_playback(monkeypatch, queued, result, expected):
    from jarvis import voice_worker as worker

    clock, events, calls = [0], [], []
    queue = [SimpleNamespace(eEventId=kind, ulStreamNum=stream) for kind, stream in queued]

    class Native:
        def GetVoices(self):
            return SimpleNamespace(Count=0)

        def GetAudioOutputs(self):
            return SimpleNamespace(Count=0)

        def Speak(self, text, flags):
            calls.append((text, flags))
            return 7

        def GetEvents(self, count):
            return (queue.pop(0), 1) if queue else (None, 0)

        def GetStatus(self):
            return SimpleNamespace(hrLastResult=result), None

        def WaitUntilDone(self, timeout):
            clock[0] += 2
            return True  # Acceptance/completion alone is insufficient.

    monkeypatch.setattr(worker, "sapi", Native)
    monkeypatch.setattr(worker, "sapi_event_source", lambda voice: voice)
    monkeypatch.setattr(worker.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(worker, "emit", lambda kind, **data: events.append((kind, data)))
    with pytest.raises(ValueError, match=expected):
        worker.speak("A result.", VoiceConfig(speech_seconds=10), threading.Event())
    assert not any(kind == "done" for kind, _ in events)
    assert calls == [("A result.", 19), ("", 3)]


def test_sapi_cancel_before_start_never_opens_output(monkeypatch):
    from jarvis import voice_worker as worker

    cancelled = threading.Event()
    cancelled.set()

    def unexpected():
        pytest.fail("Cancelled speech must not create SAPI or open output")

    monkeypatch.setattr(worker, "sapi", unexpected)
    worker.speak("A stale reply.", VoiceConfig(), cancelled)


def test_sapi_speak_failure_still_purges_owned_output(monkeypatch):
    from jarvis import voice_worker as worker

    calls = []

    class Native:
        def GetVoices(self):
            return SimpleNamespace(Count=0)

        def GetAudioOutputs(self):
            return SimpleNamespace(Count=0)

        def Speak(self, text, flags):
            calls.append((text, flags))
            if text:
                raise OSError("Output disconnected")

    monkeypatch.setattr(worker, "sapi", Native)
    monkeypatch.setattr(worker, "sapi_event_source", lambda voice: voice)
    with pytest.raises(OSError):
        worker.speak("A result.", VoiceConfig(), threading.Event())
    assert calls == [("A result.", 19), ("", 3)]


@pytest.mark.parametrize(
    "raw",
    [
        b'{"kind":"devices","inputs":[],"voices":[],"outputs":[],"stt_ready":false,"errors":[]}\n',
        b'{"kind":"propose_action"}\n',
    ],
)
def test_owned_audio_process_protocol_cleanup_and_no_agent_request(tmp_path, raw):
    processes = []

    class Process:
        def __init__(self):
            self.stdin, self.stdout = io.BytesIO(), io.BytesIO(raw)
            self.cleaned = False

        def poll(self):
            return 0

        def wait(self, timeout):
            self.cleaned = True

    def popen(command, **options):
        assert command[-1] == "jarvis.voice_worker" and options["shell"] is False
        process = Process()
        processes.append(process)
        return process

    jobs = AudioJobs(tmp_path, popen=popen)
    jobs.active = True
    jobs.run(
        0,
        {"operation": "inspect", "root": str(tmp_path), "config": VoiceConfig().model_dump()},
        VoiceConfig(),
    )
    assert not jobs.active and processes[0].cleaned
    assert processes[0].stdin.closed and processes[0].stdout.closed
    kinds = []
    while not jobs.events.empty():
        kinds.append(jobs.events.get_nowait()[1]["kind"])
    assert kinds[-1] == "finished"
    assert ("devices" in kinds) == (b'"devices"' in raw)
