# 0019 — Fixed private vision-to-chat handoff

The owner explicitly requested improved integration between the installed vision
and chat models so screen answers feel natural. This authorizes a fixed two-stage
M5 pipeline within the existing brokered read. It supersedes MODEL-05's initial
single-model restriction only for this admitted screen-read explanation.

Keep perception structured and private. Use the active primary text profile for
one bounded, text-only explanation with a dedicated non-action response boundary.
Pass controller-issued evidence references and limited local conversation as
untrusted data. Never run this through the general planner or public research.

Bind the answer to the exact observation and request/revision/model. Retain the
same hard expiry, indicator/liveness, cancellation and independent target checks.
Preserve uncertainty and capture age. Keep Wordle recommendations deterministic.
If the explanation fails, display only the validated vision reading with an honest
limitation and a safe diagnostic receipt. No model substitution or desktop replay.

Screen discussion is bounded in-memory working context. It remains separate from
ordinary history and tools, is usable only for fresh same-target screen requests,
and clears on topic change/revoke/shutdown. It grants no persistent memory,
automatic search disclosure or new UI control.

Evidence binding does not establish semantic entailment or correct perception.
Retain that limitation and actual model/Windows evidence separately. See
[implementation and validation](../SCREEN_CHAT_HANDOFF.md).
