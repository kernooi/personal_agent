# M0 implementation plan

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

M0 is implemented and mock-tested on Windows/Python 3.13. M1 and Windows control
remain outside this plan, unimplemented and untested. No live qualification claim.

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
