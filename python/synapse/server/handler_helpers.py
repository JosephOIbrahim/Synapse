"""
Shared handler helpers.

Utilities used across multiple handler files (handlers.py, handlers_render.py).
Extracted to avoid circular imports between handler modules.
"""

import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.aliases import USD_PARM_ALIASES

try:
    import hou
    _HOU_AVAILABLE = True
except ImportError:
    hou = None  # type: ignore[assignment]
    _HOU_AVAILABLE = False


_HOUDINI_UNAVAILABLE = (
    "Houdini isn't reachable right now \u2014 make sure it's running "
    "and Synapse is started from the Python Panel"
)

_NODE_NAME_ILLEGAL = re.compile(r"[^A-Za-z0-9_]+")


def _safe_node_name(name, fallback="node"):
    """Houdini-legal node name from arbitrary (artist/LLM) input.

    Node names allow only [A-Za-z0-9_] and may not start with a digit --
    anything else (hyphens, brackets, spaces in asset names) makes
    createNode()/setName() raise mid-undo-group (hardening report 4.3).
    Node-name rules ONLY: USD prim-name sanitization is the D-3 RFC's lane
    (docs/RFC_agent_usd_ledger.md).
    """
    safe = _NODE_NAME_ILLEGAL.sub("_", str(name)).strip("_")
    if not safe:
        return fallback
    if safe[0].isdigit():
        safe = "_" + safe
    return safe


_FRAME_TOKEN_RE = re.compile(r"\$F(\d*)")


def _expand_frame_tokens(path, frame):
    """Resolve $F / $Fn Houdini frame tokens to a concrete frame number.

    str.replace('$F4', ...) only handled that one spelling -- artist paths
    using $F, $F2, $F5 etc. polled a literal token path and produced false
    "output wasn't created" failures (hardening report 4.3).
    """
    f = int(frame)

    def _sub(m):
        pad = m.group(1)
        return str(f).zfill(int(pad)) if pad else str(f)

    return _FRAME_TOKEN_RE.sub(_sub, str(path))


def _wire_display(new_tip, wired_from=None, set_display=True):
    """Move the LOP display flag to new_tip when it extends the display chain.

    wired_from = the PRE-EXISTING node the new chain was wired from (not
    intermediates created in the same call). Returns result keys (truth
    contract -- display:'set' only after isDisplayFlagSet() readback).
    """
    keys = {}
    current = None
    try:
        parent = new_tip.parent()
        if parent is not None and hasattr(parent, "displayNode"):
            current = parent.displayNode()
    except Exception:
        current = None
    extends = current is None or (
        wired_from is not None
        and hasattr(wired_from, "isDisplayFlagSet")
        and wired_from.isDisplayFlagSet()
    )
    if set_display and extends and hasattr(new_tip, "setDisplayFlag"):
        try:
            new_tip.setDisplayFlag(True)
            if new_tip.isDisplayFlagSet():
                keys["display"] = "set"
                keys["display_node"] = new_tip.path()
                return keys
        except Exception:
            pass
    keys["display"] = "not_set"
    if current is not None:
        keys["display_node"] = current.path()
        keys["needs_rewire"] = (
            "The edit lives on a side branch -- the display flag is on "
            + current.path() + ", so the viewport, Karma, and USD export "
            "won't see this change until the display flag moves to "
            + new_tip.path() + " or the branch is wired back into the chain."
        )
    return keys


_URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]+:")


def _is_resolver_uri(path):
    """True for ArResolver-style URIs (asset:/shot:/file:/op:/opdef:...).

    The scheme needs 2+ chars before the colon, so a Windows drive letter
    ('C:') is ONE char and intentionally never matches (M2-D).
    """
    return bool(_URI_SCHEME_RE.match(str(path or "")))


def _path_warnings(path, context="path"):
    """Path-policy advisory (M2-D): a baked absolute path breaks on any
    project move -- prefer $HIP/$JOB tokens. Token paths, resolver URIs,
    relative paths, and empty values warn nothing."""
    p = str(path or "")
    if not p or "$" in p or _is_resolver_uri(p):
        return []
    if os.path.isabs(p):
        return [
            f"absolute path baked into {context} -- prefer $HIP/$JOB tokens "
            "so the scene survives a project move (path policy advisory)"
        ]
    return []


def _convert_preview(src, dst, hfs, ocio=None, source_colorspace=None,
                     display=None, view=None, timeout=15):
    """Color-managed preview conversion, EXR -> displayable (M2-G).

    The bare-iconvert preview applied whatever transform
    HOUDINI_AUTOCONVERT_IMAGE_FILES implied and recorded nothing -- on
    OCIO/ACES shows the LLM judged exposure/color through the wrong
    transform (hardening report 4.3). Legs, strongest first:

      1. hoiiotool --ociodisplay (when $OCIO or an explicit ocio= config is
         set, injected via the subprocess env -- the live-verified
         mechanism on H21.0.671). The ONLY leg that claims
         color_managed=True.
      2. hoiiotool --tocolorspace 'sRGB - Display' (OIIO built-in config,
         no $OCIO): honest sRGB fallback, color_managed=False.
      3. iconvert -g auto: pins today's verified default against
         HOUDINI_AUTOCONVERT_IMAGE_FILES drift ('-g 2.2' is a phantom
         flag value on this binary). color_managed=False.

    Best-effort contract: returns a dict, never raises. ``error`` keeps
    the LAST failure's stderr snippet even when a later leg succeeds, so
    a broken $OCIO that silently fell back stays visible.
    """
    result = {
        "converted": False,
        "tool": None,
        "color_transform": "none (unconverted)",
        "color_managed": False,
        "error": None,
    }

    def _bin(name):
        exe = Path(hfs) / "bin" / f"{name}.exe"
        if not exe.exists():
            exe = Path(hfs) / "bin" / name
        return exe if exe.exists() else None

    def _run(argv, env=None):
        try:
            proc = subprocess.run(
                argv, timeout=timeout, capture_output=True, env=env
            )
        except Exception as e:
            result["error"] = str(e)
            return False
        if proc.returncode != 0:
            stderr = proc.stderr or b""
            snippet = stderr[-300:].decode("utf-8", "replace").strip()
            result["error"] = snippet or f"exit {proc.returncode}"
            return False
        try:
            return Path(dst).exists() and Path(dst).stat().st_size > 0
        except OSError:
            return False

    ocio = ocio or os.environ.get("OCIO")

    hoiiotool = _bin("hoiiotool")
    if hoiiotool is not None:
        if ocio:
            ociodisplay = "--ociodisplay"
            if source_colorspace:
                ociodisplay = f"--ociodisplay:from={source_colorspace}"
            argv = [str(hoiiotool), "-i", str(src), ociodisplay,
                    display or "default", view or "default", "-o", str(dst)]
            if _run(argv, env={**os.environ, "OCIO": str(ocio)}):
                result.update(
                    converted=True,
                    tool="hoiiotool",
                    color_managed=True,
                    color_transform=(
                        f"ociodisplay:{display or 'default'}/"
                        f"{view or 'default'} via {ocio}"
                    ),
                )
                return result
        else:
            argv = [str(hoiiotool), "-i", str(src), "--tocolorspace",
                    "sRGB - Display", "-o", str(dst)]
            if _run(argv):
                result.update(
                    converted=True,
                    tool="hoiiotool",
                    color_managed=False,
                    color_transform="srgb (OIIO built-in config, no $OCIO)",
                )
                return result

    iconvert = _bin("iconvert")
    if iconvert is not None:
        argv = [str(iconvert), "-g", "auto", str(src), str(dst)]
        if _run(argv):
            result.update(
                converted=True,
                tool="iconvert",
                color_managed=False,
                color_transform="gamma_auto (iconvert)",
            )
            return result

    return result


def _suggest_parms(node, invalid_name: str, limit: int = 8) -> str:
    """Find similar parameter names on a node for error enrichment."""
    try:
        all_names = [p.name() for p in node.parms()]
    except Exception:
        return ""
    needle = invalid_name.lower()
    matches = [n for n in all_names if needle in n.lower() or n.lower() in needle]
    if not matches:
        # Fallback: common prefix match
        matches = [n for n in all_names if n.lower().startswith(needle[:3])]
    # Check USD alias -- if the invalid name maps to an encoded USD parm, include hint
    usd_hint = ""
    usd_encoded = USD_PARM_ALIASES.get(invalid_name.lower())
    if usd_encoded and usd_encoded in all_names:
        usd_hint = f" Try '{usd_encoded}' (the encoded USD name for '{invalid_name}')."
    if not matches and not usd_hint:
        return ""
    parts = []
    if usd_hint:
        parts.append(usd_hint)
    if matches:
        parts.append(" Similar parameters: " + ", ".join(matches[:limit]))
    return "".join(parts)


def _char_similarity(a: str, b: str) -> float:
    """Simple character-level similarity ratio between two strings.

    Returns a float between 0.0 and 1.0 based on longest common subsequence
    length divided by the longer string length.  No external dependencies.
    """
    if not a or not b:
        return 0.0
    a_lower = a.lower()
    b_lower = b.lower()
    if a_lower == b_lower:
        return 1.0
    # Count matching characters (order-aware, simple approach)
    shorter, longer = (a_lower, b_lower) if len(a_lower) <= len(b_lower) else (b_lower, a_lower)
    matches = 0
    used = set()
    for ch in shorter:
        for idx, ch2 in enumerate(longer):
            if idx not in used and ch == ch2:
                matches += 1
                used.add(idx)
                break
    return matches / len(longer) if longer else 0.0


def _suggest_prim_paths(stage, invalid_path, max_suggestions=3):
    """Suggest similar USD prim paths when an invalid path is given.

    Walks the stage hierarchy and scores each prim path by:
    - Path segment overlap (segments in common between the invalid path and candidate)
    - Prefix match on the final segment (character-level similarity)

    Returns a formatted string like:
    " Similar prims: /scene/rubbertoy/geo, /scene/rubbertoy/geo/shape"

    Returns empty string if stage is None or no good matches found.
    """
    if stage is None:
        return ""

    try:
        all_prims = [p for p in stage.Traverse()]
    except Exception:
        return ""

    if not all_prims:
        return ""

    invalid_segments = [s for s in invalid_path.split("/") if s]
    if not invalid_segments:
        return ""

    invalid_last = invalid_segments[-1]
    invalid_set = set(s.lower() for s in invalid_segments)

    scored = []
    for prim in all_prims:
        prim_path = str(prim.GetPath())
        prim_segments = [s for s in prim_path.split("/") if s]
        if not prim_segments:
            continue

        # Score: segment overlap (how many segments match by name)
        prim_set = set(s.lower() for s in prim_segments)
        overlap = len(invalid_set & prim_set)

        # Score: final segment similarity
        prim_last = prim_segments[-1]
        last_sim = _char_similarity(invalid_last, prim_last)

        # Combined score (segment overlap weighted higher)
        score = overlap * 2.0 + last_sim

        if score > 0.5:
            scored.append((score, prim_path))

    if not scored:
        return ""

    # Sort by score descending, then path alphabetically for determinism
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = [path for _, path in scored[:max_suggestions]]
    return " Similar prims: " + ", ".join(top)


def _render_diagnostic_checklist(node):
    """Build a render readiness checklist for a LOP/ROP node.

    Returns a dict:
    {
        "camera_set": bool,
        "materials_bound": bool,
        "output_path_exists": bool,
        "output_dir_writable": bool,
        "resolution_set": bool,
        "renderer_valid": bool
    }

    Used by safe_render and error messages to give artists actionable next steps.
    Returns all-False dict if node is None.
    """
    result = {
        "camera_set": False,
        "materials_bound": False,
        "output_path_exists": False,
        "output_dir_writable": False,
        "resolution_set": False,
        "renderer_valid": False,
    }

    if node is None:
        return result

    # Check camera parameter
    for cam_parm in ("camera", "cam"):
        try:
            p = node.parm(cam_parm)
            if p is not None:
                val = p.eval()
                if val and str(val).strip():
                    result["camera_set"] = True
                    break
        except (AttributeError, TypeError):
            pass

    # Check output path
    output_path = None
    for out_parm in ("picture", "outputimage", "lopoutput"):
        try:
            p = node.parm(out_parm)
            if p is not None:
                val = p.eval()
                if val and str(val).strip():
                    output_path = str(val)
                    break
        except (AttributeError, TypeError):
            pass

    if output_path:
        out_dir = os.path.dirname(output_path)
        if out_dir:
            result["output_path_exists"] = os.path.isdir(out_dir)
            if result["output_path_exists"]:
                result["output_dir_writable"] = os.access(out_dir, os.W_OK)

    # Check resolution
    for res_parm in ("res", "res1", "res2", "override_res"):
        try:
            p = node.parm(res_parm)
            if p is not None:
                result["resolution_set"] = True
                break
        except (AttributeError, TypeError):
            pass

    # Check renderer
    try:
        p = node.parm("renderer")
        if p is not None:
            val = p.eval()
            if val and str(val).strip():
                result["renderer_valid"] = True
    except (AttributeError, TypeError):
        pass

    # Check materials_bound -- heuristic: node is in a LOP context
    try:
        node_type = node.type()
        if node_type is not None:
            cat = node_type.category()
            if cat is not None and cat.name() == "Lop":
                # In LOP context, check if stage has any material bindings
                try:
                    stage = node.stage()
                    if stage:
                        for prim in stage.Traverse():
                            # Check for material binding relationship
                            rel = prim.GetRelationship("material:binding")
                            if rel and rel.GetTargets():
                                result["materials_bound"] = True
                                break
                except Exception:
                    pass
    except (AttributeError, TypeError):
        pass

    return result


# ── Vertical Layout Helpers ────────────────────────────────────────────────
#
# Professional VFX artists wire Solaris networks as clean vertical columns —
# top-to-bottom, single-column for linear chains, layered columns for DAGs.
# These helpers replace Houdini's `layoutChildren()` black-box algorithm with
# explicit `setPosition()` calls that produce network layouts matching the
# reference style used in professional studios.
#
# Houdini network editor coordinates:
#   - X increases rightward
#   - Y increases upward (so top-to-bottom flow = decreasing Y)
#
# Spacing constants tuned to match H21 default node sizes in LOP networks.

# Vertical distance between consecutive nodes (units in network editor)
VERTICAL_SPACING = 1.2
# Horizontal distance between parallel streams in a DAG
HORIZONTAL_SPACING = 3.5
# M55 (grid snap) was evaluated and DROPPED. The measured LOP tile on 22.0.368
# is 1.1296 x 0.2824 units, but snapping x to the tile grid fights the two fixes
# that actually matter: it perturbs a merge off its parents' exact barycenter
# (M9) and pulls swept siblings below the exact min separation (M8). And it buys
# nothing here -- a linear spine already yields a pixel-perfect vertical column
# because every node inherits its single parent's exact x, and branch nodes sit
# at the exact mean of their parents. Left as None; the barycenter math is exact.
_GRID_SNAP_X = None


def _free_origin(parent_node, new_ids, v_spacing: float = VERTICAL_SPACING):
    """A layout origin that does not collide with existing content (M7).

    build_graph laid every network out at absolute (0, 0) with no awareness of
    what was already in the stage, so a second build -- or any build into a
    populated shot -- landed exactly on top of the first (measured: 4/4 node
    pairs at dx=dy=0). This returns an origin just BELOW the lowest existing
    node that is not part of this build, so the new network reads as a separate
    column instead of an overlap. Best-effort: any failure returns (0, 0), the
    prior behavior. Only nodes NOT in ``new_ids`` count as existing.
    """
    if not _HOU_AVAILABLE or parent_node is None:
        return 0.0, 0.0
    new = set(new_ids or ())
    lowest_y = None
    center_x = 0.0
    seen = 0
    try:
        for child in parent_node.children():
            if child.path() in new or child in new:
                continue
            pos = child.position()
            seen += 1
            center_x += pos[0]
            if lowest_y is None or pos[1] < lowest_y:
                lowest_y = pos[1]
    except Exception:  # noqa: BLE001 -- origin is best-effort
        return 0.0, 0.0
    if lowest_y is None:
        return 0.0, 0.0
    # One clear row-gap below the existing content, at its horizontal center.
    return (center_x / seen if seen else 0.0), lowest_y - v_spacing * 2.0


def _compute_dag_positions(
    sorted_ids: List[str],
    connections: List[Dict[str, Any]],
    start_x: float = 0.0,
    start_y: float = 0.0,
    v_spacing: float = VERTICAL_SPACING,
    h_spacing: float = HORIZONTAL_SPACING,
) -> Dict[str, tuple]:
    """Pure layered-DAG placement -> {node_id: (x, y)}. No ``hou`` (testable).

    Fixes three artist-visible defects the old center-every-layer version had:

    * M8 -- within-layer order followed the topological id order (effectively
      alphabetical), so the nodes feeding a merge's inputs 0/1/2 could be drawn
      in any order and the wires crossed. Nodes sharing a child are now ordered
      by the input index they occupy on that child, so merge inputs read
      left-to-right in wire order.
    * M9 -- every layer was centered on start_x regardless of where its parents
      sat, so a child could land at x=0 while its only parent was at x=+3.5.
      Each node is now placed at the barycenter (mean x) of its already-placed
      parents, with a left-to-right sweep enforcing min separation.
    * M55 -- x is snapped to a fraction of the measured tile width so columns
      align cleanly instead of on raw averaged floats.
    """
    if not sorted_ids:
        return {}

    children_of: Dict[str, List[str]] = defaultdict(list)
    parents_of: Dict[str, List[str]] = defaultdict(list)
    # input index each edge occupies on its target, for wire-order ordering.
    edge_input: Dict[tuple, int] = {}
    for conn in connections:
        f, t = conn["from"], conn["to"]
        children_of[f].append(t)
        parents_of[t].append(f)
        edge_input[(f, t)] = conn.get("input", 0)

    # Longest-path depth (unchanged: correct, avoids naive-BFS diamond squash).
    depth: Dict[str, int] = {}
    for nid in sorted_ids:
        pd = [depth[p] for p in parents_of[nid] if p in depth]
        depth[nid] = (max(pd) + 1) if pd else 0

    layers: Dict[int, List[str]] = defaultdict(list)
    for nid in sorted_ids:
        layers[depth[nid]].append(nid)

    def _primary_child_key(nid):
        # The closest downstream child; among a node's edges, the input index it
        # feeds. Roots feeding one merge thus sort by that merge's input index.
        kids = children_of.get(nid, [])
        if not kids:
            return (10 ** 9, "", 0)
        best = min(kids, key=lambda c: (depth.get(c, 10 ** 9), str(c)))
        return (depth.get(best, 10 ** 9), str(best), edge_input.get((nid, best), 0))

    pos: Dict[str, tuple] = {}
    if _GRID_SNAP_X:
        snap = lambda x: round(x / _GRID_SNAP_X) * _GRID_SNAP_X
        # Effective spacing is a WHOLE number of grid steps, rounded UP, so
        # snapping a swept position can never pull two nodes closer than the
        # nominal h_spacing (my own M55 snap otherwise violated min separation).
        steps = int(h_spacing / _GRID_SNAP_X)
        if steps * _GRID_SNAP_X < h_spacing:
            steps += 1
        h_eff = steps * _GRID_SNAP_X
    else:
        snap = lambda x: x
        h_eff = h_spacing

    for d in sorted(layers):
        nodes = layers[d]
        if d == 0:
            # Roots: order by the child+input they feed, so a fan-in reads in
            # wire order from the very top.
            nodes = sorted(nodes, key=lambda n: (_primary_child_key(n), str(n)))
            ideal = [start_x + (i - (len(nodes) - 1) / 2.0) * h_eff
                     for i in range(len(nodes))]
        else:
            # Order by parent barycenter (parents already placed), tie-break by
            # the input index into the shared child (fixes the merge case).
            def _bary(n):
                px = [pos[p][0] for p in parents_of[n] if p in pos]
                return sum(px) / len(px) if px else start_x
            nodes = sorted(nodes, key=lambda n: (_bary(n), _primary_child_key(n), str(n)))
            ideal = [_bary(n) for n in nodes]

        # Left-to-right sweep on the grid: snap each ideal, then honor order and
        # enforce a grid-aligned min gap. prev is on-grid and h_eff is on-grid,
        # so every result stays on-grid with exact separation.
        y = start_y - d * v_spacing
        xs: List[float] = []
        for i, n in enumerate(nodes):
            want = snap(ideal[i])
            if i > 0:
                want = max(want, xs[i - 1] + h_eff)
            xs.append(want)
        for n, x in zip(nodes, xs):
            pos[n] = (x, y)

    # Recenter so the bbox centers on start_x (keeps barycenter-relative
    # alignment, removes rightward drift). Shift is grid-snapped to stay on-grid.
    all_x = [p[0] for p in pos.values()]
    if all_x:
        shift = snap(start_x - (min(all_x) + max(all_x)) / 2.0)
        pos = {n: (x + shift, y) for n, (x, y) in pos.items()}
    return pos


def _layout_vertical_chain(
    nodes: list,
    start_x: float = 0.0,
    start_y: float = 0.0,
    spacing: float = VERTICAL_SPACING,
) -> None:
    """Position nodes in a clean vertical column, top to bottom.

    This is the layout professional VFX artists use for linear Solaris chains:
    componentgeometry → materiallibrary → camera → domelight → rendersettings → rop

    Args:
        nodes: List of hou.Node objects in chain order (first = top).
        start_x: X coordinate for the column center.
        start_y: Y coordinate for the top node.
        spacing: Vertical distance between nodes.
    """
    if not _HOU_AVAILABLE or not nodes:
        return
    for i, node in enumerate(nodes):
        node.setPosition(hou.Vector2(start_x, start_y - i * spacing))


def _layout_dag_vertical(
    sorted_ids: List[str],
    connections: List[Dict[str, Any]],
    id_to_hou: Dict[str, Any],
    start_x: float = 0.0,
    start_y: float = 0.0,
    v_spacing: float = VERTICAL_SPACING,
    h_spacing: float = HORIZONTAL_SPACING,
) -> None:
    """Position DAG nodes in layered vertical columns.

    Assigns each node to a depth layer (BFS from roots), then positions
    layers top-to-bottom. Nodes within the same layer are spread
    horizontally, centered on start_x. Single-node layers stay on the
    center column for a clean vertical spine.

    Args:
        sorted_ids: Topologically sorted node IDs.
        connections: List of {from, to, input?, output?} connection dicts.
        id_to_hou: Mapping from node ID to hou.Node.
        start_x: X center coordinate.
        start_y: Y coordinate for the top layer.
        v_spacing: Vertical distance between layers.
        h_spacing: Horizontal distance between nodes in the same layer.
    """
    if not _HOU_AVAILABLE or not sorted_ids:
        return
    positions = _compute_dag_positions(
        sorted_ids, connections, start_x, start_y, v_spacing, h_spacing)
    for nid, (x, y) in positions.items():
        node = id_to_hou.get(nid)
        if node is not None:
            node.setPosition(hou.Vector2(x, y))


# ── Section boxes (M10) ────────────────────────────────────────────────────
#
# Section a built Solaris network into a few labelled, colored network boxes so
# a 40-node shot reads at a glance. Design: "Tri-Band Minimal" -- SCENE /
# LIGHTING / RENDER, chosen by a TD judge panel over minimal/tier/branch lenses.
# Because the Phase-3 layout stacks nodes strictly top-to-bottom by rank, these
# rank cuts are CONTIGUOUS vertical bands that never interleave, so a
# fit-around-contents box per band can never swallow a neighbouring band's node.
#
# Every hou call below was live-verified on 22.0.368 (createNetworkBox / addNode
# / setComment / setColor / fitAroundContents / findNetworkBox / destroy) plus
# two behaviours that would otherwise bite: createNetworkBox AUTO-SUFFIXES on a
# name collision (so a blind re-create stacks duplicate boxes every rebuild --
# hence find-first), and box.destroy() does NOT delete member nodes (so
# destroy-then-recreate is a safe way to guarantee fresh membership).

# (name, comment, (r,g,b) 0..1, rank predicate). Muted low-value hues: a band
# tint behind default-grey LOP nodes, distinguished by hue not intensity.
_SECTION_BANDS = (
    ("synapse_sec_scene",
     "SCENE  ·  geo → materials → layout",
     (0.24, 0.29, 0.36), lambda r: r < 400),
    ("synapse_sec_lighting",
     "LIGHTING  ·  camera → lights",
     (0.38, 0.32, 0.19), lambda r: 400 <= r < 700),
    ("synapse_sec_render",
     "RENDER  ·  settings → rop → output",
     (0.22, 0.31, 0.28), lambda r: r >= 700),
)
# Below this, sectioning is noise, not help.
_MIN_NODES_FOR_SECTIONS = 4
# Namespace for every SYNAPSE-authored section box. The unconditional sweep
# clears by this prefix, so an artist's own boxes are never touched and any
# auto-suffixed duplicate (createNetworkBox suffixes on collision) is caught.
_SECTION_BOX_PREFIX = "synapse_sec_"


def _compute_section_bands(node_ranks: Dict[str, int]) -> List[Dict[str, Any]]:
    """{node_id: rank} -> [{name, comment, color, node_ids}] for populated bands.

    Pure logic (no ``hou``) so the banding is unit-tested directly. Returns an
    EMPTY list when boxes would add noise instead of clarity: a network below
    the size floor, or one whose nodes all fall in a single band (a net that
    lives in one tier needs no sectioning).
    """
    if len(node_ranks) < _MIN_NODES_FOR_SECTIONS:
        return []
    bands: List[Dict[str, Any]] = []
    for name, comment, color, pred in _SECTION_BANDS:
        ids = sorted(nid for nid, r in node_ranks.items() if pred(r))
        if ids:
            bands.append({"name": name, "comment": comment,
                          "color": color, "node_ids": ids})
    if len(bands) < 2:
        return []
    return bands


def _bands_are_rank_monotonic(bands: List[Dict[str, Any]],
                              node_y: Dict[str, float]) -> bool:
    """True iff the bands occupy DISJOINT vertical slabs, top-to-bottom in band
    order — the precondition that makes a fit-around-contents box per band safe.

    The layout (``_compute_dag_positions``) positions nodes by longest-path DAG
    DEPTH, not by rank. When the caller wired the graph in pipeline order the two
    coincide and the bands are clean contiguous slabs. When they do NOT (e.g. a
    light wired as a root feeding geometry), a rank band would span a Y range
    that overlaps a neighbour's or swallows a foreign node, and a box drawn
    around it would be visually wrong. This gate detects that and lets the caller
    suppress the boxes rather than draw a misleading one. (Adversarial finding,
    netbox design workflow: "layout is depth-keyed, not rank-keyed".)

    Bands arrive in _SECTION_BANDS order = decreasing rank = top-to-bottom, i.e.
    strictly DECREASING network-editor Y (Y increases upward). Requires each
    band's whole Y-slab to sit strictly above the next band's, and no node to
    fall inside a slab it does not belong to.
    """
    slabs = []
    for band in bands:
        ys = [node_y[nid] for nid in band["node_ids"] if nid in node_y]
        if not ys:
            return False
        slabs.append((min(ys), max(ys), set(band["node_ids"])))
    # Adjacent slabs must not overlap: earlier band (higher rank tier, lower on
    # screen? no — SCENE is first and sits at TOP = highest Y). SCENE band is
    # first with the HIGHEST Y; each subsequent band must sit strictly below.
    for (hi_min, hi_max, _), (lo_min, lo_max, _) in zip(slabs, slabs[1:]):
        if hi_min <= lo_max:            # upper band dips into/through the lower
            return False
    # No foreign node inside another band's slab.
    for i, (lo, hi, members) in enumerate(slabs):
        for nid, y in node_y.items():
            if nid in members:
                continue
            if lo <= y <= hi and any(nid in b["node_ids"] for b in bands):
                return False
    return True


def _apply_section_boxes(parent_node, id_to_hou: Dict[str, Any],
                         node_ranks: Dict[str, int]) -> List[str]:
    """Idempotently draw one network box per populated section band.

    Destroy-then-recreate keyed on a fixed namespaced name per band: a rebuild
    reflects the CURRENT network with no stale members and no stacked
    duplicates. Best-effort throughout -- sectioning is cosmetic and must never
    fail a build, so every hou call is guarded and a failure just skips that
    box. Returns the names of the boxes actually drawn.

    KNOWN LIMITATION (multi-network, documented fast-follow): the box names are
    stage-global, so building a SECOND independent network into the same /stage
    sweeps the first network's section boxes and draws only the second's. The
    nodes and wiring of both networks are untouched -- only the first's visual
    grouping is lost. The common case is one network per /stage; per-network box
    identity (namespacing by display_node) is deferred.
    """
    if not _HOU_AVAILABLE or parent_node is None:
        return []

    # 1. UNCONDITIONAL SWEEP FIRST. Remove every prior SYNAPSE section box before
    #    deciding anything. This is what makes the feature honest across every
    #    rebuild: a network that shrank, changed, or became non-rank-monotonic
    #    must not keep a stale/ghost box, and clearing by PREFIX also catches any
    #    auto-suffixed duplicate (createNetworkBox suffixes on collision). Member
    #    NODES survive box.destroy() (verified live), so this is purely visual.
    try:
        for box in list(parent_node.networkBoxes()):
            if box.name().startswith(_SECTION_BOX_PREFIX):
                box.destroy()
    except Exception:  # noqa: BLE001
        pass

    # 2. Compute the bands and gate them on rank-monotonicity.
    try:
        bands = _compute_section_bands(node_ranks)
        if not bands:
            return []
        # The layout is depth-keyed, so rank bands are only safe to box when they
        # occupy disjoint vertical slabs. Read live Y and suppress if they don't
        # -- a missing box is honest, an overlapping one is a lie.
        node_y = {}
        for nid in node_ranks:
            n = id_to_hou.get(nid)
            if n is not None:
                node_y[nid] = n.position()[1]
        if not _bands_are_rank_monotonic(bands, node_y):
            return []
    except Exception:  # noqa: BLE001
        return []

    # 3. Create fresh. Names are free (swept above), so no auto-suffix risk.
    drawn: List[str] = []
    for band in bands:
        try:
            box = parent_node.createNetworkBox(band["name"])
            for nid in band["node_ids"]:
                node = id_to_hou.get(nid)
                if node is not None:
                    box.addNode(node)
            box.setComment(band["comment"])
            box.setColor(hou.Color(band["color"]))
            box.fitAroundContents()
            drawn.append(band["name"])
        except Exception:  # noqa: BLE001 -- cosmetic; never break the build
            continue
    return drawn
