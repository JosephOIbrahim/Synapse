# CAPSULE 2026-09-04 — BP5 plan: close the loop, then v5.63.0

Paste this whole file into a fresh chat first thing. It is the boot. It was written 2026-09-03 ~20:40
by the CTO seat (Fable 5.1) after v5.62.0 published; nothing here is inferred — every sha, path and
number is from tonight's receipts. Companion: `harness/notes/CAPSULE_2026-09-03_BP4.md` (what happened).

## 0. Boot facts (verify with one command before anything else)

    git -C C:\Users\User\SYNAPSE log -1 --format='%h %s' ; git -C C:\Users\User\SYNAPSE status --short | measure

- master = origin = `2b9f9e01` (release commit). v5.62.0 is Latest, tag at `8bd4fee5`. No wave armed. Nothing running.
- `bp4/rulings` is BROKEN-carried at `a62267f9` (product `ff3d6f73`), worktree `.claude/worktrees/bp4-rulings`. Not merged.
- 27 worktrees kept on purpose (unusable-only prune standard). 18 prune commands sit in `harness/battleplan/notes/BP4_TIDY.md`; none executed.
- Untracked-on-purpose helpers under `harness/notes/h22/`: `bp4_merge_train.ps1`, `gatec_push_bp4.ps1`, `gatec_push_tag_v5620.ps1`. Copy, rename per wave.
- Another writer's surface on master, untouched all wave (leave it): `harness/reach/`, `harness/flow/`, `harness/hardening/`, `.claude/agents/`, `.claude/workflows/`, `docs/REACH_BLUEPRINT.md`, `docs/harness/`, the modified `harness/battleplan/prompts/BP2-*.md`, `dashboard_bp1.py`, `harness/rope/STATE.json`.
- Machine truths: GUI Houdini 22.0.400; hython pinned `SYNAPSE_HYTHON=22.0.400` (22.0.429 fails the hytest gate); prefs dir `C:\Users\User\OneDrive\Documents\houdini22.0` (set `HOUDINI_USER_PREF_DIR`); hython path in `harness/battleplan/notes/BP3_RECON.md` T2. Claude Code 2.1.259: `--effort max` valid, `--max-turns` absent. Rails referee = `claude-fable-5-1`; builders Opus 4.8; chores Haiku 4.5 (all proven by `runs/2026-09-03/preflight_bp4.json`).
- DC rules that bit tonight: `$`-variables need a `.ps1` run via `-File`; `powershell -File x.ps1 -Legs a,b,c` FLATTENS the array (call the script in-process with `&` instead); `Set-Content -Encoding utf8` writes a BOM (use python for byte-exact writes); `cmd` eats `^{}`; never chain `git commit` behind `findstr failed` (it matches the word and commits anyway); 4-minute foreground ceiling — detach and poll.
- Token meter (rails) counts cache reads. BP4 per-leg, measured: Opus builders 14.8M / 18.4M / 20.0M / 32.0M in; Haiku legs 8.8M–9.5M; Fable 5.1 crucible ≥ 41.8M (six lanes, lead transcript only). Plan caps from these, not from hope.

## 1. First principles — what "closed" means

Three things were shipped honest-but-open in v5.62.0. "Closed" is a predicate per item, measurable on the machine, not a feeling:

| Item | Closed means (predicate) | Evidence that proves it |
|---|---|---|
| Spatial module | The three queries are registered by default, the lane is `ratified:true` with its diff applied, tests pass in a FRESH clone (fixtures fetched, not assumed), timing measured from before the triangle gather | `tests/test_spatial_lane.py` green in a fresh clone; `authoring_domains.json` carries the lane; registry grep shows default-on; timing lines include the gather |
| Panel typography | The floor is a MEASURED Houdini default (family + size from the running GUI), zero typography literals outside the token module, stylesheet still scale-invariant | `FONT_FLOOR_PX` provenance = `measured (probe_ui_font.py, 22.0.400 GUI, <date>)`; `test_panel_typography` + the path-selected hex/px conformance test green; 5-scale check identical or size-only diff; before/after screenshots |
| Probe / splat render | The World Labs splat renders IN COLOUR through Karma XPU 22.0.400, and the review's causal story is the crucible-verified one | EXR stats: per-channel means differ (not the grey `RGB max/avg/stddev identical to 6 d.p.` of BP4); husk log; review §13.1/§13.5 amended |

Rules that do not bend: runtime is truth, the local help cache is the referee, model memory is hypothesis. Unmeasured renders UNKNOWN. Nothing registers or ratifies without Joe's per-act word. CRUX verdict is READ before any merge word. Commit before receipt. One writer per surface. Prune unusable only.

## 2. Sequence, with mile markers (~6–8 h wall, most of it agents)

### Mile 0 — Rulings, cold (this fresh session, reasoning tier, before any wave)
1. Fix `bp4/rulings` mechanically, exactly per `harness/battleplan/notes/BP4-CRUX_verdicts.md` §"BP4-RULINGS" (on master since 85a26c34). Work IN the worktree `.claude/worktrees/bp4-rulings` on branch `bp4/rulings`:
   - add row 22: leg CRUX, id `CRUX-1`, claim verbatim from `harness/notes/receipts/BP3-CRUX.json:for_ruling[0]` (the "Confirmed and re-anchored the BP3-STUBS ruling item…" entry), anchor `BP3-CRUX.json:for_ruling[0]`, recommendation `none stated`, ruling PENDING;
   - count line → `rows: 22 (expected 22; RECON 3, PANEL 1, PROBE 5, CORPUS 7, STUBS 2, CRUX 1, TIDY 3)`, drop the delta note;
   - add the missing `severity` column (9 columns per the brief); fix row 17's item id (a first-colon extraction caught `ratified:false`);
   - re-encode the file as UTF-8 (cp1252 bytes at offsets 14 and 74 — `open(..., encoding='utf-8')` raises today);
   - receipt findings #3/#4 corrected (D3.1/D3.2 read `no` in the table while the receipt claims `yes`); ratification classification made consistent (rows 10/11/12 CORPUS tier promotions and 20 TIDY-R2 settings-fence edit match the "yes" rule).
   Commit the product, then a receipt amendment, then post the S5 release line on the bus (`python harness\battleplan\bus.py post bp4 BP4-RULINGS status "{\"release\": [\"harness/notes/CTO_RULINGS_BP3.md\"]}" *`).
2. RULE all 22 (fill the CTO ruling column) — cold, from the table, anchors open. Then rule the six BP4 CRUX items (`BP4-CRUX_verdicts.md` §"For ruling (compiled)": R-1, I-1, B7-1, S-1, P-1, U-1) and the two-writers rule in `harness/notes/receipts/BP4-INTAKE.harvest-addendum.json`.
3. Joe's ratifications (his words, per item): **M-1** schema stays `docs/intake/`; **M-2** pin hython 22.0.400; **D-DEP-03** `hou` over `pxr` where RECON found it; **D3.1** the spatial lane diff (after its contract path is reconciled `schemas/…` → `docs/intake/…`); **D3.2** schema home. D3.1/D3.2 are what unlock Mile 3's SPATIAL-CLOSE flip.
4. Joe: `merge rulings` → `git merge --no-ff bp4/rulings` on master. Done = `CTO_RULINGS_BP3.md` on master with 22 rulings, five ratified.

### Mile 1 — Joe's hands (10 minutes, GUI Houdini 22.0.400)
1. Python shell: paste `python/synapse/panel/scripts/probe_ui_font.py`; copy the printed family / pointSize / pixelSize / scaledSize lines into the chat. That is the font floor, measured.
2. Panel screenshots before the BP5 change at UI scale 100% and 150% (after-shots come at Mile 4).
3. Drop `synapse_worldlabs_blueprint.docx` and `synapse_worldlabs_coffee_shop_talk.docx` into `docs/intake/src/` (MANIFEST rows flip from `missing`; CTO commits them, named files).

### Mile 2 — Pre-arm hardening (CTO, ~30 min, all named-file commits on master)
Each of these cost real minutes tonight; fix before arming, not after:
1. **S5 release line**: three legs omitted it. Add to `harness/battleplan/prompts/_template.md` a final step that posts `status {"release": <touches>}` on the bus immediately before the receipt commit — or have `orchestrate.ps1` post it at close. Test: dry run shows the line in the prompt.
2. **Absolute-path leak**: INTAKE and TIDY wrote copies of their product into the MAIN tree from worktrees. Add to the template: "write only worktree-relative paths; never `C:\Users\User\SYNAPSE\...` absolute." Add to the merge train a pre-merge check: for each leg branch, list files it adds that exist untracked in the main tree; compare hashes; stop if different, delete if identical.
3. **Watcher flag collision**: `watch_bp4.ps1` drops `harness/notes/h22/BP4_CRUX_LANDED.flag` into the main tree; CRUX commits the same path. Point the watcher's flag at `harness/notes/h22/<wave>_CRUX_LANDED.watcher.flag`.
4. **Clone hardcodes**: `status_bp4.py` shipped a BP2 leg list; `dashboard_bp4.py` words/PAIRS were stale. In `author_bp5.py`, generate `LEGS = [...]` and `PAIRS` from `M` instead of string-replacing bp4→bp5.
5. **`-k panel` gate hole**: it deselects `test_rope_design_conformance.py::test_no_hardcoded_hex_or_px_outside_designsystem`. Missions say `pytest tests/test_panel_typography.py tests/test_rope_design_conformance.py tests -k panel` — select by path.
6. **Rails settle on a blocked ledger** refuses; the halting wave's later legs read UNKNOWN. Either size the cap so it doesn't halt mid-crucible, or add `settle --allow-blocked` (small change in `harness/rails.py`, tests in `tests/test_rails.py`). If skipped, meter by hand with `harness/battleplan/meter_transcript.py <transcript.jsonl>`.
7. Fixture fetch: `harness/probes/fetch_worldlabs_fixture.py` — downloads `narrow_european_cobblestone_lane_{500k.ply,_collider.glb,_pano.png}` from `https://wlt-ai-cdn.art/example_exports/narrow_european_cobblestone_lane/` into the fixtures dir, verifies SHA256 against the values in `docs/reviews/bp3-h22-worldlabs-probes-2026-09-03.md`, skips LOUDLY (not silently) when offline. SPATIAL-CLOSE's fresh-clone test depends on it.

### Mile 3 — Author BP5 (CTO; `author_bp5.py` in the `author_bp4.py` shape; missions below)
Wave = three builders + CRUX. TIDY by hand (three git commands) unless the census is wanted as a leg.

**BP5-SPATIAL-CLOSE** (reasoning, Opus 4.8, self-cap 30). Touches: `python/synapse/spatial/`, `python/synapse/server/authoring_domains.json`, the registry module RECON named, `tests/test_spatial_lane.py`, `harness/probes/fetch_worldlabs_fixture.py`, `docs/reviews/bp5-spatial-close-<date>.md`. Targets: T1 timing `t0` before `_collect_triangles` (or a `gather_seconds` field asserted on the sum); T2 registration: the three tools registered by default, the `SYNAPSE_SPATIAL_LANE` flag becomes an OFF switch (documented in `docs/studio/DEPLOYMENT.md`), registry test updated; T3 the wall/ceiling partition above 45° (S-1) with a test; T4 lane diff: reconcile `contract` to `docs/intake/world_manifest.schema.json`, `git apply` it (ONLY because D3.1/D3.2 are ratified — cite the ruling row), `ratified:true`; T5 fresh-clone proof: clone to `%TEMP%`, run the fetch script, run the tests, paste the summary. Acceptance: tests green in the fresh clone (test); registry grep shows default-on (check); timing lines include the gather (probe); `authoring_domains.json` carries the lane with the reconciled path (check). Crucible: re-runs the fresh-clone test itself; mutations: break the gather timing → reddens; set the flag to 0 → tools absent; strip the lane → conformance reddens. HELD until Mile 0 step 3 lands D3.1/D3.2 — the flip is Joe's word.

**BP5-PANEL-LITERALS** (reasoning, Opus 4.8, self-cap 30). Touches: `python/synapse/panel/`, `tests/test_panel_typography.py`, `harness/battleplan/notes/BP5_PANEL_LITERALS_AUDIT.md`. Targets: T1 read `BP4_PANELFONT_AUDIT.md` + CRUX's 166-literal grep; T2 set `FONT_FLOOR_PX` from Joe's paste with provenance `measured`; T3 substitution-only: every remaining font-family/size/weight literal outside `designsystem/tokens.py` → its token (this is the scope of held spawns BP3-INLINE-HEX / BP3-STYLES-MIGRATE — say which rows those spawns become); T4 the 5-scale stylesheet check re-run (identical or size-only diff, stated); T5 tests: `test_panel_typography` + path-selected `test_no_hardcoded_hex_or_px_outside_designsystem` green; `synapse_panel.py` lifecycle/timer ranges untouched. Acceptance: zero typography literals outside the token module by the crucible's own grep (check); floor provenance `measured` (check); tests green (test); screenshots after Joe's hands (gui_probe, gui_required). Crucible mutations: reintroduce one literal → reddens; lower a token below the floor → reddens; add a widget subclass → whitespace-only checker reddens.

**BP5-SPLAT-COLOUR** (reasoning, Opus 4.8, self-cap 30; hython + husk, detached and polled). Touches: `harness/probes/synapse_blueprint_probes.py` (a NEW probe B-8, not edits to B-7), `harness/notes/h22wl/bp5_splat_colour/`, `docs/reviews/bp3-h22-worldlabs-probes-2026-09-03.md` (append-only §14). Targets: T1 amend the §13.1/§13.5 causal sentence to the crucible-verified story (Karma XPU 22.0.400 substitutes a default distant light when the stage carries none; the camera bind silences husk errors without changing pixels; the composite rewiring restores lighting); T2 B-8: render the splat in colour — try in order and record each: (a) `labs::relight_gsplats` LOP if present on the build (R-4 said gsplat tooling is native), (b) the gsplat primitive with its per-point SH primvars bound to Karma's gsplat shader, (c) fallback: bake SH-DC (`f_dc_0..2` → displayColor) onto the Points prim so a plain shader picks up colour; T3 EXR stats per channel (oiiotool or hython) — closed means channel means differ and the mean colour matches the PLY's SH-DC mean within a stated tolerance; T4 if none of (a)–(c) produces colour on 22.0.400, the verdict is UNKNOWN with the traceback/husk lines, never "black by design". Acceptance: B-8 stdout with build line (probe); per-channel stats with the command (receipt); §13 amended, §14 appended (check); the path that worked, named, or UNKNOWN with evidence (receipt). Crucible: re-renders with its own out dir and recomputes stats; mutation: drop the colour binding → channels equalise again.

**BP5-CRUX** (referee, Fable 5.1, self-cap 40, READ-ONLY). Three lanes. Same STD_CRUX. Final writes: verdicts + mutations → flag (watcher-safe path) → commit → receipt, nothing after.

Budget: `-Budget '6turns,90000000tokens'` (3 builders + CRUX + 2 slack; the ceiling sits above three Opus legs at BP4's worst case 32M each plus a crucible at ~45M — tight on purpose; if it halts before CRUX, re-arm CRUX alone on a mini-cap as tonight). Model rails unchanged. Effort `max`.

### Mile 4 — Run
    python harness\battleplan\author_bp5.py                              # 4 missions validated, prompts, control, live manifest
    powershell -File harness\battleplan\dryrun_bp5.ps1                   # cap parsed, deps gate, no launch; stop the pid after the pass
    powershell -File harness\battleplan\arm_bp5.ps1 -Budget '6turns,90000000tokens'   # Joe's word: `go batch` (enumerated, incl. the SPATIAL-CLOSE flip)
    python -X utf8 harness\battleplan\dashboard_bp5.py --watch           # board on the second monitor
    python harness\battleplan\receipts_bp5.py --full                     # one line per receipt, straight from the branches
Then: CRUX lands → read `BP5-CRUX_verdicts.md` in full → Joe: `merge N–M` → train (in-process: `& .\harness\notes\h22\bp5_merge_train.ps1`) → ratchet TWICE (full `python -X utf8 -m pytest tests -q -p no:cacheprovider`, detached, ~5 min; expect 6942+ passed / 0 failed) → Joe: `push` (Gate C override script, once) → capsule.

### Mile 5 — Release v5.63.0 (the ritual, in the order GitHub actually accepts)
1. Bump the six surfaces exactly as `8bd4fee5` did: `VERSION`, `pyproject.toml`, `python/synapse/__init__.py` (two lines), `CLAUDE.md` (`SYNAPSE v5.63.0`), `README.md` (`<sub>v5.63.0 `), plus `harness/notes/RELEASE_v5.63.0.md` in the house voice (draft-only header, scope, For artists, Under the hood, what the CTO got wrong by name, Tests, Not in this release, Handoff).
2. `python harness\verify\version_agreement.py` → `agree=True` on all six.
3. `python -X utf8 harness\verify\checks.py --task R.R --worktree C:\Users\User\SYNAPSE --mode B` detached (~5 min). Expect verdict FAIL with the SAME line as v5.61.0/v5.62.0: blockers `mutation_fail_closed, hot_reload_gated, installer_host_targeted, ci_covers_shipping_surface`; accepted (solo) `process_bridge_armed, auth_fail_closed`; open hygiene `tool_metadata_single_source, packaging_self_contained`. Anything else is a regression — stop.
4. Commit the bump. Joe: `waiver + publish` (one enumerated word): push the bump; `git tag -a v5.63.0 <bump-sha> -m '…'`; push the tag under the override; `gh release create v5.63.0 --title 'v5.63.0 - <phrase>' --notes-file harness/notes/RELEASE_v5.63.0.md` (create FROM the existing tag — do not draft-then-retarget; GitHub refuses a bare sha target and refuses to publish a draft without a tag); append the *Published* line (waiver re-signed, tag at sha), commit, push.
5. Triple check before saying "published": `gh release list --limit 1` shows Latest; `git ls-remote --tags origin 'refs/tags/v5.63.0^{}'` peels to the bump sha (PowerShell, not cmd); every path the notes claim exists at that commit; `VERSION` reads 5.63.0.

## 3. Words (per act, never banked)
`merge rulings` · five ratification words (M-1, M-2, D-DEP-03, D3.1, D3.2) · `go batch` (enumerates the four legs and the SPATIAL-CLOSE flip) · `merge N–M` after reading the verdicts · `push` · `waiver + publish`. Everything else — authoring, hardening commits, release lines, harvests, settles, the census — is CTO-delegated.

## 4. When it breaks
- A leg stuck at `closing` with "no RELEASE line" → post it: `python harness\battleplan\bus.py post bp5 <LEG> status "{\"release\": [\"<touches>\"]}" *`.
- "untracked working tree files would be overwritten by merge" → the leak; compare hashes (`git hash-object` vs `git rev-parse bp5/<leg>:<path>`), delete if identical, else move aside and read both.
- BUDGET HALT before CRUX → re-arm CRUX alone: `arm_bp5.ps1 -Budget '2turns,50000000tokens'` (receipts present → only CRUX dispatches).
- CRUX process alive long after its receipt → it's idling; check the transcript hasn't grown, then kill it.
- B-8 produces only grey → that is a finding about the gsplat path on 22.0.400, not a failure of the leg; the review says UNKNOWN + evidence, and the release notes say so in those words.
- SPATIAL-CLOSE ready but D3.1/D3.2 not ratified → it stays HELD; nothing else in the wave depends on it.

## 5. Definition of closed, restated in one line each
Spatial: default-on, ratified, green in a fresh clone. Panel: measured floor, zero literals, invariant stylesheet. Splat: colour in the EXR, or UNKNOWN with the husk lines. Then v5.63.0 says exactly that.
