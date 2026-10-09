# Build evidence

2026-10-09, Windows / PowerShell, installed Python 3.13.14.
Read all 1,574 specification lines in four ranges, inspected repository and ancestor
instructions, and checked Git status. No applicable AGENTS.md existed. Initial
README contained only the repository title; specification was untracked and preserved.
`python --version` and `python -m pip --version` succeeded. `py --list-paths`
reported no registered interpreters; `uv --version` was unavailable.

Decision: use installed Python 3.13 rather than globally provision 3.12; retain
3.12-compatible syntax and declare >=3.12,<3.14. Compatibility evidence is Windows
3.13 only until another interpreter is tested.

## Provisioning actually executed

All successful provisioning changed the project-local `.venv`, not global Python.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pip-tools
.\.venv\Scripts\python.exe -m piptools compile --extra dev --generate-hashes --output-file requirements-dev.lock pyproject.toml
.\.venv\Scripts\python.exe -m piptools compile --extra dev --strip-extras --allow-unsafe --generate-hashes --output-file requirements-dev.lock pyproject.toml
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
```

Venv creation succeeded. The initial sandboxed pip install failed (exit 1) with
WinError 10013 connecting to PyPI. A sandbox-reviewed network retry succeeded
(exit 0); no approval was rejected. Both compile runs exited 0. The first warned
that pip/setuptools were unpinned; the second generated a complete hash lock
including them. Hash-checked install and editable install exited 0. Resolver:
pip-tools 7.6.2, initial pip 26.1.2; final lock installs pip 26.2.1. Windows x64
Python 3.13.14. Runtime/test packages resolved: Pydantic 2.14.0 / pydantic-core
2.50.0, pytest 9.1.1, Ruff 0.16.10, setuptools 84.0.0. No invented versions/hashes.

## Implementation and verification evidence

Implemented, simulated: owner request identity and explicit alias scope; frozen
profile; provider reply identity; strict JSON/argument/schema boundary; reviewed
registry; canonical action digest; session/effect/expiry/revocation policy;
single-use exact approval; SQLite intent and atomic one-attempt admission;
last adapter cancellation gate; fake mutation; separate fresh matching observation;
durable evidence/result; duplicate delivery; conservative recovery with no replay.

Tests trap socket/process creation in the main broker fixture. Manual clock and
explicit hooks cover cancellation, expiry, stale replies/revisions, changed target
and approval, grant revocation, admission and post-effect faults. Reopen tests use
the actual SQLite file, not an in-memory substitute. No timing sleeps are used.

Commands run during implementation:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff check . --fix
.\.venv\Scripts\python.exe -m ruff format .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
git diff --check
git diff -- README.md
git status --short
git ls-files
```

Initial pytest run: 71 passed, two setup/teardown errors associated with an
oversized parametrized ID exceeding Windows temporary-directory path handling.
Short IDs fixed the fixture path without removing/changing the oversized-input
test; next run: 72 passed (2.33 s). Ruff initially reported formatting/long lines;
import fixes and formatter resolved them without suppressing lint rules. Added
14 review-boundary regressions: 86 passed (2.91 s). Added waiting-input cancellation
coverage before final checks. Final results are recorded below.

CLI commands actually run (each exit 0):

```powershell
.\.venv\Scripts\python.exe -m jarvis demo --scenario open-editor
.\.venv\Scripts\python.exe -m jarvis demo --scenario denied
.\.venv\Scripts\python.exe -m jarvis demo --scenario cancelled
.\.venv\Scripts\python.exe -m jarvis demo --scenario recovery-unknown
.\.venv\Scripts\python.exe -m jarvis demo --scenario open-editor --profile config/examples/fake-alternate.toml
```

| Scenario | Task result | Executions | Fake effects | Observations |
|---|---|---:|---:|---:|
| open-editor | SUCCEEDED, SIMULATED | 1 | 1 (running count 0 -> 1) | 1 |
| denied | FAILED, SIMULATED | 0 | 0 | 0 |
| cancelled | CANCELLED, SIMULATED | 0 | 0 | 0 |
| recovery-unknown | NEEDS_REVIEW, SIMULATED | 1 before injected crash | 1 | 0 |
| alternate fake profile | SUCCEEDED, SIMULATED | 1 | 1 (running count 0 -> 1) | 1 |

Recovery reports unknown despite the injected effect, reopens durable state, and
never repeats execution. The second fake profile changes identity, reply formatting,
and limits; broker and policy code remain identical. Both profiles also run denial
regressions. This is architectural independence evidence, not model qualification.

Reviewed new source/test/config files and README changes. Existing specification
was preserved without edits and remains untracked as found. Git tracked only the
original README. No user files were deleted, staged, committed, pushed, or published.
Environment, caches, egg-info, and database artifacts are ignored. Git emits its
configured LF-to-CRLF warning; whitespace checks otherwise pass.

## Scope and remaining gaps

M0: implemented and mock-tested on Windows; no live model or real Windows control.
No setup blocked after the reviewed dependency download. Not tested: Python 3.12,
other OS/interpreters, GPU behavior, hard power-loss/disk-full durability, actual
Ollama transport, real native hangs/cancellation, or real application identity/input.
Process loss is fault injection with SQLite reopen; no physical crash claim.
The synchronous fake adapter is bounded trusted code, not an OS sandbox. Exact
approval is a trusted fixture callback, not an interactive approval frontend.
Paused/review tasks do not resume automatically. Unknown admission always remains
for manual review; migrations, backups and personal persistence UI are absent.

M1 requires separate authorization/provisioning for a local runtime and model,
bounded provider transport, strict M1 profiles, doctor/chat/evaluation, offline
local-only evidence, and live qualification through fake execution. M2 owns actual
Windows control. Neither was started.

## Final checks and M0 exit gate

After the waiting-input regression, a long SQL string triggered one Ruff E501;
splitting the string resolved it without altering SQL or lint rules. Final runs:

| Actual command | Exit | Observed result |
|---|---:|---|
| `.\.venv\Scripts\python.exe -m pytest -q` | 0 | 87 passed in 3.10 s |
| `.\.venv\Scripts\python.exe -m ruff check .` | 0 | All checks passed |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | 0 | 18 files already formatted |
| `.\.venv\Scripts\python.exe -m pip check` | 0 | No broken requirements found |
| `git diff --check` | 0 | No whitespace errors; configured CRLF warning only |
| `git diff --no-index --check -- NUL $reviewFile` (loop over new/current files) | 0 | 24 files checked; no whitespace errors |
| `git check-ignore .venv src/jarvis_simulated_core.egg-info .pytest_cache .ruff_cache` | 0 | Existing local environment/cache entries ignored |
| `git status --short` / `git ls-files` | 0 | README modified, M0 files untracked; original spec untouched |

Also inspected new domain/adapter diffs with `git diff --no-index -- NUL <path>`;
exit 1 is Git's expected result for a nonempty new-file diff. Full source review
included broker, storage, policy, parser, composition, profiles, and test changes.

The final regression total includes parser/policy/state transitions; provider
identity/profile switching; both fake configurations; denial/cancellation/expiry;
single-use and changed/expired approvals; duplicate deliveries/admissions; matching,
failed, stale and unknown verification; before/after-effect crash uncertainty;
unadmitted recovery; verified journal reopen; and untrusted scope expansion.
Denied cases assert zero execution and zero fake effects.

M0 exit gate is met: deterministic regressions pass, four simulated CLI scenarios
run, no real model setup/network/desktop control exists. Stop at M0 for user review.

## Follow-up: Windows pytest directory permissions

The user's pasted verbose run reported 8 passed, 79 setup errors, and 2 warnings
in 15.21 s. The repeated failure was `PermissionError: [WinError 5]` while pytest
scanned `%TEMP%\pytest-of-User`; cache warnings also reported access denied under
the repository's `.pytest_cache\v\cache`. The failing cases never reached their
assertions. An earlier reproduction in this execution session had passed all 87,
so that alone did not establish that the user's execution context had working
temp/cache access. The original directory ownership/ACL cause was not established.

Changed `tests/conftest.py` to allocate a fresh `.pytest-run-*` directory inside
the repository for each invocation, validate its resolved location, supply a
nonexistent disposable child as pytest's default basetemp, and register cleanup
for only that session's directory. Explicit `--basetemp` remains honored.
Disabled the optional cacheprovider via pyproject `addopts`, avoiding the stale
cache entirely; cache-based `--lf`/`--ff` selection is unavailable by default.
Added the session-directory ignore rule and README explanation. No old directories
were deleted, ACLs changed, elevation requested, or tests/assertions weakened.

Validation actually run after the fix:

- `.\.venv\Scripts\python.exe -m pytest -v -ra`: exit 0, 87 passed in 2.97 s;
  no errors/warnings.
- A PowerShell here-string piped to `.\.venv\Scripts\python.exe -` patched
  `os.scandir` to raise PermissionError for the exact old temp/cache roots, then
  called `pytest.main(['-q', '-ra', '-W', 'error'])`: exit 0, 87 passed in 3.20 s,
  zero shared-directory scan attempts. This fault injection changed no real ACLs.
- `.\.venv\Scripts\python.exe -m ruff check .`: exit 0, all checks passed.
- `.\.venv\Scripts\python.exe -m ruff format --check .`: exit 0, 19 files formatted.
- `git diff --check` and `git diff --no-index --check -- NUL tests/conftest.py`:
  exit 0, no whitespace errors (configured LF-to-CRLF warnings only).
- `Get-ChildItem -Force -Directory -Filter '.pytest-run-*'`: no leftover session
  directories after both test runs. Reviewed configuration/conftest/docs changes.

This verifies the workaround in the Codex execution context and under injected
denial; the user's normal PowerShell rerun remains to be confirmed. Runtime M0
logic and milestone scope are unchanged.
