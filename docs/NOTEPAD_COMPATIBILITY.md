# Measured Microsoft Notepad compatibility

2026-10-10, this desktop only. Windows 11 Home 10.0.26200, build 26200;
Python 3.13.2; RTX 4070 / 32 GB / Ryzen 5 5600X. The earlier laptop is not
used as qualification evidence for this adapter.

Installed application: packaged/tabbed Microsoft Notepad 11.2607.14.0,
`Microsoft.WindowsNotepad_11.2607.14.0_x64__8wekyb3d8bbwe`.
Both the fixed System32 launcher and installed WindowsApps Notepad binary had
valid Microsoft Authenticode signatures. The private registration pins paths,
package and SHA-256 hashes outside Git. No PATH lookup or launch arguments are used.
Classic/unpackaged Notepad is unsupported by this implementation.

Native discovery requires visible class `Notepad`, exact registered executable
and hash, Microsoft package, current user SID and interactive session. Process
creation time, HWND and UIA runtime ID bind later observations. Names/titles,
document bodies, session/recovery files and ordinary keystrokes are never read.
Tab runtime IDs are counted, never tab labels. `GetLastInputInfo` supplies only
an activity tick; foreground identity distinguishes expected effect transitions
from user takeover. Locked/non-default desktops fail closed.

This version exposes one native `RichEditD2DPT` **Document** control (UIA 50030),
not Edit (50004). The original Edit-only query returned unknown state and the
first lab safely stopped, leaving its window open. The corrected query recognizes
Edit or Document, then checks the measured native editor class. Empty state is
measured by TextPattern document endpoint comparison, without GetText; dirty state
is independently queried with bounded `EM_GETMODIFY`. Actual blank state was
empty=true / modified=false / one tab; after the user's synthetic typing it was
empty=false / modified=true / one tab. Unknown modify state is never treated clean.

Official references: [UIA threading](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-threading),
[CompareEndpoints](https://learn.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationtextrange-compareendpoints),
[EM_GETMODIFY](https://learn.microsoft.com/en-us/windows/win32/controls/em-getmodify),
[foreground restrictions](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow),
[registered hotkeys](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey).
The control classification and application behavior above were measured here,
not inferred from those general API documents.

The default launcher produced two distinct windows in the attended test. A process
or launch receipt alone was never accepted as readiness. A selected authorized
window was reused without another launch. Focus was independently observed as the
exact target HWND, without injected keys or repeated activation attempts. Graceful
WM_CLOSE removed only the selected confirmed empty/unmodified single-tab window;
the other window remained. No saved/preserved-content claim was made.

The interactive adapter lab `evaluations/m2-notepad-windows-v3.json` exited 0:
open/reuse/focus/two-window targeting/empty close passed; manually typed unsaved
work caused pre-dispatch handoff; physical Ctrl+Alt+Shift+F10 with Notepad focused
latched stop, and the next request was cancelled with no additional delivery.
`evaluations/m2-native-takeover-v1.json` separately records an attended paused
focus admission: the user's actual click changed activity/foreground; the worker
rejected before any native effect, preserving the synthetic window (exit 0).

Live qwen3:8b chat is separate: `evaluations/m2-live-chat-v1.json` records verified
real open, focus and clean close at 1.7952, 2.6335 and 2.4206 seconds. Ambiguity
clarified; an unavailable browser request clarified incorrectly but dispatched
nothing; selecting the user-confirmed synthetic dirty window led to close handoff
with zero delivery. That remaining unsaved window is left for manual handling.
Prior personal windows were not read or closed. The existing synthetic dirty
window was preserved during the new live-chat window's operations.

Limits: default launching may instead add/restore a tab or yield no uniquely new
window on another configuration. Such outcomes require review, never automatic
relaunch or ownership of an existing window. Multiple/mixed/restored tabs, dirty
or unknown state, unexpected activity, inaccessible UIA and dialogs prevent
automatic close. No actual save-dialog handling, session lock, app update or
hostile same-user executable substitution was manufactured on this PC; relevant
identity/dialog/timeout/recovery failures are tested with fakes/mocks. A handoff
does not qualify automatic dirty-document close. No settings were changed.

Conversational retest on the same installation: planner-m2-v9, qwen3:8b,
`docs/evaluations/m2-live-conversation-v9-r1.json` passed. Two sequential real
opens, natural focus variants, explicit empty-disposable confirmation and clean
close verified independently. Dirty synthetic close and physical stop both
prevented admission. Changed input/focus also paused three requests before effects;
these remain recorded. One synthetic unsaved window remains for manual handling.
No compatibility claim extends to another Notepad version or PC.

Operator transcript correction: v10 real open, both text-editor/repetition focus
phrases and confirmed clean close verified on this same installation. Bound
clarification focus paused before delivery for changed input. Initial live report
is retained as failed for a non-action state claim; final controller guard passed
an actual local-model terminal check with zero effects. See v10 reports and build
log; no new Notepad compatibility claim or broader desktop scope is implied.
