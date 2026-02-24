"""
Determinism Edge Case Tests

Tests for IEEE 754 special values (NaN, Inf, -Inf, -0.0) in round_float().
"""

import math
import os
import sys

# Add package to path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.core.determinism import (
    DeterministicConfig,
    get_config,
    set_config,
    round_float,
)


class TestRoundFloatEdgeCases:
    """Tests for IEEE 754 special value handling in round_float()."""

    def test_nan_returns_zero(self):
        """NaN is replaced with 0.0 as a safe sentinel."""
        result = round_float(float('nan'))
        assert result == 0.0
        assert not math.isnan(result)

    def test_positive_inf_passthrough(self):
        """Positive infinity passes through unchanged."""
        result = round_float(float('inf'))
        assert result == float('inf')
        assert math.isinf(result) and result > 0

    def test_negative_inf_passthrough(self):
        """Negative infinity passes through unchanged."""
        result = round_float(float('-inf'))
        assert result == float('-inf')
        assert math.isinf(result) and result < 0

    def test_negative_zero(self):
        """Negative zero rounds to positive zero."""
        result = round_float(-0.0)
        assert result == 0.0

    def test_normal_float_unchanged(self):
        """Normal floats round correctly."""
        result = round_float(3.14159, 2)
        assert result == 3.14

    def test_strict_mode_nan(self):
        """Under strict_mode=True, NaN still returns 0.0 (guard fires before Decimal)."""
        original = get_config()
        try:
            strict_cfg = DeterministicConfig(strict_mode=True)
            set_config(strict_cfg)
            result = round_float(float('nan'))
            assert result == 0.0
            assert not math.isnan(result)
        finally:
            set_config(original)
