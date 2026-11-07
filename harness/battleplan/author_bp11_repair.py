# author_bp11_repair.py - seat, 13:32. Two mid-wave legs after HARDEN's green receipt proved false (seat findings
# 13:14-13:25): BP11-HARDFIX (fix-forward on bp11/harden) and BP11-CRUX2 (referee on HARDFIX). Authored on Joe's
# standing pre-approval (2026-09-28 11:22). Writes the two mission JSONs, validates them, and compiles ONLY these two
# (prompts + waves/bp11.rows.repair.json). It does not touch the live manifest.
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from author_bp11 import fence, packet_line, OUTPUT_RULE, CRUX_COMMON, PLAN, BLUEPRINT
import mission_schema as ms
import compile_wave as cw

SHELL_RULE = (" Shell rule (seat, 13:05): keep `#` comments out of every quoted shell argument, including `python -c` "
              "and `bash -c`; Claude Code stops for a manual prompt on them and no one is at the keyboard. For any "
              "script longer than three lines, Write it to `.scratch/<name>.py` in your worktree (gitignored and "
              "allowed) and run that file with python. Never commit anything under `.scratch/`.")

HARDFIX = {
    "id": "BP11-HARDFIX", "band": "BUILD", "class": "build", "tier": "auto", "readonly": False,
    "deps": ["BP11-HARDEN", "BP11-CRUX"],
    "name": "HARDEN repair: Identify files restored with additive logging, a fail-closed ratchet, and behavior pins",
    "note": fence(16, "Added mid-wave by the seat on Joe's standing pre-approval (2026-09-28 11:22). Your worktree is "
        "cut from bp11/harden (tip fbd7eb8a), whose green receipt the seat found false; your packet lists the six "
        "verified defects with HARDEN's exact diff. FIRST read CRUX's verdicts: `git show "
        "bp11/crux:harness/battleplan/notes/BP11-CRUX_verdicts.md`. Scope: the six defects, plus any CRUX finding rated "
        "BROKEN or marked must-fix against a file in your touches. Every other CRUX finding goes to for_ruling with its "
        "anchor, never a silent skip. Restore each Identify file HARDEN edited from bp11/salience bytes (`git show "
        "bp11/salience:<path>` read through Python and written with write_bytes; checkout and restore are denied), then "
        "make each broad handler non-silent ADDITIVELY: `import logging` and one `_log = logging.getLogger(__name__)` "
        "per file, and one `_log.debug(...)` line at the top of each broad except body. Every original statement in the "
        "body stays; only a bare `pass` may become the debug line. No root-level logging calls anywhere in "
        "python/synapse/identify/. The ratchet fails closed: a file it cannot read or parse is printed as "
        "`UNPARSED <path>` and the default mode exits 1. The baseline `_rule` text becomes 'count may shrink, never "
        "grow'. Lowering a baseline is always allowed; raising one needs Joe's word." + " Windows CI (seat dry run 13:39-13:47, .token-saver/bp11/ci_dry, CI env and commands): the test command fails "
        "the same tests on master 312ed2cf and on bp11/salience, twice each, so none is BP11's. Windows + Python 3.11: "
        "six, namely test_pkg_bootstrap_invariant.py::test_r310_shapes_leave_no_runtime_divergence, "
        "test_routing.py::TestTieredRouter::test_latency_is_tracked, test_sessions.py::TestSessionManager::"
        "test_touch_updates_last_active and ::test_expire_stale, plus the two persistence tests. Windows + Python 3.14: "
        "two, test_prst_network_persistence.py::test_store_still_opens_after_a_search_then_abrupt_restart and "
        "::test_recall_survives_an_unrelated_prune. The clock ones follow Windows' 15.6 ms time.time() resolution "
        "before Python 3.13 (your Windows python reproduces them). Mark exactly these with pytest.mark.xfail(condition=..., "
        "reason=..., strict=False): sys.platform == 'win32' and sys.version_info < (3, 13) for the clock ones, "
        "sys.platform == 'win32' for the persistence ones; each reason names the cause and says BP12 fixes the root "
        "cause. Add the R310 marker only if R310 still fails once the clock markers are in (its subprocess runs "
        "perpetrator files). Never skip, never delete, never change an assertion. The seat re-runs the Windows dry "
        "run on 3.11 and 3.14 on your tip." + SHELL_RULE),
    "targets": [
        "T1) python/synapse/identify/{apply,facts,library,salience}.py equal their bp11/salience bytes except added "
        "logging lines (the import, the module logger, one `_log.debug` per broad handler); `git diff bp11/salience -- "
        "python/synapse/identify/` removes no line other than a bare `pass` replaced by a debug line.",
        "T2) scripts/except_ratchet.py fails closed on an unreadable or unparsable file (`UNPARSED <path>`, exit 1); "
        "tests/test_except_ratchet.py gains that control on a temporary root; the baseline `_rule` reads 'count may "
        "shrink, never grow'; docs/HARDENING_RATCHETS.md states both.",
        "T3) tests/test_identify_hardfix.py (new, fakes only, no hou): a plain parm is not an expression and a keyed "
        "parm is; summarize with a raising lookup returns the honest-unknown fallback; run_shadow releases its slot "
        "when job submission raises; every python/synapse/identify/*.py compiles.",
        "T4) The receipt restates HARDEN's rows 2 and 3 with corrected evidence, and gives every CRUX finding against "
        "HARDEN or a touched file a disposition: fixed (with anchor) or for_ruling (with reason).",
        "T5) Windows CI: the eight known Windows failures from the seat's dry run carry xfail(strict=False) markers "
        "with platform and version conditions and reasons; nothing is skipped, deleted or reworded.",
    ],
    "touches": [
        "python/synapse/identify/__init__.py", "python/synapse/identify/apply.py", "python/synapse/identify/compose.py",
        "python/synapse/identify/facts.py", "python/synapse/identify/library.py", "python/synapse/identify/salience.py",
        "python/synapse/cognitive/tools/sidefx_library.py", "python/synapse/panel/command_palette.py",
        "python/synapse/panel/selection_inspector.py", "python/synapse/panel/synapse_panel.py",
        "scripts/except_ratchet.py", "scripts/probe_identify.py", "tests/test_except_ratchet.py",
        "tests/fixtures/except_ratchet_baseline.json", "tests/test_identify_hardfix.py", "tests/test_identify_apply.py",
        "tests/test_identify_compose.py", "tests/test_identify_library.py", "tests/test_identify_facts_lop.py",
        "tests/test_identify_salience.py", "tests/panel/test_identify_button.py", "docs/HARDENING_RATCHETS.md",
        "tests/test_pkg_bootstrap_invariant.py", "tests/test_routing.py", "tests/test_sessions.py",
        "tests/test_prst_network_persistence.py",
    ],
    "acceptance": [
        {"predicate": "`python -m compileall -q python/synapse/identify scripts` exits 0 on the leg tip",
         "evidence": "check"},
        {"predicate": "pytest passes on the leg tip for tests/test_identify_*.py, tests/panel/test_identify_button.py and "
                      "tests/test_except_ratchet.py with no collection error; the pass counts are in the receipt",
         "evidence": "test"},
        {"predicate": "`git diff bp11/salience -- python/synapse/identify/` removes no line other than a bare `pass`, and "
                      "grep finds no root-level `logging.<level>(` call in python/synapse/identify/", "evidence": "check"},
        {"predicate": "scripts/except_ratchet.py exits 1 and names the file when a scanned module cannot be parsed "
                      "(control in tests/test_except_ratchet.py), and exits 0 on the leg tip with every identify file at 0",
         "evidence": "test"},
        {"predicate": "each pin in tests/test_identify_hardfix.py fails when the matching HARDEN defect (packet items 2-4) "
                      "is re-applied; the three mutations and their outcomes are in the receipt", "evidence": "test"},
        {"predicate": "every CRUX finding against HARDEN or a touched file has a disposition in the receipt (fixed with "
                      "anchor, or for_ruling with reason)", "evidence": "receipt"},
        {"predicate": "on the leg's Windows python, pytest over tests/test_routing.py, tests/test_sessions.py, "
                      "tests/test_prst_network_persistence.py and tests/test_pkg_bootstrap_invariant.py (-m 'not needs_houdini') "
                      "reports 0 failed, with the known cases as xfailed", "evidence": "test"},
    ],
    "crucible_criteria": CRUX_COMMON + [
        "the crucible re-applies each of the six seat defects one at a time and proves a test or the ratchet bites on each",
        "the crucible confirms the Identify diff against bp11/salience is additive"],
    "source": {"doc": PLAN, "anchor": "seat findings 13:14-13:25 (.token-saver/bp11/seat_findings.md); HARDEN rows 2-3"},
}

CRUX2 = {
    "id": "BP11-CRUX2", "band": "TRUST", "class": "crucible", "tier": "referee", "readonly": True,
    "deps": ["BP11-HARDFIX"],
    "name": "CRUX2: adversarial re-verification of BP11-HARDFIX, and closure of every CRUX finding",
    "note": fence(20, "Read-only on product files. Added mid-wave by the seat on Joe's standing pre-approval. Re-run every "
        "HARDFIX row in a fresh `git clone --shared` of bp11/hardfix, which carries the whole Identify chain plus HARDEN "
        "and the repair. Read CRUX's verdicts first (`git show bp11/crux:harness/battleplan/notes/BP11-CRUX_verdicts.md`) "
        "and give each finding a closure line: closed by HARDFIX (anchor), for_ruling in HARDFIX's receipt, or open. "
        "Your packet holds the six seat defects and a mutation seed for each; re-apply each in your clone and record "
        "bite, survived or crash. Rate bp11/hardfix as the merge candidate: SOUND, SOUND-WITH-NITS or BROKEN. gui_probe "
        "rows stay UNKNOWN: the seat closes them by computer use after the wave. Check the Windows xfail markers: each "
        "is conditioned to Windows (and to Python < 3.13 for the clock ones), carries a reason, and no assertion or test "
        "body changed; remove one marker in your clone and show the test fails on your Windows python." + SHELL_RULE),
    "targets": [
        "T1) harness/battleplan/notes/BP11-CRUX2_verdicts.md: the verdict on bp11/hardfix with every row anchored, and a "
        "closure table for every CRUX finding.",
        "T2) harness/battleplan/notes/BP11-CRUX2_mutations.json: the six seed mutations plus at least two of the "
        "crucible's own, each with its target row and outcome.",
    ],
    "touches": ["harness/battleplan/notes/BP11-CRUX2_verdicts.md", "harness/battleplan/notes/BP11-CRUX2_mutations.json"],
    "acceptance": [
        {"predicate": "every HARDFIX acceptance row has a CRUX2 verdict with a crucible anchor", "evidence": "check"},
        {"predicate": "the six seed mutations and at least two crucible-authored ones are recorded, each labelled bite, "
                      "survived or crash", "evidence": "check"},
        {"predicate": "every CRUX finding has a closure line", "evidence": "check"},
        {"predicate": "gui_probe rows are UNKNOWN in the verdicts, never pass", "evidence": "check"},
    ],
    "crucible_criteria": ["the crucible flips no contract feature and edits no product file",
                          "a leg with any UNKNOWN acceptance is at best SOUND-WITH-NITS, never SOUND",
                          "any hash of a committed file is taken over git blob bytes (`git cat-file blob`), never a "
                          "Windows checkout"],
    "source": {"doc": BLUEPRINT, "anchor": "sec. 3 Rules; seat findings 13:14-13:25"},
}

if __name__ == "__main__":
    rows = []
    for m in (HARDFIX, CRUX2):
        m["note"] = packet_line(m["id"]) + m["note"] + OUTPUT_RULE
        errs = ms.validate_mission(m)
        if errs:
            raise SystemExit(f"{m['id']} failed validation: {errs}")
        (HERE / "missions" / f"{m['id']}.json").write_text(json.dumps(m, indent=2, ensure_ascii=True) + "\n",
                                                          encoding="utf-8")
        row = cw.leg_row(m)
        (HERE / "prompts" / f"{m['id']}.md").write_text(cw.fill_prompt(m, row), encoding="utf-8")
        rows.append(row)
        print(f"{m['id']}: tier={row.get('tier')} branch={row['branch']} deps={row['deps']} prompt={row['prompt']}")
    (HERE / "waves" / "bp11.rows.repair.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False),
                                                         encoding="utf-8")
    print("wrote waves/bp11.rows.repair.json")
