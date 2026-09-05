"""P10 -- cited-path liveness for the RSI registry (harness/rsi/verify.py).

The registry is the harness's single source of truth about which
self-improvement loops exist and what evidence backs each rung. Evidence is
cited as repo paths with line numbers. A path that no longer exists at HEAD --
or a line number past the end of the file -- is a citation to nothing, and a
registry that carries one is stale by definition (CTO B7: A3 cited
python/synapse/memory/evolution.py:217 a month after the module was renamed
to .deprecated and its call sites deleted).

Two layers:
  * the REAL registry must cite only live paths (this is the test that goes
    red when the tree moves under the registry);
  * synthetic registries prove P10 can actually fail -- a dead path, a line
    past EOF, and a commit pin that does not hold each turn it red.

Run: python -m pytest tests/rsi/test_verify_paths.py -q
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
VERIFY = REPO / "harness" / "rsi" / "verify.py"


@pytest.fixture(scope="module")
def verify():
    spec = importlib.util.spec_from_file_location("rsi_verify", VERIFY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _registry_with(evidence, surfaces=()):
    return {"loops": [{"id": "X", "rungs_proven": ["L0"],
                       "surfaces": list(surfaces), "evidence": evidence}]}


# ── the real registry ───────────────────────────────────────────────────────

def test_p10_is_on_the_bar(verify):
    assert "P10" in [pid for pid, _, _ in verify.PREDICATES]


def test_real_registry_cites_only_live_paths(verify):
    data, err = verify.load_registry()
    assert data is not None, err
    status, reason = verify.p10(data)
    assert status == verify.PASS, reason


def test_real_registry_has_citations_to_check(verify):
    """Guards the guard: P10 PASS over an empty citation set would be vacuous."""
    data, _ = verify.load_registry()
    cited = list(verify.cited_paths(data))
    assert len(cited) > 20, f"only {len(cited)} citations parsed -- extractor regressed?"


# ── P10 can fail ────────────────────────────────────────────────────────────

def test_dead_path_fails(verify):
    status, reason = verify.p10(_registry_with(
        {"L0": ["harness/rsi/this_module_was_deleted.py:12"]}))
    assert status == verify.FAIL
    assert "this_module_was_deleted.py" in reason and "absent at HEAD" in reason


def test_dead_surface_fails(verify):
    status, reason = verify.p10(_registry_with(
        {"L0": ["harness/rsi/verify.py:1"]}, surfaces=["python/synapse/memory/evolution.py"]))
    assert status == verify.FAIL
    assert "X:surfaces python/synapse/memory/evolution.py" in reason


def test_line_past_eof_fails(verify):
    n_lines = VERIFY.read_text(encoding="utf-8").count("\n") + 1
    status, reason = verify.p10(_registry_with(
        {"L0": [f"harness/rsi/verify.py:{n_lines + 500}"]}))
    assert status == verify.FAIL
    assert "cites line" in reason


def test_live_path_and_in_range_lines_pass(verify):
    status, reason = verify.p10(_registry_with(
        {"L0": ["harness/rsi/verify.py:1-5 -- the docstring",
                "harness/rsi/verify.py:10, :12, :14 and tests/rsi/test_verify_paths.py::test_x"]}))
    assert status == verify.PASS, reason
    assert "3 cited path(s)" in reason


def test_shorthand_citation_is_not_a_repo_path(verify):
    """'router.py:293' names no repo path; it is neither checked nor a failure."""
    status, reason = verify.p10(_registry_with({"L1": ["router.py:293, :462 -- eight call sites"]}))
    assert status == verify.PASS
    assert "all 0 cited" in reason


# ── commit pins ─────────────────────────────────────────────────────────────

def test_pinned_citation_is_checked_at_its_commit_not_head(verify):
    # python/synapse/agent/learning.py was deleted 2026-08-01 (loop A2 retirement);
    # it existed at 38aba50. Unpinned it is dead; pinned it is live.
    dead, _ = verify.p10(_registry_with({"L0": ["python/synapse/agent/learning.py:109"]}))
    assert dead == verify.FAIL
    status, reason = verify.p10(_registry_with(
        {"L0": ["python/synapse/agent/learning.py:109-116 (at 38aba50)"]}))
    if status == verify.PENDING:
        pytest.skip(f"git unavailable in this environment: {reason}")
    assert status == verify.PASS, reason
    assert "1 pinned" in reason


def test_pin_to_a_commit_where_the_path_is_absent_fails(verify):
    status, reason = verify.p10(_registry_with(
        {"L0": ["harness/rsi/log_receipt.py:1 (at 38aba50)"]}))
    if status == verify.PENDING:
        pytest.skip(f"git unavailable in this environment: {reason}")
    assert status == verify.FAIL
    assert "absent at 38aba50" in reason
