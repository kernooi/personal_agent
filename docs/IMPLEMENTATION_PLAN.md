# JARVIS implementation plan

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
