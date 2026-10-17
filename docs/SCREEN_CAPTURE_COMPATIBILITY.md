# Screen capture compatibility

Initial inspected host: Windows 11 Home 10.0.26200, Python 3.13, Ryzen 5 5600X,
32 GB RAM, RTX 4070 / 12,282 MiB VRAM. Inspection is not a capture test.
Native capture and live-vision evidence is tracked separately in M5_TEST_REPORT.md.
Real owned-window capture passed on this host: 802-by-622 physical pixels, DPI 96,
with error text, a public flower photograph and two Wordle states. Excluding the
owned Python window denied capture with generation zero. Physical global stop
cancelled the next request with zero new captures. Covered-window rejection was
also observed before the fixture was made visible. No ordinary apps were captured.
Following the owner's standing full-screen authorization, a real main-display
capture passed at 2560-by-1440, DPI 96, without saving pixels or running image
inference. The initial attempt correctly failed its conservative region check;
diagnosis showed DWM-cloaked invisible helper surfaces were being treated as
visible. Skip only surfaces positively reported cloaked; unknown status still
fails through policy checks. No exclusion or protection bypass was added.
Multi-display desktop, multi-monitor moves, non-96 DPI, protected/password windows,
remote-session and actual lock/disconnect transitions remain NOT RUN natively.

The backend uses `GetForegroundWindow`, existing process/session/owner identity,
DWM visible frame bounds, per-monitor-v2 physical pixels, monitor enumeration,
GDI `BitBlt` and `GetDIBits`. All handles use explicit 64-bit signatures.
No elevated worker, global DPI change, desktop service or extra dependency is used.

Supported by implementation (native compatibility must still be tested):

- Foreground window or an explicitly chosen visible window.
- Explicitly chosen monitor or entire virtual desktop, within configured pixel limits.
- Negative monitor origins and windows spanning contiguous monitors.
- Original-resolution lossless PNG with capture time, DPI, region, identity and generation.

Conservative failures:

- Any overlap above a selected window, including the capture indicator, rejects it.
  Move the indicator outside the target before another explicit request. Nothing
  is hidden automatically. Maximized/fullscreen window capture may therefore fail;
  select a separately permitted display or use a smaller window.
- Monitor gaps, offscreen pixels, resizing and disconnected displays reject capture.
- Hidden/minimized/cloaked windows are not restored to make them capturable.
- Protected affinity, visible accessibility password fields and configured exclusions
  deny inspection. Unavailable sensitive-field inspection fails the worker.
- Locked/secure/non-default desktops and remote sessions are unsupported.
- Solid/empty images are not accepted as evidence. Partly protected content may still
  be unreadable; report uncertainty rather than bypassing OS protection.

Display capture checks every intersecting top-level window and fails if one cannot
be inspected under policy. Shell surfaces and inaccessible processes may therefore
prevent full-display capture. This is a known limit, not a permission bypass.
Title-based exclusions are heuristics and cannot identify every sensitive website
or localized private browser. Explicit narrower executable allowlists and carefully
chosen windows are recommended; no universal secret detection is claimed.

Workers have configured deadlines and bounded IPC/image sizes. A hung or crashed
worker is terminated, never the observed app. Screenshots do not go to disk.
The adapter does not read browser cookies, profiles, history or hidden page content.
