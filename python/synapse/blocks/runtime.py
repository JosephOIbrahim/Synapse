"""BLOCKS reconciler runtime -- the ONLY module in this package that touches
``hou``.

``apply_fixture(name)`` means "make /stage match the definition", not "build
the definition":

    clean stage          -> build (nodes, exact names, parms, wires,
                            positions, display flag, box)
    already applied      -> NO-OP. ops == 0. Not delete-and-rebuild.
    partially applied /  -> reconcile inside the box to match; report
    drifted box contents    what changed
    artist nodes present -> untouched, always (D2/D3)
    artist node dragged  -> EJECTED from the box and LEFT ALIVE in the stage,
    into the box            never deleted (R-M5-3)

``remove_fixture(name)`` deletes the box members and the box. Nothing else.
That is unchanged by R-M5-3 and deliberately so: "remove this fixture" is an
explicit instruction from the artist, not the reconciler deciding on its own
that a node it did not create should stop existing.

The four rulings, and where each one lives in this file
------------------------------------------------------
D1  Ownership = network box. ``_ensure_box`` creates ``BLOCKS_<fixture>`` and
    every created node is added to it. Nodes stay flat in /stage -- native and
    directly editable. No USD customData is written anywhere in this module.

D2  Collisions fail loudly. ``apply_fixture`` builds a plan and returns
    immediately if ``plan.blocked``. The mutation block below that return is
    unreachable while a collision is outstanding, so "create NOTHING, delete
    NOTHING" is a control-flow property, not a promise.

D3  Delete scope = box members only. Deletion candidates enter the plan from
    ``snapshot["box_members"]``, which ``observe()`` builds by enumerating
    ``box.nodes(recurse=False)`` and keeping only direct children of the
    stage. No name pattern is ever matched against the wider graph.
    NARROWED by R-M5-3: within that scope, only a DECLARED-but-wrong-type
    member is destroyed. An UNDECLARED member is ejected instead.

D4  Seam = Dispatcher tool. Mounted by ``synapse.cognitive.tools.apply_fixture``
    (pure, zero-hou) which ships a three-line script into the Houdini process
    and calls the functions here.

Runtime facts this module is built on (VERIFIED-RUNTIME, build 22.0.368,
probed 2026-08-06 -- see harness/notes/_m5_*.py)
-----------------------------------------------------------------------
* ``createNode`` with a taken name does NOT raise. It silently auto-renames
  (``syn_probe_n1`` -> ``syn_probe_n3``). Collision detection therefore has to
  happen BEFORE creation; a post-hoc check is already too late. Every create
  below re-asserts the resulting name anyway, as a second line of defence.
* ``NetworkBox.destroy(destroy_contents=False)`` -- the default leaves members
  alive. ``remove_fixture`` destroys members explicitly and then the box.
* ``NetworkBox.removeItem(item)`` exists on 22.0.368 with the signature
  ``(self, item: NetworkMovableItem) -> void``. It drops membership and leaves
  the node alive in the stage with every authored property intact -- but it
  RAISES ``hou.OperationFailed`` when handed a non-member, so the eject pass
  reads the current membership set by name first (probed 2026-08-06,
  ``harness/notes/_m5b_eject_probe.py``).
* ``box.fitAroundContents()`` does NOT re-capture an ejected node, even one
  positioned inside the box's rectangle. Membership is explicit, not spatial,
  so the cosmetic fit at the end of an apply cannot silently undo an ejection.
* The LOP display flag is EXCLUSIVE: setting it clears every sibling.
* A String parm's authored value is ``unexpandedString()``, not ``eval()``.
  ``camera``'s default ``primpath`` is ``/cameras/$OS``, which EVALUATES to
  ``/cameras/camera`` -- exactly what the fixture declares. Comparing on
  ``eval()`` would report the node already correct and never author the
  literal.
* ``hou.undos.group()`` works in headless hython.
* Comparing a destroyed ``hou.Node`` raises ``hou.ObjectWasDeleted``, so node
  handles are dropped before a destroy pass, never after.
"""

from __future__ import annotations

import contextlib
from typing import Any, Dict, List, Optional

from synapse.blocks.fixtures import (
    FixtureError,
    box_name_for,
    declared_wires,
    load_fixture,
)
from synapse.blocks.plan import Plan, build_plan

try:  # pragma: no cover - exercised only inside Houdini
    import hou  # type: ignore
    HOU_AVAILABLE = True
except ImportError:
    hou = None  # type: ignore
    HOU_AVAILABLE = False

__all__ = [
    "HOU_AVAILABLE",
    "ReconcilerError",
    "StageNotFoundError",
    "apply_fixture",
    "observe",
    "remove_fixture",
    "require_hou",
]

DEFAULT_STAGE_PATH = "/stage"

STATUS_BUILT = "built"
STATUS_NOOP = "noop"
STATUS_RECONCILED = "reconciled"
STATUS_COLLISION = "collision"
STATUS_REMOVED = "removed"
STATUS_ABSENT = "absent"
STATUS_INCOMPLETE = "incomplete"
STATUS_PLANNED = "planned"


class ReconcilerError(RuntimeError):
    """The reconciler could not do what it was asked."""


class StageNotFoundError(ReconcilerError):
    """The requested stage context does not exist in this session."""


def require_hou() -> None:
    if not HOU_AVAILABLE:
        raise ReconcilerError(
            "synapse.blocks.runtime requires Houdini (import hou failed). "
            "The planner in synapse.blocks.plan is pure Python and runs "
            "without it."
        )


# --------------------------------------------------------------------- read


def _stage_node(stage_path: str):
    node = hou.node(stage_path)
    if node is None:
        raise StageNotFoundError("%r is not present in this session" % stage_path)
    return node


def _type_base(node_type) -> str:
    """The version-stripped identity of a node type.

    ``NodeType.nameComponents()`` returns ``(scope, namespace, name, version)``
    -- ``('', '', 'domelight', '3.0')`` for the node ``createNode("domelight")``
    actually produces. That third component is the identity a fixture's bare
    type literal is written against; see ``plan.type_matches``.
    """
    fn = getattr(node_type, "nameComponents", None)
    if callable(fn):
        try:
            parts = fn()
            if len(parts) >= 3 and parts[2]:
                return str(parts[2])
        except Exception:
            pass
    return str(node_type.name()).split("::")[0]


def _known_type_bases(stage) -> set:
    """Every type name AND version-stripped base creatable under ``stage``."""
    names = set()
    for tname, ntype in stage.childTypeCategory().nodeTypes().items():
        names.add(tname)
        names.add(_type_base(ntype))
    return names


def _check_types_exist(stage, fixture: Dict[str, Any]) -> None:
    """Refuse a fixture naming a type this build cannot create.

    Fails when: a fixture written for another build names a type that is gone
    or renamed. ``createNode`` would raise ``hou.OperationFailed`` partway
    through the build, leaving a half-built network behind -- the undo group
    makes that undoable but does NOT unwind it. Checking first means nothing
    is created at all.
    """
    known = _known_type_bases(stage)
    missing = sorted({spec["type"] for spec in fixture["nodes"]
                      if spec["type"] not in known})
    if missing:
        raise ReconcilerError(
            "fixture names node type(s) this build cannot create: %s "
            "(build %s). Nothing was created."
            % (", ".join(missing), hou.applicationVersionString())
        )


def _read_parm(parm) -> Any:
    """The AUTHORED value of a parm -- see the module docstring on $OS."""
    try:
        if parm.parmTemplate().type() == hou.parmTemplateType.String:
            return parm.unexpandedString()
    except Exception:
        pass
    try:
        return parm.eval()
    except Exception as e:      # a parm we cannot read is drift we cannot judge
        raise ReconcilerError(
            "could not read parm %s: %s" % (parm.path(), e)
        ) from e


def _node_inputs(node) -> Dict[int, Optional[str]]:
    """``{index: source node name}`` for connected inputs only.

    VERIFIED-RUNTIME: ``node.inputs()`` returns the connected prefix, not a
    connector-width padded tuple -- one connection gives a length-1 tuple, and
    disconnecting gives ``()``.
    """
    out: Dict[int, Optional[str]] = {}
    for i, src in enumerate(node.inputs()):
        if src is not None:
            out[i] = src.name()
    return out


def observe(
    fixture: Dict[str, Any],
    box_name: str,
    stage_path: str = DEFAULT_STAGE_PATH,
) -> Dict[str, Any]:
    """Snapshot the live stage as the plain dict ``build_plan`` consumes.

    The D3 boundary is drawn here and nowhere else: ``box_members`` comes from
    enumerating the box; ``outside_names`` comes from the stage's children.
    They are disjoint by construction, and only the first is ever a deletion
    candidate.
    """
    require_hou()
    stage = _stage_node(stage_path)
    box = stage.findNetworkBox(box_name)

    declared = {spec["name"]: spec for spec in fixture["nodes"]}

    members: Dict[str, Any] = {}
    if box is not None:
        for node in box.nodes(recurse=False):
            # Structural belt: a box only ever holds items from its own
            # network, but if that ever stops being true, a foreign node must
            # not become a deletion candidate.
            if node.parent().path() != stage.path():
                continue
            name = node.name()
            entry: Dict[str, Any] = {
                "type": node.type().name(),
                "type_base": _type_base(node.type()),
                "position": [float(node.position()[0]), float(node.position()[1])],
                "display": bool(node.isDisplayFlagSet()),
                "inputs": _node_inputs(node),
                "parms": {},
                "parms_missing": [],
            }
            spec = declared.get(name)
            if spec is not None:
                for pname in (spec.get("parms") or {}):
                    parm = node.parm(pname)
                    if parm is None:
                        entry["parms_missing"].append(pname)
                    else:
                        entry["parms"][pname] = _read_parm(parm)
            members[name] = entry

    outside: Dict[str, str] = {}
    for child in stage.children():
        cname = child.name()
        if cname in members:
            continue
        outside[cname] = child.type().name()

    return {
        "stage_path": stage.path(),
        "box_name": box_name,
        "box_present": box is not None,
        "box_members": members,
        "outside_names": outside,
    }


# -------------------------------------------------------------------- write


def _undo_group(label: str):
    """``hou.undos.group`` when the session offers it, else a no-op context.

    Returns (context_manager, wrapped: bool) so the caller can REPORT whether
    the mutation was actually grouped rather than claim it was.
    """
    undos = getattr(hou, "undos", None)
    group = getattr(undos, "group", None) if undos is not None else None
    if group is None:
        return contextlib.nullcontext(), False
    try:
        return group(label), True
    except Exception:
        return contextlib.nullcontext(), False


def _create_node(stage, spec: Dict[str, Any]):
    """Create one fixture node with its EXACT name, or fail loud.

    Fails when: Houdini auto-renames because the name was taken. That should
    be impossible here -- the collision gate already ran -- so reaching this
    raise means the gate has a hole, which is exactly when you want a hard
    error rather than a quietly mis-named network.
    """
    requested = spec["name"]
    node = stage.createNode(spec["type"], requested)
    if node.name() != requested:
        actual = node.name()
        node.destroy()
        raise ReconcilerError(
            "Houdini renamed %r to %r on creation -- the name was already "
            "taken and the collision gate did not catch it. Nothing was kept."
            % (requested, actual)
        )
    return node


def _apply_parms(node, spec: Dict[str, Any], missing: List[str]) -> None:
    for pname, pval in (spec.get("parms") or {}).items():
        parm = node.parm(pname)
        if parm is None:
            missing.append("%s.%s" % (node.name(), pname))
            continue
        parm.set(pval)


def _apply_position(node, spec: Dict[str, Any]) -> None:
    pos = spec.get("position")
    if pos:
        node.setPosition(hou.Vector2(float(pos[0]), float(pos[1])))


def _verdict(status: str, fixture_name: str, plan: Plan,
             result: Dict[str, Any]) -> str:
    """The one line the panel renders. Built from structure, never prose.

    R-M5-3: an ejection is APPENDED as its own sentence rather than folded into
    the counts. Two reasons. The artist has to be told that a node they put in
    the box is no longer in it -- silence there is the Law 3 defect wearing a
    coat. And appending leaves every no-ejection verdict byte-identical to what
    M5 shipped, so the F-1..F-5 strings recorded in receipts/M5.json still hold.
    """
    line = _verdict_base(status, fixture_name, plan, result)
    ejected = list(result.get("ejected") or [])
    if ejected:
        line += (" %d node(s) not declared by the fixture were ejected from "
                 "the box and left in the stage: %s."
                 % (len(ejected), ", ".join(ejected)))
    return line


def _verdict_base(status: str, fixture_name: str, plan: Plan,
                  result: Dict[str, Any]) -> str:
    box = result.get("box", "")
    if status == STATUS_COLLISION:
        names = ", ".join(c["name"] for c in plan.collisions)
        return ("%s NOT applied - %d name collision(s) outside %s: %s. "
                "Nothing was created or deleted."
                % (fixture_name, len(plan.collisions), box, names))
    if status == STATUS_NOOP:
        return "%s already matches %s - no changes (0 ops)." % (fixture_name, box)
    if status == STATUS_BUILT:
        return ("%s built in %s - %d node(s), %d op(s)."
                % (fixture_name, box, len(result.get("created", [])), result["ops"]))
    if status == STATUS_RECONCILED:
        return ("%s reconciled in %s - %d created, %d deleted, %d changed "
                "(%d ops)."
                % (fixture_name, box, len(result.get("created", [])),
                   len(result.get("deleted", [])), len(result.get("changed", [])),
                   result["ops"]))
    if status == STATUS_REMOVED:
        return ("%s removed - %d node(s) and the box %s deleted."
                % (fixture_name, len(result.get("deleted", [])), box))
    if status == STATUS_ABSENT:
        return "%s is not applied - no box %s in the stage." % (fixture_name, box)
    if status == STATUS_PLANNED:
        return ("%s dry run - %d op(s) would be performed in %s."
                % (fixture_name, result["ops"], box))
    if status == STATUS_INCOMPLETE:
        return ("%s applied but %d op(s) remain outstanding - the reconciler "
                "did not converge. Do not trust this stage."
                % (fixture_name, result.get("residual_ops", -1)))
    return "%s: %s" % (fixture_name, status)


def _base_result(name: str, fx: Dict[str, Any], box_name: str,
                 stage_path: str) -> Dict[str, Any]:
    return {
        "fixture": fx.get("fixture", name),
        "fixture_version": fx.get("version"),
        "stage_path": stage_path,
        "box": box_name,
        "build": hou.applicationVersionString() if HOU_AVAILABLE else None,
        "applied": False,
        "ops": 0,
        "collisions": [],
        "per_node": [],
        "created": [],
        "deleted": [],
        # R-M5-3: box members the fixture does not declare. Membership dropped,
        # node LEFT ALIVE in the stage. Distinct from "deleted" on purpose --
        # the caller must be able to tell "we destroyed it" from "we let go of
        # it", because only one of those is recoverable by a drag.
        "ejected": [],
        "changed": [],
        "unmanaged_inputs": [],
        "missing_parms": [],
        "undo_grouped": False,
        # Set when honouring the fixture's declared display node moved the
        # network's exclusive display flag off another node.
        "display_taken_from": None,
        "display_taken_from_outside_box": False,
    }


def apply_fixture(
    name: str,
    stage_path: str = DEFAULT_STAGE_PATH,
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Make ``stage_path`` match the fixture definition.

    Returns a structured result every call::

        {applied, ops, collisions, box, per_node, ...}

    Never raises on a collision -- a collision is a result, not an exception.
    Raises ``FixtureError`` for an unknown or malformed fixture and
    ``StageNotFoundError`` for a missing context, because those are caller
    errors that no amount of reconciling can fix.
    """
    require_hou()
    fx = load_fixture(name)
    box_name = box_name_for(fx, name)
    result = _base_result(name, fx, box_name, stage_path)

    _check_types_exist(_stage_node(stage_path), fx)
    snapshot = observe(fx, box_name, stage_path)
    plan = build_plan(fx, snapshot, box_name=box_name)
    result["plan"] = plan.to_dict()
    result["ops"] = plan.ops
    result["unmanaged_inputs"] = list(plan.unmanaged_inputs)
    result["missing_parms"] = list(plan.missing_parms)

    # -- D2: everything below this return is unreachable while blocked ------
    if plan.blocked:
        result["collisions"] = list(plan.collisions)
        result["status"] = STATUS_COLLISION
        result["applied"] = False
        result["ops"] = 0
        result["per_node"] = [
            {"name": c["name"], "action": "blocked", "detail": c["reason"]}
            for c in plan.collisions
        ]
        result["verdict"] = _verdict(STATUS_COLLISION, result["fixture"], plan, result)
        return result

    if plan.ops == 0:
        result["status"] = STATUS_NOOP
        result["applied"] = True
        result["per_node"] = [
            {"name": n, "action": "unchanged"} for n in sorted(snapshot["box_members"])
        ]
        result["verdict"] = _verdict(STATUS_NOOP, result["fixture"], plan, result)
        return result

    if dry_run:
        result["status"] = STATUS_PLANNED
        result["applied"] = False
        result["verdict"] = _verdict(STATUS_PLANNED, result["fixture"], plan, result)
        return result

    was_empty_box = not snapshot["box_present"]
    stage = _stage_node(stage_path)
    declared = {spec["name"]: spec for spec in fx["nodes"]}
    wires = declared_wires(fx)
    missing_parms: List[str] = []
    actions: Dict[str, Dict[str, Any]] = {}

    ctx, grouped = _undo_group("SYNAPSE BLOCKS: apply %s" % result["fixture"])
    result["undo_grouped"] = grouped
    with ctx:
        # 1. the box -- D1 ownership, created before anything can enter it
        box = stage.findNetworkBox(box_name)
        if box is None:
            box = stage.createNetworkBox(box_name)
            if box.name() != box_name:
                actual = box.name()
                box.destroy()
                raise ReconcilerError(
                    "Houdini renamed the network box %r to %r -- a box with "
                    "that name already existed. Nothing was kept."
                    % (box_name, actual)
                )

        # 2. EJECTIONS (R-M5-3). A member the fixture does not declare was put
        #    there by the artist's drag, not by us, so we drop the membership
        #    and leave the node alive in /stage. Runs BEFORE the destroy pass
        #    so that if a later step raises, the node that must survive already
        #    has.
        #
        #    VERIFIED-RUNTIME 22.0.368 (harness/notes/_m5b_eject_probe.py):
        #    box.removeItem(node) leaves the node in the stage with every
        #    authored property intact and drops it from box.nodes(); but
        #    removeItem on a NON-member raises hou.OperationFailed. Hence the
        #    membership set below -- read by NAME, never by holding node
        #    handles across a mutation (M5-F8).
        current_members = {n.name() for n in box.nodes(recurse=False)}
        for stray in plan.eject_nodes:
            node = stage.node(stray)
            if node is None:
                actions[stray] = {"action": "eject_skipped",
                                  "detail": "already absent"}
                continue
            if stray not in current_members:
                actions[stray] = {"action": "eject_skipped",
                                  "detail": "not a box member"}
                continue
            box.removeItem(node)
            result["ejected"].append(stray)
            actions[stray] = {
                "action": "ejected",
                "detail": "not declared by the fixture - ejected, not deleted",
            }

        # 3. deletions. Candidates were enumerated FROM THE BOX (D3) and are
        #    now exactly the DECLARED-but-wrong-type nodes, which step 4
        #    recreates. Handles are resolved and dropped inside the loop; none
        #    survives it.
        for dead in plan.delete_nodes:
            node = stage.node(dead)
            if node is None:
                actions[dead] = {"action": "delete_skipped",
                                 "detail": "already absent"}
                continue
            reason = ("wrong type inside the box"
                      if dead in plan.recreate_nodes
                      else "not declared by the fixture")
            node.destroy()
            result["deleted"].append(dead)
            actions[dead] = {"action": "deleted", "detail": reason}

        # 4. creations, in fixture definition order
        created_nodes: Dict[str, Any] = {}
        for cname in plan.create_nodes:
            spec = declared[cname]
            node = _create_node(stage, spec)
            created_nodes[cname] = node
            box.addItem(node)
            _apply_parms(node, spec, missing_parms)
            _apply_position(node, spec)
            result["created"].append(cname)
            prev = actions.get(cname, {}).get("action")
            actions[cname] = {
                "action": "recreated" if prev == "deleted" else "created",
                "detail": spec["type"],
            }

        # 5. in-place reconcile of surviving members
        for entry in plan.set_parms:
            node = stage.node(entry["node"])
            parm = node.parm(entry["parm"]) if node is not None else None
            if parm is None:
                missing_parms.append("%s.%s" % (entry["node"], entry["parm"]))
                continue
            parm.set(entry["desired"])
            result["changed"].append(
                {"node": entry["node"], "field": "parm:" + entry["parm"],
                 "from": entry["current"], "to": entry["desired"]})
            actions.setdefault(entry["node"], {"action": "reconciled",
                                               "detail": "parms"})

        for entry in plan.set_positions:
            node = stage.node(entry["node"])
            if node is None:
                continue
            _apply_position(node, declared[entry["node"]])
            result["changed"].append(
                {"node": entry["node"], "field": "position",
                 "from": entry["current"], "to": entry["desired"]})
            actions.setdefault(entry["node"], {"action": "reconciled",
                                               "detail": "position"})

        # 6. wiring. Enforced for EVERY declared wire, not only the planned
        #    deltas: a delete in step 2 can sever a connection whose plan entry
        #    said "already correct", and a recreate replaces the object a
        #    surviving node was wired to. setInput to the value already there
        #    is a no-op, so over-enforcing is safe and under-enforcing is not.
        for dst, want in wires.items():
            dst_node = stage.node(dst)
            if dst_node is None:
                continue
            for idx, src in want.items():
                src_node = stage.node(src)
                if src_node is None:
                    continue
                current = dst_node.inputs()
                have = current[idx].name() if (idx < len(current)
                                               and current[idx] is not None) else None
                if have != src:
                    dst_node.setInput(int(idx), src_node)
                    result["changed"].append(
                        {"node": dst, "field": "input:%d" % idx,
                         "from": have, "to": src})
                    actions.setdefault(dst, {"action": "reconciled",
                                             "detail": "wiring"})

        # 7. display flag -- exclusive, so setting it is the whole operation.
        #
        #    The LOP display flag is a single network-wide slot. A fixture that
        #    declares a display node cannot be honoured without taking that
        #    slot from whoever holds it, and the holder may be an artist node
        #    outside the box. There is no implementation that both matches the
        #    definition and leaves the flag alone -- they are the same slot.
        #    So: honour the fixture, and REPORT the transfer by name rather
        #    than letting it happen silently (Law 3).
        #
        #    R-M5-2 (ruled 2026-08-06): KEEP EXACTLY THIS. The fixture's
        #    declared display node is honoured, the transfer is reported by
        #    name, and F-4 / F-4b stay split. The two alternatives were put up
        #    and rejected, both for the same defect:
        #
        #      "never take the flag from a node outside the box" and
        #      "take it only when the box is first created"
        #
        #    each leave the fixture's declared display PERMANENTLY
        #    UNSATISFIABLE whenever an outsider holds the flag. observe() would
        #    keep reporting display=False on the declared tail, build_plan
        #    would keep emitting set_display, and the post-mutation
        #    self-verification below would keep returning residual_ops=1 --
        #    forever. That breaks idempotence (F-3) and makes apply_fixture
        #    report status=incomplete on a stage that is, by the fixture's own
        #    definition, as correct as that option permits. A reconciler that
        #    can never converge is worse than one that moves a flag and says so.
        display_target = fx.get("display")
        if display_target:
            tail = stage.node(display_target)
            if tail is not None and not tail.isDisplayFlagSet():
                previous = next(
                    (c.name() for c in stage.children() if c.isDisplayFlagSet()),
                    None,
                )
                tail.setDisplayFlag(True)
                if previous is not None and previous != display_target:
                    result["display_taken_from"] = previous
                    result["display_taken_from_outside_box"] = (
                        previous not in snapshot["box_members"]
                    )
                actions.setdefault(display_target, {"action": "reconciled",
                                                    "detail": "display"})

        try:
            box.fitAroundContents()
        except Exception:
            pass        # cosmetic only; never fails an apply

    # -- self-verification. The check that makes "applied" mean something. --
    after = observe(fx, box_name, stage_path)
    residual = build_plan(fx, after, box_name=box_name)
    result["residual_ops"] = residual.ops
    result["missing_parms"] = sorted(set(result["missing_parms"]) | set(missing_parms)
                                     | set(residual.missing_parms))
    result["unmanaged_inputs"] = list(residual.unmanaged_inputs)

    if residual.ops == 0 and not residual.blocked:
        result["applied"] = True
        result["status"] = STATUS_BUILT if was_empty_box else STATUS_RECONCILED
    else:
        result["applied"] = False
        result["status"] = STATUS_INCOMPLETE
        result["residual_plan"] = residual.to_dict()

    result["per_node"] = [
        dict({"name": n}, **actions.get(n, {"action": "unchanged"}))
        for n in sorted(set(list(actions) + list(after["box_members"])))
    ]
    result["verdict"] = _verdict(result["status"], result["fixture"], plan, result)
    return result


def remove_fixture(
    name: str,
    stage_path: str = DEFAULT_STAGE_PATH,
) -> Dict[str, Any]:
    """Delete the fixture's box members and the box. Nothing else (D3).

    Fails when: nothing. An absent box is ``status == "absent"`` with zero
    ops, not an error -- removing what is not there is a no-op, and Law 3
    wants that said out loud rather than dressed up as a success.
    """
    require_hou()
    fx = load_fixture(name)
    box_name = box_name_for(fx, name)
    result = _base_result(name, fx, box_name, stage_path)

    stage = _stage_node(stage_path)
    box = stage.findNetworkBox(box_name)
    if box is None:
        result["status"] = STATUS_ABSENT
        result["applied"] = False
        result["ops"] = 0
        result["verdict"] = _verdict(STATUS_ABSENT, result["fixture"],
                                     Plan(box_name=box_name), result)
        return result

    # D3: the delete set is the box's own membership, read once, by
    # enumeration. Names are captured BEFORE any destroy -- comparing a
    # destroyed hou.Node raises hou.ObjectWasDeleted.
    member_names = sorted(
        n.name() for n in box.nodes(recurse=False)
        if n.parent().path() == stage.path()
    )

    ctx, grouped = _undo_group("SYNAPSE BLOCKS: remove %s" % result["fixture"])
    result["undo_grouped"] = grouped
    with ctx:
        for mname in member_names:
            node = stage.node(mname)
            if node is None:
                continue
            node.destroy()
            result["deleted"].append(mname)
        box.destroy()

    result["ops"] = len(result["deleted"]) + 1
    result["applied"] = False        # the fixture is no longer applied
    result["status"] = STATUS_REMOVED
    result["box_removed"] = True
    result["per_node"] = [{"name": n, "action": "deleted",
                           "detail": "box member"} for n in result["deleted"]]
    result["verdict"] = _verdict(STATUS_REMOVED, result["fixture"],
                                 Plan(box_name=box_name), result)
    return result
