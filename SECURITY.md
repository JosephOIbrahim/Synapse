# Security Policy

## Reporting a vulnerability

Report privately via [GitHub security advisories](https://github.com/JosephOIbrahim/Synapse/security/advisories/new) for this repository.

Do not open a public issue for a vulnerability. Public issues are for bugs — use the bug template, which asks for your Houdini build, license tier, and `synapse_doctor` output.

## Threat model — a localhost, single-seat surface

SYNAPSE runs inside Houdini's own Python interpreter on the artist's machine. The live surface is `ws://127.0.0.1:9999/synapse`.

The loopback bind is enforced, not just documented: the transport passes `ADDRESS=127.0.0.1` to Houdini's `hwebserver` (whose own default is the any-address `0.0.0.0`), and a non-loopback listen is refused when no authentication key exists. Listening beyond loopback is an explicit opt-in — `SYNAPSE_DEPLOY_MODE` set to a studio mode, or `SYNAPSE_ALLOW_LAN=1` with `SYNAPSE_BIND_ADDRESS` — and always requires a key. A fresh Setup install mints `~/.synapse/auth.key`, so the WebSocket handshake and the `/mcp` Bearer check are on out of the box; `SYNAPSE_API_KEY` overrides the file. `synapse_doctor` reports the listen address and fails if the port accepts on a non-loopback local address in local mode.

Stated plainly, in the same words as the README:

RBAC is inactive in local mode by default. The live surface is a loopback WebSocket; origin validation is fail-safe — a connection with an unrecognized `Origin` is rejected, never waved through. The enable path for RBAC: set `SYNAPSE_DEPLOY_MODE` to a non-local mode and configure an auth key — that turns RBAC enforcement and key checking on. An API key alone (from the installer, `SYNAPSE_API_KEY`, or `~/.synapse/auth.key`) already turns authentication on for both `/synapse` and `/mcp`.

Scene mutations are undo-wrapped and reversible. Filesystem and network effects of executed code are not.

What follows from that: on the live path, code execution (`execute_python` / `execute_vex`) runs under the deliberate single-user-localhost posture — anything that can open the localhost WebSocket can execute code in your Houdini session. Keep the port on loopback. Deploying beyond a single seat means flipping the enable path above first; a handler-layer consent gate for multi-user deployment is tracked, not shipped.

## Vendored dependencies — patching is ours

`python/synapse/_vendor/` ships vendored copies of:

`anthropic` · `pydantic` · `pydantic_core` · `httpx` · `httpcore` · `h11` · `anyio` · `certifi` · `idna` · `jiter`

Because they are vendored, upgrading the system package does not patch SYNAPSE. A vulnerability in any of these, as shipped here, is ours to patch and release — report it through the same advisory channel, even when the bug is upstream's.

## Supported versions

The latest tagged release only. No backports.
