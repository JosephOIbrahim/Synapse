# S TRACK — frozen spec (studio-readiness hardening graft)

Repo: `C:\Users\User\SYNAPSE` (branch `feat/harness-v6-track`, C-track committed at 8e42dc1).
All paths repo-relative.

## Mission

Wrap the 24 adversarially-verified findings of
`docs/reviews/synapse-studio-readiness-2026-07-06.html` into the EXISTING harness
(`harness/run.ts` loop — DO NOT rebuild it) as a fourth additive track. Each finding cluster
becomes a **durable regression gate**: a deterministic check that reads RED while the finding's
fingerprint is live in the code and flips GREEN when the fix lands (and stays green forever after,
so the finding can never silently regress). Prose review → executable gate wall.

The three security-critical clusters are **human_gate** tasks — the harness owns the acceptance
check and the review, a human authors the auth/consent change; the harness never autonomously
rewrites security code and never merges. The memory/eval/farm clusters are loop-gradable. A
capstone review task runs at the end and cannot pass while any critical finding is still live.

## Ground truth (verified this session — do not re-litigate)

- The report's 24 findings and their file:line fingerprints are the source of truth. Every S-check
  must fingerprint the ACTUAL live defect (builder VERIFIES the fingerprint matches the code, so the
  check goes RED now). A fingerprint that does not match = the finding was mis-located → STOP and report.
- The loop already runs the adversarial Evaluator on every task — that IS per-task review. S.R adds
  the capstone. "Agent teams" = the build method + run.ts's Generator/Evaluator + an OPTIONAL
  human-invoked red-team workflow S.R points at (not a deterministic dependency).
- Trigger pattern: state-file + `blocked_on` filter + read-only intake surface in run.ts
  (drop.json → Mode B; BP00_manifest.md → V.x; context_capability_21.json → C.x). S mirrors it with
  `harness/state/posture.json` (runtime state, untracked, peer of drop.json).
- Every S-check is stock-python (no hython) EXCEPT where a fingerprint needs the live handler — none
  do; all fingerprints are static (grep/AST over source + posture read). checks.py honest-false ethos:
  ok:false ALWAYS carries the reason + the exact fix criterion. ok:None reserved for gate-down.
- Guardrails (phantom_clean etc.) already run on every sprint — S-tasks inherit them; do NOT add S-checks
  to guardrails.checks.

## FROZEN CONTRACT (critics may attack; builders may NOT change)

### 1. Posture trigger + run.ts additions

- Canonical declaration: `harness/state/posture.json` (runtime state, untracked, like drop.json).
  Schema: `{ "mode": "solo"|"studio"|"farm", "identity_model": "<free text>", "auto_approve": bool }`.
- run.ts, after the CTX const:
  `const POSTURE = existsSync(join(REPO, "harness/state/posture.json"));`
- Queue filter, after the catalog filter:
  `queue = queue.filter((t: any) => !(t.blocked_on === "posture" && !POSTURE));`
- Startup status: one dim line, declared or undeclared (mirror the v6/context lines).
- New read-only surface `surfaceStudioPosture()` called in main after `surfaceContextIntake()`:
  if `!POSTURE` AND tasks.json has any `blocked_on:"posture"` task → print the declaration template
  (the three fields + allowed `mode` values) and a pointer to
  `harness/notes/spec-S-studio-readiness.md` + `harness/state/posture.json.example`; plus the
  `--task S.n cannot pierce the hold` line (mirror the context/v6 surfaces). If POSTURE → print nothing.
- `--dry` stays mutation-free.

### 2. New tasks in harness/tasks.json (phase "studio")

Appended after C.6. Schema identical to existing tasks. Add the 8 new check names to
`checks_vocabulary`. Exact entries (title prose may be polished; ids/refs/verify/blocked_on/human_gate
frozen):

- `S.0` mode A, crit true, layer "bounded-decision", human_gate —
  "Studio track — declare the deployment posture (mode + identity model) → write harness/state/posture.json"
  human_gate: { decision: "solo | studio | farm + identity model + auto_approve policy",
    recommended: "declare the mode explicitly; auto_approve only in solo; default-deny in studio/farm",
    why: "The report's Step-1 hinge: consent auto-approve and RBAC default-deny cannot be enforced
    until the deployment mode is a committed fact. Writing posture.json is the S-track trigger." }
  refs: ["harness/notes/spec-S-studio-readiness.md", "harness/state/posture.json.example"]
  verify: ["posture_declared"]

- `S.1` mode A, blocked_on "posture", crit true, layer "safety", human_gate —
  "Studio track — unify the policy layer: one authoritative capability/gate/read-only/disk table checked at the transport-agnostic dispatch boundary"
  human_gate: { decision: "author the single-source policy table + wire it into registry.invoke()/handle()",
    why: "Security-architecture change; the harness gates + reviews it, it does not autonomously rewrite
    the policy layer. Closes report finding 'no single source of truth' + is the root the criticals grow from." }
  refs: ["shared/bridge.py", "python/synapse/mcp/_tool_registry.py", "python/synapse/server/handlers.py", "python/synapse/panel/worker_policy.py"]
  verify: ["policy_single_source"]

- `S.2` mode A, blocked_on "posture", crit true, layer "safety", human_gate —
  "Studio track — enforce consent at the dispatch boundary: /mcp + autonomous paths get a HumanGate-wired bridge (not the disarmed panel singleton); record the real consent source in the IntegrityBlock"
  human_gate: { decision: "arm consent on the non-panel bridges + record the consent source",
    why: "Closes the #1 critical (consent auto-approve/absent everywhere). Security-critical; human-authored,
    harness-gated. The panel-path solo auto-approve stays a documented per-mode choice via posture.json." }
  refs: ["python/synapse/panel/bridge_adapter.py", "python/synapse/mcp/tools.py", "shared/bridge.py", "python/synapse/core/gates.py"]
  verify: ["consent_enforced"]

- `S.3` mode A, blocked_on "posture", crit true, layer "safety", human_gate —
  "Studio track — per-user identity + RBAC through dispatch on all three transports; default-deny on unresolved role/session; end the shared-handler _user_id race"
  human_gate: { decision: "move authn/RBAC to the dispatch boundary keyed by per-connection identity",
    why: "Closes criticals 2 + the identity race (SEC-1). Security-critical; human-authored, harness-gated." }
  refs: ["python/synapse/server/websocket.py", "python/synapse/server/hwebserver_adapter.py", "python/synapse/mcp/server.py", "python/synapse/server/handlers.py"]
  verify: ["rbac_at_dispatch"]

- `S.4` mode A, crit false, layer "memory" —
  "Studio track — memory: one authoritative store + real provenance (source/author/tier) + recency & conflict in recall"
  refs: ["python/synapse/memory/", "shared/evolution.py"]
  verify: ["memory_provenance"]
  note: loop-gradable. Closes the three memory highs (source='user' mislabel, dead tier fields,
  no recency → stale outranks fresh, three-store split-brain).

- `S.5` mode A, crit false, layer "eval" —
  "Studio track — eval backbone: wire the real validate_frame into the harness render check; guard the fake-hou sys.modules residency; pin permission boundaries as invariants"
  refs: ["harness/verify/checks.py", "python/synapse/server/handlers_render.py", "tests/"]
  verify: ["eval_backbone"]
  note: loop-gradable + highest-leverage-per-risk (improves the harness's OWN eval, which then better
  verifies every other fix). Touching harness/verify/checks.py here is deliberate self-improvement,
  allowed (like the P1/P2/U upgrades). The C-track goldens are the e2e demonstration this extends.

- `S.6` mode A, crit false, layer "farm" —
  "Studio track — farm-headless correctness: neutralize the latent PDG remove_files=True rollback; per-build the scout symbol table for mixed fleets; the TOP-headless + DOP-populate creation gaps (== C.4/C.5)"
  refs: ["shared/bridge.py", "python/synapse/cognitive/tools/scout.py", "host/introspect_context_capability.py"]
  verify: ["farm_headless", "context_review_clean"]
  note: loop-gradable. Cross-links the C-track catalog — the TOP/DOP creation gaps live there;
  context_review_clean re-asserts the catalog stays sound as those gaps close.

- `S.R` mode A, crit true, layer "review" —
  "Studio track — capstone studio-readiness review: aggregate every S-check, require the criticals green, emit the verdict; run the adversarial sweep"
  refs: ["harness/notes/spec-S-studio-readiness.md", "docs/reviews/synapse-studio-readiness-2026-07-06.html", "harness/state/studio_readiness_verdict.json"]
  verify: ["studio_readiness_review"]
  note: the "review at the end". Deterministic aggregate + verdict artifact; the run.ts adversarial
  Evaluator reviews it, and a human may invoke a red-team workflow (the same fan-out that produced the
  report) — that workflow is an OPTIONAL surface, never a deterministic dependency of this check.

### 3. New checks in harness/verify/checks.py

Follow the file's exact return shape `{"ok": bool|None, "detail": str}`, DISPATCH registration,
honest-false ethos, local imports, stdlib only. Each fingerprint check must be VERIFIED against the
live code so it reads RED now; if a fingerprint does not match the code, STOP and report (the finding
was mis-located). Eight checks:

- `posture_declared` — read `harness/state/posture.json` from the MAIN repo
  (`Path(__file__).resolve().parents[1].parent / "harness/state/posture.json"` — posture is a
  machine-level declaration, NOT worktree state). ok iff it exists and parses with `mode` in
  {solo,studio,farm}, a non-empty `identity_model`, and a bool `auto_approve`. Missing/malformed →
  ok:false carrying the exact JSON template to write. Never ok:None.
- `policy_single_source` — SENTINEL gate. ok:true iff a single-source policy module/marker exists
  (a declared `python/synapse/core/policy.py` OR a `# POLICY_SINGLE_SOURCE` sentinel marker in the
  authoritative table) AND the bridge's default-open fallback site is gone. Until then ok:false naming
  the divergent taxonomy files (bridge.py / _tool_registry.py / handlers.py / worker_policy.py) and the
  default-open site. Honest-false regression gate (like check_provenance_not_bypassed's ADAPT shape,
  but decidable via the sentinel).
- `consent_enforced` — FINGERPRINT. ok:false while ANY of: the `_gate = None` (or `_gate=None`) disarm
  literal is present in `panel/bridge_adapter.py`; `mcp/tools.py` imports the disarmed singleton
  (`execute_through_bridge` from panel.bridge_adapter); no `HumanGate.propose` producer exists outside
  the dormant executor (grep producers). detail lists which sub-conditions are still true. ok:true when
  all cleared. Grep/AST over source; no hython.
- `rbac_at_dispatch` — FINGERPRINT. ok:false while `check_permission` appears ONLY in
  `server/websocket.py` (0 occurrences in `hwebserver_adapter.py` + `mcp/server.py`) OR the
  `if user_session:`-with-no-`else` bypass persists in websocket.py. Reads posture: if mode in
  {studio,farm}, additionally require a default-deny site (else the studio posture is unmet). detail
  enumerates the missing enforcement points.
- `memory_provenance` — FINGERPRINT. ok:false while the model-content write path stamps
  `source='user'` (or the tier fields are unused, or recall has no recency/timestamp ordering). Builder
  locates the exact write line from the report's memory findings and greps it; detail names the live
  defect(s). ok:true when provenance is labeled + recall is recency-aware.
- `eval_backbone` — PRESENCE gate. ok:true iff `harness/verify/checks.py` `check_render` references
  `validate_frame` (not merely `size > 1024`) AND a fake-hou residency guard exists (a test/conftest
  that asserts a single planter or fails on collision). Until both: ok:false naming which is missing.
- `farm_headless` — FINGERPRINT. ok:false while a non-test caller of `dirtyAllTasks(remove_files=True)`
  is reachable in `shared/bridge.py` OR scout's version check is skipped in the external-process
  topology (grep the skip site in scout.py). detail names the live defect(s).
- `studio_readiness_review` — CAPSTONE aggregate. Runs the other seven S-checks (call the functions
  directly with the same ctx) + `context_review_clean`. ok:true iff the security-critical set
  {posture_declared, policy_single_source, consent_enforced, rbac_at_dispatch} are ALL ok:true AND no
  S-check is ok:false. Emits `harness/state/studio_readiness_verdict.json`:
  `{ "generated": "<iso>", "per_check": {<name>: <ok>}, "criticals_green": bool,
     "findings_live": [<names still red>], "verdict": "READY"|"NOT READY" }`. Until the fixes land,
  ok:false listing the live findings. This gate CANNOT pass while a critical finding is live.

Register all 8 in DISPATCH after the C rows under a `# S — studio-readiness hardening track` comment.

### 4. New docs + example

- `harness/state/posture.json.example` — the three fields with a commented example per mode (mirror
  `harness/state/drop.json.example`).

### 5. README + progress + queue (orchestrator-owned, not builders)

- `harness/README.md`: a "studio-readiness track" section (posture trigger, held-vs-declared, S.0–S.R
  one-liners) + Files rows. Frame it as the fourth state-file trigger, peer of drop.json.
- `harness/state/claude-progress.md`: MODE RULE line + one LOG delta.
- `harness/state/flywheel_queue.json`: candidate cycle `studio-readiness`, ratified:false, evidence =
  this spec + the report + the S-checks.

### 6. New tests — tests/test_s_track.py

Import checks.py the way tests/test_phantom_guardrail.py does; follow test_ctx_track.py's fixture style;
NEVER plant sys.modules fakes at module level. ~16 cases:
- conformance: every S id matches `^S\.(\d|R)$`; S.1–S.3 have blocked_on "posture"; S.0–S.3 carry
  human_gate; S.4–S.6 + S.R do not block on posture; every S verify name in DISPATCH + checks_vocabulary;
  guardrails.checks unchanged (pin the exact 4-name list).
- posture_declared: missing → ok:false with the template; malformed mode → ok:false; valid → ok:true
  (monkeypatch the posture path to a tmp file).
- fingerprint checks pinned with SYNTHETIC tmp sources (monkeypatch the file-read/grep seam like
  test_phantom_guardrail): consent_enforced RED with a tmp bridge_adapter containing `_gate = None`,
  GREEN without; eval_backbone GREEN with a tmp checks.py referencing validate_frame + a guard file,
  RED without; policy_single_source GREEN with the sentinel present, RED without.
- studio_readiness_review aggregation: all-green stub → verdict READY ok:true; one critical red →
  NOT READY ok:false naming it; verdict artifact written to a tmp path.
- Tests run under normal pytest, no hou, no hython, tmp_path only. Pin messages via SUBSTRING match on
  detail (builder words them), never exact-string equality.

## Style & traps (binding)

- Match run.ts / checks.py comment voice: first-person rationale, why-not-what, dense.
- Surgical: additive edits only; do not reformat/re-order existing code.
- LIVE TREE only — no worktrees, no `git commit` (promotion is the human's / orchestrator's).
- run.ts spawns with shell:true — forward-slash spawn paths; no args needing escaping; `--dry`
  must not mutate.
- tasks.json: valid JSON, 2-space indent, no trailing commas.
- checks.py: stdlib only; every failure path returns a REASON (honest-false); fingerprints are static
  (grep/AST over source + posture read) — none needs hython.
- Fingerprint honesty: a check must read RED now (finding live) and GREEN only when the SPECIFIC
  defect is gone. Verify each fingerprint against the live code; a non-matching fingerprint = mis-located
  finding → STOP and report, do NOT invent a passing check.
- Do NOT touch: VERSION, pyproject.toml, product code under python/synapse (the S-checks READ product
  code, they do not edit it — the fixes are the human's/loop's separate sprints), any 0.x/U.x/V.x/C.x
  task or check, guardrails.

## Deliverable split (for builders)

- BUILDER-A: harness/run.ts + harness/tasks.json (POSTURE const, filter, status+intake surface,
  8 tasks S.0–S.R, 8 vocabulary names).
- BUILDER-B: harness/verify/checks.py (8 S-checks + DISPATCH rows, per §3; VERIFY each fingerprint
  against live code so it reads RED now).
- BUILDER-C: tests/test_s_track.py (§6) + harness/state/posture.json.example (§4).

Each builder: read the real files named in your section FIRST; keep to your file set; if the frozen
contract proves impossible against the real code, STOP and report the conflict instead of improvising.
