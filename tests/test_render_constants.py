"""Tests for render validation constants extracted to shared/constants.py.

Verifies that RENDER_VALIDATE_CHECKS and RENDER_VALIDATE_DEFAULTS are
properly defined with correct types and reasonable values.
"""

import sys

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from shared.constants import RENDER_VALIDATE_CHECKS, RENDER_VALIDATE_DEFAULTS


class TestRenderValidateChecks:
    """RENDER_VALIDATE_CHECKS tuple."""

    def test_is_tuple(self):
        assert isinstance(RENDER_VALIDATE_CHECKS, tuple)

    def test_non_empty(self):
        assert len(RENDER_VALIDATE_CHECKS) > 0

    def test_all_strings(self):
        for check in RENDER_VALIDATE_CHECKS:
            assert isinstance(check, str), f"{check!r} is not a string"

    def test_expected_checks_present(self):
        expected = {"file_integrity", "black_frame", "nan_check",
                    "clipping", "underexposure", "saturation"}
        assert set(RENDER_VALIDATE_CHECKS) == expected

    def test_no_duplicates(self):
        assert len(RENDER_VALIDATE_CHECKS) == len(set(RENDER_VALIDATE_CHECKS))


class TestRenderValidateDefaults:
    """RENDER_VALIDATE_DEFAULTS dict."""

    def test_is_dict(self):
        assert isinstance(RENDER_VALIDATE_DEFAULTS, dict)

    def test_non_empty(self):
        assert len(RENDER_VALIDATE_DEFAULTS) > 0

    def test_all_values_numeric(self):
        for key, value in RENDER_VALIDATE_DEFAULTS.items():
            assert isinstance(value, (int, float)), (
                f"{key}: {value!r} is not numeric"
            )

    def test_expected_keys_present(self):
        expected_keys = {
            "black_frame_mean", "clipping_pct",
            "underexposure_mean", "saturation_pct",
            "saturation_multiplier",
        }
        assert set(RENDER_VALIDATE_DEFAULTS.keys()) == expected_keys

    def test_all_values_positive(self):
        for key, value in RENDER_VALIDATE_DEFAULTS.items():
            assert value > 0, f"{key} should be positive, got {value}"

    def test_percentage_thresholds_in_range(self):
        """Percentage-like thresholds should be between 0 and 1."""
        pct_keys = ["clipping_pct", "saturation_pct"]
        for key in pct_keys:
            assert 0 < RENDER_VALIDATE_DEFAULTS[key] <= 1.0, (
                f"{key}={RENDER_VALIDATE_DEFAULTS[key]} out of expected range"
            )

    def test_mean_thresholds_reasonable(self):
        """Mean thresholds should be small positive numbers."""
        mean_keys = ["black_frame_mean", "underexposure_mean"]
        for key in mean_keys:
            val = RENDER_VALIDATE_DEFAULTS[key]
            assert 0 < val < 1.0, f"{key}={val} out of expected range"

    def test_specific_values(self):
        """Spot-check the exact values match the specification."""
        assert RENDER_VALIDATE_DEFAULTS["black_frame_mean"] == 0.001
        assert RENDER_VALIDATE_DEFAULTS["clipping_pct"] == 0.5
        assert RENDER_VALIDATE_DEFAULTS["underexposure_mean"] == 0.05
        assert RENDER_VALIDATE_DEFAULTS["saturation_pct"] == 0.1
        assert RENDER_VALIDATE_DEFAULTS["saturation_multiplier"] == 10.0


class TestConstantsImportable:
    """Verify constants are in __all__ and importable."""

    def test_in_all(self):
        from shared import constants
        assert "RENDER_VALIDATE_CHECKS" in constants.__all__
        assert "RENDER_VALIDATE_DEFAULTS" in constants.__all__
