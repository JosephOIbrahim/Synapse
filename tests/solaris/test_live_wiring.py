"""
SR1 M3 — LIVE host-behaviour tests for the Solaris tool family.

These replace the mock-`hou` execute tests deleted from the sibling files.

Constitution Law 1: a check that cannot fail is a decoration. A mock `hou`
asserts our assumptions back at us — it is structurally incapable of
disagreeing with the host, which is exactly how F7 and F9 stayed green.

GATE: a module-level probe for a REAL `hou`. Without Houdini every test here
SKIPS — honest. Inside hython 22.0.368 every test EXECUTES against the real
host. There is no mock fallback and no env-var opt-in.

Note on the gate's shape: a bare `pytest.importorskip("hou")` is NOT a valid
gate in this suite. `tests/conftest.py:133` plants a canonical fake `hou` into
`sys.modules` before collection, so the import always succeeds and the tests
would run against the fake — the exact Law 1 failure this mile exists to
remove, recurring one layer up. The gate therefore probes host identity: the
planted fake carries `__synapse_canonical__`; the real host does not. That is
still a real runtime probe, not an opt-in flag.

Run the live tier:  hython tests/solaris/run_live.py
(or:  hython -m pytest tests/solaris/test_live_wiring.py)

EXPECTED RED: several tests here are expected to FAIL live on 22.0.368.
They are pinning the F3-F10 defects that mock-`hou` was hiding. Per Law 7 a
red result is a finding, not a failure. Do NOT xfail, skip or weaken them to
turn this file green — M4 repairs the source, this mile only makes the
defects visible.
"""

import pytest

try:
    import hou
except ImportError:  # pragma: no cover - exercised off-host
    hou = None

_NO_LIVE_HOU = hou is None or getattr(hou, "__synapse_canonical__", False)

# A marker, not `pytest.skip(allow_module_level=True)`: Law 6 counts COLLECTED
# tests, and a module-level skip removes them from the count entirely. These
# stay collected and report as honest skips off-host.
pytestmark = pytest.mark.skipif(
    _NO_LIVE_HOU,
    reason=(
        "live Houdini required — no real `hou` on this interpreter "
        "(mock-`hou` is banned for host-behaviour assertions, Law 1). "
        "Run: hython tests/solaris/run_live.py"
    ),
)

from synapse.mcp.tool_impls.solaris import component_builder as cb_mod  # noqa: E402
from synapse.mcp.tool_impls.solaris import create_variants as cv_mod  # noqa: E402
from synapse.mcp.tool_impls.solaris import import_megascans as ms_mod  # noqa: E402
from synapse.mcp.tool_impls.solaris import scene_template as st_mod  # noqa: E402
from synapse.mcp.tool_impls.solaris import set_purpose as sp_mod  # noqa: E402

PINNED_BUILD = "22.0.368"

_counter = {"n": 0}


@pytest.fixture
def lopnet():
    """A fresh, uniquely-named lopnet under /stage, destroyed after the test."""
    _counter["n"] += 1
    stage = hou.node("/stage")
    assert stage is not None, "/stage missing on this host"
    net = stage.createNode("lopnet", f"sr1_m3_{_counter['n']}")
    try:
        yield net
    finally:
        try:
            net.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Host identity — the gate's own negative control.
# ---------------------------------------------------------------------------

def test_host_is_the_pinned_build():
    """Fails if this suite is run against a Houdini other than the pinned one."""
    assert hou.applicationVersionString() == PINNED_BUILD


def test_lop_category_resolves_live():
    """`hou.lopNodeTypeCategory()` is real, not an assumption."""
    cat = hou.lopNodeTypeCategory()
    assert cat.name() == "Lop"
    assert hou.nodeType(cat, "componentgeometry") is not None


# ---------------------------------------------------------------------------
# component_builder
# ---------------------------------------------------------------------------

def test_component_builder_creates_internal_nodes_live(lopnet):
    r = cb_mod.execute({"asset_name": "cb_live", "parent": lopnet.path()})
    assert r["status"] == "created"
    comp = lopnet.node("component_cb_live")
    assert comp is not None
    types = {c.type().name() for c in comp.children()}
    assert "componentgeometry" in types
    assert "componentmaterial" in types
    assert "componentoutput" in types


def test_component_builder_wires_geo_to_mat_to_output_live(lopnet):
    cb_mod.execute({"asset_name": "cb_wire", "parent": lopnet.path()})
    comp = lopnet.node("component_cb_wire")
    by_type = {c.type().name(): c for c in comp.children()}
    mat = by_type["componentmaterial"]
    out = by_type["componentoutput"]
    # NB: `hou` returns a fresh wrapper object per call — compare paths, not identity.
    assert mat.inputs() and mat.inputs()[0].path() == by_type["componentgeometry"].path()
    assert out.inputs() and out.inputs()[0].path() == mat.path()


def test_component_builder_is_idempotent_live(lopnet):
    cb_mod.execute({"asset_name": "cb_idem", "parent": lopnet.path()})
    r2 = cb_mod.execute({"asset_name": "cb_idem", "parent": lopnet.path()})
    assert r2["status"] == "already_exists"


def test_component_builder_stamps_provenance_live(lopnet):
    cb_mod.execute({"asset_name": "cb_prov", "parent": lopnet.path()})
    comp = lopnet.node("component_cb_prov")
    assert comp.userData("synapse:tool") == cb_mod._TOOL_NAME
    assert comp.userData("synapse:source_pattern") == cb_mod._SOURCE_PATTERN


def test_f10_componentbuilder_type_is_absent_on_this_build():
    """F10: `componentbuilder` is not a live LOP type — the subnet fallback masks it.

    Fails if SideFX ever ships the type, which is the signal to drop the
    fallback rather than keep an unreachable branch.
    """
    assert hou.nodeType(hou.lopNodeTypeCategory(), "componentbuilder") is None
    assert cb_mod._has_native_componentbuilder() is False


# ---------------------------------------------------------------------------
# scene_template
# ---------------------------------------------------------------------------

def test_scene_template_creates_full_chain_live(lopnet):
    r = st_mod.execute({"parent": lopnet.path()})
    assert r["status"] == "created"
    assert r["hierarchy_root"] == "/shot"
    assert len(r["chain"]) >= 5
    assert lopnet.node("primitive_shot") is not None


def test_scene_template_is_idempotent_live(lopnet):
    st_mod.execute({"parent": lopnet.path()})
    r2 = st_mod.execute({"parent": lopnet.path()})
    assert r2["status"] == "already_exists"


def test_scene_template_chains_sop_imports_sequentially_live(lopnet):
    """Pattern 1: SOP imports chain, never merge."""
    st_mod.execute({"parent": lopnet.path(), "sop_paths": ["/obj/a", "/obj/b"]})
    g0, g1 = lopnet.node("geo_0"), lopnet.node("geo_1")
    assert g0 is not None and g1 is not None
    assert g1.inputs() and g1.inputs()[0].path() == g0.path()


def test_f8_scene_template_honours_parent_path_live(lopnet):
    """F8/Ruling 15: `parent_path` is the convergent key. EXPECTED RED until M4.

    Today `scene_template.execute` reads `params["parent"]` only, so a caller
    passing `parent_path` silently builds into /stage.
    """
    st_mod.execute({"scene_name": "f8", "parent_path": lopnet.path()})
    assert lopnet.node("primitive_f8") is not None, (
        "built outside the requested parent — parent_path silently ignored"
    )


# ---------------------------------------------------------------------------
# set_purpose  (F7)
# ---------------------------------------------------------------------------

def test_f7_componentgeometry_exposes_no_purpose_parm_live(lopnet):
    """F7 root: the parm `set_purpose` writes does not exist on 22.0.368."""
    geo = lopnet.createNode("componentgeometry", "f7_probe")
    assert geo.parm("purpose") is None
    assert [p.name() for p in geo.parms() if "purpose" in p.name().lower()] == []


def test_f7_set_purpose_does_not_report_success_when_nothing_set_live(lopnet):
    """F7/Ruling 14: a success status that set nothing is a lie. EXPECTED RED.

    Law 3: status describes what happened. Either the call authors nothing and
    says so (`noop`/`not_found`), or it says "set" AND the purpose is readable
    off the cooked stage. Nothing in between.

    SR1 M4 note: this assertion was TIGHTENED, not relaxed. Pre-M4 the tool
    returned status="set" with an advisory note having authored nothing, so
    `!= "set"` was enough to catch the lie. M4's repair authors for real in
    this scenario, so the honest contract is now the disjunction below — the
    "set" branch must survive a live readback, which the old form never
    checked at all.
    """
    from pxr import UsdGeom

    comp = lopnet.createNode("subnet", "f7_comp")
    comp.createNode("componentgeometry", "geo_f7")
    r = sp_mod.execute({"component_path": comp.path(), "purpose": "proxy"})
    if r["status"] != "set":
        assert r["status"] in ("noop", "not_found"), r
        return
    cfg = hou.node(r["configure_node"])
    prim = cfg.stage().GetPrimAtPath(r["prim_path"])
    assert prim and prim.IsValid(), f"claimed success; {r['prim_path']} absent: {r}"
    assert UsdGeom.Imageable(prim).GetPurposeAttr().Get() == "proxy", (
        f"claimed success having set nothing: {r}"
    )


def test_f7_set_purpose_authors_a_real_usd_purpose_live(lopnet):
    """F7 positive leg: the repair must actually author, not merely stop lying.

    Mechanism (VERIFIED-RUNTIME 22.0.368): the `configureprimitive` LOP —
    singular; `configureprimitives` is a PHANTOM type — carries `setpurpose`
    + `purpose`. Read back off the cooked stage via UsdGeom, not off our own
    parm (Law 1: asking the parm what we just set it to proves nothing).
    """
    from pxr import UsdGeom

    comp = lopnet.createNode("subnet", "f7_ok")
    geo = comp.createNode("componentgeometry", "geo_f7ok")
    out = comp.createNode("componentoutput", "output_f7ok")
    out.parm("name").set("f7asset")
    out.setInput(0, geo)

    r = sp_mod.execute({"component_path": comp.path(), "purpose": "proxy"})
    assert r["status"] == "set", r
    assert r["usd_purpose"] == "proxy"

    cfg = hou.node(r["configure_node"])
    assert cfg is not None
    # The configure node must sit between the geometry and the output.
    assert out.inputs() and out.inputs()[0].path() == cfg.path()

    stage = cfg.stage()
    prim = stage.GetPrimAtPath(r["prim_path"])
    assert prim and prim.IsValid(), f"{r['prim_path']} absent from the cooked stage"
    assert UsdGeom.Imageable(prim).GetPurposeAttr().Get() == "proxy"


def _purpose_component(lopnet, name):
    comp = lopnet.createNode("subnet", name)
    geo = comp.createNode("componentgeometry", "geo_" + name)
    mat = comp.createNode("componentmaterial", "mat_" + name)
    out = comp.createNode("componentoutput", "output_" + name)
    out.parm("name").set(name)
    mat.setInput(0, geo)
    out.setInput(0, mat)
    return comp


def test_set_purpose_last_write_is_the_one_that_composes_live(lopnet):
    """SR1 seam BLOCKER-1: the LAST requested purpose must be the live one.

    Pre-fix each call created a NEW configureprimitive and inserted it at the
    geometry end, i.e. UPSTREAM of the previous one, so the FIRST purpose ever
    set composed to the terminal while the call reported status="set" with the
    new value. A Law-3 lie and wrong USD.

    Readback is off the cooked stage at the SINK'S INPUT — the downstream-most
    node that still carries the authored purpose — not off the configure node
    we just wrote, which would prove nothing about ordering.

    (VERIFIED-RUNTIME 22.0.368: `componentoutput` itself restructures /ASSET
    and does not carry `purpose` through. Separate finding, recorded not fixed
    under the SR1 M4 grant; see harness/notes/sr1_seam_probe.py.)
    """
    from pxr import UsdGeom

    comp = _purpose_component(lopnet, "spord")
    r1 = sp_mod.execute({"component_path": comp.path(), "purpose": "proxy"})
    r2 = sp_mod.execute({"component_path": comp.path(), "purpose": "render"})
    assert r1["status"] == "set", r1
    assert r2["status"] in ("set", "updated"), r2

    tail = comp.node("output_spord").inputs()[0]
    prim = tail.stage().GetPrimAtPath(r2["prim_path"])
    assert prim and prim.IsValid(), f"{r2['prim_path']} absent downstream: {r2}"
    assert UsdGeom.Imageable(prim).GetPurposeAttr().Get() == "render", (
        "last write lost — an earlier purpose composes to the terminal"
    )


def test_set_purpose_is_idempotent_live(lopnet):
    """SR1 seam BLOCKER-1: repeat calls must not stack nodes, and a true no-op
    must say so. Pre-fix three calls left three configureprimitive nodes and
    all three said status="set"."""
    comp = _purpose_component(lopnet, "spidem")
    sp_mod.execute({"component_path": comp.path(), "purpose": "proxy"})
    sp_mod.execute({"component_path": comp.path(), "purpose": "render"})
    r3 = sp_mod.execute({"component_path": comp.path(), "purpose": "render"})

    cfgs = [c for c in comp.children()
            if c.type().name() == "configureprimitive"]
    assert len(cfgs) == 1, f"stacked purpose nodes: {[c.name() for c in cfgs]}"
    assert r3["status"] == "unchanged", r3


def test_create_variants_rejects_a_non_lop_path_live():
    """SR1 seam MINOR-3: a wrong-network path is a designed error, not a bare
    `OperationFailed: ... Invalid node type name` from deep inside the build."""
    from synapse.core.errors import ValidationError

    bad = hou.node("/obj").createNode("geo", "sr1_notalop")
    try:
        with pytest.raises(ValidationError) as exc:
            cv_mod.execute({
                "component_path": bad.path(), "variant_type": "geometry",
                "variants": [{"name": "a"}, {"name": "b"}],
            })
        assert bad.path() in str(exc.value), exc.value
    finally:
        bad.destroy()


# ---------------------------------------------------------------------------
# import_megascans  (F9, F3)
# ---------------------------------------------------------------------------

def test_f9_import_megascans_completes_live(lopnet, tmp_path):
    """F9 CRITICAL: EXPECTED RED — createNode targets a locked componentgeometry HDA.

    Live: hou.PermissionError. The tool cannot complete under any parameters.
    """
    usdc = tmp_path / "rock.usdc"
    usdc.write_bytes(b"")
    r = ms_mod.execute({
        "usdc_path": str(usdc), "asset_name": "f9rock", "parent": lopnet.path(),
    })
    assert r["status"] == "created"


def test_f3_megascans_material_reference_is_wired_live(lopnet, tmp_path):
    """F3 HIGH: EXPECTED RED — mtl_ref_<asset> is created but never wired
    into componentmaterial input 1."""
    usdc = tmp_path / "rock.usdc"
    usdc.write_bytes(b"")
    ms_mod.execute({
        "usdc_path": str(usdc), "asset_name": "f3rock", "parent": lopnet.path(),
    })
    comp = lopnet.node("component_f3rock")
    assert comp is not None
    mat = next(c for c in comp.children() if c.type().name() == "componentmaterial")
    inputs = mat.inputs()
    assert len(inputs) > 1 and inputs[1] is not None, "componentmaterial input 1 left open"


# ---------------------------------------------------------------------------
# create_variants  (F4, F5, F6)
# ---------------------------------------------------------------------------

def _base_component(lopnet, name):
    comp = lopnet.createNode("subnet", name)
    geo = comp.createNode("componentgeometry", "geo_base")
    mat = comp.createNode("componentmaterial", "mat_base")
    out = comp.createNode("componentoutput", "output_base")
    mat.setInput(0, geo)
    out.setInput(0, mat)
    return comp


def test_f4_material_variants_are_wired_live(lopnet):
    """F4 HIGH: EXPECTED RED — hou.copyNodesTo does not carry connections
    outside the copied set, and the tool never calls setInput on the copies."""
    comp = _base_component(lopnet, "f4_comp")
    cv_mod.execute({
        "component_path": comp.path(), "variant_type": "material",
        "variants": [{"name": "red"}, {"name": "blue"}],
    })
    for vn in ("mat_red", "mat_blue"):
        node = comp.node(vn)
        assert node is not None, f"{vn} not created"
        assert node.inputs() and node.inputs()[0] is not None, f"{vn} left unwired"


def test_f5_geometry_variants_node_reaches_terminal_live(lopnet):
    """F5 HIGH: EXPECTED RED — componentgeometryvariants never reaches the
    terminal; the component presents two terminal LOPs."""
    comp = _base_component(lopnet, "f5_comp")
    cv_mod.execute({
        "component_path": comp.path(), "variant_type": "geometry",
        "variants": [{"name": "a"}, {"name": "b"}],
    })
    gv = comp.node("geo_variants")
    assert gv is not None, "componentgeometryvariants not created"
    assert gv.outputs(), "componentgeometryvariants is a dead end — not wired downstream"


def test_f6_create_variants_status_is_honest_live(lopnet):
    """F6/Ruling 14: EXPECTED RED — bare `except Exception: pass` then
    status="created". Status must describe what happened."""
    comp = _base_component(lopnet, "f6_comp")
    r = cv_mod.execute({
        "component_path": comp.path(), "variant_type": "geometry",
        "variants": [{"name": "x"}, {"name": "y"}],
        "add_explore_node": True,
    })
    if r["status"] == "created":
        explore = lopnet.node(f"explore_{comp.name()}")
        assert explore is not None, (
            "status='created' but the explorevariants node was swallowed by "
            "`except Exception: pass`"
        )
