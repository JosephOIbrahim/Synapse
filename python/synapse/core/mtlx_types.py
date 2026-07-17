"""
Single-source MaterialX node-type constants + H22 survival probe.

MaterialX ships *inside* OpenUSD, so the MaterialX node set rides Houdini's
USD version bump. When H22 advances USD, these node-type strings are the most
likely silent breakage surface (a renamed/removed shader node fails the
``createNode`` call). Single-sourcing them here means one probe can flag the
whole set, and one edit fixes every call site.

All strings are the literal Houdini VOP node-type names used inside a
``materiallibrary`` LOP (MaterialX shader nodes are VOPs).

RAG-undocumented (higher break risk on a major bump — verify first):
    * ``mtlxgeompropvalue`` — used in-repo, absent from the H21 RAG corpus
    * ``mtlxvolume``        — used in-repo, absent from the RAG corpus

H22 history: ``mtlxstandard_volume`` (the pre-1.39 standard_volume shader) is
ABSENT on 22.0.368 — probe-confirmed twice (N-6 dump, `h22-now-probes-2026-07-16.md:149`;
re-confirmed on 22.0.368 hython at the C-MTLX fix). Its slot repointed to
``mtlxvolume`` (the MaterialX 1.39 volume *shader*: parms ``vdf``/``edf`` —
the shader analog of ``mtlxstandard_surface``, NOT ``mtlxvolumematerial``,
which is a material binder with a single ``volumeshader`` parm).
Pinned by ``tests/test_mtlx_conformance.py``.
"""

# --- MaterialX VOP node-type names (single source of truth) ---------------
MTLX_STANDARD_SURFACE = "mtlxstandard_surface"
MTLX_IMAGE = "mtlximage"
MTLX_NORMALMAP = "mtlxnormalmap"

# RAG-undocumented — flagged for priority re-verification on any major bump.
MTLX_GEOMPROPVALUE = "mtlxgeompropvalue"  # RAG-undocumented
MTLX_VOLUME = "mtlxvolume"                # RAG-undocumented; H22 successor of the
                                          # removed mtlxstandard_volume (C-MTLX)

# Every MaterialX node type the repo emits, in one tuple.
MTLX_TYPES = (
    MTLX_STANDARD_SURFACE,
    MTLX_IMAGE,
    MTLX_NORMALMAP,
    MTLX_GEOMPROPVALUE,
    MTLX_VOLUME,
)

# Subset that is undocumented in the RAG corpus (elevated break risk).
MTLX_TYPES_RAG_UNDOCUMENTED = (
    MTLX_GEOMPROPVALUE,
    MTLX_VOLUME,
)

# Houdini API — survival probe only. No-op when hou is absent (CI/standalone).
try:
    import hou
    _HOU_AVAILABLE = True
except ImportError:
    hou = None
    _HOU_AVAILABLE = False


def mtlx_type_survival():
    """Probe each MaterialX node type against the live VOP node-type category.

    MaterialX shader nodes are VOPs, so membership is decided by
    ``hou.nodeType(hou.vopNodeTypeCategory(), name) is not None`` — the same
    ``dir()``-style hard gate the scout uses, applied to the node-type table.

    Returns a dict mapping each node-type string to:
        * ``True``  — the type resolves in the live runtime (survived)
        * ``False`` — the type is a phantom in this build (H22 break)
        * ``None``  — hou is unavailable; cannot probe (CI/standalone no-op)

    Never raises — a missing API per entry degrades that entry to ``None``.
    """
    if not _HOU_AVAILABLE:
        return {name: None for name in MTLX_TYPES}

    try:
        category = hou.vopNodeTypeCategory()
    except Exception:
        return {name: None for name in MTLX_TYPES}

    result = {}
    for name in MTLX_TYPES:
        try:
            result[name] = hou.nodeType(category, name) is not None
        except Exception:
            result[name] = None
    return result
