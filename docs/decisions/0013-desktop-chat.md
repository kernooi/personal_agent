# Minimal native chat presentation

The owner explicitly requested a modern, minimal chat GUI with thinking animation.
This authorizes a desktop presentation layer for existing JARVIS capabilities; it
does not implement the specification's voice milestone, vision, generic UI control,
new grants, cloud inference or a local HTTP control server.

Use installed Python's standard Tkinter, with no new dependency. A shared trusted
launcher constructs exactly the existing private chat configuration. Simulation is
default in the GUI. Selecting attended PC controls and starting is the user's
readiness selection; all CLI registration, qualification, stop-hotkey and broker
checks still run. GUI widgets cannot execute tools or approve model proposals.

The GUI owns a single child running the existing CLI composition root. A separate
entrypoint frames existing terminal callbacks as versioned, bounded JSON events on
parent-owned pipes. Startup output is diagnostics; complete replies are one event;
trusted prompt callbacks indicate readiness. Reply text containing newlines, prompts
or JSON cannot become control events. Multiline composer text becomes one bounded
request line so it cannot silently submit a second terminal command. No shell,
browser server, wildcard binding, prompt persistence or generic input adapter exists.

All Tk work runs on the UI thread. Backend startup and pipe reads use background
threads and bounded queues. Only one request is sent while the session is ready;
thinking is an animated activity indicator and never exposes raw reasoning. Stop
uses the existing input cancellation path. Global-stop notices disable sending
until a new session; the GUI never clears a stop latch. Closing sends stop/quit,
continues draining final output, and waits cooperatively for owned backend exit.
No forced application termination or admitted-effect rollback is promised.

Diagnostics and displayed chat are held in memory and bounded. Failure details and
existing unresolved-outcome notices remain inspectable; the reverted manual-review
policy is not changed. No production capability code or frozen acceptance corpus
is modified. Existing source-bound capability qualifications remain applicable.

Validation covers framing/injection, bounded input, strict events, startup failures,
shared simulation flags, single-flight send, stop, global-stop state, EOF handling
and composer visibility at the minimum window size. A synthetic Windows layout
preview and an actual local-model GUI conversation separately verify presentation
and inference. Native application/media effects are not sent for this UI change.
