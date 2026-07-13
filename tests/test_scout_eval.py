"""CRUCIBLE for synapse.cognitive.tools.scout_eval — the phantom-rate/coverage eval.

The eval must be HONEST and UN-GAMEABLE:
  * ground truth is fixed/external (guarded here so the coverage gap can't be hidden),
  * the release-blocking alarm is wired to the metric, not a tunable threshold,
  * the instrument's arithmetic is verified against a CONTROLLED fixture corpus
    (deterministic — never depends on the real rag/ content),
  * true-phantom recall < 1.0 the instant a fake token leaks into the corpus.
"""

import hashlib
import json

import pytest

from conftest import HOUDINI_BUILD
from synapse.cognitive.tools import scout, scout_eval
from synapse.cognitive.tools.scout_eval import GroundTruth, run_eval


def _wire_corpus(tmp_path, monkeypatch, entries, table_symbols=None):
    """Hand-build a controlled store and point scout at it (caches cleared).

    Membership is table-based (Spike 2.5). When ``table_symbols`` is given, a
    controlled symbol table is written to the store and the package table is
    neutralized — so the test drives membership deterministically. When None,
    the committed package table is used (correct real/phantom answers)."""
    cdir = tmp_path / "corpus"; cdir.mkdir()
    (cdir / "entries.jsonl").write_text(
        "\n".join(json.dumps(e) for e in entries), encoding="utf-8")
    (tmp_path / "semantic_index").mkdir()
    monkeypatch.setattr(scout, "RAG_ROOT", tmp_path)
    monkeypatch.setattr(scout, "VEX_ROOT", tmp_path)
    monkeypatch.setattr(scout, "DRIFT_POLICY", "warn")   # corpus-stale is irrelevant to the eval
    if table_symbols is not None:
        syms = sorted(table_symbols)
        digest = hashlib.blake2b("\n".join(syms).encode("utf-8"), digest_size=16).hexdigest()
        (tmp_path / scout.SYMBOL_TABLE_NAME).write_text(json.dumps({
            "schema": "scout_symbol_table/v1", "houdini_version": HOUDINI_BUILD,
            "blake2b": digest, "symbol_count": len(syms), "symbols": syms,
        }), encoding="utf-8")
        monkeypatch.setattr(scout, "_PKG_SYMBOL_TABLE", tmp_path / "no_pkg_table.json")
    for c in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS, scout._TABLE_CACHE):
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
    ], table_symbols={"hou.LopNode", "pdg.EventType"})   # reals present, phantoms absent
    card = run_eval(ground_truth=gt)
    assert card.false_phantom_rate == 0.0
    assert card.true_phantom_recall == 1.0
    assert card.release_blocking is False
    assert card.conceptual_topk_hitrate == 1.0
    assert card.real_missing == () and card.phantom_leaked == ()


def test_missing_real_is_false_phantom_and_blocks(tmp_path, monkeypatch):
    gt = GroundTruth(real=("hou.LopNode", "hou.SopNode"), phantom=("hou.secure",), conceptual=())
    # Table omits hou.SopNode → a real API the table fails to resolve = a coverage gap.
    _wire_corpus(tmp_path, monkeypatch, [
        {"id": "lop", "type": "ref", "source": "lop.md", "searchable_text": "notes"},
    ], table_symbols={"hou.LopNode"})
    card = run_eval(ground_truth=gt)
    assert card.false_phantom_rate == 0.5           # 1 of 2 real symbols unresolved
    assert "hou.SopNode" in card.real_missing
    assert card.release_blocking is True            # a real API flagged fake = Sev-1
    assert "COVERAGE-GAP HALT" in card.verdict()


def test_phantom_leak_detected(tmp_path, monkeypatch):
    # A fake token wrongly present IN THE TABLE must drop true-phantom recall
    # (membership is the table's call now — a corpus mention alone can't leak it).
    gt = GroundTruth(real=("hou.LopNode",), phantom=("hou.lopNetworks", "hou.secure"), conceptual=())
    _wire_corpus(tmp_path, monkeypatch, [
        {"id": "d", "type": "ref", "source": "d.md", "searchable_text": "notes"},
    ], table_symbols={"hou.LopNode", "hou.lopNetworks"})   # phantom wrongly in the table
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
        {"id": "d", "type": "ref", "source": "d.md", "searchable_text": "notes"},
    ], table_symbols={"hou.LopNode", "hou.SopNode"})
    card = run_eval(ground_truth=gt)
    # release_blocking is DEFINED as false_phantom_rate > 0 — un-loosenable.
    assert card.release_blocking == (card.false_phantom_rate > 0.0)
    assert card.false_phantom_rate == 0.0 and card.release_blocking is False


# ── GATE 6: the standing live verdict pin (Spike 2.5 closed the Sev-1) ───────

def test_gate6_false_phantom_zero_on_live_runtime_table(monkeypatch):
    """GATE 6 — the verdict. Against the committed introspected H21.0.671 table
    (the membership authority), EVERY eval bucket-(a) real API resolves and ALL
    six phantoms (incl. the four quarantined) flag absent.

    This is the HARD GREEN PIN that replaces the Spike-2 known coverage gap
    (false_phantom_rate was 0.667 under corpus-substring membership). It is
    release-blocking in BOTH directions now:
      * false_phantom_rate must stay 0   (no real API told it's fake), and
      * true_phantom_recall must stay 1  (no phantom resurrected).
    conceptual_topk_hitrate is a sanity check — the membership fix doesn't touch
    retrieval, so conceptual recall must not REGRESS below its lexical 0.333
    baseline. (K.1 added the offline semantic index, so when it's present hybrid
    retrieval now EXCEEDS that baseline; the invariant is "no regression", not a
    frozen number — hence >= rather than ==.)
    """
    from pathlib import Path
    from synapse.cognitive.tools import scout_ingest
    try:
        info = scout_ingest.ensure_corpus()
    except Exception:
        pytest.skip("canonical rag/ corpus unavailable in this environment")
    if not scout._PKG_SYMBOL_TABLE.is_file():
        pytest.skip("committed symbol table absent in this environment")
    monkeypatch.setattr(scout, "RAG_ROOT", Path(info["store_root"]))
    monkeypatch.setattr(scout, "VEX_ROOT", Path(info["store_root"]))
    for c in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS, scout._TABLE_CACHE):
        c.clear()
    card = run_eval()
    assert card.false_phantom_rate == 0.0, f"real APIs unresolved: {card.real_missing}"
    assert card.true_phantom_recall == 1.0          # nothing fake resurrected
    assert card.phantom_leaked == ()
    assert card.release_blocking is False
    # retrieval must not regress; K.1's semantic index lifts conceptual recall
    # above the old lexical-only 0.333 baseline when the index is present.
    assert card.conceptual_topk_hitrate >= round(2 / 6, 4)


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
