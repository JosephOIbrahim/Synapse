#!/usr/bin/env python3
"""
checks.py — deterministic verification for the SYNAPSE → H22 harness.

This is the domain-correct stand-in for the web harness's Playwright: instead of clicking a
DOM it cooks networks in hython, runs your existing synapse_doctor, parses the agent.usd
ledger, and renders a frame with husk. It returns FACTS as JSON; judgment is the Evaluator's.

It reuses what you already built. The ~handful of `# ADAPT` lines are the only places you
wire this to your real repo — they're marked, not hidden. Nothing here pretends to pass.

Usage (called by run.ts):
    python harness/verify/checks.py --task 0.4 --worktree <path> --hython <path> --mode A
"""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path

def sh(cmd, cwd=None, timeout=900):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                            shell=(os.name == "nt"))
        return p.returncode, p.stdout or "", p.stderr or ""
    except Exception as e:
        return 1, "", f"{type(e).__name__}: {e}"

def hython(hython_bin, script, cwd):
    """Run a python snippet inside Houdini's interpreter."""
    if not hython_bin:
        return 1, "", "HYTHON unset"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(script); path = f.name
    try:
        return sh([hython_bin, path], cwd=cwd)
    finally:
        os.unlink(path)

# ---------- individual checks: each returns {"ok": bool, "detail": str} ----------

_BOOT = ("import os, sys\n"
         "root = os.getcwd()\n"  # cwd == worktree (hython() runs with cwd=wt) — no hardcoded path
         "sys.path.insert(0, os.path.join(root, 'python'))\n"  # the synapse package lives here
         "sys.path.insert(0, root)\n")  # repo root too — handler surface imports `from shared`

def check_import_panel(ctx):
    # WIRED (Step 2): real module is `synapse` under <repo>/python; panel is synapse.panel.
    code = _BOOT + "import synapse\nprint('import-ok', synapse.__version__)"
    rc, out, err = hython(ctx["hython"], code, ctx["wt"])
    return {"ok": rc == 0 and "import-ok" in out, "detail": (err or out).strip()[:500]}

def check_brain_answers(ctx):
    # WIRED (Step 2): in-proc bridge liveness — the memory brain must wake up. Transport-
    # agnostic for the in-proc path; works headless. (sidecar-vs-abi3 is human gate 0.1;
    # either choice keeps this property valid — synapse has no module-level ping().)
    code = _BOOT + ("import synapse\n"
                    "try:\n"
                    "    b = synapse.get_bridge()\n"
                    "    print('brain-ok' if getattr(b, '_synapse', None) is not None else 'brain-no')\n"
                    "except Exception as e:\n"
                    "    print('brain-err', e)")
    rc, out, err = hython(ctx["hython"], code, ctx["wt"])
    return {"ok": "brain-ok" in out, "detail": (out or err).strip()[:500]}

def check_doctor(ctx):
    # WIRED (Step 2): real doctor is synapse.server.doctor.run_doctor (no standalone CLI).
    # Green = zero failing checks (skipped != fail). Headless, the 'houdini' check is skipped.
    if not ctx["hython"]:
        return {"ok": False, "detail": "HYTHON unset"}
    code = _BOOT + ("import json\n"
                    "from synapse.server.doctor import run_doctor\n"
                    "res = run_doctor({}, handler=None)\n"
                    "res['status'] = 'green' if res.get('summary', {}).get('fail', 1) == 0 else 'red'\n"
                    "print(json.dumps(res))")
    rc, out, err = hython(ctx["hython"], code, ctx["wt"])
    try:
        # tolerate Houdini's launch banner — the doctor JSON is the last {...} line
        jline = [l for l in out.splitlines() if l.strip().startswith("{")]
        data = json.loads(jline[-1]) if jline else {}
        return {"ok": data.get("status") == "green",
                "detail": json.dumps(data.get("summary", {}))[:600] or (err or out).strip()[:300]}
    except Exception:
        return {"ok": False, "detail": (err or out).strip()[:500] or "doctor produced no JSON"}

def check_probe_runs(ctx):
    # WIRED (Step 3): real probe entrypoint is scripts/run_apex_verify.py (APEX surface
    # verification). On H21 it runs clean (rc 0); the --diff/delta layer is NOT implemented,
    # so probe_clean stays ADAPT / Mode-B. This proves the probe HARNESS runs.
    if not ctx["hython"]:
        return {"ok": False, "detail": "HYTHON unset"}
    rc, out, err = sh([ctx["hython"], "scripts/run_apex_verify.py", ".claude/apex_registry.jsonl"],
                      cwd=ctx["wt"])
    return {"ok": rc == 0, "detail": (out or err).strip()[-500:]}

def check_probe_clean(ctx):
    p = Path(ctx["wt"]) / ".claude/probe_delta.json"
    if not p.exists():
        return {"ok": False, "detail": "no probe_delta.json — run probe_runs first"}
    try:
        delta = json.loads(p.read_text())
        n = len(delta.get("unpatched", delta if isinstance(delta, list) else []))
        return {"ok": n == 0, "detail": f"{n} unpatched drift item(s)"}
    except Exception as e:
        return {"ok": False, "detail": str(e)[:300]}

def check_version_single_source(ctx):
    wt = Path(ctx["wt"])
    def read(p):
        f = wt / p
        return f.read_text().strip() if f.exists() else None
    version = read("VERSION")
    pyproj = read("pyproject.toml") or ""
    # ADAPT: tighten these greps to your file shapes.
    import re
    pv = re.search(r'version\s*=\s*"([^"]+)"', pyproj)
    pv = pv.group(1) if pv else None
    ok = version is not None and pv is not None and version == pv
    return {"ok": ok, "detail": f"VERSION={version} pyproject={pv}"}

def check_cook(ctx, node=None):
    """Build/refresh a target node and cook it; fail on any cook error."""
    target = node or "ADAPT_existing_tool_node"  # ADAPT: a known node path for cook_existing
    code = (f"import hou\n"
            f"node = hou.node('{target}')\n"
            f"assert node, 'node not found: {target}'\n"
            f"node.cook(force=True)\n"
            f"errs = node.errors()\n"
            f"print('COOK-ERR' if errs else 'COOK-OK', errs)")
    rc, out, err = hython(ctx["hython"], code, ctx["wt"])
    return {"ok": rc == 0 and "COOK-OK" in out, "detail": (out or err).strip()[:600]}

def check_hip_opens(ctx):
    # ADAPT: path to the staged demo hip.
    hip = "demo/synapse_demo.hip"
    code = (f"import hou\nhou.hipFile.load('{hip}', suppress_save_prompt=True, "
            f"ignore_load_warnings=False)\nprint('HIP-OK')")
    rc, out, err = hython(ctx["hython"], code, ctx["wt"])
    return {"ok": rc == 0 and "HIP-OK" in out, "detail": (out or err).strip()[:500]}

def check_shot_login(ctx):
    # WIRED (Step 3): real module is synapse.panel.shot_login; entry is shot_login() (no resolve()).
    # Still honestly gated on OCIO being set + the demo hip being staged (0.5) — false until both.
    ocio = bool(os.environ.get("OCIO"))
    code = _BOOT + ("from synapse.panel import shot_login as s\n"
                    "print('SHOT-OK' if s.shot_login() else 'SHOT-NO')")
    rc, out, err = hython(ctx["hython"], code, ctx["wt"])
    return {"ok": "SHOT-OK" in out and ocio, "detail": f"OCIO={'set' if ocio else 'UNSET'}; {(out or err).strip()[:400]}"}

def check_runsheet_present(ctx):
    f = Path(ctx["wt"]) / "DEMO_SCRIPT.md"
    if not f.exists():
        return {"ok": False, "detail": "DEMO_SCRIPT.md missing"}
    beats = f.read_text().count("##")  # ADAPT: match your beat marker
    return {"ok": beats >= 6, "detail": f"{beats} beat headings (expect ≥6)"}

def check_clean_install(ctx):
    # The 'your tool vs a studio's tool' check: the SHIPPED product surface must not bake in a
    # per-user path. Scan ONLY what reaches a clean machine (houdini/, packages/, the synapse
    # package) — NOT the harness, tests, dev scripts, docs, or vendored third-party code (and so
    # not this file's own search literal). Reports the offending files. ADAPT: also assert
    # install.py registers into a TEMP HOUDINI_USER_PREF_DIR for a true clean-env test.
    wt = Path(ctx["wt"])
    needles = ("c:\\users\\user\\synapse", "c:/users/user/synapse")
    product_roots = ("houdini", "packages", "python/synapse")
    skip_parts = ("_vendor", "__pycache__", ".git")
    offenders = []
    for rel in product_roots:
        base = wt / rel
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in (".py", ".json", ".pypanel"):
                continue
            if any(s in p.parts for s in skip_parts):
                continue
            try:
                text = p.read_text(errors="ignore").lower()
            except Exception:
                continue
            if any(n in text for n in needles):
                offenders.append(str(p.relative_to(wt)).replace("\\", "/"))
    return {"ok": not offenders,
            "detail": (f"hardcoded user-path in: {', '.join(offenders[:8])}" if offenders
                       else "no hardcoded user-path in the shipped product surface "
                            "(ADAPT: also assert install.py into a temp pref dir)")}

def check_nodes_appear(ctx):
    # ADAPT: after install, confirm the panel's tools/nodes register — kills the 'processes but no nodes' class.
    code = ("import hou\n"
            "ok = hou.nodeType(hou.sopNodeTypeCategory(), 'synapse::ADAPT')  # ADAPT a real registered type\n"
            "print('NODES-OK' if ok else 'NODES-NO')")
    rc, out, err = hython(ctx["hython"], code, ctx["wt"])
    return {"ok": "NODES-OK" in out, "detail": (out or err).strip()[:400]}

def check_ledger(ctx):
    # Parse agent.usd for this sprint's entry: decision + reasoning + revert.
    # ADAPT: the ledger path + prim/attr schema. Requires pxr (USD python).
    code = ("from pxr import Usd\n"
            "stage = Usd.Stage.Open('agent.usd')  # ADAPT path\n"
            "entries = [p for p in stage.Traverse() if p.GetTypeName() == 'SynapseAction']  # ADAPT type\n"
            "good = [p for p in entries if p.GetAttribute('decision') and "
            "p.GetAttribute('reasoning') and p.GetAttribute('revertPath')]  # ADAPT attr names\n"
            "print('LEDGER-OK' if good else 'LEDGER-NO', len(entries), 'entries')")
    rc, out, err = hython(ctx["hython"], code, ctx["wt"])
    return {"ok": "LEDGER-OK" in out, "detail": (out or err).strip()[:500]}

def check_revert_clean(ctx):
    # ADAPT: invoke your revert on the last action, then diff the stage hash before/after.
    return {"ok": False, "detail": "ADAPT: wire revert + stage-hash diff. Until wired, treated as not-verified."}

def check_render(ctx):
    # Karma XPU via husk → assert the frame exists and isn't all-black.
    # ADAPT: the USD to render + husk path. husk ships in Houdini's bin alongside hython.
    husk = str(Path(ctx["hython"]).with_name("husk")) if ctx["hython"] else ""
    usd, out_img = "demo/render.usd", ".claude/render_check.exr"  # ADAPT
    if not husk:
        return {"ok": False, "detail": "HYTHON unset → can't locate husk"}
    rc, o, e = sh([husk, "--renderer", "BRAY_HdKarmaXPU", "-f", "1", "-o", out_img, usd],
                  cwd=ctx["wt"], timeout=1800)
    img = Path(ctx["wt"]) / out_img
    if rc != 0 or not img.exists():
        return {"ok": False, "detail": (e or o).strip()[:500] or "render produced no file"}
    # non-black check
    code = (f"import hou\nimport numpy as np\n"
            f"# ADAPT: load {out_img} and check variance > 0; or use OIIO if available\n"
            f"print('IMG-NONBLACK')  # ADAPT real pixel check")
    return {"ok": img.stat().st_size > 1024, "detail": f"frame written ({img.stat().st_size} bytes); ADAPT real non-black check"}

def check_theme_ok(ctx):
    # Honest: theme correctness is screenshot + human review. Surface, don't fake-pass.
    return {"ok": False, "detail": "ADAPT/HUMAN: capture panel screenshot in host theme; flagged for visual review, not auto-passed"}


def check_mcp_registered(ctx):
    # D-H22-1: the APEX MCP is registered as a first-class provider and a round-trip tool call
    # returns a truth-contract-shaped envelope (it carries what was OBSERVED). On H21 this
    # exercises the provider against the mock. ADAPT: provider registry accessor + a benign tool.
    code = ("import synapse\n"
            "try:\n"
            "    prov = synapse.providers.get('apex_mcp')  # ADAPT registry accessor\n"
            "    env = prov.call_tool('ping', {})           # ADAPT a benign tool name\n"
            "    ok = bool(prov) and isinstance(env, dict) and env.get('observed') is not None\n"
            "    print('MCP-OK' if ok else 'MCP-NO')\n"
            "except Exception as e:\n"
            "    print('MCP-ERR', e)")
    rc, out, err = hython(ctx["hython"], code, ctx["wt"])
    return {"ok": "MCP-OK" in out, "detail": (out or err).strip()[:500]}

def check_mcp_surface_probe(ctx):
    # D-H22-4: introspect the native APEX MCP's ACTUAL tool list on the installed build, diff
    # vs the recorded surface, and quarantine absent/renamed endpoints. Same discipline as
    # apex_probes, aimed at the MCP's tool surface instead of hou.*. On H21 it points at the
    # mock (science/mcp_mock.py); the diff should be ~empty — that empty diff proves the probe
    # works before the drop makes it real.
    # ADAPT: how mcp_surface_probe.py enumerates the MCP's tools + where it writes the delta.
    runner = ctx["hython"] or sys.executable
    rc, out, err = sh([runner, "science/mcp_surface_probe.py", "--diff", "--out",
                       ".claude/mcp_surface_delta.json"], cwd=ctx["wt"])
    p = Path(ctx["wt"]) / ".claude/mcp_surface_delta.json"
    if rc != 0 or not p.exists():
        return {"ok": False, "detail": (out or err).strip()[:400] or "mcp_surface_probe.py not wired — ADAPT science/mcp_surface_probe.py"}
    try:
        d = json.loads(p.read_text())
        absent, renamed = d.get("absent", []), d.get("renamed", [])
        ok = not absent and not renamed
        return {"ok": ok, "detail": f"absent={len(absent)} renamed={len(renamed)} (both must be 0 before wiring)"}
    except Exception as e:
        return {"ok": False, "detail": str(e)[:300]}

def check_mcp_truth_contract(ctx):
    # The handler cannot claim an outcome it didn't observe, and the MCP's own validator verdict
    # is recorded as a provenance INPUT — never restated as a Synapse claim. ADAPT: envelope fields.
    code = ("import synapse\n"
            "try:\n"
            "    env = synapse.providers.get('apex_mcp').call_tool('validate', {'src': 'noop'})  # ADAPT\n"
            "    observed = 'observed' in env\n"
            "    no_overclaim = ('claimed' not in env) or (env.get('claimed') == env.get('observed'))\n"
            "    verdict_is_input = 'validator_verdict' in env  # the MCP's verdict, carried not asserted\n"
            "    ok = observed and no_overclaim and verdict_is_input\n"
            "    print('TC-OK' if ok else 'TC-NO', {'observed': observed, 'verdict_input': verdict_is_input})\n"
            "except Exception as e:\n"
            "    print('TC-ERR', e)")
    rc, out, err = hython(ctx["hython"], code, ctx["wt"])
    return {"ok": "TC-OK" in out, "detail": (out or err).strip()[:500]}

def check_no_rigging_drift(ctx):
    # D-H22-3 non-goal: Synapse's authoring center of gravity stays off rigging/APEX — that is
    # the native MCP's floor. The clean signal is a declared authoring-domain allowlist.
    # ADAPT: server/authoring_domains.json = {"domains": ["cop","lop","sop","karma","usd"]}.
    wt = Path(ctx["wt"])
    allow = wt / "server" / "authoring_domains.json"  # ADAPT path
    in_scope = {"cop", "cops", "lop", "lops", "sop", "sops", "karma", "usd", "solaris", "mat", "obj"}
    drift_terms = {"apex", "rig", "rigging", "kinefx", "muscle", "cfx"}
    if allow.exists():
        try:
            decl = {d.lower() for d in json.loads(allow.read_text()).get("domains", [])}
            drift = decl & drift_terms
            if drift:
                return {"ok": False, "detail": f"authoring domains include rigging surface: {sorted(drift)}"}
            stray = decl - in_scope
            note = f" (note: undeclared-scope entries {sorted(stray)})" if stray else ""
            return {"ok": True, "detail": f"authoring domains in-scope: {sorted(decl)}{note}"}
        except Exception as e:
            return {"ok": False, "detail": f"authoring_domains.json unreadable: {str(e)[:200]}"}
    return {"ok": None, "detail": "authoring-domain allowlist not declared yet (ADAPT server/authoring_domains.json)"}

def check_provenance_not_bypassed(ctx):
    # Non-goal: not a commodity hou.* passthrough. Every scene/stage mutation routes through the
    # provenance gateway and lands in agent.usd. The rigorous form is a RUNTIME sentinel (perform
    # a sandboxed mutation, assert the ledger grew by one). Until that's wired this WARNS — it
    # neither fake-passes nor blocks every sprint.
    # ADAPT: name the provenance gateway + either a mutation-capable-module manifest (static) or
    # the sandbox sentinel (runtime, Mode B).
    return {"ok": None, "detail": "ADAPT: wire the provenance-gateway manifest or the runtime ledger-grew sentinel. Warn-only until then."}

def check_scout_federates(ctx):
    # D-H22-2: scout returns APEX results tagged as sourced from the federated MCP provider,
    # and exists_in_runtime remains present + authoritative on every hit. ADAPT: scout query API.
    code = ("import synapse\n"
            "try:\n"
            "    hits = synapse.scout.query('apex rig pose', domains=['apex'])  # ADAPT query API\n"
            "    src_ok = bool(hits) and all(h.get('source') == 'apex_mcp' for h in hits)\n"
            "    rt_ok = all('exists_in_runtime' in h for h in hits)\n"
            "    print('SCOUT-OK' if (src_ok and rt_ok) else 'SCOUT-NO')\n"
            "except Exception as e:\n"
            "    print('SCOUT-ERR', e)")
    rc, out, err = hython(ctx["hython"], code, ctx["wt"])
    return {"ok": "SCOUT-OK" in out, "detail": (out or err).strip()[:500]}

def check_scout_no_apex_corpus(ctx):
    # D-H22-2 non-goal: APEX syntax knowledge must come ONLY from the federated MCP, never a
    # local corpus that competes with the first-party source. ADAPT: scout corpus root + registry.
    wt = Path(ctx["wt"])
    forbidden = []
    for pat in ("**/scout/**/apex*", "**/rag/**/apex*corpus*", "**/corpus/**/apex*"):
        forbidden += [p for p in wt.glob(pat) if ".git" not in str(p) and "worktrees" not in str(p)]
    if forbidden:
        rel = ", ".join(str(p.relative_to(wt)) for p in forbidden[:5])
        return {"ok": False, "detail": f"local APEX corpus present (must federate, not rebuild): {rel}"}
    reg = wt / "server" / "scout_sources.json"  # ADAPT path
    if reg.exists():
        try:
            data = json.loads(reg.read_text())
            apex = data.get("apex") or data.get("APEX")
            if apex and apex.get("kind") != "provider":
                return {"ok": False, "detail": f"scout APEX source kind='{apex.get('kind')}' — must be federated 'provider'"}
            return {"ok": True, "detail": "no local APEX corpus; scout APEX source is federated"}
        except Exception as e:
            return {"ok": False, "detail": f"scout_sources.json unreadable: {str(e)[:200]}"}
    return {"ok": None, "detail": "no APEX corpus found; scout source-registry not wired yet (ADAPT server/scout_sources.json)"}

def run_one(name, task, ctx):
    fn = DISPATCH.get(name)
    if not fn:
        return {"ok": False, "detail": "no check implemented — ADAPT"}
    if name == "cook_node":
        return check_cook(ctx, node=(task.get("target_node", "") or "").replace("ADAPT: ", "") or None)
    return fn(ctx)


DISPATCH = {
    "import_panel": check_import_panel, "brain_answers": check_brain_answers,
    "doctor": check_doctor, "probe_runs": check_probe_runs, "probe_clean": check_probe_clean,
    "version_single_source": check_version_single_source, "cook_existing": check_cook,
    "cook_node": check_cook,  # FIX: was missing → cook_node silently reported "not implemented" on tasks 2.2/2.3
    "hip_opens": check_hip_opens, "shot_login": check_shot_login,
    "runsheet_present": check_runsheet_present, "clean_install": check_clean_install,
    "nodes_appear": check_nodes_appear, "ledger": check_ledger,
    "revert_clean": check_revert_clean, "render": check_render, "theme_ok": check_theme_ok,
    # v2 — MCP orchestration
    "mcp_surface_probe": check_mcp_surface_probe, "mcp_registered": check_mcp_registered,
    "mcp_truth_contract": check_mcp_truth_contract, "scout_federates": check_scout_federates,
    # v2 — guardrails
    "scout_no_apex_corpus": check_scout_no_apex_corpus, "no_rigging_drift": check_no_rigging_drift,
    "provenance_not_bypassed": check_provenance_not_bypassed,
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--worktree", required=True)
    ap.add_argument("--hython", default="")
    ap.add_argument("--mode", default="A")
    a = ap.parse_args()

    doc = json.loads((Path(__file__).resolve().parents[1] / "tasks.json").read_text())
    tasks = doc["tasks"]
    guardrail_names = (doc.get("guardrails") or {}).get("checks", [])
    task = next((t for t in tasks if t["id"] == a.task), None)
    if not task:
        print(json.dumps({"verdict": "ERROR", "detail": f"unknown task {a.task}"})); return

    ctx = {"wt": a.worktree, "hython": a.hython, "mode": a.mode}

    # task-specific verifies
    facts = {}
    for name in task.get("verify", []):
        facts[name] = run_one(name, task, ctx)

    # cross-cutting guardrails — every sprint
    guards = {}
    for name in guardrail_names:
        guards[name] = run_one(name, task, ctx)
    violations = [k for k, v in guards.items() if v.get("ok") is False]
    unwired = [k for k, v in guards.items() if v.get("ok") is None]

    task_ok = all(v.get("ok") for v in facts.values()) if facts else True
    required_ok = task_ok and not violations

    print(json.dumps({
        "task": a.task, "mode": a.mode,
        "verdict": "PASS" if required_ok else "FAIL",
        "checks": facts,
        "guardrails": guards,
        "guardrail_violations": violations,
        "guardrail_unwired": unwired,
    }, indent=2))

if __name__ == "__main__":
    main()
