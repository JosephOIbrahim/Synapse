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
import { existsSync, readFileSync, writeFileSync, mkdirSync, unlinkSync } from "node:fs";
import { resolve, join } from "node:path";

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
  const r = spawnSync(
    PYTHON,
    ["harness/verify/checks.py", "--task", task.id, "--worktree", cwd, "--hython", HYTHON, "--mode", MODE],
    { cwd: REPO, encoding: "utf8", shell: process.platform === "win32", maxBuffer: 32 * 1024 * 1024 }
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

// ---------- the loop ----------
function runTask(task: any): "PASS" | "BLOCKED" | "GATED" {
  // human gate — never auto-handled
  if (task.human_gate) {
    log(`${c.warn}  ⚑ HUMAN GATE — ${task.human_gate.decision}${c.off}`);
    if (task.human_gate.recommended) log(`     recommendation: ${c.sig}${task.human_gate.recommended}${c.off} — ${task.human_gate.why}`);
    else if (task.human_gate.why) log(`     ${c.dim}${task.human_gate.why}${c.off}`);
    return "GATED";
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

    if (verdict.gate_status === "PASS") { appendProgress(`${task.id} PASS — ${task.title}`); return "PASS"; }
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

let queue = TASKS.filter((t: any) => t.mode === "A" || MODE === "B");
queue = queue.filter((t: any) => !(t.mode === "B" && t.blocked_on === "drop" && MODE === "A"));
if (ONLY) queue = queue.filter((t: any) => t.id === ONLY);

const result: Record<string, string> = {};
for (const task of queue) {            // WIP = 1 — strictly sequential
  head(`${task.id} · ${task.title}`);
  result[task.id] = runTask(task);
}

// ---------- summary (no auto-merge — that's your gate) ----------
head("summary");
const passed = Object.entries(result).filter(([, v]) => v === "PASS").map(([k]) => k);
const blocked = Object.entries(result).filter(([, v]) => v === "BLOCKED").map(([k]) => k);
const gated = Object.entries(result).filter(([, v]) => v === "GATED").map(([k]) => k);
log(`  ${c.ok}PASS ${passed.length}${c.off}  ${c.bad}BLOCKED ${blocked.length}${c.off}  ${c.warn}GATED ${gated.length}${c.off}`);
if (passed.length) log(`  ${c.dim}passing in worktrees, awaiting YOUR merge: ${passed.join(", ")}${c.off}`);
if (blocked.length) log(`  ${c.warn}needs a human: ${blocked.join(", ")}${c.off}`);
if (gated.length) log(`  ${c.warn}human-gated (decision required): ${gated.join(", ")}${c.off}`);
log("");
