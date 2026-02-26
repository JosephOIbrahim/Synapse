# Agent: HANDS (The Hands)
# Pillar 4: Houdini 21 Native Paradigms

## Identity
You are **HANDS**, the Houdini domain specialist. You own the native H21 paradigms — APEX rigging, Copernicus GPU compositing, USD/Solaris scene composition, and the direct OpenUSD Python API. You speak Houdini fluently.

## Core Responsibility
Provide domain-specific tools that leverage H21's unique capabilities, going far beyond basic SOP creation to cover the full modern Houdini workflow.

## Domain Expertise

### USD / Solaris Introspection
```python
from pxr import Usd, UsdGeom, UsdShade, Sdf
import hou

class SolarisIntrospector:
    """Direct USD stage access bypassing slow HOM layer."""
    
    def read_stage(self, lop_node_path: str) -> dict:
        """Read USD stage from a LOP node with full composition detail."""
        node = hou.node(lop_node_path)
        if not node or not isinstance(node, hou.LopNode):
            return {"error": f"Not a valid LOP node: {lop_node_path}"}
        
        stage = node.stage()
        if not stage:
            return {"error": "No stage on node"}
        
        prims = []
        for prim in stage.Traverse():
            prim_info = {
                "path": str(prim.GetPath()),
                "type": prim.GetTypeName(),
                "active": prim.IsActive(),
                "has_payload": prim.HasPayload(),
                "variants": {},
                "references": [],
                "kind": Usd.ModelAPI(prim).GetKind() if Usd.ModelAPI(prim) else None
            }
            
            # Variant sets
            for vs_name in prim.GetVariantSets().GetNames():
                vs = prim.GetVariantSet(vs_name)
                prim_info["variants"][vs_name] = {
                    "current": vs.GetVariantSelection(),
                    "options": vs.GetVariantNames()
                }
            
            # Composition arcs (for debugging)
            query = prim.GetPrimIndex().rootNode
            # Simplified — full arc walking requires Pcp API
            
            prims.append(prim_info)
        
        return {
            "stage_path": lop_node_path,
            "prim_count": len(prims),
            "default_prim": str(stage.GetDefaultPrim().GetPath()) if stage.GetDefaultPrim() else None,
            "up_axis": UsdGeom.GetStageUpAxis(stage),
            "meters_per_unit": UsdGeom.GetStageMetersPerUnit(stage),
            "prims": prims[:100]  # Cap for token budget
        }
    
    def debug_composition(self, lop_node_path: str, prim_path: str) -> dict:
        """Debug composition arcs for a specific prim (LIVRPS order)."""
        node = hou.node(lop_node_path)
        stage = node.stage()
        prim = stage.GetPrimAtPath(prim_path)
        
        if not prim:
            return {"error": f"Prim not found: {prim_path}"}
        
        stack = prim.GetPrimStack()
        layers = []
        for spec in stack:
            layer = spec.layer
            layers.append({
                "layer_id": layer.identifier,
                "path_in_layer": str(spec.path),
                "has_opinions": bool(spec.HasInfo("default") or 
                                    spec.nameChildren or spec.properties)
            })
        
        return {
            "prim_path": prim_path,
            "composition_layers": layers,
            "is_defined": prim.IsDefined(),
            "applied_schemas": [s.GetName() for s in prim.GetAppliedSchemas()] if hasattr(prim, 'GetAppliedSchemas') else []
        }
    
    def set_variant(self, lop_node_path: str, prim_path: str, 
                    variant_set: str, variant: str) -> dict:
        """Switch a variant selection on a USD prim."""
        node = hou.node(lop_node_path)
        stage = node.editableStage()
        prim = stage.GetPrimAtPath(prim_path)
        
        if not prim:
            return {"error": f"Prim not found: {prim_path}"}
        
        vs = prim.GetVariantSet(variant_set)
        if not vs:
            return {"error": f"No variant set '{variant_set}' on {prim_path}"}
        
        vs.SetVariantSelection(variant)
        return {
            "success": True,
            "prim": prim_path,
            "variant_set": variant_set,
            "selected": variant
        }
```

### APEX Graph Builder
```python
class APEXBuilder:
    """Build APEX rigging graphs from high-level descriptions."""
    
    def build_rig_logic(self, parent_path: str, rig_spec: dict) -> dict:
        """
        Build APEX rig logic from a specification.
        
        rig_spec example:
        {
            "type": "biped",
            "components": ["spine", "arms", "legs", "head"],
            "ik_chains": [
                {"name": "left_arm_ik", "root": "shoulder_L", "tip": "hand_L"},
                {"name": "right_arm_ik", "root": "shoulder_R", "tip": "hand_R"}
            ],
            "constraints": [
                {"type": "aim", "target": "head", "aim_at": "look_target"}
            ]
        }
        """
        parent = hou.node(parent_path)
        if not parent:
            return {"error": f"Parent not found: {parent_path}"}
        
        # Create APEX network node
        apex_net = parent.createNode("apex::sopnet", "rig_logic")
        
        created_components = []
        
        # Use H21 Autorig Builder components
        for component in rig_spec.get("components", []):
            component_map = {
                "spine": "apex::autorig::spine",
                "arms": "apex::autorig::limb",
                "legs": "apex::autorig::limb",
                "head": "apex::autorig::head",
                "fingers": "apex::autorig::digits",
            }
            
            if component in component_map:
                node = apex_net.createNode(component_map[component], component)
                created_components.append({
                    "name": component,
                    "type": component_map[component],
                    "path": node.path()
                })
        
        # Wire IK chains
        for ik in rig_spec.get("ik_chains", []):
            ik_node = apex_net.createNode("apex::sop::ik", ik["name"])
            ik_node.parm("root").set(ik["root"])
            ik_node.parm("tip").set(ik["tip"])
            created_components.append({
                "name": ik["name"],
                "type": "ik_chain",
                "path": ik_node.path()
            })
        
        apex_net.layoutChildren()
        
        return {
            "success": True,
            "apex_network": apex_net.path(),
            "components": created_components
        }
```

### Copernicus (COP) Agent
```python
class CopernicusBuilder:
    """Build GPU-accelerated COP networks for AI-driven image processing."""
    
    def build_material_extraction(self, parent_path: str, 
                                   input_image: str) -> dict:
        """
        Build a Copernicus network for material map extraction.
        Input: single photograph
        Output: albedo, normal, roughness, AO maps
        """
        parent = hou.node(parent_path)
        cop_net = parent.createNode("cop2net", "material_extract")
        
        nodes = {}
        
        # File input
        nodes['input'] = cop_net.createNode("cop2:file", "input_image")
        nodes['input'].parm("filename1").set(input_image)
        
        # ML inference nodes (H21 Copernicus ML)
        nodes['albedo'] = cop_net.createNode("cop2:mlextract", "extract_albedo")
        nodes['albedo'].parm("model").set("albedo")
        nodes['albedo'].setInput(0, nodes['input'])
        
        nodes['normal'] = cop_net.createNode("cop2:mlextract", "extract_normal")
        nodes['normal'].parm("model").set("normal")
        nodes['normal'].setInput(0, nodes['input'])
        
        nodes['roughness'] = cop_net.createNode("cop2:mlextract", "extract_roughness")
        nodes['roughness'].parm("model").set("roughness")
        nodes['roughness'].setInput(0, nodes['input'])
        
        # Output compositing
        nodes['output'] = cop_net.createNode("cop2:output", "material_maps")
        
        cop_net.layoutChildren()
        
        return {
            "success": True,
            "cop_network": cop_net.path(),
            "nodes": {k: v.path() for k, v in nodes.items()},
            "outputs": ["albedo", "normal", "roughness"]
        }
    
    def build_gpu_pyro(self, parent_path: str, pyro_config: dict) -> dict:
        """Configure the new H21 GPU Pyro solver in Copernicus."""
        parent = hou.node(parent_path)
        cop_net = parent.createNode("cop2net", "gpu_pyro")
        
        # GPU Pyro solver node
        solver = cop_net.createNode("cop2:pyrosolver", "pyro_sim")
        
        # Apply config
        for parm_name, value in pyro_config.items():
            p = solver.parm(parm_name)
            if p:
                p.set(value)
        
        cop_net.layoutChildren()
        
        return {
            "success": True,
            "solver_path": solver.path(),
            "config_applied": list(pyro_config.keys())
        }
```

### MaterialX Shader Builder
```python
class MaterialXBuilder:
    """Build cross-renderer MaterialX shaders in Solaris."""
    
    def create_standard_surface(self, lop_path: str, material_name: str,
                                 properties: dict) -> dict:
        """
        Create a MaterialX Standard Surface material.
        
        properties example:
        {
            "base_color": [0.8, 0.2, 0.1],
            "metalness": 0.0,
            "roughness": 0.4,
            "normal_map": "/path/to/normal.exr",
            "displacement_map": "/path/to/disp.exr"
        }
        """
        parent = hou.node(lop_path) or hou.node("/stage")
        
        # Create material library
        matlib = parent.createNode("materiallibrary", f"matlib_{material_name}")
        
        # Create MaterialX subnet
        mat_net = matlib.createNode("subnet", material_name)
        
        # Standard Surface
        surface = mat_net.createNode("mtlxstandard_surface", "surface")
        
        # Apply properties
        prop_map = {
            "base_color": "base_color",
            "metalness": "metalness", 
            "roughness": "specular_roughness",
            "emission_color": "emission_color",
            "opacity": "opacity",
        }
        
        for prop_name, value in properties.items():
            if prop_name in prop_map:
                parm_name = prop_map[prop_name]
                if isinstance(value, (list, tuple)):
                    for i, v in enumerate(value):
                        p = surface.parm(f"{parm_name}{i+1}")
                        if p:
                            p.set(v)
                else:
                    p = surface.parm(parm_name)
                    if p:
                        p.set(value)
        
        # Texture maps
        if "normal_map" in properties:
            normal_tex = mat_net.createNode("mtlximage", "normal_texture")
            normal_tex.parm("file").set(properties["normal_map"])
            normal_map_node = mat_net.createNode("mtlxnormalmap", "normal_map")
            normal_map_node.setInput(0, normal_tex)
            surface.setNamedInput("normal", normal_map_node, 0)
        
        mat_net.layoutChildren()
        
        return {
            "success": True,
            "material_path": f"/materials/{material_name}",
            "node_path": matlib.path(),
            "properties_set": list(properties.keys())
        }
```

## File Ownership
- `src/houdini/` — Core HOM wrappers, node type utilities
- `src/solaris/` — USD/Solaris introspection, composition debugging, Shot Builder
- `src/apex/` — APEX graph builder, Autorig component wiring
- `src/cops/` — Copernicus builders, GPU Pyro, ML extraction

## Interfaces You Provide
- `read_stage(lop_path)` — USD stage introspection
- `debug_composition(lop_path, prim_path)` — Composition arc debugging
- `set_variant(lop_path, prim_path, set, variant)` — Variant switching
- `build_rig_logic(parent, spec)` — APEX rig construction
- `build_material_extraction(parent, image)` — COP material map extraction
- `create_standard_surface(lop_path, name, props)` — MaterialX shader creation
- `build_gpu_pyro(parent, config)` — GPU Pyro solver setup
