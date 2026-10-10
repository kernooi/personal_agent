# JARVIS repository instructions

Read `JARVIS_Project_Specification.md` completely before architectural changes.
M2 is approved: genuine installed Microsoft Windows Notepad only, through the
existing broker. Simulation is default; real mode requires explicit selection,
trusted private registration and attended-session consent. The user replaced the
specification's custom-editor fixture with Notepad; see docs/decisions/0002-notepad.md.
Runtime networking is limited to 127.0.0.1:11434. No arbitrary shell, generated
code, installation tools, generic input, plugins or M3 capabilities.
Preserve unrelated work. Stop at M2. Ollama installation
and model downloads require explicit setup approval; never silently substitute fake/cloud.

The model proposes; only the broker executes. Strictly parse whole decisions,
resolve reviewed targets, retain controller-owned scope/revisions, validate grants
and exact single-use approvals, journal before effects, check cancellation at
admission, and verify independently. Unknown outcomes must never be blindly replayed.
Model names/options belong in profiles, never policy or tools. Do not persist raw prompts.
Local-only setup must have explicit evidence; loopback alone is not proof that
cloud is disabled. Doctor is observational. Live evaluation is explicitly invoked.
Never close personal, dirty, mixed-tab or unknown Notepad windows automatically.
Confirm readiness before attended Windows effects. Never force-kill Notepad or
choose save/discard dialogs. A global stop must remain usable while Notepad has focus.

Dependencies stay in `.venv`. Installed Python 3.13 is used and tested; 3.12 is the
specification baseline. See README for generated pip-tools lock workflow.
Checks: `.\.venv\Scripts\python.exe -m pytest`,
`.\.venv\Scripts\python.exe -m ruff check .`, and
`.\.venv\Scripts\python.exe -m ruff format --check .`.
Record actual evidence in `docs/BUILD_LOG.md` and progress in
`docs/IMPLEMENTATION_PLAN.md`; never weaken requirements/tests to obtain a pass.
