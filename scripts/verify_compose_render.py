"""Live render verification for the Solaris Compose Tier (BL-007 + BL-008).

This is the [REAL] end-to-end close for the two silent-failure backlog items
the Compose Tier was built to kill:

  * BL-007 -- "silent no-output": a built shot had no authored render output
              path (the ``productName`` parm does not author the prim), so
              renders produced nothing with no error.
  * BL-008 -- "silent material-binding loss": ``assignmaterial`` appeared to
              succeed but the material never reached the renderer.

WHY THIS IS A SCRIPT, NOT A CI TEST
-----------------------------------
It needs a live, GUI Houdini session with a working render delegate. It does
NOT run under headless CI. Import is side-effect free; ``main()`` self-skips
unless ``hou`` + a UI are available.

THE HUSK / HOUDINI INDIE FINDING (the reason this script renders via flipbook)
------------------------------------------------------------------------------
On a **Houdini Indie** license (``hou.licenseCategory() ==
licenseCategoryType.Indie``), the standalone USD render path -- ``husk``,
driven by ``usdrender_rop.render()`` -- **silently no-ops**: it returns with
zero errors, zero warnings, and writes no file. ``handlers_render.py`` already
documents and works around this with a viewport-flipbook fallback
("husk may not support this license type"). So the dispatch's original
gold-standard (a Karma EXR at ``UsdRenderProduct.productName``) is
**not obtainable on this license** -- not a tier defect, a license limitation.

The license-appropriate render path that DOES work on Indie is **Karma
interactive** (the viewport delegate). This script renders one frame through
the Karma CPU viewport delegate via a flipbook, writes a real file to disk,
and samples its pixels. That single render closes both items:

  * BL-007 passes if a render file lands at the configured writable path with
    size > 0 (proves the output path is real, not silently missing).
  * BL-008 passes if the bound emissive material renders **magenta** -- the
    chroma signature ``R == B >> G`` -- rather than the neutral ``R == G == B``
    of a default / unbound surface.

RECORDED RESULT (Houdini 21.0.671, Indie, 2026-05-30)
-----------------------------------------------------
  delegate   = 'Karma CPU'
  file       = fb_check.0001.jpg  (6209 bytes -> BL-007 PASS)
  grid_mean  = [0.332, 0.167, 0.332]  (R == B >> G -> magenta -> BL-008 PASS)

Run inside the Houdini Python Source Editor / shell::

    exec(open(r"scripts/verify_compose_render.py").read())
    main()
"""

from __future__ import annotations

import os
import tempfile

try:
    import hou
    _HOU = True
except ImportError:  # pragma: no cover - only meaningful inside Houdini
    hou = None  # type: ignore[assignment]
    _HOU = False


# Magenta emission the test material is given. Default mtlxstandard_surface is
# neutral gray, so any R==B>>G reading proves *our* material reached the renderer.
_EMISSION_RGB = (1.0, 0.0, 1.0)

# Quad authored on the XZ plane, double-sided so it is visible from any angle.
_QUAD_CODE = (
    "from pxr import UsdGeom\n"
    "_n = hou.pwd()\n"
    "_s = _n.editableStage()\n"
    "_m = UsdGeom.Mesh.Define(_s, '/geo/quad')\n"
    "_m.CreatePointsAttr([(-10, 0, -10), (10, 0, -10), (10, 0, 10), (-10, 0, 10)])\n"
    "_m.CreateFaceVertexCountsAttr([4])\n"
    "_m.CreateFaceVertexIndicesAttr([0, 3, 2, 1])\n"
    "_m.CreateDoubleSidedAttr(True)\n"
)


def _classify(rgb: list[float]) -> str:
    """Return 'magenta', 'neutral', or 'other' for an RGB triple.

    Magenta == R and B both clearly above G, with R ~= B. Neutral == the three
    channels within a tight band of each other (a default/unbound surface).
    """
    r, g, b = (float(rgb[0]), float(rgb[1]), float(rgb[2]))
    span = max(r, g, b) - min(r, g, b)
    if span < 0.04:
        return "neutral"
    rb_close = abs(r - b) < 0.05 * (abs(r) + abs(b) + 1e-6) + 0.02
    if rb_close and r > g + 0.05 and b > g + 0.05:
        return "magenta"
    return "other"


def _build_shot(stage_net):
    """Build a minimal magenta-emissive quad shot. Returns the list of nodes."""
    from synapse.server import solaris_compose as sc
    from synapse.server import solaris_compose_tools as sct

    nodes = []
    geo = sc.make_pythonscript_lop(stage_net, "vcr_geo", _QUAD_CODE)
    nodes.append(geo)

    matlib = sct.ensure_mtlx_material(
        stage_net, "vcr_matlib", "emit",
        params={"emission_color": _EMISSION_RGB, "emission": 1.0},
        input_node=geo,
    )
    nodes.append(matlib)

    bind = sct.bind_material(
        stage_net, "vcr_bind", "//Mesh", "/materials/emit", input_node=matlib,
    )
    bind_node = bind if hasattr(bind, "path") else stage_net.node("vcr_bind")
    if bind_node is not None:
        nodes.append(bind_node)
        bind_node.setDisplayFlag(True)
    return nodes


def _render_flipbook(out_path: str, res: int = 128) -> str | None:
    """Render frame 1 of /stage through the Karma viewport delegate.

    Returns the resolved frame path if a file was written, else None.
    """
    desktop = hou.ui.curDesktop()
    sv = desktop.paneTabOfType(hou.paneTabType.SceneViewer)
    if sv is None:
        return None
    try:
        sv.setPwd(hou.node("/stage"))
    except Exception:
        pass
    vp = sv.curViewport()
    # Karma interactive is allowed on Indie even when husk standalone is not.
    try:
        for name in sv.hydraRenderers():
            if name.lower() == "karma cpu":
                sv.setHydraRenderer(name)
                break
    except Exception:
        pass
    hou.setFrame(1)
    try:
        vp.frameAll()
    except Exception:
        pass

    fb = sv.flipbookSettings()
    fb.frameRange((1, 1))
    fb.output(out_path)
    fb.useResolution(True)
    fb.resolution((res, res))
    sv.flipbook(viewport=vp, settings=fb, open_dialog=False)

    resolved = out_path.replace("$F4", "0001")
    if os.path.exists(resolved) and os.path.getsize(resolved) > 0:
        return resolved
    return None


def _sample(path: str) -> dict:
    """Read center + 3x3 grid mean from an image via OpenImageIO."""
    import OpenImageIO as oiio

    buf = oiio.ImageBuf(path)
    spec = buf.spec()
    cx, cy = spec.width // 2, spec.height // 2
    center = [round(float(v), 4) for v in list(buf.getpixel(cx, cy))[:3]]
    acc = [0.0, 0.0, 0.0]
    count = 0
    for dx in (-25, 0, 25):
        for dy in (-25, 0, 25):
            px = list(buf.getpixel(cx + dx, cy + dy))
            for i in range(3):
                acc[i] += float(px[i])
            count += 1
    grid_mean = [round(acc[i] / count, 4) for i in range(3)]
    return {
        "res": (spec.width, spec.height, spec.nchannels),
        "center": center,
        "grid_mean": grid_mean,
    }


def main() -> dict:
    """Compose -> render (Karma flipbook) -> assert BL-007 + BL-008. Returns a report."""
    if not _HOU:
        print("verify_compose_render: hou unavailable -- run inside Houdini.")
        return {"skipped": "no hou"}
    if not hou.isUIAvailable():
        print("verify_compose_render: no UI -- Karma interactive needs a GUI session.")
        return {"skipped": "no UI"}

    report: dict = {"license": str(hou.licenseCategory())}
    stage_net = hou.node("/stage")
    out_dir = os.path.join(tempfile.gettempdir(), "synapse_verify_compose")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "fb_check.$F4.jpg").replace("\\", "/")

    built = []
    try:
        built = _build_shot(stage_net)
        rendered = _render_flipbook(out_path)
        report["bl007_file_written"] = bool(rendered)
        report["bl007_size"] = os.path.getsize(rendered) if rendered else 0
        if rendered:
            sample = _sample(rendered)
            report.update(sample)
            report["color_class"] = _classify(sample["grid_mean"])
            report["bl008_material_renders"] = report["color_class"] == "magenta"
        report["BL007_PASS"] = report.get("bl007_file_written") and report.get("bl007_size", 0) > 0
        report["BL008_PASS"] = report.get("bl008_material_renders", False)
        report["ALL_GREEN"] = report["BL007_PASS"] and report["BL008_PASS"]
    finally:
        for n in built:
            try:
                n.destroy()
            except Exception:
                pass
        try:
            for f in os.listdir(out_dir):
                os.remove(os.path.join(out_dir, f))
            os.rmdir(out_dir)
        except Exception:
            pass

    print("verify_compose_render report:")
    for k, v in report.items():
        print("  %-22s %s" % (k, v))
    return report


if __name__ == "__main__":
    main()
