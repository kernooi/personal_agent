"""Owned offline audio process; no agent, tools, web access or conversation history."""

import importlib.util
import json
import math
import os
import queue
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from jarvis.voice_data import Audio, Transcript, VoiceConfig


def emit(kind, **data):
    print(json.dumps({"kind": kind, **data}, ensure_ascii=False), flush=True)


def model_path(root, config):
    path = (root / config.model_directory).resolve()
    if not path.is_relative_to(root.resolve()) or not all(
        (path / name).is_file() for name in ("model.bin", "config.json", "tokenizer.json")
    ):
        raise ValueError("STT_MODEL_MISSING")
    if not any((path / name).is_file() for name in ("vocabulary.txt", "vocabulary.json")):
        raise ValueError("STT_MODEL_MISSING")
    return path


def input_devices():
    import sounddevice as sd

    apis = sd.query_hostapis()
    return [
        {"id": f"{apis[d['hostapi']]['name']} / {d['name']}", "index": i, "name": d["name"]}
        for i, d in enumerate(sd.query_devices())
        if d["max_input_channels"] > 0
    ]


def sapi():
    from comtypes.client import CreateObject

    return CreateObject("SAPI.SpVoice")


def tokens(collection):
    return [
        {"id": collection.Item(i).Id, "name": collection.Item(i).GetDescription()}
        for i in range(min(collection.Count, 128))
    ]


def input_format(config):
    import sounddevice as sd

    device = None
    if config.input_device:
        matches = [d for d in input_devices() if d["id"] == config.input_device]
        if len(matches) != 1:
            raise ValueError("MICROPHONE_CHANGED_OR_AMBIGUOUS")
        device = matches[0]["index"]
    rate = 16000
    try:
        sd.check_input_settings(device=device, channels=1, dtype="int16", samplerate=rate)
    except sd.PortAudioError:
        rate = int(sd.query_devices(device, "input")["default_samplerate"])
    if not 8000 <= rate <= 192000:
        raise ValueError("MICROPHONE_FORMAT_UNSUPPORTED")
    return device, rate


def pcm_audio(pcm, rate, maximum_seconds):
    import numpy as np

    if not isinstance(pcm, bytes) or len(pcm) % 2 or not 8000 <= rate <= 192000:
        raise ValueError("INVALID_AUDIO")
    samples = np.frombuffer(pcm, dtype="<i2")
    if rate != 16000:
        # PyAV is already supplied by faster-whisper. Its band-limited resampler
        # avoids folding high-frequency headset input into the speech band, and
        # flushing retains the filter tail instead of clipping final consonants.
        import av

        frame = av.AudioFrame.from_ndarray(samples.reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate = rate
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        converted = [*resampler.resample(frame), *resampler.resample(None)]
        samples = np.concatenate([part.to_ndarray().reshape(-1) for part in converted])
    audio = Audio(samples.astype("<i2").tobytes())
    audio.validate(maximum_seconds)
    return audio


def inspect(root, config):
    missing = [
        name
        for name in ("sounddevice", "faster_whisper", "numpy")
        if importlib.util.find_spec(name) is None
    ]
    result = {"inputs": [], "voices": [], "outputs": [], "stt_ready": False, "errors": []}
    if missing:
        result["errors"].append("VOICE_DEPENDENCIES_MISSING")
    else:
        try:
            model_path(root, config)
            result["stt_ready"] = True
        except ValueError:
            result["errors"].append("STT_MODEL_MISSING")
        try:
            result["inputs"] = input_devices()
        except Exception:
            result["errors"].append("MICROPHONE_UNAVAILABLE")
    try:
        voice = sapi()
        result["voices"] = tokens(voice.GetVoices())
        result["outputs"] = tokens(voice.GetAudioOutputs())
    except Exception:
        result["errors"].append("OFFLINE_TTS_UNAVAILABLE")
    if config.tts_provider == "kokoro":
        try:
            from jarvis.voice_neural import asset_directory

            asset_directory(root, config)
            if importlib.util.find_spec("kokoro_onnx") is None:
                raise ValueError("NEURAL_TTS_DEPENDENCIES_MISSING")
        except ValueError as exc:
            result["errors"].append(str(exc))
    if config.app_name_hints:
        try:
            from jarvis.voice_vocabulary import installed_names

            result["app_names"] = installed_names(root)
        except Exception:
            result["errors"].append("APP_VOCABULARY_UNAVAILABLE")
    emit("devices", **result)


def record(
    config,
    stop,
    progress=lambda step: None,
    level=lambda value: None,
    *,
    listening_state="LISTENING",
    deadline=None,
    require_endpoint=False,
):
    progress("loading_audio")
    import numpy as np
    import sounddevice as sd

    if stop.is_set():
        raise ValueError("VOICE_CANCELLED")

    progress("checking_device")
    device, rate = input_format(config)
    chunks, count, failed = [], 0, threading.Event()
    bound = rate * config.recording_seconds
    last_sound = [None]
    input_level = [0.0]

    def callback(data, frames, timing, status):
        nonlocal count
        if status:
            failed.set()
            raise sd.CallbackAbort
        if stop.is_set() or count + frames > bound:
            raise sd.CallbackStop
        chunks.append(bytes(data))
        count += frames
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        input_level[0] = min(1.0, float(np.sqrt(np.mean(samples * samples))) / 32768)
        if config.silence_seconds and input_level[0] * 32768 > 240:
            last_sound[0] = time.monotonic()

    try:
        progress("opening_stream")
        with sd.RawInputStream(
            samplerate=rate,
            channels=1,
            dtype="int16",
            device=device,
            callback=callback,
            blocksize=max(160, rate // 20),
        ) as stream:
            emit("stage", state=listening_state)  # Only after native stream start.
            until = time.monotonic() + config.recording_seconds
            if deadline is not None:
                until = min(until, deadline)
            next_level = 0
            ended_on_silence = False
            while not stop.wait(0.025) and time.monotonic() < until:
                if failed.is_set() or not stream.active:
                    break
                if time.monotonic() >= next_level:
                    level(round(input_level[0], 4))
                    next_level = time.monotonic() + 0.25
                if (
                    last_sound[0]
                    and config.silence_seconds
                    and (time.monotonic() - last_sound[0] >= config.silence_seconds)
                ):
                    ended_on_silence = True
                    break
    except Exception:
        raise ValueError("MICROPHONE_UNAVAILABLE_OR_DENIED") from None
    if failed.is_set():
        raise ValueError("MICROPHONE_DISCONNECTED_OR_OVERFLOW")
    samples = np.frombuffer(b"".join(chunks), dtype=np.int16).astype(np.float32)
    chunks.clear()
    if len(samples) < rate * 0.2 or np.sqrt(np.mean(samples * samples)) < 100:
        raise ValueError("NO_SPEECH_DETECTED")
    if require_endpoint and not ended_on_silence:
        raise ValueError("WAKE_UTTERANCE_LIMIT")  # Never submit a clipped command.
    return pcm_audio(samples.astype("<i2").tobytes(), rate, config.recording_seconds)


def transcribe(audio, root, config, cancel=lambda: False, *, model=None):
    import numpy as np
    from faster_whisper import WhisperModel

    audio.validate(config.recording_seconds)
    if cancel():
        raise ValueError("VOICE_CANCELLED")
    started = time.monotonic()
    model = model or WhisperModel(
        str(model_path(root, config)),
        device="cpu",
        compute_type="int8",
        cpu_threads=min(4, os.cpu_count() or 1),
        num_workers=1,
        local_files_only=True,
    )
    loaded = time.monotonic()
    if config.language not in {None, "en"} and not model.model.is_multilingual:
        raise ValueError("STT_LANGUAGE_INCOMPATIBLE")
    samples = np.frombuffer(audio.pcm, dtype="<i2").astype(np.float32) / 32768
    quality = {
        "audio_seconds": len(samples) / 16000,
        "audio_rms": float(np.sqrt(np.mean(samples * samples))),
        "audio_peak": float(np.max(np.abs(samples))),
        "clipped_fraction": float(np.mean(np.abs(samples) >= 0.999)),
    }
    from jarvis.voice_vocabulary import vocabulary

    terms = []
    for term in vocabulary(config.recognition_terms):
        candidate = ", ".join([*terms, term])
        # Bound complete terms using the active recognizer's actual tokenizer;
        # leave room for start/language/task/output tokens. Never rely on the
        # library silently slicing a long hint into an incomplete name.
        if len(model.hf_tokenizer.encode(" " + candidate).ids) <= 160:
            terms.append(term)
    hints = {"hotwords": ", ".join(terms)} if terms else {}
    segments, info = model.transcribe(
        samples,
        language=config.language,
        beam_size=config.stt_beam_size,
        condition_on_previous_text=False,
        vad_filter=True,
        # Keep soft beginnings/endings; optional bounded spelling hints are
        # decoder input only, never a post-hoc rewrite or an instruction to act.
        vad_parameters={"min_silence_duration_ms": 1000, "speech_pad_ms": 500},
        temperature=0,
        without_timestamps=True,
        **hints,
    )
    parts, uncertain = [], False
    minimum_logprob, maximum_no_speech = None, None
    for segment in segments:
        if cancel():
            raise ValueError("VOICE_CANCELLED")
        if not all(
            math.isfinite(value)
            for value in (segment.no_speech_prob, segment.avg_logprob, segment.compression_ratio)
        ):
            raise ValueError("STT_RESULT_INVALID")
        # Whisper already applies its joint no-speech/log-probability rule.
        # Do not silently drop an emitted word/segment on no_speech_prob alone:
        # an incomplete request can change meaning. Keep it as a review-only
        # draft when any existing confidence threshold is exceeded.
        uncertain |= (
            segment.no_speech_prob > 0.6
            or segment.avg_logprob < -0.8
            or segment.compression_ratio > 2.4
        )
        minimum_logprob = (
            segment.avg_logprob
            if minimum_logprob is None
            else min(minimum_logprob, segment.avg_logprob)
        )
        maximum_no_speech = (
            segment.no_speech_prob
            if maximum_no_speech is None
            else max(maximum_no_speech, segment.no_speech_prob)
        )
        parts.append(segment.text.strip())
        if sum(map(len, parts)) > 4096:
            raise ValueError("TRANSCRIPT_LIMIT")
    transcript = Transcript(
        text=" ".join(parts).strip(),
        language=info.language,
        uncertain=bool(uncertain),
        seconds=len(audio.pcm) / 32000,
    )
    if not transcript.text:
        raise ValueError("NO_SPEECH_DETECTED")
    return transcript, {
        "load_seconds": loaded - started,
        "stt_seconds": time.monotonic() - loaded,
        **quality,
        "minimum_logprob": minimum_logprob,
        "maximum_no_speech_probability": maximum_no_speech,
        "vocabulary_terms": len(terms),
    }


def sapi_event_source(voice):
    # sapi() loads the installed type library before this import. Read the native
    # queue directly: automation callbacks depend on COM message dispatch and can
    # be missed even when WaitUntilDone reports completion.
    from comtypes.gen.SpeechLib import (
        SPEI_END_INPUT_STREAM,
        SPEI_RESERVED1,
        SPEI_RESERVED2,
        SPEI_START_INPUT_STREAM,
        ISpVoice,
    )

    source = voice.QueryInterface(ISpVoice)
    # SAPI's SPFEI macro includes both reserved FLAGCHECK bits. Subscribe only to
    # start/end events, which carry no token/string resources to release.
    interests = (
        (1 << SPEI_RESERVED1)
        | (1 << SPEI_RESERVED2)
        | (1 << SPEI_START_INPUT_STREAM)
        | (1 << SPEI_END_INPUT_STREAM)
    )
    source.SetInterest(interests, interests)
    return source


def speak(
    text,
    config,
    cancel,
    started=lambda: emit("stage", state="SPEAKING"),
    *,
    report_done=True,
    pcm=None,
    deadline=None,
):
    if not isinstance(text, str) or not 1 <= len(text) <= 2400:
        raise ValueError("SPEECH_TEXT_LIMIT")
    if cancel.is_set():
        return
    voice = sapi()
    for field, collection, setting in (
        ("Voice", voice.GetVoices(), config.voice if pcm is None else ""),
        ("AudioOutput", voice.GetAudioOutputs(), config.output_device),
    ):
        if setting:
            matches = [
                collection.Item(i)
                for i in range(collection.Count)
                if collection.Item(i).Id == setting
            ]
            if len(matches) != 1:
                raise ValueError("VOICE_OR_OUTPUT_DEVICE_CHANGED")
            setattr(voice, field, matches[0])
    voice.Volume, voice.Rate = config.volume, config.rate if pcm is None else 0
    source = sapi_event_source(voice)
    start_time = time.monotonic()
    playback_time, ended = None, False
    until = (
        min(start_time + config.speech_seconds, deadline)
        if deadline is not None
        else start_time + config.speech_seconds
    )
    start_until = min(until, start_time + 8)
    if cancel.is_set():
        return
    try:
        if pcm is None:
            stream = voice.Speak(text, 1 | 2 | 16)  # Async, purge, plain text; never XML/SSML.
        else:
            audio_stream = pcm_stream(pcm, config.speech_seconds)
            if cancel.is_set() or time.monotonic() >= until:
                raise ValueError("VOICE_CANCELLED" if cancel.is_set() else "SPEECH_TIMEOUT")
            stream = voice.SpeakStream(audio_stream, 1 | 2)
        while True:
            if cancel.is_set():
                return
            # A one-element read matches the generated COM signature. Draining
            # the queue also catches a short stream that ended between polls.
            for _ in range(64):
                event, fetched = source.GetEvents(1)
                if not fetched:
                    break
                if cancel.is_set():
                    return
                if event.ulStreamNum != stream:
                    continue
                if event.eEventId == 1 and playback_time is None:  # START_INPUT_STREAM
                    playback_time = time.monotonic()
                    started()
                elif event.eEventId == 2:  # END_INPUT_STREAM
                    ended = True
            complete = voice.WaitUntilDone(20)
            if cancel.is_set():
                return
            status, _ = source.GetStatus()
            if status.hrLastResult < 0:
                raise ValueError("SPEECH_OUTPUT_FAILED")
            if complete and ended and playback_time is not None:
                completed_at = time.monotonic()
                break
            if playback_time is None and time.monotonic() >= start_until:
                raise ValueError("SPEECH_PLAYBACK_NOT_STARTED")
            if time.monotonic() >= until:
                raise ValueError("SPEECH_TIMEOUT")
            if cancel.wait(0.01):
                return
    finally:
        voice.Speak("", 1 | 2)
    if cancel.is_set():
        return
    if report_done:
        emit(
            "done",
            metrics={
                "start_seconds": playback_time - start_time,
                "speech_seconds": time.monotonic() - start_time,
            },
        )
    return completed_at


class FasterWhisperSTT:
    def __init__(self, root):
        self.root = root

    def transcribe(self, audio, config, cancel):
        return transcribe(audio, self.root, config, cancel)


class SapiTTS:
    def speak(self, text, config, cancel, started):
        return speak(text, config, cancel, started)


def pcm_stream(pcm, maximum_seconds):
    from array import array

    from comtypes.client import CreateObject
    from comtypes.gen.SpeechLib import SAFT24kHz16BitMono

    if not isinstance(pcm, bytes) or not 480 <= len(pcm) <= 48000 * maximum_seconds or len(pcm) % 2:
        raise ValueError("NEURAL_AUDIO_INVALID")
    stream = CreateObject("SAPI.SpMemoryStream")
    stream.Format.Type = SAFT24kHz16BitMono
    stream.SetData(array("B", pcm))
    return stream


def speak_wake_acknowledgement(config, cancel, *, pcm=None):
    """Fixed local output; caller must first release its owned microphone."""
    try:
        options = {} if pcm is None else {"pcm": pcm}
        return speak(
            "Yes sir.",
            config.model_copy(update={"speech_seconds": min(config.speech_seconds, 10)}),
            cancel,
            report_done=False,
            **options,
        )
    except ValueError:
        raise
    except Exception:
        raise ValueError("SPEECH_OUTPUT_FAILED") from None


def acknowledge_wake(stream, config, finish, cancel, *, pcm=None):
    """Pause this owned input stream before the fixed local wake response."""
    stream.stop()
    if finish.is_set() or cancel.is_set():
        return False
    emit("stage", state="WAKE_ACKNOWLEDGING")
    if pcm is None:
        speak_wake_acknowledgement(config, cancel)
    else:
        speak_wake_acknowledgement(config, cancel, pcm=pcm)
    return not finish.is_set() and not cancel.is_set()


def whisper_wake(root, config, finish, cancel, *, ack_pcm=None):
    """Bounded local recognition; only wake-addressed text reaches the GUI."""
    import numpy as np
    import sounddevice as sd
    from faster_whisper import WhisperModel

    from jarvis.voice_wake import SpeechBuffer, WakeGate

    model = WhisperModel(
        str(model_path(root, config)),
        device="cpu",
        compute_type="int8",
        cpu_threads=min(4, os.cpu_count() or 1),
        num_workers=1,
        local_files_only=True,
    )
    gate = WakeGate(config.wake_followup_seconds, wake_call=config.wake_call)
    until = time.monotonic() + config.wake_session_seconds
    hard_until = until + 10 + config.wake_followup_seconds
    emit("opening", step="checking_device")
    device, rate = input_format(config)
    segments = SpeechBuffer(
        rate, config.recording_seconds, config.wake_silence_seconds, config.wake_minimum_rms
    )
    frames_queue = queue.Queue(maxsize=80)  # Four seconds at 50 ms per callback.
    failed = threading.Event()
    approved = None

    def callback(data, frames, timing, status):
        if finish.is_set() or cancel.is_set():
            raise sd.CallbackStop
        if status:
            failed.set()
            raise sd.CallbackAbort
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        rms = float(np.sqrt(np.mean(samples * samples)))
        try:
            frames_queue.put_nowait((bytes(data), frames, rms, time.monotonic()))
        except queue.Full:
            failed.set()
            raise sd.CallbackAbort from None  # Never drop a command's beginning silently.

    emit("opening", step="opening_stream")
    try:
        with sd.RawInputStream(
            samplerate=rate,
            channels=1,
            dtype="int16",
            device=device,
            callback=callback,
            blocksize=max(160, rate // 20),
        ) as stream:
            emit("stage", state="WAKE_LISTENING")
            next_level, awaiting = 0, False
            while not finish.is_set() and not cancel.is_set() and time.monotonic() < until:
                if failed.is_set() or not stream.active:
                    raise ValueError("MICROPHONE_DISCONNECTED_OR_OVERFLOW")
                if awaiting and time.monotonic() >= gate.until and not segments.active:
                    awaiting = False
                    emit("stage", state="WAKE_LISTENING")
                try:
                    pcm, frames, rms, captured_at = frames_queue.get(timeout=0.05)
                except queue.Empty:
                    continue
                if captured_at >= next_level:
                    emit("level", value=round(min(1.0, rms / 32768), 4))
                    next_level = captured_at + 0.25
                clip = segments.feed(pcm, frames, rms, captured_at)
                if clip is None:
                    continue
                if not clip.pcm:
                    gate.until = 0
                    continue
                audio = pcm_audio(clip.pcm, rate, config.recording_seconds)
                emit("stage", state="WAKE_CHECKING")  # Mic remains on; bounded queue fills.
                try:
                    result, metrics = transcribe(audio, root, config, cancel.is_set, model=model)
                    accepted, armed = gate.accept(result, clip.ended_at, started_at=clip.started_at)
                    del result
                except ValueError as exc:
                    if str(exc) != "NO_SPEECH_DETECTED":
                        raise
                    accepted, armed = None, False
                finally:
                    audio = clip = None
                if finish.is_set() or cancel.is_set():
                    return
                if failed.is_set() or not stream.active:
                    raise ValueError("MICROPHONE_DISCONNECTED_OR_OVERFLOW")
                if accepted:
                    approved = accepted, metrics
                    break
                awaiting = armed or gate.until > time.monotonic()
                if armed:
                    if not acknowledge_wake(stream, config, finish, cancel, pcm=ack_pcm):
                        return
                    # Discard queued pre-acknowledgement speech. The followup
                    # grant begins only after actual microphone restart.
                    while True:
                        try:
                            frames_queue.get_nowait()
                        except queue.Empty:
                            break
                    segments = SpeechBuffer(
                        rate,
                        config.recording_seconds,
                        config.wake_silence_seconds,
                        config.wake_minimum_rms,
                    )
                    emit("opening", step="opening_stream")
                    if finish.is_set() or cancel.is_set():
                        return
                    stream.start()
                    if not stream.active:
                        raise ValueError("MICROPHONE_UNAVAILABLE_OR_DENIED")
                    gate.arm(time.monotonic())
                    until = min(hard_until, max(until, gate.until))
                    emit("wake_ready")
                emit("stage", state="LISTENING" if awaiting else "WAKE_LISTENING")
    except ValueError:
        raise
    except Exception:
        raise ValueError("MICROPHONE_UNAVAILABLE_OR_DENIED") from None
    finally:
        # Clearing this owned queue cannot expose audio or keep it past the session.
        while True:
            try:
                frames_queue.get_nowait()
            except queue.Empty:
                break
    if approved and not finish.is_set() and not cancel.is_set():
        accepted, metrics = approved
        # The actual capture context has closed before any GUI request can submit.
        emit("stage", state="TRANSCRIBING")
        emit("transcript", transcript=accepted.model_dump(), metrics=metrics, addressed=True)
    else:
        emit("done")


@contextmanager
def prepare_wake_command(config, finish, cancel):
    """Reserve an INACTIVE input before wake recognition; never capture during TTS."""
    import numpy as np
    import sounddevice as sd

    emit("opening", step="checking_device")
    device, rate = input_format(config)
    frames_queue = queue.Queue(maxsize=80)
    failed, armed = threading.Event(), threading.Event()

    def callback(data, frames, timing, status):
        if cancel.is_set() or finish.is_set():
            raise sd.CallbackStop
        if not armed.is_set():
            failed.set()
            raise sd.CallbackAbort  # Never retain input from an unstarted reserved stream.
        if status:
            failed.set()
            raise sd.CallbackAbort
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        rms = float(np.sqrt(np.mean(samples * samples)))
        try:
            frames_queue.put_nowait((bytes(data), frames, rms, time.monotonic()))
        except queue.Full:
            failed.set()
            raise sd.CallbackAbort from None

    emit("opening", step="opening_stream")
    stream = None
    try:
        if cancel.is_set() or finish.is_set():
            raise ValueError("VOICE_CANCELLED")
        stream = sd.RawInputStream(
            samplerate=rate,
            channels=1,
            dtype="int16",
            device=device,
            callback=callback,
            blocksize=max(160, rate // 20),
        )  # Constructor opens the device but DOES NOT start recording.
        if stream.active or failed.is_set():
            raise ValueError("WAKE_INPUT_NOT_INACTIVE")
        yield stream, rate, frames_queue, failed, armed
    except ValueError:
        raise
    except Exception:
        raise ValueError("MICROPHONE_UNAVAILABLE_OR_DENIED") from None
    finally:
        original_error = sys.exc_info()[0] is not None
        try:
            if stream is not None:
                stream.close()
        except Exception:
            if not original_error:
                raise ValueError("MICROPHONE_INPUT_DID_NOT_STOP") from None
        finally:
            armed.clear()
            while True:
                try:
                    frames_queue.get_nowait()
                except queue.Empty:
                    break


def record_wake_command(config, finish, cancel, prepared, acknowledgement_completed_at):
    """Start the reserved input immediately after verified acknowledgement completion."""
    from jarvis.voice_wake import SpeechBuffer

    stream, rate, frames_queue, failed, armed = prepared
    segments = SpeechBuffer(
        rate, config.recording_seconds, config.wake_silence_seconds, config.wake_minimum_rms
    )
    emit("opening", step="opening_stream")
    try:
        if cancel.is_set() or finish.is_set():
            return None
        if stream.active or armed.is_set():
            raise ValueError("WAKE_INPUT_NOT_INACTIVE")
        armed.set()
        ready_until = acknowledgement_completed_at + 8
        stream.start()
        # LISTENING is announced only when the first real input block arrives.
        start_until = hard_until = None
        next_level = 0
        while not cancel.is_set() and not finish.is_set():
            now = time.monotonic()
            if hard_until is not None and now >= hard_until:
                return None
            if failed.is_set() or not stream.active:
                raise ValueError("MICROPHONE_DISCONNECTED_OR_OVERFLOW")
            try:
                pcm, frames, rms, captured_at = frames_queue.get(timeout=0.05)
            except queue.Empty:
                if start_until is None and time.monotonic() >= ready_until:
                    raise ValueError("MICROPHONE_START_TIMEOUT") from None
                if (
                    start_until is not None
                    and time.monotonic() >= start_until
                    and not segments.active
                    and not segments.signal_frames
                ):
                    return None
                continue
            if cancel.is_set() or finish.is_set():
                return None
            if start_until is None:
                if captured_at >= ready_until:
                    raise ValueError("MICROPHONE_START_TIMEOUT")
                start_until = captured_at + config.wake_followup_seconds
                hard_until = (
                    start_until + config.recording_seconds + config.wake_silence_seconds + 1
                )
                emit("stage", state="LISTENING")
                emit(
                    "wake_ready",
                    metrics={
                        "command_input_ready_seconds": max(
                            0.0, captured_at - acknowledgement_completed_at
                        )
                    },
                )
            if captured_at >= start_until and not segments.active and not segments.signal_frames:
                return None
            if captured_at >= next_level:
                emit("level", value=round(min(1.0, rms / 32768), 4))
                next_level = captured_at + 0.25
            clip = segments.feed(pcm, frames, rms, captured_at)
            if clip is not None:
                if not clip.pcm:
                    raise ValueError("WAKE_UTTERANCE_LIMIT")
                return pcm_audio(clip.pcm, rate, config.recording_seconds)
        return None
    except ValueError:
        raise
    except Exception:
        raise ValueError("MICROPHONE_UNAVAILABLE_OR_DENIED") from None


def native_wake_command(config, finish, cancel, prepared, *, ack_pcm=None):
    from jarvis.voice_keyword import WindowsWakeDetector

    detector = WindowsWakeDetector(config, cancel, emit)
    try:
        emit("opening", step="opening_stream")
        detector.open()
        matched = detector.wait(time.monotonic() + config.wake_session_seconds)
    except Exception as exc:
        try:
            detector.close()
        except Exception:
            pass  # Preserve the original failure; the owned worker exits next.
        if isinstance(exc, ValueError):
            raise
        raise ValueError("WAKE_ENGINE_START_FAILED") from None
    else:
        detector.close()  # Release native capture before any speaker or second mic.
    if cancel.is_set() or finish.is_set():
        return
    if not matched:
        return
    completed_at = (
        speak_wake_acknowledgement(config, cancel)
        if ack_pcm is None
        else speak_wake_acknowledgement(config, cancel, pcm=ack_pcm)
    )
    if cancel.is_set() or finish.is_set():
        return
    if type(completed_at) not in {int, float}:
        raise ValueError("SPEECH_OUTPUT_FAILED")
    audio = record_wake_command(config, finish, cancel, prepared, completed_at)
    if cancel.is_set() or finish.is_set():
        return
    if audio is None:
        emit("wake_status", status="EXPIRED")
    return audio


def wake(root, config, finish, cancel):
    ack_pcm = None
    if cancel.is_set() or finish.is_set():
        return
    if config.tts_provider == "kokoro":
        from jarvis.voice_neural import acknowledgement

        ack_pcm = acknowledgement(root, config, cancel)
    if config.wake_provider == "whisper":
        return whisper_wake(root, config, finish, cancel, ack_pcm=ack_pcm)
    if cancel.is_set() or finish.is_set():
        return
    with prepare_wake_command(config, finish, cancel) as prepared:
        if cancel.is_set() or finish.is_set():
            return
        audio = native_wake_command(config, finish, cancel, prepared, ack_pcm=ack_pcm)
    if cancel.is_set() or finish.is_set():
        return
    if audio is None:
        emit("done")
        return
    emit("stage", state="TRANSCRIBING")
    result, metrics = FasterWhisperSTT(root).transcribe(audio, config, cancel.is_set)
    del audio
    if not cancel.is_set() and not finish.is_set():
        emit("transcript", transcript=result.model_dump(), metrics=metrics, addressed=True)


def prepare(operation, config=None):
    # NumPy's native module initialization can deadlock on Windows while another
    # thread blocks in buffered stdin. Load speech libraries before the control
    # reader starts. Parent supervision still bounds/cancels this startup phase.
    if operation in {"listen", "wake"}:
        import faster_whisper  # noqa: F401
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        import sounddevice  # noqa: F401
    if config is not None and config.tts_provider == "kokoro" and operation in {"wake", "speak"}:
        import kokoro_onnx  # noqa: F401


def main():
    # Both speech engines use only installed local artifacts. No lazy hub fallback.
    os.environ.update(HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", TRANSFORMERS_OFFLINE="1")
    request = json.loads(sys.stdin.buffer.readline(32769))
    config = VoiceConfig.model_validate(request["config"], strict=True)
    if config.app_name_hints and request.get("app_names"):
        from jarvis.voice_vocabulary import valid_term, vocabulary

        names = request["app_names"]
        if (
            not isinstance(names, list)
            or len(names) > 64
            or any(not valid_term(name) for name in names)
        ):
            raise ValueError("APP_VOCABULARY_INVALID")
        # Worker-scoped only: do not write discovered OS names to voice.toml,
        # chat history, prompts or journals. No process paths/arguments enter STT.
        config = config.model_copy(
            update={"recognition_terms": vocabulary(config.recognition_terms, names)}
        )
    root = Path(request["root"])
    finish, cancel = threading.Event(), threading.Event()
    if request["operation"] in {"listen", "wake"}:
        emit("opening", step="loading_audio")
    prepare(request["operation"], config)

    def input_control():
        for raw in iter(lambda: sys.stdin.buffer.readline(32), b""):
            if raw.strip() == b"finish":
                finish.set()
            elif raw.strip() == b"cancel":
                cancel.set()
                finish.set()
        cancel.set()
        finish.set()

        def parent_gone():
            time.sleep(1.25)
            os._exit(0)  # Only this owned audio worker, even if STT is blocked.

        threading.Thread(target=parent_gone, daemon=True).start()

    threading.Thread(target=input_control, daemon=True).start()
    if request["operation"] == "inspect":
        inspect(root, config)
    elif request["operation"] == "wake":
        if config.interaction_mode != "wake_word" or not config.wake_enabled:
            raise ValueError("WAKE_NOT_ENABLED")
        wake(root, config, finish, cancel)
    elif request["operation"] == "listen":
        model_path(root, config)  # Missing assets never activate the microphone.
        audio = record(
            config,
            finish,
            lambda step: emit("opening", step=step),
            lambda value: emit("level", value=value),
        )
        if cancel.is_set():
            return
        emit("stage", state="TRANSCRIBING")
        result, metrics = FasterWhisperSTT(root).transcribe(audio, config, cancel.is_set)
        if not cancel.is_set():
            emit("transcript", transcript=result.model_dump(), metrics=metrics)
    elif request["operation"] == "speak":
        if config.tts_provider == "kokoro":
            from jarvis.voice_neural import speak_reply

            speak_reply(
                root,
                request["text"],
                config,
                cancel,
                lambda: emit("stage", state="SPEAKING"),
                speak,
                emit,
            )
        else:
            SapiTTS().speak(
                request["text"], config, cancel, lambda: emit("stage", state="SPEAKING")
            )
    else:
        raise ValueError("VOICE_OPERATION_INVALID")


def re_safe(value):
    return value and len(value) <= 80 and all(c.isupper() or c == "_" for c in value)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        from jarvis.voice_keyword import WakeSetupError

        code = (
            str(exc) if isinstance(exc, ValueError) and re_safe(str(exc)) else "VOICE_WORKER_FAILED"
        )
        if isinstance(exc, WakeSetupError):
            emit("error", code=code, setup=exc.diagnostic.model_dump())
        else:
            emit("error", code=code)
    finally:
        # A daemon control reader may still be waiting on stdin. All native
        # streams/playback were closed above; avoid buffered-reader shutdown hangs.
        sys.stdout.flush()
        os._exit(0)
