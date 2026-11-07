# author_bp11_idfix.py - seat, 16:40. After the GUI gates on merged master 9e7feb34 (16:26-16:35): G6 FAILED (bubbles reach
# disk: install_save_callbacks() never runs in the product path), G2 showed polyextrude's summary as '#type: node' (BOM),
# and G5's 200-node run took ~40 s (211 ms per uncached lookup, all 200 composed though 60 show). BP11-IDFIX fixes those
# three on top of bp11/hardfix; CRUX2 is re-scoped to review bp11/idfix (HARDFIX + IDFIX) as the merge candidate.
# Authored on Joe's standing pre-approval. Writes the two missions, validates, compiles ONLY these two.
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from author_bp11 import fence, packet_line, OUTPUT_RULE, CRUX_COMMON, PLAN, BLUEPRINT
from author_bp11_repair import SHELL_RULE, CRUX2
import mission_schema as ms
import compile_wave as cw

IDFIX = {
    "id": "BP11-IDFIX", "band": "BUILD", "class": "build", "tier": "auto", "readonly": False,
    "deps": ["BP11-HARDFIX"],
    "name": "Identify gate fixes: save callbacks installed on show, BOM-safe summaries, capped and memoized lookups",
    "note": fence(14, "Added by the seat after the GUI gates on merged master 9e7feb34 (Houdini 22.0.400, 16:26-16:35; the "
        "evidence is in your packet). Your worktree is cut from bp11/hardfix. G6 FAILED, bubbles reach disk: "
        "install_save_callbacks() is called only by scripts/probe_identify.py and a test, never by the product path, so a GUI "
        "save kept 60 sentinels in the .hip (hython count 60, raw bytes 60). G2 showed polyextrude's summary as '#type: node': "
        "its help text starts with a UTF-8 BOM, so the '#type:' header line was not skipped. G5 responsiveness holds (max "
        "main-thread gap 92.6 ms against an idle 93.5 ms), but the 200-node run took about 40 s end to end: library.summarize "
        "costs about 211 ms per node, uncached, and the panel worker composes all 200 though show() keeps 60. Fix exactly "
        "these three: (1) show(), and so toggle and /identify, installs the BeforeSave/AfterSave callbacks idempotently before "
        "its first write, in apply.py; (2) the summary path strips a leading U+FEFF and skips '#key: value' header lines, so "
        "the first prose sentence wins or the honest unknown does; (3) the panel worker caps paths to apply.CAP before reading "
        "facts and composing while the flash still reports the full selection count, and summarize memoizes per (help_url, "
        "hda_help) for the life of the process. Keep HARDFIX's additive-logging rule: no root-level logging calls, and no "
        "deleted statement in python/synapse/identify/ that a fix does not need. F4 (a standalone sentinel line inside artist "
        "text) is out of scope and stays a known issue. Live GUI re-runs of G2, G5 and G6 are the seat's: mark them UNKNOWN."
        + SHELL_RULE),
    "targets": [
        "T1) apply.py: show() installs the save callbacks idempotently; tests/test_identify_idfix.py pins that a show() on a "
        "fake hou registers exactly one hipFile callback, and that before_save strips every block while after_save restores it.",
        "T2) library.py: a leading BOM and '#key: value' header lines are skipped; a test with a BOM-prefixed help text whose "
        "first lines are '#type: node' and '#context: sop' returns the prose sentence, and returns the honest unknown when no "
        "prose follows.",
        "T3) synapse_panel.py worker: paths capped to apply.CAP before facts and compose, with total = the full count; "
        "library.summarize memoized; a test shows 200 paths of 5 types make at most 5 lookups, compose at most CAP, and flash "
        "a total of 200.",
        "T4) The receipt gives each gate finding its disposition and leaves the live G2/G5/G6 re-runs UNKNOWN for the seat.",
    ],
    "touches": ["python/synapse/identify/apply.py", "python/synapse/identify/library.py",
                "python/synapse/panel/synapse_panel.py", "tests/test_identify_idfix.py", "tests/test_identify_apply.py",
                "tests/test_identify_library.py", "tests/panel/test_identify_button.py",
                "tests/fixtures/except_ratchet_baseline.json"],
    "acceptance": [
        {"predicate": "pytest passes on the leg tip for tests/test_identify_*.py, tests/panel/test_identify_button.py and "
                      "tests/test_except_ratchet.py with no collection error; the counts are in the receipt", "evidence": "test"},
        {"predicate": "a show() on the fake hou registers the save callback exactly once, and a hython save round trip with "
                      "bubbles shown and NO explicit install call leaves 0 sentinels on disk", "evidence": "test"},
        {"predicate": "a BOM-prefixed help text with '#key: value' header lines yields its first prose sentence",
         "evidence": "test"},
        {"predicate": "200 selected paths of 5 types make at most 5 library lookups, compose at most CAP, and flash a total "
                      "of 200", "evidence": "test"},
        {"predicate": "scripts/except_ratchet.py exits 0 on the leg tip and every identify file stays at 0 silent",
         "evidence": "check"},
        {"predicate": "live G2/G5/G6 re-run in Houdini 22.0.400 (the seat's, after the wave)", "evidence": "gui_probe",
         "gui_required": True},
    ],
    "crucible_criteria": CRUX_COMMON + [
        "the crucible removes the install call from show(), drops the BOM strip, and removes the cap and the memo, one at a "
        "time, and proves a test bites on each"],
    "source": {"doc": BLUEPRINT, "anchor": "sec. 7 G2/G5/G6; seat gate run 16:26-16:35 (.token-saver/bp11/seat_findings.md)"},
}

CRUX2 = dict(CRUX2)
CRUX2["deps"] = ["BP11-HARDFIX", "BP11-IDFIX"]
CRUX2["name"] = "CRUX2: adversarial re-verification of BP11-HARDFIX and BP11-IDFIX, and closure of every CRUX finding"
CRUX2["note"] = CRUX2["note"].replace(
    "Re-run every HARDFIX row in a fresh `git clone --shared` of bp11/hardfix, which carries the whole Identify chain plus "
    "HARDEN and the repair.",
    "Re-run every HARDFIX and IDFIX row in a fresh `git clone --shared` of bp11/idfix, which carries the whole Identify "
    "chain plus HARDEN, HARDFIX and IDFIX. For IDFIX, remove the install call from show(), drop the BOM strip, and remove "
    "the cap and the memo, one at a time, and show a test bites on each.")
CRUX2["note"] = CRUX2["note"].replace("Rate bp11/hardfix as the merge candidate", "Rate bp11/idfix as the merge candidate")
assert "bp11/idfix" in CRUX2["note"]
CRUX2["acceptance"] = [dict(a) for a in CRUX2["acceptance"]]
CRUX2["acceptance"][0]["predicate"] = "every HARDFIX and IDFIX acceptance row has a CRUX2 verdict with a crucible anchor"

if __name__ == "__main__":
    rows = []
    for m in (IDFIX, CRUX2):
        if not m["note"].startswith("START FROM YOUR CONTEXT PACKET"):
            m["note"] = packet_line(m["id"]) + m["note"] + OUTPUT_RULE
        errs = ms.validate_mission(m)
        if errs:
            raise SystemExit(f"{m['id']} failed validation: {errs}")
        (HERE / "missions" / f"{m['id']}.json").write_text(json.dumps(m, indent=2, ensure_ascii=True) + "\n",
                                                          encoding="utf-8")
        row = cw.leg_row(m)
        (HERE / "prompts" / f"{m['id']}.md").write_text(cw.fill_prompt(m, row), encoding="utf-8")
        rows.append(row)
        print(f"{m['id']}: tier={row.get('tier')} branch={row['branch']} deps={row['deps']}")
    (HERE / "waves" / "bp11.rows.idfix.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote waves/bp11.rows.idfix.json")