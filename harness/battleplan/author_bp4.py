# author_bp4.py - CTO seat (Fable 5.1), 2026-09-03 evening. Authors wave BP4 = BP3 closing + Joe's two new asks.
# Writes missions/BP4-*.json, clones the per-wave bp3 files to bp4 (HELD emptied, effort max, budget with a token
# ceiling), then runs compile_wave -> make_control -> build_manifest_bp4. Same shape as author_bp3.py on purpose.
# Authoring is CTO-delegated. ARM ("go batch", enumerated eight legs incl. SPATIAL) / merge / push are Joe's words.
import json, re, subprocess, sys
from pathlib import Path

AF = Path(r"C:\Users\User\SYNAPSE\harness\battleplan")
REPO = AF.parents[1]
SRC = "docs/intake/blueprint-h22-worldlabs-intent.md"
SKILLS = "harness/battleplan/notes/skills/"
STD_CRUX = [
    "the crucible trusts no builder's proved_it_bites - it authors its own mutations",
    "every verdict row carries the crucible's own anchor",
    "a leg with any UNKNOWN acceptance is at best SOUND-WITH-NITS, never SOUND",
    "the crucible flips no contract feature and edits no product file",
]
HYTHON_NOTE = ("Environment truths (capsule 2026-09-03, demonstrated): five hythons are installed and SYNAPSE_HYTHON must be pinned to 22.0.400 "
               "(22.0.429 fails the hytest usability gate); the hython path and the pref dir are recorded in harness/battleplan/notes/BP3_RECON.md T2 - read them, never re-derive; "
               "H22 prefs live at C:\\Users\\User\\OneDrive\\Documents\\houdini22.0 (OneDrive known-folder redirect) - set HOUDINI_USER_PREF_DIR explicitly; "
               "long hython runs: detach and poll a log file, never foreground-wait past 4 minutes; a fresh deep-path clone needs `git config core.longpaths true`.")
FENCE_NOTE = ("Permission fence: your settings profile allows scoped `git add` + `git commit`; push/merge/checkout/reset are denied; "
              "use `cd <path> && git status --short`, never `git -C` (unmatched by the allow patterns, the command would stall). Commit product files BEFORE the receipt; the receipt is your final write.")

M = []

M.append({
 "id": "BP4-INTAKE", "band": "BUILD", "class": "build", "tier": "mechanical",
 "name": "Intake drop: home the World Labs blueprint + coffee-notes source docs under docs/intake/src/, hash them, link them from blueprint v0.3's header - RECON's dossier_in_repo:false becomes true by artifact",
 "note": "Tier: mechanical (Haiku 4.5). Self-cap: 10 turns (progress every 3). Joe drops up to four files into docs/intake/src/ before arm: synapse_worldlabs_blueprint.docx, synapse_worldlabs_coffee_shop_talk.docx, and their .md extractions (CTO-side pandoc). If a .md is absent but its .docx is present, extract it yourself with python zipfile (word/document.xml: <w:p> paragraphs, <w:t> runs, Heading1/Heading2 pStyle -> # / ##) and name the tool in the manifest. If BOTH docx are absent at your start, poll docs/intake/src/ with one powershell loop (Start-Sleep 60, at most 20 iterations); still absent -> bus finding 'intake files missing' and a receipt with every acceptance UNKNOWN - never fabricate content. Token-saver: read the .md by headings (grep '^#'), not whole. " + FENCE_NOTE,
 "targets": [
  "T1) docs/intake/src/MANIFEST.md: table `file | bytes | sha256 | role (source-docx | extracted-md) | extraction tool (pandoc CTO-side | zipfile leg-side | n/a)` for every file present; a 'missing' row for any of the four that is not.",
  "T2) Edit ONLY the header block of docs/intake/blueprint-h22-worldlabs-intent.md: add one `Sources:` line naming the files under docs/intake/src/ (relative paths) and MANIFEST.md. No other edit (rule D-3: the blueprint gains no scope).",
  "T3) Cross-check: grep the intent doc for 'dossier|coffee' claim pointers; for each, confirm the cited section exists in the extracted .md by heading; append table `pointer (file:line) | cited section | found (heading) or not found` to MANIFEST.md.",
  "T4) Post one bus finding to *: {\"claim\": \"dossier_in_repo: true|partial|false\", \"anchor\": \"docs/intake/src/MANIFEST.md\"}. Then commit the named files and write the receipt."
 ],
 "touches": ["docs/intake/src/", "docs/intake/blueprint-h22-worldlabs-intent.md"],
 "readonly": False, "deps": [],
 "crucible_criteria": ["the crucible recomputes SHA256 + bytes for every file under docs/intake/src/ and diffs against MANIFEST.md", "`git diff master..HEAD -- docs/intake/blueprint-h22-worldlabs-intent.md` is one hunk inside the header block (the crucible reads the hunk's line range)"] + STD_CRUX[1:2],
 "spawn_classes": [],
 "source": {"doc": SRC, "anchor": "capsule 2026-09-03 EOD open item 4 (dossier + coffee notes into docs/intake/); BP3-RECON T4 dossier_in_repo:false"},
 "acceptance": [
  {"predicate": "MANIFEST.md has a row per present file with bytes + sha256 + role, and a 'missing' row per absent one", "evidence": "check"},
  {"predicate": "blueprint header gained exactly one Sources line; the diff vs master is confined to the header block", "evidence": "check"},
  {"predicate": "bus finding posted with dossier_in_repo value and MANIFEST anchor", "evidence": "receipt"},
 ],
})

M.append({
 "id": "BP4-RULINGS", "band": "TRUTH", "class": "truth", "tier": "mechanical",
 "name": "Compile the banked BP3 ruling items into one cold-ruling table for the CTO seat: every for_ruling entry from the seven BP3 receipts (+ CRUX verdicts) with claim, anchor, the receipt's own recommendation, ruling column PENDING - the leg extracts, it never rules",
 "note": "Tier: mechanical (Haiku 4.5). Self-cap: 12 turns (progress every 4). Expected 22 items (RECON 3, PANEL 1, PROBE 5, CORPUS 7, STUBS 2, CRUX 1, TIDY 3 per capsule 09-03); a different count is a FINDING you report with the file you looked in, never a rounding. Sources: harness/notes/receipts/BP3-*.json `for_ruling` arrays (also scan `banked`, `open`, `for_joe` keys if present); harness/battleplan/notes/BP3-CRUX_verdicts.md; harness/battleplan/notes/BP3_TIDY.md. Token-saver: `python -c` to load each receipt and print only its ruling arrays; grep the verdicts for 'ruling'. Shape reference: harness/notes/CTO_RULINGS_01.md (read its first 40 lines only). " + FENCE_NOTE,
 "targets": [
  "T1) harness/notes/CTO_RULINGS_BP3.md: table `# | leg | item id | severity | claim (verbatim) | anchor | receipt recommendation (verbatim or 'none stated') | CTO ruling | ratification (Joe) yes/no`; every CTO ruling cell = PENDING; ratification = yes when the item would flip a ratified contract, a corpus tier, a manifest HELD state, or a settings fence.",
  "T2) Section 'Capsule recommendations': the CTO recommendations already in the capsule (M-1 schema stays docs/intake; M-2 pin hython 22.0.400 now; D-DEP-03 hou; PANEL narrow scope accepted, spawns held; TIDY-R1 T1 merged status = UNKNOWN) each mapped to its row number, or 'no matching row' with the search you ran.",
  "T3) Count line: `rows: N (expected 22; per leg: RECON a, PANEL b, PROBE c, CORPUS d, STUBS e, CRUX f, TIDY g)`; if N != 22 list the delta per leg with the file inspected.",
  "T4) Post one bus finding to *: {\"claim\": \"rulings table compiled: N rows\", \"anchor\": \"harness/notes/CTO_RULINGS_BP3.md\"}. Commit the named file, then the receipt."
 ],
 "touches": ["harness/notes/CTO_RULINGS_BP3.md"],
 "readonly": False, "deps": [],
 "crucible_criteria": ["the crucible re-counts ruling entries across the seven receipts + verdicts itself and compares to the table's count line", "every claim cell greps verbatim in its source file (the crucible samples every row)", "no ruling cell filled by the leg (all PENDING)"] + STD_CRUX[1:2],
 "spawn_classes": [],
 "source": {"doc": SRC, "anchor": "capsule 2026-09-03 EOD open item 1 (rule the 22 banked items cold; record in harness/notes/CTO_RULINGS_*.md)"},
 "acceptance": [
  {"predicate": "table row count equals the for_ruling total the crucible recounts; count line present", "evidence": "check"},
  {"predicate": "every row has claim + anchor + recommendation cells; every ruling cell is PENDING", "evidence": "check"},
  {"predicate": "bus finding posted with the row count and the file anchor", "evidence": "receipt"},
 ],
})

M.append({
 "id": "BP4-B7FIX", "band": "BUILD", "class": "build", "tier": "reasoning",
 "name": "Fix probe bug B-7 in harness/probes/synapse_blueprint_probes.py (camera assigned to the render settings + a light authored BEFORE rop.render), re-run B-7 only on hython 22.0.400, then and only then settle D2.4 / R-1 - pass, fail, or UNKNOWN with the new evidence",
 "note": "Tier: reasoning. Self-cap: 25 turns (progress every 5). BP3 truth (capsule 09-03): the D2.4 black EXR is a PROBE BUG, not a Karma verdict - the camera was created after the render settings and never assigned; husk reported Total Lights 0 and a camera-name mismatch. Read docs/reviews/bp3-h22-worldlabs-probes-2026-09-03.md first (B-7 row, husk lines), then harness/notes/h22wl/bp3_probes/stdout.txt by grep only. Fixture paths + SHA256 are in the review doc (ignored binaries); a missing fixture is re-downloaded per BP3-PROBE T1 and re-hashed - a hash mismatch is a finding. The diff to the probe script is the B-7 block plus a `--only <probe-id>` flag if the script lacks one; no other probe's logic changes. " + HYTHON_NOTE + " " + FENCE_NOTE,
 "targets": [
  "T1) B-7 fix: author the camera prim AND a light (dome or distant) before the render settings; set the render settings' camera relationship to the camera path; keep the existing resolution; minimal diff. Add `--only <id>` if absent (skipped probes read NOT_RUN in probe_results.json).",
  "T2) Run detached + polled with SYNAPSE_HYTHON pinned to 22.0.400 and HOUDINI_USER_PREF_DIR set: `hython harness\\probes\\synapse_blueprint_probes.py --only B-7 --ply <ply> --glb <glb> --out harness\\notes\\h22wl\\bp4_b7fix`; stdout verbatim to stdout.txt; capture husk's own log (Total Lights, camera lines) into the out dir.",
  "T3) EXR stats: mean/max pixel via oiiotool if on PATH, else hython (COP read or hou image API), else UNKNOWN naming the missing tool; record the exact command + numbers. Non-black -> D2.4 pass candidate; still black -> fail with the new husk lines quoted.",
  "T4) Append a dated 'B-7 re-run (BP4)' section to docs/reviews/bp3-h22-worldlabs-probes-2026-09-03.md (append-only; BP3 rows untouched): fix summary, `git diff --stat`, stdout anchor, EXR stats, D2.4 verdict pass|fail|UNKNOWN, R-1 status triggered|clear|UNKNOWN, each with anchor. Post a bus finding with the verdict + anchor, commit the named files, then the receipt."
 ],
 "touches": ["harness/probes/synapse_blueprint_probes.py", "harness/notes/h22wl/bp4_b7fix/", "docs/reviews/bp3-h22-worldlabs-probes-2026-09-03.md"],
 "readonly": False, "deps": [],
 "crucible_criteria": ["the crucible re-runs `--only B-7` itself in a fresh checkout with its own out dir and recomputes the EXR stats", "`git diff master..HEAD -- harness/probes/synapse_blueprint_probes.py` touches only the B-7 block and the --only plumbing (the crucible reads every hunk)", "the review doc's BP3 rows are byte-identical to master (append-only, checked by diff line ranges)"] + STD_CRUX[2:3],
 "spawn_classes": [],
 "source": {"doc": SRC, "anchor": "capsule 2026-09-03 EOD open item 2 (fix B-7 before ruling R-1 / D2.4); blueprint v0.3 sec.2.8 D2.4; sec.10 R-1"},
 "acceptance": [
  {"predicate": "probe-script diff limited to the B-7 block + --only plumbing", "evidence": "check"},
  {"predicate": "bp4_b7fix/stdout.txt exists with the hython build line (22.0.400) and the B-7 block", "evidence": "probe"},
  {"predicate": "EXR stats recorded with the command; D2.4 verdict pass|fail|UNKNOWN with anchor", "evidence": "receipt"},
  {"predicate": "R-1 status stated (triggered|clear|UNKNOWN) with anchor in the appended section", "evidence": "check"},
 ],
})

M.append({
 "id": "BP4-SPATIAL", "band": "BUILD", "class": "build", "tier": "reasoning",
 "name": "Mile 2: implement the three read-only spatial query tools on the fixture component (D3.3/D3.4) - unregistered, tested, timed; no authoring (re-homed from the held BP3-SPATIAL; armed by Joe's enumerated 'go batch')",
 "note": "Tier: reasoning. Self-cap: 30 turns (progress every 5). Supersedes BP3-SPATIAL (held in bp3.live.json; its deps PROBE + STUBS are merged on master). Inputs on master: PROBE's b6_wl_component.usdc + stdout under harness/notes/h22wl/bp3_probes/ (numbers B-3 bbox, S-2 dominant bin, S-3 count), STUBS' docs/intake/world_manifest.schema.json + example, BP3_RECON.md spatial_helpers. BP3 truth: the fixture collider is 46,993 tris (not the blueprint's 200k) - the timing predicate is on the collider as it is. Rule D-1: tools stay unregistered (no mcp_server import, or behind SYNAPSE_SPATIAL_LANE=1 defaulting off) because the lane is ratified:false. D-DEP-03: use pxr or hou to match RECON's spatial_helpers finding; say which. " + HYTHON_NOTE + " " + FENCE_NOTE,
 "targets": [
  "T1) Implement synapse_spatial_describe, synapse_spatial_classify (max_angle_deg default = the scatter Up Axis mask default from P-5), synapse_spatial_frustum in the reconciled module home (RECON's finding; else python/synapse/spatial/ with a note). Read-only: no prim authored, no file written by the tools.",
  "T2) Tests on PROBE's b6_wl_component.usdc: describe bounds == B-3 bbox within 1e-3; classify floor fraction covers the lane, walls present on both sides (sign of x), dominant floor height == S-2 dominant bin within the bin width; frustum count == S-3 count within 2% for the same eye/fov. Each call timed; < 5 s on the fixture collider, recorded in docs/reviews/bp4-spatial-lane-probes-<date>.md.",
  "T3) D3.4: run the three tools on one existing SYNAPSE test stage (fixtures/solaris.basic.json or RECON's pick) without code change; record outputs.",
  "T4) Do not register. If the house style requires a registry entry, add it behind SYNAPSE_SPATIAL_LANE=1 defaulting off, and cite the line. Post a bus finding with the review doc path, commit the named files, then the receipt."
 ],
 "touches": ["python/synapse/spatial/", "tests/test_spatial_lane.py", "docs/reviews/bp4-spatial-lane-probes-*.md"],
 "readonly": False, "deps": [],
 "crucible_criteria": ["correctness anchors are PROBE's stdout numbers, re-read by the crucible", "timing lines present per call; the crucible re-runs the tests and timings in a fresh checkout", "registry off: grep shows no default-on registration"] + STD_CRUX[1:3],
 "spawn_classes": [],
 "source": {"doc": SRC, "anchor": "v0.3 sec.3.4 tools; sec.3.7 D3.3/D3.4; sec.5 Mile 2; rule D-1; capsule 2026-09-03 EOD open item 3 (SPATIAL flip)"},
 "acceptance": [
  {"predicate": "three tools return correct answers on the fixture per T2 tolerances", "evidence": "test"},
  {"predicate": "each call < 5 s on the fixture collider (46,993 tris), recorded", "evidence": "probe"},
  {"predicate": "tools run on a second stage without code change (D3.4)", "evidence": "test"},
  {"predicate": "no default-on registration in mcp_server / tool registries", "evidence": "check"},
 ],
})

M.append({
 "id": "BP4-PANELFONT", "band": "BUILD", "class": "build", "tier": "reasoning",
 "name": "Typography pass on the SYNAPSE Python panel: one font-family token, one type scale, every size a token, floor = the MEASURED Houdini default UI font size; substitution-only change set traceable to a design-system audit; no new widgets, no behaviour",
 "note": "Tier: reasoning. Self-cap: 30 turns (progress every 5); at 80% post wrap_up and ship what is clean. Audit shape: " + SKILLS + "design-system.md (shipped skill text). Continue from the accepted result: BP3-PANEL landed the token audit (harness/battleplan/notes/BP3_PANEL_AUDIT.md: tokens 8.5/10, adoption 3.5/10; 492 px, 168 hex across 34 modules) and its whitespace/token change set; held spawns BP3-INLINE-HEX / BP3-STYLES-MIGRATE stay held - you do typography only. synapse_panel.py lifecycle and timer ranges are untouchable (BP2-CRUX rule). BP3 truth: the stylesheet is byte-identical across the 5 scales it is generated at; after your change it may differ by size tokens only - say which. Houdini default: MEASURE, never recall. hython has no Qt app, so the family/point-size read is GUI-only: write python/synapse/panel/scripts/probe_ui_font.py (prints QApplication.instance().font().family(), .pointSize(), .pixelSize(), and hou.ui.scaledSize(1) if present) for Joe to paste into the Houdini 22.0.400 Python shell; his paste is the gui_required evidence. Until it lands, the floor is what the local H22 help cache states for the default UI font (cite file:line under C:\\Users\\User\\OneDrive\\Documents\\houdini22.0\\config\\Help\\cache) marked DOC-STATED; if the cache states nothing, the floor is UNKNOWN and the change set makes no size smaller than the smallest size already shipped on master (say so). The floor lives as ONE constant in the token module with a provenance string. " + FENCE_NOTE,
 "targets": [
  "T1) Read first: BP3_PANEL_AUDIT.md, docs/PANEL_RHYTHM_SPEC.md, python/synapse/panel/designsystem/ (tokens, qss.py), `git log --oneline -10 master -- python/synapse/panel/`. Post a bus claim on python/synapse/panel/ before any edit.",
  "T2) Typography audit -> harness/battleplan/notes/BP4_PANELFONT_AUDIT.md in the shipped audit shape, typography rows only: every font-family / font-size / font-weight / line-height occurrence per file (grep, file:line) grouped by value; the smallest size on master; existing typography tokens; the Houdini default with provenance (measured | DOC-STATED | UNKNOWN).",
  "T3) Tokens: one family token (the Houdini family if measured, else the family Houdini's own prefs/QSS name with citation, else the panel's current majority family - provenance stated); a type scale of at most 5 sizes named by role (the rhythm spec's names if it has them), floor = the Houdini default; weight tokens 400/500/600 at most; line-height tokens. Land them where the existing colour/spacing tokens live.",
  "T4) Change set: substitution only - each hardcoded typography value -> its token; sizes below the floor -> floor; families -> the family token. No new widget/signal/slot/timer/import/behaviour. Every hunk cites its audit row in the commit body. Evidence: `python -m pytest tests -k panel -q` green before and after; the 5-scale stylesheet check re-run (identical, or size-token-only diff, stated); `git diff --stat master..HEAD -- python/synapse/panel/` lists designsystem/manifests/qss/layout/scripts files only; synapse_panel.py lifecycle/timer ranges unchanged. Add tests/test_panel_typography.py: no typography literal outside the token module; no size token below the floor constant.",
  "T5) Last section of the audit doc: Joe-hands steps (paste probe_ui_font.py output; before/after screenshots at 100% and 150% UI scale). Post a bus finding with the audit path, commit the named files, then the receipt."
 ],
 "touches": ["python/synapse/panel/", "tests/test_panel_typography.py", "harness/battleplan/notes/BP4_PANELFONT_AUDIT.md"],
 "readonly": False, "deps": [],
 "crucible_criteria": ["the crucible greps the branch for any remaining hardcoded font-size/font-family/font-weight/line-height outside the token module and lists file:line", "mutations: re-introduce one hardcoded px size -> test_panel_typography reddens; set one size token below the floor -> reddens; add a QWidget subclass -> the whitespace-only checker reddens", "panel tests green in a fresh checkout; the 5-scale stylesheet check re-run by the crucible"] + STD_CRUX[2:3],
 "spawn_classes": [],
 "source": {"doc": SRC, "anchor": "Joe 2026-09-03: panel fonts consistent and no smaller than the Houdini default (design-system pass); BP3-PANEL audit + held spawns; blueprint v0.3 rule D-2 verified over pretty"},
 "acceptance": [
  {"predicate": "BP4_PANELFONT_AUDIT.md has typography rows per file:line and the floor's provenance (measured | DOC-STATED | UNKNOWN)", "evidence": "check"},
  {"predicate": "token module defines family + scale + weights + line-heights; test_panel_typography finds no typography literal outside it", "evidence": "test"},
  {"predicate": "no size token below the floor constant", "evidence": "test"},
  {"predicate": "panel tests green before and after; diff limited to designsystem/manifests/qss/layout/scripts + the new test", "evidence": "test"},
  {"predicate": "probe_ui_font.py output pasted from the Houdini 22.0.400 GUI and before/after screenshots captured", "evidence": "gui_probe", "gui_required": True},
 ],
})

M.append({
 "id": "BP4-USDKNOW", "band": "BUILD", "class": "build", "tier": "reasoning",
 "name": "Scaffold USD composition knowledge for the World Labs component into SYNAPSE's knowledge layer: a LIVRPS decision record for /WL_<world_id>, a machine-readable rule seed tiered by evidence (VERIFIED needs a hython 22.0.400 anchor), and a checker that reddens unanchored promotions - ratified:false, nothing registered, engine untouched",
 "note": "Tier: reasoning. Self-cap: 30 turns (progress every 5). Vocabulary/referee: " + SKILLS + "solaris-usd-composition.md + " + SKILLS + "composition-deep-dive.md (shipped skill text; read the CTO note at the top of the deep-dive - one of its examples is wrong and left visible so you verify, not recite). Truth: pxr under hython 22.0.400. Continue from the accepted result: BP3-CORPUS's proposal + checker pattern (docs/reviews/bp3-h22-promotion-proposal.md, harness/battleplan/notes/bp3_promotion_check.py); BP3_RECON.md's path table names the LOP-knowledge home (verified_lop_solaris_knowledge_*.json) - you write the seed under harness/bench/corpus/usd/ (create if absent) and record RECON's home as the proposed final destination with an unexecuted `git mv` line. Inputs on master: PROBE's b6_wl_component.usdc (built via the SOP-side USD Create Component, 19.8 MB) + stdout under harness/notes/h22wl/bp3_probes/; blueprint sec.2-4 topology. Rule D-1: you PROPOSE (ratified:false); no edit under python/synapse/; no registry. " + HYTHON_NOTE + " " + FENCE_NOTE,
 "targets": [
  "T1) Decision record docs/reviews/bp4-usd-composition-worldlabs.md: for each choice in blueprint sec.2 + sec.4 (payload for splat and collider; purpose render/proxy; variantSet splatTier full|low; variantSet physics none|collision; kind=component; customData:worldlabs provenance; instanceable yes/no; where the metric/ground/chirality transforms live in the layer stack) - the arc chosen, the LIVRPS reason (why not each neighbour arc), the failure it prevents (viewport re-cook, double transform, payload unpacked in memory), the evidence tier + anchor.",
  "T2) Rule seed harness/bench/corpus/usd/usd_composition_worldlabs_<build>.json = {build, generated_at, source_doc, ratified: false, rows:[{id, topic, rule, arc, why, anchor, tier}]}, tier in VERIFIED-RUNTIME | FIXTURE-VERIFIED | DOC-STATED | PROPOSED: VERIFIED-RUNTIME only where a probe stdout line proves it on 22.0.400; FIXTURE-VERIFIED where the B-6 usdc proves it (PrimCompositionQuery / GetPayloads / purpose attr / variant sets on the actual file); DOC-STATED for the skill text; PROPOSED otherwise.",
  "T3) Probe harness/probes/bp4_usd_composition_probes.py (hython, detached + polled; stdout verbatim to harness/notes/h22wl/bp4_usdknow/stdout.txt): open b6_wl_component.usdc; per prim: composition arcs (PrimCompositionQuery), purpose, variant sets + selections, kind, customData keys; payload Unload/Load round trip with prim counts before/after; a synthetic tiny stage demonstrating LIVRPS (one attribute with local, inherit, variant, reference, payload, specialize opinions - print the winner per pair, which settles the deep-dive's disputed Specialize line). Every VERIFIED row anchors to stdout.txt:line.",
  "T4) Checker harness/battleplan/notes/bp4_usdknow_check.py (plain Python, no deps): exit 1 if any VERIFIED-RUNTIME / FIXTURE-VERIFIED row's anchor does not grep in the named stdout; run it, exit code in the receipt. Post a bus finding with the seed path + row counts per tier, commit the named files, then the receipt."
 ],
 "touches": ["docs/reviews/bp4-usd-composition-worldlabs.md", "harness/bench/corpus/usd/", "harness/probes/bp4_usd_composition_probes.py", "harness/notes/h22wl/bp4_usdknow/", "harness/battleplan/notes/bp4_usdknow_check.py"],
 "readonly": False, "deps": [],
 "crucible_criteria": ["the crucible re-runs bp4_usd_composition_probes.py in a fresh checkout with its own out dir and diffs the printed arcs/winners against the builder's", "the crucible runs bp4_usdknow_check.py, then mutates: strip an anchor; promote a PROPOSED row to VERIFIED-RUNTIME; change the arc on a VERIFIED row - each must exit 1", "`git diff master..HEAD -- python/synapse/` is empty; the seed carries ratified:false"] + STD_CRUX[1:3],
 "spawn_classes": [],
 "source": {"doc": SRC, "anchor": "Joe 2026-09-03: scaffold USD composition knowledge where needed (solaris-usd-composition); blueprint v0.3 sec.2 substrate split, sec.4 component topology; rule D-1"},
 "acceptance": [
  {"predicate": "decision record covers every sec.2/sec.4 choice with arc + LIVRPS reason + tier + anchor", "evidence": "check"},
  {"predicate": "seed JSON parses; every VERIFIED-RUNTIME / FIXTURE-VERIFIED anchor greps; bp4_usdknow_check.py exits 0 on the committed seed", "evidence": "test"},
  {"predicate": "probe stdout has the per-prim arc listing for b6_wl_component.usdc, the payload round trip counts, and the LIVRPS winner table", "evidence": "probe"},
  {"predicate": "no edit under python/synapse/; ratified:false present in the seed", "evidence": "check"},
 ],
})

BUILDERS = ["BP4-INTAKE", "BP4-RULINGS", "BP4-B7FIX", "BP4-SPATIAL", "BP4-PANELFONT", "BP4-USDKNOW"]

M.append({
 "id": "BP4-CRUX", "band": "TRUST", "class": "crucible", "tier": "referee",
 "name": "Adversarial crucible for wave BP4 - six parallel lanes (one per builder), re-runs probes/tests/checkers itself in fresh checkouts, authors its own mutations, builds nothing",
 "note": "Tier: referee (claude-fable-5-1 via rails; harness/battleplan/runs/2026-09-03/preflight_bp4.json proves the alias resolves; if dispatch falls back to reasoning the ledger row says so). Read-only under harness/readonly-settings.json. Blocked until the six builder receipts exist. One lane per builder, lanes in parallel via agent teams - HOLD YOUR TURN until every lane has reported; then write. A BROKEN verdict means that leg does not ride. Verdicts are READ by Joe before any merge word; a green CRUX receipt is a precondition, never a substitute. Self-cap: 40 turns (progress every 5). Order of final writes (capsule 09-03 authoring rule): verdicts + mutations files, then harness/notes/h22/BP4_CRUX_LANDED.flag, then commit, then the receipt as the last write - nothing after the receipt. " + HYTHON_NOTE + " " + FENCE_NOTE,
 "targets": [
  "T1) For each builder receipt: re-run every acceptance predicate independently in a fresh checkout of the leg branch; verdict rows pass|fail|UNKNOWN with your own anchors, never the builder's. gui_required predicates are UNKNOWN to you - say so.",
  "T2) INTAKE lane: recompute SHA256 + bytes under docs/intake/src/ vs MANIFEST.md; the blueprint diff is one header hunk; mutations: alter a hash cell; add a line outside the header - each must redden your check.",
  "T3) RULINGS lane: recount ruling entries across the seven receipts + verdicts; grep every claim cell verbatim; every ruling cell PENDING; mutations: change one claim word; fill one ruling - each must redden.",
  "T4) B7FIX lane: re-run `hython ... --only B-7` yourself (own out dir, pinned hython, pref dir), recompute EXR stats, read every hunk of the probe-script diff, confirm the review doc's BP3 rows are byte-identical to master; mutations: drop the camera assignment - the re-run must go black again; touch a non-B-7 block - the hunk audit reddens.",
  "T5) SPATIAL lane: run tests/test_spatial_lane.py + timings on the fixture yourself; grep registries for default-on registration; run the tools on the second stage; mutations: flip a tolerance; register the tool by default - each must redden.",
  "T6) PANELFONT lane: grep the branch for hardcoded typography outside the token module; run panel tests + test_panel_typography + the 5-scale stylesheet check; mutations: re-introduce a px size; set a token below the floor; add a QWidget subclass - each must redden. GUI rows UNKNOWN.",
  "T7) USDKNOW lane: re-run bp4_usd_composition_probes.py (own out dir) and diff arcs/winners; run bp4_usdknow_check.py then mutate (strip anchor; promote PROPOSED; change arc on VERIFIED) - each must exit 1; `git diff master..HEAD -- python/synapse/` empty.",
  "T8) Verdict per leg: SOUND | SOUND-WITH-NITS | BROKEN with chain_broken_at named. Write harness/battleplan/notes/BP4-CRUX_verdicts.md and BP4-CRUX_mutations.json, post each verdict on the bus to *, write harness/notes/h22/BP4_CRUX_LANDED.flag, commit, then the receipt."
 ],
 "touches": [], "readonly": True,
 "deps": BUILDERS,
 "crucible_criteria": STD_CRUX,
 "spawn_classes": [],
 "source": {"doc": SRC, "anchor": "v0.3 rule D-1 two keys; docs/BATTLEPLAN.md sec.12 R-5/R-6 crucible precedent; capsule 2026-09-03 authoring rule (nothing after the receipt)"},
 "acceptance": [
  {"predicate": "one verdict per builder leg (six), each with independently re-run acceptance rows and the crucible's own anchors", "evidence": "receipt"},
  {"predicate": ">= 2 self-authored mutations per builder leg, each named with the check it reddens (BP4-CRUX_mutations.json)", "evidence": "test"},
  {"predicate": "B-7, the spatial tests, and the USD composition probes re-run by the crucible with its own artifacts, statuses diffed against the builders'", "evidence": "probe"},
 ],
})

M.append({
 "id": "BP4-TIDY", "band": "TRUST", "class": "tidy", "tier": "mechanical",
 "name": "House cleaning, proposal-only: worktree census with prune commands (unusable-only standard; `git branch --merged` now allowed), receipt-order + named-file-commit checks on every BP4 leg, UNKNOWN-discipline grep on BP4 artifacts, log/scratch census - removes nothing; prunes ride in Joe's closing batch",
 "note": "Tier: mechanical (Haiku 4.5). Read-only under readonly-settings.json (`cd <wt> && git status --short`, never `git -C`). Runs after BP4-CRUX so nothing you read is moving. Capsule 09-03 counted 22 worktrees; `git worktree list` on 09-03 evening showed 18 + main - your census settles it. BP3-TIDY's merged column was UNKNOWN because `git branch` was fenced; `git branch --merged master` is allowed now. Self-cap: 15 turns (progress every 4). EXCLUDED from every table and proposal - another writer's surface, list once under 'not ours' and stop: harness/reach/, harness/flow/, harness/hardening/, .claude/agents/, .claude/workflows/, docs/REACH_BLUEPRINT.md, docs/harness/, the modified harness/battleplan/prompts/BP2-*.md, harness/battleplan/dashboard_bp1.py, harness/rope/STATE.json, harness/memory/runs/. " + FENCE_NOTE,
 "targets": [
  "T1) Worktree census: for every row of `git worktree list` - path, branch, HEAD, merged into master (`git branch --merged master` contains it: yes/no), dirty count, usable (dir exists, HEAD resolves), proposed action + exact `git worktree remove <path>` / `git branch -d <branch>` ONLY when merged AND clean; otherwise 'keep' + reason. bp2/nits is BROKEN-carried: keep, say so.",
  "T2) Receipt order per BP4 leg branch: the receipt commit is the last commit and every product file's commit precedes it; no `git add -A` footprint (branch diff vs master contains only the leg's touches + receipt); list violations with shas.",
  "T3) UNKNOWN discipline: grep BP4 review docs, audit docs, the rule seed and receipts for numeric zeros or 'pass' on rows whose status is BLOCKED, NOT_RUN, gui_required or UNKNOWN; list hits file:line.",
  "T4) Log/scratch census: harness/notes/h22/*.err *.pid *.log from bp1/bp2/bp3 (bytes, mtime), %TEMP%\\orch_BP4-*.ps1 count, docs/ root *.txt scratch family - ONE proposed Remove-Item / git mv list; touch nothing.",
  "T5) Write harness/battleplan/notes/BP4_TIDY.md with the four tables; post one bus finding with the path; commit it; then the receipt."
 ],
 "touches": [], "readonly": True, "deps": ["BP4-CRUX"],
 "crucible_criteria": ["every proposed prune row carries the merged/clean/usable evidence triple with the command that produced it", "the leg's branch diff vs master contains only BP4_TIDY.md and its receipt"] + STD_CRUX[1:2],
 "spawn_classes": [],
 "source": {"doc": SRC, "anchor": "harness constitution: unusable-only prune standard, commit-before-receipt, named-file commits; capsule 2026-09-03 housekeeping + hardening notes"},
 "acceptance": [
  {"predicate": "census row count equals `git worktree list` row count; each row has the merged/clean/usable triple and a command or a keep reason", "evidence": "check"},
  {"predicate": "receipt-order row per BP4 leg with shas", "evidence": "check"},
  {"predicate": "no file removed or moved by this leg (branch diff = BP4_TIDY.md + receipt only)", "evidence": "check"},
 ],
})

# ---- write missions
for m in M:
    (AF / "missions" / f"{m['id']}.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"wrote {len(M)} missions")

# ---- template: model line becomes tier-aware (wave-neutral)
tpl = AF / "prompts" / "_template.md"
t = tpl.read_text(encoding="utf-8")
t2 = t.replace("Model: Opus 4.8, dispatched by harness/orchestrate.ps1.",
               "Model: resolved per mission tier by harness/rails_exec.json (mechanical Haiku 4.5 / reasoning Opus 4.8 / referee Fable 5.1), dispatched by harness/orchestrate.ps1.")
if t2 != t:
    tpl.write_text(t2, encoding="utf-8"); print("template model line made tier-aware")
else:
    print("template: model line not found or already tier-aware")

# ---- clone per-wave files bp3 -> bp4
def clone(src, dst, extra=None):
    s = (AF / src).read_text(encoding="utf-8").replace("bp3", "bp4").replace("BP3", "BP4")
    if extra: s = extra(s)
    (AF / dst).write_text(s, encoding="utf-8"); print("cloned", dst)

def manifest_patch(s):
    s = re.sub(r'HELD = \{.*?\}', 'HELD = {}  # BP4: nothing held - SPATIAL is armed by Joe\'s enumerated "go batch" (capsule 09-03 open item 3)', s, count=1, flags=re.S)
    s = s.replace('"effort": "ultracode",', '"effort": "max",  # Joe 2026-09-03: max effort; preflight_bp4.json proves every tier accepts --effort max')
    s = s.replace("(RECON -> PROBE -> CORPUS; STUBS after RECON; PANEL independent; CRUX after the five; TIDY after CRUX; SPATIAL held; ",
                  "(six independent builders INTAKE/RULINGS/B7FIX/SPATIAL/PANELFONT/USDKNOW; CRUX after the six; TIDY after CRUX; nothing held; ")
    return s
clone("build_manifest_bp3.py", "build_manifest_bp4.py", manifest_patch)
clone("arm_bp3.ps1", "arm_bp4.ps1", lambda s: s.replace("param([string]$Budget = '12turns')", "param([string]$Budget = '12turns,105000000tokens')  # 8 dispatches + 4 slack; token ceiling <= BP3's 102.8M in + 1.5M out"))
def dash_patch(s):
    pairs = ('PAIRS = {"BP4-INTAKE": "builder", "BP4-RULINGS": "builder", "BP4-B7FIX": "builder", "BP4-SPATIAL": "builder",\n'
             '         "BP4-PANELFONT": "builder", "BP4-USDKNOW": "builder", "BP4-CRUX": "solo (referee)", "BP4-TIDY": "solo (tidy)"}')
    return re.sub(r'PAIRS = \{.*?\}', pairs, s, count=1, flags=re.S)
clone("dashboard_bp3.py", "dashboard_bp4.py", dash_patch)
for f in ("status_bp3.py", "watch_bp3.ps1"):
    clone(f, f.replace("bp3", "bp4"))

# ---- compile -> control -> manifest
def run(*args):
    r = subprocess.run([sys.executable] + list(args), cwd=str(AF), capture_output=True, text=True)
    print(f"$ {' '.join(args)}\n{r.stdout}{r.stderr}"); return r.returncode
rc = run("compile_wave.py", "bp4")
rc |= run("make_control.py", "bp4")
rc |= run("build_manifest_bp4.py")
sys.exit(rc)
