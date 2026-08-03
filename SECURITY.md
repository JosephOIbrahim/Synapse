# Security Policy

## Reporting a vulnerability

Report privately via [GitHub security advisories](https://github.com/JosephOIbrahim/Synapse/security/advisories/new) for this repository.

Do not open a public issue for a vulnerability. Public issues are for bugs — use the bug template, which asks for your Houdini build, license tier, and `synapse_doctor` output.

## Threat model — a localhost, single-seat surface

SYNAPSE runs inside Houdini's own Python interpreter on the artist's machine. The live surface is `ws://localhost:9999/synapse`.

Stated plainly, in the same words as the README:

RBAC is inactive in local mode by default. The live surface is a localhost WebSocket; origin validation is fail-safe — a connection with an unrecognized `Origin` is rejected, never waved through. No auth key is required or checked unless one is configured. The enable path: set `SYNAPSE_DEPLOY_MODE` to a non-local mode and configure an auth key — that turns RBAC enforcement and key checking on.

Scene mutations are undo-wrapped and reversible. Filesystem and network effects of executed code are not.

What follows from that: on the live path, code execution (`execute_python` / `execute_vex`) runs under the deliberate single-user-localhost posture — anything that can open the localhost WebSocket can execute code in your Houdini session. Keep the port on loopback. Deploying beyond a single seat means flipping the enable path above first; a handler-layer consent gate for multi-user deployment is tracked, not shipped.

## Vendored dependencies — patching is ours

`python/synapse/_vendor/` ships vendored copies of:

`anthropic` · `pydantic` · `pydantic_core` · `httpx` · `httpcore` · `h11` · `anyio` · `certifi` · `idna` · `jiter`

Because they are vendored, upgrading the system package does not patch SYNAPSE. A vulnerability in any of these, as shipped here, is ours to patch and release — report it through the same advisory channel, even when the bug is upstream's.

## Supported versions

The latest tagged release only. No backports.
