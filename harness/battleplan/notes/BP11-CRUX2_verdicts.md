# BP11-CRUX2 - verdicts on bp11/hardfix and bp11/idfix, and closure of every CRUX finding

2026-09-28 - referee seat (Fable 5.1) - branch `bp11/crux2` - read-only on product files.

The merge candidate is `bp11/idfix` (tip 3f7157cd): the whole Identify chain (idcore, idsurf, salience)
plus HARDEN 04d827e4, HARDFIX 6efbe4c6 and IDFIX cf6d14f9, each with its receipt commit. HARDFIX is the
fix-forward of HARDEN (BROKEN in BP11-CRUX); IDFIX fixes the three live gate findings (G2 BOM, G5 hold, G6 disk).

Every row was re-run by the crucible in a **fresh `git clone --shared -c core.longpaths=true`** of the leg
branch under the session scratchpad: `idfix` at 3f7157cd (product cf6d14f9) and, for the HARDFIX rows that
name "the leg tip", `hardfix` at 5159b6bc (product 6efbe4c6). `git status --short` was empty on each before
any check and after every mutation. Anchors are the crucible's own; builder `BITES` claims were not trusted.
The mutation record is `harness/battleplan/notes/BP11-CRUX2_mutations.json` (16 mutations: 14 bite, 2 survived,
0 crash; the seat's seven seeds M1-M6/M8, the four IDFIX seeds M9-M12, and five crucible-authored C1-C5) plus
five probes (G6 hython round trip, H-M3 replay, memo outage, BOM, Python 3.11 CI analog).

Import binding: under pytest, `pyproject.toml:110` `pythonpath = ["python"]` binds `synapse` to the clone
(BP11-CRUX proved this per clone); every crucible script inserts `<clone>/python` at `sys.path[0]` and prints
the module file it bound (`MODULE .../scratchpad/idfix/python/synapse/__init__.py` in the G6, memo and BOM
probes).

Tooling: hython `C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe` (22.0.400, Python
3.13.10, `hou.applicationVersionString()` printed by the G6 probe); system Python 3.14.2 (`C:\Python314`);
`py -3.12` (3.12) and `py -V:Astral/CPython3.11.15` (3.11.15, the CI version) for the Windows clock rows;
git 2.55.0. No Houdini GUI for this seat: every gui_probe row stays UNKNOWN.

**How verdicts are assigned** (BP10-CRUX's three definitions, unchanged from BP11-CRUX):

- **SOUND** - every row passes on re-run, no UNKNOWN, no crucible nit.
- **SOUND-WITH-NITS** - any UNKNOWN row; or a row that fails as written but the receipt itself discloses the
  gap; or a rule violation / unpinned rule that the crucible's own checks surface outside the rows.
- **BROKEN** - a builder-marked `pass` that is false on re-run and is either undisclosed in the receipt or
  lands a false claim on an owned/product surface. Nothing merges on a BROKEN.

Row numbering follows the receipt order (1-based); the JEV SCREEN pre-read in the brief indexes the same rows
0-based (`acc_0` = row 1). The brief carries a SCREEN line for HARDFIX (weak rows [0..6], self_contradiction
0.27, crux_need 1.36) and none for IDFIX.

Closure labels used below: **closed by HARDFIX (anchor)**, **closed by IDFIX (anchor)** (added because four
CRUX findings were closed one commit later than HARDFIX), **for_ruling** (present in HARDFIX's receipt
`for_ruling[]`, item number given), **open** (nobody on this branch line touched it), **UNKNOWN** (gui or
billed run; never a pass).

---

## Merge candidate: `bp11/idfix` 3f7157cd - **SOUND-WITH-NITS**

Every HARDFIX row (7) and every IDFIX row (6) passes on re-run except IDFIX row 6, which is gui_probe and
stays UNKNOWN; the gui rows inherited from IDSURF (G1/G2/G3/G5) and SALIENCE (G4) stay UNKNOWN as well, so
the tip cannot be SOUND. No builder-marked pass was false on re-run. Every seed mutation bites. The crucible
edited no product file and flipped no contract feature; nothing under `harness/battleplan/notes/` outside the
two `touches` files was written. The nits are listed in their own section; none is BROKEN-class.

---

## BP11-HARDFIX - **SOUND-WITH-NITS**

Checkout 5159b6bc (product 6efbe4c6; base bp11/salience 92c81850, cut through bp11/harden fbd7eb8a).

| # | Predicate (short) | CRUX2 verdict | Crucible anchor |
|---|---|---|---|
| 1 | `compileall -q python/synapse/identify scripts` exits 0 on the leg tip | **pass** | rc 0 on the hardfix clone and on the idfix clone (crucible run, Python 3.14.2). |
| 2 | identify + button + ratchet tests pass, no collection error, counts in the receipt | **pass** | hardfix clone: `79 passed` for exactly the named set (`pytest -q --tb=line -p no:cacheprovider`). idfix clone, same set plus IDFIX's file: `90 passed`; per file apply 12, compose 18, library 21, facts_lop 5, salience 9, hardfix 5, idfix 4, button 10, ratchet 6. |
| 3 | diff vs bp11/salience removes only bare `pass`; no root-level `logging.<level>(` in identify | **pass** - NIT | `git diff 92c81850 6efbe4c6 -- python/synapse/identify/ \| grep '^-[^-]'`: 12 removed lines, 0 that are not a bare `pass` (5 at 12 spaces, 7 at 8). `grep -rnE 'logging\.(debug\|info\|warning\|error\|critical\|exception\|warn)\('` over identify: 0 hits on both tips; `_log = logging.getLogger(__name__)` at apply.py:19, facts.py:19, library.py:18, salience.py:37. M6 (a root `logging.debug(` back at apply.py:116): the row's grep bites, the 23 tracked identify+ratchet tests stay green - the clause is grep-pinned only (nit N2). |
| 4 | ratchet exits 1 naming an unparsable file (control); exits 0 on the tip with every identify file at 0 | **pass** | `python scripts/except_ratchet.py` on both tips: `broad_total=1379`, `silent_total=995`, `OK`, rc 0; the tracked baseline lists no identify file; `analyze_file` per identify file (`.scratch/crux2_identify_silent.py`): silent 0 for all six (broad: apply 2, facts 23, library 1, salience 1, others 0). Control M1 (salience.py made unparsable): `UNPARSED python/synapse/identify/salience.py` + `1 file(s) could not be read or parsed; ratchet fails closed.`, rc 1. C1 (fail-open `return (0, 0)` restored): `test_fail_closed_on_unparsable_file` + `test_analyze_file_raises_on_unparsable` FAILED. |
| 5 | each pin in test_identify_hardfix.py fails when defects 2-4 are re-applied | **pass** | M2 -> `test_plain_parm_is_not_expression` FAILED (1 failed, 4 passed); M3 -> `test_summarize_returns_honest_unknown_when_lookup_raises` FAILED; M4 -> `test_run_shadow_releases_slot_when_spawn_raises` FAILED. Live (hython 22.0.400, idfix clone, `.scratch/crux2_g6.py`): PolyBevel `offset` 0.07 -> `is_expression False`, bubble line `Distance 0.07` - the `(expr)` regression CRUX saw on bp11/harden is gone. |
| 6 | every CRUX finding against HARDEN or a touched file has a disposition | **pass** | closure table below: every CRUX finding in that scope is `closed by HARDFIX` (findings 1-7 = HARDEN rows 2-3 and the seat's six defects + defect 7) or `for_ruling` (receipt items 1-8). The crucible found no in-scope finding without a disposition. SALIENCE's G4 and live-Jev UNKNOWNs are outside the predicate (not against HARDEN or a touched file) and are listed as UNKNOWN here. |
| 7 | Windows python: routing + sessions + persistence + pkg_bootstrap report 0 failed, known cases xfailed | **pass** | idfix clone, Python 3.14.2: `291 passed, 2 xpassed` (58 s; the two persistence tests XPASS). Python 3.11.15 (the CI version, which the receipt admits it only reasoned about): `288 passed, 4 xfailed, 1 xpassed, 0 failed` (27 s) - XFAIL latency, expire_stale, both persistence; XPASS touch_updates_last_active (tick nondeterminism, strict=False is right). R310 passes on both with no marker. Marker check below. |

**Screen vs CRUX2:** SCREEN = REFEREE, weak rows [0..6] (all seven), self_contradiction 0.27, crux_need 1.36.
CRUX2: all seven pass on re-run (**disagree** on every flagged row); the nits live outside the rows.
Agreement: **DISAGREE** - 0 of 7 flagged rows failed, 0 unflagged rows failed.

### The Windows xfail markers (seat check)

`git diff fbd7eb8a 6efbe4c6 -- tests/test_routing.py tests/test_sessions.py tests/test_prst_network_persistence.py
tests/test_pkg_bootstrap_invariant.py`: 5 hunks, every one a pure `+@pytest.mark.xfail(...)` block; 0 removed
lines; no assertion, body or import changed; `test_pkg_bootstrap_invariant.py` has no hunk (R310 passes
transitively, confirmed on 3.11 and 3.14).

| Marker | Condition | reason | strict |
|---|---|---|---|
| test_routing.py:1106 `test_latency_is_tracked` | `sys.platform == "win32" and sys.version_info < (3, 13)` | 15.6 ms tick, BP12 root cause | False |
| test_sessions.py:115 `test_touch_updates_last_active` | same | same | False |
| test_sessions.py:145 `test_expire_stale` | same | same | False |
| test_prst_network_persistence.py:291 `test_store_still_opens_after_a_search_then_abrupt_restart` | `sys.platform == "win32"` | WAL UUID parse -> silent MemoryStore downgrade, BP12 | False |
| test_prst_network_persistence.py:441 `test_recall_survives_an_unrelated_prune` | `sys.platform == "win32"` | swap-and-pop recall reorder, BP12 | False |

`import sys` is present at test_routing.py:11, test_sessions.py:10, test_prst_network_persistence.py:60.
Removal (C4): with the marker deleted from `test_latency_is_tracked`, `py -3.12 -m pytest` -> `FAILED
tests/test_routing.py::TestTieredRouter::test_latency_is_tracked` (1 failed); the same test passes on 3.14.
With the marker in place it reports XFAIL on 3.12 and 3.11 and passes on 3.14. Nit N6 on the persistence pair.

---

## BP11-IDFIX - **SOUND-WITH-NITS** (row 6 gui_probe UNKNOWN)

Checkout 3f7157cd (product cf6d14f9; base bp11/hardfix 5159b6bc). IDFIX touched apply.py, library.py,
synapse_panel.py and three test files; `tests/fixtures/`, `scripts/except_ratchet.py`,
`tests/test_except_ratchet.py` and `.github/workflows/ci.yml` are byte-identical from hardfix to idfix
(`git diff --stat` empty), and ci.yml is unchanged since harden.

| # | Predicate (short) | CRUX2 verdict | Crucible anchor |
|---|---|---|---|
| 1 | identify tests + button test + ratchet test pass, no collection error, counts in the receipt | **pass** | `74 passed` for `tests/test_identify_*.py` (7 files: 12+18+21+5+9+5+4), `10 passed` button, `6 passed` ratchet; 90 in one run, 0 errors (Python 3.14.2, no hou). |
| 2 | show() on the fake hou registers the save callback exactly once; hython round trip with bubbles shown and NO explicit install leaves 0 sentinels on disk | **pass** | M9 (install call removed from show) -> `test_show_installs_exactly_one_save_callback`, `test_reshow_does_not_re_register_the_callback`, `test_toggle_and_clear_paths_also_arm_save_safety` FAILED (3 failed, 1 passed). Crucible hython probe `.scratch/crux2_g6.py` (22.0.400, product path facts -> compose -> show, no install call): before show `_SAVE_CALLBACK is None` True, hip callbacks 0; after show callback installed True, hip callbacks 1; `SHOWN 60 of 60`; `hou.hipFile.save` -> `RAW_DISK_SENTINELS 0`, `RESTORED_AFTER_SAVE 60`, artist note intact; fresh-hython reload -> `RELOAD_NODES 60 RELOAD_SENTINELS 0`, artist comment `'artist note'`; `G6_RESULT PASS`. C2 (before_save keeps the block) -> `test_before_save_strips_every_block_and_after_save_restores` FAILED, so the strip is now pinned under pytest, not live only. C5 (BeforeSave event no longer calls before_save) SURVIVES all 16 apply+idfix tests - the event-to-strip wiring is live-proven only (nit N5). |
| 3 | a BOM-prefixed help text with `#key: value` header lines yields its first prose sentence | **pass** | M10 (header strip dropped) -> 4 FAILED: `test_summary_paragraph_strips_bom_and_header_directives`, `test_summarize_bom_header_yields_first_prose_sentence`, `test_summarize_header_only_is_honest_unknown`, `test_first_prose_line_wins_even_without_blank_line`. Crucible probe `.scratch/crux2_bom_probe.py`: U+FEFF + `#type:`/`#context:`/`#internal:` + prose -> `('Extrudes polygons into 3D.', 'library')`; header-only -> `(None, 'unknown')`; prose starting `#1 rule:` is kept (the directive regex `^#[A-Za-z][\w-]*:` needs a letter). |
| 4 | 200 selected paths of 5 types: at most 5 library lookups, compose at most CAP, flash total 200 | **pass** - NIT | M11 (CAP slice removed) -> `test_worker_caps_before_facts_memoizes_lookup_and_flashes_full_total` FAILED. M12 (memo never served) -> that test + `test_summarize_memoizes_default_path_one_lookup_per_key` FAILED (2 failed, 29 passed). Nit N1: the memo also caches the honest unknown (`.scratch/crux2_memo_probe.py`: `MEMO_PINS_OUTAGE True`). The live 200-node hold is IDFIX row 6 (UNKNOWN). |
| 5 | except_ratchet.py exits 0 on the tip and every identify file stays at 0 silent | **pass** | idfix clone: `broad_total=1379 silent_total=995 OK` rc 0; per-file silent 0 (row 4 of HARDFIX, same script); baseline byte-identical hardfix..idfix. M5 (a swallow in compose.py) -> ratchet `compose.py: 0 -> 1` rc 1 + `test_except_ratchet_passes_on_clean_tree` FAILED. |
| 6 | live G2/G5/G6 re-run in Houdini 22.0.400 | **UNKNOWN** | gui_probe; no GUI for this seat. Headless halves proven above (G6 disk round trip PASS; G2 BOM and G5 cap+memo pinned by tests + mutations). The seat closes G1-G6 by computer use after the wave. |

**Screen vs CRUX2:** no SCREEN line for IDFIX in the brief - n/a.

---

## The seat's defects (packet 13:14-13:25 + defect 7 + the gate evidence)

| Defect | Closure | Crucible anchor |
|---|---|---|
| 1 salience.py IndentationError | closed by HARDFIX | compileall rc 0 both tips; M1 re-breaks it: ratchet `UNPARSED` rc 1, `tests/test_identify_salience.py` collection ERROR (rc 2). Nit N3 on the compile guard. |
| 2 keyframes guard deleted | closed by HARDFIX | facts.py `_parm_is_expression` keeps `if parm.keyframes(): return True`; M2 bites; hython `Distance 0.07` / `is_expression False`. |
| 3 `hit = None` deleted | closed by HARDFIX | library.py summarize except branch keeps `hit = None` (survives IDFIX's memo rewrite); M3 bites. |
| 4 `_JOBS.slot.release()` deleted | closed by HARDFIX | salience.py:214 keeps the release; M4 bites. |
| 5 root-level `logging.debug` | closed by HARDFIX - NIT | one `_log` per file; grep 0 hits; M6 bites the grep only (N2). |
| 6 ratchet fail-open + reversed `_rule` | closed by HARDFIX - NIT | `RatchetUnparsable` at scripts/except_ratchet.py:77, `UNPARSED` + exit 1 in both modes (:202-208); `_rule` now `count may shrink, never grow` (:215 and the fixture). C1 bites; C3 (wording reversed) survives - documentation only (N4). |
| 7 self-resetting positive control (CRUX H-M3) | closed by HARDFIX | `.scratch/crux2_hm3_replay.py` on the hardfix clone: planted swallow -> ratchet rc 1; one run of `tests/test_except_ratchet.py` -> tracked baseline bytes unchanged, synapse_panel.py bytes unchanged, ratchet STILL rc 1; restored -> rc 0, git clean. M8 (control pointed at the tracked baseline) -> the autouse guard ERRORs the test. |
| G6 save kept every block (seat, merged master) | closed by IDFIX (headless); live UNKNOWN | row 2 above: show() installs the callback; raw disk 0, reload 0. |
| G2 `#type: node` bubble (BOM) | closed by IDFIX; live UNKNOWN | row 3 above. |
| G5 ~40 s before the first bubble (200 composes, 211 ms lookups) | closed by IDFIX (cap before facts + memo); live hold UNKNOWN | row 4 above. |
| F4 standalone sentinel in artist text | out of scope by the brief | for_ruling item 3 in HARDFIX's receipt; IDFIX finding 3. |

---

## Closure of every BP11-CRUX finding

| # | CRUX finding | Closure |
|---|---|---|
| 1 | FIXFWD row 2: verifier CI-red on LF runners (network clone hashed as CRLF checkout) | **open** on this branch line - repaired on `bp11/fixfwd2` f29d81fd (CRUX FIXFWD2 rows 1-4 pass); merge `bp11/fixfwd2`, never `bp11/fixfwd`. |
| 2 | FIXFWD row 3: NOTICE hashes are CRLF checkout hashes, false provenance sentence | **open** here - same route as 1. |
| 3 | FIXFWD receipt says `green` with four `pass` rows (BROKEN on the receipt) | **open** - annotating a predecessor receipt is a human act (CRUX FIXFWD2 nit c). |
| 4 | FIXFWD2 nit a: mutation/CRLF tests rewrite NOTICE.md in text mode, checkout dirty on Windows | **open** - not in HARDFIX/IDFIX touches; `newline="\n"` fix still due on the fixfwd2 line. |
| 5 | FIXFWD2 nit b: F2-M2 survived (checkout-vs-blob under eol=lf) | **open** - fixfwd2 line. |
| 6 | FIXFWD2 nit c: for_ruling on the predecessor receipt | **open** - human. |
| 7 | IDCORE row 3 nit: a standalone `~ identify ~` line in artist text reads as an Identify block (F4) | **for_ruling** item 3; IDFIX finding 3 restates it as out of scope. Still present on the tip (apply.py `_block_start`). |
| 8 | IDCORE row 7 nit: rule 1 no-network clause and rule 7 unpinned by a tracked test | **for_ruling** item 4. |
| 9 | IDSURF nit a: R9-M2 survived - the Identify button is not token-pinned | **for_ruling** item 5 + spawn BP12-IDPANEL-LOG. |
| 10 | IDSURF nit b: three silent `except Exception: pass` on the zero-token path (synapse_panel.py:3346/3369/3373) | **for_ruling** item 6 + spawn. On the idfix tip they sit at 3346/3374/3378 (IDFIX shifted lines); count unchanged, ratchet OK. |
| 11 | IDSURF rows 5-8: G1/G2/G3/G5 UNKNOWN | **for_ruling** item 7; **UNKNOWN** here too. |
| 12 | SALIENCE row 4 nit: LOP key hashes reproduce only through the full producer (HoudiniCreatorNode id) | **for_ruling** item 8. |
| 13 | SALIENCE row 5 nit: the grader writes the tracked `harness/jev/ledger/bp11.salience.jsonl` on every run | **for_ruling** item 8. |
| 14 | SALIENCE: live Jev agreement UNKNOWN (no billed run); G4 UNKNOWN | **UNKNOWN** - not in HARDFIX's receipt (outside its predicate scope); the seat's computer-use pass and a billed run close them. |
| 15 | HARDEN row 1 / H-M2: the ci.yml OS matrix is unpinned by a tracked test | **for_ruling** item 1. ci.yml unchanged harden..idfix. |
| 16 | HARDEN row 2 / H-M3: positive control re-baselines the tracked fixture, never tests check-mode exit 1, leaves synapse_panel.py + baseline CRLF-rewritten | **closed by HARDFIX** - `tests/test_except_ratchet.py` rewritten on tmp roots with an autouse unchanged-bytes guard and `newline="\n"`; crucible replay above (ratchet rc 1 survives a test run; both files byte-unchanged); M8 bites. |
| 17 | HARDEN row 3 (i): salience.py IndentationError | **closed by HARDFIX** - defect 1 above. |
| 18 | HARDEN row 3 (ii): library.summarize UnboundLocalError on a raising lookup | **closed by HARDFIX** - defect 3 above. |
| 19 | HARDEN row 3 (iii): `_parm_is_expression` True for every literal parm (`(expr)` everywhere) | **closed by HARDFIX** - defect 2 above, live-confirmed. |
| 20 | HARDEN row 3 (iv): run_shadow slot leak | **closed by HARDFIX** - defect 4 above. |
| 21 | HARDEN row 3: four identify files edited outside the leg's touches | **closed by HARDFIX** - the four files are in HARDFIX's touches (bus claim 18d98ec5); diff vs bp11/salience is additive-only (12 bare-pass removals, 0 other). |
| 22 | HARDEN receipt called the regressions "logging added to import guards" | **closed by HARDFIX** - receipt findings 1-7 name each defect with an anchor; `harden_rows_restated` restates rows 2-3 as BROKEN in substance. |
| 23 | HARDEN row 5: Windows CI green on GitHub UNKNOWN | **for_ruling** item 2; crucible adds the Windows 3.11 analog (288 passed, 4 xfailed, 1 xpassed, 0 failed). Push and the GitHub run stay Joe's word: **UNKNOWN**. |
| 24 | Cross-leg: R4-M1 (BeforeSave strip disabled) bites live only, all 12 apply tests green | **closed by IDFIX** - `test_before_save_strips_every_block_and_after_save_restores`; C2 bites under pytest. The event wiring itself is still live-only (N5). |
| 25 | Cross-leg: rule 1 no-network (R1-M2), rule 7 (R7-M1b), rule 9 token clause (R9-M2) pinned by grep only | **for_ruling** items 4 and 5. |
| 26 | Cross-leg: ADR refusal list unpinned (F1-M1) | **open** - fixfwd line. |
| 27 | Cross-leg: CI matrix unpinned (H-M2) | **for_ruling** item 1 (same as 15). |
| 28 | Cross-leg: three tests rewrite tracked files in text mode | HARDEN's control **closed by HARDFIX** (16); FIXFWD2's **open** (4); the salience grader **for_ruling** item 8 (13). |
| 29 | Cross-leg: gui rows UNKNOWN, seat closes G1-G6 by computer use | **UNKNOWN**, unchanged. |
| 30 | CRUX packet gaps (informational) | n/a - fed forward; this wave's gaps are listed at the end. |

---

## Nits (crucible findings outside the rows; none BROKEN-class)

- **N1 memo caches the honest unknown.** `library.summarize` stores `(None, "unknown")` in `_SUMMARY_CACHE`
  for the life of the process (`.scratch/crux2_memo_probe.py`: `help_summary` raises once, then returns a row;
  the second call still answers `(None, 'unknown')`, underlying calls 1). A library outage on the first click
  pins `- not in library` on that type until Houdini restarts. The key `(help_url, hda_help)` also ignores the
  corpus root, and `tests/test_identify_library.py:130-133` (`test_summarize_end_to_end_against_corpus`) calls
  the memoized path without clearing the cache afterwards; no tracked test collides today.
- **N2 root-logging clause is grep-pinned.** M6 puts a root `logging.debug(` back at apply.py:116 and 23
  tracked tests stay green; only HARDFIX row 3's grep catches it.
- **N3 the compile guard cannot report the defect it was written for.** `tests/test_identify_hardfix.py:21`
  imports `salience` at module level, so with salience.py unparsable (M1) the whole module errors at collection
  (`ERROR tests/test_identify_hardfix.py`, pytest rc 4 on the node id); the ratchet's `UNPARSED` line and the
  salience test-file collection error are the working detectors.
- **N4 `_rule` wording is unpinned.** C3 reverses it to HARDEN's text and all 6 ratchet tests pass. Documentation only.
- **N5 the save-event wiring is live-only.** C5 makes `_save_dispatch` skip `before_save()` on BeforeSave and
  16 tests stay green; the crucible's hython G6 is the only proof. A fake-event dispatch test would pin it.
- **N6 the persistence xfails carry no Python condition.** On this box they XPASS on 3.14 and XFAIL on 3.11;
  the packet's CI dry run (CI env, keys and Houdini vars dropped) had them failing on 3.14 too. `strict=False`
  is the right setting for an environment-dependent failure, and it also mutes the Windows signal on every
  Python until BP12 deletes the marker. Disclosed in the reason text.
- **N7 summary line in a scratch clone.** hython resolved PolyBevel's What line to `PolyBevel - not in library`
  in the clone (no `.synapse/sidefx_library.json` there; the main tree's points `root` at `G:/HOUDINI22/_CORPUS`
  and `SYNAPSE_SIDEFX_CORPUS_ROOT` alone did not resolve it). Same as CRUX's IDCORE row 5 note; pre-existing
  IDCORE behaviour, not this leg's, and the G6 verdict does not depend on it.

---

## gui_probe rows (UNKNOWN, never pass)

IDFIX row 6 (live G2/G5/G6), IDSURF rows 5-8 (G1/G2/G3/G5), SALIENCE G4, and HARDEN row 5 (GitHub Windows CI)
are UNKNOWN in this document. The headless halves are recorded above; the seat closes G1-G6 by computer use
after the wave (IDENTIFY_BLUEPRINT sec. 7).

## Packet gaps for the next wave

The packet gave the six defects, the seeds, HARDEN's identify diff, the gate evidence and the IDFIX seeds -
enough for every seed. It lacked: the IDFIX receipt and product diff (read via `git show` / `git diff`); the
HARDFIX test files (`tests/test_identify_hardfix.py`, `tests/test_except_ratchet.py`, read in the clone); the
xfail-marker diff and each marker's line; apply.py's `install_save_callbacks` / `before_save` / `after_save` /
`_save_dispatch` bodies (apply.py:207-249) and `_reset_state`; `read_selection_facts` signature (facts.py:223);
the library config resolution (`sidefx_library.py:21-22`); and which alternate Pythons the box has (`py -0p`:
3.14, 3.13, 3.12, 3.11).
