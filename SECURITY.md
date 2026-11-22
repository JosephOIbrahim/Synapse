# Security Policy

## Reporting a vulnerability

Report privately via [GitHub security advisories](https://github.com/JosephOIbrahim/Synapse/security/advisories/new) for this repository.

Do not open a public issue for a vulnerability. Public issues are for bugs — use the bug template, which asks for your Houdini build, license tier, and `synapse_doctor` output.

## Threat model — a localhost, single-seat surface

SYNAPSE runs inside Houdini's own Python interpreter on the artist's machine. The live surface is `ws://127.0.0.1:9999/synapse`.

The loopback bind is enforced, not just documented: the transport passes `ADDRESS=127.0.0.1` to Houdini's `hwebserver` (whose own default is the any-address `0.0.0.0`), and a non-loopback listen is refused when no authentication key exists. Listening beyond loopback is an explicit opt-in — `SYNAPSE_DEPLOY_MODE` set to a studio mode, or `SYNAPSE_ALLOW_LAN=1` with `SYNAPSE_BIND_ADDRESS` — and always requires a key. Setup mints `~/.synapse/auth.key` whenever no readable key exists, so the WebSocket handshake and the `/mcp` Bearer check are on out of the box; `SYNAPSE_API_KEY` overrides the file. `synapse_doctor` reports the listen address and fails if the port accepts on any of this machine's hostname-resolved non-loopback IPv4 addresses in local mode. One exception ships: `server/api_adapter.py`, an older REST adapter that no shipped path starts, still uses Houdini's default any-address; do not start it by hand.

Stated plainly:

This build enforces no roles. `server/rbac.py` defines them, but neither shipped endpoint (`/synapse`, `/mcp`) checks them, and the key is one shared secret with no user identity: anyone holding it can execute code. The live surface is a loopback WebSocket; origin validation is fail-safe — a connection with an unrecognized `Origin` is rejected, never waved through. An API key (from the installer, `SYNAPSE_API_KEY`, or `~/.synapse/auth.key`) turns authentication on for both `/synapse` and `/mcp`. Setting `SYNAPSE_DEPLOY_MODE` to `studio-lan` or `studio-vpn` moves the bind off loopback (unless `SYNAPSE_BIND_ADDRESS` names another address) and, when the bind is off loopback, requires that key; it does not turn roles on.

Wrapped scene edits are grouped so one Ctrl+Z undoes the whole operation. Grouping is not rollback: a failed operation can leave partial work in the scene until you undo it, and not every live handler is wrapped. Filesystem and network effects of executed code cannot be undone.

What follows from that: on the live path, code execution (`execute_python` / `execute_vex`) runs under the deliberate single-user-localhost posture — anything that can open the localhost WebSocket, presenting the key when one is set (and any process running as your user can read `~/.synapse/auth.key`), can execute code in your Houdini session. Keep the port on loopback. Deploying beyond a single seat gives every key holder code execution in that Houdini session; per-user roles and a handler-layer consent gate are tracked, not shipped.

## Vendored dependencies — patching is ours

`python/synapse/_vendor/` ships vendored copies of:

`anthropic` · `pydantic` · `pydantic_core` · `httpx` · `httpcore` · `h11` · `anyio` · `certifi` · `idna` · `jiter`

Because they are vendored, upgrading the system package does not patch SYNAPSE. A vulnerability in any of these, as shipped here, is ours to patch and release — report it through the same advisory channel, even when the bug is upstream's.

## Supported versions

The latest tagged release only. No backports.
