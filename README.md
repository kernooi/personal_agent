# JARVIS local text assistant

## Installed applications on this Windows PC

Application control now discovers targets from Windows AppsFolder metadata rather
than a fixed app list. Windows is the first native platform; the platform interface
can accept future native controllers. It cannot control other devices yet.
Use `python -m jarvis inspect-apps` to list this PC's supported launch identities
without effects. Discovery found 145 supported entries and 51 unavailable entries;
that is catalog coverage, not a claim that every app's windows have been tested.

The private `$env:LOCALAPPDATA\Jarvis\applications.toml` enables the catalog.
The checked-in `config/examples/applications.toml` defaults to disabled.
Restart chat to load changes. Application effects default to simulation and require
separate real-mode flags and current local-model qualification:

```powershell
.\.venv\Scripts\python.exe -m jarvis chat `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml" `
  --applications-config "$env:LOCALAPPDATA\Jarvis\applications.toml" `
  --real-apps --apps-attended `
  --applications-report .\docs\evaluations\applications-qwen3-8b-v3-r5.json `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --web-config "$env:LOCALAPPDATA\Jarvis\web.toml"
```

Try `Open Calculator`, `Open Discord`, `Open Spotify`, `Minimize it`,
`Bring it to the front`, or `Close Spotify`. A selected or sole verified window
needs no reference or extra close confirmation. If several windows match, reply
with the number JARVIS offers. `/apps` and `/app-windows` remain optional diagnostics.
Notepad must still be independently empty, unmodified and single-tab; text,
unsaved changes, dialogs and unknown state pause close without discarding work.
Normal close uses the application's ordinary close operation. Some apps hide to
the tray; that closes their visible window without terminating the background
process or necessarily stopping playback.
Unknown outcomes require manual inspection before further effects. Ctrl+Alt+Shift+F10
stops new effects globally. Run one attended session at a time.

See [natural close and launcher identity](docs/decisions/0009-natural-app-close.md).

For the existing `my text editor` route, additionally use `--real --attended`,
the Notepad registration, `m2-natural-close-model-v1-r2.json` as `--model-report`
and `m2-natural-close-conversation-v1-r1.json` as `--conversation-report`.
For real Chrome/Spotify, retain their separate flags/configuration and use
`m4-natural-close-regression-v1-r1.json` and
`m4-windows-natural-close-regression-v1-r1.json` respectively. Each execution mode
is displayed separately; enabling applications does not authorize browser or media
effects. See [the architecture decision](docs/decisions/0008-device-applications.md).

Unsupported entries, elevated/tray-only apps, unverified launch delegates and portable apps
absent from AppsFolder remain outside the verified path. No executable-path,
argument, shell or generic typing/clicking fallback is provided.

The attended [Windows application lab](docs/evaluations/applications-windows-v1-r4.json)
passed Calculator open/minimize/repeat/restore/close, Character Map
open/minimize/repeat/restore, independent Windows state checks and the physical
stop hotkey with zero new admissions. Three pre-existing windows were preserved.
Earlier failures remain recorded. EXE close is simulation-tested, not exercised
in this native lab. Other app compatibility needs individual validation.

The subsequent [launcher lab](docs/evaluations/application-launchers-windows-v1-r3.json)
passed Discord, Spotify and Notepad open/minimize/focus/normal-close with independent
Windows checks and no extra close confirmation. The linked run continued only its
exact Spotify test window after a zero-delivery planning pause, preserved original
windows, and verified cancellation with zero new admissions. Discord close hides
to the tray; background termination is not claimed. Earlier failures are retained.

Complete combined session with the existing private setup on this PC:

```powershell
.\.venv\Scripts\python.exe scripts\Chat-JarvisAll.py
```

This attended launcher uses the private configs and current reports below and
changes no settings. Add `--print-command` to inspect its arguments without
starting chat. Exit old chats first. The equivalent full command is:

```powershell
.\.venv\Scripts\python.exe -m jarvis chat `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml" `
  --real --attended `
  --registration "$env:LOCALAPPDATA\Jarvis\notepad-registration.json" `
  --model-report .\docs\evaluations\m2-natural-close-model-v1-r2.json `
  --conversation-report .\docs\evaluations\m2-natural-close-conversation-v1-r1.json `
  --applications-config "$env:LOCALAPPDATA\Jarvis\applications.toml" `
  --real-apps --apps-attended `
  --applications-report .\docs\evaluations\applications-qwen3-8b-v3-r5.json `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --web-config "$env:LOCALAPPDATA\Jarvis\web.toml" `
  --media-config "$env:LOCALAPPDATA\Jarvis\media-all-v1.toml" `
  --real-browser --browser-attended `
  --browser-registration "$env:LOCALAPPDATA\Jarvis\chrome-registration.json" `
  --media-report .\docs\evaluations\m4-natural-close-regression-v1-r1.json `
  --real-media --media-attended `
  --windows-media-report .\docs\evaluations\m4-windows-natural-close-regression-v1-r1.json
```

## Selected Notepad minimize

With the desktop v10 profile, try `Minimize Notepad`, `Minimize my text editor`
or `Minimize it` after opening or selecting the registered window. `Bring it to
the front` restores a minimized window and focuses it. Minimize leaves unsaved
work intact. Close no longer requires `/confirm-empty`, but retains independent
empty/unmodified/single-tab checks. This older Notepad route is separate from the opt-in discovered-application
controller above. Restart chat to load the new code.
Older qualification reports are preserved but cannot authorize this changed code.

Notepad-only real chat on this PC:

```powershell
.\.venv\Scripts\python.exe -m jarvis chat `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml" `
  --real --attended `
  --registration "$env:LOCALAPPDATA\Jarvis\notepad-registration.json" `
  --model-report .\docs\evaluations\m2-natural-close-model-v1-r2.json `
  --conversation-report .\docs\evaluations\m2-natural-close-conversation-v1-r1.json
```

For the combined session, retain the public currency/web/media configuration flags
and use `m4-natural-close-regression-v1-r1.json` as `--media-report` and
`m4-windows-natural-close-regression-v1-r1.json` as `--windows-media-report`.
Do not run two attended chat sessions simultaneously. The new attended lab is
`scripts/Test-JarvisNotepadMinimize.py`; the attended local-model Windows run
passed open, minimize, repeated minimize, restore/focus and safe close. Independent
Windows state checks confirmed both minimize operations and restoration. See
`docs/evaluations/m2-minimize-windows-v1-r1.json`. Fake/model qualification remains
separate from this bounded Windows evidence.


## M4: dedicated Google Chrome and media

M4 adds opt-in installed Chrome for YouTube and Netflix, and an official Spotify
API adapter. See [M4 results](docs/M4_TEST_REPORT.md),
[browser compatibility](docs/BROWSER_COMPATIBILITY.md),
[media setup](docs/MEDIA_COMPATIBILITY.md) and
[private profile policy](docs/BROWSER_PROFILE_POLICY.md). Stop at M4; no M5.
Browser, Notepad, currency and public research permissions remain independent.

Spotify can now use Windows media controls without a developer account or API
token. Open the installed Spotify app and start a track manually, then run:

```powershell
.\.venv\Scripts\python.exe -m jarvis chat `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml" `
  --media-config "$env:LOCALAPPDATA\Jarvis\media-windows-v1.toml" `
  --real-media --media-attended `
  --windows-media-report .\docs\evaluations\m4-windows-natural-close-regression-v1-r1.json
```

Try `What is playing on Spotify?`, `Pause Spotify`, `Resume Spotify`,
`Next track on Spotify`, `Previous track on Spotify`. Song search, launching the
app, remote-device selection and volume are outside this backend. Ctrl+Alt+Shift+F10
stops new effects while Spotify has focus. Do not run another attended JARVIS chat
at the same time. Native playback and physical stop passed in
`docs/evaluations/m4-windows-spotify-v1-r2.json`; see
[Spotify setup and limitations](docs/MEDIA_COMPATIBILITY.md). Notepad and browser
actions remain simulated in this Spotify-only command. No API fallback occurs.

The generated lock includes the `browser` extra. Do **not** run `playwright install`:
production uses your installed stable Chrome. Inspect and register explicitly:

```powershell
.\.venv\Scripts\python.exe -m jarvis inspect-chrome
.\.venv\Scripts\python.exe -m jarvis register-chrome `
  --output "$env:LOCALAPPDATA\Jarvis\chrome-registration.json"
```

Registration creates an empty private profile and never overwrites existing data.
Copy `config/examples/media.toml` to a new private
`%LOCALAPPDATA%\Jarvis\media-m4-v1.toml`, set `enabled=true`, and enable only intended
services. No auth values belong in that file. Evaluate the actual local model
against frozen fake media before real effects:

```powershell
.\.venv\Scripts\python.exe -m jarvis eval-media --live `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml" `
  --report .\docs\evaluations\m4-user-model-r1.json
```

Use a new filename for every run. Reports must match the model, runtime, profile,
frozen corpus and source contract, with 100% correctness and zero unauthorized
dispatches. Fake qualification does not establish live Chrome compatibility.
After explicit attended readiness, run the real YouTube lab:

```powershell
.\.venv\Scripts\python.exe -m jarvis test-media --windows --attended --interactive `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml" `
  --browser-registration "$env:LOCALAPPDATA\Jarvis\chrome-registration.json" `
  --media-report .\docs\evaluations\m4-natural-close-regression-v1-r1.json `
  --report .\docs\evaluations\m4-user-youtube-r1.json
```

The lab closes only its own dedicated context and pauses for a physical hotkey
check. Ads, restrictions and uncertain outcomes stop rather than replaying.
Interactive browser chat uses independent real-browser flags:

```powershell
.\.venv\Scripts\python.exe -m jarvis chat `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml" `
  --media-config "$env:LOCALAPPDATA\Jarvis\media-m4-v1.toml" `
  --real-browser --browser-attended `
  --browser-registration "$env:LOCALAPPDATA\Jarvis\chrome-registration.json" `
  --media-report .\docs\evaluations\m4-natural-close-regression-v1-r1.json
```

Example separate turns: `Search YouTube for Rick Astley Never Gonna Give You Up`,
`Open the first result`, `Play it`, `Pause the video`, `Resume it`,
`What video is currently open on YouTube?`. Compound search-and-play currently
requires separate turns and explicit selection. `/media-status` is observational;
`/media-device <reference>` selects an observed Spotify device. Inspect uncertain
effects manually before `/review-media <task> manually-handled`; no replay.

Add existing `--public-data-config` and `--web-config` flags for currency/research.
Real Notepad additionally requires its existing `--real --attended`, registration
and matching M2 model/conversation reports. Real-browser flags alone keep Notepad
simulated. Ctrl+Alt+Shift+F10 stops new effects while Chrome has focus; `/stop`
cancels while the chat terminal is focused. Never run two attended sessions.
The successful attended YouTube evidence is
`docs/evaluations/m4-windows-youtube-v1-r6.json`. Spotify Windows playback is now
live-tested; the optional Spotify API and Netflix setup remain pending.
Overall M4 remains **NOT FULLY VERIFIED**.

The latency optimization has been restored as an opt-in `assistant-v2` candidate.
Use the existing private fast profile on this PC; it keeps Windows effects simulated:

```powershell
.\.venv\Scripts\python.exe -m jarvis chat `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\assistant-fast-v1.toml" `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --web-config "$env:LOCALAPPDATA\Jarvis\web.toml"
```

Restart chat to load the restored code. Keep the manually started local Ollama and
SearXNG servers running. Simple ordinary conversation uses one model turn; common
conversions need three turns instead of five. Uncertain numeric requests retain a separate intent
classifier before planning or answering. Complex monetary interpretation retains
reasoning, and all conversions retain semantic review and
broker verification. Verified currency answers no longer receive a redundant
model rewrite. Stage output limits and ten-minute model residency are profile
settings. `config/examples/assistant-fast.toml` is an unverified-cloud template
for other PCs; do not copy this PC's setup evidence or qualification.

This remains experimental: final interpretation scored 14/18 (earlier 16/18),
and currency scored 31/34. Both failed their unchanged 100% gates. Notepad
simulation/conversation passed 18/18 and 29/29; public smoke passed three narrow
checks. The frozen ticket example took 8.08 seconds; overall median was 10.10
seconds versus the historical 13.95-second run. These are single-run observations,
with varying accuracy and complex-request delays, not a universal speed guarantee.
Fresh results and per-stage timing measurements are in
`docs/evaluations/*restored-fast-r4.json` and `docs/BUILD_LOG.md`. The frozen gates
remain unchanged. Historical reports cannot qualify changed assistant code or
profiles. The older candidate and commands below remain available.

An opt-in conversation candidate now uses local model interpretation for currency
requests, bounded arithmetic plans and same-session numerical follow-ups. It also
renders verified tool results naturally. Its profile is separately qualified;
historical M2 reports do not authorize this new profile for Windows effects.
See [the design decision](docs/decisions/0005-semantic-conversation.md) and the
latest actual results in `docs/BUILD_LOG.md`. This remains within M3.5.

On this PC, test the candidate with Windows actions simulated:

```powershell
.\.venv\Scripts\python.exe -m jarvis chat `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\assistant-staged-v2.toml" `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --web-config "$env:LOCALAPPDATA\Jarvis\web.toml"
```

Try `40 tickets at 40 SGD each in USD`, a discount/fee/bill split, and then
`make that 5 people instead`. Ask `who is Lee Zii Jia?` with the configured local
SearXNG server running. General conversation uses the local model. Missing prices
or ambiguous currencies should still prompt for clarification; unavailable or
insufficient public evidence must not become a confident answer.
The candidate is experimental: interpretation scored 16/18 and the frozen currency
corpus scored 29/34. Both failed their unchanged 100% gates. Missing-price
clarification, currency follow-ups and inference timeouts remain blockers.
Notepad simulation passed 18/18 and conversation passed 29/29; no new attended
Windows test is claimed. The three-case public smoke passed its narrow checks,
but biography rendering fell back to lengthy excerpts. Broad research quality
remains unqualified.
For another PC, start from `config/examples/assistant.toml`; verify that PC's
cloud-disabled startup evidence before creating a private profile.

Evaluate without genuine Windows effects (choose unused report filenames):

```powershell
.\.venv\Scripts\python.exe -m jarvis eval-assistant `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\assistant-staged-v2.toml" `
  --live --report .\docs\evaluations\assistant-local-new.json
```

This explicitly runs real local inference against a synthetic currency fixture;
it measures interpretation, rather than live exchange-rate availability. Separate
`eval-m3`, `eval-m2` and `eval-m2-chat` checks remain required for their scopes.
Do not append `--real` or reuse historical M2 reports with this candidate.

M0's safe simulated core and M1's local Ollama integration are implemented from
`JARVIS_Project_Specification.md`. **Simulation remains the default.**
The real model proposes a decision; strict parsing, the reviewed registry,
authorization, durable intent, cancellation gates, fake execution, and independent
observation determine the result. M2 adds explicit attended control of the installed
Microsoft Notepad: registered open, selected-window minimize/focus and safe graceful close.
See the M2 instructions below and `docs/NOTEPAD_COMPATIBILITY.md` for measured limits.

M3 adds opt-in provider-supported currency reference quotes and conversions through
the same broker. Local Ollama inference, public retrieval and Windows execution
have separate permissions. Decimal calculations and cited answers are produced
from validated data, not model memory. See the M3 commands below and
[M3 test report](docs/M3_TEST_REPORT.md).

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
.\.venv\Scripts\python.exe -m piptools compile --extra dev --extra windows --extra browser --extra media --strip-extras --allow-unsafe --generate-hashes --output-file requirements-dev.lock pyproject.toml
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
The historical M2 v1 corpus retains its 90% / zero unauthorized dispatch gate.
The current desktop v10 profile uses frozen m2-corpus-v2 (24 cases) and
m2-conversation-v3 (34 cases), both requiring 100% and zero unauthorized dispatches. Failed prompt versions remain in `docs/evaluations/`. A matching
passed M2 report, installation registration and attended selection are required
for real chat. Model qualification is limited corpus evidence, not general
permission to control applications. There is no automatic save/discard or force kill.

After the minimize extension, the matching reports for the desktop v10 profile
are `docs/evaluations/m2-minimize-model-v1-r5.json` (24/24) and
`docs/evaluations/m2-minimize-conversation-v1-r3.json` (34/34). Use these as
`--model-report` and `--conversation-report` respectively. The older v10 reports
remain historical evidence; their code fingerprint no longer matches current chat.

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
Do not overwrite old evaluation reports. That M2 validation did not include M3.

## M3: public currency data with local inference

The generic M3 extension discovers currency coverage from the configured provider's
metadata. MYR/JPY, JPY/MYR and other supported pairs use the same typed capability.
The original 11-case corpus/results are retained; the new 34-case v2 corpus keeps
the 100% correctness / zero desktop execution gate and passes 34/34 on this PC.
See current measured results in the test report. General internet research is absent.
Read [provider and freshness limits](docs/PUBLIC_DATA_COMPATIBILITY.md) and
[actual commands/results](docs/M3_TEST_REPORT.md).

The existing Python 3.13 `.venv` and `qwen3:8b` profile are reused. For a clean
project checkout, use the project-local setup block above after verifying that
`python --version` reports 3.13; do not copy another PC's `.venv`. Existing setups
only need the locked packages and editable project installation:

```powershell
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
```

Public data defaults to disabled when no config is selected. To retain a useful
currency limitation while making supplied-rate calculations locally:

```powershell
$jarvisProfile = "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml"
.\.venv\Scripts\python.exe -m jarvis chat --profile $jarvisProfile `
  --public-data-config .\config\examples\public-data-disabled.toml
```

The approved non-secret provider config was created on this PC at
`%LOCALAPPDATA%\Jarvis\public-data.toml` from the enabled example. On a new PC,
copy `config/examples/public-data-enabled.toml` there only when choosing to enable
that reviewed provider; preserve an existing config. Start currency chat:

```powershell
.\.venv\Scripts\python.exe -m jarvis chat --profile $jarvisProfile `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml"
```

This runs the real local model and real public currency retrieval while Windows
actions remain simulated. No `--real` or `--attended` is needed for currency.
For attended real Notepad **as well**, retain all the separate M2 arguments above
and add `--public-data-config`; do not substitute an M3 report for an M2 report.

Try these as separate messages:

```text
What is the MYR to JPY exchange rate now?
Convert 1,000 MYR to JPY using the latest available rate.
How much is 10,000 JPY in MYR?
convert 2000myr to jpy
Convert 250 SGD to MYR.
If I bought 40 tickets each worth 40 SGD, how much would the 40 tickets be in USD?
How much are 3 books at 12.50 EUR each in MYR?
Convert 40 * 40 SGD to USD.
What's 100 EUR in USD?
Convert 50 pounds to Japanese yen.
What's the reverse rate?
What about 500?
When was that rate published, and where did it come from?
Convert 100 MYR to JPY using rate 30
What is an exchange rate?
```

Normal replies show the requested conversion or rate, with a short approximation
notice. Stale rates retain a warning. Ask `Where did that rate come from?` to see
source IDs, the effective date, UTC/local retrieval time and both sources. Detailed
evidence remains recorded by the broker. A date-only source
cannot answer an exact publication-time question. All provider-advertised canonical
three-letter codes are accepted; a pair still needs available, fresh provider data.
Reviewed English aliases include ringgit, yen, US/Singapore dollars and pounds.
Simple quantity × unit-price requests calculate the total locally before converting
it. Item labels and quantities never go to the rate provider. Item quantities must
be whole numbers; totals retain the existing amount/precision limits. For multiple
purchases, fees, discounts or unclear wording, provide the final total to convert.
The common `what much` typo is accepted in a quantity question. A next-turn
clarification such as `I said 40 tickets each worth 40` reuses only the explicitly
established currency pair in that session; unrelated chat clears it. JARVIS retrieves
the rate itself when public currency access is enabled.
Unspecified dollar/symbols, misspellings, missing direction and multiple pairs
get clarification; unknown codes fail as unsupported. Weather/news are absent.
Amount replies such as `2000` resolve a pending amount question; `What about 500?`
reuses the immediately preceding unambiguous pair. An unrelated or ambiguous turn
clears that context. Reverse requests use the provider's native reverse endpoint.

Same-currency requests (`Convert 500 MYR to MYR`) calculate locally at rate 1 and
claim no external quote. Supplied-rate and identity operations never make network
requests, including metadata requests. To validate provider membership they require
unexpired cached coverage: on a cold/expired cache, explicitly request a latest rate
first. This is a deliberate fail-closed constraint, not a model-memory fallback.
Metadata has its own 24-hour TTL (`metadata_cache_seconds`); quote TTL is one hour.
Display rounding is half-even: JPY whole units, other currencies two decimal places.
This is a display policy, not a claim about every currency's legal minor units.
Accepted amounts are 0 through 1,000,000,000,000, at most 24 significant digits and
12 decimal places; scientific notation, negatives and nonfinite values are rejected.

Controls must be entered on their own line:

```text
/cache
/cache-clear
/refresh-rate
/stop
/quit
```

`/refresh-rate` submits a new broker request for the last sourced pair and bypasses
fresh cache. Cache clearing does not erase task evidence or replay requests.
Stale fallback is disabled by default; enabling it explicitly still labels dated
cached information and keeps its original retrieval timestamp. An invalid cache
file is preserved for manual inspection and not served.

Repeat the checks explicitly (use new report filenames, never overwrite failures):

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check

.\.venv\Scripts\python.exe -m jarvis currency-check --live `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --report .\docs\evaluations\m3-provider-next.json

.\.venv\Scripts\python.exe -m jarvis eval-m3 --live --profile $jarvisProfile `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --report .\docs\evaluations\m3-model-next.json

.\.venv\Scripts\python.exe -m jarvis doctor --profile $jarvisProfile `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --evaluation-report .\docs\evaluations\m3-qwen3-8b-v2-r2.json
```

`currency-check` exercises real retrieval through the broker using scripted lab
proposals, not local-model inference. `eval-m3` uses the real configured Ollama
model and `Conversation` path, real provider for live cases, a disabled-policy case,
and a clearly labeled simulated provider outage. Doctor is observational and
does not contact the public provider. No physical network isolation is claimed
by M3's outage test; disconnect networking manually if testing that separately.
Neither command opens/focuses/closes Notepad. Report hashes bind the current
currency contract, corpus, model profile/runtime identity and public-data config.
The 100% / zero-desktop-action gate is separate from M1/M2 qualification.

M3's currency capability ends here. No transactions, Notepad typing/saving,
cloud inference, additional models or M4 capabilities were added.

## M3.5: public web research with local SearXNG (qualification pending)

M3.5 adds separately configured public research to the existing broker. SearXNG
is the initial replaceable search adapter, with no required paid search API or key.
Use your own local instance. See [Windows setup/API compatibility](docs/SEARCH_PROVIDER_COMPATIBILITY.md),
[network/privacy policy](docs/WEB_NETWORK_POLICY.md), and [actual test report](docs/M3_5_TEST_REPORT.md).
The initial inspection found no working Docker/Podman runtime. The user subsequently
installed Docker Desktop and authorized local SearXNG setup. It now runs on
`127.0.0.1:8080`, with JSON enabled and restart policy `no`; the private JARVIS
configuration is `%LOCALAPPDATA%\Jarvis\web.toml`. See the compatibility document
for the pinned image and manual restart/stop commands. Search infrastructure is
available; the full research qualification gate remains separate.

Web research is absent without `--web-config`; the disabled example supplies
explicit status controls. The enabled example authorizes one exact local search
API. Public fetching still blocks loopback/private networks. Ollama, currency and
attended Notepad permissions remain separate, with no M4 browser/media automation.

After your own local SearXNG has been set up and validated, preserve any existing
private configuration and create a new one from the non-secret example:

```powershell
$jarvisProfile = "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml"
$jarvisWebConfig = "$env:LOCALAPPDATA\Jarvis\web.toml"
if (Test-Path -LiteralPath $jarvisWebConfig) { throw 'Inspect existing web config first.' }
Copy-Item -LiteralPath .\config\examples\web-searxng.toml -Destination $jarvisWebConfig
.\.venv\Scripts\python.exe -m jarvis chat --profile $jarvisProfile `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --web-config $jarvisWebConfig
```

Windows remains simulated. For genuine attended Notepad, retain all existing M2
`--real --attended --registration --model-report --conversation-report` arguments
and matching passed reports. Web research never supplies Windows authorization.

Try `What is the latest stable Python version?`, `Find documentation for Python
venv`, `Research recent AI news from two sources`, or
`Read this page: https://docs.python.org/3/library/venv.html`. Automatic routing
uses reviewed freshness/research terms plus local-model classification for owner
factual questions; obscure questions can also explicitly request `Search` or
`Research`. Trivial arithmetic/recursion/rewrite stays local. Structured
currency takes priority over generic research.

The local model plans owner-topic queries, selects result IDs, then selects fetched
source/excerpt IDs. Normal replies show the selected text without reference links,
timestamps or diagnostic footers. `/sources` and explicit source questions show
provenance; broker records retain citations and retrieval failures. Uncertainty
and conflicting-evidence warnings remain visible. This initial answer mode is extractive, not unrestricted
paraphrased synthesis. Sources may be incomplete or wrong; retrieval today never
establishes publication today. See the report for qualification limits.

Controls, on separate lines:

```text
/web-status
/web-enable
/web-disable
/sources
/web-refresh
/web-cache
/web-cache-clear
/stop
/quit
```

`What sources did you use?` reuses evidence without networking. `What changed?`
reuses fresh session evidence. `Check whether anything newer came out today` and
`/web-refresh` bypass caches. The public memory-only caches retain original times;
clearing them retains task evidence. Queries never receive chat history, Notepad,
files or memory. Known private patterns are refused; this is not universal secret
detection. Invalid/blocked/insufficient/conflicting/partial retrieval stays visible.

Default checks remain pytest, ruff check, ruff format --check and pip check.
Explicit live tests use synthetic public questions, no Windows effects and new
exclusive report filenames:

```powershell
# Full ten-category corpus requires your own ready SearXNG instance.
.\.venv\Scripts\python.exe -m jarvis eval-web --live --profile $jarvisProfile `
  --web-config $jarvisWebConfig --report .\docs\evaluations\m3_5-web-next.json
# Real public fetch and real local model, with no search-provider call:
.\.venv\Scripts\python.exe -m jarvis eval-web --live --owner-url-only `
  --profile $jarvisProfile --web-config .\config\examples\web-searxng.toml `
  --report .\docs\evaluations\m3_5-owner-url-next.json
# Observational; no public search/fetch:
.\.venv\Scripts\python.exe -m jarvis doctor --profile $jarvisProfile `
  --web-config .\config\examples\web-disabled.toml
```

The owner-URL test does not establish the full search gate. M3.5 remains incomplete,
with historical failed/pass evidence retained. M4 remains outside scope. No machine
installation is performed by these JARVIS commands.

### Improved source selection on this PC

The private `%LOCALAPPDATA%\Jarvis\web.toml` now uses 8 candidates per query,
5 bounded page attempts, 1 MiB per response and 3 MiB total, with a preserved backup.
Restart chat to load changed configuration/code. Returned search alternatives may
be fetched if preferred pages fail; every attempt consumes the configured budget.
Biographical refinements, domain diversity, later social/derivative candidates and
relevant paragraph selection improve readable evidence. Site access restrictions
are respected; Wikipedia/BWF/other 403 responses are not bypassed. The world-record
question can still be insufficient even when pages are retrieved.

The explicit fixed-public-question diagnostics (simulation only) are repeatable:

```powershell
.\.venv\Scripts\python.exe scripts/Test-JarvisSourceSelection.py --live `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml" `
  --web-config "$env:LOCALAPPDATA\Jarvis\web.toml" `
  --report docs/evaluations/m3_5-source-selection-next.json
```

The report preserves retrieved pages, failure receipts, source excerpts, timing
and model assessment. Manual answer review is required; script exit 0 alone is
not full milestone qualification. Existing reports cannot be overwritten.
