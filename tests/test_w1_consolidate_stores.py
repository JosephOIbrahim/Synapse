"""W1 consolidation migration: data-safety contract, on synthetic stores.

Pins keep-both, idempotency, embedder-dim-mismatch preservation, read-only
sources, and never-overwrite/never-delete -- the invariants that protect the
user's real memory when scripts/w1_consolidate_stores.py runs for real.
"""

import hashlib
import importlib.util
import json
import os
import uuid
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "w1_consolidate_stores.py"
_spec = importlib.util.spec_from_file_location("w1_consolidate_stores", _SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _tree_hashes(root: Path) -> dict:
    out = {}
    for r, _d, files in os.walk(root):
        for f in files:
            fp = Path(r) / f
            out[str(fp.relative_to(root))] = _sha(fp)
    return out


def _make_synapse_store(path: Path, jsonl_lines, moneta_ids, dim=4) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    body = ("\n".join(jsonl_lines) + "\n") if jsonl_lines else ""
    (path / "memory.jsonl").write_text(body, encoding="utf-8")
    md = path / ".moneta"
    md.mkdir(exist_ok=True)
    rows = []
    for mid in moneta_ids:
        rows.append({
            "entity_id": str(uuid.uuid4()),
            "payload": json.dumps({"id": mid, "content": mid}),
            "semantic_vector": [0.0] * dim, "utility": 1.0, "attended_count": 0,
            "protected_floor": 0.0, "last_evaluated": 0.0, "state": 0,
            "usd_link": None,
        })
    (md / "snapshot.json").write_text(
        json.dumps({"snapshot_version": 1, "snapshot_created_at": 0.0, "rows": rows}),
        encoding="utf-8")
    return path


# --- canonical derivation --------------------------------------------------

def test_canonical_root_override(tmp_path):
    root = mod.canonical_unsaved_root(str(tmp_path / "x" / "untitled"))
    assert root == Path(os.path.normpath(str(tmp_path / "x" / "untitled")))


def test_canonical_root_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("HOUDINI_TEMP_DIR", str(tmp_path / "ht"))
    root = mod.canonical_unsaved_root()
    assert root.name == "untitled" and str(tmp_path / "ht") in str(root)


def test_canonical_root_default_no_literal(monkeypatch):
    monkeypatch.delenv("HOUDINI_TEMP_DIR", raising=False)
    root = mod.canonical_unsaved_root()
    assert not mod._has_literal_env_segment(str(root))
    assert "houdini_temp" in str(root).replace("\\", "/")


def test_canonical_root_refuses_literal(monkeypatch):
    monkeypatch.setenv("HOUDINI_TEMP_DIR", "$UNDEFINED_TOKEN")
    # env holds a literal token -> _has_literal_env_segment rejects it -> default
    root = mod.canonical_unsaved_root()
    assert not mod._has_literal_env_segment(str(root))


# --- classification --------------------------------------------------------

def test_is_unsaved_scene_predicate():
    assert mod.is_unsaved_scene_store("C:/Users/U/Synapse/$HOUDINI_TEMP_DIR/untitled/.synapse")
    assert mod.is_unsaved_scene_store("C:/Users/U/untitled.hip/.synapse")
    assert mod.is_unsaved_scene_store("C:/Users/U/untitled.hip/claude")
    assert mod.is_unsaved_scene_store("C:/Temp/houdini_temp/untitled/.synapse")
    # leaves
    assert not mod.is_unsaved_scene_store("C:/Users/U/.synapse")
    assert not mod.is_unsaved_scene_store("C:/Users/U/Desktop/claude")
    assert not mod.is_unsaved_scene_store("C:/Users/U/rope-beacon-wt/.synapse")
    assert not mod.is_unsaved_scene_store("C:/Users/U/SYNAPSE/.synapse")


def test_classify_splits_canonical_fragment_leave(tmp_path):
    root = tmp_path / "Temp" / "houdini_temp" / "untitled"
    reals = [
        str(root / ".synapse"),               # canonical
        str(root / "claude"),                 # canonical
        str(tmp_path / "untitled.hip" / ".synapse"),   # fragment
        str(tmp_path / ".synapse"),           # leave (home-like)
    ]
    cls = mod.classify(reals, root)
    assert os.path.normpath(str(root / ".synapse")) in cls["canonical"]
    assert os.path.normpath(str(tmp_path / "untitled.hip" / ".synapse")) in cls["fragment"]
    assert os.path.normpath(str(tmp_path / ".synapse")) in cls["leave"]


# --- jsonl merge -----------------------------------------------------------

def test_merge_jsonl_appends_and_is_idempotent(tmp_path):
    canon = tmp_path / "canon" / "memory.jsonl"
    canon.parent.mkdir(parents=True)
    canon.write_text("A\nB\n", encoding="utf-8")
    frag = tmp_path / "frag" / "memory.jsonl"
    frag.parent.mkdir(parents=True)
    frag.write_text("B\nC\nD\n", encoding="utf-8")  # B is dup

    rep = {}
    mod.merge_jsonl(frag, canon, apply=True, rep=rep)
    assert rep["jsonl"]["appended"] == 2  # C, D
    lines = canon.read_text(encoding="utf-8").splitlines()
    assert lines == ["A", "B", "C", "D"]

    rep2 = {}
    mod.merge_jsonl(frag, canon, apply=True, rep=rep2)
    assert rep2["jsonl"]["appended"] == 0  # idempotent
    assert canon.read_text(encoding="utf-8").splitlines() == ["A", "B", "C", "D"]


# --- moneta merge ----------------------------------------------------------

def test_merge_moneta_dim_match_appends(tmp_path):
    canon = _make_synapse_store(tmp_path / "canon", [], ["mem_a", "mem_b"], dim=4)
    frag = _make_synapse_store(tmp_path / "frag", [], ["mem_c", "mem_d"], dim=4)
    rep = {}
    mod.merge_moneta(frag, canon, "frag", apply=True, rep=rep)
    assert rep["moneta"]["appended"] == 2
    rows = json.loads((canon / ".moneta" / "snapshot.json").read_text())["rows"]
    ids = {json.loads(r["payload"])["id"] for r in rows}
    assert ids == {"mem_a", "mem_b", "mem_c", "mem_d"}
    # idempotent
    rep2 = {}
    mod.merge_moneta(frag, canon, "frag", apply=True, rep=rep2)
    assert rep2["moneta"]["appended"] == 0


def test_merge_moneta_dim_mismatch_preserves_not_merges(tmp_path):
    canon = _make_synapse_store(tmp_path / "canon", [], ["mem_a"], dim=4)
    frag = _make_synapse_store(tmp_path / "frag", [], ["mem_x"], dim=8)  # mismatch
    rep = {}
    mod.merge_moneta(frag, canon, "frag_slug", apply=True, rep=rep)
    assert rep["moneta"]["preserved_not_merged"] is True
    assert rep["moneta"]["appended"] == 0
    # canonical snapshot UNCHANGED (no 8-dim vector merged in)
    rows = json.loads((canon / ".moneta" / "snapshot.json").read_text())["rows"]
    assert len(rows) == 1
    # fragment moneta preserved under the incoming dir
    preserved = canon / ".w1_incoming_moneta" / "frag_slug" / "snapshot.json"
    assert preserved.is_file()


def test_merge_moneta_id_collision_keeps_both(tmp_path):
    canon = _make_synapse_store(tmp_path / "canon", [], ["mem_a"], dim=4)
    # fragment reuses mem_a but with DIFFERENT payload content
    frag = tmp_path / "frag"
    _make_synapse_store(frag, [], [], dim=4)
    rows = [{
        "entity_id": str(uuid.uuid4()),
        "payload": json.dumps({"id": "mem_a", "content": "DIFFERENT"}),
        "semantic_vector": [0.0] * 4, "utility": 1.0, "attended_count": 0,
        "protected_floor": 0.0, "last_evaluated": 0.0, "state": 0, "usd_link": None,
    }]
    (frag / ".moneta" / "snapshot.json").write_text(
        json.dumps({"snapshot_version": 1, "snapshot_created_at": 0.0, "rows": rows}),
        encoding="utf-8")
    rep = {}
    mod.merge_moneta(frag, canon, "frag", apply=True, rep=rep)
    assert "mem_a" in rep["moneta"]["collisions_kept_both"]
    # canonical unchanged (loser quarantined, not overwritten)
    crows = json.loads((canon / ".moneta" / "snapshot.json").read_text())["rows"]
    assert len(crows) == 1
    assert json.loads(crows[0]["payload"])["content"] == "mem_a"
    q = canon / ".w1_quarantine" / "frag" / "moneta_rows"
    assert q.is_dir() and any(q.iterdir())


# --- file keep-both --------------------------------------------------------

def test_merge_files_keep_both_on_differ_never_overwrites(tmp_path):
    canon = tmp_path / "canon"
    canon.mkdir()
    (canon / "decisions.md").write_text("CANON", encoding="utf-8")
    frag = tmp_path / "frag"
    frag.mkdir()
    (frag / "decisions.md").write_text("FRAG", encoding="utf-8")
    (frag / "memory.jsonl").write_text("x\n", encoding="utf-8")  # skipped here
    rep = {}
    mod.merge_files(frag, canon, "frag", apply=True, rep=rep)
    # canonical decisions.md is UNTOUCHED
    assert (canon / "decisions.md").read_text(encoding="utf-8") == "CANON"
    # fragment copy kept beside it
    assert any(p.name.startswith("decisions.md.w1-collision-") for p in canon.iterdir())
    # memory.jsonl was NOT copied by merge_files (jsonl has its own path)
    assert not (canon / "memory.jsonl").exists()


# --- end-to-end: apply + idempotency + read-only sources -------------------

def _build_census(tmp_path, root):
    canon_syn = _make_synapse_store(root / ".synapse", ["c1", "c2"], ["mem_c1"], dim=4)
    (root / "claude").mkdir(parents=True, exist_ok=True)
    (root / "claude" / "memory.md").write_text("# canon claude\n", encoding="utf-8")
    frag_syn = _make_synapse_store(
        tmp_path / "untitled.hip" / ".synapse", ["c2", "f1", "f2"], ["mem_f1"], dim=4)
    (frag_syn / "decisions.md").write_text("frag decisions\n", encoding="utf-8")
    frag_cla = tmp_path / "untitled.hip" / "claude"
    frag_cla.mkdir(parents=True, exist_ok=True)
    (frag_cla / "memory.md").write_text("# frag claude\n", encoding="utf-8")
    home = tmp_path / ".synapse"  # a leave store
    home.mkdir(parents=True, exist_ok=True)
    (home / "memory.jsonl").write_text("home\n", encoding="utf-8")
    census = {"entries": [{"value": {"stores": [
        {"path": str(canon_syn), "classification": "real"},
        {"path": str(root / "claude"), "classification": "real"},
        {"path": str(frag_syn), "classification": "real"},
        {"path": str(frag_cla), "classification": "real"},
        {"path": str(home), "classification": "real"},
    ]}}]}
    cpath = tmp_path / "census.json"
    cpath.write_text(json.dumps(census), encoding="utf-8")
    return cpath, canon_syn, frag_syn, frag_cla, home


def test_consolidate_apply_then_idempotent_and_sources_untouched(tmp_path):
    root = tmp_path / "Temp" / "houdini_temp" / "untitled"
    census, canon_syn, frag_syn, frag_cla, home = _build_census(tmp_path, root)

    frag_before = {**_tree_hashes(frag_syn), **_tree_hashes(frag_cla)}
    home_before = _tree_hashes(home)

    rep = mod.consolidate(str(census), root, apply=True)

    # jsonl merged: c2 dup skipped, f1+f2 appended
    canon_lines = (canon_syn / "memory.jsonl").read_text(encoding="utf-8").splitlines()
    assert canon_lines == ["c1", "c2", "f1", "f2"]
    # moneta merged (dim match)
    crows = json.loads((canon_syn / ".moneta" / "snapshot.json").read_text())["rows"]
    assert {json.loads(r["payload"])["id"] for r in crows} == {"mem_c1", "mem_f1"}
    # fragment decisions.md copied into canonical (was absent)
    assert (canon_syn / "decisions.md").read_text(encoding="utf-8") == "frag decisions\n"

    # SOURCES READ-ONLY: no fragment/home file changed
    assert {**_tree_hashes(frag_syn), **_tree_hashes(frag_cla)} == frag_before
    assert _tree_hashes(home) == home_before
    # home (leave) never received anything
    assert home_before == _tree_hashes(home)
    assert "leave" in rep["classification"]
    assert os.path.normpath(str(home)) in rep["classification"]["leave"]

    # IDEMPOTENT: a second apply appends nothing and leaves the canonical
    # memory.jsonl + snapshot byte-identical (pre-images are only written when a
    # file is actually extended, so no new .w1-pre-* file appears either).
    canon_after_first = _tree_hashes(canon_syn)
    rep2 = mod.consolidate(str(census), root, apply=True)
    appended2 = sum(f.get("jsonl", {}).get("appended", 0)
                    + f.get("moneta", {}).get("appended", 0)
                    for f in rep2["fragments"])
    assert appended2 == 0
    assert _tree_hashes(canon_syn) == canon_after_first
    assert (canon_syn / "memory.jsonl").read_text().splitlines() == ["c1", "c2", "f1", "f2"]


def test_dry_run_writes_nothing(tmp_path):
    root = tmp_path / "Temp" / "houdini_temp" / "untitled"
    census, canon_syn, frag_syn, frag_cla, home = _build_census(tmp_path, root)
    before = _tree_hashes(tmp_path)
    rep = mod.consolidate(str(census), root, apply=False)
    assert rep["mode"] == "dry-run"
    assert _tree_hashes(tmp_path) == before  # nothing written anywhere
