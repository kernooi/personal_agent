# JARVIS local text assistant

M0's safe simulated core and M1's local Ollama integration are implemented from
`JARVIS_Project_Specification.md`. **Simulation remains the default.**
The real model proposes a decision; strict parsing, the reviewed registry,
authorization, durable intent, cancellation gates, fake execution, and independent
observation determine the result. M2 adds explicit attended control of the installed
Microsoft Notepad: registered open, selected-window focus and safe graceful close.
See the M2 instructions below and `docs/NOTEPAD_COMPATIBILITY.md` for measured limits.

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
M1 profiles remain simulated. M2's separately selected adapter supports only
Notepad open/focus/close; browser control, desktop input, capture, audio, file
editing, cloud providers, arbitrary execution, plugins and autonomous tasks remain
absent. M1 qualification does not qualify an M2 profile or another computer.

To regenerate the generated lock after a deliberate dependency change:

```powershell
# Bootstrap only if pip-tools is not already installed in .venv:
.\.venv\Scripts\python.exe -m pip install pip-tools
.\.venv\Scripts\python.exe -m piptools compile --extra dev --extra windows --strip-extras --allow-unsafe --generate-hashes --output-file requirements-dev.lock pyproject.toml
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
```

`--allow-unsafe` includes pip/build dependencies in the lock and grants no runtime
execution permission. Editable installation uses the locked local build backend.
Regenerate/test a separate lock if changing interpreter/platform makes resolution
incompatible. SQLite schema version 1 has no migration/backup tooling yet.

## M2: attended Microsoft Notepad

The approved target change is recorded in `docs/decisions/0002-notepad.md`.
This PC uses packaged Notepad 11.2607.14.0 and the existing qwen3:8b model.
M2's frozen 18-case model corpus uses the unchanged 90% / zero unauthorized
dispatch gate. Failed prompt versions remain in `docs/evaluations/`. A matching
passed M2 report, installation registration and attended selection are required
for real chat. Model qualification is limited corpus evidence, not general
permission to control applications. There is no automatic save/discard or force kill.

From the project directory, local dependency setup is:

```powershell
# Create only when .venv does not already exist; never copy another machine's venv.
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
.\scripts\Register-Notepad.ps1 -Output "$env:LOCALAPPDATA\Jarvis\notepad-registration.json"
.\.venv\Scripts\python.exe -m jarvis inspect-notepad --registration "$env:LOCALAPPDATA\Jarvis\notepad-registration.json"
```

Registration is private, pins the verified Microsoft package/executable and
launcher hashes, and refuses overwriting an existing registration. After an app
update, inspect the changed installation and deliberately create a new registration.
No Notepad settings or recovery files are touched. Classic/unpackaged installations
are currently unsupported and fail closed.

Start the already installed standalone Ollama manually in a separate terminal:

```powershell
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = "$env:LOCALAPPDATA\Jarvis\models"
$env:OLLAMA_CONTEXT_LENGTH = '4096'
& "$env:LOCALAPPDATA\Jarvis\runtime\ollama-v0.40.2\bin\ollama.exe" serve
```

These settings affect this process only. Check its actual startup log for
`Ollama cloud disabled: true` before marking private profile evidence verified.
Do not infer cloud-disabled status solely from the loopback address.
On this PC the private M2 profile was derived from `desktop.toml`, retaining its
model/provider options, setting `prompt_version="planner-m2-v10"` and
`decision_version="decision-m2-v1"`. The checked-in example
`config/examples/notepad-m2.toml` starts with cloud evidence unverified.

```powershell
$m2Profile = "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml"
$notepadRegistration = "$env:LOCALAPPDATA\Jarvis\notepad-registration.json"
.\.venv\Scripts\python.exe -m jarvis chat --profile $m2Profile
.\.venv\Scripts\python.exe -m jarvis eval-m2 --live --profile $m2Profile --report docs/evaluations/m2-new-run.json
# Multi-turn usability has an additional frozen 29-case, 100% / zero unauthorized gate.
.\.venv\Scripts\python.exe -m jarvis eval-m2-chat --live --profile $m2Profile --report docs/evaluations/m2-chat-new-run.json
# Requires both matching passed reports. This is a real, attended desktop session.
.\.venv\Scripts\python.exe -m jarvis chat --profile $m2Profile --real --attended --registration $notepadRegistration --model-report docs/evaluations/m2-new-run.json --conversation-report docs/evaluations/m2-chat-new-run.json
```

Ask `Open Notepad.` or `Open my text editor.`, then
`Bring that Notepad window to the front.`. Use `/windows` to list opaque scoped
references. `/select <reference>` selects the window; only when you personally
confirm the whole window is an empty disposable single-tab test window, use
`/select <reference> empty-disposable` before `Close that Notepad window.`.
For the currently selected window, `/confirm-empty` provides the same explicit
operator confirmation without copying its reference. Use it only after personally
checking that the whole window is your empty, unmodified, single-tab disposable
window. Then `Close it`, `Close the Notepad window` or `Please close it` works.
`Focus on the Notepad`, `Bring Notepad to front`, and polite requests resolve to
that selected window. These are bounded single-action forms; arbitrary desktop
requests remain unsupported. Repeated focus is independently verified each time.
The adapter independently rechecks identity, empty/unmodified state and all tabs.
Nonempty, modified, multiple-tab, dialog or unknown state causes handoff before
WM_CLOSE, even if you supplied disposable confirmation. It never clicks dialogs.
Ambiguous or missing targets cannot acquire action permission. The v10 qualification handles `Open my editor` by asking a clarification;
`Open my text editor` names the registered application explicitly. An unavailable
app cannot acquire a grant. Bare `clear` asks what you mean; `/clear` clears only
the terminal display, retaining conversation and window selection. Enter slash
commands on their own line, then send the action request separately.
`Bring the text editor to the front` and `Bring it to the front again` are supported.
A reply such as `the only one that is open now` can resolve only an immediately
preceding window clarification, only to the already selected window, and only if
independent inventory shows exactly that one window. Changed selection, another
window, or an intervening turn prevents that resolution. It never selects a
personal window implicitly. Model prose claiming an effect is not an action receipt;
unsupported claims are replaced with a truthful no-action reply.
General chat retains its history. Window requests use fresh controller state and
the current owner request rather than stale action replies; their model schema
contains only the action permitted for that exact scoped reference.
Ordinary conversational replies display natural text; only simulated actions are
labeled `[SIMULATED]`. Verified real actions have no simulated label.

Ctrl+Alt+Shift+F10 latches stop while any app has focus. A hotkey conflict prevents
real startup. `/stop` also cancels inference; `/quit` exits. Restart chat after
stop only after reviewing any pending effect. Unknown effects are never retried;
after manually checking the outcome, `/review <task_id> manually-handled` records
operator review without replaying that action. The recovery notice prints the
exact task ID. Inspect and handle the outcome before acknowledging review; this
does not select a window, confirm it disposable, or re-execute the old request. Real persistence is separate at
`%LOCALAPPDATA%\Jarvis\m2-journal.sqlite`. Close dirty/unknown leftovers yourself;
exiting chat does not close Notepad. Stop Ollama with Ctrl+C in its serve terminal.

Automated tests use synthetic windows and no Ollama/desktop effects:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
```

The separate opt-in adapter lab uses scripted proposals through the same broker.
Before running it, confirm you are at the PC and accept at most two new disposable
Notepad windows and short focus changes. Pre-existing windows are excluded.
Use an interactive PowerShell terminal, stay at the PC and avoid input during
each automated operation. The interactive steps require you to type synthetic
unsaved text manually, then press the global stop hotkey with Notepad focused.

```powershell
.\.venv\Scripts\python.exe -m jarvis test-notepad --windows --attended --interactive --registration $notepadRegistration --report docs/evaluations/m2-windows-new-run.json
# Separate takeover check: exactly one user-confirmed synthetic window must remain.
.\.venv\Scripts\python.exe -m jarvis test-notepad --windows --attended --takeover-only --prepared-synthetic --registration $notepadRegistration --report docs/evaluations/m2-takeover-new-run.json
```

Default launcher behavior is measured, not guaranteed to produce a new isolated
window. If it opens an existing tab or cannot uniquely establish readiness, the
adapter reports uncertainty, blocks new effects and leaves manual handling.
Prepare/select an empty disposable window yourself rather than changing settings.
Do not overwrite old evaluation reports. M2 stops here; no M3 features are included.
