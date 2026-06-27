"""Pin the single-source Solaris production-rules catalog.

The catalog (``synapse.core.solaris_guardrails``) is the durable, importable
form of the common-error rules that previously lived only as prose in
``rag/skills/houdini21-reference/common_errors.md`` and as scattered inline
checks. These tests pin that the named rules are present, that encoding-
dependent rules defer to the single-source punycode map (no re-hardcoded
``xn__`` literals), and that the pure advisory checks behave.
"""

import os
import sys

# Add package to path (same idiom as the rest of the suite)
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.core.solaris_guardrails import (
    PRODUCTION_RULES,
    RULES_BY_ID,
    Advisory,
    ProductionRule,
    LIGHTING_LAW_INTENSITY,
    check_camera_target,
    check_light_intensity,
    check_tuple_parm,
    get_rule,
    rule_encoding,
)
from synapse.core.usd_punycode import PUNYCODE_PARMS, encoded


# --- Catalog shape ---------------------------------------------------------
_EXPECTED_RULE_IDS = {
    "materiallibrary_cook_before_child",
    "karma_camera_prim_path",
    "vector_color_parmtuple",
    "lighting_law_intensity",
    "usdrender_output_agreement",
    "karma_xpu_file_flush_delay",
    "lop_sphere_radius_encoding",
}


def test_named_rules_present():
    """Every rule named in the task brief is in the catalog."""
    missing = _EXPECTED_RULE_IDS - set(RULES_BY_ID)
    assert not missing, f"catalog missing rules: {sorted(missing)}"


def test_rules_well_formed():
    """Each rule has a non-empty id/rule/rationale/fact and cites the source."""
    assert PRODUCTION_RULES, "catalog is empty"
    for r in PRODUCTION_RULES:
        assert isinstance(r, ProductionRule)
        assert r.id and r.rule and r.rationale and r.fact
        assert "common_errors.md" in r.source


def test_rule_ids_unique():
    assert len(RULES_BY_ID) == len(PRODUCTION_RULES)


def test_get_rule():
    assert get_rule("lighting_law_intensity") is RULES_BY_ID["lighting_law_intensity"]
    assert get_rule("not_a_rule") is None


# --- Encoding rows defer to the single source ------------------------------
def test_no_hardcoded_xn_literals_in_module():
    """The catalog must not paste any ``xn__`` literal — encodings come from
    usd_punycode only."""
    module_path = os.path.join(
        python_dir, "synapse", "core", "solaris_guardrails.py"
    )
    with open(module_path, "r", encoding="utf-8") as fh:
        text = fh.read()
    assert "xn__" not in text, "solaris_guardrails.py hardcodes an xn__ encoding"


def test_encoding_dependent_rules_resolve_via_punycode():
    """Rules with an alias present in PUNYCODE_PARMS resolve to its live literal."""
    color_rule = get_rule("vector_color_parmtuple")
    assert color_rule.encoding_alias == "color"
    assert rule_encoding(color_rule) == PUNYCODE_PARMS["color"]
    assert rule_encoding(color_rule) == encoded("color")

    intensity_rule = get_rule("lighting_law_intensity")
    assert intensity_rule.encoding_alias == "intensity"
    assert rule_encoding(intensity_rule) == PUNYCODE_PARMS["intensity"]


def test_rule_encoding_none_for_non_encoding_rule():
    """A rule with no encoding_alias resolves to None (not an error)."""
    assert rule_encoding(get_rule("materiallibrary_cook_before_child")) is None


def test_radius_encoding_defers_to_single_source():
    """The sphere-radius rule must mirror whatever usd_punycode says for 'radius'
    — never carry its own copy. On 21.0.671 that value is still an UNVERIFIED
    placeholder, which is exactly why the catalog must not hardcode it."""
    radius_rule = get_rule("lop_sphere_radius_encoding")
    assert radius_rule.encoding_alias == "radius"
    # Deference invariant: catalog == single source, verified or not.
    assert rule_encoding(radius_rule) == PUNYCODE_PARMS.get("radius")
    assert rule_encoding(radius_rule) == encoded("radius")


# --- Advisory: Lighting Law intensity --------------------------------------
def test_intensity_one_is_ok():
    result = check_light_intensity(1.0)
    assert isinstance(result, Advisory)
    assert result.ok
    assert result.rule_id == "lighting_law_intensity"


def test_intensity_five_flags():
    result = check_light_intensity(5.0)
    assert not result.ok
    assert "exposure" in result.message


def test_intensity_below_one_ok():
    assert check_light_intensity(0.5).ok


def test_lighting_law_constant():
    assert LIGHTING_LAW_INTENSITY == 1.0


# --- Advisory: camera target prim-path -------------------------------------
def test_camera_prim_path_ok():
    result = check_camera_target("/cameras/cam")
    assert isinstance(result, Advisory)
    assert result.ok
    assert result.rule_id == "karma_camera_prim_path"


def test_camera_node_path_flags():
    result = check_camera_target("/obj/cam1")
    assert not result.ok
    assert "node path" in result.message


def test_camera_stage_node_path_flags():
    assert not check_camera_target("/stage/cam1").ok


def test_camera_empty_flags():
    assert not check_camera_target("").ok


def test_camera_relative_path_flags():
    assert not check_camera_target("cameras/cam").ok


# --- Advisory: tuple parm --------------------------------------------------
def test_color_is_tuple_parm():
    result = check_tuple_parm("color")
    assert not result.ok  # affirmative "use parmTuple" instruction
    assert "parmTuple" in result.message
    assert result.rule_id == "vector_color_parmtuple"


def test_scalar_is_not_tuple_parm():
    assert check_tuple_parm("intensity").ok
