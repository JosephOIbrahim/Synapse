"""
Synapse Material Handler Mixin

Extracted from handlers_render.py -- contains material creation, assignment,
and reading handlers for the SynapseHandler class.
"""

import logging
from typing import Dict, Tuple

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param, resolve_param_with_default
from .handlers_usd import _usd_to_json
from .handler_helpers import _HOUDINI_UNAVAILABLE, _suggest_prim_paths

_log = logging.getLogger(__name__)

# Material presets — common physically-based starting points.
# Keys map to mtlxstandard_surface parm names.
MATERIAL_PRESETS: Dict[str, Dict] = {
    "glass": {
        "base_color": (1.0, 1.0, 1.0), "specular_roughness": 0.0,
        "transmission": 1.0, "specular_IOR": 1.5, "metalness": 0.0,
    },
    "mirror": {
        "base_color": (1.0, 1.0, 1.0), "specular_roughness": 0.0,
        "metalness": 1.0,
    },
    "rough_metal": {
        "base_color": (0.7, 0.7, 0.7), "metalness": 1.0,
        "specular_roughness": 0.35,
    },
    "polished_metal": {
        "base_color": (0.8, 0.8, 0.8), "metalness": 1.0,
        "specular_roughness": 0.05,
    },
    "skin": {
        "base_color": (0.8, 0.55, 0.45), "subsurface": 0.5,
        "subsurface_color": (0.9, 0.4, 0.3), "specular_roughness": 0.4,
    },
    "cloth": {
        "base_color": (0.4, 0.4, 0.5), "specular_roughness": 0.8,
        "sheen": 0.3,
    },
    "plastic": {
        "base_color": (0.8, 0.1, 0.1), "specular_roughness": 0.3,
        "metalness": 0.0, "coat": 0.5, "coat_roughness": 0.1,
    },
    "ceramic": {
        "base_color": (0.9, 0.88, 0.85), "specular_roughness": 0.15,
        "coat": 1.0, "coat_roughness": 0.05,
    },
    "wax": {
        "base_color": (0.9, 0.8, 0.6), "subsurface": 0.8,
        "subsurface_color": (0.9, 0.6, 0.3), "specular_roughness": 0.4,
    },
    "rubber": {
        "base_color": (0.05, 0.05, 0.05), "specular_roughness": 0.7,
        "metalness": 0.0,
    },
}


def _query_material_usd_path(matlib_node, desired_name: str) -> str:
    """Cook a materiallibrary node and find the actual USD material path.

    Tries to cook the node and walk the stage to find a material prim
    matching *desired_name*.  If the stage is unavailable or the walk
    fails, returns a fallback path and logs a warning — never silently
    swallows exceptions.
    """
    fallback = f"/materials/{desired_name}"
    try:
        matlib_node.cook(force=True)
        stage = matlib_node.stage()
        if stage is None:
            _log.warning(
                "_query_material_usd_path: stage is None after cooking %s — "
                "using fallback path %s",
                matlib_node.path(), fallback,
            )
            return fallback

        from pxr import UsdShade

        materials_prim = stage.GetPrimAtPath("/materials")
        if not materials_prim or not materials_prim.IsValid():
            _log.warning(
                "_query_material_usd_path: /materials prim not found on %s — "
                "using fallback path %s",
                matlib_node.path(), fallback,
            )
            return fallback

        for child in materials_prim.GetChildren():
            child_path = str(child.GetPath())
            if UsdShade.Material(child).GetPrim().IsValid():
                if desired_name in child_path:
                    return child_path

        _log.warning(
            "_query_material_usd_path: no material matching '%s' found "
            "under /materials on %s — using fallback path %s",
            desired_name, matlib_node.path(), fallback,
        )
        return fallback
    except Exception as exc:
        _log.warning(
            "_query_material_usd_path: stage query failed on %s: %s — "
            "using fallback path %s",
            matlib_node.path(), exc, fallback,
        )
        return fallback


def _validate_prim_pattern(stage, pattern: str) -> Tuple[bool, str]:
    """Check whether *pattern* resolves to any prims on *stage*.

    Returns ``(is_valid, message)`` where *message* contains suggestions
    when the pattern does not match.  Never silently swallows exceptions.
    """
    if stage is None:
        return False, "Stage is not available — cannot validate prim pattern"

    if pattern.startswith("/**"):
        return True, ""

    try:
        test_prim = stage.GetPrimAtPath(pattern)
        if test_prim and test_prim.IsValid():
            return True, ""

        suggestions = _suggest_prim_paths(stage, pattern)
        msg = f"Couldn't find a prim at '{pattern}'"
        if suggestions:
            msg += f" -- did you mean one of these?{suggestions}"
        else:
            msg += " -- double-check the path on the USD stage"
        return False, msg
    except Exception as exc:
        _log.warning(
            "_validate_prim_pattern: error validating '%s': %s", pattern, exc,
        )
        return False, f"Could not validate pattern '{pattern}': {exc}"


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
        category = resolve_param(payload, "category", required=False)
        preset_name = resolve_param(payload, "preset", required=False)
        shader_type = resolve_param_with_default(
            payload, "shader_type", "mtlxstandard_surface"
        )

        # Resolve preset defaults — explicit params override preset values
        preset_vals = {}
        if preset_name:
            if preset_name not in MATERIAL_PRESETS:
                available = ", ".join(sorted(MATERIAL_PRESETS.keys()))
                raise ValueError(
                    f"Unknown preset '{preset_name}'. "
                    f"Available presets: {available}"
                )
            preset_vals = dict(MATERIAL_PRESETS[preset_name])

        # Explicit params from payload (override preset)
        base_color = resolve_param(payload, "base_color", required=False)
        metalness = resolve_param(payload, "metalness", required=False)
        roughness = resolve_param(payload, "roughness", required=False)
        opacity = resolve_param(payload, "opacity", required=False)
        emission = resolve_param(payload, "emission", required=False)
        emission_color = resolve_param(payload, "emission_color", required=False)
        subsurface = resolve_param(payload, "subsurface", required=False)
        subsurface_color = resolve_param(payload, "subsurface_color", required=False)
        transmission = resolve_param(payload, "transmission", required=False)
        coat = resolve_param(payload, "coat", required=False)
        coat_roughness = resolve_param(payload, "coat_roughness", required=False)
        ior = resolve_param(payload, "ior", required=False)

        from .main_thread import run_on_main

        def _apply_shader_parm(shader, parm_name, value):
            """Set a scalar or color parm on a shader node."""
            if value is None:
                return
            if isinstance(value, (list, tuple)) and len(value) >= 3:
                for i, ch in enumerate(("r", "g", "b")):
                    p = shader.parm(f"{parm_name}{ch}")
                    if p:
                        p.set(float(value[i]))
            else:
                p = shader.parm(parm_name)
                if p:
                    p.set(float(value))

        def _on_main():
            node = self._resolve_lop_node(node_path_arg)  # type: ignore[attr-defined]

            parent = node.parent()

            # Create materiallibrary node and wire it after the resolved LOP node
            matlib = parent.createNode("materiallibrary", name)
            matlib.setInput(0, node)
            matlib.moveToGoodPosition()

            # Set material path prefix for category-based organization
            # e.g. category="metal" -> /materials/metal/{name}
            if category:
                prefix_parm = matlib.parm("matpathprefix")
                if prefix_parm:
                    prefix_parm.set(f"/materials/{category}")

            # Cook the matlib so its internal network is ready for child creation
            matlib.cook(force=True)

            # Create shader node inside the materiallibrary
            shader = matlib.createNode(shader_type, name + "_shader")
            if shader is None:
                raise RuntimeError(
                    f"Couldn't create a '{shader_type}' shader inside the material library "
                    "-- check that this shader type is available in your Houdini build"
                )

            # Apply preset defaults first (if any), then explicit overrides
            for parm_name, val in preset_vals.items():
                _apply_shader_parm(shader, parm_name, val)

            # Explicit params override preset values
            _apply_shader_parm(shader, "base_color", base_color)
            _apply_shader_parm(shader, "metalness", metalness)
            _apply_shader_parm(shader, "specular_roughness", roughness)
            _apply_shader_parm(shader, "opacity", opacity)
            _apply_shader_parm(shader, "emission", emission)
            _apply_shader_parm(shader, "emission_color", emission_color)
            _apply_shader_parm(shader, "subsurface", subsurface)
            _apply_shader_parm(shader, "subsurface_color", subsurface_color)
            _apply_shader_parm(shader, "transmission", transmission)
            _apply_shader_parm(shader, "coat", coat)
            _apply_shader_parm(shader, "coat_roughness", coat_roughness)
            _apply_shader_parm(shader, "specular_IOR", ior)

            material_usd_path = _query_material_usd_path(matlib, name)

            result = {
                "matlib_path": matlib.path(),
                "shader_path": shader.path(),
                "material_usd_path": material_usd_path,
                "shader_type": shader_type,
                "name": name,
            }
            if category:
                result["category"] = category
            if preset_name:
                result["preset"] = preset_name
            return result

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

            result = {
                "node_path": assign_node.path(),
                "prim_pattern": prim_pattern,
                "material_path": material_path,
            }

            upstream_stage = node.stage()
            is_valid, message = _validate_prim_pattern(upstream_stage, prim_pattern)
            if not is_valid and message:
                result["warning"] = message

            return result

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
                _, message = _validate_prim_pattern(stage, prim_path)
                raise ValueError(
                    message or f"Couldn't find a prim at '{prim_path}'"
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

            material_usd_path = _query_material_usd_path(matlib, name)

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

                matlib_stage = matlib.stage()
                is_valid, message = _validate_prim_pattern(matlib_stage, geo_pattern)
                if not is_valid and message:
                    result["warning"] = message

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
