"""
Synapse TOPS/PDG Handler Mixin -- Wedge

Auto-extracted from the monolith handlers_tops.py.

R-032 (CONDUCTOR-4): the wedge handlers used to write invented parameter
names ('range<idx>x', 'range<idx>y', 'steps<idx>') that do not exist on the
H22.0.400 Wedge TOP, so every sweep reported success while configuring
nothing. The real parameter vocabulary is taken from the live node catalogue
(rag/catalog/h22.0.400/Top.json -> types['wedge']['parms']):

    wedgeattributes          multiparm count of wedge attributes
    wedgecount               range samples per range attribute
    channel#                 target parameter
    exportchannel#           enable target parameter
    name# / type#            attribute name and attribute type menu
    valuetype#               set-value-as menu (0 attr ref, 1 parm value,
                             2 parm expression)
    wedgetype#               range / value / value-list / bracket menu
    floatrangestart#         range start, float families (4 components)
    floatrangeend#           range end
    intrangestart#           range start, integer families
    intrangeend#             range end
    colorrangestart#         range start, color family
    colorrangeend#           range end
    values#                  multiparm count of a value list
    floatvalue#_#            value list entries (also floatvector#_#,
                             intvalue#_#, intvector#_#, strvalue#_#,
                             colorvalue#_#)

'#' is the 1-based multiparm index. Every write goes through _wedge_parm(),
which fails when the parameter is absent instead of silently skipping it.
"""

import time
from typing import Any, Dict, List, Optional

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ...core.aliases import resolve_param, resolve_param_with_default
from ...core.determinism import round_float, kahan_sum, deterministic_uuid
from ..handler_helpers import _HOUDINI_UNAVAILABLE
from ._common import _run_in_main_thread_pdg, _ensure_tops_warm_standby, _MAX_MONITOR_EVENTS


# ---------------------------------------------------------------------------
# H22.0.400 wedge vocabulary (rag/catalog/h22.0.400/Top.json, types.wedge)
# ---------------------------------------------------------------------------

# Attribute type menu (type#): Float, Float Vector, Integer, Integer Vector,
# String, Color.
_WEDGE_TYPE_TOKEN = {
    "float": 0,
    "floatvector": 1,
    "float_vector": 1,
    "vector": 1,
    "int": 2,
    "integer": 2,
    "intvector": 3,
    "int_vector": 3,
    "string": 4,
    "color": 5,
}
_WEDGE_TYPE_LABEL = {
    0: "float",
    1: "floatvector",
    2: "int",
    3: "intvector",
    4: "string",
    5: "color",
}
# Range start/end families that exist on the node. String has no range family.
_WEDGE_RANGE_FAMILY = {
    0: "floatrange",
    1: "floatrange",
    2: "intrange",
    3: "intrange",
    5: "colorrange",
}
# Value-list entry families that exist on the node.
_WEDGE_VALUE_FAMILY = {
    0: "floatvalue",
    1: "floatvector",
    2: "intvalue",
    3: "intvector",
    4: "strvalue",
    5: "colorvalue",
}
_WEDGE_TYPE_STRING = 4
_WEDGE_TYPE_INT = 2
_WEDGE_TYPE_INT_VECTOR = 3
_WEDGE_WEDGETYPE_RANGE = 0
_WEDGE_WEDGETYPE_VALUE_LIST = 2
_WEDGE_VALUETYPE_PARAMETER_VALUE = 1

# Families declared with 4 components in the catalogue.
_WEDGE_MULTI_COMPONENT = frozenset(
    ("floatrange", "intrange", "colorrange", "floatvector", "intvector", "colorvalue")
)


def _wedge_parm(node, name: str):
    """Return node.parm(name), or raise when the parameter is absent.

    Refusing here is the repair for CONDUCTOR-4: a missing parameter used to
    be skipped with ``if parm:``, which turned a misconfigured sweep into a
    success report.
    """
    parm = node.parm(name)
    if parm is None:
        available = []
        parms_fn = getattr(node, "parms", None)
        if callable(parms_fn):
            available = sorted(p.name() for p in parms_fn())
        listing = (
            ", ".join(available[:40]) + (" ..." if len(available) > 40 else "")
            if available
            else "none reported"
        )
        raise ValueError(
            f"The wedge node at {node.path()} has no '{name}' parameter -- "
            "refusing to write a parameter that doesn't exist on this build's "
            "Wedge TOP (H22.0.400 names, see rag/catalog/h22.0.400/Top.json). "
            f"Available parameters: {listing}"
        )
    return parm


def _set_wedge_parm(node, name: str, value):
    """Set one wedge parameter, failing when the parameter is absent."""
    parm = _wedge_parm(node, name)
    if isinstance(value, (tuple, list)):
        parm.set(tuple(value))
    else:
        parm.set(value)
    return parm


def _wedge_parm_int(node, name: str) -> int:
    parm = _wedge_parm(node, name)
    return int(parm.eval())


def _fill_components(value, family: str):
    """Expand a scalar to the declared component count for a family."""
    if family in _WEDGE_MULTI_COMPONENT:
        return tuple(value for _ in range(4))
    return value


def _range_samples(start, end, steps: int):
    """Evenly spaced samples from start to end, inclusive."""
    if steps < 1:
        raise ValueError("'steps' should be 1 or more")
    if steps == 1:
        return [start]
    span = float(end) - float(start)
    return [start + span * i / (steps - 1) for i in range(steps)]


def _normalize_attributes(attributes) -> List[Dict]:
    """Validate wedge attribute definitions and attach their sample values."""
    if not isinstance(attributes, list) or len(attributes) == 0:
        raise ValueError(
            "The 'attributes' parameter should be a list of attribute definitions "
            "(each with name, type, start, end, steps)"
        )

    normalized = []
    for i, raw in enumerate(attributes):
        if not isinstance(raw, dict):
            raise ValueError(
                f"attributes[{i}] should be an object with name, type, start, end, steps"
            )
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"attributes[{i}] is missing a non-empty 'name'")

        type_raw = raw.get("type", "float")
        type_name = str(type_raw).strip().lower()
        token = _WEDGE_TYPE_TOKEN.get(type_name)
        if token is None:
            raise ValueError(
                f"attributes[{i}].type '{type_raw}' isn't a Wedge TOP attribute type -- "
                f"use one of: {', '.join(sorted(_WEDGE_TYPE_TOKEN))}"
            )

        explicit = raw.get("values")
        if explicit is not None:
            if not isinstance(explicit, list) or len(explicit) == 0:
                raise ValueError(f"attributes[{i}].values should be a non-empty list")
            if token == _WEDGE_TYPE_STRING and not all(isinstance(v, str) for v in explicit):
                raise ValueError(
                    f"attributes[{i}].values should all be strings for a string wedge"
                )
            normalized.append({
                "name": name.strip(),
                "type": type_name,
                "token": token,
                "mode": "value_list",
                "values": list(explicit),
                "steps": len(explicit),
            })
            continue

        if token == _WEDGE_TYPE_STRING:
            raise ValueError(
                f"attributes[{i}] is a string wedge and needs an explicit 'values' list "
                "(a numeric start/end range can't produce strings)"
            )

        start = raw.get("start", 0)
        end = raw.get("end", 1)
        steps_raw = raw.get("steps", 5)
        try:
            start = float(start)
            end = float(end)
            steps = int(steps_raw)
        except (TypeError, ValueError):
            raise ValueError(
                f"attributes[{i}] needs numeric start/end and an integer steps"
            ) from None
        if steps < 1:
            raise ValueError(f"attributes[{i}].steps should be 1 or more")

        normalized.append({
            "name": name.strip(),
            "type": type_name,
            "token": token,
            "mode": "range",
            "start": start,
            "end": end,
            "steps": steps,
            "samples": _range_samples(start, end, steps),
        })

    normalized.sort(key=lambda a: a["name"])
    return normalized


def _values_type_token(values) -> int:
    """Pick the wedge attribute type for a flat list of explicit values."""
    if any(isinstance(v, bool) for v in values):
        raise ValueError(
            "'values' should be all numbers or all strings -- booleans can't be "
            "applied to a wedge attribute"
        )
    if all(isinstance(v, int) for v in values):
        return _WEDGE_TYPE_INT
    if all(isinstance(v, (int, float)) for v in values):
        return 0
    if all(isinstance(v, str) for v in values):
        return _WEDGE_TYPE_STRING
    raise ValueError(
        "'values' should be all numbers or all strings -- mixed or non-scalar "
        "values can't be applied to one wedge attribute"
    )


def _coerce_wedge_value(token: int, value):
    if token == _WEDGE_TYPE_STRING:
        return str(value)
    if token in (_WEDGE_TYPE_INT, _WEDGE_TYPE_INT_VECTOR):
        if isinstance(value, float) and not value.is_integer():
            raise ValueError(
                f"value {value!r} isn't a whole number -- an integer wedge can't apply it"
            )
        return int(value)
    return float(value)


def _attribute_name_for_parm(wedge_parm: str) -> str:
    """Derive the work-item attribute name from a target parameter path."""
    leaf = wedge_parm.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    leaf = leaf.split(".")[-1]
    cleaned = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in leaf)
    cleaned = cleaned.strip("_")
    if not cleaned:
        return "wedge"
    if cleaned[0].isdigit():
        return f"attr_{cleaned}"
    return cleaned


def _resolve_or_create_wedge_node(node, requested_path: str):
    """Return the wedge node for a path, creating one inside a TOP network."""
    category = node.type().category().name()
    if category == "Top":
        type_name = node.type().name().lower()
        if "wedge" not in type_name:
            raise ValueError(
                f"The node at {requested_path} is a '{node.type().name()}' TOP, not a "
                "Wedge TOP -- point to a wedge node or to the TOP network that holds one"
            )
        return node
    if category == "TopNet":
        for child in node.children():
            if "wedge" in child.type().name().lower():
                return child
        created = node.createNode("wedge", "wedge1")
        mover = getattr(created, "moveToGoodPosition", None)
        if callable(mover):
            mover()
        return created
    raise ValueError(
        f"The node at {requested_path} is a {category} node, not a TOP network -- "
        "point to a TOP network or a specific wedge/TOP node"
    )


def _apply_wedge_values(wedge_node, wedge_parm: str, values) -> Dict:
    """Configure a single value-list wedge attribute on a Wedge TOP.

    Applies the requested parm/values to the node's real parameters; every
    absent parameter raises instead of being skipped.
    """
    if not isinstance(wedge_parm, str) or not wedge_parm.strip():
        raise ValueError("'parm' should be a non-empty parameter name or path to wedge")
    if not isinstance(values, list) or len(values) == 0:
        raise ValueError("'values' is empty -- pass at least one value to wedge over")

    token = _values_type_token(values)
    family = _WEDGE_VALUE_FAMILY[token]
    attribute = _attribute_name_for_parm(wedge_parm.strip())

    _set_wedge_parm(wedge_node, "wedgeattributes", 1)
    _set_wedge_parm(wedge_node, "wedgetype1", _WEDGE_WEDGETYPE_VALUE_LIST)
    _set_wedge_parm(wedge_node, "valuetype1", _WEDGE_VALUETYPE_PARAMETER_VALUE)
    _set_wedge_parm(wedge_node, "name1", attribute)
    _set_wedge_parm(wedge_node, "type1", token)
    _set_wedge_parm(wedge_node, "channel1", wedge_parm.strip())
    _set_wedge_parm(wedge_node, "exportchannel1", 1)
    _set_wedge_parm(wedge_node, "values1", len(values))

    applied = []
    for j, raw in enumerate(values, start=1):
        value = _coerce_wedge_value(token, raw)
        _set_wedge_parm(wedge_node, f"{family}1_{j}", _fill_components(value, family))
        applied.append(value)

    return {
        "parm": wedge_parm.strip(),
        "attribute": attribute,
        "attribute_type": _WEDGE_TYPE_LABEL[token],
        "values": applied,
        "requested_items": len(applied),
        "wedgecount": _wedge_parm_int(wedge_node, "wedgecount"),
    }


def _read_back_work_items(wedge_node) -> int:
    """Generate static items and return the node's work-item count."""
    generate = getattr(wedge_node, "generateStaticItems", None)
    if not callable(generate):
        raise ValueError(
            f"The wedge node at {wedge_node.path()} can't generate work items -- "
            "this build's TOP node has no generateStaticItems()"
        )
    generate()
    pdg_node = wedge_node.getPDGNode()
    if pdg_node is None:
        raise ValueError(
            f"The wedge node at {wedge_node.path()} has no PDG node after item "
            "generation -- can't read back the generated work-item count"
        )
    work_items = getattr(pdg_node, "workItems", None)
    if work_items is None:
        raise ValueError(
            f"The PDG node behind {wedge_node.path()} reported no 'workItems' -- "
            "can't read back the generated work-item count"
        )
    return len(work_items)


class TopsWedgeMixin:
    """Mixin providing TOPS/PDG wedge handlers."""

    def _handle_wedge(self, payload: Dict) -> Dict:
        """Run a TOPs/PDG wedge to explore parameter variations.

        With 'parm' + 'values' the wedge node is configured to sweep that
        parameter over those values before cooking. With neither, an existing
        wedge node (or the first wedge node inside a TOP network) is cooked.
        One without the other, values that can't be applied, or a wedge node
        missing a required parameter are refused instead of silently ignored.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        top_path = resolve_param(payload, "node")  # TOP network or wedge node
        wedge_parm = resolve_param(payload, "parm", required=False)
        values = resolve_param(payload, "values", required=False)

        if values is not None and not isinstance(values, list):
            raise ValueError(
                "'values' should be a list (e.g. [0.5, 1.0, 2.0]) -- "
                "wrap your values in square brackets"
            )

        if (wedge_parm is None) != (values is None):
            raise ValueError(
                "'parm' and 'values' go together -- pass both to configure the wedge "
                "on that parameter, or neither to cook an existing wedge node"
            )

        def _run_wedge():
            node = hou.node(top_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {top_path} -- "
                    "double-check the path to your TOP network or wedge node"
                )

            if wedge_parm is not None:
                wedge_node = _resolve_or_create_wedge_node(node, top_path)
                summary = _apply_wedge_values(wedge_node, wedge_parm, values)
                summary["work_item_count"] = _read_back_work_items(wedge_node)
                wedge_node.cookWorkItems(block=True)
                summary["node"] = wedge_node.path()
                summary["status"] = "cooked"
                return summary

            # No parm/values -- cook an existing wedge node.
            if node.type().category().name() == "Top":
                node.cookWorkItems(block=True)
                return {"node": top_path, "status": "cooked"}
            elif node.type().category().name() == "TopNet":
                wedge_nodes = [n for n in node.children() if "wedge" in n.type().name().lower()]
                if wedge_nodes:
                    wedge_nodes[0].cookWorkItems(block=True)
                    return {"node": wedge_nodes[0].path(), "status": "cooked"}
                else:
                    raise ValueError(
                        f"Couldn't find a wedge node inside {top_path} -- "
                        "create a wedge TOP or point to one directly"
                    )
            else:
                raise ValueError(
                    f"The node at {top_path} isn't a TOP network -- "
                    "point to a TOP network or a specific wedge/TOP node"
                )

        result = _run_in_main_thread_pdg(_run_wedge)
        return result

    # =========================================================================
    # TOPS / PDG HANDLERS
    # =========================================================================



    # =========================================================================
    # TOPS / PDG HANDLERS -- Phase 3: Advanced
    # =========================================================================

    def _handle_tops_setup_wedge(self, payload: Dict) -> Dict:
        """Set up a Wedge TOP node for parameter variation exploration.

        Creates a wedge node inside a TOP network and configures its real
        H22.0.400 parameters (name#, type#, wedgetype#, the range start/end
        families or the value-list family). A uniform step count drives the
        node's range mode and 'wedgecount'; differing step counts are written
        as explicit value lists, because 'wedgecount' is a single node-level
        sample count. Every write is checked against the node and fails when a
        requested parameter is absent. Afterwards the node reports its
        'wedgecount' readback and the generated work-item count.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        topnet_path = resolve_param(payload, "topnet_path")
        wedge_name = resolve_param_with_default(payload, "wedge_name", "wedge1")
        attributes = resolve_param(payload, "attributes")

        attrs = _normalize_attributes(attributes)

        step_counts = {a["steps"] for a in attrs}
        range_mode = (
            all(a["mode"] == "range" for a in attrs) and len(step_counts) == 1
        )
        uniform_steps = step_counts.pop() if range_mode else None

        def _run():
            node = hou.node(topnet_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {topnet_path} -- "
                    "double-check the path exists"
                )

            cat = node.type().category().name()
            if cat not in ("TopNet",):
                raise ValueError(
                    f"The node at {topnet_path} is a {cat} node, not a TOP network -- "
                    "point to a topnet node (e.g. '/obj/topnet1')"
                )

            wedge_node = node.createNode("wedge", wedge_name)
            mover = getattr(wedge_node, "moveToGoodPosition", None)
            if callable(mover):
                mover()

            _set_wedge_parm(wedge_node, "wedgeattributes", len(attrs))
            if range_mode:
                _set_wedge_parm(wedge_node, "wedgecount", uniform_steps)

            total_variations = 1
            attr_results = []
            for idx, attr in enumerate(attrs, start=1):
                token = attr["token"]
                _set_wedge_parm(wedge_node, f"name{idx}", attr["name"])
                _set_wedge_parm(wedge_node, f"type{idx}", token)

                if range_mode:
                    _set_wedge_parm(wedge_node, f"wedgetype{idx}", _WEDGE_WEDGETYPE_RANGE)
                    family = _WEDGE_RANGE_FAMILY[token]
                    start_value = _coerce_wedge_value(token, attr["start"])
                    end_value = _coerce_wedge_value(token, attr["end"])
                    _set_wedge_parm(
                        wedge_node, f"{family}start{idx}", _fill_components(start_value, family)
                    )
                    _set_wedge_parm(
                        wedge_node, f"{family}end{idx}", _fill_components(end_value, family)
                    )
                    total_variations *= len(attr["samples"])
                    attr_results.append({
                        "name": attr["name"],
                        "type": attr["type"],
                        "mode": "range",
                        "start": round_float(float(attr["start"])),
                        "end": round_float(float(attr["end"])),
                        "steps": attr["steps"],
                    })
                else:
                    # Differing step counts can't share the single 'wedgecount'
                    # sample count, so every attribute becomes an explicit list
                    # (a range definition contributes its computed samples).
                    _set_wedge_parm(wedge_node, f"wedgetype{idx}", _WEDGE_WEDGETYPE_VALUE_LIST)
                    family = _WEDGE_VALUE_FAMILY[token]
                    samples = attr["values"] if "values" in attr else attr["samples"]
                    _set_wedge_parm(wedge_node, f"values{idx}", len(samples))
                    written = []
                    for j, raw in enumerate(samples, start=1):
                        value = _coerce_wedge_value(token, raw)
                        _set_wedge_parm(
                            wedge_node, f"{family}{idx}_{j}", _fill_components(value, family)
                        )
                        written.append(value)
                    total_variations *= len(written)
                    attr_results.append({
                        "name": attr["name"],
                        "type": attr["type"],
                        "mode": "value_list",
                        "values": written,
                        "steps": len(written),
                    })

            # Read back what the node actually holds and generates.
            wedgecount = _wedge_parm_int(wedge_node, "wedgecount")
            work_item_count = _read_back_work_items(wedge_node)

            return {
                "topnet": topnet_path,
                "wedge_node": wedge_node.path(),
                "attributes": attr_results,
                "total_variations": total_variations,
                "wedge_mode": "range" if range_mode else "value_list",
                "wedgecount": wedgecount,
                "work_item_count": work_item_count,
            }

        return _run_in_main_thread_pdg(_run)
