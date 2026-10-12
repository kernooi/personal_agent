# Concurrent PC use during targeted window lifecycle

On 12 October 2026 the owner explicitly requested that using the keyboard/mouse or
switching focus while waiting should not cancel application commands. This replaces
the exclusive-input requirement for opted-in named/selected open, focus, minimize
and normal close operations. It does not authorize generic typing/clicking, changes
to personal work, save/discard, force-kill, secure-desktop access or automatic replay.

Trusted profile field `window_input_policy` defaults to `exclusive` for compatibility;
`targeted` is an explicit operator selection. The private combined-session profile
selects targeted mode; the older private v10 profile remains intact. The controller
copies this selection into the prepared, approval-bound worker payload. It is not a
model argument or an authority a model response can create.

Targeted effects bind the named or selected exact identity, not whichever window
is currently foreground. Revalidate identities, binary hashes, user/session,
registration, dialogs, clean Notepad state, grant/revision/expiry and cancellation
before delivery. Native desktop observation still rejects locked/secure desktops.
An unrelated input timestamp or foreground change does not invalidate that binding.
The desktop lease still serializes automation effects, and the global stop remains.

Verification inspects actual window postconditions independently. Focus success
still requires the exact target in the foreground; if Windows refuses foreground
activation or the user changes it again, do not claim success or inject keys to
force it. Closing dirty/mixed/unknown Notepad remains prohibited even when input
changes are permitted. Unknown delivery/identity outcomes remain journaled and manual.
Public research and browser/media target rules are not altered by this policy.

Retain exclusive-mode regressions and historical corpora/reports. New application
corpus v4 changes only the unrelated-input expectation under explicit targeted
policy; its acceptance remains 100% and zero unauthorized effects. New tests verify
target preservation while another app receives input, continued dirty-work denial,
exact native commit, and cancellation/revocation/stale-target/dialog protections in
both modes. Historical-report fixture migration adds the new default profile field
only to synthetic current-code qualification records, without editing old evidence.
