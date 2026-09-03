# BP3-CRUX — Verdicts for wave BP3

**Referee:** BP3-CRUX (adversarial crucible, branch `bp3/crux`) · 2026-09-03
**Method:** every builder receipt's acceptance array independently re-run in a **fresh `git clone --shared` scratch checkout** of the leg branch (never the builder's worktree, never the main tree); probe suite re-run by the crucible on pinned hython 22.0.400 with `HOUDINI_USER_PREF_DIR` set to the OneDrive prefs dir; **10 self-authored mutations** (ledger: `BP3-CRUX_mutations.json`) against crux-green baselines. Every verdict row below carries the crucible's own anchor, never the builder's. gui_required acceptance is UNKNOWN — unobtainable headless, said plainly.
**Crucible probe artifacts (durable):** `harness/battleplan/notes/bp3_crux_probe_rerun/{stdout.txt,probe_results.json}` (binaries not committed, matching the disclosed public-autopush policy).

## Summary

| Leg | Verdict | chain_broken_at | Why not SOUND |
|---|---|---|---|
| BP3-RECON | **SOUND-WITH-NITS** | none | 2 cosmetic doc nits (multiplicity ×5→×3; drop.json labeled tracked while untracked) |
| BP3-PROBE | **SOUND-WITH-NITS** | none | 1 gui_required acceptance UNKNOWN (constitutional ceiling) |
| BP3-CORPUS | **SOUND** | none | — (3/3 acceptance pass, 3/3 mutations bite, zero discrepancies) |
| BP3-STUBS | **SOUND** | none | — (3/3 acceptance pass, 3/3 mutations bite, zero discrepancies) |
| BP3-PANEL | **SOUND-WITH-NITS** | none | 1 gui_required acceptance UNKNOWN + 2 guard holes (pre-existing, spawns filed) |

No leg is BROKEN. **Every leg rides.** A green CRUX receipt is a PRECONDITION for Joe's merge words, never a substitute — these verdicts are for reading before merge words fire.

---

## BP3-RECON — SOUND-WITH-NITS

Scratch: clone of `bp3/recon` @ 1e5018d1 (product 062669fe). All 3 acceptance rows re-ran **pass** with crux anchors.

| Acceptance | Builder | Crux | Crux anchor |
|---|---|---|---|
| one row per blueprint V0 path, no row invented | pass | **pass** | Crux grep over the blueprint → 13 distinct repo-path tokens (2 sidefx.com URL fragments and the SS0.4-rejected pipeline file excluded, each with a reason); all 13 present in tables A/B with evidence cells. The 2 non-blueprint rows are mission-tasked (missions/BP3-RECON.json:9), not invented |
| bus finding with all 9 env fields | pass | **pass** | bus/bp3/bus.jsonl record n=18d1e389e49cfc98 read directly: all 9 fields present, values match receipt verbatim |
| prior-artifact list N-3/N-5/N-7/KAR-04/SOL-03 | pass | **pass** | Each cited file:line read by crux: cto-roadmap:103/105/107, doc-intel-wave2:34 (KAR-04), h22_probe_results.json:51 (SOL-03 block L50-64). F-1 numbering caveat accurate |

**T6 path truth table (crucible's own):** 75 path assertions tested — 51 expected-true → 50 true + 1 partial (drop.json, nit 2 below); 24 expected-false → 24 false. **Zero true/false inversions.**

**Environment re-verified first-hand:** hython 22.0.400 exists (4359472 B); OneDrive pref dir exists; pre-redirect `C:/Users/User/Documents/houdini22.0` absent; installed hython roster {21.0.773, 22.0.400, 22.0.413, 22.0.417, 22.0.429} matches recon T2 verbatim. **M-2 hazard upgraded from inferred to demonstrated:** 22.0.429's hython passes hytest's usability gate live (`import pytest, PySide6` → USABLE), so an unpinned lane WILL probe on 22.0.429, which has no symbol table (h22 table pins 22.0.400). The 22.0.400 pin re-probed: prints `22.0.400`.

**NITS (both verdict-neutral, one-line fixes on bp3/recon):**
1. BP3_RECON.md T3 by-symbol table says `paintinstances @ ~L238 (x5)` — actual count in verified_lop_solaris_knowledge_22.0.368.json is **3** (lines 238, 246, 438). Anchor right, multiplicity wrong.
2. The `USD 0.26.5 → harness/state/drop.json` row lists drop.json under "repo artifact(s)" but it is **untracked** (`git ls-files '*drop.json'` → 0; only drop.json.example tracked). Exists only on the live main tree; a fresh checkout will not contain it. Builder's own hedge ("drop.json is a human word") stands; wording should read "untracked/existence-gate".

---

## BP3-PROBE — SOUND-WITH-NITS

Scratch: clone of `bp3/probe` @ df15ec33 (product d6c6d9b3). 5 of 6 acceptance rows re-ran **pass**; 1 **UNKNOWN** (gui_required — constitutional ceiling: with any UNKNOWN acceptance, at best SOUND-WITH-NITS).

| Acceptance | Builder | Crux | Crux anchor |
|---|---|---|---|
| stdout first block P-0 with version line | pass | **pass** | Builder stdout line 5 `Houdini: 22.0.400` (crux grep); crux re-run prints the identical P-0 block, line 5 |
| 22 entries RAN\|BLOCKED + seconds + wall line | pass | **pass** | Crux python diff: builder JSON 22 ids {RAN:21, BLOCKED:1(P-6)}, all RAN rows carry seconds; wall at stdout:444 (6.5s) |
| review doc D1.1 + D2.1–D2.4 rows w/ verdict+anchor | pass | **pass** | Crux read of review sec.5 (lines 89–135): all 5 rows, every one anchored |
| B-6 usdc exists w/ size printed | pass | **pass** | stdout:336 "19.8 MB"; on-disk 19,756,921 B matches receipt + run_meta byte-for-byte; crux re-run exported 19,756,922 B (+1 B — embedded out-path length, benign) |
| SHA256 + bytes for 3 fixtures | pass | **pass** | **Crux recomputed full hashes:** ply be734a30…beb65/34000416 · glb 08e75e0a…eb00c9/959216 · png e6772fbd…821fdf/4213568 — full-hash identical to review sec.3 |
| B-2 handedness confirmed in viewer | UNKNOWN | **UNKNOWN** | gui_required, unobtainable headless — UNKNOWN per constitution. Crux re-run reproduces the same "not decidable numerically" line + matching numerics (raw y 95% = 0.61767578125) |

**T2 — crucible's own probe re-run (the core of this leg's audit):**
- Ran on pinned hython 22.0.400 (NOT 22.0.429, despite both installed), OneDrive pref dir, own `--out`. Exit 0, wall **5.6s** (builder 6.5s).
- **Status diff: IDENTICAL 22-id map.** 21 RAN / 1 BLOCKED, only P-6, same `AttributeError: 'OpNode' object has no attribute 'stage'` traceback. Zero per-id divergences (`only-builder: [] only-crux: []`).
- `git diff master..bp3/probe -- harness/probes/` → **empty** (confirmed twice: first-hand in the crux worktree AND in the scratch clone).
- **Both FAIL verdicts are real** (the crucible's key question): D2.2's 46,993 tris is doubly derived and internally consistent (GLB accessors 140979/3 = 46993 == Houdini unpack count); D2.4's all-zero RGB **recomputed by the crucible on its own re-run EXR** via OpenImageIO: RGB nonzero = 0 across 1280×720×3, alpha signature matching (avg 0.03513758 vs builder 0.03513613). Corroborating husk stats: Total Lights: 0, camera-name mismatch (rendercamera=/cameras/camera1 vs wl_cam).

**NITS / notes:**
1. B-2 handedness UNKNOWN (gui) — forces the verdict ceiling; honest on both sides.
2. Evidence binaries (b6 usdc / b7 EXR / hip) are deliberately unstaged (public-autopush policy, disclosed in run_meta + review sec.3); sizes match run_meta byte-for-byte so no tamper sign, but that evidence dies with the bp3-probe worktree.
3. Reproducibility: usdc/EXR byte sizes are out-dir-dependent (+1 B / +141 B in crux re-run) — anyone pinning exact sizes must pin the out path. Husk error summary counted 6 vs crux 5 for the identical no-camera failure class — verdict-neutral nondeterminism.

---

## BP3-CORPUS — SOUND

Scratch: clone of `bp3/corpus` @ d2529974 (product ac2b9440; parentage verified via merge-base). All 3 acceptance rows **pass**; 3/3 crux mutations **REDDENED**; zero discrepancies.

| Acceptance | Builder | Crux | Crux anchor |
|---|---|---|---|
| checker exit 0; every promotable row anchored | pass | **pass** | Crux run: exit 0, "8 promotable rows checked / PASS", stdout resolved `git:bp3/probe` (445 lines, 44 blocked); anchors :21/22/42/43/241/246/247/252 match receipt; tree clean so checked doc == committed doc |
| parm seed rows == P-5 rows (138==138) | pass | **pass** | **Crux's own method** (banner-bounded parse, lines 52..219, `^\s*\S+\s*\|` rows, 29 [Folder] headers excluded) → 138; `len(json rows)` → 138; count_caveat present in provenance |
| worksheet: 34 rows, each status + anchor/BLOCKED | pass | **pass** | Crux parse: 34 contiguous rows, zero lacking status or anchor; row 27 UNKNOWN-AFTER-PROBE (P-4 body verified empty at stdout:46-48), row 29 BLOCKED(P-6) (stdout:230 verified) |

**Mutations (all bite):** CORPUS-M1 strip-anchor → exit 1; CORPUS-M2 promote-BLOCKED via line **226** (crucible's own choice, not the builder's 230) → exit 1 with the correct BLOCKED-block reason; CORPUS-M3 tier-flip on artifact-less WL-EX-03 → exit 1 as a 9th promotable row failing the anchor gate. Green re-confirmed after every restore.

**Beyond the checker — semantic spot-audit of 2 promoted anchors:** stdout:246 really carries the `executionmode` menu labels ('Deferred','Immediate') inside the P-9 block; stdout:252 heads B-1 with `points: 500000 prims: 0` + DC-only schema, and `grep -c f_rest` over the whole stdout = 0. Both anchors **support** their promoted claims, not merely exist.

---

## BP3-STUBS — SOUND

Scratch: clone of `bp3/stubs` @ bb669478 (content 26e8313c). All 3 acceptance rows **pass**; 3/3 crux mutations **REDDENED**; zero discrepancies.

| Acceptance | Builder | Crux | Crux anchor |
|---|---|---|---|
| 3 candidates × {signature, preconditions, refusal, claim IDs, impl:none} | pass | **pass** | 15/15 items line-cited by crux (C1 L61-109, C2 L119-167, C3 L177-211+; PC ledger L41-46); RC-1/RC-2 present |
| lane diff apply-checks clean; authoring_domains.json unchanged | pass | **pass** | `apply --check` exit 0; diff vs master 0 lines; `cmp` identical; 301 bytes both sides; hunk @@ -1,4 +1,16 @@ adds "lanes" with ratified:false, domains line untouched |
| example validates vs schema + negative control | pass | **pass** | jsonschema 4.26.0: positive VALID; negative control raises exactly "'manifest_version' is a required property"; fixture shape confirmed (source=fixture, applied flags false, probes=[]) |

**Zero-hits grep (crucible's own, full tree):** all three tool names → **0 hits** in mcp_server.py, every mcp_tools_*.py, _tool_registry.py, and all of python/. Whole-tree hits live only in stub/mission text (blueprint, candidates doc, mission files, receipt) — the author_bp3.py:97 hit was inspected and is mission-prompt prose, not code.

**Mutations (all bite):** STUBS-M1 drop-required → invalid example now validates ⇒ negative control reddens (and the naive positive check stays green — proof the control is load-bearing); STUBS-M2 real function body → grep 0→1 hit (upgrades the builder's "structurally-satisfied" self-check to a demonstrated red); STUBS-M3 apply-the-diff → byte-identity reddens (301→1022 B, 22 diff lines). Restored clean after each.

**Confirmed for-ruling (builder's own, re-anchored by crux):** the lane diff's verbatim contract path `schemas/world_manifest.schema.json` (diff L19) points at a directory with **0 tracked files**; actual schema_home is `docs/intake/`. Must reconcile before the diff is ever applied. Blueprint L9 Sidecars line already reads docs/intake/ — the tension is inside the verbatim §3.2 lane text only.

---

## BP3-PANEL — SOUND-WITH-NITS

Scratch: clone of `bp3/panel` @ 38449ec7 (product 1276fed0). 3 of 4 acceptance rows **pass**; 1 **UNKNOWN** (gui_required ceiling). 4 crux mutations: 1 REDDENED, 3 SURVIVED-with-named-reddening-check (guard holes recorded below).

| Acceptance | Builder | Crux | Crux anchor |
|---|---|---|---|
| audit doc in audit shape w/ file:line instances | pass | **pass** | All 7 sections at crux-read line numbers; 37-row file table; 18 #Ds* classes; 7 file:line citations spot-checked and exact (e.g. agent_health.py:177 holds #00E676/#FFAB00/#FF3D71; performance_profiler.py:352 holds #2a2a2a) |
| diff scope: only qss.py product; synapse_panel.py untouched | pass | **pass** | Full-repo `diff --stat master..HEAD` = exactly 3 files (audit note, receipt, qss.py 5 ins/5 del); `diff -- synapse_panel.py` = **0 bytes**. Nothing rides along |
| tests green (123/25/0) | pass | **pass** | Crux checkout, PYTHONPATH bound and **verified** (synapse.__file__ + pytest rootdir = scratch): `123 passed, 25 skipped` — exact reproduction, re-green after every mutation restore |
| before/after screenshots | UNKNOWN | **UNKNOWN** | gui_required, unobtainable headless. Structural substitute **independently reproduced hash-for-hash**: stylesheet(scale) sha256[:16] at 5 scales = 1779b114/7a1a99e7/e7d4298e/be8d2aaa/c99024cd on HEAD AND after `checkout master -- qss.py` — byte-identical, matching the receipt's values |

**Hunk↔audit-row map (built by the crucible, the acceptance's core):** 5 hunks ↔ rows A–E, 1:1, no unmapped hunk, no hunkless row (qss.py:124 12px→SPACE_12 · :164 11→SIZE_SMALL · :188 10→SIZE_MICRO · :232 16px→SPACE_MD · :382 24px→SPACE_LG). Token values verified identical at tokens.py:308/309/433/434/444.

**Mutations:** PANEL-M2 (QWidget subclass w/ hardcoded hex in synapse_panel.py) → **REDDENED** by `test_no_hardcoded_hex_or_px_outside_designsystem` (1 failed/122 passed) — the guard bites exactly where it claims. M1a/M1b/M3 **SURVIVED** the automated guards; each is caught by a named crux structural check (see mutations ledger) and maps to a **pre-existing, bounded guard hole** — not something this leg introduced, and nothing the builder claimed otherwise:

**NITS / guard holes (spawns filed in the CRUX receipt):**
1. gui screenshots UNKNOWN — constitutional ceiling (builder honest about it; byte-identity fallback reproduced).
2. **Guard hole (M1b):** an off-palette hex inside designsystem/qss.py survives all 148 tests — designsystem/ is exempt from the hex/px scan *by construction* (test_rope_design_conformance.py:27-34); density guard scans density-keyed blocks only; token-authority scans ast.Assign declarations only. Palette drift inside the token authority itself is invisible to every automated guard. Spawn: pin that every hex emitted by `stylesheet()` is a tokens.py value.
3. **Guard hole (M3):** no test pins synapse_panel.py's live timer intervals (2000ms _ctx_timer / 4000ms _health_timer); a silent interval change survives the whole target list. Spawn: durable timer-interval pin.
4. Nuance (M1a): a cosmetic token-revert is invisible to both tests and byte-identity hashing (value-identical both ways) — the leg's tokenisation claim rests on diff review. Recorded, verdict-neutral.

---

## Cross-cutting findings

1. **Windows long-path clone hazard (4 of 5 audit lanes):** a fresh clone of SYNAPSE into a deep temp path fails checkout on `python/synapse/_vendor/anthropic/types/beta/*` ("Filename too long") and leaves a **silently partial tree with staged deletions** — a lane that doesn't notice could report missing artifacts as builder failures. Fix: `git config core.longpaths true` + restore before trusting the tree. Belongs in the crux/battleplan lane discipline.
2. **M-2 pin is demonstrated, not hypothetical:** 22.0.429 is live-usable to the hytest shim; any probe lane without `SYNAPSE_HYTHON` pinned WILL run on a build with no symbol table.
3. All five builder receipts' commit hygiene verified: each branch = product commit(s) + receipt commit, nothing outside declared touches, product_head fields match actual parentage.
