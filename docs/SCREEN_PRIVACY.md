# Screen privacy and consent

The owner authorized on-demand whole-screen reads without repeated prompts.
With enabled configuration, explicit visual questions default to the whole main
monitor (`default_capture_scope="primary_display"`), resolved from trusted display
metadata. No window reference or per-request permission question is required.
The default is not continuous observation; ordinary chat never starts a capture.
Selected windows remain an optional narrower scope; an explicit whole-screen
question returns to main-display scope. All-monitor/desktop questions bind a
separate exact desktop target and still obey geometry/pixel limits.

Screen assistance is off without a selected `--screen-config`; the example also
defaults `enabled=false`. GUI service startup never captures a screen. Enabling
the configuration allows explicit screen questions, not background scanning.

`/screen-windows` lists eligible windows and displays without taking images.
`/screen-allow <reference>` permits on-demand reads of one exact window.
`/screen-allow-display <reference>` separately permits one display.
`/screen-allow-desktop <reference>` separately permits the whole visible desktop.
References come only from native discovery. Reused handles, changed process
creation/session/owner identity or bounds fail validation.

With `default_capture_scope="foreground_window"`, an explicit visual question may inspect the foreground
eligible window. It must remain the same through capture; no retargeting to a
different foreground window. In a chat GUI, explicitly select the intended app
first so the chat window is not mistaken for the subject. The default main-display
mode avoids binding the capture to the foreground chat window. Follow-ups reobserve;
after switching targets, old-reference follow-ups ask for scope clarification.

The separate visible **JARVIS SCREEN ACCESS** indicator stays present through
capture and inference. Close it to stop. `/screen-stop`, `/screen-revoke`, `/stop`
and Ctrl+Alt+Shift+F10 stop further admissions. In-flight local inference may
continue inside Ollama temporarily; late results are not published. No rollback
or secure physical erasure of memory is promised.

Watching needs `watch_enabled=true`, an explicitly allowed window and
`/screen-watch` (or an explicit watch request after selection). It has a fixed
configured duration, low sampling rate and sample count. Switching to another
application ends watching. No unsolicited descriptions are emitted. Pixel changes
are changes between sampled frames, not proof of intervening user actions.

Pixels, descriptions, recognized text and recent structured observations stay in
memory. The latest and one previous structured observation, plus at most four
transient replies, are retained for bounded comparisons;
no complete frame history. Session close/revocation clears references. Captures
are never stored in ordinary logs, support bundles or Git, or passed into normal
text history or public web research. The local provider sends images only to the
fixed 127.0.0.1:11434 endpoint with proxies/redirects disabled. Local-mode evidence
and actual installed vision capabilities remain required. No cloud fallback.

The owner-approved vision-to-chat handoff sends bounded structured observations
to the configured primary local text model for one read-only explanation. It sends
no pixels to the text model. Up to two screen discussion pairs remain private in
memory and are used only for fresh same-target screen questions. Topic changes
clear that discussion context; it never enters ordinary chat history, public
research, currency tools or action planning. Limited ordinary conversation can
flow into this private explanation step. See SCREEN_CHAT_HANDOFF.md.

Failure diagnostics store only fixed stage/category codes. `/screen-status` shows
the configured context and last safe failure; model replies, validation inputs and
runtime error bodies are not copied into diagnostics. Invalid/truncated visual
results cannot publish a partial Wordle guess. A failed capture is not automatically
repeated. Configured vision recovery can retry once on CPU using a bounded
derivative of the same captured image; it never recaptures or extends expiry.
The text explanation stage is not retried. If it fails, the validated vision reading
remains available with an explanation-failure notice and safe diagnostic category.

Exclusion configuration supports executable basenames and sensitive title terms.
Password-flag inspection reads no names or values and is confined to the permitted
window. Exclusion heuristics are not perfect content classification. Select only
content you intend to share with the local model. Screenshots and model readings
are untrusted evidence; displayed instructions never become commands or consent.

Screen-derived information is not automatically searched online. If updated public
documentation is needed, submit a separate non-sensitive public query. No general
clicking, typing, camera, voice, memory or hidden screenshot access is added.
