#!/usr/bin/env python3
"""E1 - dead surface: which registered tools have NO call evidence?

READ-ONLY. Writes one artifact under harness/notes/econ/. Reads the local audit
trail in memory and persists ONLY operation-name counts - never a decrypted
record, never a payload.

A tool that is registered but never invoked costs its full definition on every
single turn. S1 already found five Solaris tools registered, tested and
completely unreachable, so this is a live failure mode in this codebase, not a
hypothetical one.

Evidence is gathered at three DIFFERENT strengths and they are never conflated:

  REACHABILITY  (VERIFIED-DERIVED) Does the tool's command_type resolve to a
                handler? SynapseHandler builds standalone - no Houdini needed -
                so its registry is ground truth. A tool whose command_type is
                absent is STRUCTURALLY DEAD: it cannot be called at all, and its
                definition is pure cost. This is the S1 failure mode.
  CALL          (VERIFIED-RUNTIME) Does the local encrypted audit trail record
                the operation? ~/.synapse/audit/*.jsonl is the only artifact on
                this machine that records real invocations.
  MENTION       (VERIFIED-STATIC) Does the name appear in tests/docs/scripts?
                A name in a doc table is NOT a call. Reported for completeness
                and explicitly ranked lowest.

CONTAMINATION, stated up front because it decides how much CALL evidence is
worth: this repo has already been burned by exactly this - ~/.synapse/logs/
synapse.log holds test-authored INFO records, and 4,795 "epoch closed" lines
that read as production RSI were all pytest (harness/notes/RSI_SURFACE_AUDIT.md).
The audit trail has the same exposure. This producer therefore flags any session
containing an operation that is NOT a registered tool or command type as
TEST-SUSPECT, and reports every per-tool count twice: all sessions, and
excluding suspect sessions. Neither figure is authoritative on its own and the
artifact says so.

SCOPE, stated because it bounds every conclusion: this is ONE developer machine
over the audit trail's date span. Absence here means "never called on this host",
which is evidence, not proof, of a tool nobody uses. It cannot see other
installs. That limit is recorded in the artifact rather than left for a reader
to discover.

Emits: harness/notes/econ/E1_call_evidence.json
Usage: python harness/notes/econ/econ_call_evidence.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "python"))

OUT_FP = Path(__file__).resolve().parent / "E1_call_evidence.json"
AUDIT_DIR = Path(os.path.expanduser("~")) / ".synapse" / "audit"

# SessionJournal (python/synapse/panel/session_journal.py) writes one line per
# tool dispatch, and unlike the audit trail it records the MCP TOOL NAME and is
# NOT gated on mutation - so it is the only source that can see a read-only
# tool being called. _resolve_log_dir():97 puts it at <hipfile-dir>/claude/ when
# hou is importable, and at <tempdir>/synapse_journal otherwise. That fallback
# path is EXACTLY the path pytest takes, because `import hou` fails under
# pytest - which makes journal provenance decidable from the path alone.
TEST_MARKER_RE = re.compile(r"^(fake|test|mock|dummy|stub|c5|probe)[_A-Z]|^test$")
JOURNAL_TOOL_RE = re.compile(r"^\[\d\d:\d\d:\d\d\]\s+TOOL\s+([A-Za-z0-9_]+):")


def _journal_candidates() -> list[tuple[Path, str, str]]:
    """(path, provenance, why). No hardcoded user paths - all derived."""
    import tempfile

    home = Path(os.path.expanduser("~"))
    tmp = Path(tempfile.gettempdir())
    out: list[tuple[Path, str, str]] = [
        (home / "claude" / "journal.log", "production",
         "hipfile-relative journal for scenes saved under the user home; "
         "written only when hou was importable (session_journal.py:101)"),
        (tmp / "synapse_journal" / "journal.log", "test",
         "the no-hou fallback dir (session_journal.py:110) - the path pytest "
         "necessarily takes, since `import hou` fails under pytest"),
        (REPO_ROOT / "claude" / "journal.log", "test",
         "journal for scenes saved into the repo working tree - dev/test scratch"),
        (REPO_ROOT / "tests" / "fixtures" / "claude" / "journal.log", "test",
         "checked-in test fixture"),
    ]
    # This leg runs in a git worktree, so REPO_ROOT is not the main checkout.
    # Journals written against the main tree are invisible from here unless the
    # main root is added explicitly.
    if ".claude" in REPO_ROOT.parts and "worktrees" in REPO_ROOT.parts:
        main_root = REPO_ROOT.parents[2]
        out += [
            (main_root / "claude" / "journal.log", "test",
             "journal for scenes saved into the main repo working tree - dev scratch"),
            (main_root / "tests" / "fixtures" / "claude" / "journal.log", "test",
             "checked-in test fixture in the main checkout"),
        ]
    seen = {p.resolve() for p, _, _ in out if p.exists()}
    for extra in sorted(home.glob("*/claude/journal.log")):
        if extra.resolve() not in seen:
            out.append((extra, "production", "discovered hipfile-relative journal"))
    return out


def _scan_journals(known_names: set[str]) -> dict:
    """Parse SessionJournal files. Tool NAMES, so read-only tools are visible."""
    srcs = []
    prod: Counter[str] = Counter()
    test: Counter[str] = Counter()
    for fp, prov, why in _journal_candidates():
        if not fp.exists():
            srcs.append({"path": str(fp), "exists": False, "provenance": prov, "why": why})
            continue
        counts: Counter[str] = Counter()
        lines = 0
        for line in fp.read_text(encoding="utf-8", errors="replace").splitlines():
            lines += 1
            m = JOURNAL_TOOL_RE.match(line.strip())
            if m:
                counts[m.group(1)] += 1
        unknown = sorted(set(counts) - known_names)
        unknown_records = sum(counts[u] for u in unknown)
        total_records = sum(counts.values())
        unknown_share = (unknown_records / total_records) if total_records else 0.0
        # Downgrade production -> test on EVIDENCE, not on the mere presence of
        # an unrecognised name. A first cut downgraded the main production
        # journal on one record: `hrudini_create_noe`, plainly a fat-fingered
        # `houdini_create_node` typed by a human, 1 of 1,705 records. That is a
        # user typo, not a fixture, and discarding 1,705 real dispatches over it
        # would have manufactured dead surface out of a spelling mistake.
        # So: downgrade on an explicit TEST MARKER, or when unrecognised names
        # are a material share of the file.
        markers = sorted(u for u in unknown
                         if TEST_MARKER_RE.match(u))
        material = unknown_share > 0.05
        effective = "test" if (prov == "test" or markers or material) else "production"
        (prod if effective == "production" else test).update(counts)
        srcs.append({
            "path": str(fp), "exists": True, "lines": lines,
            "tool_records": sum(counts.values()), "distinct_tools": len(counts),
            "declared_provenance": prov, "effective_provenance": effective,
            "unknown_tool_names": unknown,
            "unknown_records": unknown_records,
            "unknown_share": round(unknown_share, 5),
            "test_marker_names": markers,
            "downgrade_reason": ("declared-by-path" if prov == "test" else
                                 "test-marker-name" if markers else
                                 "unknown-share>5%" if material else None),
            "why": why,
            "downgraded": effective != prov,
        })
    return {
        "available": any(s.get("exists") for s in srcs),
        "sources": srcs,
        "_prod": dict(prod),
        "_test": dict(test),
        "production_records": sum(prod.values()),
        "test_records": sum(test.values()),
        "note": (
            "The journal is the ONLY runtime source that records read-only tool "
            "calls: session_journal is written from mcp/tools.py:148 on every "
            "dispatch, with no mutation gate. Its weakness is the mirror of the "
            "audit's - no date on the timestamp (session_journal.py:139 formats "
            "%H:%M:%S only), so records cannot be ordered across days."
        ),
    }

# Surfaces searched for static MENTIONs, and what a hit there is worth.
STATIC_SURFACES = {
    "tests": "tests",
    "python_tests": "python/synapse/tests",
    "scripts": "scripts",
    "panel": "python/synapse/panel",
    "docs": "docs",
    "harness_notes": "harness/notes",
    "rag": "rag",
}


def _handler_registry() -> tuple[set[str], str]:
    """Command types with a live handler. SynapseHandler builds without hou."""
    from synapse.server.handlers import SynapseHandler

    h = SynapseHandler()
    reg = h._registry
    rt = getattr(reg, "registered_types", None)
    if callable(rt):
        types = set(rt())
    elif isinstance(rt, (list, tuple, set)):
        types = set(rt)
    else:  # pragma: no cover
        types = set(getattr(reg, "_handlers", {}))
    return types, "synapse.server.handlers.SynapseHandler()._registry.registered_types"


def _scan_audit(known_ops: set[str]) -> dict:
    """Stream the encrypted audit trail. Accumulates counts only."""
    if not AUDIT_DIR.is_dir():
        return {"available": False, "reason": f"{AUDIT_DIR} does not exist"}

    from synapse.core.crypto import get_crypto

    ce = get_crypto()
    files = sorted(AUDIT_DIR.glob("audit_*.jsonl"))
    if not files:
        return {"available": False, "reason": f"no audit_*.jsonl under {AUDIT_DIR}"}

    op_counts: Counter[str] = Counter()
    op_first: dict[str, str] = {}
    op_last: dict[str, str] = {}
    op_sessions: dict[str, set[str]] = defaultdict(set)
    session_ops: dict[str, set[str]] = defaultdict(set)
    lines_total = decoded = failed = 0

    for fp in files:
        with open(fp, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                lines_total += 1
                try:
                    rec = json.loads(
                        ce.decrypt_line(line) if line.startswith("SYNAPSE_ENC_V1:") else line)
                except Exception:
                    failed += 1
                    continue
                decoded += 1
                op = rec.get("operation") or ""
                if not op:
                    continue
                sid = str(rec.get("session_id") or "")
                ts = str(rec.get("timestamp_utc") or "")
                op_counts[op] += 1
                op_sessions[op].add(sid)
                session_ops[sid].add(op)
                if op not in op_first or (ts and ts < op_first[op]):
                    op_first[op] = ts
                if op not in op_last or (ts and ts > op_last[op]):
                    op_last[op] = ts

    # A session containing an operation that is neither a registered tool, a
    # registered command type, nor a known system event is almost certainly a
    # test fixture driving the audit log directly. Flag the whole session.
    #
    # SYSTEM_OPS is an allowlist verified by inspection, not a convenience: the
    # HumanGate lifecycle (CLAUDE.md 1.2.1, GateProposal PROPOSED -> APPROVED)
    # legitimately writes gate_proposal / gate_decision entries that are not
    # tools. Without this, every consent-gated production session was being
    # mis-flagged as a test session and the "clean" counts were understated.
    SYSTEM_OPS = {"gate_proposal", "gate_decision"}
    unknown_ops = {o for o in op_counts if o not in known_ops and o not in SYSTEM_OPS}
    suspect_sessions = {s for s, ops in session_ops.items() if ops & unknown_ops}

    clean_counts: Counter[str] = Counter()
    for fp in files:  # second pass, counting only non-suspect sessions
        with open(fp, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(
                        ce.decrypt_line(line) if line.startswith("SYNAPSE_ENC_V1:") else line)
                except Exception:
                    continue
                op = rec.get("operation") or ""
                sid = str(rec.get("session_id") or "")
                if op and sid not in suspect_sessions:
                    clean_counts[op] += 1

    return {
        "available": True,
        "audit_dir": str(AUDIT_DIR),
        "files": len(files),
        "date_span": [files[0].name, files[-1].name],
        "lines_total": lines_total,
        "decoded": decoded,
        "decode_failed": failed,
        "distinct_operations": len(op_counts),
        "distinct_sessions": len(session_ops),
        "unknown_operation_names": sorted(unknown_ops)[:60],
        "unknown_operation_count": len(unknown_ops),
        "suspect_sessions": len(suspect_sessions),
        "suspect_session_share": (round(len(suspect_sessions) / len(session_ops), 4)
                                  if session_ops else None),
        "_op_counts": dict(op_counts),
        "_op_counts_clean": dict(clean_counts),
        "_op_first": op_first,
        "_op_last": op_last,
        "_op_sessions": {k: len(v) for k, v in op_sessions.items()},
    }


def _static_mentions(names: list[str]) -> dict:
    """Word-boundary counts per surface via git grep. R5: no substring hits."""
    out: dict[str, dict[str, int]] = {n: {} for n in names}
    for label, rel in STATIC_SURFACES.items():
        d = REPO_ROOT / rel
        if not d.exists():
            for n in names:
                out[n][label] = 0
            continue
        # one pass per surface: grep every name at once, count per name
        proc = subprocess.run(
            ["git", "grep", "-oh", "-E", r"\b(" + "|".join(re.escape(n) for n in names) + r")\b",
             "--", rel],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        c = Counter(proc.stdout.split())
        for n in names:
            out[n][label] = c.get(n, 0)
    return out


def main() -> int:
    from synapse.mcp._tool_registry import TOOL_DEFS
    from synapse.mcp.tools import get_tools
    from synapse.core.protocol import normalize_command_type
    from synapse.server.handlers import _READ_ONLY_COMMANDS as READ_ONLY_COMMANDS

    tools = get_tools()
    cmd_of = {d[0]: d[1] for d in TOOL_DEFS}
    names = [t["name"] for t in tools]

    handler_types, handler_source = _handler_registry()

    # ---- REACHABILITY ------------------------------------------------------
    reach = {}
    for n in names:
        ct = cmd_of.get(n)
        direct = ct in handler_types
        norm = normalize_command_type(ct) if ct else None
        via_alias = (not direct) and norm in handler_types
        reach[n] = {
            "command_type": ct,
            "handler_direct": direct,
            "handler_via_normalise": via_alias,
            "reachable": bool(direct or via_alias),
        }

    known_ops = set(names) | set(cmd_of.values()) | handler_types

    # ---- CALL: two sources with complementary blind spots ------------------
    audit = _scan_audit(known_ops)
    journals = _scan_journals(set(names))
    j_prod = journals.pop("_prod", {})
    j_test = journals.pop("_test", {})
    op_counts = audit.pop("_op_counts", {}) if audit.get("available") else {}
    op_clean = audit.pop("_op_counts_clean", {}) if audit.get("available") else {}
    op_first = audit.pop("_op_first", {}) if audit.get("available") else {}
    op_last = audit.pop("_op_last", {}) if audit.get("available") else {}
    op_sess = audit.pop("_op_sessions", {}) if audit.get("available") else {}
    for k in ("_op_counts", "_op_counts_clean", "_op_first", "_op_last", "_op_sessions"):
        audit.pop(k, None)

    # ---- MENTION -----------------------------------------------------------
    mentions = _static_mentions(names)

    # ---- per-tool roll-up + classification --------------------------------
    census_fp = Path(__file__).resolve().parent / "E1_surface_census.json"
    tok_of: dict[str, int] = {}
    if census_fp.exists():
        cj = json.loads(census_fp.read_text(encoding="utf-8"))
        tok_of = {r["name"]: r["total_tokens"] for r in cj["stats"]["tools"]}

    rows = []
    for n in names:
        ct = cmd_of.get(n) or ""
        calls = op_counts.get(n, 0) + (op_counts.get(ct, 0) if ct != n else 0)
        calls_clean = op_clean.get(n, 0) + (op_clean.get(ct, 0) if ct != n else 0)
        jp = j_prod.get(n, 0)
        jt = j_test.get(n, 0)
        m = mentions[n]
        m_total = sum(m.values())
        r = reach[n]
        auditable = ct not in READ_ONLY_COMMANDS
        any_prod = (calls > 0) or (jp > 0)
        if not r["reachable"]:
            cls = "STRUCTURALLY_DEAD"
        elif any_prod:
            cls = "CALLED"
        elif jt > 0:
            cls = "CALLED_TEST_ONLY"
        elif not auditable:
            # handlers.py:531 gates the audit write on `if _mutating`, and
            # _mutating is `cmd_type not in _READ_ONLY_COMMANDS`. For these
            # tools the audit trail CANNOT record a call, so "never called"
            # here is a check that could never have returned "called" - a
            # Law 1 decoration. Absence is unmeasured, not measured-absent.
            cls = "AUDIT_BLIND_UNMEASURABLE"
        else:
            cls = "NO_RUNTIME_EVIDENCE"
        rows.append({
            "name": n,
            "command_type": ct,
            "tokens": tok_of.get(n),
            "reachable": r["reachable"],
            "handler_direct": r["handler_direct"],
            "handler_via_normalise": r["handler_via_normalise"],
            "audit_calls_all_sessions": calls,
            "audit_calls_excluding_suspect": calls_clean,
            "auditable": ct not in READ_ONLY_COMMANDS,
            "journal_calls_production": jp,
            "journal_calls_test": jt,
            "audit_sessions": op_sess.get(n, 0) + (op_sess.get(ct, 0) if ct != n else 0),
            "audit_first_seen": op_first.get(n) or op_first.get(ct),
            "audit_last_seen": op_last.get(n) or op_last.get(ct),
            "static_mentions": m,
            "static_mentions_total": m_total,
            "classification": cls,
        })

    by_class: dict[str, list[str]] = defaultdict(list)
    tokens_by_class: Counter[str] = Counter()
    for r in rows:
        by_class[r["classification"]].append(r["name"])
        tokens_by_class[r["classification"]] += (r["tokens"] or 0)

    no_evidence = [r for r in rows
                   if r["audit_calls_all_sessions"] == 0 and r["static_mentions_total"] == 0]
    never_called = [r for r in rows if r["audit_calls_all_sessions"] == 0]
    unreachable = [r for r in rows if not r["reachable"]]

    # ---- AUDIT COVERAGE: the validity constraint on every CALL number ----
    # handlers.py:531 -> `if _mutating: self._submit_logs(...)`, and
    # handlers.py:488 -> `_mutating = cmd_type not in _READ_ONLY_COMMANDS`.
    # The audit trail therefore records ONLY non-read-only commands. For every
    # other tool a "never called" verdict is structurally incapable of being
    # anything else, which is precisely the Law 1 failure mode: a check that
    # cannot fail. Those tools are classified UNMEASURABLE and are NEVER
    # counted as dead surface.
    #
    # Confirmation that this model is complete, not a hypothesis: the tools
    # whose annotations say readOnlyHint=true but whose command_type is ABSENT
    # from _READ_ONLY_COMMANDS are EXACTLY the read-only-hinted tools that do
    # carry audit evidence. Perfect agreement, zero residual.
    auditable = [r for r in rows if r["auditable"]]
    blind = [r for r in rows if not r["auditable"]]
    never_called_auditable = [r for r in auditable if r["audit_calls_all_sessions"] == 0]
    no_runtime = [r for r in rows if r["classification"] == "NO_RUNTIME_EVIDENCE"]
    test_only = [r for r in rows if r["classification"] == "CALLED_TEST_ONLY"]

    ro_hint = {t["name"]: bool((t.get("annotations") or {}).get("readOnlyHint")) for t in tools}
    hint_mismatch = sorted(n for n in names
                           if ro_hint.get(n) and cmd_of.get(n) not in READ_ONLY_COMMANDS)
    ro_hinted_with_calls = sorted(r["name"] for r in rows
                                  if ro_hint.get(r["name"]) and r["audit_calls_all_sessions"] > 0)

    audit_coverage = {
        "rule": "a command is audited iff cmd_type not in handlers._READ_ONLY_COMMANDS",
        "anchor": "python/synapse/server/handlers.py:488 and :531",
        "read_only_commands_count": len(READ_ONLY_COMMANDS),
        "auditable_tools": len(auditable),
        "unmeasurable_tools": len(blind),
        "unmeasurable_tokens": sum(r["tokens"] or 0 for r in blind),
        "never_called_of_auditable": len(never_called_auditable),
        "never_called_of_auditable_rate": (round(len(never_called_auditable) / len(auditable), 4)
                                           if auditable else None),
        "never_called_of_auditable_tokens": sum(r["tokens"] or 0 for r in never_called_auditable),
        "model_check": {
            "readOnlyHint_true_but_not_in_READ_ONLY_COMMANDS": hint_mismatch,
            "read_only_hinted_tools_with_audit_evidence": ro_hinted_with_calls,
            "sets_identical": hint_mismatch == ro_hinted_with_calls,
            "why_it_matters": (
                "If these two sets are identical the coverage model explains "
                "100% of the observed evidence with no residual. It also surfaces "
                "a real inconsistency: these tools advertise readOnlyHint=true to "
                "MCP clients while the server treats them as mutating for the C5 "
                "lock, the integrity envelope and the audit write."
            ),
        },
        "worked_example": (
            "synapse_ping shows zero audit calls. It is called on every session "
            "start. It is not dead - its command type 'ping' is in "
            "_READ_ONLY_COMMANDS, so no call it ever receives can be recorded. "
            "This single example is why the read-only set is excluded from the "
            "dead-surface count rather than discounted."
        ),
    }

    stats = {
        "n_tools": len(rows),
        "evidence_strengths": {
            "REACHABILITY": "VERIFIED-DERIVED - handler registry, deterministic, no Houdini",
            "CALL": "VERIFIED-RUNTIME - local encrypted audit trail, one host",
            "MENTION": "VERIFIED-STATIC - word-boundary git grep; a mention is NOT a call",
        },
        "handler_registry": {
            "source": handler_source,
            "registered_command_types": len(handler_types),
        },
        "audit": audit,
        "journals": journals,
        "combined_coverage": {
            "rule": ("A tool counts as CALLED if it appears in the audit trail "
                     "(by command_type, mutating commands only) OR in a "
                     "PRODUCTION SessionJournal (by tool name, no mutation "
                     "gate). The two sources have complementary blind spots: "
                     "the audit cannot see read-only calls, the journal cannot "
                     "order records across days. Together they cover all 120."),
            "called": sum(1 for r in rows if r["classification"] == "CALLED"),
            "called_test_only": len(test_only),
            "no_runtime_evidence": len(no_runtime),
            "no_runtime_evidence_tokens": sum(r["tokens"] or 0 for r in no_runtime),
            "still_unmeasurable_note": (
                "A tool in NO_RUNTIME_EVIDENCE that is also audit-blind is "
                "evidenced only by the journal; if it never appeared there "
                "either, absence is real but rests on one source."
            ),
        },
        "contamination_warning": (
            "Per harness/notes/RSI_SURFACE_AUDIT.md, ~/.synapse/logs/synapse.log "
            "was found to hold test-authored records that read as production "
            "activity. The audit trail has the same exposure, so every CALL count "
            "is reported twice - all sessions and excluding TEST-SUSPECT sessions "
            "- and neither is treated as authoritative alone."
        ),
        "scope_limit": (
            "One developer machine. Absence of a call here means 'never called on "
            "this host over the audit span', which is evidence and not proof that "
            "no user calls the tool."
        ),
        "summary": {
            "structurally_dead": len(unreachable),
            "structurally_dead_tokens": tokens_by_class["STRUCTURALLY_DEAD"],
            "never_called_any_session": len(never_called),
            "never_called_tokens": sum(r["tokens"] or 0 for r in never_called),
            "no_evidence_at_all": len(no_evidence),
            "no_evidence_tokens": sum(r["tokens"] or 0 for r in no_evidence),
            "by_classification": {k: len(v) for k, v in sorted(by_class.items())},
            "tokens_by_classification": dict(tokens_by_class),
            "auditable_tools": len(auditable),
            "unmeasurable_tools": len(blind),
            "dead_surface_candidates": len(no_runtime),
            "dead_surface_candidate_tokens": sum(r["tokens"] or 0 for r in no_runtime),
            "called_test_only": len(test_only),
        },
        "audit_coverage": audit_coverage,
        "structurally_dead_tools": [
            {"name": r["name"], "command_type": r["command_type"], "tokens": r["tokens"]}
            for r in unreachable],
        "dead_surface_candidates": sorted(
            ({"name": r["name"], "tokens": r["tokens"], "command_type": r["command_type"],
              "auditable": r["auditable"],
              "static_mentions_total": r["static_mentions_total"]}
             for r in no_runtime), key=lambda r: -(r["tokens"] or 0)),
        "called_test_only_tools": sorted(
            ({"name": r["name"], "tokens": r["tokens"],
              "journal_calls_test": r["journal_calls_test"]} for r in test_only),
            key=lambda r: -(r["tokens"] or 0)),
        "audit_only_never_called": sorted(
            ({"name": r["name"], "tokens": r["tokens"]}
             for r in never_called_auditable), key=lambda r: -(r["tokens"] or 0)),
        "unmeasurable_tools": sorted(
            ({"name": r["name"], "tokens": r["tokens"], "command_type": r["command_type"]}
             for r in blind), key=lambda r: -(r["tokens"] or 0)),
        "never_called_tools_ALL_including_unmeasurable": sorted(
            ({"name": r["name"], "tokens": r["tokens"],
              "static_mentions_total": r["static_mentions_total"]} for r in never_called),
            key=lambda r: -(r["tokens"] or 0)),
        "no_evidence_tools": [
            {"name": r["name"], "tokens": r["tokens"]} for r in no_evidence],
        "tools": sorted(rows, key=lambda r: (r["audit_calls_all_sessions"], -(r["tokens"] or 0))),
    }
    digest = hashlib.blake2b(
        json.dumps(stats, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"),
        digest_size=16).hexdigest()
    out = {"schema": "e1_call_evidence/v1",
           "producer": "harness/notes/econ/econ_call_evidence.py",
           "stats": stats, "blake2b": digest}
    OUT_FP.parent.mkdir(parents=True, exist_ok=True)
    OUT_FP.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str),
                      encoding="utf-8")

    print(f"[econ_call_evidence] wrote {OUT_FP}")
    print(json.dumps({
        "handler_registry": stats["handler_registry"],
        "audit": {k: v for k, v in audit.items() if k != "unknown_operation_names"},
        "summary": stats["summary"],
        "audit_coverage": {k: v for k, v in audit_coverage.items()
                           if k not in ("worked_example", "model_check")},
        "journals": [{k: v for k, v in s0.items() if k != "why"}
                     for s0 in journals["sources"]],
        "combined_coverage": {k: v for k, v in stats["combined_coverage"].items()
                              if k not in ("rule", "still_unmeasurable_note")},
        "structurally_dead_tools": stats["structurally_dead_tools"],
        "dead_surface_candidates": stats["dead_surface_candidates"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
