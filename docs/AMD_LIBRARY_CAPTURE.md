# Follow-up: capture the exact AMD material library token

**Status:** blocked on a live Houdini session with the AMD library loaded.
**Depends on:** #23 (adds the probe + the materiallinker mechanism doc).

## Why this is a separate PR

The AMD material library is reached through the `materiallinker` LOP, not a
filesystem sublayer. A headless probe (`scripts/probe_materiallinker_amd.py`,
hython 21.0.671) proved the structure but **could not extract the AMD token**,
because the relevant menu is dynamically populated and is empty on a stage with
no library loaded. So the last datum needs a live session — exactly the case Joe
flagged ("honestly tricky to find because it's a dropdown from materiallinker").

## What is already known (captured in #23)

`materiallinker` is a multiparm node:

- **Files multiparm** (`num_files`): `filepath_N` loads the USD / material
  library file; `createprims_N` = Edit Existing / Create New; `primpath_N`.
- **Links multiparm** (`num_links`): `link_prim_N` / `link_id_N` is the
  **dropdown** that binds a material; `link_type_N` = Direct Binding /
  Collection Binding.

The AMD materials appear as options in the `link_prim` dropdown **once the AMD
library is loaded via `filepath_N`**.

## What is still needed

1. The absolute path (or `$VAR`-relative path) of the AMD library file that goes
   in `filepath_N`.
2. The exact `link_prim_N` / `link_id_N` menu token(s) for the AMD materials.
3. Whether the library is Direct vs Collection bound by default (`link_type_N`).

## How to finish it

In a live session with the AMD library available:

1. Drop a `materiallinker`, set `filepath_1` to the AMD library, add a link.
2. Re-run `scripts/probe_materiallinker_amd.py` (it sets `num_files`/`num_links`
   to 1 and dumps inner parms + menus) — the `link_prim`/`link_id` menu will now
   list the AMD entries.
3. Record path + token + bind type in
   `rag/skills/houdini21-reference/pipeline_preferences.md` (replace the
   "Still pending" note), and re-run `python -m synapse.memory.seed_corpus --force`
   so the Moneta pointer picks up the concrete values.

## Acceptance

- `pipeline_preferences.md` AMD section has the concrete path + token.
- `synapse_knowledge_lookup("amd material library")` returns it.
- Moneta re-seeded so `synapse_recall("amd library")` surfaces it.
