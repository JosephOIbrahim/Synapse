"""CRUCIBLE for synapse.cognitive.tools.scout_eval — the phantom-rate/coverage eval.

The eval must be HONEST and UN-GAMEABLE:
  * ground truth is fixed/external (guarded here so the coverage gap can't be hidden),
  * the release-blocking alarm is wired to the metric, not a tunable threshold,
  * the instrument's arithmetic is verified against a CONTROLLED fixture corpus
    (deterministic — never depends on the real rag/ content),
  * true-phantom recall < 1.0 the instant a fake token leaks into the corpus.
"""

import json

import pytest

from synapse.cognitive.tools import scout, scout_eval
from synapse.cognitive.tools.scout_eval import GroundTruth, run_eval


def _wire_corpus(tmp_path, monkeypatch, entries):
    """Hand-build a controlled store and point scout at it (caches cleared)."""
    cdir = tmp_path / "corpus"; cdir.mkdir()
    (cdir / "entries.jsonl").write_text(
        "\n".join(json.dumps(e) for e in entries), encoding="utf-8")
    (tmp_path / "semantic_index").mkdir()
    monkeypatch.setattr(scout, "RAG_ROOT", tmp_path)
    monkeypatch.setattr(scout, "VEX_ROOT", tmp_path)
    monkeypatch.setattr(scout, "DRIFT_POLICY", "warn")   # stale is irrelevant to the eval
    for c in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS):
        c.clear()


# ── un-gameable ground-truth guards ──────────────────────────────────────────

def test_quarantined_phantoms_are_in_ground_truth():
    # The four canonical quarantined phantoms MUST be in the phantom bucket and
    # MUST stay flagged-false — CLAUDE.md §11.15 / harness invariant.
    for q in ("hou.pdg.workItem", "hou.secure", "hou.lopNetworks", "hou.updateGraphTick"):
        assert q in scout_eval.PHANTOM_SYMBOLS


def test_load_bearing_real_symbols_pinned():
    # You cannot quietly drop a real symbol from bucket (a) to make the
    # false-phantom rate look clean — these must remain in the ground truth.
    for r in ("hou.LopNode", "hou.SopNode", "pdg.EventType", "pxr.Usd"):
        assert r in scout_eval.REAL_SYMBOLS


def test_buckets_are_reality_disjoint():
    assert set(scout_eval.REAL_SYMBOLS).isdisjoint(set(scout_eval.PHANTOM_SYMBOLS))


# ── instrument arithmetic on a controlled corpus ─────────────────────────────

def test_clean_corpus_scores_perfect(tmp_path, monkeypatch):
    gt = GroundTruth(
        real=("hou.LopNode", "pdg.EventType"),
        phantom=("hou.lopNetworks", "hou.secure"),
        conceptual=(("render passes", "karma_aov"),),
    )
    _wire_corpus(tmp_path, monkeypatch, [
        {"id": "lop", "type": "ref", "source": "lop.md",
         "searchable_text": "use hou.LopNode and pdg.EventType in the callback"},
        {"id": "karma_aov", "type": "ref", "source": "karma_aov.md",
         "searchable_text": "karma render passes aov beauty depth"},
    ])
    card = run_eval(ground_truth=gt)
    assert card.false_phantom_rate == 0.0
    assert card.true_phantom_recall == 1.0
    assert card.release_blocking is False
    assert card.conceptual_topk_hitrate == 1.0
    assert card.real_missing == () and card.phantom_leaked == ()


def test_missing_real_is_false_phantom_and_blocks(tmp_path, monkeypatch):
    gt = GroundTruth(real=("hou.LopNode", "hou.SopNode"), phantom=("hou.secure",), conceptual=())
    _wire_corpus(tmp_path, monkeypatch, [
        {"id": "lop", "type": "ref", "source": "lop.md",
         "searchable_text": "only hou.LopNode appears here, not the other class"},
    ])
    card = run_eval(ground_truth=gt)
    assert card.false_phantom_rate == 0.5           # 1 of 2 real symbols missing
    assert "hou.SopNode" in card.real_missing
    assert card.release_blocking is True            # a real API flagged fake = Sev-1
    assert "COVERAGE-GAP HALT" in card.verdict()


def test_phantom_leak_detected(tmp_path, monkeypatch):
    # A doc that literally writes a quarantined phantom must drop true-phantom recall.
    gt = GroundTruth(real=("hou.LopNode",), phantom=("hou.lopNetworks", "hou.secure"), conceptual=())
    _wire_corpus(tmp_path, monkeypatch, [
        {"id": "bad", "type": "ref", "source": "bad.md",
         "searchable_text": "hou.LopNode and a bogus hou.lopNetworks reference slipped in"},
    ])
    card = run_eval(ground_truth=gt)
    assert card.true_phantom_recall == 0.5
    assert "hou.lopNetworks" in card.phantom_leaked
    assert "PHANTOM LEAK" in card.verdict()


def test_conceptual_miss_counted(tmp_path, monkeypatch):
    gt = GroundTruth(real=(), phantom=(),
                     conceptual=(("water splashing", "flip_simulation"),
                                 ("nonexistent topic xyzzy", "absent_doc")))
    _wire_corpus(tmp_path, monkeypatch, [
        {"id": "flip_simulation", "type": "ref", "source": "flip.md",
         "searchable_text": "flip fluid water splashing simulation solver"},
    ])
    card = run_eval(ground_truth=gt)
    assert card.conceptual_topk_hitrate == 0.5
    assert "nonexistent topic xyzzy" in card.conceptual_misses


# ── the alarm is wired to the metric, not a tunable threshold ────────────────

def test_release_blocking_tracks_metric(tmp_path, monkeypatch):
    gt = GroundTruth(real=("hou.LopNode", "hou.SopNode"), phantom=(), conceptual=())
    _wire_corpus(tmp_path, monkeypatch, [
        {"id": "lop", "type": "ref", "source": "lop.md",
         "searchable_text": "hou.LopNode hou.SopNode both present"},
    ])
    card = run_eval(ground_truth=gt)
    # release_blocking is DEFINED as false_phantom_rate > 0 — un-loosenable.
    assert card.release_blocking == (card.false_phantom_rate > 0.0)
    assert card.false_phantom_rate == 0.0 and card.release_blocking is False


# ── standing live-corpus safety pin (the phantom-catch invariant) ────────────

def test_quarantined_stay_flagged_on_live_corpus(monkeypatch):
    """The four quarantined phantoms MUST flag not-found on the REAL canonical
    corpus, through every change (harness invariant). This is release-blocking
    in the other direction: a phantom leaking into the grounding corpus is a
    Sev-1. Stable — those tokens will never be added to rag/.

    NOTE: this pins true-phantom recall, NOT the false-phantom rate. As of the
    Spike 2 run the false-phantom rate is 0.667 (a known COVERAGE GAP, surfaced
    via the capsule HALT) — that is open follow-up work, not pinned green here.
    """
    from pathlib import Path
    from synapse.cognitive.tools import scout_ingest
    try:
        info = scout_ingest.ensure_corpus()
    except Exception:
        pytest.skip("canonical rag/ corpus unavailable in this environment")
    monkeypatch.setattr(scout, "RAG_ROOT", Path(info["store_root"]))
    monkeypatch.setattr(scout, "VEX_ROOT", Path(info["store_root"]))
    for c in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS):
        c.clear()
    card = run_eval()
    assert card.true_phantom_recall == 1.0          # nothing fake leaked in
    assert card.phantom_leaked == ()


def test_scorecard_to_dict_schema(tmp_path, monkeypatch):
    gt = GroundTruth(real=("hou.LopNode",), phantom=("hou.secure",), conceptual=())
    _wire_corpus(tmp_path, monkeypatch, [
        {"id": "lop", "type": "ref", "source": "lop.md", "searchable_text": "hou.LopNode"},
    ])
    d = run_eval(ground_truth=gt).to_dict()
    assert set(d) >= {"false_phantom_rate", "true_phantom_recall",
                      "conceptual_topk_hitrate", "release_blocking",
                      "real", "phantom", "conceptual"}
    assert set(d["real"]) == {"total", "found", "missing"}
