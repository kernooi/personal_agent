# 0018 — Native animated screen companion

The owner explicitly approved the supplied black-orb companion request, including
M5 integration, a code renderer, preview, settings and attended Windows validation.
This is presentation for existing authorized screen reads, not a new controller.

Reuse tkinter's Tcl event loop and Windows GDI+ rather than adding Qt/web rendering
or shipping a reference sprite. The alpha-layered orb is transparent, click-through
and non-activating; the separate readable stop/privacy indicator stays available.
Use a native indicator window because this Windows/Tk build activated a hidden
initial Tk wrapper even when withdrawn and styled NOACTIVATE before mapping.

Only trusted broker-stage events reach the bounded companion IPC. Acknowledged
capture state precedes screenshots, allowing unsupported-affinity fallback to hide
only the orb. Terminal/cancellation events cannot be revived by stale updates.
UI failure must never rewrite a verified broker result or silently remove the
required capture indicator. The UI process has a bounded graceful tail and an
independent self-exit watchdog on parent shutdown/EOF; it never kills a target app.

Capture exclusion uses supported per-window affinity plus narrowly checked owned
interpreter/UI identity; it creates no general exception for protected windows.
Native light/dark image comparisons verified exclusion on this PC. DPI and other
compatibility limits remain explicit in [the companion report](../DESKTOP_COMPANION.md).
