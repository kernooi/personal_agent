# JARVIS local desktop assistant

## Local hands-free voice (M6: not fully qualified)

Start the existing GUI with:

```powershell
.\.venv\Scripts\python.exe scripts\Chat-JarvisGUI.py
```

When chat is ready, say your configured wake call (default **Jarvis**). The orb
appears and replies **"Yes sir."**, then listens for one command. Speak when the
acknowledgement finishes; a short pause ends your command automatically. Voice
uses the same chat pipeline and broker as typing.

**Settings**, beside **Details**, controls the microphone, output, wake call,
command listening window (3-20 seconds), end-of-command pause and speech engine.
Spoken replies are always on. Stop/Esc interrupts and pauses wake listening;
Settings > Save resumes it. Ctrl+Alt+Shift+F10 is the global emergency stop.
The visible microphone status distinguishes quiet input, sound and transcription.

This PC selects the approved local **small.en** command recognizer on CPU and
**Kokoro / Michael (American male)** speech. Base.en is retained; Windows offline
voices remain explicitly selectable. Windows SAPI recognizes only the wake call;
Whisper transcribes commands. The microphone pauses during speech/processing,
audio stays transient, and startup never downloads models or uses cloud speech.
Only the fixed "Yes sir." acknowledgement has a setup-created private audio cache.
Voice and screen assistance share the existing orb, with screen privacy priority.

Actual handoff tests measured about **66-67 ms** from acknowledgement completion
to command input, but recognition accuracy remains unresolved: the general
attended corpus matched **2/7** exactly and the spelling corpus **1/4**. Both failed
the unchanged gate. Automatic app-name hints caused literal "this cord" to become
"Discord"; they are now **off by default** and disabled privately. Settings keeps
these as an experimental opt-in. Optional **Names and spellings** can also bias
recognition; no replacement table rewrites transcripts. Restart the GUI after
code/settings changes.

Text chat remains available when voice setup fails. No voice request bypasses
registrations, qualifications, scope, transcript review or broker checks. Native
microphone/speaker validation requires attended readiness. Full M6 acceptance,
noise/false-wake coverage and integrated screen/voice validation remain incomplete.
See [voice setup and controls](docs/VOICE.md), [actual M6 results](docs/M6_TEST_REPORT.md),
[wake architecture](docs/decisions/0022-windows-wake-grammar.md) and
[spelling-hint limits](docs/decisions/0024-local-speech-vocabulary.md).

## Animated screen companion

Screen questions now display a small animated charcoal orb with two white eyes.
It reflects actual capture, local analysis and completion, then disappears without
taking focus or blocking clicks. The readable screen-access/stop indicator remains.
No capture occurs at startup. Restart the GUI to load the feature; existing screen
settings are preserved and companion defaults apply automatically.

```powershell
.\.venv\Scripts\python.exe -m jarvis companion-preview --cycle
```

This standalone preview uses the real renderer without screen/model access.
See [configuration, implementation and actual Windows evidence](docs/DESKTOP_COMPANION.md).

## M5 screen assistance — limited native validation

Screen questions now use the vision model to read the image and the primary chat
model to write a natural explanation. The private handoff shares bounded relevant
context, preserves uncertainty and keeps screen-derived information out of ordinary
chat history and public tools. Wordle retains its deterministic solver. Restart chat
to load the new defaults; see [settings and real-model validation](docs/SCREEN_CHAT_HANDOFF.md).

M5 adds separately configured on-demand Windows screen understanding, local image
analysis, bounded window watching and deterministic Wordle advice. It uses the
existing task broker and chat, including the GUI; it adds no click/type, webcam,
voice or memory capability. **M5 is NOT FULLY VERIFIED.** See the
[M5 test report](docs/M5_TEST_REPORT.md),
[capture compatibility](docs/SCREEN_CAPTURE_COMPATIBILITY.md),
[vision compatibility](docs/VISION_COMPATIBILITY.md),
[screen privacy](docs/SCREEN_PRIVACY.md) and [Wordle solver](docs/WORDLE.md).

The inspected PC is Windows 11 build 26200 with RTX 4070/12 GB VRAM and 32 GB RAM.
Initially only text-only `qwen3:8b` was installed. The owner subsequently approved
and installed `qwen2.5vl:3b` for images, keeping qwen3 as the main chat model.
Neither this command nor GUI startup downloads models.
On this PC the private `screen.toml` is already enabled for on-demand questions
with `qwen2.5vl:3b`; watching remains off. On another setup, create a private
configuration from `config/examples/screen.toml`, preserving an
existing file. Set `enabled=true` and `vision_model` to an installed local
image-capable model only when choosing to enable screen assistance. Watching
separately needs `watch_enabled=true`. Do not copy another PC's local-mode evidence.

```powershell
# After configuring private screen.toml and installing an approved vision model:
.\.venv\Scripts\python.exe -m jarvis chat `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-concurrent-v1.toml" `
  --screen-config "$env:LOCALAPPDATA\Jarvis\screen.toml"
```

This command leaves app/media actions simulated; screen reads are independently
opted in. The combined launcher/GUI also includes the private `screen.toml` when
present, retaining all existing real app/media qualifications. No capture happens
on startup. Screen questions now capture your whole main monitor automatically;
you do not need to choose a window or approve each capture:

```text
Scan my screen and explain what I am looking at.
What am I looking at?
What plant is this?
What does this error mean?
Help me solve this Wordle.
I entered another guess. Check again.
/screen-status
/screen-revoke
```

The owner's standing permission covers on-demand main-screen reads. Optional
`/screen-windows` and `/screen-allow <reference>` restrict questions to one window;
asking to read the whole screen uses the main monitor again. Explicit all-monitor
requests use desktop scope and can fail on monitor gaps or image limits. For the
original foreground-window default, set `default_capture_scope="foreground_window"`.
Watching still requires its separate enabled setting and an explicitly selected
window; this change does not start background watching. Capture is limited to
visible pixels and still checks exclusions, protection and changed targets.
The visible **JARVIS SCREEN ACCESS** window must remain open during
capture/analysis/watching. Move it outside a selected window if it overlaps.
Closing the indicator, `/screen-stop`, `/stop` or Ctrl+Alt+Shift+F10 stops further
capture/submissions. Pixels remain in memory; normal logs/history/web searches
receive neither screenshots nor their private descriptions. No screenshot uploads.
`/screen-status` shows the loaded vision context and last safe failure category.
The private vision context is 8192 for full-display input. NYT Wordle detection
supports small browser row/column spacing differences; invalid/truncated model
output or an unreadable board never produces an unchecked guess.

If Ollama's GPU vision runner returns an explicitly incomplete answer, JARVIS can
retry once on CPU using a bounded thumbnail of the same capture. It retains the
same model, local-only transport, cancellation and deadline, and warns about reduced
detail. CPU recovery can take roughly 45–60 seconds or time out; normal GPU reads
keep full resolution. See [vision recovery settings and limits](docs/VISION_COMPATIBILITY.md).

After confirming attended readiness, this implemented lab displays only its own
controlled error, plant illustration and Wordle fixture. It uses actual capture
and local vision through the normal `Conversation` interface. The illustration
does not establish photograph/species recognition. Reports refuse overwriting:

```powershell
.\.venv\Scripts\python.exe scripts\Test-JarvisScreen.py --windows --attended `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-concurrent-v1.toml" `
  --screen-config "$env:LOCALAPPDATA\Jarvis\screen.toml" `
  --report .\docs\evaluations\m5-screen-windows-new.json
```

Ordinary pytest remains deterministic and never captures a real desktop or calls
Ollama. Real local error reading, public flower-photo description, Wordle extraction
and physical stop passed on the owned fixture. This does not establish species
recognition or universal capture compatibility. Native watching, full-display,
multi-monitor/DPI and session-lock evidence are tracked separately in the test
report. Do not infer them from mocked tests.

## Desktop chat

Spotify desktop search needs its installed main window restored and visible.
A new song/playlist search can bind to Spotify after it has been closed and reopened;
old choices are discarded. Switching between Spotify and YouTube retains each
service's selected content. Specific controller errors explain when to restore a
window, inspect the current browser page, search again or restart the chat.
Interacting with the dedicated browser can still require a current-page inspection
before control resumes; unknown delivered effects are never automatically retried.
After manually skipping an ad, ask `What video is currently open on YouTube?`
before pause/resume. This refreshes the manual handoff through the broker.
The dedicated browser keeps processing its network/page events between chat turns,
including while waiting for your next message or manual login.

Currency is an optional capability. JARVIS requests a rate or conversion only for
a clear monetary request, such as `Convert 100 SGD to USD` or `USD to MYR rate`.
Generic “how much” questions, unrelated numeric questions, explanations and
corrections do not activate it. Changing topics releases a pending currency pair
and calculation operands, including when switching to app or media control.
`What about 500?` can continue the active conversion; after a topic change, it asks
what you want to do with that number instead of assuming currency.

Explicit currency queries, generic provider-discovered currencies, local supplied
rates and source inspection remain supported. Currency symbols or incomplete money
requests may still need clarification. Ordinary arithmetic and unit conversions
remain normal chat. Both GUI and terminal use this routing.

Open the minimal desktop chat window:

```powershell
.\.venv\Scripts\pythonw.exe scripts\Chat-JarvisGUI.py
```

The slate/navy header includes the JARVIS core logo, name and session controls.
On Windows 11, the matching native title bar replaces the white caption while
retaining Windows window controls, dragging, resizing and snapping. This uses
[per-window DWM colors](https://learn.microsoft.com/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute),
without changing your Windows theme. Older systems retain supported native styling.

The GUI connects automatically. It starts the registered standalone Ollama server
when needed, preloads the already installed model from your active profile, and
starts your local SearXNG container. If Docker Desktop is stopped, it starts the
installed Docker Desktop first. Existing running services are reused. The old
ephemeral SearXNG container may have been removed when Docker stopped; the GUI can
recreate it using the cached pinned image, existing private mounts and loopback-only
port binding. Nothing is installed or downloaded, and no Windows startup entry or
Docker restart policy is enabled. Services remain running after the GUI closes.

The GUI uses the same private setup and attended real controls as `Chat-JarvisAll.py`.
At the owner's explicit request, opening it automatically enables real app, Notepad,
YouTube and Spotify controls. No control or animation toggle is needed. Stay at the
PC during this attended session; exit other attended JARVIS chats first. Wait for
**Ready** in the activity bar before requesting an action. No app or playback action happens
merely from opening the GUI. Core/profile and ordinary CLI simulation defaults remain
unchanged; missing registration or qualification fails startup without fallback.
Existing registration, qualification and broker checks still apply. **End session**
is intentional; after ending or a startup failure, **Start chat** retries connecting.

The dark slate conversation uses rounded message bubbles: muted blue user bubbles
on the right and softer slate JARVIS replies on the left. The composer, menus and
full-message reader share the dark palette. The logo and circular send button use
antialiased transparent artwork for smooth edges, with no extra dependency.
Message text can be selected; right-click **Copy message** copies a whole bubble.
Long replies have **Read full message** so large output stays readable without
making the main view sluggish. **Latest** returns to new replies after scrolling up.

The rounded message box grows for multiline input, with a compact arrow send
button. Focusing the field hides its placeholder and shows a blue outline and
blinking caret; leaving an empty field restores the placeholder. Placeholder text
is never sent to the model. Enter sends; Shift+Enter
adds a line. Always-on animated thinking dots and elapsed time show
that JARVIS is working; they are activity indicators, not streamed model reasoning.
The chat uses a slim rounded scrollbar that brightens on hover and disappears
when everything fits. Drag, wheel, track paging and keyboard navigation work;
wheel movement is eased in pixels and works over blank spaces, bubbles and the
scrollbar, including small wheel deltas. New replies preserve your position when
you are reading earlier messages. Direct scrollbar navigation cancels wheel motion.
**Stop** or Esc cancels the current request through the existing cancellation path.
Ctrl+Alt+Shift+F10 remains the global stop in attended mode; end that session before
starting another after a global stop. **End session** and closing the window send
stop/quit cooperatively, without force-killing apps or promising rollback.

**Details** shows startup and connection diagnostics; normal replies appear in the
chat. Existing slash commands work in the composer. Chat display and diagnostics
remain in memory; the existing minimal action journal is unchanged. No GUI network
server, additional dependency, cloud fallback, auto-start entry or installation is
added. Startup progress appears in the activity bar; a search startup failure leaves
local chat available with an explicit notice. Missing model/runtime/image artifacts
are reported rather than downloaded. M5 screen assistance is independently opted
in through the private screen configuration above. M6 adds independently bounded
GUI voice controls; see the voice section and its pending native acceptance status.

Approved service startup metadata is private at `%LOCALAPPDATA%\Jarvis\gui-startup.toml`:
registered Ollama executable/hash/version, local Docker context, owned container name
and pinned SearXNG image. Model names/options remain in the text profile. Ollama
starts with process-local cloud-disabled/loopback/model-directory/context settings;
fresh server startup must log cloud disabled before loading. Preloading uses an empty
request, as documented in [Ollama's FAQ](https://docs.ollama.com/faq#how-can-i-preload-a-model-into-ollama-to-get-faster-response-times).

For visible development errors, use `python.exe` instead of `pythonw.exe`.

## Installed applications on this Windows PC

Application control now discovers targets from Windows AppsFolder metadata rather
than a fixed app list. Windows is the first native platform; the platform interface
can accept future native controllers. It cannot control other devices yet.
Use `python -m jarvis inspect-apps` to list this PC's supported launch identities
without effects. Discovery found 145 supported entries and 51 unavailable entries;
that is catalog coverage, not a claim that every app's windows have been tested.

The private `$env:LOCALAPPDATA\Jarvis\applications.toml` enables the catalog.
The checked-in `config/examples/applications.toml` defaults to disabled.
Restart chat to load changes. Application effects default to simulation and require
separate real-mode flags and current local-model qualification:

```powershell
.\.venv\Scripts\python.exe -m jarvis chat `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-concurrent-v1.toml" `
  --applications-config "$env:LOCALAPPDATA\Jarvis\applications.toml" `
  --real-apps --apps-attended `
  --applications-report .\docs\evaluations\applications-spotify-admission-v4-r1.json `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --web-config "$env:LOCALAPPDATA\Jarvis\web.toml"
```

Try `Open Calculator`, `Open Discord`, `Open Spotify`, `Minimize it`,
`Bring it to the front`, or `Close Spotify`. A selected or sole verified window
needs no reference or extra close confirmation. If several windows match, reply
with the number JARVIS offers. `/apps` and `/app-windows` remain optional diagnostics.
Notepad must still be independently empty, unmodified and single-tab; text,
unsaved changes, dialogs and unknown state pause close without discarding work.
Normal close uses the application's ordinary close operation. Some apps hide to
the tray; that closes their visible window without terminating the background
process or necessarily stopping playback.
Unknown outcomes require manual inspection before further effects. Ctrl+Alt+Shift+F10
stops new effects globally. Run one attended session at a time.

See [natural close and launcher identity](docs/decisions/0009-natural-app-close.md).

The combined launcher uses the private `notepad-m2-concurrent-v1.toml` profile with
`window_input_policy = "targeted"`. You can keep using the keyboard/mouse and switch
to other apps while a window command is planned or executed. Commands remain bound
to their named/selected target. Explicit focus brings that window forward when it
executes; actual foreground success still has to be observed. Unsaved Notepad work,
stale identities, dialogs, locked desktops and stop still prevent effects. Older
profiles default to exclusive input handling. This setting covers application and
Notepad lifecycle only, without generic typing/clicking or browser target changes.
See [concurrent window control](docs/decisions/0010-concurrent-window-control.md).

For the existing `my text editor` route, additionally use `--real --attended`,
the Notepad registration, `m2-spotify-admission-model-v1-r1.json` as `--model-report`
and `m2-spotify-admission-conversation-v1-r1.json` as `--conversation-report`.
For real Chrome/Spotify, retain their separate flags/configuration and use
`m4-spotify-admission-browser-v2-r2.json` and
`m4-spotify-admission-windows-v1-r2.json` respectively. Each execution mode
is displayed separately; enabling applications does not authorize browser or media
effects. See [the architecture decision](docs/decisions/0008-device-applications.md).

Unsupported entries, elevated/tray-only apps, unverified launch delegates and portable apps
absent from AppsFolder remain outside the verified path. No executable-path,
argument, shell or generic typing/clicking fallback is provided.

The attended [Windows application lab](docs/evaluations/applications-windows-v1-r4.json)
passed Calculator open/minimize/repeat/restore/close, Character Map
open/minimize/repeat/restore, independent Windows state checks and the physical
stop hotkey with zero new admissions. Three pre-existing windows were preserved.
Earlier failures remain recorded. EXE close is simulation-tested, not exercised
in this native lab. Other app compatibility needs individual validation.

The subsequent [launcher lab](docs/evaluations/application-launchers-windows-v1-r3.json)
passed Discord, Spotify and Notepad open/minimize/focus/normal-close with independent
Windows checks and no extra close confirmation. The linked run continued only its
exact Spotify test window after a zero-delivery planning pause, preserved original
windows, and verified cancellation with zero new admissions. Discord close hides
to the tray; background termination is not claimed. Earlier failures are retained.

Complete combined session with the existing private setup on this PC:

```powershell
.\.venv\Scripts\python.exe scripts\Chat-JarvisAll.py
```

This attended launcher uses the private configs and current reports below and
changes no settings. Add `--print-command` to inspect its arguments without
starting chat. Exit old chats first. The equivalent full command is:

```powershell
.\.venv\Scripts\python.exe -m jarvis chat `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-concurrent-v1.toml" `
  --real --attended `
  --registration "$env:LOCALAPPDATA\Jarvis\notepad-registration.json" `
  --model-report .\docs\evaluations\m2-spotify-admission-model-v1-r1.json `
  --conversation-report .\docs\evaluations\m2-spotify-admission-conversation-v1-r1.json `
  --applications-config "$env:LOCALAPPDATA\Jarvis\applications.toml" `
  --real-apps --apps-attended `
  --applications-report .\docs\evaluations\applications-spotify-admission-v4-r1.json `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --web-config "$env:LOCALAPPDATA\Jarvis\web.toml" `
  --media-config "$env:LOCALAPPDATA\Jarvis\media-all-spotify-desktop-v1.toml" `
  --real-browser --browser-attended `
  --browser-registration "$env:LOCALAPPDATA\Jarvis\chrome-registration.json" `
  --media-report .\docs\evaluations\m4-spotify-admission-browser-v2-r2.json `
  --real-media --media-attended `
  --windows-media-report .\docs\evaluations\m4-spotify-admission-desktop-v1-r2.json
```

## Selected Notepad minimize

With the desktop v10 profile, try `Minimize Notepad`, `Minimize my text editor`
or `Minimize it` after opening or selecting the registered window. `Bring it to
the front` restores a minimized window and focuses it. Minimize leaves unsaved
work intact. Close no longer requires `/confirm-empty`, but retains independent
empty/unmodified/single-tab checks. This older Notepad route is separate from the opt-in discovered-application
controller above. Restart chat to load the new code.
Older qualification reports are preserved but cannot authorize this changed code.

Notepad-only real chat on this PC:

```powershell
.\.venv\Scripts\python.exe -m jarvis chat `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-concurrent-v1.toml" `
  --real --attended `
  --registration "$env:LOCALAPPDATA\Jarvis\notepad-registration.json" `
  --model-report .\docs\evaluations\m2-spotify-admission-model-v1-r1.json `
  --conversation-report .\docs\evaluations\m2-spotify-admission-conversation-v1-r1.json
```

For the combined session, retain the public currency/web/media configuration flags
and use `m4-spotify-admission-browser-v2-r2.json` as `--media-report` and
`m4-spotify-admission-desktop-v1-r2.json` as `--windows-media-report` with the desktop config.
Do not run two attended chat sessions simultaneously. The new attended lab is
`scripts/Test-JarvisNotepadMinimize.py`; the attended local-model Windows run
passed open, minimize, repeated minimize, restore/focus and safe close. Independent
Windows state checks confirmed both minimize operations and restoration. See
`docs/evaluations/m2-minimize-windows-v1-r1.json`. Fake/model qualification remains
separate from this bounded Windows evidence.


## M4: dedicated Google Chrome and media

Spotify play requests now select the first fresh result without showing a
numbered list. For example, ask `Play Avid on Spotify` or
`Play playlist Fav Jpop on Spotify`. Explicit artist/playlist-owner constraints
still apply. `Search Spotify for Avid` lists results without playing them.
See [selection behavior and qualification](docs/decisions/0023-spotify-first-result.md).
The shared GUI/terminal launcher selects the fresh `spotify-first-result-*`
qualification reports; older milestone reports remain historical evidence.

M4 adds opt-in installed Chrome for YouTube and Netflix, and an official Spotify
API adapter. See [M4 results](docs/M4_TEST_REPORT.md),
[browser compatibility](docs/BROWSER_COMPATIBILITY.md),
[media setup](docs/MEDIA_COMPATIBILITY.md) and
[private profile policy](docs/BROWSER_PROFILE_POLICY.md). M5 screen assistance is
separately configured as described above.
Browser, Notepad, currency and public research permissions remain independent.

The combined launcher now includes installed Spotify song and playlist search
without developer API setup. Leave the signed-in Spotify main window visible
(or ask the separate application controller to open/focus Spotify first). Try:

```text
Play Never Gonna Give You Up by Rick Astley on Spotify
Play playlist Deep Focus by Spotify on Spotify
Play playlist Fav Jpop
Play playlist Fav Jpop Spotify
Could you put the playlist Fav Jpop on for me using Spotify?
Search Spotify for jazz
Open the second result
Pause Spotify
Resume Spotify
What is playing on Spotify?
```

Ambiguous play requests offer numbered results; replying with a number selects
and plays within that request. A search-only request does not automatically play.
One exact title takes priority over similar names; duplicate exact titles still
need a choice. These examples are not required sentence templates. The shared GUI
and terminal backend reads explicit service/title fields and uses bounded local
model interpretation for unfamiliar action wording, such as `Pull up Calculator
for me` or `Put Never Gonna Give You Up on YouTube for me`. An explicitly named
playlist defaults to the configured Spotify desktop search backend; generic media
without a service or selected controller state needs clarification. General browser
page interaction remains outside the supported YouTube/Netflix media controller.

The combined launcher includes the matching request-language qualification along
with existing app/Notepad/media reports. To evaluate new wording with actual local
inference and synthetic Windows/media state:

```powershell
.\.venv\Scripts\python.exe -m jarvis eval-language --live `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-concurrent-v1.toml" `
  --report .\docs\evaluations\request-language-new-run.json
```

The frozen wording gate requires 100% correctness and zero unauthorized dispatches.
Existing or failed reports are preserved; choose a new output path. Real semantic
fallback requires a matching passed `--language-report`; this evidence alone does
not qualify native UI compatibility. See [decision 0016](docs/decisions/0016-natural-action-interpretation.md).

An explicit artist or playlist owner must match actual retrieved creator metadata,
not words in a different result's title. This tested adapter supports the official
Windows Store Spotify package and English accessibility labels. Localized/EXE
editions, private playlists absent from search, account/library edits, remote
devices and volume control are not validated. See the
[passed attended report](docs/evaluations/m4-spotify-desktop-windows-v1-r14.json).
The earlier r13 pass is rejected by its retained
[owner audit](docs/evaluations/m4-spotify-desktop-owner-audit-v1.json).

For playback-only operation, Spotify can still use Windows media controls without a developer account or API
token. Open the installed Spotify app and start a track manually, then run:

```powershell
.\.venv\Scripts\python.exe -m jarvis chat `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-concurrent-v1.toml" `
  --media-config "$env:LOCALAPPDATA\Jarvis\media-windows-v1.toml" `
  --real-media --media-attended `
  --windows-media-report .\docs\evaluations\m4-spotify-admission-windows-v1-r2.json
```

Try `What is playing on Spotify?`, `Pause Spotify`, `Resume Spotify`,
`Next track on Spotify`, `Previous track on Spotify`. Song search, launching the
app, remote-device selection and volume are outside this backend. Ctrl+Alt+Shift+F10
stops new effects while Spotify has focus. Do not run another attended JARVIS chat
at the same time. Native playback and physical stop passed in
`docs/evaluations/m4-windows-spotify-v1-r2.json`; see
[Spotify setup and limitations](docs/MEDIA_COMPATIBILITY.md). Notepad and browser
actions remain simulated in this Spotify-only command. No API fallback occurs.

The generated lock includes the `browser` extra. Do **not** run `playwright install`:
production uses your installed stable Chrome. Inspect and register explicitly:

```powershell
.\.venv\Scripts\python.exe -m jarvis inspect-chrome
.\.venv\Scripts\python.exe -m jarvis register-chrome `
  --output "$env:LOCALAPPDATA\Jarvis\chrome-registration.json"
```

Registration creates an empty private profile and never overwrites existing data.
Copy `config/examples/media.toml` to a new private
`%LOCALAPPDATA%\Jarvis\media-m4-v1.toml`, set `enabled=true`, and enable only intended
services. No auth values belong in that file. Evaluate the actual local model
against frozen fake media before real effects:

```powershell
.\.venv\Scripts\python.exe -m jarvis eval-media --live `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-concurrent-v1.toml" `
  --report .\docs\evaluations\m4-user-model-r1.json
```

Use a new filename for every run. Reports must match the model, runtime, profile,
frozen corpus and source contract, with 100% correctness and zero unauthorized
dispatches. Fake qualification does not establish live Chrome compatibility.
After explicit attended readiness, run the real YouTube lab:

```powershell
.\.venv\Scripts\python.exe -m jarvis test-media --windows --attended --interactive `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-concurrent-v1.toml" `
  --browser-registration "$env:LOCALAPPDATA\Jarvis\chrome-registration.json" `
  --media-report .\docs\evaluations\m4-spotify-admission-browser-v2-r2.json `
  --report .\docs\evaluations\m4-user-youtube-r1.json
```

The lab closes only its own dedicated context and pauses for a physical hotkey
check. Ads, restrictions and uncertain outcomes stop rather than replaying.
Interactive browser chat uses independent real-browser flags:

```powershell
.\.venv\Scripts\python.exe -m jarvis chat `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-concurrent-v1.toml" `
  --media-config "$env:LOCALAPPDATA\Jarvis\media-m4-v1.toml" `
  --real-browser --browser-attended `
  --browser-registration "$env:LOCALAPPDATA\Jarvis\chrome-registration.json" `
  --media-report .\docs\evaluations\m4-spotify-admission-browser-v2-r2.json
```

Example separate turns: `Search YouTube for Rick Astley Never Gonna Give You Up`,
`Open the first result`, `Play it`, `Pause the video`, `Resume it`,
`What video is currently open on YouTube?`. Named YouTube requests can search/open/play through separate broker tasks.
Try `Play Never Gonna Give You Up on YouTube` or `Search YouTube and play Outdoor Boys`.
A uniquely matching retrieved video proceeds; broad/ambiguous searches return numbered
choices. Reply `1` or `Open the first result` to open and play your choice. Ads are
not bypassed, and stale choices, stop, failed verification and expired requests halt
the workflow. Search, selection and playback remain separately journaled and approved. `/media-status` is observational;
`/media-device <reference>` selects an observed Spotify device. Inspect uncertain
effects manually before `/review-media <task> manually-handled`; no replay.
Pending media reviews survive restarting chat. Startup and subsequent media requests
now show the exact review command; a historical uncertain search can block a new
YouTube request even when no test window is currently open. Inspect and handle the
dedicated window manually first, then acknowledge the displayed task. The original
UNKNOWN record remains; acknowledging it sends no browser action. Restart chat if
the old worker stopped. Public research and ordinary Chrome are separate.

Add existing `--public-data-config` and `--web-config` flags for currency/research.
Real Notepad additionally requires its existing `--real --attended`, registration
and matching M2 model/conversation reports. Real-browser flags alone keep Notepad
simulated. Ctrl+Alt+Shift+F10 stops new effects while Chrome has focus; `/stop`
cancels while the chat terminal is focused. Never run two attended sessions.
The successful attended YouTube evidence is
`docs/evaluations/m4-windows-youtube-v1-r6.json`. Spotify Windows playback is now
live-tested; the optional Spotify API and Netflix setup remain pending.
Overall M4 remains **NOT FULLY VERIFIED**.

The latency optimization has been restored as an opt-in `assistant-v2` candidate.
Use the existing private fast profile on this PC; it keeps Windows effects simulated:

```powershell
.\.venv\Scripts\python.exe -m jarvis chat `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\assistant-fast-v1.toml" `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --web-config "$env:LOCALAPPDATA\Jarvis\web.toml"
```

Restart chat to load the restored code. Keep the manually started local Ollama and
SearXNG servers running. Simple ordinary conversation uses one model turn; common
conversions need three turns instead of five. Uncertain numeric requests retain a separate intent
classifier before planning or answering. Complex monetary interpretation retains
reasoning, and all conversions retain semantic review and
broker verification. Verified currency answers no longer receive a redundant
model rewrite. Stage output limits and ten-minute model residency are profile
settings. `config/examples/assistant-fast.toml` is an unverified-cloud template
for other PCs; do not copy this PC's setup evidence or qualification.

This remains experimental: final interpretation scored 14/18 (earlier 16/18),
and currency scored 31/34. Both failed their unchanged 100% gates. Notepad
simulation/conversation passed 18/18 and 29/29; public smoke passed three narrow
checks. The frozen ticket example took 8.08 seconds; overall median was 10.10
seconds versus the historical 13.95-second run. These are single-run observations,
with varying accuracy and complex-request delays, not a universal speed guarantee.
Fresh results and per-stage timing measurements are in
`docs/evaluations/*restored-fast-r4.json` and `docs/BUILD_LOG.md`. The frozen gates
remain unchanged. Historical reports cannot qualify changed assistant code or
profiles. The older candidate and commands below remain available.

An opt-in conversation candidate now uses local model interpretation for currency
requests, bounded arithmetic plans and same-session numerical follow-ups. It also
renders verified tool results naturally. Its profile is separately qualified;
historical M2 reports do not authorize this new profile for Windows effects.
See [the design decision](docs/decisions/0005-semantic-conversation.md) and the
latest actual results in `docs/BUILD_LOG.md`. This remains within M3.5.

On this PC, test the candidate with Windows actions simulated:

```powershell
.\.venv\Scripts\python.exe -m jarvis chat `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\assistant-staged-v2.toml" `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --web-config "$env:LOCALAPPDATA\Jarvis\web.toml"
```

Try `40 tickets at 40 SGD each in USD`, a discount/fee/bill split, and then
`make that 5 people instead`. Ask `who is Lee Zii Jia?` with the configured local
SearXNG server running. General conversation uses the local model. Missing prices
or ambiguous currencies should still prompt for clarification; unavailable or
insufficient public evidence must not become a confident answer.
The candidate is experimental: interpretation scored 16/18 and the frozen currency
corpus scored 29/34. Both failed their unchanged 100% gates. Missing-price
clarification, currency follow-ups and inference timeouts remain blockers.
Notepad simulation passed 18/18 and conversation passed 29/29; no new attended
Windows test is claimed. The three-case public smoke passed its narrow checks,
but biography rendering fell back to lengthy excerpts. Broad research quality
remains unqualified.
For another PC, start from `config/examples/assistant.toml`; verify that PC's
cloud-disabled startup evidence before creating a private profile.

Evaluate without genuine Windows effects (choose unused report filenames):

```powershell
.\.venv\Scripts\python.exe -m jarvis eval-assistant `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\assistant-staged-v2.toml" `
  --live --report .\docs\evaluations\assistant-local-new.json
```

This explicitly runs real local inference against a synthetic currency fixture;
it measures interpretation, rather than live exchange-rate availability. Separate
`eval-m3`, `eval-m2` and `eval-m2-chat` checks remain required for their scopes.
Do not append `--real` or reuse historical M2 reports with this candidate.

M0's safe simulated core and M1's local Ollama integration are implemented from
`JARVIS_Project_Specification.md`. **Simulation remains the default.**
The real model proposes a decision; strict parsing, the reviewed registry,
authorization, durable intent, cancellation gates, fake execution, and independent
observation determine the result. M2 adds explicit attended control of the installed
Microsoft Notepad: registered open, selected-window minimize/focus and safe graceful close.
See the M2 instructions below and `docs/NOTEPAD_COMPATIBILITY.md` for measured limits.

M3 adds opt-in provider-supported currency reference quotes and conversions through
the same broker. Local Ollama inference, public retrieval and Windows execution
have separate permissions. Decimal calculations and cited answers are produced
from validated data, not model memory. See the M3 commands below and
[M3 test report](docs/M3_TEST_REPORT.md).

The RTX 4070 / 32 GB / Ryzen 5 5600X desktop was separately provisioned and tested
on 2026-10-09 with Python 3.13.2, standalone Ollama 0.40.2 and `qwen3:8b`.
All 143 tests and static/dependency checks passed. The unchanged frozen corpus
scored 27/30 (90%) in each of three runs with zero unauthorized dispatches;
actual manually disconnected local inference and independently verified fake
editor state also passed. Desktop M1's simulated exit gate is met. Three request
kinds still produce rejected incorrect proposals, including an ambiguous editor
request; this is limited simulated qualification. See desktop reports in
`docs/evaluations/` and the desktop section of `docs/BUILD_LOG.md`.
Its private profile is `%LOCALAPPDATA%\Jarvis\profiles\desktop.toml`.
The laptop history and commands below describe the earlier machine; use the
desktop profile and desktop report paths on this PC.

The installed laptop model is `qwen3:1.7b`, served by official standalone Ollama
0.40.2. The corrected `planner-v4` / `ollama-chat-v2` profile scored **27/30 (90%)
in each of three runs**, with all editor and clarification cases correct and
zero unauthorized dispatches. It uses `think=false` and the original limits.
Initial failed evaluations and other unsuccessful profiles remain recorded.
The unchanged acceptance gate is 90% correct with zero unauthorized dispatches.
**The narrow simulated behavior gate passes.** Three unavailable requests still
produce clarification instead of unsupported: desktop clicking, browser opening,
and opening `other_editor`; each executes zero times. This is limited corpus
evidence, not qualification for real Windows actions. Valid structured JSON alone
does not establish correct behavior.
See `docs/evaluations/` and `docs/BUILD_LOG.md` for measured evidence and limits.
**M1's exit gate is met for this tested laptop/profile:** behavior qualification
passes and actual offline loopback inference plus verified fake execution passed.
Cloud-disabled startup evidence is operator-verified, not a programmatic attestation.
The offline check observed no physical adapters up and no active external default
routes before/after inference; snapshots do not continuously attest connectivity.

To repeat the offline check, keep the loopback server running, disconnect
Wi-Fi/Ethernet manually, and run this development check from the repository:

```powershell
.\scripts\Test-JarvisOffline.ps1
```

It reads physical-adapter/default-route state before and after real inference,
checks the fake editor's 0->1 state change and independent verification, and saves
`%LOCALAPPDATA%\Jarvis\offline-check.json`. It refuses to claim offline success while
external adapters/default routes remain active. It changes no network settings.
Snapshots do not continuously attest connectivity or exclude a hidden tunnel.
The check includes hidden adapters and counts default routes only when their
interfaces are active or unknown; stale routes on known disconnected interfaces
do not block it. Disconnect USB Ethernet as well as Wi-Fi on this laptop.
To queue a one-time check before disconnecting, add `-WaitForDisconnectSeconds 300`
(maximum five minutes). It waits locally and never disables a connection itself.
Reconnect before sharing the report in this chat; JARVIS itself needs no Codex
connection for this check. Offline success does not enable real actions.
The recorded pass is `docs/evaluations/m1-offline-validation.json`. The qualification
report's offline flag remains false because those corpus runs occurred while
connected; the separate offline report records the successful disconnected check.

From the repository root in PowerShell:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .

.\.venv\Scripts\python.exe -m pytest -v -ra
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
```

No activation or execution-policy change is required. Python 3.12 is the baseline;
Windows Python 3.13.14 was actually tested. Source uses 3.12-compatible syntax,
but Python 3.12 and other platforms have not been tested. The hash lock was
generated on Windows/Python 3.13. Development dependency setup uses PyPI.
Tests use HTTPX mock transports and fake state, with no actual network or desktop
control. Each pytest invocation creates and cleans an ignored `.pytest-run-*`
directory; optional pytest caching is disabled to avoid the previously observed
Windows temp/cache access-denied errors. Explicit `--basetemp` is honored; use
only a dedicated disposable directory because pytest clears it.

### Starting Ollama manually

The authorized standalone installation is outside Git at
`%LOCALAPPDATA%\Jarvis\runtime\ollama-v0.40.2\bin\ollama.exe`, with weights at
`%LOCALAPPDATA%\Jarvis\models`. A manually started server is currently available.
After restarting Windows, start it in a separate PowerShell terminal:

```powershell
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = "$env:LOCALAPPDATA\Jarvis\models"
$env:OLLAMA_CONTEXT_LENGTH = '4096'
& "$env:LOCALAPPDATA\Jarvis\runtime\ollama-v0.40.2\bin\ollama.exe" serve
```

These settings apply only to that process and its children. No global PATH,
persistent environment variables, startup services, or administrator setup were
changed. Do not start a second server if the existing endpoint is occupied.
The official [Windows distribution](https://docs.ollama.com/windows) supports
standalone installation; cloud disabling uses the documented
[`OLLAMA_NO_CLOUD` setting](https://docs.ollama.com/faq).
Check the startup log for `Ollama cloud disabled: true` before marking a private
profile's `cloud_disabled_verified` true and recording the evidence note.
Committed examples deliberately leave that flag false.

The private laptop profile has already been created on this machine. In the
repository terminal:

```powershell
$jarvisProfile = "$env:LOCALAPPDATA\Jarvis\profiles\laptop.toml"
.\.venv\Scripts\python.exe -m jarvis doctor --profile $jarvisProfile --evaluation-report docs/evaluations/m1-qwen3-1.7b-qualification.json
.\.venv\Scripts\python.exe -m jarvis chat --profile $jarvisProfile
# Explicit live evaluation; exit 0 passes, exit 1 fails the frozen behavior gate:
.\.venv\Scripts\python.exe -m jarvis eval --live --profile $jarvisProfile --report "$env:LOCALAPPDATA\Jarvis\last-evaluation.json"
```

Try `Hello Jarvis.`, `Open my text editor.`, `Open my editor.` followed by
`text editor`, and `What is the current MYR to JPY exchange rate?`. These flows
were exercised through the actual CLI with planner-v4. `/stop` or `/cancel`
cancels waiting inference and closes new action admissions; `/quit` exits.
Cancellation does not promise rollback after an admitted effect. Windows terminal
input handling is implemented; physical interactive key presses have not been
manually tested. Finite piped input and cancellation races are tested.

For another machine, copy `config/examples/laptop.toml` or `desktop.toml` into a
private directory outside Git, retaining `execution_mode = "simulation"`.
Edit model identity, bounded context/output settings, and provider options there;
then select it with `--profile`. The desktop example is `qwen3:8b` for the
RTX 4070 / 32 GB / Ryzen 5 5600X PC; it is separately tested as recorded above. Neither
example guarantees hardware fit. Install/download another model only after
separate setup approval, verify local-only setup, run doctor and live evaluation,
and treat its action role as unqualified until its own gates pass. No source
change or automatic routing is needed. Runtime commands never download models.

M0 regression demos still require neither Ollama nor runtime networking:

```powershell
.\.venv\Scripts\python.exe -m jarvis demo --scenario open-editor
.\.venv\Scripts\python.exe -m jarvis demo --scenario denied
.\.venv\Scripts\python.exe -m jarvis demo --scenario cancelled
.\.venv\Scripts\python.exe -m jarvis demo --scenario recovery-unknown
.\.venv\Scripts\python.exe -m jarvis demo --scenario open-editor --profile config/examples/fake-alternate.toml
```

Success changes fake running state from zero to one and observes it separately.
Denied/cancelled scenarios execute zero times. Crash recovery leaves an uncertain
effect in `NEEDS_REVIEW` without replay. Each demo has an isolated temporary
SQLite journal. Interactive chat's journal is private at
`%LOCALAPPDATA%\Jarvis\journal.sqlite`; history is memory-only, capped at eight
turns and further trimmed to fit the context budget. Raw prompts, replies, and
reasoning traces are not persisted. Synthetic evaluation reports contain case
IDs and metrics, not private conversation text.

Important files:

- `src/jarvis/models.py`: strict decision union, frozen profiles, shared provider
  interface, configurable scripted provider, and normalized inference errors.
- `ollama.py`, `prompts.py`: fixed-loopback bounded HTTP transport, metadata/model
  checks, versioned prompts and schemas, estimated context accounting.
- `core.py`, `policy.py`, `tools.py`, `domain.py`: controller-owned scope, revisions,
  exact approvals, trusted aliases, broker admission, and truthful outcomes.
- `storage.py`, `adapters.py`: durable SQLite tasks/intents/attempts/audit events,
  conservative recovery, fake mutation, and separate verification.
- `conversation.py`, `terminal.py`, `cli.py`, `evaluation.py`: bounded conversation,
  cancellation, observational doctor, explicit live evaluation and report summary.
- `tests/test_m1.py`, `tests/fixtures/m1-corpus-v1.json`: mocked integration
  regressions and the frozen 30-case live corpus; all original M0 tests remain.
- `scripts/Test-JarvisOffline.ps1`: explicit development-time offline check with
  read-only network observations and a real model/broker/fake-state smoke test.
- `docs/IMPLEMENTATION_PLAN.md`, `docs/BUILD_LOG.md`: completion and actual evidence.

One planner turn/action/observation, zero retries, one active planner, byte/token
budgets, and connection/read/task deadlines bound each request. Token accounting
uses an explicit UTF-8 byte estimate, not a claim about a real model's tokenizer.
Only exact trusted editor aliases or a controller-managed clarification bind
`text_editor`; other proposals cannot widen scope. Conversational history grants
no permissions. Exact supplied approvals remain single-use and revision/digest/
session/expiry-bound. Model switching affects the next task, never an active task.

The HTTP client accepts only `127.0.0.1:11434`, ignores environment proxies,
rejects redirects/cloud model metadata/native tool calls, caps complete responses,
and has no fake/cloud fallback. Doctor only observes; it does not install or repair.
Its selected evaluation report is historical evidence, never authorization.
Live current facts use a trusted limitation without a retrieval or model call.
M1 profiles remain simulated. M2's separately selected adapter supports only
Notepad open/focus/close; browser control, desktop input, capture, audio, file
editing, cloud providers, arbitrary execution, plugins and autonomous tasks remain
absent. M1 qualification does not qualify an M2 profile or another computer.

To regenerate the generated lock after a deliberate dependency change:

```powershell
# Bootstrap only if pip-tools is not already installed in .venv:
.\.venv\Scripts\python.exe -m pip install pip-tools
.\.venv\Scripts\python.exe -m piptools compile --extra dev --extra windows --extra browser --extra media --extra voice --extra neural-voice --strip-extras --allow-unsafe --generate-hashes --output-file requirements-dev.lock pyproject.toml
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
```

`--allow-unsafe` includes pip/build dependencies in the lock and grants no runtime
execution permission. Editable installation uses the locked local build backend.
Regenerate/test a separate lock if changing interpreter/platform makes resolution
incompatible. SQLite schema version 1 has no migration/backup tooling yet.

## M2: attended Microsoft Notepad

The approved target change is recorded in `docs/decisions/0002-notepad.md`.
This PC uses packaged Notepad 11.2607.14.0 and the existing qwen3:8b model.
The historical M2 v1 corpus retains its 90% / zero unauthorized dispatch gate.
The current desktop v10 profile uses frozen m2-corpus-v2 (24 cases) and
m2-conversation-v3 (34 cases), both requiring 100% and zero unauthorized dispatches. Failed prompt versions remain in `docs/evaluations/`. A matching
passed M2 report, installation registration and attended selection are required
for real chat. Model qualification is limited corpus evidence, not general
permission to control applications. There is no automatic save/discard or force kill.

After the minimize extension, the matching reports for the desktop v10 profile
are `docs/evaluations/m2-minimize-model-v1-r5.json` (24/24) and
`docs/evaluations/m2-minimize-conversation-v1-r3.json` (34/34). Use these as
`--model-report` and `--conversation-report` respectively. The older v10 reports
remain historical evidence; their code fingerprint no longer matches current chat.

From the project directory, local dependency setup is:

```powershell
# Create only when .venv does not already exist; never copy another machine's venv.
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
.\scripts\Register-Notepad.ps1 -Output "$env:LOCALAPPDATA\Jarvis\notepad-registration.json"
.\.venv\Scripts\python.exe -m jarvis inspect-notepad --registration "$env:LOCALAPPDATA\Jarvis\notepad-registration.json"
```

Registration is private, pins the verified Microsoft package/executable and
launcher hashes, and refuses overwriting an existing registration. After an app
update, inspect the changed installation and deliberately create a new registration.
No Notepad settings or recovery files are touched. Classic/unpackaged installations
are currently unsupported and fail closed.

For CLI-only sessions, follow [Starting Ollama manually](#starting-ollama-manually)
in a separate terminal if the registered server is not already running. Verify
the cloud-disabled startup log; loopback alone is not evidence.

On this PC the private M2 profile was derived from `desktop.toml`, retaining its
model/provider options, setting `prompt_version="planner-m2-v10"` and
`decision_version="decision-m2-v1"`. The checked-in example
`config/examples/notepad-m2.toml` starts with cloud evidence unverified.

```powershell
$m2Profile = "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-concurrent-v1.toml"
$notepadRegistration = "$env:LOCALAPPDATA\Jarvis\notepad-registration.json"
.\.venv\Scripts\python.exe -m jarvis chat --profile $m2Profile
.\.venv\Scripts\python.exe -m jarvis eval-m2 --live --profile $m2Profile --report docs/evaluations/m2-new-run.json
# Multi-turn usability has an additional frozen 29-case, 100% / zero unauthorized gate.
.\.venv\Scripts\python.exe -m jarvis eval-m2-chat --live --profile $m2Profile --report docs/evaluations/m2-chat-new-run.json
# Requires both matching passed reports. This is a real, attended desktop session.
.\.venv\Scripts\python.exe -m jarvis chat --profile $m2Profile --real --attended --registration $notepadRegistration --model-report docs/evaluations/m2-new-run.json --conversation-report docs/evaluations/m2-chat-new-run.json
```

Ask `Open Notepad.` or `Open my text editor.`, then
`Bring that Notepad window to the front.`. Use `/windows` to list opaque scoped
references. `/select <reference>` selects the window; only when you personally
confirm the whole window is an empty disposable single-tab test window, use
`/select <reference> empty-disposable` before `Close that Notepad window.`.
For the currently selected window, `/confirm-empty` provides the same explicit
operator confirmation without copying its reference. Use it only after personally
checking that the whole window is your empty, unmodified, single-tab disposable
window. Then `Close it`, `Close the Notepad window` or `Please close it` works.
`Focus on the Notepad`, `Bring Notepad to front`, and polite requests resolve to
that selected window. These are bounded single-action forms; arbitrary desktop
requests remain unsupported. Repeated focus is independently verified each time.
The adapter independently rechecks identity, empty/unmodified state and all tabs.
Nonempty, modified, multiple-tab, dialog or unknown state causes handoff before
WM_CLOSE, even if you supplied disposable confirmation. It never clicks dialogs.
Ambiguous or missing targets cannot acquire action permission. The v10 qualification handles `Open my editor` by asking a clarification;
`Open my text editor` names the registered application explicitly. An unavailable
app cannot acquire a grant. Bare `clear` asks what you mean; `/clear` clears only
the terminal display, retaining conversation and window selection. Enter slash
commands on their own line, then send the action request separately.
`Bring the text editor to the front` and `Bring it to the front again` are supported.
A reply such as `the only one that is open now` can resolve only an immediately
preceding window clarification, only to the already selected window, and only if
independent inventory shows exactly that one window. Changed selection, another
window, or an intervening turn prevents that resolution. It never selects a
personal window implicitly. Model prose claiming an effect is not an action receipt;
unsupported claims are replaced with a truthful no-action reply.
General chat retains its history. Window requests use fresh controller state and
the current owner request rather than stale action replies; their model schema
contains only the action permitted for that exact scoped reference.
Ordinary conversational replies display natural text; only simulated actions are
labeled `[SIMULATED]`. Verified real actions have no simulated label.

Ctrl+Alt+Shift+F10 latches stop while any app has focus. A hotkey conflict prevents
real startup. `/stop` also cancels inference; `/quit` exits. Restart chat after
stop only after reviewing any pending effect. Unknown effects are never retried;
after manually checking the outcome, `/review <task_id> manually-handled` records
operator review without replaying that action. The recovery notice prints the
exact task ID. Inspect and handle the outcome before acknowledging review; this
does not select a window, confirm it disposable, or re-execute the old request. Real persistence is separate at
`%LOCALAPPDATA%\Jarvis\m2-journal.sqlite`. Close dirty/unknown leftovers yourself;
exiting chat does not close Notepad. Stop Ollama with Ctrl+C in its serve terminal.

Automated tests use synthetic windows and no Ollama/desktop effects:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
```

The separate opt-in adapter lab uses scripted proposals through the same broker.
Before running it, confirm you are at the PC and accept at most two new disposable
Notepad windows and short focus changes. Pre-existing windows are excluded.
Use an interactive PowerShell terminal, stay at the PC and avoid input during
each automated operation. The interactive steps require you to type synthetic
unsaved text manually, then press the global stop hotkey with Notepad focused.

```powershell
.\.venv\Scripts\python.exe -m jarvis test-notepad --windows --attended --interactive --registration $notepadRegistration --report docs/evaluations/m2-windows-new-run.json
# Separate takeover check: exactly one user-confirmed synthetic window must remain.
.\.venv\Scripts\python.exe -m jarvis test-notepad --windows --attended --takeover-only --prepared-synthetic --registration $notepadRegistration --report docs/evaluations/m2-takeover-new-run.json
```

Default launcher behavior is measured, not guaranteed to produce a new isolated
window. If it opens an existing tab or cannot uniquely establish readiness, the
adapter reports uncertainty, blocks new effects and leaves manual handling.
Prepare/select an empty disposable window yourself rather than changing settings.
Do not overwrite old evaluation reports. That M2 validation did not include M3.

## M3: public currency data with local inference

The generic M3 extension discovers currency coverage from the configured provider's
metadata. MYR/JPY, JPY/MYR and other supported pairs use the same typed capability.
The original 11-case corpus/results are retained; the new 34-case v2 corpus keeps
the 100% correctness / zero desktop execution gate and passes 34/34 on this PC.
See current measured results in the test report. General internet research is absent.
Read [provider and freshness limits](docs/PUBLIC_DATA_COMPATIBILITY.md) and
[actual commands/results](docs/M3_TEST_REPORT.md).

The existing Python 3.13 `.venv` and `qwen3:8b` profile are reused. For a clean
project checkout, use the project-local setup block above after verifying that
`python --version` reports 3.13; do not copy another PC's `.venv`. Existing setups
only need the locked packages and editable project installation:

```powershell
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
```

Public data defaults to disabled when no config is selected. To retain a useful
currency limitation while making supplied-rate calculations locally:

```powershell
$jarvisProfile = "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-concurrent-v1.toml"
.\.venv\Scripts\python.exe -m jarvis chat --profile $jarvisProfile `
  --public-data-config .\config\examples\public-data-disabled.toml
```

The approved non-secret provider config was created on this PC at
`%LOCALAPPDATA%\Jarvis\public-data.toml` from the enabled example. On a new PC,
copy `config/examples/public-data-enabled.toml` there only when choosing to enable
that reviewed provider; preserve an existing config. Start currency chat:

```powershell
.\.venv\Scripts\python.exe -m jarvis chat --profile $jarvisProfile `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml"
```

This runs the real local model and real public currency retrieval while Windows
actions remain simulated. No `--real` or `--attended` is needed for currency.
For attended real Notepad **as well**, retain all the separate M2 arguments above
and add `--public-data-config`; do not substitute an M3 report for an M2 report.

Try these as separate messages:

```text
What is the MYR to JPY exchange rate now?
Convert 1,000 MYR to JPY using the latest available rate.
How much is 10,000 JPY in MYR?
convert 2000myr to jpy
Convert 250 SGD to MYR.
If I bought 40 tickets each worth 40 SGD, how much would the 40 tickets be in USD?
How much are 3 books at 12.50 EUR each in MYR?
Convert 40 * 40 SGD to USD.
What's 100 EUR in USD?
Convert 50 pounds to Japanese yen.
What's the reverse rate?
What about 500?
When was that rate published, and where did it come from?
Convert 100 MYR to JPY using rate 30
What is an exchange rate?
```

Normal replies show the requested conversion or rate, with a short approximation
notice. Stale rates retain a warning. Ask `Where did that rate come from?` to see
source IDs, the effective date, UTC/local retrieval time and both sources. Detailed
evidence remains recorded by the broker. A date-only source
cannot answer an exact publication-time question. All provider-advertised canonical
three-letter codes are accepted; a pair still needs available, fresh provider data.
Reviewed English aliases include ringgit, yen, US/Singapore dollars and pounds.
Simple quantity × unit-price requests calculate the total locally before converting
it. Item labels and quantities never go to the rate provider. Item quantities must
be whole numbers; totals retain the existing amount/precision limits. For multiple
purchases, fees, discounts or unclear wording, provide the final total to convert.
The common `what much` typo is accepted in a quantity question. A next-turn
clarification such as `I said 40 tickets each worth 40` reuses only the explicitly
established currency pair in that session; unrelated chat clears it. JARVIS retrieves
the rate itself when public currency access is enabled.
Unspecified dollar/symbols, misspellings, missing direction and multiple pairs
get clarification; unknown codes fail as unsupported. Weather/news are absent.
Amount replies such as `2000` resolve a pending amount question; `What about 500?`
reuses the immediately preceding unambiguous pair. An unrelated or ambiguous turn
clears that context. Reverse requests use the provider's native reverse endpoint.

Same-currency requests (`Convert 500 MYR to MYR`) calculate locally at rate 1 and
claim no external quote. Supplied-rate and identity operations never make network
requests, including metadata requests. To validate provider membership they require
unexpired cached coverage: on a cold/expired cache, explicitly request a latest rate
first. This is a deliberate fail-closed constraint, not a model-memory fallback.
Metadata has its own 24-hour TTL (`metadata_cache_seconds`); quote TTL is one hour.
Display rounding is half-even: JPY whole units, other currencies two decimal places.
This is a display policy, not a claim about every currency's legal minor units.
Accepted amounts are 0 through 1,000,000,000,000, at most 24 significant digits and
12 decimal places; scientific notation, negatives and nonfinite values are rejected.

Controls must be entered on their own line:

```text
/cache
/cache-clear
/refresh-rate
/stop
/quit
```

`/refresh-rate` submits a new broker request for the last sourced pair and bypasses
fresh cache. Cache clearing does not erase task evidence or replay requests.
Stale fallback is disabled by default; enabling it explicitly still labels dated
cached information and keeps its original retrieval timestamp. An invalid cache
file is preserved for manual inspection and not served.

Repeat the checks explicitly (use new report filenames, never overwrite failures):

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check

.\.venv\Scripts\python.exe -m jarvis currency-check --live `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --report .\docs\evaluations\m3-provider-next.json

.\.venv\Scripts\python.exe -m jarvis eval-m3 --live --profile $jarvisProfile `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --report .\docs\evaluations\m3-model-next.json

.\.venv\Scripts\python.exe -m jarvis doctor --profile $jarvisProfile `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --evaluation-report .\docs\evaluations\m3-qwen3-8b-v2-r2.json
```

`currency-check` exercises real retrieval through the broker using scripted lab
proposals, not local-model inference. `eval-m3` uses the real configured Ollama
model and `Conversation` path, real provider for live cases, a disabled-policy case,
and a clearly labeled simulated provider outage. Doctor is observational and
does not contact the public provider. No physical network isolation is claimed
by M3's outage test; disconnect networking manually if testing that separately.
Neither command opens/focuses/closes Notepad. Report hashes bind the current
currency contract, corpus, model profile/runtime identity and public-data config.
The 100% / zero-desktop-action gate is separate from M1/M2 qualification.

M3's currency capability ends here. No transactions, Notepad typing/saving,
cloud inference, additional models or M4 capabilities were added.

## M3.5: public web research with local SearXNG (qualification pending)

M3.5 adds separately configured public research to the existing broker. SearXNG
is the initial replaceable search adapter, with no required paid search API or key.
Use your own local instance. See [Windows setup/API compatibility](docs/SEARCH_PROVIDER_COMPATIBILITY.md),
[network/privacy policy](docs/WEB_NETWORK_POLICY.md), and [actual test report](docs/M3_5_TEST_REPORT.md).
The initial inspection found no working Docker/Podman runtime. The user subsequently
installed Docker Desktop and authorized local SearXNG setup. It now runs on
`127.0.0.1:8080`, with JSON enabled and restart policy `no`; the private JARVIS
configuration is `%LOCALAPPDATA%\Jarvis\web.toml`. See the compatibility document
for the pinned image and manual restart/stop commands. Search infrastructure is
available; the full research qualification gate remains separate.

Web research is absent without `--web-config`; the disabled example supplies
explicit status controls. The enabled example authorizes one exact local search
API. Public fetching still blocks loopback/private networks. Ollama, currency and
attended Notepad permissions remain separate, with no M4 browser/media automation.

After your own local SearXNG has been set up and validated, preserve any existing
private configuration and create a new one from the non-secret example:

```powershell
$jarvisProfile = "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-concurrent-v1.toml"
$jarvisWebConfig = "$env:LOCALAPPDATA\Jarvis\web.toml"
if (Test-Path -LiteralPath $jarvisWebConfig) { throw 'Inspect existing web config first.' }
Copy-Item -LiteralPath .\config\examples\web-searxng.toml -Destination $jarvisWebConfig
.\.venv\Scripts\python.exe -m jarvis chat --profile $jarvisProfile `
  --public-data-config "$env:LOCALAPPDATA\Jarvis\public-data.toml" `
  --web-config $jarvisWebConfig
```

Windows remains simulated. For genuine attended Notepad, retain all existing M2
`--real --attended --registration --model-report --conversation-report` arguments
and matching passed reports. Web research never supplies Windows authorization.

Try `What is the latest stable Python version?`, `Find documentation for Python
venv`, `Research recent AI news from two sources`, or
`Read this page: https://docs.python.org/3/library/venv.html`. Automatic routing
uses reviewed freshness/research terms plus local-model classification for owner
factual questions; obscure questions can also explicitly request `Search` or
`Research`. Trivial arithmetic/recursion/rewrite stays local. Structured
currency takes priority over generic research.

The local model plans owner-topic queries, selects result IDs, then selects fetched
source/excerpt IDs. Normal replies show the selected text without reference links,
timestamps or diagnostic footers. `/sources` and explicit source questions show
provenance; broker records retain citations and retrieval failures. Uncertainty
and conflicting-evidence warnings remain visible. This initial answer mode is extractive, not unrestricted
paraphrased synthesis. Sources may be incomplete or wrong; retrieval today never
establishes publication today. See the report for qualification limits.

Controls, on separate lines:

```text
/web-status
/web-enable
/web-disable
/sources
/web-refresh
/web-cache
/web-cache-clear
/stop
/quit
```

`What sources did you use?` reuses evidence without networking. `What changed?`
reuses fresh session evidence. `Check whether anything newer came out today` and
`/web-refresh` bypass caches. The public memory-only caches retain original times;
clearing them retains task evidence. Queries never receive chat history, Notepad,
files or memory. Known private patterns are refused; this is not universal secret
detection. Invalid/blocked/insufficient/conflicting/partial retrieval stays visible.

Default checks remain pytest, ruff check, ruff format --check and pip check.
Explicit live tests use synthetic public questions, no Windows effects and new
exclusive report filenames:

```powershell
# Full ten-category corpus requires your own ready SearXNG instance.
.\.venv\Scripts\python.exe -m jarvis eval-web --live --profile $jarvisProfile `
  --web-config $jarvisWebConfig --report .\docs\evaluations\m3_5-web-next.json
# Real public fetch and real local model, with no search-provider call:
.\.venv\Scripts\python.exe -m jarvis eval-web --live --owner-url-only `
  --profile $jarvisProfile --web-config .\config\examples\web-searxng.toml `
  --report .\docs\evaluations\m3_5-owner-url-next.json
# Observational; no public search/fetch:
.\.venv\Scripts\python.exe -m jarvis doctor --profile $jarvisProfile `
  --web-config .\config\examples\web-disabled.toml
```

The owner-URL test does not establish the full search gate. M3.5 remains incomplete,
with historical failed/pass evidence retained. M4 remains outside scope. No machine
installation is performed by these JARVIS commands.

### Improved source selection on this PC

The private `%LOCALAPPDATA%\Jarvis\web.toml` now uses 8 candidates per query,
5 bounded page attempts, 1 MiB per response and 3 MiB total, with a preserved backup.
Restart chat to load changed configuration/code. Returned search alternatives may
be fetched if preferred pages fail; every attempt consumes the configured budget.
Biographical refinements, domain diversity, later social/derivative candidates and
relevant paragraph selection improve readable evidence. Site access restrictions
are respected; Wikipedia/BWF/other 403 responses are not bypassed. The world-record
question can still be insufficient even when pages are retrieved.

The explicit fixed-public-question diagnostics (simulation only) are repeatable:

```powershell
.\.venv\Scripts\python.exe scripts/Test-JarvisSourceSelection.py --live `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-concurrent-v1.toml" `
  --web-config "$env:LOCALAPPDATA\Jarvis\web.toml" `
  --report docs/evaluations/m3_5-source-selection-next.json
```

The report preserves retrieved pages, failure receipts, source excerpts, timing
and model assessment. Manual answer review is required; script exit 0 alone is
not full milestone qualification. Existing reports cannot be overwritten.
