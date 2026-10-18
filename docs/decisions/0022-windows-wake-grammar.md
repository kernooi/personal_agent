# 0022: Separate Windows wake detection from command transcription

Date: 2026-10-18. Implemented; native validation remains pending.

Handoff update: reserve a separately owned, explicitly inactive PortAudio command
stream before native wake recognition. It must not capture or enqueue samples
until the wake recognizer is purged and verified TTS completion occurs. Start
that reserved stream directly after acknowledgement instead of rediscovering,
format-checking and reopening then. Announce command readiness on the first
received block, retain it, and close/drain the stream before command STT. Record
only bounded completion-to-first-input timing. Stop/failure releases this owned
handle. This moves setup work; it does not promise zero latency. Native device
coexistence and measured handoff require attended validation.

The owner repeatedly reports microphone sound detection followed by no wake
response, and requests wake call → immediate character/“Yes sir” → command window.
The earlier implementation used complete-utterance Whisper for both wake and
commands. It waited for the configured silence interval (three seconds in the
inspected private file), decoded a sentence, then silently rejected no-speech,
uncertain or unmatched results. This is not a dedicated wake detector. The exact
native rejection in the reported attempt has not been measured.

Read-only registry inspection found an installed Microsoft English-US SAPI
recognizer, MS-1033-80-DESK (Language 409;9, Vendor Microsoft). No speech engine
was activated, microphone opened or voice played during inspection.

The default wake provider is now windows_sapi: an owned SpInprocRecognizer with
a dynamic command grammar containing only the configured literal wake call and
the established optional hey/okay/ok prefixes. Require a unique installed
Microsoft English recognizer and exact selected-input mapping; fail explicitly
on missing/ambiguous inputs or engines. Do not use a shared recognizer, change
global speech settings, download assets or silently fall back to Whisper/cloud.

Only complete, non-emulated, high-confidence results for the owned grammar may
wake. Hypotheses and low/normal-confidence results grant nothing. Auto-pause
after recognition, resume rejected matches, and purge/verify inactive state
before TTS. Recognition emits only trusted state metadata; it does not transmit
ambient text/history/audio. Retained audio is disabled. Level and rejection
messages distinguish microphone input from wake-call rejection without logging
recognized words.

The existing orb appears on the verified wake match, independently of the text
model. Installed offline SAPI speaks the fixed acknowledgement with real output
checks. After output completes, a new bounded sounddevice capture waits for
command onset, then collects one complete utterance. CPU base.en transcribes
that command only; its confidence/review and broker/approval gates are unchanged.
The command-start window begins after mic startup. Stop cancels every stage;
no simultaneous input/TTS, stored audio, inferred authority or automatic retry.

windows_sapi is the default for existing config files lacking wake_provider.
The previous implementation remains explicitly selectable with
wake_provider="whisper" for compatibility. Its one-utterance addressed requests
remain available there; the default native flow expects wake, acknowledgement,
then command. Core PTT remains explicit, with no startup recording in the lab.

This removes the configured sentence-silence/Whisper wait before acknowledging;
it does not promise zero latency or measured detection accuracy. Windows still
has to finish recognizing the phrase and TTS must start. Fake cases are added
but unrun because the owner paused testing. Attended microphone/speaker,
false-trigger, repeated-wake, stop and latency validation remain necessary.

2026-10-18 correction: bind the exact outgoing event interface and dispatch this
owned worker's Windows queue, in bounded batches, with pointer-sized native
signatures. A COM-only wait left queued notifications pending. Inactive synthetic
diagnostics establish that difference; production never emulates StartStream.
The owner resumed only the voice-only attended lab: native input started in
0.805/0.935 seconds, and the second run observed wake, speech start and command
transcription. Its exact phrase check fails; audible confirmation remains pending.
Full M6 qualification and broader tests remain pending. Keep the eight-second
start deadline and all confidence, privacy and cancellation checks unchanged.

Primary references: Microsoft's [command grammar/context](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms722041(v=vs.85)),
[rule auto-pause behavior](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms718922(v=vs.85)),
[recognizer state semantics](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee431860(v=vs.85))
and [confidence categories](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee125196(v=vs.85)).
