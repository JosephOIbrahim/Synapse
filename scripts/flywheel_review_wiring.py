"""
scripts/flywheel_review_wiring.py — U.1 REVIEW: wiring call sites vs probe truth
================================================================================

Utility-flywheel cycle U.1, REVIEW phase (harness/notes/spec-U1-wiring-flywheel.md).
Pure Python + the connectivity catalog — no ``hou`` required (when run under
hython, the optional Ledger deposit stamps the live build).

Sweeps ``python/synapse/**`` for ``setInput(`` / ``insertInput(`` call sites —
both real code and the generated-code string templates (the sweep is textual,
so a template line like ``"solver.setInput(1, cloth, 1)\\n"`` is a call site
too, which is exactly where yesterday's miswires lived). Each site is resolved
to a node type via two lexical maps built per file:

  * ``var = <anything>.createNode('<type>' [, '<name>'])``  → var carries <type>,
    and <name> is registered so a later ``var = parent.node('<name>')`` in
    another snippet resolves to the same type (the planner's modifier steps).
  * nearest PRECEDING assignment wins (lexical flow).

Classification against the catalog is CONSERVATIVE — a finding fires only when
it holds for EVERY candidate category the type resolves in (bare 'merge' exists
in Sop/Lop/Dop/...), so the gate cannot false-positive on category ambiguity:

  CRITICAL index-out-of-arity   — literal input index >= max_inputs for ALL candidates
  CRITICAL label-claim-mismatch — a nearby comment claims a quoted input label and
                                  NO candidate's catalog label at that index matches
  INFO     dynamic-index        — non-literal index (runtime passthrough; not provable here)
  INFO     unresolved-receiver  — receiver's node type not lexically resolvable
  INFO     type-not-in-catalog  — resolvable type the catalog doesn't carry

Outputs ``.claude/flywheel_u1_findings.json`` + ``.md`` (severity-ranked).
Exit 0 iff no CRITICAL findings (the ``wiring_conformance`` check verb).

Options:
  --deposit        deposit one Confirmation/DeadEnd Ledger record PER FINDING
                   CLASS via synapse.science.deposit.LedgerDeposit (opt-in so
                   the every-sprint check verb never re-deposits)
  --queue-append   append the evidenced U.2+ candidates below to
                   harness/state/flywheel_queue.json (status "candidate",
                   ratified false — a HUMAN flips ratified; idempotent by id)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
CATALOG_PATH = _REPO / "harness" / "notes" / "verified_connectivity_21.0.671.json"
SWEEP_ROOT = _REPO / "python" / "synapse"
FINDINGS_JSON = _REPO / ".claude" / "flywheel_u1_findings.json"
FINDINGS_MD = _REPO / ".claude" / "flywheel_u1_findings.md"
QUEUE_PATH = _REPO / "harness" / "state" / "flywheel_queue.json"
SKIP_PARTS = {"_vendor", "__pycache__"}

SEVERITY_RANK = {"CRITICAL": 0, "INFO": 1}

# --- lexical maps -----------------------------------------------------------
# var = <recv>.createNode('type'[, 'name'])   (works inside string templates too)
_CREATE_RE = re.compile(
    r"(\w+)\s*=\s*[\w.()'\"/]+\.createNode\(\s*['\"]([\w:.]+)['\"]"
    r"(?:\s*,\s*['\"]([\w:.]+)['\"])?")
# var = <recv>.node('path-or-name')
_NODE_LOOKUP_RE = re.compile(r"(\w+)\s*=\s*[\w.()'\"/]+\.node\(\s*['\"]([\w./: ]+)['\"]")
# recv.setInput(<first-arg>  /  recv.insertInput(<first-arg>
_CALLSITE_RE = re.compile(r"(\w+)\.(setInput|insertInput)\(\s*([^,)]+)")
# a quoted label claimed in a comment, e.g.  # ... solver 'Constraint Geometry' input
_COMMENT_LABEL_RE = re.compile(r"#[^'\"]*['\"]([A-Za-z][\w ]{2,40})['\"]")

_VERSION_COMPONENT = re.compile(r"^[0-9][0-9.]*$")


def _strip_version(full_name: str) -> str:
    parts = full_name.split("::")
    if len(parts) > 1 and _VERSION_COMPONENT.match(parts[-1]):
        return "::".join(parts[:-1])
    return full_name


def load_catalog(path: Path = CATALOG_PATH) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "verified_connectivity/v2":
        raise SystemExit(f"catalog at {path} is not verified_connectivity/v2")
    return data


def candidates_for(catalog_entries: dict, type_name: str) -> list:
    """Every catalog entry the spelling could resolve to (any category)."""
    hits = []
    for key, entry in catalog_entries.items():
        full = entry["type_name"]
        if (full == type_name
                or _strip_version(full) == type_name
                or ("::" not in type_name
                    and _strip_version(full).split("::")[-1] == type_name)):
            hits.append(entry)
    return hits


# --- the sweep ---------------------------------------------------------------

def sweep_file(path: Path, catalog_entries: dict, name_registry: dict) -> list:
    """All classified call sites in one file. ``name_registry`` maps created
    node NAMES -> types across the whole sweep (two-pass: fill first)."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    var_types: list = []   # (line_no, var, type)
    for i, line in enumerate(lines, 1):
        for m in _CREATE_RE.finditer(line):
            var_types.append((i, m.group(1), m.group(2)))
        for m in _NODE_LOOKUP_RE.finditer(line):
            base = m.group(2).rstrip("/").rsplit("/", 1)[-1]
            if base in name_registry:
                var_types.append((i, m.group(1), name_registry[base]))

    def resolve_var(var: str, at_line: int):
        best = None
        for line_no, v, t in var_types:
            if v == var and line_no <= at_line:
                best = t
        return best

    sites = []
    rel = str(path.relative_to(_REPO)).replace("\\", "/")
    for i, line in enumerate(lines, 1):
        for m in _CALLSITE_RE.finditer(line):
            recv, call, first_arg = m.group(1), m.group(2), m.group(3).strip()
            index = int(first_arg) if first_arg.isdigit() else None
            recv_type = resolve_var(recv, i)
            claimed = []
            for back in range(max(0, i - 3), i):   # this line + 2 above
                claimed += _COMMENT_LABEL_RE.findall(lines[back])
            sites.append(classify_site(
                catalog_entries, rel, i, recv, call, index, first_arg,
                recv_type, claimed))
    return sites


def classify_site(catalog_entries, rel, line_no, recv, call, index, index_expr,
                  recv_type, claimed_labels) -> dict:
    site = {
        "file": rel, "line": line_no, "call": call, "receiver": recv,
        "receiver_type": recv_type, "index": index, "index_expr": index_expr,
        "claimed_labels": claimed_labels,
        "severity": "INFO", "kind": "", "detail": "",
    }
    if recv_type is None:
        site.update(kind="unresolved-receiver",
                    detail="receiver's node type not lexically resolvable (runtime object)")
        return site
    cands = candidates_for(catalog_entries, recv_type)
    if not cands:
        site.update(kind="type-not-in-catalog",
                    detail=f"'{recv_type}' has no entry in the connectivity catalog")
        return site
    site["candidate_keys"] = sorted(f"{c['category']}/{c['type_name']}" for c in cands)
    if index is None:
        site.update(kind="dynamic-index",
                    detail=f"input index '{index_expr}' is not a literal — not provable statically")
        return site

    # (a) arity: fires only if the index overflows EVERY candidate
    def overflows(c):
        mx = c.get("max_inputs")
        return mx is not None and mx >= 0 and index >= mx
    if all(overflows(c) for c in cands):
        worst = max(c.get("max_inputs") or 0 for c in cands)
        site.update(severity="CRITICAL", kind="index-out-of-arity",
                    detail=f"input index {index} >= max_inputs ({worst}) for every "
                           f"candidate of '{recv_type}'")
        return site

    # (b) label claim: a nearby comment names a quoted label — does the catalog
    # agree that label lives at THIS index on at least one candidate?
    labeled = [c for c in cands if c.get("input_labels")]
    if claimed_labels and labeled:
        def label_at(c):
            labels = c["input_labels"]
            return labels[index] if 0 <= index < len(labels) else None
        def claim_matches(c):
            at = label_at(c)
            if at is None:
                return False
            at_l = at.lower()
            return any(cl.lower() == at_l or cl.lower() in at_l or at_l in cl.lower()
                       for cl in claimed_labels)
        if any(claim_matches(c) for c in labeled):
            site.update(kind="label-claim-verified",
                        detail=f"comment label claim matches catalog label at index {index}")
        else:
            ats = sorted({str(label_at(c)) for c in labeled})
            site.update(severity="CRITICAL", kind="label-claim-mismatch",
                        detail=f"comment claims {claimed_labels} but catalog puts "
                               f"{ats} at index {index} of '{recv_type}'")
        return site

    site.update(kind="index-within-arity",
                detail=f"input index {index} within max_inputs for '{recv_type}'")
    return site


def run_sweep(catalog: dict) -> list:
    entries = catalog["entries"]
    files = sorted(p for p in SWEEP_ROOT.rglob("*.py")
                   if not any(s in p.parts for s in SKIP_PARTS))
    # pass 1: global created-name registry ('vellum_solver' -> 'vellumsolver')
    name_registry: dict = {}
    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in _CREATE_RE.finditer(text):
            if m.group(3):
                name_registry.setdefault(m.group(3), m.group(2))
    # pass 2: sweep
    sites: list = []
    for p in files:
        sites.extend(sweep_file(p, entries, name_registry))
    sites.sort(key=lambda s: (SEVERITY_RANK[s["severity"]], s["file"], s["line"]))
    return sites


# --- outputs ------------------------------------------------------------------

def summarize(sites: list) -> dict:
    by_kind: dict = {}
    for s in sites:
        by_kind[s["kind"]] = by_kind.get(s["kind"], 0) + 1
    return {
        "total_sites": len(sites),
        "critical": sum(1 for s in sites if s["severity"] == "CRITICAL"),
        "by_kind": dict(sorted(by_kind.items())),
    }


def write_findings(catalog: dict, sites: list) -> dict:
    summary = summarize(sites)
    payload = {
        "schema": "flywheel_findings/v1",
        "task": "U.1",
        "catalog": {"path": str(CATALOG_PATH.relative_to(_REPO)).replace("\\", "/"),
                    "houdini_version": catalog["houdini_version"],
                    "blake2b": catalog["blake2b"]},
        "summary": summary,
        "findings": sites,
    }
    FINDINGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    FINDINGS_JSON.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                             encoding="utf-8", newline="\n")

    md = ["# U.1 wiring review — findings (severity-ranked)", "",
          f"Catalog: `{payload['catalog']['path']}` (build "
          f"{catalog['houdini_version']}, blake2b `{catalog['blake2b'][:12]}`)", "",
          f"**{summary['critical']} CRITICAL** of {summary['total_sites']} call sites. "
          f"By kind: " + ", ".join(f"{k}={v}" for k, v in summary["by_kind"].items()), ""]
    for sev in ("CRITICAL", "INFO"):
        group = [s for s in sites if s["severity"] == sev]
        if not group:
            continue
        md.append(f"## {sev} ({len(group)})")
        md.append("")
        cap = len(group) if sev == "CRITICAL" else 40
        for s in group[:cap]:
            md.append(f"- `{s['file']}:{s['line']}` **{s['kind']}** "
                      f"`{s['receiver']}.{s['call']}({s['index_expr']}, ...)` "
                      f"type={s['receiver_type']} — {s['detail']}")
        if len(group) > cap:
            md.append(f"- ... and {len(group) - cap} more (see JSON)")
        md.append("")
    FINDINGS_MD.write_text("\n".join(md), encoding="utf-8", newline="\n")
    return summary


# --- Ledger deposit (opt-in) ---------------------------------------------------

def deposit_finding_classes(sites: list, summary: dict) -> tuple:
    """One Confirmation/DeadEnd per verified finding CLASS via the §7.2 seam.
    Run under hython for the live build stamp (LedgerDeposit reads hou when present)."""
    sys.path.insert(0, str(_REPO / "python"))
    from synapse.science.deposit import LedgerDeposit  # noqa: PLC0415 — after path fix

    sink = LedgerDeposit()
    now = int(time.time())
    artifact = str(FINDINGS_JSON.relative_to(_REPO)).replace("\\", "/")
    n_arity_bad = summary["by_kind"].get("index-out-of-arity", 0)
    n_label_bad = summary["by_kind"].get("label-claim-mismatch", 0)
    n_arity_ok = summary["by_kind"].get("index-within-arity", 0) \
        + summary["by_kind"].get("label-claim-verified", 0)
    n_label_ok = summary["by_kind"].get("label-claim-verified", 0)

    sink({
        "surface": "wiring/setInput-literal-index-within-catalog-arity",
        "status": "champion" if n_arity_bad == 0 else "dead_end",
        "detail": (f"{n_arity_ok} literal-index call sites resolve within catalog "
                   f"arity; {n_arity_bad} overflow. Sweep artifact: {artifact}"),
        "timestamp": now, "kind": "wiring_review", "context": "flywheel U.1 REVIEW",
    })
    sink({
        "surface": "wiring/comment-label-claims-match-catalog-labels",
        "status": "champion" if n_label_bad == 0 else "dead_end",
        "detail": (f"{n_label_ok} label-claimed sites match the catalog label at "
                   f"their index; {n_label_bad} mismatch. Sweep artifact: {artifact}"),
        "timestamp": now, "kind": "wiring_review", "context": "flywheel U.1 REVIEW",
    })
    return sink.deposited, sink.failures


# --- queue append (opt-in; candidates are proposals — a human ratifies) --------

U2_CANDIDATES = [
    {
        "id": "U.2",
        "title": "Parameter-name truth: gate emitted parm()/setParm literals against "
                 "the nodetype catalog's live parm fingerprints",
        "status": "candidate",
        "evidence": [
            "harness/notes/verified_nodetype_catalog_21.0.671.json",
            ".claude/flywheel_u1_findings.json",
            "python/synapse/routing/planner.py",
            "python/synapse/routing/recipes/fx_recipes.py",
        ],
        "ratified": False,
        "note": "The nodetype catalog already carries ordered [(parm, type, default)] "
                "per resolved type — the same sweep pattern (createNode var map -> "
                "parm('x') literals) closes the loop nobody gates today.",
    },
    {
        "id": "U.3",
        "title": "Source-output-index truth: validate setInput's third arg against "
                 "catalog output_count/output_labels",
        "status": "candidate",
        "evidence": [
            "harness/notes/verified_connectivity_21.0.671.json",
            ".claude/flywheel_u1_findings.json",
        ],
        "ratified": False,
        "note": "v2 catalog now carries output_count + ordered output_labels (e.g. "
                "vellumconstraints out 1 = Constraint Geometry, relied on by "
                "solver.setInput(1, cloth, 1)); the U.1 sweep only proves the "
                "TARGET side.",
    },
    {
        "id": "U.4",
        "title": "Wire-time arity guard at the dynamic-index API boundary "
                 "(handlers_node/api_adapter setInput passthroughs)",
        "status": "candidate",
        "evidence": [
            ".claude/flywheel_u1_findings.json",
            "python/synapse/server/api_adapter.py",
            "python/synapse/server/handlers_node.py",
        ],
        "ratified": False,
        "note": "The sweep's dynamic-index INFO sites are runtime passthroughs with "
                "no catalog check; wiring.wire_by_label/catalog lookup can gate them "
                "at call time.",
    },
]


def append_queue_candidates() -> int:
    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    have = {c["id"] for c in queue["cycles"]}
    added = 0
    for cand in U2_CANDIDATES:
        if cand["id"] not in have:
            queue["cycles"].append(cand)
            added += 1
    if added:
        QUEUE_PATH.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8", newline="\n")
    return added


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deposit", action="store_true",
                    help="deposit per-class Ledger records (opt-in)")
    ap.add_argument("--queue-append", action="store_true",
                    help="append evidenced U.2+ candidates to the flywheel queue")
    a = ap.parse_args(argv)

    catalog = load_catalog()
    sites = run_sweep(catalog)
    summary = write_findings(catalog, sites)
    print(f"WIRING REVIEW: {summary['total_sites']} sites, "
          f"{summary['critical']} CRITICAL -> {FINDINGS_JSON}")
    for k, v in summary["by_kind"].items():
        print(f"  {k}: {v}")

    if a.deposit:
        deposited, failures = deposit_finding_classes(sites, summary)
        print(f"  ledger: deposited={deposited} failures={len(failures)}")
        for f in failures:
            print(f"  DEPOSIT-FAIL: {f}")
    if a.queue_append:
        print(f"  queue: appended {append_queue_candidates()} candidate(s) "
              f"(ratified=false — human flips)")

    return 1 if summary["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
