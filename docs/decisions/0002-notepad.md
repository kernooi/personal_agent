# M2 uses genuine Windows Notepad

Date: 2026-10-10. Status: user-approved target change.

The implementation request explicitly replaces the specification's custom test
editor with the installed Microsoft Windows Notepad. Fake adapters remain the
default automated-test targets. No alternative editor or fixture application is
used for live Windows evidence.

Only registered opening and scoped window focus/graceful close are implemented.
Native/UI Automation observation uses process creation time, executable hash,
package, user session, HWND and accessibility runtime identity. Private registration
pins the measured installation; updates require deliberate re-registration.
Model arguments contain app IDs or broker-issued window references only.

Packaged Notepad may restore tabs, reuse a process, or close without a save dialog.
Therefore an empty newly discovered window is not automatically owned. An explicit
attended lab selection confirms a disposable empty single-tab window, with baseline
windows excluded. Whole-window metadata is rechecked before close; nonempty, multiple
tabs, unavailable metadata, dialogs or takeover cause handoff before WM_CLOSE.
No document text, tab titles or recovery files are read. No settings are changed.

UI Automation is confined to bounded disposable workers with JSON pipes and a
two-phase admission protocol. Workers can be terminated without terminating Notepad.
Native focus restrictions are respected without injected input or repeated attempts.
A process-local registered stop hotkey and one cross-process desktop lease guard
effects. Desktop snapshots are not a security boundary against same-user malware.
The lease is held through independent verification. Empty and unmodified state
must both be known; the measured packaged Document control is supported without
reading text. Safe identity/postcondition summaries are durable; raw prompts and
document/tab labels are not. The existing SQLite tables remain schema version 1;
optional JSON fields preserve old M0/M1 records, and real chat uses a separate journal.

Rejected: custom editor, undocumented Notepad launch switches, force termination,
title-only targeting, automatic ownership of restored windows, and assuming a save
prompt proves close safety. Unknown outcomes remain for review without replay.

Consequences: open/focus can succeed even where automatic close is unsupported.
Real completion requires separate actual adapter, local-model, dirty-state and
interruption evidence; fakes cannot qualify Windows behavior.

M2 usability follow-up (2026-10-10): owner requests use a composable, whole-message
single-action grammar for reviewed Notepad names and unambiguous selected-window
references. Negation, explanatory text, compound commands and unrelated targets
do not grant authority. Selection is refreshed independently and cannot silently
rebind to another window. The planner receives selection separately from per-turn
permission, so a refusal does not imply that the window vanished. Candidate
schemas constrain permitted effects and exact references, while strict parsing
and every broker check remain mandatory. Window requests use fresh observed
controller state rather than old action replies; ordinary conversation retains
history. `/confirm-empty` is explicit operator confirmation of the current
selected disposable window, with native clean/single-tab checks unchanged.
`/clear` affects terminal display only. New real profiles require both original
model qualification and the frozen 23-turn, 100% conversation qualification.

Transcript follow-up: action status cannot come from model say/clarify/unsupported
prose. A controller presentation guard blocks completion claims and never converts
text into an effect. v10 adds reviewed text-editor and repetition forms plus
one-turn clarification binding to an already selected, uniquely observed window.
Clarification state records effect/reference in the controller, clears on another
turn, and cannot guess or rebind targets. Unknown input-during-verification remains
UNKNOWN; messages identify cause and exact review command. No automatic recovery
acknowledgment or retry is introduced. The expanded frozen corpus is separate;
prior corpus and failed/qualified results remain historical evidence.


Selected-window minimize extension (2026-10-11): the user requested minimize in
addition to open, close and focus. This extension is limited to registered Notepad,
using windows.minimize with an exact broker-issued window reference. The existing
broker grant, single-use approval, journal, desktop lease and worker commit gate
apply. Native ShowWindowAsync(SW_MINIMIZE) is followed by an independent IsIconic
observation on the same verified identity. Focus restores a minimized window with
SW_RESTORE before attempting foreground activation; no injected input is used.
Minimize does not discard work and needs no empty-disposable confirmation. Disabled
windows or owned dialogs cause handoff. Other applications stay unregistered for
this effect. Original frozen corpora/reports remain historical; the new minimize
corpus and conversation corpus require 100% correct with zero unauthorized effects.
ShowWindowAsync only acknowledges starting an operation, not completion:
https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-showwindowasync
