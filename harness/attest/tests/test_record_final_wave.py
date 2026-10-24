"""Tests for the attest board's final-wave recorder.

The recorder is the only thing that turns a wave's journal into the board's
committed record, so its two properties matter more than its output shape:

  - it reads ONLY the journal, and says NOT_YET_PRODUCED for anything the
    journal does not contain, so the record can never claim a verdict that
    was never reached;
  - it does not carry this machine's directory layout into the repo.

Every test below names the condition under which the recorder changes its
answer, and a test that cannot fail is deleted rather than kept green.

Run:  python -m pytest harness/attest/tests/test_record_final_wave.py -q
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0]))

import record_final_wave as R  # noqa: E402


# --------------------------------------------------------------- fixtures

def _started(agent_id, label, phase):
    return {"type": "started", "agentId": agent_id, "label": label, "phase": phase}


def _result(agent_id, payload):
    return {"type": "result", "agentId": agent_id, "result": payload}


def _write_journal(tmp_path, rows, name="journal.jsonl"):
    path = tmp_path / name
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n",
                    encoding="utf-8", newline="")
    return path


def _synth_payload(**over):
    base = {
        "verdict": "SOUND",
        "graph_summary": "one graph",
        "nodes": [
            {"id": "S7", "title": "one release accessor", "owner_files": ["core/release.py"],
             "depends_on": [], "edges": ["S7 -> S6b"], "forge_now": True,
             "crucible_verdict": "SOUND-WITH-NITS", "needs_joe": [], "acceptance_proof": "5 passed"},
        ],
        "spanning_order": ["S7"],
        "parked": ["S6b"],
        "file_ownership": {"core/release.py": ["S7"]},
        "unproven": ["the live serverInfo value"],
        "needs_joe": ["which release the relay stamps"],
    }
    base.update(over)
    return base


# --------------------------------------------------------------- provenance

def test_the_record_names_the_journal_it_came_from(tmp_path):
    rows = [_started("a1", "attest:map:C1", "map"),
            _result("a1", {"cluster": "C1", "nodes": [], "edges": [], "unknowns": []})]
    path = _write_journal(tmp_path, rows)

    parsed, digest = R.read_journal(path)
    record = R.build_record(R.index(parsed), {"run_id": "wf_test", "path": str(path),
                                              "sha256": digest, "rows": len(parsed)},
                            {"spawn_cap": 30, "spawn_reserve": 2})

    assert record["journal"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert record["journal"]["rows"] == 2
    assert record["workflow_run"] == "wf_test"


def test_a_journal_with_no_rows_is_still_a_record(tmp_path):
    # A torn or empty journal must not crash the recorder, and must not
    # invent a verdict: everything is NOT_YET_PRODUCED.
    path = _write_journal(tmp_path, [])
    parsed, digest = R.read_journal(path)
    record = R.build_record(R.index(parsed), {"run_id": "wf_test", "path": str(path),
                                              "sha256": digest, "rows": 0},
                            {"spawn_cap": 30, "spawn_reserve": 2})
    assert record["state"] == "COMPLETE"          # nothing outstanding
    assert record["final_graph"]["status"] == "NOT_YET_PRODUCED"
    assert record["final_graph"]["produced_by_phase"] == "synth"


def test_a_phase_the_journal_never_produced_is_marked_not_yet_produced():
    # The board's evidence law: a phase that has not run cannot have a
    # verdict. A journal with only a map seat must leave synth and verify
    # explicitly outstanding, and name the phase that owes them.
    rows = [_started("a1", "attest:map:C1", "map"),
            _result("a1", {"cluster": "C1", "nodes": [], "edges": [], "unknowns": []})]
    idx = R.index(rows)
    record = R.build_record(idx, {"run_id": "wf_test", "path": "j", "sha256": "x", "rows": 2},
                            {"spawn_cap": 30, "spawn_reserve": 2})

    assert record["final_graph"]["status"] == "NOT_YET_PRODUCED"
    assert record["final_graph"]["produced_by_phase"] == "synth"
    assert record["spanning_order"]["status"] == "NOT_YET_PRODUCED"
    assert record["verify_proofs"]["status"] == "NOT_YET_PRODUCED"
    assert record["phases_complete"] == ["map"]
    assert record["phases_not_started"] == ["seam", "design", "crucible", "synth",
                                            "forge", "verify"]
    # the map seat DID return, so it is not listed as a phase to wait on
    assert "map" not in record["phases_running"]


def test_a_verdict_is_read_from_its_own_seat_not_asserted_by_the_recorder():
    rows = [_started("a1", "attest:crucible:S7", "crucible"),
            _result("a1", {"node_id": "S7", "verdict": "BROKEN", "summary": "why",
                            "attacks": ["one"]}),
            _started("a2", "attest:synth", "synth"),
            _result("a2", _synth_payload())]
    record = R.build_record(R.index(rows),
                            {"run_id": "wf_test", "path": "j", "sha256": "x", "rows": 4},
                            {"spawn_cap": 30, "spawn_reserve": 2})

    verdicts = {v["node_id"]: v for v in record["crucible_verdicts"]}
    assert verdicts["S7"]["verdict"] == "BROKEN"
    assert verdicts["S7"]["seat"] == "attest:crucible:S7"
    # the graph's own claim is carried, and the seat's verdict beside it
    assert record["final_graph"]["nodes"][0]["crucible_verdict"] == "SOUND-WITH-NITS"


def test_needs_joe_is_carried_verbatim():
    rows = [_started("a2", "attest:synth", "synth"),
            _result("a2", _synth_payload(needs_joe=["pick one", "pick two"]))]
    record = R.build_record(R.index(rows),
                            {"run_id": "wf_test", "path": "j", "sha256": "x", "rows": 2},
                            {"spawn_cap": 30, "spawn_reserve": 2})
    assert record["needs_joe"] == ["pick one", "pick two"]


def test_a_verify_seat_that_wrote_evidence_keeps_its_evidence():
    # RED CONTROL. The two verify seats of this wave wrote their proof under
    # "evidence" (a list of strings), not under "proof". The first cut of the
    # recorder read only "proof", so the wave's two PASS verdicts were
    # committed with proof=null - the evidence was dropped and the verdict
    # was published anyway. The evidence is the whole point of the seat.
    evidence = ["BRANCH/SHA: worktree-x @ 460a5e57",
                "DEFECT REPRODUCED INDEPENDENTLY against both trees"]
    rows = [_started("a1", "attest:verify:S7", "verify"),
            _result("a1", {"node_id": "S7", "verdict": "PASS", "commit_sha": "460a5e57",
                            "evidence": evidence})]
    record = R.build_record(R.index(rows),
                            {"run_id": "wf_test", "path": "j", "sha256": "x", "rows": 2},
                            {"spawn_cap": 30, "spawn_reserve": 2})
    v = record["verify_proofs"][0]
    assert v["verdict"] == "PASS"
    assert v["proof_status"] == "CARRIED"
    assert v["commit_sha"] == "460a5e57"
    for line in evidence:
        assert line in v["proof"]
    assert v["evidence"] == evidence
    # and it reaches the human-readable half
    report = R.render_report(record)
    assert "CARRIED" in report
    assert "DEFECT REPRODUCED INDEPENDENTLY against both trees" in report


def test_a_verify_verdict_with_no_proof_is_loud():
    # A seat that says PASS and carries no proof must not be recorded as if
    # it had one. The record says MISSING, in the record and in the report.
    rows = [_started("a1", "attest:verify:S9", "verify"),
            _result("a1", {"node_id": "S9", "verdict": "PASS"})]
    record = R.build_record(R.index(rows),
                            {"run_id": "wf_test", "path": "j", "sha256": "x", "rows": 2},
                            {"spawn_cap": 30, "spawn_reserve": 2})
    v = record["verify_proofs"][0]
    assert v["proof_status"] == "MISSING"
    assert v["proof"] is None
    assert "MISSING" in R.render_report(record)


# --------------------------------------------------------------- accounting

def test_spawn_accounting_is_counted_from_the_journals_own_rows():
    rows = [_started("a1", "attest:map:C1", "map"),
            _started("a2", "attest:map:C2", "map"),
            _started("a3", "attest:seam", "seam"),
            _result("a1", {"cluster": "C1"})]
    acct = R.spawn_accounting(R.index(rows), {"spawn_cap": 30, "spawn_reserve": 2})

    assert acct["seats_dispatched"] == 3
    assert acct["seats_returned"] == 1
    assert acct["seats_outstanding"] == 2
    assert acct["cap"] == 30 and acct["reserve"] == 2
    assert acct["available"] == 28
    assert acct["headroom"] == 25
    assert acct["within_cap"] is True


def test_a_dispatch_over_the_cap_is_reported_as_over():
    # The cap is a contract. The accounting must be able to say the wave
    # broke it - a recorder that always answers within_cap=True cannot.
    rows = [_started("a%d" % i, "attest:map:C%d" % i, "map") for i in range(29)]
    acct = R.spawn_accounting(R.index(rows), {"spawn_cap": 30, "spawn_reserve": 2})
    assert acct["seats_dispatched"] == 29
    assert acct["headroom"] == -1
    assert acct["within_cap"] is False


def test_a_single_segment_phase_is_counted_in_its_own_phase():
    # RED CONTROL. The seam seat and the synth seat are labelled
    # "attest:seam" and "attest:synth" - ONE segment after the prefix. The
    # first cut read the phase out of the label only when the label had two
    # colons, so both seats were counted as "unknown" while the record's
    # phases list said they had returned. The record disagreed with itself.
    rows = [_started("a1", "attest:seam", "seam"),
            _result("a1", {"graph_summary": "s", "seams": []}),
            _started("a2", "attest:synth", "synth"),
            _result("a2", _synth_payload())]
    idx = R.index(rows)
    acct = R.spawn_accounting(idx, {"spawn_cap": 30, "spawn_reserve": 2})
    assert acct["returned_by_phase"]["seam"] == 1
    assert acct["returned_by_phase"]["synth"] == 1
    assert "unknown" not in acct["returned_by_phase"]
    # and the phases list agrees with the accounting
    record = R.build_record(idx, {"run_id": "wf_test", "path": "j", "sha256": "x",
                                  "rows": len(rows)},
                            {"spawn_cap": 30, "spawn_reserve": 2})
    assert "seam" in record["phases_complete"]
    assert "synth" in record["phases_complete"]


# ------------------------------------------------------- the duplicate label

def test_the_state_agrees_with_the_accounting_when_two_seats_share_a_label():
    """A label is not a seat.

    The old state line compared the number of DISTINCT LABELS with the number
    of started rows, while the accounting it published compared RESULT ROWS
    with started rows. Two seats under one label therefore produced
    "state: IN_FLIGHT" printed directly above "seats_returned: 2,
    seats_outstanding: 0" - a record contradicting itself, with no way for a
    reader to tell which half to believe.
    """
    rows = [_started("a1", "attest:crucible:S7", "crucible"),
            _started("a2", "attest:crucible:S7", "crucible"),
            _result("a1", {"node_id": "S7", "verdict": "SOUND"}),
            _result("a2", {"node_id": "S7", "verdict": "BROKEN"})]
    record = R.build_record(R.index(rows),
                            {"run_id": "wf_test", "path": "j", "sha256": "x", "rows": 4},
                            {"spawn_cap": 30, "spawn_reserve": 2})
    acct = record["spawn_accounting"]
    assert acct["seats_returned"] == 2
    assert acct["seats_outstanding"] == 0
    assert record["state"] == "COMPLETE"
    # and the collapse is named rather than hidden
    assert record["duplicate_labels"] == ["attest:crucible:S7"]


def test_a_second_seat_under_a_shared_label_is_not_dropped():
    """The second seat's payload was gathered, and the old recorder threw it
    away: `results` was a label -> payload dict, so the second seat under
    the same label never reached the record. Evidence that was collected and
    then not recorded is evidence the board cannot cite."""
    rows = [_started("a1", "attest:crucible:S7", "crucible"),
            _started("a2", "attest:crucible:S7", "crucible"),
            _result("a1", {"node_id": "S7", "verdict": "SOUND", "summary": "first"}),
            _result("a2", {"node_id": "S7", "verdict": "BROKEN", "summary": "second"})]
    record = R.build_record(R.index(rows),
                            {"run_id": "wf_test", "path": "j", "sha256": "x", "rows": 4},
                            {"spawn_cap": 30, "spawn_reserve": 2})
    verdicts = record["crucible_verdicts"]
    assert len(verdicts) == 2
    assert {v["verdict"] for v in verdicts} == {"SOUND", "BROKEN"}


def test_a_label_that_carries_one_seat_is_not_called_a_duplicate():
    """The duplicate list is a finding, not a decoration. A wave whose labels
    are unique must not be reported as carrying duplicates."""
    rows = [_started("a1", "attest:crucible:S7", "crucible"),
            _started("a2", "attest:crucible:S9", "crucible"),
            _result("a1", {"node_id": "S7", "verdict": "SOUND"}),
            _result("a2", {"node_id": "S9", "verdict": "SOUND"})]
    record = R.build_record(R.index(rows),
                            {"run_id": "wf_test", "path": "j", "sha256": "x", "rows": 4},
                            {"spawn_cap": 30, "spawn_reserve": 2})
    assert record["duplicate_labels"] == []
    assert len(record["crucible_verdicts"]) == 2


# --------------------------------------------------------------- the scrub

def test_a_machine_path_in_a_seat_payload_does_not_reach_the_record(tmp_path):
    # RED CONTROL: the forge seats report the files they changed as absolute
    # paths in their own worktrees. If the scrub stops working, this path
    # reaches the committed record verbatim.
    leak = r"C:\Users\Someone\.claude\worktrees\wf_d1494930-f0c-14\mcp_server.py"
    rows = [_started("a1", "attest:forge:S7", "forge"),
            _result("a1", {"node_id": "S7", "status": "committed",
                            "branch": "worktree-wf_d1494930-f0c-14",
                            "commit_sha": "460a5e57",
                            "files_changed": [leak]})]
    record = R.build_record(R.index(rows),
                            {"run_id": "wf_test", "path": "j", "sha256": "x", "rows": 2},
                            {"spawn_cap": 30, "spawn_reserve": 2})
    blob = json.dumps(record, ensure_ascii=False)
    assert leak not in blob
    assert "C:\\Users\\Someone" not in blob
    # an out-of-repo path is replaced WHOLE - the directory layout is not
    # narrowed to a basename, because the last segment of a drive path can
    # be the account name itself ("C:\Users\Account\Someone")
    assert "<path>" in blob


def test_the_seats_own_vocabulary_survives_the_scrub():
    # RED CONTROL, and the reason this scrub was rewritten. The seats write
    # SYNAPSE's endpoint name, its status tokens and ordinary prose with
    # slashes in it. A "slash means path" rule replaced all of them with
    # <path> in the first committed record.
    for text in ("the in-Houdini /mcp HTTP endpoint cannot refuse",
                 "degraded / version.mismatch",
                 "the version carrier graph (version / identity values)",
                 "WORKTREE / BRANCH CONFIRMATION",
                 "the propagator keeps writing <tree>/VERSION",
                 "row[\"leg\"]"):
        out = R.scrub(text)
        assert out == text, "scrub mangled prose: %r -> %r" % (text, out)


def test_a_url_survives_the_scrub_whole():
    # RED CONTROL: the seam leg's finding IS the port. A URL's scheme
    # contains "s:" and a slash, and a naive drive rule ate it.
    url = "ws://localhost:9999/synapse"
    assert R.scrub("returned readiness against %s" % url) == \
        "returned readiness against %s" % url
    assert R.scrub("read https://example.invalid/a/b") == "read https://example.invalid/a/b"


def test_a_real_path_is_still_scrubbed():
    # The other side of the same control: tightening the rule must not have
    # opened the hole it was meant to close.
    # "Example" is the repo's placeholder convention - the fixture must not
    # spell a real account name into a committed file.
    out = R.scrub("installed payload: C:\\Users\\Example\\AppData\\Local\\Programs\\X\\VERSION")
    assert "C:\\Users\\Example" not in out
    assert "<path>" in out
    out = R.scrub("reads ~/.synapse/bridge.json on every start")
    assert ".synapse/bridge.json" not in out
    assert "<path>" in out


def test_a_repo_relative_path_written_with_a_leading_slash_stays_readable(tmp_path):
    # The seats write repo-relative paths with a leading slash, because
    # they are talking about "<root>/python/synapse/core/release.py".
    # That names no machine location and it is evidence, so it stays.
    root = tmp_path / "root"
    (root / "python" / "synapse").mkdir(parents=True)
    R._ROOTS.clear()
    R._register_root(root)
    try:
        out = R.scrub("the accessor sits at /python/synapse/core/release.py")
    finally:
        R._ROOTS.clear()
    assert "/python/synapse/core/release.py" in out
    assert "<path>" not in out


def test_a_path_inside_the_repo_stays_readable(tmp_path):
    # A path is evidence. The one under the repo root must survive, because
    # a record that says <path> for every file says nothing at all.
    root = tmp_path / "root"
    (root / "python" / "synapse").mkdir(parents=True)
    inside = str(root / "python" / "synapse" / "core" / "protocol.py")
    R._ROOTS.clear()
    R._register_root(root)
    try:
        out = R.scrub("touched %s and C:\\Users\\Other\\elsewhere.py" % inside)
    finally:
        R._ROOTS.clear()
    assert "python/synapse/core/protocol.py" in out
    assert "C:\\Users\\Other" not in out


def test_the_written_files_carry_no_absolute_path(tmp_path):
    # The end-to-end shape: run the recorder for real and read what it wrote.
    leak = r"C:\Users\Someone\.claude\worktrees\wf-9\mcp_server.py"
    rows = [_started("a1", "attest:forge:S7", "forge"),
            _result("a1", {"node_id": "S7", "status": "committed", "branch": "b",
                            "commit_sha": "sha", "files_changed": [leak]}),
            _started("a2", "attest:synth", "synth"),
            _result("a2", _synth_payload())]
    journal = _write_journal(tmp_path, rows)
    state = tmp_path / "STATE.json"
    state.write_text(json.dumps({"caps": {"spawn_cap": 30, "spawn_reserve": 2}},
                                 indent=1) + "\n", encoding="utf-8", newline="")
    report = tmp_path / "WAVE-RECORD.md"

    argv = sys.argv
    sys.argv = ["record_final_wave.py", "--journal", str(journal), "--run-id", "wf_test",
                "--state", str(state), "--report", str(report)]
    try:
        assert R.main() == 0
    finally:
        sys.argv = argv

    written_state = state.read_text(encoding="utf-8")
    written_report = report.read_text(encoding="utf-8")
    for blob in (written_state, written_report):
        assert leak not in blob
        assert "C:\\Users\\Someone" not in blob
    # the record is in the state file, and it names the journal
    assert "wave_final_record" in written_state
    assert "wf_test" in written_state


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
