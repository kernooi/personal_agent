# JARVIS — M0 safe simulated core

Only M0 is implemented from `JARVIS_Project_Specification.md` version 2.0.
The first request is **“Open my registered text editor.”** All actions are
**SIMULATED**. A scripted provider proposes one action; trusted code parses,
resolves, authorizes, journals, admits, executes in fake state, and independently
observes the postcondition. This is a tested application flow, not natural-language
intelligence or real-model compatibility.

From the repository root in PowerShell, using the installed Python 3.13:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .

.\.venv\Scripts\python.exe -m jarvis demo --scenario open-editor
.\.venv\Scripts\python.exe -m jarvis demo --scenario denied
.\.venv\Scripts\python.exe -m jarvis demo --scenario cancelled
.\.venv\Scripts\python.exe -m jarvis demo --scenario recovery-unknown
.\.venv\Scripts\python.exe -m jarvis demo --scenario open-editor --profile config/examples/fake-alternate.toml

.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
```

No activation or PowerShell execution-policy change is required. Development
dependency installation needs package-index access; JARVIS runtime needs none.
Tests allocate a fresh ignored `.pytest-run-*` directory inside the repository
for each invocation and clean it on exit. This avoids Windows access-denied errors
from a shared `%TEMP%\pytest-of-User` directory created in another execution context.
The optional pytest cache is disabled to avoid inaccessible stale `.pytest_cache`
files; all tests and assertions still run. `--lf`/`--ff` cache-based selection is
therefore unavailable by default. An explicit `--basetemp` is honored; pytest clears
that directory, so only supply a dedicated disposable test directory.
Python 3.12 is the specification baseline. This machine has Python 3.13.14, which
was used for resolution and testing. The source uses 3.12-compatible syntax, but
3.12 and other platforms have not been tested. The lock is generated and verified
on Windows/Python 3.13, not certified as a cross-platform lock.

To regenerate the lock after a deliberate dependency change:

```powershell
# Bootstrap only if pip-tools is not yet installed in .venv:
.\.venv\Scripts\python.exe -m pip install pip-tools
.\.venv\Scripts\python.exe -m piptools compile --extra dev --strip-extras --allow-unsafe --generate-hashes --output-file requirements-dev.lock pyproject.toml
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
```

`pip-tools` resolves actual package versions/hashes. `--allow-unsafe` includes
the resolver's pip and build backend dependencies in the lock; it grants no
JARVIS execution permission. Editable installation uses the already locked build
backend and never resolves dependencies. Regenerate/test a separate lock when
changing interpreter/platform if this lock cannot resolve there.

Files that matter:

- `src/jarvis/domain.py`: typed contracts and enumerated task transitions.
- `models.py`: strict discriminated decision schema, duplicate-key rejection,
  profile validation, provider protocol, and configurable scripted provider.
- `core.py`, `policy.py`, `tools.py`: one-turn/one-action broker, task scope,
  registry, canonical action digest, grant/approval validation, cancellation,
  deadline gates, and evidence-based outcomes.
- `storage.py`: SQLite tasks, intents, attempts, audit events, durable approval
  consumption, uniqueness constraints, and validated recovery records.
- `adapters.py`: bounded in-memory desktop mutation and separate observation.
- `bootstrap.py`, `cli.py`: composition, injected clocks, isolated CLI scenarios.
- `tests/`: deterministic behavior, denial, race-boundary, persistence, and
  crash-injection tests, including two fake-provider profiles.
- `config/`: strict M0 defaults and alternative fake profile; laptop/desktop
  candidate documentation for M1. M0 rejects the real-provider examples.
- `docs/IMPLEMENTATION_PLAN.md`, `docs/BUILD_LOG.md`: completion and actual evidence.

The trusted CLI alias binds `text_editor` before inference. A standing fixture
grant permits only that target/session/effect. Exact approval is optional for
this low-risk operation; when supplied, it must match the prepared digest,
revision, owner/session, and expiry, and is durably consumed once at admission.
Model output cannot create grants, IDs, approvals, scope, or tool registrations.
Profile selection freezes at task entry and is recorded without scripted reply
content. A different model identity does not change the policy or fake adapter.

The runtime has a fixed maximum of one planner turn, one action attempt, one
observation, zero retries/repair calls, one active planner, bounded context/output,
and a configured task deadline. Hooks and the manual clock make cancellation and
late replies deterministic without sleeps. This single-process synchronous fake
runtime is not a native-worker timeout implementation for future integrations.

Each demo uses a temporary SQLite journal and synthetic in-memory state, then
removes its fixture data. The success demo shows the fake running-state count
changing from zero to one, with one independent observation. The denial and
cancellation demos show zero execution. Recovery injects a process-loss fault
after admission/effect, reopens the journal, and refuses replay. Unknown outcomes
remain `NEEDS_REVIEW`, even if the effect may have happened. Verified duplicates
return historical evidence; they do not claim the editor is still running now.
Separate request keys represent separate intentions. Opening an already matching
fake instance does not create another instance.

SQLite uses foreign keys, short `BEGIN IMMEDIATE` transactions, rollback journaling,
and `synchronous=FULL`. Schema version 1 is initial creation only; unsupported
versions fail closed. There are no migrations/backups, interactive approval UI,
resumption/replanning of paused tasks, or persistent personal data frontend in M0.
An unadmitted intent needs review/reauthorization; an admitted unfinished attempt
becomes unknown. Recovery performs no automatic execution or reconciliation.

No Ollama, model downloads, HTTP client, runtime network, real process launch,
desktop input, screen/audio capture, personal files, external accounts, runtime
shell, generated code, plugins, elevation, startup services, or cloud fallback
exist. Network/process creation is trapped in the core regression fixture.
Windows Python tests validate portable simulated logic; real Windows application
control and live-model behavior remain untested and unimplemented.

Stop here for M0 review. M1 requires separately approved local runtime/model setup,
a bounded Ollama adapter, doctor/chat/live evaluation, local-only/offline evidence,
and qualification through this broker with execution still simulated. Real
Windows control is M2.
