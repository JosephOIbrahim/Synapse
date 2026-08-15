"""W4-GUARD target 2 — the per-context ingest ledger, single-writer.

Acceptance predicate #2: "ledger schema documented; a second-writer attempt is
rejected or detectable — single-writer enforced, not assumed" (evidence: test).

The ledger contract lives in harness/ingest_ledger.py (schema + AUTHORIZED_WRITER +
write_ledger/verify_ledger); the release gate is
harness/verify/checks.py::check_ingest_ledger_single_writer.

Target 3 is also reinforced here from the ledger's own side: apex/rig/kinefx never
enter the ledger's wired set, and authoring_domains.json carries no drift term.
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


il = _load("w4guard_ingest_ledger", "harness/ingest_ledger.py")
checks = _load("w4guard_checks_led", "harness/verify/checks.py")


def _fake_corpus(build="22.0.400"):
    return {"schema": "h22_node_corpus/v1", "build": build,
            "entries": [{"type": "chromakey", "context": "cop"},
                        {"type": "blur", "context": "cop"},
                        {"type": "rendergeometrysettings", "context": "lop"}]}


def _valid_ledger(tmp_path, corpus=None):
    corpus = corpus or _fake_corpus()
    contexts = il.contexts_from_corpus(corpus, gate_wired="G", leg_wired="I1")
    path = tmp_path / "ingest_ledger.json"
    doc = il.write_ledger(str(path), contexts, corpus["build"])
    return path, doc, corpus


# ---- schema documented ----
def test_schema_documented():
    assert il.LEDGER_SCHEMA == "ingest_ledger/v1"
    assert il.AUTHORIZED_WRITER  # named, non-empty
    doc = il.__doc__ or ""
    # every schema field name is documented in the module docstring
    for field in ("schema", "writer", "revision", "ratified_build", "contexts",
                  "wired", "build", "entries", "gate", "leg", "blake2b"):
        assert field in doc, "schema field %r not documented" % field
    assert "single writer" in doc.lower() or "single-writer" in doc.lower()


# ---- write -> verify round-trips clean ----
def test_write_then_verify_sound(tmp_path):
    path, doc, corpus = _valid_ledger(tmp_path)
    assert il.verify_ledger(doc, corpus=corpus) == []
    # reloaded from disk is identical and still verifies
    assert il.verify_ledger(il.load_ledger(str(path)), corpus=corpus) == []


# ---- single-writer: REJECTED at the write boundary ----
def test_second_writer_identity_rejected_at_write(tmp_path):
    contexts = il.contexts_from_corpus(_fake_corpus())
    with pytest.raises(il.UnauthorizedWriter):
        il.write_ledger(str(tmp_path / "l.json"), contexts, "22.0.400",
                        writer="rogue_agent")


# ---- single-writer: DETECTED at verify (out-of-band edit, no digest recompute) ----
def test_out_of_band_tamper_detected(tmp_path):
    path, doc, corpus = _valid_ledger(tmp_path)
    tampered = il.load_ledger(str(path))
    tampered["contexts"]["sop"]["wired"] = True   # a second writer flips a bit...
    tampered["contexts"]["sop"]["build"] = "22.0.400"
    # ...but does NOT recompute the digest -> stale blake2b
    viol = il.verify_ledger(tampered, corpus=corpus)
    assert any("blake2b" in v for v in viol), viol


# ---- single-writer: DETECTED even if the tamperer recomputes the digest but
#      cannot forge the authorized identity ----
def test_writer_identity_swap_detected_even_with_valid_digest(tmp_path):
    path, doc, corpus = _valid_ledger(tmp_path)
    forged = il.load_ledger(str(path))
    forged["writer"] = "some_agent"
    forged["blake2b"] = il.compute_digest(forged)   # digest now internally valid
    viol = il.verify_ledger(forged, corpus=corpus)
    assert any("unauthorized writer" in v for v in viol), viol


# ---- corpus cross-check: the ledger cannot lie about what shipped ----
def test_overclaim_wired_context_caught(tmp_path):
    corpus = _fake_corpus()
    contexts = il.contexts_from_corpus(corpus, gate_wired="G", leg_wired="I1")
    # forge sop as wired though the corpus has zero sop entries
    contexts["sop"] = {"wired": True, "build": "22.0.400", "entries": 5,
                       "gate": "G", "leg": "ING-SOP"}
    doc = il.write_ledger(str(tmp_path / "l.json"), contexts, "22.0.400")
    viol = il.verify_ledger(doc, corpus=corpus)
    assert any("over-claim" in v for v in viol), viol


def test_underreport_wired_context_caught(tmp_path):
    corpus = _fake_corpus()
    contexts = il.contexts_from_corpus(corpus, gate_wired="G", leg_wired="I1")
    # mark cop unwired though the corpus carries cop entries
    contexts["cop"] = {"wired": False, "build": None, "entries": 0,
                       "gate": None, "leg": "ING-COP"}
    doc = il.write_ledger(str(tmp_path / "l.json"), contexts, "22.0.400")
    viol = il.verify_ledger(doc, corpus=corpus)
    assert any("under-report" in v for v in viol), viol


def test_entry_count_mismatch_caught(tmp_path):
    corpus = _fake_corpus()
    contexts = il.contexts_from_corpus(corpus, gate_wired="G", leg_wired="I1")
    contexts["cop"]["entries"] = 999   # corpus has 2 cop entries
    doc = il.write_ledger(str(tmp_path / "l.json"), contexts, "22.0.400")
    viol = il.verify_ledger(doc, corpus=corpus)
    assert any("!= 2 in the served corpus" in v for v in viol), viol


# ---- target 3, from the ledger's own side: apex is never wired ----
def test_apex_policy_blocked_never_wired(tmp_path):
    corpus = _fake_corpus()
    contexts = il.contexts_from_corpus(corpus, gate_wired="G", leg_wired="I1")
    assert contexts["apex"]["wired"] is False
    assert contexts["apex"].get("blocked_by_policy") == "D-H22-2"
    # a ledger that marks apex wired is rejected
    contexts["apex"]["wired"] = True
    doc = il.write_ledger(str(tmp_path / "l.json"), contexts, "22.0.400")
    viol = il.verify_ledger(doc, corpus=corpus)
    assert any("POLICY_BLOCKED" in v and "apex" in v for v in viol), viol


# ---- the release gate end-to-end against a fixture worktree ----
def _mk_wt(tmp_path, corpus=None, ratified_build=None):
    corpus = corpus or _fake_corpus()
    (tmp_path / "harness").mkdir(parents=True, exist_ok=True)
    (tmp_path / "harness" / "ingest_ledger.py").write_bytes(
        (ROOT / "harness" / "ingest_ledger.py").read_bytes())
    cp = tmp_path / "rag" / "corpus"
    cp.mkdir(parents=True, exist_ok=True)
    (cp / "h22_nodes.json").write_text(json.dumps(corpus), encoding="utf-8")
    # a committed symbol table gives the gate a ratified-build authority (== corpus build)
    dp = tmp_path / "python" / "synapse" / "cognitive" / "tools" / "data"
    dp.mkdir(parents=True, exist_ok=True)
    (dp / "h22_symbol_table.json").write_text(
        json.dumps({"houdini_version": corpus["build"]}), encoding="utf-8")
    contexts = il.contexts_from_corpus(corpus, gate_wired="G", leg_wired="I1")
    il.write_ledger(str(tmp_path / "harness" / "ingest_ledger.json"),
                    contexts, ratified_build or corpus["build"])
    return {"wt": str(tmp_path), "hython": "", "mode": "A"}


def test_gate_passes_on_sound_ledger(tmp_path):
    ctx = _mk_wt(tmp_path)
    r = checks.check_ingest_ledger_single_writer(ctx)
    assert r["ok"] is True, r["detail"]
    assert "sole writer" in r["detail"]


def test_gate_fails_on_tampered_ledger(tmp_path):
    ctx = _mk_wt(tmp_path)
    lp = Path(ctx["wt"]) / "harness" / "ingest_ledger.json"
    doc = json.loads(lp.read_text(encoding="utf-8"))
    doc["contexts"]["sop"]["wired"] = True   # tamper, leave stale digest
    lp.write_text(json.dumps(doc), encoding="utf-8")
    r = checks.check_ingest_ledger_single_writer(ctx)
    assert r["ok"] is False
    assert "REJECTED" in r["detail"]


def test_gate_fails_on_absent_ledger(tmp_path):
    ctx = _mk_wt(tmp_path)
    (Path(ctx["wt"]) / "harness" / "ingest_ledger.json").unlink()
    r = checks.check_ingest_ledger_single_writer(ctx)
    assert r["ok"] is False   # a deleted ledger cannot clear the gate
    assert "absent" in r["detail"]


# ---- crucible fixes: write-race safety, apex case-normalization, forged ratified_build ----
def test_concurrent_writes_do_not_crash(tmp_path):
    # criterion (A) "attacked for write races": concurrent authorized writers to one
    # path must not collide on a shared temp. Unique-temp + os.replace -> last wins,
    # no PermissionError, and the surviving file is always a complete valid ledger.
    import threading
    corpus = _fake_corpus()
    contexts = il.contexts_from_corpus(corpus, gate_wired="G", leg_wired="I1")
    path = str(tmp_path / "ingest_ledger.json")
    il.write_ledger(path, contexts, "22.0.400")
    errors = []
    barrier = threading.Barrier(3)

    def worker():
        try:
            barrier.wait()
            for _ in range(60):
                il.write_ledger(path, contexts, "22.0.400")
        except Exception as e:   # a shared-tmp collision would surface here
            errors.append(repr(e))

    ts = [threading.Thread(target=worker) for _ in range(3)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert errors == [], errors
    assert il.verify_ledger(il.load_ledger(path), corpus=corpus) == []


def test_apex_case_variant_flagged_by_pure_verify(tmp_path):
    # "APEX"/"Apex"/"apex " must not smuggle a wired apex row past the PURE verify
    corpus = _fake_corpus()
    contexts = il.contexts_from_corpus(corpus, gate_wired="G", leg_wired="I1")
    for variant in ("APEX", "Apex", "apex "):
        c = dict(contexts)
        c[variant] = {"wired": True, "build": "22.0.400", "entries": 3,
                      "gate": "g", "leg": "l"}
        doc = il.write_ledger(str(tmp_path / "l.json"), c, "22.0.400")
        viol = il.verify_ledger(doc, corpus=None)   # no corpus cross-check — pure verify only
        assert any("POLICY_BLOCKED" in v for v in viol), (variant, viol)


def test_forged_ratified_build_caught_by_gate(tmp_path):
    # a forger with the plaintext writer token + a recomputed digest cannot fake the
    # ratified_build: the GATE (which knows the worktree) cross-checks it against the
    # resolved authority (the committed symbol table = 22.0.400 here).
    ctx = _mk_wt(tmp_path, ratified_build="21.0.999")   # forged in the written ledger
    r = checks.check_ingest_ledger_single_writer(ctx)
    assert r["ok"] is False
    assert "ratified_build" in r["detail"]


# ---- target 3: the real authoring_domains.json carries no rigging drift ----
def test_real_authoring_domains_no_drift():
    fp = ROOT / "python" / "synapse" / "server" / "authoring_domains.json"
    domains = {d.lower() for d in json.loads(fp.read_text(encoding="utf-8")).get("domains", [])}
    drift = {"apex", "rig", "rigging", "kinefx", "muscle", "cfx"}
    assert not (domains & drift), "rigging drift entered authoring_domains.json: %s" % (domains & drift)


def test_real_seeded_ledger_never_wires_apex():
    fp = ROOT / "harness" / "ingest_ledger.json"
    doc = il.load_ledger(str(fp))
    apex = doc["contexts"].get("apex", {})
    assert apex.get("wired") is False
    assert apex.get("blocked_by_policy") == "D-H22-2"
    # and the committed ledger itself verifies against the shipped corpus
    corpus = json.loads((ROOT / "rag" / "corpus" / "h22_nodes.json").read_text(encoding="utf-8"))
    assert il.verify_ledger(doc, corpus=corpus) == []
