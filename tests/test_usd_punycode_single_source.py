"""Pin the single-sourced USD punycode parm map.

These encodings (``inputs:color`` -> ``xn__inputscolor_zta`` etc.) used to be
copy-pasted across core/aliases.py, mcp/server.py and agent/specialist_modes.py,
and the copies *disagreed* on color (latent bugs: 'vya' was a copy-paste from
exposure; 'kya' was also phantom). They now live in one place —
``synapse.core.usd_punycode`` — live-probed off a real domelight on 21.0.671,
and the grep-guard below fails loud if either wrong literal ever reappears.
"""

import os
import sys

# Add package to path (same idiom as the rest of the suite)
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.core.usd_punycode import PUNYCODE_PARMS, USD_ATTR_NAMES, encoded
from synapse.core.aliases import USD_PARM_ALIASES, resolve_usd_parm


# The wrong, divergent color encodings. Both are phantom on 21.0.671:
# '_vya' was a copy-paste from exposure; '_kya' was the prior hand-maintained
# guess. Neither resolves on a live light. The grep-guard forbids both.
_WRONG_COLORS = ("xn__inputscolor_vya", "xn__inputscolor_kya")
# The canonical encoding, single-sourced from usd_punycode: the live-probed
# color3f parmTuple BASE name (components _ztar/_ztag/_ztab).
_CANONICAL_COLOR = "xn__inputscolor_zta"

_SYNAPSE_DIR = os.path.join(python_dir, "synapse")
_USD_PUNYCODE_FILE = os.path.join(_SYNAPSE_DIR, "core", "usd_punycode.py")

# Camera — UsdGeomCamera attrs are NOT ``inputs:``-namespaced, so the camera
# LOP never punycode-encodes them: the parm names are the plain camelCase
# schema attrs. Live-probed off the camera LOP on 21.0.671 (2026-07-01,
# harness/notes/verified_nodetype_catalog_21.0.671.json). These aliases live
# in USD_ATTR_NAMES, never in PUNYCODE_PARMS.
_CAMERA_PLAIN = {
    "focal_length": "focalLength",
    "focus_distance": "focusDistance",
    "fstop": "fStop",
    "horizontal_aperture": "horizontalAperture",
    "vertical_aperture": "verticalAperture",
    "clipping_range": "clippingRange",
}
# The six phantom xn__ camera guesses scrubbed 2026-07-01. Grep-guarded below:
# none may ever reappear anywhere under python/synapse (not even usd_punycode).
_PHANTOM_CAMERA = (
    "xn__inputsfocallength_e4b",
    "xn__inputsfocusdistance_f7b",
    "xn__inputsfstop_vya",
    "xn__inputshorizontalaperture_ohb",
    "xn__inputsverticalaperture_gfb",
    "xn__inputsclippingrange_e4b",
)


def test_punycode_parms_has_known_keys():
    """The canonical map exposes the expected friendly aliases."""
    expected = {
        "intensity",
        "exposure",
        "exposure_control",
        "color",
        "color_control",
        "color_temperature",
        "enable_temperature",
        "normalize",
        "diffuse",
        "specular",
        "texture_file",
        "texture_format",
    }
    missing = expected - set(PUNYCODE_PARMS)
    assert not missing, f"PUNYCODE_PARMS missing keys: {sorted(missing)}"
    # Every value is a punycode encoding.
    for alias, enc in PUNYCODE_PARMS.items():
        assert enc.startswith("xn__"), f"{alias} -> {enc} is not punycode-encoded"


def test_encoded_helper_matches_dict():
    assert encoded("color") == PUNYCODE_PARMS["color"]
    assert encoded("not_a_real_alias") is None


def test_color_resolves_to_verified_tuple_base_no_drift():
    """aliases.py must resolve color to the live-probed tuple-base encoding."""
    assert PUNYCODE_PARMS["color"] == _CANONICAL_COLOR
    assert PUNYCODE_PARMS["color"] not in _WRONG_COLORS
    # aliases.py is single-sourced, so it must agree.
    assert USD_PARM_ALIASES["color"] == _CANONICAL_COLOR
    assert USD_PARM_ALIASES["light_color"] == _CANONICAL_COLOR
    assert resolve_usd_parm("color") == _CANONICAL_COLOR


def test_aliases_single_sourced_from_usd_punycode():
    """No xn__ encoding in USD_PARM_ALIASES may drift from PUNYCODE_PARMS."""
    by_value = set(PUNYCODE_PARMS.values())
    for alias, enc in USD_PARM_ALIASES.items():
        if enc.startswith("xn__"):
            assert enc in by_value, (
                f"USD_PARM_ALIASES[{alias!r}] = {enc!r} is not single-sourced "
                f"from usd_punycode.PUNYCODE_PARMS"
            )


def test_wrong_color_literals_absent_everywhere_but_usd_punycode():
    """grep-guard: neither phantom color literal ('vya'/'kya') may reappear.

    usd_punycode.py is the ONE file allowed to mention them — in the docstring
    documenting which encodings were phantom and why.
    """
    offenders = []
    for dirpath, _dirnames, filenames in os.walk(_SYNAPSE_DIR):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(dirpath, fname)
            if os.path.abspath(fpath) == os.path.abspath(_USD_PUNYCODE_FILE):
                continue
            with open(fpath, "r", encoding="utf-8") as fh:
                text = fh.read()
            for wrong in _WRONG_COLORS:
                if wrong in text:
                    offenders.append(
                        f"{os.path.relpath(fpath, _SYNAPSE_DIR)} ({wrong})"
                    )
    assert not offenders, (
        f"Phantom color literal(s) found in: {offenders}. "
        f"Use synapse.core.usd_punycode.PUNYCODE_PARMS['color'] instead."
    )


def test_camera_parms_are_plain_camelcase_not_punycode():
    """Camera parms are plain camelCase — never punycode (2026-07-01 probe).

    UsdGeomCamera attrs are not ``inputs:*``, so the camera LOP surfaces them
    under the schema names verbatim. The aliases must resolve to those plain
    names via USD_ATTR_NAMES, and must never re-enter PUNYCODE_PARMS.
    """
    for alias, plain in _CAMERA_PLAIN.items():
        assert alias not in PUNYCODE_PARMS, (
            f"{alias!r} re-entered PUNYCODE_PARMS — camera parms are plain "
            f"camelCase, never punycode (verified_nodetype_catalog_21.0.671.json)"
        )
        assert USD_ATTR_NAMES[alias] == plain
        assert USD_PARM_ALIASES[alias] == plain
        assert resolve_usd_parm(alias) == plain


def test_phantom_camera_literals_absent_in_code():
    """grep-guard: none of the six phantom camera encodings may reappear.

    Unlike the color guard, there is NO exempt file — the phantoms were
    guesses, not probe results, so not even usd_punycode.py may carry them.
    """
    offenders = []
    for dirpath, _dirnames, filenames in os.walk(_SYNAPSE_DIR):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(dirpath, fname)
            with open(fpath, "r", encoding="utf-8") as fh:
                text = fh.read()
            for wrong in _PHANTOM_CAMERA:
                if wrong in text:
                    offenders.append(
                        f"{os.path.relpath(fpath, _SYNAPSE_DIR)} ({wrong})"
                    )
    assert not offenders, (
        f"Phantom camera encoding(s) found in: {offenders}. Camera parms are "
        f"plain camelCase — use synapse.core.usd_punycode.USD_ATTR_NAMES."
    )
