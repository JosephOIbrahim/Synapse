from __future__ import annotations

import inspect
from dataclasses import dataclass


@dataclass(frozen=True)
class ProbeSpec:
    surface: str            # dotted path, e.g. "apex.Graph.addNode"
    kind: str = "attr"      # one of: "attr" | "call" | "construct"
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


def probe(namespace: dict, spec: ProbeSpec) -> ProbeResult:
    """Resolve spec.surface as a dotted path against namespace.

    e.g. "apex.Graph.addNode" -> namespace["apex"].Graph.addNode

    PURE function: no hou/apex imports; the namespace is injected. If the root
    key is missing or any getattr fails, returns present=False with the error
    captured (never raises). On success, reports callability and a best-effort
    signature string.
    """
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
