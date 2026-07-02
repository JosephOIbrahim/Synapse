"""Corpus encoding conformance — keep the retrievable ``rag/`` corpus in sync
with the single-source USD punycode registry.

The code single-sources the correct light encodings in
``synapse.core.usd_punycode.PUNYCODE_PARMS`` (live-probed off 21.0.671). But
``knowledge_lookup`` / ``scout`` retrieve from the ``rag/`` corpus, so a phantom
encoding sitting in a markdown/JSON doc *re-teaches the exact bug the code just
fixed*. These tests make corpus re-rot a hard failure:

1. No ``xn__`` literal anywhere under ``rag/`` may equal a known phantom (from
   the verified-JSON phantom list + the corpus phantoms scrubbed in this pass).
2. Among every token we hold a verified-or-phantom opinion on, the corpus may
   only contain the value that matches ``PUNYCODE_PARMS`` (the single source).
3. The test's canonical aliases stay pinned to ``PUNYCODE_PARMS`` — if the
   single source is re-probed on a USD bump (H22) and an encoding moves, this
   test must be regenerated rather than silently passing.

Pure-Python: reads the registry, the verified-encodings JSON, and the corpus
text. No ``hou`` import.
"""

import json
import os
import re
import sys
from pathlib import Path

# Add package to path (same idiom as the rest of the suite).
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
if python_dir not in sys.path:
    sys.path.insert(0, python_dir)

from synapse.core.usd_punycode import PUNYCODE_PARMS  # noqa: E402  (single source)

_REPO = Path(package_root)
_RAG = _REPO / "rag"
_VERIFIED_JSON = _REPO / "harness" / "notes" / "verified_usdlux_encodings_21.0.671.json"

_XN = re.compile(r"xn__[A-Za-z0-9_]+")
_TEXT_EXT = {".md", ".json", ".txt", ".rst"}


# ---------------------------------------------------------------------------
# Canonical light-param aliases -> the phantom encodings that were scrubbed
# from the corpus in this de-poison pass. The KEY is the PUNYCODE_PARMS alias
# (so the registry value is the verified answer); the VALUES are wrong twins
# that must never reappear in rag/. Hash suffixes are opaque and drift per
# build, so every entry is a full token — never compare on the hash alone
# (``_vya`` is correct for exposure/specular but phantom for diffuse/color).
# ---------------------------------------------------------------------------
CANON_ALIAS_TO_PHANTOMS = {
    "color": ("xn__inputscolor_kya", "xn__inputscolor_vya"),
    "texture_file": ("xn__inputstexturefile_i1a", "xn__inputstexturefile_a1b"),
    "color_temperature": (
        "xn__inputscolortemperature_u5a",
        "xn__inputscolortemperature_alb",
        "xn__inputscolortemperature_job",
        "xn__inputscolorTemperature_r8a",
    ),
    "enable_temperature": (
        "xn__inputsenablecolortemperature_r5a",
        "xn__inputsenablecolortemperature_r4b",
    ),
    "diffuse": ("xn__inputsdiffuse_vya",),
    "specular": ("xn__inputsspecular_01a",),
    "normalize": ("xn__inputsnormalize_01a", "xn__inputsnormalize_ida"),
    "texture_format": ("xn__inputstextureformat_r1a", "xn__inputstextureformat_i7a"),
    "angle": ("xn__inputsangle_06a",),
    "shadow_color": ("xn__inputsshadowcolor_o5a",),
    # Geometry + cone/focus shaping — DE-PHANTOMED 2026-06-26. These leaves were
    # placeholders/guesses in both the corpus and the prior registry; the right
    # values are now live-probed on 21.0.671 and single-sourced in
    # PUNYCODE_PARMS (radius=_mva, width=_zta, height=_mva, length=_mva,
    # shaping*cone*angle=_wcbhe, *softness=_shbhe, focus=_e5ah). The VALUES below
    # are the wrong twins that were scrubbed from rag/ and must never return.
    "radius": ("xn__inputsradius_o5a",),
    "width": ("xn__inputswidth_e5a",),
    "height": ("xn__inputsheight_k5a", "xn__inputsheight_i5a"),
    "length": ("xn__inputslength_i5a",),
    "shaping_cone_angle": (
        "xn__inputsshapingconeangle_bobja",
        "xn__inputsshapingconeangle_hgbb",
    ),
    "shaping_cone_softness": (
        "xn__inputsshapingconesoftness_brbja",
        "xn__inputsshapingconesoftness_jlbb",
    ),
    "shaping_focus": (
        "xn__inputsshapingfocus_i5a",
        "xn__inputsshapingfocus_e5a",
    ),
}

# color3f component phantoms (the tuple base lives in PUNYCODE_PARMS, the
# per-channel components live in the verified JSON ``tuples_verified``).
COMPONENT_PHANTOMS = (
    "xn__inputscolorr_o5a",
    "xn__inputscolorg_o5a",
    "xn__inputscolorb_o5a",
)

# Camera phantoms — DE-PHANTOMED 2026-07-01 (live camera-LOP probe,
# harness/notes/verified_nodetype_catalog_21.0.671.json). UsdGeomCamera attrs
# (focalLength, focusDistance, fStop, horizontalAperture, verticalAperture,
# clippingRange) are NOT ``inputs:``-namespaced, so the camera LOP never
# punycode-encodes them: the real parm names are the plain camelCase schema
# attrs, single-sourced in ``usd_punycode.USD_ATTR_NAMES`` (NOT in
# PUNYCODE_PARMS — camera keys are not in CANON_ALIAS_TO_PHANTOMS above for
# that reason). The xn__ guesses below must never (re)appear in the corpus.
CAMERA_PHANTOMS = (
    "xn__inputsfocallength_e4b",
    "xn__inputsfocusdistance_f7b",
    "xn__inputsfstop_vya",
    "xn__inputshorizontalaperture_ohb",
    "xn__inputsverticalaperture_gfb",
    "xn__inputsclippingrange_e4b",
)


def _load_verified():
    return json.loads(_VERIFIED_JSON.read_text(encoding="utf-8"))


def _verified_components():
    """Verified color3f component encodings from the ground-truth JSON."""
    comps = set()
    for entry in _load_verified().get("tuples_verified", {}).values():
        comps.update(entry.get("components", []))
    return comps


def _phantom_set():
    """Every encoding that must NOT appear in the corpus."""
    phantoms = set(COMPONENT_PHANTOMS) | set(CAMERA_PHANTOMS)
    for sibs in CANON_ALIAS_TO_PHANTOMS.values():
        phantoms.update(sibs)
    # Augment from the verified JSON's own phantom ledger.
    v = _load_verified()
    for section in ("PHANTOM_in_aliases_py", "PHANTOM_in_system_prompt"):
        for entry in v.get(section, {}).values():
            if isinstance(entry, dict) and entry.get("shipped"):
                phantoms.add(entry["shipped"])
    for entry in v.get("also_wrong_elsewhere", {}).values():
        if isinstance(entry, dict) and entry.get("shipped"):
            phantoms.add(entry["shipped"])
    # A verified registry value must never be classified as a phantom.
    return phantoms - set(PUNYCODE_PARMS.values()) - _verified_components()


def _rag_files():
    return [
        p
        for p in _RAG.rglob("*")
        if p.is_file() and p.suffix.lower() in _TEXT_EXT
    ]


def _tokens_with_locations():
    """token -> list of 'relpath:lineno' where it appears."""
    locs = {}
    for f in _rag_files():
        rel = f.relative_to(_REPO).as_posix()
        for i, line in enumerate(
            f.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            for tok in _XN.findall(line):
                locs.setdefault(tok, []).append(f"{rel}:{i}")
    return locs


def test_rag_corpus_exists():
    """Guard: the corpus must be on disk, or the conformance is vacuous."""
    assert _RAG.is_dir(), f"rag corpus not found at {_RAG}"
    assert _VERIFIED_JSON.is_file(), f"ground-truth JSON missing at {_VERIFIED_JSON}"


def test_canonical_aliases_pinned_to_single_source():
    """Every alias we de-poison against must exist in the registry, and the
    registry value must not itself be one of the known phantoms. Forces this
    test to be regenerated if usd_punycode.py is re-probed on a USD bump."""
    for alias, phantoms in CANON_ALIAS_TO_PHANTOMS.items():
        assert alias in PUNYCODE_PARMS, f"unknown alias {alias!r} in conformance map"
        assert PUNYCODE_PARMS[alias] not in phantoms, (
            f"registry value for {alias!r} ({PUNYCODE_PARMS[alias]!r}) is listed "
            f"as a phantom — regenerate this test from usd_punycode.py"
        )


def test_no_phantom_encoding_in_corpus():
    """No phantom light encoding may appear anywhere under rag/."""
    phantoms = _phantom_set()
    locs = _tokens_with_locations()
    offenders = {tok: locs[tok] for tok in phantoms if tok in locs}
    assert not offenders, (
        "Phantom USD light encodings re-rotted into the corpus "
        "(re-teaches a bug fixed in synapse.core.usd_punycode):\n"
        + "\n".join(f"  {tok} @ {sites}" for tok, sites in sorted(offenders.items()))
    )


def test_corpus_light_encodings_match_registry():
    """Among every token we hold a verified-or-phantom opinion on, the corpus
    may only contain the value that matches PUNYCODE_PARMS."""
    verified = set(PUNYCODE_PARMS.values()) | _verified_components()
    family = verified | _phantom_set()
    locs = _tokens_with_locations()
    present = set(locs) & family
    bad = present - verified
    assert not bad, (
        "corpus light-param encodings diverge from the single source:\n"
        + "\n".join(f"  {tok} @ {locs[tok]}" for tok in sorted(bad))
    )
