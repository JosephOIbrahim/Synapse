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
        opacity = resolve_param(payload, "opacity", required=False)
        emission = resolve_param(payload, "emission", required=False)
        emission_color = resolve_param(payload, "emission_color", required=False)
        subsurface = resolve_param(payload, "subsurface", required=False)
        subsurface_color = resolve_param(payload, "subsurface_color", required=False)

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
            if opacity is not None:
                p = shader.parm("opacity")
                if p:
                    p.set(float(opacity))
            if emission is not None:
                p = shader.parm("emission")
                if p:
                    p.set(float(emission))
            if emission_color is not None:
                if isinstance(emission_color, (list, tuple)) and len(emission_color) >= 3:
                    for i, ch in enumerate(("r", "g", "b")):
                        p = shader.parm(f"emission_color{ch}")
                        if p:
                            p.set(float(emission_color[i]))
            if subsurface is not None:
                p = shader.parm("subsurface")
                if p:
                    p.set(float(subsurface))
            if subsurface_color is not None:
                if isinstance(subsurface_color, (list, tuple)) and len(subsurface_color) >= 3:
                    for i, ch in enumerate(("r", "g", "b")):
                        p = shader.parm(f"subsurface_color{ch}")
                        if p:
                            p.set(float(subsurface_color[i]))

            # Read actual USD material path from the stage (not hardcoded)
            material_usd_path = f"/materials/{name}"
            try:
                matlib.cook(force=True)
                stage = matlib.stage()
                if stage:
                    from pxr import UsdShade
                    # Walk /materials/ prims to find the one matching our name
                    materials_prim = stage.GetPrimAtPath("/materials")
                    if materials_prim and materials_prim.IsValid():
                        for child in materials_prim.GetChildren():
                            child_path = str(child.GetPath())
                            if UsdShade.Material(child).GetPrim().IsValid():
                                # Match by name prefix — matlib may append _shader
                                if name in child_path:
                                    material_usd_path = child_path
                                    break
            except Exception as _stage_err:
                import logging as _log
                _log.getLogger(__name__).warning(
                    "create_material stage query failed: %s", _stage_err
                )

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

            # If the prim itself IS a Material, read it directly
            direct_mat = UsdShade.Material(prim)
            if direct_mat.GetPrim().IsValid() and direct_mat.GetSurfaceOutput():
                material = direct_mat
                mat_path_str = prim_path
            else:
                # Otherwise look for a material binding on the prim
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

            def _extract_shader_info(shader_prim):
                """Extract type and params from a UsdShade.Shader prim."""
                s_type = ""
                s_params = {}
                id_attr = shader_prim.GetIdAttr()
                if id_attr:
                    s_type = str(id_attr.Get() or "")
                for shader_input in shader_prim.GetInputs():
                    input_name = shader_input.GetBaseName()
                    val = shader_input.Get()
                    if val is not None:
                        s_params[input_name] = _usd_to_json(val)
                return s_type, s_params

            # Try multiple approaches to find the surface shader:
            # 1. Standard UsdShade surface output
            # 2. MaterialX outputs (surface, out)
            # 3. Walk child prims for any Shader prim
            surface_output = material.GetSurfaceOutput()
            shader_found = False

            if surface_output:
                source = surface_output.GetConnectedSources()
                if source and source[0]:
                    shader_prim = UsdShade.Shader(source[0][0].source.GetPrim())
                    if shader_prim.GetPrim().IsValid():
                        shader_type, shader_params = _extract_shader_info(shader_prim)
                        shader_found = True

            # Fallback: try MaterialX-style outputs
            if not shader_found:
                mat_prim = material.GetPrim()
                for output_name in ("surface", "out", "mtlx:surface"):
                    mtlx_out = material.GetOutput(output_name)
                    if mtlx_out:
                        source = mtlx_out.GetConnectedSources()
                        if source and source[0]:
                            shader_prim = UsdShade.Shader(source[0][0].source.GetPrim())
                            if shader_prim.GetPrim().IsValid():
                                shader_type, shader_params = _extract_shader_info(shader_prim)
                                shader_found = True
                                break

            # Final fallback: walk child prims for any Shader-typed prim
            if not shader_found:
                mat_prim = material.GetPrim()
                for child in mat_prim.GetChildren():
                    child_shader = UsdShade.Shader(child)
                    if child_shader.GetPrim().IsValid() and child_shader.GetIdAttr():
                        shader_type, shader_params = _extract_shader_info(child_shader)
                        shader_found = True
                        break

            return {
                "prim_path": prim_path,
                "has_material": True,
                "material_path": mat_path_str,
                "shader_type": shader_type,
                "shader_params": shader_params,
            }

        return run_on_main(_on_main)

    def _handle_create_textured_material(self, payload: Dict) -> Dict:
        """Create a MaterialX standard surface with texture file inputs.

        Creates a materiallibrary with an mtlxstandard_surface shader and
        wires mtlximage nodes for each provided texture map (diffuse, roughness,
        normal, displacement). Handles UDIM detection (<UDIM> in filename) and
        connects UV coordinates (mtlxgeompropvalue) to all texture nodes.

        This is the production-ready version of create_material — use this when
        the artist has texture files, use create_material for simple solid colors.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path_arg = resolve_param(payload, "node", required=False)
        name = resolve_param_with_default(payload, "name", "textured_material")

        # Texture maps (all optional — at minimum provide diffuse_map)
        diffuse_map = resolve_param(payload, "diffuse_map", required=False)
        roughness_map = resolve_param(payload, "roughness_map", required=False)
        normal_map = resolve_param(payload, "normal_map", required=False)
        metalness_map = resolve_param(payload, "metalness_map", required=False)
        displacement_map = resolve_param(payload, "displacement_map", required=False)
        opacity_map = resolve_param(payload, "opacity_map", required=False)

        # Scalar fallback values (used when no texture map is provided)
        roughness_value = resolve_param(payload, "roughness", required=False)
        metalness_value = resolve_param(payload, "metalness", required=False)

        # Geo assignment pattern (optional — assign material to prims matching this)
        geo_pattern = resolve_param(payload, "geo_pattern", required=False)

        from .main_thread import run_on_main

        def _on_main():
            node = self._resolve_lop_node(node_path_arg)  # type: ignore[attr-defined]
            parent = node.parent()

            # Create materiallibrary and cook before adding children
            matlib = parent.createNode("materiallibrary", name)
            matlib.setInput(0, node)
            matlib.moveToGoodPosition()
            matlib.cook(force=True)

            # Create the main shader
            shader = matlib.createNode("mtlxstandard_surface", name + "_shader")
            if shader is None:
                raise RuntimeError(
                    "Couldn't create mtlxstandard_surface shader -- "
                    "check that MaterialX is available in your Houdini build"
                )

            # Create UV coordinate node (shared by all texture readers)
            uv_node = matlib.createNode("mtlxgeompropvalue", "uv_reader")
            if uv_node:
                # Set to read 'st' (UV) attribute as vector2
                sig_parm = uv_node.parm("signature")
                if sig_parm:
                    sig_parm.set("vector2")
                prop_parm = uv_node.parm("geomprop")
                if prop_parm:
                    prop_parm.set("st")

            connected_maps = []

            def _create_texture(tex_path, tex_name, shader_input, is_color=False):
                """Create an mtlximage node and connect it to the shader."""
                img = matlib.createNode("mtlximage", tex_name)
                if img is None:
                    return None

                # Set file path
                file_parm = img.parm("file")
                if file_parm:
                    file_parm.set(tex_path)

                # Set signature based on whether this is color or scalar
                sig_parm = img.parm("signature")
                if sig_parm:
                    if is_color:
                        sig_parm.set("color3")
                    else:
                        sig_parm.set("float")

                # Connect UV reader to texture's texcoord input
                if uv_node:
                    img.setNamedInput("texcoord", uv_node, 0)

                # Connect texture output to shader input
                shader.setNamedInput(shader_input, img, 0)

                connected_maps.append({
                    "map": tex_name,
                    "file": tex_path,
                    "shader_input": shader_input,
                    "node": img.path(),
                    "udim": "<UDIM>" in tex_path or "<udim>" in tex_path,
                })
                return img

            # Wire texture maps to shader inputs
            if diffuse_map:
                _create_texture(diffuse_map, "diffuse_tex", "base_color", is_color=True)

            if roughness_map:
                _create_texture(roughness_map, "roughness_tex", "specular_roughness")
            elif roughness_value is not None:
                p = shader.parm("specular_roughness")
                if p:
                    p.set(float(roughness_value))

            if metalness_map:
                _create_texture(metalness_map, "metalness_tex", "metalness")
            elif metalness_value is not None:
                p = shader.parm("metalness")
                if p:
                    p.set(float(metalness_value))

            if normal_map:
                # Normal maps need a mtlxnormalmap node between the image and shader
                normal_img = matlib.createNode("mtlximage", "normal_tex")
                if normal_img:
                    fp = normal_img.parm("file")
                    if fp:
                        fp.set(normal_map)
                    sig = normal_img.parm("signature")
                    if sig:
                        sig.set("vector3")
                    if uv_node:
                        normal_img.setNamedInput("texcoord", uv_node, 0)

                    # Create normalmap converter
                    normal_conv = matlib.createNode("mtlxnormalmap", "normal_convert")
                    if normal_conv:
                        normal_conv.setNamedInput("in", normal_img, 0)
                        shader.setNamedInput("normal", normal_conv, 0)

                    connected_maps.append({
                        "map": "normal_tex",
                        "file": normal_map,
                        "shader_input": "normal",
                        "node": normal_img.path(),
                        "udim": "<UDIM>" in normal_map or "<udim>" in normal_map,
                    })

            if opacity_map:
                _create_texture(opacity_map, "opacity_tex", "opacity", is_color=True)

            # Layout nodes cleanly
            matlib.layoutChildren()

            # Query actual USD material path from stage
            material_usd_path = f"/materials/{name}"
            try:
                matlib.cook(force=True)
                stage = matlib.stage()
                if stage:
                    from pxr import UsdShade
                    materials_prim = stage.GetPrimAtPath("/materials")
                    if materials_prim and materials_prim.IsValid():
                        for child in materials_prim.GetChildren():
                            child_path = str(child.GetPath())
                            if UsdShade.Material(child).GetPrim().IsValid():
                                if name in child_path:
                                    material_usd_path = child_path
                                    break
            except Exception as _e:
                import logging as _log
                _log.getLogger(__name__).warning(
                    "create_textured_material stage query: %s", _e
                )

            result = {
                "matlib_path": matlib.path(),
                "shader_path": shader.path(),
                "material_usd_path": material_usd_path,
                "name": name,
                "connected_maps": connected_maps,
            }

            # Optional: create inline material assignment
            if geo_pattern:
                assign_node = parent.createNode(
                    "assignmaterial", f"assign_{name}"
                )
                assign_node.setInput(0, matlib)
                assign_node.moveToGoodPosition()
                assign_node.parm("primpattern1").set(geo_pattern)
                assign_node.parm("matspecpath1").set(material_usd_path)
                result["assign_node"] = assign_node.path()
                result["geo_pattern"] = geo_pattern

            # Handle displacement separately (needs render settings context)
            if displacement_map:
                connected_maps.append({
                    "map": "displacement_tex",
                    "file": displacement_map,
                    "shader_input": "displacement",
                    "node": None,
                    "udim": "<UDIM>" in displacement_map or "<udim>" in displacement_map,
                    "note": "Displacement requires a displacementshader setup — "
                            "use set_usd_attribute to configure displacement on the geometry prim",
                })

            return result

        return run_on_main(_on_main)
