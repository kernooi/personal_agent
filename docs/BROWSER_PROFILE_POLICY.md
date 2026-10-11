# Private browser and credentials policy

The dedicated Chrome profile lives outside the repository at
`%LOCALAPPDATA%\Jarvis\browser\chrome`. It can contain cookies, authenticated
service sessions and browser-managed local state. Treat the whole directory as
private. Never commit, copy to another machine, inspect everyday Chrome profiles,
export cookies/storage-state or include this directory in research evidence.
The application rejects profile overrides, repository paths and reparse points.

Login is manual in the dedicated window. JARVIS never requests passwords in chat,
types credentials, copies another profile's authentication or bypasses challenges.
Page observations are limited to public media titles/IDs, playback state and coarse
login/restriction status. No raw DOM, screenshots, cookies, headers, account names
or browsing history enter model context or durable broker records. Public labels
are untrusted; they cannot authorize effects. Search disclosures use the current
owner media query only, with no conversation history or private browser state.

Spotify access tokens use Windows Credential Manager target `Jarvis/M4/Spotify`.
The explicit `spotify-store-token` command reads a hidden terminal input, requires
a maximum one-hour expiry and the reviewed scopes. Never paste tokens here or put
them in TOML, command arguments, logs or Git. Scope/expiry supplied at token setup
are operator statements, not programmatic proof of account entitlement. Each API
operation checks expiry/scopes and handles service denial; no token refresh or
OAuth account creation happens automatically.

The global Ctrl+Alt+Shift+F10 hotkey remains registered while Chrome has focus.
Stopping prevents new admissions. If delivery has already happened, the outcome
may be unknown; inspect manually before `/review-media <task> manually-handled`.
That acknowledgement never replays a request or refreshes old references. An
explicit current-state request reobserves after user input/navigation. Do not run
multiple attended JARVIS sessions or modify the page during an automated step.

Worker termination targets only the owned Python worker. No force-kill of Chrome
or Notepad. Normal shutdown closes only the dedicated launched browser context.
An orphaned Chrome/profile lock after a crash requires manual handling.
