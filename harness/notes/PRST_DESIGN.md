# PRST — seam C design note: capture-current-network → fixture, addressed by phrase

**Status: PROPOSAL FOR RULING. Nothing here is built. Do not build it from this note —
it exists so the fork below is decided deliberately.**

Date 2026-08-08 · leg PRST · branch `finish/network-persistence` @ `1f18ab46`

---

## Why a design note instead of a fix

Seam C is **FAULTY by construction**, not by defect. A deterministic replay engine exists
and is oracle-pinned; nothing addresses it from a prompt, and nothing can write one from a
network the artist already has. Both gaps are missing *mechanisms*, not broken ones — so
there is no small evidenced repair to make, and the brief correctly routes this to design.

What exists today, verified this session:

| Piece | State | Anchor |
|---|---|---|
| Deterministic build engine | **EXISTS, oracle-pinned** | `python/synapse/cognitive/tools/apply_fixture.py`, `python/synapse/blocks/runtime.py` |
| Its committed oracle | baseline `762e3a85…a297`, canonicalizer **c3**, F-1..F-7 PASS with 7 negative controls | `harness/blocks/runs/m5_invariants_20260806_214024/invariants_m5.json`, `fixtures/solaris.basic.json:22-29` |
| Prompt → fixture address (M6) | **ABSENT** | grep for `phrase_table\|prompt_to_fixture\|fixture_alias` → zero product hits |
| Live network → fixture (capture) | **ABSENT** | grep for `to_fixture\|write_fixture\|capture_fixture\|fixture_from` → zero hits, anywhere |
| Fixture inventory | exactly one hand-authored file | `fixtures/solaris.basic.json` |
| `synapse_apply_fixture` registration | absent from `TOOL_DEFS` (123 tools) **and** the panel toolset (129 tools) — external-MCP stdio only | `python/synapse/mcp/mcp_server.py:855` |
| Recall payload | `{id, summary, content, date}` — prose, no nodes/wiring/parms | `python/synapse/session/tracker.py:569-574` |

> **Correction to carry forward:** `harness/legs.json:491` cites the M5 oracle as baseline
> `8bb05761` / canonicalizer `c2`. That baseline was superseded 2026-08-06 (R-M5-1) for
> being MACHINE-LOCAL. **Any M6 spec must quote `762e3a85…` / `c3`.** Reported, not corrected
> — governing docs are outside this leg's grant.

---

## THE FORK — rule this first, it changes everything downstream

These are **different products**, not different sizes of one product.

**(a) Replay the exact network the artist had.**
"Remember *this* network" in the literal sense. Requires a capture writer that does not
exist, plus structural storage memory does not currently hold. Months. Delivers the promise
as Joe stated it.

**(b) Re-run the same deterministic build.**
"That phrase means *that* committed setup." Requires only the M6 address plus an
already-committed fixture. Weeks. Delivers sameness, but only for setups a human authored
in advance — it never remembers what the artist actually made.

**A ruling on (a) vs (b) is a prerequisite for writing any M6 line**, because (b) needs no
capture writer and (a) is mostly capture writer.

---

## Proposed shape, if the ruling is (a)

Three parts, in dependency order. Each is independently rulable; none is started.

**C-1 · CAPTURE — `capture_fixture(network_path) → fixture dict`.**
The inverse of `apply_fixture`. Walks a live LOP network and emits the same schema
`fixtures/solaris.basic.json` uses. The canonicalizer (`python/synapse/blocks/canonical.py`,
`CANONICALIZER_VERSION = "c3"`) already defines what "the same network" means for the
compare direction — capture should emit exactly what c3 canonicalizes over, so a captured
fixture round-trips through `build_plan` to a stable hash. *Open question for ruling:* does
capture store absolute parm values, or the delta from node defaults? The former is
reproducible and brittle to Houdini upgrades; the latter survives upgrades and is harder to
verify.

**C-2 · ADDRESS — the M6 phrase table (HELD; this note does not implement it).**
Exact-match table first, model only on miss, zero tokens on the common path. Two constraints
this leg discovered that the M6 brief should absorb:
- `apply_fixture` validates its `fixture` argument against `^[a-z0-9][a-z0-9_.-]*$`
  (`apply_fixture.py:48`), so the phrase is never the fixture name — the table maps
  *phrase → name*, and the model never spells the phrase as an argument.
- Bare substring containment is already the recall matcher and it is brittle: 4 of 9
  realistic rephrasings of Joe's own prompt return zero, including a trailing full stop.
  M6's matcher should be ruled **with** the recall matcher, not separately — they are the
  same problem twice.

**C-3 · REGISTRATION — and this is the part that is easy to forget.**
A phrase table that resolves `"Create a Solaris Network" → solaris.basic` is still
unreachable from both Houdini panels today. **Ruling needed:** does the deterministic engine
enter the panel tool surface as
- a *model-callable tool* (the model may decline it — sameness is likely, not guaranteed), or
- a *pre-model interception* (the prompt resolves before the model is invoked — sameness is
  guaranteed, and the model never sees the turn)?

**Only the second actually delivers the reported ask.** They have opposite failure modes.

---

## The precedent worth copying (found by the crucible, not the survey)

`python/synapse/panel/hda_controller.py:113` `_select_recipe(prompt, context)` already does
this shape: it deterministically keyword-scores a free-text prompt against a committed table
(`python/synapse/routing/hda_recipes.py`, 5 recipes) with **no model call**, then emits a
payload carrying exact node types, names, parms and connections to the live handler.

It is shipped, wired, and in the panel. It is useless for Joe's flow — HDA output, no
Solaris-network recipe, never touches memory — but it means **M6's addressing pattern has a
working in-tree precedent to copy rather than a design to invent.** Read it before speccing.

---

## What this note deliberately does not propose

- **No sampling pin.** Pinning `temperature`/`seed` (nothing in
  `python/synapse/panel/providers/` pins any of them today) narrows variance without ever
  guaranteeing sameness — tool-call ordering stays unpinned and no provider promises bitwise
  reproducibility. Recorded so the option is consciously declined, not overlooked. Brief
  prohibition #3.
- **No new fixtures.** The repro's throwaway only.
- **No M6 implementation.** HELD.

---

## Open items this note hands to the human

1. **The (a)/(b) fork.** Blocks everything.
2. **C-3 registration posture** — model-callable vs pre-model interception.
3. **C-1 capture fidelity** — absolute parms vs deltas.
4. **The oracle asymmetry.** The one build path with a committed baseline is the one no
   prompt can reach; the reachable builders (`synapse_solaris_scene_template`,
   `synapse_solaris_build_graph`) have no canonical hash at all. Should a reachable builder
   acquire an oracle, or is the intent to funnel all reproducible work through the fixture
   engine and mark the free-hand builders non-reproducible *by design*? Today the tree is
   silent and the silence reads as an accident.
5. **`route_chat` is proposal-only** — `handlers.py:1665` builds `TieredRouter` with no
   `command_fn`, so every recipe/plan match on the chat panel is returned as text and never
   executed. Intended posture, or an unfinished wire? The answer changes whether M6 should
   target the router at all.

---

**Coverage limit, stated rather than papered over:** Houdini was not running this session, so
`hython harness/blocks/invariants_m5.py` could not be re-run. Every byte-identity claim about
the engine is cited from the committed 2026-08-06 artifact on build 22.0.368. A build bump is
a re-baseline event (`python/synapse/blocks/canonical.py:25`) — if the seat has moved off
22.0.368, the oracle needs re-cutting before any M6 work leans on it.
