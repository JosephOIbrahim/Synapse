"""Pins the C-track (context-capability graft) checks — harness/verify/checks.py:
context_catalog_fresh, context_review_clean, context_golden_{sop,lop,cop,top,dop,mat} —
plus the tasks.json conformance surface and the guardrail freeze. Loaded by path like
test_phantom_guardrail.py — the harness verify layer isn't a package. Every case is
hermetic: tmp_path worktrees, no git, no hou, no hython (the probe seam is a monkeypatched
checks.sh whose fake honors --out — so the golden checks parse a fabricated artifact FILE
exactly as the frozen contract demands — and answers the `git show HEAD:` baseline read,
keeping the ratchet cases agnostic to whether the committed catalog is read from HEAD or
the worktree file).

Assertion discipline (spec-C §6, binding): SUBSTRING matches on detail prose ("C.0",
"HYTHON unset", "merge", the schema string) — BUILDER-B words the messages, the spec only
freezes what they must name. Exact equality is reserved for non-prose frozen surfaces
(verify lists, the guardrail name list, the findings schema string).

Landing order (this file is BUILDER-D; A/B/C land concurrently):
- tasks.json conformance skips loudly until BUILDER-A's C-entries exist (sibling pattern);
- every DISPATCH-backed case fails (KeyError) until BUILDER-B registers the 8 checks;
- the two review cases additionally pytest.fail until BUILDER-C lands
  scripts/flywheel_review_context.py — they copy the REAL script into the tmp worktree and
  let the check drive it through its own subprocess seam, because "digest-broken ⇒ ≥1
  CRITICAL" is SCRIPT semantics: a faked sh() would only ever assert this file's fixtures.

Sibling caveat re-pinned: never plant sys.modules fakes (monkeypatch or nothing); never
branch on hou importability.
"""
import hashlib
import importlib.util
import json
import pathlib
import re

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]
_CHECKS = _REPO / "harness" / "verify" / "checks.py"
_spec = importlib.util.spec_from_file_location("harness_checks_ctx", _CHECKS)
checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checks)

CONTEXTS = ("sop", "lop", "cop", "top", "dop", "mat")
CTX_CHECKS = {"context_catalog_fresh", "context_review_clean"} | {
    f"context_golden_{c}" for c in CONTEXTS}
CATALOG_REL = "harness/notes/context_capability_21.json"
SCHEMA = "context_capability/v1"

# guardrails.checks as of the graft's start — the C track adds TASK verifies, never
# guardrails, so this list is frozen byte-for-byte (spec-C §6 "guardrails.checks unchanged").
GUARDRAILS_FROZEN = ["scout_no_apex_corpus", "no_rigging_drift",
                     "provenance_not_bypassed", "phantom_clean",
                     "suite_baseline"]  # ratchet: full-suite green baseline (2026-07-07)


def _blake(obj):
    # the frozen digest recipe (spec-C §3/§4): blake2b-16 over the canonical dumps of
    # `contexts` ONLY — generated/summary/unclassified sit outside it.
    return hashlib.blake2b(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        digest_size=16).hexdigest()


def _entry(golden_ok=True, gaps=(), failing_step=None, commands=()):
    steps = [{"step": "create_container", "ok": True, "detail": ""}]
    if failing_step:
        steps.append({"step": failing_step, "ok": False, "detail": "probe step failed"})
    return {"commands": list(commands),
            "golden": {"ok": golden_ok, "steps": steps, "revert_ok": True},
            "extended": [], "gaps": list(gaps)}


# A review-CLEAN catalog needs per-context command lists that dodge every §5 CRITICAL:
# cops_/tops_ prefixes only under cop/top, and no command classified into two contexts.
_CLEAN_COMMANDS = {"sop": [], "lop": ["create_usd_prim"], "cop": ["cops_create_node"],
                   "top": ["tops_generate_items"], "dop": [],
                   "mat": ["create_material"], "generic": ["create_node"]}


def _catalog_doc(entries=None):
    contexts = {c: _entry(commands=_CLEAN_COMMANDS[c]) for c in (*CONTEXTS, "generic")}
    if entries:
        contexts.update(entries)
    return {"schema": SCHEMA, "houdini_version": "21.0.671", "synapse_version": "5.20.0",
            "generated": "2026-07-06T00:00:00", "handler_command_count": 115,
            "contexts": contexts, "unclassified": [],
            "summary": {c: {"golden_ok": e["golden"]["ok"], "gaps": len(e["gaps"])}
                        for c, e in contexts.items()},
            "blake2b": _blake(contexts)}


def _plant(wt, rel, doc):
    p = wt / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")


def _probe_seam(monkeypatch, wt, name, entry, baseline=None):
    """Fake EVERY sh() call the golden check makes, at the checks.sh seam (the
    test_phantom_guardrail precedent — no real hython, no real git):
    - a `git show` call is the baseline read → served the committed catalog (or rc!=0 when
      baseline is None, simulating no catalog merged at HEAD);
    - the probe call honors --out (writes the artifact FILE where the check pointed it,
      relative to cwd) instead of pre-planting — robust to BUILDER-B's defensive clear of
      a stale artifact before the run.
    When baseline is given the worktree copy is planted too, so these cases pin the
    CONTRACT (ratchet vs the committed catalog) without caring whether the implementation
    reads it via `git show HEAD:` (the landed form) or the worktree file. Returns the call
    list so a test can pin the frozen probe-invocation shape."""
    contexts = {name: entry}
    doc = {"schema": SCHEMA, "houdini_version": "21.0.671",
           "generated": "2026-07-06T00:00:01", "contexts": contexts,
           "summary": {name: {"golden_ok": entry["golden"]["ok"],
                              "gaps": len(entry["gaps"])}},
           "blake2b": _blake(contexts)}
    if baseline is not None:
        _plant(wt, CATALOG_REL, baseline)
    calls = []
    def fake(cmd, cwd=None, timeout=900, env=None):
        cmd = [str(c) for c in cmd]
        calls.append(cmd)
        if cmd[0] == "git":
            if baseline is None:
                return 128, "", "fatal: path does not exist in 'HEAD'"
            return 0, json.dumps(baseline), ""
        out = pathlib.Path(cwd) / cmd[cmd.index("--out") + 1]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc), encoding="utf-8")
        return 0, "", ""
    monkeypatch.setattr(checks, "sh", fake)
    return calls


def _golden(name, wt, hython="X:/fake/hython"):
    # through DISPATCH, not getattr: run_one reaches these by name, and the frozen surface
    # is the DISPATCH row — the helper/function naming underneath is BUILDER-B's.
    return checks.DISPATCH[f"context_golden_{name}"]({"wt": str(wt), "hython": hython,
                                                      "mode": "A"})


# ---------- conformance: guardrails frozen, DISPATCH rows, tasks.json ----------

def test_guardrails_untouched_by_graft():
    doc = json.loads((_REPO / "harness" / "tasks.json").read_text(encoding="utf-8"))
    assert doc["guardrails"]["checks"] == GUARDRAILS_FROZEN


def test_ctx_checks_registered_in_dispatch():
    assert CTX_CHECKS <= set(checks.DISPATCH)


def test_c_tasks_conform_to_contract():
    # Correct against the FINAL contract: validates whatever C-tasks tasks.json carries.
    # BUILDER-A lands the C entries concurrently — skip loudly (not vacuous-pass) until then.
    doc = json.loads((_REPO / "harness" / "tasks.json").read_text(encoding="utf-8"))
    c_tasks = [t for t in doc["tasks"] if str(t.get("id", "")).startswith("C.")]
    if not c_tasks:
        pytest.skip("no C-tasks in tasks.json yet (BUILDER-A pending)")
    vocab = set(doc.get("checks_vocabulary", []))
    assert CTX_CHECKS <= vocab
    assert {t["id"] for t in c_tasks} == {f"C.{n}" for n in range(0, 7)}
    order = dict(zip((f"C.{n}" for n in range(1, 7)), CONTEXTS))  # C.1 sop … C.6 mat, frozen
    for t in c_tasks:
        assert re.fullmatch(r"C\.\d", t["id"]), t["id"]
        if t["id"] == "C.0":
            assert t.get("blocked_on") != "catalog", "C.0 must not gate on its own output"
            assert t.get("verify") == ["context_catalog_fresh", "context_review_clean"]
        else:
            assert t.get("blocked_on") == "catalog", t["id"]
            assert t.get("verify") == [f"context_golden_{order[t['id']]}",
                                       "context_catalog_fresh"], t["id"]
        for name in t.get("verify", []):
            assert name in checks.DISPATCH, f"{t['id']}: verify '{name}' not in DISPATCH"
            assert name in vocab, f"{t['id']}: verify '{name}' not in checks_vocabulary"


# ---------- context_catalog_fresh ----------

def test_catalog_fresh_missing_names_c0(tmp_path):
    res = checks.DISPATCH["context_catalog_fresh"]({"wt": str(tmp_path), "hython": "",
                                                    "mode": "A"})
    assert res["ok"] is False
    assert "C.0" in res["detail"]


def test_catalog_fresh_wrong_schema(tmp_path):
    doc = _catalog_doc()
    doc["schema"] = "context_capability/v0"
    _plant(tmp_path, CATALOG_REL, doc)
    res = checks.DISPATCH["context_catalog_fresh"]({"wt": str(tmp_path), "hython": "",
                                                    "mode": "A"})
    assert res["ok"] is False
    assert SCHEMA in res["detail"]  # the failure must name the expected schema


def test_catalog_fresh_blake2b_mismatch(tmp_path):
    doc = _catalog_doc()
    doc["blake2b"] = "00" * 16
    _plant(tmp_path, CATALOG_REL, doc)
    res = checks.DISPATCH["context_catalog_fresh"]({"wt": str(tmp_path), "hython": "",
                                                    "mode": "A"})
    assert res["ok"] is False
    assert "blake2b" in res["detail"].lower()


def test_catalog_fresh_valid_hython_unset_notes_skip(tmp_path):
    # HYTHON unset is ok:TRUE for the catalog check (unlike the goldens) — but the detail
    # must admit the live-build comparison never ran, never imply it did.
    _plant(tmp_path, CATALOG_REL, _catalog_doc())
    res = checks.DISPATCH["context_catalog_fresh"]({"wt": str(tmp_path), "hython": "",
                                                    "mode": "A"})
    assert res["ok"] is True
    assert "skipped" in res["detail"].lower()


# ---------- context_golden_* (probe seam faked; ratchet math pinned) ----------

def test_golden_hython_unset(tmp_path):
    # ok:false by design — a golden that can't run is not verified (never ok:None here).
    _plant(tmp_path, CATALOG_REL, _catalog_doc())
    res = _golden("cop", tmp_path, hython="")
    assert res["ok"] is False
    assert "HYTHON unset" in res["detail"]


def test_golden_committed_catalog_missing_mentions_merge(tmp_path, monkeypatch):
    # probe succeeds (golden ok) but there is no committed baseline to ratchet against —
    # order-agnostic: whether BUILDER-B checks the catalog before or after the probe run,
    # the verdict is false and must point at C.0 + merge.
    _probe_seam(monkeypatch, tmp_path, "dop", _entry(golden_ok=True), baseline=None)
    res = _golden("dop", tmp_path)
    assert res["ok"] is False
    assert "merge" in res["detail"].lower()


def test_golden_ratchet_no_improvement_fails(tmp_path, monkeypatch):
    calls = _probe_seam(monkeypatch, tmp_path, "sop",
                        _entry(golden_ok=True, gaps=["a", "b", "c"]),
                        baseline=_catalog_doc({"sop": _entry(golden_ok=True,
                                                             gaps=["a", "b", "c"])}))
    res = _golden("sop", tmp_path)
    assert res["ok"] is False  # base 3 / now 3: unchanged is NOT progress
    # frozen invocation shape: the probe script, targeted at this context
    probe = next(c for c in calls if any("introspect_context_capability" in s for s in c))
    assert probe[probe.index("--context") + 1] == "sop"


def test_golden_ratchet_improvement_passes(tmp_path, monkeypatch):
    _probe_seam(monkeypatch, tmp_path, "lop", _entry(golden_ok=True, gaps=["a", "b"]),
                baseline=_catalog_doc({"lop": _entry(golden_ok=True,
                                                     gaps=["a", "b", "c"])}))
    res = _golden("lop", tmp_path)
    assert res["ok"] is True  # base 3 / now 2, golden ok
    # detail must state gaps now/baseline (numbers, not prose — safe to substring)
    assert "2" in res["detail"] and "3" in res["detail"]


def test_golden_ratchet_clean_stays_clean(tmp_path, monkeypatch):
    # a context already at 0 gaps banks trivially — spec says that is correct, not a bug.
    _probe_seam(monkeypatch, tmp_path, "top", _entry(golden_ok=True, gaps=[]),
                baseline=_catalog_doc({"top": _entry(golden_ok=True, gaps=[])}))
    res = _golden("top", tmp_path)
    assert res["ok"] is True


def test_golden_ratchet_regression_from_clean_fails(tmp_path, monkeypatch):
    # base 0 / now 1: the (0,0) branch is strict — a regression from clean must fail even
    # though now <= base - 1 is unsatisfiable and might tempt a sloppier disjunction.
    _probe_seam(monkeypatch, tmp_path, "cop", _entry(golden_ok=True, gaps=["new_gap"]),
                baseline=_catalog_doc({"cop": _entry(golden_ok=True, gaps=[])}))
    res = _golden("cop", tmp_path)
    assert res["ok"] is False


def test_golden_fail_blocks_even_when_ratchet_passes(tmp_path, monkeypatch):
    # golden.ok and the ratchet are BOTH required: gaps improved 3→1 but the golden run
    # itself failed ⇒ false, and the detail names the first failing step.
    _probe_seam(monkeypatch, tmp_path, "mat",
                _entry(golden_ok=False, gaps=["assign_material"],
                       failing_step="assign_material"),
                baseline=_catalog_doc({"mat": _entry(golden_ok=True,
                                                     gaps=["a", "b", "c"])}))
    res = _golden("mat", tmp_path)
    assert res["ok"] is False
    assert "assign_material" in res["detail"]


# ---------- context_review_clean (real script, through the check's own subprocess seam) ----------
# Deliberately NOT a monkeypatched sh(): "digest-broken ⇒ ≥1 CRITICAL" is the SCRIPT's
# semantics (spec-C §5) — a faked seam could only ever assert this file's own fixtures.
# The real scripts/flywheel_review_context.py is copied into the tmp worktree (it resolves
# paths from its own location, mirroring flywheel_review_lop.py) and the check drives it
# exactly as production does: sh([sys.executable, ...], cwd=wt). Stock python, no hou.

def _stage_review_wt(tmp_path, catalog_doc):
    src = _REPO / "scripts" / "flywheel_review_context.py"
    if not src.is_file():
        pytest.fail("scripts/flywheel_review_context.py not landed yet (BUILDER-C pending)")
    dst = tmp_path / "scripts" / "flywheel_review_context.py"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / ".claude").mkdir(exist_ok=True)  # mirror a real checkout, not a bare fork
    _plant(tmp_path, CATALOG_REL, catalog_doc)
    return {"wt": str(tmp_path), "hython": "", "mode": "A"}


def test_review_clean_valid_catalog(tmp_path):
    ctx = _stage_review_wt(tmp_path, _catalog_doc())
    res = checks.DISPATCH["context_review_clean"](ctx)
    assert res["ok"] is True
    findings = json.loads((tmp_path / ".claude" / "flywheel_ctx_findings.json")
                          .read_text(encoding="utf-8"))
    assert findings["schema"] == "ctx_review/v1"  # frozen findings schema (§5)
    assert findings["summary"]["critical"] == 0


def test_review_clean_digest_broken_catalog(tmp_path):
    doc = _catalog_doc()
    doc["blake2b"] = "00" * 16
    ctx = _stage_review_wt(tmp_path, doc)
    res = checks.DISPATCH["context_review_clean"](ctx)
    assert res["ok"] is False
    findings = json.loads((tmp_path / ".claude" / "flywheel_ctx_findings.json")
                          .read_text(encoding="utf-8"))
    assert findings["summary"]["critical"] >= 1
