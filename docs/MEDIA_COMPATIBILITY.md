# M4 media compatibility and setup

| Service | Implemented path | Verification | Live state |
| --- | --- | --- | --- |
| YouTube | Dedicated installed Chrome; bounded search, select/open, current, play/pause/resume | Fresh result IDs/titles, actual player video ID and state | PASS: attended report v1-r6, including physical stop |
| Spotify Windows | Current, play/pause/resume, next/previous on the unique native Spotify session | Session, metadata and actual playback state re-read independently | PASS: attended report v1-r2, including physical stop |
| Spotify desktop search | Store app's fixed package-targeted search, exact song/playlist result selection and Play control | Fresh accessibility content/context, explicit creator match and independent Windows playback metadata/state | PASS: attended v1-r14; frozen model corpus 25/25 |
| Spotify API | Optional official track search/select, devices, current, playback | Fresh official track/device/playback responses | BLOCKED: authorized token/account/device setup absent |
| Netflix | Dedicated Chrome; manual login, title search/select/open/current | Current title URL identity and visible title metadata | NOT RUN: manual login absent; protected playback unsupported |

YouTube candidates require explicit ordinal or a uniquely matching current title.
Search/open/play are separate steps. Ads/loading/login/age/region/challenge states
are reported as limitations; no ad skipping, plan changes or challenge bypass.
Observed service playback is not a claim that audio is audible on this PC.

## Spotify without API setup

The combined launcher selects `spotify_backend="desktop"` in the separate private
`media-all-spotify-desktop-v1.toml`; the original playback-only config is preserved.
The signed-in Store app must have a visible, unminimized main window. This bounded
adapter can search songs and playlists, offer numbered alternatives, and play a
fresh matching result. Try `Play Never Gonna Give You Up by Rick Astley on Spotify`
or `Play playlist Deep Focus by Spotify on Spotify`. `Search Spotify for jazz`
returns results without automatic playback. Ambiguous play requests retain their
play goal when you choose a result number.

Attended [v1-r14](evaluations/m4-spotify-desktop-windows-v1-r14.json) passed actual
song selection/play/pause/resume, Spotify-owned Deep Focus selection/play/pause,
and stop cancellation with zero new admissions. The prior r13 apparent pass is
rejected by [the owner audit](evaluations/m4-spotify-desktop-owner-audit-v1.json):
a copied playlist's title had incorrectly supplied the requested creator words.
Selection now matches explicit title/creator separately; the lab verifies both.
All earlier failed reports remain. Catalog IDs are retrieved accessibility metadata;
rows without track URLs use controller-owned native_ identities. Neither is a
service API attestation. Playback is independently observed through Windows, with
the selected row/card's Pause context while playing. Audible sound is not attested.

Measured support is the official Store package on this PC with English semantic
labels. Other Spotify editions/locales, private playlists missing from native
search, volume, remote devices and account/library edits are unsupported or untested.
No keyboard/mouse injection or API/web-player fallback is provided.
The original Windows playback-only path below remains available separately.

The user-selected Windows backend needs only the installed Spotify app, signed in
and exposing a playing/paused track through Windows media sessions. The adapter
does not launch Spotify or select arbitrary songs. Start a track manually first.
Use the private `media-windows-v1.toml` configuration created on this PC:

```powershell
.\.venv\Scripts\python.exe -m jarvis chat `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-concurrent-v1.toml" `
  --media-config "$env:LOCALAPPDATA\Jarvis\media-windows-v1.toml" `
  --real-media --media-attended `
  --windows-media-report .\docs\evaluations\m4-spotify-admission-windows-v1-r2.json
```

Try `What is playing on Spotify?`, `Pause Spotify`, `Resume Spotify`,
`Next track on Spotify`, `Previous track on Spotify`. After manually choosing a
different song, inspect current playback again before asking for effects.
Missing/ambiguous sessions, unsupported controls, replacement sessions and
unverified outcomes do not trigger another app, global media keys or an API
fallback. Previous may restart instead of changing tracks; that remains
unverified. Audible sound and catalog identity are not attested by Windows state.
For an uncertain delivered effect, inspect it manually and use the existing
`/review-media <task> manually-handled`; restart a stopped worker without replay.

YouTube can be enabled in a separate private configuration with these same
Spotify settings. Add its independent `--real-browser --browser-attended`,
`--browser-registration` and current passed `--media-report` flags. Notepad keeps
its independent consent and qualification flags; Spotify flags leave it simulated.
Do not run concurrent attended JARVIS sessions.

Repeat model qualification with `eval-windows-media --live --profile <profile>
--report <unused-file>`. Repeat the attended lab with
`scripts/Test-JarvisWindowsMedia.py --attended --profile <profile>
--model-report <passed-report> --report <unused-file>` after explicit readiness.

## Optional official API setup

Spotify platform documentation was checked on 2026-10-11. API playback requires Premium
and the relevant [playback scope](https://developer.spotify.com/documentation/web-api/reference/start-a-users-playback).
Development mode has account/user and endpoint restrictions; do not infer Premium
from a profile field removed in the
[February migration](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide).
The later [July changelog](https://developer.spotify.com/documentation/web-api/references/changes/july-2026)
raises the developer app limit to 25 and shares development quota across apps.
The [May account field](https://developer.spotify.com/documentation/web-api/references/changes/may-2026)
is not entitlement evidence. This adapter never requests profile/account metadata.

Spotify setup is an explicit operator handoff, not an automated account signup:

1. Use your own approved Spotify developer application and eligible account. Any
   subscription/developer account/terms setup requires your separate approval.
2. Obtain a short-lived user access token through official
   [Authorization Code with PKCE](https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow).
   Request `user-read-playback-state`, `user-read-currently-playing` and
   `user-modify-playback-state`. Record the returned granted scopes and expiry.
   A client-credentials token cannot authorize user playback.
3. Follow the official [redirect URI rules](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri):
   exact registered URI, HTTPS or explicit loopback IP for an operator-owned OAuth
   callback; `localhost` is not allowed. The public browser media tools do not gain
   loopback permission. This milestone does not provision a callback server.
4. In your private terminal run
   `.\.venv\Scripts\python.exe -m jarvis spotify-store-token --expires-in 3600`
   (use the actual remaining lifetime). Paste the access token at its hidden prompt,
   never in chat. Automatic acquisition/refresh is not implemented.
5. Enable `spotify=true` in the private media config. Open your chosen Spotify
   client/device manually. Ask `List Spotify devices`, then select its opaque
   reference using `/media-device device_<reference>`. Search, open the selected
   track, and play/pause/resume. No default device guessing or playback transfer.

HTTP 401 means authentication/expiry failure; 403 means access/entitlement denied
(no unsupported guess about the specific cause); 404 may indicate no device;
429 is rate/quota restriction. No retry or fallback to authenticated web controls.
Device availability uses the official
[device endpoint](https://developer.spotify.com/documentation/web-api/reference/get-a-users-available-devices).
Accepted playback commands must still be independently observed on the intended
track/device. Restricted devices and changed active content fail closed.

Netflix setup: enable `netflix=true` privately, enter `Log in to Netflix`, and
complete login manually in JARVIS Chrome. Ask for the current Netflix page to
reobserve after manual interaction, then search for a title and open its current
result. Account profile selection, plan/region restrictions and layout changes can
block this path. Protected playback, fullscreen, DRM and account mutation are
unsupported. No Netflix password, profile name or account identifier is logged.
