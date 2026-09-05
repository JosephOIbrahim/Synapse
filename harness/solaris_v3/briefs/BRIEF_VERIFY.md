# BRIEF — VERIFY stream (C4 predicates P1–P6)

You are the VERIFY worker in a six-agent swarm implementing `docs/SOLARIS_RECIPES_H22_BLUEPRINT_V3.md`. Read, in order: `docs/solaris_v3/SWARM_CONTRACT.md`, `python/synapse/recipes/contracts.py`, then blueprint pages 08, 05, 13 (S6, S7). Your worktree is the current working directory; branch `bp5/solaris-verify`. Work only inside your exclusive write set.

## Principle
A graph is not its output. Nodes/wires, composed USD, and rendered pixels answer different questions; each needs its own evidence. Verifiers are independent of writers: they read the scene, they never mutate it. No required predicate is ever skipped into a green result — unreachable host = `CheckStatus.NOT_RUN` or `UNKNOWN` with a reason.

## Deliverables

1. **`python/synapse/recipes/verify.py`** — one class per check implementing `contracts.Verifier`, each returning `CheckResult` with evidence dicts that a receipt can store verbatim:
   - **P1 Graph** — owned IDs/types/parents, nested shader nodes, ports, flags, bound parameter values vs the `RecipeSpec` + `RecipeInstance.owned_node_ids`. Reuse `blocks.runtime.observe` where it fits (read-only).
   - **P2 USD** — live stage; expected prims active/defined; schema/type; material resolution and intended bindings (`UsdShade.MaterialBindingAPI` compute-bound material equals intended).
   - **P3 Render readiness** — resolve the **intended** `RenderSettings` prim explicitly (path from spec), never "whichever is first"; camera via `UsdRender.Settings.GetCameraRel()` (relationship, not `winning_layer()`); valid `UsdGeom.Camera`; products/vars/output authored; **two authored lights**; explicit render-input branch present (B-7 lesson: camera binding alone cannot pass).
   - **P4 Composition** — composition errors + relevant node errors; missing assets / payload load state reported separately.
   - **P5 Image smoke** — terminal job state, **fresh output file identity** (new inode/mtime/size + content digest ≠ any prior artifact recorded in context), expected dimensions/channels, readable finite RGB, expected visible content via a reference-derived region/coverage criterion with documented tolerances. Non-black alone is not a pass. Start qualification at 64×64 / 1 sample. Read EXR via whatever the repo already uses (search `tests/` and `python/` for an EXR reader before adding a dependency).
   - **P6 Locality/recovery** — allowed field delta only (diff of semantic digests restricted to the action's slot bindings), unrelated artist state preserved, measured rollback residue when a recovery happened.
2. **`python/synapse/server/solaris_compose_tools.py`** — extend `_assess_stage` / `assess_render_ready` (do not duplicate them): explicit RenderSettings resolution by path argument, `GetCameraRel()` relationship read, two-light count, render-input-branch check. Existing callers and `tests/test_solaris_compose_tools.py` stay green; add tests there for the new keys only.
3. **Tests** — `tests/test_recipe_verify*.py` pure-Python: each predicate against small fake observations (dicts / lightweight stubs you construct in the test, **not** a planted `hou`). Negative controls: T7 (render-input branch removed → P3 FAIL even though camera relationship is valid), T8 (old EXR or wrong-scene image → P5 FAIL on fresh-file identity and on content criterion, separately), T9 (stage unavailable → P2/P3 UNKNOWN, no success fallback, diagnosis retained). Hython-only tests live in a clearly named file and `pytest.skip` with reason when `hou` is not resident; they must exercise the real path when it is.
4. **`docs/solaris_v3/VERIFY_TOLERANCES.md`** — the documented tolerances and the region/coverage criterion, stated as candidates to be measured on the pinned scene, not guarantees.

## Notes
- The prior BP4 CRUX receipt `harness/notes/receipts/BP4-CRUX.json` records the B-7 cause; treat it as evidence from that case, not a universal explanation.
- Status lines to `harness/solaris_v3/STATUS_VERIFY.md`; final report `docs/solaris_v3/REPORT_VERIFY.md`.
