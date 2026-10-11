# ADR 0007: Spotify Windows media sessions

The user explicitly selected Windows media control instead of developer-app/OAuth
setup. This changes the Spotify adapter choice within M4, not general Windows
control. The existing official API adapter remains available, with its original
credential and entitlement requirements. There is no automatic backend fallback.

`spotify_backend="windows"` selects GSMTC through locked PyWinRT 3.2.1 bindings.
Real selection separately requires `--real-media --media-attended` and matching
passed `--windows-media-report`; neither Chrome nor real Notepad is required.
Simulation remains the default. Prepared arguments bind the backend. The model
still proposes a narrow media choice; the existing broker owns scope, grants,
journal, admission, cancellation and independent verification.

Only one exact Spotify source session may be selected. Other players' properties
are not inspected. Missing/ambiguous sessions fail closed. No global media keys,
focus changes, app launching, API calls, remote-device transfer, catalog search or
credential reads occur. The app must be opened and signed in manually. Current,
play/pause/resume and next/previous are supported when advertised by the session.

A supervised native worker uses existing bounded JSON pipes/deadlines and the
shared desktop lease across effect and verification. It rechecks session,
metadata, state and supported controls immediately before delivery. A successful
Try* result is only acknowledgement; actual state is polled without replay and
read independently again by the broker. Unknown delivery stays manual review.
The global stop remains active while Spotify has focus.

GSMTC exposes app-reported metadata, not a Spotify catalog track identifier or
cryptographic identity/entitlement proof. Exact source identifiers are OS-reported
and cannot protect against malicious software running as the same user. Track
metadata fingerprints use a per-worker random salt; raw track titles/artists are
not written to journals or reports. Identical metadata cannot distinguish tracks.
Previous may restart a track rather than change it; in that case the requested
track change is unverified. Reported playback state does not attest audible audio.

Windows attended evidence: `m4-windows-spotify-v1-r2.json` passed all five operations
and physical stop with zero new admissions. Initial harness failure is preserved.
See BUILD_LOG and MEDIA_COMPATIBILITY for exact commands and qualification.
