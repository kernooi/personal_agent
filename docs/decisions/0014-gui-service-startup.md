# Automatic local services and GUI connection

The owner explicitly requested automatic model/SearXNG startup and connection when
opening the GUI, without pressing Start chat. This supersedes decision 0013's manual
runtime-start/initial-connect behavior. It does not authorize new model-callable
capabilities, automatic real PC effects, installations or logon services.

The GUI automatically begins a simulation session. Existing local infrastructure
is prepared off the UI thread before launching the same qualified chat backend.
The installed-profile model and local SearXNG boot independently. An explicit
attended-controls checkbox reconnects in real mode without another Start click;
mode changes start a fresh context. Stop/close cancels further startup steps and
cooperatively ends chat. It does not kill shared services, undo admitted work or
silently retry an uncertain desktop operation.

Private gui-startup.toml holds registered runtime path/hash/version, local Docker
context, owned SearXNG name and immutable image digest. Model names, context and
keep-alive remain in the existing text profile. Validate runtime location/hash,
reuse the expected loopback server or start it with process-local NO_CLOUD, HOST,
MODELS and CONTEXT_LENGTH. On a fresh start, check the actual new private log for
cloud disabled before warming the model. Existing profile setup evidence remains
operator-verified; loopback does not create a new cloud-disable attestation. Check
installed models first, preload only the configured artifact with an empty local
API request, then independently observe it in /api/ps. Never pull a model or use a
cloud/fake fallback. Missing/changing artifacts fail with a visible startup error.

Use the existing installed Docker CLI and documented desktop start --detach when
the engine is stopped. Require the explicitly chosen context to use a known local
Windows named pipe and the Linux engine. Inspect cached pinned image and container
identity, private mounts, nonprivileged bridge networking, exact loopback port
binding and disabled restart policy before starting a stopped container. If the
previous --rm container disappeared, recreate only the same approved cached image
and mounts with --pull never. Verify live published ports and the local /healthz
endpoint. These fixed service probes are bootstrap-only authority; public web fetch
still rejects all local/private destinations. No private chat is sent to search.

Reuse services across GUI sessions and leave them running on close. No unrelated
container/server is stopped or reconfigured, no Docker context is globally changed,
and no restart policy, Windows startup entry, elevated installation or WSL/network
configuration is added. An unavailable search service yields a notice and allows
local chat; unavailable local model prevents chat. Bounded waits and cancellation
keep the UI responsive. Services already started may remain after cancellation.

Tests distinguish mocked cold server/Docker-engine startup from actual GUI startup
on this PC. Cover reuse, stopped/removed container, local-only destinations,
hash/version/model checks, cloud-log verification, pinned/no-download creation,
mount/network/restart/privilege denials, optional search failure, cancellation,
single-flight auto-connect and explicit attended-mode switch. Existing frozen
model/native gates and unknown/unsaved-work policies remain unchanged.
