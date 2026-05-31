from __future__ import annotations

import inspect
from dataclasses import dataclass


@dataclass(frozen=True)
class ProbeSpec:
    surface: str            # dotted path, e.g. "apex.Graph.addNode"
    kind: str = "attr"      # one of: "attr" | "call" | "construct" | "nodetype"
    expect: str = "unknown"  # one of: "present" | "absent" | "unknown"
    rationale: str = ""
    rank: int = 0


@dataclass(frozen=True)
class ProbeResult:
    surface: str
    kind: str
    present: bool
    is_callable: bool = False
    signature: str | None = None
    error: str | None = None


def _probe_nodetype(namespace: dict, spec: ProbeSpec) -> ProbeResult:
    """Resolve a node-type surface by NAME membership in a catalog.

    Houdini node-type names contain "::" and are not getattr-resolvable; they
    live keyed by name in a catalog (dict / set / any __contains__ object). The
    surface carries a "nodetypes." prefix only as a routing label, e.g.
    "nodetypes.apex::sop::invoke" -> catalog membership test on
    "apex::sop::invoke".

    A node type def is not a callable, so present results report
    is_callable=False, signature=None. Cleanly absent names report present=False
    with error=None (a true dead_end). Only a missing catalog is an error.

    Never raises.
    """
    if "nodetypes" not in namespace:
        return ProbeResult(
            surface=spec.surface,
            kind=spec.kind,
            present=False,
            error=repr(KeyError("nodetypes")),
        )

    catalog = namespace["nodetypes"]
    if catalog is None:
        # Key present but explicitly None: no usable catalog. Report a truthful
        # error (the key exists, so don't fabricate a KeyError) — never raise.
        return ProbeResult(
            surface=spec.surface,
            kind=spec.kind,
            present=False,
            error=repr(TypeError("nodetypes catalog is None")),
        )

    name = spec.surface.split(".", 1)[1] if "." in spec.surface else spec.surface

    try:
        present = name in catalog  # membership, NOT getattr
    except Exception as exc:  # noqa: BLE001 - capture, never raise
        return ProbeResult(
            surface=spec.surface,
            kind=spec.kind,
            present=False,
            error=repr(exc),
        )

    return ProbeResult(
        surface=spec.surface,
        kind=spec.kind,
        present=present,
        is_callable=False,   # a node type def is not a callable
        signature=None,
        error=None,          # present True OR cleanly-absent both have no error
    )


def probe(namespace: dict, spec: ProbeSpec) -> ProbeResult:
    """Resolve spec.surface as a dotted path against namespace.

    e.g. "apex.Graph.addNode" -> namespace["apex"].Graph.addNode

    PURE function: no hou/apex imports; the namespace is injected. If the root
    key is missing or any getattr fails, returns present=False with the error
    captured (never raises). On success, reports callability and a best-effort
    signature string.

    For ``spec.kind == "nodetype"`` the surface is NOT getattr-resolvable:
    Houdini node-type names contain "::" (e.g. "apex::sop::invoke"), which are
    looked up by NAME in a node-type catalog, not as attributes. The branch
    below resolves them via membership against ``namespace["nodetypes"]``.
    """
    if spec.kind == "nodetype":
        return _probe_nodetype(namespace, spec)

    parts = spec.surface.split(".")
    root_key = parts[0]

    if root_key not in namespace:
        return ProbeResult(
            surface=spec.surface,
            kind=spec.kind,
            present=False,
            error=repr(KeyError(root_key)),
        )

    obj = namespace[root_key]
    try:
        for attr in parts[1:]:
            obj = getattr(obj, attr)
    except Exception as exc:  # noqa: BLE001 - capture, never raise
        return ProbeResult(
            surface=spec.surface,
            kind=spec.kind,
            present=False,
            error=repr(exc),
        )

    is_callable = callable(obj)
    signature: str | None = None
    try:
        signature = str(inspect.signature(obj))
    except (ValueError, TypeError):
        signature = None
    except Exception:  # noqa: BLE001 - signature is best-effort only
        signature = None

    return ProbeResult(
        surface=spec.surface,
        kind=spec.kind,
        present=True,
        is_callable=is_callable,
        signature=signature,
        error=None,
    )
