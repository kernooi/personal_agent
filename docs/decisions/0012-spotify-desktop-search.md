# Spotify-specific installed-app search and playback

The owner requested named song and playlist playback and explicitly selected the
installed Spotify application without developer API setup. This extends M4 with a
reviewed Spotify-specific accessibility controller. It does not add generic UI
primitives or a Spotify web-player fallback.

The initial native adapter identifies the official Windows Store Spotify package
through AppsFolder, validates its signed installed launcher and runtime association,
then binds the unique window's user/session/process/creation/hash identity. A title
or model path cannot identify the app. Native EXE editions/localized layouts remain
outside this measured adapter until separately implemented/tested.

Search uses only a fixed, encoded spotify:search URI addressed through WinRT to the
exact verified Spotify package family (no default protocol-handler fallback). The
labelled search ValuePattern is read for verification. The labelled Search button
inside the unique search form may commit that query. Songs/Playlists filters are
optional and can receive effects only if their retrieved route belongs to that exact
query; stale filter metadata causes no filter click. Requested result types may be
read from the current All view. The exact Play control in a current result's row/card
may receive effects.
There is no keyboard/mouse injection, coordinate click, generic selector, arbitrary
URL navigation beyond that fixed search URI, script, credential extraction, login
automation, playlist edit,
library mutation, purchase or machine-level installation. The client handles its ordinary network
traffic and account restrictions. Public research receives no Spotify session data.

The owner query is bounded and disclosed only to the Spotify client. Fresh main-view
result links yield validated Spotify playlist/artist IDs from exact HTTPS
open.spotify.com or xpui.app.spotify.com origins. The Store Songs view exposes
track rows without catalog URLs: controller-derived native_ identities bind the
row runtime ID, exact title/artist and validated artist IDs. These are explicitly
not Spotify track catalog IDs. Controller-issued opaque references select those
fresh rows or playlist cards. Labels are untrusted. Search, selection and playback use separate broker
tasks and exact scope/revision/approval/cancellation checks. Search is a visible UI
effect despite using the existing media read-class permission; it is separately
opted into through the desktop backend and attended native-media consent.

Selection pins a verified result without playing it. Explicit "by" artist/owner
requests must match the exact title and actual creator metadata separately. Playlist
owners come from the same unique card's validated public user link or exact Play
label, never creator words in a playlist title. Generic active-row Pause labels are
accepted only inside the selected fresh row, whose title/artist metadata remains
bound through the read-only More-options label or unique track link. No menu is
invoked. Exact named matches may proceed;
ambiguity offers numbered choices. Playlist context requires the matching card's
Pause control and independent unique Spotify Windows playback state; songs require
the selected row's exact Pause control and observed title/artist to match. GSMTC does not expose Spotify catalog IDs: these
are combined accessibility/native-state checks, not a service API attestation or
audible-sound proof. Pause/resume revalidate the native session and actual track;
manual target changes, stale references and unknown effects stop without replay.

The desktop backend is explicit and defaults disabled in examples. The Windows
playback-only and optional API backends remain separate. A new frozen desktop corpus
retains the 100%/zero-unauthorized gate. Real mode requires its matching qualification;
the playback-only corpus cannot authorize desktop search. Native compatibility is
recorded separately, and a stopped worker is restarted only at a fresh chat boundary.
