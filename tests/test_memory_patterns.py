"""Tests for memory pattern detection."""

import sys
import os

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.memory.patterns import detect_patterns


class TestPatternDetection:
    """Pattern detection on raw markdown content."""

    def test_repeated_blocker(self):
        """Same blocker mentioned multiple times triggers pattern."""
        content = (
            "## Blockers\n\n"
            "### Render timeout\nKarma keeps timing out on frame 42.\n\n"
            "### Render timeout again\nKarma timing out, tried increasing timeout.\n\n"
            "### Render timeout third time\nStill timing out on frame 42.\n"
        )
        patterns = detect_patterns(content)
        assert any(p["type"] == "repeated_blocker" for p in patterns)
        blocker = next(p for p in patterns if p["type"] == "repeated_blocker")
        assert blocker["count"] >= 2

    def test_oscillating_parameter(self):
        """Parameter going back and forth triggers pattern."""
        content = (
            "## Parameters\n\n"
            "### Set exposure to 5.0\nBefore: 3.0, After: 5.0. Too bright.\n\n"
            "### Set exposure to 3.0\nBefore: 5.0, After: 3.0. Too dark.\n\n"
            "### Set exposure to 5.0\nBefore: 3.0, After: 5.0. Still too bright.\n"
        )
        patterns = detect_patterns(content)
        assert any(p["type"] == "oscillating_parameter" for p in patterns)

    def test_no_patterns_for_clean_memory(self):
        """Clean memory with no repetition returns empty list."""
        content = (
            "## Decisions\n\n"
            "### Chose Karma XPU\nFast GPU rendering.\n\n"
            "## Notes\n\n"
            "### Scene looks good\nReady for review.\n"
        )
        patterns = detect_patterns(content)
        assert patterns == []

    def test_returns_sorted_by_severity(self):
        """Multiple patterns are sorted by severity (highest first)."""
        content = (
            "## Blockers\n\n"
            "### Crash on export\nCrash.\n\n"
            "### Crash on export\nCrash again.\n\n"
            "### Crash on export\nThird crash.\n\n"
            "## Parameters\n\n"
            "### Set roughness to 0.5\nBefore: 0.2, After: 0.5.\n\n"
            "### Set roughness to 0.2\nBefore: 0.5, After: 0.2.\n\n"
            "### Set roughness to 0.5\nBefore: 0.2, After: 0.5.\n"
        )
        patterns = detect_patterns(content)
        assert len(patterns) >= 2
        # Repeated blocker (severity=3) should rank above oscillating (severity=1)
        assert patterns[0]["severity"] >= patterns[-1]["severity"]

    def test_empty_content(self):
        """Empty content returns no patterns."""
        assert detect_patterns("") == []

    def test_single_blocker_no_pattern(self):
        """A single blocker is not a pattern."""
        content = (
            "## Blockers\n\n"
            "### Render crash\nFixed by updating driver.\n"
        )
        assert detect_patterns(content) == []

    def test_two_changes_no_oscillation(self):
        """Two parameter changes don't constitute oscillation."""
        content = (
            "## Parameters\n\n"
            "### Set exposure\nBefore: 3.0, After: 5.0.\n\n"
            "### Set exposure\nBefore: 5.0, After: 3.0.\n"
        )
        # Need 3+ changes for oscillation
        patterns = detect_patterns(content)
        assert not any(p["type"] == "oscillating_parameter" for p in patterns)

    def test_oscillation_evidence_contains_transitions(self):
        """Oscillation evidence shows the A->B->A transitions."""
        content = (
            "## Parameters\n\n"
            "### Set samples\nBefore: 64, After: 256.\n\n"
            "### Set samples\nBefore: 256, After: 64.\n\n"
            "### Set samples\nBefore: 64, After: 256.\n"
        )
        patterns = detect_patterns(content)
        osc = next(p for p in patterns if p["type"] == "oscillating_parameter")
        assert len(osc["evidence"]) == 3
        assert "64->256" in osc["evidence"][0]
