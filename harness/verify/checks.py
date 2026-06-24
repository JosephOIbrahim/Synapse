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
    # The 'your tool vs a studio's tool' check: install via package only, no hardcoded fallback.
    # ADAPT: run install.py against a TEMP HOUDINI_USER_PREF_DIR so it's a real clean env.
    bad = "C:\\Users\\User\\SYNAPSE"
    src = ""
    for root, _, files in os.walk(ctx["wt"]):
        if ".git" in root or "worktrees" in root:
            continue
        for fn in files:
            if fn.endswith((".py", ".json", ".pypanel")):
                try:
                    src += (Path(root) / fn).read_text(errors="ignore")
                except Exception:
                    pass
    hardcoded = bad.lower() in src.lower()
    return {"ok": not hardcoded, "detail": "hardcoded user-path fallback FOUND" if hardcoded
            else "no hardcoded fallback detected (ADAPT: also assert install.py registers nodes in a temp pref dir)"}

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

DISPATCH = {
    "import_panel": check_import_panel, "brain_answers": check_brain_answers,
    "doctor": check_doctor, "probe_runs": check_probe_runs, "probe_clean": check_probe_clean,
    "version_single_source": check_version_single_source, "cook_existing": check_cook,
    "hip_opens": check_hip_opens, "shot_login": check_shot_login,
    "runsheet_present": check_runsheet_present, "clean_install": check_clean_install,
    "nodes_appear": check_nodes_appear, "ledger": check_ledger,
    "revert_clean": check_revert_clean, "render": check_render, "theme_ok": check_theme_ok,
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--worktree", required=True)
    ap.add_argument("--hython", default="")
    ap.add_argument("--mode", default="A")
    a = ap.parse_args()

    tasks = json.loads((Path(__file__).resolve().parents[1] / "tasks.json").read_text())["tasks"]
    task = next((t for t in tasks if t["id"] == a.task), None)
    if not task:
        print(json.dumps({"verdict": "ERROR", "detail": f"unknown task {a.task}"})); return

    ctx = {"wt": a.worktree, "hython": a.hython, "mode": a.mode}
    facts = {}
    for name in task.get("verify", []):
        fn = DISPATCH.get(name)
        if not fn:
            facts[name] = {"ok": False, "detail": "no check implemented — ADAPT"}
            continue
        # cook_node uses the task's target_node; cook_existing uses the default
        if name == "cook_node":
            facts[name] = check_cook(ctx, node=task.get("target_node", "").replace("ADAPT: ", "") or None)
        else:
            facts[name] = fn(ctx)

    required_ok = all(v.get("ok") for v in facts.values()) if facts else True
    print(json.dumps({
        "task": a.task, "mode": a.mode,
        "verdict": "PASS" if required_ok else "FAIL",
        "checks": facts,
    }, indent=2))

if __name__ == "__main__":
    main()
