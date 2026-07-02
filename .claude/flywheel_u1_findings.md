# U.1 wiring review — findings (severity-ranked)

Catalog: `harness/notes/verified_connectivity_21.0.671.json` (build 21.0.671, blake2b `c21357095915`)

**0 CRITICAL** of 150 call sites. By kind: dynamic-index=3, index-within-arity=113, label-claim-verified=3, unresolved-receiver=31

## INFO (150)

- `python/synapse/host/graph_builder.py:157` **unresolved-receiver** `tgt.setInput(e.target_input_index, ...)` type=None — receiver's node type not lexically resolvable (runtime object)
- `python/synapse/panel/system_prompt.py:107` **unresolved-receiver** `node.setInput(0, ...)` type=None — receiver's node type not lexically resolvable (runtime object)
- `python/synapse/panel/system_prompt.py:143` **unresolved-receiver** `new_node.setInput(0, ...)` type=None — receiver's node type not lexically resolvable (runtime object)
- `python/synapse/panel/system_prompt.py:144` **unresolved-receiver** `display_node.setInput(0, ...)` type=None — receiver's node type not lexically resolvable (runtime object)
- `python/synapse/routing/planner.py:287` **index-within-arity** `solver.setInput(0, ...)` type=vellumsolver — input index 0 within max_inputs for 'vellumsolver'
- `python/synapse/routing/planner.py:288` **index-within-arity** `solver.setInput(1, ...)` type=vellumsolver — input index 1 within max_inputs for 'vellumsolver'
- `python/synapse/routing/planner.py:300` **index-within-arity** `drape.setInput(0, ...)` type=vellumdrape — input index 0 within max_inputs for 'vellumdrape'
- `python/synapse/routing/planner.py:314` **index-within-arity** `solver.setInput(2, ...)` type=vellumsolver — input index 2 within max_inputs for 'vellumsolver'
- `python/synapse/routing/planner.py:328` **index-within-arity** `wind.setInput(0, ...)` type=vellumconstraintproperty — input index 0 within max_inputs for 'vellumconstraintproperty'
- `python/synapse/routing/planner.py:341` **index-within-arity** `cache.setInput(0, ...)` type=filecache — input index 0 within max_inputs for 'filecache'
- `python/synapse/routing/planner.py:368` **index-within-arity** `asm.setInput(0, ...)` type=assemble — input index 0 within max_inputs for 'assemble'
- `python/synapse/routing/planner.py:370` **index-within-arity** `cons.setInput(0, ...)` type=rbdconstraintsfromrules — input index 0 within max_inputs for 'rbdconstraintsfromrules'
- `python/synapse/routing/planner.py:374` **index-within-arity** `props.setInput(0, ...)` type=rbdconstraintproperties — input index 0 within max_inputs for 'rbdconstraintproperties'
- `python/synapse/routing/planner.py:376` **index-within-arity** `solver.setInput(0, ...)` type=rbdbulletsolver — input index 0 within max_inputs for 'rbdbulletsolver'
- `python/synapse/routing/planner.py:377` **index-within-arity** `solver.setInput(1, ...)` type=rbdbulletsolver — input index 1 within max_inputs for 'rbdbulletsolver'
- `python/synapse/routing/planner.py:391` **index-within-arity** `debris.setInput(0, ...)` type=debrissource — input index 0 within max_inputs for 'debrissource'
- `python/synapse/routing/planner.py:404` **index-within-arity** `pyro.setInput(0, ...)` type=pyrosolver — input index 0 within max_inputs for 'pyrosolver'
- `python/synapse/routing/planner.py:417` **index-within-arity** `cache.setInput(0, ...)` type=filecache — input index 0 within max_inputs for 'filecache'
- `python/synapse/routing/planner.py:540` **index-within-arity** `evl.setInput(0, ...)` type=oceanevaluate — input index 0 within max_inputs for 'oceanevaluate'
- `python/synapse/routing/planner.py:556` **index-within-arity** `solver.setInput(0, ...)` type=flipsolver — input index 0 within max_inputs for 'flipsolver'
- `python/synapse/routing/planner.py:568` **index-within-arity** `ww_solve.setInput(0, ...)` type=whitewatersolver — input index 0 within max_inputs for 'whitewatersolver'
- `python/synapse/routing/planner.py:570` **index-within-arity** `ww_src.setInput(0, ...)` type=whitewatersource — input index 0 within max_inputs for 'whitewatersource'
- `python/synapse/routing/planner.py:597` **index-within-arity** `wrangle.setInput(0, ...)` type=attribwrangle — input index 0 within max_inputs for 'attribwrangle'
- `python/synapse/routing/planner.py:600` **index-within-arity** `rast.setInput(0, ...)` type=volumerasterizeattributes — input index 0 within max_inputs for 'volumerasterizeattributes'
- `python/synapse/routing/planner.py:603` **index-within-arity** `solver.setInput(0, ...)` type=pyrosolver — input index 0 within max_inputs for 'pyrosolver'
- `python/synapse/routing/planner.py:606` **index-within-arity** `cache.setInput(0, ...)` type=filecache — input index 0 within max_inputs for 'filecache'
- `python/synapse/routing/planner.py:652` **index-within-arity** `matlib.setInput(0, ...)` type=materiallibrary — input index 0 within max_inputs for 'materiallibrary'
- `python/synapse/routing/planner.py:655` **index-within-arity** `assign.setInput(0, ...)` type=assignmaterial — input index 0 within max_inputs for 'assignmaterial'
- `python/synapse/routing/planner.py:664` **index-within-arity** `cam.setInput(0, ...)` type=camera — input index 0 within max_inputs for 'camera'
- `python/synapse/routing/planner.py:673` **index-within-arity** `key.setInput(0, ...)` type=light — input index 0 within max_inputs for 'light'
- `python/synapse/routing/planner.py:676` **index-within-arity** `fill.setInput(0, ...)` type=light — input index 0 within max_inputs for 'light'
- `python/synapse/routing/planner.py:679` **index-within-arity** `rim.setInput(0, ...)` type=light — input index 0 within max_inputs for 'light'
- `python/synapse/routing/planner.py:687` **index-within-arity** `light.setInput(0, ...)` type=light — input index 0 within max_inputs for 'light'
- `python/synapse/routing/planner.py:696` **index-within-arity** `rs.setInput(0, ...)` type=karmarenderproperties — input index 0 within max_inputs for 'karmarenderproperties'
- `python/synapse/routing/planner.py:699` **index-within-arity** `karma.setInput(0, ...)` type=karma — input index 0 within max_inputs for 'karma'
- `python/synapse/routing/planner.py:707` **index-within-arity** `out.setInput(0, ...)` type=null — input index 0 within max_inputs for 'null'
- `python/synapse/routing/recipes/fx_recipes.py:84` **label-claim-verified** `solver.setInput(0, ...)` type=vellumsolver — comment label claim matches catalog label at index 0
- `python/synapse/routing/recipes/fx_recipes.py:86` **label-claim-verified** `solver.setInput(1, ...)` type=vellumsolver — comment label claim matches catalog label at index 1
- `python/synapse/routing/recipes/fx_recipes.py:90` **index-within-arity** `cache.setInput(0, ...)` type=filecache — input index 0 within max_inputs for 'filecache'
- `python/synapse/routing/recipes/fx_recipes.py:133` **index-within-arity** `asm.setInput(0, ...)` type=assemble — input index 0 within max_inputs for 'assemble'
- ... and 110 more (see JSON)
