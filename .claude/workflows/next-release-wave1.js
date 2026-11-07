// Wave 1 of the next-release graph, dispatched as a dynamic workflow.
//
// Shape: a gate that refuses on a red CI or a missing JEV decision, then the
// two nodes JEV opened (NR-PLAN-TRUTH, NR-WRITE-RECEIPT) plus one GPU
// feasibility probe, each built in its own worktree and attacked before it is
// reported. Nothing merges and nothing pushes; the owner does that.
//
// Tandem rule: every build works in its own worktree and never touches the
// master checkout, an in-flight CI run, a running render or another session.

export const meta = {
  name: 'next-release-wave1',
  description:
    'Gate on green CI, take the JEV graph decision, fan the land-now nodes into worktree builds plus a GPU feasibility probe, then attack each change.',
  phases: [
    { title: 'Gate', detail: 'CI green on master; JEV graph decision re-read' },
    { title: 'Recon', detail: 'Two cartographers on the land-now nodes, one GPU feasibility scout' },
    { title: 'Build', detail: 'Worktree builds for the code nodes; a probe receipt for the GPU route' },
    { title: 'Attack', detail: 'Adversarial review of each change against its closure predicate' },
  ],
}

const GATE = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    master_sha: { type: 'string' },
    ci: { type: 'string' },
    land_now: { type: 'array', items: { type: 'string' } },
    park: { type: 'array', items: { type: 'string' } },
    needs_joe: { type: 'array', items: { type: 'string' } },
    first_landing: { type: 'string' },
    reason: { type: 'string' },
  },
  required: ['ok', 'master_sha', 'ci', 'land_now', 'park', 'needs_joe', 'first_landing', 'reason'],
}

const RECON = {
  type: 'object',
  properties: {
    node: { type: 'string' },
    plan: { type: 'array', items: { type: 'object', properties: {
      file: { type: 'string' }, change: { type: 'string' }, why: { type: 'string' },
    }, required: ['file', 'change', 'why'] } },
    fixtures: { type: 'array', items: { type: 'string' } },
    predicate: { type: 'string' },
    risks: { type: 'array', items: { type: 'string' } },
  },
  required: ['node', 'plan', 'fixtures', 'predicate', 'risks'],
}

const BUILD = {
  type: 'object',
  properties: {
    node: { type: 'string' },
    worktree: { type: 'string' },
    branch: { type: 'string' },
    commit: { type: 'string' },
    predicate_rc: { type: 'number' },
    tests: { type: 'string' },
    summary: { type: 'string' },
    blocked: { type: 'string' },
  },
  required: ['node', 'worktree', 'branch', 'commit', 'predicate_rc', 'tests', 'summary', 'blocked'],
}

const ATTACK = {
  type: 'object',
  properties: {
    node: { type: 'string' },
    verdict: { type: 'string', enum: ['approve', 'needs-work', 'reject'] },
    blockers: { type: 'array', items: { type: 'object', properties: {
      claim: { type: 'string' }, where: { type: 'string' },
      observed: { type: 'string' }, correction: { type: 'string' },
    }, required: ['claim', 'where', 'observed', 'correction'] } },
  },
  required: ['node', 'verdict', 'blockers'],
}

const REPO = 'C:/Users/User/SYNAPSE/.claude/worktrees/g32-merge'
const MASTER_SHA = args.masterSha
const GATE_SHA = args.gateSha || MASTER_SHA
const RUN_ID = args.runId || '42326231848'

// ---------------------------------------------------------------- gate
const gate = await agent(
  `Mechanical gate. No judgement beyond the checks listed. Do not modify, commit or push anything.

Repository (the master worktree): ${REPO}
Local master head: ${MASTER_SHA}
Pushed commit whose CI gates this wave: ${GATE_SHA}
CI run to verify: ${RUN_ID}

1. Run: git -C ${REPO} rev-parse HEAD   -> must equal or descend from ${MASTER_SHA}; and
   git -C ${REPO} merge-base --is-ancestor ${GATE_SHA} HEAD  -> must succeed (the pushed
   commit under test is in the history; the only delta since then is documentation).
2. Poll the CI run to completion, up to 20 minutes: gh run view ${RUN_ID} --json status,conclusion . Repeat every 30 seconds while status is not "completed". Record the conclusion.
3. Confirm the next-release plan is present: harness/next-release/graph.json and harness/next-release/RULING-2026-11-06.md exist in the worktree.
4. Run the JEV graph guard from the worktree:
   cd ${REPO} && python harness/harness2/compositor.py --mode graph --input harness/next-release/graph.json --wave next-release
   Read harness/harness2/runs/next-release/graph_decision.json and report land_now, park, needs_joe, first_landing and reason.
5. ok is true only when: HEAD matches, CI conclusion is success, the files exist, and the decision file parses. Otherwise name the failed check in reason and set ok false.

Return the schema fields. ci is "success" / "failure" / "timeout" / "<status>".`,
  { label: 'gate', phase: 'Gate', schema: GATE, agentType: 'general-purpose' },
)

if (!gate || !gate.ok) {
  return { halted: true, reason: (gate && gate.reason) || 'gate returned nothing', gate }
}

const NODES = [
  {
    id: 'NR-PLAN-TRUTH',
    surface: 'python/synapse/autonomy/planner.py and python/synapse/autonomy/driver.py',
    ask: `Make the original render plan immutable and reconcile retries against it.
Read the two files and the existing tests (tests/test_autonomy_*.py, tests/test_render_plan_truth.py if present).
Find: where the plan can be rewritten to match returned frames; where retry targets are computed; whether a sparse plan like [1,3] survives a retry of [3]; what happens to a missing terminal product with no evaluation row; whether a multi-render-step plan is silently truncated to the first step.
Name the exact functions and lines, the minimal change, and the failing-first fixtures for: sparse [1,3] retry [3]; missing terminal product; two render steps refused before dispatch.`,
    predicate: `grep -q 'OUTPUT_MISSING' python/synapse/autonomy/planner.py`,
  },
  {
    id: 'NR-WRITE-RECEIPT',
    surface: 'python/synapse/server/parm_authored.py, python/synapse/server/handlers.py (set_parm), python/synapse/core/tool_results.py, python/synapse/mcp/tools.py',
    ask: `Give authored writes a receipt that survives success, failure and every installed route.
Read the files above and tests/test_parm_write_truth.py, tests/test_parm_authored_reads.py.
Find: where a failed transport loses the receipt detail; whether an uninspectable parm can read as "no animation"; whether a queued mutation can carry a precondition; what the comparison domain is for authored strings vs evaluated values.
Name the exact functions and lines, the minimal change, and the failing-first fixtures for: unknown preflight refusing before any setter; a raw $HIP string compared as authored text; a lost transport still returning the structured receipt.`,
    predicate: `grep -q 'raw_authored' python/synapse/server/parm_authored.py`,
  },
]

const recon = await parallel(
  NODES.map((n) => () =>
    agent(
      `You are mapping ONE work package. Read-only: do not edit, commit or run renderers.

Repository: ${REPO} (master at ${MASTER_SHA})
Node: ${n.id}
Surfaces: ${n.surface}

${n.ask}

Also confirm the node's closure predicate is red on this tree today:
  cd ${REPO} && ${n.predicate}   (expect a non-zero exit)

Return: the plan (file, change, why), the fixtures, the predicate you verified, and the risks that could make the change wrong or unsafe. One owner per file; do not propose edits outside the surfaces unless a dependency forces it, and name that dependency.`,
      { label: `recon:${n.id}`, phase: 'Recon', schema: RECON, agentType: 'cartographer' },
    ),
  ),
)

const gpuRecon = await agent(
  `Feasibility scout for one OpenCV 5.1 CUDA chain on this Windows box. Read-only: do not install, build or modify anything.

Repository: ${REPO}
Facts to collect (command, then the observed value; say "absent" rather than guess):
- nvidia-smi: GPU name, driver, memory
- nvcc --version (CUDA toolkit), and where it lives
- cmake --version, and Visual Studio / MSVC toolset presence
- the Python interpreters available (py -0p, python --version, hython version)
- free disk on the drive the build would use
- whether opencv or opencv_contrib sources are already present anywhere in the repo or a known build cache

Then state, from those facts only: the exact source revisions the blueprint names (opencv e4f78fb..., contrib b67a855...), the build route that would produce a CUDA-enabled cv2 for this machine, the commands a build would run, and every blocker that could stop it (toolkit absence, compiler, disk, time). Do not claim a build works; this is the plan and the blockers.`,
  { label: 'recon:NR-GPU-FEASIBILITY', phase: 'Recon', schema: RECON, agentType: 'cartographer' },
)

// ---------------------------------------------------------------- build
const builds = await parallel(
  NODES.map((n, i) => () => {
    const r = Array.isArray(recon) ? recon[i] : null
    return agent(
      `Build ONE work package in its OWN worktree. Never cd to or edit the master checkout at ${REPO}; never stop a process, render or CI run; never push or merge.

Node: ${n.id}
Plan from recon: ${JSON.stringify(r ? r.plan : [])}
Fixtures to write first: ${JSON.stringify(r ? r.fixtures : [])}
Closure predicate (must exit 0 after your change): ${n.predicate}

Steps:
1. Create the worktree from the reviewed master:
   cd ${REPO} && git worktree add .claude/worktrees/nr-${i + 1} -b nr/${n.id.toLowerCase()} ${MASTER_SHA}
   (If the path exists, use a -2 suffix; never delete an existing worktree.)
2. Work only inside that worktree and use relative paths. Write the failing-first tests named above; run them and confirm they fail for the right reason.
3. Make the smallest change that satisfies the node. One owner per file. Do not add new modules unless the plan named one.
4. Run: the closure predicate (must exit 0), the node's focused tests, and the nearest existing suites the change touches.
5. Commit ONE atomic commit (git commit -F a message file; do not use here-strings). Do not merge, do not push.
6. Report the commit sha, the predicate rc, the test summary line, and any blocker. If blocked, commit nothing and say exactly what stopped you.

Be honest: a test you did not run is not passing; a predicate you did not execute is not closed.`,
      { label: `build:${n.id}`, phase: 'Build', schema: BUILD, agentType: 'general-purpose' },
    )
  }),
)

const gpuBuild = await agent(
  `Write the GPU feasibility receipt in its own worktree. Probe only: do not run a full CUDA build, do not install anything.

Node: NR-GPU-FEASIBILITY
Scout report: ${JSON.stringify(gpuRecon)}

Steps:
1. cd ${REPO} && git worktree add .claude/worktrees/nr-gpu-feas -b nr/gpu-feasibility ${MASTER_SHA}
2. Re-run the cheap facts yourself (nvidia-smi, nvcc --version, cmake --version, py -0p, free disk) and record the exact command output, trimmed.
3. Write harness/next-release/gpu_feasibility.json with: schema, generated_utc, machine facts, the pinned source revisions, the build route (commands), the blockers, and what is UNKNOWN. No invented success.
4. Run the node's closure predicate: test -f harness/next-release/gpu_feasibility.json (expect 0 after the write).
5. One atomic commit; never merge or push. Report the commit sha and the predicate rc.`,
  { label: 'build:NR-GPU-FEASIBILITY', phase: 'Build', schema: BUILD, agentType: 'general-purpose' },
)

// ---------------------------------------------------------------- attack
const attackable = (builds || []).filter((b) => b && b.commit)
const attacks = await parallel(
  attackable.map((b) => () =>
    agent(
      `Adversarial review. Read-only: do not fix, commit or push.

Repository: ${REPO} (master ${MASTER_SHA})
Branch under review: ${b.branch} (worktree ${b.worktree}, commit ${b.commit})
Node: ${b.node}
Builder's claim: ${b.summary}
Tests the builder reports: ${b.tests}

Attack the change against the node's contract, not its style:
- read the full diff (git -C ${REPO} diff ${MASTER_SHA}...${b.commit})
- try to construct an input where the change still reports success or a pass without the effect it claims
- check the fixtures actually fail on master and pass on the branch
- check for regressions in the nearest existing suites (run them if quick)
- check ownership: did the change touch files outside the node's surfaces, and why

Return verdict and blockers only. A blocker must name the claim, where it sits, what you observed, and the correction. If you could not run something, say so and do not treat it as passing.`,
      { label: `attack:${b.node}`, phase: 'Attack', schema: ATTACK, agentType: 'crucible' },
    ),
  ),
)

return {
  gate,
  recon,
  gpuRecon,
  builds,
  gpuBuild,
  attacks,
  master_sha: MASTER_SHA,
}
