# Gate 0.1 — Brain survival on Houdini 22: sidecar vs abi3 (DECISION BRIEF)

> Status: **evidence + recommendation for the human.** The harness does NOT commit this — you do.
> Grounded in a read-only sweep of the real code (2026-06-24). Speculation is flagged inline.

## TL;DR
- The "brain" (Claude Agent SDK loop) runs **in-process** today: a daemon **thread** inside Houdini, boot-gated on `hou.isUIAvailable()`, marshaling tool calls to the main thread. It is **not** a sidecar. (`python/synapse/host/daemon.py`, `__init__.py:51-57`)
- **abi3 is not actually an available option.** Only **two** vendored deps carry native binaries — `pydantic_core` 2.46.3 (5 MB) and `jiter` 0.14.0 (445 KB), both Rust/PyO3 — and both ship **`cp311-cp311-win_amd64`** wheels, **not abi3** (`_vendor/.../WHEEL:4`). Everything else vendored is pure-Python. Going abi3 means **forking + maintaining custom abi3 builds** of those two (upstream doesn't publish them). High effort, low payoff.
- So the real fork in the road is **Sidecar (decouple)** vs **Status-quo in-process + re-vendor-on-drop**.
- **Recommendation: Sidecar** *if* you want drop-day to be truly "verification, not surgery" and you'll fund a small one-time build. **Otherwise** status-quo is cheaper now and the drop-day "surgery" is small (re-vendor 2 wheels) — *provided* H22's Python has prebuilt `pydantic_core`/`jiter` wheels (it will, if H22 ships a mainstream CPython).

## What the brain actually is (why this is tractable)
- `python/synapse/cognitive/agent_loop.py` has **zero `hou` imports** — the brain is pure Python + the Anthropic SDK. Only the **host** (`daemon.py`, `main_thread_executor.py`) touches `hou`. *That clean seam is what makes a sidecar feasible at all.*
- The ABI lock is tiny: 2 Rust extensions. The other ~13 vendored packages (anthropic 0.96.0, httpx, anyio, pydantic-pure, …) are pure-Python and ABI-agnostic.
- Transports a sidecar could reuse already exist: WebSocket (`server/websocket.py`), `hwebserver_adapter`, MCP JSON-RPC (`mcp/server.py`), and endpoint discovery (`server/bridge_endpoint.py`).
- The harness check is **transport-agnostic** (`check_brain_answers` verifies `get_bridge()._synapse`, not the mechanism) — **either choice keeps the harness valid.**

## The three options

| | **Sidecar** (brain in its own pinned cp311) | **abi3** (single stable-ABI wheel) | **Status quo** (in-process + re-vendor on drop) |
|---|---|---|---|
| H22-day work | **~zero** — brain runs on its own interpreter regardless of H22's Python | n/a until upstream ships abi3 | re-vendor 2 wheels for H22's cpXX, widen the `__init__.py` gate, re-run tests |
| Availability | buildable now (clean seam exists) | **blocked** — `pydantic_core`/`jiter` don't ship abi3; needs a fork | available now |
| Net-new code | **yes** — process lifecycle, IPC, re-home the fork-bomb guard | fork + maintain abi3 builds | none |
| Fork-bomb guard (`hou.isUIAvailable`) | must be re-homed to the host (sidecar has no `hou`) | unchanged (in-proc) | unchanged (in-proc) |
| IPC latency | +~50-100 ms/call *(SPECULATION — unmeasured)* | none | none |
| Risk profile | front-loaded (build it once, then immune) | upstream-dependent, uncertain | deferred to drop-day, small but nonzero |

**Things NONE of them remove** (verified): the `hou.isUIAvailable()` boot gate (fork-bomb guard), the Windows `WindowsSelectorEventLoopPolicy` workaround (`daemon.py:355-367`), and the `PYTHONNOUSERSITE` guard. These are Houdini/Windows realities, not ABI choices.

## The H22 unknown (the hinge)
SideFX has **not announced H22's Python version** (SPECULATION-free statement: it's absent from the repo and unreleased). H20.5/21.0/21.5 all ship **3.11**.
- **If H22 stays on 3.11:** the current in-process build survives **unchanged** — no work at all. This is a real possibility and argues for not over-investing now.
- **If H22 moves to 3.12+:** status-quo needs a re-vendor (small, *if* upstream wheels exist for the new cpXX — they will for any mainstream CPython); sidecar is immune.

## Recommendation
1. **Drop abi3 from consideration** unless upstream `pydantic_core`/`jiter` start shipping abi3 wheels — verify on drop day, don't fork for it now.
2. **Default to Sidecar** as the *target* (it's what makes the mission's "verification not surgery" literally true, and the agent_loop seam is already clean) — **but stage it, don't commit blind:** build a minimal sidecar skeleton (reuse `bridge_endpoint` + WebSocket; re-home the `hou.isUIAvailable` guard to the host launcher) and prove `check_brain_answers` green through it on H21 *before* H22.
3. **Acceptable cheaper path:** stay in-process and treat drop-day re-vendor as the plan — only valid if you accept a (small) drop-day task and H22 ships a CPython with prebuilt wheels for the 2 native deps.
- Either way the harness is ready: `check_brain_answers` validates the property, not the mechanism.

## Drop-day checklist (works for either architecture)
1. Install H22 clean; `hython -c "import sys; from pxr import Usd; import PySide6.QtCore as q; print(sys.version_info, Usd.GetVersion(), q.__version__)"` → read **Python · USD · PySide**.
2. Write `harness/state/drop.json` with those three numbers (+ houdini build). *(This is the Mode-B human trigger.)*
3. Regenerate the symbol table inside H22: `hython host/introspect_runtime.py` → `h22_symbol_table.json`.
4. Does the brain wake under H22? Run `check_brain_answers` (sidecar: through IPC; in-proc: after re-vendoring the 2 wheels for H22's cpXX + widening the `__init__.py:51` gate).
5. Fire the probe → API delta: `hython scripts/run_apex_verify.py` and diff vs the H21 baseline. Patch per delta (probe truth > pinned constants).

## Open questions (only you / the H22 drop can resolve)
- H22's actual Python/USD/PySide versions (the hinge above).
- Do upstream `pydantic_core`/`jiter` publish abi3 wheels by H22? (re-check on drop)
- If sidecar: IPC transport choice (reuse WebSocket+`bridge_endpoint` is the path of least resistance) and where the fork-bomb guard re-homes.
- Real IPC latency for a sidecar (unmeasured — build the skeleton and measure before committing).

_Evidence base: `daemon.py`, `host/main_thread_executor.py`, `cognitive/agent_loop.py`, `__init__.py:20-57`, `_vendor/{pydantic_core,jiter}/*.pyd` + `*-dist-info/WHEEL`, `_vendor/README.md`, `tests/test_vendored_deps.py`, `server/{websocket,hwebserver_adapter,bridge_endpoint,freeze_chain}.py`, `mcp/server.py`, `harness/verify/checks.py`._

## Evidence appended 2026-07-01 — the IPC-latency spike (the open number, now measured)

`harness/notes/gate01_ipc_latency.py` — cross-process localhost WebSocket echo
(same `websockets` lib as the transport), JSON-enveloped, 200 rounds/size,
Python 3.14.2, this workstation:

| payload | p50 | p95 | p99 |
|---|---|---|---|
| 256 B (tool call) | 0.102 ms | 0.192 ms | 0.375 ms |
| 4 KB (tool result) | 0.119 ms | 0.233 ms | 0.296 ms |
| 64 KB (fat observation) | 0.319 ms | 0.509 ms | 1.004 ms |

**Reading:** sidecar IPC is ~4 orders of magnitude under the latency floor that
actually governs turns (LLM inference + the ~2 s Houdini cook floor per the
latency-refactor findings). Latency is NOT a discriminator between the two
arms. The remaining trade is purely engineering: sidecar = a skeleton +
process-lifecycle work, buys permanent immunity to Houdini's Python bumps;
in-process re-vendor = near-zero work now (wheels for cp312 AND cp313 are
pre-cached at `harness/state/wheel_cache/`, runbook at
`docs/studio/UPGRADE.md` Step 2a), repeats on every future bump.

**Recommendation with evidence in hand:** if H22 ships cp311 → no-op, defer
sidecar to the post-release backlog. If H22 moved Python → re-vendor on drop
day (cheap, pre-cached), and schedule the sidecar as the durable fix in the
first post-release cycle rather than inside the drop window.

## DECISION — 2026-07-10 (human sanction)

**Sidecar.** Chosen by the owner with the IPC evidence in hand (p50 ~0.1 ms
— latency a non-discriminator; the trade was purely engineering). Per this
brief's own window guidance: the sidecar is the durable architecture, built
in the **first post-release cycle**, not inside the drop window. Drop-day
contingency stays UPGRADE.md Step 2a (re-vendor from the pre-cached
cp312/cp313 wheels at `harness/state/wheel_cache/`) if H22 ships a
non-cp311 Python; if H22 is cp311 the drop is a no-op either way.
