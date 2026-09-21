# JEV-HARVEST triage (Site 1)

**Verdict header: judged.**

Producer: `python harness/jev/jev_harvest.py --shadow` · guard `harvest` · ledger `harness/jev/ledger/bp10.harvest.jsonl`. This leg SORTS the quarantine; it never promotes a guide to `rag/corpus/guides/` (Joe's word). Fill `answer_key.json` to decide fix-or-drop per token; `jev_grade.py --guard harvest` grades the judgments against it.

Ingest: 31 guides -> 26 corpus (115 chunks), 5 quarantined; 113 tool rewrites, 25 drops.

## Residual tokens (quarantine reasons)

### likely_rename — a close symbol exists -- probably a rename between builds; check the suggestion

| guide | token | nearest | jev token_kind | suggest |
| --- | --- | --- | --- | --- |
| assets | `rockgenerator` | genericgenerator, gen_integrator, rendervar | node_type_renamed @ 0.77 | — |
| model | `foo` | floor, for, fog | attribute_name @ 0.93 | — |

### likely_phantom_node — no close symbol -- an uninstalled package node, or a genuine phantom

| guide | token | nearest | jev token_kind | suggest |
| --- | --- | --- | --- | --- |
| heightfields | `thermalerodabilitymask` | texturemateriallibrary, featherutility, neural_layertomask_sam2 | node_type_renamed @ 0.28 | — |

### format_or_literal — a file format / backend / literal, not a node name -- likely unbacktick or drop

| guide | token | nearest | jev token_kind | suggest |
| --- | --- | --- | --- | --- |
| io | `bgeo.sc` | geo, heatgeodesic, rbdglueobject | generic_word @ 0.62 | — |
| render | `renderman` | render, rendervar, renderpass | generic_word @ 0.42 | — |
| render | `soho` | shop, sopgeo, smooth | node_type_renamed @ 0.36 | — |

## Tool references (does the SYNAPSE equivalent do the job?)

| tool | SYNAPSE equivalent | does the job | read first |
| --- | --- | --- | --- |
| `cancel_top_cook` | tops_cancel_cook | 0.35 | yes |
| `capture_screenshot` | houdini_capture_viewport | 0.43 |  |
| `connect_nodes` | houdini_connect_nodes | 0.60 |  |
| `connect_nodes_batch` | houdini_connect_nodes | 0.35 | yes |
| `cook_top_node` | tops_cook_node | 0.45 |  |
| `create_hda` | houdini_hda_create | 0.61 |  |
| `create_render_node` | houdini_create_node | 0.48 | yes |
| `dirty_work_items` | tops_dirty_node | 0.57 |  |
| `generate_static_items` | tops_generate_items | 0.43 |  |
| `get_expression` | houdini_get_parm | 0.42 | yes |
| `get_geometry_info` | synapse_inspect_node | 0.46 | yes |
| `get_hda_info` | houdini_hda_list | 0.45 |  |
| `get_help_page` | synapse_knowledge_lookup | 0.50 |  |
| `get_node_info` | synapse_inspect_node | 0.62 |  |
| `get_parameter` | houdini_get_parm | 0.60 |  |
| `get_pdg_graph` | tops_get_dependency_graph | 0.45 |  |
| `get_scene_info` | houdini_scene_info | 0.48 |  |
| `get_stage_info` | houdini_stage_info | 0.64 |  |
| `get_top_scheduler_info` | tops_pipeline_status | 0.49 | yes |
| `get_usd_bound_material` | houdini_read_material | 0.46 | yes |
| `get_usd_composition` | synapse_inspect_stage | 0.48 | yes |
| `get_usd_layers` | houdini_stage_info | 0.54 | yes |
| `get_usd_materials` | houdini_read_material | 0.56 | yes |
| `get_work_item_info` | tops_get_work_items | 0.32 | yes |
| `get_work_item_states` | tops_query_items | 0.46 |  |
| `list_node_types` | synapse_scout | 0.58 |  |
| `list_usd_prims` | houdini_query_prims | 0.51 |  |
| `pause_top_cook` | tops_pause_cook | 0.57 |  |
| `set_hda_section_content` | houdini_hda_set_help | 0.39 | yes |
| `setup_pyro_sim` | build the network | 0.39 | yes |
| `start_render` | houdini_render | 0.61 |  |
| `topcook` | tops_cook_node | 0.57 |  |
| `update_hda` | houdini_hda_package | 0.44 | yes |

