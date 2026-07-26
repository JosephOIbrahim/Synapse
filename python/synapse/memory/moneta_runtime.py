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

**Provenance.** Because ``$MONETA_SRC`` names a *working directory*, "which
Moneta" is not answered by a version string or even a path — the substrate is
whatever branch that worktree has checked out, and it can change under SYNAPSE
without a single SYNAPSE file changing. :func:`moneta_provenance` therefore
resolves and reports the checked-out git SHA (read from the git metadata files,
never via a subprocess, cached per package root). Read :data:`REVISION_SCOPE`
before treating that SHA as a full pin: it covers committed state only.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, Optional, Tuple

_MONETA_AVAILABLE = False
_MONETA_IMPORT_ERROR: Optional[str] = None
Moneta = None
MonetaConfig = None

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


# ── git-revision resolution (pure file reads; never a subprocess) ────────────
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


def moneta_provenance() -> dict:
    """Which Moneta actually loaded, for diagnostics + drift detection.

    SYNAPSE declares no moneta dependency and imports whatever is installed,
    and the package exposes no ``__version__``. Worse, ``importlib.metadata``
    reports the same ``1.2.0rc1`` for rc1, rc2, and rc2+N commits, so the
    version string cannot discriminate builds. The resolved ``file`` path
    names which copy is on ``sys.path``; ``revision`` names WHICH COMMIT of
    that copy, which is the field that actually discriminates when
    ``$MONETA_SRC`` points at a live worktree (the deployed configuration).

    Read :data:`REVISION_SCOPE` before treating ``revision`` as a full pin --
    it covers committed state only.
    """
    prov: dict = {"available": _MONETA_AVAILABLE, "version": None,
                  "file": None, "import_error": _MONETA_IMPORT_ERROR,
                  "moneta_src": os.environ.get("MONETA_SRC"),
                  "root": None, "revision": None, "revision_ref": None,
                  "revision_source": "unavailable", "revision_repo": None,
                  "revision_resolved_at": None,
                  "revision_scope": REVISION_SCOPE}
    if not _MONETA_AVAILABLE:
        return prov
    prov["version"] = _dist_version()
    try:
        import moneta as _m
        prov["file"] = getattr(_m, "__file__", None)
    except Exception:  # noqa: BLE001
        pass
    prov.update(_resolve_revision(prov["file"]))
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
