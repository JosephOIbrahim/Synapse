"""BLOCKS fixture loading and validation. Pure Python -- no ``hou``.

A fixture is a committed JSON definition of a deterministic Houdini network
(``fixtures/<name>.json``). It is the noun: "basic Solaris setup" resolves to
``fixtures/solaris.basic.json`` and to nothing else.

This module answers only: does this fixture exist, is it well-formed, and
what does it declare? It never touches a scene. Validation is strict on
purpose -- a malformed fixture must fail here, loudly, before the reconciler
has created a single node.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "FixtureError",
    "FixtureNotFoundError",
    "box_name_for",
    "fixture_dir",
    "fixture_path",
    "list_fixtures",
    "load_fixture",
    "repo_root",
    "validate_fixture",
]


class FixtureError(ValueError):
    """A fixture is missing, unreadable, or structurally invalid."""


class FixtureNotFoundError(FixtureError):
    """No fixture file exists for the requested name."""


# Fixture names are file-system identifiers. The regex is the trust boundary:
# a name reaches ``fixture_path`` and becomes a path, and it is interpolated
# into the injected script by the cognitive adapter. No separators, no dots
# leading, no traversal, no whitespace, no quotes.
_VALID_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
_TRAVERSAL_RE = re.compile(r"\.\.")

_REQUIRED_NODE_KEYS = ("type", "name")


def repo_root() -> Path:
    """Repository root, resolved from this module's own location.

    ``python/synapse/blocks/fixtures.py`` -> parents[3] is the repo root.
    Deriving it from ``__file__`` (not from cwd, not from an env var) means a
    git worktree loads ITS OWN fixtures, which is what makes a worktree run
    trustworthy evidence about the worktree's code.
    """
    return Path(__file__).resolve().parents[3]


def fixture_dir() -> Path:
    return repo_root() / "fixtures"


def _check_name(name: Any) -> str:
    if not isinstance(name, str):
        raise FixtureError(
            "fixture name must be str, got %s" % type(name).__name__
        )
    if _TRAVERSAL_RE.search(name) or not _VALID_NAME_RE.match(name):
        raise FixtureError(
            "fixture name failed validation: %r. Must match "
            "[a-z0-9][a-z0-9_.-]* and contain no path traversal." % (name,)
        )
    return name


def fixture_path(name: str) -> Path:
    """Absolute path to a fixture definition. Does not check existence."""
    return fixture_dir() / (_check_name(name) + ".json")


def list_fixtures() -> List[str]:
    """Every fixture name available in this tree, sorted."""
    d = fixture_dir()
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.json"))


def load_fixture(name: str) -> Dict[str, Any]:
    """Load and validate a fixture by name.

    Raises:
        FixtureNotFoundError: no such fixture file.
        FixtureError: unreadable, not JSON, or structurally invalid.
    """
    path = fixture_path(name)
    if not path.is_file():
        raise FixtureNotFoundError(
            "no fixture %r at %s. Available: %s"
            % (name, path, ", ".join(list_fixtures()) or "(none)")
        )
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise FixtureError("could not read %s: %s" % (path, e)) from e
    try:
        fx = json.loads(raw)
    except json.JSONDecodeError as e:
        raise FixtureError(
            "fixture %r is not valid JSON: %s at position %s"
            % (name, e.msg, e.pos)
        ) from e
    if not isinstance(fx, dict):
        raise FixtureError(
            "fixture %r root must be a JSON object, got %s"
            % (name, type(fx).__name__)
        )
    validate_fixture(fx, name=name)
    return fx


def validate_fixture(fx: Dict[str, Any], *, name: Optional[str] = None) -> None:
    """Structural validation. Raises ``FixtureError`` on the first problem.

    Every rule here has a failure it can catch on a real malformed fixture:
    a duplicate node name (the reconciler would silently build one node), a
    wire naming a node that does not exist (setInput would raise mid-build,
    after partial creation), a display node that is not in the definition
    (the tail flag would land nowhere).
    """
    label = "fixture %r" % (name,) if name else "fixture"

    nodes = fx.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise FixtureError("%s: 'nodes' must be a non-empty list" % label)

    seen = set()
    for i, spec in enumerate(nodes):
        if not isinstance(spec, dict):
            raise FixtureError(
                "%s: nodes[%d] must be an object, got %s"
                % (label, i, type(spec).__name__)
            )
        for key in _REQUIRED_NODE_KEYS:
            if not isinstance(spec.get(key), str) or not spec[key]:
                raise FixtureError(
                    "%s: nodes[%d] missing required string %r" % (label, i, key)
                )
        nname = spec["name"]
        if nname in seen:
            raise FixtureError(
                "%s: duplicate node name %r -- names are the identity the "
                "reconciler reconciles on" % (label, nname)
            )
        seen.add(nname)

        parms = spec.get("parms", {})
        if not isinstance(parms, dict):
            raise FixtureError(
                "%s: nodes[%d].parms must be an object" % (label, i)
            )
        pos = spec.get("position")
        if pos is not None:
            if (not isinstance(pos, (list, tuple)) or len(pos) != 2
                    or not all(isinstance(v, (int, float))
                               and not isinstance(v, bool) for v in pos)):
                raise FixtureError(
                    "%s: nodes[%d].position must be [x, y] numbers" % (label, i)
                )

    wires = fx.get("wires", [])
    if not isinstance(wires, list):
        raise FixtureError("%s: 'wires' must be a list" % label)
    for i, w in enumerate(wires):
        if not isinstance(w, (list, tuple)) or len(w) != 3:
            raise FixtureError(
                "%s: wires[%d] must be [dst, index, src]" % (label, i)
            )
        dst, idx, src = w
        if dst not in seen:
            raise FixtureError(
                "%s: wires[%d] destination %r is not a declared node"
                % (label, i, dst)
            )
        if src not in seen:
            raise FixtureError(
                "%s: wires[%d] source %r is not a declared node"
                % (label, i, src)
            )
        try:
            int(idx)
        except (TypeError, ValueError):
            raise FixtureError(
                "%s: wires[%d] index %r is not an integer" % (label, i, idx)
            ) from None

    display = fx.get("display")
    if display is not None and display not in seen:
        raise FixtureError(
            "%s: display %r is not a declared node" % (label, display)
        )

    own = fx.get("ownership")
    if own is not None:
        if not isinstance(own, dict):
            raise FixtureError("%s: 'ownership' must be an object" % label)
        nb = own.get("network_box")
        if nb is not None and (not isinstance(nb, str) or not nb):
            raise FixtureError(
                "%s: ownership.network_box must be a non-empty string" % label
            )


def box_name_for(fx: Dict[str, Any], name: Optional[str] = None) -> str:
    """The network box that owns this fixture's nodes (D1).

    Declared under ``ownership.network_box`` when the fixture says so;
    otherwise derived as ``BLOCKS_<name with '.'/'-' -> '_'>``. The derived
    form is a fallback, never a second convention -- solaris.basic declares
    ``BLOCKS_solaris_basic`` and the derivation reproduces exactly that, so a
    fixture that forgets the key still lands in the same box.
    """
    own = fx.get("ownership") or {}
    declared = own.get("network_box")
    if isinstance(declared, str) and declared:
        return declared
    base = name if name is not None else fx.get("fixture", "")
    if not base:
        raise FixtureError(
            "cannot derive a box name: fixture declares neither "
            "ownership.network_box nor 'fixture'"
        )
    return "BLOCKS_" + re.sub(r"[^A-Za-z0-9_]", "_", base)


def declared_wires(fx: Dict[str, Any]) -> Dict[str, Dict[int, str]]:
    """``{dst_name: {input_index: src_name}}`` from the fixture's wire list."""
    out: Dict[str, Dict[int, str]] = {}
    for dst, idx, src in fx.get("wires", []):
        out.setdefault(dst, {})[int(idx)] = src
    return out


def declared_nodes(fx: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """``[(name, spec), ...]`` in definition order -- creation order matters."""
    return [(spec["name"], spec) for spec in fx["nodes"]]
