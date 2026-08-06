"""BLOCKS reconcile planner -- the diff logic, in pure Python.

This module decides WHAT must change. ``synapse.blocks.runtime`` is the only
thing that changes it. The split exists so the rulings D2 and D3 are testable
without a Houdini session and without a mocked ``hou`` (Constitution Law 1:
mock-hou tests assert your assumptions back at you).

Everything here operates on two plain dicts:

    fixture   -- the committed definition (see synapse.blocks.fixtures)
    snapshot  -- what the live stage looks like right now

Snapshot contract (produced by runtime.observe, never by this module)::

    {
      "stage_path":   "/stage",
      "box_name":     "BLOCKS_solaris_basic",
      "box_present":  True,
      "box_members":  {                    # DIRECT members, enumerated FROM
        "geo": {                           # the box -- never name-matched
          "type":     "sopcreate",         # against the wider graph (D3)
          "position": [0.0, 0.0],
          "display":  False,
          "inputs":   {0: "dome_light"},   # index -> sibling node NAME
          "parms":    {"primpath": "/geo"},# ONLY fixture-declared parm names
          "parms_missing": [],             # declared names absent on the node
        },
      },
      "outside_names": {"camera": "cam"},  # /stage children NOT in the box
    }

The D2 and D3 guarantees are structural properties of this file:

  D2  ``collisions()`` is consulted first and short-circuits the whole plan.
      A colliding plan carries empty create/delete lists -- there is no code
      path that mutates while a collision is outstanding.

  D3  Every deletion candidate is drawn from ``snapshot["box_members"]``,
      which the runtime builds by enumerating the box. No deletion candidate
      is ever derived from ``outside_names`` or from a name pattern. Grep
      this file for ``outside_names``: it appears only in collision
      detection, never in ``delete_nodes``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from synapse.blocks.fixtures import declared_wires

__all__ = [
    "POSITION_EPSILON",
    "Plan",
    "build_plan",
    "collisions",
    "parm_equal",
    "position_equal",
    "type_matches",
]

# Houdini stores node positions as float pairs. We only ever compare values we
# authored ourselves, but an exact == would make any future grid-snapping a
# permanent one-op churn that breaks F-3 (already-applied => ops == 0) forever.
# A tolerance is the difference between an idempotent reconciler and one that
# reports work every single call.
POSITION_EPSILON = 1e-4

_NUMERIC = (int, float)


def parm_equal(current: Any, desired: Any) -> bool:
    """Is the live parm value already what the fixture asks for?

    Numeric-vs-numeric compares as float within 1e-9; everything else compares
    as text. A fixture that writes ``1`` and a parm that evaluates to ``1.0``
    agree; a fixture that writes ``"/geo"`` and a parm holding ``"/Geo"`` do
    not.
    """
    if (isinstance(current, _NUMERIC) and not isinstance(current, bool)
            and isinstance(desired, _NUMERIC) and not isinstance(desired, bool)):
        return abs(float(current) - float(desired)) <= 1e-9
    return str(current) == str(desired)


def position_equal(current: Optional[Any], desired: Optional[Any]) -> bool:
    """Positions equal within ``POSITION_EPSILON``. Missing on either side
    means "nothing declared" and compares equal only if both are missing."""
    if desired is None:
        return True          # fixture declares no position -> nothing to enforce
    if current is None:
        return False
    try:
        return all(abs(float(a) - float(b)) <= POSITION_EPSILON
                   for a, b in zip(current, desired))
    except (TypeError, ValueError):
        return False


def type_matches(declared: str, live_type: Any, live_base: Any = None) -> bool:
    """Is the live node the type the fixture asked for?

    VERIFIED-RUNTIME 22.0.368, and the defect this function exists to fix:
    ``createNode("domelight")`` produces a node whose ``type().name()`` is
    ``"domelight::3.0"``. Comparing the fixture's literal against the raw type
    name therefore reported a permanent mismatch, and the reconciler planned
    an endless delete-and-recreate of that one node -- never converging, never
    idempotent. (``nodeTypeCategory().nodeType("domelight")`` does NOT resolve
    the version either; it returns the unversioned entry. The stable identity
    is ``NodeType.nameComponents()[2]``, which ``observe`` records as
    ``type_base``.)

    The rule:

      * a fixture that declares a bare name (``domelight``) matches on the
        version-stripped base -- it wants that KIND of node, and the build
        decides the version;
      * a fixture that declares a versioned name (``domelight::3.0``) is
        pinning deliberately and matches exactly.

    Fails when: the box holds a ``null`` where the fixture wants a ``camera``
    -- which is what drives the recreate path.
    """
    if "::" in declared:
        return str(live_type) == declared
    if live_base is not None:
        return str(live_base) == declared
    return str(live_type).split("::")[0] == declared


def collisions(fixture: Dict[str, Any], snapshot: Dict[str, Any]) -> List[Dict[str, str]]:
    """D2 -- every fixture node name that already exists OUTSIDE the box.

    Fails when: the artist has a node called ``camera`` sitting in /stage and
    the fixture also declares ``camera``. Returns one entry per clash, so the
    report names every one rather than stopping at the first.

    Why this must exist at all: VERIFIED-RUNTIME 22.0.368 --
    ``stage.createNode("null", "taken_name")`` does NOT raise. It silently
    auto-renames (``syn_probe_n1`` -> ``syn_probe_n3``). Detecting the clash
    afterwards is impossible without already having mutated the scene.
    """
    outside = snapshot.get("outside_names") or {}
    hits = []
    for spec in fixture["nodes"]:
        name = spec["name"]
        if name in outside:
            hits.append({
                "name": name,
                "existing_type": outside[name],
                "fixture_type": spec["type"],
                "reason": "name already exists in the stage outside the box",
            })
    return hits


@dataclass
class Plan:
    """What must change for the stage to match the definition.

    ``ops`` is the honest count of mutations this plan will perform. A plan
    with ``ops == 0`` performs nothing -- that is F-3.
    """

    box_name: str
    collisions: List[Dict[str, str]] = field(default_factory=list)
    create_box: bool = False
    create_nodes: List[str] = field(default_factory=list)
    delete_nodes: List[str] = field(default_factory=list)
    recreate_nodes: List[str] = field(default_factory=list)
    set_parms: List[Dict[str, Any]] = field(default_factory=list)
    set_inputs: List[Dict[str, Any]] = field(default_factory=list)
    set_positions: List[Dict[str, Any]] = field(default_factory=list)
    set_display: List[str] = field(default_factory=list)
    unmanaged_inputs: List[Dict[str, Any]] = field(default_factory=list)
    missing_parms: List[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        """True when D2 has fired. A blocked plan mutates nothing."""
        return bool(self.collisions)

    @property
    def ops(self) -> int:
        if self.blocked:
            return 0
        return (
            (1 if self.create_box else 0)
            + len(self.create_nodes)
            + len(self.delete_nodes)
            + len(self.set_parms)
            + len(self.set_inputs)
            + len(self.set_positions)
            + len(self.set_display)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "box": self.box_name,
            "blocked": self.blocked,
            "collisions": list(self.collisions),
            "create_box": self.create_box,
            "create_nodes": list(self.create_nodes),
            "delete_nodes": list(self.delete_nodes),
            "recreate_nodes": list(self.recreate_nodes),
            "set_parms": list(self.set_parms),
            "set_inputs": list(self.set_inputs),
            "set_positions": list(self.set_positions),
            "set_display": list(self.set_display),
            "unmanaged_inputs": list(self.unmanaged_inputs),
            "missing_parms": list(self.missing_parms),
            "ops": self.ops,
        }


def build_plan(
    fixture: Dict[str, Any],
    snapshot: Dict[str, Any],
    *,
    box_name: Optional[str] = None,
) -> Plan:
    """Diff the definition against the observed stage.

    Fails when: the stage drifts from the definition in any dimension the
    fixture pins -- a missing node, a wrong node type inside the box, a parm
    the artist retyped, a wire pulled, a node dragged, the display flag moved,
    or a stray node inside the box. Each of those produces a specific entry;
    a stage that matches produces ``ops == 0``.
    """
    box = box_name if box_name is not None else snapshot.get("box_name")
    plan = Plan(box_name=box or "")

    # -- D2 first. A blocked plan is a report, not an intent. ---------------
    plan.collisions = collisions(fixture, snapshot)
    if plan.collisions:
        return plan

    members: Dict[str, Any] = dict(snapshot.get("box_members") or {})
    declared = {spec["name"]: spec for spec in fixture["nodes"]}
    order = [spec["name"] for spec in fixture["nodes"]]
    wires = declared_wires(fixture)
    display_target = fixture.get("display")

    plan.create_box = not snapshot.get("box_present", False)

    # -- classify every box member. Deletion candidates come from HERE and
    #    nowhere else (D3). ------------------------------------------------
    def _ok(n: str) -> bool:
        return type_matches(declared[n]["type"],
                            members[n].get("type"),
                            members[n].get("type_base"))

    strays = [n for n in sorted(members) if n not in declared]
    retype = [n for n in order if n in members and not _ok(n)]
    matched = [n for n in order if n in members and _ok(n)]
    missing = [n for n in order if n not in members]

    plan.recreate_nodes = list(retype)
    plan.delete_nodes = strays + retype
    plan.create_nodes = [n for n in order if n in missing or n in retype]

    # -- reconcile the members that survive in place ------------------------
    for name in matched:
        spec = declared[name]
        live = members[name]

        live_parms = live.get("parms") or {}
        for pname, desired in (spec.get("parms") or {}).items():
            if pname in (live.get("parms_missing") or []):
                # The fixture pins a parm this node type does not have. That is
                # a fixture/build mismatch, not drift -- surface it, never
                # silently skip it (Law 3).
                plan.missing_parms.append("%s.%s" % (name, pname))
                continue
            current = live_parms.get(pname)
            if not parm_equal(current, desired):
                plan.set_parms.append({
                    "node": name, "parm": pname,
                    "current": current, "desired": desired,
                })

        live_inputs = {int(k): v for k, v in (live.get("inputs") or {}).items()}
        want_inputs = wires.get(name, {})
        for idx, src in want_inputs.items():
            if live_inputs.get(idx) != src:
                plan.set_inputs.append({
                    "node": name, "index": int(idx),
                    "current": live_inputs.get(idx), "desired": src,
                })
        for idx, src in sorted(live_inputs.items()):
            # An input the fixture does not declare. NOT disconnected: the
            # source may be an artist node wired deliberately into ours, and
            # nothing in D1-D4 authorises reaching outside the box to sever
            # it. Reported so the caller sees it (Law 3), never acted on.
            if src is not None and idx not in want_inputs:
                plan.unmanaged_inputs.append({
                    "node": name, "index": int(idx), "source": src,
                })

        if not position_equal(live.get("position"), spec.get("position")):
            plan.set_positions.append({
                "node": name,
                "current": live.get("position"),
                "desired": spec.get("position"),
            })

        # There is deliberately NO "clear the display flag on the wrong node"
        # branch. VERIFIED-RUNTIME 22.0.368: the LOP display flag is EXCLUSIVE
        # -- setDisplayFlag(True) on one node clears every sibling. A clear
        # list could never be non-empty at a moment when acting on it did
        # anything, so it would be a check that cannot fail (Law 1) and an op
        # count for work nobody performed (Law 3).
        if display_target is not None and name == display_target:
            if not live.get("display", False):
                plan.set_display.append(name)

    return plan
