"""
scripts/flywheel_review_lop.py — U.5 REVIEW: LOP/Solaris knowledge vs probe truth
================================================================================

Utility-flywheel cycle U.5, REVIEW phase (harness/notes/spec-U5-lop-solaris-flywheel.md).
Pure Python + the two committed catalogs — no ``hou``, no ``G:\\`` corpus (when run under
hython, the optional Ledger deposit stamps the live build).

Where U.1's review swept ``setInput(`` call sites against WIRING truth, this grounds the
authored LOP/Solaris CONTEXT catalog against PROBE truth — the standing "probe truth >
authored prose" rule — using only committed artifacts:

  * python/synapse/cognitive/tools/data/lop_solaris_knowledge_21.json  (the authored catalog)
  * python/synapse/cognitive/tools/data/connectivity_21.json           (the U.1 live probe)

Checks (CRITICAL fails the ``lop_review_clean`` verb; INFO is informational):

  CRITICAL integrity-blake2b            — blake2b over `content` does not recompute (corrupt/hand-edit)
  CRITICAL structural-*                 — known_absent also an entry; ordering rule names an unknown type
  CRITICAL probe-confirmed-drift        — a `probe_confirmed_types` entry is NOT in the live probe Lop set
  CRITICAL known-absent-contradiction   — a `known_absent` type IS present in the live probe Lop set
  INFO     probe-confirmed              — an authored entry the live probe also carries (grounded live)
  INFO     authored-only                — an authored entry grounded in corpus prose only (not probed)

Outputs ``.claude/flywheel_u5_findings.json`` + ``.md`` (severity-ranked).
Exit 0 iff no CRITICAL findings (the ``lop_review_clean`` check verb).

Options:
  --deposit   deposit one Confirmation/DeadEnd Ledger record PER CHECK CLASS via
              synapse.science.deposit.LedgerDeposit (opt-in so the every-sprint check
              verb never re-deposits; run under hython POST-MERGE for the live build
              stamp — mirrors U.1's flywheel_review_wiring.py).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
CATALOG_PATH = (_REPO / "python" / "synapse" / "cognitive" / "tools"
                / "data" / "lop_solaris_knowledge_21.json")
CONNECTIVITY_PATH = (_REPO / "python" / "synapse" / "cognitive" / "tools"
                     / "data" / "connectivity_21.json")
FINDINGS_JSON = _REPO / ".claude" / "flywheel_u5_findings.json"
FINDINGS_MD = _REPO / ".claude" / "flywheel_u5_findings.md"

SEVERITY_RANK = {"CRITICAL": 0, "INFO": 1}
SCHEMA = "lop_solaris_knowledge/v1"


def _blake(obj) -> str:
    return hashlib.blake2b(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        digest_size=16,
    ).hexdigest()


def load_catalog(path: Path = CATALOG_PATH) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise SystemExit(f"catalog at {path} is not {SCHEMA}")
    return data


def connectivity_lop_types(path: Path = CONNECTIVITY_PATH) -> set:
    """The Lop type names the U.1 live connectivity probe recorded (the cross-check)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {e.get("type_name", "").split("::")[0]
            for e in data.get("entries", {}).values()
            if e.get("category") == "Lop"}


def _f(severity: str, kind: str, detail: str, **extra) -> dict:
    return {"severity": severity, "kind": kind, "detail": detail, **extra}


def run_review(catalog: dict, conn_lop: set) -> list:
    content = catalog.get("content", {})
    entries = content.get("entries", {})
    known_absent = content.get("known_absent", {})
    ordering = content.get("ordering_rules", [])
    probe_confirmed = catalog.get("probe_confirmed_types", [])
    findings: list = []

    # (1) integrity — blake2b over `content` recomputes
    if _blake(content) != catalog.get("blake2b"):
        findings.append(_f("CRITICAL", "integrity-blake2b",
                           "blake2b over `content` does not recompute (corrupt/hand-edited)"))

    # (2) structural — known_absent disjoint from entries; ordering refs real entries
    for name in known_absent:
        if name in entries:
            findings.append(_f("CRITICAL", "structural-known-absent-is-entry",
                               f"'{name}' is in known_absent AND an entry — contradiction",
                               type_name=name))
    for r in ordering:
        rid = r.get("id", "?")
        for key in ("on_type", "requires_type"):
            t = r.get(key)
            if t is not None and t not in entries:
                findings.append(_f("CRITICAL", "structural-ordering-unknown-type",
                                   f"ordering rule '{rid}' {key} '{t}' is not an entry",
                                   type_name=t))
        for t in r.get("satisfied_by", []):
            if t not in entries:
                findings.append(_f("CRITICAL", "structural-ordering-unknown-type",
                                   f"ordering rule '{rid}' satisfied_by '{t}' is not an entry",
                                   type_name=t))

    # (3)+(4)+(5) require the live probe. If it is unreadable, skip the cross-check
    # loudly rather than emit false drift (each un-probed entry would look drifted).
    if conn_lop:
        for name in probe_confirmed:
            if name in conn_lop:
                findings.append(_f("INFO", "probe-confirmed",
                                   f"'{name}' authored entry is also present in the live probe",
                                   type_name=name))
            else:
                findings.append(_f("CRITICAL", "probe-confirmed-drift",
                                   f"'{name}' claimed probe-confirmed but NOT in the live probe "
                                   "Lop set (catalog/probe drift)", type_name=name))
        for name in known_absent:
            if name in conn_lop:
                findings.append(_f("CRITICAL", "known-absent-contradiction",
                                   f"'{name}' is marked known_absent but IS present in the live "
                                   "probe Lop set (contradiction)", type_name=name))
        for name in entries:
            if name not in conn_lop:
                findings.append(_f("INFO", "authored-only",
                                   f"'{name}' authored from corpus prose (not in the U.1 probe "
                                   "subset — expected for un-probed types)", type_name=name))
    else:
        findings.append(_f("INFO", "probe-cross-check-skipped",
                           "connectivity_21.json unreadable — probe cross-check skipped"))

    findings.sort(key=lambda f: (SEVERITY_RANK[f["severity"]], f["kind"],
                                 f.get("type_name", "")))
    return findings


def summarize(findings: list) -> dict:
    by_kind: dict = {}
    for f in findings:
        by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1
    return {
        "total": len(findings),
        "critical": sum(1 for f in findings if f["severity"] == "CRITICAL"),
        "by_kind": dict(sorted(by_kind.items())),
    }


def write_findings(catalog: dict, findings: list) -> dict:
    summary = summarize(findings)
    payload = {
        "schema": "flywheel_findings/v1",
        "task": "U.5",
        "catalog": {"path": str(CATALOG_PATH.relative_to(_REPO)).replace("\\", "/"),
                    "houdini_version": catalog.get("houdini_version"),
                    "blake2b": catalog.get("blake2b")},
        "summary": summary,
        "findings": findings,
    }
    FINDINGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    FINDINGS_JSON.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                             encoding="utf-8", newline="\n")

    md = ["# U.5 LOP/Solaris knowledge review — findings (severity-ranked)", "",
          f"Catalog: `{payload['catalog']['path']}` (build "
          f"{catalog.get('houdini_version')}, blake2b `{str(catalog.get('blake2b'))[:12]}`)", "",
          f"**{summary['critical']} CRITICAL** of {summary['total']} checks. "
          f"By kind: " + ", ".join(f"{k}={v}" for k, v in summary["by_kind"].items()), ""]
    for sev in ("CRITICAL", "INFO"):
        group = [f for f in findings if f["severity"] == sev]
        if not group:
            continue
        md.append(f"## {sev} ({len(group)})")
        md.append("")
        cap = len(group) if sev == "CRITICAL" else 40
        for f in group[:cap]:
            md.append(f"- **{f['kind']}** {f['detail']}")
        if len(group) > cap:
            md.append(f"- ... and {len(group) - cap} more (see JSON)")
        md.append("")
    FINDINGS_MD.write_text("\n".join(md), encoding="utf-8", newline="\n")
    return summary


# --- Ledger deposit (opt-in; run under hython POST-MERGE — mirrors U.1) ---------

def deposit_review_classes(catalog: dict, summary: dict) -> tuple:
    """One Confirmation/DeadEnd per verified check CLASS via the §7.2 deposit seam."""
    sys.path.insert(0, str(_REPO / "python"))
    from synapse.science.deposit import LedgerDeposit  # noqa: PLC0415 — after path fix

    sink = LedgerDeposit()
    now = int(time.time())
    artifact = str(FINDINGS_JSON.relative_to(_REPO)).replace("\\", "/")
    bk = summary["by_kind"]
    integrity_bad = bk.get("integrity-blake2b", 0)
    structural_bad = (bk.get("structural-known-absent-is-entry", 0)
                      + bk.get("structural-ordering-unknown-type", 0))
    drift_bad = bk.get("probe-confirmed-drift", 0)
    contradiction_bad = bk.get("known-absent-contradiction", 0)
    n_confirmed = bk.get("probe-confirmed", 0)
    n_absent = len(catalog.get("content", {}).get("known_absent", {}))

    sink({
        "surface": "lop_knowledge/catalog-integrity-and-structure",
        "status": "champion" if (integrity_bad == 0 and structural_bad == 0) else "dead_end",
        "detail": (f"catalog blake2b recomputes over `content`; known_absent disjoint from "
                   f"entries; ordering rules reference real entries. "
                   f"{integrity_bad + structural_bad} violation(s). Artifact: {artifact}"),
        "timestamp": now, "kind": "lop_review", "context": "flywheel U.5 REVIEW",
    })
    sink({
        "surface": "lop_knowledge/probe-confirmed-types-grounded-in-live-probe",
        "status": "champion" if drift_bad == 0 else "dead_end",
        "detail": (f"{n_confirmed} authored entries are present in the U.1 live connectivity "
                   f"probe (probe truth > authored prose); {drift_bad} drifted. "
                   f"Artifact: {artifact}"),
        "timestamp": now, "kind": "lop_review", "context": "flywheel U.5 REVIEW",
    })
    sink({
        "surface": "lop_knowledge/known-absent-types-absent-from-live-probe",
        "status": "champion" if contradiction_bad == 0 else "dead_end",
        "detail": (f"{n_absent} known_absent type(s) (grid/plane) do not appear in the live "
                   f"probe Lop set (no contradiction); {contradiction_bad} contradiction(s). "
                   f"Artifact: {artifact}"),
        "timestamp": now, "kind": "lop_review", "context": "flywheel U.5 REVIEW",
    })
    return sink.deposited, sink.failures


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deposit", action="store_true",
                    help="deposit per-class Ledger records (opt-in; run under hython post-merge)")
    a = ap.parse_args(argv)

    catalog = load_catalog()
    conn_lop = connectivity_lop_types()
    findings = run_review(catalog, conn_lop)
    summary = write_findings(catalog, findings)
    print(f"LOP REVIEW: {summary['total']} checks, {summary['critical']} CRITICAL "
          f"-> {FINDINGS_JSON}")
    for k, v in summary["by_kind"].items():
        print(f"  {k}: {v}")
    if not conn_lop:
        print("  NOTE: connectivity probe catalog unreadable — probe cross-check skipped")

    if a.deposit:
        deposited, failures = deposit_review_classes(catalog, summary)
        print(f"  ledger: deposited={deposited} failures={len(failures)}")
        for f in failures:
            print(f"  DEPOSIT-FAIL: {f}")

    return 1 if summary["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
