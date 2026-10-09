# JARVIS local text assistant

M0's safe simulated core and M1's local Ollama integration are implemented from
`JARVIS_Project_Specification.md`. **All desktop actions remain SIMULATED.**
The real model proposes a decision; strict parsing, the reviewed registry,
authorization, durable intent, cancellation gates, fake execution, and independent
observation determine the result. M2 Windows control is not implemented.

The RTX 4070 / 32 GB / Ryzen 5 5600X desktop was separately provisioned and tested
on 2026-10-09 with Python 3.13.2, standalone Ollama 0.40.2 and `qwen3:8b`.
All 143 tests and static/dependency checks passed. The unchanged frozen corpus
scored 27/30 (90%) in each of three runs with zero unauthorized dispatches;
actual manually disconnected local inference and independently verified fake
editor state also passed. Desktop M1's simulated exit gate is met. Three request
kinds still produce rejected incorrect proposals, including an ambiguous editor
request; this is limited simulated qualification. See desktop reports in
`docs/evaluations/` and the desktop section of `docs/BUILD_LOG.md`.
Its private profile is `%LOCALAPPDATA%\Jarvis\profiles\desktop.toml`.
The laptop history and commands below describe the earlier machine; use the
desktop profile and desktop report paths on this PC.

The installed laptop model is `qwen3:1.7b`, served by official standalone Ollama
0.40.2. The corrected `planner-v4` / `ollama-chat-v2` profile scored **27/30 (90%)
in each of three runs**, with all editor and clarification cases correct and
zero unauthorized dispatches. It uses `think=false` and the original limits.
Initial failed evaluations and other unsuccessful profiles remain recorded.
The unchanged acceptance gate is 90% correct with zero unauthorized dispatches.
**The narrow simulated behavior gate passes.** Three unavailable requests still
produce clarification instead of unsupported: desktop clicking, browser opening,
and opening `other_editor`; each executes zero times. This is limited corpus
evidence, not qualification for real Windows actions. Valid structured JSON alone
does not establish correct behavior.
See `docs/evaluations/` and `docs/BUILD_LOG.md` for measured evidence and limits.
**M1's exit gate is met for this tested laptop/profile:** behavior qualification
passes and actual offline loopback inference plus verified fake execution passed.
Cloud-disabled startup evidence is operator-verified, not a programmatic attestation.
The offline check observed no physical adapters up and no active external default
routes before/after inference; snapshots do not continuously attest connectivity.

To repeat the offline check, keep the loopback server running, disconnect
Wi-Fi/Ethernet manually, and run this development check from the repository:

```powershell
.\scripts\Test-JarvisOffline.ps1
```

It reads physical-adapter/default-route state before and after real inference,
checks the fake editor's 0->1 state change and independent verification, and saves
`%LOCALAPPDATA%\Jarvis\offline-check.json`. It refuses to claim offline success while
external adapters/default routes remain active. It changes no network settings.
Snapshots do not continuously attest connectivity or exclude a hidden tunnel.
The check includes hidden adapters and counts default routes only when their
interfaces are active or unknown; stale routes on known disconnected interfaces
do not block it. Disconnect USB Ethernet as well as Wi-Fi on this laptop.
To queue a one-time check before disconnecting, add `-WaitForDisconnectSeconds 300`
(maximum five minutes). It waits locally and never disables a connection itself.
Reconnect before sharing the report in this chat; JARVIS itself needs no Codex
connection for this check. Offline success does not enable real actions.
The recorded pass is `docs/evaluations/m1-offline-validation.json`. The qualification
report's offline flag remains false because those corpus runs occurred while
connected; the separate offline report records the successful disconnected check.

From the repository root in PowerShell:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .

.\.venv\Scripts\python.exe -m pytest -v -ra
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
```

No activation or execution-policy change is required. Python 3.12 is the baseline;
Windows Python 3.13.14 was actually tested. Source uses 3.12-compatible syntax,
but Python 3.12 and other platforms have not been tested. The hash lock was
generated on Windows/Python 3.13. Development dependency setup uses PyPI.
Tests use HTTPX mock transports and fake state, with no actual network or desktop
control. Each pytest invocation creates and cleans an ignored `.pytest-run-*`
directory; optional pytest caching is disabled to avoid the previously observed
Windows temp/cache access-denied errors. Explicit `--basetemp` is honored; use
only a dedicated disposable directory because pytest clears it.

The authorized standalone installation is outside Git at
`%LOCALAPPDATA%\Jarvis\runtime\ollama-v0.40.2\bin\ollama.exe`, with weights at
`%LOCALAPPDATA%\Jarvis\models`. A manually started server is currently available.
After restarting Windows, start it in a separate PowerShell terminal:

```powershell
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = "$env:LOCALAPPDATA\Jarvis\models"
$env:OLLAMA_CONTEXT_LENGTH = '4096'
& "$env:LOCALAPPDATA\Jarvis\runtime\ollama-v0.40.2\bin\ollama.exe" serve
```

These settings apply only to that process and its children. No global PATH,
persistent environment variables, startup services, or administrator setup were
changed. Do not start a second server if the existing endpoint is occupied.
The official [Windows distribution](https://docs.ollama.com/windows) supports
standalone installation; cloud disabling uses the documented
[`OLLAMA_NO_CLOUD` setting](https://docs.ollama.com/faq).
Check the startup log for `Ollama cloud disabled: true` before marking a private
profile's `cloud_disabled_verified` true and recording the evidence note.
Committed examples deliberately leave that flag false.

The private laptop profile has already been created on this machine. In the
repository terminal:

```powershell
$jarvisProfile = "$env:LOCALAPPDATA\Jarvis\profiles\laptop.toml"
.\.venv\Scripts\python.exe -m jarvis doctor --profile $jarvisProfile --evaluation-report docs/evaluations/m1-qwen3-1.7b-qualification.json
.\.venv\Scripts\python.exe -m jarvis chat --profile $jarvisProfile
# Explicit live evaluation; exit 0 passes, exit 1 fails the frozen behavior gate:
.\.venv\Scripts\python.exe -m jarvis eval --live --profile $jarvisProfile --report "$env:LOCALAPPDATA\Jarvis\last-evaluation.json"
```

Try `Hello Jarvis.`, `Open my text editor.`, `Open my editor.` followed by
`text editor`, and `What is the current MYR to JPY exchange rate?`. These flows
were exercised through the actual CLI with planner-v4. `/stop` or `/cancel`
cancels waiting inference and closes new action admissions; `/quit` exits.
Cancellation does not promise rollback after an admitted effect. Windows terminal
input handling is implemented; physical interactive key presses have not been
manually tested. Finite piped input and cancellation races are tested.

For another machine, copy `config/examples/laptop.toml` or `desktop.toml` into a
private directory outside Git, retaining `execution_mode = "simulation"`.
Edit model identity, bounded context/output settings, and provider options there;
then select it with `--profile`. The desktop example is `qwen3:8b` for the
RTX 4070 / 32 GB / Ryzen 5 5600X PC; it is separately tested as recorded above. Neither
example guarantees hardware fit. Install/download another model only after
separate setup approval, verify local-only setup, run doctor and live evaluation,
and treat its action role as unqualified until its own gates pass. No source
change or automatic routing is needed. Runtime commands never download models.

M0 regression demos still require neither Ollama nor runtime networking:

```powershell
.\.venv\Scripts\python.exe -m jarvis demo --scenario open-editor
.\.venv\Scripts\python.exe -m jarvis demo --scenario denied
.\.venv\Scripts\python.exe -m jarvis demo --scenario cancelled
.\.venv\Scripts\python.exe -m jarvis demo --scenario recovery-unknown
.\.venv\Scripts\python.exe -m jarvis demo --scenario open-editor --profile config/examples/fake-alternate.toml
```

Success changes fake running state from zero to one and observes it separately.
Denied/cancelled scenarios execute zero times. Crash recovery leaves an uncertain
effect in `NEEDS_REVIEW` without replay. Each demo has an isolated temporary
SQLite journal. Interactive chat's journal is private at
`%LOCALAPPDATA%\Jarvis\journal.sqlite`; history is memory-only, capped at eight
turns and further trimmed to fit the context budget. Raw prompts, replies, and
reasoning traces are not persisted. Synthetic evaluation reports contain case
IDs and metrics, not private conversation text.

Important files:

- `src/jarvis/models.py`: strict decision union, frozen profiles, shared provider
  interface, configurable scripted provider, and normalized inference errors.
- `ollama.py`, `prompts.py`: fixed-loopback bounded HTTP transport, metadata/model
  checks, versioned prompts and schemas, estimated context accounting.
- `core.py`, `policy.py`, `tools.py`, `domain.py`: controller-owned scope, revisions,
  exact approvals, trusted aliases, broker admission, and truthful outcomes.
- `storage.py`, `adapters.py`: durable SQLite tasks/intents/attempts/audit events,
  conservative recovery, fake mutation, and separate verification.
- `conversation.py`, `terminal.py`, `cli.py`, `evaluation.py`: bounded conversation,
  cancellation, observational doctor, explicit live evaluation and report summary.
- `tests/test_m1.py`, `tests/fixtures/m1-corpus-v1.json`: mocked integration
  regressions and the frozen 30-case live corpus; all original M0 tests remain.
- `scripts/Test-JarvisOffline.ps1`: explicit development-time offline check with
  read-only network observations and a real model/broker/fake-state smoke test.
- `docs/IMPLEMENTATION_PLAN.md`, `docs/BUILD_LOG.md`: completion and actual evidence.

One planner turn/action/observation, zero retries, one active planner, byte/token
budgets, and connection/read/task deadlines bound each request. Token accounting
uses an explicit UTF-8 byte estimate, not a claim about a real model's tokenizer.
Only exact trusted editor aliases or a controller-managed clarification bind
`text_editor`; other proposals cannot widen scope. Conversational history grants
no permissions. Exact supplied approvals remain single-use and revision/digest/
session/expiry-bound. Model switching affects the next task, never an active task.

The HTTP client accepts only `127.0.0.1:11434`, ignores environment proxies,
rejects redirects/cloud model metadata/native tool calls, caps complete responses,
and has no fake/cloud fallback. Doctor only observes; it does not install or repair.
Its selected evaluation report is historical evidence, never authorization.
Live current facts use a trusted limitation without a retrieval or model call.
Real launching/closing, browser control, desktop input, capture, audio, personal
files, cloud providers, arbitrary execution, plugins and autonomous tasks are
absent. Offline validation and qualification are required before claiming M1's
exit gate. Stop for M1 review; do not enable M2.

To regenerate the generated lock after a deliberate dependency change:

```powershell
# Bootstrap only if pip-tools is not already installed in .venv:
.\.venv\Scripts\python.exe -m pip install pip-tools
.\.venv\Scripts\python.exe -m piptools compile --extra dev --strip-extras --allow-unsafe --generate-hashes --output-file requirements-dev.lock pyproject.toml
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
```

`--allow-unsafe` includes pip/build dependencies in the lock and grants no runtime
execution permission. Editable installation uses the locked local build backend.
Regenerate/test a separate lock if changing interpreter/platform makes resolution
incompatible. SQLite schema version 1 has no migration/backup tooling yet.
