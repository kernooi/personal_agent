# JARVIS implementation plan

Conversation echo correction complete (2026-10-09): remove repeated known internal
non-action prefixes from both visible replies and assistant history; preserve
broker/journal semantics and trusted simulation labels for actions. Two-turn echo
regressions and all 145 tests pass with lint, format and dependency checks.

Conversational presentation follow-up complete (2026-10-09): terminal replies
hide internal state labels and non-action boilerplate, while simulated action
results retain `[SIMULATED]`. Broker/journal safety semantics remain unchanged;
all 143 tests, lint, format and dependency checks pass. See BUILD_LOG.md.

## Desktop PC validation — 2026-10-09

1. Complete: confirmed latest M1 commit `44c3d6d` and clean initial tree; preserved
   existing private data and older Ollama installation. No implementation transfer
   or architectural change required.
2. Complete: fresh local Python 3.13.2 `.venv`, hash-locked dependencies and
   editable installation. All 143 tests, lint, formatting and dependency checks pass.
3. Complete: explicitly authorized official standalone Ollama 0.40.2 archive,
   verified release SHA-256, process-local loopback/cloud-disabled/context settings,
   actual cloud-disabled startup evidence, and only qwen3:8b in the new model store.
   Private desktop profile remains simulation with original bounded settings.
4. Complete: doctor and real broker inference independently verified fake state
   0->1; 100% GPU placement observed. Three frozen-corpus runs each scored 27/30
   (90%) with zero unauthorized dispatches. Retain all nine rejected incorrect
   proposals; desktop clarification accuracy differs from the laptop.
5. Complete: user manually disconnected networking; queued read-only offline check
   passed actual inference/fake verification with disconnected before/after network
   snapshots. Preserve the earlier connected/blocked report and snapshot limits.
6. Complete: recorded measured desktop evidence separately from laptop artifacts.
   Desktop M1 exit gate met for this profile's simulated scope; stop at M1.

Detailed commands, results and limitations are in BUILD_LOG.md and the desktop
reports under `docs/evaluations/`. Prior laptop qualification remains historical
evidence for that machine only. M2 and real desktop control remain unauthorized.

1. Complete: project-local `.venv`, src project, strict configuration, generated
   hash lock, concise repository instructions, and README setup/check commands.
2. Complete: typed domain/provider contracts, configurable fake provider, strict
   decision union, reviewed `apps.open` registry, and trusted editor alias scope.
3. Complete: scoped policy, exact single-use approvals, revisions, SQLite journal,
   atomic admission, bounded fake execution, cancellation, independent observation,
   duplicate delivery handling, and conservative unknown-outcome recovery.
4. Complete: four CLI scenarios plus alternate fake profile and deterministic
   adversarial/integration regressions. Actual results live in BUILD_LOG.md.
5. Complete: reviewed source and README diff, checked whitespace and ignored local
   artifacts, recorded checks/results and limits. M0 exit gate met; stop for review.

M0 is implemented and mock-tested on Windows/Python 3.13. The following M1 work
was subsequently authorized. Real Windows control remains outside this plan.

Design choices: one planner turn/action/observation and zero retries are stricter
than the proposed default budgets and sufficient for this vertical slice. Flat
responsibility modules avoid empty future packages. Recovery always requests
review for uncertain effects instead of reconciling or redispatching. The only
enabled capability is low-risk fake opening; exact approval validation is tested
through a trusted controller callback, without introducing consequential tools.

Follow-up: isolate pytest temporary files per invocation inside the repository and
disable its optional persistent cache after a user run showed Windows access-denied
errors in shared pytest temp/cache directories. Test assertions and M0 scope remain
unchanged. Validation evidence is recorded in BUILD_LOG.md.

## M1: authorized local text integration

1. Complete: re-read the specification, repository instructions, existing source,
   plan and evidence; verify all 87 M0 tests and lint before integration.
2. Complete: add HTTPX through the generated lock; strict live profiles, bounded
   fixed-loopback Ollama provider, metadata/capability checks, normalized errors,
   complete schema decisions and no install/pull/cloud/fake fallback.
3. Complete: retain the shared broker and fake desktop; add bounded session-only
   conversation, trusted clarification/aliases, current-information limitations,
   prompt/schema versions, cancellation during inference and clean terminal exit.
4. Complete: after explicit user setup authorization, install the verified official
   standalone Windows distribution and only qwen3:1.7b outside Git; start a manual
   loopback/cloud-disabled server using process-only settings. Reuse it thereafter.
5. Complete: observational doctor, explicit live evaluation, frozen 30-case corpus,
   structured synthetic reports, and deterministic HTTP transport/broker tests.
6. Complete: preserve all 87 M0 regressions; 143 total tests passed on Windows
   Python 3.13.14. Lint, formatting, dependency checks and retained demos pass.
7. Complete: actual JARVIS live evaluation and finite-input CLI exercise. v1 scored
   16/30; v2 scored 24/30 twice before final report validation. All editor and
   clarification cases pass with v2; zero unauthorized dispatches. Keep failed
   runs and their unchanged corpus/criteria. Do not qualify the model at 80%.
8. Complete: actual offline loopback inference through the broker/fake desktop;
   no physical adapters Up and no potentially active external default routes in
   before/after snapshots. State 0->1 independently verified. Cloud-disabled setup
   remains operator-verified; snapshots are not continuous security attestation.
9. Complete: planner-v4 / ollama-chat-v2 / think=false passed the frozen >=90% gate
   in three repetitions. Narrow simulated qualification only; three unavailable
   request kinds remain misclassified. See follow-up details and recorded limitations.
10. Complete: README, plan/evidence updates and final diff review. Stop at M1 review;
    M1's exit gate is met for this tested laptop/profile. Do not start M2 or enable
    real actions without separate authorization and Windows compatibility work.

M1 code and provisioning are implemented, mock-tested and live-model-tested on
Windows. Offline inference is tested. Physical interactive terminal input, the desktop
candidate and other platforms/interpreters remain unverified. M0 tests remain
unchanged. Profiles freeze at task entry; switching profiles cannot change policy.

## M1 gap resolution: authorized follow-up

1. Complete: full specification reread, existing source/evidence inspection and
   baseline 134-test/lint/format pass. Preserve prior uncommitted M1 work.
2. Complete: fix empty-context/latest-owner transport ordering and version it;
   isolate the scope rendering fix in planner-v4 using unchanged v2 instructions.
   Retain unsuccessful shorter prompt and thinking experiments as measured evidence.
   No case-specific routing or reduced acceptance gate.
3. Complete: three frozen-corpus live runs each scored 27/30 (90%), with all editor
   and clarification cases passing and zero unauthorized dispatches. Select v4 in
   the private laptop profile. Actual multi-turn CLI flow passes; safety regressions
   remain passing. Three unsupported kinds remain misclassified, with zero execution.
4. Complete: queued bounded local check ran during manual disconnection. Real model
   proposed editor action, broker verified fake state 0->1; before/after snapshots
   showed zero physical adapters Up/unknown and zero active default routes.
   Recorded evidence level and hidden-tunnel/continuous-monitoring limits.
5. Complete: final regression checks, diff review, README and evidence/status updates.
   Stay within M1; no new model downloads, global network changes or M2 control.

Current exit assessment: behavior qualification is resolved at the unchanged gate.
Actual offline validation passed in `docs/evaluations/m1-offline-validation.json`.
M1's exit gate is met for the tested laptop/profile. Stop at M1 review; M2 is not
authorized by this follow-up and remains unimplemented.

## M2: user-authorized installed Microsoft Notepad (2026-10-10)

This later explicit request supersedes the preceding M1 stop instruction only
for the M2 slice. `decisions/0002-notepad.md` records the approved replacement of
the custom editor fixture. No M3 work is authorized or implemented.

1. Complete: read specification/instructions/history; preserve M0/M1; baseline
   145 tests and static/dependency checks pass; review this desktop's separately
   passed M1 corpus/offline artifacts and actual cloud-disabled Ollama startup.
2. Complete: observational Microsoft package/signature inspection and private
   registration; generated locked optional comtypes dependency in .venv only.
3. Complete: versioned M2 decisions/scoped window references, existing broker
   authorization/intent/approval/recovery, bounded native/UIA workers, independent
   postconditions, foreground restrictions, desktop lease and latched global stop.
   Default demos and profiles remain simulated; real chat requires explicit
   flags, registration, attended consent and matching M2 model qualification.
4. Complete: frozen 18-case corpus, unchanged >=90% / zero unauthorized gate;
   retain failed v1/v2/v3 reports; v4 passed 18/18 three times using actual qwen3:8b.
5. Complete: attended genuine Notepad opening/reuse/focus/two-window targeting,
   clean graceful close, manual synthetic unsaved handoff, physical stop and a
   separate native takeover rejection; preserve failed compatibility/input runs.
6. Complete: actual local-model terminal chat verifies open/focus/clean close,
   ambiguity/unregistered-app no-effect handling and unsaved handoff. The browser
   request incorrectly clarifies rather than unsupported; record this limitation.
7. Complete: final checks, README commands, compatibility record, build evidence
   and separate model/adapter/live reports. Leave the dirty synthetic window for
   manual handling. No automatic cleanup, extra model, settings change or push.

M2's measured Windows safety exit gate is met for this installation/profile:
open/focus/empty close, identity, unsaved work, takeover, stop and independent
verification have actual evidence. Qualification is narrow corpus evidence;
conversation can still misclassify unavailable requests, and other installations,
classic Notepad, dirty automatic close and general desktop control are unqualified.
Simulation remains default. Stop after M2.

Terminal presentation follow-up: corrected the Enter newline being labeled
JARVIS and made the console prompt inline/flushed. Console regression and all
197 tests/static checks pass; physical manual confirmation is pending. No
authorization, adapter or milestone scope changed.

## M2 conversational completion follow-up (2026-10-10)

The prior Windows safety completion did not establish conversational usability.
The reported transcript is now represented by a separate frozen 23-turn corpus,
with a 100% / zero unauthorized dispatch gate in addition to the unchanged
18-case >=90% gate. Old profiles and failed reports are preserved.

Implemented: whole-message natural request resolution; selection and permission
separation; stale identity clearing; permitted candidate schemas with exact
references; fresh action context; actionable close handoff; `/confirm-empty` and
terminal-only `/clear`. No typing/saving/general desktop or M3 functionality.

v9 passes 23/23 on two runs and 17/18 on two original-corpus runs. The remaining
classification error is generic `Open my editor`: unsupported instead of clarify,
with zero effect; `Open my text editor` resolves correctly. This meets the original
unchanged 90% gate and the added 100% conversation gate.

Complete: attended actual qwen3:8b retest (`m2-live-conversation-v9-r1.json`): two
genuine windows opened sequentially, natural focus variants, unconfirmed-close
handoff, `/confirm-empty`, polite clean close, missing pronoun clarification,
manual synthetic dirty close with zero admission, physical global stop followed
by cancelled focus with zero admission. Three input/focus-change rejections are
preserved in that report. Five effects have independent native postconditions.
No pre-existing windows; one unsaved synthetic window remains for manual handling.

Final validation: 244 tests, lint, formatting, dependency and diff checks pass.
Doctor now recognizes explicitly selected matching M2 evaluation evidence while
remaining observational. Old profile/report gates remain reproducible; new
profiles require matching conversation evidence as well. Default simulation,
whole-window clean disposable confirmation, no typing/save/discard and no M3
remain deliberate limits. M2 completion is measured for this PC and profile.

### Operator transcript correction after v9 completion assessment

The v9 assessment was too broad: real operator conversation still made false say
completion claims and missed editor/repetition phrases. This follow-up fixes those
specific gaps with controller presentation enforcement and versioned narrow request
resolution. Clarification is bound to a single already selected window, never to
an arbitrary personal window. Unknown input-during-verification stays blocked;
recovery instructions identify the required manual review.

Current final source: planner-m2-v10; original r3 18/18 and expanded 29-turn
conversation r2 29/29, zero unauthorized dispatches. Initial attended v10 report
is retained as failed due to a missed state-claim wording; corrected guard passes
regression tests and the final real-model no-effect terminal check. Native real
open/new phrases/clean close have independent postconditions; a bound clarification
focus was correctly blocked for changed input, not falsely reported as success.
257 tests/static/dependency checks pass. M2 is still a bounded attended Notepad
controller, not unrestricted natural-language desktop control. No M3 work was
included in that M2 assessment.

### Initial M3 — approved public currency retrieval (2026-10-10, historical scope)

Complete for the measured RTX 4070 desktop and existing qwen3:8b profile:

- Existing deterministic M1/M2 baseline reviewed: 257 passing tests; actual M1
  same-PC live/offline evidence and M2 Windows evidence retained. Both current
  M2 qualification report contracts still match after M3.
- Separate disabled/fixture/enabled public-data configuration, without enabling
  real Windows actions or changing the local model/loopback gateway.
- Existing broker/registry integration with owner-owned semantic scope, exact
  typed model proposal, authorization, durable intent, admission gates and
  independently validated currency evidence. Failed public reads/recovery do
  not latch desktop control or automatically replay.
- One reviewed provider: Frankfurter v2, ECB-specific daily reference pair routes.
  Actual socket-peer binding, normal TLS/SNI, public-address checks, no redirects
  or environment proxies, bounded worker/watchdog/deadlines/bytes/concurrency,
  no automatic retries, and pair-only public disclosure.
- Runtime-owned source records, date-only source precision, UTC/local retrieval
  times, bounded public-only cache, explicit stale policy, source follow-ups,
  trusted decimal conversions/rounding and local supplied-rate calculations.
- `/cache`, `/cache-clear`, `/refresh-rate`, observational doctor evidence,
  explicit `currency-check` and `eval-m3`; non-secret examples and provider ADR.
- Final deterministic gate: 375 tests in 11.16 s, lint/format/dependency/diff checks
  pass. Real provider r3: both directions pass. Real configured model, actual
  Conversation/broker/provider r6: 11/11 frozen cases, zero desktop executions.
  Failed r1/r2 and intermediate passed r3/r4/r5 are preserved; no gate weakening.

M3's narrow gate is met. Physical M3 network disconnection was not tested:
offline behavior uses a labeled provider fault and disabled-network policy.
No new attended Notepad effects were performed; existing M2 evidence remains
separate. General internet research, other currency pairs, intraday quotations,
transactions, Notepad typing/saving and all M4 work remain outside this milestone.
See `M3_TEST_REPORT.md`, `PUBLIC_DATA_COMPATIBILITY.md` and final build evidence.

### M3 generic provider-supported currency clarification (2026-10-10)

Complete for the same PC/profile/config; supersedes the initial two-pair limitation.

- Generic canonical-code arguments; provider-wide `supported_currencies()` through
  the same fixed broker-admitted public transport, validated membership before pair
  dispatch and independent validation before factual rendering.
- Bounded provider/version/origin/UTC/TTL catalogue cache, malformed/expired fail
  closed, no support invented from ISO syntax or the model. Actual metadata advertises
  45 codes; fresh pair availability is checked separately, including legacy limits.
- Seven representative deterministic pairs and arbitrary synthetic advertised codes
  prove no per-pair source change is needed. Native provider reverse quotes only;
  no unsafe local inverse/cross fallback. Trusted Decimal math and display policy.
- Compact/repeated-base amount fix, reviewed names, pending amount replies,
  single-pair session followups, source/effective/refresh and context invalidation
  prevent unsourced numeric model responses. Identity at rate 1 is local; local
  calculations require unexpired cached coverage and never request metadata/quotes.
- Preserve v1 corpus/failed evidence; freeze expanded v2 with original 11 + 23 new
  cases. Final real provider v2-r2 3/3 including EUR/USD; actual qwen3:8b/broker/live
  provider v2-r2 34/34, unchanged 100% / zero desktop-action gate. Doctor matches.
- Final default suite 429 passed in 12.23 s; lint, formatting (58 files), dependency
  and diff checks pass. M2 original qualification still matches; no Windows effects,
  package/model installation, network-setting changes, push or M3 commit.

Known constraints are documented: daily data, seven-day source age, provider legacy
coverage distinct from fresh quotes, canonical codes for unreviewed names, cached
metadata needed before local-only calculation, and simulated outage rather than
physical M3 disconnection. No general web/crypto/securities/banking/trades/payments
or M4. Stop after M3 for review.

### M3.5 — local SearXNG public research (2026-10-10)

Authorized by the M3.5 attachment and the user's no-paid-search clarification.
Do not begin M4. Preserve M0–M3 and all old passed/failed evidence.

- Implemented: replaceable search-provider/fetch interfaces, local SearXNG JSON
  adapter, explicit endpoint-specific infrastructure permission, independent pinned
  public HTTPS, supervised cancellation/time/memory/byte bounds, inert HTML/plain/PDF
  extraction, controller-issued result/source/excerpt identities, broker grants and
  journal/read admission, strict research model boundaries, extractive citations,
  dates, session followups, independent controls and public memory caches.
- Deterministic tests: 120 new offline research cases currently pass; full combined
  suite and final static/dependency checks are being verified. No new Windows effects.
- Real public source + real local model: Python venv URL fetched through the broker;
  initial altered-quote failure r1 and insufficient assessment r2 retained; r3 passes
  the narrow owner-URL check, not search qualification. Final evidence still pending.
- Existing M3 real model/provider corpus rerun: 34/34, zero desktop dispatches,
  `m3-qwen3-8b-v2-r3-m3_5.json`. Original M2 reports still match current qualification.
- Blocked: live SearXNG search/full real-provider model corpus. No detected Docker
  or Podman/runtime distribution. No host installation/configuration performed;
  exact prepared Windows instructions are in SEARCH_PROVIDER_COMPATIBILITY.md.
- Added model-assisted consideration for scoped factual questions, while explicit
  freshness overrides and trivial-topic exclusions remain controller-owned. The
  model's confidence cannot bypass disabled networking or widen the public query.
- Open qualification limits: answers select
  evidence excerpts rather than unrestricted paraphrases. Latest-event ordering,
  semantic relevance/conflict adjudication and broad live-source behavior are not
  certified. These are completion gaps, not silently weakened acceptance criteria.

M3.5 is not complete. Finish available validation and record actual results; keep
live search and remaining qualification work visible for review after provisioning.

Final available validation: **559/559** deterministic tests in 15.70 s; lint,
formatting (75 files), dependency and diff checks pass. Narrow real public URL +
qwen3:8b r7 **1/1**; real local-model planning with synthetic web r3 **3/3**; final
matching M3 regression r5-m3_5 **34/34**, zero desktop dispatches. Failed r1/r2 and
all intermediate evidence retained. SearXNG full live search remains pending.
See M3_5_TEST_REPORT.md for actual commands, receipts and qualification limits.
Additional regressions cover new/recent/compare forms, empty source-view questions,
NAT64 private translations and full structured currency execution with web enabled.

### M3.5 follow-up — assistant self-identification

Fixed identity questions incorrectly entering public research. Existing local
chat now handles whole-request identity forms regardless of web enablement;
external identity topics retain research routing. Added 31 offline regressions;
full suite 590/590, lint/format/dependency checks passed. M3.5 live-search setup
and qualification remain pending; this correction does not complete the milestone.
# 2026-10-10 follow-up: local search provisioned, full gate still failing

- User-provided Docker Desktop is operational. Authorized local SearXNG setup is
  complete: official pinned image, private JSON-enabled settings, localhost-only
  port 8080, manual lifecycle, no restart policy. JARVIS private web.toml is ready.
- Actual real-provider/local-model frozen evaluations are retained: r1 1/10
  (Ollama stopped), r2 8/10, r3 7/10, r4 7/10. No full gate passed.
- Fixed gzip compatibility within unchanged byte ceilings, per-source text space
  and combined synthesis context budgeting; strengthened two-source scoring.
- 597 deterministic tests passed in 18.60 s; lint, formatting and dependency checks
  passed. Existing M3 report still matches, verified by doctor exit 0.
- Remaining blockers: unstable/inaccessible upstream pages, insufficient second
  sources for news/comparisons, and broad semantic/latest/conflict qualification.
  Do not declare M3.5 complete or advance to M4. See M3_5_TEST_REPORT.md for details.

The separate live conversation smoke r2 passed 5/5 (identity, documentation,
source view, fresh followup, independent web disable). No real Windows adapter
was selected. Full milestone qualification remains failed/pending as above.

### Source-selection follow-up ? 2026-10-10/11

Implemented same-task alternative candidates, diverse domains, lower-priority
social/derivative sources, exact reviewed biography refinements, relevant paragraph
selection and measured failure byte accounting. Backed up the private configuration;
now 8 results, 5 attempts, 1 MiB/page and 3 MiB/task. No network/access protection
or hard ceiling was relaxed. All 610 deterministic tests passed in 20.82 s.
Live Lee Zii Jia research now retrieves biographical information. Shrimp research
retrieves usable pages but its worldwide-record conclusion remains insufficient.
The frozen retrieval/binding corpus r5 passed 10/10. Broad semantic/freshness/conflict
qualification remains open; its old full_milestone_passed flag is not milestone
completion. Future reports distinguish the corpus gate and full qualification.
No M4 was implemented, no real Windows effects ran, and changes remain uncommitted.

Final 2026-10-11 validation: frozen corpus r6 passed 10/10, exit 0, zero Windows
effects; corpus_gate_passed=true, full_milestone_passed=false with explicit semantic,
latest-ordering and conflict qualification limits. Final source SHA256:
044046565d48d573e4585ed9b167a618cf09a9278e2bf64d2031259a90bc5fb0.
All 610 offline tests passed in 20.82 s; ruff lint/format (76 files), pip check and
diff check passed. Doctor exit 0 still matches the existing 34/34 M3 report, local
model ready, no public provider contact. Source-selection work is complete for this
correction; broad M3.5 semantic/freshness qualification remains open. Historical
failures and intermediate results are retained. No commit/push or M4 work ran.

2026-10-11: User-requested concise chat presentation completed. Normal verified web
and currency replies omit reference metadata and diagnostic footers. Detailed broker
records and source-on-request views remain; uncertainty/conflict/stale warnings
remain visible. No research schema or acceptance gate changed. Full validation:
615 tests passed (19.82 s), Ruff lint/format, dependency and diff checks passed.
No new live model or Windows qualification claimed. Restart chat to load the change.

2026-10-11 follow-up: Updated matching simulated M2 qualification after the
conversation.py presentation change invalidated old v10 fingerprints. Frozen
model corpus passed 18/18 and conversation corpus passed 29/29, both with zero
unauthorized dispatches, saved as v10-answer-only-r1 reports. Observational
qualified() checks passed against the installed model and current code/profile.
Real chat must reference these new reports. Historical reports and gates remain
unchanged; no new genuine Windows qualification claimed.

2026-10-11: Simple quantity × unit-price conversions implemented and validated
through the existing currency broker. The reported ticket request resolves to
1600 SGD to USD; arithmetic stays local and only the pair reaches the provider.
Unclear/multi-purchase/tax/discount requests clarify rather than ignoring terms.
Full tests 647/647; lint, formatting and dependency checks passed. Actual local-model
plus public-rate smoke check passed with independent Decimal verification; unchanged
frozen M3 v2 corpus passed 34/34 with zero desktop effects. Detailed provenance is
still checked in broker evidence; concise visible calculations remain checked.
Fresh M3 report: m3-qwen3-8b-v2-quantity-r1.json. Existing M2 answer-only reports
still match, so no additional startup command change is needed. No native Windows
or physical-offline validation claimed, and no milestone expansion or commit.

2026-10-11 follow-up: Reported quantity-question typo and next-turn correction now
resolve through currency routing. Reuse only an explicit same-session pair, recompute
the quantity locally, clear context across unrelated turns, and refuse conflicting
currencies or inherited discounts/fees. Missing pair gets trusted clarification.
652 tests and quality checks passed. Actual two-turn local-model/public-rate check
passed on final source (m3-quantity-followup-qwen3-8b-r2.json); frozen M3 v2 final
quantity-r4 passed 34/34 with zero desktop effects. Intermediate reports preserved.
Both M2 answer-only reports remain matching. Restart latest command unchanged.
Broader natural-language coverage and M3.5 qualification remain bounded; no M4 work.

2026-10-11: Corrected another quantity grammar gap: `how much would 40 tickets
worth in USD` and related worth/be-worth questions. Twelve broker wording variants
and conflicting-count/discount checks added. 665 tests and quality checks passed.
Exact reported sentence passed real local-model/public-rate smoke verification;
frozen M3 v2 quantity-r5 passed 34/34 with zero desktop effects. M2 report paths
still match; restart with the latest command unchanged. General language coverage
remains bounded; no milestone expansion or native Windows effects.

2026-10-11: User requested committing the current M3.5 checkpoint. Pre-commit checks
passed: 665 tests (22.97 s), lint, formatting, dependency and diff checks. Preserve
historical evaluations and remaining semantic/freshness qualification limits.
Model-led natural-language routing and broader conversation redesign are discussed
future work, not included in this checkpoint. Local commit only; no push.


2026-10-11: Conversation redesign implemented as opt-in assistant-v1 within M3.5.
Local model classification/typed plans replace pre-inference currency grammar
rejection for this candidate. Controller-bound operand expressions use bounded
Decimal arithmetic, numerical follow-ups preserve same-session roles, and verified
results receive a natural rendering with guarded fallback. Public queries remain
owner-only and source evidence remains authoritative. Existing Notepad intent and
ambiguity routing are retained; no Windows permission can be granted by the new
interpreter. Unsupported answers retain their specific explanation in chat.
All 706 offline tests pass; lint, format and dependencies pass. Live qualification
is separate and remains mandatory. Historical failed/intermediate reports are
preserved. The 2048-token staged candidate scored 16/18 (two invalid responses);
the first corrected M2 model corpus passed 18/18 with zero unauthorized dispatches.
A separately versioned private staged-v2 profile tests 4096 output tokens,
16384 context, 60-second read timeout, while retaining the 120-second original
task deadline and eight-turn limit. Legacy defaults and profiles stay unchanged.
Do not use historical M2 evidence for the candidate. Simulation remains default;
no new native Windows or physical-offline qualification is claimed. No M4 work.
Final live outcomes and remaining qualification blockers are recorded in BUILD_LOG.


2026-10-11 final continuation: 724 regression tests pass; lint, formatting (81
files), dependency and diff checks pass. Final assistant-staged-v2 source/profile
hashes match saved reports. Interpretation 16/18 and frozen M3 v2 currency 29/34
FAILED unchanged 100% gates. Missing-price clarification, currency follow-up
context and inference timeouts remain blockers; the candidate is not promoted.
Matching Notepad simulation 18/18 and conversation 29/29 pass with zero unauthorized
dispatches; no new attended native validation is claimed. Actual public smoke
passed three narrow examples with independently checked arithmetic/rates and
retrieved biography evidence. Biography output fell back to verbose excerpts;
broad research semantics, relevance and freshness remain unqualified. Preserve
all failed/intermediate evidence. README exposes only opt-in simulation testing.
No new physical-offline validation, model downloads, system changes or M4 work.
