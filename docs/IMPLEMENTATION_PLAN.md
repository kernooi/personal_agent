# JARVIS implementation plan

## Natural action wording (2026-10-14)

Corrected the shared GUI/terminal legacy action path: service/title fields are
parsed independently, unfamiliar wording gets bounded local-model extraction,
and configured media/apps inform capability explanations. Unique exact titles
outrank similar titles; ambiguous exact duplicates still ask. Media selection
survives ordinary chat while pending multi-step continuations do not. YouTube
artist text must match retrieved creator metadata, independently of title words.

No new tool authority: existing controllers resolve all targets and the broker
executes each phase. Literal owner text, reviewed operation ceilings, strict JSON,
request/revision/deadline, controller snapshot, cancellation and single-use approval
checks remain. Added separate 100% / zero-unauthorized-dispatch wording gate for
real semantic fallback, retaining all existing frozen corpora and failed results.
See decision 0016. The final wording v3 corpus passes 33/33 with actual qwen3:8b;
Notepad 24/24, conversation 41/41, app 31/31, browser 27/27 and Spotify desktop 25/25
also pass at their unchanged 100% gates. All six source/profile/runtime-matching
reports authorize the shared launcher. Older wording corpora and failed runs remain.

Attended song/playlist Spotify and YouTube wording regressions pass. Spotify's
transient search-control rebuild is handled by bounded repeated reads, never repeated
URI/value/click delivery; identity/window errors still stop. YouTube lab reobserves
the same pinned video after the ad before playback controls. Ordinary Chrome stays
excluded. Chrome's update to 155.0.8059.41 required operator-approved private
registration refresh; the old identity and existing profile were preserved.

Full suite: 1252 passed in 51.51s; lint, format (150 files), dependency and whitespace
checks pass. Combined real startup and GUI worker both reach ready and quit cleanly
with all existing features and new language qualification. No commit/push.

## Device-discovered applications (2026-10-12)

User selected this Windows PC first with an extensible platform interface.
Implemented dynamic AppsFolder catalog, desktop/package launch identity, generic
open/focus/minimize/close controller, strict model boundary and existing broker
integration. Added bounded supervised worker, same-user/session/process/binary
identity, exact commit, desktop lease, independent state proof, single-use work
review and unknown-outcome manual-review controls. Notepad's close boundary stays
strict. Platform protocol and fake implementation are portable; other native
platforms/devices are not implemented or qualified. Conservative catalog coverage
is 145 supported launch entries, 51 unavailable; no all-app guarantee.

Deterministic application/controller/native-boundary tests, frozen local-model
gate, configuration, CLI controls and architecture decision are implemented.
All four existing Notepad/conversation/media gates have refreshed passed reports;
failed evidence and the 100% gates remain unchanged. Combined simulation startup
works with currency, research and media configuration. Attended native r4 passed
Calculator's four operations, repeated minimize, Character Map open/minimize/focus
and physical global-stop cancellation with zero new admissions. Three existing
windows preserved; Character Map left for manual cleanup after stop. Failed
native r1-r3 remain with manually acknowledged uncertain outcomes, no replay.
Host-frame and detached-content lifecycle verification were added and tested.
EXE close remains simulation-tested, not covered in this native lab. Other apps
need individual compatibility validation. No generic input, shell arguments,
installer, remote device, other OS effects, commit or push are included.

Final checks: 1015 tests passed; lint/format/dependencies/diff clean. Current
application report r13 passes 28/28 with zero unauthorized effects; source/profile/
actual-model qualification checks pass alongside refreshed original gates
(24/24 Notepad, 34/34 conversation, 22/22 media, 12/12 Windows media). README has
the combined startup command. Intermittent pre-existing currency fixture failures
were observed and recorded; final unchanged full repeat passed, cause unresolved.
Windows-first implementation and bounded native validation are complete; additional
app compatibility and other native platforms remain future validation/work.

## Spotify Windows backend follow-up (2026-10-11)

User explicitly selected Windows media controls instead of developer-app/OAuth
setup. Implemented and deterministic-tested the native Spotify-only adapter,
replaceable backend configuration, broker/stop integration, bounded worker,
independent verification, lease and historical API journal compatibility.
Created private `media-windows-v1.toml`; simulation remains default, with separate
`--real-media --media-attended --windows-media-report` for actual playback.
Current local-model qualification passes 12/12 new frozen native cases and 22/22
unchanged original media cases, zero unauthorized dispatches. Attended native
current/pause/resume/next/previous and physical stop PASS in report r2; failed r1
retained. Final checks: 927 tests pass, lint/format/dependency/diff checks clean.
No API setup needed for this path; app launch, song search, volume and remote
devices unsupported. Optional official API and Netflix setup remain pending.
No automatic fallback, global media keys, broader UI control, commit or push.
Overall M4 still NOT FULLY VERIFIED. See ADR 0007 and BUILD_LOG for exact evidence.

## M4: approved Chrome and media slice (2026-10-11, NOT FULLY VERIFIED)

The user's M4 attachment supersedes the preceding M3.5 stop boundary. Preserve all
prior passed/failed evidence; the assistant-v2 interpretation/currency candidate
remains unqualified. Do not begin M5 or generic M8 control.

1. Baseline verified: clean 885c8ff, 753 deterministic tests, lint/format/pip checks.
2. Installed signed stable Chrome inspected; private profile and pinned registration
   implementation added. No ordinary Chrome profile reads/attachment.
3. Implement semantic media registry on existing broker, persistent supervised
   worker, strict references, grants/admission/journal, independent observations,
   cancellation/takeover/unknown outcomes and independent configuration.
4. Primary YouTube search/open/current/play/pause/resume; Netflix manual-login and
   narrow title search/open; official Spotify API with OS-protected credentials,
   scopes/device checks and truthful setup/entitlement restrictions. No fallback.
5. Offline adversarial/fixture tests, frozen local-model qualification, opt-in
   attended Chrome lab and compatibility/privacy/decision documentation implemented.
6. Actual Chrome 154.0.8037.98 / Playwright 1.63.0 YouTube search/open/video identity,
   play/pause/resume/current and physical hotkey passed in live v1-r6. Ads finished
   naturally; no bypass or replay. Failed reports remain preserved.
7. User explicitly left Spotify OAuth/account/device and Netflix manual login
   pending. Normal-Chrome coexistence/live takeover also remain unverified. Stop
   at M4 for review; never turn the partial platform evidence into overall PASS.


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


2026-10-11: User accidentally reverted the latency changes. Clean starting
worktree at 6e445dd confirmed; committed assistant-v1 and historical reports
remain intact, while the private assistant-fast-v1 profile survives outside Git.
Restored the opt-in assistant-v2 implementation and example: combined simple
interpretation/answering, selective reasoning, strict literal-amount fast review,
verified currency rendering without a model rewrite, owned web evidence routing,
and bounded isolated stage output profiles. All authorization, cancellation,
revision, independent verification and original deadlines remain enforced.
Added session-only numeric stage timing/token/load measurements to diagnose
remaining waits; explicitly invoked assistant reports preserve those measurements.
22 new regression cases cover call reductions and unchanged safety boundaries.
746 tests pass (21.80 seconds), with clean lint, formatting and dependency checks.
Private profile and running Ollama/SearXNG were reused without modification.
Fresh live evaluation is required; restored results will be recorded below.
No native Windows effects, downloads, installation, global changes or M4 work.

Restoration and further latency work finished on final r4 source: 753 passing
tests (24.68 s), clean lint/format/dependency/diff checks. Kept a separate intent
classifier for unresolved numeric/weak-grammar requests after broader merging
failed live tests. Clear conversions and greetings retain shorter paths; typed
no-progress stopping and numeric profiling are implemented. Actual median
13.9505 -> 10.095 s (single historical comparison; current run warm). Interpretation
14/18 and M3 31/34 FAILED unchanged 100% gates, including an interpretation
accuracy regression versus historical 16/18. Candidate remains opt-in, experimental
and not promoted. Model review, numerical follow-ups and missing-price behavior
are accuracy blockers; complex inference remains slow. Final M2 simulation 18/18
and conversation 29/29 pass; three actual public smoke checks pass narrowly.
Final report source/profile hashes match independently; legacy M2 reports still
match. All failed/rejected r1?r4 results are preserved. README documents the fast
simulation command and qualification limits. No new native/physical-offline
validation, system changes, installs, model downloads, commits or pushes. M3.5
boundary retained. See BUILD_LOG for exact commands, measurements and limitations.


2026-10-11: Selected Notepad minimize extension in progress. Added strict
windows.minimize proposals, exact selected scope/grants, native asynchronous
minimize and independently observed minimized state, plus restoration on focus.
No generic app control. Frozen m2-corpus-v2 (24 cases, 100%) and
m2-conversation-v3 (34 cases, 100%) retain all historical cases and add minimize.
Regression coverage includes unsaved/multi-tab minimize, target isolation, stale
identity, stop/cancellation, user takeover, revocation, missing permission, modal
handoff, unknown non-replay and completion-prose honesty. Fresh qualifications and
attended native results are required before declaring real minimize validated.


Final deterministic checks: 953 passed (29.89 s); lint, formatting (104 files),
dependency and diff checks pass. Actual local model final minimize action 24/24,
conversation 34/34, existing Chrome media 22/22 and Windows Spotify 12/12 gates
pass with zero unauthorized effects. Four independent qualification checks return
True for final reports. Failed r1/r2 ambiguous-editor results and intermediate
passing reports remain preserved. Historical profiles do not grant minimize.
README and BUILD_LOG contain current report filenames/launch commands. Attended
native minimize validation remains pending the requested operator readiness; no
Windows effect, native pass, commit or push is claimed for this extension.


Attended native minimize validation completed after explicit operator readiness.
Actual qualified qwen3:8b -> broker -> registered Windows Notepad passed all five
checks: open, minimize, repeat minimize, restore/focus and safe close. Independently
verified IsIconic=True on both minimize checks and IsIconic=False plus exact
foreground HWND on restore. No pre-existing windows (preservation check True).
Report m2-minimize-windows-v1-r1.json passed; persistent private journal retained.
This supersedes pending readiness above. Selected Notepad minimize is implemented
and validated on this PC. Other apps remain outside this window-effect scope.

## 2026-10-12 - Owner-requested natural lifecycle correction

Implemented OS AppsFolder activation, signed versioned/exact packaged runtime
association and durable launch/runtime evidence. Natural authenticated close now
binds a selected/sole verified window without extra confirmation; Notepad dirty,
mixed, dialog and unknown protections remain. Multiple windows accept a number;
current-profile bare/pronoun requests retain their controller route. Normal close
to tray uses exact hidden-window proof and makes no termination claim.

Live gates: apps 31/31, M2 decisions 24/24, conversation 41/41, media 22/22,
Windows media 12/12. Current qualification helpers match. Failed reports retained.
Attended Discord/Spotify/Notepad lifecycle passed across a linked zero-delivery
continuation, preserving original windows and stopping new admissions. Earlier
physical hotkey evidence retained. 1027 tests passed. Added one-command attended
`scripts/Chat-JarvisAll.py` and updated full README command with refreshed reports;
actual combined startup/quit smoke passed. Other application/platform compatibility
needs separate validation; unverified delegates/elevated/tray-only apps remain
unsupported. Netflix/account setup stays pending. No new installation, generic
input, model downloads, global settings, commit or push.

## 2026-10-12 - Steam compatibility correction

Completed generic signed descendant runtime identity using bounded, revalidated
native process ancestry instead of application-name rules. Read-only discovery
and durable verification identify Steam's helper-owned window. Delivered open
with a changed input timestamp now pauses and reconciles that exact window once,
without new effects. Stable exact unique proof is required; takeover before
admission, continuing input, changed identity, stop and genuine uncertainty remain
fail-closed. No acceptance gate or historical test/result was weakened.

1042 deterministic tests passed; lint/format/dependencies passed. Actual local
application corpus remains 31/31 with zero unauthorized effects, current report
applications-qwen3-8b-v3-r4.json. Existing M2/media gates still match. After attended
readiness/manual reviews, Steam open/minimize/restore-focus/close and zero-admission
stop passed in application-steam-windows-v1-r4.json. Three failed native reports
and passive diagnostic observation are preserved. Original user-journal uncertainty
was acknowledged through the controller using the owner's manual inspection;
historical UNKNOWN remains, unresolved desktop count is zero, and no replay occurred.

One-command combined launcher and README reference the current application gate;
combined startup/quit succeeded. Steam normal close hides to tray. Operation latency
was about 9-10 seconds; broader application coverage, orphan/exited delegates and
other platforms remain separate compatibility work. Existing account/service
setup limitations remain. No automatic commit or machine configuration changes.

## 2026-10-12 - Interactive launch settling follow-up

Corrected slow cold-start verification and overly brief activity settling. Open now
allows 30 seconds of observation and up to three read-only epochs for the same exact
unique window after releasing ownership. Continued input, identity changes, ambiguous
or missing windows, cancellation and pre-admission takeover remain fail-closed. No
effect replay; uncertain messages retain diagnostic cause. Historical failed evidence
and the user's manual acknowledgements are preserved.

1044 tests, lint, formatting and dependency checks passed. Actual qwen3:8b frozen
application gate r5 passed 31/31 with zero unauthorized effects; all five qualification
helpers match. Attended Steam/Photoshop open/minimize/focus/close and zero-admission
cancellation passed all nine native checks in application-startup-windows-v1-r1.json.
Baseline windows were preserved. Steam normal close hides to tray; Photoshop test
window closed. Combined helper startup/quit accepted all qualifications; README/helper
use r5. No document/account effects, installation, settings, commit or push. Individual
compatibility coverage and operation latency limitations remain.

## 2026-10-12 - Runtime availability restored

Recovered stopped standalone Ollama using the already approved process-local
settings; verified actual cloud-disabled startup log, API version 0.40.2 and existing
qwen3:8b. Combined startup/quit passed without effects. Ollama still requires manual
startup after it stops or Windows restarts; no startup service or global setting added.

## 2026-10-12 - Search endpoint restored

Restored the previously approved dedicated SearXNG container using existing pinned
image/configuration, loopback-only host port 8080 and manual lifecycle. The user's
other container lacked host port publication. JSON API and JARVIS supervised adapter
checks passed. Full end-to-end research was not reevaluated; no software download,
global settings, source change, automatic service or commit.

## 2026-10-12 - Concurrent-use targeted window policy

Implemented the owner's explicit input/focus behavior change for app and Notepad
lifecycle only. A trusted targeted profile permits continued PC use without revoking
the exact named/selected window command; exclusive mode remains default for old
profiles. Exact identity/scope, registration, dirty/dialog checks, grants, expiry,
cancellation, secure-desktop rejection, independent state verification and no-replay
requirements remain. No generic input, force-focus or browser target relaxation.
See decision 0010. Private v10 profile and historical corpora/reports are preserved.

1064 tests passed; lint/format/dependency checks passed. Current targeted gates:
apps v4 31/31, M2 decisions 24/24, M2 conversation 41/41, media 22/22 and Windows
media 12/12; all five qualified. Failed M2 first-run report retained without changing
requirements. Calculator native test passed while operator input occurred during a
paused actual-model minimize request, with independent state and zero-admission stop.
Separately attended registered Notepad lifecycle passed all five native regressions,
including clean-close and preserved existing windows. Combined startup/quit accepted
new profile/current qualifications. Helper/README point to that setup. No installation,
global settings, automatic commit/push or new UI capabilities.

## 2026-10-12 - Natural YouTube request routing

Implemented bounded conversation-level search/open/play through existing broker
tasks. Named requests find their own results; broad channel requests ask which video
and retain requested playback through an exact current selection. Owner/browser
session, generation/deadline, scoped model choices, approvals, stop and independent
verification remain. Ads stop automatic play; unknown effects never replay.
Decision 0011 records this change, without new browser/account/UI permissions.

1104 tests, lint/format/dependency checks passed. Actual local gates passed: M4 v2
27/27, Windows Spotify 12/12, apps 31/31, M2 decisions 24/24 and conversation 41/41.
All five qualification helpers match. Historical corpora/results and failed app
explanation reports remain. Added missing informational catalog context without
changing target authority. Helper/README use refreshed reports. Live Chrome retest
is prepared but pending attended readiness and exit of the current chat, whose stop
hotkey blocks a second real session. No new browser effects, install/settings or push.

## 2026-10-12 - YouTube workflow native evidence

Attended readiness received and previous chat exited. Real compound search, matching
result selection with retained play goal, verified playback, pause/resume and
zero-admission software stop passed in m4-youtube-flow-windows-v1-r2.json. Dedicated
test context closed; ordinary Chrome excluded. First failed report is preserved:
the lab did not copy a post-ad snapshot generation, causing zero-delivery pause
rejection, not an uncertain action. Fixed harness bookkeeping via existing adapter
method; production source/gates unchanged. Combined startup/quit passed. This
supersedes pending live validation above; no sound-verification or general-all-videos
claim, account changes, ad bypass, installation, global settings, commit or push.

## 2026-10-12 - Combined-session media review visibility

The reported compound requests were blocked by a historical UNKNOWN YouTube search
in the combined private application journal, not by the new request grammar. Their
records contain no prepared/admitted actions. Standalone native validation used a
separate lab journal and did not resolve production history.

Startup and blocked media requests now identify the pending review and exact command;
no model/browser call occurs while blocked. Invalid media-proposal presentation no
longer labels real-mode rejection as simulation. All admission/unknown-outcome
protections remain. Combined-controller restart/review regression passed, as did
1107 tests, lint/format and dependency checks. Isolated backup of the actual journal
reproduced the block with the corrected explanation and zero model/media calls.
Original journal was untouched during diagnosis. Owner later confirmed the dedicated
window/chat closed; recorded the explicit manual-review event through existing control.
No pending media reviews remain; the original UNKNOWN action remains unchanged.
No browser launch/effect or replay was performed. Current local qualification reports
passed all unchanged gates: M2 24/24, conversation 41/41, applications 31/31, media
27/27 and Windows Spotify 12/12. Helper/README use the new media-review reports.
Restart chat to load this fix. No new attended browser validation was performed.

## 2026-10-12 - Spotify installed-app search extension

Owner chose native Spotify song/playlist search without developer setup. Implemented
Spotify-specific accessibility controls and a supervised worker through the existing
media broker. Search, selection and play remain separate; metadata/context and unique
Windows Spotify playback state verify results. No arbitrary UI, account mutation,
credentials, API fallback or later milestone capabilities. Existing backends retained.

Read-only native inspection confirms the Store app's search/control surfaces. 43
new offline regressions and the full 1150-test suite passed. Desktop corpus v1 is
frozen (25 cases, 100% gate). Actual model qualification is running. Native attended
search/song/playlist verification is prepared in Test-JarvisSpotifySearch.py; readiness
must be received before effects. Combined launcher will switch to a separate private
desktop config only after validation; all affected qualifications require refresh.

Follow-up: native search r1/r2 stopped before playback; owner reviewed both. Fixed
literal title preservation and changed search activation to a locked Windows.System
package-targeted spotify:search URI. Native r3 exposed a Python/WinRT overload error,
reviewed by the owner and corrected with a regression test. Native r4 reached song
results but stopped at the client's space-to-plus query readback and duplicate filter
label; corrected exact representation matching/filter selection. Its required manual
review and the corrected attended song/playlist playback test remain pending here.
All failed results/UNKNOWN journal actions are retained; no playback was sent by
those failed tests. Desktop qualification r3 failed 16/25 under GPU saturation;
after owner freed the GPU, r4/r5/r6 passed 25/25 with the unchanged gate. Latest full
suite: 1159 passed; lint/format/dependencies/diff checks passed. Refreshing all
existing combined-launcher qualifications; desktop mode is not enabled there yet.

All refreshed existing gates passed: M2 24/24, conversation 41/41, applications
31/31, browser media 27/27, basic Windows Spotify 12/12; desktop r6 25/25. Every
qualification helper validates the current sources/runtime/profile. Combined helper
and README now use the refreshed existing-backend reports; startup then /quit
passed without effects. Outstanding: owner review of native search r4, corrected
attended song/playlist playback validation, then switching the helper to desktop
configuration only if that validation passes. No commit was requested/performed.

### Completed native search validation

Corrected native URI encoding, both observed track-row layouts, active generic
Pause context, fixed Search-form commit and stale optional filter handling. Native
r10/r11 established correct song play/pause/resume; retained their later playlist
search failures and explicit owner reviews. Rejected the r13 apparent pass after
auditing a copied playlist whose title falsely satisfied requested owner words.
The failed owner audit preserves that error. Selection and the native lab now
check explicit title/creator separately; validated playlist-card owner links supply
creator evidence, and decoy-title regressions prevent that substitution.

Current model desktop v1-r15 passed 25/25 under unchanged frozen 100% gate. Corrected
native v1-r14 passed song search/play/pause/resume, Spotify-owned Deep Focus
search/play/pause and stop cancellation with zero new admissions. Spotify left
open/paused. Full suite: 1167 passed. Combined helper switched to separate private
desktop config; refreshing existing M2/conversation/app/browser/basic qualifications
and verifying combined startup. Other Spotify editions/locales, private playlists
missing from native search, remote-device/volume/account edits remain outside the
measured path. Audible sound and service-API catalog attestation are not claimed.

Completed final refresh: M2 model v1-r2 24/24, conversation v1-r2 41/41,
applications v4-r2 31/31, browser media v2-r3 27/27, Windows playback-only v1-r3
12/12; desktop model v1-r15 25/25. All six current qualification helpers passed.
Combined launcher startup/quit passed with native Spotify search enabled. Final
lint/format/dependency/diff checks passed; 1167 tests passed. Native extension is
complete within its measured compatibility scope; no later milestone or commit.

## 2026-10-13 - Spotify admission failure explanation

Reported named-playlist failure was a zero-effect admission rejection mislabeled
SIMULATED. Observational Windows check confirms Spotify is currently minimized.
Added explicit minimized-window classification and allowlisted natural error hints
through the broker; no automatic restore, effect replay or gate relaxation. Generic
worker details remain private. Four regressions verify actual-mode presentation,
known FAILED outcome and zero playback delivery. Full suite 1171 passed, targeted
media suite 204 passed. Refreshing affected frozen model gates and launcher reports.
This does not implement personal-library browsing or establish search availability
for the owner's playlist. Restart chat and restore Spotify to try native search.

Completed source-bound refresh: M2 24/24, conversation 41/41, applications 31/31,
browser 27/27, Windows playback-only 12/12 and desktop 25/25, unchanged gates.
All current qualification helpers, helper argument inspection, lint/format,
dependencies and whitespace checks pass. Updated combined helper and docs; no
native effect, private playlist discovery claim, automatic restore or commit.

## 2026-10-13 - Restore startup compatibility after owner revert

The owner reverted abandonment code, leaving private configuration keys unsupported
by the restored strict schemas: unknown_outcome_policy in the active combined
profile and spotify_failure_policy in media configs. Backed up each affected private
file and removed only those unsupported keys; all four affected files validate.
Simulation profile default, targeted input policy, local inference, model settings,
registration and permission gates remain intact. Did not reimplement the reverted
feature. Existing M2/conversation/application qualifications match; restored media
contract has no matching historical report, so refreshing unchanged frozen browser
and native Spotify gates with actual local inference and simulated controllers.
Combined helper points to new revert-compat reports. Helper lint/format passed.
No native desktop/browser/playback effect, global setting, commit or push performed.

Final validation: browser 27/27 and native Spotify 25/25 passed; both current-contract
qualification helpers returned True. Combined helper startup and immediate /quit
passed exit 0 without action requests. Restored review-mode code displayed four
historical Spotify uncertainties; these remain unresolved and may block media
requests. No human review was fabricated or old action replayed. Startup schema
mismatch is fixed; restoring abandonment behavior was not requested this turn.

## 2026-10-14 - Desktop chat presentation complete

Owner-approved minimal native GUI reuses the existing combined private setup and
CLI broker: simulation default, explicit attended-PC-controls selection, Start/End,
Enter/Shift+Enter, thinking animation/elapsed time, Stop/Esc and global-stop display.
Versioned JSON framing isolates complete replies from UI state. No raw reasoning,
voice, vision, generic UI, HTTP server, new packages or hidden fallback. Closing is
cooperative and no old task is replayed. Existing reverted recovery policy is retained.

Implemented scripts/Chat-JarvisGUI.py, gui.py, gui_session.py and gui_worker.py;
shared launcher preserves current terminal behavior. Added decision 0013 and README
instructions. Private own-window visual inspection and actual local-model GUI chat
passed; real effects were not sent. 12 GUI boundary tests and full 1183-test suite
pass, along with lint, formatting, dependency and whitespace checks. Existing five
capability qualification checks match. Ollama was manually started with the already
approved process-local cloud-disabled settings for validation; GUI never auto-starts
it. No later milestone, machine-level setup, commit or push is included.

## 2026-10-14 - Automatic local GUI startup complete

Owner-approved GUI opening now prepares registered standalone Ollama and the
installed-profile model, installed local Docker Desktop if required, and approved
cached/mounted loopback SearXNG, then connects automatically. Background stages,
bounded waits, cancellation, existing-service reuse and optional search failure are
implemented. No install/pull, global settings/startup policy or model-callable shell.
Private gui-startup.toml contains registered service metadata; profiles/qualification
remain separate. Real controls still require explicit attended checkbox selection;
that choice reconnects automatically with a fresh context and all broker checks.

Added gui_startup.py, startup/progress integration, decision 0014 and 33 targeted
GUI/bootstrap regressions. Actual auto-opening, cached-container recreation, local
reply and final-source reuse validation passed in simulation without real actions.
Cold Windows daemon/Desktop startup was not forced; cold process/settings/log and
Docker-start paths are mocked and clearly separate. Tk tests retain all assertions
in isolated processes to match production. Full suite 1204 passed; final checks and
qualification matching are recorded in BUILD_LOG. Existing manual-review/unsaved-work
policies, frozen gates and native controls are untouched. No later milestone,
dependency download, machine configuration, commit or push.

Final current-source full suite: 1204 passed in 37.95s. All 33 GUI/bootstrap tests
are retained; no skips or lowered gates. Ruff lint/format (137 files), dependency
and diff whitespace checks pass. Final-source GUI auto-reopen report confirms
simulation Ready with both local services reused; no Start click or real action.
Five existing qualification helpers match current source/profile/runtime. Cold
Docker Desktop/Ollama process start remains mocked evidence, not represented as
an actual forced cold-host test. Current running services were left intact. No
commit or push performed.

### 2026-10-14 — Desktop title bar complete

Owner-requested Docker-inspired navy branding is implemented with a matching
native caption, custom JARVIS monogram, compact LOCAL badge and session controls.
Native window management remains available; unsupported DWM colors fall back
without replacing Windows chrome. Own-window visual inspection and lifecycle/
minimum-size regression passed. Full suite: 1205 passed in 40.39s; lint, formatting
and dependency checks passed. Existing auto-connect/bootstrap and attended broker
behavior remain unchanged. See BUILD_LOG for evidence and initial test correction.

### 2026-10-14 — Modern transcript scrollbar complete

Chat now has a slim rounded thumb with hover/focus feedback, no arrow buttons or
bright track, and no visible thumb when content fits. Drag, wheel, track paging,
keyboard navigation and minimum-size layout were verified with real Tk widgets;
own-window synthetic preview visually checked. Existing reading position stays
stable when new replies arrive. Full suite: 1206 passed in 41.10s; lint, formatting,
dependencies and whitespace passed. Presentation only; previous work is preserved.

### 2026-10-14 — GUI combined-control mode parity

Confirmed GUI uses current source and the terminal helper's same profile and
capability settings. The reported difference was default simulation versus terminal
attended real mode. Prominent explicit control toggle, persistent mode badge and
preview/real status make that distinction clear. No automatic consent or replay.
New exhaustive real-command parity test and actual Tk toggle regression pass;
17 GUI tests passed. Real Windows/media effects were not invoked during validation.
Default simulation and all existing registrations, grants and qualifications remain
required. Full-suite and earlier scrollbar timing evidence are recorded in BUILD_LOG.

Final suite: 1207 passed in 35.25s; lint, format, dependencies and whitespace passed.

### 2026-10-14 — Real GUI default and redesigned chat complete

Owner-selected GUI now auto-connects/restarts with all existing attended real
controls, and animations are always enabled. Removed the toggles; kept visible
attended/global-stop scope, existing qualification/registration gates and offline
failure behavior. Ordinary CLI/profile defaults remain simulation. Decision 0015
records the owner's explicit override of the earlier GUI selection requirement.

Rounded growing composer, placeholder/focus styling, circular accessible Send,
cleaner message spacing and welcome screen implemented without dependencies.
Own-window synthetic previews inspected. 18 GUI tests passed, including automatic
real single-flight startup, command parity, placeholder isolation, keyboard Send,
growth/shrink, minimum-size layout, all animation phases and existing stop/scroll
regressions. Final full suite: 1208 passed in 39.78s; lint, format, dependency and
whitespace checks pass. No live app/media effects exercised for this UI change;
all prior unrelated work preserved. No commit/push.

### 2026-10-14 — Reference bubble GUI and focus correction complete

Conversation area rebuilt with true left/right rounded message widgets, a light
palette, selectable content, Copy message, Latest navigation and responsive width.
Composer focus now hides the placeholder and visibly updates its border/caret;
blur restores the placeholder only if empty. Header/native window management,
automatic attended real startup, always-on animation and existing broker checks
remain. Long-message previews and full-message reader bound widget geometry while
retaining content; in-memory history is bounded and destroyed widgets are pruned.

Normal/focused/compact own-window synthetic previews inspected. Existing scroll,
single-flight, cancellation and stop assertions retained; added actual focus,
alignment, selection, resize, long-reply and history regressions. Final suite:
1210 passed in 43.59s, including all 20 GUI tests. Lint/format, dependencies and
whitespace pass. No live app/media effects or new model capability; no commit/push.

### 2026-10-14 — Dark slate theme and smooth branding complete

Soft dark palette now covers the full GUI, preserving the bubble layout and focus
behavior. New original core mark and send icon use cached, supersampled transparent
PNG rendering without dependencies; native window icons match the header. Hover,
keyboard, disabled states, automatic real control and animation behavior retained.
Own-window and native-size artwork previews inspected; transparent edges verified.
Existing 20 GUI tests pass. Final suite: 1210 passed in 44.38s; lint, formatting,
dependencies and whitespace pass. No global theme/configuration, live app/media
effect, new agent capability, dependency download, commit or push.

### 2026-10-14 — Header badge removed

Removed the text badge beside JARVIS at the owner's request. Real app/media startup
is unchanged; readiness and attended/global-stop status remain elsewhere in the UI.
Full suite: 1210 passed in 43.08s; lint, format, dependencies and whitespace pass.

### 2026-10-14 — Smooth scrolling and wheel stalls fixed

Wheel events now work on blank gaps, bubbles, floating controls and scrollbar.
Fractional pixel targets ease at 16ms intervals; direct navigation and destruction
cancel motion cleanly. New replies respect manual scrolling away from the bottom.
Native Tk regression covers five mapped surfaces, partial deltas, actual endpoint,
reply arrival, navigation cancellation and close. Existing scroll/stop tests retained.
21 GUI tests pass; final full suite 1211 passed in 50.35s. Lint, formatting,
dependency and whitespace checks pass. No real app/media actions or commit/push.
