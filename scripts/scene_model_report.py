"""Scene-model Mile 0 baseline report — reads the two measurement ledgers.

Usage:
    python scripts/scene_model_report.py [--read-ledger PATH] [--turns PATH] [--json]

Computes, from ``read_ledger.jsonl`` + ``turns.jsonl``:

  (a) the live-path re-read rate: records whose (cmd_type, args_hash) was
      already observed EARLIER in the SAME session_id. The pure-re-read vs
      post-mutation-re-read split is reported as UNAVAILABLE: the Mile 0
      ledgers capture reads only — intervening-mutation attribution arrives
      when the scene-model store lands (Mile 1+).
  (b) per-session, per-cmd_type, per-session-scope and aggregate counts.
  (c) the turns-per-send distribution (median / p25 / p75 / mean, cap-hit
      rate) from the U2 instrument, segmented by outcome and model.

Honesty guards (fix pass 2026-07-18):

  * Liveness/control-plane traffic (:data:`INFRA_READ_COMMANDS` — a
    conformance-pinned copy of ``server.read_ledger.INFRA_READ_COMMANDS``)
    is excluded from the re-read rate and reported separately; identical-
    payload polling is not a cacheable scene read. The ledger itself skips
    these at record time — the report-side filter keeps any legacy rows
    from polluting the number.
  * ``batch_commands`` sub-reads bypass the handler hook (documented seam)
    — the baseline UNDERCOUNTS reads issued inside batches; stated in the
    output.
  * Turns rows carry an ``outcome``; rows written before the fix pass
    captured completed/cap sends only (aborted/error sends missing) —
    stated in the output.

Deterministic: same input files -> same numbers (file order is the event
order; percentiles use ``statistics.quantiles(..., method="inclusive")``).
Pure stdlib, zero SYNAPSE imports — safe to run anywhere. Malformed JSONL
lines are tolerated and counted (the RecommendationHistory read idiom).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from typing import Any, Dict, List, Optional

SPLIT_NOTE = (
    "unavailable: Mile 0 ledgers capture reads only -- "
    "intervening-mutation attribution arrives when the scene-model "
    "store lands"
)

BATCH_NOTE = (
    "batch_commands sub-reads bypass the handler hook (documented seam) -- "
    "reads issued inside batches are UNDERCOUNTED in this baseline"
)

INFRA_NOTE = (
    "liveness/control-plane traffic (identical-payload polling, not "
    "cacheable scene reads) -- excluded from the re-read rate"
)

TURNS_OUTCOME_NOTE = (
    "rows written before the 2026-07-18 fix pass captured completed/cap "
    "sends only; aborted/error sends from that window are missing "
    "(survivorship)"
)

# Conformance-pinned copy of server.read_ledger.INFRA_READ_COMMANDS
# (test_read_ledger asserts equality — this script stays zero-import).
INFRA_READ_COMMANDS = frozenset({
    "ping", "heartbeat", "get_health", "get_help",
    "get_metrics", "get_live_metrics", "router_stats", "list_recipes",
    "render_farm_status", "render_farm_cancel",
})


def default_log_dir() -> str:
    """Mirror ``synapse.core.logfile.log_dir()`` (the SSOT) without
    importing the package: ``$SYNAPSE_LOG_DIR`` else ``~/.synapse/logs``.
    Conformance-pinned against the SSOT by test_read_ledger."""
    override = os.environ.get("SYNAPSE_LOG_DIR", "").strip()
    if override:
        return override
    return os.path.join(os.path.expanduser("~"), ".synapse", "logs")


def load_jsonl(path: str) -> "tuple[List[Dict[str, Any]], int]":
    """Load records from *path* in file order.

    Returns ``(records, malformed_count)``. A missing file is an empty
    ledger, not an error. Non-dict / unparseable lines count as malformed.
    """
    records: List[Dict[str, Any]] = []
    malformed = 0
    if not os.path.isfile(path):
        return records, malformed
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                malformed += 1
                continue
            if isinstance(obj, dict):
                records.append(obj)
            else:
                malformed += 1
    return records, malformed


def compute_read_stats(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Re-read rate + observation counts from read_ledger records.

    A re-read is a record whose ``(session_id, cmd_type, args_hash)`` key
    was seen at an EARLIER record (file order == event order) in the same
    session. Infra traffic (:data:`INFRA_READ_COMMANDS`) is bucketed out
    before the rate; records missing any key field are skipped and counted.
    """
    total = 0
    skipped = 0
    re_reads = 0
    sessions: Dict[str, int] = {}
    per_cmd_type: Dict[str, int] = {}
    session_scopes: Dict[str, int] = {}
    infra_per_cmd: Dict[str, int] = {}
    seen: set = set()

    for rec in records:
        cmd = rec.get("cmd_type")
        if cmd in INFRA_READ_COMMANDS:
            infra_per_cmd[cmd] = infra_per_cmd.get(cmd, 0) + 1
            continue
        sid = rec.get("session_id")
        ahash = rec.get("args_hash")
        if not sid or not cmd or not ahash:
            skipped += 1
            continue
        total += 1
        sessions[sid] = sessions.get(sid, 0) + 1
        per_cmd_type[cmd] = per_cmd_type.get(cmd, 0) + 1
        scope = rec.get("session_scope") or "unrecorded"
        session_scopes[scope] = session_scopes.get(scope, 0) + 1
        key = (sid, cmd, ahash)
        if key in seen:
            re_reads += 1
        else:
            seen.add(key)

    return {
        "total_observations": total,
        "skipped_records": skipped,
        "session_count": len(sessions),
        "per_session_observations": dict(sorted(sessions.items())),
        "per_cmd_type": dict(sorted(per_cmd_type.items())),
        "session_scopes": dict(sorted(session_scopes.items())),
        "infra_excluded": {
            "total": sum(infra_per_cmd.values()),
            "per_cmd_type": dict(sorted(infra_per_cmd.items())),
            "note": INFRA_NOTE,
        },
        "batch_note": BATCH_NOTE,
        "re_reads": {
            "total": re_reads,
            "rate": (re_reads / total) if total else None,
            "pure_re_reads": None,
            "post_mutation_re_reads": None,
            "split_note": SPLIT_NOTE,
        },
    }


def _quantiles(values: List[float]) -> "tuple[Optional[float], Optional[float], Optional[float]]":
    """(p25, median, p75) — deterministic, inclusive method."""
    if not values:
        return None, None, None
    if len(values) == 1:
        v = float(values[0])
        return v, v, v
    q1, q2, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return float(q1), float(q2), float(q3)


def compute_turn_stats(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Turns-per-send distribution from turns.jsonl records.

    Distribution covers ALL valid rows (aborted/error sends spent real
    turns; excluding them re-creates the survivorship bias). ``outcomes``
    + ``models`` segment the population; legacy rows without ``outcome``
    are inferred from ``hit_25_cap`` (they were only ever written on
    completion or cap).
    """
    turns: List[float] = []
    cap_hits = 0
    skipped = 0
    outcomes: Dict[str, int] = {}
    models: Dict[str, int] = {}
    for rec in records:
        t = rec.get("turns")
        if not isinstance(t, (int, float)) or isinstance(t, bool):
            skipped += 1
            continue
        turns.append(float(t))
        if rec.get("hit_25_cap"):
            cap_hits += 1
        outcome = rec.get("outcome") or (
            "cap" if rec.get("hit_25_cap") else "completed")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        model = rec.get("model") or "unrecorded"
        models[model] = models.get(model, 0) + 1

    p25, median, p75 = _quantiles(turns)
    return {
        "sends": len(turns),
        "skipped_records": skipped,
        "turns_mean": (sum(turns) / len(turns)) if turns else None,
        "turns_median": median,
        "turns_p25": p25,
        "turns_p75": p75,
        "cap_hits": cap_hits,
        "cap_hit_rate": (cap_hits / len(turns)) if turns else None,
        "outcomes": dict(sorted(outcomes.items())),
        "models": dict(sorted(models.items())),
        "outcome_note": TURNS_OUTCOME_NOTE,
    }


def build_report(read_path: str, turns_path: str) -> Dict[str, Any]:
    read_records, read_malformed = load_jsonl(read_path)
    turn_records, turns_malformed = load_jsonl(turns_path)
    read_stats = compute_read_stats(read_records)
    read_stats["malformed_lines"] = read_malformed
    turn_stats = compute_turn_stats(turn_records)
    turn_stats["malformed_lines"] = turns_malformed
    return {
        "read_ledger": {"path": read_path, **read_stats},
        "turns_ledger": {"path": turns_path, **turn_stats},
    }


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def print_human(report: Dict[str, Any]) -> None:
    r = report["read_ledger"]
    t = report["turns_ledger"]
    rr = r["re_reads"]
    infra = r["infra_excluded"]
    print("=== Scene-model Mile 0 baseline ===")
    print()
    print(f"READ LEDGER  {r['path']}")
    print(f"  observations (aggregate): {r['total_observations']}")
    print(f"  sessions:                 {r['session_count']}")
    for sid, count in r["per_session_observations"].items():
        print(f"    {sid}: {count}")
    print("  per cmd_type:")
    for cmd, count in r["per_cmd_type"].items():
        print(f"    {cmd}: {count}")
    print("  session scopes:           "
          + (", ".join(f"{k}={v}" for k, v in r["session_scopes"].items())
             or "none"))
    print(f"  re-reads:                 {rr['total']}"
          f"  (rate {_fmt(rr['rate'])})")
    print(f"  pure vs post-mutation split: {rr['split_note']}")
    print(f"  infra excluded:           {infra['total']}"
          + (f"  ({', '.join(f'{k}={v}' for k, v in infra['per_cmd_type'].items())})"
             if infra["per_cmd_type"] else ""))
    print(f"    note: {infra['note']}")
    print(f"  batch note: {r['batch_note']}")
    if r["skipped_records"] or r["malformed_lines"]:
        print(f"  skipped/malformed:        "
              f"{r['skipped_records']}/{r['malformed_lines']}")
    print()
    print(f"TURNS LEDGER  {t['path']}")
    print(f"  sends:        {t['sends']}")
    print(f"  turns mean:   {_fmt(t['turns_mean'])}")
    print(f"  turns median: {_fmt(t['turns_median'])}"
          f"  (p25 {_fmt(t['turns_p25'])} / p75 {_fmt(t['turns_p75'])})")
    print(f"  cap hits:     {t['cap_hits']}"
          f"  (rate {_fmt(t['cap_hit_rate'])})")
    print("  outcomes:     "
          + (", ".join(f"{k}={v}" for k, v in t["outcomes"].items())
             or "none"))
    print("  models:       "
          + (", ".join(f"{k}={v}" for k, v in t["models"].items())
             or "none"))
    print(f"    note: {t['outcome_note']}")
    if t["skipped_records"] or t["malformed_lines"]:
        print(f"  skipped/malformed: "
              f"{t['skipped_records']}/{t['malformed_lines']}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scene-model Mile 0 baseline report "
                    "(read_ledger.jsonl + turns.jsonl)")
    log_dir = default_log_dir()
    parser.add_argument(
        "--read-ledger",
        default=os.path.join(log_dir, "read_ledger.jsonl"),
        help="path to read_ledger.jsonl (default: <logs dir>)")
    parser.add_argument(
        "--turns",
        default=os.path.join(log_dir, "turns.jsonl"),
        help="path to turns.jsonl (default: <logs dir>)")
    parser.add_argument(
        "--json", action="store_true",
        help="emit machine-readable JSON instead of the human report")
    args = parser.parse_args(argv)

    report = build_report(args.read_ledger, args.turns)
    if args.json:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        print()
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
