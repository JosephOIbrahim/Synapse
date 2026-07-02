# U.1 wiring review — findings (severity-ranked)

Catalog: `harness/notes/verified_connectivity_21.0.671.json` (build 21.0.671, blake2b `c21357095915`)

**0 CRITICAL** of 147 call sites. By kind: dynamic-index=3, index-within-arity=108, label-claim-verified=3, unresolved-receiver=33

## INFO (147)

- `python/synapse/core/wiring.py:163` **unresolved-receiver** `node.setInput(index, ...)` type=None — receiver's node type not lexically resolvable (runtime object)
- `python/synapse/core/wiring.py:166` **unresolved-receiver** `node.setInput(resolved, ...)` type=None — receiver's node type not lexically resolvable (runtime object)
- `python/synapse/host/graph_builder.py:157` **unresolved-receiver** `tgt.setInput(e.target_input_index, ...)` type=None — receiver's node type not lexically resolvable (runtime object)
- `python/synapse/panel/system_prompt.py:107` **unresolved-receiver** `node.setInput(0, ...)` type=None — receiver's node type not lexically resolvable (runtime object)
- `python/synapse/panel/system_prompt.py:143` **unresolved-receiver** `new_node.setInput(0, ...)` type=None — receiver's node type not lexically resolvable (runtime object)
- `python/synapse/panel/system_prompt.py:144` **unresolved-receiver** `display_node.setInput(0, ...)` type=None — receiver's node type not lexically resolvable (runtime object)
- `python/synapse/routing/planner.py:302` **index-within-arity** `drape.setInput(0, ...)` type=vellumdrape — input index 0 within max_inputs for 'vellumdrape'
- `python/synapse/routing/planner.py:331` **index-within-arity** `wind.setInput(0, ...)` type=vellumconstraintproperty — input index 0 within max_inputs for 'vellumconstraintproperty'
- `python/synapse/routing/planner.py:344` **index-within-arity** `cache.setInput(0, ...)` type=filecache — input index 0 within max_inputs for 'filecache'
- `python/synapse/routing/planner.py:371` **index-within-arity** `asm.setInput(0, ...)` type=assemble — input index 0 within max_inputs for 'assemble'
- `python/synapse/routing/planner.py:373` **index-within-arity** `cons.setInput(0, ...)` type=rbdconstraintsfromrules — input index 0 within max_inputs for 'rbdconstraintsfromrules'
- `python/synapse/routing/planner.py:377` **index-within-arity** `props.setInput(0, ...)` type=rbdconstraintproperties — input index 0 within max_inputs for 'rbdconstraintproperties'
- `python/synapse/routing/planner.py:396` **index-within-arity** `debris.setInput(0, ...)` type=debrissource — input index 0 within max_inputs for 'debrissource'
- `python/synapse/routing/planner.py:409` **index-within-arity** `pyro.setInput(0, ...)` type=pyrosolver — input index 0 within max_inputs for 'pyrosolver'
- `python/synapse/routing/planner.py:422` **index-within-arity** `cache.setInput(0, ...)` type=filecache — input index 0 within max_inputs for 'filecache'
- `python/synapse/routing/planner.py:545` **index-within-arity** `evl.setInput(0, ...)` type=oceanevaluate — input index 0 within max_inputs for 'oceanevaluate'
- `python/synapse/routing/planner.py:561` **index-within-arity** `solver.setInput(0, ...)` type=flipsolver — input index 0 within max_inputs for 'flipsolver'
- `python/synapse/routing/planner.py:573` **index-within-arity** `ww_solve.setInput(0, ...)` type=whitewatersolver — input index 0 within max_inputs for 'whitewatersolver'
- `python/synapse/routing/planner.py:575` **index-within-arity** `ww_src.setInput(0, ...)` type=whitewatersource — input index 0 within max_inputs for 'whitewatersource'
- `python/synapse/routing/planner.py:602` **index-within-arity** `wrangle.setInput(0, ...)` type=attribwrangle — input index 0 within max_inputs for 'attribwrangle'
- `python/synapse/routing/planner.py:605` **index-within-arity** `rast.setInput(0, ...)` type=volumerasterizeattributes — input index 0 within max_inputs for 'volumerasterizeattributes'
- `python/synapse/routing/planner.py:608` **index-within-arity** `solver.setInput(0, ...)` type=pyrosolver — input index 0 within max_inputs for 'pyrosolver'
- `python/synapse/routing/planner.py:611` **index-within-arity** `cache.setInput(0, ...)` type=filecache — input index 0 within max_inputs for 'filecache'
- `python/synapse/routing/planner.py:657` **index-within-arity** `matlib.setInput(0, ...)` type=materiallibrary — input index 0 within max_inputs for 'materiallibrary'
- `python/synapse/routing/planner.py:660` **index-within-arity** `assign.setInput(0, ...)` type=assignmaterial — input index 0 within max_inputs for 'assignmaterial'
- `python/synapse/routing/planner.py:669` **index-within-arity** `cam.setInput(0, ...)` type=camera — input index 0 within max_inputs for 'camera'
- `python/synapse/routing/planner.py:678` **index-within-arity** `key.setInput(0, ...)` type=light — input index 0 within max_inputs for 'light'
- `python/synapse/routing/planner.py:681` **index-within-arity** `fill.setInput(0, ...)` type=light — input index 0 within max_inputs for 'light'
- `python/synapse/routing/planner.py:684` **index-within-arity** `rim.setInput(0, ...)` type=light — input index 0 within max_inputs for 'light'
- `python/synapse/routing/planner.py:692` **index-within-arity** `light.setInput(0, ...)` type=light — input index 0 within max_inputs for 'light'
- `python/synapse/routing/planner.py:701` **index-within-arity** `rs.setInput(0, ...)` type=karmarenderproperties — input index 0 within max_inputs for 'karmarenderproperties'
- `python/synapse/routing/planner.py:704` **index-within-arity** `karma.setInput(0, ...)` type=karma — input index 0 within max_inputs for 'karma'
- `python/synapse/routing/planner.py:712` **index-within-arity** `out.setInput(0, ...)` type=null — input index 0 within max_inputs for 'null'
- `python/synapse/routing/recipes/fx_recipes.py:84` **label-claim-verified** `solver.setInput(0, ...)` type=vellumsolver — comment label claim matches catalog label at index 0
- `python/synapse/routing/recipes/fx_recipes.py:86` **label-claim-verified** `solver.setInput(1, ...)` type=vellumsolver — comment label claim matches catalog label at index 1
- `python/synapse/routing/recipes/fx_recipes.py:90` **index-within-arity** `cache.setInput(0, ...)` type=filecache — input index 0 within max_inputs for 'filecache'
- `python/synapse/routing/recipes/fx_recipes.py:133` **index-within-arity** `asm.setInput(0, ...)` type=assemble — input index 0 within max_inputs for 'assemble'
- `python/synapse/routing/recipes/fx_recipes.py:136` **index-within-arity** `cons.setInput(0, ...)` type=rbdconstraintsfromrules — input index 0 within max_inputs for 'rbdconstraintsfromrules'
- `python/synapse/routing/recipes/fx_recipes.py:141` **index-within-arity** `props.setInput(0, ...)` type=rbdconstraintproperties — input index 0 within max_inputs for 'rbdconstraintproperties'
- `python/synapse/routing/recipes/fx_recipes.py:144` **index-within-arity** `solver.setInput(0, ...)` type=rbdbulletsolver — input index 0 within max_inputs for 'rbdbulletsolver'
- ... and 107 more (see JSON)
