"""
Synapse Material Handler Mixin

Extracted from handlers_render.py -- contains material creation, assignment,
and reading handlers for the SynapseHandler class.
"""

from typing import Dict

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param, resolve_param_with_default
from .handlers_usd import _usd_to_json
from .handler_helpers import _HOUDINI_UNAVAILABLE


class MaterialHandlerMixin:
    """Mixin providing material creation, assignment, and reading handlers."""

    def _handle_create_material(self, payload: Dict) -> Dict:
        """Create a materiallibrary LOP with a MaterialX shader inside it.

        Uses native Houdini nodes (materiallibrary + shader child) so the
        material is visible and editable in the artist's network.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path_arg = resolve_param(payload, "node", required=False)
        name = resolve_param_with_default(payload, "name", "material")
        shader_type = resolve_param_with_default(
            payload, "shader_type", "mtlxstandard_surface"
        )
        base_color = resolve_param(payload, "base_color", required=False)
        metalness = resolve_param(payload, "metalness", required=False)
        roughness = resolve_param(payload, "roughness", required=False)

        from .main_thread import run_on_main

        def _on_main():
            node = self._resolve_lop_node(node_path_arg)  # type: ignore[attr-defined]

            parent = node.parent()

            # Create materiallibrary node and wire it after the resolved LOP node
            matlib = parent.createNode("materiallibrary", name)
            matlib.setInput(0, node)
            matlib.moveToGoodPosition()

            # Cook the matlib so its internal network is ready for child creation
            matlib.cook(force=True)

            # Create shader node inside the materiallibrary
            shader = matlib.createNode(shader_type, name + "_shader")
            if shader is None:
                raise RuntimeError(
                    f"Couldn't create a '{shader_type}' shader inside the material library "
                    "-- check that this shader type is available in your Houdini build"
                )

            # Set optional shader parameters
            if base_color is not None:
                if isinstance(base_color, (list, tuple)) and len(base_color) >= 3:
                    for i, ch in enumerate(("r", "g", "b")):
                        p = shader.parm(f"base_color{ch}")
                        if p:
                            p.set(float(base_color[i]))
            if metalness is not None:
                p = shader.parm("metalness")
                if p:
                    p.set(float(metalness))
            if roughness is not None:
                p = shader.parm("specular_roughness")
                if p:
                    p.set(float(roughness))

            # Read the USD material path that the matlib auto-generates
            material_usd_path = f"/materials/{name}"

            return {
                "matlib_path": matlib.path(),
                "shader_path": shader.path(),
                "material_usd_path": material_usd_path,
                "shader_type": shader_type,
                "name": name,
            }

        return run_on_main(_on_main)

    def _handle_assign_material(self, payload: Dict) -> Dict:
        """Create an assignmaterial LOP to bind a material to geometry prims."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path_arg = resolve_param(payload, "node", required=False)
        prim_pattern = resolve_param(payload, "prim_pattern")
        material_path = resolve_param(payload, "material_path")

        from .main_thread import run_on_main

        def _on_main():
            node = self._resolve_lop_node(node_path_arg)  # type: ignore[attr-defined]

            parent = node.parent()
            # Safe node name from the material path
            safe_name = material_path.rstrip("/").rsplit("/", 1)[-1] or "mat"
            assign_node = parent.createNode("assignmaterial", f"assign_{safe_name}")
            assign_node.setInput(0, node)
            assign_node.moveToGoodPosition()

            # Set the prim pattern and material spec path
            assign_node.parm("primpattern1").set(prim_pattern)
            assign_node.parm("matspecpath1").set(material_path)

            return {
                "node_path": assign_node.path(),
                "prim_pattern": prim_pattern,
                "material_path": material_path,
            }

        return run_on_main(_on_main)

    def _handle_read_material(self, payload: Dict) -> Dict:
        """Read material binding and shader parameters from a USD prim.

        Pure stage query -- no node creation. Uses UsdShade API to inspect
        material bindings and shader inputs.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path_arg = resolve_param(payload, "node", required=False)
        prim_path = resolve_param(payload, "prim_path")

        from .main_thread import run_on_main

        def _on_main():
            node = self._resolve_lop_node(node_path_arg)  # type: ignore[attr-defined]

            stage = node.stage()
            if stage is None:
                raise ValueError(
                    "That node doesn't have an active USD stage yet -- "
                    "it may need to cook first, or check the LOP network is set up"
                )

            prim = stage.GetPrimAtPath(prim_path)
            if not prim.IsValid():
                raise ValueError(
                    f"Couldn't find a prim at {prim_path} -- "
                    "double-check the path on the USD stage"
                )

            from pxr import UsdShade

            binding_api = UsdShade.MaterialBindingAPI(prim)
            bound = binding_api.GetDirectBinding()
            mat_path_str = str(bound.GetMaterialPath()) if bound.GetMaterial() else ""

            if not mat_path_str:
                return {
                    "prim_path": prim_path,
                    "has_material": False,
                    "material_path": "",
                    "shader_type": "",
                    "shader_params": {},
                }

            material = bound.GetMaterial()
            shader_type = ""
            shader_params = {}

            # Get the surface shader output
            surface_output = material.GetSurfaceOutput()
            if surface_output:
                source = surface_output.GetConnectedSources()
                if source and source[0]:
                    shader_prim = UsdShade.Shader(source[0][0].source.GetPrim())
                    shader_type = str(shader_prim.GetIdAttr().Get() or "")

                    for shader_input in shader_prim.GetInputs():
                        input_name = shader_input.GetBaseName()
                        val = shader_input.Get()
                        if val is not None:
                            shader_params[input_name] = _usd_to_json(val)

            return {
                "prim_path": prim_path,
                "has_material": True,
                "material_path": mat_path_str,
                "shader_type": shader_type,
                "shader_params": shader_params,
            }

        return run_on_main(_on_main)
