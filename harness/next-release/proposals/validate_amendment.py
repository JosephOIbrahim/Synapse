"""Offline, merge-aware validator for the vision/Grow amendment to the next-release graph.

    python harness/next-release/proposals/validate_amendment.py [--graph PATH]

Loads harness/next-release/graph.json (or PATH: a scratch copy, for a mutation proof)
and harness/next-release/proposals/vision-grow.amendment.PROPOSED.json, checks the
amendment against the graph, then runs every amendment node's closure predicate. One
line per check, then a final SUMMARY line. Exit 0 only if every check passes.

Merge-aware since 2026-11-08, when Joe merged the OpenCV lane into graph.json (ADR-0002,
"Ratification and owner rulings (2026-11-08)", answer 2, quoted in the amendment's
_status). The amendment's _merge_record names the merged nodes, edges and changes, the
owner decisions ruled that day and the ruled why edits.

Merged nodes (now in graph.json):
- the graph entry uses the node schema and equals the amendment entry on id, title,
  owner_files, depends_on, predicate and effort; its gate is the amendment gate or the
  gate a ruled owner decision sets; its why is the amendment why with exactly the
  ruled why edits of _merge_record applied. An edit may drop only cites of ruled owner
  decisions, keeps every open one and dates what was ruled;
- each merged change to an existing node is applied the same way (the proposed value,
  plus the ruled why edits for a why), and a ruled proposed_gate is applied;
- every amendment edge whose two endpoints are in graph.json is in graph.json verbatim,
  and graph.json has no NR-VG- node or edge that the amendment does not carry;
- each merged predicate runs and its result is reported as INFO: green, or red with its
  first failure line. Only "it runs" (exit 0 or 1) is a check.
Unmerged nodes (the Grow lane; OD-01 is unruled) keep every check: schema, NR-VG- prefix,
edges, red for the declared reason in place and when relocated.
Across the merged view (graph.json plus the unmerged nodes and edges): structure,
prefix-aware ownership, wiring, cycle, coverage and not-collected checks.

Checks added after the graph and truth review of the C0 scaffold:
- G1: no predicate finds the repo root by folder depth; each predicate is also copied
  to a temporary folder at a different depth and must resolve ROOT to this repository
  when run from the repo root. An unmerged copy must still be red for its declared
  reason; a merged copy must end with the same exit code as the predicate in place.
- G2: a changed existing node whose new predicate file is not in the repo must carry
  the file's full draft (proposed_file) at the path its predicate names; the draft is
  written to the temporary folder only and must be red for its declared reason. Once
  the file is in the repo, the repo file is the predicate (INFO: equal to the carried
  draft or not; its owner may revise it).
- G3: every .json path a predicate reads that some node owns belongs to the node itself
  or to a node it reaches through depends_on.
- G4: every node, new or existing, that an OPEN owner decision names is gate joe or has
  an open owner decision proposing joe (proposed_gate); OD node ids resolve.
- T1: no bare "ADR-0002 Consequence N" cite in the amendment, README or C0 report.

Standard library only. No network, no JEV, no GPU, no Houdini. It never edits
graph.json or the amendment and never writes outside its own temporary folder:
predicates run with PYTHONDONTWRITEBYTECODE=1, -p no:cacheprovider and TEMP, TMP,
TMPDIR and SYNAPSE_LOG_DIR pointed into that folder.

Scope of the ownership check: graph.json contains owner_files collisions among
pre-amendment nodes (K1-K4). Those are printed as INFO and must match the amendment's
_known_existing_collisions list exactly; they are owner decisions. Any collision that
involves an amendment node, merged or not, fails. Overlap is prefix-aware: an entry
ending in "/" owns everything under it.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
GRAPH = ROOT / "harness" / "next-release" / "graph.json"
AMENDMENT = HERE / "vision-grow.amendment.PROPOSED.json"
ADR = ROOT / "docs" / "decisions" / "ADR-0002-retina-t1-optional-cuda-backend.md"
ADR_SECTION = "## Ratification and owner rulings (2026-11-08)"
PREDICATE_DIR = "harness/next-release/proposals/predicates/"
MERGE_DATE = "2026-11-08"
OWNER_CHOICE = ('"Merge with defaults (Recommended)": "Merge the OpenCV lane with these defaults for its '
                'open choices: the change-mask chain is added beside the meanStdDev census (OD-22); '
                'predicates stay under harness/next-release/proposals/ (OD-03); NR-GPU-QUALIFICATION\'s '
                'gate becomes joe (OD-23); the canary node stays parked behind the worker."')
STATUS = ("OpenCV lane MERGED into harness/next-release/graph.json on 2026-11-08 by Joe's choice "
          "(ADR-0002, 'Ratification and owner rulings (2026-11-08)', answer 2): " + OWNER_CHOICE
          + " Grow lane: still PROPOSED - not ratified (OD-01 unruled); its adoption is Joe's merge into "
          "graph.json followed by the JEV ranking in the lane README, section 2. The merged entries below "
          "stay as history; _merge_record names what merged and the ruled why edits.")
NODE_KEYS = ["id", "title", "owner_files", "depends_on", "why", "predicate", "gate", "effort"]
EDGE_KEYS = ["from", "to", "type", "why"]
GATES = {"crux", "joe"}
RULINGS = {"R1", "R2", "R3", "R4"}
STAGES = ["G1", "G2", "G3", "G4", "G5", "G6", "C1", "C2", "C3", "C4", "C5", "C6"]
TIMEOUT_S = 120
OD_RE = re.compile(r"OD-\d\d")

_results: list[tuple[str, str, str]] = []


def record(ok: bool, name: str, detail: str = "") -> bool:
    _results.append(("PASS" if ok else "FAIL", name, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f" - {detail}" if detail else ""), flush=True)
    return ok


def info(name: str, detail: str) -> None:
    print(f"INFO  {name} - {detail}", flush=True)


def overlaps(a: str, b: str) -> bool:
    if a == b:
        return True
    if a.endswith("/") and b.startswith(a):
        return True
    return b.endswith("/") and a.startswith(b)


def ekey(e: dict) -> str:
    return json.dumps(e, sort_keys=True)


def find_cycle(adj: dict[str, set[str]]) -> list[str] | None:
    WHITE, GREY, BLACK = 0, 1, 2
    color = {n: WHITE for n in adj}
    stack: list[str] = []

    def visit(n: str) -> list[str] | None:
        color[n] = GREY
        stack.append(n)
        for m in sorted(adj.get(n, ())):
            if color.get(m, WHITE) == GREY:
                return stack[stack.index(m):] + [m]
            if color.get(m, WHITE) == WHITE:
                found = visit(m)
                if found:
                    return found
        stack.pop()
        color[n] = BLACK
        return None

    for n in sorted(adj):
        if color[n] == WHITE:
            found = visit(n)
            if found:
                return found
    return None


def apply_edits(src: str, eds: list[dict]) -> tuple[str | None, str]:
    """Apply ruled why edits in order; each 'replace' text must occur exactly once."""
    out = src
    for ed in eds:
        rep = str(ed.get("replace", ""))
        n = out.count(rep) if rep else 0
        if n != 1:
            return None, f"edit text found {n} times, not once: {rep[:70]!r}"
        out = out.replace(rep, str(ed.get("with", "")))
    return out, ""


def adr_section() -> str:
    if not ADR.is_file():
        return ""
    text = ADR.read_text(encoding="utf-8")
    i = text.find(ADR_SECTION)
    if i < 0:
        return ""
    j = text.find("\n## ", i + len(ADR_SECTION))
    return text[i:] if j < 0 else text[i:j]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Merge-aware validator for the vision/Grow amendment.")
    ap.add_argument("--graph", type=Path, default=GRAPH,
                    help="graph file to check (default: the repo graph.json); a scratch copy for a mutation proof")
    gpath = ap.parse_args(argv).graph.resolve()
    try:
        graph = json.loads(gpath.read_text(encoding="utf-8"))
        amend = json.loads(AMENDMENT.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        record(False, "load", f"{type(exc).__name__}: {exc}")
        return finish()
    gname = "graph.json" if gpath == GRAPH.resolve() else f"{gpath.name} (not the repo graph)"
    record(True, "load", f"{gname} ({len(graph['nodes'])} nodes, {len(graph['edges'])} edges); "
                         f"amendment ({len(amend.get('nodes', []))} nodes, {len(amend.get('edges', []))} edges)")

    # --- amendment header ----------------------------------------------------------
    record(amend.get("_status") == STATUS, "status",
           "_status records the 2026-11-08 OpenCV-lane merge, quotes the owner's choice, keeps the Grow lane PROPOSED")
    record(OWNER_CHOICE in adr_section(), "owner choice verbatim",
           "the quoted choice appears verbatim in ADR-0002, 'Ratification and owner rulings (2026-11-08)'")
    srcs = amend.get("_sources", [])
    blob = json.dumps(srcs)
    record(len(srcs) >= 5
           and "bbaeed26669b945c2811399b9bbae0a1a183dbd18b6bb57d121f7391d271bf43" in blob
           and "070904d4e06b202dbeeb86bccfd6041ae99ee455e13a82bcd34ce49412dd9647" in blob
           and "ADR-0002" in blob and "g0-receipt" in blob and "c0-report" in blob,
           "sources", "ADR-0002, G0 receipt, C0 report and both blueprints by sha256")

    gnodes = {n["id"]: n for n in graph["nodes"]}
    am_list = amend.get("nodes", [])
    am_ids = [n.get("id") for n in am_list]
    am = {n.get("id"): n for n in am_list}
    changes = amend.get("_proposed_changes_to_existing", [])
    change_keys = [f"{c.get('node')}.{c.get('field')}" for c in changes]
    ods = amend.get("_owner_decisions", [])
    od_ids = {od.get("id") for od in ods}
    mr = amend.get("_merge_record") or {}
    ruled = mr.get("ruled") or {}
    open_ods = od_ids - set(ruled)
    m_listed = mr.get("merged_nodes") or []
    m_changes = set(mr.get("merged_changes") or [])
    merged_ids = [i for i in am_ids if i in gnodes]
    record(mr.get("date") == MERGE_DATE and bool(ruled) and set(ruled) <= od_ids
           and sorted(merged_ids) == sorted(m_listed) and m_changes <= set(change_keys),
           "merge record",
           f"dated {MERGE_DATE}; the {len(merged_ids)} amendment nodes in {gname} are the ones listed; "
           f"{len(m_changes)} merged changes exist; ruled {sorted(ruled)} are declared; {len(open_ods)} owner decisions stay open"
           + ("" if sorted(merged_ids) == sorted(m_listed) else f"; in graph {sorted(merged_ids)}, listed {sorted(m_listed)}")
           + ("" if m_changes <= set(change_keys) else f"; unknown changes {sorted(m_changes - set(change_keys))}"))

    dup = sorted({str(i) for i in am_ids if am_ids.count(i) > 1})
    old_ids = [i for i in gnodes if i not in am]
    record(not dup, "unique ids", f"{len(old_ids)} pre-amendment + {len(am)} amendment nodes ({len(merged_ids)} merged)"
           + (f"; duplicates {dup}" if dup else ""))
    unmerged = {i: n for i, n in am.items() if i not in gnodes}
    grow = set(next((od.get("nodes", []) for od in ods if od.get("id") == "OD-01"), []))
    record(set(unmerged) == grow and "OD-01" not in ruled, "Grow lane stays out",
           f"the {len(unmerged)} unmerged nodes are exactly OD-01's, and OD-01 is unruled"
           + ("" if set(unmerged) == grow else f"; unmerged {sorted(unmerged)}, OD-01 {sorted(grow)}"))
    bad_prefix = [i for i in am if not str(i).startswith("NR-VG-")]
    stray = [i for i in gnodes if str(i).startswith("NR-VG-") and i not in am]
    record(not bad_prefix and not stray, "new id prefix",
           f"every amendment id starts with NR-VG-; {gname} has no NR-VG- node the amendment lacks"
           + (f"; bad {bad_prefix}" if bad_prefix else "") + (f"; stray {stray}" if stray else ""))

    # --- node schema -----------------------------------------------------------------
    for nid, n in am.items():
        keys_ok = list(n.keys()) == NODE_KEYS
        filled = all(isinstance(n.get(k), str) and n[k].strip() for k in ("title", "why", "predicate", "gate", "effort"))
        lists = isinstance(n.get("owner_files"), list) and n["owner_files"] and isinstance(n.get("depends_on"), list)
        record(keys_ok and filled and bool(lists), f"schema {nid}",
               "keys id,title,owner_files,depends_on,why,predicate,gate,effort; fields non-empty")

    # --- ruled why edits (_merge_record) -----------------------------------------------
    edits = mr.get("ruled_why_edits") or []
    targets = set(merged_ids) | {k.split(".", 1)[0] for k in m_changes if k.endswith(".why")}
    by_node: dict[str, list[dict]] = {}
    for i, ed in enumerate(edits, 1):
        nid, rep, wit = ed.get("node"), str(ed.get("replace", "")), str(ed.get("with", ""))
        cr, cw = set(OD_RE.findall(rep)), set(OD_RE.findall(wit))
        problems = []
        if nid not in targets:
            problems.append(f"{nid} is neither a merged node nor a merged why change")
        if not rep or not wit or rep == wit or not str(ed.get("basis", "")).strip():
            problems.append("replace, with and basis must be non-empty, and with must differ")
        if (cr - cw) - set(ruled):
            problems.append(f"drops open owner decisions {sorted((cr - cw) - set(ruled))}")
        if cw & set(ruled) and MERGE_DATE not in wit:
            problems.append("cites a ruled owner decision without its date")
        if (cr | cw) - od_ids:
            problems.append(f"undeclared {sorted((cr | cw) - od_ids)}")
        record(not problems, f"ruled why edit {i} {nid}",
               "drops only ruled owner-decision cites, keeps every open one, dates what was ruled"
               + (f"; {problems}" if problems else ""))
        by_node.setdefault(str(nid), []).append(ed)

    # --- merged nodes: graph.json against the amendment -----------------------------
    ruled_gate = {od["proposed_gate"].get("node"): od["proposed_gate"].get("to") for od in ods
                  if od.get("id") in ruled and isinstance(od.get("proposed_gate"), dict)}
    for nid in merged_ids:
        a, g = am[nid], gnodes[nid]
        diffs = [k for k in ("id", "title", "owner_files", "depends_on", "predicate", "effort") if g.get(k) != a.get(k)]
        if list(g.keys()) != NODE_KEYS:
            diffs.append(f"keys {list(g.keys())}")
        if g.get("gate") not in {a.get("gate"), ruled_gate.get(nid)}:
            diffs.append(f"gate {g.get('gate')!r}")
        want, err = apply_edits(str(a.get("why", "")), by_node.get(nid, []))
        if want is None:
            diffs.append(err)
        elif g.get("why") != want:
            diffs.append("why is not the amendment why plus its ruled edits")
        record(not diffs, f"merged node {nid}",
               f"equals the amendment on id, title, owner_files, depends_on, predicate, effort; gate {g.get('gate')}; "
               f"why = amendment why + {len(by_node.get(nid, []))} ruled edit(s)" + (f"; differs: {diffs}" if diffs else ""))

    # --- changes to existing nodes: merged ones applied, unmerged ones still pending ---
    view = {k: json.loads(json.dumps(v)) for k, v in gnodes.items()}
    for i, ch in enumerate(changes, 1):
        nid, field = ch.get("node"), ch.get("field")
        key = f"{nid}.{field}"
        rul = ch.get("ruling")
        rul_list = rul if isinstance(rul, list) else [rul]
        base = (nid in gnodes and nid not in am and field in gnodes[nid] and "proposed" in ch
                and bool(rul_list) and all(r in RULINGS for r in rul_list))
        print(f"      change {i}: {key} (ruling {'+'.join(map(str, rul_list))})"
              + (" - MERGED 2026-11-08" if key in m_changes else ""), flush=True)
        print(f"        current : {json.dumps(ch.get('current'))[:300]}", flush=True)
        print(f"        proposed: {json.dumps(ch.get('proposed'))[:300]}", flush=True)
        if key in m_changes:
            want, err = ch.get("proposed"), ""
            if field == "why":
                want, err = apply_edits(str(want), by_node.get(str(nid), []))
            ok = base and want is not None and gnodes[nid].get(field) == want
            record(ok, f"merged change {i} {key}",
                   f"{gname} carries the proposed value"
                   + (f" plus {len(by_node.get(str(nid), []))} ruled edit(s)" if field == "why" else "")
                   + "; ruling in R1-R4" + (f"; {err}" if err else "") + ("" if ok else "; NOT APPLIED AS RECORDED"))
        else:
            ok = base and ch.get("current") == gnodes[nid].get(field)
            record(ok, f"proposed change {i} {key}",
                   "existing node and field; 'current' equals graph.json; ruling in R1-R4")
            if ok:
                view[nid][field] = ch["proposed"]
    for nid, gate in sorted(ruled_gate.items()):
        record(view.get(nid, {}).get("gate") == gate, f"ruled gate {nid}",
               f"gate is {gate}, as the ruled owner decision sets it (found {view.get(nid, {}).get('gate')!r})")
    view.update(json.loads(json.dumps(unmerged)))

    # --- gates ---------------------------------------------------------------------------
    bad_gate = [k for k, v in view.items() if v.get("gate") not in GATES]
    record(not bad_gate, "gates", "every node's gate is crux or joe" + (f"; bad {bad_gate}" if bad_gate else ""))
    od_unresolved = [(od.get("id"), x) for od in ods for x in od.get("nodes", []) if x not in view]
    record(not od_unresolved, "owner-decision nodes resolve", "every node an OD names exists in the merged view"
           + (f"; unresolved {od_unresolved}" if od_unresolved else ""))
    # Every node, new or existing, that waits on an OPEN owner decision is gate joe, or an
    # open OD proposes moving its gate to joe (listed for Joe, never applied here).
    waits = {x for od in ods if od.get("id") in open_ods for x in od.get("nodes", []) if x in view}
    gate_ods = {od["proposed_gate"]["node"]: od["id"] for od in ods if od.get("id") in open_ods
                and isinstance(od.get("proposed_gate"), dict) and od["proposed_gate"].get("to") == "joe"}
    not_joe = sorted(x for x in waits if view[x]["gate"] != "joe" and x not in gate_ods)
    pending = sorted(f"{x} ({gate_ods[x]})" for x in waits if view[x]["gate"] != "joe" and x in gate_ods)
    record(not not_joe, "owner-decision gates",
           f"{len(waits)} nodes (new and existing) wait on an open owner decision; each is gate joe or has an open OD proposing joe"
           + (f"; gate change proposed for {pending}" if pending else "") + (f"; not joe {not_joe}" if not_joe else ""))
    cited_text = ([str(n.get("why", "")) for n in am.values()] + [json.dumps(ch) for ch in changes]
                  + [str(view[k].get("why", "")) for k in sorted(targets) if k in view] + [json.dumps(edits)])
    undeclared = sorted({m for s in cited_text for m in OD_RE.findall(s)} - od_ids)
    record(not undeclared, "owner-decision refs",
           "every OD id cited in an amendment why, a change, a merged graph why or a ruled edit is declared"
           + (f"; undeclared {undeclared}" if undeclared else ""))

    # --- edges -----------------------------------------------------------------------
    gedges = graph["edges"]
    types = {e["type"] for e in gedges}
    gkeys = {ekey(e) for e in gedges}
    gpairs = {(e["from"], e["to"], e["type"]) for e in gedges}
    am_edges = amend.get("edges", [])
    am_keys = {ekey(e) for e in am_edges}
    m_edges = [e for e in am_edges if e.get("from") in gnodes and e.get("to") in gnodes]
    u_edges = [e for e in am_edges if not (e.get("from") in gnodes and e.get("to") in gnodes)]
    missing = [f"{e.get('from')}->{e.get('to')}" for e in m_edges if ekey(e) not in gkeys or list(e.keys()) != EDGE_KEYS]
    record(not missing and len(m_edges) == mr.get("merged_edges"), "merged edges",
           f"{len(m_edges)} amendment edges have both endpoints in {gname} (merge record: {mr.get('merged_edges')}); "
           "each is there verbatim" + (f"; missing or altered {missing}" if missing else ""))
    stray_e = [f"{e['from']}->{e['to']}" for e in gedges
               if (str(e["from"]).startswith("NR-VG-") or str(e["to"]).startswith("NR-VG-")) and ekey(e) not in am_keys]
    record(not stray_e, "no NR-VG- edge outside the amendment",
           f"every {gname} edge that touches an NR-VG- node is an amendment edge" + (f"; stray {stray_e}" if stray_e else ""))
    bad = []
    for e in u_edges:
        if list(e.keys()) != EDGE_KEYS:
            bad.append(f"keys {e}")
        elif e["type"] not in types:
            bad.append(f"type {e['type']}")
        elif e["from"] not in view or e["to"] not in view:
            bad.append(f"endpoint {e['from']}->{e['to']}")
        elif (e["from"], e["to"], e["type"]) in gpairs:
            bad.append(f"duplicate {e['from']}->{e['to']}")
        elif e["from"] not in unmerged and e["to"] not in unmerged:
            bad.append(f"edge between merged or existing nodes {e['from']}->{e['to']}")
    record(not bad, "unmerged edges", f"{len(u_edges)} Grow-lane edges; types within {sorted(types)}; endpoints resolve; "
           "each touches an unmerged node" + (f"; {bad}" if bad else ""))

    all_edges = gedges + u_edges
    unresolved = [(k, d) for k, v in view.items() for d in v.get("depends_on", []) if d not in view]
    record(not unresolved, "depends_on resolve", "every depends_on id exists" + (f"; {unresolved}" if unresolved else ""))
    incons = [(e["from"], e["to"]) for e in all_edges if e["type"] == "dep" and e["from"] in view
              and e["to"] in view and e["from"] not in view[e["to"]].get("depends_on", [])]
    record(not incons, "dep edges match depends_on", "every dep edge's source is in its target's depends_on (merged view)"
           + (f"; {incons}" if incons else ""))

    adj: dict[str, set[str]] = {k: set() for k in view}
    for k, v in view.items():
        for d in v.get("depends_on", []):
            if d in adj:
                adj[d].add(k)
    for e in all_edges:
        if e["type"] == "dep" and e["from"] in adj and e["to"] in adj:
            adj[e["from"]].add(e["to"])
    cyc = find_cycle(adj)
    record(cyc is None, "acyclic", "depends_on plus dep edges, merged view" + (f"; cycle {' -> '.join(cyc)}" if cyc else ""))

    # --- ownership -------------------------------------------------------------------
    owned = [(k, f) for k, v in view.items() for f in v.get("owner_files", [])]
    known = {frozenset(c["nodes"]): c["id"] for c in amend.get("_known_existing_collisions", [])}
    seen_existing: set[frozenset] = set()
    new_hits = []
    for i in range(len(owned)):
        for j in range(i + 1, len(owned)):
            (na, fa), (nb, fb) = owned[i], owned[j]
            if na == nb or not overlaps(fa, fb):
                continue
            if na in am or nb in am:
                new_hits.append(f"{na}:{fa} x {nb}:{fb}")
            else:
                pair = frozenset((na, nb))
                seen_existing.add(pair)
                info("existing collision", f"{known.get(pair, 'UNDECLARED')} {na}:{fa} x {nb}:{fb} (pre-existing in graph.json)")
    record(not new_hits, "owner_files exclusive (amendment nodes)",
           "no amendment node's owner_files, merged or not, overlap any other node, prefix-aware"
           + (f"; {new_hits}" if new_hits else ""))
    record(seen_existing == set(known), "existing collisions declared",
           f"{len(seen_existing)} pre-existing node pairs, all listed in _known_existing_collisions"
           + ("" if seen_existing == set(known) else f"; found {sorted(map(sorted, seen_existing))} declared {sorted(map(sorted, known))}"))
    under = [f for k in am for f in am[k]["owner_files"] if f.startswith("harness/next-release/")]
    record(not under, "no new receipts under harness/next-release/", "keeps clear of NR-FOLLOW-ON's blanket claim (OD-03)")
    info("predicate files", f"{PREDICATE_DIR} sits inside NR-FOLLOW-ON's harness/next-release/ claim and is in no node's "
                            "owner_files; the predicates stay there by Joe's 2026-11-08 ruling (OD-03)")

    # --- coverage --------------------------------------------------------------------
    cov = amend.get("_coverage", {})
    miss = [s for s in STAGES if s not in cov or not cov[s].get("nodes")]
    badref = [(s, x) for s in cov for x in cov[s].get("nodes", []) if x not in view]
    record(not miss and not badref, "coverage", "G1-G6 and C1-C6 each map to existing, merged or unmerged nodes"
           + (f"; missing {miss}" if miss else "") + (f"; unresolved {badref}" if badref else ""))

    # --- predicates not collected by pytest testpaths or CI ----------------------------
    record(*collection_check())

    # --- ADR-0002 consequence cites name their list (review T1) -----------------------
    record(*consequence_cite_check())

    # --- predicate sources: every amendment node's predicate plus the changed node's ---
    markers = amend.get("_red_markers", {})
    sources: dict[str, tuple[str, str]] = {}   # node id -> (predicate target, source text)
    for nid in am:
        target = predicate_target(str(view[nid].get("predicate", "")))
        if target and target.startswith(PREDICATE_DIR) and (ROOT / target).is_file():
            sources[nid] = (target, (ROOT / target).read_text(encoding="utf-8"))
    drafts = draft_sources(amend, sources)

    depth = [nid for nid, (_, src) in sources.items() if "parents[" in src]
    record(not depth, "root not found by folder depth",
           f"{len(sources)} predicates find the repo root from the working directory, none by parents[N]"
           + (f"; depth-based {depth}" if depth else ""))
    record(*receipt_reach_check(sources, view))

    # --- predicate runs: unmerged red for the declared reason; merged reported --------
    with tempfile.TemporaryDirectory(prefix="vg-validate-") as tmp:
        env = predicate_env(Path(tmp))
        rcs: dict[str, int | None] = {}
        for nid in am:
            if nid in unmerged:
                run_predicate(nid, unmerged[nid]["predicate"], markers.get(nid), env)
            else:
                rcs[nid] = run_merged(nid, str(view[nid]["predicate"]), env)
        for key in sorted(m_changes):
            nid, field = key.split(".", 1)
            if field == "predicate" and nid in view:
                rcs[nid] = run_merged(nid, str(view[nid]["predicate"]), env)
        # The same predicates, copied outside the repo at a different folder depth and run
        # from the repo root: a predicate that located the root by depth would go red for
        # a false reason here (review G1).
        for nid, (target, src) in sources.items():
            if nid in drafts:
                continue
            copy = Path(tmp) / "relocated" / "a" / "b" / "c" / "d" / "e" / Path(target).name
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_text(src, encoding="utf-8")
            run_file(f"relocated predicate {nid}", nid, copy, Path(tmp) / "relocated",
                     markers.get(nid) if nid in unmerged else None, env, rcs.get(nid))
        # Drafts for changed existing nodes whose file is not in the repo, materialised in
        # the temp folder only (review G2).
        for nid, (path, src) in drafts.items():
            copy = Path(tmp) / "draft" / path
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_text(src, encoding="utf-8")
            run_file(f"draft predicate {nid}", nid, copy, Path(tmp) / "draft", markers.get(nid), env, None)
    return finish()


def predicate_target(predicate: str) -> str | None:
    toks = shlex.split(predicate, posix=True)
    if toks[:3] != ["python", "-m", "pytest"] or len(toks) < 4:
        return None
    return toks[3]


def draft_sources(amend: dict, sources: dict) -> dict[str, tuple[str, str]]:
    """Each changed existing node's new predicate file is in the repo, or its full draft is
    carried in the change entry at exactly the path the predicate names. A repo file is the
    predicate; a carried draft is materialised in the temp folder only (returned)."""
    drafts: dict[str, tuple[str, str]] = {}
    for ch in amend.get("_proposed_changes_to_existing", []):
        if ch.get("field") != "predicate":
            continue
        nid = ch.get("node")
        target = predicate_target(str(ch.get("proposed", "")))
        pf = ch.get("proposed_file") or {}
        lines = pf.get("source_lines")
        exists = bool(target) and (ROOT / target).is_file()
        carried = bool(target) and pf.get("path") == target and isinstance(lines, list) and bool(lines)
        draft = "\n".join(lines) + "\n" if carried else ""
        src = (ROOT / target).read_text(encoding="utf-8") if exists else draft
        head = src.lstrip()
        named = head.startswith('"""') and nid in head.split('"""')[1]
        ok = (exists or carried) and named
        record(ok, f"predicate file {nid}",
               (f"{target} is in the repo" if exists else f"{target} is carried in full as proposed_file at that path")
               + ("" if exists or carried else "; MISSING - a merge of this change alone would leave the node red for rc 4")
               + ("" if named else "; docstring does not name its node"))
        if exists and carried:
            info(f"predicate file {nid}", "the repo file " + ("equals" if src == draft else "differs from")
                 + " the draft carried in proposed_file (history; the node's owner may revise the file)")
        if ok:
            sources[nid] = (target, src)
            if not exists:
                drafts[nid] = (target, src)
    return drafts


def receipt_reach_check(sources: dict, merged: dict) -> tuple[bool, str, str]:
    """Every .json path a predicate reads (a string constant under some node's owner_files)
    must belong to the node itself or to a node it reaches through depends_on, so that a
    depends_on scheduler never dispatches a node whose closure needs an unscheduled receipt
    (review G3)."""
    def ancestors(nid: str) -> set[str]:
        seen: set[str] = set()
        todo = list(merged.get(nid, {}).get("depends_on", []))
        while todo:
            d = todo.pop()
            if d not in seen and d in merged:
                seen.add(d)
                todo += merged[d].get("depends_on", [])
        return seen
    bad, n_reads = [], 0
    for nid, (_, src) in sources.items():
        consts = {c.value for c in ast.walk(ast.parse(src))
                  if isinstance(c, ast.Constant) and isinstance(c.value, str) and c.value.endswith(".json")
                  and "/" in c.value and " " not in c.value}
        reach = ancestors(nid) | {nid}
        for path in sorted(consts):
            owners = {k for k, v in merged.items() for f in v.get("owner_files", []) if overlaps(f, path)}
            if not owners:
                continue
            n_reads += 1
            if not owners & reach:
                bad.append(f"{nid} reads {path} owned by {sorted(owners)}")
    return (not bad, "receipt reads reachable through depends_on",
            f"{n_reads} owned .json reads across {len(sources)} predicates; each has an owner that is the node or a depends_on ancestor"
            + (f"; {bad}" if bad else ""))


def consequence_cite_check() -> tuple[bool, str, str]:
    """ADR-0002 has two numbered consequence lists; a bare 'Consequence N' is ambiguous."""
    files = [AMENDMENT, HERE / "README.md", ROOT / "docs" / "reviews" / "neural-growth-c0-report-2026-11-07.md"]
    hits = []
    for f in files:
        if not f.is_file():
            hits.append(f"{f.name}: missing")
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"ADR-0002 Consequences? \d", line):
                hits.append(f"{f.name}:{n}")
    return (not hits, "ADR-0002 consequence cites qualified",
            "every cite names the list ('Consequences of R1-R4' or 'Consequences') and an item"
            + (f"; bare cites at {hits}" if hits else ""))


def collection_check() -> tuple[bool, str, str]:
    import tomllib
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    testpaths = cfg.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("testpaths", [])
    hits = [t for t in testpaths if overlaps(t.rstrip("/") + "/", PREDICATE_DIR)]
    ci_paths = []
    for wf in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
        for line in wf.read_text(encoding="utf-8").splitlines():
            m = re.search(r"\bpytest\b(.*)$", line)
            if not m or line.lstrip().startswith("#"):
                continue
            toks = [t for t in shlex.split(m.group(1), posix=True) if not t.startswith("-")]
            args = [t for t in toks if "/" in t or t in (".", "harness", "tests")]
            ci_paths += args or ["<testpaths>"]
            for t in args:
                if overlaps(t.rstrip("/") + "/" if not t.endswith(".py") else t, PREDICATE_DIR) or t == ".":
                    hits.append(f"{wf.name}: {t}")
    ok = not hits
    return ok, "not collected by CI", (f"testpaths {testpaths}; CI pytest targets {sorted(set(ci_paths))}"
                                        + (f"; COLLECTED BY {hits}" if hits else ""))


def predicate_env(tmp: Path) -> dict[str, str]:
    env = dict(os.environ)
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(k, None)
    for sub in ("temp", "logs", "pycache"):
        (tmp / sub).mkdir(parents=True, exist_ok=True)
    env.update({
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": str(tmp / "pycache"),
        "TEMP": str(tmp / "temp"),
        "TMP": str(tmp / "temp"),
        "TMPDIR": str(tmp / "temp"),
        "SYNAPSE_LOG_DIR": str(tmp / "logs"),
    })
    return env


def run_predicate(nid: str, predicate: str, marker: str | None, env: dict[str, str]) -> None:
    name = f"predicate {nid}"
    toks = shlex.split(predicate, posix=True)
    if toks[:3] != ["python", "-m", "pytest"] or len(toks) < 4:
        record(False, name, f"not a 'python -m pytest <file>' predicate: {predicate}")
        return
    target = toks[3]
    if not target.startswith(PREDICATE_DIR) or not (ROOT / target).is_file():
        record(False, name, f"predicate file missing or outside {PREDICATE_DIR}: {target}")
        return
    if not marker:
        record(False, name, "no red marker declared in _red_markers")
        return
    head = (ROOT / target).read_text(encoding="utf-8").lstrip()
    if not (head.startswith('"""') and nid in head.split('"""')[1]):
        record(False, name, "predicate docstring does not name its node")
        return
    cmd = [sys.executable] + toks[1:]
    if "no:cacheprovider" not in toks:
        cmd += ["-p", "no:cacheprovider"]
    _run(name, cmd, marker, env)


def run_merged(nid: str, predicate: str, env: dict[str, str]) -> int | None:
    """Run a merged node's graph predicate. Its result is INFO; only 'it runs' is checked."""
    name = f"merged predicate {nid}"
    toks = shlex.split(predicate, posix=True)
    target = predicate_target(predicate)
    if not target or not (ROOT / target).is_file():
        record(False, name + " runs", f"not a 'python -m pytest <file>' predicate on a repo file: {predicate}")
        return None
    cmd = [sys.executable] + toks[1:]
    if "no:cacheprovider" not in toks:
        cmd += ["-p", "no:cacheprovider"]
    rc, out = _exec(cmd, env)
    if rc is None:
        record(False, name + " runs", f"timed out after {TIMEOUT_S} s")
        return None
    record(rc in (0, 1), name + " runs", f"rc={rc}; 0 (green) or 1 (red) - 2, 4 and 5 mean it cannot run")
    info(name, describe(rc, out))
    return rc


def run_file(name: str, nid: str, path: Path, base: Path, marker: str | None, env: dict[str, str],
             expect_rc: int | None) -> None:
    """Run one predicate file that lives in the temp folder, from the repo root.

    A red run alone cannot tell a correct root from a wrong one (a wrong root makes every
    receipt look uncommitted, which raises the same marker), so the copy's module-level
    ROOT is loaded first and must equal this repository's root. An unmerged copy (marker
    given) must be red for its marker; a merged copy must end with the in-place exit code."""
    if not marker and expect_rc is None:
        record(False, name, f"no red marker declared in _red_markers for {nid}, and no in-place result to match")
        return
    probe = ("import importlib.util, sys\n"
             "spec = importlib.util.spec_from_file_location('vg_predicate_probe', sys.argv[1])\n"
             "mod = importlib.util.module_from_spec(spec)\n"
             "spec.loader.exec_module(mod)\n"
             "print('ROOT=' + str(mod.ROOT))\n")
    try:
        cp = subprocess.run([sys.executable, "-c", probe, str(path)], cwd=str(ROOT), env=env,
                            capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        record(False, name, f"root probe timed out after {TIMEOUT_S} s")
        return
    got = next((ln[5:] for ln in cp.stdout.splitlines() if ln.startswith("ROOT=")), "")
    if not got or Path(got).resolve() != ROOT:
        record(False, name, f"the copy resolves ROOT to {got or '<nothing>'} (rc {cp.returncode}), not {ROOT}; "
                            "it would be red for a false reason")
        return
    # Pin pytest's rootdir to the temp copy's own folder. Without it pytest takes the
    # system temp folder as rootdir and scans it, which is slow and fails at random when
    # another process's temp file vanishes mid-scan (observed: rc 2 on one run).
    ini = base / "pytest.ini"
    if not ini.is_file():
        ini.write_text("[pytest]\n", encoding="utf-8")
    cmd = [sys.executable, "-m", "pytest", str(path), "-q", "-p", "no:cacheprovider", "-c", str(ini), "--rootdir", str(base)]
    if marker:
        _run(name + " (ROOT resolved to the repo root)", cmd, marker, env)
        return
    rc, out = _exec(cmd, env)
    record(rc == expect_rc, name + " (ROOT resolved to the repo root)",
           f"rc={rc}, the in-place predicate ended rc={expect_rc}; {describe(rc, out) if rc is not None else 'timed out'}")


def _exec(cmd: list[str], env: dict[str, str]) -> tuple[int | None, str]:
    try:
        cp = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return None, ""
    return cp.returncode, (cp.stdout or "") + (cp.stderr or "")


def describe(rc: int | None, out: str) -> str:
    summary = next((ln.strip() for ln in reversed(out.splitlines()) if ln.strip()), "")
    if rc == 0:
        return f"GREEN rc=0; {summary}"
    first = next((ln.strip() for ln in out.splitlines() if re.match(r"^E\s", ln)), "")
    return f"RED rc={rc}; first failure: {first or '<no E line>'}; {summary}"


def _run(name: str, cmd: list[str], marker: str, env: dict[str, str]) -> None:
    rc, out = _exec(cmd, env)
    if rc is None:
        record(False, name, f"timed out after {TIMEOUT_S} s")
        return
    e_lines = [ln for ln in out.splitlines() if re.match(r"^E\s", ln) and marker in ln]
    summary = next((ln.strip() for ln in reversed(out.splitlines()) if ln.strip()), "")
    ok = rc == 1 and bool(e_lines)
    why = ("red for its declared reason" if ok else
           "rc must be 1 (tests failed), not 0 (green), 2 (collection/import error), 4 (usage/file not found) or 5 (no tests)"
           if rc != 1 else "rc 1 but the declared marker is not on any pytest 'E' line")
    record(ok, name, f"rc={rc}; {why}; {summary}")


def finish() -> int:
    total = len(_results)
    failed = sum(1 for r in _results if r[0] == "FAIL")
    verdict = ("merge-aware: merged OpenCV lane matches the amendment and its rulings; every unmerged predicate red "
               "for its declared reason" if not failed else "amendment INVALID")
    print(f"SUMMARY: {total} checks, {total - failed} passed, {failed} failed - {verdict}", flush=True)
    return 0 if not failed and total else 1


if __name__ == "__main__":
    sys.exit(main())
