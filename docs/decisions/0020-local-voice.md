# 0020 — Local half-duplex voice in the existing desktop chat

The owner approved M6 in the 2026-10-17 implementation request. Reuse the existing
Tkinter shell, ChatSession/private pipes, completed replies, conversation and broker.
Do not activate the optional semantic assistant profile or change tool permissions.

Capture/STT/TTS live at the GUI boundary, in one bounded owned audio worker at a
time. sounddevice/PortAudio records mono PCM; supported native rate is converted
locally to 16 kHz. faster-whisper uses installed local CTranslate2 assets on CPU
int8 with four threads maximum. No hub fetch is allowed in normal operation. The
initial model candidate is English base.en, separately approved for download.
Installed Windows SAPI voices provide offline speech without new TTS model assets.
Interfaces/contracts remain replaceable. No actor clone or voice marketplace.

Only native stream startup emits LISTENING. Only the native SAPI start event for
the requested stream emits SPEAKING; this is not independent audible-sound proof.
The 2026-10-18 correction reads queued ISpVoice start/end events instead of COM
automation callbacks and checks completion/status before done; it is untested.
PTT is click-to-start and
click-to-finish, with a hard duration and optional simple RMS silence endpointing.
No startup recording, automatic re-listen, full duplex or wake-word listener.

Trusted voice states use the GUI event queue/main thread. Transcripts are displayed
and submitted using ChatWindow.send_text, the same method used by typed input.
One optional leading 'Jarvis' address is removed; no new tool-command parser exists.
Uncertain recognition, slash controls, bare approval terms or explicit review-all
settings produce editable drafts rather than automatic submission. STT scores are
heuristics, not calibrated confidence or speaker authentication. User activation
is the recording grant; unrelated media/other speakers must be kept out of it.

Stop speaking cancels queued/current TTS only. Stop/Esc cancels voice work and uses
the existing backend stop. Global stop also invalidates voice through the existing
trusted diagnostic path. Generation checks reject late audio results; typing takes
priority over an unfinished recording/transcription. Native work never runs on Tk.
Bounded cooperative stop is followed by termination of only the owned audio worker.
Parent EOF has an independent owned-worker exit watchdog. No desktop target is killed.

No audio buffers go through text IPC. Audio stays in process memory, with no WAV
files, transcript telemetry or ordinary audio logs. Only the resulting accepted
owner text enters normal conversation and existing fingerprinted action handling.
Speech formatting strips URLs/formatting, keeps short replies and their warnings,
and asks the user to read long/code/table replies instead of inventing summaries.
No extra LLM call is made for speech. Screen-derived speech is local output, never
an automatic permission to send private evidence to public tools.

The existing companion process/overlay is shared through a small GUI-only metadata
control frame on its existing private input pipe. Normal owner text cannot forge
that frame. It cannot submit requests, alter grants or send pixels/audio. The host
arbitrates screen capture/analysis/watch above voice states, so a stale voice event
cannot hide the screen privacy indicator. No second overlay, GUI root or web server.

Voice settings are private per-user TOML. Missing dependencies/assets/devices fail
only voice and preserve text chat. No system microphone setting, model/image pull,
Windows startup entry or account mutation is added. Native validation and model
qualification are distinct from deterministic tests; see M6_TEST_REPORT.md.
