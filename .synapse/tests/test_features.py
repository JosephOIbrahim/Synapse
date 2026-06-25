"""Proves the checklist is HARNESS-AUTHORITATIVE: a feature the worker marks passing=True
is flipped back to False unless its verify command actually exits 0. Premature victory
is impossible by construction (CRUCIBLE Commandment 7)."""
import json
import sys
from memory import FlatFileMemory

PY = sys.executable


def _contract():
    return {
        "id": "t", "goal": "g",
        "features": [
            {"description": "feat A (verify passes)",
             "verify": f'"{PY}" -c "import sys; sys.exit(0)"', "passing": False},
            {"description": "feat B (claims passing, verify FAILS)",
             "verify": f'"{PY}" -c "import sys; sys.exit(1)"', "passing": True},
        ],
    }


def test_harness_authoritative_flip(tmp_path):
    mem = FlatFileMemory(str(tmp_path), _contract())
    mem.ensure()
    npass, ntotal = mem.evaluate()
    assert ntotal == 2
    assert npass == 1                       # only the genuinely-passing feature counts
    feats = {f["description"]: f for f in json.load(open(mem.feat_file))["features"]}
    assert feats["feat A (verify passes)"]["passing"] is True
    assert feats["feat B (claims passing, verify FAILS)"]["passing"] is False
    assert feats["feat B (claims passing, verify FAILS)"].get("regressed") is True


def test_next_failing_picks_one(tmp_path):
    mem = FlatFileMemory(str(tmp_path), _contract())
    mem.ensure()
    mem.evaluate()
    assert "feat B" in mem.next_failing()
