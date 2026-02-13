# Spec: HDA Scaffolding Recipe for Synapse

**Status**: Ready for implementation
**Target**: `python/synapse/routing/recipes.py` -> `RecipeRegistry._register_builtins()`
**Category**: `pipeline`
**Priority**: High (closes gap vs HDA Architect)

---

## Overview

A Synapse recipe that scaffolds a complete HDA (Houdini Digital Asset) from a natural language description. Creates the subnet structure, wires I/O, creates the HDA definition, adds standard parameters, and saves to the project's `otls/` directory.

This is a **scaffold** -- it creates the structural shell with proper conventions. The artist (or higher-tier Synapse operations) fills in the internal logic.

## Why This Matters

- **HDA Architect** (competitor) generates HDAs from prompts using Gemini. Synapse currently has no HDA creation recipe.
- HDAs are the standard packaging format for reusable tools in Houdini. Every studio pipeline depends on them.
- Scaffolding removes the tedious boilerplate: subnet creation, I/O wiring, HDA definition, namespace, version, help text, icon, category.

## Trigger Patterns

```python
triggers=[
    r"^(?:create|make|build|scaffold)\s+(?:an?\s+)?(?:hda|digital asset|otl)(?:\s+(?:called|named)\s+(?P<name>[\w]+))?(?:\s+(?:for|that|to|which)\s+(?P<description>.+))?$",
    r"^(?:new|setup)\s+(?:hda|digital asset)(?:\s+(?P<name>[\w]+))?(?:\s+(?:for|that|to|which)\s+(?P<description>.+))?$",
    r"^hda\s+scaffold(?:\s+(?P<name>[\w]+))?(?:\s+(?P<description>.+))?$",
],
parameters=["name", "description"],
```

**Match examples**:
- `"create an hda called rock_generator for scattering rocks on terrain"` -> name=`rock_generator`, description=`scattering rocks on terrain`
- `"scaffold hda debris_sim"` -> name=`debris_sim`, description=``
- `"make a digital asset for color correction"` -> name=``, description=`color correction`
- `"new hda noise_deformer that deforms geometry with layered noise"` -> name=`noise_deformer`, description=`deforms geometry with layered noise`

## Recipe Structure

```python
Recipe(
    name="hda_scaffold",
    description="Scaffold a complete HDA: subnet, I/O, definition, parameters, and save to $HIP/otls/",
    triggers=[
        r"^(?:create|make|build|scaffold)\s+(?:an?\s+)?(?:hda|digital asset|otl)(?:\s+(?:called|named)\s+(?P<name>[\w]+))?(?:\s+(?:for|that|to|which)\s+(?P<description>.+))?$",
        r"^(?:new|setup)\s+(?:hda|digital asset)(?:\s+(?P<name>[\w]+))?(?:\s+(?:for|that|to|which)\s+(?P<description>.+))?$",
        r"^hda\s+scaffold(?:\s+(?P<name>[\w]+))?(?:\s+(?P<description>.+))?$",
    ],
    parameters=["name", "description"],
    gate_level=GateLevel.REVIEW,
    category="pipeline",
    steps=[
        # Step 1: Create and configure the subnet + HDA definition
        RecipeStep(
            action="execute_python",
            payload_template={
                "code": HDA_SCAFFOLD_CODE,
            },
            gate_level=GateLevel.REVIEW,
            output_var="hda",
        ),
    ],
)
```

## Python Code (HDA_SCAFFOLD_CODE)

This is the `execute_python` payload. It's a single step because HDA creation is transactional -- you need the subnet to exist before creating the HDA definition, and it all happens in one `hou` session.

```python
HDA_SCAFFOLD_CODE = '''
import hou
import os
import re

# --- Parameters from trigger ---
raw_name = "{name}".strip()
description = "{description}".strip()

# --- Derive names ---
# Default name if not provided
if not raw_name:
    raw_name = "custom_tool"

# Sanitize: lowercase, underscores only
hda_name = re.sub(r"[^a-z0-9_]", "_", raw_name.lower()).strip("_")
hda_label = raw_name.replace("_", " ").title()

# --- Find parent context ---
# Prefer selected node's parent, fall back to /obj
sel = hou.selectedNodes()
if sel and sel[0].type().category() == hou.sopNodeTypeCategory():
    parent = sel[0].parent()
elif sel:
    parent = sel[0]
else:
    # Create a geo container if we're at /obj level
    obj = hou.node("/obj")
    parent = obj.createNode("geo", hda_name + "_dev")
    parent.moveToGoodPosition()

# --- Create subnet structure ---
subnet = parent.createNode("subnet", hda_name)

# Create input null (standard convention)
input_null = subnet.createNode("null", "IN")
input_null.setPosition(hou.Vector2(0, 0))

# Create output null with display/render flags
output_null = subnet.createNode("null", "OUT")
output_null.setPosition(hou.Vector2(0, -3))
output_null.setInput(0, input_null)
output_null.setDisplayFlag(True)
output_null.setRenderFlag(True)

# Wire subnet's first input to IN null
# The subnet's internal input connector maps to input_null
subnet.indirectInputs()[0].setInput(0, None)  # Clear
input_null.setInput(0, subnet.indirectInputs()[0])

# Layout
subnet.layoutChildren()
subnet.moveToGoodPosition()

# --- Create HDA definition ---
otls_dir = os.path.join(hou.getenv("HIP", ""), "otls")
if not os.path.exists(otls_dir):
    os.makedirs(otls_dir)

hda_path = os.path.join(otls_dir, hda_name + ".hda")

# Determine operator namespace
# Convention: Sop/{namespace}::{name}::{version}
op_name = "Sop/" + hda_name
hda_node = subnet.createDigitalAsset(
    name=hda_name,
    hda_file_name=hda_path,
    description=hda_label,
    min_num_inputs=1,
    max_num_inputs=1,
)

# --- Configure the HDA definition ---
definition = hda_node.type().definition()

# Set help text
help_text = "= " + hda_label + " =\\n\\n"
if description:
    help_text += description + "\\n\\n"
help_text += "== Parameters ==\\n\\n"
help_text += "See parameter interface for controls.\\n"
definition.setExtraFileOption("Help", help_text)

# Set icon (generic SOP icon)
definition.setIcon("SOP_subnet")

# Set sections metadata
definition.setExtraFileOption("CreatedBy", "Synapse HDA Scaffold")

# Add a standard parameter folder
ptg = hda_node.parmTemplateGroup()

# Main tab
main_folder = hou.FolderParmTemplate(
    "main_folder", "Main", folder_type=hou.folderType.Tabs
)

# Add description as a label if provided
if description:
    main_folder.addParmTemplate(
        hou.LabelParmTemplate("info_label", "Purpose", column_labels=[description])
    )

# Add standard control parameters
main_folder.addParmTemplate(
    hou.FloatParmTemplate("blend", "Blend", 1, default_value=(1.0,),
                          min=0.0, max=1.0, min_is_strict=True, max_is_strict=True)
)
main_folder.addParmTemplate(
    hou.ToggleParmTemplate("enable", "Enable", default_value=True)
)

ptg.append(main_folder)
hda_node.setParmTemplateGroup(ptg)

# Save
definition.save(hda_path, hda_node)

# Select the new HDA instance
hda_node.setSelected(True, clear_all_selected=True)
hda_node.setDisplayFlag(True)
hda_node.setRenderFlag(True)

result = {
    "node": hda_node.path(),
    "hda_file": hda_path,
    "hda_name": hda_name,
    "hda_label": hda_label,
    "definition": op_name,
    "description": description or "(none provided)",
}
'''
```

## Data Flow

The recipe uses `output_var="hda"` so the LLM response can reference:
- `$hda.node` -- path to the HDA instance node
- `$hda.hda_file` -- path to the saved .hda file
- `$hda.hda_name` -- sanitized name
- `$hda.hda_label` -- display label
- `$hda.definition` -- operator type name
- `$hda.description` -- user's description

## What the Artist Gets

After the recipe runs:

1. **A subnet-based HDA** at the current context (or in a new geo container)
2. **IN/OUT nulls** wired correctly (standard convention)
3. **HDA definition saved** to `$HIP/otls/{name}.hda`
4. **Parameter interface** with a Main tab, Blend slider, Enable toggle
5. **Help text** pre-filled with the description
6. **Node selected** and ready for the artist to dive in and build the internal logic

## Future Extensions

These can be added as additional recipes or as recipe steps:

| Extension | How |
|-----------|-----|
| **Multi-input HDA** | Add `inputs` parameter to trigger, create multiple IN nulls |
| **Category selection** | Add `category` parameter (SOP/DOP/LOP/COP), adjust `op_name` prefix |
| **Template parameters** | Detect common patterns from description ("noise" -> add freq/amp/octaves parms) |
| **LLM-driven internals** | Chain with Tier 5/6 to generate internal node graph from description |
| **Version management** | Increment version number, keep history in `$HIP/otls/` |
| **Namespace** | Studio namespace prefix (e.g., `studio::hda_name::1.0`) |

## Integration with Synapse Knowledge

When this recipe fires, the Synapse LLM tier can also:
1. Look up the description in the knowledge index for relevant node types
2. Suggest internal nodes based on the description (e.g., "noise deformer" -> suggest mountain SOP, attribute noise)
3. Reference VEX patterns from the RAG layer for wrangle-heavy HDAs

## Registration

Add to `RecipeRegistry._register_builtins()` after the existing pipeline recipes (sopimport_chain, edit_transform, file_cache):

```python
# Define the code string at module level or as a class constant
HDA_SCAFFOLD_CODE = '''...'''  # (the Python code above)

self.register(Recipe(
    name="hda_scaffold",
    description="Scaffold a complete HDA: subnet, I/O, definition, parameters, and save to $HIP/otls/",
    triggers=[...],  # (the triggers above)
    parameters=["name", "description"],
    gate_level=GateLevel.REVIEW,
    category="pipeline",
    steps=[
        RecipeStep(
            action="execute_python",
            payload_template={"code": HDA_SCAFFOLD_CODE},
            gate_level=GateLevel.REVIEW,
            output_var="hda",
        ),
    ],
))
```

## Test Cases

| Input | Expected |
|-------|----------|
| `"create hda rock_gen for scattering rocks"` | Creates `rock_gen.hda` in `$HIP/otls/`, label "Rock Gen" |
| `"scaffold hda"` | Creates `custom_tool.hda` with default name |
| `"make a digital asset called my_tool"` | Creates `my_tool.hda`, label "My Tool" |
| `"new hda Color_Fix that fixes color banding"` | Creates `color_fix.hda`, description in help text |
| `"build an hda for noise displacement"` | Creates `custom_tool.hda`, description "noise displacement" |

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Name collision with existing HDA | Check `hou.nodeType()` before creating; warn if exists |
| `$HIP` not set | Fall back to temp directory, warn user |
| Selected node is in wrong context | Detection logic in code handles SOP, OBJ, fallback |
| Large description with special chars | Sanitize description for help text (escape backslashes) |
| GateLevel.REVIEW blocks execution | Expected -- artist reviews before committing HDA to disk |

---
*Spec written for Synapse v5.3.0 recipe system. Ready for implementation in `python/synapse/routing/recipes.py`.*
