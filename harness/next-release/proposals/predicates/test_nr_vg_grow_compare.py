"""Closure predicate for NR-VG-GROW-COMPARE (PROPOSED amendment; not in graph.json).

Flips green only when harness/vision/grow_compare/creative_sidecar_contract.json is
committed and records: a schema version for a creative sidecar kept separate from the
perception envelope; the envelope fields unchanged as
{ch, v, tier, claim, checks, verdict, proof, at}; hard validity checks before any
ranking; the test that refuses an empty mandatory-check list; that a style score cannot
override a failed protection or provenance check; Joe's review against the
reference-only and guided baselines; and retina/creative_sidecar.py and
tests/test_creative_sidecar.py are committed.

Red today: the contract is not committed (marker below).

Reads committed files only. It never imports retina, renders, touches a GPU,
launches Houdini or uses the network.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    """Find the repository root from the working directory, never from this file's
    location, so the predicate keeps working wherever it is moved (review G1)."""
    here = Path.cwd().resolve()
    for p in (here, *here.parents):
        if (p / ".git").exists() and (p / "harness" / "next-release" / "graph.json").is_file():
            return p
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=60)
    if r.returncode == 0 and r.stdout.strip():
        return Path(r.stdout.strip()).resolve()
    raise AssertionError("repository root not found: run this predicate from inside the SYNAPSE checkout")


ROOT = _repo_root()
MARKER = ("NR-VG-GROW-COMPARE RED: no committed creative-sidecar contract "
          "harness/vision/grow_compare/creative_sidecar_contract.json")
CONTRACT = "harness/vision/grow_compare/creative_sidecar_contract.json"
ENVELOPE = ["ch", "v", "tier", "claim", "checks", "verdict", "proof", "at"]


def _committed(rel: str) -> bool:
    if not (ROOT / rel).is_file():
        return False
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", "--", rel],
                       capture_output=True, text=True, timeout=60)
    return r.returncode == 0


def _contract() -> dict:
    if not _committed(CONTRACT):
        raise AssertionError(MARKER)
    return json.loads((ROOT / CONTRACT).read_text(encoding="utf-8"))


def test_contract_is_committed():
    c = _contract()
    assert isinstance(c, dict) and c, "the committed contract is empty"


def test_sidecar_is_separate_and_envelope_unchanged():
    c = _contract()
    assert c.get("schema_version") and c.get("separate_from_envelope") is True, "creative sidecar not separate and versioned"
    assert c.get("envelope_fields") == ENVELOPE, "envelope fields changed"


def test_truth_before_taste():
    c = _contract()
    assert c.get("hard_checks_before_ranking") is True, "ranking must follow hard validity checks"
    assert c.get("empty_mandatory_checks_refused_test"), "no test refusing an empty mandatory-check list"
    assert c.get("style_cannot_override_failed_check") is True, "a style score may override a failed check"


def test_joe_review_and_files():
    c = _contract()
    rv = c.get("joe_review", {})
    assert rv.get("by") == "Joe" and rv.get("date"), "no review by Joe"
    assert {"reference_only", "guided"} <= set(rv.get("baselines", [])), "review lacks the two baselines"
    for rel in ("retina/creative_sidecar.py", "tests/test_creative_sidecar.py"):
        assert _committed(rel), f"{rel} is not committed"
