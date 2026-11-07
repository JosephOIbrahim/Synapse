# author_bp11.py - author wave BP11 (Identify + production hardening) as mission JSONs.
# Shape: JEV-SHAPE chose build-screen-crux @ 1.00 (harness/jev/ledger/bp11.shape.jsonl, 2026-09-28T10:37:45).
# Edges and chained bases were added by the CTO seat (notes/BP11_CTO_PLAN.md sec. 4). Writes
# missions/BP11-*.json as UTF-8 through json.dumps (ASCII-escaped), so no encoding round trip can corrupt
# them. Authoring only: nothing is compiled or armed by this script.
import json
from pathlib import Path

AF = Path(r"C:\Users\User\SYNAPSE\harness\battleplan")
NOTES = r"C:\Users\User\SYNAPSE\harness\battleplan\notes"
HYTHON = r"C:\Program Files\Side Effects Software\Houdini 22.0.400\bin\hython.exe"
BLUEPRINT = "harness/battleplan/notes/IDENTIFY_BLUEPRINT.md"
PLAN = "harness/battleplan/notes/BP11_CTO_PLAN.md"
# Token-saver (2026-09-28): every leg starts from a packet of exact code windows (build_packets_bp11.py),
# screened per target by JEV-PACKET (harness/jev/jev_packet.py). BP10's Opus legs spent 42-57% of their
# cost-weighted tokens on cache reads of 330-397k contexts (runs/2026-09-21/ledger_orch_20260921-121433.json).
PACKETS = r"C:\Users\User\SYNAPSE\.token-saver\bp11"
OUTPUT_RULE = (" Tool-output discipline (token-saver): run pytest -q --tb=line -p no:cacheprovider on the files you "
               "touch plus the named pins, never the whole suite unless a row demands it; pipe long output through "
               "Select-Object -Last 40 or Select-String; never print a whole log, diff or JSON you can grep. Receipt "
               "evidence cells stay one or two lines each.")


def packet_line(leg):
    return (f"START FROM YOUR CONTEXT PACKET {PACKETS}\\{leg}.packet.md - the exact code windows the seat already "
            "located for your targets (token-saver). Search beyond it only for what it lacks, and list what it "
            "lacked in the receipt under packet_gaps; that feedback tunes the next wave's packets. ")


def fence(turns, extra=""):
    return (
        f"Self-cap: {turns} turns (progress every 5). Permission fence: scoped `git add` + `git commit` only; "
        "push/merge/checkout/reset denied; use `cd <path> && git status --short`, never `git -C`. Commit code BEFORE "
        "the receipt; the receipt is your final write. Budget discipline: run /token-saver first and keep to it - "
        "Select-String / grep for symbols, read 40-line windows around cited lines, never whole files. The source "
        f"docs are untracked on master, so read them by absolute path under {NOTES} (IDENTIFY_BLUEPRINT.md, "
        "BP11_CTO_PLAN.md): ONCE in full at the start, then only grep them. Houdini GUI is NOT available to you: "
        "anything that needs a live panel is UNKNOWN, never a pass. hython IS available at "
        f"`{HYTHON}` (22.0.400) for headless gates. Minimal diff: touch only the files in `touches`. House rule: "
        "no number enters a document without a producer path beside it. Every UNKNOWN stays UNKNOWN - never a "
        "pass, never a 0. Write text files as UTF-8 through Python (pathlib.write_text(..., encoding='utf-8')), "
        "never through PowerShell default encodings (the BP10 SCAFFOLD mojibake came from a cp1252 round trip). "
        + extra
    )


CRUX_COMMON = [
    "the crucible trusts no builder's proved_it_bites - it authors its own mutations",
    "every verdict row carries the crucible's own anchor",
    "a leg with any UNKNOWN acceptance is at best SOUND-WITH-NITS, never SOUND",
    "the crucible flips no contract feature and edits no product file",
]


def gui(pred):
    return {"predicate": pred, "evidence": "gui_probe", "gui_required": True}


MISSIONS = [
    {
        "id": "BP11-FIXFWD", "band": "BUILD", "class": "build", "tier": "mechanical", "readonly": False, "deps": [],
        "name": "BP10 fix-forward: ADR-0001 refusals 4 -> 8, NOTICE.md hashes from git blobs (LF), plus a verifier",
        "note": fence(15, "Tier: mechanical (Haiku 4.5) - this leg edits to a written fix list; it designs nothing. "
                      "The fix list is in the unmerged branch: read it with `git show bp10/crux:harness/battleplan/notes/"
                      "BP10-CRUX_verdicts.md` (section 'BP10-SCAFFOLD', 'Fix list'). Already closed on master, do NOT "
                      "touch: the questions.json mojibake (0 occurrences on 2026-09-28) and the README overclaim (gone "
                      "after 312ed2cf). Upstream pin: https://github.com/healkeiser/fxhoudinimcp @ "
                      "29b6695b6726b90537eab3f02411e05d7c6760a5; shallow-clone it to a temp dir outside the repo."),
        "targets": [
            "T1) docs/decisions/ADR-0001*.md: the Refused Sites section lists all eight refusals from "
            "harness/battleplan/notes/JEV_HARVEST_BLUEPRINT.md 'Risks and refusals' (the four present plus: probe "
            "passed, which model runs anything, instant tier, run_on_main closure), wording copied from the blueprint.",
            "T2) python/synapse/_vendor/fxhoudinimcp/NOTICE.md: the 31 guide hashes and the LICENSE hash regenerated "
            "as sha256 of the committed git blobs (LF bytes), with one sentence saying so; LICENSE size corrected to "
            "the blob size.",
            "T3) scripts/verify_vendor_notice.py recomputes every blob hash and compares it with NOTICE.md, exit 1 on "
            "any mismatch; tests/test_vendor_notice.py runs it.",
        ],
        "touches": ["docs/decisions/", "python/synapse/_vendor/fxhoudinimcp/NOTICE.md",
                    "scripts/verify_vendor_notice.py", "tests/test_vendor_notice.py"],
        "acceptance": [
            {"predicate": "ADR-0001 Refused Sites lists 8 refusals and names each of the blueprint's 8 refusal subjects",
             "evidence": "check"},
            {"predicate": "scripts/verify_vendor_notice.py exits 0 on the leg tip and exits 1 after one hex digit of "
                          "one NOTICE.md hash is flipped (mutation shown in the receipt)", "evidence": "test"},
            {"predicate": "NOTICE.md's anim.md hash equals sha256 of anim.md at upstream 29b6695b from a fresh clone",
             "evidence": "check"},
            {"predicate": "harness/jev/questions.json is byte-identical to master on the leg tip", "evidence": "check"},
        ],
        "crucible_criteria": CRUX_COMMON + [
            "the crucible hashes git BLOBS, never a checkout: raw bytes of `git cat-file blob <rev>:<path>` for three random "
            "guides and LICENSE, on bp11/fixfwd and on upstream 29b6695b, compared with NOTICE.md (Windows core.autocrlf=true "
            "turns every checkout into CRLF; the seat's check .token-saver/bp11/check_notice_hashes.py found 0/31 blob "
            "matches on bp11/fixfwd at 11:20)"],
        "source": {"doc": "harness/battleplan/notes/JEV_HARVEST_BLUEPRINT.md",
                   "anchor": "sec. 'Risks and refusals'; bp10/crux BP10-CRUX_verdicts.md 'Fix list'"},
    },
    {
        "id": "BP11-FIXFWD2", "band": "BUILD", "class": "build", "tier": "auto", "readonly": False,
        "deps": ["BP11-FIXFWD"],
        "name": "FIXFWD repair: NOTICE.md hashes from git blob bytes (LF), and a verifier that hashes blobs, never a "
                "Windows checkout",
        "note": fence(12, "Added mid-wave by the seat on Joe's standing pre-approval (2026-09-28 11:22). Your worktree "
                      "is cut from bp11/fixfwd. The seat's check C:\\Users\\User\\SYNAPSE\\.token-saver\\bp11\\"
                      "check_notice_hashes.py (run 11:20) found 0 of 31 guide hashes, and the LICENSE hash, in NOTICE.md "
                      "equal to their committed blobs: every value is a CRLF checkout hash, because core.autocrlf=true "
                      "converts LF to CRLF on every Windows checkout, a fresh clone included. Hash raw blob bytes only: "
                      "`git cat-file blob HEAD:<path>` read through Python hashlib over sys.stdin.buffer (or "
                      "subprocess stdout bytes). For upstream, hash `git cat-file blob 29b6695b:<path>` inside the "
                      "clone. Never hash a file read from the working tree."),
        "targets": [
            "T1) python/synapse/_vendor/fxhoudinimcp/NOTICE.md: all 31 guide hashes and the LICENSE hash replaced by "
            "sha256 of the committed git blobs (LF bytes); the provenance sentence says so; the LICENSE size is the "
            "blob size.",
            "T2) scripts/verify_vendor_notice.py hashes `git cat-file blob HEAD:<path>` bytes, never working-tree "
            "files; tests/test_vendor_notice.py gains a test in which a table of CRLF hashes FAILS the verifier.",
            "T3) The receipt corrects BP11-FIXFWD's rows 2 and 3, whose evidence hashed CRLF checkout bytes.",
        ],
        "touches": ["python/synapse/_vendor/fxhoudinimcp/NOTICE.md", "scripts/verify_vendor_notice.py",
                    "tests/test_vendor_notice.py"],
        "acceptance": [
            {"predicate": "for all 31 guides and LICENSE, the NOTICE.md value equals sha256 of `git cat-file blob "
                          "HEAD:<path>` (count line 32/32 in the receipt)", "evidence": "check"},
            {"predicate": "NOTICE.md gives anim.md as 57fae325b428776d32fd368d4bb7d514e1a21ddf1798d275c7faad0ae0f2ba93 "
                          "and LICENSE as 79a2891ba34d73cb07da165714464f3bb6a6c6a254ea7ad1bac2cf3f7aae5918 (blob "
                          "values from the seat's check)", "evidence": "check"},
            {"predicate": "tests/test_vendor_notice.py passes, including the new test in which a CRLF-hashed table "
                          "fails the verifier", "evidence": "test"},
            {"predicate": "the verifier hashes through git cat-file only; grep shows no read_bytes or open() on a "
                          "guide path in scripts/verify_vendor_notice.py", "evidence": "check"},
        ],
        "crucible_criteria": CRUX_COMMON + [
            "the crucible hashes git blobs itself for five random guides and LICENSE, and flips one NOTICE value to "
            "a CRLF hash to prove the new verifier test bites"],
        "source": {"doc": PLAN, "anchor": "sec. 1 BP10 fix-forward; seat check .token-saver/bp11/check_notice_hashes.py"},
    },
    {
        "id": "BP11-IDCORE", "band": "BUILD", "class": "build", "tier": "auto", "team": "auto", "readonly": False,
        "deps": [],
        "name": "Identify core: python/synapse/identify (facts, library, compose, apply) - zero-token bubbles from "
                "exact sources, one undo group, artist text never lost, never on disk",
        "note": fence(30, "IDENTIFY_BLUEPRINT.md sections 1-4 are the contract; section 3's nine rules are what CRUX "
                      "re-verifies. M0 probe scripts (read-only reference, port what you need into "
                      "scripts/probe_identify.py): C:\\Users\\User\\Downloads\\synapse_identify_probe.py, _probe2.py, "
                      "_probe3.py, _probe4.py. Reuse, don't fork: selection facts come from "
                      "synapse.server.introspection.inspect_selection with the call pattern in "
                      "panel/selection_inspection.py:68-80 (run_on_main, timeout=3.0, record_stall=False, "
                      "record_wait=False, a label). The library reader is python/synapse/cognitive/tools/"
                      "sidefx_library.py: query-only, never build or download. If it lacks an exact help-path lookup, "
                      "add ONE read-only function there and test it; a query_library search result is never a node's "
                      "summary. The Selection Inspector stays read-only: add nothing to it in this leg."),
        "targets": [
            "T1) python/synapse/identify/compose.py: a pure function (no hou, no Qt) from facts to bubble lines per "
            "blueprint sec. 2 - What / Here / State, at most 3 lines, a width constant, the parm filter (folders, "
            "folder sets, separators, labels, hidden parms, ramp\\d+(pos|value|interp) internals), labels not names, "
            "3 significant digits, the (expr) marker, '...' truncation, and '- not in library' for unknown types.",
            "T2) python/synapse/identify/library.py: exact lookup from node type to summary by the help path derived "
            "from defaultHelpUrl() including versioned types (operator:Sop/polybevel?version=3.0); HDA embedded help "
            "first sentence; returns (text, source) or (None, 'unknown'); never searches.",
            "T3) python/synapse/identify/facts.py: per-node facts from inspect_selection(include_parameters=True, "
            "node_paths=...) plus the extras it lacks, read in one short main-thread read: help url, parm labels, "
            "default and expression flags, errors, warnings, bypass, and LOP last-modified prims if the 22.0.400 API "
            "has them (probe it; UNKNOWN otherwise).",
            "T4) python/synapse/identify/apply.py: the only writer - ASCII sentinel block '~ identify ~' appended "
            "below any artist comment and stripped from the sentinel down; a per-session registry of the prior "
            "DisplayComment flag keyed by node sessionId; one hou.undos.group('SYNAPSE Identify') per show and per "
            "clear; BeforeSave strip and AfterSave re-apply with undo disabled; a 60-bubble cap with the flash line "
            "'Identify: N of M nodes'; idempotent toggle; orphan blocks (no registry entry) removed on clear.",
            "T5) tests/test_identify_compose.py, tests/test_identify_library.py, tests/test_identify_apply.py (fake "
            "hou objects), and scripts/probe_identify.py (hython: build the M0 seven-node chain in a temp .hip, show, "
            "save, reopen, assert zero sentinels, print hou.applicationVersionString()).",
        ],
        "touches": ["python/synapse/identify/", "python/synapse/cognitive/tools/sidefx_library.py",
                    "tests/test_identify_compose.py", "tests/test_identify_library.py",
                    "tests/test_identify_apply.py", "scripts/probe_identify.py"],
        "acceptance": [
            {"predicate": "pytest tests/test_identify_compose.py tests/test_identify_library.py "
                          "tests/test_identify_apply.py passes on system Python without hou", "evidence": "test"},
            {"predicate": "compose() on the M0 PolyBevel facts (offset 0.07 plus five changed ramp internals) yields "
                          "exactly one Here entry, shown by its label, and no ramp internal", "evidence": "test"},
            {"predicate": "an artist comment is byte-identical after show then clear, after show + BeforeSave strip + "
                          "AfterSave re-apply + clear, and when the artist comment quotes the sentinel inside prose",
             "evidence": "test"},
            {"predicate": "library returns 'unknown' for a type with no exact help-path row, and swapping the exact "
                          "lookup for query_library search makes a test fail (mutation shown in the receipt)",
             "evidence": "test"},
            {"predicate": "hython scripts/probe_identify.py on 22.0.400 prints the version, shows 7 bubbles on the M0 "
                          "chain, and the saved .hip reopened has zero sentinel lines and one undo group per show",
             "evidence": "check"},
            {"predicate": "the main-thread apply for 60 nodes is timed in hython and the ms figure is in the receipt "
                          "against the 100 ms starting target (a miss is a finding, never hidden)", "evidence": "check"},
            {"predicate": "nothing under python/synapse/identify imports harness/ or opens a network connection, and "
                          "only apply.py calls setComment, setGenericFlag or hou.undos (grep count lines in the "
                          "receipt)", "evidence": "check"},
        ],
        "crucible_criteria": CRUX_COMMON + [
            "the crucible writes its own artist comment that quotes the sentinel in prose and proves show + clear "
            "leaves it byte-identical",
            "the crucible disables the BeforeSave strip and proves the save row bites",
            "the crucible re-runs scripts/probe_identify.py in hython itself"],
        "source": {"doc": BLUEPRINT, "anchor": "sec. 2 The bubble; sec. 3 Rules; sec. 4 Where it lives"},
    },
    {
        "id": "BP11-IDSURF", "band": "BUILD", "class": "build", "tier": "auto", "team": "auto", "readonly": False,
        "deps": ["BP11-IDCORE"],
        "name": "Identify surface: panel button + /identify (panel-answered) + read-only Inspector column, tokens only",
        "note": fence(25, "Your worktree is cut from the IDCORE leg's branch, so python/synapse/identify/ is already "
                      "present; do not re-open its design. Registry rule: '/identify' goes into "
                      "PANEL_ANSWERED_COMMANDS in panel/command_palette.py (the panel answers it, the model never sees "
                      "it) and is surfaced through tool_palette._load_entries (panel/tool_palette.py:141), the single "
                      "row source. Widgets come from panel/designsystem/components with tokens; a new token goes only "
                      "into designsystem/tokens.py. Threading: facts and compose run on a daemon (the "
                      "selection_inspection._launch pattern), apply runs through run_on_main in one short hold. The "
                      "Selection Inspector's docstring contract (read-only, owns no Houdini objects) must stay true. "
                      "Existing tests that pin the exact PANEL_ANSWERED_COMMANDS set may be updated, nothing else."),
        "targets": [
            "T1) An Identify button in the synapse_panel.py action row that toggles show / clear for the current "
            "selection, disabled with a reason when nothing is selected.",
            "T2) '/identify' and '/identify off' registered once and answered by the panel.",
            "T3) A read-only Identify column in the Selection Inspector showing compose() text for inspected rows.",
            "T4) tests/panel/test_identify_button.py driving the real handler against fake Qt leaves (the "
            "test_rope_switcher_wires_profile.py pattern), plus the registry and thread-identity tests.",
        ],
        "touches": ["python/synapse/panel/synapse_panel.py", "python/synapse/panel/tool_palette.py",
                    "python/synapse/panel/command_palette.py", "python/synapse/panel/selection_inspector.py",
                    "python/synapse/panel/designsystem/", "tests/panel/test_identify_button.py",
                    "tests/test_panel_finesse.py", "tests/test_first_session_panel.py"],
        "acceptance": [
            {"predicate": "tests/panel/test_identify_button.py, tests/panel/test_token_authority.py and every "
                          "existing PANEL_ANSWERED_COMMANDS pin pass", "evidence": "test"},
            {"predicate": "'/identify' is in PANEL_ANSWERED_COMMANDS, appears exactly once in "
                          "tool_palette._load_entries(), and sending it never reaches the model send path (spy count 0)",
             "evidence": "test"},
            {"predicate": "compose and library run off the Qt main thread and apply runs on it, asserted with thread "
                          "identities in a test that drives the real handler", "evidence": "test"},
            {"predicate": "selection_inspector.py contains no setComment, setGenericFlag or undos call (count line 0 "
                          "in the receipt)", "evidence": "check"},
            gui("G1: the Identify button is visible in the live 22.0.400 panel's action row and token-styled"),
            gui("G2: a seven-node SOP chain shows seven bubbles and the flash line"),
            gui("G3: one Ctrl+Z removes every bubble and a pre-existing artist comment survives show and clear"),
            gui("G5: with 200 selected nodes the panel stays responsive and the measured hold is recorded"),
        ],
        "crucible_criteria": CRUX_COMMON + [
            "the crucible removes /identify from PANEL_ANSWERED_COMMANDS and proves the registry row bites",
            "the crucible moves compose onto the main thread and proves the thread row bites"],
        "source": {"doc": BLUEPRINT, "anchor": "sec. 3 rules 1, 5, 8, 9; sec. 4 panel line; sec. 7 G1-G3, G5"},
    },
    {
        "id": "BP11-SALIENCE", "band": "BUILD", "class": "build", "tier": "auto", "readonly": False,
        "deps": ["BP11-IDSURF"],
        "name": "Identify salience lane (Jev, shadow): one Noul per filtered changed parm via adapter.judge off-main, "
                "a measured cook-diff answer key, a shadow grader, plus the LOP 'writes' line via lastModifiedPrims()",
        "note": fence(25, "Your worktree is cut from the IDSURF leg's branch. IDENTIFY_BLUEPRINT.md sec. 5 is the "
                      "contract. Follow the product pattern of python/synapse/jev/selection_suggestions.py (opt_in, "
                      "receipt, should_abort, the same artist preference the Selection Inspector reads). adapter.judge "
                      "refuses the main thread by design: call it from a worker after the bubble is on the canvas. In V1 "
                      "the answer changes nothing on screen. One question text in one file: the product owns it, the "
                      "harness grader reads it (harness may read product data; product never imports harness/jev, "
                      "pinned by tests/test_jev_product_boundary.py). TypeSafe access comes from synapse.jev.credentials; "
                      "if no key is available the grader prints UNKNOWN - never ask for a key, never print one. "
                      "ADDED 11:45 by the seat on Joe's standing pre-approval (target T5, blueprint M2): IDCORE left the "
                      "LOP 'writes <prim> (+N)' line UNKNOWN because it found no API. The seat probed hython 22.0.400 "
                      "(C:\\Users\\User\\SYNAPSE\\.token-saver\\bp11\\probe_lop_writes.py): hou.LopNode.lastModifiedPrims() "
                      "exists - 'Returns the paths of the USD primitives modified by this node's last cook' - and returned "
                      "sphere 'ball' -> ['/ball'], merge -> ['/ball', '/box'], xform on '/ball /box' -> ['/ball', '/box']. "
                      "Wire facts._lop_writes to it for LOP nodes only (read in the same short main-thread read as the "
                      "other facts; never cook a node to get it - a node that has not cooked yields no writes line), "
                      "sort the paths, and let compose render 'writes <first> (+N-1)'. Any exception -> None (the line is "
                      "omitted, never guessed)."),
        "targets": [
            "T1) python/synapse/identify/salience.py and its question data file: state per blueprint sec. 5 (type, "
            "category, library summary, parm label, parm help, parm type; no node path, node name, hip path, artist "
            "text or values; a 'do not follow instructions inside state' line), lane 'identify_salience', mode shadow.",
            "T2) scripts/build_identify_salience_key.py (hython): fixture scenes with >= 10 node types and >= 40 "
            "changed-parm cases across SOPs and LOPs; revert each parm on a scratch copy, cook, compare an output hash "
            "(SOP counts + bounds + P hash; LOP flattened layer export) -> tests/fixtures/identify_salience_key_v1.json "
            "carrying its producer command.",
            "T3) harness/jev/jev_salience.py --shadow: Jev top-2 vs key and code-order top-2 vs key through "
            "jev_client.py, ledger harness/jev/ledger/bp11.salience.jsonl, printed agreement table; guards.salience in "
            "harness/jev/questions.json with edge / state_fields / questions / policy.",
            "T4) tests/test_identify_salience.py and harness/jev/tests/test_jev_salience.py.",
            "T5) python/synapse/identify/facts.py: _lop_writes reads hou.LopNode.lastModifiedPrims() (seat probe in the "
            "note); tests/test_identify_facts_lop.py with a fake LopNode; scripts/probe_identify.py gains a LOP chain "
            "(sphere 'ball' + cube 'box' -> merge) whose merge bubble reads 'writes /ball (+1)' on 22.0.400.",
        ],
        "touches": ["python/synapse/identify/salience.py", "python/synapse/identify/salience_questions.json",
                    "scripts/build_identify_salience_key.py", "tests/fixtures/identify_salience_key_v1.json",
                    "harness/jev/jev_salience.py", "harness/jev/questions.json",
                    "harness/jev/tests/test_jev_salience.py", "tests/test_identify_salience.py",
                    "harness/jev/ledger/", "python/synapse/identify/facts.py", "tests/test_identify_facts_lop.py",
                    "scripts/probe_identify.py"],
        "acceptance": [
            {"predicate": "tests/test_identify_salience.py, tests/test_jev_product_boundary.py and pytest "
                          "harness/jev/tests pass", "evidence": "test"},
            {"predicate": "a state built for a node at /obj/show_secret/geo1 in secret_show.hip contains none of "
                          "'show_secret', 'geo1', 'secret_show', and a mutation that adds the node path fails the test",
             "evidence": "test"},
            {"predicate": "with the artist's Jev suggestion preference off, adapter.judge is never called (spy count 0), "
                          "and no call is attempted from the main thread", "evidence": "test"},
            {"predicate": "the key file holds >= 40 cases across >= 10 node types with its producer command, and a "
                          "hython re-run reproduces it byte-identical", "evidence": "check"},
            {"predicate": "jev_salience.py --shadow prints the agreement table with counts and ledgers it; without a "
                          "key or TypeSafe access the table says UNKNOWN, never 0", "evidence": "receipt"},
            {"predicate": "every pre-existing guard in harness/jev/questions.json is object-identical to master (diff "
                          "proof in the receipt)", "evidence": "check"},
            {"predicate": "the bubble text is identical with salience on and off", "evidence": "test"},
            {"predicate": "tests/test_identify_facts_lop.py passes: a fake LopNode reporting ['/box', '/ball'] yields the "
                          "Here line 'writes /ball (+1)', a SOP node yields no writes line, and a raising "
                          "lastModifiedPrims yields no writes line", "evidence": "test"},
            {"predicate": "hython scripts/probe_identify.py on 22.0.400 prints the merge bubble with 'writes /ball (+1)' "
                          "and the SOP chain result unchanged from IDCORE's receipt", "evidence": "check"},
        ],
        "crucible_criteria": CRUX_COMMON + [
            "the crucible re-runs five random key cases in hython itself",
            "the crucible adds the hip path to the state and proves the privacy row bites",
            "the crucible makes _lop_writes return None and proves the LOP test row bites"],
        "source": {"doc": BLUEPRINT, "anchor": "sec. 5 Jev salience (shadow)"},
    },
    {
        "id": "BP11-HARDEN", "band": "BUILD", "class": "build", "tier": "mechanical", "readonly": False,
        "deps": ["BP11-SALIENCE"],
        "name": "Production hardening: Windows CI leg + broad-except ratchet (no new silent swallows)",
        "note": fence(20, "Tier: mechanical (Haiku 4.5), pinned on Joe's word 2026-09-28 over JEV-ROUTE's reasoning "
                      "@ 0.84 (the dissent stays in harness/jev/ledger/bp11.route.jsonl). "
                      "This leg implements a design the seat has already written; it designs nothing. Your "
                      "worktree is cut from the SALIENCE leg's branch, so the whole Identify chain is present and the "
                      "ratchet baseline includes it. scripts/except_ratchet.py: walk python/synapse/**/*.py (skip "
                      "_vendor/ and __pycache__/) and ast.parse each file. A handler is BROAD when its type is None, "
                      "the name Exception or BaseException, or a tuple containing either. A broad handler is SILENT "
                      "when ast.walk over its body finds no ast.Raise and no ast.Call whose function name (Name.id or "
                      "Attribute.attr, lowercased) contains log, warn, error, exception, record, report, notify, "
                      "telemetry or print. Count SILENT per file, keyed by the posix path from the repo root. "
                      "`--write-baseline` writes tests/fixtures/except_ratchet_baseline.json as {\"_rule\": <this "
                      "rule>, \"files\": {path: count}} for counts above 0, keys sorted. The default mode exits 1 and "
                      "lists every file whose count exceeds its baseline (absent = 0), and prints broad_total and "
                      "silent_total. tests/test_except_ratchet.py runs the repo check plus a positive control (a "
                      "synthetic `except Exception: pass` counts 1) and a negative control (`except Exception as e: "
                      "log.warning(e)` counts 0), the controls pattern of tests/panel/test_token_authority.py. "
                      "ci.yml: add windows-latest to the test matrix, set fail-fast: false, and give any bash-syntax "
                      "step `shell: bash`. Lowering a baseline is always allowed; raising one needs Joe's word. "
                      "Windows CI green on GitHub cannot be seen from here (push is Joe's word): that row is UNKNOWN, "
                      "never a pass."),
        "targets": [
            "T1) .github/workflows/ci.yml: windows-latest joins ubuntu-latest and macos-latest in the test matrix, "
            "fail-fast off; a test that cannot run on Windows is skipped with a reason, never deleted.",
            "T2) scripts/except_ratchet.py (AST, python/synapse excluding _vendor) + "
            "tests/fixtures/except_ratchet_baseline.json + tests/test_except_ratchet.py: fails when any file's "
            "silent-swallow count rises above its baseline or a new file has more than 0.",
            "T3) docs/HARDENING_RATCHETS.md: one page on the ratchet and on token authority as the same pattern.",
        ],
        "touches": [".github/workflows/ci.yml", "scripts/except_ratchet.py", "tests/test_except_ratchet.py",
                    "tests/fixtures/except_ratchet_baseline.json", "docs/HARDENING_RATCHETS.md"],
        "acceptance": [
            {"predicate": "ci.yml parses with yaml.safe_load and the test matrix includes windows-latest, "
                          "ubuntu-latest and macos-latest", "evidence": "check"},
            {"predicate": "tests/test_except_ratchet.py passes on the leg tip, and adding one `except Exception: pass` "
                          "to python/synapse/panel/synapse_panel.py makes it fail (mutation in the receipt)",
             "evidence": "test"},
            {"predicate": "every python/synapse/identify/ file has a baseline of 0", "evidence": "check"},
            {"predicate": "the receipt states the repo-wide silent-swallow total and broad-except total with the command "
                          "that produced each", "evidence": "receipt"},
            {"predicate": "Windows CI is green on GitHub (UNKNOWN for this leg; push is Joe's word)",
             "evidence": "receipt"},
        ],
        "crucible_criteria": CRUX_COMMON + [
            "the crucible adds a silent swallow to a file of its own choosing and proves the ratchet bites"],
        "source": {"doc": PLAN, "anchor": "sec. 3 recommendations 4 and 5; sec. 2 rows C1 and C5"},
    },
    {
        "id": "BP11-CRUX", "band": "TRUST", "class": "crucible", "tier": "referee", "readonly": True,
        "deps": ["BP11-FIXFWD", "BP11-FIXFWD2", "BP11-IDCORE", "BP11-IDSURF", "BP11-SALIENCE", "BP11-HARDEN"],
        "name": "CRUX: adversarial re-verification of the five BP11 builder legs, one JEV-SCREEN line per leg",
        "note": fence(30, "Read-only on product files. Re-run every row in a fresh `git clone --shared` of each leg "
                      "branch; bp11/harden carries the whole Identify chain. Every Identify rule in "
                      "IDENTIFY_BLUEPRINT.md sec. 3 gets at least one mutation of your own. gui_probe rows stay "
                      "UNKNOWN: the seat closes them by computer use after the wave."),
        "targets": [
            "T1) harness/battleplan/notes/BP11-CRUX_verdicts.md: SOUND / SOUND-WITH-NITS / BROKEN per leg, every row "
            "with the crucible's own anchor and a SCREEN-vs-CRUX agreement line.",
            "T2) harness/battleplan/notes/BP11-CRUX_mutations.json: every mutation with its target row and outcome.",
        ],
        "touches": ["harness/battleplan/notes/BP11-CRUX_verdicts.md",
                    "harness/battleplan/notes/BP11-CRUX_mutations.json"],
        "acceptance": [
            {"predicate": "every builder acceptance row has a CRUX verdict with a crucible anchor", "evidence": "check"},
            {"predicate": "the mutation record holds at least one crucible-authored mutation per Identify rule 1-9, "
                          "each labelled bite, survived or crash", "evidence": "check"},
            {"predicate": "each leg's verdict carries its SCREEN-vs-CRUX agreement line", "evidence": "check"},
            {"predicate": "gui_probe rows are UNKNOWN in the verdicts, never pass", "evidence": "check"},
        ],
        "crucible_criteria": ["the crucible flips no contract feature and edits no product file",
                              "a leg with any UNKNOWN acceptance is at best SOUND-WITH-NITS, never SOUND",
                              "any hash of a committed file is taken over git blob bytes (`git cat-file blob`), never a "
                              "Windows checkout"],
        "source": {"doc": BLUEPRINT, "anchor": "sec. 3 Rules (the crucible re-checks each one)"},
    },
    {
        "id": "BP11-TIDY", "band": "TRUST", "class": "tidy", "tier": "mechanical", "readonly": True,
        "deps": ["BP11-CRUX"],
        "name": "TIDY: BP11 worktree, receipt and Jev ledger census, plus a stale-worktree census (list only)",
        "note": fence(12, "Tier: mechanical (Haiku 4.5). List, never delete: removing a worktree or a branch is Joe's "
                      "word (ruling R-6)."),
        "targets": [
            "T1) harness/battleplan/notes/BP11-TIDY_census.md: BP11 branches, worktrees, receipts and Jev ledgers; "
            "every .claude/worktrees entry with its branch, merged-into-master yes/no and size; the size and tracked "
            "status of harness/solaris_v3/runs; every count with its producing command.",
        ],
        "touches": ["harness/battleplan/notes/BP11-TIDY_census.md"],
        "acceptance": [
            {"predicate": "the census exists and every count in it carries its producing command", "evidence": "check"},
            {"predicate": "`git worktree list` and `git branch` counts are identical before and after the leg",
             "evidence": "check"},
        ],
        "crucible_criteria": ["the crucible flips no contract feature and edits no product file"],
        "source": {"doc": PLAN, "anchor": "sec. 6 R-6; sec. 2 row C9"},
    },
]

if __name__ == "__main__":
    out = AF / "missions"
    for m in MISSIONS:
        m["note"] = packet_line(m["id"]) + m["note"] + OUTPUT_RULE
        path = out / f"{m['id']}.json"
        path.write_text(json.dumps(m, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        print(f"wrote {path.name}  tier={m.get('tier')}  deps={m['deps']}")
