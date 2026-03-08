"""
RELAY-SOLARIS: Component Builder Node Verification

CRITICAL BLOCKER CHECK — must run before Phase 3 implementation.

This script verifies whether "componentbuilder" exists as a native
createable node type in Houdini 21. If it doesn't, Phase 3 must
redesign the Component Builder tool as manual subnet assembly.

Run via SYNAPSE execute_python or directly in Houdini's Python shell.

Expected outcomes:
  A) componentbuilder exists as native node → Phase 3 uses it directly
  B) componentbuilder does NOT exist → Phase 3 uses manual subnet pattern:
     - Create subnet node
     - Wire componentgeometry, componentmaterial, componentoutput inside
     - Adjust atomic operation model (+50% time estimate)
"""

# ------------------------------------------------------------------
# Script to run via execute_python over WebSocket
# ------------------------------------------------------------------

VERIFY_SCRIPT = '''
import hou
import json

results = {
    "component_builder": {"exists": False, "type_name": None, "category": None},
    "component_geometry": {"exists": False, "type_name": None, "category": None},
    "component_material": {"exists": False, "type_name": None, "category": None},
    "component_output": {"exists": False, "type_name": None, "category": None},
    "component_geometry_variants": {"exists": False, "type_name": None, "category": None},
}

stage = hou.node("/stage")
if stage is None:
    stage = hou.node("/").createNode("lopnet", "stage")

# Test each node type
for key, type_name in [
    ("component_builder", "componentbuilder"),
    ("component_geometry", "componentgeometry"),
    ("component_material", "componentmaterial"),
    ("component_output", "componentoutput"),
    ("component_geometry_variants", "componentgeometryvariants"),
]:
    try:
        test_node = stage.createNode(type_name, f"_verify_{type_name}")
        results[key]["exists"] = True
        results[key]["type_name"] = test_node.type().name()
        results[key]["category"] = test_node.type().category().name()
        # Check if it's a subnet (has children capacity)
        try:
            results[key]["is_subnet"] = test_node.isNetwork()
        except Exception:
            results[key]["is_subnet"] = None
        # Check available parameters
        try:
            results[key]["parm_count"] = len(test_node.parms())
            results[key]["parm_names"] = [p.name() for p in test_node.parms()[:20]]
        except Exception:
            pass
        test_node.destroy()
    except Exception as e:
        results[key]["exists"] = False
        results[key]["error"] = str(e)

# Also check via node type categories
try:
    lop_types = hou.lopNodeTypeCategory().nodeTypes()
    results["all_component_types"] = [
        name for name in lop_types.keys()
        if "component" in name.lower()
    ]
except Exception as e:
    results["all_component_types_error"] = str(e)

# Determine Phase 3 strategy
if results["component_builder"]["exists"]:
    results["phase3_strategy"] = "NATIVE — use componentbuilder node directly"
elif all(results[k]["exists"] for k in [
    "component_geometry", "component_material", "component_output"
]):
    results["phase3_strategy"] = (
        "SUBNET — componentbuilder not native, but individual components exist. "
        "Create subnet and wire componentgeometry + componentmaterial + componentoutput inside."
    )
else:
    results["phase3_strategy"] = (
        "MANUAL — neither componentbuilder nor individual component nodes exist. "
        "Must build entirely from scratch with generic LOP nodes. +100% time estimate."
    )

result = json.dumps(results, indent=2)
'''


def get_verify_script() -> str:
    """Return the verification script for execute_python."""
    return VERIFY_SCRIPT


if __name__ == "__main__":
    print("=== RELAY-SOLARIS Component Builder Verification ===")
    print()
    print("This script must be run inside Houdini (Python shell or via execute_python).")
    print()
    print("To run via SYNAPSE MCP:")
    print("  Use synapse execute_python tool with the script from get_verify_script()")
    print()
    print("To run in Houdini Python shell:")
    print("  Copy the VERIFY_SCRIPT string and paste into the Python Source Editor")
    print()
    print("Expected output: JSON with exists/type_name/category for each component node type")
    print("Plus phase3_strategy recommendation: NATIVE, SUBNET, or MANUAL")
