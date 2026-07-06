"""
scripts/flywheel_review_context.py — C track REVIEW: context-capability catalog sweep
=====================================================================================

C track, REVIEW phase (harness/notes/spec-C-context-capability.md §5). Pure stock
Python + the committed catalog — no ``hou``, no hython, no network.

Where U.5's review grounded authored LOP prose against probe truth, this sweeps the
C.0 context-capability catalog (``harness/notes/context_capability_21.json``) for
integrity, structural, and classification violations, and surfaces the capability
story (failed goldens, open gaps, dead undo, the DOP dedicated-verb void) as
advisories the C.1–C.6 sprints consume.

Finding classes (frozen):

  CRITICAL catalog-missing / catalog-unreadable — no catalog to review (run C.0 first)
  CRITICAL schema-mismatch                      — schema != context_capability/v1
  CRITICAL blake2b-mismatch                     — digest over `contexts` does not recompute
  CRITICAL internal-inconsistency               — summary disagrees with contexts, or
                                                  golden.ok true over a failed golden step
  CRITICAL prefix-misclassified                 — a cops_/tops_ command anywhere but cop/top
  CRITICAL double-classified                    — one command in two contexts
  ADVISORY golden-fail / gaps-open / undo-dead / dop-verb-void

Writes ``.claude/flywheel_ctx_findings.json``. Exit 0 whenever the sweep itself RAN —
the ``context_review_clean`` check verb judges ``summary.critical``, not the rc (a
missing catalog is a finding, not a crash).

Options:
  --catalog PATH   review a catalog at a non-canonical path (tests / smoke runs);
                   findings still land at .claude/flywheel_ctx_findings.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
CATALOG_PATH = _REPO / "harness" / "notes" / "context_capability_21.json"
FINDINGS_JSON = _REPO / ".claude" / "flywheel_ctx_findings.json"

SCHEMA = "context_capability/v1"
CONTEXTS = ("sop", "lop", "cop", "top", "dop", "mat", "generic")
SEVERITY_RANK = {"CRITICAL": 0, "ADVISORY": 1}


def _blake(obj) -> str:
    return hashlib.blake2b(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        digest_size=16,
    ).hexdigest()


def _f(severity: str, context: str, what: str, evidence: str) -> dict:
    return {"severity": severity, "context": context, "what": what,
            "evidence": evidence}


def load_catalog(path: Path):
    """(catalog, finding) — a missing/unreadable catalog is a CRITICAL finding,
    never a crash: the sweep must still run and write its findings file."""
    if not path.exists():
        return None, _f("CRITICAL", "", "catalog-missing",
                        f"{path} not found — run C.0 first and commit the catalog")
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as e:
        return None, _f("CRITICAL", "", "catalog-unreadable", str(e)[:300])


def run_review(catalog) -> list:
    findings: list = []
    if catalog is None:
        return findings  # the load finding was already recorded by the caller

    # (1) schema + digest integrity — blake2b covers `contexts` ONLY (the
    # generated timestamp / summary / unclassified sit outside by design).
    if catalog.get("schema") != SCHEMA:
        findings.append(_f("CRITICAL", "", "schema-mismatch",
                           f"schema={catalog.get('schema')!r} != {SCHEMA!r}"))
    contexts = catalog.get("contexts")
    if not isinstance(contexts, dict):
        findings.append(_f("CRITICAL", "", "internal-inconsistency",
                           "`contexts` is missing or not an object"))
        return _sorted(findings)
    if _blake(contexts) != catalog.get("blake2b"):
        findings.append(_f("CRITICAL", "", "blake2b-mismatch",
                           "digest over `contexts` does not recompute "
                           "(corrupt/hand-edited catalog)"))

    # (2) internal consistency — summary must agree with contexts, key-for-key,
    # and no golden may claim ok over a failed golden step.
    if set(contexts) != set(CONTEXTS):
        findings.append(_f("CRITICAL", "", "internal-inconsistency",
                           f"contexts keys {sorted(contexts)} != {sorted(CONTEXTS)}"))
    summary = catalog.get("summary") or {}
    for ctx, entry in sorted(contexts.items()):
        golden = entry.get("golden") or {}
        steps = golden.get("steps") or []
        if golden.get("ok") is True and any(not s.get("ok") for s in steps):
            bad = next(s.get("step") for s in steps if not s.get("ok"))
            findings.append(_f("CRITICAL", ctx, "internal-inconsistency",
                               f"golden.ok is true but step '{bad}' is ok:false"))
        s = summary.get(ctx)
        if not isinstance(s, dict):
            findings.append(_f("CRITICAL", ctx, "internal-inconsistency",
                               "context absent from summary"))
        else:
            if bool(s.get("golden_ok")) != bool(golden.get("ok")):
                findings.append(_f("CRITICAL", ctx, "internal-inconsistency",
                                   f"summary.golden_ok={s.get('golden_ok')} != "
                                   f"contexts golden.ok={golden.get('ok')}"))
            if s.get("gaps") != len(entry.get("gaps") or []):
                findings.append(_f("CRITICAL", ctx, "internal-inconsistency",
                                   f"summary.gaps={s.get('gaps')} != "
                                   f"len(gaps)={len(entry.get('gaps') or [])}"))

    # (3) classification law — cops_/tops_ prefixes belong to cop/top and
    # nowhere else (contexts OR unclassified); no command lives in two contexts.
    seen: dict = {}
    for ctx, entry in sorted(contexts.items()):
        for cmd in entry.get("commands") or []:
            if cmd.startswith("cops_") and ctx != "cop":
                findings.append(_f("CRITICAL", ctx, "prefix-misclassified",
                                   f"'{cmd}' (cops_ prefix) classified into '{ctx}'"))
            if cmd.startswith("tops_") and ctx != "top":
                findings.append(_f("CRITICAL", ctx, "prefix-misclassified",
                                   f"'{cmd}' (tops_ prefix) classified into '{ctx}'"))
            if cmd in seen:
                findings.append(_f("CRITICAL", ctx, "double-classified",
                                   f"'{cmd}' classified into both '{seen[cmd]}' "
                                   f"and '{ctx}'"))
            else:
                seen[cmd] = ctx
    for cmd in catalog.get("unclassified") or []:
        if cmd.startswith(("cops_", "tops_")):
            findings.append(_f("CRITICAL", "", "prefix-misclassified",
                               f"'{cmd}' left unclassified — its prefix pins it to "
                               f"{'cop' if cmd.startswith('cops_') else 'top'}"))

    # (4) capability advisories — the material the C.1–C.6 sprints consume.
    for ctx, entry in sorted(contexts.items()):
        golden = entry.get("golden") or {}
        if golden.get("ok") is not True:
            first_bad = next((s.get("step") for s in golden.get("steps") or []
                              if not s.get("ok")), None)
            findings.append(_f("ADVISORY", ctx, "golden-fail",
                               f"golden fails (first failing step: {first_bad})"))
        gaps = entry.get("gaps") or []
        if gaps:
            findings.append(_f("ADVISORY", ctx, "gaps-open",
                               f"{len(gaps)} gap(s): {'; '.join(gaps[:6])[:260]}"))
        for step in entry.get("extended") or []:
            if step.get("step") == "undo_unwind" and not step.get("ok"):
                findings.append(_f("ADVISORY", ctx, "undo-dead",
                                   str(step.get("detail"))[:260]))
    if not (contexts.get("dop") or {}).get("commands"):
        findings.append(_f("ADVISORY", "dop", "dop-verb-void",
                           "no dedicated dop_* handler verbs exist — DOP creation "
                           "rides generic verbs only"))
    return _sorted(findings)


def _sorted(findings: list) -> list:
    findings.sort(key=lambda f: (SEVERITY_RANK[f["severity"]], f["context"],
                                 f["what"], f["evidence"]))
    return findings


def summarize(findings: list) -> dict:
    return {
        "critical": sum(1 for f in findings if f["severity"] == "CRITICAL"),
        "advisory": sum(1 for f in findings if f["severity"] == "ADVISORY"),
    }


def write_findings(findings: list) -> dict:
    summary = summarize(findings)
    payload = {"schema": "ctx_review/v1", "summary": summary, "findings": findings}
    FINDINGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    FINDINGS_JSON.write_text(
        json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", default=None,
                    help="catalog path override (default: the canonical "
                         "harness/notes/context_capability_21.json)")
    a = ap.parse_args(argv)

    catalog_path = Path(a.catalog) if a.catalog else CATALOG_PATH
    catalog, load_finding = load_catalog(catalog_path)
    findings = ([load_finding] if load_finding else []) + run_review(catalog)
    findings = _sorted(findings)
    summary = write_findings(findings)

    print(f"CTX REVIEW: {len(findings)} finding(s), {summary['critical']} CRITICAL, "
          f"{summary['advisory']} ADVISORY -> {FINDINGS_JSON}")
    by_what: dict = {}
    for f in findings:
        by_what[f["what"]] = by_what.get(f["what"], 0) + 1
    for what, n in sorted(by_what.items()):
        print(f"  {what}: {n}")

    # Exit 0 whenever the sweep itself ran — the context_review_clean check
    # judges summary.critical; the rc only signals a sweep that could not run.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
