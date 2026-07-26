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

Substrate truth (H6 / R64)
--------------------------
"Moneta is working as SYNAPSE's USD substrate" is FIVE independent claims, not
one. :func:`moneta_available` tests exactly the first, and any of the other
four can be false while it still reads ``True``::

    1  the module imports                    <- moneta_available()
    2  the SAME module on both interpreters  <- compare provenance["file"]
    3  the schema is REGISTERED with USD     <- schema_registered()
    4  prims are AUTHORED with that type     <- schema_in_use()
    5  a memory ROUND-TRIPS typed            <- 3 AND 4 together

Conditions 3 and 4 are reported here as **tri-state**: ``True`` / ``False`` /
``None``. ``None`` means *could not check* and is NOT ``False``. Collapsing
those two is the defect this module exists to stop -- a boolean that cannot
say "I don't know" will say "no" when it means "I never looked", and a boolean
that cannot say "no" is a decoration.

The pair matters more than either field. ``schema_in_use`` alone is NOT
evidence of a working substrate: Sdf-level authoring is schema-blind, so USD
writes ``typeName="MonetaMemory"`` to disk with or without a registered
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

import os
import sys
from typing import Any, Optional, Tuple

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


def moneta_provenance(usd_root: Optional[Any] = None) -> dict:
    """Which Moneta actually loaded, for diagnostics + drift detection.

    SYNAPSE declares no moneta dependency and imports whatever is installed,
    and the package exposes no ``__version__``. Worse, ``importlib.metadata``
    reports the same ``1.2.0rc1`` for rc1, rc2, and rc2+N commits, so the
    version string cannot discriminate builds. The resolved ``file`` path is
    the load-bearing field -- it names exactly which copy is on ``sys.path``.

    Reports five fields, one per condition (H6 / R64): ``available``,
    ``version``/``file`` (which copy -- compare across interpreters for
    condition 2), ``schema_registered``, and ``schema_in_use``. Each schema
    field is accompanied by a ``*_reason`` naming how the verdict was reached,
    because a tri-state without a reason still cannot tell an operator WHY it
    said ``None``.

    **This function must never raise.** ``store.py``'s ``_make_store`` calls it
    from inside its own ``except`` handler to name the resolved copy; an
    exception here would propagate out of ``_make_store`` and break Houdini
    panel startup -- exactly the failure the backend flag is contracted never
    to cause. Every field is computed defensively and the whole body is
    fenced, so a broken probe degrades to ``None`` and never to a traceback.
    """
    prov: dict = {"available": _MONETA_AVAILABLE, "version": None,
                  "file": None, "import_error": _MONETA_IMPORT_ERROR,
                  "schema_registered": None, "schema_registered_reason": None,
                  "schema_in_use": None, "schema_in_use_reason": None,
                  "usd_root_inspected": None}

    # Conditions 3 and 4 are independent of whether the PACKAGE imported, so
    # they are computed before the early return. A schema can be registered
    # with no moneta on sys.path, and prims can be authored by a copy this
    # interpreter cannot import.
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
    try:
        import importlib.metadata as _md
        prov["version"] = _md.version("moneta")
    except Exception:  # noqa: BLE001 -- best-effort
        pass
    try:
        import moneta as _m
        prov["file"] = getattr(_m, "__file__", None)
    except Exception:  # noqa: BLE001
        pass
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
