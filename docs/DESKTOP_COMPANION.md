# Animated desktop companion

The M5 screen assistant now has one code-rendered, charcoal orb with exactly two
white capsule eyes. It uses Windows GDI+ vector drawing, a per-pixel-alpha native
layered window, and the existing tkinter/Tcl event loop. There are no new packages,
sprites, image downloads, animation model calls or additional desktop controls.

The renderer follows the supplied reference: circular graphite body, upper-left
material lighting, darker lower-right shading, small upper-middle eyes, coordinated
gaze and slight eye rotation. It adds no mouth, pupils, rings, particles or text to
the character. The separate readable privacy/stop indicator remains visible.
The former red rectangular panel is now a compact charcoal badge with rounded
corners and shorter activity text. Click the badge to stop screen access.

## Use and preview

Restart the normal GUI, then ask `What am I looking at?` or `Scan my screen`.
With the existing enabled private screen configuration, the orb appears only after
scope/model validation, changes from curious capture to gentler upward-looking
analysis, then blinks, subtly bounces and fades. Errors look down and fade;
cancellation hides immediately. Denied requests do not display a scanning orb.
Opening JARVIS alone never starts capture.

```powershell
.\.venv\Scripts\pythonw.exe scripts\Chat-JarvisGUI.py

# Same renderer/state machine, without captures, models or infrastructure startup:
.\.venv\Scripts\python.exe -m jarvis companion-preview --cycle
.\.venv\Scripts\python.exe -m jarvis companion-preview --reduced-motion
.\.venv\Scripts\python.exe -m jarvis companion-preview --size 128 --duration 30

# Generated artwork only; refuses to overwrite an existing file:
.\.venv\Scripts\python.exe -m jarvis companion-preview --size 128 --export orb-preview.png
```

The preview menu exercises hidden, appearing, idle, left/right/up gaze, blinking,
capturing, analyzing, watching, success, error and disappearing. Cycle changes every
two seconds; choosing a menu entry stops cycling. Terminal states intentionally
finish their animation and hide. Export is a row-major contact sheet in that order,
alternating light and dark synthetic backgrounds; it is not a desktop screenshot.

Append this optional table to private `%LOCALAPPDATA%\Jarvis\screen.toml`, keeping
all existing capture/vision settings. Omitted values receive these defaults:

```toml
[companion]
enabled = true
size = 80
position = "bottom-right"
intensity = 0.7
reduced_motion = "system"
show_during_watch = true
```

Size is 48–128 DIP. Position accepts the four corners. Intensity is 0–1;
reduced motion accepts `system`, `always`, `never`. The system preference is read,
never modified. `enabled=false` disables only the orb. The privacy/stop indicator
remains. `show_during_watch=false` hides the orb between samples, never the readable
watch indicator; scheduled capture/analysis can still display it.

Watching retains M5's separate `watch_enabled` setting, selected exact window,
expiry/sample limits and foreground policy. Between samples the indicator says
`Watching active · between scheduled samples`; it does not imply continuous
capture. No recording capability was added. Close/click the readable indicator,
`/screen-stop`, `/stop` or Ctrl+Alt+Shift+F10 stops further reads.

## Implementation

- `companion.py`: strict settings, bounded task/sequence state, geometry, smooth
  270 ms gaze interpolation, controlled holds, 150 ms blinks, subtle bob and tails.
- `companion_windows.py`: GDI+ gradients/capsules, native alpha composition,
  work-area/monitor DPI placement, no-activate transparent hit testing, cleanup.
- `companion_status.py`: readable native no-activate stop window. A Tcl interpreter
  dispatches timers/messages without creating a Tk toplevel. This avoids the
  hidden-window activation observed with Tk's initial map on this PC.
- `companion_host.py`: bounded metadata-only IPC, responsive animation while the
  parent performs synchronous inference, reduced motion and bounded shutdown.
- `screen_tools.py` emits presentation events from actual broker/capture/vision
  stages. Acknowledgement precedes pixel capture; model text cannot issue UI events.
  Duplicate/late/retired events cannot revive a finished task. No prompts, titles,
  pixels or interpretations are sent to the orb host.
- `screen_capture.py`, `screen_worker.py`: existing transient capture and liveness
  gates, with narrowly verified ownership for the companion/indicator windows.
  Windows venv launcher ancestry, interpreter identity, session, owner, creation
  order, exact UI class and affinity are checked before ignoring those windows.
  This does not exempt another application's protected window.

The orb uses `WDA_EXCLUDEFROMCAPTURE` and checks it back. If unsupported, it hides
synchronously during capture, retaining the privacy indicator. Exclusion is not a
DRM/security boundary. The live comparison below verifies this capture backend on
this Windows build, not every screen recorder. See
[Microsoft's display-affinity documentation](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity).

## Validation on this PC

All reports are retained under `docs/evaluations/companion-*`. The native lab
captures only its own synthetic fixture; it never saves ordinary desktop images.
After attended readiness:

```powershell
.\.venv\Scripts\python.exe scripts\Test-JarvisCompanion.py --windows --attended --interactive `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-concurrent-v1.toml" `
  --screen-config "$env:LOCALAPPDATA\Jarvis\screen.toml" `
  --report docs/evaluations/companion-windows-next.json
```

The lab's `REVIEW REQUIRED` means inspect the individual checks; it is not a pass.

| Evidence | Actual result |
| --- | --- |
| r1/r2 | Capture rejected the venv UI child; preserved failed runs. |
| r3/r4 | Click-through worked, but initial Tk map took focus; exclusion comparison and watching failed. Preserved. |
| r3 physical input/stop | Operator clicked and typed through the orb. Global hotkey produced CANCELLED, zero new captures, UI process ended. |
| r5, native status fix | Light/dark: visible orb, unchanged foreground, hit test reaches fixture, byte-identical captures with/without overlay, HWND destroyed. Real local M5 capture 0.389 s and vision 4.027 s. |
| r6 | Same light/dark checks pass. Native bounded watch captured twice and ended; between-sample and terminal events recorded. Watch interpretation was explicitly scripted, not live-vision qualification. |
| Monitor placement v1 | Primary at 48 DIP with reduced motion, secondary at 128 DIP: within monitor bounds, no focus change, HWNDs destroyed. Both monitors are 96 DPI. |
| Shutdown v1 | Intentionally blocked the owned UI event loop. Shutdown watchdog ended its process and destroyed the orb in 1.261 s; zero captures. |
| Performance v1 | 181 frames / 3.013 s = 60.08 FPS; 0.607 ms render/frame; 0.141 CPU seconds (4.67% of one CPU core); 37.45 MiB working set, 22.31 MiB private memory for the UI process. |

r6's one-shot timing object was inadvertently shared with subsequent watch samples;
its timing fields reflect the final scripted sample. Use r5 for real-vision timing.
The lab now copies timing values. No old result was rewritten. Performance is a
short local sample, excluding capture/model processes; it is not a long-run CPU,
memory-leak or frame-pacing guarantee.

Generated contact-sheet artwork was visually compared with the reference at 128 DIP:
smooth circular outline, understated graphite depth, exactly two rounded white eyes,
correct upper-middle placement/spacing and no extra facial decorations. Live light
and dark fixture comparisons independently established visibility/exclusion.

Deterministic tests cover geometry/bounds, gaze/blink, entrance/exit, cancellation,
duplicates/late/rapid events, repeated tasks, watching, disabled/reduced mode,
monitor/DPI placement, exclusion ownership and idempotent cleanup/fallback. Full
suite: **1,488 passed**; ruff lint/format, pip dependency and whitespace checks pass.

All six source-bound qwen3:8b qualification checks were refreshed and matched:
Notepad model 24/24, conversation 41/41, applications 31/31, browser 27/27,
Spotify desktop 25/25 and request language 33/33. These use actual local inference
with fake effect controllers; they do not add live app/media testing. The first
Notepad run preserved a 30.46 s greeting timeout (23/24, zero unauthorized effects).
Repeating the unchanged gate after the other evaluations warmed the model passed
24/24. No timeout/profile/acceptance threshold was changed. Both GUI and terminal
share the refreshed report paths in `Chat-JarvisAll.py`; the initial cold-load
timeout remains an observed runtime limitation.

Native validation here is at 96 DPI on both monitors. Higher/mixed DPI,
monitor hot-plug, real reduced-motion Windows setting, lock/unlock transitions,
unsupported-affinity fallback and long-duration resource behavior remain unverified
on hardware; geometry/fallback branches have deterministic tests. No system settings
were changed to test them. Broader **M5 remains NOT FULLY VERIFIED** as documented
in [its report](M5_TEST_REPORT.md). This feature adds presentation, not permissions
or generic screen control. No commit or push was performed.
