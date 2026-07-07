#!/usr/bin/env bun
/**
 * SYNAPSE → H22 long-running harness — orchestrator.
 *
 * The loop your checklist already implies: probe → delta → patch, made autonomous,
 * with an adversarial gate. WIP=1, hard context reset per sprint, atomic commits in
 * isolated worktrees. It does NOT merge to main and does NOT decide architecture —
 * those are deliberate human gates.
 *
 *   MODE A (now, on H21):  grinds Phase 0. Trigger: just run it.
 *   MODE B (mid-July):     fires when harness/state/drop.json exists (the three numbers).
 *   V6 TRACK:              V-tasks arm when docs/v6/BP00_manifest.md exists (blueprint drop).
 *
 * v2 (boundary graft): the cross-cutting non-goal GUARDRAILS from checks.py are enforced
 * DETERMINISTICALLY here. Any guardrail ok:false fails the sprint and writes a repair ticket
 * BEFORE the Evaluator is even called — the boundary's moat is not left to LLM discretion.
 * A guardrail reporting ok:null ("not wired yet") only warns.
 *
 * Run:  bun run harness/run.ts
 *       bun run harness/run.ts --task 0.8        # single task
 *       bun run harness/run.ts --dry             # plan only, no agents spawned
 *
 * Env (all optional, sensible defaults):
 *   HYTHON   path to hython for the CURRENT mode. Mode A → H21's hython; Mode B → H22's.
 *            Windows example: "C:\\Program Files\\Side Effects Software\\Houdini 21.0.671\\bin\\hython.exe"
 *   PYTHON   python with pxr (USD) available for checks.py            (default: "python")
 *   CLAUDE_BIN   the Claude Code CLI                                  (default: "claude")
 *   MAX_ROUNDS   repair rounds before a task is flagged for a human   (default: 3)
 *   WORKTREE_DIR base for git worktrees                               (default: ".claude/worktrees")
 */

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync, mkdirSync, unlinkSync, statSync, renameSync } from "node:fs";
import { resolve, join } from "node:path";
import { createHash } from "node:crypto";

// ---------- config ----------
const REPO = process.cwd();
const HYTHON = process.env.HYTHON ?? "";
const PYTHON = process.env.PYTHON ?? "python";
const CLAUDE_BIN = process.env.CLAUDE_BIN ?? "claude";
const MAX_ROUNDS = Number(process.env.MAX_ROUNDS ?? 3);
const WORKTREE_DIR = process.env.WORKTREE_DIR ?? ".claude/worktrees";

const args = process.argv.slice(2);
const DRY = args.includes("--dry");
const ONLY = args.includes("--task") ? args[args.indexOf("--task") + 1] : null;
const FORCE = args.includes("--force");   // re-run tasks the completion ledger marks done
const DRIVE = args.includes("--drive");   // red-driver: select the next blocking-red readiness finding and drive only it

const GEN_PROMPT = readFileSync(join(REPO, "harness/prompts/generator.md"), "utf8");
const EVAL_PROMPT = readFileSync(join(REPO, "harness/prompts/evaluator.md"), "utf8");
const TASKS = JSON.parse(readFileSync(join(REPO, "harness/tasks.json"), "utf8")).tasks;
const PROGRESS = join(REPO, "harness/state/claude-progress.md");

// ---------- tiny log ----------
const c = { dim: "\x1b[2m", sig: "\x1b[36m", ok: "\x1b[32m", bad: "\x1b[31m", warn: "\x1b[33m", off: "\x1b[0m" };
const log = (s: string) => console.log(s);
const head = (s: string) => log(`\n${c.sig}━━ ${s}${c.off}`);

// ---------- mode ----------
const DROP = join(REPO, "harness/state/drop.json");
const MODE: "A" | "B" = existsSync(DROP) ? "B" : "A";
const DONE = join(REPO, "harness/state/done.json");   // completion ledger (runtime state, like drop.json — not tracked)
// v6 blueprint intake — the second state-file trigger, peer of drop.json. A human drops
// blueprints into docs/v6/; the exact file BP00_manifest.md is the arming marker. Until it
// exists, every blocked_on:"blueprints" task is held out of the queue.
const V6 = existsSync(join(REPO, "docs/v6/BP00_manifest.md"));
// C-track catalog intake — the third state-file trigger. C.0's probe deposits the per-context
// create-capability catalog; a human merges it. Until it exists, every blocked_on:"catalog"
// task (C.1–C.6) is held out of the queue — they read the catalog's gaps, so arming them
// catalog-less would be a sprint without a target.
const CTX = existsSync(join(REPO, "harness/notes/context_capability_21.json"));
// S-track studio-posture intake — the fourth state-file trigger. A human declares the
// deployment posture (mode + identity model + auto_approve) by writing posture.json; it is
// runtime state (untracked, peer of drop.json), NOT a committed catalog. Until it exists,
// every blocked_on:"posture" task (S.1–S.3) is held out of the queue — they cannot enforce a
// consent/RBAC posture the deployment has not declared. S.0 (a human gate) prompts the write.
const POSTURE = existsSync(join(REPO, "harness/state/posture.json"));

// ---------- helpers ----------
function sh(cmd: string, cmdArgs: string[], cwd = REPO) {
  return spawnSync(cmd, cmdArgs, { cwd, encoding: "utf8", shell: process.platform === "win32" });
}

function ensureWorktree(id: string): string {
  const wt = join(REPO, WORKTREE_DIR, `feature-${id}`);
  if (existsSync(wt)) return wt;
  mkdirSync(join(REPO, WORKTREE_DIR), { recursive: true });
  const branch = `harness/${id}`;
  // ADAPT: assumes a clean main and that you build off it. Adjust base ref if needed.
  const r = sh("git", ["worktree", "add", "-b", branch, wt, "HEAD"]);
  if (r.status !== 0) log(`${c.warn}  worktree note: ${(r.stderr || "").trim()}${c.off}`);
  return wt;
}

// Red-driver (--drive): select the next blocking-red readiness finding and map it to its
// remediation task. Phase 2 of the instinct loop — protect green (the ratchet) already lands;
// this SELECTS the red to target. It refreshes the studio-readiness verdict against the REPO
// first (so a stale on-disk snapshot can never mis-target), then keys on the POSTURE-SCOPED
// `blockers` set — NEVER findings_live — so posture-accepted trade-offs are structurally
// un-drivable and a solo posture (blockers:[]) idles correctly. It selects only; runTask is
// unchanged, so human-gated criticals (S.1–S.3) still surface as GATED (a human MUST author
// security fixes); only ungated reds (S.4–S.6) remediate autonomously. Writes nothing itself.
function selectRedTask(): string | null {
  const verdictPath = join(REPO, "harness/state/studio_readiness_verdict.json");
  const stampBefore = existsSync(verdictPath)
    ? (() => { try { return JSON.parse(readFileSync(verdictPath, "utf8")).generated ?? ""; } catch { return ""; } })()
    : "";
  // freshness: recompute the capstone against the REPO so we never drive on a stale snapshot
  const r = sh(PYTHON, ["harness/verify/checks.py", "--task", "S.R", "--worktree", REPO, "--mode", MODE]);
  if (r.status !== 0) {
    log(`${c.warn}  --drive: S.R refresh failed (status ${r.status}) — refusing to drive on a stale verdict.${c.off}`);
    return null;
  }
  if (!existsSync(verdictPath)) {
    log(`${c.warn}  --drive: no studio_readiness_verdict.json after refresh — nothing to drive.${c.off}`);
    return null;
  }
  let v: any;
  try { v = JSON.parse(readFileSync(verdictPath, "utf8")); }
  catch (e) { log(`${c.warn}  --drive: unreadable verdict — ${String(e)}${c.off}`); return null; }
  if ((v.generated ?? "") === stampBefore && stampBefore !== "") {
    log(`${c.warn}  --drive: verdict 'generated' did not advance — the S.R refresh may have silently failed; refusing to drive on a possibly-stale verdict.${c.off}`);
    return null;
  }
  const blockers: string[] = Array.isArray(v.blockers) ? v.blockers : [];
  if (String(v.verdict ?? "").startsWith("READY") || blockers.length === 0) {
    log(`${c.dim}  --drive: no blocking-red under ${v.posture ?? "?"} posture — nothing to drive (${v.verdict ?? "?"}).${c.off}`);
    return null;
  }
  const finding = blockers[0];  // honest "next blocking-red": strict order, never skip a gate to do easier work
  const target = TASKS.find((t: any) => t.phase === "studio" && (t.verify ?? []).includes(finding));
  if (!target) {
    log(`${c.warn}  --drive: blocking-red '${finding}' maps to no studio task — surface to a human.${c.off}`);
    return null;
  }
  log(`${c.sig}  --drive: next blocking-red '${finding}' → ${target.id} (${target.title}).${c.off}`);
  return target.id;
}

/**
 * Spawn a fresh, headless Claude in the worktree.
 *
 * IMPORTANT (Windows): the Generator/Evaluator system prompt and the user message are large,
 * multi-line, and full of markdown specials (backticks, quotes, $, |, #). Passing those on the
 * command line routes them through cmd.exe (shell:true is required to launch claude.cmd), which
 * mangles the line breaks and can break the invocation entirely. So we keep the command line
 * tiny: the system prompt goes to a temp FILE (--append-system-prompt-file), and the user
 * message goes in via STDIN. Only small flags ever touch the command line.
 *
 * Verified on Claude Code 2.x: -p, --permission-mode acceptEdits, and --append-system-prompt-file
 * are all valid. acceptEdits lets the headless agent apply edits in the throwaway worktree; your
 * deny rules still hold (no push, no merge, VERSION + harness untouched).
 */
function runAgent(systemPrompt: string, userMsg: string, cwd: string): string {
  if (DRY) return "";
  mkdirSync(join(cwd, ".claude"), { recursive: true });
  const sysFile = join(cwd, ".claude", `sysprompt-${Date.now()}-${Math.floor(Math.random() * 1e6)}.md`);
  writeFileSync(sysFile, systemPrompt);
  // --settings (highest CLI precedence) loads harness/agent-settings.json, which blanks
  // ANTHROPIC_API_KEY so spawned agents auth on the Max-plan login. Without it, each child
  // inherits the credit-starved .env key → 400 credit-too-low AND the "claude.ai connectors
  // disabled" banner on every spawn. Forward-slash both paths: shell:true joins args WITHOUT
  // escaping (Node DEP0190), so a backslashed Windows path is mangled → "settings file not
  // found" → silent fallback to the credit-starved key. --settings goes first.
  const AGENT_SETTINGS = join(REPO, "harness/agent-settings.json").replace(/\\/g, "/");
  try {
    const r = spawnSync(
      CLAUDE_BIN,
      ["--settings", AGENT_SETTINGS, "-p", "--permission-mode", "acceptEdits", "--append-system-prompt-file", sysFile.replace(/\\/g, "/")],
      {
        cwd,
        encoding: "utf8",
        shell: process.platform === "win32",
        input: userMsg,                 // prompt via stdin — keeps it off the command line
        maxBuffer: 64 * 1024 * 1024,
        // Worktree-shadowing guard (flywheel U.1 meta-finding): the agent's bare
        // `pytest` would resolve `synapse` from the MAIN checkout via a dev-machine
        // editable install — pin this worktree's package first for all children.
        env: {
          ...process.env,
          PYTHONPATH: `${cwd.replace(/\\/g, "/")}/python${process.platform === "win32" ? ";" : ":"}${process.env.PYTHONPATH ?? ""}`,
        },
      }
    );
    if (r.status !== 0) log(`${c.warn}  agent exited ${r.status}: ${(r.stderr || "").slice(0, 400)}${c.off}`);
    return r.stdout ?? "";
  } finally {
    try { unlinkSync(sysFile); } catch {}
  }
}


function runChecks(task: any, cwd: string): any {
  if (DRY) return { _dry: true, verdict: "SKIPPED" };
  // shell:true (required for the .cmd launcher) makes cmd.exe re-parse args WITHOUT escaping
  // (Node DEP0190): a spaced path shatters and an empty-string arg vanishes — the latter made
  // checks.py argparse-error ("--hython: expected one argument") whenever HYTHON was unset, read
  // downstream as a spurious BLOCKED. So quote+forward-slash path args (only when shell is on),
  // and omit --hython entirely when unset — checks.py then reports not-runnable, as intended.
  const win = process.platform === "win32";
  const qp = (p: string) => (win ? `"${String(p).replace(/\\/g, "/")}"` : String(p));
  const checkArgs = ["harness/verify/checks.py", "--task", task.id, "--worktree", qp(cwd), "--mode", MODE];
  if (HYTHON) checkArgs.push("--hython", qp(HYTHON));
  const r = spawnSync(
    PYTHON,
    checkArgs,
    { cwd: REPO, encoding: "utf8", shell: win, maxBuffer: 32 * 1024 * 1024 }
  );
  const out = r.stdout ?? "";
  // checks.py prints one JSON object, but hython/Houdini can emit a startup banner or warnings
  // onto stdout when spawned. Extract the JSON object rather than parsing the whole stream.
  const m = out.match(/\{[\s\S]*"verdict"[\s\S]*\}/);
  if (m) { try { return JSON.parse(m[0]); } catch {} }
  try { return JSON.parse(out); } catch {}
  // Could not read JSON. The check PASSES when run by hand, so something differs when the
  // harness spawns it. Dump the raw streams so we can see exactly what it received.
  try {
    mkdirSync(join(REPO, ".claude"), { recursive: true });
    writeFileSync(
      join(REPO, ".claude", `checks_debug_${task.id}.txt`),
      `=== exit code: ${r.status} ===\n\n=== STDOUT (what run.ts tried to parse) ===\n${out}\n\n=== STDERR ===\n${r.stderr ?? ""}\n`
    );
    log(`  ${c.dim}(raw check output written to .claude/checks_debug_${task.id}.txt)${c.off}`);
  } catch {}
  return { verdict: "ERROR", detail: (out || r.stderr || "checks.py produced no JSON").slice(0, 600) };
}

/** Pull the first {...} block containing gate_status out of the evaluator's reply. */
function parseVerdict(raw: string): any {
  const m = raw.match(/\{[\s\S]*"gate_status"[\s\S]*\}/);
  if (!m) return { gate_status: "FAIL", scores: {}, remediation_manifest: [
    { target_file: "(harness)", issue: "Evaluator output was not parseable JSON.", evidence: raw.slice(0, 400) } ] };
  try { return JSON.parse(m[0]); }
  catch { return { gate_status: "FAIL", scores: {}, remediation_manifest: [
    { target_file: "(harness)", issue: "Evaluator JSON failed to parse.", evidence: m[0].slice(0, 400) } ] }; }
}

function writeTicket(cwd: string, manifest: any[]) {
  const dir = join(cwd, ".claude");
  mkdirSync(dir, { recursive: true });
  const lines = manifest.map((m, i) =>
    `## Ticket ${i + 1}\n- **file:** \`${m.target_file}\`\n- **issue:** ${m.issue}\n- **evidence:** ${m.evidence}\n`);
  writeFileSync(join(dir, "remediation_ticket.md"),
    `# REPAIR MODE — fix only what is below. Do not refactor unrelated files.\n\n${lines.join("\n")}`);
}

/** Turn deterministic guardrail violations into repair tickets — these are boundary non-goals. */
function ticketsFromGuardrails(facts: any): any[] {
  const g = facts.guardrails ?? {};
  return (facts.guardrail_violations ?? []).map((name: string) => ({
    target_file: `(guardrail) ${name}`,
    issue: `SYNAPSE_H22_BOUNDARY.md non-goal violated: ${name}.`,
    evidence: `checks.py guardrail ${name} → ok:false — ${g[name]?.detail ?? "no detail"}`,
    vector: "boundary",
  }));
}

function appendProgress(line: string) {
  if (DRY) return;
  const stamp = new Date().toISOString().replace("T", " ").slice(0, 16);
  writeFileSync(PROGRESS, `${readFileSync(PROGRESS, "utf8")}\n- ${stamp} · ${line}`);
}

// ---------- completion ledger (Upgrade 1: monotonic progress + resume) ----------
// The loop had no memory of what passed — a re-run re-did the whole queue, and a kill
// lost the campaign. This records each PASS keyed by a hash of the task's `refs` source.
// A task is skipped on re-run only if it passed AND its refs are byte-identical to pass
// time; editing a ref (or merging its worktree, which changes main) re-arms it. Nothing
// but PASS is ever recorded — BLOCKED/GATED must surface every run. --force / --task override.
type DoneRec = { verdict: string; refs_hash: string; commit: string; ts: string };
function loadDone(): Record<string, DoneRec> {
  if (!existsSync(DONE)) return {};
  try { return JSON.parse(readFileSync(DONE, "utf8")); } catch { return {}; }
}
const doneLog: Record<string, DoneRec> = loadDone();

// Hash the refs' contents. A ref may be a not-yet-created file or a directory; when it is
// a readable file we fold its bytes in, else only its path — best-effort skip, never a gate.
function refsHash(task: any): string {
  const h = createHash("sha256");
  for (const ref of (task.refs ?? [])) {
    h.update(String(ref) + "\0");
    try { const p = join(REPO, ref); if (existsSync(p)) h.update(readFileSync(p)); } catch {}
  }
  return h.digest("hex").slice(0, 16);
}
function isDone(task: any): boolean {
  const rec = doneLog[task.id];
  if (!rec || rec.verdict !== "PASS" || rec.refs_hash !== refsHash(task)) return false;
  // Only honor a skip when the hash folded REAL file bytes. A task with no refs, or only
  // directory/missing refs, hashes to a near-constant and would otherwise bank forever.
  return (task.refs ?? []).some((r: string) => { try { return statSync(join(REPO, r)).isFile(); } catch { return false; } });
}
function recordDone(task: any, wt: string) {
  if (DRY) return;
  let commit = "";
  try { const r = sh("git", ["rev-parse", "HEAD"], wt); if (r.status === 0) commit = (r.stdout || "").trim().slice(0, 12); } catch {}
  doneLog[task.id] = { verdict: "PASS", refs_hash: refsHash(task), commit, ts: new Date().toISOString().slice(0, 19) + "Z" };
  // atomic: a kill mid-write must not truncate done.json (loadDone would then wipe the ledger).
  try { writeFileSync(DONE + ".tmp", JSON.stringify(doneLog, null, 2) + "\n"); renameSync(DONE + ".tmp", DONE); } catch {}
}

// ---------- ratification surface (Upgrade 2: the flywheel's missing seam) ----------
// run.ts never opened flywheel_queue.json before, so ratified:false candidates sat dormant.
// This surfaces them at run end with evidence + the exact line to flip — the human's whole
// interaction is one boolean. STRICTLY READ-ONLY: the harness reads `ratified`, never writes
// it (the anti-runaway anchor, spec-U1-wiring-flywheel.md). Evidence-free ⇒ flagged INVALID.
function surfaceRatification() {
  const QUEUE = join(REPO, "harness/state/flywheel_queue.json");
  if (!existsSync(QUEUE)) return;
  let raw = "", data: any;
  try { raw = readFileSync(QUEUE, "utf8"); data = JSON.parse(raw); } catch { return; }
  const cycles = Array.isArray(data.cycles) ? data.cycles : [];
  const pending = cycles.filter((cy: any) => cy && typeof cy === "object" && cy.ratified === false);
  if (!pending.length) return;
  const lines = raw.split("\n");
  head("ratification pending — flywheel candidates (a human flips ratified, never the harness)");
  for (const cyc of pending) {
    const idLine = lines.findIndex((l: string) => l.includes('"id"') && l.includes(`"${cyc.id}"`));
    // bound the forward scan to THIS cycle's object — stop before the next cycle's id line, so a
    // reversed field order or an adjacent cycle can't make us borrow the wrong ratified line.
    let stop = lines.length;
    for (let i = idLine + 1; i < lines.length; i++) { if (/"id"\s*:/.test(lines[i])) { stop = i; break; } }
    let ratLine = -1;
    for (let i = idLine; i >= 0 && i < stop; i++) { if (/"ratified"\s*:\s*false/.test(lines[i])) { ratLine = i + 1; break; } }
    const ev = Array.isArray(cyc.evidence) ? cyc.evidence : [];
    const invalid = ev.length === 0;
    log(`  ${invalid ? c.bad : c.sig}${cyc.id}${c.off}  ${cyc.title ?? ""}`);
    log(`     ${c.dim}status:${c.off} ${cyc.status ?? "?"}    ${c.dim}evidence:${c.off} ${invalid ? `${c.bad}NONE — INVALID candidate (evidence-free; reject at review)${c.off}` : `${ev.length} artifact(s)`}`);
    if (!invalid) for (const e of ev) log(`        ${c.dim}· ${e}${c.off}`);
    log(ratLine > 0
      ? `     ${c.warn}→ to arm: set ratified:true at harness/state/flywheel_queue.json:${ratLine}${c.off}`
      : `     ${c.warn}→ to arm: set this cycle's "ratified" to true in harness/state/flywheel_queue.json${c.off}`);
  }
}

// ---------- blueprint intake surface (v6 track: paper → disk) ----------
// The v6 plan exists only on paper until a human drops blueprints into docs/v6/. While the
// track is held this prints the canonical drop list — the human's whole interaction is
// copying files in and committing. STRICTLY READ-ONLY: the harness never authors blueprints
// BP00–BP08 (BP09/BP10 are V-task deliverables, authored in worktrees, not here). Once
// armed it prints nothing — the queue speaks.
function surfaceBlueprintIntake() {
  if (V6) return;
  if (!TASKS.some((t: any) => t.blocked_on === "blueprints")) return;
  head("v6 track held — blueprint drop wanted (a human drops files, never the harness)");
  log(`  ${c.warn}required:${c.off}    docs/v6/BP00_manifest.md  (the arming marker — exact name)`);
  log(`  ${c.dim}recommended: docs/v6/BP01_*.md … BP08_*.md  (human-authored, BP0N_*.md pattern)${c.off}`);
  log(`  ${c.dim}harness-authored — do NOT drop: BP09_iteration_controller.md, BP10_knowledge_base.md${c.off}`);
  log(`  ${c.dim}contract + drop checklist: docs/v6/INTAKE.md — COMMIT the drop; worktrees fork from HEAD${c.off}`);
  // --task cannot pierce the hold: the blueprints filter runs before ONLY selects, so naming
  // a held V-task yields an empty queue. Say so instead of printing a bare empty summary.
  if (ONLY && TASKS.some((t: any) => t.id === ONLY && t.blocked_on === "blueprints"))
    log(`  ${c.warn}--task ${ONLY} cannot override this hold — V-tasks stay filtered until BP00_manifest.md lands.${c.off}`);
}

// ---------- context intake surface (C track: probe → catalog) ----------
// The context track holds until the capability catalog lands on disk. While held this
// prints the one command that deposits it — the human's whole interaction is running C.0
// and merging its worktree. STRICTLY READ-ONLY: the harness never authors the catalog here
// (C.0's probe writes it, in its worktree, under hython). Once armed it prints nothing —
// the queue speaks.
function surfaceContextIntake() {
  if (CTX) return;
  if (!TASKS.some((t: any) => t.blocked_on === "catalog")) return;
  head("context track held — capability catalog wanted (C.0 deposits it, a human merges)");
  log(`  ${c.warn}to arm:${c.off}      bun run harness/run.ts --task C.0`);
  log(`  ${c.dim}then MERGE the C.0 worktree — the catalog must reach HEAD (worktrees fork from HEAD)${c.off}`);
  log(`  ${c.dim}once harness/notes/context_capability_21.json is committed, C.1–C.6 arm and re-rank off its gaps${c.off}`);
  // --task cannot pierce the hold: the catalog filter runs before ONLY selects, so naming
  // a held C-task yields an empty queue. Say so instead of printing a bare empty summary.
  if (ONLY && TASKS.some((t: any) => t.id === ONLY && t.blocked_on === "catalog"))
    log(`  ${c.warn}--task ${ONLY} cannot override this hold — C-tasks stay filtered until the catalog lands.${c.off}`);
}

// ---------- studio posture surface (S track: declare → policy/consent/RBAC arm) ----------
// The studio-readiness track holds until a human declares the deployment posture on disk.
// posture.json is a machine-level declaration (mode + identity model + auto_approve), the
// fourth state-file trigger and peer of drop.json. While held this prints the declaration
// template — the human's whole interaction is writing the three fields. STRICTLY READ-ONLY:
// the harness never authors posture.json (S.0 is a human gate; the human writes it). Once
// declared it prints nothing — the queue speaks.
function surfaceStudioPosture() {
  if (POSTURE) return;
  if (!TASKS.some((t: any) => t.blocked_on === "posture")) return;
  head("studio track held — deployment posture wanted (a human declares it, never the harness)");
  log(`  ${c.warn}to arm:${c.off}      write harness/state/posture.json with the three fields:`);
  log(`  ${c.dim}    mode           solo | studio | farm   (the deployment topology)${c.off}`);
  log(`  ${c.dim}    identity_model free text — who the caller is and how identity resolves${c.off}`);
  log(`  ${c.dim}    auto_approve   bool — allowed in solo; studio/farm must default-deny${c.off}`);
  log(`  ${c.dim}contract + example: harness/notes/spec-S-studio-readiness.md · harness/state/posture.json.example${c.off}`);
  // --task cannot pierce the hold: the posture filter runs before ONLY selects, so naming a
  // held S-task yields an empty queue. Say so instead of printing a bare empty summary.
  if (ONLY && TASKS.some((t: any) => t.id === ONLY && t.blocked_on === "posture"))
    log(`  ${c.warn}--task ${ONLY} cannot override this hold — S.1–S.3 stay filtered until posture.json lands.${c.off}`);
}

// ---------- the loop ----------
function runTask(task: any): "PASS" | "BLOCKED" | "GATED" {
  // human gate — never auto-handled
  if (task.human_gate) {
    log(`${c.warn}  ⚑ HUMAN GATE — ${task.human_gate.decision}${c.off}`);
    if (task.human_gate.recommended) log(`     recommendation: ${c.sig}${task.human_gate.recommended}${c.off} — ${task.human_gate.why}`);
    else if (task.human_gate.why) log(`     ${c.dim}${task.human_gate.why}${c.off}`);
    return "GATED";
  }

  // dry run: describe, never mutate (no worktree, no branch, no agent).
  if (DRY) {
    log(`  ${c.dim}(dry: would create worktree feature-${task.id}, generate, then check ${(task.verify ?? []).join(", ") || "—"} + guardrails)${c.off}`);
    return "PASS";
  }

  const wt = ensureWorktree(task.id);
  log(`  worktree: ${c.dim}${wt}${c.off}`);

  for (let round = 0; round <= MAX_ROUNDS; round++) {
    const refs = (task.refs ?? []).join(", ");
    const ticketHint = round === 0
      ? `New feature sprint. Read harness/state/claude-progress.md, then implement task ${task.id}: "${task.title}". Touch only: ${refs}. Make ONE atomic commit.`
      : `REPAIR round ${round}. Read .claude/remediation_ticket.md and fix exactly what it lists. Re-verify locally. One atomic commit.`;

    log(`  ${round === 0 ? "generate" : `repair r${round}`} …`);
    runAgent(GEN_PROMPT, ticketHint, wt);

    const facts = runChecks(task, wt);
    if (DRY) { log(`  ${c.dim}(dry: would check ${(task.verify ?? []).join(", ") || "—"} + guardrails)${c.off}`); return "PASS"; }
    log(`  checks → ${facts.verdict === "PASS" ? c.ok : c.warn}${facts.verdict}${c.off}`);

    // unwired guardrails: surface, do not block
    const gw = facts.guardrail_unwired ?? [];
    if (gw.length) log(`  ${c.warn}guardrails unwired (warn, not blocking): ${gw.join(", ")}${c.off}`);

    // DETERMINISTIC guardrail enforcement — boundary non-goals fail the gate before the Evaluator
    const gv = facts.guardrail_violations ?? [];
    if (gv.length) {
      log(`  ${c.bad}GUARDRAIL FAIL${c.off} ${c.dim}${gv.join(", ")}${c.off}`);
      writeTicket(wt, ticketsFromGuardrails(facts));
      continue; // regenerate against the boundary ticket; no Evaluator round spent
    }

    const verdict = parseVerdict(runAgent(
      EVAL_PROMPT,
      `Evaluate task ${task.id}.\n\nTASK:\n${JSON.stringify(task, null, 2)}\n\nCHECK FACTS:\n${JSON.stringify(facts, null, 2)}\n\nReturn your markdown report and the JSON verdict block.`,
      wt));

    const s = verdict.scores ?? {};
    log(`  evaluator → ${verdict.gate_status === "PASS" ? c.ok : c.bad}${verdict.gate_status}${c.off} ${c.dim}${Object.entries(s).map(([k, v]) => `${k}:${v}`).join(" ")}${c.off}`);

    if (verdict.gate_status === "PASS") { appendProgress(`${task.id} PASS — ${task.title}`); recordDone(task, wt); return "PASS"; }
    writeTicket(wt, verdict.remediation_manifest ?? []);
  }

  appendProgress(`${task.id} BLOCKED after ${MAX_ROUNDS} rounds — needs a human — ${task.title}`);
  return "BLOCKED";
}

// ---------- main ----------
head(`SYNAPSE → H22 harness  ·  MODE ${MODE}${DRY ? "  (dry run)" : ""}`);
if (MODE === "A") log(`${c.dim}  H22 not dropped — grinding Phase 0 on H21. drop.json absent.${c.off}`);
else log(`${c.dim}  drop.json present — post-drop pipeline armed.${c.off}`);
if (!HYTHON && !DRY) log(`${c.warn}  HYTHON unset — checks that cook/import will report not-runnable. Set it to your Houdini bin/hython.${c.off}`);
if (V6) {
  log(`${c.dim}  v6 track armed — docs/v6/BP00_manifest.md present. V-tasks in the queue.${c.off}`);
  // Worktrees fork from HEAD (ensureWorktree), so an UNCOMMITTED drop arms the track here
  // while every V-task worktree — and every worktree-relative check — sees no docs/v6 at
  // all. Catch that before it burns MAX_ROUNDS on a baffling "BP00 missing". Read-only.
  const st = sh("git", ["status", "--porcelain", "docs/v6"]);
  if (st.status === 0 && (st.stdout || "").trim())
    log(`${c.warn}  docs/v6 has uncommitted changes — worktrees fork from HEAD and will NOT see them. Commit the drop first.${c.off}`);
} else log(`${c.dim}  v6 track held — docs/v6/BP00_manifest.md absent. Blueprint drop arms it (docs/v6/INTAKE.md).${c.off}`);
if (CTX) {
  log(`${c.dim}  context track armed — harness/notes/context_capability_21.json present. C.1–C.6 in the queue.${c.off}`);
  // Same trap as the v6 drop: an UNCOMMITTED catalog arms the track here while every C-task
  // worktree — and every worktree-relative check — forks from HEAD and sees no catalog at
  // all. Catch that before it burns MAX_ROUNDS on a baffling "run C.0 first". Read-only.
  const st = sh("git", ["status", "--porcelain", "harness/notes/context_capability_21.json"]);
  if (st.status === 0 && (st.stdout || "").trim())
    log(`${c.warn}  context_capability_21.json has uncommitted changes — worktrees fork from HEAD and will NOT see them. Commit the catalog first.${c.off}`);
} else log(`${c.dim}  context track held — harness/notes/context_capability_21.json absent. C.0 deposits it (--task C.0).${c.off}`);
// posture.json is read from the MAIN repo by checks.py (a machine-level declaration), not from
// a worktree — so unlike the v6/context drops there is no uncommitted-in-worktree trap here.
if (POSTURE) log(`${c.dim}  studio track armed — harness/state/posture.json present. S.1–S.3 in the queue.${c.off}`);
else log(`${c.dim}  studio track held — harness/state/posture.json absent. A human declares the posture via S.0 (--task S.0).${c.off}`);

let queue = TASKS.filter((t: any) => t.mode === "A" || MODE === "B");
queue = queue.filter((t: any) => !(t.mode === "B" && t.blocked_on === "drop" && MODE === "A"));
queue = queue.filter((t: any) => !(t.blocked_on === "blueprints" && !V6));
queue = queue.filter((t: any) => !(t.blocked_on === "catalog" && !CTX));
queue = queue.filter((t: any) => !(t.blocked_on === "posture" && !POSTURE));
if (ONLY) queue = queue.filter((t: any) => t.id === ONLY);
if (DRIVE) {                              // red-driver narrows to the next blocking-red (or idles)
  const redId = selectRedTask();
  queue = redId ? queue.filter((t: any) => t.id === redId) : [];
}

const result: Record<string, string> = {};
for (const task of queue) {            // WIP = 1 — strictly sequential
  head(`${task.id} · ${task.title}`);
  if (!ONLY && !DRIVE && !FORCE && isDone(task)) {   // completion ledger — skip work already banked (--drive re-attempts a banked finding)
    log(`  ${c.dim}✓ already passed (refs unchanged) — skipping. --force re-runs.${c.off}`);
    result[task.id] = "SKIP";
    continue;
  }
  result[task.id] = runTask(task);
}

// ---------- summary (no auto-merge — that's your gate) ----------
head("summary");
const passed = Object.entries(result).filter(([, v]) => v === "PASS").map(([k]) => k);
const blocked = Object.entries(result).filter(([, v]) => v === "BLOCKED").map(([k]) => k);
const gated = Object.entries(result).filter(([, v]) => v === "GATED").map(([k]) => k);
const skipped = Object.entries(result).filter(([, v]) => v === "SKIP").map(([k]) => k);
log(`  ${c.ok}PASS ${passed.length}${c.off}  ${c.bad}BLOCKED ${blocked.length}${c.off}  ${c.warn}GATED ${gated.length}${c.off}  ${c.dim}SKIP ${skipped.length}${c.off}`);
if (passed.length) log(`  ${c.dim}passing in worktrees, awaiting YOUR merge: ${passed.join(", ")}${c.off}`);
if (blocked.length) log(`  ${c.warn}needs a human: ${blocked.join(", ")}${c.off}`);
if (gated.length) log(`  ${c.warn}human-gated (decision required): ${gated.join(", ")}${c.off}`);
if (skipped.length) log(`  ${c.dim}already banked (completion ledger): ${skipped.join(", ")}${c.off}`);

// Upgrade 2 — surface flywheel candidates awaiting human ratification (read-only)
surfaceRatification();
// v6 track — surface the blueprint drop list while the track is held (read-only)
surfaceBlueprintIntake();
// context track — surface the C.0 arming path while the catalog is absent (read-only)
surfaceContextIntake();
// studio track — surface the posture declaration template while the track is held (read-only)
surfaceStudioPosture();
log("");
