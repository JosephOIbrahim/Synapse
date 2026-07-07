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

def sh(cmd, cwd=None, timeout=900, env=None):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                            shell=(os.name == "nt"), env=env)
        return p.returncode, p.stdout or "", p.stderr or ""
    except Exception as e:
        return 1, "", f"{type(e).__name__}: {e}"


def _wt_env(ctx):
    """Env for stock-python subprocesses with the WORKTREE's synapse package
    first on the path — a dev machine may carry an editable install pointing at
    the main checkout, which would silently test the wrong code."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(ctx["wt"]) / "python") + os.pathsep + env.get("PYTHONPATH", "")
    return env

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
    # REAL frame validation (was a size>1024 byte stub — a 2 KB all-black EXR passes that but is a
    # failed render). Score the rendered PIXELS with the shipped product validator,
    # synapse.server.handlers_render._handle_validate_frame, which runs OIIO black-frame / NaN-Inf
    # analysis and degrades to file-integrity when OIIO is absent. Run it inside hython — OIIO and
    # the synapse package live in Houdini's interpreter, not stock python.
    driver = (_BOOT + "import json\n"
              "from synapse.server.handlers_render import RenderHandlerMixin\n"
              "class _V(RenderHandlerMixin):\n"
              "    pass\n"
              "res = _V()._handle_validate_frame({'image_path': " + json.dumps(str(img)) + ",\n"
              "    'checks': ['file_integrity', 'black_frame', 'nan_check']})\n"
              "print('VALIDATE', json.dumps(res))\n")
    vrc, vout, verr = hython(ctx["hython"], driver, ctx["wt"])
    line = next((l for l in vout.splitlines() if l.startswith("VALIDATE ")), "")
    if not line:
        return {"ok": False, "detail": ("validate_frame did not run: " + (verr or vout).strip())[:500]
                or "validate_frame produced no output"}
    try:
        verdict = json.loads(line[len("VALIDATE "):])
    except Exception as ex:
        return {"ok": False, "detail": f"validate_frame output unparseable: {str(ex)[:300]}"}
    if not verdict.get("oiio_available"):
        # honest-false: without OIIO the validator only checked file integrity, so a real
        # non-black assertion is impossible here — never a fake pass on an unverifiable frame.
        return {"ok": False, "detail": "OIIO unavailable in hython — frame written but pixels "
                                       "unverified (cannot assert non-black)"}
    black = verdict.get("checks", {}).get("black_frame", {})
    non_black = bool(black.get("passed"))
    nan_ok = bool(verdict.get("checks", {}).get("nan_check", {}).get("passed", True))
    ok = non_black and nan_ok
    return {"ok": ok, "detail": (f"validate_frame: non_black={non_black} (mean_lum="
            f"{black.get('value')}) nan_ok={nan_ok}; {img.stat().st_size} bytes — "
            f"{verdict.get('summary', '')}")[:500]}

def check_theme_ok(ctx):
    # Honest: theme correctness is screenshot + human review. Surface, don't fake-pass.
    return {"ok": False, "detail": "ADAPT/HUMAN: capture panel screenshot in host theme; flagged for visual review, not auto-passed"}


def check_mcp_registered(ctx):
    # D-H22-1: the APEX MCP is registered as a first-class provider and a round-trip tool call
    # returns a truth-contract-shaped envelope (it carries what was OBSERVED). On H21 this
    # exercises the provider against the mock (science/mcp_mock.py behind the endpoint seam).
    # WIRED (WS2 Part 1): registry = synapse.providers.get; benign tool = ping.
    code = _BOOT + ("import synapse.providers as providers\n"
            "try:\n"
            "    prov = providers.get('apex_mcp')\n"
            "    env = prov.call_tool('ping', {})\n"
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
    # WIRED (WS2 Part 1): the probe enumerates via providers.get('apex_mcp').list_tools()
    # and writes the delta where --out points. Exit 0 = facts reported; the gate below judges.
    runner = ctx["hython"] or sys.executable
    rc, out, err = sh([runner, "python/synapse/science/mcp_surface_probe.py", "--diff", "--out",
                       ".claude/mcp_surface_delta.json"], cwd=ctx["wt"])
    p = Path(ctx["wt"]) / ".claude/mcp_surface_delta.json"
    if rc != 0 or not p.exists():
        return {"ok": False, "detail": (out or err).strip()[:400] or "mcp_surface_probe.py produced no delta — see python/synapse/science/mcp_surface_probe.py"}
    try:
        d = json.loads(p.read_text())
        absent, renamed = d.get("absent", []), d.get("renamed", [])
        ok = not absent and not renamed
        return {"ok": ok, "detail": f"absent={len(absent)} renamed={len(renamed)} (both must be 0 before wiring)"}
    except Exception as e:
        return {"ok": False, "detail": str(e)[:300]}

def check_mcp_truth_contract(ctx):
    # The handler cannot claim an outcome it didn't observe, and the MCP's own validator verdict
    # is recorded as a provenance INPUT — never restated as a Synapse claim.
    # WIRED (WS2 Part 1): envelope fields per synapse/providers/apex_mcp.py.
    code = _BOOT + ("import synapse.providers as providers\n"
            "try:\n"
            "    env = providers.get('apex_mcp').call_tool('validate', {'src': 'noop'})\n"
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
    # WIRED (WS2 Part 1): python/synapse/server/authoring_domains.json =
    # {"domains": ["cop","lop","sop","karma","usd"]}.
    wt = Path(ctx["wt"])
    allow = wt / "python" / "synapse" / "server" / "authoring_domains.json"
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
    return {"ok": None, "detail": "authoring-domain allowlist not declared yet (python/synapse/server/authoring_domains.json missing)"}

def check_provenance_not_bypassed(ctx):
    # Non-goal: not a commodity hou.* passthrough. Every scene/stage mutation routes through the
    # provenance gateway and lands in agent.usd. The rigorous form is a RUNTIME sentinel (perform
    # a sandboxed mutation, assert the ledger grew by one). Until that's wired this WARNS — it
    # neither fake-passes nor blocks every sprint.
    # ADAPT: name the provenance gateway + either a mutation-capable-module manifest (static) or
    # the sandbox sentinel (runtime, Mode B).
    return {"ok": None, "detail": "ADAPT: wire the provenance-gateway manifest or the runtime ledger-grew sentinel. Warn-only until then."}

# ---------- phantom guardrail (Upgrade 3 / P2): the orphaned gate, wired into the loop ----------
# forge_evaluator_gate.py::gate_phantom scanned a fixed file list and was never called by the
# loop. This is the live-loop form: a deterministic guardrail that fails a sprint which
# INTRODUCES a phantom hou.* API — SYNAPSE's #1 failure class (hou.pdg / hou.secure /
# hou.lopNetworks / hou.updateGraphTick). Authority is the introspected dir() symbol table
# (the Spike-2.5 lesson: membership by the table, NEVER a hardcoded denylist — that demotion
# drove false-phantom 0.667 -> 0). AST-based, so comments / docstrings / string-literals are
# inherently ignored (a phantom named in prose is a Constant node, never an Attribute).

# GUI-only top-level hou submodules that a HEADLESS dir() introspection can't see (Houdini
# doesn't load them without a UI), yet are real, documented, and used across panel/host code —
# absence from the headless table is an introspection artifact, NOT a phantom, so union them in.
_GUI_HOU_ABSENT_HEADLESS = {"hou.ui", "hou.qt", "hou.audio", "hou.desktop", "hou.viewportVisualizers"}


def _hou_phantoms_in_source(src, table_syms):
    """[(lineno, "hou.<attr>"), ...] for hou-module attribute accesses the table PROVES absent.
    Depth-1 hou.<attr> ONLY: the table enumerates every top-level name of `hou` via dir(), so
    absence there is proof; deeper access (hou.Class.method) is not table-complete, so unknown
    != phantom (the inner hou.Class is judged + covered; the outer has an Attribute value and is
    skipped). `import hou as X` aliases resolve to the canonical hou.<attr>."""
    import ast  # local, mirrors check_version_single_source's local `import re`
    tree = ast.parse(src)  # SyntaxError on a broken file — the caller handles it
    hou_names = {"hou"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "hou":
                    hou_names.add(alias.asname or "hou")
    hits = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id in hou_names):
            symbol = "hou." + node.attr
            if symbol not in table_syms:
                hits.append((node.lineno, symbol))
    return hits

def _sprint_added_py(wt, base):
    """{relpath: set(added_line_no) | None} for .py touched since <base> — None marks a new
    untracked file (whole file is new). `git diff --unified=0` gives exact added line numbers
    (committed + staged + unstaged); ls-files --others adds files the Generator never `git add`ed.
    Judging only ADDED lines is what makes the gate fail *introduced* phantoms, not pre-existing
    ones on an unchanged line of a merely-edited file."""
    import re
    added = {}
    _, diff, _ = sh(["git", "diff", "--unified=0", "--diff-filter=d", base, "--", "*.py"], cwd=wt)
    cur, newline = None, 0
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:].strip()
            cur = cur if cur.endswith(".py") else None
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            newline = int(m.group(1)) if m else 0
        elif line.startswith("+") and not line.startswith("+++"):
            if cur:
                added.setdefault(cur, set()).add(newline)
            newline += 1
        elif line.startswith("-") and not line.startswith("---"):
            pass  # deletions don't advance the new-file line counter
        else:
            newline += 1
    _, u_out, _ = sh(["git", "ls-files", "--others", "--exclude-standard", "--", "*.py"], cwd=wt)
    for ln in u_out.splitlines():
        rel = ln.strip()
        if rel.endswith(".py"):
            added[rel] = None
    return added

def check_phantom_clean(ctx):
    # Cross-cutting guardrail (tasks.json guardrails.checks): ok:False ⇒ run.ts short-circuits to
    # a repair ticket BEFORE the Evaluator. Table missing/stale/gate-down ⇒ ok:None (WARN, never
    # a false block). Scoped to the sprint's CHANGED .py (git diff vs the branch fork point).
    wt = ctx["wt"]
    # 1) membership authority — reuse scout's own loader (per-major path + blake2b integrity +
    #    host-version staleness, for free; pure-python, zero-hou). None ⇒ gate down ⇒ WARN.
    try:
        from synapse.cognitive.tools.scout import _load_symbol_table
    except Exception as e:
        return {"ok": None, "detail": f"scout unavailable; phantom gate down: {type(e).__name__}: {e}"[:300]}
    table_syms, status = _load_symbol_table()
    if table_syms is None:
        return {"ok": None, "detail": f"symbol table missing/stale; phantom gate down: {status.get('reason')}"[:300]}
    if "hou" not in table_syms:
        return {"ok": None, "detail": "symbol table lacks the hou surface — cannot prove hou.* absence "
                                      "(regenerate via host/introspect_runtime.py)"}
    # GUI-only submodules (hou.ui/qt/audio/…) are real but absent from a HEADLESS dir() table —
    # union them so a live panel/host sprint isn't false-flagged into a stall.
    table_syms = table_syms | _GUI_HOU_ABSENT_HEADLESS
    # 2) scope to the sprint's ADDED .py lines — base = master HEAD at worktree-add time (fork
    #    point, robust if master advanced). Judging only newly-authored lines means a pre-existing
    #    phantom on an unchanged line of a merely-edited file never blocks the sprint.
    base_rc, base_out, base_err = sh(["git", "merge-base", "master", "HEAD"], cwd=wt)
    base = base_out.strip()
    if base_rc != 0 or not base:
        return {"ok": None, "detail": f"cannot determine diff base (git merge-base failed): "
                                      f"{(base_err or base_out).strip()[:200]}"}
    added = _sprint_added_py(wt, base)  # {relpath: set(added_lines) | None (=whole new file)}
    if not added:
        return {"ok": True, "detail": "no changed .py lines in this sprint"}
    # 3) AST-scan each changed file; flag table-proven-absent hou.<attr> only on ADDED lines.
    offenders, unparseable = [], []
    for rel, addl in added.items():
        f = Path(wt) / rel
        if not f.is_file():
            continue  # rename/deletion artifact, or a path outside the tree
        try:
            src = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        try:
            hits = _hou_phantoms_in_source(src, table_syms)
        except SyntaxError:
            unparseable.append(rel)  # a broken file fails other checks anyway — don't crash the gate
            continue
        for lineno, symbol in hits:
            if addl is None or lineno in addl:
                offenders.append(f"{rel}:{lineno}:{symbol}")
    ver = status.get("houdini_version", "?")
    if offenders:
        note = f" (+{len(unparseable)} unparseable, skipped)" if unparseable else ""
        return {"ok": False, "detail": (f"phantom hou.* introduced (absent in the {ver} symbol "
                f"table): {', '.join(sorted(set(offenders))[:12])}{note}")[:500]}
    clean = f"{len(added)} changed .py clean of table-proven phantom hou.* APIs (vs {len(table_syms)} live symbols @ {ver})"
    if unparseable:
        clean += f" ({len(unparseable)} unparseable, skipped)"
    return {"ok": True, "detail": clean[:500]}

def check_scout_federates(ctx):
    # D-H22-2: scout returns APEX results tagged as sourced from the federated MCP provider,
    # and exists_in_runtime remains present + authoritative on every hit.
    # WIRED (WS2 Part 1): query API = synapse_scout(query, domain='apex').
    code = _BOOT + ("try:\n"
            "    from synapse.cognitive.tools.scout import synapse_scout\n"
            "    hits = synapse_scout('apex rig pose', domain='apex')['hits']\n"
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
    reg = wt / "python" / "synapse" / "server" / "scout_sources.json"  # WIRED (WS2 Part 1)
    if reg.exists():
        try:
            data = json.loads(reg.read_text())
            apex = data.get("apex") or data.get("APEX")
            if apex and apex.get("kind") != "provider":
                return {"ok": False, "detail": f"scout APEX source kind='{apex.get('kind')}' — must be federated 'provider'"}
            return {"ok": True, "detail": "no local APEX corpus; scout APEX source is federated"}
        except Exception as e:
            return {"ok": False, "detail": f"scout_sources.json unreadable: {str(e)[:200]}"}
    return {"ok": None, "detail": "no APEX corpus found; scout source-registry not wired yet (python/synapse/server/scout_sources.json missing)"}

def check_connectivity_catalog_fresh(ctx):
    # U.1: the packaged connectivity catalog (the wire_by_label / P3e authority) must be
    # (a) internally sound — schema v2 + blake2b recomputes over its entries,
    # (b) byte-identical to the harness probe artifact it claims to be a copy of, and
    # (c) stamped with the live build when hython is available (stamp==build or the check
    #     FAILS explicitly — a stale catalog is a phantom-wiring vector, never silent).
    wt = Path(ctx["wt"])
    pkg = wt / "python/synapse/cognitive/tools/data/connectivity_21.json"
    if not pkg.exists():
        return {"ok": False, "detail": "packaged connectivity_21.json missing"}
    try:
        import hashlib
        data = json.loads(pkg.read_text(encoding="utf-8"))
        if data.get("schema") != "verified_connectivity/v2":
            return {"ok": False, "detail": f"schema={data.get('schema')} != verified_connectivity/v2"}
        digest = hashlib.blake2b(
            json.dumps(data.get("entries", {}), sort_keys=True, ensure_ascii=False).encode("utf-8"),
            digest_size=16).hexdigest()
        if digest != data.get("blake2b"):
            return {"ok": False, "detail": "packaged catalog blake2b mismatch (corrupt/hand-edited)"}
        stamp = data.get("houdini_version", "")
        harness_fp = wt / "harness" / "notes" / f"verified_connectivity_{stamp}.json"
        if not harness_fp.exists() or harness_fp.read_bytes() != pkg.read_bytes():
            return {"ok": False, "detail": f"packaged copy != {harness_fp.name} (re-run "
                                           "host/introspect_connectivity.py + re-copy)"}
    except Exception as e:
        return {"ok": False, "detail": f"catalog unreadable: {str(e)[:300]}"}
    if ctx["hython"]:
        code = "import hou\nprint('BUILD', hou.applicationVersionString())"
        rc, out, err = hython(ctx["hython"], code, ctx["wt"])
        live = next((l.split(" ", 1)[1] for l in out.splitlines() if l.startswith("BUILD ")), None)
        if live is None:
            return {"ok": False, "detail": f"could not read live build: {(err or out).strip()[:200]}"}
        if live != stamp:
            return {"ok": False, "detail": f"catalog stamp {stamp} != live build {live} — STALE; "
                                           "regenerate via host/introspect_connectivity.py"}
        return {"ok": True, "detail": f"catalog sound, byte-matched, stamp==live build {live}"}
    return {"ok": True, "detail": f"catalog sound + byte-matched (stamp {stamp}; live-build "
                                  "comparison skipped — HYTHON unset)"}

def check_wiring_conformance(ctx):
    # U.1: the REVIEW sweep re-runs clean — scripts/flywheel_review_wiring.py exits 0 with
    # zero CRITICAL findings (index-out-of-arity / label-claim-mismatch vs the catalog).
    # Runs WITHOUT --deposit / --queue-append: the Ledger deposit and queue append are the
    # Stage-3 opt-ins, never an every-sprint side effect.
    rc, out, err = sh([sys.executable, "scripts/flywheel_review_wiring.py"],
                      cwd=ctx["wt"], env=_wt_env(ctx))
    p = Path(ctx["wt"]) / ".claude/flywheel_u1_findings.json"
    if not p.exists():
        return {"ok": False, "detail": (out or err).strip()[:400] or "sweep produced no findings file"}
    try:
        crit = json.loads(p.read_text(encoding="utf-8"))["summary"]["critical"]
    except Exception as e:
        return {"ok": False, "detail": f"findings unreadable: {str(e)[:200]}"}
    head = (out or err).strip().splitlines()
    return {"ok": rc == 0 and crit == 0,
            "detail": f"rc={rc} critical={crit}; {head[0][:300] if head else ''}"}

def check_validator_catches_miswire(ctx):
    # U.1: the golden miswire fixtures (vellumsolver constraint->2 / collision->1 swap,
    # rbdbulletsolver constraint->2, out-of-range index) are REJECTED by GraphValidator P3e
    # while the corrected forms pass — pinned in tests/test_wiring_flywheel.py. Runs the
    # pinned assertions directly (stock python; the fixtures are pure + packaged-catalog-backed).
    rc, out, err = sh([sys.executable, "-m", "pytest",
                       "tests/test_wiring_flywheel.py", "-q"],
                      cwd=ctx["wt"], env=_wt_env(ctx))
    tail = (out or err).strip().splitlines()
    return {"ok": rc == 0, "detail": (tail[-1] if tail else "no pytest output")[:400]}


def check_lop_knowledge_fresh(ctx):
    # U.5: the packaged LOP/Solaris knowledge catalog (the validator's CONTEXT authority)
    # must be (a) schema lop_solaris_knowledge/v1 + blake2b recomputes over `content`, and
    # (b) byte-identical to the harness artifact it claims to copy (a hand-edit fails loud).
    # Corpus-authored (not a live probe), so there is no live-build stamp comparison — the
    # per-build re-mine duty is enforced by the byte-identical + source_digest gate in the miner.
    wt = Path(ctx["wt"])
    pkg = wt / "python/synapse/cognitive/tools/data/lop_solaris_knowledge_21.json"
    if not pkg.exists():
        return {"ok": False, "detail": "packaged lop_solaris_knowledge_21.json missing"}
    try:
        import hashlib
        data = json.loads(pkg.read_text(encoding="utf-8"))
        if data.get("schema") != "lop_solaris_knowledge/v1":
            return {"ok": False, "detail": f"schema={data.get('schema')} != lop_solaris_knowledge/v1"}
        digest = hashlib.blake2b(
            json.dumps(data.get("content", {}), sort_keys=True, ensure_ascii=False).encode("utf-8"),
            digest_size=16).hexdigest()
        if digest != data.get("blake2b"):
            return {"ok": False, "detail": "packaged catalog blake2b mismatch (corrupt/hand-edited)"}
        stamp = data.get("houdini_version", "")
        harness_fp = wt / "harness" / "notes" / f"verified_lop_solaris_knowledge_{stamp}.json"
        if not harness_fp.exists() or harness_fp.read_bytes() != pkg.read_bytes():
            return {"ok": False, "detail": f"packaged copy != {harness_fp.name} (re-run "
                                           "scripts/mine_lop_knowledge.py)"}
    except Exception as e:
        return {"ok": False, "detail": f"catalog unreadable: {str(e)[:300]}"}
    return {"ok": True, "detail": f"LOP catalog sound + byte-matched (schema v1, stamp {stamp})"}

def check_lop_review_clean(ctx):
    # U.5: the REVIEW grounding sweep re-runs clean — scripts/flywheel_review_lop.py exits 0
    # with zero CRITICAL (integrity / structural / probe-confirmed-drift / known-absent-
    # contradiction). Runs WITHOUT --deposit: the Ledger deposit is the Stage-3 post-merge opt-in.
    rc, out, err = sh([sys.executable, "scripts/flywheel_review_lop.py"],
                      cwd=ctx["wt"], env=_wt_env(ctx))
    p = Path(ctx["wt"]) / ".claude/flywheel_u5_findings.json"
    if not p.exists():
        return {"ok": False, "detail": (out or err).strip()[:400] or "review produced no findings file"}
    try:
        crit = json.loads(p.read_text(encoding="utf-8"))["summary"]["critical"]
    except Exception as e:
        return {"ok": False, "detail": f"findings unreadable: {str(e)[:200]}"}
    head = (out or err).strip().splitlines()
    return {"ok": rc == 0 and crit == 0,
            "detail": f"rc={rc} critical={crit}; {head[0][:300] if head else ''}"}

def check_validator_lop_conformance(ctx):
    # U.5: the golden LOP behaviors are pinned in tests/test_lop_flywheel.py — grid/plane
    # HARD-ERROR (incl. capitalized + EXISTING-skip); materiallibrary/reference/sublayer SATISFY;
    # a missing material source ADVISES (never a hard reject); a malformed catalog degrades to skip.
    # Runs the pinned assertions directly (stock python; pure + packaged-catalog-backed).
    rc, out, err = sh([sys.executable, "-m", "pytest",
                       "tests/test_lop_flywheel.py", "-q"],
                      cwd=ctx["wt"], env=_wt_env(ctx))
    tail = (out or err).strip().splitlines()
    return {"ok": rc == 0, "detail": (tail[-1] if tail else "no pytest output")[:400]}


# ---------- v6 track: blueprint-armed checks (all stock python, no hython) ----------
# Every check here reads the WORKTREE (ctx['wt']) like the rest of this file. run.ts arms
# the track off the MAIN checkout's working tree, but worktrees fork from HEAD — so an
# uncommitted docs/v6/ drop arms V-tasks whose worktrees contain no docs/v6 at all. The
# failure details below say so explicitly; the fix is always "commit the drop".

_V6_CANONICAL = ("BP00_manifest.md", "BP09_iteration_controller.md", "BP10_knowledge_base.md")

def check_blueprints_present(ctx):
    # v6: the arming marker + the Evaluator's drop inventory. ok hinges ONLY on BP00 (the
    # trigger file); the detail enumerates the whole BP00–BP10 surface either way. Never ok:None
    # — a missing drop is a fact, not a down gate.
    d = Path(ctx["wt"]) / "docs" / "v6"
    canon = {name: (d / name).is_file() for name in _V6_CANONICAL}
    pattern = sorted(p.name for p in d.glob("BP0[1-8]_*.md")) if d.is_dir() else []
    present = sorted([n for n, there in canon.items() if there] + pattern)
    missing = [n for n, there in canon.items() if not there]
    inv = f"present: {', '.join(present) or 'none'}; missing canonical: {', '.join(missing) or 'none'}"
    if not canon["BP00_manifest.md"]:
        return {"ok": False, "detail": ("docs/v6/BP00_manifest.md absent from the WORKTREE — "
                "if you dropped it, did you `git add docs/v6 && git commit`? (worktrees fork "
                f"from HEAD). {inv}")[:500]}
    return {"ok": True, "detail": inv[:500]}

def _bp00_manifest_rows(text):
    """[(path, layer_cell), ...] from BP00's `## Module Manifest` table, or None if the
    section or its table is missing entirely. A row counts as data only when its first
    column is a .py path — the header row ('path | layer | …') and the |---| separator
    fall out for free. Distinguishing None (no table) from [] (hollow table) matters: a
    zero-row table must NOT vacuously pass the conformance check."""
    import re
    lines = text.splitlines()
    idx = next((i for i, l in enumerate(lines)
                if re.match(r"\s*#{2,6}\s", l) and "module manifest" in l.lower()), None)
    if idx is None:
        return None
    rows, seen_table = [], False
    for l in lines[idx + 1:]:
        s = l.strip()
        if re.match(r"#{1,6}\s", s):
            break  # next section
        if not s.startswith("|"):
            if seen_table and s:
                break  # prose after the table ends it
            continue
        seen_table = True
        cells = [c.strip() for c in s.strip("|").split("|")]
        if cells and cells[0].endswith(".py"):
            rows.append((cells[0].replace("\\", "/"), cells[1] if len(cells) > 1 else ""))
    return rows if seen_table else None

def check_v6_skeleton_conformance(ctx):
    # V.1's gate: every module BP00's manifest names must exist and compile; "pure"-layer
    # rows must carry ZERO hou imports at ANY depth (V.1's wording — pure means pure; a
    # function-level `import hou` is still a hou dependency. importlib-string evasion is
    # left to the adversarial Evaluator). Compile is in-memory builtin compile(), not
    # py_compile — a verify step must not litter __pycache__ into the tree it judges.
    import ast
    wt = Path(ctx["wt"])
    bp00 = wt / "docs" / "v6" / "BP00_manifest.md"
    if not bp00.is_file():
        return {"ok": False, "detail": "docs/v6/BP00_manifest.md missing in worktree "
                                       "(commit the drop?) — see docs/v6/INTAKE.md"}
    # utf-8-sig on every human-authored read: a Windows-saved drop arrives BOM'd, and a BOM
    # survives a plain utf-8 decode — it then breaks the heading regex here and is a
    # SyntaxError to compile() below. Tolerate the BOM, don't flunk the drop over an editor.
    rows = _bp00_manifest_rows(bp00.read_text(encoding="utf-8-sig", errors="ignore"))
    if rows is None:
        return {"ok": False, "detail": "no `## Module Manifest` section/table in "
                                       "BP00_manifest.md — see docs/v6/INTAKE.md"}
    if not rows:
        return {"ok": False, "detail": "Module Manifest table has no module rows (first "
                                       "column must be a repo-relative .py path) — see docs/v6/INTAKE.md"}
    missing, broken, impure, escapes = [], [], [], []
    for rel, layer in rows:
        rp = Path(rel)
        # containment: rows are contractually repo-relative. An absolute/drive/.. path makes
        # `wt / rel` silently REPLACE the base (pathlib join semantics), so a file OUTSIDE
        # the worktree could satisfy "exists + compiles" — reject the row, never judge
        # foreign disk.
        if rp.is_absolute() or rp.drive or ".." in rp.parts:
            escapes.append(rel)
            continue
        f = wt / rel
        if not f.is_file():
            missing.append(rel)
            continue
        src = f.read_text(encoding="utf-8-sig", errors="ignore")
        try:
            tree = ast.parse(src)
            compile(src, str(f), "exec")
        except SyntaxError as e:
            broken.append(f"{rel}:{e.lineno}")
            continue
        if "pure" in layer.lower():
            for node in ast.walk(tree):
                names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                         else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
                if any(n == "hou" or n.startswith("hou.") for n in names):
                    impure.append(rel)
                    break
    bad = []
    if escapes:
        bad.append(f"not repo-relative (escapes worktree): {', '.join(escapes[:6])}")
    if missing:
        bad.append(f"missing: {', '.join(missing[:6])}")
    if broken:
        bad.append(f"won't compile: {', '.join(broken[:6])}")
    if impure:
        bad.append(f"pure layer imports hou: {', '.join(impure[:6])}")
    if bad:
        return {"ok": False, "detail": ("; ".join(bad))[:500]}
    return {"ok": True, "detail": f"{len(rows)} manifest module(s) present + compile; pure layers hou-free"}

def _v6_spec_headings(ctx, rel, required):
    # Shared mechanic for v6_spec_bp09/bp10: case-insensitive substring match restricted to
    # HEADING LINES (^#{1,6}\s) only — body prose like "we will add tests later" must never
    # satisfy the "Tests" requirement (that would be a quiet fake pass).
    import re
    f = Path(ctx["wt"]) / rel
    if not f.is_file():
        return {"ok": False, "detail": f"{rel} missing in worktree"}
    heads = [l.strip().lower() for l in f.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
             if re.match(r"\s*#{1,6}\s", l)]
    missing = [t for t in required if not any(t.lower() in h for h in heads)]
    if missing:
        return {"ok": False, "detail": f"{rel}: missing required heading(s): "
                                       f"{', '.join(missing)} ({len(heads)} headings scanned)"}
    return {"ok": True, "detail": f"{rel}: all {len(required)} required headings present"}

def check_v6_spec_bp09(ctx):
    # "Convergence" + "Stop" may live in one heading ("Convergence & Stop Logic") — matched
    # as two independent terms, so that form satisfies both.
    return _v6_spec_headings(ctx, "docs/v6/BP09_iteration_controller.md",
                             ["Loop Orchestration", "Convergence", "Stop", "Max-Iteration",
                              "Strategy", "H22 Dependencies", "Tests"])

def check_v6_spec_bp10(ctx):
    return _v6_spec_headings(ctx, "docs/v6/BP10_knowledge_base.md",
                             ["Recipe Store", "Failure", "Vector Schema", "Query API", "Tests"])

# The roundtrip driver runs in a STOCK-PYTHON SUBPROCESS with the worktree's package pinned
# first (env=_wt_env) — in-process import would resolve `synapse` to whatever this process
# already loaded (editable install / repo checkout), silently testing the wrong tree. The
# KB-FILE line lets the parent assert the module really came from the worktree.
_KB_ROUNDTRIP_DRIVER = """\
import sys, tempfile
import synapse.v6.knowledge_base as kb_mod
print("KB-FILE", getattr(kb_mod, "__file__", "?"))
recipe = {"name": "pyro_smoke_v1",
          "steps": [{"op": "create", "type": "pyrosolver", "parms": {"divsize": 0.05}}],
          "tags": ["pyro", "smoke"]}
failure = {"symptom": "black frame",
           "context": {"node": "/stage/karma1", "frames": [1, 2, 3], "settings": {"engine": "xpu"}}}
with tempfile.TemporaryDirectory() as tmp:
    kb = kb_mod.KnowledgeBase(root=tmp)
    kb.add_recipe(recipe)
    kb.add_failure(failure)
    got_r = kb.query("recipe")
    got_f = kb.query("failure")
    lossless = any(x == recipe for x in got_r) and any(x == failure for x in got_f)
    print("KB-ROUNDTRIP-OK" if lossless else "KB-ROUNDTRIP-LOSSY",
          f"recipes={len(got_r)} failures={len(got_f)}")
"""

def check_v6_kb_roundtrip(ctx):
    # V.3's independent gate (vs v6_tests_green's generator-authored tests): nested payloads
    # in, deep-equal out — lossless or fail. Disk check FIRST so the verdict never depends on
    # what `synapse` resolves to in THIS process (the module-absent branch stays hermetic
    # forever, even after v6/ merges to the main repo).
    wt = Path(ctx["wt"]).resolve()
    mod = wt / "python" / "synapse" / "v6" / "knowledge_base.py"
    if not mod.is_file():
        return {"ok": False, "detail": "BP10 not built yet (task V.3): "
                                       "python/synapse/v6/knowledge_base.py absent"}
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(_KB_ROUNDTRIP_DRIVER); path = f.name
    try:
        rc, out, err = sh([sys.executable, path], cwd=ctx["wt"], env=_wt_env(ctx))
    finally:
        os.unlink(path)
    fileline = next((l for l in out.splitlines() if l.startswith("KB-FILE ")), "")
    resolved = fileline[8:].strip().replace("\\", "/").lower()
    if resolved and str(wt).replace("\\", "/").lower() not in resolved:
        return {"ok": False, "detail": f"knowledge_base resolved OUTSIDE the worktree: {resolved[:300]}"}
    if rc == 0 and "KB-ROUNDTRIP-OK" in out:
        return {"ok": True, "detail": "recipe + failure round-trip deep-equal (lossless)"}
    return {"ok": False, "detail": (err or out).strip()[-500:] or "roundtrip produced no output"}

def check_v6_tests_green(ctx):
    # V.3–V.7's shared gate. tests/v6 absent → honest-false (test-first is the v6 law).
    # rc 0 alone is NOT green: an all-skipped run also exits 0, so a blanket pytestmark=skip
    # could fake a pass — require ≥1 test actually PASSED in the summary. (Empty dir is
    # already safe: pytest rc 5.)
    import re
    wt = Path(ctx["wt"])
    if not (wt / "tests" / "v6").is_dir():
        return {"ok": False, "detail": "test-first: tests/v6/ must land first"}
    rc, out, err = sh([sys.executable, "-m", "pytest", "tests/v6/", "-q", "--no-header", "-x"],
                      cwd=ctx["wt"], env=_wt_env(ctx))
    tail = (out or err).strip().splitlines()
    summary = tail[-1] if tail else "no pytest output"
    if rc == 0 and not re.search(r"\b[1-9]\d* passed\b", out):
        return {"ok": False, "detail": f"rc=0 but ZERO tests passed (all skipped?) — {summary[:350]}"}
    return {"ok": rc == 0, "detail": f"rc={rc}; {summary[:400]}"}


# ---------- C track: context-capability (catalog + review sweep + per-context goldens) ----------
# The catalog (harness/notes/context_capability_21.json) is this track's truth deposit: what
# SYNAPSE can actually CREATE per Houdini context (sop/lop/cop/top/dop/mat), probed through the
# live handler surface — never raw hou for mutations. Worktrees fork from HEAD, so the failure
# details below say "commit/merge" explicitly, same discipline as the v6 block above.

def check_context_catalog_fresh(ctx):
    # C.0 + every C.n: the catalog must be (a) internally sound — schema v1 + blake2b
    # recomputes over `contexts` (generated/summary/unclassified sit OUTSIDE the digest by
    # design), and (b) stamped with the live build when hython is available (stale → FAIL
    # loud; a stale catalog re-ranks C.1–C.6 off dead truth). Unlike connectivity there is
    # no packaged copy yet — the harness note IS canonical — so no byte-identity leg.
    wt = Path(ctx["wt"])
    cat = wt / "harness" / "notes" / "context_capability_21.json"
    if not cat.exists():
        return {"ok": False, "detail": "harness/notes/context_capability_21.json missing — "
                                       "run C.0 first; commit the catalog — worktrees fork from HEAD"}
    try:
        import hashlib
        data = json.loads(cat.read_text(encoding="utf-8"))
        if data.get("schema") != "context_capability/v1":
            return {"ok": False, "detail": f"schema={data.get('schema')} != context_capability/v1"}
        digest = hashlib.blake2b(
            json.dumps(data.get("contexts", {}), sort_keys=True, ensure_ascii=False).encode("utf-8"),
            digest_size=16).hexdigest()
        if digest != data.get("blake2b"):
            return {"ok": False, "detail": "catalog blake2b mismatch (corrupt/hand-edited)"}
        stamp = data.get("houdini_version", "")
    except Exception as e:
        return {"ok": False, "detail": f"catalog unreadable: {str(e)[:300]}"}
    if ctx["hython"]:
        code = "import hou\nprint('BUILD', hou.applicationVersionString())"
        rc, out, err = hython(ctx["hython"], code, ctx["wt"])
        live = next((l.split(" ", 1)[1] for l in out.splitlines() if l.startswith("BUILD ")), None)
        if live is None:
            return {"ok": False, "detail": f"could not read live build: {(err or out).strip()[:200]}"}
        if live != stamp:
            return {"ok": False, "detail": f"catalog stamp {stamp} != live build {live} — STALE; "
                                           "regenerate via host/introspect_context_capability.py"}
        return {"ok": True, "detail": f"catalog sound, stamp==live build {live}"}
    return {"ok": True, "detail": f"catalog sound (stamp {stamp}; live-build "
                                  "comparison skipped — HYTHON unset)"}

def check_context_review_clean(ctx):
    # C.0: the REVIEW sweep re-runs clean — scripts/flywheel_review_context.py exits 0 with
    # zero CRITICAL findings (integrity / misclassification / internal inconsistency). The
    # sweep only reports; THIS check judges critical — mirrors check_lop_review_clean.
    rc, out, err = sh([sys.executable, "scripts/flywheel_review_context.py"],
                      cwd=ctx["wt"], env=_wt_env(ctx))
    p = Path(ctx["wt"]) / ".claude/flywheel_ctx_findings.json"
    if not p.exists():
        return {"ok": False, "detail": (out or err).strip()[:400] or "review produced no findings file"}
    try:
        crit = json.loads(p.read_text(encoding="utf-8"))["summary"]["critical"]
    except Exception as e:
        return {"ok": False, "detail": f"findings unreadable: {str(e)[:200]}"}
    head = (out or err).strip().splitlines()
    return {"ok": rc == 0 and crit == 0,
            "detail": f"rc={rc} critical={crit}; {head[0][:300] if head else ''}"}

def _context_golden(ctx, name):
    # C.1–C.6's shared gate: re-run the probe for ONE context; ok needs BOTH the golden (the
    # context's minimum viable create-path) AND the ratchet (gaps strictly decrease vs the
    # COMMITTED catalog, unless already 0). The baseline reads HEAD's catalog via `git show`,
    # NOT the worktree file — the sprint refreshes the catalog in-tree, and a refreshed file
    # as baseline would compare the probe against itself (fresh==fresh ⇒ the ratchet could
    # never hold). HEAD is what the human merged; promoting a new baseline is theirs.
    if not ctx["hython"]:
        # ok:False, not ok:None — a golden that can't run is not verified (spec §3).
        return {"ok": False, "detail": "HYTHON unset — a golden that cannot run is not verified"}
    rc_b, cat, _ = sh(["git", "show", "HEAD:harness/notes/context_capability_21.json"], cwd=ctx["wt"])
    if rc_b != 0 or not cat.strip():
        return {"ok": False, "detail": "no committed catalog at HEAD — run C.0 + merge first "
                                       "(the ratchet baseline is the MERGED catalog, not this sprint's refresh)"}
    try:
        gaps_base = len(json.loads(cat)["contexts"][name].get("gaps") or [])
    except Exception as e:
        return {"ok": False, "detail": f"committed catalog lacks a sound '{name}' entry "
                                       f"({type(e).__name__}: {str(e)[:150]}) — run C.0 + merge first"}
    artifact = f".claude/ctx_probe_{name}.json"
    p = Path(ctx["wt"]) / artifact
    p.unlink(missing_ok=True)  # a stale artifact surviving a failed probe run must not fake a verdict
    rc, out, err = sh([ctx["hython"], "host/introspect_context_capability.py",
                       "--context", name, "--out", artifact], cwd=ctx["wt"])
    if not p.exists():
        # the probe's contract is rc 0 iff the artifact was written — judge the FILE, and
        # NEVER stdout (hython banners pollute it); the tail is only failure evidence.
        return {"ok": False, "detail": f"probe wrote no artifact (rc={rc}): {(err or out).strip()[-300:]}"}
    try:
        entry = json.loads(p.read_text(encoding="utf-8"))["contexts"][name]
        golden = entry.get("golden") or {}
        golden_ok = golden.get("ok") is True
        steps = golden.get("steps") or []
        gaps = entry.get("gaps") or []
        gaps_now = len(gaps)
    except Exception as e:
        return {"ok": False, "detail": f"probe artifact unreadable/malformed for '{name}': "
                                       f"{type(e).__name__}: {str(e)[:250]}"}
    first_fail = next((s for s in steps if s.get("ok") is not True), None)
    if first_fail is not None:
        fail_note = f"; first failing step: {first_fail.get('step')} ({str(first_fail.get('detail'))[:120]})"
    elif gaps:
        fail_note = f"; first gap: {str(gaps[0])[:120]}"  # extended-step failure — golden steps all ok
    else:
        fail_note = ""
    ratchet = (gaps_base == 0 and gaps_now == 0) or (gaps_base > 0 and gaps_now <= gaps_base - 1)
    return {"ok": golden_ok and ratchet,
            "detail": (f"golden={'ok' if golden_ok else 'FAIL'}; gaps now={gaps_now} baseline={gaps_base}; "
                       f"ratchet {'holds' if ratchet else 'broken (gaps must strictly decrease unless already 0)'}"
                       + fail_note)[:500]}

def check_context_golden_sop(ctx):
    return _context_golden(ctx, "sop")

def check_context_golden_lop(ctx):
    return _context_golden(ctx, "lop")

def check_context_golden_cop(ctx):
    return _context_golden(ctx, "cop")

def check_context_golden_top(ctx):
    return _context_golden(ctx, "top")

def check_context_golden_dop(ctx):
    return _context_golden(ctx, "dop")

def check_context_golden_mat(ctx):
    return _context_golden(ctx, "mat")


# ---------- S — studio-readiness hardening track (all stock python, no hython) ----------
# Each S-check is a DURABLE REGRESSION GATE around a finding of
# docs/reviews/synapse-studio-readiness-2026-07-06.html: it reads RED while the finding's
# fingerprint is live in the product source and flips GREEN only when the SPECIFIC defect is
# gone (then stays green so the finding can never silently regress). Fingerprints are static
# grep/AST over the worktree's source (ctx['wt']) — none needs hython. Honest-false ethos:
# every ok:false names the live defect + the fix criterion. The four security-critical checks
# (posture/policy/consent/rbac) are the capstone's gate; the fixes are the human's/loop's
# separate sprints — these checks only READ product code, they never edit it.

def _posture_path():
    # Posture is a MACHINE-LEVEL declaration (peer of drop.json), NOT worktree state — so it is
    # read from the MAIN repo, never ctx['wt']. checks.py lives at <repo>/harness/verify/, so
    # parents[1] is harness/ and parents[1].parent is the repo root. A module-level function so
    # tests can monkeypatch the seam to a tmp posture file.
    return Path(__file__).resolve().parents[1].parent / "harness" / "state" / "posture.json"

def _read_posture():
    """Parsed posture dict, or None if absent/malformed. Never raises — a down posture just
    means the studio legs stay dormant (solo/undeclared is the default posture)."""
    p = _posture_path()
    try:
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def _read_src(ctx, rel):
    """(text, path) for a product file under the worktree, or (None, path) if unreadable.
    The worktree is the SSOT the harness gates (worktrees fork from HEAD; committed product
    code is present). Tests set ctx['wt'] to a tmp tree carrying synthetic sources."""
    p = Path(ctx["wt"]) / rel
    try:
        return p.read_text(encoding="utf-8", errors="ignore"), p
    except Exception:
        return None, p

_POSTURE_TEMPLATE = ('{"mode": "solo|studio|farm", "identity_model": "<free text>", '
                     '"auto_approve": <true|false>}')

def check_posture_declared(ctx):
    # S.0 trigger: the deployment posture must be a committed fact before consent-auto-approve
    # and RBAC-default-deny can be enforced per-mode. Reads the MAIN-repo posture.json (NOT the
    # worktree). Never ok:None — a missing declaration is a FACT (write the file), not a down gate.
    p = _posture_path()
    if not p.exists():
        return {"ok": False, "detail": (f"harness/state/posture.json not declared — write "
                f"{_POSTURE_TEMPLATE} (mode in solo/studio/farm). See S.0 / spec-S-studio-readiness.md")[:500]}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"ok": False, "detail": (f"posture.json malformed ({type(e).__name__}: "
                f"{str(e)[:120]}) — expected {_POSTURE_TEMPLATE}")[:500]}
    mode, idm, aa = data.get("mode"), data.get("identity_model"), data.get("auto_approve")
    problems = []
    if mode not in ("solo", "studio", "farm"):
        problems.append(f"mode={mode!r} not in solo/studio/farm")
    if not (isinstance(idm, str) and idm.strip()):
        problems.append("identity_model missing/empty")
    if not isinstance(aa, bool):
        problems.append("auto_approve not a bool")
    if problems:
        return {"ok": False, "detail": (f"posture.json invalid: {'; '.join(problems)} — "
                f"expected {_POSTURE_TEMPLATE}")[:500]}
    return {"ok": True, "detail": f"posture declared: mode={mode}, identity_model={idm!r}, auto_approve={aa}"}

def check_policy_single_source(ctx):
    # S.1 SENTINEL gate (report: "No single source of truth for policy: five disagreeing
    # taxonomies, default-open on the bridge path"). GREEN needs BOTH a declared single source
    # (python/synapse/core/policy.py OR a `# POLICY_SINGLE_SOURCE` marker in the authoritative
    # table) AND the bridge's default-open fallback removed. Until then RED, naming the divergent
    # taxonomy files + the default-open site.
    wt = Path(ctx["wt"])
    sentinel = (wt / "python/synapse/core/policy.py").is_file()
    taxonomy = ("shared/bridge.py", "python/synapse/mcp/_tool_registry.py",
                "python/synapse/server/handlers.py", "python/synapse/panel/worker_policy.py")
    marker = False
    for rel in taxonomy + ("python/synapse/core/policy.py",):
        src, _ = _read_src(ctx, rel)
        if src and "# POLICY_SINGLE_SOURCE" in src:
            marker = True
            break
    bridge_src, _ = _read_src(ctx, "shared/bridge.py")
    # default-open: an unmapped op falls back to REVIEW (logs-and-continues, never blocks) rather
    # than default-deny. The literal on the bridge path — its removal is the fix's fingerprint.
    default_open = bool(bridge_src) and "OPERATION_GATES.get(self.operation_type, GateLevel.REVIEW)" in bridge_src
    present = [rel for rel in taxonomy if (wt / rel).is_file()]
    if (sentinel or marker) and not default_open:
        how = "core/policy.py" if sentinel else "# POLICY_SINGLE_SOURCE marker"
        return {"ok": True, "detail": f"single-source policy present ({how}); bridge default-open fallback removed"}
    reasons = []
    if not (sentinel or marker):
        reasons.append("no single source (python/synapse/core/policy.py absent AND no "
                       "`# POLICY_SINGLE_SOURCE` marker in the authoritative table)")
    if default_open:
        reasons.append("bridge default-open fallback live (shared/bridge.py: "
                       "OPERATION_GATES.get(self.operation_type, GateLevel.REVIEW) — unmapped ops "
                       "default to REVIEW, not default-deny)")
    reasons.append(f"divergent policy taxonomies: {', '.join(present)}")
    return {"ok": False, "detail": ("; ".join(reasons))[:500]}

def check_consent_enforced(ctx):
    # S.2 FINGERPRINT (report: HumanGate.propose has zero live producers; the only bridge-wired
    # path disarms its own gate and the MCP tools share that neutered singleton). RED while ANY
    # sub-condition holds; detail lists which are still true. Grep/AST over source, no hython.
    import re
    live = []
    ba_src, _ = _read_src(ctx, "python/synapse/panel/bridge_adapter.py")
    disarmed = bool(ba_src and re.search(r"_gate\s*=\s*None", ba_src))
    if disarmed:
        live.append("panel/bridge_adapter.py disarms consent (`_gate = None` on the panel bridge singleton)")
        # mcp sharing the panel singleton is a defect ONLY while that singleton is disarmed — once
        # the disarm is removed, the same import routes through an ARMED bridge. Gate this leg on the
        # disarm being live, else a correct fix (arm the bridge, keep the import) would stick RED.
        tools_src, _ = _read_src(ctx, "python/synapse/mcp/tools.py")
        if tools_src and "execute_through_bridge" in tools_src and "bridge_adapter" in tools_src:
            live.append("mcp/tools.py dispatches through the DISARMED panel singleton "
                        "(imports execute_through_bridge from synapse.panel.bridge_adapter)")
    # Producer backstop: a HumanGate.propose producer must exist SOMEWHERE on the consent surface —
    # INCLUDING the bridge's own site + core/gates.py. The natural fix arms the EXISTING bridge.py
    # producer by un-nulling _gate, which adds no `.propose(` token to a transport file; scanning
    # only transports would stay RED after that fix (a stuck gate, and consent is a critical → the
    # capstone would never certify READY). So fire only when NO producer exists anywhere — a real
    # regression, not the armed-bridge state.
    producer_surface = ("python/synapse/mcp/tools.py", "python/synapse/mcp/server.py",
                        "python/synapse/server/handlers.py", "python/synapse/server/websocket.py",
                        "python/synapse/server/hwebserver_adapter.py",
                        "python/synapse/panel/bridge_adapter.py",
                        "shared/bridge.py", "python/synapse/core/gates.py")
    producers = [rel for rel in producer_surface
                 if (_read_src(ctx, rel)[0] or "").find(".propose(") >= 0]
    if not producers:
        live.append("HumanGate.propose has zero producers across the consent surface "
                    "(bridge + gates + transports) — consent proposals are never created")
    if live:
        return {"ok": False, "detail": ("consent NOT enforced: " + "; ".join(live))[:500]}
    return {"ok": True, "detail": "consent armed: panel disarm removed, mcp/tools off the disarmed "
                                  "singleton, a live HumanGate.propose producer exists at dispatch"}

def check_rbac_at_dispatch(ctx):
    # S.3 FINGERPRINT (report: RBAC enforced only on one transport; `if user_session:` with no
    # else lets an unresolved session skip RBAC; default-deny missing). RED while EITHER the
    # single-transport enforcement OR the no-else bypass persists. Studio/farm posture additionally
    # requires a default-deny site. detail enumerates the missing enforcement points.
    import re, ast
    live = []
    ws_src, _ = _read_src(ctx, "python/synapse/server/websocket.py")
    hw_src, _ = _read_src(ctx, "python/synapse/server/hwebserver_adapter.py")
    mcp_src, _ = _read_src(ctx, "python/synapse/mcp/server.py")
    def _calls(src):
        return len(re.findall(r"check_permission\s*\(", src or ""))
    if _calls(ws_src) >= 1 and _calls(hw_src) == 0 and _calls(mcp_src) == 0:
        live.append("check_permission enforced ONLY on the WS transport (0 calls in "
                    "hwebserver_adapter.py + mcp/server.py) — the hweb + MCP transports dispatch ungated by role")
    if ws_src:
        try:
            tree = ast.parse(ws_src)
            for node in ast.walk(tree):
                if (isinstance(node, ast.If) and isinstance(node.test, ast.Name)
                        and node.test.id == "user_session" and not node.orelse
                        and any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                                and n.func.id == "check_permission" for n in ast.walk(node))):
                    live.append("websocket.py: `if user_session:` guards check_permission with NO "
                                "else — an unresolved session skips RBAC entirely (no default-deny)")
                    break
        except SyntaxError:
            pass  # a broken file fails other checks anyway
    posture = _read_posture()
    if posture and posture.get("mode") in ("studio", "farm"):
        deny = False
        for rel in ("python/synapse/server/websocket.py",
                    "python/synapse/server/hwebserver_adapter.py", "python/synapse/mcp/server.py"):
            src, _ = _read_src(ctx, rel)
            if src and re.search(r"default[_\s-]?den|unresolved\s+(role|session)", src, re.I):
                deny = True
                break
        if not deny:
            live.append(f"posture mode={posture['mode']} requires default-deny on an unresolved "
                        "role/session — no default-deny site found on any transport")
    if live:
        return {"ok": False, "detail": ("RBAC not at dispatch: " + "; ".join(live))[:500]}
    return {"ok": True, "detail": "RBAC enforced at dispatch on all transports; no no-else bypass; "
                                  "default-deny satisfied for posture"}

def check_memory_provenance(ctx):
    # S.4 FINGERPRINT (report: AI decisions stamped source='user' at write time; recall has no
    # recency/conflict ordering so a stale memory can outrank a fresh fact). RED while EITHER
    # defect is live; detail names them. Loop-gradable (not a critical).
    import re
    live = []
    store_src, _ = _read_src(ctx, "python/synapse/memory/store.py")
    if store_src and re.search(r"source\s*=\s*['\"]user['\"]", store_src):
        live.append("memory write path stamps source='user' (store.py) — AI-authored content "
                    "mislabeled as user provenance")
    # recall ranks by score with an id tiebreaker only — no recency term, so stale outranks fresh.
    # Match the EXACT current score-only sort literal, NOT a prefix: the natural fix inserts a
    # recency term (…(-r.score, -r.memory.created_at, r.memory.id)…) which keeps the `(-r.score`
    # prefix, so a prefix grep would stick RED after the fix. The full 2-tuple literal changes the
    # moment recency lands → the gate clears exactly when the defect is gone.
    if store_src and "results.sort(key=lambda r: (-r.score, r.memory.id))" in store_src:
        live.append("recall ranks by score only (store.py: results.sort(key=lambda r: "
                    "(-r.score, r.memory.id))) — no recency/created_at term; a stale memory can "
                    "outrank a fresher fact")
    if live:
        return {"ok": False, "detail": ("memory provenance/recall defects: " + "; ".join(live))[:500]}
    return {"ok": True, "detail": "memory write path stamps a real source (not hardcoded 'user'); "
                                  "recall ranking is recency-aware"}

def check_eval_backbone(ctx):
    # S.5 PRESENCE gate (self-improvement of the harness's OWN eval, allowed like P1/P2/U). GREEN
    # needs BOTH: this file's check_render wires the real validate_frame handler (not merely
    # size>1024), AND a fake-hou residency guard exists (a tests/ file marked
    # `# FAKE_HOU_RESIDENCY_GUARD` that asserts a single sys.modules['hou'] planter / fails on
    # collision). Until both: RED naming which is missing.
    import re
    missing = []
    checks_src, _ = _read_src(ctx, "harness/verify/checks.py")
    # isolate check_render's body so this check's OWN mention of validate_frame can't self-satisfy
    body = ""
    if checks_src:
        m = re.search(r"def check_render\(ctx\):(.*?)(?=\ndef |\Z)", checks_src, re.S)
        body = m.group(1) if m else ""
    if "validate_frame" not in body:
        missing.append("harness/verify/checks.py check_render still asserts only size>1024 — wire "
                       "the real validate_frame handler (handlers_render.py::_handle_validate_frame)")
    # The guard must live in a conftest.py — the ONE place a residency assert actually runs at
    # collection time and gates the whole suite. Scanning any tests/*.py let the S-track's own
    # test_s_track.py (which names the marker in a fixture string) spuriously satisfy this — a
    # fake-pass that would flip GREEN the instant the validate_frame leg landed, with no real guard.
    # Require the marker in a conftest.py (tests/**/conftest.py or the repo-root conftest.py).
    guard = False
    candidates = list((Path(ctx["wt"]) / "tests").rglob("conftest.py"))
    root_conftest = Path(ctx["wt"]) / "conftest.py"
    if root_conftest.is_file():
        candidates.append(root_conftest)
    for f in candidates:
        try:
            if "# FAKE_HOU_RESIDENCY_GUARD" in f.read_text(encoding="utf-8", errors="ignore"):
                guard = True
                break
        except Exception:
            continue
    if not guard:
        missing.append("no fake-hou residency guard — add a conftest.py marked "
                       "`# FAKE_HOU_RESIDENCY_GUARD` that asserts a single sys.modules['hou'] "
                       "planter at collection time (fails on collision)")
    if missing:
        return {"ok": False, "detail": ("eval backbone incomplete: " + "; ".join(missing))[:500]}
    return {"ok": True, "detail": "check_render wires validate_frame + fake-hou residency guard present"}

def check_farm_headless(ctx):
    # S.6 FINGERPRINT (report/latent: PDG-fail rollback wipes generated caches via
    # dirtyAllTasks(remove_files=True); scout skips the symbol-table version check in an external
    # process, unsafe on a mixed fleet). RED while EITHER defect is live; detail names them.
    import re
    live = []
    bridge_src, _ = _read_src(ctx, "shared/bridge.py")
    if bridge_src and "dirtyAllTasks(remove_files=True)" in bridge_src:
        live.append("shared/bridge.py calls dirtyAllTasks(remove_files=True) — PDG-fail rollback "
                    "wipes generated caches on disk (a latent farm-headless data-loss path)")
    scout_src, _ = _read_src(ctx, "python/synapse/cognitive/tools/scout.py")
    if (scout_src and re.search(r"EXPECTED_HOUDINI_VERSION\s*:\s*Optional\[str\]\s*=\s*None", scout_src)
            and "and EXPECTED_HOUDINI_VERSION and" in scout_src):
        live.append("scout.py skips the symbol-table version check when EXPECTED_HOUDINI_VERSION is "
                    "unset (default None, host-injected only) — in an external farm process the "
                    "staleness gate is bypassed (mixed-fleet phantom-wiring risk)")
    if live:
        return {"ok": False, "detail": ("farm-headless defects: " + "; ".join(live))[:500]}
    return {"ok": True, "detail": "no reachable dirtyAllTasks(remove_files=True); scout version "
                                  "check enforced in external processes"}

def check_studio_readiness_review(ctx):
    # S.R CAPSTONE: aggregate the other seven S-checks + context_review_clean, emit the verdict
    # artifact, and REFUSE to pass while any security-critical finding is live. ok:true iff the
    # critical set {posture, policy, consent, rbac} are ALL ok:true AND no aggregated check is
    # ok:false. Calls the check functions directly (global names, so tests can monkeypatch them).
    import datetime
    aggregate = {
        "posture_declared": check_posture_declared,
        "policy_single_source": check_policy_single_source,
        "consent_enforced": check_consent_enforced,
        "rbac_at_dispatch": check_rbac_at_dispatch,
        "memory_provenance": check_memory_provenance,
        "eval_backbone": check_eval_backbone,
        "farm_headless": check_farm_headless,
        "context_review_clean": check_context_review_clean,
    }
    per_check = {}
    for name, fn in aggregate.items():
        try:
            per_check[name] = fn(ctx).get("ok")
        except Exception as e:
            per_check[name] = None  # a broken sub-check is a down gate, not a silent pass
    criticals = ("posture_declared", "policy_single_source", "consent_enforced", "rbac_at_dispatch")
    criticals_green = all(per_check.get(c) is True for c in criticals)
    findings_live = [name for name, ok in per_check.items() if ok is not True]
    # READY iff every critical is green AND no aggregated check is non-green (False OR None — a
    # down/errored sub-check is NOT a pass). Basing this on findings_live (not just `is False`)
    # keeps the verdict consistent with the list we report: a None sub-check can't co-exist with READY.
    ok = criticals_green and not findings_live
    verdict = "READY" if ok else "NOT READY"
    out = {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "per_check": per_check,
        "criticals_green": criticals_green,
        "findings_live": findings_live,
        "verdict": verdict,
    }
    try:
        vp = Path(ctx["wt"]) / "harness" / "state" / "studio_readiness_verdict.json"
        vp.parent.mkdir(parents=True, exist_ok=True)
        vp.write_text(json.dumps(out, indent=2), encoding="utf-8")
    except Exception:
        pass  # a read-only fs must not crash the gate — the return value is the authority
    if ok:
        return {"ok": True, "detail": "studio-readiness verdict: READY — all criticals green, no S-check red"}
    red_crit = [c for c in criticals if per_check.get(c) is not True]
    return {"ok": False, "detail": (f"studio-readiness verdict: NOT READY — findings live: "
            f"{', '.join(findings_live) or 'none'}"
            + (f"; criticals still red: {', '.join(red_crit)}" if red_crit else ""))[:500]}


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
    "phantom_clean": check_phantom_clean,
    # U.1 — utility flywheel: network-wiring truth
    "connectivity_catalog_fresh": check_connectivity_catalog_fresh,
    "wiring_conformance": check_wiring_conformance,
    "validator_catches_miswire": check_validator_catches_miswire,
    # U.5 — utility flywheel: LOP/Solaris knowledge (context truth)
    "lop_knowledge_fresh": check_lop_knowledge_fresh,
    "lop_review_clean": check_lop_review_clean,
    "validator_lop_conformance": check_validator_lop_conformance,
    # v6 — blueprint-armed track (V.1–V.7)
    "blueprints_present": check_blueprints_present,
    "v6_skeleton_conformance": check_v6_skeleton_conformance,
    "v6_spec_bp09": check_v6_spec_bp09,
    "v6_spec_bp10": check_v6_spec_bp10,
    "v6_kb_roundtrip": check_v6_kb_roundtrip,
    "v6_tests_green": check_v6_tests_green,
    # C — context-capability track
    "context_catalog_fresh": check_context_catalog_fresh,
    "context_review_clean": check_context_review_clean,
    "context_golden_sop": check_context_golden_sop,
    "context_golden_lop": check_context_golden_lop,
    "context_golden_cop": check_context_golden_cop,
    "context_golden_top": check_context_golden_top,
    "context_golden_dop": check_context_golden_dop,
    "context_golden_mat": check_context_golden_mat,
    # S — studio-readiness hardening track
    "posture_declared": check_posture_declared,
    "policy_single_source": check_policy_single_source,
    "consent_enforced": check_consent_enforced,
    "rbac_at_dispatch": check_rbac_at_dispatch,
    "memory_provenance": check_memory_provenance,
    "eval_backbone": check_eval_backbone,
    "farm_headless": check_farm_headless,
    "studio_readiness_review": check_studio_readiness_review,
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--worktree", required=True)
    ap.add_argument("--hython", default="")
    ap.add_argument("--mode", default="A")
    a = ap.parse_args()

    # Worktree-shadowing guard (flywheel U.1 meta-finding): a dev-machine
    # editable install (__editable__.synapse-*.pth) resolves `synapse` to the
    # MAIN checkout — for this process AND bare children — so a worktree gate
    # can green-light code it never imported. Pin the WORKTREE's package first
    # for both resolution paths.
    _wt_py = str(Path(a.worktree).resolve() / "python")
    sys.path.insert(0, _wt_py)
    os.environ["PYTHONPATH"] = _wt_py + os.pathsep + os.environ.get("PYTHONPATH", "")

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
