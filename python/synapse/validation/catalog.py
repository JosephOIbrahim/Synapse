"""Runtime node-schema catalog lookup (W5-PARMGATE, target 2).

Cheap, exact, embedding-free lookups over the build-keyed schema catalog that
W5-CATALOG dumps from the live Houdini build into ``rag/catalog/<build>/``.
Each ``<Category>.json`` (``Cop.json``, ``Dop.json``, ``Chop.json``,
``Vop.json``, ``Sop.json`` ...) carries ``types[<node_type>]["parms"]`` where
every parm has a ``name``. This module turns that data into two lookups the
Parm Gate needs:

    catalog.parms(category, node_type)     -> frozenset[str] | None
    catalog.signature(category, node_type) -> list[dict]      | None

Both are pure dict indexing over a lazily-loaded, per-category-cached JSON
file -- no embedding round-trips, no ``hou``. Category names map 1:1 to file
names via ``hou.NodeType.category().name()`` (``Cop`` -> ``Cop.json``), which
is exactly how the catalog was keyed.

Degrade-safe by construction: a missing catalog root, a missing category file,
a malformed file, or an absent node type each returns ``None`` rather than
raising. ``None`` means "no authority" -- the gate then degrades to a permissive
safe-set instead of a false rejection. This is what lets the gate ship on a
branch whose tree does not yet contain the (2.5M-line) catalog data: the data
arrives when W5-CATALOG merges; until then every lookup is honestly ``None``.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional


# Build the catalog was dumped for. The gate reads whatever build dir it finds;
# this is only the preferred pick when several are present.
DEFAULT_BUILD = "h22.0.400"

# Env overrides (both optional):
#   SYNAPSE_PARM_CATALOG_ROOT  -> a build dir (.../rag/catalog/h22.0.400) OR its
#                                 parent (.../rag/catalog); either is accepted.
#   SYNAPSE_PARM_CATALOG_BUILD -> pick this build subdir under rag/catalog.
_ENV_ROOT = "SYNAPSE_PARM_CATALOG_ROOT"
_ENV_BUILD = "SYNAPSE_PARM_CATALOG_BUILD"


def _repo_rag_catalog() -> Optional[Path]:
    """``<repo>/rag/catalog`` located from this file, or ``None`` if absent.

    catalog.py lives at ``<repo>/python/synapse/validation/catalog.py`` so the
    repo root is ``parents[3]``. On a branch that has not merged W5-CATALOG this
    directory simply will not exist -- the caller degrades to ``None``.
    """
    try:
        root = Path(__file__).resolve().parents[3] / "rag" / "catalog"
    except Exception:  # noqa: BLE001 -- discovery is best-effort
        return None
    return root if root.is_dir() else None


def _resolve_build_dir(rag_catalog: Path) -> Optional[Path]:
    """Choose the build subdir under a ``rag/catalog`` directory.

    Preference order: ``$SYNAPSE_PARM_CATALOG_BUILD`` -> ``DEFAULT_BUILD`` ->
    the lexically-greatest ``h*`` subdir present. Returns ``None`` if nothing
    usable is there.
    """
    env_build = os.environ.get(_ENV_BUILD)
    if env_build:
        cand = rag_catalog / env_build
        return cand if cand.is_dir() else None
    default = rag_catalog / DEFAULT_BUILD
    if default.is_dir():
        return default
    subs = sorted((p for p in rag_catalog.iterdir()
                   if p.is_dir() and p.name.startswith("h")),
                  key=lambda p: p.name)
    return subs[-1] if subs else None


def _default_root() -> Optional[Path]:
    """The build dir the default catalog reads (``.../rag/catalog/<build>``).

    Honors ``$SYNAPSE_PARM_CATALOG_ROOT`` first (accepting either a build dir or
    its parent), then falls back to in-repo discovery. ``None`` when no catalog
    data is reachable -- the honest "no authority" state.
    """
    env_root = os.environ.get(_ENV_ROOT)
    if env_root:
        p = Path(env_root)
        if not p.is_dir():
            return None
        # A build dir has category files directly; a parent has build subdirs.
        if (p / "Cop.json").is_file() or any(
                p.glob("*.json")):
            # If it also has build subdirs and no top-level category files,
            # treat it as a parent below; otherwise it's a build dir.
            if (p / "_manifest.json").is_file() or (p / "Cop.json").is_file():
                return p
        resolved = _resolve_build_dir(p)
        if resolved is not None:
            return resolved
        return p if p.is_dir() else None
    rag_catalog = _repo_rag_catalog()
    if rag_catalog is None:
        return None
    return _resolve_build_dir(rag_catalog)


@lru_cache(maxsize=64)
def _load_types(root_str: str, category: str) -> Optional[Dict[str, dict]]:
    """``types`` map for one category file, cached per (root, category).

    Returns ``None`` for a missing/malformed file or one without a ``types``
    object. Never raises.
    """
    try:
        path = Path(root_str) / f"{category}.json"
        if not path.is_file():
            return None
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    types = data.get("types") if isinstance(data, dict) else None
    return types if isinstance(types, dict) else None


class Catalog:
    """Exact node-schema lookups rooted at one build dir (or ``None``).

    A ``root`` of ``None`` (no catalog data) makes every lookup return ``None``,
    which the gate reads as "no authority -> permissive". Construct with an
    explicit ``root`` in tests to gate against a fixture catalog.
    """

    def __init__(self, root: Optional[os.PathLike | str] = None):
        self._root = Path(root) if root is not None else None

    @property
    def root(self) -> Optional[Path]:
        return self._root

    @property
    def available(self) -> bool:
        return self._root is not None and self._root.is_dir()

    def _types(self, category: str) -> Optional[Dict[str, dict]]:
        if not self.available or not category:
            return None
        return _load_types(str(self._root), category)

    def signature(self, category: str, node_type: str) -> Optional[List[dict]]:
        """Full parm-schema list for a type, or ``None`` if uncatalogued.

        Each element is the raw catalog parm dict (``name``, ``type``,
        ``data_type``, ``default``, ``folder`` ...). ``None`` means the
        (category, node_type) pair is not in the catalog -- distinct from an
        empty list, which would mean a real type with zero parms.
        """
        types = self._types(category)
        if types is None:
            return None
        entry = types.get(node_type)
        if not isinstance(entry, dict):
            return None
        parms = entry.get("parms")
        return parms if isinstance(parms, list) else None

    def parms(self, category: str, node_type: str) -> Optional[FrozenSet[str]]:
        """Valid parm names for a type, or ``None`` if uncatalogued.

        The gate's authority: a name absent from this set (when the set exists)
        is a hallucinated parm. Folder/separator/label controls are included --
        the gate catches invented names, it does not police settability.
        """
        sig = self.signature(category, node_type)
        if sig is None:
            return None
        names = [p.get("name") for p in sig if isinstance(p, dict)]
        return frozenset(n for n in names if isinstance(n, str) and n)

    def has_type(self, category: str, node_type: str) -> bool:
        """True iff this (category, node_type) has a catalog signature."""
        return self.parms(category, node_type) is not None


# ── Module-level default catalog (repo-discovered, env-overridable) ─────────
_DEFAULT: Optional[Catalog] = None


def default_catalog() -> Catalog:
    """Process-wide default catalog, discovered once from the repo/env.

    Cached; call ``reset_default()`` after changing the env in a test.
    """
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Catalog(_default_root())
    return _DEFAULT


def reset_default() -> None:
    """Drop the cached default catalog and the per-file cache (test hook)."""
    global _DEFAULT
    _DEFAULT = None
    _load_types.cache_clear()


def parms(category: str, node_type: str) -> Optional[FrozenSet[str]]:
    """Valid parm names via the default catalog (``None`` if uncatalogued)."""
    return default_catalog().parms(category, node_type)


def signature(category: str, node_type: str) -> Optional[List[dict]]:
    """Full parm signature via the default catalog (``None`` if uncatalogued)."""
    return default_catalog().signature(category, node_type)
