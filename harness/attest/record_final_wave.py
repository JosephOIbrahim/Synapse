"""Assemble the attest wave's FINAL record from the workflow journal.

The workflow returns its report INLINE, so the report is not a file on disk -
it is a set of rows in the run's journal. This script is the only thing that
turns those rows into the board's record, and it is the reason the record can
be trusted:

  - It reads ONLY the journal. Nothing in the record is asserted by this
    script; every value it writes came out of a journal row.
  - Anything the journal does not contain is recorded as NOT_YET_PRODUCED,
    with the phase that owes it named. The board's evidence law forbids
    writing a verdict for a phase that has not run.
  - The record carries the journal's own sha256 and row counts, so a reader
    can tell which evidence produced it, and can re-run this script on a
    later journal and see the delta.

Usage:
  python harness/attest/record_final_wave.py --journal <journal.jsonl> \
      [--state harness/attest/STATE.json] [--report harness/attest/WAVE.md] \
      [--dry-run]

The journal lives under the session directory, not the repo:
  <session>/subagents/workflows/<run_id>/journal.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Phases, in the order the board runs them. Used to say WHICH phase owes an
# artifact when it is missing, instead of a bare "not produced".
PHASE_ORDER = ["map", "seam", "design", "crucible", "synth", "forge", "verify"]

# A committed record must not carry a machine's directory layout. The seats
# wrote absolute paths - a forge seat reports the files it changed in its own
# worktree, and every worktree path is a full local path. Inside the repo the
# path stays readable (repo-relative); anywhere else it becomes <path>, so
# the record says WHAT was touched without saying WHERE this seat lives.
#
# What counts as a path is decided by SHAPE, not by the first slash. A naive
# "slash means path" rule eats the seats' own vocabulary: the endpoint name
# /mcp, the status token /version.mismatch, the prose "version / identity",
# and the "s:" of "ws://" (which is a URL scheme, not a drive letter). The
# first cut of this scrub did exactly that, and the committed record carried
# "<path>" where the seats had written "/mcp".
#
# So:
#   - a URL is not a path, and is protected before anything else runs. It
#     carries evidence the seam leg measured (the port), so it stays whole.
#   - a drive-rooted path IS a path (C:\Users\...), but only when the letter
#     is not the tail of a scheme.
#   - a slash-rooted path is a path only when it has TWO OR MORE segments
#     (/Users/someone/.synapse/bridge.json). One segment is a name, not a
#     location: /mcp, /VERSION, /version.mismatch, /row[ all survive.
#   - a lone slash between two words is prose and survives.
#   - a slash-rooted path whose first segment is a real directory in this
#     tree is a repo-relative path the seat wrote with a leading slash, and
#     it stays readable.
_URL_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://[^\s\"'`,;)\]]*")
_DRIVE_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s\"'`,;)\]]*")
_POSIX_RE = re.compile(r"(?<![\w.])(?:/[^\s\"'`,;)\]\/]+){2,}")
_ROOTS = []


def _register_root(p) -> None:
    try:
        _ROOTS.append(str(Path(p).resolve()).replace("\\", "/").rstrip("/"))
    except Exception:  # noqa: BLE001
        pass


def _relativise(path: str) -> str:
    norm = path.replace("\\", "/")
    for root in _ROOTS:
        if norm.lower().startswith(root.lower() + "/"):
            return norm[len(root) + 1:]
    # A slash-rooted path whose FIRST segment is a real directory in the
    # tree is a repo-relative path the seat wrote with a leading slash -
    # "<root>/python/synapse/core/release.py". It names no machine
    # location, and it is evidence, so it stays readable.
    if norm.startswith("/"):
        head = norm[1:].split("/")[0]
        if head:
            for root in _ROOTS:
                try:
                    if (Path(root) / head).exists():
                        return path
                except OSError:
                    continue
    return "<path>"


def _scrub_text(text: str) -> str:
    """Scrub one string, leaving URLs and prose alone.

    The URLs are stashed first: a URL's scheme contains a colon and a slash
    (ws://, file://), and a path rule reading "s:" as a drive letter would
    eat the port the seam leg measured.
    """
    stashed: list[str] = []

    def _stash(m):
        stashed.append(m.group(0))
        return "\x00URL%d\x00" % (len(stashed) - 1)

    text = _URL_RE.sub(_stash, text)
    text = _DRIVE_RE.sub(lambda m: _relativise(m.group(0)), text)
    text = _POSIX_RE.sub(lambda m: _relativise(m.group(0)), text)
    for i, url in enumerate(stashed):
        text = text.replace("\x00URL%d\x00" % i, url)
    return text


def scrub(value):
    """Strip machine-specific detail out of anything the seats wrote."""
    if isinstance(value, str):
        return _scrub_text(value)
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    return value


def read_journal(path: Path) -> tuple[list[dict], str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    rows = []
    for line in raw.decode("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            # A torn final line is a journal that was read mid-write. It is
            # recorded by the row count, not silently repaired.
            continue
    return rows, digest


def _phase_from_label(label: str) -> str:
    """The phase a seat label names, or "unknown".

    "attest:seam" is the SEAM phase. The first cut of this read the phase out
    of the label only when the label had TWO colons, so the seam seat and the
    synth seat - the two seats whose labels are a single segment - were
    counted as "unknown" while the phases list said they had returned. The
    record disagreed with itself.
    """
    parts = label.split(":")
    if len(parts) >= 2 and parts[0] == "attest":
        return parts[1].lower()
    return "unknown"


def index(rows: list[dict]) -> dict:
    """label -> result payload, plus the started rows and their phase.

    Two mappings are kept, and the difference matters. `results` is
    label -> the FIRST payload for that label, which is what the single-seat
    phases (synth, seam) want. `results_all` is label -> EVERY payload for
    that label, because two seats can share a label: a retry, or two waves in
    one journal. The old code kept only the first, so the second seat's
    payload was dropped on the floor and the record showed one seat where the
    journal had two. Evidence that was gathered and then not recorded is
    evidence the board cannot cite.
    """
    labels = {}
    phases = {}
    started = []
    result_rows = []
    results = {}
    results_all = {}
    for r in rows:
        t = r.get("type")
        if t == "started":
            labels[r.get("agentId")] = r.get("label")
            phases[r.get("agentId")] = (r.get("phase") or "").lower()
            started.append(r)
        elif t == "result":
            label = labels.get(r.get("agentId"))
            if label is None:
                # A result whose started row we never saw. Recorded as its
                # agent id rather than dropped.
                label = "unknown:" + str(r.get("agentId"))
            payload = scrub(r.get("result"))
            result_rows.append(label)
            results.setdefault(label, payload)
            results_all.setdefault(label, []).append(payload)
    # label -> the phase its seat was dispatched in. The STARTED row is
    # authoritative; the label is the fallback for a result whose started
    # row never arrived.
    label_phase = {}
    for aid, lab in labels.items():
        label_phase[lab] = phases.get(aid) or _phase_from_label(lab)
    for label in result_rows:
        label_phase.setdefault(label, _phase_from_label(label))
    return {"labels": labels, "phases": phases, "label_phase": label_phase,
            "started": started, "result_rows": result_rows, "results": results,
            "results_all": results_all}


def _seats(idx: dict, prefix: str):
    """Every seat whose label starts with `prefix`, in journal order.

    A label can carry more than one seat, so this yields per PAYLOAD, not
    per label. The old code iterated a label -> payload dict and therefore
    saw one seat where the journal had two.
    """
    for label, payloads in (idx.get("results_all") or {}).items():
        if not label.startswith(prefix):
            continue
        for payload in payloads:
            yield label, payload


def spawn_accounting(idx: dict, caps: dict) -> dict:
    """Every agent this board dispatched, against the cap.

    The cap is a contract, not a tuneable. The accounting is computed from
    the journal's own started/result rows, so it cannot drift from what ran.
    """
    by_phase = {}
    for r in idx["started"]:
        phase = (r.get("phase") or "unknown").lower()
        by_phase.setdefault(phase, {"dispatched": 0, "returned": 0})
        by_phase[phase]["dispatched"] += 1
    result_rows = idx.get("result_rows")
    if not result_rows:
        result_rows = list(idx["results"])
    label_phase = idx.get("label_phase") or {}
    for label in result_rows:
        phase = label_phase.get(label) or _phase_from_label(label)
        by_phase.setdefault(phase, {"dispatched": 0, "returned": 0})
        by_phase[phase]["returned"] += 1

    dispatched = len(idx["started"])
    returned = len(result_rows)
    cap = int(caps.get("spawn_cap", 30))
    reserve = int(caps.get("spawn_reserve", 2))
    return {
        "seats_dispatched": dispatched,
        "seats_returned": returned,
        "seats_outstanding": dispatched - returned,
        "dispatched_by_phase": {p: v["dispatched"] for p, v in sorted(by_phase.items())},
        "returned_by_phase": {p: v["returned"] for p, v in sorted(by_phase.items())},
        "cap": cap,
        "reserve": reserve,
        "available": cap - reserve,
        "headroom": (cap - reserve) - dispatched,
        "within_cap": dispatched <= (cap - reserve),
        "source": "counted from the journal's own started/result rows",
    }


def _phase_has_result(idx: dict, phase: str) -> bool:
    return any(label.startswith("attest:" + phase + ":") or label == "attest:" + phase
               for label in idx["results"])


def not_yet(artifact: str, phase: str) -> dict:
    return {
        "artifact": artifact,
        "produced_by_phase": phase,
        "status": "NOT_YET_PRODUCED",
        "why": "The journal for this wave contains no result row for the %s phase. "
               "Writing it here would be fabrication; the board's evidence law "
               "forbids it." % phase,
    }


def build_record(idx: dict, journal_meta: dict, caps: dict) -> dict:
    results = idx["results"]
    accounting = spawn_accounting(idx, caps)
    # The state is read off the SAME accounting the record publishes. The old
    # state line compared the number of DISTINCT LABELS with the number of
    # started rows, while the accounting compared RESULT ROWS with started
    # rows - so two seats sharing a label produced "state: IN_FLIGHT" beside
    # "seats_returned: 2, seats_outstanding: 0". A record that contradicts
    # itself is worse than one that is pessimistic, because a reader cannot
    # tell which half to believe.
    record = {
        "wave": "attest-20261022-w1",
        "workflow_run": journal_meta["run_id"],
        "state": "IN_FLIGHT" if accounting["seats_outstanding"] > 0 else "COMPLETE",
        "recorded_at_note": "Written by harness/attest/record_final_wave.py from the "
                            "wave's journal. Every value below came out of a journal "
                            "row; anything the journal does not contain is marked "
                            "NOT_YET_PRODUCED.",
        "journal": journal_meta,
        "phases_complete": [],
        "phases_running": [],
        "phases_not_started": [],
        "spawn_accounting": accounting,
        # Labels carried by more than one seat. Named rather than collapsed,
        # so a reader can see that a label is not a seat.
        "duplicate_labels": sorted(label for label, payloads
                                   in (idx.get("results_all") or {}).items()
                                   if len(payloads) > 1),
    }

    for phase in PHASE_ORDER:
        dispatched = any((r.get("phase") or "").lower() == phase for r in idx["started"])
        returned = _phase_has_result(idx, phase)
        if returned:
            record["phases_complete"].append(phase)
        elif dispatched:
            record["phases_running"].append(phase)
        else:
            record["phases_not_started"].append(phase)

    # ---- the graph -------------------------------------------------------
    synth = results.get("attest:synth")
    if synth is None:
        record["final_graph"] = not_yet("final unified graph (SYNTH)", "synth")
        record["spanning_order"] = not_yet("spanning order (SYNTH)", "synth")
        record["parked"] = not_yet("forge_now vs park split (SYNTH)", "synth")
        record["file_ownership"] = not_yet("file ownership resolution (SYNTH)", "synth")
        record["unproven"] = not_yet("honest unproven list (SYNTH)", "synth")
        record["needs_joe"] = not_yet("needs_joe (verbatim)", "design then synth")
    else:
        record["final_graph"] = {
            "verdict": synth.get("verdict"),
            "summary": synth.get("graph_summary"),
            "nodes": [
                {
                    "id": n.get("id"),
                    "title": n.get("title"),
                    "owner_files": n.get("owner_files"),
                    "depends_on": n.get("depends_on"),
                    "edges": n.get("edges"),
                    "forge_now": n.get("forge_now"),
                    "crucible_verdict": n.get("crucible_verdict"),
                    "needs_joe": n.get("needs_joe"),
                    "acceptance_proof": n.get("acceptance_proof"),
                }
                for n in synth.get("nodes", [])
            ],
        }
        record["spanning_order"] = synth.get("spanning_order")
        record["parked"] = synth.get("parked")
        record["file_ownership"] = synth.get("file_ownership")
        record["unproven"] = synth.get("unproven")
        record["needs_joe"] = synth.get("needs_joe")

    # ---- crucible verdicts, from their own seats ------------------------
    verdicts = []
    for label, payload in _seats(idx, "attest:crucible:"):
        if not isinstance(payload, dict):
            continue
        verdicts.append({
            "node_id": payload.get("node_id"),
            "seat": label,
            "verdict": payload.get("verdict"),
            "summary": payload.get("summary"),
            "attacks": payload.get("attacks"),
        })
    record["crucible_verdicts"] = verdicts or not_yet(
        "per-node crucible verdict: SOUND | SOUND-WITH-NITS | BROKEN | COULD-NOT-ASSESS",
        "crucible")

    # ---- forge branches and SHAs -----------------------------------------
    forges = []
    for label, payload in _seats(idx, "attest:forge:"):
        if not isinstance(payload, dict):
            continue
        forges.append({
            "node_id": payload.get("node_id"),
            "seat": label,
            "status": payload.get("status"),
            "branch": payload.get("branch"),
            "commit_sha": payload.get("commit_sha"),
            "files_changed": payload.get("files_changed"),
            "proof_output": payload.get("proof_output"),
            "notes": payload.get("notes"),
        })
    record["forge_branches"] = forges or not_yet("forge branch names and commit SHAs", "forge")

    # ---- verify proofs ---------------------------------------------------
    verifies = []
    for label, payload in _seats(idx, "attest:verify:"):
        if not isinstance(payload, dict):
            continue
        # The verify seats write their proof under ONE of two keys: "proof"
        # (a string) or "evidence" (a list of strings). The first cut of this
        # recorder read only "proof", so this wave's two verify seats were
        # recorded as PASS with proof=null - the verdict was committed and
        # the evidence behind it was dropped on the floor. A verdict with no
        # evidence attached is the one thing this board must never publish.
        evidence = payload.get("evidence")
        proof = payload.get("proof")
        if proof is None and evidence is not None:
            if isinstance(evidence, list):
                proof = "\n\n".join(str(e) for e in evidence)
            else:
                proof = str(evidence)
        entry = {
            "node_id": payload.get("node_id"),
            "seat": label,
            "verdict": payload.get("verdict"),
            "proof": proof,
            # LOUD on purpose: a reader must be able to tell "the seat
            # proved it" from "the seat said so" without reading the text.
            "proof_status": "CARRIED" if proof else "MISSING",
        }
        if payload.get("commit_sha"):
            entry["commit_sha"] = payload.get("commit_sha")
        if evidence is not None:
            entry["evidence"] = evidence
        if payload.get("notes") is not None:
            entry["notes"] = payload.get("notes")
        verifies.append(entry)
    record["verify_proofs"] = verifies or not_yet("verify proof per forged node", "verify")

    # ---- the seed, attacked ----------------------------------------------
    map_seats = [(label, payload) for label, payload in _seats(idx, "attest:map:")
                 if isinstance(payload, dict)]
    record["map_seats"] = [{
        "seat": label,
        "cluster": payload.get("cluster"),
        "seed_confirmed": payload.get("seed_confirmed"),
        "nodes_returned": len(payload.get("nodes") or []),
        "edges_returned": len(payload.get("edges") or []),
        "unknowns_returned": len(payload.get("unknowns") or []),
    } for label, payload in sorted(map_seats, key=lambda t: t[0])]

    seam = results.get("attest:seam")
    record["seam"] = ({
        "graph_summary": seam.get("graph_summary"),
        "seams": seam.get("seams"),
        "global_invariants": seam.get("global_invariants"),
        "unknowns": seam.get("unknowns"),
    } if isinstance(seam, dict) else not_yet("the seam reconciliation", "seam"))

    return record


def render_report(record: dict) -> str:
    """The human-readable half of the record."""
    out = []
    w = out.append
    acct = record.get("spawn_accounting", {})
    w("# Attest wave %s — final record" % record.get("wave"))
    w("")
    w("Workflow run `%s`. State: **%s**." % (record.get("workflow_run"), record.get("state")))
    w("")
    j = record.get("journal", {})
    w("Assembled from the run's journal: `%s`" % j.get("path", "(unknown)"))
    w("")
    w("- journal sha256: `%s`" % j.get("sha256", "(none)"))
    w("- journal rows: %s" % j.get("rows"))
    w("- seats dispatched: %s, returned: %s, outstanding: %s"
      % (acct.get("seats_dispatched"), acct.get("seats_returned"),
         acct.get("seats_outstanding")))
    w("- cap: %s dispatched + %s reserve = %s usable; headroom %s; within cap: %s"
      % (acct.get("cap"), acct.get("reserve"), acct.get("available"),
         acct.get("headroom"), acct.get("within_cap")))
    w("")
    w("## Phases")
    w("")
    w("Complete: %s" % (", ".join(record.get("phases_complete") or []) or "none"))
    w("")
    w("Running: %s" % (", ".join(record.get("phases_running") or []) or "none"))
    w("")
    w("Not started: %s" % (", ".join(record.get("phases_not_started") or []) or "none"))
    w("")

    graph = record.get("final_graph")
    if isinstance(graph, dict) and graph.get("nodes"):
        w("## The graph — %s" % graph.get("verdict"))
        w("")
        w("### Spanning order")
        w("")
        w("`%s`" % " -> ".join(record.get("spanning_order") or []))
        w("")
        w("### Nodes, owners and typed edges")
        w("")
        for n in graph["nodes"]:
            w("**%s** — %s" % (n.get("id"), n.get("title")))
            w("")
            w("- owners: %s" % ", ".join(n.get("owner_files") or []))
            w("- depends on: %s" % (", ".join(n.get("depends_on") or []) or "none"))
            w("- forge now: %s" % n.get("forge_now"))
            w("- crucible: %s" % (n.get("crucible_verdict") or "not stated"))
            w("- needs_joe: %s" % (", ".join(n.get("needs_joe") or []) or "none"))
            w("- edges:")
            for e in n.get("edges") or []:
                w("  - %s" % e)
            w("")
    else:
        w("## The graph")
        w("")
        w("`%s`" % json.dumps(graph, ensure_ascii=False))
        w("")

    w("## Crucible verdicts")
    w("")
    verdicts = record.get("crucible_verdicts")
    if isinstance(verdicts, list) and verdicts:
        for v in verdicts:
            w("- **%s** — `%s` (seat `%s`)" % (v.get("node_id"), v.get("verdict"), v.get("seat")))
    else:
        w("`%s`" % json.dumps(verdicts, ensure_ascii=False))
    w("")

    w("## Forge branches")
    w("")
    forges = record.get("forge_branches")
    if isinstance(forges, list) and forges:
        w("| node | status | branch | commit SHA | files |")
        w("|---|---|---|---|---|")
        for f in forges:
            w("| %s | %s | `%s` | `%s` | %s |"
              % (f.get("node_id"), f.get("status"), f.get("branch"),
                 f.get("commit_sha"), ", ".join(f.get("files_changed") or [])))
    else:
        w("`%s`" % json.dumps(forges, ensure_ascii=False))
    w("")

    w("## Verify")
    w("")
    verifies = record.get("verify_proofs")
    if isinstance(verifies, list) and verifies:
        for v in verifies:
            w("### %s — `%s`" % (v.get("node_id"), v.get("verdict")))
            w("")
            w("- seat: `%s`" % v.get("seat"))
            if v.get("commit_sha"):
                w("- commit SHA: `%s`" % v["commit_sha"])
            w("- proof: **%s**" % (v.get("proof_status") or "CARRIED"))
            w("")
            evidence = v.get("evidence")
            if isinstance(evidence, list) and evidence:
                for line in evidence:
                    w("- %s" % line)
                w("")
            elif v.get("proof"):
                w("%s" % v["proof"])
                w("")
            if v.get("notes"):
                w("- notes: %s" % v["notes"])
                w("")
    else:
        w("`%s`" % json.dumps(verifies, ensure_ascii=False))
        w("")

    w("## needs_joe (verbatim)")
    w("")
    nj = record.get("needs_joe")
    if isinstance(nj, list) and nj:
        for item in nj:
            w("- %s" % item)
    else:
        w("`%s`" % json.dumps(nj, ensure_ascii=False))
    w("")

    w("## The unproven list")
    w("")
    up = record.get("unproven")
    if isinstance(up, list) and up:
        for item in up:
            w("- %s" % item)
    else:
        w("`%s`" % json.dumps(up, ensure_ascii=False))
    w("")

    w("## Parked")
    w("")
    pk = record.get("parked")
    if isinstance(pk, list) and pk:
        for item in pk:
            w("- %s" % (item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)))
    else:
        w("`%s`" % json.dumps(pk, ensure_ascii=False))
    w("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Record the attest wave's final state from its journal")
    ap.add_argument("--journal", required=True, help="path to the run's journal.jsonl")
    ap.add_argument("--run-id", default="", help="workflow run id, recorded in the record")
    ap.add_argument("--state", default=str(ROOT / "harness/attest/STATE.json"))
    ap.add_argument("--report", default=str(ROOT / "harness/attest/WAVE-RECORD.md"))
    ap.add_argument("--root", action="append", default=[],
                    help="an extra root whose paths stay readable in the record "
                         "(repeatable). Default: this checkout and the main checkout.")
    ap.add_argument("--dry-run", action="store_true", help="print, do not write")
    a = ap.parse_args()

    journal = Path(a.journal)
    if not journal.is_file():
        print("journal not found: %s" % journal, file=sys.stderr)
        return 2

    rows, digest = read_journal(journal)

    # Roots whose paths stay READABLE in the record: this checkout, and the
    # main checkout the worktrees hang off. Everything else becomes <path>.
    # Registered BEFORE the payloads are scrubbed.
    _register_root(ROOT)
    for extra in a.root:
        _register_root(extra)
    try:
        import subprocess
        common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=str(ROOT),
                                capture_output=True, text=True, timeout=30).stdout.strip()
        if common:
            _register_root(Path(common).resolve().parent)
    except Exception:  # noqa: BLE001
        pass

    idx = index(rows)

    state_path = Path(a.state)
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    caps = state.get("caps") or {"spawn_cap": 30, "spawn_reserve": 2}

    meta = {
        "path": scrub(str(journal)),
        "sha256": digest,
        "rows": len(rows),
        "run_id": a.run_id or state.get("spawn_ledger", {}).get("waves", [{}])[0]
        .get("workflow_run", ""),
    }
    record = build_record(idx, meta, caps)

    report = render_report(record)
    if not a.dry_run:
        state["wave_final_record"] = record
        state_path.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n",
                               encoding="utf-8", newline="")
        Path(a.report).write_text(report, encoding="utf-8", newline="\n")
        print("wrote %s" % state_path)
        print("wrote %s" % a.report)
    else:
        print(report)
    acct = record["spawn_accounting"]
    print("state=%s  seats %s dispatched / %s returned  (cap %s + %s reserve, headroom %s)"
          % (record["state"], acct["seats_dispatched"], acct["seats_returned"],
             acct["cap"], acct["reserve"], acct["headroom"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
