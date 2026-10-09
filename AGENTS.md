# JARVIS repository instructions

Read `JARVIS_Project_Specification.md` completely before architectural changes.
Only M0 is approved: scripted fake providers and fake desktop; no runtime network,
real model, OS control, shell, generated code, installation tools, or plugins.
Preserve unrelated work. Stop for review at M0; later milestones need authorization.

The model proposes; only the broker executes. Strictly parse whole decisions,
resolve reviewed targets, retain controller-owned scope/revisions, validate grants
and exact single-use approvals, journal before effects, check cancellation at
admission, and verify independently. Unknown outcomes must never be blindly replayed.
Model names/options belong in profiles, never policy or tools. Do not persist raw prompts.

Dependencies stay in `.venv`. Installed Python 3.13 is used and tested; 3.12 is the
specification baseline. See README for generated pip-tools lock workflow.
Checks: `.\.venv\Scripts\python.exe -m pytest`,
`.\.venv\Scripts\python.exe -m ruff check .`, and
`.\.venv\Scripts\python.exe -m ruff format --check .`.
Record actual evidence in `docs/BUILD_LOG.md` and progress in
`docs/IMPLEMENTATION_PLAN.md`; never weaken requirements/tests to obtain a pass.
