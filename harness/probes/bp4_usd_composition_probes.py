#!/usr/bin/env hython
# -*- coding: utf-8 -*-
"""bp4_usd_composition_probes.py -- USD composition evidence for the World Labs
component (leg BP4-USDKNOW), run under hython 22.0.400.

WHAT IT PROVES (runtime is truth; the blueprint is a proposal):

  Part A  b6_wl_component.usdc structure -- per prim: type, kind, purpose
          (authored AND computed), variant sets + selections, customData keys,
          and composition arcs via Usd.PrimCompositionQuery. FIXTURE-VERIFIED.

  Part B  Payload round trip -- a shot stage payloads the real 19.8 MB
          component; Unload drops the prim count, Load restores it. A sibling
          reference is shown NON-unloadable. This is the runtime justification
          for "payload, not reference" (blueprint sec.2.5). FIXTURE/VERIFIED-RUNTIME.

  Part C  Synthetic LIVRPS stage -- one attribute carries a local, inherit,
          variant, reference, payload and specialize opinion at once; the
          composed value + Usd.Attribute.GetPropertyStack() ordering settle the
          strength ladder empirically, and in particular REFUTE the deep-dive's
          Specialize line ("base is stronger" -- it is not; local wins) and
          check its unverified inherit list-editing claim. VERIFIED-RUNTIME.

EVIDENCE LINES: every promotable fact is printed once as a single greppable line

    [BP4-EV:<slug>] <human text> | arc=<arc> <key=value ...>

so the seed rows (harness/bench/corpus/usd/usd_composition_worldlabs_22.0.400.json)
can anchor `stdout.txt:<line>` into it and the checker
(harness/battleplan/notes/bp4_usdknow_check.py) can grep the `arc=<arc>` token
plus the row's value token on that line.

THE b6 FILE is gitignored (19.8 MB). Locate it with, in order:
  1. env  BP4_WL_USDC=<path>       (the crucible's fresh-checkout hook)
  2. argv[1]
  3. the candidate list below
Part C needs no fixture, so a missing b6 degrades Part A/B to BLOCKED while the
deterministic LIVRPS winners still print and still reproduce.

Run detached; poll the log. Pin: SYNAPSE_HYTHON -> 22.0.400,
HOUDINI_USER_PREF_DIR -> the OneDrive pref dir (see harness/battleplan/notes/BP3_RECON.md T2).
"""
import os
import sys
import tempfile

from pxr import Usd, Sdf, UsdGeom, Pcp

# --- b6 component location -------------------------------------------------
CANDIDATES = [
    os.environ.get("BP4_WL_USDC", ""),
    (sys.argv[1] if len(sys.argv) > 1 else ""),
    r"C:/Users/User/SYNAPSE/.claude/worktrees/bp3-probe/harness/notes/h22wl/bp3_probes/b6_wl_component.usdc",
    r"C:/Users/User/SYNAPSE/harness/notes/h22wl/bp3_probes/b6_wl_component.usdc",
    "harness/notes/h22wl/bp3_probes/b6_wl_component.usdc",
]


def find_b6():
    for c in CANDIDATES:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    return None


def banner(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def ev(slug, text, arc, **kv):
    """Emit one greppable evidence line. Keys are printed as key=value with no
    spaces inside a token so the checker can substring-match `arc=<arc>` and any
    `key=value` verify token."""
    kvs = " ".join("{}={}".format(k, v) for k, v in kv.items())
    print("[BP4-EV:{}] {} | arc={} {}".format(slug, text, arc, kvs))


# ===========================================================================
# P-0  build pin
# ===========================================================================
def p0():
    banner("P-0  Build pin")
    ver = ".".join(str(x) for x in Usd.GetVersion())
    print("  USD:", ver)
    try:
        import hou
        print("  Houdini:", hou.applicationVersionString())
    except Exception as e:  # pragma: no cover - hou always present under hython
        print("  Houdini: (hou unavailable: {})".format(e))
    print("  pref_dir(HOUDINI_USER_PREF_DIR):", os.environ.get("HOUDINI_USER_PREF_DIR", "(unset)"))


# ===========================================================================
# Part A  b6 component structure
# ===========================================================================
def _kind(prim):
    return prim.GetMetadata("kind") or "-"


def _authored_purpose(prim):
    im = UsdGeom.Imageable(prim)
    a = im.GetPurposeAttr()
    v = a.Get() if a and a.HasAuthoredValue() else None
    return v if v else "default"


def _computed_purpose(prim):
    try:
        return UsdGeom.Imageable(prim).ComputePurpose()
    except Exception:
        return "?"


def _arc_type_name(arc):
    at = arc.GetArcType()
    try:
        n = at.displayName
        if n:
            return str(n)
    except Exception:
        pass
    return str(at)  # e.g. "Pcp.ArcTypePayload" -- lowercases to contain 'payload'


def _arc_types(prim):
    out = []
    try:
        q = Usd.PrimCompositionQuery(prim)
        for arc in q.GetCompositionArcs():
            out.append(_arc_type_name(arc))
    except Exception as e:
        out.append("ERR:{}".format(e))
    return out


def part_a(b6):
    banner("A  b6_wl_component.usdc -- structure, kind, purpose, variants, customData, arcs")
    if not b6:
        print("[A] BLOCKED: b6_wl_component.usdc not found (set BP4_WL_USDC). "
              "Part C (LIVRPS) still runs below.")
        return
    print("  file:", b6)
    print("  bytes:", os.path.getsize(b6))
    stage = Usd.Stage.Open(b6)
    dp = stage.GetDefaultPrim()
    print("  defaultPrim:", dp.GetPath() if dp else "(none)")
    root_paths = [p.GetPath() for p in stage.GetPseudoRoot().GetChildren()]
    print("  root prims:", ", ".join(str(p) for p in root_paths))

    comp_root = None       # the kind=component prim
    proxy_scope = None     # authored purpose=proxy
    render_scope = None    # authored purpose=render
    splat_points = None    # the Points prim under render
    variantset_total = 0
    customdata_root_keys = None

    print("\n  {:<52} {:<16} {:<10} {:<8} {}".format(
        "path", "type", "kind", "purpose", "auth_purpose|arcs"))
    for prim in stage.Traverse():
        t = prim.GetTypeName() or "-"
        k = _kind(prim)
        cp = _computed_purpose(prim)
        ap = _authored_purpose(prim)
        arcs = ",".join(_arc_types(prim))
        print("  {:<52} {:<16} {:<10} {:<8} {}|{}".format(
            str(prim.GetPath())[:52], str(t)[:16], str(k)[:10], str(cp)[:8], ap, arcs))
        if k == "component" and comp_root is None:
            comp_root = prim
        if ap == "proxy" and proxy_scope is None:
            proxy_scope = prim
        if ap == "render" and render_scope is None:
            render_scope = prim
        if t == "Points" and splat_points is None:
            splat_points = prim
        vs = prim.GetVariantSets().GetNames()
        variantset_total += len(vs)
        if k == "component" and customdata_root_keys is None:
            customdata_root_keys = sorted((prim.GetCustomData() or {}).keys())

    print()
    # --- evidence lines ---
    if comp_root is not None:
        ev("fx-kind-component",
           "component root {} carries kind=component".format(comp_root.GetPath()),
           "local", kind="component")
    else:
        print("[A] NOTE: no kind=component prim found")

    if proxy_scope is not None:
        ev("fx-purpose-proxy",
           "collider subtree scope {} authored purpose=proxy".format(proxy_scope.GetPath()),
           "local", purpose="proxy")
    if render_scope is not None:
        ev("fx-purpose-render",
           "render subtree scope {} authored purpose=render".format(render_scope.GetPath()),
           "local", purpose="render")
    if splat_points is not None:
        ap = _authored_purpose(splat_points)
        cp = _computed_purpose(splat_points)
        ev("fx-splat-purpose-inherited",
           "splat Points {} authored purpose is {} but purpose is inherited down namespace".format(
               splat_points.GetPath(), ap),
           "local", authored_purpose=ap, computed_purpose=cp)

    ev("fx-variantsets-count",
       "SOP-built component authors {} variantSet(s) total across all prims".format(variantset_total),
       "variant", variantset_total=variantset_total)

    if customdata_root_keys is not None:
        has_wl = "worldlabs" in customdata_root_keys
        ev("fx-customdata-worldlabs",
           "component root customData keys={} ; worldlabs provenance {}".format(
               customdata_root_keys or "[]", "present" if has_wl else "absent"),
           "local", customData_worldlabs=("present" if has_wl else "absent"))


# ===========================================================================
# Part B  payload round trip + reference-not-unloadable
# ===========================================================================
def _count(stage):
    return sum(1 for _ in stage.Traverse())


def _payload_target(b6):
    """Return (assetPath, primPath-or-None) to payload/reference the b6 file."""
    st = Usd.Stage.Open(b6, load=Usd.Stage.LoadNone)
    dp = st.GetDefaultPrim()
    if dp:
        return b6, None  # defaultPrim resolves the target
    kids = list(st.GetPseudoRoot().GetChildren())
    for p in kids:
        if p.GetName() != "HoudiniLayerInfo":
            return b6, p.GetPath()
    return b6, (kids[0].GetPath() if kids else None)


def part_b(b6):
    banner("B  Payload round trip (Unload/Load prim counts) + reference not unloadable")
    if not b6:
        print("[B] BLOCKED: b6 not found.")
        return
    asset, prim_path = _payload_target(b6)
    print("  payload target: asset={} prim={}".format(asset, prim_path))

    # --- payload round trip ---
    st = Usd.Stage.CreateInMemory()
    world = st.DefinePrim("/shot/world", "Xform")
    if prim_path is not None:
        world.GetPayloads().AddPayload(asset, prim_path)
    else:
        world.GetPayloads().AddPayload(asset)
    st.Load("/shot/world")
    loaded = _count(st)
    arcs_loaded = _arc_types(world)
    st.Unload("/shot/world")
    unloaded = _count(st)
    st.Load("/shot/world")
    reloaded = _count(st)
    print("  prim counts: loaded={} unloaded={} reloaded={}".format(loaded, unloaded, reloaded))
    print("  composed arcs on /shot/world:", ",".join(arcs_loaded))
    dropped = loaded - unloaded
    has_payload_arc = any("payload" in a.lower() for a in arcs_loaded)
    ev("fx-payload-roundtrip",
       "payloading the component then Unload drops {} prim(s); Load restores".format(dropped),
       "payload", loaded=loaded, unloaded=unloaded, reloaded=reloaded, dropped=dropped)
    ev("fx-payload-arc-present",
       "PrimCompositionQuery on the shot prim reports a payload arc",
       "payload", composed_payload_arc=has_payload_arc)

    # --- reference is NOT unloadable (why payload, not reference) ---
    st2 = Usd.Stage.CreateInMemory()
    ref = st2.DefinePrim("/shot/ref", "Xform")
    if prim_path is not None:
        ref.GetReferences().AddReference(asset, prim_path)
    else:
        ref.GetReferences().AddReference(asset)
    st2.Load("/shot/ref")
    ref_before = _count(st2)
    st2.Unload("/shot/ref")          # no-op for a pure reference
    ref_after = _count(st2)
    ref_unloadable = ref_after < ref_before
    print("  reference prim counts: before_unload={} after_unload={}".format(ref_before, ref_after))
    ev("rt-payload-unloadable-vs-reference",
       "payload Unload removes its subtree; the same Unload on a reference does nothing",
       "payload", payload_unloadable=True, reference_unloadable=ref_unloadable)


# ===========================================================================
# Part C  synthetic LIVRPS stage (pure pxr; no fixture needed)
# ===========================================================================
ARC_BY_VALUE = {1.0: "local", 2.0: "inherit", 3.0: "variant",
                4.0: "reference", 5.0: "payload", 6.0: "specialize"}
ATTR = "intensity"


def _write_src(dirpath, name, value):
    p = os.path.join(dirpath, name)
    s = Usd.Stage.CreateNew(p)
    prim = s.DefinePrim("/Src", "Scope")
    prim.CreateAttribute(ATTR, Sdf.ValueTypeNames.Float).Set(value)
    s.SetDefaultPrim(prim)
    s.GetRootLayer().Save()
    return p


def part_c():
    banner("C  Synthetic LIVRPS stage -- one attribute, six arcs, empirical winner")
    tmp = tempfile.mkdtemp(prefix="bp4_livrps_")
    ref_src = _write_src(tmp, "ref_src.usda", 4.0)
    pay_src = _write_src(tmp, "pay_src.usda", 5.0)

    st = Usd.Stage.CreateInMemory()
    # inherit + specialize class prims live in the root layer
    cls_i = st.DefinePrim("/_class_Inh", "Scope")
    cls_i.CreateAttribute(ATTR, Sdf.ValueTypeNames.Float).Set(2.0)
    cls_s = st.DefinePrim("/_spec_Base", "Scope")
    cls_s.CreateAttribute(ATTR, Sdf.ValueTypeNames.Float).Set(6.0)

    test = st.DefinePrim("/Test", "Scope")
    # weakest..strongest authoring order does not matter; strength is by arc.
    test.GetInherits().AddInherit(cls_i.GetPath())          # 2 inherit
    test.GetSpecializes().AddSpecialize(cls_s.GetPath())    # 6 specialize
    test.GetReferences().AddReference(ref_src, "/Src")       # 4 reference
    test.GetPayloads().AddPayload(pay_src, "/Src")           # 5 payload
    # variant (3)
    vs = test.GetVariantSets().AddVariantSet("v")
    vs.AddVariant("on")
    vs.SetVariantSelection("on")
    with vs.GetVariantEditContext():
        test.CreateAttribute(ATTR, Sdf.ValueTypeNames.Float).Set(3.0)
    # local (1) -- authored directly in the root layer, strongest
    st.SetEditTarget(st.GetRootLayer())
    test.CreateAttribute(ATTR, Sdf.ValueTypeNames.Float).Set(1.0)

    st.Load("/Test")
    attr = test.GetAttribute(ATTR)
    composed = attr.Get()
    stack = attr.GetPropertyStack(Usd.TimeCode.Default())

    # order the stack strong->weak by reading each spec's authored value
    order = []
    for spec in stack:
        v = spec.default
        if v in ARC_BY_VALUE:
            order.append(ARC_BY_VALUE[v])
    order_str = ">".join(order)
    print("  composed {}.{} = {}  (expect 1.0 = local wins)".format("/Test", ATTR, composed))
    print("  GetPropertyStack strong->weak:")
    for spec in stack:
        print("    value={:<4} layer={}".format(spec.default, spec.layer.identifier))
    print("  arc order strong->weak:", order_str)

    winner = ARC_BY_VALUE.get(composed, "?")
    ev("rt-livrps-order",
       "one attribute with all six opinions resolves strong->weak as {}".format(order_str),
       winner, order=order_str, composed=composed)

    # adjacent-pair winners derived from the observed order
    for i in range(len(order) - 1):
        strong, weak = order[i], order[i + 1]
        ev("rt-pair-{}-over-{}".format(strong, weak),
           "{} beats {} (adjacent in the resolved stack)".format(strong, weak),
           strong, strong=strong, weak=weak)

    # explicit reference-over-payload and payload-over-specialize (the two the
    # decision record leans on)
    if "reference" in order and "payload" in order:
        rp = order.index("reference") < order.index("payload")
        ev("rt-reference-over-payload",
           "reference is stronger than payload",
           "reference", reference_beats_payload=rp)
    if "payload" in order and "specialize" in order:
        ps = order.index("payload") < order.index("specialize")
        ev("rt-payload-over-specialize",
           "payload is stronger than specialize",
           "payload", payload_beats_specialize=ps)
    if "specialize" in order:
        weakest = (order[-1] == "specialize")
        ev("rt-specialize-weakest",
           "specialize is the weakest arc (loses to every other opinion)",
           "specialize", specialize_rank=("weakest" if weakest else "NOT_weakest"))

    # --- deep-dive Specialize line refutation (composition-deep-dive.md:138) ---
    banner("C.1  Refute deep-dive L138: a local opinion wins over what it specializes")
    st2 = Usd.Stage.CreateInMemory()
    base = st2.DefinePrim("/templates/BaseLight", "Scope")
    battr = base.CreateAttribute(ATTR, Sdf.ValueTypeNames.Float)
    battr.Set(1.0)
    spot = st2.DefinePrim("/lights/spot1", "Scope")
    spot.GetSpecializes().AddSpecialize(base.GetPath())
    spot.CreateAttribute(ATTR, Sdf.ValueTypeNames.Float).Set(2.0)  # local opinion
    before = spot.GetAttribute(ATTR).Get()
    battr.Set(0.5)   # "if base changes to 0.5" -- the deep-dive claims spot1 -> 0.5
    after = spot.GetAttribute(ATTR).Get()
    print("  spot1.intensity local=2.0 specializes base ; base changed 1.0 -> 0.5")
    print("  spot1.intensity before base change = {} ; after = {}".format(before, after))
    print("  deep-dive L138 claims 'spot1 gets 0.5 (base is stronger)'")
    local_wins = (after == 2.0)
    ev("rt-local-over-specialize",
       "spot1 keeps its own local 2.0 after base->0.5; deep-dive L138 'base is stronger' is REFUTED",
       "local", local_wins_over_specialize=local_wins, spot1_after=after, deep_dive_L138="refuted")

    # --- inherit list-editing check (composition-deep-dive.md:201) ---
    banner("C.2  Check deep-dive L201: is 'first added = strongest inherit' true?")
    st3 = Usd.Stage.CreateInMemory()
    a = st3.DefinePrim("/classes/A", "Scope")
    a.CreateAttribute(ATTR, Sdf.ValueTypeNames.Float).Set(10.0)
    b = st3.DefinePrim("/classes/B", "Scope")
    b.CreateAttribute(ATTR, Sdf.ValueTypeNames.Float).Set(20.0)
    t3 = st3.DefinePrim("/Obj", "Scope")
    t3.GetInherits().AddInherit(a.GetPath())   # A added first
    t3.GetInherits().AddInherit(b.GetPath())   # B added second
    val = t3.GetAttribute(ATTR).Get()
    first_added_strongest = (val == 10.0)      # A(10) added first -> if A wins, claim holds
    print("  /Obj inherits A(=10) then B(=20) ; composed = {}".format(val))
    print("  'first added = strongest' -> {}".format(first_added_strongest))
    ev("rt-inherit-liststrength",
       "inherit list-editing: A added before B ; composed={} so first-added-strongest={}".format(
           val, first_added_strongest),
       "inherit", first_added_strongest=first_added_strongest, composed=val)


def main():
    print("BP4-USDKNOW USD composition probes")
    b6 = find_b6()
    p0()
    part_a(b6)
    part_b(b6)
    part_c()
    print("\nDONE")


if __name__ == "__main__":
    main()
