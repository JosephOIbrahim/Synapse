"""Per-node facts for the Identify bubble — the one short main-thread read.

``inspect_selection`` (the Selection Inspector's own pipeline) supplies the
identified, staleness-checked selection; Identify adds no second walk of it
(IDENTIFY_BLUEPRINT rule 7). The bubble needs a little more per node than the
inspector serializes — the help URL, parameter *labels* (not names), default
and expression flags, errors, warnings, bypass, and, for a LOP, the prims it
last wrote — so ``node_facts`` reads those extras straight off each already
identified node.

Everything here runs on Houdini's main thread (it touches live ``hou`` objects).
Library lookup and text composition happen elsewhere, off the main thread
(rule 5). ``hou`` is import-guarded so the module imports on system Python; the
live path is exercised by ``scripts/probe_identify.py`` under hython.
"""
from __future__ import annotations

try:  # pragma: no cover - exercised live under hython
    import hou
except Exception:  # pragma: no cover
    hou = None


#: Parameter kinds compose treats as structural noise (folders/labels/...).
#: ``facts`` records the kind; the pure filter lives in ``compose``.
_STRUCTURAL = {"folder", "folderset", "separator", "label"}


def _template_kind(template) -> str:
    """Lower-case kind name from a parm template, robust to enum shape."""
    try:
        ttype = template.type()
        name = ttype.name() if hasattr(ttype, "name") else str(ttype)
        return str(name).rsplit(".", 1)[-1].lower()
    except Exception:
        return "other"


def _is_hidden(template) -> bool:
    try:
        return bool(template.isHidden())
    except Exception:
        return False


def _parm_is_expression(tuple_) -> bool:
    """True if any component of the tuple is driven by an expression/channel."""
    try:
        for parm in tuple_:
            try:
                parm.expression()
                return True
            except Exception:
                if parm.keyframes():
                    return True
    except Exception:
        return False
    return False


def _tuple_value(tuple_):
    """(value, multi): the single scalar, or ``(None, True)`` for a vector."""
    try:
        values = tuple_.eval()
    except Exception:
        return (None, True)
    if len(tuple_) == 1:
        return (values[0], False)
    return (None, True)


def _node_params(node) -> list[dict]:
    """Non-default parameters, one entry per tuple, with bubble metadata."""
    params: list[dict] = []
    seen: set[str] = set()
    try:
        parms = node.parms()
    except Exception:
        return params
    for parm in parms:
        try:
            if parm.isAtDefault():
                continue
            tuple_ = parm.tuple()
            tname = tuple_.name()
            if tname in seen:
                continue
            seen.add(tname)
            template = parm.parmTemplate()
            value, multi = _tuple_value(tuple_)
            params.append({
                "name": tname,
                "label": template.label(),
                "kind": _template_kind(template),
                "value": value,
                "multi": multi,
                "is_expression": _parm_is_expression(tuple_),
                "hidden": _is_hidden(template),
            })
        except Exception:
            continue
    return params


def _lop_writes(node) -> dict | None:
    """Prims a LOP last modified. UNKNOWN on 22.0.400 until an API is proved.

    No public 22.0.400 method for "last modified prims" has been verified, so
    this returns ``None`` (honest unknown) rather than an estimate. The probe
    explores whether such an API exists; compose already renders the line when
    a future read supplies ``{"first": ..., "count": N}``.
    """
    return None


def node_facts(node) -> dict:
    """Read one identified node's bubble facts on the main thread."""
    facts: dict = {
        "path": None, "type_name": None, "type_label": None, "category": None,
        "help_url": None, "hda_help": None, "params": [], "lop_writes": None,
        "errors": [], "warnings": [], "bypassed": False, "beta": False,
    }
    try:
        facts["path"] = node.path()
    except Exception:
        pass
    try:
        ntype = node.type()
        try:
            facts["type_name"] = ntype.name()
        except Exception:
            pass
        try:
            facts["type_label"] = ntype.description()
        except Exception:
            pass
        try:
            facts["category"] = ntype.category().name()
        except Exception:
            pass
        try:
            facts["help_url"] = ntype.defaultHelpUrl()
        except Exception:
            pass
        # Embedded help is only meaningful for an HDA (not a compiled type).
        try:
            definition = ntype.definition()
            if definition is not None:
                facts["hda_help"] = definition.embeddedHelp()
        except Exception:
            pass
    except Exception:
        pass
    try:
        facts["params"] = _node_params(node)
    except Exception:
        pass
    facts["lop_writes"] = _lop_writes(node)
    try:
        facts["errors"] = list(node.errors())
    except Exception:
        pass
    try:
        facts["warnings"] = list(node.warnings())
    except Exception:
        pass
    try:
        facts["bypassed"] = bool(node.isBypassed())
    except Exception:
        pass
    return facts


def read_selection_facts(node_paths, *, inspect=None, node_lookup=None) -> list[dict]:
    """Raw facts for the identified selection — the single main-thread read.

    *inspect* defaults to ``server.introspection.inspect_selection`` and is
    called once (``include_parameters=True``) so the identities and staleness
    checks are the Selection Inspector's, not a second walk. *node_lookup* maps
    a path to a live node (defaults to ``hou.node``). Summaries and composition
    are added later, off the main thread.
    """
    paths = list(node_paths or ())
    if inspect is None:
        from synapse.server.introspection import inspect_selection as inspect
    # One call: reuse the inspector's identity/staleness pipeline (rule 7).
    inspect(include_parameters=True, node_paths=paths)
    if node_lookup is None:
        if hou is None:
            raise RuntimeError("hou is unavailable; a node_lookup is required")
        node_lookup = hou.node
    out: list[dict] = []
    for path in paths:
        node = node_lookup(path)
        if node is None:
            continue
        out.append(node_facts(node))
    return out
