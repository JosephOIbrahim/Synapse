"""V1 / PROBE A — capture-verb class surfaces on the live Houdini build.

Answers Q1: what capture verbs exist? Method is R73's, not a keyword search:
**dump the COMPLETE member list of each class, then judge.** Reading the whole
list is the positive control that licenses an ABSENT verdict (R50/R58).

Boundary this probe declares BEFORE it runs (H3a-F5):
  * class surfaces (hou.SceneViewer, hou.FlipbookSettings, ...) DO resolve under
    headless hython even though instances cannot be obtained -> ABSENT is licensed
    for class members.
  * hou.ui and hou.qt are MODULES that do not exist headless -> every hou.ui.* /
    hou.qt.* verdict from this producer is UNVERIFIABLE, never ABSENT. They are
    settled by the live-GUI producer instead.

Controls (Law 1 — state the condition under which this fails):
  positive  hou.node (module fn), hou.Node.type (class attr), hou.undos.group
            (submodule attr), plus a NAMED per-class control on every class dumped.
  negative  the four quarantined phantoms (Article II), plus hou.ActiveRender and
            hou.activeRenders which R73 settled as absent-at-runtime, plus a
            synthetic name that cannot exist.
  FAILS IF  any positive control != EXISTS, or any negative control != ABSENT.
            controls_ok:false makes this file UNINTERPRETABLE and uncitable.

Writes JSON to stdout's companion path; mutates nothing.
"""

from __future__ import annotations

import json
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "probe_a_surfaces.json"

try:
    import hou  # type: ignore
    HOU = True
except Exception as exc:  # pragma: no cover - the no-hou mutation leg
    hou = None  # type: ignore
    HOU = False
    _IMPORT_ERR = repr(exc)

# --------------------------------------------------------------------------
# Controls
# --------------------------------------------------------------------------
POSITIVE = [
    ("hou.node", "module-level function resolution"),
    ("hou.Node.type", "class-attribute resolution"),
    ("hou.undos.group", "submodule-attribute resolution"),
]
NEGATIVE = [
    ("hou.pdg", "quarantined phantom (Article II)"),
    ("hou.secure", "quarantined phantom (Article II)"),
    ("hou.lopNetworks", "quarantined phantom (Article II)"),
    ("hou.updateGraphTick", "quarantined phantom (Article II)"),
    ("hou.ActiveRender", "R73: documented #status:ni, absent at runtime"),
    ("hou.activeRenders", "R73: documented #status:ni, absent at runtime"),
    ("hou.zzz_synthetic_capture_verb_that_cannot_exist", "synthetic"),
]

# Classes whose COMPLETE surface we dump, each with a NAMED same-class control.
# The control is a member independently expected to exist on THAT class; if it
# does not resolve, every ABSENT verdict on that class is void (R50).
CLASS_TARGETS = [
    ("hou.SceneViewer", "curViewport", "flipbook host"),
    ("hou.FlipbookSettings", "output", "what a flipbook writes"),
    ("hou.GeometryViewport", "name", "viewport grab candidates"),
    ("hou.GeometryViewportSettings", "camera", "viewport render state"),
    ("hou.RopNode", "render", "render-to-disk (H3a: no cancel verb)"),
    ("hou.CopNode", "type", "Copernicus buffer readback (OPEN SIDEFX ASK)"),
    ("hou.Cop2Node", "type", "legacy COP readback, for contrast"),
    ("hou.IPRViewer", "killRender", "R73-confirmed present; doubles as a control"),
    ("hou.LopNode", "stage", "USD render product access"),
    ("hou.Node", "type", "base-class surface, for inherited-vs-own separation"),
]

# Named candidates. Each is judged only if its class control passed.
CANDIDATES = [
    # --- flipbook -------------------------------------------------------
    ("hou.SceneViewer.flipbook", "hou.SceneViewer", False, "Q1 flipbook"),
    ("hou.SceneViewer.flipbookSettings", "hou.SceneViewer", False, "Q1 flipbook"),
    ("hou.SceneViewer.curViewport", "hou.SceneViewer", False, "Q1 flipbook"),
    ("hou.SceneViewer.viewports", "hou.SceneViewer", False, "Q1 flipbook"),
    ("hou.FlipbookSettings.output", "hou.FlipbookSettings", False, "Q1 what it writes"),
    ("hou.FlipbookSettings.outputToMPlay", "hou.FlipbookSettings", False, "Q1 what it writes"),
    ("hou.FlipbookSettings.useResolution", "hou.FlipbookSettings", False, "Q1"),
    ("hou.FlipbookSettings.resolution", "hou.FlipbookSettings", False, "Q1"),
    ("hou.FlipbookSettings.frameRange", "hou.FlipbookSettings", False, "Q1"),
    ("hou.FlipbookSettings.beautyPassOnly", "hou.FlipbookSettings", False, "Q1"),
    ("hou.FlipbookSettings.antialias", "hou.FlipbookSettings", False, "Q1"),
    ("hou.FlipbookSettings.renderAllViewports", "hou.FlipbookSettings", False, "Q1"),
    # --- viewport grab --------------------------------------------------
    ("hou.GeometryViewport.saveFrameBuffer", "hou.GeometryViewport", False, "Q1 viewport grab"),
    ("hou.GeometryViewport.frameBuffer", "hou.GeometryViewport", False, "Q1 viewport grab"),
    ("hou.GeometryViewport.snapshot", "hou.GeometryViewport", False, "Q1 viewport grab"),
    ("hou.GeometryViewport.grab", "hou.GeometryViewport", False, "Q1 viewport grab"),
    # --- render to disk -------------------------------------------------
    ("hou.RopNode.render", "hou.RopNode", False, "Q1 render-to-disk"),
    ("hou.RopNode.addRenderEventCallback", "hou.RopNode", False, "Q1 render observation"),
    ("hou.RopNode.removeRenderEventCallback", "hou.RopNode", False, "Q1"),
    ("hou.RopNode.renderFrameRange", "hou.RopNode", False, "Q1"),
    # --- Copernicus readback (OPEN SIDEFX ASK -- verify twice) -----------
    ("hou.CopNode.allPixels", "hou.CopNode", False, "Q1 COP readback"),
    ("hou.CopNode.allPixelsAsString", "hou.CopNode", False, "Q1 COP readback"),
    ("hou.CopNode.planes", "hou.CopNode", False, "Q1 COP readback (HOM-02: removed in H22?)"),
    ("hou.CopNode.getPixel", "hou.CopNode", False, "Q1 COP readback"),
    ("hou.CopNode.getPixelHDR", "hou.CopNode", False, "Q1 COP readback"),
    ("hou.CopNode.xRes", "hou.CopNode", False, "Q1 COP readback"),
    ("hou.CopNode.yRes", "hou.CopNode", False, "Q1 COP readback"),
    ("hou.CopNode.saveImage", "hou.CopNode", False, "Q1 COP readback"),
    ("hou.Cop2Node.allPixels", "hou.Cop2Node", False, "Q1 legacy COP readback"),
    ("hou.Cop2Node.allPixelsAsString", "hou.Cop2Node", False, "Q1 legacy COP readback"),
    ("hou.Cop2Node.planes", "hou.Cop2Node", False, "Q1 legacy COP readback"),
    # --- GUI-gated: UNVERIFIABLE from this producer by construction ------
    ("hou.ui.openImageViewer", None, True, "Q1 GUI-only"),
    ("hou.ui.paneTabOfType", None, True, "Q1 GUI-only"),
    ("hou.ui.curDesktop", None, True, "Q1 GUI-only"),
    ("hou.qt.screenshot", None, True, "Q1 GUI-only"),
]

# Module-level sweep: any hou.* name whose spelling suggests pixels leaving Houdini.
SWEEP_PATTERNS = (
    "flipbook", "capture", "screenshot", "snapshot", "framebuffer", "frame_buffer",
    "raster", "pixel", "image", "render", "cop", "viewport", "plane", "buffer",
    "mplay", "husk", "aov", "product",
)


def resolve(dotted):
    """Walk a dotted name from the hou root. Returns (verdict, detail)."""
    if not HOU:
        return "UNVERIFIABLE", "hou did not import"
    parts = dotted.split(".")
    assert parts[0] == "hou"
    obj = hou
    walked = "hou"
    for p in parts[1:]:
        if not hasattr(obj, p):
            return "ABSENT", f"{walked} has no attribute {p!r}"
        obj = getattr(obj, p)
        walked += "." + p
    return "EXISTS", type(obj).__name__


def members(dotted):
    v, _ = resolve(dotted)
    if v != "EXISTS":
        return None
    obj = hou
    for p in dotted.split(".")[1:]:
        obj = getattr(obj, p)
    return sorted(n for n in dir(obj) if not n.startswith("_"))


result = {
    "probe": "V1/A capture-verb class surfaces",
    "producer": "harness/notes/v1/probe_a_surfaces.py",
    "hou_imported": HOU,
    "build": None,
    "python": sys.version.split()[0],
    "ui_available": None,
    "license_category": None,
    "declared_blind_spot": (
        "hou.ui and hou.qt are absent under headless hython by construction; every "
        "hou.ui.*/hou.qt.* verdict here is UNVERIFIABLE and must be settled by the "
        "live-GUI producer (H3a-F5, R50)."
    ),
}
if HOU:
    # Defensive by design, NOT to mask failure: the controls below are the
    # instrument, and they must stay reachable even when a metadata read blows
    # up. Any failure here is recorded as a string, never swallowed (Law 3).
    for key, fn in (
        ("build", lambda: str(hou.applicationVersionString())),
        ("ui_available", lambda: bool(hou.isUIAvailable())),
        ("license_category", lambda: str(hou.licenseCategory())),
    ):
        try:
            result[key] = fn()
        except Exception as exc:
            result[key] = f"ERROR: {exc!r}"
else:
    result["import_error"] = _IMPORT_ERR

# ---- controls -------------------------------------------------------------
pos = []
for name, why in POSITIVE:
    v, d = resolve(name)
    pos.append({"symbol": name, "why": why, "verdict": v, "detail": d})
neg = []
for name, why in NEGATIVE:
    v, d = resolve(name)
    neg.append({"symbol": name, "why": why, "verdict": v, "detail": d})

positive_ok = all(p["verdict"] == "EXISTS" for p in pos)
negative_ok = all(n["verdict"] == "ABSENT" for n in neg)

# ---- class surfaces -------------------------------------------------------
surfaces = {}
class_control_ok = {}
for cls, control, why in CLASS_TARGETS:
    ms = members(cls)
    ctl_v, ctl_d = resolve(f"{cls}.{control}")
    class_control_ok[cls] = (ms is not None and len(ms) > 0 and ctl_v == "EXISTS")
    surfaces[cls] = {
        "why": why,
        "class_resolves": ms is not None,
        "named_control": control,
        "named_control_verdict": ctl_v,
        "control_ok": class_control_ok[cls],
        "member_count": len(ms) if ms else 0,
        "members": ms,
    }

# ---- candidates -----------------------------------------------------------
cands = []
for sym, owner, gui_only, bears in CANDIDATES:
    v, d = resolve(sym)
    if gui_only:
        verdict = "UNVERIFIABLE"
        note = "GUI-gated module absent under headless hython; not an absence claim"
    elif owner and not class_control_ok.get(owner, False):
        verdict = "UNVERIFIABLE"
        note = f"same-class control on {owner} did not pass; ABSENT is not licensed (R50)"
    else:
        verdict = "CONFIRMED" if v == "EXISTS" else "ABSENT"
        note = d
    cands.append({
        "symbol": sym, "bears_on": bears, "owner_class": owner,
        "gui_only": gui_only, "raw": v, "verdict": verdict, "note": note,
    })

# ---- module sweep ---------------------------------------------------------
sweep = {}
if HOU:
    for n in sorted(dir(hou)):
        if n.startswith("_"):
            continue
        low = n.lower()
        hits = [p for p in SWEEP_PATTERNS if p in low]
        if hits:
            sweep[n] = {"matched": hits, "type": type(getattr(hou, n, None)).__name__}

controls_ok = positive_ok and negative_ok and all(class_control_ok.values())
result.update({
    "controls": {
        "positive": pos, "negative": neg,
        "positive_ok": positive_ok, "negative_ok": negative_ok,
        "class_controls": class_control_ok,
        "controls_ok": controls_ok,
        "stated_failure_condition": (
            "controls_ok is false if any positive control != EXISTS, any negative "
            "control != ABSENT, or any dumped class fails its named same-class "
            "control. A file with controls_ok:false is UNINTERPRETABLE and may not "
            "be cited."
        ),
    },
    "class_surfaces": surfaces,
    "candidates": cands,
    "module_sweep": sweep,
})

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=1, sort_keys=False)

print(f"controls_ok={controls_ok} positive_ok={positive_ok} negative_ok={negative_ok}")
print(f"wrote {OUT}")
sys.exit(0 if controls_ok else 1)
