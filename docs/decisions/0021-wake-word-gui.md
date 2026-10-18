# 0021: Owner-selected local wake addressing and simpler voice controls

Date: 2026-10-17. Implementation unverified; owner stopped further tests.

Owner clarification, 2026-10-18: expose Wake call and Command listening window
in GUI Settings. Default call Jarvis retains compatibility with older files.
Validated 1–5 word literal phrases replace the fixed name in the wake gate and
visible status; keep exact whole-word matching/confidence, no fuzzy authority.
The command window remains bounded to 3–20 seconds after acknowledgement and
microphone restart. The scrollable settings form leaves Save/error feedback
accessible. New fake config/gate/UI cases are unrun; no native validation.

2026-10-18 owner update: a standalone “JARVIS” now shows the existing orb and
speaks the fixed “Yes sir.” through installed local SAPI. No model/history/tool
submission is made for that acknowledgement. The owned microphone stops before
output; old queued input is discarded before restarting capture and arming the
bounded one-request followup. Reuses the same wake worker/model, with a hard
session bound. Native speech-start/completion checks and Stop remain required;
an error never silently retries. One-utterance addressed questions keep the direct
submission path. This implementation and added fake cases remain untested.

The owner explicitly requested Settings beside Details, removal of manual Mic and
Stop speaking controls, wake addressing with "JARVIS", and always-on spoken replies.
This changes ADR 0020's ordinary-GUI PTT-only startup selection. Core default voice
configuration and the explicit attended fixture retain PTT; no scope/grant changes.

The GUI selects wake_word and spoken replies. Once connected and ready, an owned
bounded CPU worker uses existing local base.en to recognize silence-ended speech.
Only a confident leading "Jarvis" (optionally "hey/okay") or the next utterance
within ten seconds of a standalone wake word can produce a request. Background
audio/text is transient and discarded; unaddressed transcripts never enter GUI
history, backend requests or research. No cloud, new engine/model, or audio files.
One model instance serves a bounded wake session; sessions renew only while the
GUI remains ready, unstopped and without typed drafts/settings open.

This is speech recognition of an address, not a dedicated keyword-spotting model
or identity authentication. CPU load, accent accuracy, false wake behavior, noisy
rooms and long-running device compatibility remain unmeasured. Ambient media can
still pronounce the address; existing exact approvals cannot come from voice.
Unsupported/uncertain recognition grants no extra tool authority.

After the owner's missed-wake report, capture now stays open during local wake
recognition, with an 80-block queue (four seconds at 50 ms) and bounded utterance
buffers. A 300 ms pre-roll preserves word beginnings without retaining long idle
silence. Overflow fails rather than silently dropping a command's beginning.
Followup expiry uses actual speech capture times, not slow recognition completion.
The acoustic activation level is adjustable; recognition-confidence and exact
leading-address gates remain unchanged. No fuzzy name matching or prompted
wake-word hallucination is introduced. These changes remain untested.

Capture closes before transcript handoff and is absent during task processing and TTS.
There is no full-duplex interruption or acoustic echo cancellation. After speech
finishes, a new request needs its own wake word. Stop/Esc pauses listening and
interrupts audio; the global stop remains authoritative. Settings > Save can
resume wake listening, or disable microphone use while replies remain spoken.

Settings automatically releases the idle wake worker before configuration saves.
The ordinary composer has only a readable microphone/task status. The existing
single orb handles addressed requests; passive wake states do not create another
overlay. Explicit PTT fixture startup still cannot automatically record.

No tests, native audio, GUI launch or new qualification are claimed for this
change. Added fake-only cases await execution when the owner resumes validation.
