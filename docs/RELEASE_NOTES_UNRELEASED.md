# Release notes — UNRELEASED

**Status:** not tagged, not released, not merged. **Gate C is the human's.**
**Branch:** `feat/cto-relay-01` · **Head:** `1d3ac69` · **Written:** 2026-07-25

> This file exists so that the things known to be broken are written down *before* a
> tag, not discovered after one. Two rulings (R17 unreachable emergency halt, R18/R2
> consent gates that do not gate) are **open**. A version tag would certify them as
> shipped. Do not tag on this state.

---

## What changed

**Documentation and claim accuracy only. No product code changed on this branch.**

The CTO-RELAY-01 run put five legs over the codebase and the two findings that mattered
were about **claims, not code**. This branch corrects the claims.

### Corrected — the reversibility guarantee

`hou.undos.group` is a **grouping primitive, not a transaction.**

It groups undo entries so that one **Ctrl+Z** reverses a completed operation. It does
**not** roll back when the wrapped block raises. The previously stated guarantee — *"every
mutation is reversible"* — was overstated as written.

On the exception path a handler can leave a partial network on the graph while the
`IntegrityBlock` still reports `undo_group_active=True` at fidelity 1.0.

**One path is genuinely better and is now named as the exception rather than the rule:**
`python/synapse/host/graph_builder.py:165-181` carries explicit unwind bookkeeping — on a
mid-build failure it destroys the nodes it created and returns a structured `FAILED` with
zero net mutation. Generalising that to the handler paths is open work.

*Corrected in:* `CLAUDE.md` (commit `1aa2661`), `README.md` (commit `1d3ac69`).

### Corrected — the suite count now carries its scope

**4744 passed · 100 skipped · 0 failed.**

*Producer:* `python -m pytest tests -q -p no:cacheprovider --basetemp=<tmp>` on
`feat/cto-relay-01` @ `9b796a4`, **system Python 3.14.2**, 2026-07-25, 111.69 s.

That is a statement about the **development** environment and has never been a statement
about the shipping one. It may not be cited as a shipping-environment claim.

### Corrected — "five swappable engines"

`python/synapse/panel/providers/` is **1,510 LOC** *(producer:
`find python/synapse/panel/providers -name "*.py" | xargs wc -l`)* with all five engines
implemented. Only **Claude** works on a key alone; the other four require their own
configuration. The claim was true and misleading at the same time. The claim was fixed;
the code was not touched (Ruling 23 — the code waits for T.1).

### Added — a "Known limitations" section on the public README

Undo scope · suite scope · engines · absent emergency halt · unvendored dependencies ·
COP grounding. Each item carries a producer path.

### Added — a two-roads diagram

`/mcp` (bridge-routed, audited, full anchor set) versus `/synapse` (direct handlers,
RBAC-gated) with the partial-undo drift drawn on the live path.

---

## Known broken — stated plainly, not omitted

### The suite does not complete on the interpreter artists run

Under `hython3.13` — Houdini's own shipping Python — the suite dies with a **Windows
access violation** in `PySide6.QtWidgets.QApplication.font()` at
`tests/panel/test_font_scale.py:65`.

**VERIFIED-RUNTIME this session.** The cause is **Qt, not the vendored tree** — there are
zero `_vendor` frames in the fault. The trigger is **fake-Qt residency**:
`tests/test_hda_panel.py:172-175` plants `sys.modules["PySide6"]` stubs at module level,
resident before any panel test runs. Run in isolation, `tests/panel/` passes 27/29 with no
crash.

*Trace:* `harness/notes/GATE_01B_TRACE.md`, committed at `aa04be5` on
`feat/solaris-repair-01`.

**Do not "fix" this by skipping the panel tests.** That converts a real defect into a
silent one.

### Emergency halt has no artist-reachable surface

`CLAUDE.md` Safety Rule 11 states halt is immediate. The implementation exists only in
`chat_panel.py`, a tree whose loader is never installed. The shipped panel —
`python/synapse/panel/synapse_panel.py` — has **no halt control**.

*Producer:* `grep -n "HALT\|emergency_halt" python/synapse/panel/synapse_panel.py` → no
matches.

**Ruling 17 is open.** A stated safety rule with no implementation on the shipped surface.

### Three panel surfaces report consent decisions they did not make

`COMMIT-TO-/STAGE` announces consent-gate routing that never happens — it sets a UI
substate. Gate Approve and Gate Reject call `mark_decided()` and emit `decision_announced`
**unconditionally**, after an `except` that only logs. If `HumanGate` is absent or
`decide()` raises, the artist sees a decision that never reached the gate.

*Anchors:* `python/synapse/panel/gate_widget.py:490`, `:509`;
`python/synapse/panel/synapse_panel.py:1180`.

**Rulings 18 / R2 are open.** This is on the exact surface whose purpose is receipts.

### `websockets` and `mcp` are required but not vendored

Neither is present in `python/synapse/_vendor/` *(producer: `ls python/synapse/_vendor/`)*.
Both are pip-installed into the development Python and exist nowhere in the shipping
environment. Three test modules cannot collect under `hython3.13` for this reason.

### Copernicus grounding is at 6.2%

6.2% of 384 live `Cop` types, 13.6% of 169 legacy `Cop2` types, **zero semantic grounding
for either**. `hou.CopNode` and `hou.Cop2Node` are different data models, not two versions
of one API. Any COP tool whose contract is *"read pixels / enumerate planes / save an
image"* has no Copernicus destination. All COP work is held behind one probe.

### Five Solaris tools are unreachable

None appear in the MCP registry. Their tests live outside the collected `testpaths` and
drive a `MagicMock` `hou`, so they cannot disagree with reality. A relocation exists on
`feat/solaris-repair-01` — **not on this branch** — and `import_megascans` is held back
absolutely under Ruling 13.

### A main-thread render still holds the UI

Both the panel path and `/mcp` render inline on the main thread. Cancel does not interrupt
an operation already running: the WebSocket loop reads messages one at a time, so a
`cancel` queues behind the very handler it targets. Out-of-band only.

### The live WS bridge advertises a service it does not provide

`~/.synapse/bridge.json` reads fresh and the port is open, but 9 of 9 WebSocket upgrades
return HTTP 400 and 4 of 4 plain HTTP paths return 404. The SessionStart hook reported
"bridge connected" from the sidecar file without pinging.

---

## What this branch did NOT do

Stated so nothing is assumed finished:

- **Fixed zero Solaris source bugs** — the gate condition was evidence-only.
- **Closed zero LOP/COP gaps** — gate-refused at C.0. The census is the deliverable.
- **Produced no screenshots**, verified nothing rendering — `hython` was permission-denied
  throughout the panel legs.
- **Created no version tag, opened no PR, merged nothing.**

---

## Before this can be tagged

1. **R2 / Ruling 18** — make the two gate emits conditional on the gate call succeeding.
   Three lines. It is the difference between a consent gate and consent theatre.
2. **R10 / Ruling 17** — restore a persistent halt affordance to the shipped panel.
3. **R27** — probe the `hython3.13` segfault to a recorded cause, then decide honestly
   whether the transport tests are declared system-Python-only.

Until 1 and 2 land, a tag would certify open safety rulings as shipped.
