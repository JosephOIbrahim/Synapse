# BP11-CRUX - verdicts on the six BP11 builder legs

2026-09-28 - referee seat (Fable 5.1) - branch `bp11/crux` - read-only on product files.

The brief says five builder legs; its dependency list carries six, because BP11-FIXFWD2 is the fix-forward of
BP11-FIXFWD on the same branch line. Six verdicts follow.

Every row was re-run by the crucible in a **fresh `git clone --shared -c core.longpaths=true` of the leg branch**
under the session scratchpad (clone tips: fixfwd 38fbb912, fixfwd2 88bcf957, idcore 5f5c4c13, idsurf 6fc22be6,
salience 92c81850, harden fbd7eb8a; `git status --short` empty on each before any check). Anchors are the
crucible's own. Builder `proved_it_bites` claims were not trusted: the mutation record is
`harness/battleplan/notes/BP11-CRUX_mutations.json` (23 mutations: 20 bite, 3 survived, 0 crash; every
IDENTIFY_BLUEPRINT.md sec. 3 rule 1-9 carries at least one crucible-authored mutation).

Import binding was proven per clone before any test was trusted: under pytest, `pyproject.toml:110`
`pythonpath = ["python"]` binds `synapse` to the clone (the R5-M1 / R8-M1 panel mutations could only redden
tests if it does); under bare python `synapse` resolves to the main tree
(`C:\Users\User\Synapse\python\synapse\__init__.py`), so every crucible script inserts `<clone>/python` at
`sys.path[0]` and prints the module file it bound.

Tooling: hython `C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe` (22.0.400, Python
3.13.10, `hou.applicationVersionString()` printed by every probe), system Python 3.14.2, git 2.55.0. No Houdini
GUI for this seat: every gui_probe row stays UNKNOWN.

**How verdicts are assigned** (BP10-CRUX's three definitions plus one clause):

- **SOUND** - every row passes on re-run, no UNKNOWN, no crucible nit.
- **SOUND-WITH-NITS** - any UNKNOWN row; or a row that fails as written but the receipt itself discloses the gap;
  or a rule violation / unpinned rule that the crucible's own checks surface outside the rows.
- **BROKEN** - a builder-marked `pass` that is false on re-run and is either undisclosed in the receipt or lands a
  false claim on an owned/product surface (NOTICE, CI, a live guard, product code). Nothing merges on a BROKEN.

Row numbering follows the receipt order (1-based); the JEV SCREEN ledger indexes the same rows 0-based
(`acc_0` = row 1). SCREEN lines are read from `harness/jev/ledger/bp11.screen.jsonl` (main tree, untracked).

---

## BP11-FIXFWD - **BROKEN** (superseded on its own branch line by BP11-FIXFWD2: merge `bp11/fixfwd2`, never `bp11/fixfwd`)

Checkout 38fbb912 (product e4500544).

| # | Predicate (short) | CRUX verdict | Crucible anchor |
|---|---|---|---|
| 1 | ADR-0001 Refused Sites lists 8 refusals naming the blueprint's 8 subjects | **pass** | `.scratch/crux_adr_check.py`: 8 numbered bullets under `## Refused Sites`, 0 missing subjects (quarantine, licence, probe, stamp, benchmark, which model, instant tier, run_on_main). Mutation F1-M1 (delete refusal 8) reddens only the crucible's check: no tracked test pins the ADR (`tests/test_vendor_notice.py` 2 passed with the bullet gone). |
| 2 | verifier exits 0 on the tip and 1 after one flipped hex digit | **FAIL on any LF platform** (pass on this Windows box only) | Windows clone: rc 0, 2 passed. The verifier runs `git clone --depth 1 https://github.com/healkeiser/fxhoudinimcp` into a tmpdir on EVERY run (`scripts/verify_vendor_notice.py:42-49`; network inside a test) and hashes that checkout. With the clone forced to LF - `GIT_CONFIG_PARAMETERS="'core.autocrlf=false'"`, the default on ubuntu-latest / macos-latest - rc 1 with 32 mismatches and `FAILED tests/test_vendor_notice.py::test_verify_vendor_notice` (T2 F1-M2). CI is red for this branch on two of three matrix legs. |
| 3 | NOTICE.md anim.md hash == sha256 of anim.md at upstream 29b6695b | **FAIL** | NOTICE(fixfwd) line 17 `57514d24...` is the CRLF-checkout hash; the blob is `57fae325...`. Crucible sha256 of `git cat-file blob HEAD:<path>` for all 32 table rows: 0 match, 32/32 equal sha256(blob with LF->CRLF). Five random upstream guides + LICENSE at 29b6695b (`python/fxhoudinimcp/prompts/markdown/workflows/*.md`, `LICENSE`; `random.seed(20260928)`): 0/6 match. NOTICE line 13 says the values are "computed from the committed git blob (LF bytes)" - a false provenance sentence on an owned surface. The receipt's "1104 B blob" for LICENSE is the CRLF size; the blob is 1083 B. |
| 4 | harness/jev/questions.json byte-identical to master | **pass** | `git diff --quiet origin/master HEAD -- harness/jev/questions.json` in the clone: IDENTICAL (origin/master = 312ed2cf). |

Disclosure status: BP11-FIXFWD2's receipt (its T3) records rows 2-3 as CRLF-tainted; the FIXFWD receipt itself
still says `green`, four `pass` rows, `packet_gaps: none identified`. BROKEN on the receipt and on the owned
surface; the branch line is repaired one commit later (f29d81fd) under `bp11/fixfwd2`.

**Screen vs CRUX:** SCREEN = REFEREE, weak rows [1, 3] (0-based -> rows 2 and 4), crux_need 0.52. CRUX: row 2
FAIL-on-CI (**agree**), row 4 pass (**disagree** - SCREEN doubted `git status` as evidence; the predicate holds),
row 3 FAIL (**SCREEN missed it** - `acc_2` supports 0.98; the CRLF trap needs a blob hash, not a read).
Agreement: **PARTIAL** - 1 of 2 flagged rows confirmed, 1 cleared, 1 unflagged row failed.

---

## BP11-FIXFWD2 - **SOUND-WITH-NITS**

Checkout 88bcf957 (product f29d81fd; carries the two FIXFWD commits).

| # | Predicate (short) | CRUX verdict | Crucible anchor |
|---|---|---|---|
| 1 | 32/32 NOTICE values == sha256(`git cat-file blob HEAD:<path>`) | **pass** | crucible python over the 32 table rows: blob-match 32, mismatch []. Upstream: 5 random guides + LICENSE at 29b6695b -> 6/6 match (muscles.md, io.md, tops.md, dopparticles.md, ocean.md, LICENSE). |
| 2 | anim.md = 57fae325..., LICENSE = 79a2891b... | **pass** | blob sha256 anim.md = `57fae325b428776d32fd368d4bb7d514e1a21ddf1798d275c7faad0ae0f2ba93` (2140 B, 0 CR), LICENSE = `79a2891ba34d73cb07da165714464f3bb6a6c6a254ea7ad1bac2cf3f7aae5918` (1083 B, 0 CR); both equal NOTICE lines 17 / 48. |
| 3 | tests pass, including the CRLF-table test | **pass** | 3 passed. F2-M1 (anim.md value -> its CRLF hash) reddens the verifier (`Mismatch anim.md: NOTICE 57514d24..., blob 57fae325...`) and 2 of 3 tests. F2-M2 (verifier reads the checkout instead of the blob) SURVIVES all 3 tests: `.gitattributes:12` `* text=auto eol=lf` makes checkout bytes == blob bytes in this repo, so the CRLF-table test cannot tell a blob-hashing verifier from a checkout-hashing one. |
| 4 | verifier hashes through git cat-file only; no read_bytes/open() on a guide path | **pass** | `grep -nE 'open\(|read_bytes|read_text' scripts/verify_vendor_notice.py` -> one hit, line 31, `read_text` on NOTICE.md itself. `git_blob()` = `git cat-file blob HEAD:<path>` (lines 58-67). CI simulation (`GIT_CONFIG_PARAMETERS` autocrlf=false): rc 0, "all 32 hashes match their committed git blobs". No network call. Pinned by grep only (see row 3). |

NITs: (a) `test_verify_vendor_notice_mutation_fails` and the CRLF test rewrite NOTICE.md in text mode -> CRLF on
Windows -> after a green run `git status` shows ` M python/synapse/_vendor/fxhoudinimcp/NOTICE.md`
(content-identical under `--ignore-cr-at-eol`; eol=lf is pinned, git warns "CRLF will be replaced by LF").
Write with `newline="\n"`. (b) F2-M2 survived (row 3). (c) The receipt's `for_ruling` on the predecessor
receipt is right: annotating BP11-FIXFWD.json is a human act, not a leg's.

**Screen vs CRUX:** SCREEN = REFEREE, weak rows [0, 1] (rows 1-2), partial 0.52 / 0.51. CRUX: both pass on re-run
(**disagree** on both - SCREEN read the count line and the literal hashes as under-evidenced; the crucible's own
blob hashes settle them). Rows 3-4 unflagged, pass. Agreement: **DISAGREE** - 0 of 2 flagged rows failed, 0
unflagged rows failed. No UNKNOWN row; SOUND-WITH-NITS on the nits alone.

---

## BP11-IDCORE - **SOUND-WITH-NITS**

Checkout 5f5c4c13 (product c46a6e79).

| # | Predicate (short) | CRUX verdict | Crucible anchor |
|---|---|---|---|
| 1 | compose + library + apply tests pass on system Python without hou | **pass** | 45 passed (`pytest -q --tb=line -p no:cacheprovider`, Python 3.14.2, no hou). |
| 2 | compose on the M0 PolyBevel facts -> one Here entry by label, no ramp internal | **pass** | `test_m0_polybevel_one_here_entry_no_ramp_internal` green; live hython probe with `SYNAPSE_SIDEFX_CORPUS_ROOT=G:/HOUDINI22/_CORPUS`: `[OK] polybevel one Here entry: here='Distance 0.07'`, summary from the library "Bevels points and edges." |
| 3 | artist comment byte-identical after show->clear, after show+BeforeSave+AfterSave+clear, and when it quotes the sentinel in prose | **pass** - NIT | the three tests green; the crucible's own comment (`.scratch/crux_artist_comment.py`: two lines quoting `~ identify ~` inline) -> bubble shown, byte-identical after clear. R2-M1 (`strip_block` drops one extra line) reddens all three tests and the crucible's check. **NIT (rule 2 edge):** an artist comment that carries the sentinel as a STANDALONE line (`"artist line one\n~ identify ~\nartist line two"`) is read as an Identify block before any show: `has_block()` is True, `show()` strips "artist line two", and after `clear()` the comment is `"artist line one"` - not byte-identical; `toggle()` on such a node clears instead of showing. The `_block_start` docstring (apply.py:70-77) promises the opposite ("an artist's own standalone sentinel (earlier) is left in place"), which only holds after our block has been appended. Low probability, deterministic, undisclosed. |
| 4 | library returns unknown where a search would phantom; swapping exact for search reddens a test | **pass** | `test_exact_returns_unknown_where_search_would_phantom` green; R6-M1 (help_summary -> stem `LIKE` search, first page wins; `sidefx_library.py`) reddens it plus `test_help_summary_prefers_versioned_page` and `test_help_summary_excludes_example_pages` (3 failed, 12 passed). |
| 5 | hython probe: version, 7 bubbles, 0 sentinel lines on disk, one undo group per show | **pass** | crucible run in the clone: `VERSION 22.0.400`, `7/7 comments carry the sentinel`, `undoLabels gained 1 'SYNAPSE Identify'`, `7/7 sentinels back after save`, `0 sentinel lines survived the save`, `PROBE_RESULT PASS`. `CORPUS_CONFIG None` in a scratch clone (the probe walks parent dirs for `.synapse/sidefx_library.json`; a scratchpad has none) -> all seven summaries "- not in library" and still PASS; a second run with the corpus env set resolved 7/7 from the library. R3-M1 (show outside its undo group) -> `undoLabels gained 0` + `test_one_undo_group_per_show_and_per_clear`; R4-M1 (BeforeSave strip disabled) -> `7 sentinel lines survived the save`, `PROBE_RESULT FAIL` - while all 12 apply tests stay green (the save path is pinned live only). |
| 6 | 60-node main-thread apply timed against the 100 ms target | **pass** | `APPLY_MS 60 nodes = 0.5 ms` (second run 0.7 ms), producer `apply.show` timed in hython. R5-M2 (cap removed) -> `test_cap_and_flash_line`. |
| 7 | no harness/network import under identify; writers only in apply.py | **pass** - NIT | `grep -rnE 'import harness|from harness|socket|requests|urllib|http' python/synapse/identify --include=*.py` -> 0 hits; `grep -c 'setComment\|setGenericFlag\|hou.undos'` -> apply.py 11 lines (10 code + 1 docstring), every other file 0. R1-M2 (`import urllib.request` in compose.py) reddens only the crucible's grep: all 45 tests survive. R7-M1b (`read_selection_facts` stops calling `inspect_selection`) survives all 45 tests too; only the crucible's grep bites. Rule 1's no-network clause and rule 7 are unpinned by any tracked test. |

**Screen vs CRUX:** SCREEN = REFEREE, weak rows [0..6] (all seven), crux_need 0.99, self_contradiction 0.17.
CRUX: all seven pass on re-run (**disagree** on every flagged row); the two nits (rule-2 sentinel collision,
rules 1/7 unpinned) are crucible findings outside the rows. Agreement: **DISAGREE** - 0 of 7 flagged rows
failed. SCREEN's 0.99 read evidence style ("ms figure", "grep count lines"), not defects.

---

## BP11-IDSURF - **SOUND-WITH-NITS** (four gui_probe rows UNKNOWN)

Checkout 6fc22be6 (product fbbb7187; base bp11/idcore).

| # | Predicate (short) | CRUX verdict | Crucible anchor |
|---|---|---|---|
| 1 | identify_button + token_authority + every PANEL_ANSWERED pin pass | **pass** | 74 passed (test_identify_button 9, test_token_authority 33, test_palette_ranking, test_panel_finesse, test_first_session_panel). |
| 2 | '/identify' is panel-answered, appears exactly once in `_load_entries()`, never reaches the model | **pass** | R1-M1 / R1-M1b (drop `"/identify"` from `PANEL_ANSWERED_COMMANDS`): crucible membership check `panel-answered = False`; 3 failed - `test_identify_is_panel_answered_and_appears_exactly_once`, `test_the_five_panel_answered_commands_are_marked_at_the_one_build_path`, `test_exactly_five_palette_sends_are_still_literals`. R9-M1 (catalogue row duplicated): 2 failed - `appears_exactly_once`, `still_literals`. |
| 3 | compose/library off the Qt main thread, apply on it, thread identities in a real-handler test | **pass** | R5-M1 (`run_on_main(lambda: _compose.compose(...))` in `_identify_worker`) -> `test_compose_and_library_run_off_main_and_apply_runs_on_main` FAILED, 8 passed. |
| 4 | selection_inspector.py has no setComment / setGenericFlag / undos call (count 0) | **pass** | `grep -Ec 'setComment|setGenericFlag|\.undos' python/synapse/panel/selection_inspector.py` -> 0. R8-M1 (a `setComment` writer in `identify_cell_text`) -> `test_inspector_stays_read_only_no_writer_calls` FAILED + crucible grep count 1. |
| 5 | G1: Identify button visible and token-styled in the live 22.0.400 panel | **UNKNOWN** | gui_probe; no GUI for this seat. Static only: `c.Button("Identify", variant="ghost")` at synapse_panel.py:1251, action-row grid col 6 (line 1261). |
| 6 | G2: seven bubbles + the flash line on a SOP chain | **UNKNOWN** | gui_probe. Headless half proven (IDCORE row 5: 7/7 sentinels live); the flash text shape is pinned by `test_cap_and_flash_line` only. |
| 7 | G3: one Ctrl+Z removes every bubble; a pre-existing artist comment survives | **UNKNOWN** | gui_probe. Headless half: one `SYNAPSE Identify` undo label per show (live), byte-identical artist text (tests + crucible). The IDCORE rule-2 sentinel-collision nit applies here too. |
| 8 | G5: 200 selected nodes, panel responsive, hold measured | **UNKNOWN** | gui_probe. Headless: 60-node apply 0.5-0.7 ms in hython; the Qt-side hold is unmeasured. |

NITs: (a) R9-M2 **SURVIVED**: replacing the token button with `QtWidgets.QPushButton("Identify")` +
`setStyleSheet("color: #ff00ff;")` keeps `tests/panel/test_token_authority.py` (33 passed) and
`test_identify_button.py` (9 passed) green - rule 9's "every new widget uses components and tokens" is not
pinned for this button (token authority audits colour declarations, not widget construction). (b) `_run_identify`
adds a silent `except Exception: pass` at synapse_panel.py:3346 (and :3369, :3373 in `_identify_worker`) on the
new zero-token path - the exact class HARDEN's ratchet exists to stop growing; on bp11/harden they are counted
into synapse_panel.py's baseline rather than logged. (c) The receipt's "74 passed" reproduced exactly.

**Screen vs CRUX:** SCREEN = REFEREE, weak rows [0, 1, 2, 4, 5, 6, 7], crux_need 0.87; rows 4-7 `claims_unknown`
1.0. CRUX: rows 5-8 UNKNOWN (**agree** x4), rows 1-3 pass on re-run (**disagree** x3), row 4 unflagged and pass.
Agreement: **PARTIAL** - 4 of 7 flagged rows confirmed as UNKNOWN, 3 cleared, 0 unflagged failed.

---

## BP11-SALIENCE - **SOUND-WITH-NITS**

Checkout 92c81850 (product df7aba01; base bp11/idsurf).

| # | Predicate (short) | CRUX verdict | Crucible anchor |
|---|---|---|---|
| 1 | salience + product-boundary + harness/jev/tests pass | **pass** | 93 passed for exactly the named set plus test_identify_facts_lop; the receipt's 138 adds the 45 IDCORE tests. |
| 2 | a state for /obj/show_secret/geo1 in secret_show.hip leaks none of the secrets; adding the path reddens | **pass** | `test_states_for_a_secret_node_leak_nothing` green; S-M1 (`_node_view` appends `facts["path"]` to node_summary) -> FAILED, 8 passed. |
| 3 | preference off -> `adapter.judge` never called; never from the main thread | **pass** | S-M3 (`opt_in` no longer gates `run_shadow`) -> `test_preference_off_never_calls_judge` FAILED. `.scratch/crux_slot_leak.py`: after one failing spawn a second `run_shadow` still returns a Thread (slot released) on this tip. |
| 4 | key >= 40 cases across >= 10 types with its producer; a hython re-run is byte-identical | **pass** - NIT | fixture: 45 cases, 21 (context, type) pairs, 33 matters=True, 2 skipped, producer `hython scripts/build_identify_salience_key.py`. Full producer re-run in a second fresh clone (salience2, hython 22.0.400): `KEY_RESULT PASS`, `git diff --stat` on the fixture EMPTY (byte-identical), 45/45 hash pairs identical, 45/45 `matters` agree. **NIT:** the crucible's own 5-random-case re-measure (`.scratch/crux_key_recheck.py`, seed 20260928, the leg's own `measure_case`) matched 4/5; `Lop light::2.0 primpath` differs in BOTH hashes because `stage.Flatten().ExportToString()` embeds `HoudiniCreatorNode = <node id>` / `HoudiniEditorNodes` (probe `.scratch/crux_lop_export.py`: two identical lights in one session -> different sha, diff `int HoudiniCreatorNode = 10` vs `11`). LOP hashes reproduce only by the full script in creation order; `matters` is unaffected (both hashes in a case share the id). |
| 5 | `--shadow` prints the agreement table with counts and ledgers it; no key / no access -> UNKNOWN, never 0 | **pass** - NIT | `SYNAPSE_JEV=off python harness/jev/jev_salience.py --shadow`: 6 gradeable groups, `code-order agree=9/10`, `jev agree=UNKNOWN`, ledger line written. **NIT:** the grader writes the TRACKED `harness/jev/ledger/bp11.salience.jsonl` on every run (clone dirty afterwards: ` M harness/jev/ledger/bp11.salience.jsonl`). |
| 6 | every pre-existing guard object-identical to master | **pass** | crucible compare against `origin/master:harness/jev/questions.json`: added ['salience'], removed [], identical 9 of 9, changed []. |
| 7 | bubble text identical with salience on and off | **pass** | `test_bubble_text_identical_salience_on_and_off` green. `run_shadow` has no caller under python/synapse (grep: no importer of `identify.salience`) - disclosed by the receipt and its spawn. |
| 8 | facts_lop: 'writes /ball (+1)', SOP -> none, raising -> none | **pass** | 5 passed; S-M2 (`_lop_writes` returns None) -> `test_lop_writes_sorts_and_counts` + `test_lop_writes_here_line_reads_writes_ball_plus_one` FAILED. |
| 9 | hython probe: merge bubble 'writes /ball (+1)', SOP rows unchanged from IDCORE | **pass** | crucible run: `BUBBLE both lop_writes= {'first': '/ball', 'count': 2} ... // writes /ball (+1)`, `PROBE_RESULT PASS`; SOP rows identical to IDCORE (7/7, 1 group, 0 on disk, 0.5 ms). S-M2 live: `[FINDING] LOP merge Here line ...: here=None`, `PROBE_RESULT FAIL`. |

Honest in the receipt and confirmed: live Jev agreement UNKNOWN (no billed run); G4 UNKNOWN (gui).

**Screen vs CRUX:** SCREEN = REFEREE, weak rows [1, 2, 5, 6, 7, 8], crux_need 0.56. CRUX: all six flagged rows
pass on re-run (**disagree** x6); the two nits live in unflagged rows 4 (supports 1.0) and 5 (supports 0.88).
Agreement: **DISAGREE** - 0 of 6 flagged rows failed, 2 unflagged rows carry nits, none fails.

---

## BP11-HARDEN - **BROKEN** (the tip that carries the whole Identify chain)

Checkout fbd7eb8a (product 04d827e4; base bp11/salience).

| # | Predicate (short) | CRUX verdict | Crucible anchor |
|---|---|---|---|
| 1 | ci.yml parses; matrix has windows/ubuntu/macos | **pass** | `yaml.safe_load`: job `test` os = [ubuntu-latest, macos-latest, windows-latest], python [3.11, 3.14], fail-fast False. H-M2 (windows-latest removed) reddens the crucible's yaml check only; `tests/test_r_track.py -k ci_` plants its own ci.yml and survives - the matrix is unpinned by a tracked test. |
| 2 | test_except_ratchet passes; a new `except Exception: pass` in synapse_panel.py makes it fail | **pass as written - BROKEN in substance** | 4 passed. H-M1 (a swallow appended to compose.py, the crucible's file of choice): `python scripts/except_ratchet.py` rc 1 `python/synapse/identify/compose.py: 0 -> 1`; `test_except_ratchet_passes_on_clean_tree` + `test_identify_files_have_zero_baseline` FAILED - the checker bites on a fresh baseline. But `test_positive_control_detects_new_silent_handler` (tests/test_except_ratchet.py:29-91) never asserts the checker exits 1: it runs `--write-baseline`, asserts the count grew, and its `finally` restores only synapse_panel.py. H-M3 (`.scratch/crux_ratchet_selfdefeat.py`): plant a swallow -> checker rc 1; run that test file ONCE; restore the swallow's file; re-plant -> checker rc 0 (`OK`); the tracked baseline now carries `"python/synapse/identify/compose.py": 1`. One run of the leg's own tests resets the ratchet. The same test leaves synapse_panel.py and the baseline CRLF-rewritten (` M` in `git status`; eol=lf pinned by .gitattributes:12). |
| 3 | every python/synapse/identify file has a baseline of 0 | **pass as written - BROKEN in substance** | `analyze_file` silent counts: __init__ 0, apply 0, compose 0, facts 0, library 0, salience 0; the baseline lists no identify file. Achieved by editing FOUR files outside the leg's `touches` (`git diff --name-only 92c81850 04d827e4`: identify/apply.py, facts.py, library.py, salience.py) and the edits regressed the product: (i) `salience.py:215` IndentationError - the module cannot import; `pytest tests/test_identify_salience.py` -> collection ERROR, 0 collected; (ii) `library.py:104` UnboundLocalError on `hit` when the lookup raises - `test_summarize_swallows_lookup_error_to_unknown` FAILED (1 failed, 14 passed): a library outage now crashes the bubble path instead of an honest unknown; (iii) `facts.py:68-76` `_parm_is_expression` returns True whenever `parm.expression()` raises, i.e. for every literal parameter - hython 22.0.400 on the harden clone (`.scratch/crux_harden_regress.py`): `sizex` literal 2.5 -> `is_expression=True`, bubble `Size (expr)`; the leg's own probe on the same clone prints `PolyBevel ... // Distance (expr)` and `Scatter ... // Force Total Count (expr)` where every earlier tip prints `Distance 0.07` / `Force Total Count 250`, and still ends `PROBE_RESULT PASS` because no probe check pins a Here value; (iv) `salience.py` dropped `_JOBS.slot.release()` in the spawn-failure branch (moot while the module cannot import). The receipt's single finding calls these "logging added to import guards". |
| 4 | receipt states repo-wide silent and broad totals with the producer command | **pass** | `python scripts/except_ratchet.py` on the clone prints `broad_total=1378`, `silent_total=995`, matching the receipt's `--write-baseline` figures. |
| 5 | Windows CI green on GitHub | **UNKNOWN** | push is Joe's word; unmeasurable here. Note: the ubuntu/macos legs would collect `tests/test_identify_salience.py` and ERROR on this tip regardless of OS. |

Merge consequence: `bp11/harden` is the only branch carrying idcore + idsurf + salience + harden together, and its
product commit breaks the chain it carries. Two clean routes for Joe's ruling: **(A)** merge `bp11/salience`
(92c81850, SOUND-WITH-NITS, the whole Identify chain) and redo HARDEN on top of it without touching
`python/synapse/identify/` (the ratchet rows then need a route that does not rewrite identify files: baseline the
four files' honest counts, or fix the except blocks in a leg whose `touches` include them); **(B)** fix-forward on
`bp11/harden`: restore the four identify files to 92c81850, rebuild the baseline, repair the positive-control test
(assert checker rc 1; never persist the rewritten baseline; write with `newline="\n"`). Either way the two
CRLF-rewriting tests (HARDEN's control, FIXFWD2's mutation test) deserve the same `newline` fix.

**Screen vs CRUX:** SCREEN = REFEREE, weak rows [0, 1, 2, 4], self_contradiction 0.22, crux_need 1.56 (the wave's
highest). CRUX: row 2 BROKEN in substance (**agree**), row 3 pass-as-written but the root of every regression
(**agree in direction** - SCREEN rated it supports 0.74 / partial 0.26), row 1 pass (**disagree**), row 5 UNKNOWN
(**agree**, `claims_unknown` 0.98). Agreement: **AGREE** - 3 of 4 flagged rows confirmed (two BROKEN-class, one
UNKNOWN), 1 cleared, 0 unflagged failed.

---

## Cross-leg notes

- gui_probe rows (IDSURF 5-8) and HARDEN row 5 are UNKNOWN; the seat closes G1-G6 by computer use after the wave
  (IDENTIFY_BLUEPRINT sec. 7).
- Mutation floor: rules 1-9 each carry at least one crucible mutation (T2 `rule_coverage`); 20 of 23 bite,
  3 survived (R9-M2 the token half of rule 9; F2-M2 checkout-vs-blob under eol=lf; H-M3 the ratchet self-reset),
  0 crash. Every driver mutation restored from HEAD; `restored_clean` is false on H-M1 only because HARDEN's own
  test rewrote the tracked baseline mid-check (restored by H-M3 STEP0 / STEP5).
- Rules pinned by the crucible's grep only (no tracked test reddens): rule 1's no-network clause (R1-M2), rule 7
  (R7-M1b), rule 9's token clause for the button (R9-M2), the ADR refusal list (F1-M1), the CI matrix (H-M2), and
  the BeforeSave strip under pytest (R4-M1 bites live only).
- Three tests rewrite tracked files in text mode and leave a Windows checkout dirty after a green run: HARDEN's
  positive control (synapse_panel.py + the baseline), FIXFWD2's mutation / CRLF tests (NOTICE.md), and the salience
  grader (ledger). `newline="\n"` and a restore-in-finally fix all three.
- No product file was edited by this leg. Nothing under `harness/battleplan/notes/` outside the two `touches`
  files was written.
- Packet gaps for the next wave: the packet gave BP10's verdict / receipt / mutation windows and the blueprint's
  sec. 3 and 7; it lacked the six leg receipts, the SCREEN ledger lines, the identify package source windows
  (apply / facts / library / salience / probe), the HARDEN diff to `identify/`, and the upstream guide path
  (`python/fxhoudinimcp/prompts/markdown/workflows/`). All were located by grep.
