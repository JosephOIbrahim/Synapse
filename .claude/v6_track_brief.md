# V6 TRACK — frozen design brief (harness graft)

Repo: `C:\Users\User\SYNAPSE` (branch `feat/harness-v6-track`, off master). All paths repo-relative.

## Mission

Graft the "SYNAPSE v6 → Houdini 22" build plan onto the EXISTING harness (`harness/run.ts`
loop: fresh Generator WIP=1 → checks.py → deterministic guardrail short-circuit → adversarial
Evaluator → PASS/repair-ticket, completion ledger `harness/state/done.json`, worktrees, NO
merge). DO NOT rebuild the loop. DO NOT touch the Phase-0 / Mode-B / U.x tasks. The graft is
additive: one new trigger, seven new tasks, six new checks, two new docs, one new test file.

## Ground truth (verified this session — do not re-litigate)

- PR #43 (ledger + ratification + phantom guardrail) is MERGED; master run.ts has all of it.
- The v6 plan's "Session E — arm the probe" is ALREADY DONE: task 0.2 PASSED 2026-07-02,
  Mode-A identity diff empty on 21.0.671 (`scripts/h22_api_delta.py`, `check_probe_runs`/
  `check_probe_clean`). The v6 track must NOT duplicate it.
- Blueprints BP00–BP08 exist ONLY on paper. Nothing matching BP0*/gsplat/iteration-controller
  exists in the repo. Therefore the v6 track cannot arm until a human drops files.
- The plan's post-drop probe gate == existing tasks 1.4 (fire probe) / 2.1 (patch deltas).
- BP06 risk (APEX Script MCP server unconfirmed) == existing 1.7 quarantine + boundary doc.

## FROZEN CONTRACT — names and semantics (critics may attack; builders may NOT change)

### 1. Blueprint intake trigger (mirrors drop.json exactly in spirit)

- Canonical intake dir: `docs/v6/`.
- Arming marker: a file named exactly `docs/v6/BP00_manifest.md`.
- Human-authored blueprints BP01–BP08: free-named but must match `BP0N_*.md` (documented, not enforced for arming).
- Harness-authored blueprints (created by V-tasks): exactly `docs/v6/BP09_iteration_controller.md` and `docs/v6/BP10_knowledge_base.md`.
- run.ts: `const V6 = existsSync(join(REPO, "docs/v6/BP00_manifest.md"))`.
- Queue filter (add after the existing blocked_on:"drop" filter):
  `queue = queue.filter((t: any) => !(t.blocked_on === "blueprints" && !V6));`
- Startup status line: one dim line stating v6 track armed or held (mirror the MODE A/B lines).
- New read-only surface `surfaceBlueprintIntake()` called in main after `surfaceRatification()`:
  if `!V6` AND tasks.json has any `blocked_on:"blueprints"` task → print the canonical drop
  list (BP00_manifest.md required; BP01–BP08 recommended; BP09/BP10 harness-authored) + a
  pointer to `docs/v6/INTAKE.md`. If V6 → print nothing (the queue speaks). NEVER writes files.
- `--dry` must stay mutation-free.

### 2. New tasks in harness/tasks.json (phase "v6")

All additive, appended after U.5. JSON must stay valid (no trailing commas). Schema identical
to existing tasks. Exact entries (title prose may be polished, ids/refs/verify are frozen):

- `V.1` mode A, blocked_on "blueprints", crit false, layer "scaffold" —
  "v6 Session A — scaffold the skeleton: stub every module in the BP00 manifest"
  refs: ["docs/v6/BP00_manifest.md", "docs/v6/INTAKE.md"]
  verify: ["blueprints_present", "v6_skeleton_conformance"]
  note: stubs land exactly where BP00's `## Module Manifest` table says; pass bodies; zero hou
  imports in pure layers.
- `V.2` mode A, blocked_on "blueprints", crit false, layer "spec" —
  "v6 Session B — write BP09 (Iteration Controller) at BP00–08 fidelity"
  refs: ["docs/v6/BP09_iteration_controller.md", "docs/v6/BP00_manifest.md"]
  verify: ["blueprints_present", "v6_spec_bp09"]
  note: propose→build→evaluate→decide→iterate; convergence/stop logic; max-iteration handling;
  pulls active strategies from BP07. Spec only — no code.
- `V.3` mode A, blocked_on "blueprints", crit false, layer "build" —
  "v6 Session C — spec + BUILD BP10 (Global Knowledge Base): pure Python, zero hou"
  refs: ["docs/v6/BP10_knowledge_base.md", "python/synapse/v6/knowledge_base.py", "tests/v6/test_knowledge_base.py"]
  verify: ["v6_spec_bp10", "v6_kb_roundtrip", "v6_tests_green"]
  note: recipe store + failure DB + vector schema (spec'd; JSONL is the shipped store) + query
  API. The one spine piece shippable before H22.
- `V.4` mode A, blocked_on "blueprints", crit false, layer "build" —
  "v6 Session D — pure-Python layers, test-first: gsplat_compare interpretation, scoring rubrics, meta-cognitive stats"
  refs: ["docs/v6/INTAKE.md", "python/synapse/v6/", "tests/v6/"]
  verify: ["v6_tests_green"]
  note: tests FIRST (each blueprint specifies them) so drop day is "make them pass".
- `V.5` mode B, blocked_on "blueprints", crit false —
  "v6 Miles 1–2 — BP01 Perception + BP02 G-Splat against shipped H22 (highest uncertainty first)"
  verify: ["probe_clean", "v6_tests_green"]
  note: the 1.4 probe report re-ranks V.5–V.7 before work starts; build to survive "feature X
  shipped differently".
- `V.6` mode B, blocked_on "blueprints", crit false —
  "v6 Miles 3–4 — BP08 three-tier evaluator (keystone; 01+02 become the engine)"
  verify: ["v6_tests_green"]
- `V.7` mode B, blocked_on "blueprints", crit false —
  "v6 Miles 5–7 — BP09+BP10 integration: first autonomous cycle, PYRO ONLY"
  verify: ["v6_tests_green", "ledger"]
  note: prove pyro end-to-end before branches (BP07: G-Splat convergence tracks pyro r=0.78,
  characters r=0.31). Branches 03–07 are production-ordered after this, not corpus-ordered.

Also: append the six new check names to `checks_vocabulary`.

### 3. New checks in harness/verify/checks.py

All pure Python under `PYTHON` (no hython, like check_phantom_clean). Follow the file's
existing return shape, registry/dispatch pattern, and honest-false ethos EXACTLY (read the
file first; do not invent a new pattern). Six checks:

- `blueprints_present` — ok:true iff `docs/v6/BP00_manifest.md` exists; detail enumerates
  which BP00–BP10 canonical/pattern files are present/missing. Never ok:null.
- `v6_skeleton_conformance` — parse BP00_manifest.md for a `## Module Manifest` section
  containing a markdown table whose FIRST column is a repo-relative .py path. ok:false with a
  pointer to docs/v6/INTAKE.md if section/table missing. Else: every listed path must exist
  and `py_compile` cleanly; pure layers (any manifest row whose 2nd column contains "pure")
  must not import hou at module top (AST check, reuse phantom_clean's AST approach where
  sensible). Detail lists offenders.
- `v6_spec_bp09` — `docs/v6/BP09_iteration_controller.md` exists and contains ALL required
  headings (case-insensitive substring match on markdown headings): "Loop Orchestration",
  "Convergence" + "Stop" (may be one heading "Convergence & Stop Logic"), "Max-Iteration",
  "Strategy" (the BP07 pull), "H22 Dependencies", "Tests". ok:false lists missing headings.
- `v6_spec_bp10` — same mechanic for `docs/v6/BP10_knowledge_base.md`; required: "Recipe
  Store", "Failure", "Vector Schema", "Query API", "Tests".
- `v6_kb_roundtrip` — import `synapse.v6.knowledge_base` (sys.path: `<worktree>/python`).
  In a tempdir: construct `KnowledgeBase(root=tmp)`, `add_recipe(dict)` + `add_failure(dict)`
  with nested payloads, `query(...)` both back, deep-equal against what went in (lossless or
  fail — SYNAPSE fidelity ethos). Module missing → ok:false "BP10 not built yet (task V.3)".
- `v6_tests_green` — run `PYTHON -m pytest tests/v6/ -q --no-header -x` in the worktree;
  rc 0 → ok:true. `tests/v6/` absent → ok:false "test-first: tests/v6/ must land first".

## 4. New docs

- `docs/v6/INTAKE.md` — the paper→disk contract. Must contain: (a) the arming rule
  (BP00_manifest.md exact name), (b) the `## Module Manifest` table format with a 3-row
  example (columns: path | layer | notes; "pure" in layer = zero-hou enforced), (c) canonical
  names BP09/BP10 + BP0N_*.md pattern for 01–08, (d) the one allowed intake edit: if BP00's
  layout disagrees with `python/synapse/v6/` rooting, re-point tasks.json V.3/V.4 refs at
  intake time, (e) a 5-line copy-paste drop checklist, (f) what happens next (which V-tasks
  arm, in what order, and that `bun run harness/run.ts` grinds them).
- `docs/v6/PLAN.md` — the v6→H22 build plan RECONCILED against repo truth. Preserve the
  plan's voice and structure (You are here / RIGHT NOW / DROP DAY / POST-DROP / WATCH), but:
  Session E marked DONE with evidence (task 0.2, 2026-07-02, empty Mode-A delta); the probe
  gate mapped to tasks 1.4/2.1; Sessions A–D mapped to V.1–V.4; miles mapped to V.5–V.7;
  BP06 WATCH mapped to task 1.7 + SYNAPSE_H22_BOUNDARY.md. End with the plan's own meta-work
  warning verbatim ("editing this plan more than acting on it is the avoidance pattern") and
  a line that THIS reconciliation was one-shot — the next edit should be a blueprint drop,
  not a plan edit.

## 5. README + progress

- `harness/README.md`: add a short "v6 track" section (trigger file, held-vs-armed, V.1–V.7
  one-liners) + rows for the new files in the Files table. Do NOT reframe the three human
  gates; the blueprint drop is "the second state-file trigger", peer of drop.json.
- `harness/state/claude-progress.md`: extend MODE RULE with the v6 arm line; append one LOG
  delta line for this graft.

## 6. New tests — tests/test_v6_track.py

Pin the new checks (import checks.py the way tests/test_phantom_guardrail.py does — READ IT
FIRST and follow its fixture/monkeypatch style; NEVER plant sys.modules fakes at module level,
that is the known repo trap):
- blueprints_present: missing dir → ok:false; BP00 present in tmp → ok:true; detail lists.
- v6_skeleton_conformance: no section → ok:false w/ INTAKE pointer; table w/ existing+compiling
  stub → ok:true; missing path → ok:false; "pure" row importing hou at top → ok:false.
- v6_spec_bp09 / v6_spec_bp10: missing file → ok:false; all headings → ok:true; one missing
  heading → ok:false naming it.
- v6_kb_roundtrip: module absent → ok:false mentioning V.3.
- v6_tests_green: tests/v6 absent → ok:false "test-first".
- Conformance: every V-task's verify entries exist in checks.py's dispatch AND in
  checks_vocabulary; every V-task id matches ^V\.\d$; all V tasks have blocked_on "blueprints".
Tests run under the repo's normal pytest (no hou needed). Target ~14–18 focused cases.

## Style & traps (binding)

- Match run.ts / checks.py comment voice: first-person rationale, why-not-what, dense.
- Surgical: do not reformat, re-order, or "improve" existing code. Additive edits only.
- Windows: run.ts spawns with shell:true — never add args that need escaping; forward-slash
  any new paths passed to spawns (none expected).
- tasks.json: valid JSON, 2-space indent matching file, no comments outside "_comment".
- checks.py: no new deps; stdlib only; every failure path returns a REASON (honest-false).
- Tests: no wall-clock sleeps, no network, tmp_path fixtures, monkeypatch not sys.modules.
- Do NOT touch: VERSION, pyproject.toml, .claude/settings.json, any src/product file outside
  the listed set. python/synapse/v6/ is NOT created now (V.1's job, post-intake).

## Deliverable split (for builders)

- BUILDER-A: harness/run.ts + harness/tasks.json (trigger, filter, status line, intake
  surface, 7 tasks, vocabulary).
- BUILDER-B: harness/verify/checks.py (6 checks, registered per existing pattern) +
  tests/test_v6_track.py.
- BUILDER-C: docs/v6/INTAKE.md + docs/v6/PLAN.md + harness/README.md +
  harness/state/claude-progress.md.

Each builder: read the real files first; keep to your file set; if the frozen contract proves
impossible against the real code, STOP and report the conflict instead of improvising.
