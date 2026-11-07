# author_bp11_idfix2.py - seat, 17:18. Joe approved (17:16, "continue with your stated plan"): one tiny repair leg after
# CRUX2 for the summary path. IDFIX's BOM fix only strips at the very start of the text, but real corpus bodies read
# 'Title\n\n\ufeff#type: node\n\nSummary.\n\n:include ...', so PolyExtrude still shows '#type: node'. Held until CRUX2
# settles; then run 5 (1 turn) dispatches it. Verified by the seat with a corpus sweep and a live G2 re-run.
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from author_bp11 import fence, packet_line, OUTPUT_RULE, CRUX_COMMON, BLUEPRINT
from author_bp11_repair import SHELL_RULE
import mission_schema as ms
import compile_wave as cw

IDFIX2 = {
    "id": "BP11-IDFIX2", "band": "BUILD", "class": "build", "tier": "auto", "readonly": False,
    "deps": ["BP11-IDFIX", "BP11-CRUX2"],
    "name": "Identify summaries from real help pages: skip markup paragraphs after the title (the corpus shape)",
    "note": fence(10, "Added by the seat on Joe's word (2026-09-28 17:16). Your worktree is cut from bp11/idfix. IDFIX's "
        "_strip_help_header only strips a BOM and '#key: value' lines at the very START of the text, but the real corpus "
        "body for PolyExtrude is 'PolyExtrude\\n\\n\\ufeff#type: node\\n\\nExtrudes polygonal faces and edges.\\n\\n:include "
        "/shelf/polyextrude#includeme:' (help_summary(['nodes/sop/polyextrude']) with SYNAPSE_SIDEFX_CORPUS_ROOT = "
        "G:/HOUDINI22/_CORPUS; your packet has it). summary_paragraph drops the title, then returns the directive paragraph, so "
        "the bubble still reads '#type: node'. IDFIX's test passed on a synthetic text that starts with the BOM. Fix in "
        "library.py only: before choosing the head, drop every paragraph that is help markup alone (after stripping U+FEFF, "
        "each non-empty line is a '#key: value' directive or a ':name ...:' include), wherever it sits. Then sweep the real "
        "corpus: for every node help page the library indexes, count summaries that still start with markup ('#', ':', "
        "U+FEFF, '@', '=', '{') before and after your change, and report both counts and the first ten offenders. Fix any "
        "other markup class the sweep finds only when the same paragraph rule covers it; otherwise list it in for_ruling. "
        "Keep HARDFIX's rules: additive logging only, no root-level logging calls." + SHELL_RULE),
    "targets": [
        "T1) library.py: markup-only paragraphs (U+FEFF, '#key: value' directives, ':name ...:' includes) are skipped wherever "
        "they sit, so the first prose paragraph after the title wins or the honest unknown does.",
        "T2) tests/test_identify_library.py: a test on the exact real corpus shape above returns 'Extrudes polygonal faces and "
        "edges.', and a corpus-gated test (skipped with a reason when the corpus root is absent) asserts no indexed SOP/LOP "
        "summary starts with markup.",
        "T3) The receipt reports the sweep: pages scanned, markup-leading summaries before and after, first ten offenders.",
    ],
    "touches": ["python/synapse/identify/library.py", "tests/test_identify_library.py"],
    "acceptance": [
        {"predicate": "pytest passes on the leg tip for tests/test_identify_*.py, tests/panel/test_identify_button.py and "
                      "tests/test_except_ratchet.py; counts in the receipt", "evidence": "test"},
        {"predicate": "summarize('operator:Sop/polyextrude::2.0') against the real corpus returns ('Extrudes polygonal faces "
                      "and edges.', 'library')", "evidence": "check"},
        {"predicate": "the corpus sweep reports markup-leading summaries before and after, with 0 after for the classes the "
                      "rule covers", "evidence": "check"},
        {"predicate": "scripts/except_ratchet.py exits 0; grep finds no root-level logging call in python/synapse/identify/",
         "evidence": "check"},
    ],
    "crucible_criteria": CRUX_COMMON + ["the crucible removes the markup-paragraph skip and proves the real-shape test bites"],
    "source": {"doc": BLUEPRINT, "anchor": "sec. 2 exact sources; seat finding 17:10 (.token-saver/bp11/seat_findings.md)"},
}

if __name__ == "__main__":
    m = IDFIX2
    m["note"] = packet_line(m["id"]) + m["note"] + OUTPUT_RULE
    errs = ms.validate_mission(m)
    if errs:
        raise SystemExit(f"validation: {errs}")
    (HERE / "missions" / "BP11-IDFIX2.json").write_text(json.dumps(m, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    row = cw.leg_row(m)
    (HERE / "prompts" / "BP11-IDFIX2.md").write_text(cw.fill_prompt(m, row), encoding="utf-8")
    (HERE / "waves" / "bp11.rows.idfix2.json").write_text(json.dumps([row], indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"BP11-IDFIX2: tier={row.get('tier')} branch={row['branch']} deps={row['deps']}")