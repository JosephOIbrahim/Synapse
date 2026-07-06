# C TRACK — frozen spec (context-capability graft)

Repo: `C:\Users\User\SYNAPSE` (branch `feat/harness-v6-track`). All paths repo-relative.

## Mission

Graft a **context-capability track** onto the EXISTING harness (`harness/run.ts` loop — DO NOT
rebuild it): measure SYNAPSE's real ability to CREATE in each Houdini context (SOP, LOP, COP,
TOP, DOP, MAT) by driving its own live handler surface under hython, deposit the truth as a
catalog, then grind per-context improvement sprints gated by a deterministic golden+ratchet.
Additive only: one new state-file trigger, 7 tasks, 8 checks, 2 scripts, 1 test file, doc rows.

## Ground truth (verified this session — do not re-litigate)

- The live dispatch seam is `SynapseHandler.handle(SynapseCommand)` —
  `python/synapse/server/handlers.py:353` — with `CommandHandlerRegistry.registered_types`
  (`handlers.py:281`) for enumeration and `invoke()` carrying the FloorGate provenance hook.
  The probe drives THIS surface (same path the live WS transport calls), never raw `hou`
  for mutations. `hou` reads are allowed only to VERIFY and to revert probe residue.
- The v6 graft is UNCOMMITTED on this branch. Builders edit the LIVE TREE (no worktrees —
  a worktree forks from HEAD and would miss the v6 edits in tasks.json/checks.py/run.ts).
- Pattern authority: state triggers + `blocked_on` filters + read-only surfaces in run.ts
  (drop.json → Mode B; BP00_manifest.md → V.x); catalog checks with schema + blake2b +
  live-build stamp in checks.py (`check_connectivity_catalog_fresh`); review-sweep checks
  (`check_lop_review_clean`); test style in tests/test_v6_track.py + test_phantom_guardrail.py.
- APEX/rigging is OUT of scope structurally (`no_rigging_drift` guardrail). CHOP/OBJ excluded
  (low creation leverage). Renders are NOT part of any golden (Indie husk silently no-ops —
  a render golden would be dishonest headless; `render` stays a separate ADAPT check).
- Guardrails (phantom_clean etc.) already run on every sprint — C-tasks inherit them for free.

## FROZEN CONTRACT (critics may attack; builders may NOT change)

### 1. Catalog trigger + run.ts additions

- Canonical catalog: `harness/notes/context_capability_21.json` (major-pinned name; the
  `houdini_version` field inside carries the full build, mirroring connectivity_21.json).
- run.ts, after the V6 const: `const CTX = existsSync(join(REPO, "harness/notes/context_capability_21.json"));`
- Queue filter, after the blueprints filter: `queue = queue.filter((t: any) => !(t.blocked_on === "catalog" && !CTX));`
- Startup status: one dim line, armed or held (mirror the v6 lines). When armed AND
  `git status --porcelain harness/notes/context_capability_21.json` is non-empty, print the
  same commit-first warning the v6 block prints (worktrees fork from HEAD).
- New read-only surface `surfaceContextIntake()` called in main after `surfaceBlueprintIntake()`:
  if `!CTX` AND tasks.json has any `blocked_on:"catalog"` task → print: run
  `bun run harness/run.ts --task C.0`, merge the catalog, C.1–C.6 arm; plus the
  `--task C.n cannot pierce the hold` line (mirror lines 296–299). If CTX → print nothing.
- `--dry` stays mutation-free.

### 2. New tasks in harness/tasks.json (phase "context")

Appended after V.7. Schema identical to existing tasks. Add the 8 new check names to
`checks_vocabulary`. Exact entries (title prose may be polished; ids/refs/verify frozen):

- `C.0` mode A, crit false, layer "utility" — "Context track — probe SYNAPSE's create-capability
  per Houdini context (SOP/LOP/COP/TOP/DOP/MAT), deposit the catalog + review sweep".
  refs: ["harness/notes/spec-C-context-capability.md", "host/introspect_context_capability.py",
  "scripts/flywheel_review_context.py", "harness/notes/context_capability_21.json",
  "tests/test_ctx_track.py"]
  verify: ["context_catalog_fresh", "context_review_clean"]
  note: read-only vs product code; the catalog is the deliverable. Re-run per build.
- `C.1`–`C.6` mode A, blocked_on "catalog", crit false, layer "build" — one per context in this
  order: C.1 sop, C.2 lop, C.3 cop, C.4 top, C.5 dop, C.6 mat. Title pattern: "Context track —
  <CTX>: close the top create-gap the catalog surfaces; prove by golden + ratchet".
  refs: ["harness/notes/spec-C-context-capability.md", "harness/notes/context_capability_21.json",
  "python/synapse/server/handlers.py", "tests/test_ctx_track.py"]
  verify: ["context_golden_<ctx>", "context_catalog_fresh"]
  note (each): read the catalog's `gaps` for this context; close the highest-leverage one by
  extending the HANDLER surface (new/fixed command verbs), not by weakening the probe; the
  golden ratchet gates (gaps must strictly decrease unless already 0); re-run the probe
  in-worktree to refresh the catalog as part of the sprint. The catalog re-ranks C.1–C.6 —
  a context whose golden already passes with 0 gaps banks trivially and that is correct.

### 3. New checks in harness/verify/checks.py

Follow the file's exact return shape `{"ok": bool|None, "detail": str}`, DISPATCH registration,
honest-false ethos, local imports, stdlib only. Eight checks:

- `context_catalog_fresh` — worktree file `harness/notes/context_capability_21.json` exists
  (missing → ok:false "run C.0 first; commit the catalog — worktrees fork from HEAD");
  `schema == "context_capability/v1"`; blake2b (digest_size=16) over
  `json.dumps(data["contexts"], sort_keys=True, ensure_ascii=False)` recomputes to
  `data["blake2b"]`; when ctx["hython"] is set, live `hou.applicationVersionString()` must equal
  `houdini_version` (stale → ok:false naming both); HYTHON unset → ok:true with
  "live-build comparison skipped" note (mirror check_connectivity_catalog_fresh exactly).
- `context_review_clean` — run `scripts/flywheel_review_context.py` via
  `sh([sys.executable, ...], cwd=ctx["wt"], env=_wt_env(ctx))`; findings at
  `.claude/flywheel_ctx_findings.json`; ok = rc==0 AND summary.critical==0
  (mirror check_lop_review_clean exactly, including missing-findings-file handling).
- `context_golden_sop|lop|cop|top|dop|mat` — one function via a shared `_context_golden(ctx, name)`
  helper. HYTHON unset → ok:false "HYTHON unset". Run
  `sh([ctx["hython"], "host/introspect_context_capability.py", "--context", <name>, "--out",
  ".claude/ctx_probe_<name>.json"], cwd=ctx["wt"])`; parse the JSON artifact (tolerate hython
  banners — read the FILE, not stdout). ok requires BOTH:
  (a) `golden.ok is True`, and (b) the RATCHET: with `baseline` = the catalog entry for this
  context read from `git show HEAD:harness/notes/context_capability_21.json` — HEAD, not the
  working file, because a C-sprint refreshes the in-tree catalog and a working-file baseline
  would compare the probe against its own refresh, so an improving sprint could never pass
  (ratified 2026-07-06; missing at HEAD → ok:false "run C.0 + merge first"),
  `gaps_now = len(probe.contexts[<name>].gaps)`, `gaps_base = len(baseline.gaps)`:
  pass iff (gaps_base == 0 and gaps_now == 0) or (gaps_base > 0 and gaps_now <= gaps_base - 1).
  detail always states golden ok/fail + gaps now/baseline + first failing step if any.

### 4. The probe — host/introspect_context_capability.py

Mirror `host/introspect_connectivity.py` conventions (read it first: arg parsing, atomic
write, stamp fields). Runs ONLY under hython. CLI:

```
hython host/introspect_context_capability.py                       # full catalog → harness/notes/context_capability_21.json
hython host/introspect_context_capability.py --context sop --out X # one context, artifact → X (worktree-relative)
hython host/introspect_context_capability.py --out Y               # full catalog to a custom path
```

Behavior (frozen):
- Boot: `hou.hipFile.clear(suppress_save_prompt=True)`; never saves a hip; never touches user
  prefs; no network; atomic write (`.tmp` + `os.replace`); rc 0 iff the artifact was written.
- Instantiate `SynapseHandler()` once; enumerate `registered_types`; classify every command:
  prefix `cops_` → cop, `tops_` → top; the Solaris/USD/stage family → lop; material family →
  mat; generic node verbs (create_node, connect_nodes, set_parameter/set_parm, delete_node,
  execute_vex, …) → generic (usable in every context); the remainder (memory, render, hda,
  session, science, …) → a top-level `unclassified` list. Contexts map keys are EXACTLY
  sop, lop, cop, top, dop, mat, generic.
- All mutations via `handle(SynapseCommand(...))` (read SynapseCommand's real constructor in
  handlers.py / its module — do not guess field names). `hou` used only for verification reads,
  frame stepping, and revert deletes. A needed verb absent from the registry is a GAP entry
  ("no handler verb: <what>"), never a crash. Every step try/except → ok:false with the
  exception text; one step's failure never aborts the run.
- Per context, run GOLDEN (required) then EXTENDED (gap probes). Every failed step name (golden
  or extended) is appended to that context's `gaps` list. After each context: revert (delete the
  probe's root container(s), verify gone → `revert_ok`); also attempt `hou.undos` unwind and
  record `undo_unwind` as an EXTENDED observation (reversibility is the differentiator —
  observed, not gated).

GOLDEN steps (frozen intent; builder maps to real registry verbs):
- sop: create geo container + box → set a parm (box scale) → create scatter + wire box→scatter
  → cook → verify pointcount > 0 → revert.
- lop: create a /stage sphere (via the Solaris graph/compose family or generic create in /stage)
  → set radius → verify via `node.stage()` prim + radius attr (editableStage is None outside a
  LOP cook — read via node.stage()) → revert.
- cop: create copnet → noise node → wire to output/null → cook → verify layer/resolution info
  (cops_read_layer_info or node cook state) → revert.
- top: create topnet → wedge with wedgecount=3 (tops_setup_wedge or generic create+parm) →
  generate items (tops_generate_items) → verify 3 work items → revert. Generate, not cook.
- dop: create dopnet → smokeobject + smokesolver (expected: via GENERIC verbs — no dop_ family
  exists) → coarse division size → cook 3 frames by frame stepping → verify the sim object
  exists and carries a density field → revert. If generic verbs refuse DOP context, golden
  fails honestly — that IS the C.5 target.
- mat: create a MaterialX standard-surface material (create_material) → assign to a probe box
  (assign_material) → verify binding (read_material) → revert.

EXTENDED steps (frozen names; each maps to one small probe; failures → gaps, never abort):
- sop: `vex_wrangle` (execute_vex @P jitter), `boolean_union`, `group_create`.
- lop: `mtlx_in_lop` (material authored+assigned in LOP), `usdlux_light` (use the verified
  encodings — harness/notes/verified_usdlux_encodings_21.0.671.json ethos; a phantom parm is a
  gap, not a guess), `variant_set`, `collection`, `point_instancer`.
- cop: `procedural_texture`, `composite_aovs`, `cops_to_materialx`.
- top: `local_cook_3` (tops_cook_node on the wedge), `cook_stats`.
- dop: `sop_volumesource`, `pyrosolver`, `vellum_min`, `rbd_min`.
- mat: `textured_material` (procedural texture input, no file IO), `light_linking`.
- every context: `undo_unwind` (see above).

Catalog schema (frozen):
```json
{ "schema": "context_capability/v1", "houdini_version": "<full build>",
  "synapse_version": "<synapse.__version__>", "generated": "<iso8601>",
  "handler_command_count": 0,
  "contexts": { "<ctx>": { "commands": [], 
      "golden": { "ok": false, "steps": [{"step": "", "ok": false, "detail": ""}], "revert_ok": null },
      "extended": [{"step": "", "ok": false, "detail": ""}],
      "gaps": [] } },
  "unclassified": [],
  "summary": { "<ctx>": {"golden_ok": false, "gaps": 0} },
  "blake2b": "<over contexts only>" }
```
`generated`/`summary`/`unclassified` sit OUTSIDE the digest. Step lists are deterministic —
same code ⇒ same gaps. Full run must stay under ~3 minutes headless.

### 5. The review sweep — scripts/flywheel_review_context.py

Stock python, zero hou (read scripts/flywheel_review_lop.py first; mirror its structure, exit
semantics, findings-file discipline). Loads the worktree catalog; writes
`.claude/flywheel_ctx_findings.json` `{"schema": "ctx_review/v1", "summary": {"critical": N,
"advisory": N}, "findings": [{"severity", "context", "what", "evidence"}]}`; exit 0 whenever the
sweep itself ran (the CHECK judges critical). Finding classes (frozen):
- CRITICAL: catalog missing/unreadable; schema mismatch; blake2b mismatch; internal
  inconsistency (summary disagrees with contexts, or golden.ok true while a golden step is
  ok:false); a `cops_`/`tops_`-prefixed command classified anywhere but cop/top; a command
  classified into two contexts.
- ADVISORY: golden_ok false; gaps > 0; `undo_unwind` false; DOP dedicated-verb void.

### 6. New tests — tests/test_ctx_track.py

Import checks.py the way tests/test_phantom_guardrail.py does; follow test_v6_track.py's
fixture/monkeypatch style; NEVER plant sys.modules fakes at module level. ~16 focused cases:
- conformance: every C-task id matches `^C\.\d$`; C.1–C.6 have blocked_on "catalog"; C.0 does
  not; every C-task verify name exists in DISPATCH and checks_vocabulary; guardrails.checks
  unchanged by this graft.
- context_catalog_fresh: missing → ok:false naming C.0; wrong schema → ok:false; digest
  mismatch → ok:false; valid tmp catalog + hython unset → ok:true noting skipped live check.
- context_golden_*: HYTHON unset → ok:false; committed-catalog missing → ok:false mentioning
  merge; ratchet math pinned with synthetic probe artifacts (base 3 / now 3 → false; base 3 /
  now 2 → true (given golden ok); base 0 / now 0 → true; golden fail → false).
- context_review_clean: valid catalog → 0 critical + ok:true; digest-broken catalog →
  ≥1 critical + ok:false.
Tests run under normal pytest, no hou, no hython, tmp_path only.

### 7. Docs + queue (orchestrator-owned, not builders)

harness/README.md (context-track section + Files rows), harness/state/claude-progress.md
(MODE RULE line + one LOG delta), harness/state/flywheel_queue.json (candidate cycle
`ctx-capability`, ratified:false, evidence = this spec + the probe + the review script).

## Style & traps (binding)

- Match run.ts / checks.py comment voice: first-person rationale, why-not-what, dense.
- Surgical: additive edits only; do not reformat or re-order existing code.
- LIVE TREE only — no worktrees, no `git commit` (promotion is the human's).
- run.ts spawns with shell:true — forward-slash any path handed to a spawn; no args needing
  escaping; `--dry` must not mutate.
- tasks.json: valid JSON, 2-space indent, no trailing commas.
- checks.py: stdlib only; every failure path returns a REASON (honest-false); `ok:None` is
  reserved for gate-down, and none of these eight ever needs it (HYTHON-unset is ok:false
  for goldens by design — a golden that can't run is not verified).
- Probe: if you are unsure a `hou.*` symbol exists, the registry/table is the gate — absent
  means gap, never guess (the phantom discipline).
- Do NOT touch: VERSION, pyproject.toml, product code under python/synapse (the probe reads
  handlers; it does not edit them), any 0.x/U.x/V.x task or check, guardrails.

## Deliverable split (for builders)

- BUILDER-A: harness/run.ts + harness/tasks.json (CTX const, filter, status+warning lines,
  surfaceContextIntake, 7 tasks, 8 vocabulary names).
- BUILDER-B: harness/verify/checks.py (8 checks + DISPATCH rows, per §3).
- BUILDER-C: host/introspect_context_capability.py + scripts/flywheel_review_context.py (§4+§5).
- BUILDER-D: tests/test_ctx_track.py (§6).

Each builder: read the real files named in your section FIRST; keep to your file set; if the
frozen contract proves impossible against the real code, STOP and report the conflict instead
of improvising.
