# Natural named YouTube requests through bounded broker phases

The owner's named/compound YouTube requests were rejected by the separate-step M4
interface. The conversation entrypoint now expands them into existing search/open/play
tasks. No selectors, browser primitives, script execution, account changes or network
permissions are added. Spotify/Netflix boundaries remain unchanged.

Each phase needs its own scoped model proposal, fresh runtime identity/generation,
single-use approval, durable journal, cancellation and independent verification.
Queries derive only from owner text and pass existing private/URL restrictions.
Titles/creators are untrusted retrieved data. Only a unique matching result proceeds
automatically; broad channel searches require a numbered choice. Pending playback
binds owner/browser session, result generation and the original request deadline.

Changed results, expiry and unrelated requests clear continuation. Ads stop automatic
play attempts rather than being bypassed. Failed or unknown phases halt without
retry/rollback. Cancellation after delivery before observation remains UNKNOWN.
A bounded session receipt cache rejects reused keys with changed content; pending
workflows are never resumed from old results after restart.

M4 corpus v1/raw-broker tests remain. V2 exercises the actual conversation entrypoint
with explicit one/three-effect counts, 100% correctness and zero unauthorized actions.
Tests cover phase order, stale choices, reused IDs, cancellation, ads, expiry and
private/unsupported queries. Qualification checks exact frozen dispatch counts.

Application informational context now includes bounded actual catalog labels as
untrusted data. Application availability is separate from Notepad registration.
This corrects a regression where the model falsely called registered Nova Desktop
unregistered, without changing action permissions or target resolution.
