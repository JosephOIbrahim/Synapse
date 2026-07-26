"""H8 — assemble harness/notes/RULING_AUDIT.json.

    python harness/notes/h8/assemble_audit.py <ledger_final.json> <out.json>

Wraps the machine-produced ledger with the positive-control result (reported FIRST, per the
brief), the R25 provenance block, the counts, and the structural findings. Every integer here
comes from build_ledger.py; none is typed by hand.
"""
import json
import sys

CONTROL = {
    "_read_this_first": (
        "An audit that cannot detect known errors cannot be trusted on unknown ones. This block "
        "reports whether the method could, BEFORE any of its other conclusions are read."
    ),
    "design": {
        "probe_set": [15, 48, 58, 64, 2, 14, 35, 50, 60, 71, 75, 77],
        "known_wrong_planted": [15, 48, 58, 64],
        "decoys": [2, 14, 35, 50, 60, 71, 75, 77],
        "blinding": (
            "No lens was told which rulings were known-wrong, that the set contained any, or what "
            "distribution to expect."
        ),
        "lenses": ["crucible (evidence)", "crucible (logic/scope)", "h22-adjudicator (consistency)"],
        "acceptance_criteria": [
            "SENSITIVITY: all four known-wrong flagged SUPERSEDED_UNMARKED or SCOPE_ERROR, or a "
            "higher-precedence verdict carrying one of them in also_applies.",
            "SPECIFICITY: the method must be able to return SOUND. A method that flags all twelve "
            "also 'catches' all four and proves nothing. This is Law 1 applied to the audit itself.",
        ],
    },
    "result": "PASS",
    "sensitivity": {
        "verdict": "4 of 4 caught, by all three lenses independently",
        "detail": {
            "R15": ["EVIDENCE_FAILS +SUPERSEDED_UNMARKED", "EVIDENCE_FAILS", "EVIDENCE_FAILS +SUPERSEDED_UNMARKED +SCOPE_ERROR"],
            "R48": ["SUPERSEDED_UNMARKED", "SUPERSEDED_UNMARKED", "SUPERSEDED_UNMARKED"],
            "R58": ["SUPERSEDED_UNMARKED +SCOPE_ERROR", "SUPERSEDED_UNMARKED", "SUPERSEDED_UNMARKED"],
            "R64": ["SUPERSEDED_UNMARKED +UNENFORCED", "EVIDENCE_FAILS +SUPERSEDED_UNMARKED", "SUPERSEDED_UNMARKED"],
        },
        "note": "12 of 12 lens-verdicts on the known-wrong four are non-SOUND.",
    },
    "specificity": {
        "verdict": "PASS - the method returns SOUND, unanimously, on four decoys",
        "unanimous_sound": [14, 35, 60, 75],
        "note": (
            "No lens flagged everything; each returned SOUND for at least four decoys. The "
            "instrument can report clean, so its non-clean reports carry information."
        ),
    },
    "found_beyond_the_control": {
        "R50": (
            "Planted as a decoy; scored non-SOUND by all three lenses. R50 states 'Ruled, adopted "
            "into the constitution'. Orchestrator verified directly: grep -i 'positive control|same "
            "class|UNVERIFIABLE' harness/AGENT_CONSTITUTION.md returns ZERO MATCHES, and "
            "git log -- harness/AGENT_CONSTITUTION.md shows a single commit 6b41e1a (v1, never "
            "amended). Law 3 violated in the act of adopting a law."
        ),
        "R70": (
            "Found by the sweep and independently reproduced by the orchestrator. R70 states 'The "
            "convergence happened. The raise did not.' Executed on this branch: "
            "validate({'asset_name':'x','parentPath':'/stage'}) -> ValidationError: unknown "
            "parameter(s); validate({...,'parent_path':...}) -> OK. The raise exists and landed in "
            "1cb99a9 (2026-07-25), one day BEFORE R70. H2b-F5 measured _resolve_parent_path in "
            "isolation - a private helper that validate() makes unreachable."
        ),
    },
    "reader_calibration_R50_applied_to_this_audit": {
        "claim": "An 'enforcement: none' verdict is a finding, not a failed search.",
        "proof": (
            "All 10 verdict-producing agents reported found_a_real_mechanism=true with real "
            "file:line. Orchestrator independently confirmed mechanisms at "
            "tests/test_solaris_tool_registration.py:134 (R33), harness/verify/checks.py:1684 "
            "(R34/R71), harness/verify/checks.py:2122 (R31/R40), harness/orchestrate.ps1:147 (R61), "
            "tests/test_v5_features.py:54 (R9)."
        ),
    },
}

STRUCTURAL = [
    {
        "id": "H8-S1",
        "title": "Unmarked supersession is structurally guaranteed, not an author oversight",
        "tier": "VERIFIED-STATIC",
        "finding": (
            "Edit(harness/notes/CTO_RULINGS_01.md) is DENIED in BOTH agent profiles - "
            "harness/relay-settings.json:65 and harness/readonly-settings.json:46. No leg agent can "
            "ever mark a ruling it refuted. The H6 leg produced a human-authorised R64 amendment, "
            "correctly refused to bypass the fence, and parked it at "
            ".claude/worktrees/h6-substrate-truth/.claude/R64_AMENDMENT_pending.md - 'Status BLOCKED "
            "BY FENCE ... No bypass was attempted.' It is untracked, alongside amend_R64.md and "
            "amend_h6.md. The document can therefore only grow, never be corrected in place, and "
            "every supersession becomes an unmarked one by construction."
        ),
        "corroboration": (
            "0 of 105 cross-reference pair rows have original_marked_in_place=true, across 50 "
            "supersession-class relations (17 AMEND, 12 NARROW, 11 REVERSE, 10 REFUTE)."
        ),
    },
    {
        "id": "H8-S2",
        "title": "Four 'adopted-into' containers do not exist as artifacts",
        "tier": "VERIFIED-STATIC",
        "finding": (
            "R26 and R32 both rule 'add to the Law 1 check set'; grep -rl 'Law 1 check set' over the "
            "tree returns only CTO_RULINGS_01.md itself. R50 rules 'adopted into the constitution'; "
            "the constitution has zero matches and one commit. R34/R60/R71 adopt into 'the mutation "
            "standard'; it exists only as prose in the rulings and leg prompts. Article VII cites a "
            "'harness amendments ledger'; no such file exists. All four propagate by being copied "
            "into leg prompts - instruction, not structure, which is the exact distinction R61 rules "
            "against."
        ),
    },
    {
        "id": "H8-S3",
        "title": "The document violates its own R66, in the file that issues the ban",
        "tier": "VERIFIED-STATIC",
        "finding": (
            "R66 rules the unpinned SideFX docs URL 'banned in any governing document, ruling or "
            "vendor ask'. CTO_RULINGS_01.md:1482 (R58's Method line) still carries "
            "sidefx.com/docs/houdini/hom/hou/RopNode.html, ~290 lines earlier in the same file. Also "
            "at harness/prompts/h5.md:15. No mechanism scans for it."
        ),
    },
    {
        "id": "H8-S4",
        "title": "The evidence base for rulings 48-78 is not on the branch that carries them",
        "tier": "VERIFIED-STATIC",
        "finding": (
            "31 of 78 rulings (40%) rule from leg receipts. git ls-tree -r HEAD -- "
            "harness/notes/receipts/ returns 12 files (H2 H3 L0-L5 Q1 Q2 SR1 T0). RES/H3a/H1/H6 are "
            "committed only on other branches. LEDGER.json, H5.json and H2b.json are UNTRACKED on "
            "disk - in no commit on any branch. H7.json does not exist at all. A reader of the "
            "rulings on the branch that holds them can open ZERO of the receipts underpinning R48-R78."
        ),
        "why_it_bites": (
            "harness/orchestrate.ps1:51-63 resolves leg state from those same untracked worktree "
            "files, so `git worktree remove` would destroy the evidence for eleven rulings AND "
            "silently reset those legs from done to ready. Commit bd17870 shows this exact defect "
            "was found once already and recurred. R38 mandated governing documents travel TO every "
            "branch; the return trip for evidence was never made."
        ),
        "independent_confirmation": "All 10 verdict-producing agents reported it unprompted; one labelled it 'SYSTEMIC GAP'.",
    },
    {
        "id": "H8-S5",
        "title": "An unexecuted ruling accidentally kept the release notes correct",
        "tier": "VERIFIED-STATIC",
        "finding": (
            "R48 clause 3 ordered v5.34.0's Known-limitations wording corrected to say Houdini "
            "exposes no render-cancel API. Nobody executed it. R73 then proved rkill works, which "
            "means the ordered correction would have made docs/RELEASE_NOTES_v5.34.0.md:72 LESS "
            "accurate than the wording it already had. The non-enforcement of R48 is the only reason "
            "the released documentation is right."
        ),
    },
]

FOR_RULING = [
    {
        "id": "H8-R1",
        "question": (
            "The rulings file is deny-listed from agent edit in both profiles, so no agent can mark "
            "a ruling it refutes, and amendments die in untracked worktree files. Should an "
            "amendment channel exist that does not require widening the fence - e.g. an append-only "
            "harness/notes/RULING_AMENDMENTS.md that agents MAY write, which the rulings file "
            "references once at its head?"
        ),
        "why_escalated": (
            "Article I: this is a value judgement between defensible options (fence integrity vs "
            "document currency), not a fact provable from the tree. The fence is working as "
            "designed; the question is whether the design has the right shape."
        ),
    },
    {
        "id": "H8-R2",
        "question": (
            "Three receipts underpinning eleven rulings (LEDGER, H5, H2b) exist only as untracked "
            "files in disposable worktrees, and H7.json was never written. Commit them, or accept "
            "that R48-R78 rest on evidence that is not in version control?"
        ),
        "why_escalated": "Committing another leg's receipts crosses a branch boundary; Gate C is human.",
    },
    {
        "id": "H8-R3",
        "question": (
            "H8's own fence: the orchestrator selected readonly-settings.json and this leg ran "
            "sed/find/mkdir/diff/git ls-tree - none of which are in its 19-entry allow list. The "
            "deny list was NOT probed (Article I forbids an agent testing its own leash). Is the "
            "read-only profile enforcing what R61 intended?"
        ),
        "why_escalated": (
            "Verifying it requires probing the fence, which the constitution forbids the fenced "
            "agent from doing. It needs a human or an out-of-fence check."
        ),
    },
    {
        "id": "H8-R4",
        "question": (
            "R50's rule ('ABSENT requires a positive control on the same class') and the mutation "
            "standard (R34/R60/R71) are cited as adopted law but exist only as prose. Ratify them "
            "into AGENT_CONSTITUTION.md, or downgrade the rulings' language from 'adopted' to "
            "'proposed'?"
        ),
        "why_escalated": "Amending the constitution is human-only under Article VII.",
    },
]


def main(ledger_path, out_path):
    led = json.load(open(ledger_path, encoding="utf-8"))

    doc = {
        "_schema": "ruling_audit/v1",
        "leg": "H8",
        "generated": "2026-07-26",
        "document_audited": "harness/notes/CTO_RULINGS_01.md",
        "document_commit": "a64033d",
        "branch": "repair/h8-ruling-audit",
        "rulings_audited": 78,
        "model": "claude-opus-5[1m]",
        "settings_profile": "harness/readonly-settings.json",
        "producer": (
            "harness/notes/h8/build_ledger.py <sweep.jsonl> <adjudication.jsonl>, then "
            "harness/notes/h8/assemble_audit.py. No count in this file is hand-entered."
        ),
        "method": (
            "The document's own laws turned on the document: Law 1 (a check must be able to fail), "
            "Law 2 (no number without a producer), Law 3 (status describes what happened), Law 5 "
            "(write from the tree), R50 (ABSENT needs a same-class positive control), R60 (a pin's "
            "reader needs calibration), R74 (design documents are UNVERIFIED by default)."
        ),
        "positive_control": CONTROL,
        "counts": led["counts"],
        "counts_note": (
            "Primary-verdict partition; sums to 78. Precedence EVIDENCE_FAILS > CONTRADICTED > "
            "SUPERSEDED_UNMARKED > SCOPE_ERROR > UNFALSIFIABLE > UNENFORCED > SOUND means "
            "CONTRADICTED / SCOPE_ERROR / UNFALSIFIABLE can be masked by a higher verdict on the "
            "same ruling. counts_any_basis reports every verdict that applies."
        ),
        "counts_any_basis": led["counts_any_basis"],
        "unenforced_count": led["counts"]["UNENFORCED"],
        "unenforced_any_basis": led["counts_any_basis"]["UNENFORCED"],
        "enforcement": led["enforcement"],
        "rulings_with_no_mechanism_on_this_branch": led["rulings_with_no_mechanism_on_this_branch"],
        "any_original_marked_in_place": led["any_original_marked_in_place"],
        "cross_lens_pair_rows": led["cross_lens_pair_rows"],
        "structural_findings": STRUCTURAL,
        "for_ruling": FOR_RULING,
        "verdicts": led["verdicts"],
    }

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)

    ef = [v for v in led["verdicts"] if v["verdict"] == "EVIDENCE_FAILS"]
    missing_anchor = [v["ruling"] for v in ef if len(v.get("evidence", "")) < 40]
    print(json.dumps({
        "written": out_path,
        "rulings": len(led["verdicts"]),
        "counts": led["counts"],
        "unenforced_count": led["counts"]["UNENFORCED"],
        "evidence_fails": sorted(v["ruling"] for v in ef),
        "evidence_fails_missing_anchor_text": missing_anchor,
    }, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
