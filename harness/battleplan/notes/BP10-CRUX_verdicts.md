# BP10-CRUX — verdicts on the four BP10 builder legs

2026-09-21 · referee seat (Fable 5.1) · branch `bp10/crux` · read-only on product files.

Every row below was re-run by the crucible in a **fresh `git clone --shared` of the leg branch** under the
session scratchpad (scaffold at `--revision 357bf1e7`, the commit that actually carries the scaffold
product; see finding X1). Anchors are the crucible's own. Builder `proved_it_bites` claims were not
trusted: the mutation record is `harness/battleplan/notes/BP10-CRUX_mutations.json` (16 mutations,
13 right-reason bites, 1 reverse-specific, 1 crash-red, 1 survived).

Tooling: hython `C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe` (22.0.400,
`hou.applicationVersionString()` printed by the probes), system Python 3.14.2, git 2.55.0.
Import binding was proven per clone before any test was trusted (`help_archive.__file__`,
`guides.__file__`, `scope_weights.__file__` all resolved into the scratch tree; `synapse` resolves to
the main tree under bare python and to the clone under pytest's `pythonpath=["python"]`).

**How verdicts are assigned (stated so the asymmetry below is principled):**

- **SOUND** — every row passes on re-run, no UNKNOWN.
- **SOUND-WITH-NITS** — any UNKNOWN row, or a row that fails as written but the receipt itself discloses the
  gap in that row's evidence / `for_ruling` and no owned or product surface claims otherwise.
- **BROKEN** — a builder-marked `pass` that is false on re-run and is either undisclosed in the receipt or lands
  a false claim on an owned/product surface (README, a live guard, CI). Nothing merges on a BROKEN.

Row numbering follows the receipt order; the JEV SCREEN ledger indexes the same rows 0-based (`acc_0` = row 1).

---

## BP10-SCAFFOLD — **BROKEN** (already on master via 357bf1e7 → fix-forward, not a merge gate)

Checkout: `357bf1e7` (product `5ab7ee9d`). The branch ref `bp10/scaffold` points at `845da18e`, the
*pre*-scaffold commit (`git worktree list` shows the scaffold worktree at 845da18e too); the product is
reachable only through master and the three sibling legs (`git branch --contains 5ab7ee9d`).

| # | Predicate (short) | CRUX verdict | Crucible anchor |
|---|---|---|---|
| 1 | LICENSE sha256 == upstream @29b6695b | **pass** | `git show 5ab7ee9d:python/synapse/_vendor/fxhoudinimcp/LICENSE \| sha256sum` = `79a2891b…5918` (1083 B) == upstream clone `git show 29b6695b:LICENSE` = `79a2891b…5918` (1083 B). Blob id `0d52230e` identical on all four leg tips and master. NIT: receipt says 1104 bytes — that is the CRLF working-tree size (21 lines), not the blob. |
| 2 | 31 guides present, each sha256 == upstream | **pass** (content) · NOTICE table wrong | Blob-vs-blob: 31/31 identical (`diff` of sorted sha lists, scratch `vendored_guides.sha256` vs `upstream_guides.sha256`, empty). **But NOTICE.md's 31 published hashes match upstream 0/31** — they are sha256 of the CRLF working-tree files (`core.autocrlf=true`): proven on anim.md, sha256(blob with LF→CRLF) = `57514d24…` = NOTICE value, while the blob/upstream is `57fae325…`. Anyone verifying NOTICE against upstream raw files gets 31 mismatches. Receipt's "per upstream manifest" is not a thing — the hashes were self-computed. |
| 3 | questions.json parses; harvest/rerank/bench have edge/state_fields/questions/policy; six pre-existing guards byte-identical | **FAIL** | Parses; all three new guards carry the four fields (CRUX-S3). Pre-existing guards at 845da18e: route, screen, drift, release, shape, team (six; the receipt's list names "edge", which is a *field*, not a guard). Object-identical **5 of 6**: `guards.screen` changed — the em dash U+2014 in the `claims_unknown` instruction became `\u00e2\u20ac\u201d` ("â€”" mojibake), `git diff 845da18e 5ab7ee9d -- harness/jev/questions.json` hunk `@@ -113`. It is on master today (decoded `master:harness/jev/questions.json`, offset 1067 of the screen guard) and `harness/jev/jev_screen.py:35-38` sends that instruction text to Jev on every SCREEN call. The other five are re-wrapped (not byte-identical either), content unchanged. |
| 4 | `pytest harness/jev/tests` green on system Python; dir in pyproject testpaths and ci.yml | **pass** (evidence false) | Scratch `s`: 55 passed. `pyproject.toml:111`, `.github/workflows/ci.yml:110`. The receipt's evidence — "tests directory does not exist yet" — is false: `git ls-tree 845da18e -- harness/jev/tests` lists 7 files; the leg asserted green without running them. |
| 5 | ADR-0001 contains all eight refusal bullets | **FAIL** | ADR `## Refused Sites` has 4 numbered bullets (quarantine, licence, benchmark check, stamp). Blueprint `JEV_HARVEST_BLUEPRINT.md` "Risks and refusals" lists 8 (probe passed, which model runs anything, instant tier, run_on_main closure are absent). The receipt's own evidence says "Four of eight" and marks pass. Reverse mutation S-M3 turns CRUX-S5 green only when the four are added. |
| 6 | tool_map keys cover every backticked tool name (count line = grep count) | **pass** · NIT | 40 backticked tokens are upstream tool names (upstream `python/fxhoudinimcp/tools/*.py` @29b6695b, decorated defs + `name=`); 40/40 are keys (CRUX-S6; mutation S-M4 bites). Keys = 336 = every token matching the `_comment` regex; 296 of them are help-page paths / node names / parms, not tools. There is **no count line** in tool_map.json to equal a grep count. |

**Mutations (right-reason bites):** S-M1 LICENSE byte → CRUX-S1; S-M2 drop `guards.bench.policy` → CRUX-S3;
S-M4 drop `capture_screenshot` → CRUX-S6; S-M3 reverse (ADR +4 bullets) → CRUX-S5 SPECIFIC. No tracked
test pins any scaffold acceptance row; only the crucible's checks do (see BENCH B-M5: the bench test that
"reads questions.json" survives deleting `guards.bench.policy`).

**Fix list (one leg, BP10-SCAFFOLD-FIX):** restore U+2014 in `guards.screen` (write the file as UTF-8 without a
cp1252 round-trip); add the 4 missing refusals to ADR-0001; regenerate NOTICE.md hashes from git blobs
(LF) and say so; correct the receipt prose (1083 B; tests dir pre-existed).

**Screen vs CRUX:** SCREEN = FLAG rows [4, 5] (0-based → rows 5, 6), plus `acc_3` does_not_support 0.53.
CRUX: row 5 FAIL (**agree**), row 6 pass-with-NIT (**disagree** — coverage holds, the map is mis-scoped),
row 4 pass on re-run (SCREEN was right that the *evidence* did not support it; the predicate itself holds),
row 3 FAIL (**SCREEN missed it** — `acc_2` partial 0.64; the mojibake needed a diff, not a read).
Agreement: **PARTIAL** — 1 of 2 flagged rows confirmed, 1 flagged row cleared, 1 unflagged row failed.

---

## BP10-CORPUS — **SOUND-WITH-NITS**

Checkout: `b32a877c` (product `fa00652a`, base 357bf1e7).

| # | Predicate (short) | CRUX verdict | Crucible anchor |
|---|---|---|---|
| 1 | G0 pytest test_help_archive + test_scope_weights green | **pass** | 26 passed (scratch `c`, python 3.14.2); binding: `help_archive.__file__` → scratch `c/rag/ingest/help_archive.py`. |
| 2 | G1 `hython help_archive.py --build`: scopes ≥ 50, pages ≥ 11000, zero empty source | **pass** | Rebuilt on 22.0.400 in 7 s wall (`g1_build.log` 14:42:21 → 14:42:28): STAMP scope_count 55, page_count 11460, chunk_count 36168, quarantine_count 106 — identical to the committed stamp except `ingest_ts` (`git diff` one line). Independent scan of the 55 generated jsonl files: 36168 chunks, 0 empty `source`, 0 empty `text`, 55 scopes, 11436 distinct page keys (24 pages yield no chunk), `licence=sidefx-eula` on all. |
| 3 | G3 25 probes 0/25 confident-wrong **with h22_prose first and H21 fallback** | **fail** (as written; disclosed) | `tests/test_knowledge_retrieval_repair.py` → 24 passed (the "25" has no producer; the suite collects 24). The condition is not exercised: on bp10/corpus `git grep -l -E 'scope_weights\|h22_prose\|corpus/guides' -- python/synapse` → 0 files; `KnowledgeRouter` reads `documentation/_metadata/semantic_index.json` (`knowledge.py:439`) and `corpus/h22_nodes.json` only. The probe suite cannot regress from a corpus it never sees. The receipt discloses this in the same row ("NOT wired … staged for BP10-GUIDES") and asks a ruling — hence NITS, not BROKEN. |
| 4 | G4 phantom_gate_status CURRENT on 22.0.400, STALE after hand-edit | **pass** | `hython rag/ingest/help_archive.py --status` → `CURRENT` (stamp 22.0.400 / live 22.0.400); copy with build edited to 22.0.368 via `--rag-root` → `STALE`. Mutation C-M2 (always CURRENT) reddens both the unit test and this live check. |
| 5 | rerank_shadow.md before+after tables, judged/unjudged header; ledger row per call or fallback | **pass** · NIT | `harness/notes/harvest/rerank_shadow.md:3` "Verdict header: unjudged.", `## Before` line 10, `## After` line 26; `harness/jev/ledger/bp10.rerank.jsonl` 3 fallback rows (before, before, after), reason `SYNAPSE_JEV=off`. NIT: line 8 blames a missing `TYPESAFE_API_KEY`, the ledger says `SYNAPSE_JEV=off`, and the receipt says the key IS present — one sentence, three stories. |
| 6 | no rag/corpus/h22_prose/*.jsonl tracked | **pass** | `git ls-files rag/corpus/h22_prose rag/quarantine/prose` → `STAMP.json`, `README.md` only; `.gitignore` +245 `rag/corpus/h22_prose/*.jsonl` (added in 5ab7ee9d). Same on guides and bench tips. |

**Mutations:** C-M1 gate never quarantines → `test_phantom_hits_catches_absent_type` (`assert [] == ['sop/frobnicator']`);
C-M2 status always CURRENT → unit test + live STALE check; C-M3 h21 base 110 → `test_scope_weights.py` (`assert 90 > 110`).

**Screen vs CRUX:** SCREEN = FLAG rows [2] (0-based → row 3, does_not_support 0.69). CRUX row 3 = fail-as-written.
Agreement: **AGREE**.

---

## BP10-GUIDES — **BROKEN** (one README line; everything else sound)

Checkout: `b84bf8e5` (product `02028f63`, base 357bf1e7).

| # | Predicate (short) | CRUX verdict | Crucible anchor |
|---|---|---|---|
| 1 | G2 every guide in exactly one of corpus/quarantine; quarantined guides list failing tokens | **pass** · NIT | `hython rag/ingest/guides.py --build` → `guides: 31 \| corpus 26 (115 chunks) \| quarantine 5 \| tool rewrites 113 \| drops 25`; quarantined assets, heightfields, io, model, render; union == the 31 vendored names, disjoint; failing tokens `rockgenerator`, `thermalerodabilitymask`, `bgeo.sc`, `foo`, `soho`. Rebuild is content-identical to the committed tree (`git diff --ignore-cr-at-eol --stat` empty). NIT: the writer emits CRLF on Windows, so every build leaves 32 line-ending-dirty files (`git status` M on all corpus/quarantine outputs + ingest_report.json). |
| 2 | G0 pytest test_guides_ingest green; broken fixture quarantined | **pass** | 9 passed; `test_gate_quarantines_planted_fake_node`, `test_fixtures_partition_clean_and_broken` green; mutation G-M2 bites. |
| 3 | G3 0/25 confident-wrong **with the guide scope active** | **fail** (as written; **undisclosed**) | 24 passed. `scope_weights.is_active('guide')` is True, but `git grep -l scope_weights bp10/guides` → `docs/decisions/ADR-0001…`, `harness/jev/jev_grade.py`, the receipt, `tests/test_scope_weights.py` — nothing under `python/synapse`. Nothing in the runtime reads `rag/corpus/guides` (0 hits for `corpus/guides`/`h22_prose`/`scope_weights` under `python/synapse`). The probe suite ran against a retrieval path the guide scope never enters. The receipt does not say so. |
| 4 | every chunk carries origin + licence; one-line query lists all | **pass** | 115 chunks; 115 `origin` prefixed `fxhoudinimcp@29b6695b:`; 115 `licence=mit`; 0 missing either field; fields `build, chunk_index, content_sha, id, licence, origin, page, scope, source, text, title`. |
| 5 | triage.md exists, judged/unjudged header; no quarantine→corpus move (git diff proves) | **pass** · NIT | `harness/notes/harvest/triage.md` "Verdict header: judged."; `git diff --name-status 357bf1e7 02028f63 -- rag/` R-lines 0. NIT: that git proof is vacuous by construction (both directories are new in one commit); the load-bearing proof is CRUX-G2 — the dry-run/rebuild reproduces the same 5-name quarantine, and mutation G-M4 (a planted fake node in anim.md) moves anim into it. |
| 6 | README diff exactly one added line | **pass** · **the line is the BROKEN item** | `git diff --numstat 357bf1e7 02028f63 -- README.md` → `1 0`. The line (README.md:121) sits under `## What's ready` (README.md:114): "**How nodes go together:** `rag/corpus/guides` — 31 workflow guides … gate-checked against 22.0.400." No runtime path serves that directory (row 3 anchors), so the public README now lists as *ready* a knowledge source the product does not consult. Owned surface, false readiness claim → BROKEN per the rule above. Fix is one line: move it to a staged/"not yet served" statement, or land the serving wiring first. |

**Mutations (right-reason bites):** G-M2 licence=None → `test_chunks_carry_name_title_origin_licence`; G-M3 guide inactive →
`test_guide_slot_active_after_bp10_guides` (+ ranked_scopes default); G-M4 planted `frobnicator_zzz` in vendored anim.md → CRUX-G2
dry-run quarantine set gains `anim`. G-M1 (resolve() → True) reddened by `TypeError: cannot unpack non-iterable bool` — a crash-red,
recorded as *not* right-reason and not counted.

**Screen vs CRUX:** SCREEN = REFEREE, weak rows [2] (0-based → row 3, does_not_support 0.57), self_contradiction 0.57, crux_need 0.87.
CRUX row 3 = fail-as-written (**agree**); CRUX adds row 6's README overclaim, which SCREEN rated `supports` 1.0 because it judged
the numstat, not the truth of the added line. Agreement: **PARTIAL** — flagged row confirmed; the BROKEN item is CRUX-only.

---

## BP10-BENCH — **SOUND-WITH-NITS**

Checkout: `cededc17` (product `cb1cd0de`, base 357bf1e7).

| # | Predicate (short) | CRUX verdict | Crucible anchor |
|---|---|---|---|
| 1 | prompts.jsonl 24 rows, 4 per domain, non-empty check | **pass** | 24 rows; SOP/Pyro/Vellum/Solaris-LOP/Copernicus/VEX = 4 each; 0 empty checks; kinds nodes 24 / cook 8 / parm 1 / attrib 3. Live probe under hython 22.0.400 over `hou.nodeTypeCategories()`: all 45 node specs exist (`missing=[]`). Mutation B-M4 bites. |
| 2 | --leak-check ran over 24; ledger committed; none ≥ 0.50 remain | **pass** | Committed `harness/jev/ledger/bp10.leak.jsonl`: 50 rows = 24 + 24 ok + 2 summaries; run 1 max noul 0.96, 8 prompts ≥ 0.50 (= the summary's `leaked` list); run 2 max 0.26, 0 ≥ 0.50. **CRUX live re-run** (`python harness/jev/jev_bench.py --leak-check` in the scratch clone, 24 real `jev-latest` calls, 0 fallback): leaked [], max noul 0.27 — reproduces. |
| 3 | one prompt per arm on the empty scene → two ledger rows with provider tokens + verify verdict | **UNKNOWN** | `harness/notes/outside_in/results.jsonl` holds exactly 2 rows, both `UNKNOWN` with reasons (port 9999 held by a server the benchmark did not start; no fx venv), token fields `null` — nothing fabricated. CRUX did not attempt the live turn: the SessionStart hook reports the artist's bridge connected on 9999 and isolation forbids touching it; `pip install fxhoudinimcp` into a venv is spend/network held for Joe (receipt R2). Stays UNKNOWN. |
| 4 | verify.py runs in a third hython and reads no arm text | **pass** | `test_verify_reads_no_arm_text_code_inspection` green (AST: `verify imports arms` assertion, mutation B-M1 bites). Live: builder hython → `crux_scene.hip` (`/obj/geo1/sphere1`) → separate hython `verify.py --scene … --check @chk_sphere.json` → `{"verdict": "PASS", …}`; `@chk_box.json` → `{"verdict": "FAIL", "reason": "nodes:box failed"}`. Mutation B-M3 (ok=True) flips the live box check to PASS and reddens the unit test. |
| 5 | run.py refuses --scene large without --confirm-spend and prints an estimate | **pass** | `python harness/outside_in/run.py --scene large --runs 3` → exit 2, "REFUSED … 144 agent turns (= 24 prompts x 3 runs x 2 arms) … per-turn token median: UNKNOWN (no run recorded in turn_stats.json yet)"; `spend_gate` (`run.py:97`) is consulted at `run.py:246` before any arm starts. Mutation B-M2 bites. |
| 6 | G5 not executed (≤ 2 benchmark rows) | **pass** | 2 rows in results.jsonl. |

**Mutations (right-reason bites):** B-M1, B-M2, B-M3, B-M4 (above). **Survived:** B-M5 — deleting `guards.bench.policy`
leaves `test_bench_spec_reads_questions_json` green; no test on any bp10 branch pins the scaffold's guard policy blocks.

**Screen vs CRUX:** SCREEN = FLAG rows [2, 5] (0-based → rows 3, 6) with a *code* count-mismatch ("row 2 reports 2 but the
mission expects 24"; same for row 5) plus jev weak rows [2, 3], crux_need 0.98. CRUX: row 3 UNKNOWN (**agree** it is not a pass;
`acc_2` = claims_unknown 1.0 was the honest read), row 6 pass (**disagree** — the "2" is the row count the predicate demands, the
24 is the prompt count; the code matcher paired the wrong numbers), row 4 pass. Agreement: **PARTIAL**.

---

## Licence audit row (T4)

| Check | Result | Anchor |
|---|---|---|
| No SideFX help text tracked by git | **pass** · 1 NIT | `git ls-files rag/corpus/h22_prose rag/quarantine/prose` on bp10/corpus, bp10/guides, bp10/bench → `STAMP.json` + `README.md` only; the 55 generated `*.jsonl` (36168 EULA chunks) and the 106 quarantine chunks are untracked, `.gitignore` +245. Fixtures `tests/fixtures/help/pages/*.txt` (10 files, 14 KB) are hand-authored wiki-markup samples (`frobnicator`, "Links page", "Bold and bullets"); one sentence in `plain_prose.txt` — "nodes connected together that describe the steps to accomplish a task." — appears verbatim in the live corpus page `basics/intro`. De minimis, but it is a SideFX sentence in git: paraphrase it. `rag/corpus/h22_nodes.json` (pre-existing, spec's open question) not re-litigated here. |
| Vendored LICENSE byte-identical to upstream | **pass** | sha256 `79a2891ba34d73cb07da165714464f3bb6a6c6a254ea7ad1bac2cf3f7aae5918`, 1083 bytes, both sides (`git show 5ab7ee9d:python/synapse/_vendor/fxhoudinimcp/LICENSE` vs upstream clone `git show 29b6695b:LICENSE`); blob `0d52230e` unchanged on every bp10 tip and master. |
| 31 vendored guides byte-identical to upstream | **pass** | 31/31 blob sha256 equal (scratch `vendored_guides.sha256` vs `upstream_guides.sha256`). NOTICE.md's published hashes are CRLF hashes (SCAFFOLD row 2) — the manifest, not the files, is wrong. |

---

## Cross-leg findings

- **X1 — the scaffold branch ref does not carry the scaffold.** `bp10/scaffold` = 845da18e; the product 5ab7ee9d/357bf1e7 is already in master (v5.79.0 was cut on top). The SCAFFOLD BROKEN is therefore a fix-forward on master, not a merge decision.
- **X2 — neither new corpus is served.** Nothing under `python/synapse` imports `rag/retrieval/scope_weights.py` or reads `rag/corpus/h22_prose` / `rag/corpus/guides` on any bp10 tip. Both G3 rows are vacuous; CORPUS disclosed it, GUIDES did not and published the README line. HARVEST_SPEC's "Corpus done" (h22 prose first, H21 fallback) is not met by M1+M2 as shipped.
- **X3 — the "25-probe set" has no producer.** The collected suite is 24 assertions over PREFLIGHT(5)+REGRESSION_TOPICS(4). Both legs disclosed it; the spec and both mission briefs still say 25.
- **X4 — CRLF is the wave's recurring gremlin.** NOTICE hashes (SCAFFOLD), 1104-byte LICENSE claim (SCAFFOLD), 32 dirty files after every guides build, STAMP.json "CRLF will be replaced" warnings. Writers should open with `newline="\n"`; hashes should be taken from git blobs.
- **X5 — guard policy blocks are unpinned.** B-M5 survived: no test on any bp10 branch fails if `guards.bench.policy` (or harvest/rerank) disappears.

## Merge words (Joe's)

- BP10-CORPUS: SOUND-WITH-NITS — mergeable; the rerank header sentence and the STAMP newline are cosmetic.
- BP10-BENCH: SOUND-WITH-NITS — mergeable; G5 stays held (R2).
- BP10-GUIDES: BROKEN on README.md:121 only — one-line fix (or the serving wiring) then re-verdict; the corpus/quarantine/provenance work is sound.
- BP10-SCAFFOLD: BROKEN, already on master — a fix-forward leg for the four items in its fix list.
