"""Pin the single-sourced USD punycode parm map.

These encodings (``inputs:color`` -> ``xn__inputscolor_kya`` etc.) used to be
copy-pasted across core/aliases.py, mcp/server.py and agent/specialist_modes.py,
and the copies *disagreed* on color (a latent bug: 'vya' was a copy-paste from
exposure). They now live in one place — ``synapse.core.usd_punycode`` — and the
grep-guard below fails loud if the wrong literal ever reappears.
"""

import os
import sys

# Add package to path (same idiom as the rest of the suite)
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.core.usd_punycode import PUNYCODE_PARMS, encoded
from synapse.core.aliases import USD_PARM_ALIASES, resolve_usd_parm


# The wrong, divergent color encoding (copy-pasted from exposure_vya).
_WRONG_COLOR = "xn__inputscolor_vya"
# The canonical encoding, single-sourced from usd_punycode.
_CANONICAL_COLOR = "xn__inputscolor_kya"

_SYNAPSE_DIR = os.path.join(python_dir, "synapse")
_USD_PUNYCODE_FILE = os.path.join(_SYNAPSE_DIR, "core", "usd_punycode.py")


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
        "focal_length",
        "focus_distance",
        "fstop",
        "horizontal_aperture",
        "vertical_aperture",
        "clipping_range",
    }
    missing = expected - set(PUNYCODE_PARMS)
    assert not missing, f"PUNYCODE_PARMS missing keys: {sorted(missing)}"
    # Every value is a punycode encoding.
    for alias, enc in PUNYCODE_PARMS.items():
        assert enc.startswith("xn__"), f"{alias} -> {enc} is not punycode-encoded"


def test_encoded_helper_matches_dict():
    assert encoded("color") == PUNYCODE_PARMS["color"]
    assert encoded("not_a_real_alias") is None


def test_color_resolves_to_kya_no_drift():
    """aliases.py must resolve color to the canonical 'kya' encoding."""
    assert PUNYCODE_PARMS["color"] == _CANONICAL_COLOR
    assert PUNYCODE_PARMS["color"] != _WRONG_COLOR
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


def test_wrong_color_literal_absent_everywhere_but_usd_punycode():
    """grep-guard: the divergent 'vya' color literal must not reappear.

    usd_punycode.py is the ONE file allowed to mention it — in a VERIFY-LIVE
    comment documenting that the divergence was resolved.
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
                if _WRONG_COLOR in fh.read():
                    offenders.append(os.path.relpath(fpath, _SYNAPSE_DIR))
    assert not offenders, (
        f"Divergent color literal {_WRONG_COLOR!r} found in: {offenders}. "
        f"Use synapse.core.usd_punycode.PUNYCODE_PARMS['color'] instead."
    )
