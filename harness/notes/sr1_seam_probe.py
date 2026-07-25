"""SR1 seam-finding probe — fail-before / pass-after evidence, live 22.0.368.

    hython harness/notes/sr1_seam_probe.py

Three legs, one per seam-hunter finding. Prints LEG-n PASS/FAIL.

NOT RUN — seam D (F9's sopnet/geo retarget against a genuinely LOCKED real
Megascans HDA). A Megascans library DOES exist on this host at
``%USERPROFILE%/OneDrive/Documents/Megascans Library``, contrary to the
seam-hunter's read, but every downloaded asset is FBX + JPG/EXR — there is no
``.usdc`` anywhere in it, and ``import_megascans`` takes a ``usdc_path``. So
the seam is still unexercisable here and F9 remains proven only against a
fresh probe ``componentgeometry``. No verdict is claimed for seam D.

RECORDED, NOT FIXED — ``componentoutput`` restructures the asset
(``/ASSET`` -> ``/<rootprim>``) and does NOT carry an authored ``purpose``
through, so no upstream ``configureprimitive`` purpose survives to the
component's published sink. Distinct from the three findings below and outside
the SR1 M4 grant.
"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "python"))

import hou  # noqa: E402
from pxr import UsdGeom  # noqa: E402

from synapse.mcp.tool_impls.solaris import set_purpose as sp  # noqa: E402
from synapse.mcp.tool_impls.solaris import create_variants as cv  # noqa: E402

results = {}
stage = hou.node("/stage")
net = stage.createNode("lopnet", "sr1_seam")


def leg(name, fn):
    try:
        fn()
        results[name] = "PASS"
    except AssertionError as exc:
        results[name] = f"FAIL: {exc}"
    except Exception as exc:  # noqa: BLE001
        results[name] = f"ERROR: {type(exc).__name__}: {exc}"


def _comp(name):
    c = net.createNode("subnet", name)
    geo = c.createNode("componentgeometry", "geo_base")
    mat = c.createNode("componentmaterial", "mat_base")
    out = c.createNode("componentoutput", "output_base")
    out.parm("name").set(name)
    mat.setInput(0, geo)
    out.setInput(0, mat)
    return c


# --- LEG 1: set_purpose last-write-wins + idempotency -----------------------
def leg1():
    c = _comp("l1")
    r1 = sp.execute({"component_path": c.path(), "purpose": "proxy"})
    r2 = sp.execute({"component_path": c.path(), "purpose": "render"})
    r3 = sp.execute({"component_path": c.path(), "purpose": "render"})
    print("   r1", r1.get("status"), "| r2", r2.get("status"), "| r3", r3.get("status"))
    cfgs = [n.name() for n in c.children() if n.type().name() == "configureprimitive"]
    print("   configureprimitive nodes:", cfgs)
    # Read at the sink's INPUT, i.e. the downstream-most node that still carries
    # the authored purpose. (componentoutput restructures /ASSET and drops it —
    # a separate finding, recorded not fixed.)
    tail = c.node("output_base").inputs()[0]
    prim = tail.stage().GetPrimAtPath(r2["prim_path"])
    live = UsdGeom.Imageable(prim).GetPurposeAttr().Get()
    print("   DOWNSTREAM purpose (last requested=render):", live)
    assert len(cfgs) == 1, f"stacked configureprimitive nodes: {cfgs}"
    assert r3.get("status") == "unchanged", f"re-set of same value not reported unchanged: {r3}"
    assert live == "render", f"last write lost: stage reads {live!r}"


# --- LEG 2: static verifier catalog matches post-F4/F5 source ---------------
def leg2():
    from synapse.validation.solaris import verify_create_variants as v

    c = _comp("l2")
    cv.execute({"component_path": c.path(), "variant_type": "geometry",
                "variants": [{"name": "red"}, {"name": "blue"}]})
    emitted = {n.name(): [i.name() for i in n.inputs() if i is not None]
               for n in c.children() if n.type().name() != "output"}
    declared = {n["name"]: [i for i in (n.get("inputs") or []) if i]
                for n in v.EXPECTED_TOPOLOGY_GEOMETRY}
    print("   emitted geometry :", emitted)
    print("   declared geometry:", declared)
    assert emitted == declared, "static geometry catalog != live emission"

    c2 = _comp("l2m")
    cv.execute({"component_path": c2.path(), "variant_type": "material",
                "variants": [{"name": "red"}, {"name": "blue"}]})
    em = {n.name(): [i.name() for i in n.inputs() if i is not None]
          for n in c2.children() if n.type().name() != "output"}
    dm = {n["name"]: [i for i in (n.get("inputs") or []) if i]
          for n in v.EXPECTED_TOPOLOGY_MATERIAL}
    print("   emitted material :", em)
    print("   declared material:", dm)
    assert em == dm, "static material catalog != live emission"


# --- LEG 3: wrong-path input is a designed error ---------------------------
def leg3():
    obj = hou.node("/obj")
    bad = obj.createNode("geo", "notalop_sr1")
    try:
        cv.execute({"component_path": bad.path(), "variant_type": "geometry",
                    "variants": [{"name": "a"}, {"name": "b"}]})
    except Exception as exc:  # noqa: BLE001
        print(f"   raised {type(exc).__name__}: {exc}")
        assert type(exc).__name__ == "ValidationError", f"undesigned error: {type(exc).__name__}"
        assert bad.path() in str(exc), "error does not name the offending path"
        return
    finally:
        bad.destroy()
    raise AssertionError("no error raised for a non-LOP component_path")


for n, f in (("LEG-1 set_purpose", leg1), ("LEG-2 verifier catalog", leg2),
             ("LEG-3 input guard", leg3)):
    print(f"== {n}")
    leg(n, f)

print()
for k, v in results.items():
    print(f"{k}: {v}")
net.destroy()
sys.exit(0 if all(v == "PASS" for v in results.values()) else 1)
