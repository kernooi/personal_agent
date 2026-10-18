# M6 local voice implementation and validation

Spelling-context update for owner-reported Discord/this-cord confusion: generic
bounded friendly app-name hints and optional private explicit spellings implemented
through existing local decoder. No replacements/extra decode or new tool authority.
1720 tests pass in 61.67s; lint/format (224 files), pip and whitespace checks pass.
Synthetic spelling corpus v1 passes all four phrases in both variants (8 exact
checks), including literal-cord counterexamples; unhinted also passed, so no
measured owner improvement claimed. Attended spelling r1 FAILED (1/4 exact): first
Discord request exact, second missing leading words, both literal-cord sentences
WORDS_DIFFER. Owner confirms "this cord" became "Discord". Automatic app-name hints
are now OFF by default and explicitly disabled privately; experimental opt-in
remains. No native retest after that correction, and original recognition accuracy
is unresolved. All old failed reports preserved. Full M6 remains unqualified.
Six saved action qualification contracts still validate unchanged.
After disabling broad hints: 1722 fake tests pass in 64.45s; lint, formatting (225
files), dependency and whitespace checks pass. This does not qualify speech.

Recognition update: approved small.en installed/selected on CPU; base preserved.
Capture/decoding corrections and private 1.0s command pause retain original Stop,
half-duplex, no-overlap and approval rules. 1700 full tests plus seven additional
setup/scoring checks pass; lint/format/dependency checks pass. Synthetic r1 exact-
match gate FAILED (both base/small 5/7); no threshold changed. Number formatting
accounts for small's general-question mismatch; playlist name remains incorrect.
Actual owner speech was tested through the normal wake/ack/command path in
m6-recognition-attended-r1.json: all seven transcripts, 2/7 exact matches, FAILED;
no worker errors, post-ack input 65.5–67.5ms. No words/audio saved; mismatch causes
need operator feedback or separate diagnostics. Exact gate remains unchanged.
Lab sent no actions or screen requests. Full M6 remains unqualified; see BUILD_LOG.
Final software checks after diagnostic additions: 1708 passed in 54.35s; lint,
format (221 files), dependency and whitespace checks pass. No additional live run.

Natural-voice update: owner-approved Kokoro install completed; American male
am_michael selected privately, retaining exact microphone/output and wake settings.
Actual CPU model synthesis and asset hashes are verified; those checks used no
microphone or speakers. 1684 full fake tests plus 147 final focused voice checks
pass, including exact output, no false playback, cache validation, cancellation,
GUI selection and the unchanged prepared-input handoff. Lint/format/pip check pass.
Separately attended speaker-only preview completed: four verified sample
completions and one Stop during playback (0.232s worker exit), with operator-
confirmed clear Michael speech and interruption; no errors or microphone/tools.
Report: evaluations/m6-neural-speech-michael-r1.json. Full M6 remains unqualified. Earlier
67ms native handoff evidence below applies to Windows SAPI synthesis and must not
be silently carried over to neural PCM speech. See VOICE.md and BUILD_LOG.md.

Latest handoff optimization: reserve an inactive command stream before native
wake, then start it after verified TTS completion and wait for first actual input
before announcing Listening. 128 focused fake-only tests pass in 4.50s, including
the new ownership/first-sample/cancellation/failure cases. Synthetic 0.05s readiness
is not a native latency result. The subsequent owner-approved attended test
observed Windows SAPI/PortAudio coexistence, audible acknowledgement/orb and
0.0668258s from verified output completion to first input. The immediately spoken
synthetic question matches exactly, without uncertainty. See preserved
evaluations/m6-wake-warm-input-r1.json and its handoff-validation-v1 summary.
No qualification gate was relaxed; full M6 and physical-stop regression remain
separate. No app/media/screen effects or raw audio/transcript persistence.
Final fake-only suite: 1666 passed in 63.69s; lint/format/whitespace pass. Existing
six combined qualification reports remain accepted by their unchanged validators.

Fake-only validation resumed with owner approval for the Spotify selection change:
all 1658 tests pass, including the pending voice/wake and empty-command recovery
regressions. This supersedes earlier UNRUN statements for those fake cases only.
No new native microphone/speaker test was performed; command accuracy and native
empty-turn recovery remain unverified. Existing attended reports are preserved.

Latest code correction: ordinary GUI logs show an empty command recognition
disabling voice. The wake frontend now ends that empty turn and waits for worker
completion before rearming through the existing GUI loop. No request/replay;
Stop and non-empty-result failures stay authoritative. New fake lifecycle/error
cases are UNRUN under the owner's general test pause. No native audio test was
performed for this correction; existing reports do not qualify its recovery.

Latest attended evidence: r4 operator checkboxes confirm hearing "Yes sir" and
seeing the orb. Native input starts in 0.886 seconds, with wake/acknowledgement/
command capture/STT states observed. A 1.05-second clip produces non-uncertain
text but fails the exact synthetic question. Operator confirms saying the intended
phrase; recognized text/cause remain unknown. The exact acceptance check stays
unchanged. r3 was not performed by the operator and is not an accuracy trial.
See preserved r3/r4 reports and r3 operator supplement. Full M6 remains unverified.
Run r5 starts input in 0.796 seconds but observes no wake/command; operator
participation is unknown. It provides no question-mismatch diagnosis. No audio
test remains running. Lint/format pass; broad pytest remains paused.

Current evidence, 2026-10-18: the owner resumed the specific attended voice-only
test. Explicit Windows message dispatch fixes the startup timeout in both runs:
native input StartStream arrives at 0.805/0.935 seconds after lab launch. Run r2
also observes wake acknowledgement, real speech-start state, command recording
and non-uncertain local transcription. The exact synthetic phrase check fails;
operator audibility/wording confirmation remains pending. Run r1 timed out with
no wake observed; both reports are retained. This is partial native evidence,
not M6 qualification or measured wake latency. Broad pytest remains paused.
See [r1](evaluations/m6-wake-live-r1.json), [r2](evaluations/m6-wake-live-r2.json)
and [inactive message comparison](evaluations/m6-wake-message-pump-v1.json).

Latest correction, 2026-10-18: owner approved an **inactive setup check only**.
Plain and event-comparison inspections exited 0 with complete inactive grammar
setup. Automatic event-interface discovery failed at EVENTS/BINDING; explicit
_ISpeechRecoContextEvents succeeded. This reproduces and corrects a startup
binding defect without activating the microphone. See
[actual comparison](evaluations/m6-wake-inactive-setup-v1.json). No recording or
speech was requested. Live detection, latency, audibility and stop remain untested;
the earlier pause still covers those tests. M6 remains NOT FULLY VERIFIED.

Latest 2026-10-18 update: user confirms sound is detected, but wake recognition
produces no response. New windows_sapi wake adapter separates a fixed configured
phrase grammar from Whisper command STT. Read-only registry metadata confirms a
Microsoft English SAPI recognizer is installed; this is **not activation proof**.
Fake grammar/handoff cases are unrun. Static checks only; native recognition,
audibility, false triggers, repeated sessions and wake-to-reply latency are
unverified. The earlier test pause remains active. See decision 0022. Historical
passes below do not qualify this adapter or the current M6 tree.

2026-10-18 clarification: Settings now includes Wake call (literal 1–5 words,
default Jarvis) and Command listening window (3–20 seconds). The configured call
drives matching/status and persists privately; no model swap or gate relaxation.
New mocked gate/config/GUI cases remain **UNRUN**. No native speech/audio/GUI test;
the reported failure is not experimentally resolved. M6 remains unverified.

Latest 2026-10-18 owner update: implemented the same orb plus fixed local “Yes sir”
for a standalone wake address. Input stops during speech, then resumes with a
fresh bounded followup. No extra model/tool request or audio worker. Fake lifecycle,
cancellation and followup cases are added but **UNRUN**; no GUI/audio/native tests.
Native accuracy, audibility and restart compatibility remain unverified.

2026-10-18 update: the owner still reports SPEECH_PLAYBACK_NOT_STARTED. The
automation callback path is now replaced with native queued SAPI start/end events
bound to the exact requested stream, with explicit interest, output-status checks,
finite deadlines, cancellation and finally-purge. Matching events and completion
are required; receipt alone is insufficient. New/updated fake cases are **UNRUN**.
Static checks only; no microphone/speaker, GUI or model validation was performed.
The native cause and audible behavior have not been experimentally established;
this correction and all pending wake changes remain unverified. Earlier passes
below predate this implementation. Failed evidence is retained; no gate changed.

Latest owner update: the ordinary GUI now uses local "JARVIS" wake addressing,
Settings beside Details and always-on spoken replies, with no manual audio toolbar.
This replaces its earlier PTT selection; the explicit attended fixture keeps PTT.
The owner subsequently reported frequent missed wake addresses. Code corrections
trim long idle silence, retain a bounded input queue during local recognition,
use capture-time followup expiry and expose Voice activation level/input feedback.
These changes and new fake-buffer cases are untested; recognition-confidence and
address/approval gates are unchanged. Native compatibility/accuracy are pending.
The wake changes, added fake cases and final SAPI event-interest correction are
**NOT TESTED**. The owner stopped tests; no native audio or GUI was launched for
this update. Static lint/format review is not runtime verification. Earlier PTT
recognition and the last 1593-test pass do not qualify this new mode. See ADR 0021.

Date: 2026-10-17. Base revision **d96c1c4**; current M6 changes are uncommitted.
Verdict: **NOT FULLY VERIFIED**. Local voice code is implemented and mock-tested;
Real microphone recognition is now observed for the two synthetic phrases;
audible playback, interruption and integrated screen acceptance remain pending.
The owner stopped further testing. The owner approved base.en download and attended
audio/owned-screen testing; setup and offline loading now pass. Do not equate
device enumeration, COM event registration or mocked playback with hearing speech.

## Existing architecture reused

Read the owner request, AGENTS/specification, README, current-state/handoff reports,
implementation/build evidence, GUI/session/worker/bootstrap, conversation/broker,
M5 screen pipeline, companion code and relevant tests/ADRs. Preserve the existing
Tkinter root/layout/theme, ChatSession, framed private IPC, CLI composition,
Conversation/ApplicationConversation, Ollama profile, controllers and broker.

`ChatWindow.send_text` is the common typed/transcript submission method. Recognized
text is visibly marked Voice in the existing bubble renderer; it has no independent
history/planner/action dispatcher. No text model/profile switch or tool permission
change was made. Completed backend replies are the speech source; no extra LLM
speech-summary call. Existing GUI infrastructure startup remains in gui_startup.py.

## Files and boundaries

New runtime: `voice_data.py` (private config/contracts), `voice.py` (GUI-owned state),
`voice_runtime.py` (single-flight audio supervision), `voice_worker.py` (device/STT/
SAPI adapters), `gui_voice.py` (small composer controls/settings),
`voice_presentation.py` (trusted metadata-only companion frames).

Changed integration: `gui.py`, `gui_session.py`, `gui_worker.py`, `terminal.py` and
`companion.py`, `companion_host.py`, `companion_status.py`, `screen_capture.py`.
CaptureIndicator IPC is serialized; the existing single orb is shared. Capture,
analysis and watch indicators take priority over stale voice states. Voice frames
carry only strict bounded sequence/state; they cannot execute tools, change scope
or carry raw audio/pixels. Typed/model reply content cannot forge those frames.

Setup/testing: `config/examples/voice.toml`, `scripts/Setup-JarvisVoice.py`,
`scripts/Test-JarvisVoice.py`, `tests/test_voice.py`, `tests/test_voice_gui.py`.
Updated optional voice dependencies/lock, editable installation, combined launcher
qualification paths, README, AGENTS, plan/build/context documents, VOICE.md and
decision 0020. No commit/push or existing failed-result overwrite.

## Engine and asset choice

faster-whisper 1.2.1 with CTranslate2 4.8.3 uses CPU int8 and at most four threads.
The initial separately downloaded candidate is English base.en, approximately
150 MB. This avoids a competing CUDA speech workload. Actual recognition/model
latency and peak memory are not yet measured. Runtime requires an installed local
directory, local_files_only and offline hub settings. The owner subsequently
approved installation: 147,769,510 bytes, pinned revision
`3d3d5dee26484f91867d81cb899cfcf72b96be6c`. Offline CPU loading took 0.312 s and
synthetic silence returned zero segments. See m6-stt-offline-load-v1.json.

sounddevice 0.5.6 supplies Windows PortAudio capture. Native mono int16 is requested
at 16 kHz; a supported default device rate is bounded and resampled in memory when
needed. Invalid formats, empty/silent recordings, overflow/disconnect, selected
device mismatch, permission failure, stop and duration limits are handled.

Windows SAPI uses the existing installed voices/output devices. Typed COM was
required: dynamic-dispatch event discovery failed in a metadata-only probe. The
typed event connection succeeded without requesting speech. StartStream, not mere
Speak acceptance, drives SPEAKING. SAPI remains a system voice with limited
naturalness; no cloned actor/neural voice or additional TTS asset was installed.
Output supports discovered SAPI endpoints, volume and rate. No system default or
Windows audio setting is modified.

Added lock entries include NumPy 2.5.4, CFFI/PortAudio support, PyAV 19.0.1,
onnxruntime 1.31.0 for packaged STT VAD, tokenizers and Hugging Face dependencies.
All installed from locked hashes into `.venv`, with CPython 3.13-compatible Windows
wheels. Existing pinned inference/control dependencies were not upgraded. No
system CUDA/FFmpeg/runtime install. Permissive engine/model licensing and remaining
binary redistribution audit are documented in VOICE.md; no public release claim.

## Audio lifecycle, cancellation and privacy

DISABLED/IDLE → user activation → successful native capture LISTENING → capture
closed TRANSCRIBING → reviewed or accepted transcript SUBMITTING → shared backend
PROCESSING → actual SAPI stream SPEAKING → IDLE. Error/stop paths use ERROR and
STOPPING. The original explicit PTT lab has no automatic recording/re-listen;
ordinary GUI wake mode now renews bounded listening as described in ADR 0021.
Neither mode uses full duplex. Optional
simple RMS endpointing is off by default. No model confidence calibration claim.

A bounded background supervisor owns one audio process; device initialization,
capture, resampling, recognition, synthesis and playback do not run on Tk. Tk
consumes a bounded event queue. Recording defaults to 20 seconds, recognition to
45 seconds and speech to 90 seconds. Process cancellation is cooperative first,
then confined to the owned audio worker. Parent EOF has an independent exit
watchdog. GUI waits only a bounded interval for audio cleanup; existing backend
cooperative shutdown behavior is retained. Audio is not sent over text IPC or
saved to files/logs/journals/support bundles.

Stop speaking only purges current/queued speech. Stop/Esc cancels voice and the
active backend task; global stop still latches the existing backend. Stale replies
and late transcription cannot submit or speak after cancellation, session change,
typed-input takeover or an earlier audio error. Approval/control transcripts need
manual review; speech cannot approve itself. Long/code/table output directs the
user to the full GUI reply, including limitations, rather than dropping a late
failure warning. No cancellation is described as undoing an admitted app effect.

## Actual evidence

| Layer | Result |
| --- | --- |
| Pre-change deterministic baseline | 1531 passed in 54.37 s. |
| Initial integrated full suite | 1583 passed in 56.24 s. |
| Final focused voice/UI suite | 56 passed in 1.34 s; fake audio/backend, owned Tk widgets only. |
| Last full suite | 1593 passed in 60.08 s, before the final untested SAPI event-interest correction; not a real-audio test. |
| Lint / formatting / dependency health | Ruff and format checks passed; pip check passed; final commands recorded in BUILD_LOG. |
| Real installed-device enumeration | 8 input endpoints, 4 SAPI outputs, 2 installed voices; no recording/playback. |
| Hardware inspected | Ryzen 5 5600X, 6 cores/12 threads, 34,257,739,776 physical RAM bytes; RTX 4070, 12,282 MiB total/1,903 MiB used snapshot. |
| Real local model / fake effects | Browser 27/27, Spotify desktop 25/25, language 33/33, applications 31/31; unchanged gates. |
| Strict existing qualification readers | All six match after affected reports refreshed; v2 report preserved separately from failed v1 stale-app check. |
| Existing Notepad model/conversation | Unchanged matching 24/24 and 41/41 reports retained; not falsely labelled new evaluations. |
| Real STT model inference | Pinned model loads locally on CPU int8 in 0.312 s; synthetic silence returns zero segments. Microphone accuracy pending. |
| Real microphone capture/disconnect | R4 genuine PTT capture and two synthetic phrases recognized; device disconnect/recovery not verified. |
| Audible SAPI playback/physical interruption | No verified pass. Native SAPI event interest was zero; corrected after owner stopped testing, no retest. |
| Actual integrated voice→M5→spoken answer | NOT RUN; prepared production-GUI fixture lab below. |
| App/media/web through real voice | NOT RUN; requires further attended scope after basic audio works. |
| Recognition timing / long-run resource use | R4 four samples: CPU model loading 0.322–0.381 s, STT 0.584–0.756 s. Peak resources/long-run GUI latency not measured. |

The 56 deterministic cases cover input format/bounds, cancellation, review, silence,
rate conversion, denied/disconnected devices, worker cleanup/protocols, typed-input
priority, transcript errors and late results, missing model, speech formatting,
SAPI start/purge mocks, bounded process behavior, GUI submission/bubbles and orb
screen priority. Existing regressions remain unchanged. Initial test harness/None
language persistence and dynamic SAPI issues were fixed, not hidden by relaxed
assertions. Source-bound report v1 detected a stale app contract; the app gate was
rerun and a new v2 validation retained rather than changing qualification rules.

## Prepared attended demonstration

After separate model approval/setup and attended readiness, run:

```powershell
.\.venv\Scripts\python.exe scripts\Test-JarvisVoice.py --attended `
  --report docs/evaluations/m6-voice-gui-native-new.json
```

This uses the production ChatWindow/VoicePanel/shared combined backend and existing
service startup. It opens only its synthetic fixture, resolves that exact owned
window, confirms the existing screen grant and keeps Mic unavailable until that
scope is confirmed. Only the two synthetic conversation/screen phrases and lab
scope/stop controls are admitted by the harness. No automatic recording, app/media
command or display capture. Click Mic, read a phrase and click Finish. Listen to
the response; use Stop/Esc for interruption. Close JARVIS to save bounded state/timing/boolean
evidence without raw audio/transcripts/replies. A report never silently qualifies
audibility: physical operator confirmation and broker outcome review are still
required. Reports refuse overwrite. Native r1 stopped before recording because the
fixture HWND was resolved before Tk finished mapping its wrapper. The failed r1
is preserved. The harness now resolves the mapped window on Tk's thread, then
performs inventory in the background. R2 confirmed the exact fixture scope, but
ended without a recognized phrase or spoken stream after the owner encountered
the Voice settings save blocker. Both zero defaults had appeared blank, and a
generic error incorrectly blamed active work. Zero values are now preserved;
numeric/range, busy-state and write errors are distinct. An isolated Tk/fake-audio
test exercises all these paths and successful save/recovery; focused suite 58/58.
The corrected native audio run remains pending restart under existing readiness.
R3 then exposed a native startup deadlock: NumPy initialization while a control
thread blocks on stdin. A separate no-capture reproduction confirmed the native
import stall. Preloading speech libraries before the reader fixes the synthetic
worker path (2.027 s, correct silence rejection). The real r3 timeout failures are
preserved; r4 is awaiting physical microphone/speaker acceptance. Startup is now
bounded to eight seconds and the GUI shows transient quiet/sound levels only after
capture starts. Neither synthetic buffers nor a level indication qualifies STT
accuracy or audibility. New ordering/timeout/protocol cases pass (62 focused tests).

Subsequently, r4 ended after the owner requested "skip the tests for now".
Its genuine PTT/local-STT path recognized both synthetic phrases and submitted two
requests to the existing backend. No raw audio/transcript content was retained;
only the predetermined phrase-match booleans and bounded states/timings. No
spoken-stream start or physical interruption was verified. A no-speaker memory
stream showed default SAPI EventInterests=0, preventing the subscribed StartStream
callback despite generated audio. Set the instance's event interest to 2 before
subscription; this final correction is untested because testing was stopped.
The last 1593-test/lint pass predates it. No further native effects or tests were
launched. M6 is NOT FULLY VERIFIED; resume only when the owner requests testing.
No capture exclusion or scope check was weakened. Initial STT loading also caught
the missing vocabulary file; setup now includes it and validates native loading,
and incomplete local models cannot enable the microphone.

Test device loss/recovery, task cancellation, global stop, disabled voice/text
fallback, ambiguous recognition and single-overlay M5 handoff afterward. Real
Notepad/Spotify/web scenarios need separate confirmed attended scope; no such
effect was delivered during current development. Stop after M6; no reminders,
email/calendar, persistent memory, installer or M8 computer control is included.
