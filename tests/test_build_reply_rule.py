"""Pin: the build-reply rule keeps honest disclosure (DIAG round 2, Thu 10/1)."""
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "python" / "synapse" / "panel" / "system_prompt.py"


def test_build_reply_rule_requires_disclosure_of_undone_or_unverified_work():
    text = SRC.read_text(encoding="utf-8")
    assert "not done or not verified" in text
    assert "if nothing was built, say that first" in text
    assert "never drop it" in text
