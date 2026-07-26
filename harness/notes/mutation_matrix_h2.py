"""H2 · PART B — mutation matrix for every regression pin written against F1–F11.

R34 standard: *a pin must be shown to FAIL against a deliberately broken
implementation. A test that passes on both the fix and its inverse is a
decoration.*

Method
------
For each mutation: apply a surgical edit to the IMPLEMENTATION (never the test),
run the FULL 83-pin F1–F11 set under hython, record exactly which pins went red,
restore. A control row runs unmutated first; if the control is not green nothing
downstream is believable (RES's hard-won lesson — every subset gets a control).

Because the whole pin set runs on every row, the output is a true matrix: for
each pin we learn whether ANY mutation could turn it red.

Honest classification (this is the part that matters)
-----------------------------------------------------
A pin that never goes red is NOT automatically a decoration. Three classes:

  detects        — went red for >=1 mutation. The pin works.
  host_fact      — asserts a property of the HOST (build number, LOP catalogue
                   membership). No edit to SYNAPSE source can falsify it; only a
                   different Houdini could. Unmutatable BY DESIGN, not a
                   decoration. Listed separately and never counted as one.
  SURVIVING      — its subject WAS mutated and it stayed green anyway.
                   This is the decoration class. It is the headline number.

Usage
-----
    hython3.13 harness/notes/mutation_matrix_h2.py --verify-anchors
    hython3.13 harness/notes/mutation_matrix_h2.py --json harness/notes/mutation_matrix_h2.json

Never run under stock python: tests/solaris all-skips there and every row would
be a vacuous green — a Law 1 violation in the instrument that enforces Law 1.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
IMPL = REPO / "python" / "synapse" / "mcp" / "tool_impls" / "solaris"
REGISTRY = REPO / "python" / "synapse" / "mcp" / "_tool_registry.py"

# The three files holding every pin written against F1–F11.
PIN_FILES = [
    "tests/solaris/test_live_wiring.py",
    "tests/test_solaris_wiring_verifiers.py",
    "tests/test_solaris_tool_registration.py",
]

# Pins that assert a HOST property. No source edit can falsify these; they are
# unmutatable by construction and are reported as their own class rather than
# being smuggled into the decoration count.
HOST_FACT_PINS = {
    "test_host_is_the_pinned_build",
    "test_lop_category_resolves_live",
    "test_f10_componentbuilder_type_is_absent_on_this_build",
    "test_componentbuilder_is_absent_from_the_live_catalogue",
    "test_catalog_is_the_pinned_live_build",
    "test_f7_componentgeometry_exposes_no_purpose_parm_live",
    "test_copy_nodes_to_carries_outside_inputs_live",
}


class Mutation:
    def __init__(self, mid, finding, path, old, new, intent, targets):
        self.id = mid
        self.finding = finding
        self.path = path
        self.old = old
        self.new = new
        self.intent = intent
        self.targets = targets  # what we EXPECT to go red; recorded, not enforced


M = Mutation

MUTATIONS = [
    # ---- F3 · the material Reference LOP must reach componentmaterial input 1
    M("M1", "F3", IMPL / "import_megascans.py",
      "            if ref_lop is not None:\n                mat_node.setInput(1, ref_lop)",
      "            if ref_lop is not None:\n                pass  # MUTATED M1: F3 material rewiring removed",
      "orphan the material Reference LOP again (the original F3 defect)",
      ["test_f3_megascans_material_reference_is_wired_live"]),

    # ---- F9 · usdimport must target the writable interior, not the locked HDA
    M("M2", "F9", IMPL / "import_megascans.py",
      '            usd_imp = sop_geo.createNode("usdimport", "import_usdc")',
      '            usd_imp = geo_node.createNode("usdimport", "import_usdc")  # MUTATED M2',
      "createNode back into the locked componentgeometry HDA (the original F9 defect)",
      ["test_f9_import_megascans_completes_live",
       "test_f9_import_megascans_ingests_real_geometry_live"]),

    # ---- F5 · the variant set must reach the terminal
    M("M3", "F5", IMPL / "create_variants.py",
      "                                consumer.setInput(idx, geo_variants)",
      "                                pass  # MUTATED M3: F5 terminal rewiring removed",
      "dead-end componentgeometryvariants again -> two terminal LOPs",
      ["test_f5_geometry_variants_node_reaches_terminal_live"]),

    # ---- F6 · a swallowed failure must not report status="created"
    M("M4", "F6", IMPL / "create_variants.py",
      '                explore = parent.createNode("explorevariants", f"explore_{comp.name()}")\n'
      "                explore.setInput(0, comp)\n"
      "                explore_path = explore.path()",
      "                try:  # MUTATED M4: bare except restored\n"
      '                    explore = parent.createNode("explorevariantsBOGUS", f"explore_{comp.name()}")\n'
      "                    explore.setInput(0, comp)\n"
      "                    explore_path = explore.path()\n"
      "                except Exception:\n"
      "                    pass",
      "reintroduce silent false-success: the node fails to build, status stays 'created'",
      ["test_f6_create_variants_status_is_honest_live"]),

    # ---- F7 · the repair must actually AUTHOR a purpose, not merely stop lying
    M("M5", "F7", IMPL / "set_purpose.py",
      "        pattern_parm.set(prim_path)\n        set_parm.set(1)\n        value_parm.set(usd_token)",
      "        pattern_parm.set(prim_path)\n        set_parm.set(0)  # MUTATED M5: purpose never enabled\n"
      "        value_parm.set(usd_token)",
      "author nothing while still reporting success (the original F7 no-op)",
      ["test_f7_set_purpose_authors_a_real_usd_purpose_live",
       "test_set_purpose_last_write_is_the_one_that_composes_live"]),

    # ---- F7/Law 3 · three outcomes need three words
    M("M6", "F7", IMPL / "set_purpose.py",
      '            "status": ("unchanged" if already\n'
      '                       else "updated" if existing is not None else "set"),',
      '            "status": "set",  # MUTATED M6: Law 3 collapse - always claims a fresh write',
      "collapse the honest status vocabulary back to an unconditional 'set'",
      ["test_set_purpose_is_idempotent_live",
       "test_set_purpose_distinguishes_applied_from_skipped"]),

    # ---- F8 · parent_path is the convergent key (three tools, three rows)
    M("M7", "F8", IMPL / "scene_template.py",
      'PARENT_KEYS = ("parent_path", "parent")',
      'PARENT_KEYS = ("parent",)  # MUTATED M7',
      "scene_template ignores parent_path -> silently builds into /stage",
      ["test_f8_scene_template_honours_parent_path_live"]),

    M("M8", "F8", IMPL / "component_builder.py",
      'PARENT_KEYS = ("parent_path", "parent")',
      'PARENT_KEYS = ("parent",)  # MUTATED M8',
      "component_builder ignores parent_path",
      ["test_f8_component_builder_honours_parent_path_live"]),

    M("M9", "F8", IMPL / "import_megascans.py",
      'PARENT_KEYS = ("parent_path", "parent")',
      'PARENT_KEYS = ("parent",)  # MUTATED M9',
      "import_megascans ignores parent_path",
      ["test_f8_import_megascans_honours_parent_path_live"]),

    # ---- core wiring · geo -> mat -> out
    M("M10", "core", IMPL / "component_builder.py",
      "                mat_node.setInput(0, geo_node)\n                out_node.setInput(0, mat_node)",
      "                pass  # MUTATED M10: geo->mat->out wiring removed",
      "leave the component's three internal nodes unwired",
      ["test_component_builder_wires_geo_to_mat_to_output_live"]),

    # ---- core wiring · the scene_template chain
    M("M11", "core", IMPL / "scene_template.py",
      "            rs.setInput(0, prev)",
      "            pass  # MUTATED M11: render_settings detached from the chain",
      "detach karmarendersettings from the sequential chain",
      # H2 NOTE: this row turns NOTHING red. Both pins that claim to verify the
      # scene_template chain miss a detached karmarendersettings — see finding
      # H2-F3. A candidate closing pin was drafted and is recorded in the
      # receipt; it is NOT added here, because PART B's standing order is
      # "REPORT IT as a finding, do not quietly rewrite it."
      ["test_scene_template_creates_full_chain_live",
       "test_scene_template_topology_is_fully_wired"]),

    # ---- core wiring · sopimport sequencing
    M("M12", "core", IMPL / "scene_template.py",
      "                imp.setInput(0, prev)",
      "                pass  # MUTATED M12: sop imports no longer chained",
      "stop chaining sopimport nodes sequentially",
      ["test_scene_template_chains_sop_imports_sequentially_live"]),

    # ---- F1 · registration reachability
    M("M13", "F1", REGISTRY,
      '("synapse_solaris_set_purpose", "solaris_set_purpose", _identity,',
      '("synapse_solaris_set_purposeXX", "solaris_set_purpose", _identity,  # MUTATED M13',
      "unregister one Solaris tool from the MCP registry (the original F1 defect)",
      ["test_active_tool_is_in_the_registry[synapse_solaris_set_purpose-solaris_set_purpose]"]),

    # ---- F3 static · the orphan check itself
    M("M14", "F3", IMPL / "import_megascans.py",
      '                ref_lop = comp.createNode("reference", f"mtl_ref_{asset_name}")',
      '                ref_lop = comp.createNode("reference", f"mtlref{asset_name}")  # MUTATED M14',
      "rename the material reference LOP - breaks any name-coupled static check",
      ["test_megascans_material_reference_is_orphaned"]),
]


# --------------------------------------------------------------------------
def hython() -> str:
    return sys.executable


def run_pins(basetemp: Path, verbose: bool = False) -> tuple[set[str], dict, list[str]]:
    """Run the full F1–F11 pin set. Return (failed_pin_names, summary, all_pin_names).

    `all_pin_names` is harvested from a -v run. It is NOT taken from
    `--collect-only -q`: this repo's pytest config renders that as an indented
    TREE (<Dir>/<Module>/<Function>), not as `path::name` lines, so the obvious
    parse silently yields zero pins — which would make the surviving-mutation
    count vacuously 0. Caught by this harness's own control (Law 1).
    """
    cmd = [hython(), "-m", "pytest", *PIN_FILES, "-p", "no:cacheprovider",
           "--basetemp", str(basetemp), "--no-header", "-rf",
           "-v" if verbose else "-q"]
    proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    out = proc.stdout + proc.stderr

    failed = set()
    for line in out.splitlines():
        m = re.match(r"^(?:FAILED|ERROR)\s+(\S+?)::(\S+?)(?:\s|$)", line)
        if m:
            failed.add(m.group(2))

    seen = []
    for line in out.splitlines():
        m = re.match(r"^\S+?::(\S+?)\s+(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)", line)
        if m and m.group(1) not in seen:
            seen.append(m.group(1))

    tail = [l for l in out.splitlines() if " passed" in l or " failed" in l or "error" in l.lower()]
    summary = {
        "returncode": proc.returncode,
        "summary_line": tail[-1] if tail else "(no summary line)",
        "collected": _int(re.search(r"collected (\d+) item", out)),
        "passed": _int(re.search(r"(\d+) passed", out)),
        "failed": _int(re.search(r"(\d+) failed", out)),
        "errors": _int(re.search(r"(\d+) error", out)),
    }
    return failed, summary, seen


def _int(m):
    return int(m.group(1)) if m else 0


def _enc(pattern: str, blob: bytes) -> bytes:
    """Encode a \\n-written pattern to match `blob`'s actual line endings.

    The mutations below are authored with LF. If the file on disk is CRLF, a
    naive .encode() silently fails to match on every multi-line anchor — and a
    mutation that does not apply is scored as 'the pin survived', manufacturing
    a false decoration. So the anchor is translated to the file's own ending.
    """
    if b"\r\n" in blob:
        return pattern.replace("\n", "\r\n").encode("utf-8")
    return pattern.encode("utf-8")


def verify_anchors() -> list[dict]:
    """Every mutation's anchor must appear EXACTLY once. Law 1 for the harness."""
    report = []
    for mut in MUTATIONS:
        # Verify through the SAME byte path the mutation uses. An anchor check
        # that normalises line endings while the mutation does not would pass
        # here and silently no-op there.
        blob = mut.path.read_bytes()
        n = blob.count(_enc(mut.old, blob))
        report.append({
            "id": mut.id, "finding": mut.finding,
            "file": str(mut.path.relative_to(REPO)).replace("\\", "/"),
            "occurrences": n, "ok": n == 1,
            "line_ending": "CRLF" if b"\r\n" in blob else "LF",
        })
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=str, default=None)
    ap.add_argument("--verify-anchors", action="store_true")
    args = ap.parse_args()

    anchors = verify_anchors()
    bad = [a for a in anchors if not a["ok"]]
    if args.verify_anchors or bad:
        for a in anchors:
            flag = "OK " if a["ok"] else "BAD"
            print(f"[{flag}] {a['id']:4s} {a['finding']:5s} x{a['occurrences']}  {a['file']}")
        if bad:
            print(f"\nANCHOR FAILURE: {len(bad)} mutation(s) do not match exactly once.")
            print("Refusing to run: a mutation that does not apply would be scored as")
            print("'pin survived', manufacturing a false decoration.")
            return 2
        if args.verify_anchors:
            print("\nAll anchors resolve exactly once.")
            return 0

    # The tree must be clean BEFORE we start, or a pre-existing edit gets
    # blamed on this harness's restore path.
    pre = subprocess.run(["git", "status", "--porcelain", "--", "python/"],
                         cwd=str(REPO), capture_output=True, text=True).stdout.strip()
    if pre:
        print("REFUSING TO RUN: python/ is dirty before mutation. Restore it first.")
        print(pre)
        return 4

    basetemp = REPO / ".mm_h2_tmp"
    basetemp.mkdir(exist_ok=True)

    # ---- CONTROL ---------------------------------------------------------
    print("=== CONTROL (unmutated) ===")
    ctrl_failed, ctrl_summary, all_pins = run_pins(basetemp / "control", verbose=True)
    print(f"  {ctrl_summary['summary_line']}")
    print(f"  harvested {len(all_pins)} pin names")
    control_green = ctrl_summary["failed"] == 0 and ctrl_summary["errors"] == 0
    if not control_green:
        print("  CONTROL IS NOT GREEN — every row below is uninterpretable.")
        print(f"  failing: {sorted(ctrl_failed)}")
    if not all_pins:
        print("  HARVESTED ZERO PINS — the classification would be vacuously 0.")
        return 5

    rows = []
    for mut in MUTATIONS:
        # BYTES, not text. read_text/write_text round-trips LF -> CRLF on
        # Windows, so a content-perfect restore still leaves every line of the
        # file modified in git. The first run of this harness did exactly that
        # and reported "restore failed" against a byte-identical tree.
        original = mut.path.read_bytes()
        try:
            mutated = original.replace(_enc(mut.old, original),
                                       _enc(mut.new, original), 1)
            assert mutated != original, f"{mut.id}: replacement was a no-op"
            mut.path.write_bytes(mutated)
            failed, summary, _ = run_pins(basetemp / mut.id)
        finally:
            mut.path.write_bytes(original)  # ALWAYS restore, byte-exact

        newly_red = sorted(failed - ctrl_failed)
        expected_hit = [t for t in mut.targets if t in failed]
        rows.append({
            "id": mut.id,
            "finding": mut.finding,
            "file": str(mut.path.relative_to(REPO)).replace("\\", "/"),
            "intent": mut.intent,
            "expected_red": mut.targets,
            "expected_red_that_went_red": expected_hit,
            "expected_red_that_STAYED_GREEN": [t for t in mut.targets if t not in failed],
            "all_newly_red": newly_red,
            "newly_red_count": len(newly_red),
            "summary": summary,
            "verdict": "DETECTED" if newly_red else "NO_PIN_NOTICED",
        })
        mark = "RED" if newly_red else "!! NOTHING WENT RED !!"
        print(f"{mut.id:4s} [{mut.finding:5s}] {mark:24s} newly_red={len(newly_red)}  {mut.intent}")
        if newly_red:
            for n in newly_red[:6]:
                print(f"        - {n}")

    # ---- classification --------------------------------------------------
    ever_red = set()
    for r in rows:
        ever_red.update(r["all_newly_red"])

    detects, host_fact, surviving = [], [], []
    for p in all_pins:
        base = p.split("[")[0]
        if p in ever_red:
            detects.append(p)
        elif base in HOST_FACT_PINS:
            host_fact.append(p)
        else:
            surviving.append(p)

    result = {
        "schema": "mutation_matrix/h2/v1",
        "standard": "R34 — every regression pin must FAIL against a deliberately broken implementation",
        "interpreter": sys.version.split()[0],
        "executable": sys.executable,
        "pin_files": PIN_FILES,
        "pins_total": len(all_pins),
        "control": {"green": control_green, **ctrl_summary,
                    "failing": sorted(ctrl_failed)},
        "mutations_total": len(rows),
        "mutations_that_no_pin_noticed": [r["id"] for r in rows if not r["all_newly_red"]],
        "rows": rows,
        "classification": {
            "detects_count": len(detects),
            "host_fact_count": len(host_fact),
            "surviving_mutation_count": len(surviving),
            "detects": sorted(detects),
            "host_fact_unmutatable_by_design": sorted(host_fact),
            "SURVIVING_MUTATION": sorted(surviving),
        },
    }

    print("\n=== CLASSIFICATION ===")
    print(f"  pins total                    : {len(all_pins)}")
    print(f"  detects (went red >=1 row)    : {len(detects)}")
    print(f"  host-fact (unmutatable)       : {len(host_fact)}")
    print(f"  SURVIVING MUTATION            : {len(surviving)}")
    for s in sorted(surviving):
        print(f"      - {s}")

    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")

    # tree must be clean when we are done
    st = subprocess.run(["git", "status", "--porcelain"], cwd=str(REPO),
                        capture_output=True, text=True).stdout.strip()
    dirty = [l for l in st.splitlines()
             if not l.endswith(("mutation_matrix_h2.py", "mutation_matrix_h2.json"))
             and ".mm_h2_tmp" not in l]
    print(f"\ntree clean after restore: {not dirty}")
    if dirty:
        print("DIRTY (restore failed!):")
        for d in dirty:
            print("   ", d)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
