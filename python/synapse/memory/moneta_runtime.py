"""Import-guarded access to the Moneta memory engine (Mile 3).

Moneta ships as a separate package (repo: JosephOIbrahim/Moneta). It is NOT a
hard dependency of SYNAPSE: this module guards the import so SYNAPSE runs
unchanged when Moneta is absent (CI without the package, or environments that
haven't opted into the Moneta backend). When present, :func:`make_ephemeral`
builds a pxr-free, in-memory, ``MockUsdTarget``-backed handle -- the path CI
exercises with no OpenUSD requirement (harness AP9).

Package resolution order:
  1. ``import moneta`` (pip-installed, or already on ``sys.path``).
  2. If that fails and ``$MONETA_SRC`` points at a directory, insert it on
     ``sys.path`` and retry.

Packaging Moneta as a proper wheel is the long-term fix; until then the env
var is the seam (the production bridge / CI sets it). No user-specific path is
ever hard-coded here.

Substrate truth -- five conditions, five fields (R64, composed by U1)
--------------------------------------------------------------------
"Moneta is working as SYNAPSE's USD substrate" is FIVE independent claims, not
one. :func:`moneta_available` tests exactly the first, and any of the other
four can be false while it still reads ``True``::

    1  the module imports                    <- moneta_available()
    2  the SAME module on both interpreters  <- file + revision (below)
    3  the schema is REGISTERED with USD     <- schema_registered()
    4  prims are AUTHORED with that type     <- schema_in_use()
    5  a memory ROUND-TRIPS typed            <- 3 AND 4 together

:func:`moneta_provenance` reports all five in ONE payload. That composition is
the point, and it is why this module was AUTHORED rather than merged: R64
specified the five fields and the work was then dispatched as two independent
legs -- LEDGER (conditions 1/2) and H6 (conditions 1/3/4) -- which rewrote this
function from the same base in ignorance of each other. Neither half was
complete and the two conflicted textually. R91 ruled the union authored.

Condition 2 -- WHICH copy, and which COMMIT of it
-------------------------------------------------
Because ``$MONETA_SRC`` names a *working directory*, "which Moneta" is not
answered by a version string or even by a path -- the substrate is whatever
branch that worktree has checked out, and it can change under SYNAPSE without a
single SYNAPSE file changing. ``importlib.metadata`` reports the same
``1.2.0rc1`` for rc1, rc2 and rc2+N (and reports NOTHING at all for a
path-injected copy), so the version string cannot discriminate builds.
:func:`moneta_provenance` therefore also resolves and reports the checked-out
git SHA, read from the git metadata files, never via a subprocess, cached per
package root. Read :data:`REVISION_SCOPE` before treating that SHA as a full
pin: it covers committed state only.

The walk that resolves it is BOUNDED (:data:`MAX_REVISION_WALK`). Unbounded, it
reported the ENCLOSING repository's HEAD as Moneta's revision -- provenance that
was not absent but **confidently wrong**, which is worse, because a wrong SHA is
trusted (LEDGER.F2 / R52).

Conditions 3 and 4 -- tri-state, and only meaningful as a PAIR
--------------------------------------------------------------
Conditions 3 and 4 are reported here as **tri-state**: ``True`` / ``False`` /
``None``. ``None`` means *could not check* and is NOT ``False``. Collapsing
those two is the defect this module exists to stop -- a boolean that cannot
say "I don't know" will say "no" when it means "I never looked", and a boolean
that cannot say "no" is a decoration.

The pair matters more than either field. ``schema_in_use`` alone is NOT
evidence of a working substrate (R75): Sdf-level authoring is schema-blind, so
USD writes ``typeName="MonetaMemory"`` to disk with or without a registered
schema. VERIFIED-RUNTIME 2026-07-26, both interpreters, same authored bytes:

    PXR_PLUGINPATH_NAME unset -> GetTypeName()=="MonetaMemory" BUT
                                 IsA(Usd.Typed) is False and the prim
                                 definition is empty  (dead bytes)
    PXR_PLUGINPATH_NAME set   -> IsA(Usd.Typed) is True, definition populated

So ``registered=False, in_use=True`` is the dangerous cell on this build: the
type name is on disk and the runtime does not know what it means. Nothing in
``packages/synapse.json`` or in Moneta itself sets ``PXR_PLUGINPATH_NAME``
(Moneta's own ``SURGERY_complete_codeless_schema.md:21`` states the substrate
deliberately does not register the plugin), so that is the default posture.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_MONETA_AVAILABLE = False
_MONETA_IMPORT_ERROR: Optional[str] = None
Moneta = None
MonetaConfig = None

#: The concrete typed schema Moneta authors. Moneta's schema/plugInfo.json
#: declares ``schemaIdentifier="MonetaMemory"``, ``schemaKind="concreteTyped"``,
#: ``bases=["UsdTyped"]`` -- an IsA schema, not an applied API schema -- so
#: ``FindConcretePrimDefinition`` is the correct registry query.
SCHEMA_TYPE_NAME = "MonetaMemory"

#: Moneta's root layer filename (usd_target.py sublayer routing). Memory prims
#: live in SUBLAYERS (cortex_protected.usda / cortex_YYYY_MM_DD.usda), so the
#: root must be COMPOSED via Usd.Stage.Open -- an Sdf-level read of the root
#: layer alone finds zero prims and would report a false negative.
USD_ROOT_FILENAME = "cortex_root.usda"

#: Traversal bound for :func:`schema_in_use`. A diagnostics probe must not walk
#: an unbounded production stage; it stops at the first match anyway, and the
#: cap is reported in the reason so a truncated scan is never read as "clean".
_MAX_PRIMS_SCANNED = 20000

# What a resolved git SHA does and does not pin. ``$MONETA_SRC`` normally points
# at a live git worktree, so the loaded substrate is "whatever branch is checked
# out PLUS any uncommitted edits". The SHA below captures the first half only.
# Stated as a constant so every consumer carries the caveat instead of inferring
# a stronger guarantee than the evidence supports.
REVISION_SCOPE = (
    "committed-only; uncommitted or untracked working-tree edits under "
    "$MONETA_SRC are NOT captured by this SHA. Resolved once per process and "
    "cached: a git checkout inside $MONETA_SRC during a live session leaves "
    "this SHA stale — compare revision_resolved_at"
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# The distribution version, resolved at most once. importlib.metadata.version()
# scans installed-distribution metadata on every call, and moneta_provenance()
# is on the per-deposit path — a backfill of N records would pay N scans.
_VERSION_UNSET = object()
_VERSION_CACHE: Any = _VERSION_UNSET


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dist_version() -> Optional[str]:
    """``importlib.metadata`` version for the moneta distribution, cached.

    Returns None for a ``$MONETA_SRC`` path-injected copy — there is no
    installed distribution to describe it. That None is informative: it means
    'this copy came from a directory', which is exactly when ``revision``
    becomes the load-bearing field.
    """
    global _VERSION_CACHE
    if _VERSION_CACHE is _VERSION_UNSET:
        try:
            import importlib.metadata as _md
            _VERSION_CACHE = _md.version("moneta")
        except Exception:  # noqa: BLE001 -- best-effort; absence is a real answer
            _VERSION_CACHE = None
    return _VERSION_CACHE

# Resolved-revision cache, keyed by the package root that produced it. The git
# metadata is read from disk exactly once per root (never shelled out, never
# re-read per call) -- moneta_provenance() is called on diagnostic paths and on
# every ledger deposit, so a per-call filesystem walk would be a real cost.
_REVISION_CACHE: Dict[str, Dict[str, Optional[str]]] = {}


def _try_import() -> bool:
    """Attempt to bind ``Moneta``/``MonetaConfig``. Idempotent and cheap."""
    global _MONETA_AVAILABLE, _MONETA_IMPORT_ERROR, Moneta, MonetaConfig
    if _MONETA_AVAILABLE:
        return True
    try:
        from moneta import Moneta as _M, MonetaConfig as _C
        Moneta, MonetaConfig = _M, _C
        _MONETA_AVAILABLE = True
        _MONETA_IMPORT_ERROR = None
        return True
    except Exception as first_err:  # ImportError, or a transitive failure
        src = os.environ.get("MONETA_SRC")
        if src and os.path.isdir(src):
            if src not in sys.path:
                sys.path.insert(0, src)
            try:
                from moneta import Moneta as _M, MonetaConfig as _C
                Moneta, MonetaConfig = _M, _C
                _MONETA_AVAILABLE = True
                _MONETA_IMPORT_ERROR = None
                return True
            except Exception as second_err:
                _MONETA_IMPORT_ERROR = f"{type(second_err).__name__}: {second_err}"
                return False
        _MONETA_IMPORT_ERROR = f"{type(first_err).__name__}: {first_err}"
        return False


_try_import()


def moneta_available() -> bool:
    """True if the Moneta package can be imported (retries once)."""
    return _MONETA_AVAILABLE or _try_import()


def import_error() -> Optional[str]:
    """The last import failure string, or None if Moneta imported cleanly."""
    return _MONETA_IMPORT_ERROR


# ---------------------------------------------------------------------------
# Condition 3 -- is the schema REGISTERED with this USD runtime?
# ---------------------------------------------------------------------------

def _schema_registered_detail() -> Tuple[Optional[bool], str]:
    """``(verdict, reason)`` for :func:`schema_registered`.

    Deliberately independent of ``moneta_available()``: plugin registration is
    a property of the USD runtime's ``PXR_PLUGINPATH_NAME``, not of whether the
    Python package imports. Gating this on ``available`` would re-collapse two
    of the five conditions back into one -- the exact defect being removed.

    NOT cached. Registration is process-global and one-shot in practice, but a
    cache would make the check unable to observe a subprocess that sets the env
    var, which is how it is tested (and the only way it CAN be tested honestly).
    """
    plugin_path = os.environ.get("PXR_PLUGINPATH_NAME") or ""
    try:
        from pxr import Usd
    except Exception as exc:  # noqa: BLE001 -- pxr absent IS a valid outcome
        return None, (
            f"could not check: pxr unavailable ({type(exc).__name__}: {exc}). "
            "This is UNKNOWN, not False."
        )
    try:
        prim_def = Usd.SchemaRegistry().FindConcretePrimDefinition(
            SCHEMA_TYPE_NAME
        )
    except Exception as exc:  # noqa: BLE001 -- registry query itself failed
        return None, (
            f"could not check: SchemaRegistry query raised "
            f"({type(exc).__name__}: {exc}). This is UNKNOWN, not False."
        )
    where = f"PXR_PLUGINPATH_NAME={plugin_path!r}" if plugin_path else (
        "PXR_PLUGINPATH_NAME is unset -- nothing in packages/synapse.json or "
        "in Moneta sets it, so this is the default posture"
    )
    if prim_def is None:
        return False, (
            f"checked and FALSE: FindConcretePrimDefinition("
            f"{SCHEMA_TYPE_NAME!r}) returned None; {where}"
        )
    return True, (
        f"checked and TRUE: FindConcretePrimDefinition({SCHEMA_TYPE_NAME!r}) "
        f"resolved; {where}"
    )


def schema_registered() -> Optional[bool]:
    """Condition 3. Does THIS USD runtime know the ``MonetaMemory`` type?

    ``True``  -- the registry resolved a concrete prim definition.
    ``False`` -- pxr is present, the registry answered, and it does not know it.
    ``None``  -- could not check (no pxr, or the query raised). NOT ``False``.

    Never raises.
    """
    return _schema_registered_detail()[0]


# ---------------------------------------------------------------------------
# Condition 4 -- are prims AUTHORED with that type?
# ---------------------------------------------------------------------------

def _resolve_usd_root(usd_root: Optional[Any]) -> Tuple[Optional[str], str]:
    """Resolve which stage :func:`schema_in_use` should inspect, and say so.

    Law 2 -- a verdict travels with the artifact that produced it. Order:

      1. the explicit ``usd_root`` argument (a root layer file, or a directory
         containing ``cortex_root.usda``),
      2. ``$SYNAPSE_MONETA_USD_ROOT`` -- the operator/test seam,
      3. nothing.

    There is deliberately no fallback that reaches into the live store: as of
    2026-07-26 ``MonetaBackedStore.from_storage_dir`` builds ``MonetaConfig``
    without ``use_real_usd=True``, so the live handle is ``MockUsdTarget``-backed
    and authors ZERO USD files (VERIFIED-RUNTIME, both interpreters). A
    resolver that hunted for a stage SYNAPSE never writes would return None for
    a reason that reads like absence of data rather than absence of wiring.
    Callers that DO have a stage (synapse_doctor) pass it in explicitly.
    """
    candidate = usd_root or os.environ.get("SYNAPSE_MONETA_USD_ROOT") or ""
    source = "usd_root argument" if usd_root else (
        "$SYNAPSE_MONETA_USD_ROOT" if candidate else "none"
    )
    if not candidate:
        return None, source
    path = str(candidate)
    if os.path.isdir(path):
        return os.path.join(path, USD_ROOT_FILENAME), source
    return path, source


def _schema_in_use_detail(
    usd_root: Optional[Any] = None,
) -> Tuple[Optional[bool], str, Optional[str]]:
    """``(verdict, reason, inspected_path)`` for :func:`schema_in_use`."""
    path, source = _resolve_usd_root(usd_root)
    if path is None:
        return None, (
            "could not check: no USD root supplied. Pass usd_root= or set "
            "$SYNAPSE_MONETA_USD_ROOT. NOTE: SYNAPSE's Moneta store is "
            "MockUsdTarget-backed -- moneta_store.from_storage_dir builds "
            "MonetaConfig without use_real_usd=True, so it authors no USD at "
            "all. This is UNKNOWN, not False."
        ), None
    try:
        if not os.path.exists(path):
            return None, (
                f"could not check: no stage at {path} (resolved from {source}). "
                "This is UNKNOWN, not False."
            ), path
    except Exception as exc:  # noqa: BLE001 -- unreadable path is not False
        return None, (
            f"could not check: {path} unreadable ({type(exc).__name__}: {exc}). "
            "This is UNKNOWN, not False."
        ), path
    try:
        from pxr import Usd
    except Exception as exc:  # noqa: BLE001
        return None, (
            f"could not check: pxr unavailable ({type(exc).__name__}: {exc}). "
            "This is UNKNOWN, not False."
        ), path
    try:
        # Compose, do not read the root layer directly: Moneta routes memory
        # prims into SUBLAYERS, so an Sdf-level root read finds zero prims.
        # Same pattern as Moneta tests/_schema_gate_subprocess.py step 3.
        stage = Usd.Stage.Open(path)
        if stage is None:
            return None, (
                f"could not check: Usd.Stage.Open({path}) returned None. "
                "This is UNKNOWN, not False."
            ), path
        scanned = 0
        for prim in stage.Traverse():
            scanned += 1
            if str(prim.GetTypeName()) == SCHEMA_TYPE_NAME:
                return True, (
                    f"checked and TRUE: {prim.GetPath()} on {path} reports "
                    f"typeName {SCHEMA_TYPE_NAME!r} (prim {scanned} of the "
                    f"traversal; resolved from {source}). Authored typeName "
                    f"only -- pair with schema_registered() before reading "
                    f"this as a working typed substrate."
                ), path
            if scanned >= _MAX_PRIMS_SCANNED:
                return None, (
                    f"could not check: traversal of {path} hit the "
                    f"{_MAX_PRIMS_SCANNED}-prim probe cap with no "
                    f"{SCHEMA_TYPE_NAME} prim seen. Truncated, so this is "
                    "UNKNOWN, not False."
                ), path
    except Exception as exc:  # noqa: BLE001 -- a broken stage is not False
        return None, (
            f"could not check: traversing {path} raised "
            f"({type(exc).__name__}: {exc}). This is UNKNOWN, not False."
        ), path
    if scanned == 0:
        return None, (
            f"could not check: {path} composed to zero prims -- nothing has "
            "been authored yet, so there is nothing to judge. This is "
            "UNKNOWN, not False."
        ), path
    return False, (
        f"checked and FALSE: {scanned} prim(s) on {path} and not one reports "
        f"typeName {SCHEMA_TYPE_NAME!r} (resolved from {source})"
    ), path


def schema_in_use(usd_root: Optional[Any] = None) -> Optional[bool]:
    """Condition 4. Does any AUTHORED prim carry ``typeName="MonetaMemory"``?

    ``True``  -- at least one prim on the composed stage reports that type.
    ``False`` -- the stage has prims and none of them do.
    ``None``  -- could not check: no stage supplied, no stage on disk, no pxr,
                 zero prims authored, a truncated scan, or a traversal error.
                 NOT ``False``.

    *usd_root* is a root layer file or a directory containing
    ``cortex_root.usda``; it falls back to ``$SYNAPSE_MONETA_USD_ROOT``.

    Never raises.
    """
    return _schema_in_use_detail(usd_root)[0]


# ── condition 2: git-revision resolution (pure file reads; never a subprocess) ─
#
# $MONETA_SRC points at a working directory, so "which Moneta" is not answered
# by a version string (importlib.metadata reports 1.2.0rc1 for rc1, rc2 and
# rc2+N alike) nor by a path (one path, many branches). The checked-out commit
# is the discriminator. It is read straight out of the git metadata files --
# shelling out to `git` on a hot path is both slow and unavailable in the
# sandboxed/headless contexts this module is expected to survive.


def _read_text(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


# How far above the package root a ``.git`` may live and still plausibly OWN
# this copy of Moneta. An over-wide walk does not merely waste time — it
# FABRICATES provenance: a copy nested inside some other repository reports THAT
# repository's HEAD as the Moneta revision. A wrong SHA is worse than no SHA,
# because it is trusted.
#
# 1, not 3. Every real source layout is at most one level deep
# (``<repo>/moneta``, ``<repo>/src/moneta``, ``<repo>/python/moneta`` -- the
# deployed ``$MONETA_SRC=.../Moneta/src`` is the middle one). A wider bound buys
# no real layout and opens a window: at 3, a vendored copy at
# ``<repo>/vendor/moneta-src/moneta`` inherited ``<repo>``'s HEAD, and the
# site-packages guard below did NOT catch it (CRUCIBLE blocker, 2026-07-26 --
# review had read the class as closed because one sub-case was pinned).
#
# The residual bound, stated rather than hidden: at 1, the revision reported is
# that of the repository DIRECTLY containing the package root. If some other
# project vendors Moneta at its own root or one level in, that project's HEAD is
# what is reported -- and that is the defensible answer, because that repository
# is what versions the copy. ``revision_repo`` names it so the claim is auditable
# instead of implicit.
MAX_REVISION_WALK = 1

# Path components that prove a copy was installed rather than checked out. No
# enclosing repo owns it, however close that repo's .git happens to be.
_INSTALLED_MARKERS = frozenset({"site-packages", "dist-packages"})


def _find_git_dir(start: str) -> Tuple[Optional[str], Optional[str]]:
    """Walk up from ``start`` for a ``.git`` directory (normal clone) or a
    ``.git`` FILE (linked worktree / submodule: ``gitdir: <path>``).

    Returns ``(git_dir, work_dir)`` where ``work_dir`` is the directory that
    HELD the ``.git`` entry — the repository whose HEAD is being reported, which
    the caller surfaces so the claim can be audited.

    Bounded by :data:`MAX_REVISION_WALK`; refuses outright for an installed
    copy. Returning ``(None, None)`` is a correct answer, not a failure."""
    start = os.path.abspath(start)
    # abspath normalizes separators, but split on both anyway: a false negative
    # here does not degrade to "no answer", it degrades to a fabricated one.
    parts = {p.lower() for p in re.split(r"[\\/]", start)}
    if _INSTALLED_MARKERS & parts:
        return None, None
    cur = start
    for _ in range(MAX_REVISION_WALK + 1):
        candidate = os.path.join(cur, ".git")
        if os.path.isdir(candidate):
            return candidate, cur
        if os.path.isfile(candidate):
            match = re.search(r"^gitdir:\s*(.+)$", _read_text(candidate) or "", re.MULTILINE)
            if match:
                gitdir = match.group(1).strip()
                if not os.path.isabs(gitdir):
                    gitdir = os.path.normpath(os.path.join(cur, gitdir))
                if os.path.isdir(gitdir):
                    return gitdir, cur
            return None, None
        parent = os.path.dirname(cur)
        if parent == cur:
            return None, None
        cur = parent
    return None, None


def _common_git_dir(git_dir: str) -> str:
    """The shared git dir that owns refs/packed-refs. A linked worktree's own
    git dir holds HEAD but delegates refs via ``commondir``."""
    text = _read_text(os.path.join(git_dir, "commondir"))
    if not text:
        return git_dir
    common = text.strip()
    if not os.path.isabs(common):
        common = os.path.normpath(os.path.join(git_dir, common))
    return common if os.path.isdir(common) else git_dir


def _resolve_ref(git_dir: str, common_dir: str, ref: str) -> Tuple[Optional[str], Optional[str]]:
    """``refs/heads/x`` -> ``(sha, source)``. Loose ref first, then packed-refs."""
    for base in (git_dir, common_dir):
        loose = (_read_text(os.path.join(base, *ref.split("/"))) or "").strip()
        if _SHA_RE.match(loose):
            return loose, "git-loose-ref"
    packed = _read_text(os.path.join(common_dir, "packed-refs"))
    for line in (packed or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("^"):
            continue
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[1].strip() == ref and _SHA_RE.match(parts[0]):
            return parts[0], "git-packed-refs"
    return None, None


def _resolve_revision(package_file: Optional[str]) -> Dict[str, Optional[str]]:
    """Resolve the git revision behind a loaded ``moneta/__init__.py``.

    Cached per resolved package root: the git files are read ONCE per root for
    the life of the process. Every field is honest about failure -- an
    unresolvable revision reports ``None`` plus a ``revision_source`` naming
    why, never a fabricated or inherited SHA.
    """
    if not package_file:
        return {"root": None, "revision": None, "revision_ref": None,
                "revision_source": "no-package-file"}

    # <root>/moneta/__init__.py -> <root> (the dir $MONETA_SRC would name).
    root = os.path.dirname(os.path.dirname(os.path.abspath(package_file)))
    cached = _REVISION_CACHE.get(root)
    if cached is not None:
        return dict(cached)

    result: Dict[str, Optional[str]] = {
        "root": root, "revision": None, "revision_ref": None,
        "revision_source": "not-a-git-worktree", "revision_repo": None,
        # WHEN the git files were read. The resolution is cached for the life of
        # the process, so a `git checkout` inside $MONETA_SRC during a long
        # Houdini session leaves this SHA stale. Staleness you can see beats
        # staleness you have to infer (CRUCIBLE finding, 2026-07-26).
        "revision_resolved_at": _utc_now(),
    }
    git_dir, work_dir = _find_git_dir(root)
    if git_dir:
        result["revision_repo"] = work_dir
        common_dir = _common_git_dir(git_dir)
        head = (_read_text(os.path.join(git_dir, "HEAD")) or "").strip()
        if _SHA_RE.match(head):  # detached HEAD
            result.update(revision=head, revision_ref="HEAD",
                          revision_source="git-head-detached")
        elif head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()
            sha, source = _resolve_ref(git_dir, common_dir, ref)
            result.update(revision=sha, revision_ref=ref,
                          revision_source=source or "unresolved-ref")
        else:
            result["revision_source"] = "unreadable-head"

    _REVISION_CACHE[root] = dict(result)
    return result


def reset_revision_cache() -> None:
    """Drop the cached git + version resolution (tests; a re-pointed
    ``$MONETA_SRC``). Both caches clear together — a caller re-reading one and
    silently keeping the other would report a spliced provenance."""
    global _VERSION_CACHE
    _REVISION_CACHE.clear()
    _VERSION_CACHE = _VERSION_UNSET


#: Reason recorded when a caller explicitly declined the schema probes. Kept
#: deliberately distinct from every "could not check" string: *I was not asked*
#: and *I looked and could not tell* are different facts, and not collapsing
#: facts of that kind is this module's entire contract.
NOT_PROBED_REASON = (
    "not probed: the caller passed probe_schema=False, so conditions 3 and 4 "
    "were never evaluated on this call. UNKNOWN-BY-REQUEST -- not False, and "
    "not a check that failed."
)


def moneta_provenance(usd_root: Optional[Any] = None, *,
                      probe_schema: bool = True) -> dict:
    """Which Moneta actually loaded, and how much of the substrate is real.

    All five conditions of R64 in one payload (see the module docstring):

    ============================  =========================================
    ``available``                 1 -- the module imports
    ``version`` / ``file``        2 -- WHICH copy is on ``sys.path``
    ``revision`` (+ ``_ref`` /    2 -- WHICH COMMIT of that copy. The field
    ``_source`` / ``_repo`` /          that actually discriminates when
    ``_resolved_at`` / ``_scope``)     ``$MONETA_SRC`` points at a live
                                       worktree -- the deployed configuration
    ``schema_registered``         3 -- does this USD runtime know the type
    ``schema_in_use``             4 -- is any prim AUTHORED with that type
    ============================  =========================================

    Condition 5 (a memory round-trips typed) is 3 AND 4 together; it gets no
    field of its own because it has no measurement of its own.

    ``version`` cannot discriminate builds -- ``importlib.metadata`` reports the
    same ``1.2.0rc1`` for rc1, rc2 and rc2+N, and reports nothing at all for a
    path-injected copy. ``file`` names the copy; ``revision`` names the commit.
    Read :data:`REVISION_SCOPE` before treating ``revision`` as a full pin -- it
    covers committed state only.

    Each schema field is accompanied by a ``*_reason`` naming how the verdict
    was reached, because a tri-state without a reason still cannot tell an
    operator WHY it said ``None``. ``schema_in_use`` is NOT evidence on its own
    (R75) -- read it paired with ``schema_registered``.

    *usd_root* is the stage condition 4 inspects; it falls back to
    ``$SYNAPSE_MONETA_USD_ROOT`` and otherwise reports "could not check".

    *probe_schema* -- pass ``False`` to skip conditions 3 and 4. Both fields
    then report ``None`` with :data:`NOT_PROBED_REASON`. This exists because the
    two halves of this payload have very different costs. The version/revision
    half is cached and effectively free after the first call; the schema half is
    uncached BY DESIGN (registration is process-global, and a cache could not
    observe a subprocess setting ``PXR_PLUGINPATH_NAME`` -- which is the only
    honest way to test it), and when a stage IS resolved it opens and traverses
    that stage. On a per-record caller such as the ledger deposit seam that cost
    is paid once per record. A caller that only needs "which copy" can say so
    rather than paying for an answer it will not read.

    **This function must never raise.** ``store.py``'s ``_make_store`` calls it
    from inside its own ``except`` handler to name the resolved copy; an
    exception here would propagate out of ``_make_store`` and break Houdini
    panel startup -- exactly the failure the backend flag is contracted never
    to cause. Every field is computed defensively and every probe is fenced, so
    a broken probe degrades to ``None`` and never to a traceback.
    """
    prov: dict = {"available": _MONETA_AVAILABLE, "version": None,
                  "file": None, "import_error": _MONETA_IMPORT_ERROR,
                  # condition 2 -- which copy, and which commit of it
                  "moneta_src": os.environ.get("MONETA_SRC"),
                  "root": None, "revision": None, "revision_ref": None,
                  "revision_source": "unavailable", "revision_repo": None,
                  "revision_resolved_at": None,
                  "revision_scope": REVISION_SCOPE,
                  # conditions 3 and 4 -- tri-state, each with its reason
                  "schema_registered": None, "schema_registered_reason": None,
                  "schema_in_use": None, "schema_in_use_reason": None,
                  "usd_root_inspected": None}

    # Conditions 3 and 4 are independent of whether the PACKAGE imported, so
    # they are computed before the early return. A schema can be registered
    # with no moneta on sys.path, and prims can be authored by a copy this
    # interpreter cannot import.
    if not probe_schema:
        prov["schema_registered_reason"] = NOT_PROBED_REASON
        prov["schema_in_use_reason"] = NOT_PROBED_REASON
    else:
        try:
            registered, reg_reason = _schema_registered_detail()
            prov["schema_registered"] = registered
            prov["schema_registered_reason"] = reg_reason
        except Exception as exc:  # noqa: BLE001 -- belt and braces; see docstring
            prov["schema_registered_reason"] = (
                f"could not check: probe itself raised "
                f"({type(exc).__name__}: {exc})"
            )
        try:
            in_use, use_reason, inspected = _schema_in_use_detail(usd_root)
            prov["schema_in_use"] = in_use
            prov["schema_in_use_reason"] = use_reason
            prov["usd_root_inspected"] = inspected
        except Exception as exc:  # noqa: BLE001
            prov["schema_in_use_reason"] = (
                f"could not check: probe itself raised "
                f"({type(exc).__name__}: {exc})"
            )

    if not _MONETA_AVAILABLE:
        return prov
    prov["version"] = _dist_version()
    try:
        import moneta as _m
        prov["file"] = getattr(_m, "__file__", None)
    except Exception:  # noqa: BLE001
        pass
    # update(), not assignment: _resolve_revision's no-package-file arm returns
    # a SUBSET of the revision keys, and the seeded defaults above have to
    # survive for the keys it omits rather than dropping out of the payload.
    # Fenced for the same reason as the schema probes -- _make_store calls this
    # from inside an except handler and a raise here would escape it.
    try:
        prov.update(_resolve_revision(prov["file"]))
    except Exception as exc:  # noqa: BLE001
        prov["revision_source"] = (
            f"could not check: revision probe itself raised "
            f"({type(exc).__name__}: {exc})"
        )
    return prov


def make_ephemeral(embedding_dim: Optional[int] = None, **overrides: Any):
    """Construct an ephemeral, pxr-free Moneta handle (``MockUsdTarget``-backed).

    ``MonetaConfig.ephemeral()`` auto-generates a unique ``storage_uri`` and
    defaults ``use_real_usd=False`` (mock target) with no snapshot/WAL paths,
    so the handle is fully in-memory and needs no OpenUSD.

    The caller owns the handle lifetime -- use it as a context manager or call
    ``close()`` -- because Moneta enforces single-owner URI locking.
    """
    if not moneta_available():
        raise RuntimeError(
            "Moneta is not importable. Install the moneta package or set "
            f"$MONETA_SRC to its source directory. Last error: {import_error()}"
        )
    cfg_kwargs = dict(overrides)
    if embedding_dim is not None:
        cfg_kwargs["embedding_dim"] = embedding_dim
    return Moneta(MonetaConfig.ephemeral(**cfg_kwargs))


# ---------------------------------------------------------------------------
# SYNAPSE-authored cortex_root.usda  (W3-STORE) -- the WRITE side of the substrate
# ---------------------------------------------------------------------------
#
# Everything ABOVE READS the cortex (``schema_in_use`` opens a stage and looks
# for a ``MonetaMemory`` prim). :class:`UsdCortexStore` WRITES it: it
# materializes a real ``cortex_root.usda`` at the resolved usd_root with a typed
# ``MonetaMemory`` root prim carrying a ``version`` attribute, and lands every
# memory as a typed prim keyed by ``(kind, id)``. This is what flips
# ``schema_in_use`` from UNKNOWN ("no stage on disk", condition 4) to True on the
# seat -- ``server/doctor.py::_check_moneta_substrate`` inspects EXACTLY this
# file (it hints ``<store_dir>/.moneta`` and ``_resolve_usd_root`` appends
# ``cortex_root.usda``).
#
# SCOPE, stated honestly (R75, and the module docstring): Sdf/Usd authoring is
# schema-BLIND -- a prim's ``typeName`` is written to disk with or without
# ``PXR_PLUGINPATH_NAME`` registration. So this makes condition 4
# (``schema_in_use``) a real True; it does NOT by itself make condition 3
# (``schema_registered``) True -- that is the separate packages/synapse.json
# ``PXR_PLUGINPATH_NAME`` wiring (see ``fix/moneta-schema-registration``). Until
# both hold, the doctor's *overall* moneta_substrate status stays a loud
# "DEAD BYTES" fail; ``in_use`` alone is the claim this leg makes true.

#: Version stamped on the MonetaMemory root prim's ``version`` attribute.
CORTEX_STORE_VERSION = "1.0.0"

#: The single typed root prim path. Its typeName is ``MonetaMemory`` so a bare
#: (memory-free) store already reports ``schema_in_use=True``.
CORTEX_ROOT_PATH = "/MonetaMemory"

#: Attribute names on each memory prim. ``id`` / ``kind`` hold the RAW key so a
#: round-trip is exact even after ``Tf.MakeValidIdentifier`` mangles the path
#: segment; ``payload`` holds ``Memory.to_json()`` verbatim.
_CORTEX_ATTR_KIND = "kind"
_CORTEX_ATTR_ID = "id"
_CORTEX_ATTR_PAYLOAD = "payload"

def _load_usd_author():
    """Lazily import pxr for AUTHORING. Returns ``(Usd, Sdf, Tf)`` or
    ``(None, None, None)``.

    Function-scoped exactly like the read-side probes (``_schema_*_detail``):
    importing ``moneta_runtime`` must stay pxr-free so the ephemeral engine path
    CI exercises loads no OpenUSD (harness AP9, pinned by
    ``test_ephemeral_path_is_pxr_free``). pxr loads only when a
    :class:`UsdCortexStore` is actually constructed.
    """
    try:
        from pxr import Usd, Sdf, Tf
        return Usd, Sdf, Tf
    except Exception:  # noqa: BLE001 -- pxr absent is a valid standalone/CI outcome
        return None, None, None


def usd_author_available() -> bool:
    """True if pxr is importable for AUTHORING the cortex stage.

    Distinct from :func:`moneta_available` (the engine) and from the read-side
    pxr probes: this gates the WRITE path. When False, :class:`UsdCortexStore`
    degrades to a no-op (``available=False``) and never raises -- the JSONL
    dual-write safety net still carries the memory (W3-STORE non-negotiable).
    Imports pxr on call (lazy); does not load it at module import.
    """
    return _load_usd_author()[0] is not None


class UsdCortexStore:
    """SYNAPSE-authored ``cortex_root.usda`` -- typed ``MonetaMemory`` prims.

    Materializes a real USD stage at *usd_root* (a ``cortex_root.usda`` file, or
    a directory in which case ``cortex_root.usda`` is appended). On construction
    it authors the typed root prim (:data:`CORTEX_ROOT_PATH`, typeName
    ``MonetaMemory``) carrying a ``version`` attribute, so an empty store already
    satisfies the doctor's ``schema_in_use`` condition. :meth:`write` lands a
    memory as a typed prim keyed by ``(kind, id)``; :meth:`query` walks the typed
    prims back.

    Pure OpenUSD -- makes ZERO ``hou.*`` calls (mirrors ``agent_state.py``), so
    it is safe off the Houdini main thread and preserves the store adapter's
    no-hou invariant. Never raises on an authoring failure: it logs and degrades
    to ``available=False`` so a broken stage can never break memory writes.
    """

    ROOT_TYPE_NAME = SCHEMA_TYPE_NAME  # "MonetaMemory"

    def __init__(self, usd_root: Any, *, version: str = CORTEX_STORE_VERSION) -> None:
        # Resolve to a concrete ``cortex_root.usda`` file. A path already ending
        # in ``.usda``/``.usd`` is the layer itself; anything else is the
        # directory that CONTAINS it (append ``cortex_root.usda``). Extension,
        # not os.path.isdir, so a not-yet-created ``.moneta`` dir still resolves
        # to the same file the doctor's _resolve_usd_root(dir) reports.
        p = str(usd_root)
        if not p.lower().endswith((".usda", ".usd")):
            p = os.path.join(p, USD_ROOT_FILENAME)
        self.path = p
        self.version = version
        self._stage = None
        # Lazy pxr resolution -- importing moneta_runtime stays pxr-free.
        self._Usd, self._Sdf, self._Tf = _load_usd_author()
        self.available = self._Usd is not None
        if self.available:
            try:
                self._open_or_create()
            except Exception as exc:  # noqa: BLE001 -- authoring must never break the store
                logger.warning(
                    "UsdCortexStore could not open/create %s (%s: %s); "
                    "cortex authoring disabled, JSONL dual-write still carries memory",
                    self.path, type(exc).__name__, exc,
                )
                self._stage = None
                self.available = False

    # -- lifecycle ----------------------------------------------------------

    @property
    def stage(self):
        return self._stage

    def _open_or_create(self) -> None:
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if os.path.exists(self.path):
            self._stage = self._Usd.Stage.Open(self.path)
            if self._stage is None:
                # Corrupt/unreadable stage: do NOT delete the operator's file
                # (it may be recoverable). Disable authoring loudly instead.
                logger.warning(
                    "cortex_root.usda at %s did not open; cortex authoring "
                    "disabled (file left untouched)", self.path,
                )
                self.available = False
                return
        else:
            self._stage = self._Usd.Stage.CreateNew(self.path)
        self._ensure_root()

    def _ensure_root(self) -> None:
        stage = self._stage
        root = stage.GetPrimAtPath(CORTEX_ROOT_PATH)
        if not root or not root.IsValid():
            root = stage.DefinePrim(CORTEX_ROOT_PATH, self.ROOT_TYPE_NAME)
        elif str(root.GetTypeName()) != self.ROOT_TYPE_NAME:
            root.SetTypeName(self.ROOT_TYPE_NAME)
        attr = root.GetAttribute("version")
        if not attr or not attr.IsValid():
            attr = root.CreateAttribute("version", self._Sdf.ValueTypeNames.String)
        attr.Set(self.version)
        try:
            stage.SetDefaultPrim(root)
        except Exception:  # noqa: BLE001 -- cosmetic; never fatal
            pass
        self._save()

    # -- write --------------------------------------------------------------

    def _child_path(self, kind: str, mem_id: str) -> str:
        safe_kind = self._Tf.MakeValidIdentifier(str(kind) or "unknown")
        safe_id = self._Tf.MakeValidIdentifier(str(mem_id) or "unknown")
        return f"{CORTEX_ROOT_PATH}/{safe_kind}/{safe_id}"

    def write(self, kind: str, mem_id: str, payload: str) -> Optional[str]:
        """Author (or overwrite) a typed ``MonetaMemory`` prim keyed by ``(kind, id)``.

        Idempotent per key -- re-writing the same ``(kind, id)`` overwrites in
        place. Returns the authored prim path, or ``None`` when authoring is
        unavailable (pxr absent / disabled). The intermediate ``{kind}`` prim is
        left untyped (a plain grouping ``def``), so only the root and the leaves
        carry the ``MonetaMemory`` typeName.
        """
        if not self.available or self._stage is None:
            return None
        path = self._child_path(kind, mem_id)
        vt = self._Sdf.ValueTypeNames.String
        prim = self._stage.DefinePrim(path, self.ROOT_TYPE_NAME)
        prim.CreateAttribute(_CORTEX_ATTR_KIND, vt).Set(str(kind))
        prim.CreateAttribute(_CORTEX_ATTR_ID, vt).Set(str(mem_id))
        prim.CreateAttribute(_CORTEX_ATTR_PAYLOAD, vt).Set(str(payload))
        self._save()
        return str(prim.GetPath())

    # -- read ---------------------------------------------------------------

    def query(self, *, kind: Optional[str] = None,
              mem_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Walk the typed ``MonetaMemory`` memory prims.

        Returns a list of ``{"kind", "id", "payload", "path"}`` dicts (the root
        prim itself is skipped). Optional exact filters on ``kind`` / ``mem_id``.
        """
        if not self.available or self._stage is None:
            return []
        out: List[Dict[str, Any]] = []
        for prim in self._stage.Traverse():
            if str(prim.GetTypeName()) != self.ROOT_TYPE_NAME:
                continue
            if str(prim.GetPath()) == CORTEX_ROOT_PATH:
                continue  # the typed root prim is not a memory
            k_attr = prim.GetAttribute(_CORTEX_ATTR_ID)
            if not k_attr or not k_attr.IsValid():
                continue  # a MonetaMemory prim with no id is not one of ours
            k = prim.GetAttribute(_CORTEX_ATTR_KIND).Get()
            i = prim.GetAttribute(_CORTEX_ATTR_ID).Get()
            p_attr = prim.GetAttribute(_CORTEX_ATTR_PAYLOAD)
            pay = p_attr.Get() if (p_attr and p_attr.IsValid()) else None
            if kind is not None and k != kind:
                continue
            if mem_id is not None and i != mem_id:
                continue
            out.append({"kind": k, "id": i, "payload": pay, "path": str(prim.GetPath())})
        return out

    def get(self, kind: str, mem_id: str) -> Optional[Dict[str, Any]]:
        rows = self.query(kind=kind, mem_id=mem_id)
        return rows[0] if rows else None

    def count(self) -> int:
        """Number of typed memory prims (excludes the root prim)."""
        return len(self.query())

    def _save(self) -> None:
        if self._stage is None:
            return
        try:
            self._stage.GetRootLayer().Save()
        except Exception as exc:  # noqa: BLE001 -- a failed save is logged, never raised
            logger.warning(
                "cortex_root.usda save failed at %s (%s: %s)",
                self.path, type(exc).__name__, exc,
            )

    def close(self) -> None:
        self._save()
