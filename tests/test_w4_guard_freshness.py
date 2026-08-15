"""W4-GUARD target 1 — the served-corpus build-stamp freshness gate.

Acceptance predicate #1: "stale-stamp fixture fails the freshness gate loudly;
matching stamp passes" (evidence: test). Plus the crucible criterion the gate
exists to satisfy: it must FAIL the release, NEVER warn — so every unverifiable
path returns ok:False, never ok:None.

The gate under test is harness/verify/checks.py::check_corpus_stamp_fresh, driven
against synthetic fixture worktrees (no live corpus, no live host required).
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


checks = _load("w4guard_checks_fresh", "harness/verify/checks.py")


# ---- fixture builders: assemble a minimal worktree in tmp_path ----
def _mk_corpus(wt, build, entries=None, omit_build=False):
    p = wt / "rag" / "corpus"
    p.mkdir(parents=True, exist_ok=True)
    doc = {"schema": "h22_node_corpus/v1",
           "entries": entries if entries is not None
           else [{"type": "chromakey", "context": "cop"}]}
    if not omit_build:
        doc["build"] = build
    (p / "h22_nodes.json").write_text(json.dumps(doc), encoding="utf-8")


def _mk_symtable(wt, build, major="22"):
    p = wt / "python" / "synapse" / "cognitive" / "tools" / "data"
    p.mkdir(parents=True, exist_ok=True)
    (p / ("h%s_symbol_table.json" % major)).write_text(
        json.dumps({"schema": "symbol_table/v1", "houdini_version": build}),
        encoding="utf-8")


def _mk_drop(wt, build):
    p = wt / "harness" / "state"
    p.mkdir(parents=True, exist_ok=True)
    (p / "drop.json").write_text(json.dumps({"houdini_build": build}), encoding="utf-8")


def _mk_ledger_module(wt):
    # the gate imports harness/ingest_ledger.py from the worktree for resolve_ratified_build
    dst = wt / "harness" / "ingest_ledger.py"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes((ROOT / "harness" / "ingest_ledger.py").read_bytes())


def _ctx(wt):
    return {"wt": str(wt), "hython": "", "mode": "A"}


# ---- the core acceptance: matching passes, stale fails loud ----
def test_matching_stamp_passes(tmp_path):
    _mk_ledger_module(tmp_path)
    _mk_symtable(tmp_path, "22.0.400")
    _mk_corpus(tmp_path, "22.0.400")
    r = checks.check_corpus_stamp_fresh(_ctx(tmp_path))
    assert r["ok"] is True, r["detail"]
    assert "22.0.400" in r["detail"]


def test_stale_stamp_fails_loud(tmp_path):
    _mk_ledger_module(tmp_path)
    _mk_symtable(tmp_path, "22.0.400")     # ratified .400
    _mk_corpus(tmp_path, "22.0.368")       # served .368 — STALE
    r = checks.check_corpus_stamp_fresh(_ctx(tmp_path))
    assert r["ok"] is False                # FAIL, and specifically not None (never a warn)
    d = r["detail"]
    assert "STALE" in d
    assert "22.0.368" in d and "22.0.400" in d   # both builds named — loud, actionable


def test_drop_json_is_the_ratified_authority(tmp_path):
    # drop.json present (the human-ratified pin) and no symbol table -> it wins
    _mk_ledger_module(tmp_path)
    _mk_drop(tmp_path, "22.0.400")
    _mk_corpus(tmp_path, "22.0.400")
    r = checks.check_corpus_stamp_fresh(_ctx(tmp_path))
    assert r["ok"] is True, r["detail"]
    assert "drop.json" in r["detail"]


def test_no_build_stamp_fails(tmp_path):
    # an unstamped corpus is the exact silent-staleness defect the gate kills
    _mk_ledger_module(tmp_path)
    _mk_symtable(tmp_path, "22.0.400")
    _mk_corpus(tmp_path, "22.0.400", omit_build=True)
    r = checks.check_corpus_stamp_fresh(_ctx(tmp_path))
    assert r["ok"] is False
    assert "NO `build`" in r["detail"] or "no `build`" in r["detail"].lower()


def test_absent_corpus_fails(tmp_path):
    _mk_ledger_module(tmp_path)
    _mk_symtable(tmp_path, "22.0.400")
    r = checks.check_corpus_stamp_fresh(_ctx(tmp_path))   # no corpus written
    assert r["ok"] is False
    assert "absent" in r["detail"]


def test_no_ratified_authority_blocks_not_warns(tmp_path):
    # corpus present + stamped, but NO drop.json and NO symbol table -> cannot resolve
    # the ratified build. A release gate must BLOCK (ok:False), never shrug (ok:None).
    _mk_ledger_module(tmp_path)
    _mk_corpus(tmp_path, "22.0.400")
    r = checks.check_corpus_stamp_fresh(_ctx(tmp_path))
    assert r["ok"] is False
    assert r["ok"] is not None
    assert "verify freshness" in r["detail"] or "ratified-build authority" in r["detail"]


def test_authorities_disagree_fails(tmp_path):
    # drop.json and the symbol table disagree on the build -> ratified build is
    # ambiguous -> FAIL loud (do not ship on an ambiguous ratified build)
    _mk_ledger_module(tmp_path)
    _mk_drop(tmp_path, "22.0.400")
    _mk_symtable(tmp_path, "22.0.399")
    _mk_corpus(tmp_path, "22.0.400")
    r = checks.check_corpus_stamp_fresh(_ctx(tmp_path))
    assert r["ok"] is False
    assert "disagree" in r["detail"]


def test_downgrade_stamped_corpus_cannot_self_select_an_older_authority(tmp_path):
    # Attack: stamp the corpus at an OLD build ("21.0.671") to try to match an
    # older committed symbol table and pass. The ratified authority is the
    # HIGHEST-major committed table (h22=.400), chosen independently of the corpus,
    # so a 21-stamped corpus is correctly STALE, never a self-selected pass.
    _mk_ledger_module(tmp_path)
    _mk_symtable(tmp_path, "21.0.671", major="21")
    _mk_symtable(tmp_path, "22.0.400", major="22")
    _mk_corpus(tmp_path, "21.0.671")
    r = checks.check_corpus_stamp_fresh(_ctx(tmp_path))
    assert r["ok"] is False
    assert "STALE" in r["detail"]
    assert "22.0.400" in r["detail"]   # compared against the ratified .400, not .671


def test_non_dict_corpus_fails_not_raises(tmp_path):
    # a parseable-but-non-dict corpus (JSON list/str/number/bool/null) must return
    # ok:False, NEVER raise — a raise crashes checks.py to a verdict:ERROR that routes
    # to LLM adjudication instead of the deterministic block (crucible finding, crit B).
    _mk_ledger_module(tmp_path)
    _mk_symtable(tmp_path, "22.0.400")
    cp = tmp_path / "rag" / "corpus"
    cp.mkdir(parents=True, exist_ok=True)
    for txt in ("[]", '"22.0.400"', "42", "true", "null"):
        (cp / "h22_nodes.json").write_text(txt, encoding="utf-8")
        r = checks.check_corpus_stamp_fresh(_ctx(tmp_path))
        assert r["ok"] is False, (txt, r)
        assert r["ok"] is not None


def test_gate_never_returns_none(tmp_path):
    # The anti-warn invariant across every failure mode: ok is always a bool.
    _mk_ledger_module(tmp_path)
    cases = []
    # absent everything
    cases.append(checks.check_corpus_stamp_fresh(_ctx(tmp_path)))
    # corpus only, no authority
    _mk_corpus(tmp_path, "22.0.400")
    cases.append(checks.check_corpus_stamp_fresh(_ctx(tmp_path)))
    # stale
    _mk_symtable(tmp_path, "22.0.400")
    _mk_corpus(tmp_path, "22.0.368")
    cases.append(checks.check_corpus_stamp_fresh(_ctx(tmp_path)))
    for r in cases:
        assert r["ok"] is False
        assert r["ok"] is not None


def test_live_worktree_is_honestly_green():
    # Sanity against the REAL worktree: W5-DELTA re-ingested the corpus at 22.0.400
    # (== ratified build), so the gate is correctly GREEN now. The synthetic cases
    # above still pin the honest-red behavior. Documents the live state; not a
    # synthetic fixture. (Was test_live_worktree_is_honestly_red pre-W5-DELTA.)
    r = checks.check_corpus_stamp_fresh({"wt": str(ROOT), "hython": "", "mode": "A"})
    assert r["ok"] is True
    assert "22.0.400" in r["detail"]
