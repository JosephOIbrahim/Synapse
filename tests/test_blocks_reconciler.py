"""M5 BLOCKS reconciler -- planner, fixture loader, canonicalizer seam.

Plain Python. No Houdini, and deliberately NO mocked ``hou``: Constitution
Law 1 bans mock-hou tests for host-behaviour assertions because they assert
your assumptions back at you. Everything asserted here is a property of pure
functions over plain dicts. The host behaviour (does createNode really rename,
does destroy really keep members) is proved by the hython harness at
``harness/blocks/invariants_m5.py``, not here.

Every test below names the condition under which it fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from synapse.blocks import canonical, fixtures, plan as planmod

REPO = Path(__file__).resolve().parent.parent
FIXTURE_NAME = "solaris.basic"


# ---------------------------------------------------------------- helpers


def load_fx():
    return fixtures.load_fixture(FIXTURE_NAME)


def clean_snapshot(box_name="BLOCKS_solaris_basic", outside=None):
    """A stage with nothing of ours in it."""
    return {
        "stage_path": "/stage",
        "box_name": box_name,
        "box_present": False,
        "box_members": {},
        "outside_names": dict(outside or {}),
    }


def applied_snapshot(fx, box_name="BLOCKS_solaris_basic", outside=None):
    """The snapshot ``observe()`` would return right after a clean apply."""
    wires = fixtures.declared_wires(fx)
    members = {}
    for spec in fx["nodes"]:
        name = spec["name"]
        members[name] = {
            "type": spec["type"],
            "type_base": spec["type"].split("::")[0],
            "position": list(spec.get("position") or [0.0, 0.0]),
            "display": name == fx.get("display"),
            "inputs": dict(wires.get(name, {})),
            "parms": dict(spec.get("parms") or {}),
            "parms_missing": [],
        }
    return {
        "stage_path": "/stage",
        "box_name": box_name,
        "box_present": True,
        "box_members": members,
        "outside_names": dict(outside or {}),
    }


# ---------------------------------------------------------------- fixtures


def test_solaris_basic_loads_and_validates():
    """Fails if fixtures/solaris.basic.json goes missing or malformed."""
    fx = load_fx()
    assert fx["fixture"] == "solaris.basic"
    assert [n["name"] for n in fx["nodes"]] == [
        "geo", "dome_light", "materials", "camera", "render_settings",
    ]


def test_box_name_is_declared_and_the_derivation_agrees():
    """D1: the box name is the ownership marker.

    Fails if the fixture's declared ``ownership.network_box`` and the
    fallback derivation ever disagree -- which would mean two conventions for
    'our' box and a reconciler that could orphan a previous apply.
    """
    fx = load_fx()
    assert fixtures.box_name_for(fx, FIXTURE_NAME) == "BLOCKS_solaris_basic"
    stripped = {k: v for k, v in fx.items() if k != "ownership"}
    assert fixtures.box_name_for(stripped, FIXTURE_NAME) == "BLOCKS_solaris_basic"


@pytest.mark.parametrize("bad", [
    "../etc/passwd", "solaris/basic", "Solaris.basic", "", ".hidden",
    "sol aris", "sol'aris", "..",
])
def test_fixture_name_validation_rejects(bad):
    """Fails if a name that could escape the fixtures dir or the repr() in
    the injected script is accepted."""
    with pytest.raises(fixtures.FixtureError):
        fixtures.fixture_path(bad)


def test_unknown_fixture_raises_not_found():
    with pytest.raises(fixtures.FixtureNotFoundError):
        fixtures.load_fixture("definitely.not.a.fixture")


@pytest.mark.parametrize("mutate,fragment", [
    (lambda f: f.__setitem__("nodes", []), "non-empty list"),
    (lambda f: f["nodes"].append(dict(f["nodes"][0])), "duplicate node name"),
    (lambda f: f["wires"].append(["geo", 0, "nope"]), "is not a declared node"),
    (lambda f: f.__setitem__("display", "nope"), "is not a declared node"),
    (lambda f: f["nodes"][0].__setitem__("position", [1]), "must be [x, y]"),
    (lambda f: f["nodes"][0].__setitem__("parms", []), "parms must be an object"),
    (lambda f: f["wires"].append(["geo", "x", "camera"]), "not an integer"),
])
def test_validate_fixture_catches(mutate, fragment):
    """Each mutation is a malformed fixture that would otherwise fail
    mid-build, after the reconciler had already created nodes."""
    fx = load_fx()
    mutate(fx)
    with pytest.raises(fixtures.FixtureError) as e:
        fixtures.validate_fixture(fx, name=FIXTURE_NAME)
    assert fragment in str(e.value)


# ---------------------------------------------------------------- canonicalizer


def test_canonicalizer_is_single_sourced_with_autoresearch():
    """The brief's ONE-source-of-truth requirement, asserted by identity.

    Fails the moment harness/autoresearch/probes.py grows its own copy of the
    filter list -- at which point a fixture baseline would mean one thing to
    the evidence harness and another to the reconciler.
    """
    sys.path.insert(0, str(REPO / "harness" / "autoresearch"))
    try:
        import probes  # noqa: PLC0415
    finally:
        sys.path.pop(0)
    assert probes.canonicalize_usda is canonical.canonicalize_usda
    assert probes.CANONICALIZER_VERSION is canonical.CANONICALIZER_VERSION
    assert tuple(probes._C1_RULES) == tuple(canonical.C1_RULES)


def test_canonicalizer_strips_exactly_the_declared_rules():
    """Fails if a rule stops firing (silent baseline drift) or a new one
    starts eating scene content."""
    text = "\n".join([
        "#usda 1.0",
        '    doc = "2026-08-05T18:26:46 built"',
        "    subLayers = [@anon:0000023F@]",
        "    customData = { string HoudiniCreatorNode = 'x' }",
        "    HoudiniEditorNodes = [3]",
        "def Xform \"geo\"   ",
        "{",
        "}",
    ]) + "\n"
    assert canonical.canonicalize_usda(text) == (
        'def Xform "geo"\n{\n}\n'
    )


def test_canonicalizer_version_matches_the_committed_fixture_baseline():
    """Fails if the canonicalizer is bumped without re-baselining fixtures --
    the exact drift that turns a green oracle into a lie."""
    fx = load_fx()
    assert fx["baseline"]["canonicalizer"] == canonical.CANONICALIZER_VERSION


# ------------------------------------------------------- c3 / R-M5-1 (env paths)


def _env(**kw):
    return canonical.houdini_env_map(lambda n: kw.get(n, ""))


def test_c3_normalizes_an_env_derived_path_back_to_its_token():
    """R-M5-1. Fails if rule 5 stops firing -- at which point every fixture
    baseline silently goes back to pinning the directory it was cut in."""
    a = "C:/Users/User/SYNAPSE/.claude/worktrees/m5b-rulings"
    b = "C:/Users/User/SYNAPSE"
    line = '        asset[] f = @%s/render/untitled.render_settings.0001.exr@'
    ca = canonical.canonicalize_usda(line % a + "\n", env=_env(**{"$HIP": a}))
    cb = canonical.canonicalize_usda(line % b + "\n", env=_env(**{"$HIP": b}))
    assert ca == cb
    assert "$HIP/render/untitled.render_settings.0001.exr" in ca
    assert "C:/Users" not in ca


def test_c3_normalizes_a_path_embedded_mid_line():
    """VERIFIED-RUNTIME 22.0.368: the $HIP expansion also appears INSIDE a
    query string (``&savepath=...&``), not only as a whole value. Fails if the
    rule is ever narrowed to line-leading or whole-value matching, which would
    leave HoudiniVolumeFilePaths machine-local while every other line looked
    clean."""
    a, b = "C:/wt/a", "C:/some/other/root"
    line = "  asset[] v = [@op:/stage/geo&savepath=%s/usd/geo.usd&t=0@]"
    ca = canonical.canonicalize_usda(line % a + "\n", env=_env(**{"$HIP": a}))
    cb = canonical.canonicalize_usda(line % b + "\n", env=_env(**{"$HIP": b}))
    assert ca == cb
    assert "savepath=$HIP/usd/geo.usd" in ca


def test_c3_refuses_bare_word_env_values():
    """The guard that keeps rule 5 from being worse than the drift it fixes.

    ``$HIPNAME`` expands to ``untitled`` and ``$OS`` to the NODE NAME. VERIFIED-
    RUNTIME 22.0.368: ``untitled`` appears 240 times in the composed stage.
    Substituting those by value would rewrite genuine scene content.

    Fails if the path guard is loosened -- and the second assertion shows the
    damage that would do: a prim legitimately named ``untitled`` gets rewritten.
    """
    env = _env(**{"$HIPNAME": "untitled", "$OS": "render_settings",
                  "$HIP": "C:/wt/a"})
    assert "$HIPNAME" not in env
    assert "$OS" not in env
    assert "$HIP" in env
    text = 'def Xform "untitled" { string s = "render_settings" }\n'
    assert canonical.canonicalize_usda(text, env=env) == text


def test_c3_substitution_order_is_deterministic():
    """VERIFIED-RUNTIME 22.0.368: ``$HIP`` and ``$JOB`` expand to the SAME
    directory, so whichever is applied first is the token that lands in the
    canonical text. Fails if the ordering stops being pinned, at which point
    the same stage could hash two ways in two processes -- a baseline that
    disagrees with itself."""
    same = "C:/Users/User/SYNAPSE"
    env = _env(**{"$HIP": same, "$JOB": same})
    out = {canonical.canonicalize_usda("  p = %s/render/x.exr\n" % same,
                                       env=env) for _ in range(8)}
    assert len(out) == 1
    assert "$HIP/render/x.exr" in out.pop()


def test_c3_prefers_the_longer_path_when_one_prefixes_another():
    """Fails if substitutions are applied shortest-first: ``C:/a`` would eat
    the prefix of ``C:/a/b`` and leave ``$JOB/b/render`` -- a token that no
    longer corresponds to any real variable, and one that differs by machine
    anyway."""
    env = _env(**{"$JOB": "C:/a", "$HIP": "C:/a/b"})
    out = canonical.canonicalize_usda("  p = C:/a/b/render/x.exr\n", env=env)
    assert "$HIP/render/x.exr" in out


def test_c3_without_env_reduces_to_the_c2_result():
    """The documented footgun, asserted so it stays documented rather than
    discovered. Fails if omitting ``env`` ever silently starts normalizing --
    which would make an unportable baseline indistinguishable from a portable
    one."""
    a, b = "C:/wt/a", "C:/wt/bbbb"
    line = "  p = %s/render/x.exr\n"
    assert (canonical.canonicalize_usda(line % a, env={})
            != canonical.canonicalize_usda(line % b, env={}))


def test_every_baseline_producer_passes_env():
    """Named in ``canonical.canonicalize_usda``'s docstring; this is it.

    A baseline cut without ``env`` is machine-local while wearing a c3 label.
    Every call site that turns composed USD into a committed number must pass
    it. Fails the moment someone adds a producer that forgets -- which is
    exactly how M5-F1 happened the first time.
    """
    producers = [
        REPO / "harness" / "autoresearch" / "probes.py",
        REPO / "harness" / "blocks" / "invariants_m5.py",
    ]
    for path in producers:
        src = path.read_text(encoding="utf-8")
        for chunk in src.split("canonicalize_usda(")[1:]:
            head = chunk[:200]
            if head.lstrip().startswith(("text", "\n", '"')):
                continue        # the def / import line, not a call
            assert "env=" in head, (
                "%s calls canonicalize_usda without env= -- that produces a "
                "machine-local hash under a c3 label" % path.name)


def test_superseded_baseline_is_recorded_not_overwritten():
    """R-M5-1 said: do not silently overwrite history. Fails if a future
    re-baseline drops the trail, leaving a committed number with no account of
    what it replaced or why."""
    fx = load_fx()
    old = fx.get("superseded_baselines")
    assert isinstance(old, list) and old
    prior = old[0]
    assert prior["canonicalizer"] == "c2"
    assert prior["sha256"] == (
        "8bb057619efe5cb2e3b7e6b7fb82bcb1bdd8d8a65017eb0f27aba6813b060ee7")
    assert prior["superseded_by"] == "R-M5-1"
    assert prior["reason"]
    assert prior["sha256"] != fx["baseline"]["sha256"]


def test_the_committed_baseline_declares_itself_environment_independent():
    """The claim c3 exists to make. Fails if a fixture is re-baselined back to
    a machine-local number without saying so -- which is the state M5 shipped
    in and R-M5-1 closed."""
    fx = load_fx()
    assert fx["baseline"]["environment_independent"] is True
    assert fx["baseline"]["canonicalizer"] == "c3"
    assert fx["baseline"]["producer"]


# ---------------------------------------------------------------- planner: build


def test_clean_stage_plans_a_full_build():
    fx = load_fx()
    p = planmod.build_plan(fx, clean_snapshot(), box_name="BLOCKS_solaris_basic")
    assert not p.blocked
    assert p.create_box is True
    assert p.create_nodes == [
        "geo", "dome_light", "materials", "camera", "render_settings",
    ]
    assert p.delete_nodes == []
    assert p.ops == 6          # 5 nodes + the box


def test_already_applied_is_a_true_noop():
    """F-3 in pure form. Fails if any comparison in the planner is
    asymmetric -- if it were, every call would report phantom work and the
    'no-op on re-apply' contract would be prose, not behaviour."""
    fx = load_fx()
    p = planmod.build_plan(fx, applied_snapshot(fx), box_name="BLOCKS_solaris_basic")
    assert p.ops == 0
    assert p.to_dict()["ops"] == 0
    assert not p.blocked


# ---------------------------------------------------------------- planner: D2


def test_collision_outside_the_box_blocks_everything():
    """D2. Fails if a colliding plan carries ANY create or delete intent."""
    fx = load_fx()
    snap = clean_snapshot(outside={"camera": "cam", "geo": "null"})
    p = planmod.build_plan(fx, snap, box_name="BLOCKS_solaris_basic")
    assert p.blocked
    assert sorted(c["name"] for c in p.collisions) == ["camera", "geo"]
    assert p.create_nodes == []
    assert p.delete_nodes == []
    assert p.create_box is False
    assert p.ops == 0


def test_collision_report_names_every_clash_not_just_the_first():
    fx = load_fx()
    snap = clean_snapshot(outside={n["name"]: "null" for n in fx["nodes"]})
    p = planmod.build_plan(fx, snap, box_name="BLOCKS_solaris_basic")
    assert len(p.collisions) == 5


def test_collision_survives_a_partially_applied_box():
    """The nastiest D2 case: our box exists and holds some nodes, and the
    artist separately owns one of our names outside it. Fails if the planner
    only checks collisions on a clean stage."""
    fx = load_fx()
    snap = applied_snapshot(fx)
    del snap["box_members"]["camera"]
    snap["outside_names"]["camera"] = "null"
    p = planmod.build_plan(fx, snap, box_name="BLOCKS_solaris_basic")
    assert p.blocked
    assert p.create_nodes == [] and p.delete_nodes == []


# ---------------------------------------------------------------- planner: D3


def test_artist_nodes_outside_the_box_are_never_deletion_candidates():
    """D3. Fails if any deletion candidate is derived from outside_names."""
    fx = load_fx()
    snap = applied_snapshot(fx, outside={
        "my_hero_light": "domelight",
        "wip_backup": "null",
        "geo_OLD": "sopcreate",        # near-miss name, deliberately
    })
    p = planmod.build_plan(fx, snap, box_name="BLOCKS_solaris_basic")
    assert p.delete_nodes == []
    assert p.ops == 0


def test_delete_scope_is_drawn_from_the_box_source_shape():
    """D3 as a source property, not just a behaviour.

    Fails if plan.py ever reads outside_names outside of collision detection
    -- the shape the ruling asked to be provable from the code.
    """
    src = (REPO / "python" / "synapse" / "blocks" / "plan.py").read_text(
        encoding="utf-8")
    body = src.split("def build_plan", 1)[1]
    # inside build_plan, outside_names must not appear at all: collisions()
    # is the only reader, and it is a separate function.
    assert "outside_names" not in body, (
        "build_plan reads outside_names directly -- D3 requires deletion "
        "candidates to come only from the enumerated box."
    )
    collide = src.split("def collisions", 1)[1].split("@dataclass", 1)[0]
    assert "outside_names" in collide


def _with_stray(fx, name="leftover", outside=None):
    snap = applied_snapshot(fx, outside=outside)
    snap["box_members"][name] = {
        "type": "null", "type_base": "null", "position": [5.0, 5.0],
        "display": False, "inputs": {}, "parms": {}, "parms_missing": [],
    }
    return snap


def test_stray_inside_the_box_is_ejected_not_deleted():
    """R-M5-3, ruled 2026-08-06 -- OVERRIDES what M5 shipped.

    A member the fixture does not declare was put there by the artist's drag,
    not by us. It leaves the box and stays alive. This replaces M5's
    ``test_stray_inside_the_box_is_deleted``: a ruled behaviour change, not a
    weakened test -- the assertion is strictly more specific, because
    ``delete_nodes`` must now be provably EMPTY where it used to hold the name.

    Fails if a stray ever re-enters ``delete_nodes`` -- i.e. if the reconciler
    goes back to destroying artist work it did not create.
    """
    fx = load_fx()
    p = planmod.build_plan(fx, _with_stray(fx),
                           box_name="BLOCKS_solaris_basic")
    assert p.eject_nodes == ["leftover"]
    assert p.delete_nodes == []
    assert p.create_nodes == []
    assert p.recreate_nodes == []
    assert p.ops == 1


def test_ejection_is_counted_as_an_op():
    """Fails if ``ops`` ignores ejections -- which would make an apply that
    ejects a node report ``ops == 0`` and take the NOOP early-return, so the
    ejection would never actually run."""
    fx = load_fx()
    assert planmod.build_plan(fx, applied_snapshot(fx),
                              box_name="BLOCKS_solaris_basic").ops == 0
    p = planmod.build_plan(fx, _with_stray(fx),
                           box_name="BLOCKS_solaris_basic")
    assert p.ops == 1
    assert "eject_nodes" in p.to_dict()
    assert p.to_dict()["eject_nodes"] == ["leftover"]


def test_ejection_converges_on_the_next_apply():
    """Idempotence, the property M5-F2 was found by losing.

    Once the stray is out of the box it is an ordinary outside node, so the
    next plan must be empty. Fails if an ejected node is somehow still a
    deletion or ejection candidate -- which would be a permanent one-op churn
    and would break F-3 forever.
    """
    fx = load_fx()
    after = applied_snapshot(fx, outside={"leftover": "null"})
    p = planmod.build_plan(fx, after, box_name="BLOCKS_solaris_basic")
    assert p.eject_nodes == []
    assert p.delete_nodes == []
    assert p.ops == 0
    assert not p.blocked


def test_an_ejected_stray_can_never_become_a_collision():
    """The safety property that makes ejection idempotent rather than a trap.

    A stray is BY DEFINITION a name the fixture does not declare, so putting it
    outside the box can never satisfy the collision test. Fails if
    ``collisions()`` ever starts matching on something other than declared
    names -- at which point ejecting would hand the very next apply a blocked
    plan and the reconciler would deadlock itself.
    """
    fx = load_fx()
    declared = {spec["name"] for spec in fx["nodes"]}
    assert "leftover" not in declared
    after = applied_snapshot(fx, outside={"leftover": "null"})
    assert planmod.collisions(fx, after) == []


def test_a_wrong_type_member_is_still_deleted_not_ejected():
    """R-M5-3 narrows the delete scope; it does not empty it.

    A DECLARED node of the wrong type must still be destroyed, because it has
    to be recreated as the type the fixture asks for. Fails if the eject rule
    was written too broadly and swallowed the recreate path -- which would
    leave the wrong node in the box forever with ``residual_ops`` never
    reaching zero.
    """
    fx = load_fx()
    snap = applied_snapshot(fx)
    snap["box_members"]["camera"]["type"] = "null"
    snap["box_members"]["camera"]["type_base"] = "null"
    p = planmod.build_plan(fx, snap, box_name="BLOCKS_solaris_basic")
    assert p.delete_nodes == ["camera"]
    assert p.eject_nodes == []
    assert p.recreate_nodes == ["camera"]


def test_remove_fixture_still_deletes_members_source_shape():
    """R-M5-3 explicitly leaves ``remove_fixture`` alone: "remove this fixture"
    is an instruction from the artist and a different act from reconciling.

    Asserted as a source property because the behaviour itself needs Houdini.
    Fails if someone "helpfully" makes remove_fixture eject too, at which point
    ``remove`` would stop removing and F-2 would break.
    """
    src = (REPO / "python" / "synapse" / "blocks" / "runtime.py").read_text(
        encoding="utf-8")
    body = src.split("def remove_fixture", 1)[1]
    assert "node.destroy()" in body
    assert "removeItem" not in body


# ---------------------------------------------------------------- planner: drift


def test_wrong_type_in_the_box_is_recreated_not_edited():
    fx = load_fx()
    snap = applied_snapshot(fx)
    # both fields, because that is what observe() reports for a real node
    snap["box_members"]["camera"]["type"] = "null"
    snap["box_members"]["camera"]["type_base"] = "null"
    p = planmod.build_plan(fx, snap, box_name="BLOCKS_solaris_basic")
    assert p.recreate_nodes == ["camera"]
    assert "camera" in p.delete_nodes and "camera" in p.create_nodes
    # a retyped node must not ALSO generate in-place parm edits
    assert [e for e in p.set_parms if e["node"] == "camera"] == []


def test_drifted_parm_is_planned():
    fx = load_fx()
    snap = applied_snapshot(fx)
    snap["box_members"]["geo"]["parms"]["primpath"] = "/somewhere_else"
    p = planmod.build_plan(fx, snap, box_name="BLOCKS_solaris_basic")
    assert p.set_parms == [{
        "node": "geo", "parm": "primpath",
        "current": "/somewhere_else", "desired": "/geo",
    }]
    assert p.ops == 1


def test_pulled_wire_is_planned():
    fx = load_fx()
    snap = applied_snapshot(fx)
    snap["box_members"]["camera"]["inputs"] = {}
    p = planmod.build_plan(fx, snap, box_name="BLOCKS_solaris_basic")
    assert p.set_inputs == [{
        "node": "camera", "index": 0, "current": None, "desired": "materials",
    }]


def test_moved_node_is_planned_but_epsilon_jitter_is_not():
    """Fails if the position comparison is exact -- which would make any
    future grid-snap a permanent one-op churn, breaking F-3 forever."""
    fx = load_fx()
    snap = applied_snapshot(fx)
    snap["box_members"]["geo"]["position"] = [0.0, 0.0 + planmod.POSITION_EPSILON / 2]
    assert planmod.build_plan(fx, snap, box_name="B").set_positions == []
    snap["box_members"]["geo"]["position"] = [3.0, 7.0]
    moved = planmod.build_plan(fx, snap, box_name="B").set_positions
    assert moved == [{"node": "geo", "current": [3.0, 7.0], "desired": [0.0, 0.0]}]


def test_display_flag_drift_is_planned_and_there_is_no_clear_list():
    """The LOP display flag is exclusive (VERIFIED-RUNTIME 22.0.368), so a
    'clear the other node' list could never fire usefully. Fails if one is
    reintroduced as a check that cannot fail (Law 1)."""
    fx = load_fx()
    snap = applied_snapshot(fx)
    snap["box_members"]["render_settings"]["display"] = False
    snap["box_members"]["geo"]["display"] = True
    p = planmod.build_plan(fx, snap, box_name="B")
    assert p.set_display == ["render_settings"]
    assert p.ops == 1
    assert not hasattr(p, "clear_display")


def test_undeclared_input_is_reported_not_severed():
    """An artist wired their node into ours at an index the fixture does not
    declare. Fails if the planner tries to disconnect it -- nothing in D1-D4
    authorises reaching outside the box to sever a wire."""
    fx = load_fx()
    snap = applied_snapshot(fx)
    snap["box_members"]["materials"]["inputs"][1] = "artist_thing"
    p = planmod.build_plan(fx, snap, box_name="B")
    assert p.unmanaged_inputs == [
        {"node": "materials", "index": 1, "source": "artist_thing"},
    ]
    assert p.set_inputs == []
    assert p.ops == 0


def test_missing_parm_is_surfaced_not_silently_skipped():
    """Law 3: a parm the fixture pins that the node type does not have is a
    fixture/build mismatch. Fails if it is swallowed."""
    fx = load_fx()
    snap = applied_snapshot(fx)
    snap["box_members"]["geo"]["parms"].pop("primpath")
    snap["box_members"]["geo"]["parms_missing"] = ["primpath"]
    p = planmod.build_plan(fx, snap, box_name="B")
    assert p.missing_parms == ["geo.primpath"]
    assert p.set_parms == []


def test_missing_box_alone_is_one_op():
    """Nodes present and correct but the box gone (artist deleted the box,
    keeping contents -- the documented destroy(False) default)."""
    fx = load_fx()
    snap = applied_snapshot(fx)
    snap["box_present"] = False
    p = planmod.build_plan(fx, snap, box_name="B")
    assert p.create_box is True and p.ops == 1


def test_plan_serializes_to_json():
    """The result crosses a JSON-RPC boundary. Fails if a dataclass or a
    non-serializable value leaks into the payload."""
    fx = load_fx()
    p = planmod.build_plan(fx, clean_snapshot(), box_name="B")
    json.dumps(p.to_dict())


# ---------------------------------------------------------------- comparators


@pytest.mark.parametrize("declared,live,base,expected", [
    ("domelight", "domelight::3.0", "domelight", True),
    ("domelight", "domelight::3.0", None, True),      # string fallback
    ("domelight", "domelight", "domelight", True),
    ("domelight::3.0", "domelight::3.0", "domelight", True),
    ("domelight::3.0", "domelight::2.0", "domelight", False),
    ("domelight::3.0", "domelight", "domelight", False),
    ("domelight", "null", "null", False),
    ("camera", "camera", "camera", True),
])
def test_type_matches(declared, live, base, expected):
    assert planmod.type_matches(declared, live, base) is expected


def test_versioned_node_type_does_not_plan_an_endless_recreate():
    """REGRESSION (VERIFIED-RUNTIME 22.0.368, found by the F-1..F-5 harness).

    createNode("domelight") produces a node whose type().name() is
    "domelight::3.0". Comparing the fixture literal against the raw type name
    reported a permanent mismatch, so every apply planned delete+recreate of
    dome_light, apply_fixture never converged, and F-3 could never be green.

    Fails if the base-name comparison is removed: this snapshot is a
    faithfully-applied stage as the live runtime actually reports it.
    """
    fx = load_fx()
    snap = applied_snapshot(fx)
    snap["box_members"]["dome_light"]["type"] = "domelight::3.0"
    snap["box_members"]["dome_light"]["type_base"] = "domelight"
    p = planmod.build_plan(fx, snap, box_name="B")
    assert p.recreate_nodes == []
    assert p.delete_nodes == [] and p.create_nodes == []
    assert p.ops == 0


def test_a_fixture_pinning_a_version_still_detects_the_wrong_one():
    """Fails if version-stripping is applied unconditionally -- a fixture
    that deliberately pins domelight::3.0 must not silently accept ::2.0."""
    fx = load_fx()
    for spec in fx["nodes"]:
        if spec["name"] == "dome_light":
            spec["type"] = "domelight::3.0"
    snap = applied_snapshot(fx)
    snap["box_members"]["dome_light"]["type"] = "domelight::2.0"
    snap["box_members"]["dome_light"]["type_base"] = "domelight"
    p = planmod.build_plan(fx, snap, box_name="B")
    assert p.recreate_nodes == ["dome_light"]


@pytest.mark.parametrize("a,b,expected", [
    ("/geo", "/geo", True),
    ("/geo", "/Geo", False),
    (1, 1.0, True),
    (1.0, 1.0000000001, True),
    (1.0, 1.1, False),
    ("1", 1, True),          # text-vs-number falls back to string compare
    (None, "/geo", False),
])
def test_parm_equal(a, b, expected):
    assert planmod.parm_equal(a, b) is expected
