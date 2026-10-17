# M5: private screen observations on the existing broker

The owner approved general screen understanding, extending the earlier Wordle-only
M5 scope. Advice does not authorize interaction. Existing app/media/web permissions
stay separate. A vision model must be installed and advertise image input; neither
the text model nor an unavailable vision model receives fabricated images/replies.

The existing `Broker.dispatch`, policy, task states, intent/admission journal,
cancellation and evidence checks admit `screen.observe / screen_private_read`.
The authenticated chat controller binds one exact capture target and opaque nonce;
the vision model receives no tool registry and cannot choose paths or targets.
Screen results never enter ordinary model history, public research or action logs.
The journal contains hashes/opaque references and completion receipts only.

The initial Windows backend uses GDI BitBlt on visible desktop pixels in a bounded,
disposable native worker, with per-thread per-monitor-v2 awareness. It reuses the
existing Native process-creation/session/owner/executable identity infrastructure.
It rejects hidden, minimized, protected, covered, resized or offscreen windows,
locked/non-default desktops, unsupported remote sessions and monitor changes.
The owner subsequently supplied standing permission for on-demand full-screen
reads without scope-selection prompts. Enabled screen configurations now default
to `primary_display`; trusted discovery binds the main monitor for each explicit
visual question. Optional selected windows remain narrower, while explicit whole
screen wording returns to the main monitor. All-monitor requests bind desktop
scope separately, retaining geometry/pixel limits. Foreground-only behavior remains
configurable. No automatic startup/background reads or unrelated control follows
from this grant; exclusions, visible indication, cancellation and broker checks
remain mandatory.

Windows.Graphics.Capture has a useful native picker and capture border but requires
additional WinRT/Direct3D bindings not installed in this project. PrintWindow can
render hidden content and block target processes; it is not used. GDI is deliberately
visible-only: no occlusion bypass, hidden-tab read or capture-protection workaround.
It is an initial conservative compatibility choice, not universal Windows support.
See [capture compatibility](../SCREEN_CAPTURE_COMPATIBILITY.md).

Images are lossless PNGs in memory at native resolution. Excess dimensions fail
with a request to resize/select a smaller scope instead of silently destroying
small text. A question explicitly about Wordle may use a strictly detected regular
5-by-6 grid crop within the authorized pixels, with lossless 2x enlargement when
within the pixel budget. Original bounds and analyzed regions remain recorded.
General tiling/downscaling and automatic image enhancement are not implemented.
Artifact IDs are opaque in-memory references, never file operations.

Watching is explicitly started, window-scoped and bounded by duration, sample count
and interval. Polling uses the existing chat event loop and serial task broker,
with no capture backlog. Equal frame hashes skip vision. A separate small visible
indicator remains responsive while local inference waits; closing it stops further
submissions. Global stop, terminal stop, revocation, lock and lost scope stop capture.
No frame history is kept. M6/M7/M8 remain unimplemented.

Primary documentation reviewed during development:

- [Microsoft GDI BitBlt](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-bitblt)
- [Microsoft screen capture overview](https://learn.microsoft.com/en-us/windows/apps/develop/media-authoring-processing/screen-capture)
- [Microsoft display affinity](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowdisplayaffinity)
- [Microsoft accessibility properties](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-automation-element-propids)
- [Ollama image chat API](https://docs.ollama.com/api/chat)
