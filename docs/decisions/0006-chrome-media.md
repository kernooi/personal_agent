# ADR 0006: M4 installed Chrome and semantic media

Status: implemented; YouTube live-tested, Spotify/Netflix setup pending. M4 supersedes
the earlier M3.5 stop boundary. Stop after M4; no M5 or general computer control.

The existing broker owns media scopes, grants, exact prepared actions, journal,
admission, cancellation and postconditions. The model chooses only bounded runtime
references in a strict `media_choice` record. It cannot supply URLs, selectors,
JavaScript, credentials, files, approval tokens or a different service operation.
Each search, open and playback step has a separate broker transaction. Compound
search-and-play requests currently need separate turns and a selected result.

Installed, signed stable Google Chrome runs through Playwright in a supervised
Python worker with bounded typed stdin/stdout RPC. No CDP port, existing-browser
attachment or bundled Chromium. One persistent private profile is fixed under
LOCALAPPDATA/Jarvis/browser/chrome. Exclusive profile and shared desktop leases
prevent concurrent JARVIS workers; ordinary Chrome is never enumerated for tabs.
The worker exposes reviewed YouTube and Netflix operations only. Constant scripts
observe video identity/state and trusted input; scripts never contain model text.

Results have opaque references and navigation generations. The controller checks
owner ordinals/unique title matches; the worker re-reads result identities before
opening. A separate observation after execution verifies actual player identity
and state. An accepted command is not evidence. Ads, restrictions, loading and
unknown outcomes cannot become verified playback. Stale/user-changed state needs
reobservation. Crashes/timeouts require manual review, never automatic replay.

The original Spotify adapter uses the official Web API with Windows Credential Manager
storage. Search, track identity, devices and playback state are bounded. Playback
requires an explicit current unrestricted device and independently observed track,
device and state. Missing OAuth/Premium/device access blocks Spotify, not YouTube.
There is no authenticated web-player fallback or account mutation.
The user's later explicit Windows media choice is recorded in ADR 0007; it adds a
separately selected basic playback backend without silently falling back from API.

Browser authentication does not enter public web research or currency transports.
Browser routing rejects non-HTTPS/private DNS destinations and unexpected top-level
origins per service. Chromium owns its network stack: this does not attest every
background request or pin Chromium's resolved peer. See the compatibility and
profile policy documents for remaining security and platform limitations.
