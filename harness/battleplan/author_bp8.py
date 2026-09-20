# author_bp8.py - CTO seat (Fable 5.1), 2026-09-20. Wave BP8 = act on the BP7 verdict (chat stalls after turn 1).
# First wave shaped by JEV-SHAPE (harness/jev/ledger/bp8.shape.jsonl: build-screen-crux @ 0.99, breadth 'Few').
# CTO calls: two builders now (WATCHDOG, TIMEOUTS); the memory-store leg is HELD until Joe's 2-minute GUI repro
# (BP7_VERDICT.md 'Reproduce in the GUI' step 5) says the Save-As path is part of the symptom. Builders are tier
# `reasoning` (Opus 4.8 in rails_exec.json) on Joe's word 2026-09-20; CRUX referee; TIDY mechanical.
# This script WRITES + VALIDATES missions only. It does not compile, make control files, or arm. ARM is Joe's word.
import json, sys
from pathlib import Path

AF = Path(__file__).resolve().parent
sys.path.insert(0, str(AF))
import mission_schema as ms  # noqa: E402

SRC = "harness/battleplan/notes/BP7_VERDICT.md"
FENCE = ("Permission fence: scoped `git add` + `git commit` only; push/merge/checkout/reset denied; use "
         "`cd <path> && git status --short`, never `git -C`. Commit code BEFORE the receipt; the receipt is your final write. "
         "Token-saver: Select-String / grep for symbols, read 40-line windows around the cited lines, never whole files. "
         "Line numbers below come from BP7_VERDICT.md at 29adc6e9 - confirm each with a grep before editing; if a line has "
         "moved, follow the symbol, not the number. Houdini GUI is NOT available to you: anything that needs a live panel "
         "is UNKNOWN, never a pass. Minimal diff: touch only the files in `touches`.")
STD_CRUX = [
    "the crucible trusts no builder's proved_it_bites - it authors its own mutations",
    "every verdict row carries the crucible's own anchor",
    "a leg with any UNKNOWN acceptance is at best SOUND-WITH-NITS, never SOUND",
    "the crucible flips no contract feature and edits no product file",
]

M = [
    {
        "id": "BP8-WATCHDOG", "band": "BUILD", "class": "build", "tier": "reasoning", "readonly": False, "deps": [],
        "name": "Panel response watchdog: a silent turn-2 hang becomes a visible, recoverable failure",
        "note": "Tier: reasoning. Self-cap: 20 turns (progress every 5). " + FENCE + " Verdict facts: the waiting state is armed at "
                "chat_panel.py:891-892 and cleared ONLY at :903-904 (send failed) and :914-915 (_on_response). "
                "_on_connection_error (:964) and _on_status_changed (:944) do not clear it, and the only QTimers (:234,:239) "
                "are the context and integrity timers. Panel styling rule: no hardcoded px or off-palette hex - use the existing "
                "system-line helper and tokens.",
        "targets": [
            "T1) python/synapse/panel/chat_panel.py: a single-shot QTimer armed in _send_message after the waiting state is set, "
            "stopped in _on_response and in the send-failure path. On fire: clear _waiting_for_response, hide the typing indicator, "
            "append ONE system line saying no response arrived and the artist can send again. Budget = the server slow-op budget "
            "(30 s) plus a small margin, as a named constant, not a literal at the call site.",
            "T2) Same file: _on_connection_error and _on_status_changed(False) clear the same waiting state through ONE shared "
            "helper (no third copy of the two clearing lines).",
            "T3) tests: a headless test (no Houdini, QTimer driven by the test or a fake clock) that sends, never responds, and "
            "asserts the state clears and exactly one system line appears; one test that a normal response stops the timer so "
            "no late line appears. Name the mutation that reddens each in the receipt (proved_it_bites).",
        ],
        "touches": ["python/synapse/panel/chat_panel.py", "tests/"],
        "acceptance": [
            {"predicate": "after a send with no reply, waiting state is False and the typing indicator is hidden once the watchdog fires", "evidence": "test"},
            {"predicate": "a delivered response stops the watchdog; no 'no response' line appears afterwards", "evidence": "test"},
            {"predicate": "connection error and status->disconnected both clear the waiting state via the shared helper", "evidence": "test"},
            {"predicate": "diff touches only chat_panel.py and tests; no hardcoded px or hex added", "evidence": "check"},
            {"predicate": "in a live H22 panel a hung turn 2 shows the system line and the input works again", "evidence": "gui_probe", "gui_required": True},
        ],
        "crucible_criteria": STD_CRUX + ["the crucible deletes the timer stop in _on_response and shows the second test reddens"],
        "spawn_classes": [], "source": {"doc": SRC, "anchor": "sec. 'Smallest fix' (panel watchdog); sec. H1 traced no-recovery path"},
    },
    {
        "id": "BP8-TIMEOUTS", "band": "BUILD", "class": "build", "tier": "reasoning", "readonly": False, "deps": [],
        "name": "Enforce the router tier timeouts that are defined but never applied, and bound route() in the handler",
        "note": "Tier: reasoning. Self-cap: 25 turns (progress every 5). " + FENCE + " Verdict facts: RoutingConfig defines "
                "tier2_timeout=5.0 / tier3_timeout=15.0 (router.py:124-125) but the guarded_create calls (router.py:685,:893) are "
                "made without them; only the Tier 0/1 futures pass timeout=2.0 (:334,:340). handlers.py:1787-1805 calls route() "
                "with no try/except and no timeout, so a hung LLM call blocks until the 30 s slow-op kill and emits nothing. "
                "First find out how guarded_create / the client accepts a timeout (python/synapse/model_access.py) - do not guess "
                "a kwarg. A timed-out tier must fall through the cascade or return a well-formed failure carrying `response` and "
                "`tier` keys, because ws_bridge.py:339-344 silently drops any dict without them.",
        "targets": [
            "T1) python/synapse/routing/router.py: _try_tier2 and _tier3_sync/_tier3_worker apply self._config.tier2_timeout / "
            "tier3_timeout to the LLM call by the mechanism model_access actually supports. On timeout: record the metric as a "
            "failure for that tier and return a RoutingResult the cascade can act on. No new config fields.",
            "T2) python/synapse/server/handlers.py (~:1787): route() is wrapped so ANY exception or overall timeout yields a "
            "well-formed chat reply (`response` + `tier`) that says the request timed out - never silence.",
            "T3) tests: a fake LLM client that sleeps past the tier timeout -> the tier returns within timeout + margin and the "
            "handler's reply carries `response` and `tier`; a raising router -> same shape. Name the mutation that reddens each.",
        ],
        "touches": ["python/synapse/routing/router.py", "python/synapse/server/handlers.py", "tests/"],
        "acceptance": [
            {"predicate": "with a fake client sleeping 3x tier2_timeout, _try_tier2 returns in under tier2_timeout + 1 s", "evidence": "test"},
            {"predicate": "same for the deep tier against tier3_timeout", "evidence": "test"},
            {"predicate": "a raising or timed-out route() produces a handler reply containing both `response` and `tier`", "evidence": "test"},
            {"predicate": "the existing routing test suite is green; count before and after stated in the receipt", "evidence": "test"},
            {"predicate": "the mechanism used to pass the timeout is quoted from model_access.py with file:line", "evidence": "check"},
        ],
        "crucible_criteria": STD_CRUX + ["the crucible removes the timeout argument and shows the sleep test reddens",
                                         "the crucible greps that no LLM call site in router.py is left without a timeout"],
        "spawn_classes": [], "source": {"doc": SRC, "anchor": "sec. H4 router (traced defects); sec. 'Smallest fix' upstream root fix"},
    },
    {
        "id": "BP8-CRUX", "band": "TRUST", "class": "crucible", "tier": "referee", "readonly": True,
        "deps": ["BP8-WATCHDOG", "BP8-TIMEOUTS"],
        "name": "CRUX: adversarial re-verification of BP8-WATCHDOG and BP8-TIMEOUTS",
        "note": "Tier: referee. Start from the JEV-SCREEN line for each leg (run `python harness/jev/jev_screen.py --wave bp8`): "
                "CLEAR = spot-check two rows, REFEREE = full read, FLAG = begin at the flagged row. The screen sets depth only; "
                "it never replaces your own mutations. gui_required predicates are UNKNOWN to you - say so.",
        "targets": [
            "T1) Per builder receipt: re-run every non-GUI acceptance predicate in a fresh checkout of the leg branch; verdict "
            "rows pass|fail|UNKNOWN with your own anchors.",
            "T2) >= 2 self-authored mutations per leg, each named with the test it reddens -> harness/battleplan/notes/BP8-CRUX_mutations.json",
            "T3) harness/battleplan/notes/BP8-CRUX_verdicts.md: one verdict per leg (SOUND | SOUND-WITH-NITS | BROKEN), plus one "
            "line comparing your verdict with the JEV-SCREEN line for that leg.",
        ],
        "touches": [],
        "acceptance": [
            {"predicate": "one verdict per builder leg (two) with independently re-run rows and the crucible's own anchors", "evidence": "receipt"},
            {"predicate": ">= 2 self-authored mutations per builder leg, each named with the check it reddens", "evidence": "test"},
            {"predicate": "screen-vs-CRUX agreement line present for both legs", "evidence": "receipt"},
        ],
        "crucible_criteria": STD_CRUX, "spawn_classes": [],
        "source": {"doc": SRC, "anchor": "whole verdict; harness/battleplan/notes/JEV_BLUEPRINT.md sec.3.2 (screen line in the CRUX brief)"},
    },
    {
        "id": "BP8-TIDY", "band": "TRUST", "class": "tidy", "tier": "mechanical", "readonly": True, "deps": ["BP8-CRUX"],
        "name": "TIDY: census of BP8 worktrees, receipts and ledgers; one table with a count line",
        "note": "Tier: mechanical. Self-cap: 8 turns. Read-only: list, count, report. Fix nothing, delete nothing.",
        "targets": ["T1) harness/battleplan/notes/BP8_TIDY.md: a table of BP8 worktrees (branch, HEAD, clean?), receipts "
                    "(leg, status) and harness/jev/ledger/bp8.*.jsonl row counts, ending in a count line per table."],
        "touches": [],
        "acceptance": [{"predicate": "every table ends with a count line that equals its row count", "evidence": "check"}],
        "crucible_criteria": STD_CRUX, "spawn_classes": [],
        "source": {"doc": SRC, "anchor": "wave hygiene; same shape as BP4-TIDY"},
    },
]

if __name__ == "__main__":
    errs = [e for m in M for e in ms.validate_mission(m)]
    if errs:
        print("\n".join(errs)); sys.exit(1)
    for m in M:
        (AF / "missions" / f"{m['id']}.json").write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote", m["id"], "|", m["tier"], "| deps", m["deps"])
    print(f"-- {len(M)} missions valid. NOT compiled, NOT armed. HELD: memory-store leg, pending Joe's GUI repro (BP7_VERDICT.md).")
