# BATON — SOLARIS REPAIR 01

**Worktree** `.claude/worktrees/solaris-repair` · **Branch** `feat/solaris-repair-01`
**Governed by** `harness/AGENT_CONSTITUTION.md` — read it first, it binds you.
**Ruled by** `harness/notes/CTO_RULINGS_01.md` Rulings 12–16. These are decided. Do not re-open
them; execute them.
**Evidence** `harness/notes/l2_wiring_findings.md` — F1–F11, every one anchored.

You are running **in parallel** with CTO-RELAY-01, which owns `feat/cto-relay-01`. Stay in this
worktree. Do not touch the panel, the harness legs, or the other branch.

---

## The finding you are repairing

Five Solaris tools live in `synapse/mcp/tools/solaris/` — outside the installable
`python/synapse/` package — and none are registered in `_tool_registry.py`. Their tests sit
outside `testpaths` and drive a `MagicMock` `hou`. **Nothing can call them and nothing was
checking them.** That is why `import_megascans` raises `PermissionError` on every invocation and
`set_purpose` reports success having set nothing.

Roots before symptoms. In this order, no reordering.

---

## M1 · One tree

Move `synapse/mcp/tools/solaris/` → `python/synapse/mcp/tools/solaris/`. Register all five in
`python/synapse/mcp/_tool_registry.py`.

**Exclude `tool_audit`** — F2 established it is a Phase-2 design document, not a tool. It has no
`validate/plan/execute` and no implementation module. Move it to `docs/` or leave it; do not
register it.

**Oracle:** all five resolve through the registry; `pytest -q` green; suite count holds or rises.

## M2 · Collect the tests

Fix `pyproject.toml:102` `testpaths` so `synapse/tests/solaris/` is collected at its new home.

**Oracle:** the five test files appear in `pytest --collect-only` output. They will fail. Good —
that is the first honest signal this family has ever produced.

## M3 · Delete the MagicMock `hou` fixture — the load-bearing move

`synapse/tests/solaris/conftest.py` mocks `hou`. Per Constitution Law 1, mock-`hou` tests are
banned for host-behaviour assertions: they cannot fail when reality disagrees, which is exactly
how F7 and F9 survived.

Replace with hython-gated live tests that **skip** without Houdini. A skip is honest; a pass is a
lie. Use `harness/notes/l2_live_verify.py` as the pattern — it already drives real hython.

**Oracle:** zero `MagicMock` references remain in `synapse/tests/solaris/`. Tests skip cleanly
with no Houdini, and execute against 22.0.368 when present.

## M4 · Repair, in this order

Only now. Each fix ships with a test that **fails before and passes after** — demonstrate both.

1. **F9 CRITICAL** `import_megascans.py:172` — `createNode` targets a locked `componentgeometry`
   HDA. Retarget to the interior `sopnet/geo` subnet, which L2 live-probed as writable.
   **Do not unlock the asset.** Reproducer: `harness/notes/l2_mega_trace.py`.
2. **F3 HIGH** `import_megascans.py:240-255` — `mtl_ref_<asset>` is created, parms set, never
   wired. `componentmaterial` input 1 is left open. Wire it.
3. **F4 HIGH** `create_variants.py:152-169` — duplicated variant materials never receive
   `setInput`. `hou.copyNodesTo` does not carry connections outside the copied set.
4. **F5 HIGH** `create_variants.py:186-195` — `componentgeometryvariants` never reaches the
   terminal; the component presents two terminal LOPs live. Wire it downstream.
5. **F6 MED** `create_variants.py:193-203` — bare `except Exception: pass` then
   `status="created"`. **Constitution Law 3:** status describes what happened. Return `noop` or
   raise.
6. **F7 HIGH** `set_purpose.py:129-156` — there is no `purpose` parm on `componentgeometry`.
   `purpose` is a USD attribute (`UsdGeomImageable`). **Probe the real mechanism live before
   writing against it.** Substituting an assumed API for a refuted one is how a decay clock
   becomes a phantom.
7. **F8 LOW** — converge on `parent_path`. `scene_template.py:167` changes. Unknown parameter
   keys raise; they do not silently default to `/stage`.
8. **F10 MED** `component_builder.py:227` — `componentbuilder` is not among the 218 live LOP
   types. The `subnet` fallback at `:244` masks it. Log the phantom explicitly; keep the
   fallback.

## M5 · Registration order

`import_megascans` registers **last**, after F9 and F3 are both proven by a live verifier
(Ruling 13). The other four may register ahead of it. One broken tool does not hold the family.

---

## Standing

- **Commandment 7.** Test count strictly increases or holds. Fix forward. Never weaken a test.
- **Probes beat memory.** Confirm every `hou.*` symbol by live `dir()` on 22.0.368 first.
- **Never push, never merge, never open a PR.** Gate C is Joe's.
- **Do not edit** the constitution, the rulings, `harness/state/**`, or the settings files.
- The Phase-2 claim that five Solaris tools were delivered stays struck until M1–M3 land.

**Receipt** `harness/notes/receipts/SR1.json`, `receipt/v1` schema. Batch every decision into
`for_ruling[]`. Do not ask Joe anything until the receipt.

---

# RESUME — SR1 after crash, 2026-07-25 13:00

**What survived.** `97b879d fix(solaris): M1+M2 one tree - relocate + register 4 of 5, collect tests`.
M1 and M2 are DONE. `import_megascans` correctly held back per Ruling 13. Tests now collect.

**What killed it.** A machine-level crash took the relay, this team, both watchers, and Houdini
(pid 61208) simultaneously at ~12:50. Not a leg failure. Nothing in the repair is suspect.

**Houdini is DOWN.** This changes scope, and the change is not negotiable:

## Resume at M3 ONLY. Do not attempt M4.

**M3 — delete the MagicMock `hou` fixture.** This is the load-bearing move and it does **not**
need a live Houdini:

1. Remove every `MagicMock` `hou` from the relocated `synapse/tests/solaris/` conftest.
2. Replace with hython-gated tests that **skip** when Houdini is absent. Use
   `harness/notes/l2_live_verify.py` as the pattern.
3. With Houdini down, those tests MUST report **skip**. A skip is honest. A pass would prove the
   mock is still in the loop somewhere, and that is the exact defect being removed.

**Oracle:** zero `MagicMock` references remain under the relocated solaris tests; `pytest -q`
shows the new tests as skipped, not passed, not failed; suite count holds or rises.

## M4 is BLOCKED until Houdini returns — by ruling, not by preference

Every M4 repair needs live confirmation:
- **F9** retarget to `sopnet/geo` — must be proven against a live locked HDA.
- **F7** `purpose` is a `UsdGeomImageable` attribute, not a parm — **probe the real mechanism
  live before writing against it.** Constitution Law 5. Substituting an assumed API for a
  refuted one is how a decay clock becomes a phantom, and that is precisely the trap here.
- **F3/F4/F5** wiring fixes — provable only by a composed stage with a prim count.

Writing these blind and marking them green would produce exactly the class of defect this whole
repair exists to remove. **Do not.** Deposit each as ready-to-execute with its probe named.

## Write SR1.json when M3 lands

`receipt/v1`. Status is `amber` at best — M4 is deferred, and the receipt must say so plainly in
`resume_token`. Do not report the family as repaired. M1–M3 make it *reachable and honestly
tested*; the defects are still there and still deposited.

## Standing

Commandment 7. Probes beat memory. Never push, never merge, never open a PR — Gate C is Joe's.
Stay in this worktree; the main branch belongs to CTO-RELAY-01.
