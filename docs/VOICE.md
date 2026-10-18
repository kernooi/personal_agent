# Local voice interaction

## App-name spelling context (2026-10-18)

Attended app-spelling r1 **FAILED (1/4 exact)**. The first Discord request passed;
the second lost leading words, and both literal-cord cases differed. The owner
confirmed literal "this cord" was consistently heard as "Discord". Automatic
app-name hints therefore now default OFF and are explicitly disabled in this PC's
private voice.toml, with backup and all other settings preserved. Settings labels
them experimental; explicit custom spellings remain optional and can also bias
recognition. Removing the bias is not evidence that the original homophone issue
is fixed. No additional native check has run after disabling hints.

Owner clarified "Discord" becomes "this cord". New optional bounded spelling hints
feed the existing faster-whisper decoder, without rewriting transcripts, adding
an LLM or retrying audio. Friendly labels come from the existing fixed read-only
enabled Windows application catalog; only names enter the speech worker, never
paths, arguments, window text, conversation history or permissions. The GUI's
metadata discovery obtains them once and forwards them to recording workers only;
automatic vocabulary is transient, not added to private settings/history/logs.
Explicit optional Settings spellings are private user preferences.

Settings adds **Names and spellings (optional, one per line)** for names such as
personal playlists, and **Use installed application names as speech spelling
hints** (now labelled experimental). Defaults: app_name_hints=false,
recognition_terms=[]. Owner terms first,
compact OS names next; at most 64 entries/512 characters. The active tokenizer
keeps complete names within 160 tokens, below the decoder's context cutoff.
Disable automatic hints independently of explicit spellings. Existing local
model, acoustic confidence thresholds, whole-request review and broker gates stay.
No hardcoded Discord alias or literal-this-cord replacement, no new download.

Read-only catalog inspection on this PC supplied 54 names/509 characters and
included Discord and Spotify. Full fake suite: 1720 passed in 61.67s. Lint/format
(224 files), dependency checks pass. Tests cover fake generic app names, input and
IPC bounds, privacy, disable behavior, fixed read-only discovery, token budget,
literal-word preservation and GUI persistence of explicit spellings.

Frozen app-spelling corpus v1 has two Discord requests and two literal cord
sentences, retaining a strict 100% exact-match gate. Synthetic same-audio comparison:

```powershell
.\.venv\Scripts\python.exe scripts\Evaluate-JarvisSpelling.py --synthetic --report docs\evaluations\m6-spelling-synthetic-r1.json
```

Passed all four cases with AND without hints (8 total exact checks, zero word
errors or uncertainty). That establishes no synthetic regression, not a measured
improvement on the owner's accent. Warm decode 1.709–1.751s without hints versus
1.949–2.177s with 54 actual tokenizer-accepted names. No mic/speakers/apps used.
The earlier general synthetic 5/7 and attended 2/7 failures remain preserved.
The --corpus app-spelling microphone lab cannot execute its spoken app requests.
Its attended r1 report preserves all four transcripts' match/quality metadata,
without saving their words or audio. Handoff was 65.5–66.8ms, with no clipping,
worker errors or uncertainty flags despite wrong words. Confidence scores did not
detect these homophones. Native result is recorded in BUILD_LOG.

## Command recognition correction (2026-10-18)

Owner reported frequent incorrect recognition. Inspection found the compact base.en
model, beam search 3, linear interpolation for non-16k microphone formats, and a
private command endpoint after only 0.5s of quiet. The capture endpoint also used
callback wall-clock gaps instead of actual quiet audio-frame duration. These are
concrete reliability issues; the owner's speech failure was not recorded, so no
single cause is claimed.

SpeechBuffer now counts actual quiet frames; delayed callbacks cannot invent
silence. Private wake_silence_seconds is now 1.0 with backup, so a 650ms hesitation
keeps both parts of the same sentence. This changes the pause at the END of a
command, not readiness after "Yes sir." PyAV's already-installed band-limited
resampler replaces interpolation for native headset rates and flushes its tail.
16k input is unchanged. stt_beam_size=5 is strict/bounded 1–8; VAD retains 500ms
padding, previous-text conditioning stays off. An emitted high-no-speech segment
is retained as an uncertain draft instead of silently deleting it and submitting
the rest. Confidence thresholds are not loosened; invalid nonfinite scores fail.
GUI labels the setting "Command pause before sending (seconds)".

Owner explicitly approved small.en download/selection. Four files (486098798
bytes total) were downloaded from Systran/faster-whisper-small.en at revision
d1d751a5f8271d482d14ca55d9e2deeebbae577f. Verified model.bin is 483545366 bytes,
SHA-256 62b2a45b05ee59acb4a5341b33ee35e041395d378d418a18acfe4c9e768ee37a.
Installed under private speech/small.en and selected through model_directory;
base.en preserved. Setup saves a private config backup and retains Michael,
microphone/output tokens and all other wake settings. No new dependency, GPU
stack, cloud speech, global changes or startup downloads. Exact executed command:

```powershell
.\.venv\Scripts\python.exe scripts\Setup-JarvisVoice.py --download-small-en --approved --select
```

1700 deterministic tests passed in 63.72s; 162 focused voice tests passed in 4.04s.
Lint/format/dependency checks pass. Regression evidence includes resampling speech-
band preservation/high-frequency rejection, pause continuity, scheduling jitter,
whole-request confidence review, cancellation and existing wake/Stop/UI lifecycle.

Frozen seven-sentence synthetic comparison uses the same in-memory Michael audio
for both installed recognizers, with no mic/speaker or normal transcript storage:

```powershell
.\.venv\Scripts\python.exe scripts\Evaluate-JarvisRecognition.py --synthetic --report docs\evaluations\m6-recognition-synthetic-r1.json
```

The strict report FAILED: each model exactly matched 5/7, with word error rate
0.1087. Small.en corrected the song title missed by base.en. Its general-question
failure was numeric spelling (6/8 vs six/eight), confirmed by a synthetic-only
diagnostic; the original exact-match failure/gate is preserved. Both missed the
unusual playlist name; small.en heard "Fab J-pop". Warm decoder times were about
0.6–0.7s for base vs 1.9–2.0s for small on these clips, excluding model load and
capture. This is not evidence of the owner's microphone/accent accuracy or a
general quality improvement. No acceptance threshold was relaxed or report erased.

An attended recognition-only lab is prepared and launched after fresh owner
readiness. It uses the ordinary wake/ack/command pipeline for seven displayed
sentences and NEVER forwards transcripts to chat/tools. It displays recognized
words transiently, saves only fixed case IDs/matches/uncertainty/timing, and retains
all failures. Stop/Esc/global stop close the owned worker; timeout is bounded.

```powershell
.\.venv\Scripts\python.exe scripts\Test-JarvisRecognition.py --attended --report docs\evaluations\m6-recognition-attended-r1.json
```

Actual attended outcome is recorded in BUILD_LOG; overall M6 remains unqualified.
Attended r1 completed with all seven transcripts but only 2/7 exact matches, no
worker errors, and 65.5–67.5ms post-ack input readiness. That gate FAILED. No
transcripts were saved, so word versus formatting errors need operator feedback
or a separate attended diagnostic; do not infer a cause or advertise accuracy as
fixed. Optional --case selects a labelled diagnostic subset, never qualification
of the full corpus. New fixed error categories explain missing words, contraction
and numeric formatting without changing exact-match scoring. Safe duration,
amplitude/clipping and confidence metadata is available for diagnostics; normal
GUI logs retain only existing timing fields, not those values or speech content.
Sources: [faster-whisper](https://github.com/SYSTRAN/faster-whisper),
[pinned recognition source](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py),
[small.en artifacts](https://huggingface.co/Systran/faster-whisper-small.en).

## Natural local speech (2026-10-18)

The owner approved the proposed Kokoro installation/download and chose American
male rather than British male. Installed kokoro-onnx 0.6.1 and bundled Windows
espeakng-loader 0.2.4 dependencies through the generated hash lock in .venv. No
system speech installation or global settings changes. Approved release assets
(353,719,767 bytes total) are SHA-256 verified under private speech/kokoro-v1.0.
Model identity, exact sizes/hashes and fixed upstream release URLs live in
voice_neural.py; setup is never a runtime/model-callable operation.

Selected tts_provider="kokoro", neural_voice="am_michael" in private voice.toml;
preserved input/output tokens, wake phrase, timing, rate and volume, with a private
backup. Core default remains windows_sapi for legacy files. GUI Settings adds
Speech engine and Natural voice; the Windows voice field applies only to SAPI TTS.
Neural synthesis uses only CPUExecutionProvider with two inference threads, without
loading another GPU model. The existing SAPI output token still selects the exact
output: neural PCM is passed as an in-memory 24kHz/16-bit/mono stream. SAPI supplies
playback only, not the neural voice. Matching stream start/end and HRESULT checks,
purge-on-stop and the owned worker/supervisor remain. SPEAKING is not announced at
synthesis acceptance. Startup/discovery never downloads models or records audio.

The setup-only fixed synthetic "Yes sir." WAV and identity receipt are cached
privately. Wake reads that cache before microphone setup; microphone stays paused
through verified output, then uses the existing prepared-input handoff. No ordinary
reply audio/text is cached. A changed natural voice/rate without a cache synthesizes
the fixed acknowledgement before microphone activation, within existing startup
bounds; it does not insert work after speech completion. Missing/changed assets,
voice or output fail visibly rather than switching voice/provider/device silently.
You can explicitly select Windows offline voice in Settings to restore that engine.

Exact approved setup command (already executed on this PC):

```powershell
.\.venv\Scripts\python.exe scripts\Setup-JarvisNeuralVoice.py --approved --voice am_michael --select
```

Setup validates assets and CPU synthesis without microphone or speakers. Initial
engine load was 2.076s and fixed acknowledgement synthesis 2.619s (1.033s audio).
An independent synthetic run loaded in 2.221s, generated a greeting in 2.896s
(3.349s audio), then fixed acknowledgement in 0.921s and another sentence in
2.626s. These are synthesis timings, not audible latency or quality guarantees.
General replies load the engine per owned job and use bounded chunks; CPU generation
can add a pause before/between chunks. The existing speech deadline still applies.
Neural acknowledgement-to-mic timing still needs attended validation; the earlier
67ms SAPI-TTS result does not qualify the changed voice. The separate speaker/
interruption validation below is now complete.
Full fake suite: 1684 passed; final focused voice suite: 147 passed. No text/action
model contract changed; all six preserved combined reports match current contracts.

Prepared speaker-only lab (owner separately confirmed readiness):

```powershell
.\.venv\Scripts\python.exe scripts\Test-JarvisSpeech.py --attended --report docs\evaluations\m6-neural-speech-michael-r1.json
```

It plays fixed synthetic text, permits a physical Stop check, saves only events/
timings/operator checkboxes, and never opens a microphone or app/media/screen tool.
See BUILD_LOG.md for the actual outcome; mocks/synthesis alone do not prove sound.

Attended outcome: four sample completions and one interruption verified through
native stream events. Operator confirmed hearing Michael clearly and hearing Stop
work; stopped worker exited in 0.232s. No errors or microphone/tool effects. Actual
greeting jobs began playback 3.813–4.134s after worker synthesis began (excluding
process launch), so general neural replies have preparation latency. The fixed
wake acknowledgement is already cached; its new mic handoff has not been measured.
Restart the ordinary GUI to use the selected voice. Retain the preserved r1 report.

Sources: [Kokoro ONNX](https://github.com/thewh1teagle/kokoro-onnx),
[model and voice release](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1),
[voice descriptions](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md),
[Microsoft SpeakStream](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms723611(v=vs.85)).
Inference adapter is MIT, Kokoro weights Apache-2.0; bundled phonemizer/eSpeak
components have their own licenses, including GPL. No redistribution is performed.

The reported pause after "Yes sir" was device setup in code, not the Command
listening window setting. Native wake now reserves an inactive command stream
before wake recognition and starts it after verified acknowledgement completion.
Only the first received samples announce Listening; initial command samples are
retained. Details exposes command_input_ready_seconds for the actual completion-
to-input handoff. No recording during speech or additional model is introduced.
All 1666 fake tests pass. An owner-approved attended test on this PC measured
67ms from verified acknowledgement completion to first input and exactly recognized
the synthetic question spoken immediately afterward. Audibility/orb were confirmed.
This single trial is not a general accuracy/latency guarantee. Restart an existing
GUI to load the change; see evaluations/m6-wake-handoff-validation-v1.json.

Empty command handling: if local command STT recognizes no usable speech after
the wake acknowledgement, the GUI now drops that turn, closes out its worker and
returns to waiting for the wake call. It does not repeat the command or send
anything to chat/tools. Stop still pauses listening; device/output errors still
need attention. This correction has static review only; runtime recovery is
not yet verified. Restart the GUI to load it.

The owner subsequently resumed fake-only tests: all 1658 pass, including empty-
command recovery and wake lifecycle regressions. Native recovery remains pending;
fake tests do not establish microphone accuracy or audible output.

Attended followup r4: the operator confirms hearing the fixed acknowledgement and
seeing the orb. Command STT completes but does not exactly match the intended test
question; cause is pending. This qualifies neither arbitrary command accuracy nor
complete M6 acceptance. The improved lab keeps recognition visible until Finish
and records only fixed mismatch categories/booleans, never recognized words.

Latest startup correction (2026-10-18): the owned native listener now explicitly
dispatches Windows messages, with its eight-second startup timeout unchanged.
In the owner-approved voice-only lab, native input started in 0.805/0.935 seconds.
The second run detected the wake, started acknowledgement playback, captured a
command and transcribed it. Exact test-question matching and operator audibility
are not verified; see M6_TEST_REPORT.md. Restart the GUI to load these changes.
Other tests remain paused. No input/output selection or private config was changed.
The owner's current command-silence setting is 0.5 seconds, superseding the older
three-second inspection mentioned below; native wake itself does not use that delay.

Wake startup fix (2026-10-18): the outgoing SAPI event interface is now bound
explicitly. Owner-approved inactive inspection reproduces the old automatic
binding failure and confirms the corrected grammar builds. Setup errors now name
their stage; Details shows only the safe category/HRESULT. The non-recording
inspection command is `python scripts/Inspect-JarvisWake.py --compare-events`
using the project .venv interpreter. It never activates recognition. This is
inactive setup evidence; actual wake capture/playback/latency are still unverified.

## Latest wake path: Windows offline grammar (2026-10-18; unverified)

The default wake_provider is now windows_sapi. An owned installed Microsoft
English recognizer listens only for your configured Wake call, without waiting
for the command-silence duration or calling Whisper to decode the wake word.
Say the call, wait for the orb/“Yes sir”, then give your command. The selected
command window starts after speech finishes and the mic reopens. Whisper/base.en
transcribes that command; it does not decide whether to show the wake character.

English SAPI recognizer metadata is installed on this PC; native activation,
detection accuracy, audibility and latency remain untested. Missing or ambiguous
engines/inputs fail visibly, without downloads or fallback. Settings keeps the
same wake phrase/input/output/window selections. Current wake_silence_seconds=3
in the inspected private file now affects command completion only. This file
was not changed. Rejections show “not the wake call” or “unclear” without
displaying/logging ambient words. Core PTT is unchanged.

The older sections describe the earlier Whisper wake path, now selected only
with wake_provider="whisper" in private voice.toml. Single-utterance “Jarvis,
question” is supported by that legacy path; the new native default expects wake,
acknowledgement, then command. There is no measured guarantee of an instant reply.
See [decision 0022](decisions/0022-windows-wake-grammar.md).

## Current ordinary GUI: say “JARVIS”

**Settings** is beside **Details**. Spoken replies are always on in the GUI;
there is no Speak replies toggle or manual Mic/Finish/Stop speaking toolbar.
**Settings > Wake call** selects your own 1–5 word phrase (default “Jarvis”).
**Command listening window** selects 3–20 seconds, default ten. Save applies both
to the next local listening session and persists them in private voice.toml;
older files keep the Jarvis default. Microphone/status labels use your chosen call.
Say the phrase, pause for the character's “Yes sir”, then start your command.
The call is matched as spoken words, not executable patterns or a substring of a
longer word. A short distinctive English phrase suits the installed base.en model;
this setting does not install a dedicated keyword detector or improve recognition
accuracy by itself. Native wake/playback validation remains pending.
When the backend is ready, the GUI automatically listens locally for “JARVIS.”
Say “Jarvis, what is your name?” without a long pause, or say “Jarvis” and wait
for the orb to appear and say **“Yes sir.”**, then ask within ten seconds. About
1.1 seconds of silence ends an utterance. Change
the wake silence duration/input/output/voice in Settings. **Voice activation level**
controls microphone sensitivity: lower values pick up softer speech; higher values
reject more background noise (default 100). This is separate from the unchanged
recognition-confidence gate. The status shows input quiet/sound detected even
before wake recognition. Disabling wake listening
releases the microphone while keeping spoken replies. Stop/Esc pauses listening
and interrupts audio; Settings > Save resumes it. The existing global stop still
requires the usual session restart. Opening Settings pauses/releases the idle
wake worker automatically; changes wait for any active request to complete.

This uses installed base.en CPU recognition, not a newly downloaded keyword model.
Unaddressed background audio/text stays transient and never joins chat/history or
public research. It is microphone listening while enabled, with bounded utterance
buffers and 60-second workers renewed only during ready chat. Background words
are discarded. A clipped or uncertain utterance cannot activate an action. Wake
addressing is not voice identity authentication. No speech model/cloud download.

The wake listener retains a short 300 ms lead-in rather than long idle silence and
keeps a bounded four-second input queue while recognizing speech. This avoids
losing a followup during wake-word recognition. Overflow stops the attempt instead
of submitting clipped words. Capture closes before handing a recognized request to
the backend and stays off during processing and spoken output. A new
request after a reply needs a fresh wake word. There is no full-duplex interruption
or acoustic echo cancellation; Stop/Esc remains available during playback. The
single orb represents addressed requests; passive microphone status is in the GUI.
The fixed wake acknowledgement uses that same orb and installed offline voice,
with no model call or history entry. The owned mic is stopped during speech;
queued pre-acknowledgement input is discarded, then capture restarts and the
one-request followup timer begins. Wait until “Yes sir” finishes before asking.
No intermediate completion event ends the wake job. Repeated addresses cannot
extend its hard session limit indefinitely. Stop/cancellation prevents restart.
Noise/false wakes, accent accuracy, latency and sustained device use are unverified.
No tests or native audio were run for this update at the owner's request. Earlier
PTT results do not qualify wake mode. See [decision 0021](decisions/0021-wake-word-gui.md).

## Explicit PTT lab mode (earlier M6 behavior)

Launch the existing GUI normally:

```powershell
.\.venv\Scripts\pythonw.exe scripts\Chat-JarvisGUI.py
```

The normal launcher uses wake mode above. Only the explicit attended PTT lab
selects the following manual controls. Wait for readiness. **Mic** starts one bounded recording; click
**Finish** to stop it. Ctrl+Shift+Space is the same local-window shortcut. No global
audio shortcut or background wake-word listener is installed. Default recording
limit is 20 seconds. LISTENING appears only after capture opens. The transcript is
shown in chat as `Voice: ...` and uses the same request method as typed messages.
Audio-library startup has an eight-second limit. While listening, the status shows
whether input is quiet or sound is detected; this is a transient signal-level
indication, not recognition or speaker authentication. No recording begins at
startup. A timeout leaves text chat usable and asks you to check the selected input.

Uncertain recognition or control/approval text is left in the composer for review.
Turn on **Review every transcript** in Voice settings if desired. Edit and Send
normally. Typing during recording/transcription cancels that voice input and keeps
the draft. No automatic approvals are extracted from speech. Recognition scores
are not calibrated and cannot authenticate who spoke: activate PTT only for your
own words, with unrelated video/music/conversation kept out of the recording.

Completed replies are spoken locally, including typed chat. The internal
`stop_speaking` operation can interrupt audio without changing the completed task;
it is no longer a separate ordinary-GUI button.
**Stop/Esc** cancels the voice interaction and active backend task through existing
semantics. Ctrl+Alt+Shift+F10 remains the emergency stop; end/restart that session
afterward. Cancellation cannot undo app/media effects already delivered.

Voice is half-duplex: recording is stopped before transcription, processing and
speaking. In the explicit PTT lab, clicking Mic while speaking stops speech and
asks for another click after idle. Normal GUI wake listening resumes after output
ends, with a fresh wake address required.

## Setup and settings

The optional `voice` dependency group is included in the updated generated
`requirements-dev.lock`. Python 3.13 Windows wheels are used in `.venv`; no CUDA,
system FFmpeg, second model server or speech cloud service is needed. CPU int8
recognition leaves the GPU for existing Ollama models. The initial model is the
English `Systran/faster-whisper-base.en` CTranslate2 conversion. It is not an
Ollama model and is not loaded/downloaded by GUI infrastructure startup.

Only after separate owner approval, the operator can run:

```powershell
.\.venv\Scripts\python.exe scripts\Setup-JarvisVoice.py --download-base-en --approved
```

This fixed setup script resolves/pins the repository revision, downloads only the
recognition files under `%LOCALAPPDATA%\Jarvis\speech\base.en`, preserves an existing
destination and writes a local hash/revision manifest. Interrupted setup is not
silently overwritten. `--complete-existing` resumes only an inspected, manifest-backed
installation whose existing file hashes match, at its original pinned revision.
Setup loads the CPU model before reporting success. Normal speech operation requires a local directory and
sets offline/telemetry-disabled hub options; it never downloads a missing model.

**Voice settings** exposes discovered input/output devices and installed voices,
model directory, language, duration, optional silence endpointing, volume, rate,
enablement and transcript-review mode. Save writes private `voice.toml`; no system
default device/settings are changed. Names are discovered rather than hardcoded.
Duplicated or missing selected microphones fail; select a current endpoint.
English base.en is an English model; another language requires a separately
installed compatible model, not simply changing the language selector.

The configuration example is [voice.toml](../config/examples/voice.toml). Missing
`voice.toml` retains core PTT defaults; the ordinary GUI explicitly selects wake
mode and always-on speech under the owner's updated preference. Empty language selects
automatic detection; English is the default. Optional RMS silence endpointing is
disabled by default and is not a robust acoustic echo canceller. STT also uses the
backend's packaged VAD to reduce silence hallucinations; no VAD service is started.
Windows device permission/disconnect errors are reported only to voice. Missing
model/devices never prevent existing text/backend startup. Disable voice entirely
to avoid audio-device discovery and speech processing.

TTS uses currently installed Windows SAPI voices and discovered SAPI outputs.
Playback monitoring reads the native ISpVoice event queue, subscribed before
speaking, rather than relying on an automation callback. Start/end must match
the requested stream, and completion/output status must succeed. This prevents
short streams from being lost between polls; it is not proof of audible sound.
See Microsoft's [queued event subscription](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms717856(v=vs.85)),
[stream event meaning](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms720164(v=vs.85))
and [SDK mask definition](https://github.com/microsoft/win32metadata/blob/main/generation/WinSDK/RecompiledIdlHeaders/um/sapi.h).
SPEECH_PLAYBACK_NOT_STARTED means no matching output-start event was observed;
it does not mean wake recognition failed. Check Output device in Settings if it
persists, then Save to recover from the voice error. Restart an already running
GUI to load code changes. The 2026-10-18 queue correction is untested while the
owner's testing pause remains active; audible output/interruption are pending.
No extra voice is installed or redistributed. These may sound less natural than
neural voices; output quality is not claimed without listening. Default voice is
the system's installed choice, with no actor imitation. The owner explicitly
selected “Yes sir.” for the fixed standalone wake acknowledgement only.
Short responses keep the authoritative text. Links/formatting are omitted aloud;
long/code/table replies instead direct you to the full chat and its limitations,
so a late failure warning is not silently removed by truncation.

## Architecture and privacy

`gui_voice.py`/`voice.py` manage trusted state on Tk's existing main thread.
`voice_runtime.py` supervises one `voice_worker.py` process at a time with bounded
IPC/queues/deadlines and generation checks. Capture, resampling, STT and SAPI work
never run on Tk. PCM remains in the audio process. No recordings are saved, sent
to the text backend, added to support bundles or supplied to research. Accepted
transcript text follows the normal owner request/history path; action journaling
retains its existing fingerprint/argument policies rather than storing audio.

The only new backend input frame is bounded voice-state metadata, installed only
by the trusted GUI worker. It cannot run tools or grant screen access. Screen and
voice presentation share the existing `CaptureIndicator` host and one orb overlay.
Screen capture/analysis/watch and its stop indicator take priority; voice cannot
override them. Voice-only activity displays the orb and the GUI voice status;
it does not add a second floating status box. GUI Stop controls are authoritative
for audio. No raw text/audio/pixels reach the renderer.

Shutdown requests cooperative device release/purge; blocked native recognition is
discarded and only the owned audio worker may be terminated. No save/discard,
desktop force kill, replay or global settings change is introduced. Existing
primary profile/model/qualification defaults remain unchanged. The owner-approved
wake selection is described above; full duplex, voice cloning, reminders and new
desktop authority remain outside this change.

## Sources and licensing

The alternatives reviewed were [whisper.cpp](https://github.com/ggml-org/whisper.cpp)
and [current Piper](https://github.com/OHF-Voice/piper1-gpl). whisper.cpp remains a
valid future adapter, but would add a separately managed executable/build and model
format here. faster-whisper had compatible Python 3.13 Windows wheels and a CPU
int8 path inside the existing project environment. Piper adds another engine and
voice-asset/licensing decision (the maintained engine is GPL); installed Windows
SAPI avoids that setup for the initial M6 slice. Neither competing engine was
installed. This is an integration/packaging tradeoff, not a measured quality or
latency comparison; actual audio benchmarks remain pending.

On this PC, the owner subsequently approved base.en and attended audio validation.
Installed assets total 147,769,510 bytes at revision
`3d3d5dee26484f91867d81cb899cfcf72b96be6c`. Offline CPU int8 loading took 0.312 s;
a synthetic one-second silent buffer produced no segments. This is model-loading
evidence, not microphone accuracy or audible-playback qualification. The initial
setup omitted `vocabulary.txt`; native loading caught the error, and the same
pinned installation was completed after verifying its existing hashes.

Selection was checked against [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
and its [base.en model card](https://huggingface.co/Systran/faster-whisper-base.en),
[sounddevice installation](https://python-sounddevice.readthedocs.io/en/latest/installation.html),
and Microsoft's [SAPI Speak](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms723609(v=vs.85))
and [AudioOutput](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms723596(v=vs.85))
documentation. faster-whisper/CTranslate2, sounddevice/PortAudio and Whisper model
assets have permissive licenses; PyAV's bundled FFmpeg components and every binary
dependency still require a distribution license audit before a public installer.
Windows voices remain installed OS components, not JARVIS redistributable assets.
This M6 change does not implement that installer or claim its licensing review complete.
