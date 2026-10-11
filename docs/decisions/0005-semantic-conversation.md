# Semantic conversation within M3.5

Status: approved implementation scope; qualification is measured separately.

The user requested the previously discussed conversation improvements after the
M3.5 checkpoint. Repeated additions to a quantity grammar did not address the
underlying problem: an unfamiliar sentence could be rejected before local
inference, and a model could answer a conversion without using a verified rate.

An opt-in, versioned `assistant-v1` profile selects local model intent classification,
then a separate typed interpretation or conversational answer. Legacy profiles
retain their existing path. Explicit Notepad target resolution and evidence
inspection commands retain their controller routing. This does not add an action
capability or expand beyond M3.5.

Currency interpretations identify an owner-mentioned pair and a bounded expression
over controller-bound numeric operand IDs. Python traverses an allowlisted Decimal
AST: addition, subtraction, multiplication, division and parentheses. It never
evaluates model code. Only unit/percentage constants are allowed; every current
numeric value must be represented. IDs are stable during a same-session follow-up.
Numeric memory expires after the profile task interval and is cleared by unrelated
conversation or failure. Conversation history is bounded and stays local.

Controller checks precede a supplemental local model review of operand roles,
missing facts and direction. Rejected interpretations may be corrected at most
twice, before binding or executing an effect. A model review is not an independent
proof of semantic correctness: the frozen corpus measures behavior, and novel
requests remain fallible. No acceptance threshold is reduced to accommodate it.
The review distinguishes missing owner facts from an incorrect plan. A complete
request with a wrong proposed amount is corrected locally before retrieval instead
of asking the owner to confirm the same facts. Complete new purchases do not inherit
an earlier purchase's numerical operands or amount.

The controller can bind a read scope only from an unbound, uncancelled planning
task with the same session/revision, before any action exists. It increments the
revision atomically, validates canonical arguments and retains the original
deadline (also capped by the web task interval). A separate exact tool proposal
then passes the existing broker registry, grants, journaling, admission and
independent result verification. Identical currencies compile to local identity;
supplied rates remain local. Provider metadata determines currency support.

Search queries come from the current owner's public topic, never generated
queries, conversation history, numeric memory or private context. Existing
SearXNG endpoint permission and public fetch restrictions apply independently.
No model obtains a URL, network or Windows execution permission by classification.

Verified results can be rendered naturally. Currency output must retain the
verified conversion and numeric bounds. Web paraphrases bind individual claims
to retrieved excerpt IDs and undergo numeric/citation checks and a supplemental
semantic review. Unsupported output falls back to the verified result or exact
excerpts, without another lookup or effect. The semantic reviewer uses the same
local model and cannot guarantee entailment. Insufficient/conflicting evidence
retains its original uncertainty instead of being rewritten as a supported claim.

All local model turns share the profile's finite turn budget and original deadline.
Optional profile stage options enable reasoning for interpretation and review
without enabling it for every classification or rendering call. Output remains
bounded (up to 4096 tokens), and inference still has the original task deadline.
A separately configured 60-second read ceiling lets a reasoning response finish;
the original profile defaults are unchanged. Context reserves output before inference.
Corrections happen only before effects; unknown outcomes are never automatically
replayed. Audit events contain boundary/ordinal and binding metadata, not prompts
or private conversation text. Profiles contain model/options; broker policy does not.

The candidate must be measured on this PC. Historical M2/M3 reports cannot qualify
the new profile. M2 still requires matching model/conversation reports and fresh
attended readiness for native Windows effects. The new frozen conversation corpus
and historical M3 v2 corpus retain 100% gates. General research semantic/freshness
qualification remains a separate, broader requirement; M4 remains outside scope.

An explicitly identified output-token-limit failure may receive one concise typed
interpretation repair before any effect. It shares the original deadline/turn
budget and rechecks revision/cancellation. Transport failures, wrong response
identity, native tool calls and unknown outcomes do not enter that repair path.
Repair options belong to the profile. A fully named new pair clears previous
numerical context. Controller-recognized complete conversions cannot become
public searches, including when currency retrieval is unavailable. Ambiguous
currency symbols require clarification.

A narrow source qualifier guard rejects sporting-rank paraphrases of popularity
rankings. This is not a general factual validator. Failed summaries fall back to
exact excerpts, which can be verbose and retain confusing source phrasing.
Final candidate interpretation 16/18 and currency 29/34 failed their unchanged
100% gates. Notepad simulation 18/18 and conversation 29/29 passed. Three actual
public smoke examples passed narrow checks; biography rendering used the excerpt
fallback. The candidate remains experimental. See BUILD_LOG for exact reports.
