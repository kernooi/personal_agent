# M3.5 test report — 2026-10-10, Windows desktop

**M3.5 is incomplete.** Local SearXNG is now provisioned and real JARVIS search/fetch
evaluations have run. The frozen retrieval/evidence-binding gate now passes (r6, 10/10). Broad
semantic/freshness qualification remains pending. See the live setup follow-up below; the original
implementation evidence is retained as history. No required commercial search API, account, key or recurring search fee was
introduced. No random public SearXNG instance or consumer search HTML was substituted.

Hardware: RTX 4070, 32 GB RAM, Ryzen 5 5600X. Project Python 3.13.2 `.venv`;
existing standalone Ollama 0.40.2, qwen3:8b digest
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
The existing private `notepad-m2-v10.toml` remains unchanged, context 4096,
output 512, temperature 0, think false. Actual prior cloud-disabled startup evidence
is operator verified; no new programmatic attestation or physical offline test is
claimed. All development evaluations used simulated Windows adapters.

## Evidence categories

The table below records the initial implementation before Docker provisioning.
The follow-up section records subsequent setup and live evaluation results.

## Live setup follow-up — 2026-10-10

The user installed/started Docker and authorized the remaining SearXNG setup.
The official digest-pinned image now runs in Docker Desktop 4.94.0 / Engine 29.8.2,
Linux containers, with host binding 127.0.0.1:8080, JSON enabled, private persistent
configuration/data, and restart policy `no`. No paid API or public instance was used.
Exact setup/restart/stop commands and digest are in SEARCH_PROVIDER_COMPATIBILITY.md.
The private JARVIS config is `%LOCALAPPDATA%\Jarvis\web.toml`.

Ollama was stopped initially. The approved standalone server was restarted manually
with process-local settings; actual 21:52:04.741+08:00 stderr confirms cloud disabled,
version 0.40.2 listening on loopback. No model was downloaded or profile replaced.

| Follow-up evidence | Actual result |
|---|---|
| SearXNG JSON API | Real search returned official Python documentation and virtualenv results |
| Full corpus r1 | 1/10, failed: Ollama unavailable; retained unchanged |
| Full corpus r2 | 8/10, failed; exposed compressed responses, text starvation and overly permissive two-source scoring |
| Full corpus r3 | 7/10, failed with stricter two-source scoring; exposed three-page synthesis context limit |
| Full corpus r4 | **7/10, failed**, zero Windows effects; current-version, documentation, leadership, quantum-limit sources, owner URL, release-note excerpts and honest inaccessible-source handling credited |
| Deterministic suite after source fixes | **597 passed in 18.60 s** |
| Final source quality checks | Ruff lint/format (75 files) and pip check passed |
| Doctor | Exit 0, Ollama ready, existing M3 34/34 evidence matches; no public provider contact |

All full runs preserve the frozen ten-case corpus hash
`7122ef444f4240eca626b7b7c07118afa75516bbbaab9fcaea5ac88464b0d264`.
The default response/page/search/model/context limits were not increased. Fixes:
bounded gzip decoding (wire and decoded size ceilings), fair per-selected-page text
space, combined synthesis excerpt budget, and a stricter requirement for two distinct
cited sources when the corpus explicitly requests two sources. Gzip regression tests
reject invalid, truncated, trailing, concatenated and oversized decoded bodies.
Reports r3/r4 also retain individual retrieval failure codes.

Current live limitations: r4 news and Python/Rust comparison retrieved only one
accessible source each; the stricter gate rejects both. Quorum-sensing candidates
were site-blocked or oversized, leaving no evidence. In r3 some candidates also hit
the redirect ceiling. Upstream result availability/selection changed between runs;
CAPTCHA, rate limits, authentication/site blocks and limits were never bypassed.
Some otherwise credited answers are excerpts rather than full semantic comparisons
or validated latest-event ordering; broad semantic/freshness/conflict qualification
remains open. An 8/10 historical result cannot substitute for the stricter final gate.

Actual command for r4 (exit 1):

```powershell
.\.venv\Scripts\python.exe -m jarvis eval-web --live `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml" `
  --web-config "$env:LOCALAPPDATA\Jarvis\web.toml" `
  --report docs/evaluations/m3_5-searxng-qwen3-8b-r4.json
```

M3.5 remains incomplete. Infrastructure provisioning is complete; the failed live
research gate and broader research quality are remaining implementation/qualification
work, not missing Docker installation. No real Notepad tests ran for this follow-up.

| Category | Actual result |
|---|---|
| Implemented | Provider/fetch interfaces, SearXNG JSON adapter, broker scope/grants/journal/admission, public HTTPS pinning/peer/TLS/redirect restrictions, private-query guard, supervised inert extraction, runtime IDs, excerpt citations, routing, budgets, session followups, separate controls/caches |
| Deterministic/mock-tested | **559 passed in 15.70 s**, including 429 previous cases and 130 new research cases; no real public networking or desktop effects in default tests |
| Static/dependency checks | Ruff lint, formatting (75 files), pip check, git diff --check all exit 0 |
| Live public source | Python venv HTTPS page fetched independently, 103,240 bytes, 12,000 extracted characters, actual public IPv6 peer and verified TLS, zero search calls |
| Real local model + live source | Owner-URL evaluation r7 passes **1/1**, 10.85 s, one real model synthesis turn, zero Windows effects; **not** search qualification |
| Real local model + synthetic web | Synthetic lab r3 passes **3/3** research/source-view/fresh-followup, real query planning + result selection + excerpt selection, one synthetic search and two synthetic pages, zero public networking/Windows effects |
| M3 live regression | Frozen generic currency v2 corpus **34/34**, zero desktop dispatches, matching current contract r5-m3_5; doctor recognizes it |
| Existing M1/M2 evidence | Actual M1 27/30 in each of three desktop runs plus earlier physically disconnected check inspected; original M2 model and conversation reports still match current profile/schema/runtime qualification |
| New Windows lab | Not run; no new native adapter behavior needs Windows effects for this milestone |
| Live SearXNG / full real-model web corpus | **Not run / pending provisioning** |

Final narrow live-source evidence is
[`m3_5-owner-url-qwen3-8b-r7.json`](evaluations/m3_5-owner-url-qwen3-8b-r7.json).
It records actual public peer `2a04:4e42::223`, normal TLS, no environment proxies,
source and excerpt provenance, original nullable publication/update dates, runtime
IDs, budgets, latency and the final source-bound answer. Retrieval today is never
silently converted into publication today. The URL was owner supplied; SearXNG was
not contacted. Earlier r1–r6 are retained.

Real-model planning lab is
[`m3_5-qwen3-8b-synthetic-web-r3.json`](evaluations/m3_5-qwen3-8b-synthetic-web-r3.json).
This is explicitly a real local model with fake web services, not live-search
evidence. It uses a frozen synthetic request and followups, valid source/excerpt
IDs, supported assessments, actual model/profile metadata and zero public requests.

Current M3 evidence is
[`m3-qwen3-8b-v2-r5-m3_5.json`](evaluations/m3-qwen3-8b-v2-r5-m3_5.json),
contract `a8105c31317a853429ec712a1041f6609aff168a1d8dd4dc948f48f268272b7d`.
Its 100% / zero-desktop gate and original corpus are unchanged. r3/r4 are retained
earlier successful contract snapshots, not substitutes for the final matching report.

## Commands actually executed

Existing baseline `python -m pytest -q`: 429 passed, exit 0. After the changes:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

All final commands exit 0. Hash lock regenerated with README's pip-tools workflow;
installed `pypdf==6.20.0` and `tzdata==2026.5` only in `.venv`, then reinstalled the
project with `--no-deps --no-build-isolation -e .`. Existing locked versions remained.

```powershell
$jarvisProfile = "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml"
.\.venv\Scripts\python.exe -m jarvis eval-web --live --owner-url-only `
  --profile $jarvisProfile --web-config .\config\examples\web-searxng.toml `
  --report .\docs\evaluations\m3_5-owner-url-qwen3-8b-r7.json
.\.venv\Scripts\python.exe .\scripts\Test-JarvisResearchModel.py `
  --profile $jarvisProfile --report .\docs\evaluations\m3_5-qwen3-8b-synthetic-web-r3.json
.\.venv\Scripts\python.exe -m jarvis eval-m3 --live --profile $jarvisProfile `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --report .\docs\evaluations\m3-qwen3-8b-v2-r5-m3_5.json
.\.venv\Scripts\python.exe -m jarvis doctor --profile $jarvisProfile `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --web-config .\config\examples\web-disabled.toml `
  --evaluation-report .\docs\evaluations\m3-qwen3-8b-v2-r5-m3_5.json
```

Each final command exits 0. Doctor is observational, public providers untouched.
No real Notepad lab, Docker download/install, WSL distribution install, machine
configuration, service, new model, remote push, commit or network-setting change ran.

## Failures preserved and fixes

Owner-URL r1 fetched the source, but the model altered a proposed quotation.
`UNSUPPORTED_CITATION_OR_CLAIM` blocked publication. Instead of weakening support
validation, model output now selects runtime excerpt indexes and runtime renders
the original text. HTML extraction also normalizes wrapped paragraph whitespace.
Owner-URL r2 had source-bound excerpts but an insufficient assessment; it failed the
supported-answer criterion. The URL-task prompt was corrected to summarize the
page subject without treating unknown dates as invalidating static documentation.
r3–r7 pass the narrow URL gate. r3's truncated output pipeline exited 1 despite its
passed report; subsequent untruncated evaluation commands exit 0.

Real-model/synthetic-web r1 proposed query terms outside the owner topic.
`QUERY_WIDENS_DISCLOSURE_SCOPE` rejected it before any search or page call. No
privacy rule was relaxed. Dynamic planning schema now restricts query choices to
controller-approved topic-only refinements; runtime still validates every query.
Synthetic r2/r3 pass, with source followups reusing actual session records.

Early deterministic failures exposed missing Windows timezone data, incomplete
test profile fixtures, strict JSON tuple restoration and consumed mock streams.
Dependencies, production JSON restoration and fixtures were corrected; no existing
tests, frozen acceptance percentages or rejection cases were removed or weakened.

## Default regression coverage

130 research tests cover freshness/explicit/static/model-assisted routing, query
minimization/private guards, exact SearXNG endpoint permission, POST/JSON/recency,
domain filtering, result limits/dedup/malformed payloads/provider errors, prohibited
schemes/private IPs/alternate numeric forms, DNS pinning/peer mismatch, redirects,
HTTP errors/encoding/response bounds, inert HTML/plain/PDF extraction, encrypted/
oversized-page/empty PDFs, embedded-JS nonexecution, strict whole model decisions,
scope widening/fake IDs/out-of-range excerpts, cancellation/admission/deadlines,
revocation/idempotency, byte/search bounds and partial evidence, cache TTL/original
times/clearing, today-undated insufficiency, synthetic conflict assessments,
durable evidence tampering, interruption without replay and structured-currency
priority and full currency execution with web independently enabled. Explicit
source questions without retrieved evidence get a trusted local response, with
zero model/search/fetch calls. NAT64 private translation is rejected before any
connection, including the existing earlier reserved-address rejection. Existing
M0–M3 tests continue passing.

## Remaining completion gaps

The full ten-category frozen live corpus is committed in
`tests/fixtures/m3_5-corpus-v1.json`, with exclusive report creation and the 100%
evidence-bound/zero-Windows criterion. It has not contacted a real search API.
Provision the user's local SearXNG first; then run `eval-web --live` without
`--owner-url-only` using a new report name. Do not substitute a paid API or public
instance. See [exact prepared Windows setup](SEARCH_PROVIDER_COMPATIBILITY.md).

The initial factual answer mode is bounded extractive selection, not unrestricted
natural-language paraphrase. Citation validation proves that rendered text exists
in the cited retrieved source, not that the source is true or every excerpt is
relevant. Model assessments of conflict/insufficiency need broad live evaluation;
two independent-looking pages are not proof of independent reporting. Publication
metadata is optional and extraction heuristic. Today checks require matching dated
evidence, but an update today still does not prove an event today. Universal latest
release/event ordering and arbitrary scientific/news adjudication are not certified.
These remain visible completion limits; a passed narrow lab cannot close M3.5.

Query privacy excludes all private context inputs and rejects known private patterns;
it cannot recognize every secret deliberately included in public-looking owner text.
Public-only caches are bounded and memory-only; raw documents are discarded after
extraction. No future private disclosure, authenticated research or browser action
permission exists. No M4 work was started. Changes are local and uncommitted.

## Live conversation smoke

Real local-model/SearXNG conversation r2 passed 5/5: identity stayed local (zero
reads); documentation used one real search and three fetches; source view and
fresh followup made zero new reads; disabling web blocked an explicit search with
zero reads. The adapter was explicitly checked as simulated. Report:
[evaluations/m3_5-searxng-conversation-r2.json](evaluations/m3_5-searxng-conversation-r2.json).
An initial development harness failed while recording the effect-count field;
its failed r1 artifact is retained and no success is credited to it. This smoke
checks controls/basic conversation, not broad answer semantics or the full gate.

## Source-selection improvements ? 2026-10-10/11

The private config was backed up before changing to 8 results/query, 5 candidate
attempts, 1 MiB/response and 3 MiB/task. Model context/output, four model turns,
100-second task deadline, text limits and hard ceilings were unchanged.
Same-task alternatives, URL deduplication, domain diversity, later social/derivative
candidates, reviewed biography refinements and topical paragraph ranking now improve
accessible evidence. Known failure receipts account measured bytes; unmeasured
failures retain conservative reservations. No site restriction was bypassed.

Final offline suite: **610 passed in 20.82 s**, including 13 new regressions.
Final ruff check/format (76 files), pip check and git diff --check passed.
Doctor exited 0 with the existing matching M3 34/34 report and touched no public
provider. No real Notepad test or OS effect was performed.

Live source diagnostics preserve r1-r4. r1 retrieved weak excerpts. r2 suffered a
cp1252 development output failure, retained as partial evidence; the new explicit
live script saves incremental UTF-8 records before ASCII-safe printing. r3 retrieved
Lee Zii Jia biographies but weak shrimp excerpts. r4 retrieved identifying Malaysian
badminton-player biographies from readable alternative sources; shrimp research
retrieved Fishipedia, TFH Magazine and Aquarium Co-Op pages but could not establish
a worldwide smallest record, correctly labelled insufficient. The alternatives
can still contain dated rankings or weak material; retrieval is not truth certification.
Wikipedia/BWF refusals remain respected. No operator contact was invented for bot
identification and no alternative IP, browser impersonation or challenge bypass was used.

Final frozen retrieval/binding evaluation:
[evaluations/m3_5-searxng-qwen3-8b-r6.json](evaluations/m3_5-searxng-qwen3-8b-r6.json),
**10/10, exit 0, zero Windows effects**, original corpus and 100% binding criterion.
Earlier r5 also scored 10/10 and remains unchanged. Its legacy
full_milestone_passed flag is overbroad and is not credited as milestone completion.
r6 correctly separates corpus_gate_passed=true from full_milestone_passed=false
and records qualification limits. This strengthened status reporting does not lower
the corpus pass threshold. Broad answer relevance, conflict reasoning and latest-event
ordering remain unqualified; some retrieved material refers to older releases.

Actual final command:

```powershell
.\.venv\Scripts\python.exe -m jarvis eval-web --live `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml" `
  --web-config "$env:LOCALAPPDATA\Jarvis\web.toml" `
  --report docs/evaluations/m3_5-searxng-qwen3-8b-r6.json
```

Restart chat with the existing command to load the new code and private limits.
M3.5 is still incomplete; the source-selection correction and retrieval gate are
complete, while broad semantic qualification remains separate. No M4 work began.
