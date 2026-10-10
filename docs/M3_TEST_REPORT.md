# M3 validation — generic provider-supported currency, 2026-10-10

The generic M3 completion gate passes on this RTX 4070 desktop, using the unchanged
private qwen3:8b / Ollama 0.40.2 profile and enabled Frankfurter v2 / ECB configuration.
The user's multi-currency clarification supersedes the initial two-direction scope.
All existing work, original corpus and failed evaluations were preserved.

## Current generic implementation and deterministic evidence

The existing `currency.quote` capability accepts arbitrary canonical three-letter
codes and validates membership against the official provider-wide metadata before
pair dispatch. `public_catalogue.py` adds bounded schema validation and a separate
provider/version/origin/UTC/TTL cache. All pairs use the same worker, pinned HTTPS
transport, broker permissions, quote validation, Decimal calculation and rendering.
There is no per-pair function or invented currency support list. The small English
alias vocabulary normalizes names but grants no provider support.

`currency_router.py` now handles compact/repeated-base amounts, reviewed currency
names, missing-amount replies, amount-only followups, native reverse rates and
source/effective/refresh followups. Context stays in the authenticated session and
is cleared on intervening chat, ambiguity or failure. Numeric text without a valid
pair is clarified before inference, preventing unsourced conversion prose.
`currency_tools.py` owns that context and independently rechecks evidence and
metadata. `core.py` binds completion to the current request's resolved route.
Same-currency conversions use rate 1 and claim no public quotation. Identity and
supplied-rate calculations make no network requests; they require valid cached
membership. With cold/expired metadata, request a latest rate separately first.

Default deterministic result: **429 passed in 12.23 s**, exit **0**. This includes
54 new generic checks covering all seven representative pairs, arbitrary synthetic
provider-advertised codes, code/name/compact parsing, pending/reverse/source context,
cross-session isolation, unsupported/multiple pairs, invalid amounts, identity,
metadata schema/duplicate keys/list bounds/provider/origin/TTL/cache corruption,
metadata cancellation, changed TTL, stale legacy currencies and refusal to invent
missing/incompatible cross rates. The original 375 tests still pass. JARVIS does
not implement local inversion/cross derivation: orientation tests prove reverse
uses the provider's native response, rather than inverting its rounded forward rate.

`ruff check .`, `ruff format --check .` (**58 files**), `pip check`, and
`git diff --check` all exit **0**. Existing dependencies and private configurations
were reused; no package/model/runtime download was needed for this clarification.
Display rounding remains half-even (JPY whole units, other currencies two decimals),
with internal Decimal precision 64, at most 24 input digits and 12 decimal places.
Amounts span zero through 1,000,000,000,000. Tiny positive results may display zero;
the rate and original amount remain visible. This is an informational display policy.

## Current real-provider evidence

```powershell
.\.venv\Scripts\python.exe -m jarvis currency-check --live `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --report .\docs\evaluations\m3-provider-v2-r2.json
```

Exit **0**, **3/3**. One bounded metadata request discovers **45** advertised codes;
three representative pair requests follow (no O(N²) request matrix).

| Pair | Observed rate per one base unit | Effective date | Latency |
|---|---|---|---|
| MYR/JPY | 38.74 JPY | 2026-10-09 | 1.159 s, including metadata |
| JPY/MYR | 0.02581 MYR | 2026-10-09 | 0.596 s |
| EUR/USD | 1.1206 USD | 2026-10-09 | 0.981 s |

The report records actual metadata, public quote evidence, source IDs, UTC
retrieval/expiry, provenance and connected-public-peer/TLS receipts. These are dated
observations, not permanent expected values. Some advertised codes are legacy;
their old or missing quotes cannot pass the current freshness policy.

## Current real-model qualification

```powershell
.\.venv\Scripts\python.exe -m jarvis eval-m3 --live `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml" `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --report .\docs\evaluations\m3-qwen3-8b-v2-r2.json

.\.venv\Scripts\python.exe -m jarvis doctor `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml" `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --evaluation-report .\docs\evaluations\m3-qwen3-8b-v2-r2.json
```

Both exit **0**. The expanded frozen v2 corpus passes **34/34 (100%)** through
actual local-model `Conversation` → proposal → broker → real public provider.
It retains the original 11 cases and adds compact/repeated-base inputs, pending
amount + bare-number resolution, contextual amount/reverse/effective/refresh,
EUR/USD and USD/EUR, SGD/MYR, GBP/JPY, AUD/SGD, USD/MYR, yen/ringgit names,
identity, unsupported code, invalid amount, multi-pair ambiguity, unsupported date,
and numeric followups after failure/intervening chat. Independently checked
calculations and actual cited final answers appear in the report. **Zero desktop
executions** occurred. No raw prompts/model replies were persisted.

Doctor recognizes matching **34/34 passed**, reports local-model readiness and
`public_provider_contacted=false`. Cloud-disabled status remains the existing
operator-verified actual startup log, not programmatic attestation. The same-PC
M1 and both M2 v10 contracts remain separate, retained evidence. M2 doctor still
recognizes the original 18/18 report; no Notepad effects were tested for currency.

Initial generic provider/model r1 also passed (3/3 and 34/34); final r2 binds the
additional metadata TTL/list/cache hardening and per-request context completion.
All prior failed v1 runs remain untouched. The gate remains 100% correctness and
zero desktop actions. No physical M3 network disconnection is claimed: the corpus
uses a labeled provider outage and real disabled policy.

## Manual operation and remaining limits

```powershell
.\.venv\Scripts\python.exe -m jarvis chat `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml" `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml"
```

Windows remains simulated. Try `convert 2000myr to jpy`, `Convert SGD to MYR`
then `2000`, `What's 100 EUR in USD?`, `What about 500?`, `What's the reverse rate?`,
and `Convert 500 MYR to MYR`, one per line. `/cache`, `/cache-clear`, `/refresh-rate`,
`/stop` and `/quit` remain trusted standalone controls. The actual piped CLI smoke
uses these same synthetic requests with genuine local inference/public retrieval.

Daily reference data and fees limitations remain explicit. All advertised codes
are accepted, but names outside the reviewed aliases require their canonical code.
Metadata expiry can block a local calculation until separately refreshed. Historical
dates, general web search, crypto/securities, transactions, banking, payments,
Notepad typing/saving and M4 remain absent. Other machines/models need their own
qualification. No M3 blocking defect remains in the tested scope. Changes remain
local and uncommitted; stop for review after M3.

## Historical initial two-direction M3 evidence (superseded scope)

M3's narrow completion gate is met on this PC with the configured local
`qwen3:8b`, standalone Ollama 0.40.2, Python 3.13.2 and the explicitly selected
Frankfurter v2 / ECB provider. Public data is enabled independently of simulated
Windows execution. No Notepad effects were performed for M3.

## Prerequisites and preserved evidence

Before implementation, the existing 257 tests passed (9.06 seconds), lint and
formatting passed, and dependency checks found no conflicts. The working tree
was clean after M2 commit `a81a621`. Actual M1 same-PC model evaluation and manual
offline snapshots were reviewed, including
`evaluations/m1-qwen3-8b-desktop-qualification.json` (27/30 in three runs) and
`evaluations/m1-desktop-offline-validation.json` (passed, snapshot-level).
Cloud disabling remains operator-verified startup-log evidence, not a programmatic
attestation. The running server was reused; no runtime/model was downloaded.

M2 v10 original `evaluations/m2-qwen3-8b-simulation-v10-r3.json` (18/18) and
conversation `evaluations/m2-conversation-v10-r2.json` (29/29) still match the actual
private profile and unchanged M2 qualification contract. Earlier genuine Windows
open/focus/clean-close, dirty handoff, physical hotkey and takeover evidence remains
in the existing build log and evaluations. The initial v10 live conversation
failure is still retained, alongside the corrected no-effect truth-guard check.
No new attended Windows test was needed or claimed for currency work.

## Deterministic checks

The default suite uses fake local-model replies, fake desktop and explicit
synthetic provider records/HTTP mock transports. It forbids real sockets/processes
in currency broker fixtures. Coverage includes routing, both units/directions,
decimal bounds and half-even rounding, supplied-rate no-network behavior,
weekend/date-only/future/old observations, cache expiry/stale policy/privacy,
unknown citations, exact scope/schema, malformed/duplicate/oversized/nonfinite
responses, exponent-expansion attacks, failed provider reads and recovery,
cancellation before admission/after response/during observation, late deadlines,
grant revocation, and injection unable to trigger desktop tools.

Transport tests cover fixed URL forms, credentials/ports/queries, non-public IPv4
and IPv6 variants, changed actual peers, mixed public/private DNS answers, numeric
connection pinning, redirects, environment proxy policy, 429/no-retry, content
type/compression/size limits, unknown transport versions, worker deadline/query
minimization, and per-process concurrency. A mock Ollama gateway regression proves
the currency boundary preserves the fully validated original model profile.
Report matching and failed-report preservation are tested separately.

Commands from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Final result: **375 passed in 11.16 seconds**; tests, lint, formatting, dependency
and diff checks exit **0**. Formatting checked 56 Python files. The locked install
found every pinned requirement already satisfied; editable installation succeeded.
Detailed setup/check evidence is also recorded in `BUILD_LOG.md`.
No tests or acceptance criteria were weakened; intermediate development failures
were fixed. Python 3.12 remains the specification baseline and was not run here.

## Real provider evidence

Actual command, exit **0**:

```powershell
.\.venv\Scripts\python.exe -m jarvis currency-check --live `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --report .\docs\evaluations\m3-provider-v1-r3.json
```

The final report at 2026-10-10 07:07 UTC records two independently validated
public observations, their dates/UTC retrieval timestamps/expiry/provenance,
source IDs and actual socket-peer/TLS receipts. MYR/JPY fetched in **0.661 s**,
JPY/MYR in **0.623 s**. The observed pair values were **38.74 JPY per MYR** and
**0.02581 MYR per JPY**, effective **2026-10-09**. They are recorded observations,
not promises about future rates. Both connections used checked public IPv6
`2606:4700:20::681a:e40`, hostname `api.frankfurter.dev`, verified TLS,
no redirects and no environment proxies. Earlier provider r1/r2 are preserved.
This check used scripted lab proposals through the actual broker, not a live model.

## Real local-model chat evidence

Actual command, exit **0**:

```powershell
.\.venv\Scripts\python.exe -m jarvis eval-m3 --live `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml" `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --report .\docs\evaluations\m3-qwen3-8b-v1-r6.json
```

The frozen corpus `tests/fixtures/m3-corpus-v1.json` requires **11/11** correct
and **zero desktop executions**, not the earlier M1 90% gate. The final report
passes and matches current code/config. It records route, normalized proposal,
broker outcome, validated quote evidence, separately checked decimal calculation,
final sourced answer, audit events and measured latency, using synthetic amounts
only. It does not persist raw prompts or raw model output.

| Case | Actual final outcome |
|---|---|
| Current MYR/JPY | Real public lookup, validated dated sourced answer |
| Convert 1,000 MYR | Fresh public cache, independently checked **38,740 JPY** |
| Convert 10,000 JPY | Real reverse lookup, independently checked **258.10 MYR** |
| Source/date follow-up | Same actual source record, date-only limitation, no new fetch |
| `$100` to `yen` | Clarification, no lookup or desktop action |
| Retrieval disabled | `NETWORK_DISABLED`, no current value |
| Offline behavior | Explicit `OFFLINE_FAULT_INJECTION`, no cache/current value |
| Weather today | Capability limitation, no retrieval/desktop action |
| Static exchange-rate explanation | Ordinary local-model answer, no retrieval |
| Static arithmetic | Local-model 10,000 answer, no retrieval |
| Supplied rate 30 | Local decimal calculation **3,000 JPY**, networking disabled |

The offline case deliberately replaces only the provider with a labeled failure
probe. It is **not physical disconnection**. Existing M1 physical-disconnection
evidence is separate and was not rerun or assumed to prove M3 offline networking.
No network settings were changed.

Failed r1 (4/11, gateway profile-format integration rejection) and r2 (10/11,
source-follow-up clarification) remain in `docs/evaluations/`. r3/r4 passed during
implementation; r5 bound hardening/report matching and r6 adds the final
64-digit calculation precision correction. The new maximum-boundary regression
proves that a tiny tail above a half-cent is retained until final rounding.
The gate and corpus are unchanged across these runs. The gateway now keeps the
original model profile and selects a per-request currency boundary. Resolved
currency candidate schemas bind exact owner arguments; the source follow-up
prompt explicitly identifies the existing session evidence. Current facts and
arithmetic are rendered by trusted code regardless of model prose.

Doctor with the r6 report and public config exits **0**, reports M3 **11/11 passed**,
and records `public_provider_contacted=false`. Local Ollama readiness is true,
runtime identity/digest matches the existing model; cloud-disabled evidence is
still user verified. M2 real-action qualification remains separate.

A final piped **actual CLI** smoke test also exited 0 with real local inference:
greeting, live MYR/JPY, cached 1,000 MYR conversion, source/date follow-up,
`/cache`, `/cache-clear`, then `/cache` showing `[]`. The source ID and retrieval
time stayed identical across cache/follow-up. The startup explicitly reported
simulated Windows and enabled public data. The private disk cache ended empty.

## Scope, remaining limits and completion

See `PUBLIC_DATA_COMPATIBILITY.md` for actual provider terms, reference-rate basis,
freshness, pinned connection mechanics and residual host-trust limits. The only
public disclosure is pair plus normal HTTP/connection metadata; amounts remain
local. Cache controls are implemented on their own lines. Default retrieval is
disabled, stale fallback is off, and enabled retrieval does not enable Windows.

No blocking M3 defect remains in the tested scope. Known limits: narrow English
currency resolution, two ISO-code directions, daily rather than intraday data,
conservative seven-calendar-day freshness, no exact publication time, no manual
physical M3-disconnection test, and no new real-Notepad regression run. Other
public-information topics, browser research, transactions, voice, memory,
Notepad typing/saving and M4 are absent. The hardware/profile gate belongs to
this PC; other machines/models require their own evidence. Changes remain local;
no push or automatic M3 commit was performed.
