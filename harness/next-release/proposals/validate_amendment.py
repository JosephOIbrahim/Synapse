"""Offline validator for the PROPOSED vision/Grow amendment to the next-release graph.

    python harness/next-release/proposals/validate_amendment.py

Loads harness/next-release/graph.json and
harness/next-release/proposals/vision-grow.amendment.PROPOSED.json, checks the
amendment's structure against the graph, then runs each new node's closure predicate
and requires it to be red for its declared reason. One line per check, then a final
SUMMARY line. Exit 0 only if every check passes.

Checks added after the graph and truth review of the C0 scaffold:
- G1: no predicate finds the repo root by folder depth; each predicate is also copied
  to a temporary folder at a different depth, must resolve ROOT to this repository
  when run from the repo root, and must still be red for its declared reason.
- G2: a changed existing node whose new predicate file is not in the repo must carry
  the file's full draft (proposed_file) at the path its predicate names; the draft is
  written to the temporary folder only and must be red for its declared reason.
- G3: every .json path a predicate reads that some node owns belongs to the node itself
  or to a node it reaches through depends_on.
- G4: every node, new or existing, that an owner decision names is gate joe or has an
  owner decision proposing joe (proposed_gate); OD node ids resolve.
- T1: no bare "ADR-0002 Consequence N" cite in the amendment, README or C0 report.

Standard library only. No network, no JEV, no GPU, no Houdini. It never edits
graph.json or the amendment and never writes outside its own temporary folder:
predicates run with PYTHONDONTWRITEBYTECODE=1, -p no:cacheprovider and TEMP, TMP,
TMPDIR and SYNAPSE_LOG_DIR pointed into that folder.

Scope of the ownership check: graph.json already contains owner_files collisions
among EXISTING nodes (K1-K4). Those are printed as INFO and must match the
amendment's _known_existing_collisions list exactly; they are owner decisions, not
something this amendment may fix by editing graph.json. Any collision that involves a
NEW node fails. Overlap is prefix-aware: an entry ending in "/" owns everything under it.
"""
from __future__ import annotations

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
PREDICATE_DIR = "harness/next-release/proposals/predicates/"
STATUS = ("PROPOSED - not ratified; adoption is Joe's merge into graph.json followed by "
          "the JEV ranking in the lane README, section 2")
NODE_KEYS = ["id", "title", "owner_files", "depends_on", "why", "predicate", "gate", "effort"]
EDGE_KEYS = ["from", "to", "type", "why"]
GATES = {"crux", "joe"}
RULINGS = {"R1", "R2", "R3", "R4"}
STAGES = ["G1", "G2", "G3", "G4", "G5", "G6", "C1", "C2", "C3", "C4", "C5", "C6"]
TIMEOUT_S = 120

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


def main() -> int:
    try:
        graph = json.loads(GRAPH.read_text(encoding="utf-8"))
        amend = json.loads(AMENDMENT.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        record(False, "load", f"{type(exc).__name__}: {exc}")
        return finish()
    record(True, "load", f"graph.json ({len(graph['nodes'])} nodes, {len(graph['edges'])} edges); "
                         f"amendment ({len(amend.get('nodes', []))} nodes, {len(amend.get('edges', []))} edges)")

    # --- amendment header ----------------------------------------------------------
    record(amend.get("_status") == STATUS, "status", "_status is the PROPOSED adoption sentence")
    srcs = amend.get("_sources", [])
    blob = json.dumps(srcs)
    record(len(srcs) >= 5
           and "bbaeed26669b945c2811399b9bbae0a1a183dbd18b6bb57d121f7391d271bf43" in blob
           and "070904d4e06b202dbeeb86bccfd6041ae99ee455e13a82bcd34ce49412dd9647" in blob
           and "ADR-0002" in blob and "g0-receipt" in blob and "c0-report" in blob,
           "sources", "ADR-0002, G0 receipt, C0 report and both blueprints by sha256")

    old = {n["id"]: n for n in graph["nodes"]}
    new_nodes = amend.get("nodes", [])
    new: dict[str, dict] = {}
    dup = []
    for n in new_nodes:
        nid = n.get("id")
        if nid in old or nid in new:
            dup.append(nid)
        else:
            new[nid] = n
    record(not dup, "unique ids", f"{len(old)} existing + {len(new)} new" + (f"; duplicates {dup}" if dup else ""))
    bad_prefix = [i for i in new if not str(i).startswith("NR-VG-")]
    record(not bad_prefix, "new id prefix", "every new id starts with NR-VG-" + (f"; bad {bad_prefix}" if bad_prefix else ""))

    # --- node schema -----------------------------------------------------------------
    for nid, n in new.items():
        keys_ok = list(n.keys()) == NODE_KEYS
        filled = all(isinstance(n.get(k), str) and n[k].strip() for k in ("title", "why", "predicate", "gate", "effort"))
        lists = isinstance(n.get("owner_files"), list) and n["owner_files"] and isinstance(n.get("depends_on"), list)
        record(keys_ok and filled and bool(lists), f"schema {nid}",
               "keys id,title,owner_files,depends_on,why,predicate,gate,effort; fields non-empty")

    # --- proposed changes to existing nodes (the one exception) ---------------------
    merged = {k: json.loads(json.dumps(v)) for k, v in old.items()}
    for i, ch in enumerate(amend.get("_proposed_changes_to_existing", []), 1):
        nid, field = ch.get("node"), ch.get("field")
        rul = ch.get("ruling")
        rul_list = rul if isinstance(rul, list) else [rul]
        ok = (nid in old and field in old[nid] and ch.get("current") == old[nid][field]
              and "proposed" in ch and rul_list and all(r in RULINGS for r in rul_list))
        print(f"      change {i}: {nid}.{field} (ruling {'+'.join(map(str, rul_list))})", flush=True)
        print(f"        current : {json.dumps(ch.get('current'))[:300]}", flush=True)
        print(f"        proposed: {json.dumps(ch.get('proposed'))[:300]}", flush=True)
        record(ok, f"proposed change {i} {nid}.{field}",
               "existing node and field; 'current' equals graph.json; ruling in R1-R4")
        if ok:
            merged[nid][field] = ch["proposed"]
    merged.update(json.loads(json.dumps(new)))

    # --- gates ---------------------------------------------------------------------------
    bad_gate = [k for k, v in merged.items() if v.get("gate") not in GATES]
    record(not bad_gate, "gates", "every node's gate is crux or joe" + (f"; bad {bad_gate}" if bad_gate else ""))
    ods = amend.get("_owner_decisions", [])
    od_unresolved = [(od.get("id"), x) for od in ods for x in od.get("nodes", []) if x not in merged]
    record(not od_unresolved, "owner-decision nodes resolve", "every node an OD names exists in the merged view"
           + (f"; unresolved {od_unresolved}" if od_unresolved else ""))
    # Every node, new or existing, that waits on an owner decision is gate joe, or an OD
    # proposes moving its gate to joe (listed for Joe, never applied here).
    waits = {x for od in ods for x in od.get("nodes", []) if x in merged}
    gate_ods = {od["proposed_gate"]["node"]: od["id"] for od in ods
                if isinstance(od.get("proposed_gate"), dict) and od["proposed_gate"].get("to") == "joe"}
    not_joe = sorted(x for x in waits if merged[x]["gate"] != "joe" and x not in gate_ods)
    pending = sorted(f"{x} ({gate_ods[x]})" for x in waits if merged[x]["gate"] != "joe" and x in gate_ods)
    record(not not_joe, "owner-decision gates",
           f"{len(waits)} nodes (new and existing) wait on an owner decision; each is gate joe or has an OD proposing joe"
           + (f"; gate change proposed for {pending}" if pending else "") + (f"; not joe {not_joe}" if not_joe else ""))
    od_ids = {od.get("id") for od in ods}
    cited_text = [n["why"] for n in new.values()] + [json.dumps(ch) for ch in amend.get("_proposed_changes_to_existing", [])]
    undeclared = sorted({m for s in cited_text for m in re.findall(r"OD-\d\d", s)} - od_ids)
    record(not undeclared, "owner-decision refs", "every OD id cited in a new node's why or a proposed change is declared"
           + (f"; undeclared {undeclared}" if undeclared else ""))

    # --- edges -----------------------------------------------------------------------
    types = {e["type"] for e in graph["edges"]}
    existing_pairs = {(e["from"], e["to"], e["type"]) for e in graph["edges"]}
    edges = amend.get("edges", [])
    bad = []
    for e in edges:
        if list(e.keys()) != EDGE_KEYS:
            bad.append(f"keys {e}")
        elif e["type"] not in types:
            bad.append(f"type {e['type']}")
        elif e["from"] not in merged or e["to"] not in merged:
            bad.append(f"endpoint {e['from']}->{e['to']}")
        elif (e["from"], e["to"], e["type"]) in existing_pairs:
            bad.append(f"duplicate {e['from']}->{e['to']}")
        elif e["from"] not in new and e["to"] not in new:
            bad.append(f"edge between existing nodes {e['from']}->{e['to']}")
    record(not bad, "edges", f"{len(edges)} new edges; types within {sorted(types)}; endpoints resolve" + (f"; {bad}" if bad else ""))

    all_edges = graph["edges"] + edges
    unresolved = [(k, d) for k, v in merged.items() for d in v.get("depends_on", []) if d not in merged]
    record(not unresolved, "depends_on resolve", "every depends_on id exists" + (f"; {unresolved}" if unresolved else ""))
    incons = [(e["from"], e["to"]) for e in all_edges if e["type"] == "dep" and e["from"] in merged
              and e["to"] in merged and e["from"] not in merged[e["to"]].get("depends_on", [])]
    record(not incons, "dep edges match depends_on", "every dep edge's source is in its target's depends_on (merged view)"
           + (f"; {incons}" if incons else ""))

    adj: dict[str, set[str]] = {k: set() for k in merged}
    for k, v in merged.items():
        for d in v.get("depends_on", []):
            if d in adj:
                adj[d].add(k)
    for e in all_edges:
        if e["type"] == "dep" and e["from"] in adj and e["to"] in adj:
            adj[e["from"]].add(e["to"])
    cyc = find_cycle(adj)
    record(cyc is None, "acyclic", "depends_on plus dep edges, merged view" + (f"; cycle {' -> '.join(cyc)}" if cyc else ""))

    # --- ownership -------------------------------------------------------------------
    owned = [(k, f) for k, v in merged.items() for f in v.get("owner_files", [])]
    known = {frozenset(c["nodes"]): c["id"] for c in amend.get("_known_existing_collisions", [])}
    seen_existing: set[frozenset] = set()
    new_hits = []
    for i in range(len(owned)):
        for j in range(i + 1, len(owned)):
            (na, fa), (nb, fb) = owned[i], owned[j]
            if na == nb or not overlaps(fa, fb):
                continue
            if na in new or nb in new:
                new_hits.append(f"{na}:{fa} x {nb}:{fb}")
            else:
                pair = frozenset((na, nb))
                seen_existing.add(pair)
                info("existing collision", f"{known.get(pair, 'UNDECLARED')} {na}:{fa} x {nb}:{fb} (pre-existing in graph.json)")
    record(not new_hits, "owner_files exclusive (new nodes)", "no new node's owner_files overlap any other node, prefix-aware"
           + (f"; {new_hits}" if new_hits else ""))
    record(seen_existing == set(known), "existing collisions declared",
           f"{len(seen_existing)} pre-existing node pairs, all listed in _known_existing_collisions"
           + ("" if seen_existing == set(known) else f"; found {sorted(map(sorted, seen_existing))} declared {sorted(map(sorted, known))}"))
    under = [f for k in new for f in new[k]["owner_files"] if f.startswith("harness/next-release/")]
    record(not under, "no new receipts under harness/next-release/", "keeps clear of NR-FOLLOW-ON's blanket claim (OD-03)")
    info("predicate files", f"{PREDICATE_DIR} sits inside NR-FOLLOW-ON's harness/next-release/ claim and is in no node's owner_files (OD-03)")

    # --- coverage --------------------------------------------------------------------
    cov = amend.get("_coverage", {})
    miss = [s for s in STAGES if s not in cov or not cov[s].get("nodes")]
    badref = [(s, x) for s in cov for x in cov[s].get("nodes", []) if x not in merged]
    record(not miss and not badref, "coverage", "G1-G6 and C1-C6 each map to existing or new nodes"
           + (f"; missing {miss}" if miss else "") + (f"; unresolved {badref}" if badref else ""))

    # --- predicates not collected by pytest testpaths or CI ----------------------------
    record(*collection_check())

    # --- ADR-0002 consequence cites name their list (review T1) -----------------------
    record(*consequence_cite_check())

    # --- predicate sources: the new predicates plus the draft for a changed node -------
    markers = amend.get("_red_markers", {})
    sources: dict[str, tuple[str, str]] = {}   # node id -> (predicate target, source text)
    for nid, n in new.items():
        target = predicate_target(n["predicate"])
        if target and target.startswith(PREDICATE_DIR) and (ROOT / target).is_file():
            sources[nid] = (target, (ROOT / target).read_text(encoding="utf-8"))
    drafts = draft_sources(amend, sources)

    depth = [nid for nid, (_, src) in sources.items() if "parents[" in src]
    record(not depth, "root not found by folder depth",
           f"{len(sources)} predicates find the repo root from the working directory, none by parents[N]"
           + (f"; depth-based {depth}" if depth else ""))
    record(*receipt_reach_check(sources, merged))

    # --- red markers and predicate runs ----------------------------------------------
    with tempfile.TemporaryDirectory(prefix="vg-validate-") as tmp:
        env = predicate_env(Path(tmp))
        for nid, n in new.items():
            run_predicate(nid, n["predicate"], markers.get(nid), env)
        # The same predicates, copied outside the repo at a different folder depth and run
        # from the repo root: a predicate that located the root by depth would go red for
        # a false reason here (review G1).
        for nid, (target, src) in sources.items():
            if nid in drafts:
                continue
            copy = Path(tmp) / "relocated" / "a" / "b" / "c" / "d" / "e" / Path(target).name
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_text(src, encoding="utf-8")
            run_file(f"relocated predicate {nid}", nid, copy, Path(tmp) / "relocated", markers.get(nid), env)
        # Drafts for changed existing nodes, materialised in the temp folder only (review G2).
        for nid, (path, src) in drafts.items():
            copy = Path(tmp) / "draft" / path
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_text(src, encoding="utf-8")
            run_file(f"draft predicate {nid}", nid, copy, Path(tmp) / "draft", markers.get(nid), env)
    return finish()


def predicate_target(predicate: str) -> str | None:
    toks = shlex.split(predicate, posix=True)
    if toks[:3] != ["python", "-m", "pytest"] or len(toks) < 4:
        return None
    return toks[3]


def draft_sources(amend: dict, sources: dict) -> dict[str, tuple[str, str]]:
    """Each changed existing node whose new predicate file is not in the repo must carry
    that file's full draft in its change entry, at exactly the path the predicate names."""
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
        src = "\n".join(lines) + "\n" if carried else ""
        named = (src.lstrip().startswith('"""') and nid in src.split('"""')[1]) if carried else exists
        ok = (exists or carried) and named
        record(ok, f"draft predicate file {nid}",
               f"proposed predicate {target} is in the repo or carried in full as proposed_file at that path"
               + ("" if exists or carried else "; MISSING - a merge of this change alone would leave the node red for rc 4")
               + ("" if named else "; draft docstring does not name its node"))
        if carried and named:
            drafts[nid] = (target, src)
            sources[nid] = (target, src)
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


def run_file(name: str, nid: str, path: Path, base: Path, marker: str | None, env: dict[str, str]) -> None:
    """Run one predicate file that lives in the temp folder, from the repo root.

    A red run alone cannot tell a correct root from a wrong one (a wrong root makes every
    receipt look uncommitted, which raises the same marker), so the copy's module-level
    ROOT is loaded first and must equal this repository's root."""
    if not marker:
        record(False, name, f"no red marker declared in _red_markers for {nid}")
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
    _run(name + " (ROOT resolved to the repo root)",
         [sys.executable, "-m", "pytest", str(path), "-q", "-p", "no:cacheprovider",
          "-c", str(ini), "--rootdir", str(base)], marker, env)


def _run(name: str, cmd: list[str], marker: str, env: dict[str, str]) -> None:
    try:
        cp = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        record(False, name, f"timed out after {TIMEOUT_S} s")
        return
    out = (cp.stdout or "") + (cp.stderr or "")
    e_lines = [ln for ln in out.splitlines() if re.match(r"^E\s", ln) and marker in ln]
    summary = next((ln.strip() for ln in reversed(out.splitlines()) if ln.strip()), "")
    ok = cp.returncode == 1 and bool(e_lines)
    why = ("red for its declared reason" if ok else
           "rc must be 1 (tests failed), not 0 (green), 2 (collection/import error), 4 (usage/file not found) or 5 (no tests)"
           if cp.returncode != 1 else "rc 1 but the declared marker is not on any pytest 'E' line")
    record(ok, name, f"rc={cp.returncode}; {why}; {summary}")


def finish() -> int:
    total = len(_results)
    failed = sum(1 for r in _results if r[0] == "FAIL")
    verdict = "amendment structurally valid; every new predicate red for its declared reason" if not failed else "amendment INVALID"
    print(f"SUMMARY: {total} checks, {total - failed} passed, {failed} failed - {verdict}", flush=True)
    return 0 if not failed and total else 1


if __name__ == "__main__":
    sys.exit(main())
