"""Goalpost: APEX recipe/explainer type names are catalog-proven (G2 / WA1-RECIPE).

The phantom-namespace class -- ``apex::rig::`` / ``apex::sop::`` / ``apex::autorig::``
node names the panel invented, which do NOT exist in any Houdini build -- is the
failure this test exists to make UNSHIPPABLE. Two independent gates:

  Gate 1 (catalog membership).  Every APEX/KineFX node type EMITTED by
  ``panel/apex_recipes.py`` (the ``nodes[].type`` values that flow to
  ``houdini_create_node``) must be present in the fresh ``apex_truth`` catalog
  produced by WA1-TRUTH.  A catalog-absent name FAILS.  If NO catalog artifact
  can be found, the test FAILS LOUDLY (raises ``CatalogNotFound``) -- it NEVER
  skips to green.  A skip here would be the exact false-green the wave exists to
  kill (constitution: "skip != pass").

  Gate 2 (phantom-namespace ban).  No ``apex::rig::`` / ``apex::sop::`` /
  ``apex::autorig::`` string survives in any STRING LITERAL of
  ``apex_recipes.py`` or ``apex_explainer.py`` (prose shown to artists, or the
  ``_APEX_TYPE_PATTERNS`` classifier substrings).  ``#`` comments are exempt --
  a migration comment that documents "we replaced apex::sop::fk with
  apex::buildfkgraph" records the FIX, it is never emitted or shown as truth.

Design constraints honoured:
  * Pure Python.  No ``hou``, no ``hython``, no ``import synapse.*`` -- the two
    panel modules are read via ``ast`` / ``tokenize`` so the goalpost cannot be
    broken by an unrelated package-import failure and needs no Houdini runtime.
  * Catalog is discovered from ``APEX_TRUTH_CATALOG`` (explicit path override)
    or, failing that, the newest ``apex_truth_*.json`` under
    ``harness/autoresearch/runs`` / ``python/synapse/autoresearch/runs``.
  * "Membership authority" = the catalog's ``type_exists[*]`` entries that are
    ``exists: true`` (node-type surface) UNION every ``apex_callback_catalog``
    name (graph-callback surface).  Names the catalog explicitly falsified
    (``exists: false`` -- e.g. ``apex::fusegraph``) are treated as absent.

apex_explainer.py emits no node types (it classifies + explains, never creates),
so it contributes nothing to Gate 1; its phantom risk lives entirely in string
literals and is covered by Gate 2.
"""

from __future__ import annotations

import ast
import io
import json
import os
import re
import tokenize
from pathlib import Path

# --- Locations --------------------------------------------------------------
# tests/panel/test_apex_catalog_membership.py -> parents[2] == repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_RECIPES = _REPO_ROOT / "python" / "synapse" / "panel" / "apex_recipes.py"
_EXPLAINER = _REPO_ROOT / "python" / "synapse" / "panel" / "apex_explainer.py"

# Where TRUTH deposits (and commits) the apex_truth catalog.  Primary is the
# autoresearch harness runs dir; the science-package runs dir is a fallback.
_CATALOG_SEARCH_ROOTS = (
    _REPO_ROOT / "harness" / "autoresearch" / "runs",
    _REPO_ROOT / "python" / "synapse" / "autoresearch" / "runs",
)
_CATALOG_GLOB = "apex_truth_*.json"
_CATALOG_ENV = "APEX_TRUTH_CATALOG"

# The three invented middle segments.  No Houdini build has an ``apex::rig::`` /
# ``apex::sop::`` / ``apex::autorig::`` namespace, so ANY string carrying one is
# phantom by construction -- this pattern can never false-fire on a real name.
_PHANTOM_NS = re.compile(r"apex::(?:rig|sop|autorig)::")

# A stamp like ``20260817_122650`` embedded in a run-dir name -- the real
# recency signal (mtime is unreliable across a fresh git checkout).
_STAMP = re.compile(r"(\d{8}_\d{6})")


class CatalogNotFound(FileNotFoundError):
    """Raised when no apex_truth catalog can be located.

    Deliberately a hard error, never a skip: the membership gate cannot be
    honoured without the catalog, and a green result in its absence would be a
    false pass.  Callers let this propagate so pytest reports an ERROR.
    """


# ===========================================================================
# Catalog discovery + parsing
# ===========================================================================

def _iter_catalog_candidates(search_roots):
    for root in search_roots:
        if root.is_dir():
            yield from root.rglob(_CATALOG_GLOB)


def _recency_key(path: Path):
    stamps = _STAMP.findall(path.as_posix())
    stamp = max(stamps) if stamps else ""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (stamp, mtime, path.as_posix())


def discover_catalog_path(search_roots=_CATALOG_SEARCH_ROOTS, env=None) -> Path:
    """Return the catalog path, or raise :class:`CatalogNotFound` -- never skip.

    Priority: the ``APEX_TRUTH_CATALOG`` env override (if set, it must resolve
    to an existing file, else this is a loud error -- an operator who points the
    override at nothing gets told, not silently rescued); otherwise the newest
    ``apex_truth_*.json`` under the search roots.
    """
    env = os.environ if env is None else env
    override = (env.get(_CATALOG_ENV) or "").strip()
    if override:
        p = Path(override)
        if not p.is_file():
            raise CatalogNotFound(
                f"{_CATALOG_ENV}={override!r} does not point at an existing "
                f"catalog file. Refusing to fall back silently."
            )
        return p

    candidates = list(_iter_catalog_candidates(search_roots))
    if not candidates:
        roots = ", ".join(str(r) for r in search_roots)
        raise CatalogNotFound(
            "No apex_truth_*.json catalog found under any of: "
            f"{roots}. WA1-TRUTH must publish the catalog (or set "
            f"{_CATALOG_ENV}) before this goalpost can prove membership. "
            "This is a hard failure by design -- never a skip."
        )
    return max(candidates, key=_recency_key)


def load_catalog_names(path: Path):
    """Parse a catalog into ``(present, absent)`` name sets.

    ``present`` = ``type_exists[*]`` entries with ``exists: true`` UNION every
    ``apex_callback_catalog`` name.  ``absent`` = ``type_exists[*]`` entries the
    catalog explicitly falsified (``exists: false``).
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    present: set[str] = set()
    absent: set[str] = set()
    for entry in data.get("entries", []):
        claim = entry.get("claim", "")
        value = entry.get("value", {}) or {}
        if claim.startswith("type_exists[*]:"):
            name = claim[len("type_exists[*]:"):]
            (present if value.get("exists") else absent).add(name)
        elif claim.startswith("apex_callback_catalog:"):
            for n in value.get("names", []) or []:
                present.add(n)
    return present, absent


# ===========================================================================
# Panel-source extraction (import-free)
# ===========================================================================

def _emitted_recipe_types(source: str) -> set[str]:
    """Every ``nodes[].type`` string in ``apex_recipes.py``.

    A recipe node-spec is a dict literal carrying BOTH a ``"type"`` and a
    ``"name"`` key; its ``"type"`` value is exactly what the recipe emits to
    ``houdini_create_node``.  AST-based, so prose mentions of node names (e.g.
    the migration guide's honestly-flagged ``kinefx::fullbodyik`` sibling) are
    NOT mistaken for emitted types.
    """
    tree = ast.parse(source)
    emitted: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = [k.value for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        if "type" not in keys or "name" not in keys:
            continue
        for k, v in zip(node.keys, node.values):
            if (isinstance(k, ast.Constant) and k.value == "type"
                    and isinstance(v, ast.Constant) and isinstance(v.value, str)):
                emitted.add(v.value)
    return emitted


def _source_minus_comments(source: str) -> str:
    """Return *source* with every ``#`` comment span blanked to spaces.

    ``tokenize`` distinguishes a real comment from a ``#`` inside a string
    literal (e.g. a CSS colour ``"#FF6B6B"``), so string literals -- including
    the classifier's pattern strings and the artist-facing prose -- are fully
    preserved while migration comments are removed.
    """
    lines = source.splitlines(keepends=True)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                (srow, scol), (erow, ecol) = tok.start, tok.end
                if srow == erow:  # comments never span lines
                    line = lines[srow - 1]
                    lines[srow - 1] = line[:scol] + " " * (ecol - scol) + line[ecol:]
    except tokenize.TokenError:
        pass
    return "".join(lines)


def _is_apex_namespaced(name: str) -> bool:
    return name.startswith("apex::") or name.startswith("kinefx::")


# ===========================================================================
# Gate 1 -- catalog membership of EMITTED types (fails loud without a catalog)
# ===========================================================================

def test_emitted_recipe_types_are_catalog_present():
    catalog_path = discover_catalog_path()  # raises CatalogNotFound -> ERROR, never skip
    present, absent = load_catalog_names(catalog_path)

    assert present, f"catalog {catalog_path} yielded zero present names -- parse bug"

    emitted = _emitted_recipe_types(_RECIPES.read_text(encoding="utf-8"))
    assert emitted, "extracted zero emitted node types from apex_recipes.py -- scan bug"

    namespaced = {t for t in emitted if _is_apex_namespaced(t)}
    assert namespaced, "no APEX/KineFX-namespaced emitted types found -- scan bug"

    catalog_absent = sorted(
        t for t in namespaced if t not in present or t in absent
    )
    assert not catalog_absent, (
        "apex_recipes.py emits APEX/KineFX node types the fresh apex_truth "
        f"catalog does not prove present: {catalog_absent}. Catalog: {catalog_path}"
    )


# ===========================================================================
# Gate 2 -- phantom-namespace ban in string literals of both panel modules
# ===========================================================================

def test_no_phantom_namespace_in_panel_string_literals():
    for path in (_RECIPES, _EXPLAINER):
        code = _source_minus_comments(path.read_text(encoding="utf-8"))
        hit = _PHANTOM_NS.search(code)
        assert hit is None, (
            f"{path.name}: phantom namespace {hit.group(0)!r} survives outside a "
            f"comment. apex::rig::/apex::sop::/apex::autorig:: do not exist in any "
            f"Houdini build -- migrate to the real superseded name (apex_probes.py "
            f"supersession map)."
        )


# ===========================================================================
# Gate 1 RED-leg demonstration -- absent catalog fails LOUD, never skips
# ===========================================================================

def test_missing_catalog_fails_loudly_never_skips(tmp_path):
    """The unshippability guarantee: with no catalog reachable, discovery raises
    a hard error (not ``pytest.skip``, not a silent None). Proven two ways:
    an empty search root, and an env override that points at nothing."""
    empty = tmp_path / "empty_runs"
    empty.mkdir()

    raised = False
    try:
        discover_catalog_path(search_roots=(empty,), env={})
    except CatalogNotFound:
        raised = True
    assert raised, "empty search root must raise CatalogNotFound, not skip/return"

    missing = tmp_path / "nope" / "apex_truth_99.json"
    raised_env = False
    try:
        discover_catalog_path(search_roots=(empty,), env={_CATALOG_ENV: str(missing)})
    except CatalogNotFound:
        raised_env = True
    assert raised_env, "env override to a missing file must raise, not fall back silently"

    # Guard against a future refactor sneaking a skip CALL into the discovery
    # path. Matches the invocation form (``skip(`` / ``pytest.skip(``), not the
    # word "skip" that this module's own prose uses to promise it never skips.
    disco_src = Path(__file__).read_text(encoding="utf-8")
    disco_body = disco_src.split("def discover_catalog_path", 1)[1].split("\ndef ", 1)[0]
    assert re.search(r"\bskip\s*\(", disco_body) is None, (
        "discover_catalog_path must never call skip() -- absent catalog is a hard failure"
    )


# ===========================================================================
# Freshness -- the catalog we gate against is the real WA1-TRUTH artifact
# ===========================================================================

def test_catalog_is_the_apex_truth_artifact():
    """Sanity: the discovered catalog is an apex_truth artifact for an APEX
    build, not some unrelated JSON that happens to match the glob."""
    catalog_path = discover_catalog_path()
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    meta = data.get("meta", {})
    assert meta.get("artifact_prefix") == "apex_truth", (
        f"{catalog_path} is not an apex_truth artifact (meta={meta})"
    )
    present, _ = load_catalog_names(catalog_path)
    # The invoke bridge is the spine of every recipe that evaluates a graph;
    # if it is missing, we are reading the wrong / a truncated catalog.
    assert "apex::invokegraph" in present, (
        f"catalog {catalog_path} lacks apex::invokegraph -- wrong or partial artifact"
    )
