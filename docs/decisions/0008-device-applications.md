# ADR 0008: Device-discovered application window control

The user approved open, focus, minimize and close for installed applications,
starting with this Windows PC and an extensible platform interface. This supersedes
the prior Notepad-only application ceiling for these four operations. It does not
authorize generic input, files, installation, arbitrary shell, remote devices or
other platforms' real effects.

`ApplicationPlatform.call` supplies bounded catalog discovery, observation and
gated effects. The Windows implementation discovers AppsFolder entries using
trusted OS metadata, resolves desktop EXEs or packaged-app manifest identities,
and activates packages through IApplicationActivationManager. Target names and
IDs are device-local data, never application-specific policy branches. A fake
platform exercises the same controller and broker without Windows effects.
Other operating systems require their own native adapter and validation.

The controller resolves the owner's whole command to one catalog entry and one
window. Ambiguous names/windows require selection. The model proposes a strict
whole `applications-choice-v1` decision within that exact scope; it cannot supply
paths, launch arguments, shell commands or a replacement target. Labels are
untrusted data. The existing broker owns grants, exact approvals, revisions,
journaling, cancellation and admission. Real mode is separately opted into with
attended consent and a current 100% frozen-corpus qualification report.

Prepared targets bind catalog metadata, executable hash and window identity
(HWND, PID, process creation, user, session, package and class). A supervised
bounded worker rechecks before and after the parent's exact commit handshake.
Only that worker may be terminated on timeout, never the application. A shared
desktop lease and global stop remain in force. Observation independently checks
window state, foreground and minimization; close also requires actual HWND absence,
not merely a missing catalog match. Unknown delivery requires manual review;
there is no replay. Model/window private context is not sent to public tools.

For Windows-hosted packaged apps, bind the top-level OS frame to exactly one
visible app-owned child with the same user/session, exact installed executable and
package. The host must be the system-directory ApplicationFrameHost.exe; its PID,
creation time and binary hash plus the child HWND join the prepared identity.
Revalidation rejects changed hosts, children, packages and multiple content
windows. This uses bounded [child enumeration](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-enumchildwindows)
and [root ancestry](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getancestor),
without reading page/window text or performing generic input.

Windows can detach package content during minimization. A remembered association
is retained only while the original frame is actually minimized and both host and
content process creation, user/session, package and hashes still match. The same
child HWND must remain in that frame or become its own root; reparenting to another
frame is rejected. Detached content cannot become a second selected app window.
This handles observed Windows lifecycle behavior without guessing new identities.

Close uses WM_CLOSE after `/app-confirm-close`: the owner must inspect/save work
in the exact selected window. Review expires after 60 seconds and is single-use.
Generic apps do not expose a universal trustworthy unsaved-work signal; the
controller makes no such claim. Known modal/disabled/unsafe states refuse delivery.
Notepad additionally retains the independent empty, unmodified, single-tab check
and the owner's disposable-window confirmation. No dialog save/discard choice,
force kill or automated closing of unknown Notepad work is permitted.

Discovery is bounded and conservative. Entries with unavailable launch identity,
remote paths, installers/security tools, inaccessible processes, ambiguous shared
executables or unverifiable windows remain unsupported. Catalog presence alone
is not evidence that all four operations work for that application. Services,
elevated windows, tray-only apps, portable apps absent from AppsFolder and
applications using delegated processes may need additional reviewed adapters.
No arbitrary executable-path fallback is provided.

Existing Notepad/text-editor aliases and currency, public research and media
routes remain available. Application journals are separate for simulation and
real mode. Application names/selection are session-owned; effects never derive
from old assistant replies. The explicit Windows lab uses two new disposable
applications, with pre-existing windows excluded; it is bounded evidence only.
