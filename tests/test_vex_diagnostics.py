"""
Tests for VEX error diagnostics module.

Tests pattern matching, linting, function suggestions, and formatted output
without requiring Houdini.
"""
import sys
import types

# Stub hou before importing anything that might touch it
_mock_hou = types.ModuleType("hou")
sys.modules["hou"] = _mock_hou

import importlib.util
import os

# Import via spec to handle relative imports
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.join(_HERE, "..", "python")
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

from synapse.routing.vex_diagnostics import (
    diagnose_vex_error,
    diagnose_vex_symptom,
    format_diagnosis,
    lint_vex_snippet,
    VexDiagnosis,
    _suggest_vex_function,
)


# =========================================================================
# Pattern matching tests
# =========================================================================

class TestDiagnoseVexError:
    """Test error message pattern matching."""

    def test_missing_semicolon(self):
        diags = diagnose_vex_error("line 3: expected ';'")
        assert len(diags) >= 1
        assert diags[0].category == "syntax"
        assert "semicolon" in diags[0].symptom.lower() or "semicolon" in diags[0].fix.lower()
        assert diags[0].line_number == 3

    def test_missing_semicolon_no_line(self):
        diags = diagnose_vex_error("expected ';' before end of statement")
        assert len(diags) >= 1
        assert diags[0].category == "syntax"

    def test_undeclared_variable(self):
        diags = diagnose_vex_error("undeclared variable 'myVar'")
        assert len(diags) >= 1
        assert diags[0].category == "syntax"
        assert "myVar" in diags[0].symptom

    def test_unknown_function(self):
        diags = diagnose_vex_error("unknown function 'pcfin'")
        assert len(diags) >= 1
        assert diags[0].category == "function"
        assert "pcfin" in diags[0].symptom
        assert "pcfind" in diags[0].fix

    def test_unknown_function_no_suggestion(self):
        diags = diagnose_vex_error("unknown function 'zzzzxyz'")
        assert len(diags) >= 1
        assert diags[0].category == "function"

    def test_type_mismatch(self):
        diags = diagnose_vex_error("type mismatch in assignment")
        assert len(diags) >= 1
        assert diags[0].category == "type"
        assert diags[0].reference_topic == "vex_types"

    def test_cannot_convert(self):
        diags = diagnose_vex_error("cannot convert vector to int")
        assert len(diags) >= 1
        assert diags[0].category == "type"

    def test_readonly_attribute(self):
        diags = diagnose_vex_error("read-only attribute '@ptnum'")
        assert len(diags) >= 1
        assert diags[0].category == "attribute"
        assert "ptnum" in diags[0].symptom
        assert diags[0].reference_topic == "vex_attributes"

    def test_cannot_write_readonly(self):
        diags = diagnose_vex_error("cannot write to @Frame")
        assert len(diags) >= 1
        assert diags[0].category == "attribute"

    def test_input_not_connected(self):
        diags = diagnose_vex_error("input 1 is not connected")
        assert len(diags) >= 1
        assert diags[0].category == "runtime"

    def test_no_geometry_on_input(self):
        diags = diagnose_vex_error("no geometry on input 0")
        assert len(diags) >= 1
        assert diags[0].category == "runtime"

    def test_division_by_zero(self):
        diags = diagnose_vex_error("division by zero at point 42")
        assert len(diags) >= 1
        assert diags[0].category == "runtime"
        assert "max" in diags[0].example.lower() or "guard" in diags[0].fix.lower()

    def test_array_out_of_bounds(self):
        diags = diagnose_vex_error("array index out of bounds")
        assert len(diags) >= 1
        assert diags[0].category == "runtime"
        assert "len" in diags[0].example

    def test_no_match(self):
        diags = diagnose_vex_error("something completely unrecognized xyz")
        assert len(diags) == 0

    def test_unexpected_token(self):
        diags = diagnose_vex_error("line 5: unexpected token ')'")
        assert len(diags) >= 1
        assert diags[0].category == "syntax"
        assert diags[0].line_number == 5


# =========================================================================
# Lint tests
# =========================================================================

class TestLintVexSnippet:
    """Test pre-execution static analysis."""

    def test_readonly_write(self):
        issues = lint_vex_snippet("@ptnum = 5;")
        assert len(issues) >= 1
        assert issues[0].category == "attribute"
        assert "read-only" in issues[0].symptom.lower() or "ptnum" in issues[0].symptom

    def test_readonly_frame(self):
        issues = lint_vex_snippet("@Frame = 10;")
        assert len(issues) >= 1
        assert issues[0].category == "attribute"

    def test_readonly_equality_not_flagged(self):
        """Equality check (==) should not be flagged as assignment."""
        issues = lint_vex_snippet("if (@ptnum == 0) { @Cd = {1,0,0}; }")
        readonly_issues = [i for i in issues if "ptnum" in i.symptom]
        assert len(readonly_issues) == 0

    def test_clean_snippet(self):
        issues = lint_vex_snippet("float x = @P.x;\n@P.y += sin(x);")
        # Should have no high-confidence issues
        high_conf = [i for i in issues if i.confidence > 0.8]
        assert len(high_conf) == 0

    def test_comment_lines_ignored(self):
        issues = lint_vex_snippet("// @ptnum = 5;\nfloat x = 1;")
        readonly_issues = [i for i in issues if "ptnum" in i.symptom]
        assert len(readonly_issues) == 0


# =========================================================================
# Function suggestion tests
# =========================================================================

class TestSuggestVexFunction:
    """Test fuzzy function name matching."""

    def test_close_misspelling(self):
        assert _suggest_vex_function("pcfin") == "pcfind"

    def test_exact_match(self):
        # Exact match returns empty (no suggestion needed)
        assert _suggest_vex_function("pcfind") == ""

    def test_substring_match(self):
        result = _suggest_vex_function("npoint")
        assert result in ("npoints", "nearpoint", "nearpoints")

    def test_prefix_match(self):
        result = _suggest_vex_function("addp")
        assert result in ("addpoint", "addprim", "append")

    def test_common_typo_lenght(self):
        assert _suggest_vex_function("lenght") == "length"

    def test_unknown_function(self):
        result = _suggest_vex_function("zzzzxyz")
        assert result == ""

    def test_common_typo_neighbour(self):
        assert _suggest_vex_function("neighbour") == "neighbours"


# =========================================================================
# Format tests
# =========================================================================

class TestFormatDiagnosis:
    """Test coaching-tone output formatting."""

    def test_empty_list(self):
        assert format_diagnosis([]) == ""

    def test_single_diagnosis(self):
        d = VexDiagnosis(
            category="syntax",
            symptom="Missing semicolon",
            cause="VEX needs semicolons",
            fix="Add a semicolon",
            line_number=5,
        )
        text = format_diagnosis([d])
        assert "Missing semicolon" in text
        assert "line 5" in text
        assert "Add a semicolon" in text

    def test_with_example(self):
        d = VexDiagnosis(
            category="function",
            symptom="Unknown function",
            cause="Misspelled",
            fix="Use pcfind",
            example="int pts[] = pcfind(0, \"P\", @P, r, n);",
        )
        text = format_diagnosis([d])
        assert "pcfind" in text
        assert "```vex" in text

    def test_with_reference(self):
        d = VexDiagnosis(
            category="type",
            symptom="Type mismatch",
            cause="Wrong type",
            fix="Cast explicitly",
            reference_topic="vex_types",
        )
        text = format_diagnosis([d])
        assert "vex_types" in text

    def test_multiple_diagnoses(self):
        diags = [
            VexDiagnosis(
                category="syntax", symptom="Issue 1",
                cause="Cause 1", fix="Fix 1",
            ),
            VexDiagnosis(
                category="runtime", symptom="Issue 2",
                cause="Cause 2", fix="Fix 2",
            ),
        ]
        text = format_diagnosis(diags)
        assert "Issue 1" in text
        assert "Issue 2" in text


# =========================================================================
# Integration: diagnose + format pipeline
# =========================================================================

class TestDiagnosisPipeline:
    """Test end-to-end diagnosis from error to formatted output."""

    def test_full_pipeline_syntax(self):
        diags = diagnose_vex_error("line 7: expected ';'")
        text = format_diagnosis(diags)
        assert "semicolon" in text.lower()
        assert "line 7" in text

    def test_full_pipeline_function(self):
        diags = diagnose_vex_error("unknown function 'pcfin'")
        text = format_diagnosis(diags)
        assert "pcfind" in text.lower()

    def test_lint_fallback_on_no_pattern_match(self):
        """When error message doesn't match patterns, lint the snippet."""
        diags = diagnose_vex_error(
            "some weird error",
            snippet="@ptnum = 5;\nfloat x = 1;",
        )
        # Should pick up the readonly write from lint
        assert len(diags) >= 1
        assert any(d.category == "attribute" for d in diags)


# ==========================================================================
# Natural-Language Symptom Matching
# ==========================================================================


class TestDiagnoseVexSymptom:
    """Test natural-language symptom matching."""

    def test_points_not_moving(self):
        diags = diagnose_vex_symptom("my points aren't moving")
        assert len(diags) >= 1
        assert diags[0].reference_topic == "vex_attributes"
        assert "@P" in diags[0].example

    def test_nothing_happening(self):
        diags = diagnose_vex_symptom("nothing is happening in the wrangle")
        assert len(diags) >= 1
        assert "run-over" in diags[0].cause.lower() or "connected" in diags[0].cause.lower()

    def test_colors_wrong(self):
        diags = diagnose_vex_symptom("colors look weird on my geometry")
        assert len(diags) >= 1
        assert "Cd" in diags[0].cause or "color" in diags[0].cause.lower()

    def test_orientation_issues(self):
        diags = diagnose_vex_symptom("orientations are wrong on copy to points")
        assert len(diags) >= 1
        assert "orient" in diags[0].cause.lower()

    def test_scale_issues(self):
        diags = diagnose_vex_symptom("pscale is not working")
        assert len(diags) >= 1
        assert "pscale" in diags[0].cause.lower() or "scale" in diags[0].cause.lower()

    def test_noise_blocky(self):
        diags = diagnose_vex_symptom("noise looks blocky on my displacement")
        assert len(diags) >= 1
        assert "frequency" in diags[0].cause.lower() or "octave" in diags[0].cause.lower()

    def test_wrangle_slow(self):
        diags = diagnose_vex_symptom("my wrangle is slow")
        assert len(diags) >= 1
        assert diags[0].confidence >= 0.7
        assert "pcfind" in diags[0].example.lower()

    def test_pcfind_empty(self):
        diags = diagnose_vex_symptom("pcfind returns nothing")
        assert len(diags) >= 1
        assert "radius" in diags[0].cause.lower()

    def test_attribute_missing(self):
        diags = diagnose_vex_symptom("attribute is not showing up")
        assert len(diags) >= 1
        assert "type prefix" in diags[0].fix.lower() or "spreadsheet" in diags[0].fix.lower()

    def test_solver_exploding(self):
        diags = diagnose_vex_symptom("my solver is exploding")
        assert len(diags) >= 1
        assert "TimeInc" in diags[0].fix or "damping" in diags[0].fix.lower()

    def test_no_match_unrelated(self):
        """Non-VEX queries should return empty."""
        diags = diagnose_vex_symptom("how do I create a dome light")
        assert len(diags) == 0

    def test_sorted_by_confidence(self):
        diags = diagnose_vex_symptom("my solver is slow and exploding")
        if len(diags) >= 2:
            assert diags[0].confidence >= diags[1].confidence
