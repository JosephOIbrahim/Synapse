"""
Synapse TOPS/PDG Handler Mixin -- Render Sequence

Auto-extracted from the monolith handlers_tops.py.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ...core.aliases import resolve_param, resolve_param_with_default
from ...core.determinism import round_float, kahan_sum, deterministic_uuid
from ..handler_helpers import _HOUDINI_UNAVAILABLE
from ._common import _run_in_main_thread_pdg, _ensure_tops_warm_standby, _MAX_MONITOR_EVENTS


def _validate_rendered_frames(
    output_dir: str,
    prefix: str,
    start_frame: int,
    end_frame: int,
    step: int,
) -> Dict[str, Any]:
    """Check the output directory for rendered frames and report gaps."""
    expected_frames = list(range(start_frame, end_frame + 1, step))
    expected_count = len(expected_frames)

    missing_frames: List[int] = []
    zero_size_frames: List[int] = []
    found_count = 0

    resolved_dir = output_dir
    if HOU_AVAILABLE:
        try:
            resolved_dir = hou.text.expandString(output_dir)
        except Exception:
            pass

    for frame in expected_frames:
        padded = str(frame).zfill(4)
        found = False
        for ext in ("exr", "png", "jpg", "tif", "tiff", "rat"):
            candidate = os.path.join(resolved_dir, f"{prefix}.{padded}.{ext}")
            if os.path.isfile(candidate):
                found = True
                if os.path.getsize(candidate) == 0:
                    zero_size_frames.append(frame)
                break
        if found:
            found_count += 1
        else:
            missing_frames.append(frame)

    return {
        "expected_frames": expected_count,
        "found_frames": found_count,
        "missing_frames": missing_frames,
        "zero_size_frames": zero_size_frames,
    }


class TopsRenderSequenceMixin:
    """Mixin providing TOPS/PDG render sequence handlers."""

    def _handle_tops_render_sequence(self, payload: Dict) -> Dict:
        """Single-call interface for rendering a frame sequence via TOPS/PDG.

        Creates (or reuses) a TOPS network that renders frames through Karma,
        then generates work items and starts the cook with monitoring.

        Behavior:
        1. Validate Solaris stage is renderable
        2. Check for existing TOPS network matching the request (idempotent)
        3. If none, create TOPS network: fetch node -> Karma ROP -> file output
        4. Set frame range, camera, render settings, output directory
        5. Generate work items for frame range
        6. Start cook with monitoring
        7. Return job_id for status queries

        All mutations are wrapped in undo groups for safety.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        start_frame = resolve_param(payload, "start_frame")
        end_frame = resolve_param(payload, "end_frame")
        step = resolve_param_with_default(payload, "step", 1)
        camera = resolve_param(payload, "camera", required=False)
        output_dir = resolve_param(payload, "output_dir", required=False)
        output_prefix = resolve_param_with_default(payload, "output_prefix", "render")
        rop_node = resolve_param(payload, "rop_node", required=False)
        topnet_path = resolve_param(payload, "topnet_path", required=False)
        pixel_samples = resolve_param(payload, "pixel_samples", required=False)
        resolution = resolve_param(payload, "resolution", required=False)
        blocking = resolve_param_with_default(payload, "blocking", False)
        aov_passes = resolve_param(payload, "aov_passes", required=False)

        # Validate frame range
        start_frame = int(start_frame)
        end_frame = int(end_frame)
        step = int(step)
        if step < 1:
            raise ValueError("Step must be at least 1")
        if end_frame < start_frame:
            raise ValueError(
                f"End frame ({end_frame}) is before start frame ({start_frame}) -- "
                "swap them or check your range"
            )

        total_frames = ((end_frame - start_frame) // step) + 1

        def _run():
            # 1. Validate Solaris stage is renderable
            stage_node = None
            if rop_node:
                stage_node = hou.node(rop_node)
                if stage_node is None:
                    raise ValueError(
                        f"Couldn't find the ROP node at {rop_node} -- "
                        "double-check the path exists"
                    )
            else:
                # Auto-discover: look for a display-flagged LOP node in /stage
                stage_container = hou.node("/stage")
                if stage_container is not None:
                    for child in stage_container.children():
                        if child.isDisplayFlagSet():
                            stage_node = child
                            break
                if stage_node is None:
                    raise ValueError(
                        "Couldn't find a renderable stage -- "
                        "make sure you have a display-flagged LOP node in /stage, "
                        "or pass rop_node explicitly"
                    )

            # 2. Check for existing TOPS network (idempotent)
            network_name = "synapse_render_seq"
            target_topnet = None

            if topnet_path:
                target_topnet = hou.node(topnet_path)
                if target_topnet is None:
                    raise ValueError(
                        f"Couldn't find a TOP network at {topnet_path} -- "
                        "double-check the path exists"
                    )
            else:
                # Look for existing synapse_render_seq topnet in /obj
                obj = hou.node("/obj")
                if obj is not None:
                    existing = obj.node(network_name)
                    if existing is not None and existing.type().category().name() == "TopNet":
                        target_topnet = existing

            created_network = False
            with hou.undos.group("SYNAPSE: TOPS render sequence"):
                if target_topnet is None:
                    # 3. Create TOPS network
                    obj = hou.node("/obj")
                    if obj is None:
                        raise RuntimeError(
                            "Couldn't access /obj context -- "
                            "this shouldn't happen in a normal Houdini scene"
                        )
                    target_topnet = obj.createNode("topnet", network_name)
                    target_topnet.moveToGoodPosition()
                    created_network = True

                # Ensure warm standby (scheduler)
                scheduler_info = _ensure_tops_warm_standby(target_topnet.path())

                # 4. Find or create ROP fetch + output nodes
                rop_fetch = None
                file_output = None

                for child in target_topnet.children():
                    child_type = child.type().name().lower()
                    if child_type == "ropfetch" and child.name() == "render_frames":
                        rop_fetch = child
                    elif child_type == "fileoutput" and child.name() == "output_files":
                        file_output = child

                if rop_fetch is None:
                    rop_fetch = target_topnet.createNode("ropfetch", "render_frames")
                    rop_fetch.moveToGoodPosition()

                # Configure ROP fetch
                rop_path = rop_node or stage_node.path()
                rop_parm = rop_fetch.parm("roppath")
                if rop_parm:
                    rop_parm.set(rop_path)

                # Set frame range on the TOP network
                range_parm = rop_fetch.parm("pdg_framerange")
                if range_parm:
                    range_parm.set("custom")

                f1_parm = rop_fetch.parm("f1")
                if f1_parm:
                    f1_parm.set(start_frame)
                f2_parm = rop_fetch.parm("f2")
                if f2_parm:
                    f2_parm.set(end_frame)
                f3_parm = rop_fetch.parm("f3")
                if f3_parm:
                    f3_parm.set(step)

                # Apply optional render settings to the ROP
                if rop_node or stage_node:
                    actual_rop = hou.node(rop_path)
                    if actual_rop is not None:
                        if camera:
                            cam_parm = actual_rop.parm("camera")
                            if cam_parm:
                                cam_parm.set(camera)
                        if pixel_samples is not None:
                            samples_parm = actual_rop.parm("samplesperpixel")
                            if samples_parm:
                                samples_parm.set(int(pixel_samples))
                        if resolution is not None:
                            if isinstance(resolution, list) and len(resolution) >= 2:
                                res_parm = actual_rop.parm("override_res")
                                if res_parm:
                                    res_parm.set("specific")
                                resx = actual_rop.parm("res_overridex")
                                resy = actual_rop.parm("res_overridey")
                                if resx:
                                    resx.set(int(resolution[0]))
                                if resy:
                                    resy.set(int(resolution[1]))

                # Set output directory if provided
                if output_dir:
                    actual_rop = hou.node(rop_path)
                    if actual_rop is not None:
                        pic_parm = actual_rop.parm("picture")
                        if pic_parm:
                            out_path = f"{output_dir}/{output_prefix}.$F4.exr"
                            pic_parm.set(out_path)
                        out_parm = actual_rop.parm("outputimage")
                        if out_parm:
                            out_path = f"{output_dir}/{output_prefix}.$F4.exr"
                            out_parm.set(out_path)

                # 4b. Configure AOV passes if requested
                if aov_passes and isinstance(aov_passes, list):
                    handler = getattr(self, "_handle_configure_render_passes", None)
                    if handler is not None:
                        try:
                            handler({"passes": aov_passes})
                        except Exception as exc:
                            _log.warning("AOV setup skipped: %s", exc)
                    else:
                        _log.warning(
                            "AOV setup skipped: _handle_configure_render_passes not available"
                        )

                # 5. Generate work items
                rop_fetch.generateStaticItems()
                pdg_node = rop_fetch.getPDGNode()
                item_count = len(pdg_node.workItems) if pdg_node else 0

                # 6. Start cook
                job_id = f"render-seq-{deterministic_uuid(f'tops_render_seq_{rop_path}_{start_frame}_{end_frame}')[:8]}"
                cook_status = "pending"

                cook_error = None
                if item_count > 0:
                    try:
                        rop_fetch.cook(block=bool(blocking))
                        cook_status = "cooked" if blocking else "cooking"
                    except Exception as e:
                        _log.error("PDG cook failed for %s: %s", rop_path, e)
                        cook_status = "error"
                        cook_error = str(e)

                # Build result
                result = {
                    "job_id": job_id,
                    "topnet": target_topnet.path(),
                    "rop_fetch": rop_fetch.path(),
                    "rop_path": rop_path,
                    "frame_range": {
                        "start": start_frame,
                        "end": end_frame,
                        "step": step,
                        "total_frames": total_frames,
                    },
                    "work_items_generated": item_count,
                    "status": cook_status,
                    "created_network": created_network,
                }
                if cook_error:
                    result["error"] = cook_error

                if scheduler_info:
                    result["scheduler"] = scheduler_info
                if camera:
                    result["camera"] = camera
                if output_dir:
                    result["output_dir"] = output_dir
                if aov_passes:
                    result["aov_passes"] = aov_passes

                # 7. Post-cook frame validation
                if blocking and cook_status == "cooked" and output_dir:
                    result["validation"] = _validate_rendered_frames(
                        output_dir, output_prefix, start_frame, end_frame, step,
                    )

                return result

        return _run_in_main_thread_pdg(_run)


    def _handle_tops_multi_shot(self, payload: Dict) -> Dict:
        """Create a TOPS network for multi-shot rendering.

        Accepts a list of shot definitions, creates per-shot work items with
        shot-specific attributes (camera, frame range, overrides), partitions
        results by shot name, and optionally encodes per-shot movies.

        Each shot becomes a work item in a genericgenerator, feeds into a
        ropfetch for rendering, then partitions by shot name.

        Returns a job_id for monitoring the cook.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        shots = resolve_param(payload, "shots")
        if not isinstance(shots, list) or len(shots) == 0:
            raise ValueError(
                "The 'shots' parameter should be a list of shot definitions, "
                "each with at least a 'name' field -- e.g. "
                "[{{\"name\": \"sq010_sh010\", \"frame_start\": 1001, \"frame_end\": 1048}}]"
            )

        # Validate each shot has a name
        for i, shot in enumerate(shots):
            if not isinstance(shot, dict) or "name" not in shot:
                raise ValueError(
                    f"Shot at index {i} is missing a 'name' field -- "
                    "each shot needs at least {{\"name\": \"shot_name\"}}"
                )

        topnet_path = resolve_param_with_default(payload, "topnet_path", None)
        renderer = resolve_param_with_default(payload, "renderer", "karma_xpu")
        output_dir = resolve_param_with_default(payload, "output_dir", "$HIP/render")
        camera_pattern = resolve_param_with_default(
            payload, "camera_pattern", "/cameras/{shot}_cam"
        )
        rop_node = resolve_param_with_default(payload, "rop_node", None)
        blocking = resolve_param_with_default(payload, "blocking", False)
        encode_movie = resolve_param_with_default(payload, "encode_movie", False)

        def _run():
            # Find or create TOP network
            target_topnet = None
            created_network = False

            if topnet_path:
                target_topnet = hou.node(topnet_path)
                if target_topnet is None:
                    raise ValueError(
                        f"Couldn't find a TOP network at {topnet_path} -- "
                        "double-check the path"
                    )
            else:
                # Auto-create in /tasks
                tasks_net = hou.node("/tasks")
                if tasks_net is None:
                    tasks_net = hou.node("/obj").createNode("topnet", "tasks")
                target_topnet = tasks_net.createNode("topnet", "multi_shot_render")
                created_network = True

            # Ensure scheduler exists
            scheduler_info = _ensure_tops_warm_standby(target_topnet.path())

            # 1. Create genericgenerator for shot work items
            gen_node = target_topnet.createNode("genericgenerator", "shot_generator")

            # Build the generation script that creates per-shot work items
            shot_defs_json = []
            for shot in sorted(shots, key=lambda s: s["name"]):
                shot_def = {
                    "name": shot["name"],
                    "frame_start": shot.get("frame_start", 1001),
                    "frame_end": shot.get("frame_end", 1048),
                    "camera": shot.get(
                        "camera",
                        camera_pattern.format(shot=shot["name"])
                    ),
                }
                if "overrides" in shot:
                    shot_def["overrides"] = shot["overrides"]
                shot_defs_json.append(shot_def)

            import json as _json
            shots_json_str = _json.dumps(shot_defs_json, sort_keys=True)

            gen_script = (
                "import json\n"
                "shots = json.loads('''" + shots_json_str + "''')\n"
                "for i, shot in enumerate(shots):\n"
                "    item = item_holder.addWorkItem(index=i)\n"
                "    item.setStringAttrib('shot_name', shot['name'])\n"
                "    item.setIntAttrib('frame_start', shot['frame_start'])\n"
                "    item.setIntAttrib('frame_end', shot['frame_end'])\n"
                "    item.setStringAttrib('camera', shot['camera'])\n"
                "    if 'overrides' in shot:\n"
                "        item.setStringAttrib('overrides_json', json.dumps(shot['overrides'], sort_keys=True))\n"
            )

            # Set the generation script on the genericgenerator
            script_parm = gen_node.parm("itemcount")
            if script_parm:
                script_parm.set(len(shots))

            # Apply the generation script for shot-specific attributes
            gen_script_parm = gen_node.parm("pythonscript")
            if gen_script_parm:
                gen_script_parm.set(gen_script)

            # 2. Create ropfetch for rendering
            rop_fetch = target_topnet.createNode("ropfetch", "render_shots")
            rop_fetch.setInput(0, gen_node)

            # Find or set the ROP path
            rop_path = rop_node
            if not rop_path:
                # Auto-discover: look for usdrender ROP in /out
                out_net = hou.node("/out")
                if out_net:
                    for child in out_net.children():
                        if child.type().name() in ("usdrender", "usdrender_rop"):
                            rop_path = child.path()
                            break
                if not rop_path:
                    rop_path = "/out/karma_rop"

            rop_parm = rop_fetch.parm("roppath")
            if rop_parm:
                rop_parm.set(rop_path)

            # 3. Create partition by shot name
            partition = target_topnet.createNode(
                "partitionbyattribute", "partition_by_shot"
            )
            partition.setInput(0, rop_fetch)
            attr_parm = partition.parm("partitionattribute")
            if attr_parm:
                attr_parm.set("shot_name")

            # 4. Optionally add ffmpeg encode per shot
            encode_node = None
            if encode_movie:
                encode_node = target_topnet.createNode(
                    "ffmpegencodevideo", "encode_per_shot"
                )
                encode_node.setInput(0, partition)

            # Layout the network
            target_topnet.layoutChildren()

            # 5. Generate work items
            gen_node.generateStaticItems()
            pdg_node = gen_node.getPDGNode()
            item_count = len(pdg_node.workItems) if pdg_node else 0

            # 6. Start cook if items were generated
            job_id = f"multi-shot-{deterministic_uuid(f'tops_multi_shot_{len(shots)}')[:8]}"
            cook_status = "pending"

            last_node = encode_node or partition
            cook_error = None
            if item_count > 0:
                try:
                    last_node.cook(block=bool(blocking))
                    cook_status = "cooked" if blocking else "cooking"
                except Exception as e:
                    _log.error("Multi-shot PDG cook failed: %s", e)
                    cook_status = "error"
                    cook_error = str(e)

            # Build result
            shot_summary = []
            for shot in sorted(shots, key=lambda s: s["name"]):
                shot_summary.append({
                    "name": shot["name"],
                    "camera": shot.get(
                        "camera",
                        camera_pattern.format(shot=shot["name"])
                    ),
                    "frame_start": shot.get("frame_start", 1001),
                    "frame_end": shot.get("frame_end", 1048),
                })

            result = {
                "job_id": job_id,
                "topnet": target_topnet.path(),
                "generator": gen_node.path(),
                "rop_fetch": rop_fetch.path(),
                "partition": partition.path(),
                "rop_path": rop_path,
                "shot_count": len(shots),
                "shots": shot_summary,
                "work_items_generated": item_count,
                "status": cook_status,
                "renderer": renderer,
                "output_dir": output_dir,
                "created_network": created_network,
            }

            if encode_node:
                result["encode_node"] = encode_node.path()
            if scheduler_info:
                result["scheduler"] = scheduler_info
            if cook_error:
                result["error"] = cook_error

            return result

        return _run_in_main_thread_pdg(_run)

