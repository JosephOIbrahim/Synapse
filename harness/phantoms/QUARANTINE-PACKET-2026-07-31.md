# QUARANTINE RATIFICATION PACKET — 2026-07-31

**Status of this packet:** merge-review input and carve-out ledger. **Nothing in this file has been ratified by Joe.** Proposed `rulebook/phantoms.json` entries are populated by Joe, never by the harness. The L5 merge is **not authorized** by this document. `harness/phantoms/SPEC.md` remains **PROPOSED**.

Probed build (verbatim, `hou.applicationVersionString()` via `Houdini 22.0.368/bin/hython.exe`): **BUILD 22.0.368**.
Authority table: `python/synapse/cognitive/tools/data/h22_symbol_table.json` — houdini_version=22.0.368, 35,903 symbols, truncated=False.

---

## 1. QUARANTINE CANDIDATES

Six candidates, two independent assays against the same table (initial sweep-assay + authority re-assay). Both agree: **6/6 quarantine holds — all ABSENT.**

| Candidate | Sweep assay | Re-assay (authority) | Reason |
|---|---|---|---|
| `pdg.PyEventCallback` | ABSENT | ABSENT — QUARANTINE holds | 0 rows; sibling `pdg.PyEventHandler` present (but unconstructable, CLAUDE.md §1.7 — `PyEventHandler(fn)` has no constructor) |
| `hou.cookPDGGraph` | ABSENT | ABSENT — QUARANTINE holds | 0 rows; the entire `hou.pdg` namespace is absent — PDG lives in the standalone `pdg` module |
| `hou.pdg.scheduler` | ABSENT | ABSENT — QUARANTINE holds | no `hou.pdg*` rows at all; real equivalent `pdg.Scheduler` present |
| `hou.pdg.workItem` | ABSENT | QUARANTINE holds | real equivalent `pdg.WorkItem` present |
| `hou.pdg.GraphContext` | ABSENT | QUARANTINE holds | real equivalent `pdg.GraphContext` present |
| `hou.pdg.cookWorkItems` | ABSENT | QUARANTINE holds | namespace absent; cook surface lives under `pdg.GraphContext` methods |

### Proposed `rulebook/phantoms.json` entries — FOR JOE TO POPULATE (NOT RATIFIED)

The harness proposes the following draft rows. Joe populates/copies them; the harness never writes `phantoms.json`.

```json
[
  { "symbol": "pdg.PyEventCallback",   "status": "quarantined", "build": "22.0.368", "evidence": "QUARANTINE-PACKET-2026-07-31.md §1; 0 rows in h22_symbol_table.json; sibling pdg.PyEventHandler present but unconstructable" },
  { "symbol": "hou.cookPDGGraph",      "status": "quarantined", "build": "22.0.368", "evidence": "QUARANTINE-PACKET-2026-07-31.md §1; hou.pdg namespace absent; PDG lives in standalone pdg module" },
  { "symbol": "hou.pdg.scheduler",     "status": "quarantined", "build": "22.0.368", "evidence": "QUARANTINE-PACKET-2026-07-31.md §1; real equivalent pdg.Scheduler present" },
  { "symbol": "hou.pdg.workItem",      "status": "quarantined", "build": "22.0.368", "evidence": "QUARANTINE-PACKET-2026-07-31.md §1; real equivalent pdg.WorkItem present" },
  { "symbol": "hou.pdg.GraphContext",  "status": "quarantined", "build": "22.0.368", "evidence": "QUARANTINE-PACKET-2026-07-31.md §1; real equivalent pdg.GraphContext present" },
  { "symbol": "hou.pdg.cookWorkItems", "status": "quarantined", "build": "22.0.368", "evidence": "QUARANTINE-PACKET-2026-07-31.md §1; cook surface lives under pdg.GraphContext methods" }
]
```

Adjacent, related, also unratified (surfaced by the FIX-VERIFY crucibles): `rulebook/phantoms.json` contains **no `usdrender` entry** today — the phantom verdict rests on the H21.0.671 recon memory only (see `solaris_parameters.md` crucible finding "NOT LAW-PINNED"). Consider ratifying `usdrender` alongside the corpus fix.

---

## 2. HDEFEREVAL GAP

### 2.1 Root cause — two stacked causes, both real, both independently reproduced

**(a) Harvester scope omission.** `host/introspect_runtime.py` walks exactly three roots and never names hdefereval: `import hou` (:83) with a lazy force-import loop over only `("hou.qt", "hou.secure")` (:87-91), `import pdg` (:94/:95 walked), and `pkgutil.iter_modules(pxr.__path__)` (pxr import :102, iter_modules :105). Zero occurrences of the string "hdefereval" in the file (grep-verified).

**(b) Headless-unimportable, re-probed live.** `Houdini 22.0.368/bin/hython.exe -c "import hdefereval"` → verbatim: `IMPORT FAIL ImportError hdefereval is only available in a graphical Houdini`. hdefereval hard-**raises** under headless `hython` — stronger than the five sibling headless-blind modules (`hou.qt`, `hou.audio`, `hou.ui`, `hou.desktop`, `hou.viewportVisualizers`), which merely fail lazy-loading. It is a **permanent sixth headless-blind module**. Fixing cause (a) alone yields nothing headless (a pdg-style try/except would swallow it); a GUI-mode harvest would admit it, so (a) is still a real harvester bug worth fixing for future GUI regenerations (add try/except `import hdefereval` + `_walk` block at ~:94).

### 2.2 Blast radius (attacked; corrected figures below)

- **Premise correction:** `executeInMainThreadWithResult` is **not** called across server/handlers anymore. The 28 TOPS call sites were migrated to `run_on_main` (`python/synapse/server/handlers_tops/_common.py:76-82`); `shared/bridge.py:141-150` deliberately never dispatches the blocking primitive; `tests/test_marshal_lint.py` bans it with an empty allowlist.
- **Real `hdefereval.<attr>(` call sites:** exactly **2 in production code** — `python/synapse/server/main_thread.py:309` (`hdefereval.executeDeferred(_on_main)`) and `python/synapse/host/main_thread_executor.py:290` (same) — plus **1 in tests**: `tests/test_live_capture.py:130` (`executeInMainThreadWithResult(_frame)`, GUI/live-host probe). An extended scanner judging hdefereval roots would false-flag exactly these (2 production / 3 total). ~39 anchored import lines across 17 files (~27 production, 20 of them `handlers_tops/*`) do **not** flag under depth-1 attr semantics.
- **Scope is per-sprint-touch, not suite-wide:** `check_phantom_clean` scans only added lines in changed files vs fork point (`harness/verify/checks.py:473-481`, `_sprint_added_py` + merge-base, offender filter :497).
- **Scout false-phantoms TODAY:** `_DOTTED_RE` (`python/synapse/cognitive/tools/scout.py:149`) already judges `hdefereval.*` roots; with the stamped table loaded, `_ground_symbols` (:550) returns `exists_in_runtime=false` — **not None** — on every hdefereval token today. P5.1's gate-down=FAIL escalation converts that from an assay anomaly into a hard gate failure. (Attack note: this framing is forward-looking; current master gate-down path is **WARN**, `ok:None` at `checks.py:460/:463`.)
- **Vendor surface (22.0.368, pinned):** `houdini/python3.13libs/hdefereval.py` has exactly four public entry points (`executeDeferred` :21, `executeDeferredAfterWaiting` :32, `executeInMainThreadWithResult` :43) plus three snake_case aliases (:30, :41, :45). `tests/test_marshal_lint.py:42-45` enumerates the same four. `executeInMainThreadWithResult` is **real on the vendor** — banned by policy (marshal lint), not phantom.

### 2.3 Exact allowlist proposal

Extend the existing constant semantics at `harness/verify/checks.py:392` (union site :469 on master; ":517 on branch" unverifiable from this checkout):

```python
_HEADLESS_BLIND_SYMBOLS = _GUI_HOU_ABSENT_HEADLESS | {
    "hdefereval",
    "hdefereval.executeDeferred",
    "hdefereval.executeDeferredAfterWaiting",
    "hdefereval.executeInMainThreadWithResult",       # real (vendor :43); banned by marshal lint — membership, not permission
    "hdefereval.execute_in_main_thread_with_result",  # snake_case alias (vendor :45)
}
# then: table_syms = table_syms | _HEADLESS_BLIND_SYMBOLS
```

**Attack correction (bounded, carry with the proposal):** the set above is incomplete against the vendor surface — it omits `hdefereval.execute_deferred` (vendor :30) and `hdefereval.execute_deferred_after_waiting` (vendor :41). Zero repo usage today (grep: no matches), so latent only; a one-line addition closes it.

**Axis separation preserved:** allowlisting `executeInMainThreadWithResult` does not weaken the ban. The phantom scanner is **membership** authority; the ban stays with `tests/test_marshal_lint.py` as **policy** authority. Net flags under the fix: 0 either way (the one test call site passes membership while staying banned by policy).

### 2.4 Merge recommendation (input only — merge NOT authorized)

The authority attack verdict is **SOUND** with the two bounded corrections folded in above (test_live_capture.py:130; missing snake_case aliases) and two notes (actual import count ~39 lines/17 files; P5.1 FAIL escalation is forward-looking vs today's WARN path). **Recommendation for merge review: the L5 merge should carry the allowlist fix** — without it, extending hdefereval to judged roots under P5.1's gate-down=FAIL yields 2 production false-flag sites plus live scout false-phantoms on every hdefereval token, while the allowlist is a single constant extension with vendor-pinned membership and preserved policy separation. Carry the attack's two corrections (3 total call-site count, +2 snake_case aliases) as part of the same merge chunk; optionally fold the `host/introspect_runtime.py` hdefereval walk (~:94) for GUI-mode regenerations as a separate non-blocking follow-up.

---

## 3. FIX-VERIFY — 6 crucibles, per file-group

Joe has **ratified all 6 fixes** for dispatch. Crucible results: **0 CONFIRMED rows, 6 ISSUE rows** — every file-group carries carve-outs. `replacement_right: true` on all 6 (usdrender→usdrender_rop is the correct replacement everywhere it fires); the issues are **coverage/ledger-fidelity carve-outs**, not wrong-replacement defects. ISSUE rows quote findings verbatim and are carve-outs for the dispatch.

### 3.1 `rag/skills/houdini21-reference/karma_rendering_guide.md` — **ISSUE**

(all_mentions_found: false; replacement_right: true)

> - karma_rendering_guide.md:204 — UPPERCASE banner '# ── OUTPUT PATHS: KARMA LOP + USDRENDER ROP ──' is a true phantom mention; a case-sensitive usdrender→usdrender_rop pass (as the fix is literally worded) misses it, leaving the phantom in a section header.
> - karma_rendering_guide.md:230 — second uppercase banner '# ── USDRENDER ROP SETUP ──' — same miss risk as :204. True mention count is 18 ONLY when counted case-insensitively (16 lowercase + these 2); the ledger's 18 rows must enumerate both.
> - karma_rendering_guide.md:234 + :572 — identifier 'configure_usdrender_rop' (def and call site) contains substring 'usdrender'; a substring-based replacement yields 'configure_usdrender_rop_rop' (collateral damage). These 2 lines must be excluded/no-op rows. Trap: the case-sensitive substring count is ALSO 18 (16 true + 2 identifier false-hits), so row-count agreement cannot prove the ledger targets the right 18 lines.
> - karma_rendering_guide.md:251 — load-bearing true mention: executable corpus code 'out_net.createNode("usdrender", ...)' actively teaches the phantom node type; replacement with 'usdrender_rop' is correct and essential, not cosmetic.
> - karma_rendering_guide.md:5 — keyword line '... usdrender rop, ...': replacing (not keeping bare 'usdrender', not listing both) is correct — a phantom keyword would re-teach the wrong node via retrieval; fix improves indexing since 'usdrender_rop' is absent from :5 today. Nit: pass yields the redundant 'usdrender_rop rop'. No husk/karmarendersettings/phantom context exists in the file (grep: 0 matches), so every true mention takes usdrender_rop; keeping soho_foreground/outputimage guidance (:257,:262) is correct.

**Carve-out:** ledger must enumerate :204/:230 (uppercase banners) explicitly and mark :234/:572 (identifier containment) as excluded no-op rows. Row-count agreement alone proves nothing (16+2 == 16+2).

### 3.2 `rag/skills/houdini21-reference/rag_render_output_path.md` — **ISSUE**

(all_mentions_found: false; replacement_right: true)

> - rag_render_output_path.md:8 — Context paragraph still reads "the usdrender ROP (`outputimage`)"; NOT inside any declared edit region (recipe :13-36, verify :85-89, mistakes :125/:127). 7 true type-mentions exist (hand-grep \busdrender\b: :8,:13,:31,:32,:36,:125,:127); stated geometry covers 6 of 7. Incomplete.
> - rag/skills/houdini21-reference/rendering.md:4 — trigger line lists `usdrender` but not `usdrender_rop`; keeping usdrender is right (artists know the phantom name) but BOTH should be listed or correct-name queries miss the skill.
> - rendering.md:30 — sibling file still contains phantom in executable position: rop = out.createNode("usdrender", name); also prose at :15,:27,:314. Single-file fix leaves corpus re-teaching the phantom one file over (code/corpus divergence trap). BOUNDED WEAKNESS if scope is deliberately single-file; incompleteness if corpus-wide.
> - Replacement-target audit: usdrender_rop is the correct real sibling for all 7 true mentions — :36 is the live phantom API call; :125 loppath and :127 output_file-kwarg entries describe real usdrender_rop behavior, not intentional phantom discussion; :34/:89 'usdrender1' are node names covered by region rewrites so name-coherence holds.

**Carve-out:** :8 context-paragraph edit must be added (7th mention outside declared regions); rendering.md:4 keyword line should list both spellings.

### 3.3 `rag/skills/houdini21-reference/solaris_nodes.md` — **ISSUE**

(all_mentions_found: false; replacement_right: true)

> - COVERAGE GAP: hand-grep shows 6 bare usdrender mentions (lines 4, 505, 508, 528, 720, 764); the 3 ledger rows cover only 505/508/720. Zero usdrender_rop refs exist in-file, so the substring trap is moot — the count miss is real, not a trap artifact.
> - MISSED line 505 context is covered, but line 528 (`# GOTCHA: rop.render(output_file=...) does NOT work for usdrender ROPs.`) is left unfixed — prose re-teaches the phantom spelling to chunked retrieval (code/corpus divergence class).
> - MISSED line 764 (`**rop.render(output_file=...) does nothing for usdrender**`) — gotcha bullet survives the fix, same phantom re-teaching problem.
> - KEYWORD LINE line 4: proposed fix leaves `usdrender` present and omits `usdrender_rop` entirely. Trigger keywords are retrieval metadata, not code, so keeping `usdrender` is defensible for user-query recall, but BOTH spellings must be listed or agents searching the canonical name `usdrender_rop` will not keyword-match this document.
> - Lines 505/508/720: usdrender_rop is the correct replacement in all three contexts (all are the /out USD Render ROP node-type context; corpus self-confirms at solaris_network_blueprint.md:42). No dangling refs: 'karma_rop' second arg is a node name only, referenced downstream via the rop variable, and no /out/karma_rop string lookup exists in-file.
> - ADJACENT (out of scope, logged): solaris_network_blueprint.md:226 still emits createNode("usdrender", "render_rop") in code while line 42 of the same file declares the type invalid — corpus self-contradiction that this fix does not address.

**Carve-out:** add rows for :4 (keyword, both spellings), :528, :764 ; 3 covered rows 505/508/720 confirmed correct; adjacent blueprint self-contradiction logged out of scope.

### 3.4 `rag/skills/houdini21-reference/solaris_parameters.md` — **ISSUE**

(all_mentions_found: true; replacement_right: true)

> - SPURIOUS LEDGER ROW: solaris_parameters.md:197 is 'configure_usdrender_rop("/out/karma_rop1")' — the call site of the KEPT function name. It contains no standalone 'usdrender' (word-boundary grep \busdrender\b hits only :171 and :176) and no createNode. A literal 'createNode→usdrender_rop at 197' edit has no anchor; dispatched as-is it either no-ops or corrupts the kept call site. True row count is 2, not 3.
> - MISLABELED ROW: solaris_parameters.md:171 is a docstring ('Configure a usdrender ROP for Karma rendering.'), not a createNode — the ledger description 'createNode→usdrender_rop at 171/176/197' is only accurate for :176. Edit itself (docstring 'usdrender'→'usdrender_rop') is still correct.
> - CORPUS-INCOMPLETE (bounded, outside proposed scope): the same phantom survives in the sibling file rendering.md:30 (`rop = out.createNode("usdrender", name)` — executable code), plus prose at rendering.md:15, :27, :314. The fix as proposed leaves the corpus still teaching the phantom from rendering.md; per the code/corpus-divergence lesson this will re-teach via knowledge_lookup/scout.
> - rendering.md:4 keyword line: keeping 'usdrender' in triggers is retrieval-RIGHT (the hallucinated term is what gets queried); no change needed there, listing both also acceptable.
> - NOT LAW-PINNED: rulebook/phantoms.json contains no 'usdrender' entry — the phantom verdict rests on the H21.0.671 recon memory only; consider ratifying it in phantoms.json alongside the corpus fix.

**Carve-out:** drop the :197 row (spurious — kept call site, no anchor); relabel :171 as docstring-not-createNode; true row count is 2. Recommendation to law-pin `usdrender` in phantoms.json carried to §1.

### 3.5 `rag/skills/houdini21-reference/solaris_network_blueprint.md` — **ISSUE**

(all_mentions_found: false; replacement_right: true)

> - solaris_network_blueprint.md:210 — comment 'Karma LOP feeds usdrender ROP in /out' is a true bare-usdrender mention unaccounted for by the 1-row ledger (BOUNDED WEAKNESS, sev 2/5; prose shorthand directly above the formerly broken createNode site)
> - solaris_network_blueprint.md:244 — rule 'soho_foreground=1 on usdrender ROP' is a second true mention unaccounted for (same class; normalizing to usdrender_rop closes residual teaching surface given this repo's code/corpus re-teaching failure class)
> - rendering.md:4 — keeping 'usdrender' in the keyword line alone is acceptable: semantic index (rag/semantic_index, sentence-transformers over whole skill docs) covers usdrender_rop queries; listing BOTH is optional hardening, not required; the :226 edit does not break retrieval (whole-doc embedding), though content_digest keys on file content so an index rebuild is standard follow-up

**Carve-out:** add rows for :210 and :244; semantic-index rebuild noted as standard follow-up after content change.

### 3.6 `rag/skills/houdini21-reference/rendering.md` — **ISSUE**

(all_mentions_found: false; replacement_right: true)

> - rendering.md:15 — true `usdrender` mention (`# Create and configure a usdrender ROP in /out`) not covered by the 1-row plan; after :30 becomes createNode("usdrender_rop"), this comment contradicts the code it heads. Should also read usdrender_rop.
> - rendering.md:27 — true mention in docstring (`output_file kwarg in rop.render() does NOT work for usdrender`) not covered; correct behavioral claim but keeps teaching the phantom name for a usdrender_rop behavior.
> - rendering.md:314 — true mention in Common Mistakes (`does NOT work for usdrender ROPs; set outputimage parm directly`) not covered; outputimage is a usdrender_rop parm, so the note should name usdrender_rop.
> - rendering.md:4 — keeping `usdrender` as a keyword is right for retrieval of legacy queries, but the corrected name `usdrender_rop` is absent from the trigger list; if trigger matching is token- rather than substring-based, queries using the name the corpus now teaches dead-end. List BOTH.
> - Grep proof: `usdrender` matches exactly 5 lines (4, 15, 27, 30, 314); the file contains zero existing `usdrender_rop` occurrences, so the raw count is trap-free and the plan's implicit 2-mention scope is provably short by 3.

**Carve-out:** add rows for :15, :27, :314 ; keyword line :4 should list both spellings; the plan is provably short by 3 of the file's 5 trap-free mentions.

**Cross-file note (from crucibles 3.2/3.3/3.4):** corpus-wide coverage is the real risk class (code/corpus divergence → re-teaching via knowledge_lookup/scout). A single-file dispatch leaves the phantom alive in sibling files; the carve-outs above are additive rows, not scope creep.

---

## 4. HARNESS STATE

### 4.1 Phantom sweep v1 — verified

- `.claude/workflows/phantom-sweep.js` syntax-checked (`node --check` passes); file is **untracked** (`?? .claude/workflows/phantom-sweep.js`), so "unchanged under-cap behavior" was audited structurally against the sibling workflow (`.claude/workflows/h22-doc-scout.js`), not by diff — no baseline exists.
- Verified behaviors: overflow capture enumerates all beyond-cap groups (`.slice(MAX_HIT_GROUPS)` before cap-slicing; shallow-copy, read-only); `overflowHits` flattens symbol/path/line/snippet loss-free in-process; under-cap path leaves workflow flow untouched (`overflowGroups=[]`, conditional writer section).

### 4.2 Sweep v2 accounting fix — attacked, ships with three bounded weaknesses

Attack verdict: **OVERALL PASS — zero showstoppers, three documented bounded weaknesses.**

1. **Ledger-side fidelity of the overflow appendix is unverified.** Overflow rows reach the ledger only through the writer prompt (`JSON.stringify(ledgerData)` :213 + section-4 instruction :209–211); nothing verifies section-4 row count against `overflow_count`. The attacker's MISSING-HITS grep (lines 218–226) checks only ONE seed symbol, so silent overflow-row drops surface only incidentally. Mitigation forward: attacker counts section-4 rows vs `overflow_count`, or writer emits `rows_written` for comparison.
2. **`capped`/SW2 blank-check edge.** If groups number exactly `MAX_HIT_GROUPS`, no truncation occurs but `capped: groups.length >= MAX_HIT_GROUPS` (:199) reports true with `overflow_count: 0`, and predicate SW2 (:237) passes on its second disjunct regardless of actual classification loss. Misleading flag, not data corruption.
3. **Upstream inventory cap is a separate, by-design loss.** Hits beyond the 60-per-surface inventory cap (:122) are lost before the classify cap runs; the overflow array cannot enumerate what inventory never returned. The "CAPPED at 60" marker makes it honest, but `hits_total` understates true mention count in that case.

Plus two small pre-existing throw-surfaces noted: non-null shape-violating assay results throw TypeError mid-run (schema pins `verdicts` required; pre-existing pattern), and `JSON.parse(args)` (:14) is unguarded unlike the sibling's try/catch (h22-doc-scout.js:16).

### 4.3 SPEC status

`harness/phantoms/SPEC.md` remains **PROPOSED** — not ratified, not modified by this packet. The v2 accounting fix touched `.claude/workflows/phantom-sweep.js` only; SPEC.md was not edited.

---

*End of packet. Awaiting Joe's ratification decisions on: §1 phantoms.json population (6 pdg/hou.pdg candidates, + optional `usdrender`), §2.4 L5 merge with the allowlist (and its two attack corrections), §3 dispatch with carve-out rows.*
