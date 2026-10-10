# ADR 0003 — M3 public currency reads on the existing broker

Accepted by the user's explicit M3 request on 2026-10-10. M2's attended Microsoft
Notepad target and safety requirements remain in force. Stop after M3.

Use Frankfurter v2's provider-specific ECB routes for arbitrary supported pairs,
with a replaceable provider protocol, normalized strict quote evidence, and
trusted decimal calculation/rendering. See `../PUBLIC_DATA_COMPATIBILITY.md`
for official sources, provenance, actual enforcement and limits.
The user's generic-currency clarification supersedes the initial MYR/JPY-only
scope: bounded official ECB metadata is the authority for coverage, with separate
validated TTL caching. Native pair/reverse routes preserve the provider derivation;
JARVIS performs no local inverse/cross fallback. Local identity and supplied-rate
calculations use cached membership and cannot make network requests.

Extend the existing registry/router and broker; do not add a competing agent
loop. A deterministic freshness ceiling resolves supported pair/direction and
amount, rejects ambiguity and unsupported volatile topics, and distinguishes
source follow-ups and explicit supplied rates. The configured local model
proposes a typed action against an exact candidate schema. It cannot widen
the controller's scope. Ordinary explanations/arithmetic remain ordinary chat.

Keep the original immutable model profile and its M2 qualification contract.
The gateway accepts a controller-selected per-request currency decision boundary;
it continues to fully revalidate the original profile and fixed loopback endpoint.
Currency-specific prompting/schema is versioned and hashed for M3 evidence.
Model prose cannot supply current quote facts. Dates, citations, units and
conversion results are rendered exclusively from validated controller records.

Reuse task IDs, revisions, grants, durable intent, admission/cancellation gates
and independent evidence checks. The existing journal's opaque `window_ref`
binding field carries canonical semantic JSON for `app_id=currency`, not a Windows
reference. Storage strictly validates this branch and its public/local/read-evidence
effects; the external proposal contains typed currency arguments, never window
identities. A future journal schema migration can name this generic binding field
without changing current Windows journal compatibility.

Public reads have their own adapter and effect-appropriate failures/recovery;
they cannot acquire the Windows unknown-outcome latch or cause Notepad operations.
Network policy is a separate strict local configuration, default disabled. An
explicit enabled configuration plus a supported owner request authorizes that
pair-only lookup without routine confirmation. It grants no other network/tool
authority. The fixed worker is implementation plumbing, never a shell capability
or a model-selectable tool. No additional desktop, browser, memory or M4 capability.

Preserve failed evaluations. The frozen M3 corpus requires 100% correctness and
zero desktop actions. Qualify adapter/live-model evidence separately; real Windows
qualification and prior M1 offline evidence remain separate. A simulated provider
outage is never reported as physical network disconnection.
