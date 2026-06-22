#!/usr/bin/env python3
"""
SYNAPSE harness — long-running build harness for the SYNAPSE Houdini-22 panel work.

Lineage: the architecture is ANVIL's (the harness that governed UnrealEngine_Bridge).
This is a SYNAPSE-specific instance — re-pathed to .synapse/, contracted for the H22
blueprint, and extended with one thing a Houdini harness needs that a generic one does
not: a PHANTOM-API fence (deny / assert host calls that don't exist in the live runtime).
No UE code or IP is carried; only the architecture.

Control plane: this is a plain Python CLI you run from PowerShell. It is NOT a Claude Code
session — it SPAWNS headless `claude -p` as its one sequential worker, writing
.synapse/state.json before each spawn. The fences + session ritual run inside each spawned
session via Claude Code hooks (.claude/settings.json).

Billing: headless `claude -p` draws the Agent SDK credit / metered API — NOT the free
interactive subscription. The budget governor + footgun guard keep you inside it.

Usage:
    python .synapse/harness.py init quarantine-dead-tree
    python .synapse/harness.py queue add quarantine-dead-tree failure-trail theme-seed-tokens docking-minimums
    python .synapse/harness.py run --autonomy amber --budget 12       # halts at $12 metered; refuses red
    python .synapse/harness.py run --autonomy green --dry-run          # rehearse, no spend
    python .synapse/harness.py features quarantine-dead-tree
    python .synapse/harness.py status

Requires PyYAML. Optional: usd-core (for the USD cognitive-twin memory backend).
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory as memmod  # swappable cross-session memory backend

try:
    import yaml
except ImportError:
    sys.stderr.write("SYNAPSE harness needs PyYAML for contracts:  pip install pyyaml\n")
    sys.exit(1)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SYN = os.path.join(ROOT, ".synapse")
QUEUE = os.path.join(SYN, "queue.jsonl")
TIERS = {"green": 0, "amber": 1, "red": 2}


# ---------------- config + io ----------------
def load_config():
    cfg = {
        "gate_cmd": "pytest -q",
        "smoke_cmd": "",
        "branch_prefix": "synapse/",
        "work_dir": ".synapse/work",
        "memory_backend": "flat",          # "flat" | "usd"
        "billing_mode": "subscription",    # "subscription" (claude -p on plan/credit) | "api"
        "budget_usd": 12.0,                # hard stop for a single `run`; 0 = unlimited (not advised)
        "max_turns": 25,
        "max_sessions": 6,
        "stuck_timeout_sec": 1800,
        "claude_bin": "claude",
        "permission_mode": "acceptEdits",  # the fence 'deny' holds even under bypass
        "allowed_tools": "Edit Write MultiEdit Read Grep Glob Bash",
        "models": {"planner": "opus", "worker": "sonnet"},
        "scout_model": "opus",            # scout synthesis pass (read-only)
        "hython_bin": "hython",           # for the live dir(hou) audit
        "review_docs": [],                # paths fed to scout --synthesize / plan
        "scout_max_age_min": 120,         # warn if the scout report is older than this
    }
    path = os.path.join(SYN, "config.yaml")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            cfg.update({k: v for k, v in (yaml.safe_load(fh) or {}).items() if v is not None})
    return cfg


def load_fence():
    path = os.path.join(SYN, "ip_fence.yaml")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    return {}


def load_contract(cid):
    path = os.path.join(SYN, "contracts", cid + ".yaml")
    if not os.path.exists(path):
        sys.exit(f"SYNAPSE harness: no contract '{cid}' at {path}")
    with open(path, encoding="utf-8") as fh:
        c = yaml.safe_load(fh) or {}
    c.setdefault("id", cid)
    c.setdefault("autonomy", "amber")
    return c


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_state(state):
    with open(os.path.join(SYN, "state.json"), "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)


def append_ledger(entry):
    with open(os.path.join(SYN, "ledger.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def task_dir(cid, cfg):
    return os.path.join(ROOT, cfg["work_dir"], cid)


# ---------------- queue ----------------
def cmd_queue(args):
    if args.action == "add":
        with open(QUEUE, "a", encoding="utf-8") as fh:
            for cid in args.ids:
                fh.write(json.dumps({"id": cid, "added": now()}) + "\n")
        print(f"queued: {', '.join(args.ids)}")
    elif args.action == "list":
        items = queue_items()
        if not items:
            print("queue empty.")
        for it in items:
            c = load_contract(it["id"])
            mdl = c.get("model", "(default)")
            print(f"  [{c.get('autonomy'):5}] {it['id']:24} {mdl:8} {c.get('goal','')[:46]}")
    elif args.action == "clear":
        open(QUEUE, "w").close()
        print("queue cleared.")


def queue_items():
    if not os.path.exists(QUEUE):
        return []
    return [json.loads(l) for l in open(QUEUE, encoding="utf-8") if l.strip()]


# ---------------- IP pre-flight ----------------
def _prefix(glob):
    return glob.split("*")[0].rstrip("/")


def contract_violates_ip(contract, fence):
    bad = []
    for pat in contract.get("owns", []) or []:
        a = _prefix(pat)
        if not a:
            continue
        for fp in fence.get("forbidden_paths", []) or []:
            b = _prefix(fp)
            if not b:
                continue
            if a == b or a.startswith(b + "/") or b.startswith(a + "/"):
                bad.append((pat, fp))
    return bad


# ---------------- the session loop ----------------
def build_prompt(contract, gate_cmd):
    owns = contract.get("owns", [])
    return (
        f"You are a coding agent making INCREMENTAL progress on a long-running task. "
        f"You start with no memory of prior sessions — your orientation (feature checklist + "
        f"recent progress) was just injected into context.\n\n"
        f"TASK GOAL: {contract.get('goal','')}\n\n"
        f"Steps:\n"
        f"  1. `pwd`. Run `{gate_cmd}` once to confirm a GREEN baseline. If red, fix that first.\n"
        f"  2. Pick the SINGLE highest-priority feature that is not passing.\n"
        f"  3. Implement only that feature. Edit ONLY these paths: {owns}. Keep changes minimal.\n"
        f"     Do not add features, refactor unrelated code, or weaken/delete tests.\n"
        f"  4. PHANTOM-API RULE: never call a hou.* / pdg.* symbol unless it is verified in the\n"
        f"     runtime manifest. The fence will DENY an unverified host call; do not work around it —\n"
        f"     surface it. Prefer hou.ui / hou.qt feature-detection over guessing an API exists.\n"
        f"  5. Make `{gate_cmd}` pass. Then write a one-paragraph summary of what you did and the\n"
        f"     next step, and stop. The harness re-checks the checklist and runs you again if needed."
    )


def parse_result(stdout):
    """Defensive parse of `claude -p --output-format json`. Never assume a field exists."""
    try:
        data = json.loads(stdout)
    except Exception:
        return 0.0, 0, "parse_error", ""
    return (float(data.get("total_cost_usd", 0.0) or 0.0),
            int(data.get("num_turns", 0) or 0),
            str(data.get("subtype", "") or ""),
            str(data.get("result", "") or "")[:1000])


def _spawn(cfg, model, prompt, permission_mode, max_turns):
    """One headless `claude -p` call. Returns (cost, turns, subtype, text). Raises on timeout."""
    proc = subprocess.run(
        [cfg["claude_bin"], "-p", prompt, "--model", model,
         "--max-turns", str(max_turns),
         "--permission-mode", permission_mode,
         "--allowedTools", cfg["allowed_tools"], "--add-dir", ROOT,
         "--output-format", "json"],
        cwd=ROOT, capture_output=True, text=True,
        timeout=cfg.get("stuck_timeout_sec", 1800))
    return parse_result(proc.stdout)


def _spawn_opusplan(cfg, exec_prompt, max_turns):
    """opusplan, realized as ARCHITECT -> FORGE (your role split):
       phase A: Opus, plan-only (--permission-mode plan, no edits) drafts the approach;
       phase B: Sonnet executes, with that plan injected.
    Both phases' cost accumulates. If your Claude Code build honors `--model opusplan`
    in -p, you can collapse this to a single _spawn(model='opusplan')."""
    models = cfg.get("models", {}) or {}
    plan_prompt = (
        "PLAN ONLY — do NOT edit any file. You are the ARCHITECT. Using the orientation already "
        "in context and the goal below, produce a short concrete plan for the SINGLE "
        "highest-priority not-passing feature: which files, what change, what could regress, and "
        "the exact verify the harness will run. Respect the phantom-API rule (no unverified "
        "hou.*/pdg.*).\n\n" + exec_prompt
    )
    pc, pt, _, plan_text = _spawn(cfg, models.get("planner", "opus"),
                                  plan_prompt, "plan", max(8, max_turns // 2))
    forge_prompt = (
        "EXECUTE — you are FORGE. Implement EXACTLY the plan below, nothing more. Edit only the "
        "allowed paths; do not weaken tests; obey the phantom-API fence.\n\n"
        f"--- ARCHITECT PLAN ---\n{plan_text}\n--- END PLAN ---\n\n" + exec_prompt
    )
    ec, et, est, etext = _spawn(cfg, models.get("worker", "sonnet"),
                                forge_prompt, cfg["permission_mode"], max_turns)
    return pc + ec, pt + et, est, etext


def _load_scout_report(cfg, require=False):
    """Load .synapse/scout_report.json; warn (or refuse) if missing; warn if stale."""
    path = os.path.join(SYN, "scout_report.json")
    if not os.path.exists(path):
        msg = "no scout_report.json — run `scout` first (or `run --scout`)."
        if require:
            sys.exit("SYNAPSE harness refuses: " + msg)
        print("  (warning: " + msg + " — running without scout gating.)\n")
        return None
    try:
        rep = json.load(open(path, encoding="utf-8"))
    except Exception:
        return None
    try:
        gen = datetime.fromisoformat(rep.get("generated"))
        age_min = (datetime.now(gen.tzinfo) - gen).total_seconds() / 60
        if age_min > float(cfg.get("scout_max_age_min", 120)):
            print(f"  (warning: scout_report is {age_min:.0f} min old "
                  f"> {cfg.get('scout_max_age_min')} — consider re-scouting.)\n")
    except Exception:
        pass
    return rep


def run_gate(cmd, quiet=False):
    if not cmd:
        return True
    proc = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True)
    if not quiet:
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
    return proc.returncode == 0


def run_contract(contract, cfg, fence, budget, dry_run=False, smoke=False):
    cid = contract["id"]
    branch = cfg["branch_prefix"] + cid

    bad = contract_violates_ip(contract, fence)
    if bad:
        print(f"  x {cid}: IP-FENCE refuses to start — ownership reaches protected path(s): {bad[:3]}")
        append_ledger({"id": cid, "ts": now(), "result": "refused-ip", "cost_usd": 0.0})
        return "refused-ip"

    mem = memmod.get_memory(cfg["memory_backend"], task_dir(cid, cfg), contract)
    mem.ensure()
    if not dry_run:
        git("checkout", "-B", branch)

    effective_owns = list(contract.get("owns", [])) + mem.owns_extra()
    model = contract.get("model") or (cfg.get("models") or {}).get("worker", "sonnet")
    max_turns = int(cfg.get("max_turns", 25))
    max_sessions = int(cfg.get("max_sessions", 6))
    prompt = build_prompt(contract, cfg["gate_cmd"])

    result, last_pass, task_cost = "incomplete", -1, 0.0
    for s in range(1, max_sessions + 1):
        if budget["cap"] and budget["spent"] >= budget["cap"]:
            print(f"  $ budget reached (${budget['spent']:.2f} >= ${budget['cap']:.2f}) — stopping before {cid} s{s}.")
            result = "budget-stopped"
            break

        write_state({
            "contract": {
                "id": cid, "goal": contract.get("goal", ""),
                "owns": effective_owns, "do_not_touch": contract.get("do_not_touch", []),
                "allow_test_edits": contract.get("allow_test_edits", False),
                "autonomy": contract.get("autonomy", "amber"),
            },
            "orient": mem.orientation(),
            "branch": branch, "session": s, "model": model,
            "gate_attempts": 0, "gate_result": None,
        })

        cost = turns = 0.0
        subtype, worker_text = "dry", ""
        if dry_run:
            how = "opusplan (ARCHITECT->FORGE)" if model == "opusplan" else model
            print(f"  . {cid} s{s}: would run {how} (--max-turns {max_turns}) on -> {mem.next_failing()!r}")
        else:
            how = "opusplan (Opus plan -> Sonnet exec)" if model == "opusplan" else model
            print(f"  . {cid} s{s}/{max_sessions}: {how} (--max-turns {max_turns}) ...")
            try:
                if model == "opusplan":
                    cost, turns, subtype, worker_text = _spawn_opusplan(cfg, prompt, max_turns)
                else:
                    cost, turns, subtype, worker_text = _spawn(
                        cfg, model, prompt, cfg["permission_mode"], max_turns)
                budget["spent"] += cost
                task_cost += cost
            except subprocess.TimeoutExpired:
                print(f"  x {cid}: s{s} timed out — circuit breaker, escalating.")
                append_ledger({"id": cid, "ts": now(), "result": "timeout", "cost_usd": 0.0})
                return "timeout"

        gate_ok = run_gate(cfg["gate_cmd"], quiet=True)
        npass, ntotal = mem.evaluate()
        mem.note_session(s, worker_text or "(dry-run)", {
            "npass": npass, "ntotal": ntotal, "cost_usd": cost, "turns": turns, "ts": now()})
        state = json.load(open(os.path.join(SYN, "state.json")))
        if not dry_run:
            git("add", "-A")
            git("commit", "-m", f"synapse({cid}) s{s}: {npass}/{ntotal} feat, gate {'green' if gate_ok else 'red'}, ${cost:.2f}")
        print(f"    gate={'PASS' if gate_ok else 'FAIL'}  features={npass}/{ntotal}  "
              f"cost=${cost:.2f}  run-total=${budget['spent']:.2f}"
              + (f"  [{subtype}]" if subtype not in ('', 'dry', 'success') else ""))

        if ntotal > 0 and npass == ntotal and gate_ok:
            result = "green"
            break
        if state.get("gate_result") == "failed":
            result = "failed"
            break
        if dry_run:
            result = "green(dry)" if (ntotal and npass == ntotal) else "incomplete(dry)"
            break
        if npass <= last_pass:
            print("    no new features passed — stalling, escalating.")
            result = "stalled"
            break
        last_pass = npass

    if smoke and cfg.get("smoke_cmd") and not dry_run and result == "green":
        ok = run_gate(cfg["smoke_cmd"], quiet=False)
        print(f"    end-to-end smoke: {'PASS' if ok else 'FAIL'}")
        if not ok:
            result = "smoke-failed"

    if not dry_run and result == "green":
        print(f"  ok {cid}: GREEN on {branch}. Review & merge when ready.")
    elif not dry_run:
        print(f"  x {cid}: {result} — left on {branch}.")
    append_ledger({"id": cid, "ts": now(), "result": result, "branch": branch,
                   "cost_usd": round(task_cost, 4)})
    return result


# ---------------- commands ----------------
def _billing_guard(cfg, dry_run):
    """The footgun: a stray ANTHROPIC_API_KEY overrides the subscription and bills API
    from the first token. Refuse rather than surprise the user with a bill.
    (SYNAPSE keeps its key under SYNAPSE_ANTHROPIC_KEY precisely to avoid this.)"""
    if dry_run:
        return
    mode = cfg.get("billing_mode", "subscription")
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if mode == "subscription" and has_key:
        sys.exit(
            "SYNAPSE harness refuses to run: ANTHROPIC_API_KEY is set, which OVERRIDES your "
            "subscription and bills pay-as-you-go API from the first token. Unset it (keep your "
            "key under SYNAPSE_ANTHROPIC_KEY) to use your Max plan / Agent SDK credit, or set "
            "billing_mode: api in config.yaml if you intend metered API billing.")
    if mode == "api" and not has_key:
        sys.exit("SYNAPSE harness: billing_mode is 'api' but ANTHROPIC_API_KEY is not set.")


def cmd_run(args):
    cfg, fence = load_config(), load_fence()
    _billing_guard(cfg, args.dry_run)
    cap = args.budget if args.budget is not None else float(cfg.get("budget_usd", 0) or 0)
    budget = {"spent": 0.0, "cap": cap}
    ceiling = TIERS[args.autonomy]
    items = queue_items()
    if not items:
        print("queue empty — nothing to run.")
        return

    # --- SCOUT: the leadoff leg. Ground the plan against the real repo first. ---
    if getattr(args, "scout", False):
        import scout as scoutmod
        print("Scout: grounding the plan against the repo before any build...\n")
        scoutmod.print_summary(scoutmod.run_scout([it["id"] for it in items], write=True))
        print("")
    scout_rep = _load_scout_report(cfg, require=getattr(args, "require_scout", False))
    scout_status = (scout_rep or {}).get("contracts", {})

    print(f"SYNAPSE run . ceiling={args.autonomy.upper()} . {'DRY-RUN' if args.dry_run else cfg['billing_mode'].upper()} . "
          f"memory={cfg['memory_backend']} . budget=${cap:.2f} . sessions/task<={cfg.get('max_sessions')}\n")
    ran, held = [], []
    for it in items:
        if budget["cap"] and budget["spent"] >= budget["cap"]:
            held.append((it["id"], f"budget ${cap:.2f} reached"))
            continue
        c = load_contract(it["id"])
        if c.get("autonomy") == "red":
            held.append((it["id"], "RED — needs human + live Houdini / counsel; never autonomous"))
            continue
        if TIERS.get(c.get("autonomy", "amber"), 1) > ceiling:
            held.append((it["id"], f"{c.get('autonomy').upper()} > ceiling; raise --autonomy"))
            continue
        st = scout_status.get(it["id"], {}).get("status", "")
        if st.startswith("needs-attention") and not getattr(args, "skip_scout_gate", False):
            held.append((it["id"], f"SCOUT: {st} — fix, re-scout, or --skip-scout-gate"))
            continue
        run_contract(c, cfg, fence, budget, dry_run=args.dry_run, smoke=args.smoke)
        ran.append(it["id"])

    if held:
        print("\nHeld (not run):")
        for cid, why in held:
            print(f"  . {cid}: {why}")
    print(f"\nDone. ran={len(ran)} held={len(held)} . spent=${budget['spent']:.2f}. "
          f"Branches unmerged by design — commit/push is your gate.")


def cmd_scout(args):
    """The leadoff leg — read-only recon that grounds the plan against the real repo."""
    import scout as scoutmod
    cfg = load_config()
    ids = args.ids or [it["id"] for it in queue_items()]
    if not ids:
        print("scout: no contracts given and queue empty. Pass ids or `queue add` some first.")
        return
    print(f"SCOUT . grounding {len(ids)} contract(s) against {ROOT}\n")
    report = scoutmod.run_scout(ids, write=True)
    scoutmod.print_summary(report)
    print(f"\nwrote {os.path.join('.synapse', 'scout_report.json')}")
    if args.synthesize:
        _scout_synthesize(cfg, report)


def _scout_synthesize(cfg, report):
    """Optional Opus pass: read the recon + the review docs, recommend contract edits.
    This is where dynamic planning starts — it does NOT edit anything (plan mode)."""
    planner = (cfg.get("models") or {}).get("planner", "opus")
    docs = "\n".join(f"- {d}" for d in (cfg.get("review_docs") or [])) or "(none configured)"
    prompt = (
        "You are the SYNAPSE scout's synthesis pass. Below is a JSON recon report of the ACTUAL "
        "repo plus the review docs that define the work. Recommend concrete contract "
        "adjustments: fix unconfirmed `owns` paths, list which goalpost tests must be written "
        "first, flag any contract that should change tier. Output a short markdown punch list. "
        "Do NOT edit files.\n\n"
        f"REVIEW DOCS:\n{docs}\n\nSCOUT REPORT:\n{json.dumps(report, indent=2)[:6000]}"
    )
    print("\n--- scout synthesis (Opus, plan-only) ---")
    subprocess.run([cfg["claude_bin"], "-p", prompt, "--model", planner,
                    "--permission-mode", "plan"], cwd=ROOT)


def cmd_init(args):
    cfg = load_config()
    for cid in args.ids:
        c = load_contract(cid)
        mem = memmod.get_memory(cfg["memory_backend"], task_dir(cid, cfg), c)
        mem.ensure()
        print(f"init {cid}: {cfg['memory_backend']} memory ready in {cfg['work_dir']}/{cid}/")


def cmd_features(args):
    cfg = load_config()
    c = load_contract(args.id)
    mem = memmod.get_memory(cfg["memory_backend"], task_dir(args.id, cfg), c)
    mem.ensure()
    npass, ntotal = mem.evaluate()
    print(f"{args.id}: {npass}/{ntotal} features passing  (memory={cfg['memory_backend']})\n")
    print(mem.orientation())


def cmd_status(args):
    path = os.path.join(SYN, "ledger.jsonl")
    if not os.path.exists(path):
        print("no ledger yet.")
        return
    rows = [json.loads(l) for l in open(path) if l.strip()]
    by, spend = {}, 0.0
    for r in rows:
        by[r["result"]] = by.get(r["result"], 0) + 1
        spend += float(r.get("cost_usd") or 0.0)
    print("SYNAPSE harness ledger:")
    for k, v in sorted(by.items()):
        print(f"  {k:14} {v}")
    print(f"\ntotal metered spend recorded: ${spend:.2f}")
    print("last 8:")
    for r in rows[-8:]:
        print(f"  {r['ts']}  {r['result']:14} {r['id']}")


def cmd_gate(args):
    cfg = load_config()
    ok = run_gate(cfg["gate_cmd"])
    if args.smoke and cfg.get("smoke_cmd"):
        ok = run_gate(cfg["smoke_cmd"]) and ok
    print(f"\ngate: {'GREEN' if ok else 'RED'}")
    sys.exit(0 if ok else 1)


def cmd_plan(args):
    cfg = load_config()
    planner = (cfg.get("models") or {}).get("planner", "opus")
    goal = " ".join(args.goal)
    scout_ctx = ""
    rep_path = os.path.join(SYN, "scout_report.json")
    if os.path.exists(rep_path):
        try:
            scout_ctx = ("\n\nGROUND TRUTH from the scout (use REAL paths that resolve; do not "
                         "invent paths):\n" + json.dumps(json.load(open(rep_path)), indent=2)[:4000])
        except Exception:
            scout_ctx = ""
    prompt = (
        "You are the SYNAPSE harness initializer. Output ONLY a YAML task contract with keys: id, "
        "goal, model (haiku for mechanical work, sonnet default, opusplan for judgment-heavy work "
        "[Opus plans, Sonnet executes], opus only for the hardest reasoning), autonomy "
        "(green|amber|red), owns (minimal glob list), do_not_touch (MUST include "
        "python/synapse/panel/claude_worker.py and python/synapse/cognitive/** — the floor), "
        "stop_when, and features (list of {description, verify, passing:false} where verify is a "
        "shell command — ideally a pytest selector or .synapse/verify.py check — returning 0 only "
        "when the feature truly works). Be conservative: minimal ownership; NEVER include "
        "substrate-internal paths (cognitive/**, *memory_ladder*, *injection*, *gain*); anything "
        "touching the freeze/safety chain or needing a live engine is autonomy: red.\n\n"
        f"GOAL: {goal}{scout_ctx}"
    )
    if args.dry_run:
        print(f"# (dry-run) Opus would draft a contract + checklist for: {goal}"
              + ("  [scout-grounded]" if scout_ctx else ""))
        return
    subprocess.run([cfg["claude_bin"], "-p", prompt, "--model", planner, "--permission-mode", "plan"], cwd=ROOT)


def main():
    ap = argparse.ArgumentParser(prog="synapse-harness", description="Long-running build harness (ANVIL-pattern)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("queue"); q.add_argument("action", choices=["add", "list", "clear"])
    q.add_argument("ids", nargs="*"); q.set_defaults(func=cmd_queue)

    i = sub.add_parser("init"); i.add_argument("ids", nargs="+"); i.set_defaults(func=cmd_init)

    sc = sub.add_parser("scout")
    sc.add_argument("ids", nargs="*", help="contracts to recon (default: the queue)")
    sc.add_argument("--synthesize", action="store_true",
                    help="Opus reads the recon + review_docs and recommends contract edits (plan-only)")
    sc.set_defaults(func=cmd_scout)

    f = sub.add_parser("features"); f.add_argument("id"); f.set_defaults(func=cmd_features)

    r = sub.add_parser("run")
    r.add_argument("--autonomy", choices=["green", "amber", "red"], default="green")
    r.add_argument("--budget", type=float, default=None, help="hard $ stop for this run (overrides config)")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--smoke", action="store_true", help="also run the end-to-end (live Houdini) smoke gate")
    r.add_argument("--scout", action="store_true", help="run the scout recon first (scout -> run)")
    r.add_argument("--require-scout", action="store_true", help="refuse to run without a scout_report.json")
    r.add_argument("--skip-scout-gate", action="store_true",
                   help="run even contracts the scout flagged needs-attention")
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("status"); s.set_defaults(func=cmd_status)
    g = sub.add_parser("gate"); g.add_argument("--smoke", action="store_true"); g.set_defaults(func=cmd_gate)
    p = sub.add_parser("plan"); p.add_argument("goal", nargs="+")
    p.add_argument("--dry-run", action="store_true"); p.set_defaults(func=cmd_plan)

    args = ap.parse_args()
    if args.cmd == "run" and args.autonomy == "red":
        sys.exit("SYNAPSE harness: refusing — RED tasks are never run autonomously. "
                 "They need a human, a live Houdini session, or counsel.")
    args.func(args)


if __name__ == "__main__":
    main()
