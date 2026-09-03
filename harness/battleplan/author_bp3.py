# author_bp3.py - CTO seat, 2026-09-03. Authors wave BP3 (H22 Solaris + World Labs blueprint execution).
# Writes missions/BP3-*.json, neutralises the BP2 territory paragraph in prompts/_template.md,
# clones the per-wave bp2 files to bp3, then runs compile_wave -> make_control -> build_manifest_bp3.
# Authoring is CTO-delegated (wave authoring, ops hygiene). ARM is Joe's word. Merge/push/tag/drop/ratify are Joe's words.
import json, re, subprocess, sys
from pathlib import Path

AF = Path(r"C:\Users\User\SYNAPSE\harness\battleplan")
REPO = AF.parents[1]
SRC = "docs/intake/blueprint-h22-worldlabs-intent.md"
STD_CRUX = [
    "the crucible trusts no builder's proved_it_bites - it authors its own mutations",
    "every verdict row carries the crucible's own anchor",
    "a leg with any UNKNOWN acceptance is at best SOUND-WITH-NITS, never SOUND",
    "the crucible flips no contract feature and edits no product file",
]
HYTHON_NOTE = ("Known environment facts (memory, verify before relying): GUI Houdini is 22.0.400, hython may be 22.0.417 - pin whichever hython reports; "
               "the live H22 prefs dir is C:\\Users\\User\\OneDrive\\Documents\\houdini22.0 (OneDrive known-folder redirect) - hython launched from an agent lane has looked in the old Documents path before; "
               "set HOUDINI_USER_PREF_DIR explicitly. Long hython runs: detach and poll, never foreground-wait past 4 minutes.")

M = []

M.append({
 "id": "BP3-RECON", "band": "TRUTH", "class": "truth", "tier": "reasoning",
 "name": "Reconcile every V0 path in the H22/World Labs blueprint against the live repo; locate hython + pref dir; list prior H22 probe artifacts - writes one notes file, creates nothing",
 "note": "Tier: reasoning. Self-cap: 15 turns (progress every 5). First leg of BP3; PROBE/STUBS/CORPUS consume your bus finding live. Blueprint sec.0.0 reading map: read sec.0.3, sec.6, sec.2.6, sec.2.7 only. Never mkdir to make the blueprint true - a 'no match' row is the finding. " + HYTHON_NOTE,
 "targets": [
  "T1) Reconcile every V0 repo path named in the blueprint (sec.1.3, sec.2.8, sec.3.2, sec.3.7, sec.6 step 2): intake dir, reviews dir, probe dir, authoring_domains.json, verified_lop_solaris_knowledge_*.json, h22_doc_candidates.json, scene_recipes.py, handlers_material.py, any D-track spatial/bbox helper, the JSON-schema home (if any), the fixtures home, the panel dir (python/synapse/panel/ + designsystem/manifests/qss). Write harness/battleplan/notes/BP3_RECON.md with a table `V0 path | actual path | evidence (Test-Path / git ls-files line)`; rows with no match stay 'no match'.",
  "T2) Locate the hython SYNAPSE uses (path; build via `hython -c \"import hou;print(hou.applicationVersionString())\"`), the .synapse/hytest.py shim discipline, and the HOUDINI_USER_PREF_DIR that makes hython see the H22 prefs (verify the OneDrive path in the note). Post ONE bus finding addressed to * the moment it is known: {\"hython\": path, \"build\": str, \"pref_dir\": path, \"fixtures_dir\": path, \"reviews_dir\": path, \"notes_dir\": path, \"schema_home\": path-or-none, \"spatial_helpers\": [paths]} with anchor = BP3_RECON.md.",
  "T3) List prior H22 Solaris probe artifacts already in the repo (N-3, N-5, N-6, N-7, KAR-04/07/12, SOL-03; verified_lop_solaris_knowledge_22.0.368.json; anything under harness/notes/h22/ or docs/reviews/ naming scatterinstances, blocker, orderedImageFilters, UsdRender.Pass) so CORPUS and PROBE re-check existence only and never re-derive (blueprint sec.1.2).",
  "T4) Report whether docs/intake/ contains the dossier (`Dossier - H22 Solaris and Karma (SYNAPSE Intake)`) and the coffee notes; if absent, say so in the finding (`\"dossier_in_repo\": false`) - CORPUS falls back to blueprint pointers and Joe drops the files on his word."
 ],
 "touches": ["harness/battleplan/notes/BP3_RECON.md"],
 "readonly": False, "deps": [],
 "crucible_criteria": ["every 'actual path' row must Test-Path true in a fresh checkout; every 'no match' row must Test-Path false", "no directory or file created outside touches (git status in the worktree shows only BP3_RECON.md + receipt)"] + STD_CRUX[1:2],
 "spawn_classes": [],
 "source": {"doc": SRC, "anchor": "v0.3 sec.6 steps 1-3; sec.0.0 reading map; sec.1.2 not-to-be-re-derived list"},
 "acceptance": [
  {"predicate": "BP3_RECON.md has one row per blueprint V0 path with an evidence column; no row invented", "evidence": "check"},
  {"predicate": "bus finding posted with hython path, build string, pref_dir, fixtures/reviews/notes dirs, schema_home, spatial_helpers, dossier_in_repo", "evidence": "receipt"},
  {"predicate": "prior-artifact list with repo paths for N-3/N-5/N-7/KAR-04/SOL-03 (or 'not found' per id)", "evidence": "check"},
 ],
})

M.append({
 "id": "BP3-PROBE", "band": "TRUTH", "class": "truth", "tier": "reasoning",
 "name": "Fixture download + hython run of harness/probes/synapse_blueprint_probes.py (P/B/S, 22 probes) + review doc with D1.1, D2.1-D2.4 verdicts, gate and risk evidence",
 "note": "Tier: reasoning. Self-cap: 30 turns (progress every 5). Blocked until BP3-RECON's finding (hython, pref_dir, fixtures_dir, reviews_dir). NEVER edit harness/probes/synapse_blueprint_probes.py to make a probe pass - a wrong probe is a finding on the bus, the defect goes in the review doc. A raising probe is BLOCKED with traceback and the run continues (the script does this). gui_required rows (B-2 handedness, B-9 visual, viewport display-purpose default) are UNKNOWN headless. Rule D-1: you report evidence found/not found for gates G-1..G-4; you never write OPEN. " + HYTHON_NOTE,
 "targets": [
  "T1) Fixture: download narrow_european_cobblestone_lane_500k.ply, _collider.glb, _pano.png from https://wlt-ai-cdn.art/example_exports/narrow_european_cobblestone_lane/ into the reconciled fixtures dir under a worldlabs/narrow_european_cobblestone_lane/ folder; record SHA256 + byte size per file. Do not fetch 2m.ply or hq.glb until B-1 passes on 500k. Fixture files are NOT committed if the repo .gitignore excludes binaries - if they are ignored, the review doc records their absolute paths + hashes and that is the receipt.",
  "T2) Run, detached and polled (log to file), with HOUDINI_USER_PREF_DIR set from RECON: `hython harness\\probes\\synapse_blueprint_probes.py --ply <ply> --glb <glb> --out harness\\notes\\h22wl\\bp3_probes --save-hip`; stdout verbatim to harness/notes/h22wl/bp3_probes/stdout.txt. Wall budget 30 min recorded. Also run `husk --help | findstr -- --pass` and record the line (P-7 shell check).",
  "T3) Review doc in the reconciled reviews dir: `bp3-h22-worldlabs-probes-<yyyy-mm-dd>.md` - build pin (P-0 line), fixture hashes, per-probe status table (22 rows RAN|BLOCKED + seconds), verbatim key outputs (or stdout path + line ranges), done-condition rows D1.1, D2.1, D2.2, D2.3, D2.4 with verdict pass|fail|UNKNOWN + anchor (file:line in stdout.txt), gate evidence G-1..G-4 (found / not found + anchor), risk status R-1..R-4 (triggered / clear / unknown + anchor), blueprint sec.8 open questions 1-5 answered (anchor) or unanswered (blocked by). The B-6 exported .usdc size and B-7 EXR result (or BLOCKED traceback) are quoted verbatim.",
  "T4) Post a bus finding the moment stdout.txt lands: {\"claim\": \"bp3 probes ran: <n> RAN / <m> BLOCKED\", \"anchor\": \"harness/notes/h22wl/bp3_probes/stdout.txt\"} and a second finding with the review doc path. CORPUS and STUBS consume these live."
 ],
 "touches": ["harness/notes/h22wl/", "docs/reviews/bp3-h22-worldlabs-probes-*.md", "fixtures/worldlabs/"],
 "readonly": False, "deps": ["BP3-RECON"],
 "crucible_criteria": ["the crucible re-runs the probe script itself in a fresh checkout with its own out dir and diffs probe_results.json statuses against the builder's", "`git diff master..HEAD -- harness/probes/` is empty (no probe edits)", "fixture SHA256s recomputed by the crucible match the review doc"] + STD_CRUX[2:3],
 "spawn_classes": [],
 "source": {"doc": SRC, "anchor": "v0.3 sec.6 steps 3-5, 7; sec.2.6 fixtures; sec.2.8 D2.1-D2.4; sec.9 gates; sec.10 risks"},
 "acceptance": [
  {"predicate": "stdout.txt exists and its first probe block is P-0 with a hou.applicationVersionString() line", "evidence": "probe"},
  {"predicate": "probe_results.json has 22 entries, each RAN or BLOCKED, with seconds on RAN rows and a total wall time line in stdout", "evidence": "check"},
  {"predicate": "review doc has D1.1 and D2.1-D2.4 rows with verdict + stdout.txt anchor; gui_required rows are UNKNOWN", "evidence": "receipt"},
  {"predicate": "B-6 exported b6_wl_component.usdc exists with size printed, OR B-6 is BLOCKED with a traceback quoted in the review doc", "evidence": "probe"},
  {"predicate": "SHA256 + bytes recorded for all three fixture files", "evidence": "check"},
  {"predicate": "B-2 handedness (lane not mirrored after the Y/Z flip) confirmed in the viewer", "evidence": "gui_probe", "gui_required": True},
 ],
})

M.append({
 "id": "BP3-CORPUS", "band": "BUILD", "class": "build", "tier": "reasoning",
 "name": "Corpus seed from probe truth: merge worksheet (D1.2), scatterinstances parm surface JSON (D1.4), promotion proposal ratified:false (D1.3), open-question ledger (D1.6) - plus a checker that reddens any promotion without an anchor",
 "note": "Tier: reasoning. Self-cap: 25 turns (progress every 5). Blocked until BP3-PROBE's stdout finding. Rule D-1: you PROPOSE promotions, you never flip a tier in any corpus file; the only new corpus artifact you write is the scatterinstances parm JSON (a seed, provenance-stamped). If RECON reported dossier_in_repo:false, build the worksheet rows from the blueprint's claim-ID pointers (sec.1.2, sec.1.4, sec.2.3, sec.7) and say so in the doc header. Token-saver: read stdout.txt by grep and line ranges, never whole.",
 "targets": [
  "T1) D1.2 worksheet: docs/reviews/bp3-h22-merge-worksheet.md - one row per blueprint V0 claim touched by P-1..P-9 (sec.1.2 list, sec.1.4 candidates, the Image Filter / Texture Material Library / Render Pass type names, scatter menus from P-9, equiangular toggle from P-4, mtlxflake3d from P-8): status = named(<type or parm>) | UNKNOWN-AFTER-PROBE | BLOCKED(<probe id>), anchor = stdout.txt:line.",
  "T2) D1.4 parm surface: <notes_dir>/scatterinstances_parms_<build>.json = {build, probe_stdout_path, generated_at, rows:[{folder,name,label}]} from the P-5 block; row count must equal the P-5 rows in stdout.",
  "T3) D1.3 promotion proposal: docs/reviews/bp3-h22-promotion-proposal.md, header `ratified: false`; table `claim id | current tier | proposed tier | anchor`; VERIFIED-RUNTIME only where a stdout line proves it; blueprint sec.2.3 WL-* rows go DOC-STATED -> FIXTURE-VERIFIED only where B-1..B-4 confirm on the fixture; every other row stays put. Write harness/battleplan/notes/bp3_promotion_check.py (plain Python, no deps): exits 1 if any row proposing VERIFIED-RUNTIME or FIXTURE-VERIFIED has an anchor that does not grep in stdout.txt. Run it; paste the exit code in the receipt.",
  "T4) D1.6 open questions: append to the promotion doc a table for blueprint sec.8 items 1-5 and sec.5 tensions RECON listed: answered(anchor) | unanswered(blocked by <probe/gui>)."
 ],
 "touches": ["docs/reviews/bp3-h22-merge-worksheet.md", "docs/reviews/bp3-h22-promotion-proposal.md", "harness/notes/scatterinstances_parms_*.json", "harness/battleplan/notes/bp3_promotion_check.py"],
 "readonly": False, "deps": ["BP3-PROBE"],
 "crucible_criteria": ["the crucible runs bp3_promotion_check.py itself, then mutates: strip one anchor; promote a claim whose probe is BLOCKED; change a tier on a row with no artifact - each must exit 1", "parm JSON row count == P-5 row count counted by the crucible from stdout.txt"] + STD_CRUX[1:3],
 "spawn_classes": [],
 "source": {"doc": SRC, "anchor": "v0.3 sec.1.3 D1.2/D1.3/D1.4/D1.6; sec.6 step 6-7; rule D-1"},
 "acceptance": [
  {"predicate": "promotion proposal: every VERIFIED-RUNTIME / FIXTURE-VERIFIED row has a stdout anchor; bp3_promotion_check.py exit 0 on the committed doc", "evidence": "test"},
  {"predicate": "scatterinstances_parms_<build>.json row count equals the P-5 block row count", "evidence": "check"},
  {"predicate": "worksheet: every row has a status and an anchor or a BLOCKED probe id", "evidence": "check"},
 ],
})

M.append({
 "id": "BP3-STUBS", "band": "BUILD", "class": "build", "tier": "reasoning",
 "name": "Scaffold, not implement: three NEW_MCP_TOOL candidates as signatures + preconditions (D1.5); spatial lane entry as an UNAPPLIED diff (D3.1); world_manifest schema homed + example manifest that validates (D3.2)",
 "note": "Tier: reasoning. Self-cap: 20 turns (progress every 5). Blocked until BP3-RECON's finding (schema_home, notes_dir, authoring_domains.json path). Reads BP3-PROBE's finding if present but does not wait for it. Nothing you write is registered, imported by mcp_server, or applied: the lane is ratified:false and the tools are signatures. Mirror an existing tool's signature shape from mcp_tools_render.py / mcp_tools_usd.py so the stubs read like the house style. Rule D-3: the blueprint gains no scope; the only blueprint edit allowed is the sidecar path line if the schema moves.",
 "targets": [
  "T1) D1.5: docs/intake/h22-tool-candidates-<yyyy-mm-dd>.md - for synapse_author_light_blocker, synapse_author_image_filters, synapse_author_render_pass_chain: signature (name, params with types/defaults), preconditions from blueprint sec.1.4 (Karma delegate; Husk raster product; husk --pass present; one product per file), the exact refusal/warning text SYNAPSE returns when a precondition fails, source claim IDs, and 'implementation: none (D1.5)'. Add the two RECIPE_CHANGE rows (scatter recipe, textured material) as 'change proposal' entries with the parm-name dependency on P-5/P-2.",
  "T2) D3.1: harness/battleplan/notes/BP3_lane_spatial.diff - a unified diff against the reconciled authoring_domains.json adding the sec.3.2 lane entry verbatim (ratified:false, non_goals verbatim). `git apply --check` must pass; the diff is NOT applied. If authoring_domains.json does not exist, write the entry as BP3_lane_spatial.proposed.json and say so.",
  "T3) D3.2: move docs/intake/world_manifest.schema.json to RECON's schema_home (git mv; if schema_home is none, leave it and record that). Validate: `python -c \"import json; json.load(open(p))\"` at minimum; `jsonschema` if importable. Write docs/intake/world_manifest.example.json - a fixture-shaped instance (world.source=fixture, frame.native=marble_raw_opencv, applied flags false, provenance.probes from PROBE's finding if available else []) that validates against the schema; paste the validation command + result in the receipt.",
  "T4) If the schema moved, edit ONLY the 'Sidecars' line of docs/intake/blueprint-h22-worldlabs-intent.md to the new path. No other blueprint edit."
 ],
 "touches": ["docs/intake/h22-tool-candidates-*.md", "harness/battleplan/notes/BP3_lane_spatial.diff", "harness/battleplan/notes/BP3_lane_spatial.proposed.json", "docs/intake/world_manifest.schema.json", "docs/intake/world_manifest.example.json", "docs/intake/blueprint-h22-worldlabs-intent.md"],
 "readonly": False, "deps": ["BP3-RECON"],
 "crucible_criteria": ["grep mcp_server.py and every mcp_tools_*.py on the branch for the three tool names - zero hits", "authoring_domains.json byte-identical to master on the branch (diff not applied)", "mutations: remove `required` from the schema -> example validation must change outcome; add a body to a stub -> a 'no implementation' checker or the crucible's grep reddens; apply the diff -> authoring_domains differs from master -> red"] + STD_CRUX[1:2],
 "spawn_classes": [],
 "source": {"doc": SRC, "anchor": "v0.3 sec.1.3 D1.5; sec.3.7 D3.1/D3.2; sec.3.2 lane declaration; rule D-3"},
 "acceptance": [
  {"predicate": "three candidates each with signature, preconditions, refusal text, claim IDs, implementation: none", "evidence": "check"},
  {"predicate": "BP3_lane_spatial.diff passes `git apply --check` and authoring_domains.json is unchanged vs master", "evidence": "check"},
  {"predicate": "world_manifest.example.json validates against the schema (command + result in receipt)", "evidence": "test"},
 ],
})

M.append({
 "id": "BP3-PANEL", "band": "BUILD", "class": "build", "tier": "reasoning",
 "name": "Design-system pass on the SYNAPSE Python panel: audit (tokens, spacing scale, naming, typography) then a whitespace-and-token-only change set traceable row-by-row to the audit; no new widgets, no behaviour",
 "note": "Tier: reasoning. Self-cap: 20 turns (progress every 5) - this is the roadmap's 2h timebox; at 80% post wrap_up and ship what is clean. You own python/synapse/panel/ this wave (designsystem/, manifests/, qss, layout modules). synapse_panel.py lifecycle and timer ranges are untouchable (BP2-CRUX rule). Continue from the accepted result: read the BP2-PANELDESIGN receipt and `git log master -- python/synapse/panel/` first; do not re-derive what landed. Design-system audit shape: Summary (components reviewed, issues, score) / Naming Consistency / Token Coverage (colors, spacing, typography: defined vs hardcoded instances) / Component Completeness (states, variants, docs) / Priority Actions. Reference rhythm: docs/PANEL_RHYTHM_SPEC.md; design review: docs/SYNAPSE_PANEL_DESIGN_REVIEW_H22_LENS.md.",
 "targets": [
  "T1) Read first: harness/notes/receipts/BP2-PANELDESIGN.json, docs/PANEL_RHYTHM_SPEC.md, docs/SYNAPSE_PANEL_DESIGN_REVIEW_H22_LENS.md, `git log --oneline -15 master -- python/synapse/panel/`. Post a bus claim on python/synapse/panel/ before any edit.",
  "T2) Audit (read-only): harness/battleplan/notes/BP3_PANEL_AUDIT.md in the design-system audit shape. Token Coverage table must count hardcoded px/pt/hex/rgb/font-size instances per file (grep, cite file:line). Naming table: token names that disagree with the rhythm spec. Component table: each panel widget class with states/variants/docs ticks. Priority Actions ranked by instances fixed per edit.",
  "T3) Change set: ONLY substitutions from the audit - hardcoded value -> existing token; off-scale spacing -> nearest rhythm-spec step; inconsistent token name -> canonical name (with every reference updated). No new widget, signal, slot, timer, import of new modules, or behaviour change. Every diff hunk cites its audit row in the commit message body.",
  "T4) Evidence: headless - the panel test target (RECON's finding or `python -m pytest tests -k panel -q`) green before and after; `git diff --stat master..HEAD -- python/synapse/panel/` lists only designsystem/manifests/qss/layout files; `git diff master..HEAD -- python/synapse/panel/synapse_panel.py` shows no line inside the lifecycle/timer functions. Visual before/after is gui_required -> UNKNOWN headless; write the exact steps for Joe to capture it."
 ],
 "touches": ["python/synapse/panel/", "harness/battleplan/notes/BP3_PANEL_AUDIT.md"],
 "readonly": False, "deps": [],
 "crucible_criteria": ["every diff hunk maps to an audit row (the crucible builds the map itself)", "mutations: re-introduce one hardcoded hex/px -> the crucible's grep-based token checker reddens; add a QWidget subclass or a new signal -> whitespace-only checker reddens; touch a timer range -> red", "panel tests green in a fresh checkout"] + STD_CRUX[2:3],
 "spawn_classes": [],
 "source": {"doc": SRC, "anchor": "roadmap P5 panel spacing pass (docs/PANEL_RHYTHM_SPEC.md); blueprint v0.3 sec.0.3 rule D-2 (verified over pretty)"},
 "acceptance": [
  {"predicate": "BP3_PANEL_AUDIT.md exists in the audit shape with file:line instances per token category", "evidence": "check"},
  {"predicate": "diff touches only designsystem/manifests/qss/layout files; synapse_panel.py lifecycle/timer ranges unchanged", "evidence": "check"},
  {"predicate": "panel test target green before and after", "evidence": "test"},
  {"predicate": "before/after screenshots show only spacing/typography/colour-token changes", "evidence": "gui_probe", "gui_required": True},
 ],
})

M.append({
 "id": "BP3-CRUX", "band": "TRUST", "class": "crucible", "tier": "referee",
 "name": "Adversarial crucible for wave BP3 - audits RECON/PROBE/CORPUS/STUBS/PANEL receipts, re-runs the probes itself, authors its own mutations, builds nothing",
 "note": "Tier: referee (claude-fable-5 via rails; if the launch falls back to reasoning the ledger row says so). Read-only. Blocked until the five builder receipts exist. A BROKEN verdict means that leg does not ride. A green CRUX receipt is a PRECONDITION for Joe's merge words, never a substitute - verdicts are READ before merge words fire. Self-cap: 25 turns (progress every 5). " + HYTHON_NOTE,
 "targets": [
  "T1) For each builder receipt: re-run every acceptance predicate independently in a fresh checkout of the leg branch; verdicts pass|fail|UNKNOWN with your own anchors, never the builder's. gui_required predicates are UNKNOWN to you - say so.",
  "T2) PROBE: run harness/probes/synapse_blueprint_probes.py yourself (own --out dir, HOUDINI_USER_PREF_DIR from RECON's finding), diff probe_results.json statuses against the builder's; recompute the fixture SHA256s; confirm `git diff master..bp3/probe -- harness/probes/` is empty.",
  "T3) CORPUS: run bp3_promotion_check.py; mutations (>= 3): strip an anchor; promote a BLOCKED probe's claim; change a tier on an artifact-less row - each must exit 1. Count P-5 rows in stdout.txt yourself and compare to the parm JSON.",
  "T4) STUBS: grep mcp_server.py + mcp_tools_*.py for the three tool names (zero hits); authoring_domains.json byte-identical to master; example manifest validates; mutations (>= 3): drop `required` from the schema; add a function body to a stub; apply the diff - each must redden.",
  "T5) PANEL: build the hunk->audit-row map yourself; mutations (>= 3): re-introduce a hardcoded hex; add a QWidget subclass; edit a timer range - each must redden; panel tests green in your checkout.",
  "T6) RECON: Test-Path every 'actual path' row (true) and every 'no match' row (false).",
  "T7) Verdict per leg: SOUND | SOUND-WITH-NITS | BROKEN with chain_broken_at named. Write harness/battleplan/notes/BP3-CRUX_verdicts.md and BP3-CRUX_mutations.json. Post each verdict on the bus addressed to *. Write harness/notes/h22wl/BP3_CRUX_LANDED.flag LAST."
 ],
 "touches": [], "readonly": True,
 "deps": ["BP3-RECON", "BP3-PROBE", "BP3-CORPUS", "BP3-STUBS", "BP3-PANEL"],
 "crucible_criteria": STD_CRUX,
 "spawn_classes": [],
 "source": {"doc": SRC, "anchor": "v0.3 rule D-1 two keys; docs/BATTLEPLAN.md sec.12 R-5/R-6 crucible precedent"},
 "acceptance": [
  {"predicate": "one verdict per builder leg (five), each with independently re-run acceptance rows and the crucible's own anchors", "evidence": "receipt"},
  {"predicate": ">= 3 self-authored mutations per builder leg with a product (CORPUS, STUBS, PANEL), each named with the check it reddens (BP3-CRUX_mutations.json)", "evidence": "test"},
  {"predicate": "probe script re-run by the crucible with its own artifact; statuses diffed against the builder's; hashes recomputed", "evidence": "probe"},
 ],
})

M.append({
 "id": "BP3-TIDY", "band": "TRUST", "class": "tidy", "tier": "mechanical",
 "name": "House cleaning, proposal-only: worktree census with prune commands (unusable-only standard), receipt-order and named-file-commit checks on every BP3 leg, UNKNOWN-discipline grep, docs/ scratch census - removes nothing",
 "note": "Tier: mechanical (Haiku 4.5). Read-only by design: you PROPOSE every removal with an exact command and the evidence triple (merged into master? worktree clean? usable?); Joe or the CTO runs the prune. 'Unusable only' is the prune standard, not 'clean'. Runs after BP3-CRUX so nothing you read is moving. Self-cap: 12 turns (progress every 4).",
 "targets": [
  "T1) Worktree census: for every row of `git worktree list` - branch, HEAD, merged into master (git branch --merged), dirty (git -C <wt> status --short count), usable (dir exists, HEAD resolves), proposed action + exact `git worktree remove <path>` / `git branch -d <branch>` command ONLY when merged AND clean AND (unusable OR older than the BP2 merge); otherwise 'keep' with the reason. bp2/nits is BROKEN-carried: keep, say so.",
  "T2) Receipt order: for each BP3 leg branch with a receipt, verify the receipt's stated product HEAD sha exists on the branch before the receipt commit (CRX0 / W5H); verify no `git add -A` footprint (no unrelated files in the branch diff vs master); list violations with shas.",
  "T3) UNKNOWN discipline: grep BP3 review docs and receipts for numeric zeros or 'pass' on rows whose probe status is BLOCKED or gui_required; list hits with file:line.",
  "T4) docs/ scratch census: count *.txt probe scratch files at docs/ root (the cop_*/copnet_*/_apex_* family), total bytes, newest/oldest mtime; propose `git mv` to docs/scratch/<yyyy-mm>/ as ONE command list; touch nothing.",
  "T5) Write harness/battleplan/notes/BP3_TIDY.md with the four tables; post one bus finding with the path."
 ],
 "touches": [], "readonly": True, "deps": ["BP3-CRUX"],
 "crucible_criteria": ["every proposed prune row carries the merged/clean/usable evidence triple with the command that produced it", "the leg's branch diff vs master contains only BP3_TIDY.md and its receipt"] + STD_CRUX[1:2],
 "spawn_classes": [],
 "source": {"doc": SRC, "anchor": "v0.3 rule D-4 dependency hygiene; harness constitution: unusable-only prune standard, commit-before-receipt, named-file commits"},
 "acceptance": [
  {"predicate": "worktree table row count equals `git worktree list` row count; each row has the evidence triple", "evidence": "check"},
  {"predicate": "receipt-order check row per BP3 leg with shas", "evidence": "check"},
  {"predicate": "no file removed or moved by this leg (branch diff = notes + receipt only)", "evidence": "check"},
 ],
})

M.append({
 "id": "BP3-SPATIAL", "band": "BUILD", "class": "build", "tier": "reasoning",
 "name": "Mile 2 (HELD until Joe's word after CRUX): implement the three read-only spatial query tools on the fixture component (D3.3/D3.4) - unregistered, tested, timed; no authoring",
 "note": "Tier: reasoning. Self-cap: 30 turns (progress every 5). HELD in the manifest; flips ready on Joe's word after BP3-CRUX verdicts are read (blueprint sec.5 gate check). Consumes PROBE's b6_wl_component.usdc + stdout numbers and STUBS' schema/example. Rule D-1: tools stay unregistered (no mcp_server import, or behind a flag defaulting off) because the lane is ratified:false. D-DEP-03: use pxr or hou to match RECON's spatial_helpers finding; say which.",
 "targets": [
  "T1) Implement synapse_spatial_describe, synapse_spatial_classify (max_angle_deg default = the scatter Up Axis mask default from P-5), synapse_spatial_frustum in the reconciled module home (RECON's finding; else python/synapse/spatial/ with a note). Read-only: no prim authored, no file written by the tools.",
  "T2) Tests on PROBE's b6_wl_component.usdc: describe bounds == B-3 bbox within 1e-3; classify floor fraction covers the lane, walls present on both sides (sign of x), dominant floor height == S-2 dominant bin within the bin width; frustum count == S-3 count within 2% for the same eye/fov. Each call timed; < 5 s on the collider, recorded in docs/reviews/bp3-spatial-lane-probes-<date>.md.",
  "T3) D3.4: run the three tools on one existing SYNAPSE test stage (fixtures/solaris.basic.json or RECON's pick) without code change; record outputs.",
  "T4) Do not register. If the house style requires a registry entry, add it behind SYNAPSE_SPATIAL_LANE=1 defaulting off, and cite the line."
 ],
 "touches": ["python/synapse/spatial/", "tests/test_spatial_lane.py", "docs/reviews/bp3-spatial-lane-probes-*.md"],
 "readonly": False, "deps": ["BP3-PROBE", "BP3-STUBS"],
 "crucible_criteria": ["correctness anchors are PROBE's stdout numbers, re-read by the crucible", "timing lines present per call", "registry off: grep shows no default-on registration"] + STD_CRUX[1:3],
 "spawn_classes": [],
 "source": {"doc": SRC, "anchor": "v0.3 sec.3.4 tools; sec.3.7 D3.3/D3.4; sec.5 Mile 2; rule D-1"},
 "acceptance": [
  {"predicate": "three tools return correct answers on the fixture per T2 tolerances", "evidence": "test"},
  {"predicate": "each call < 5 s on the 200k-tri collider, recorded", "evidence": "probe"},
  {"predicate": "tools run on a second stage without code change (D3.4)", "evidence": "test"},
  {"predicate": "no default-on registration in mcp_server / tool registries", "evidence": "check"},
 ],
})

# ---- write missions
for m in M:
    (AF / "missions" / f"{m['id']}.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"wrote {len(M)} missions")

# ---- neutralise the BP2 territory paragraph in the shared template (wave-neutral; each mission's note/touches carry territory)
tpl = AF / "prompts" / "_template.md"
t = tpl.read_text(encoding="utf-8")
t2, n = re.subn(r"BP2 territory:.*?measured ledger\.", "Territory for THIS wave: each mission's `touches` is its writable surface and its `note` names ownership; anything outside your `touches` is read-only to you. Consumption is VIA THE BUS the moment a peer posts an artifact path.", t, flags=re.S)
if n:
    tpl.write_text(t2, encoding="utf-8"); print("template territory paragraph made wave-neutral")
else:
    print("template: BP2 territory paragraph not found (already neutral?)")

# ---- clone per-wave files bp2 -> bp3
def clone(src, dst, extra=None):
    s = (AF / src).read_text(encoding="utf-8").replace("bp2", "bp3").replace("BP2", "BP3")
    if extra: s = extra(s)
    (AF / dst).write_text(s, encoding="utf-8"); print("cloned", dst)

def manifest_patch(s):
    s = s.replace("HELD = {}", "HELD = {\"BP3-SPATIAL\": \"Mile 2 - flips ready on Joe's word after BP3-CRUX verdicts are read (blueprint sec.5 gate check)\"}")
    s = s.replace("(pairs 1+2: METER || PANELTRUTH, LATENCY || STORE; PANELDESIGN held; ",
                  "(RECON -> PROBE -> CORPUS; STUBS after RECON; PANEL independent; CRUX after the five; TIDY after CRUX; SPATIAL held; ")
    return s
clone("build_manifest_bp2.py", "build_manifest_bp3.py", manifest_patch)
clone("arm_bp2.ps1", "arm_bp3.ps1", lambda s: s.replace("param([string]$Budget = '10turns')", "param([string]$Budget = '12turns')"))
for f in ("dashboard_bp2.py", "status_bp2.py", "watch_bp2.ps1"):
    clone(f, f.replace("bp2", "bp3"))

# ---- compile -> control -> manifest
def run(*args):
    r = subprocess.run([sys.executable] + list(args), cwd=str(AF), capture_output=True, text=True)
    print(f"$ {' '.join(args)}\n{r.stdout}{r.stderr}"); return r.returncode
rc = run("compile_wave.py", "bp3")
rc |= run("make_control.py", "bp3")
rc |= run("build_manifest_bp3.py")
sys.exit(rc)
