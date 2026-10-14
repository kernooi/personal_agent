# 0015 — Owner-selected real GUI and simplified chat presentation

On 2026-10-14 the owner explicitly requested that GUI real app/media controls and
animations always be enabled, and requested a modern chatbot/message composer.
This replaces the GUI's earlier simulation-default/explicit-checkbox selection in
decisions 0013/0014. Opening this dedicated launcher selects the already-existing
attended combined command. A visible attended scope/global-stop reminder remains.
Only authenticated subsequent user requests may cause supported effects.

GUI sessions pass real=True to the same Chat-JarvisAll command factory. Existing
configuration, registrations, passed qualifications, attended flags and broker
checks remain required; failure ends startup rather than falling back to simulation
or cloud. Core, private profile and ordinary CLI defaults are unchanged. Simulation
can still be explicitly used through the ordinary CLI/shared command factory.
Stop, cooperative close, single-flight input and uncertain-outcome handling remain.

Remove the two GUI toggles. Activity dots always animate during a pending request;
they do not expose model reasoning. Draw the rounded composer and send button in
Tk, with in-memory placeholder, bounded automatic line growth and keyboard support.
No dependency, web-hosted frontend, new agent tool or model capability is introduced.
Windows resize/native caption and transcript selection/scrolling remain available.

Mocked startup tests verify real selection, retries and unchanged exact arguments.
Tk previews use no backend. Developer permission to edit this interface does not
authorize app/playback effects in testing: live attended effects still require
readiness. No action is launched merely by opening the GUI.
