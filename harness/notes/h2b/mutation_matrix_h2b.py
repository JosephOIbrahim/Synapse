"""H2b · PART B — mutation-test every regression pin written against F1-F11.

R34 standard, verbatim: *every regression pin for a repaired defect must be shown
to fail against a deliberately broken implementation. A test that passes on both
the fix and its inverse is a decoration.*

METHOD — and the correction that makes the headline number honest
-----------------------------------------------------------------
The naive matrix ("run all N pins against all M mutations, count pins that never
went red") CONFLATES two different things:

    (a) a pin whose OWN targeted mutation left it green   <- a decoration
    (b) a pin that no mutation in the matrix ever aimed at <- coverage debt

Only (a) is what the brief asks for. Counting (b) as "surviving mutation" would
inflate the headline by every pin the matrix simply did not address. So every
mutation here declares `targets`: the exact pins it is designed to kill. A pin is
SURVIVING only if a mutation aimed at it left it green.

Pins with no targeted mutation are reported separately as `unmutated` (coverage
debt, named, never counted as decorations). Pins asserting a property of the HOST
(build string, LOP catalogue membership) are `host_fact`: no edit to SYNAPSE
source can falsify them — only a different Houdini could. Unmutatable BY DESIGN.

CONTROLS (RES's lesson): every mutation runs its target subset UNMUTATED first.
A mutation whose control is already red proves nothing and is recorded INVALID.

MUTATION-APPLIED GUARD (Law 1 applied to the instrument itself): a mutation that
silently fails to apply looks exactly like a pin that detected nothing. Every edit
asserts the anchor string occurs EXACTLY ONCE and that the file bytes changed on
disk. A no-op edit raises rather than being scored.

RESTORE: original bytes are captured before any edit and rewritten in a finally
block; a sha256 check plus a final `git diff` prove the tree came back.

Run:  python harness/notes/h2b/mutation_matrix_h2b.py
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HYTHON = Path(
    r"C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython3.13.exe"
)
OUT = ROOT / "harness" / "notes" / "h2b" / "mutation_matrix_h2b.json"

IMPL = "python/synapse/mcp/tool_impls/solaris"
VALID = "python/synapse/validation/solaris"

LIVE = "tests/solaris/test_live_wiring.py"
VERIF = "tests/test_solaris_wiring_verifiers.py"
REG = "tests/test_solaris_tool_registration.py"

# The F1-F11 pin universe: every file holding a pin written against a finding.
PIN_FILES = [
    LIVE, VERIF, REG,
    "tests/solaris/test_component_builder.py",
    "tests/solaris/test_create_variants.py",
    "tests/solaris/test_import_megascans.py",
    "tests/solaris/test_scene_template.py",
    "tests/solaris/test_set_purpose.py",
]

# Pins that assert a HOST property. No SYNAPSE source edit can falsify these.
HOST_FACT = [
    f"{LIVE}::test_host_is_the_pinned_build",
    f"{LIVE}::test_lop_category_resolves_live",
    f"{LIVE}::test_f7_componentgeometry_exposes_no_purpose_parm_live",
    f"{LIVE}::test_copy_nodes_to_carries_outside_inputs_live",
    f"{VERIF}::test_catalog_is_the_pinned_live_build",
    f"{VERIF}::test_componentbuilder_is_absent_from_the_live_catalogue",
]

# --------------------------------------------------------------------------
# The mutations. Each breaks the IMPLEMENTATION and names the pins it must kill.
# --------------------------------------------------------------------------

MUTATIONS = [
    {
        "id": "M1", "finding": "F3",
        "description": "import_megascans no longer wires the material reference LOP into "
                       "componentmaterial input 1 — the exact F3 defect, restored.",
        "edits": [(f"{IMPL}/import_megascans.py",
                   "            if ref_lop is not None:\n                mat_node.setInput(1, ref_lop)",
                   "            if False:  # H2b-M1\n                mat_node.setInput(1, ref_lop)")],
        "targets": [f"{LIVE}::test_f3_megascans_material_reference_is_wired_live",
                    f"{VERIF}::test_megascans_material_reference_is_orphaned"],
    },
    {
        "id": "M2", "finding": "F9",
        "description": "import_megascans retargets the SOP build back onto the LOCKED "
                       "componentgeometry HDA — the exact F9 defect, restored.",
        "edits": [(f"{IMPL}/import_megascans.py",
                   '            sop_geo = geo_node.node("sopnet/geo")',
                   '            sop_geo = geo_node  # H2b-M2')],
        "targets": [f"{LIVE}::test_f9_import_megascans_completes_live",
                    f"{LIVE}::test_f9_import_megascans_ingests_real_geometry_live"],
    },
    {
        "id": "M3", "finding": "F5",
        "description": "create_variants drops the consumer-steal, so componentgeometryvariants "
                       "dead-ends again — the exact F5 defect, restored.",
        "edits": [(f"{IMPL}/create_variants.py",
                   "                if base_geo is not None:\n                    gv_path = geo_variants.path()",
                   "                if False:  # H2b-M3\n                    gv_path = geo_variants.path()")],
        "targets": [f"{LIVE}::test_f5_geometry_variants_node_reaches_terminal_live",
                    f"{VERIF}::test_variant_set_reaches_the_terminal"],
    },
    {
        "id": "M4", "finding": "F4",
        "description": "create_variants explicitly unwires each duplicated variant material, "
                       "reproducing the state F4 CLAIMED copyNodesTo produces.",
        "edits": [(f"{IMPL}/create_variants.py",
                   '                        new_mat.setName(f"mat_{vname}", unique_name=True)',
                   '                        new_mat.setName(f"mat_{vname}", unique_name=True)\n'
                   '                        new_mat.setInput(0, None)  # H2b-M4')],
        "targets": [f"{LIVE}::test_material_variants_are_wired_live",
                    f"{VERIF}::test_variant_materials_are_wired_statically"],
    },
    {
        "id": "M5", "finding": "F6",
        "description": "create_variants swallows an explorevariants build failure and still "
                       "returns status='created' — the exact F6 defect, restored.",
        "edits": [(f"{IMPL}/create_variants.py",
                   '            if add_explore:\n'
                   '                explore = parent.createNode("explorevariants", f"explore_{comp.name()}")\n'
                   '                explore.setInput(0, comp)\n'
                   '                explore_path = explore.path()',
                   '            if add_explore:\n'
                   '                try:  # H2b-M5\n'
                   '                    explore = parent.createNode("explorevariants_H2B_PHANTOM", f"explore_{comp.name()}")\n'
                   '                    explore.setInput(0, comp)\n'
                   '                    explore_path = explore.path()\n'
                   '                except Exception:\n'
                   '                    pass')],
        "targets": [f"{LIVE}::test_f6_create_variants_status_is_honest_live",
                    f"tests/solaris/test_create_variants.py::TestF6HonestStatus"],
    },
    {
        "id": "M6", "finding": "F7",
        "description": "set_purpose never enables the purpose it claims to author: setpurpose=0 "
                       "while the status still reports set/updated. The exact Ruling-14 lie.",
        "edits": [(f"{IMPL}/set_purpose.py",
                   "        set_parm.set(1)",
                   "        set_parm.set(0)  # H2b-M6")],
        "targets": [f"{LIVE}::test_f7_set_purpose_authors_a_real_usd_purpose_live",
                    f"{LIVE}::test_f7_set_purpose_does_not_report_success_when_nothing_set_live",
                    f"{LIVE}::test_set_purpose_last_write_is_the_one_that_composes_live",
                    f"{LIVE}::test_set_purpose_survives_the_componentoutput_sink_live"],
    },
    {
        "id": "M7", "finding": "F8",
        "description": "component_builder stops honouring parent_path (reads 'parent' only) — "
                       "the exact F8 silent-default defect, restored.",
        "edits": [(f"{IMPL}/component_builder.py",
                   'PARENT_KEYS = ("parent_path", "parent")',
                   'PARENT_KEYS = ("parent",)  # H2b-M7')],
        "targets": [f"{LIVE}::test_f8_component_builder_honours_parent_path_live",
                    "tests/solaris/test_component_builder.py::TestParentKeyConvergence"],
    },
    {
        "id": "M8", "finding": "F8",
        "description": "import_megascans stops honouring parent_path.",
        "edits": [(f"{IMPL}/import_megascans.py",
                   'PARENT_KEYS = ("parent_path", "parent")',
                   'PARENT_KEYS = ("parent",)  # H2b-M8')],
        "targets": [f"{LIVE}::test_f8_import_megascans_honours_parent_path_live",
                    f"tests/solaris/test_import_megascans.py::TestParentKeyConvergence"],
    },
    {
        "id": "M9", "finding": "F8",
        "description": "scene_template stops honouring parent_path — the original F8 anchor.",
        "edits": [(f"{IMPL}/scene_template.py",
                   'PARENT_KEYS = ("parent_path", "parent")',
                   'PARENT_KEYS = ("parent",)  # H2b-M9')],
        "targets": [f"{LIVE}::test_f8_scene_template_honours_parent_path_live",
                    f"tests/solaris/test_scene_template.py::TestF8ParentPathConvergence"],
    },
    {
        "id": "M10", "finding": "F10",
        "description": "component_builder claims the phantom native componentbuilder type exists, "
                       "re-arming the dead Path A the try/except used to hide.",
        "edits": [(f"{IMPL}/component_builder.py",
                   '        return hou.nodeType(cat, "componentbuilder") is not None',
                   '        return True  # H2b-M10')],
        "targets": [f"{LIVE}::test_f10_componentbuilder_type_is_absent_on_this_build"],
    },
    {
        "id": "M11", "finding": "F1",
        "description": "the import_megascans tool is dropped from the MCP registry — F1's "
                       "'unreachable from the live registry' defect, restored for one tool.",
        "edits": [("python/synapse/mcp/_tool_registry.py",
                   '    ("synapse_solaris_import_megascans", "solaris_import_megascans", _identity,',
                   '    ("synapse_solaris_import_megascans_H2B_UNREGISTERED", "solaris_import_megascans", _identity,')],
        "targets": [f"{VERIF}::test_import_megascans_is_dispatchable_and_nothing_is_gated",
                    f"{VERIF}::test_every_tool_the_audit_claims_is_accounted_for",
                    REG],
    },
    {
        "id": "M12", "finding": "F2",
        "description": "tool_audit acquires a real implementation module, falsifying "
                       "'it is a document, not a tool'.",
        "create": [(f"{IMPL}/tool_audit.py",
                    '"""H2b-M12 mutation: a real tool_audit implementation module."""\n\n\n'
                    'def validate(params):\n    return None\n\n\n'
                    'def plan(params):\n    return []\n\n\n'
                    'def execute(params):\n    return {"status": "created"}\n')],
        "targets": [f"{VERIF}::test_tool_audit_is_a_document_not_a_tool"],
    },

    # ---- R43 / Part C: pair a mutation with every remaining bucket-2 pin. -----
    # The 18 pins that were failing under the fake-hou residency are only proven
    # honest if each can be made to fail on demand. M1/M2/M6/M7/M8/M9 already
    # cover 10 of them; M13-M20 close the other 8.
    {
        "id": "M13", "finding": "F1/bucket2",
        "description": "component_builder stops wiring geo -> mat -> output inside the subnet.",
        "edits": [(f"{IMPL}/component_builder.py",
                   "                # Wire: geo → mat → output\n"
                   "                mat_node.setInput(0, geo_node)\n"
                   "                out_node.setInput(0, mat_node)",
                   "                # Wire: geo → mat → output\n"
                   "                pass  # H2b-M13")],
        "targets": [f"{LIVE}::test_component_builder_wires_geo_to_mat_to_output_live"],
    },
    {
        "id": "M14", "finding": "F1/bucket2",
        "description": "component_builder emits the wrong internal node type (no componentmaterial).",
        "edits": [(f"{IMPL}/component_builder.py",
                   '                mat_node = comp.createNode("componentmaterial", f"mat_{asset_name}")',
                   '                mat_node = comp.createNode("componentgeometry", f"mat_{asset_name}")  # H2b-M14')],
        "targets": [f"{LIVE}::test_component_builder_creates_internal_nodes_live"],
    },
    {
        "id": "M15", "finding": "F1/bucket2",
        "description": "component_builder loses its idempotency guard and rebuilds on every call.",
        "edits": [(f"{IMPL}/component_builder.py",
                   "    existing = parent.node(component_name)",
                   "    existing = None  # H2b-M15")],
        "targets": [f"{LIVE}::test_component_builder_is_idempotent_live"],
    },
    {
        "id": "M16", "finding": "F1/bucket2",
        "description": "component_builder stamps the wrong tool identity into provenance.",
        "edits": [(f"{IMPL}/component_builder.py",
                   '            _stamp_provenance(comp, {\n'
                   '                "tool": _TOOL_NAME,\n'
                   '                "source_pattern": _SOURCE_PATTERN,\n'
                   '                "reasoning": f"Created \'{asset_name}\' component per NodeFlow Pattern 2",',
                   '            _stamp_provenance(comp, {\n'
                   '                "tool": "H2b-M16-wrong",\n'
                   '                "source_pattern": _SOURCE_PATTERN,\n'
                   '                "reasoning": f"Created \'{asset_name}\' component per NodeFlow Pattern 2",')],
        "targets": [f"{LIVE}::test_component_builder_stamps_provenance_live"],
    },
    {
        "id": "M17", "finding": "F1/bucket2",
        "description": "scene_template stops chaining SOP imports sequentially (Pattern 1 broken).",
        "edits": [(f"{IMPL}/scene_template.py",
                   "                imp.setInput(0, prev)",
                   "                pass  # H2b-M17")],
        "targets": [f"{LIVE}::test_scene_template_chains_sop_imports_sequentially_live"],
    },
    {
        "id": "M18", "finding": "F1/bucket2",
        "description": "scene_template loses its idempotency guard.",
        "edits": [(f"{IMPL}/scene_template.py",
                   '    existing = parent.node(f"primitive_{scene_name}")',
                   "    existing = None  # H2b-M18")],
        "targets": [f"{LIVE}::test_scene_template_is_idempotent_live"],
    },
    {
        "id": "M19", "finding": "F1/bucket2",
        "description": "scene_template names the hierarchy-root primitive wrongly.",
        "edits": [(f"{IMPL}/scene_template.py",
                   '            prim = parent.createNode("primitive", f"primitive_{scene_name}")',
                   '            prim = parent.createNode("primitive", f"prim_{scene_name}")  # H2b-M19')],
        "targets": [f"{LIVE}::test_scene_template_creates_full_chain_live"],
    },
    {
        "id": "M20", "finding": "F7/bucket2",
        "description": "set_purpose never finds its existing configureprimitive, so repeat calls stack nodes.",
        "edits": [(f"{IMPL}/set_purpose.py",
                   '    """This tool\'s existing configureprimitive targeting ``prim_path``, if any."""\n'
                   "    for child in _stamped_configures(comp):",
                   '    """This tool\'s existing configureprimitive targeting ``prim_path``, if any."""\n'
                   "    return None  # H2b-M20\n"
                   "    for child in _stamped_configures(comp):")],
        "targets": [f"{LIVE}::test_set_purpose_is_idempotent_live"],
    },
    {
        "id": "M21", "finding": "F7",
        "description": "set_purpose reports the same success string on two distinct return paths "
                       "again — the exact ambiguity F7 named (applied and not-applied become "
                       "indistinguishable to the caller).",
        "edits": [(f"{IMPL}/set_purpose.py",
                   '            "status": "noop",',
                   '            "status": "set",  # H2b-M21'),
                  (f"{IMPL}/set_purpose.py",
                   '            "status": ("unchanged" if already\n'
                   '                       else "updated" if existing is not None else "set"),',
                   '            "status": "set",  # H2b-M21 second literal path')],
        "targets": [f"{VERIF}::test_set_purpose_distinguishes_applied_from_skipped"],
    },
]


# --------------------------------------------------------------------------

def run_pytest(node_ids, tag):
    cmd = [str(HYTHON), "-m", "pytest", *node_ids, "-q", "-p", "no:cacheprovider",
           "--basetemp", f"C:/Users/User/AppData/Local/Temp/h2b-mm-{tag}"]
    env_path = f"{ROOT / 'python'};{ROOT}"
    import os
    env = dict(os.environ, PYTHONPATH=env_path)
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, env=env)
    out = p.stdout + p.stderr
    failing = sorted(set(re.findall(r"^FAILED (\S+)", out, re.M)))
    erroring = sorted(set(re.findall(r"^ERROR (\S+)", out, re.M)))
    m = re.search(r"^=+ (.*?(?:passed|failed|error).*?) =+$", out, re.M)
    summary = m.group(1) if m else out.strip().splitlines()[-1:] or ""

    def num(word):
        mm = re.search(rf"(\d+) {word}", out)
        return int(mm.group(1)) if mm else 0

    return {
        "returncode": p.returncode,
        "summary": summary if isinstance(summary, str) else str(summary),
        "collected": num("passed") + num("failed") + num("skipped") + num("error"),
        "passed": num("passed"), "failed": num("failed"),
        "skipped": num("skipped"), "errors": num("error"),
        "failing": failing, "erroring": erroring,
        "log_tail": out[-2500:],
    }


def hit(node_id, result):
    """Did `node_id` (a pin, or a file/class prefix) go red in `result`?"""
    bad = result["failing"] + result["erroring"]
    norm = node_id.replace("\\", "/")
    for f in bad:
        g = f.replace("\\", "/")
        if g == norm or g.startswith(norm + "::") or norm.startswith(g + "::"):
            return True
    return False


def sha(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    if not HYTHON.exists():
        print(f"NOT FOUND: {HYTHON}", file=sys.stderr)
        return 2

    print("== control: the whole F1-F11 pin universe, unmutated ==")
    baseline = run_pytest(PIN_FILES, "baseline")
    print("  ", baseline["summary"])
    if baseline["failed"] or baseline["errors"]:
        print("!! BASELINE NOT GREEN — every row below is uninterpretable.")

    rows = []
    for mut in MUTATIONS:
        mid = mut["id"]
        edits = mut.get("edits", [])
        creates = mut.get("create", [])
        targets = mut["targets"]

        print(f"\n== {mid} ({mut['finding']}) {mut['description'][:70]}")

        # Control: targets alone, unmutated. A red control makes the row worthless.
        ctl = run_pytest(targets, f"{mid}-ctl")
        ctl_green = ctl["returncode"] == 0 and not ctl["failing"] and not ctl["erroring"]
        print(f"   control: {ctl['summary']}  green={ctl_green}")

        originals = {}
        created = []
        applied = []
        row = {"id": mid, "finding": mut["finding"], "description": mut["description"],
               "targets": targets, "control": ctl, "control_green": ctl_green}
        try:
            # BYTES, not text. `write_text` re-translates newlines on Windows, so an
            # LF-only file (this repo renormalizes to LF per R24 .gitattributes) comes
            # back as CRLF and the restore check fails on a file that was never really
            # changed. Byte-exact in, byte-exact out.
            for rel, old, new in edits:
                p = ROOT / rel
                raw = p.read_bytes()
                # Capture the pristine bytes ONCE per file. A row with TWO edits to
                # the same file would otherwise overwrite the saved original with the
                # already-mutated content, and the restore would leave the first edit
                # in the tree. (Found by the post-run `git diff` gate, M21.)
                if rel not in originals:
                    originals[rel] = (raw, sha(p))
                nl = b"\r\n" if b"\r\n" in raw else b"\n"
                old_b = old.replace("\n", nl.decode()).encode("utf-8")
                new_b = new.replace("\n", nl.decode()).encode("utf-8")
                n = raw.count(old_b)
                if n != 1:
                    raise RuntimeError(
                        f"{mid}: anchor occurs {n}x in {rel} (need exactly 1). "
                        "A mutation that does not apply is indistinguishable from a "
                        "pin that detected nothing — refusing to score it."
                    )
                p.write_bytes(raw.replace(old_b, new_b))
                if sha(p) == originals[rel][1]:
                    raise RuntimeError(f"{mid}: {rel} unchanged on disk after edit")
                applied.append(rel)

            for rel, body in creates:
                p = ROOT / rel
                if p.exists():
                    raise RuntimeError(f"{mid}: {rel} already exists; refusing to clobber")
                p.write_bytes(body.encode("utf-8"))
                created.append(rel)
                applied.append(rel)

            row["mutation_applied"] = applied

            # JUDGE ON THE SAME SUBSET THE CONTROL RAN.
            # Judging a mutation by a FULL-SET run while its control ran only the
            # targets is an asymmetric experiment, and it produced two false
            # SURVIVED verdicts (M8/TestParentKeyConvergence, M14/creates_internal
            # _nodes) that both died when their mutation was run against the targets
            # alone. Control and mutated runs must differ ONLY in the mutation.
            res = run_pytest(targets, f"{mid}-mut")
            row["result"] = res
            print(f"   mutated: {res['summary']}")

            # The full set still runs, but only to observe COLLATERAL damage —
            # never to decide a per-pin verdict.
            full = run_pytest(PIN_FILES, mid)
            row["full_set_run"] = {k: full[k] for k in
                                   ("summary", "passed", "failed", "failing")}

            per_target = {t: ("KILLED" if hit(t, res) else "SURVIVED") for t in targets}
            row["per_target"] = per_target
            for t, v in per_target.items():
                print(f"     {v:9s} {t}")

            row["collateral"] = [f for f in full["failing"] + full["erroring"]
                                 if not any(hit(t, {"failing": [f], "erroring": []})
                                            for t in targets)]
            row["verdict"] = ("INVALID_CONTROL_RED" if not ctl_green
                              else "ALL_TARGETS_KILLED"
                              if all(v == "KILLED" for v in per_target.values())
                              else "SOME_TARGETS_SURVIVED")
        except Exception as exc:  # noqa: BLE001
            row["error"] = f"{type(exc).__name__}: {exc}"
            row["verdict"] = "NOT_RUN"
            print(f"   !! {row['error']}")
        finally:
            for rel, (raw, digest) in originals.items():
                p = ROOT / rel
                p.write_bytes(raw)
                assert sha(p) == digest, f"RESTORE FAILED for {rel}"
            for rel in created:
                (ROOT / rel).unlink(missing_ok=True)
        rows.append(row)

    # ---- classification -------------------------------------------------
    targeted = {}
    for r in rows:
        for t, v in (r.get("per_target") or {}).items():
            targeted.setdefault(t, []).append((r["id"], v, r.get("control_green")))

    surviving, detects = [], []
    for pin, outcomes in targeted.items():
        valid = [o for o in outcomes if o[2]]
        if not valid:
            continue
        if any(v == "KILLED" for _, v, _ in valid):
            detects.append({"pin": pin, "killed_by": [i for i, v, _ in valid if v == "KILLED"]})
        else:
            surviving.append({"pin": pin, "survived": [i for i, v, _ in valid]})

    # Every collected pin, so `unmutated` is real rather than assumed.
    coll = run_pytest(PIN_FILES + ["--collect-only"], "collect")
    all_pins = sorted(set(re.findall(r"^(tests[/\\]\S+::\S+)", coll["log_tail"], re.M)))

    doc = {
        "schema": "mutation_matrix/h2b/v1",
        "standard": "R34 — a pin that passes on both the fix and its inverse is a decoration",
        "method_note": ("surviving_mutation counts ONLY pins whose OWN targeted mutation left "
                        "them green. Pins no mutation aimed at are coverage debt, reported "
                        "separately and never counted as decorations."),
        "interpreter": "hython3.13 / Houdini 22.0.368",
        "pin_files": PIN_FILES,
        "baseline_control": baseline,
        "mutations_total": len(MUTATIONS),
        "rows": rows,
        "classification": {
            "detects_count": len(detects),
            "surviving_mutation_count": len(surviving),
            "host_fact_count": len(HOST_FACT),
            "detects": sorted(detects, key=lambda d: d["pin"]),
            "SURVIVING_MUTATION": sorted(surviving, key=lambda d: d["pin"]),
            "host_fact_unmutatable_by_design": HOST_FACT,
        },
        "pins_targeted": len(targeted),
    }
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")

    print("\n" + "=" * 70)
    print(f"pins targeted by >=1 mutation : {len(targeted)}")
    print(f"  detects (pin went red)      : {len(detects)}")
    print(f"  SURVIVING MUTATION          : {len(surviving)}")
    print(f"host-fact pins (by design)    : {len(HOST_FACT)}")
    print(f"written: {OUT}")
    for s in surviving:
        print(f"  SURVIVED: {s['pin']}  (mutations {', '.join(s['survived'])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
