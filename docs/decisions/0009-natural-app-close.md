# Natural close and installed launcher identity

On 12 October 2026 the owner explicitly replaced the separate `/app-confirm-close`
and `/confirm-empty` prerequisite with a natural close request. This supersedes
those confirmation requirements in decisions 0002 and 0008, without authorizing
save, discard, force-kill, arbitrary input, broad close-all or unattended effects.

The authenticated owner request resolves the selected or sole matching window.
The controller pins fresh exact identity and creates the existing single-use broker
approval for that one normal close. Multiple unselected windows need a numbered
clarification. Stale/reused identities, dialogs, user takeover and cancellation
still prevent admission. Notepad text, modified state, multiple tabs and unknown
state remain protected by independent native inspection.

Installed application discovery remains dynamic. Desktop activation uses the OS
AppsFolder item's default open verb through a native PIDL, with no model arguments
or command lines. A versioned same-name runtime is associated only beneath the
launcher's dedicated installation folder and with the same locally verified
Authenticode leaf certificate. Package runtimes require the exact OS application
ID and package identity. Launch binary hashes and runtime hashes are distinct;
the association is recorded and validated with durable window evidence.
Authenticode verification uses cache-only URL retrieval, and does not claim fresh
online revocation checking. No application names enter matching or permission code.

Some applications interpret normal close as hide-to-tray. Success requires native
handle absence, or the exact revalidated window becoming invisible. A missing
catalog match alone is not proof. Reports describe window state, never process
termination or stopped playback. Unsure outcomes remain manual and are not replayed.

Historical corpora/results are retained. Application corpus v3 and M2 conversation
v5 reflect this explicit changed product requirement with the same 100% gate and
zero unauthorized dispatches. Native failures are retained alongside subsequent
results; compatibility is limited to actual tested applications.

Native API references: [Shell item activation](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/ns-shellapi-shellexecuteinfow),
[cache-only signature verification](https://learn.microsoft.com/en-us/windows/win32/api/wintrust/ns-wintrust-wintrust_data),
[verified signing certificate](https://learn.microsoft.com/en-us/windows/win32/api/wintrust/nf-wintrust-wthelpergetprovcertfromchain).

Steam exposed a general delegated-runtime gap: its window is owned by a differently
named helper process. Such runtimes now require the same valid signing certificate,
the launcher's dedicated installation root and a bounded, twice-revalidated native
parent chain reaching the exact registered launcher. User/session, creation times,
paths and binary hashes are bound in durable evidence. Missing parents, reused PIDs,
changed ancestry, different publishers and unrelated same-folder executables fail
closed. Discovery uses a bounded [Tool Help process snapshot](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-createtoolhelp32snapshot),
never window titles, shell commands or per-application aliases.

Input before admission still causes zero delivery. An input timestamp change after
a delivered open invalidates its observation epoch: release desktop ownership,
then perform bounded read-only reconciliation. Success requires the same exact unique
window and a stable fresh activity epoch across reobservation. Record this in
evidence; never relaunch, focus, minimize or close during reconciliation. Changed
identity, continued input, multiple/missing windows, cancellation and inaccessible
observation retain uncertain/manual-review handling. Launch observation has a
30-second settling budget, with at most three fresh activity epochs for an already
identified window; cold starts are no longer limited to the four-second window-effect
budget. Reconciliation never substitutes a different identity. Other delivered effects retain
their existing input-change boundary. A timestamp change alone cannot establish who
generated input; diagnostic observations do not grant authority to ignore input.
