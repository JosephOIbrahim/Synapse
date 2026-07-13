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


# ---------- D — diagnostic-truth track (dormant until D.0 ratified) ----------
# Frozen contract: harness/notes/spec-D-diagnostic-truth.md (intake per
# harness/notes/SYNAPSE_ODFORCE_HARNESS.md). What the scene observably DOES when poked —
# dirty-propagation, recook triggers, time-dependence, callback runtime errors — captured as a
# probed, version-stamped catalog. Every check below is HONEST-FALSE until its mile's artifact
# exists: the track arms only when a human flips D.0 ratified:true (COOK_RATIFIED trigger in
# run.ts), and D.3+ only when the committed catalog exists (COOK trigger). H22 note: artifact
# filenames are resolved MAJOR-AGNOSTICALLY below, so the H22 drop needs zero check edits —
# a 21-stamped catalog under live H22 hython goes stale-loud, forcing the re-probe.

def _resolve_cook_note(ctx, stem):
    """Resolve harness/notes/<stem>_<version>.json major-agnostically.

    Covers both naming precedents: major-pinned catalogs (cook_truth_21.json, the
    context_capability_21.json pattern) and full-build authority files
    (verified_cook_api_21.0.671.json, the verified_usdlux_encodings pattern).
    With hython: the live build picks the candidate (same major) — none for the live
    major is an honest miss. Without: single candidate wins; multiple → highest
    version, noted. Returns (path_or_None, live_build_or_None, note_str)."""
    import re as _re
    notes = Path(ctx["wt"]) / "harness" / "notes"
    cands = []
    if notes.is_dir():
        for f in notes.iterdir():
            # re.ASCII: \d must mean ASCII digits only — unicode-digit filenames must not
            # resolve here while run.ts's JS regex (ASCII \d) rejects them (TS/py lockstep).
            m = _re.fullmatch(rf"{_re.escape(stem)}_(\d+(?:\.\d+)*)\.json", f.name, _re.ASCII)
            if m:
                cands.append((tuple(int(p) for p in m.group(1).split(".")), f))
    live = None
    if ctx.get("hython"):
        rc, out, err = hython(ctx["hython"], "import hou\nprint('BUILD', hou.applicationVersionString())", ctx["wt"])
        live = next((l.split(" ", 1)[1].strip() for l in out.splitlines() if l.startswith("BUILD ")), None)
        if live is None:
            # A SET-but-FAILED hython (license crash, mute build) is a hard miss, never
            # leniency: degrading to the benign HYTHON-unset path would let a stale artifact
            # green under a broken H22 hython with a lying detail (crucible HIGH, 2026-07-07).
            return None, None, (f"hython ran but reported no BUILD (rc={rc}): "
                                f"{(err or out).strip()[:80]} — staleness UNVERIFIABLE")
    if not cands:
        return None, live, "no artifact"
    if live:
        major = live.split(".")[0]
        hit = next((f for v, f in sorted(cands, reverse=True) if str(v[0]) == major), None)
        return hit, live, ("" if hit else f"no {stem} artifact for live major {major}")
    if len(cands) > 1:
        v, f = max(cands)
        return f, None, f"multiple majors present; picked {f.name}; live disambiguation skipped — HYTHON unset"
    return cands[0][1], None, ""

def check_cook_api_confirmed(ctx):
    # Mile 1 (D.1): every hou.* symbol on D's critical path dir()-confirmed against live hython.
    # Spec-frozen schema cook_api/v1: {schema, houdini_version, confirmed:[], absent:[], blake2b}.
    # DESIGN LAW: this file is cook_api_confirmed's OWN check-side authority — it is NEVER
    # spliced into h21_symbol_table.json (that table's blake2b + dir()-membership invariant are
    # untouchable; depth-1 hou.* absences are already enforced free by phantom_clean). This file
    # carries the deeper symbols (hou.Node.<m>, event enums) phantom_clean structurally cannot judge.
    import hashlib
    p, live, note = _resolve_cook_note(ctx, "verified_cook_api")
    if p is None:
        return {"ok": False, "detail": f"{note or 'harness/notes/verified_cook_api_<build>.json missing'} — "
                                       "run D.1 (after D.0 ratification); commit the artifact — worktrees fork from HEAD"}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("schema") != "cook_api/v1":
            return {"ok": False, "detail": f"schema={data.get('schema')} != cook_api/v1"}
        confirmed, absent = data.get("confirmed") or [], data.get("absent") or []
        if not confirmed:
            return {"ok": False, "detail": "empty confirmed list — probe ran but confirmed nothing (invalid)"}
        if set(confirmed) & set(absent):
            return {"ok": False, "detail": f"confirmed/absent overlap: {sorted(set(confirmed) & set(absent))[:5]}"}
        digest = hashlib.blake2b(json.dumps({"confirmed": confirmed, "absent": absent},
                                            sort_keys=True, ensure_ascii=False).encode("utf-8"),
                                 digest_size=16).hexdigest()
        if digest != data.get("blake2b"):
            return {"ok": False, "detail": "cook-api file blake2b mismatch (corrupt/hand-edited)"}
        stamp = data.get("houdini_version", "")
    except Exception as e:
        return {"ok": False, "detail": f"cook-api file unreadable: {str(e)[:300]}"}
    if live and live != stamp:
        return {"ok": False, "detail": f"stamp {stamp} != live build {live} — STALE; re-run the D.1 probe on this build"}
    return {"ok": True, "detail": f"cook API confirmed ({len(confirmed)} confirmed / {len(absent)} quarantined, "
                                  f"stamp {stamp}{'' if live else '; live comparison skipped — HYTHON unset'})"}

def check_cook_truth_fresh(ctx):
    # Mile 2 (D.2): the perturbation catalog — cook_truth/v1 {schema, houdini_version, blake2b,
    # trials:[...]} (digest over `trials`; other keys sit outside by design, the
    # context_capability pattern). This committed file is the COOK arming trigger for D.3+.
    import hashlib
    p, live, note = _resolve_cook_note(ctx, "cook_truth")
    if p is None:
        return {"ok": False, "detail": f"{note or 'harness/notes/cook_truth_<major>.json missing'} — "
                                       "run D.2 (after D.0 ratification); commit the catalog — worktrees fork from HEAD"}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("schema") != "cook_truth/v1":
            return {"ok": False, "detail": f"schema={data.get('schema')} != cook_truth/v1"}
        digest = hashlib.blake2b(json.dumps(data.get("trials", []), sort_keys=True, ensure_ascii=False).encode("utf-8"),
                                 digest_size=16).hexdigest()
        if digest != data.get("blake2b"):
            return {"ok": False, "detail": "cook-truth catalog blake2b mismatch (corrupt/hand-edited)"}
        stamp = data.get("houdini_version", "")
    except Exception as e:
        return {"ok": False, "detail": f"cook-truth catalog unreadable: {str(e)[:300]}"}
    if live and live != stamp:
        return {"ok": False, "detail": f"catalog stamp {stamp} != live build {live} — STALE; "
                                       "regenerate via host/introspect_cook_truth.py"}
    extra = f"; {note}" if note else ("" if live else "; live-build comparison skipped — HYTHON unset")
    return {"ok": True, "detail": f"cook-truth catalog sound (stamp {stamp}{extra})"}

def check_cook_review_clean(ctx):
    # Mile 3 (D.3): the review sweep — scripts/flywheel_review_cook.py sweeps SYNAPSE's own
    # emitters + the explainer's claims against the catalog; a claim the catalog can't back is
    # a finding, not a footnote. The sweep only REPORTS; THIS check judges summary.critical
    # (the flywheel_review_context pattern). Dormant honest-false until D.3 ships the script.
    if not (Path(ctx["wt"]) / "scripts" / "flywheel_review_cook.py").is_file():
        return {"ok": False, "detail": "scripts/flywheel_review_cook.py missing — D.3 ships the cook review sweep"}
    rc, out, err = sh([sys.executable, "scripts/flywheel_review_cook.py"], cwd=ctx["wt"], env=_wt_env(ctx))
    p = Path(ctx["wt"]) / ".claude/flywheel_cook_findings.json"
    if not p.exists():
        return {"ok": False, "detail": (out or err).strip()[:400] or "cook review produced no findings file"}
    try:
        crit = json.loads(p.read_text(encoding="utf-8"))["summary"]["critical"]
    except Exception as e:
        return {"ok": False, "detail": f"findings unreadable: {str(e)[:200]}"}
    head = (out or err).strip().splitlines()
    return {"ok": rc == 0 and crit == 0,
            "detail": f"rc={rc} critical={crit}; {head[0][:300] if head else ''}"}

def _cook_golden(ctx, name):
    # D.3+ goldens: one frozen perturbation trial per context must reproduce its CATALOGED
    # dirty-set exactly — deterministic, render-free (spec §3; renders never golden). Baseline =
    # the catalog at merge-base(master, HEAD) — the human-promoted line (suite_baseline's anchor,
    # deliberately harder than _context_golden's HEAD read: a sprint that refreshes the cook
    # catalog in-tree must not golden against its own tip). Commandment 7: a golden that starts
    # failing is a bug to fix forward, never an assertion to soften.
    if not ctx["hython"]:
        return {"ok": False, "detail": "HYTHON unset — a golden that cannot run is not verified"}
    probe = Path(ctx["wt"]) / "host" / "introspect_cook_truth.py"
    if not probe.is_file():
        return {"ok": False, "detail": "host/introspect_cook_truth.py missing — D.2 ships the cook-truth probe"}
    live_p, live, note = _resolve_cook_note(ctx, "cook_truth")
    if live_p is None:
        return {"ok": False, "detail": f"no cook_truth catalog in tree ({note}) — run D.2 first"[:500]}
    mb_rc, mb_out, _ = sh(["git", "merge-base", "master", "HEAD"], cwd=ctx["wt"])
    if mb_rc != 0 or not mb_out.strip():
        # honest red, never a self-tip fallback: anchoring at HEAD would let a sprint golden
        # against its own refreshed catalog (the exact exploit the merge-base anchor kills).
        return {"ok": False, "detail": "cannot anchor the golden baseline — master ref unresolvable; "
                                       "fetch/create master before trusting goldens"}
    anchor = mb_out.strip()
    rc_b, cat_raw, _ = sh(["git", "show", f"{anchor}:harness/notes/{live_p.name}"], cwd=ctx["wt"])
    if rc_b != 0 or not cat_raw.strip():
        return {"ok": False, "detail": f"no committed {live_p.name} at the ratchet anchor — commit/merge the catalog first "
                                       "(the golden baseline is the MERGED catalog, not this sprint's refresh)"}
    try:
        committed = [t for t in json.loads(cat_raw).get("trials", []) if t.get("context") == name]
    except Exception as e:
        return {"ok": False, "detail": f"committed catalog unreadable: {str(e)[:200]}"}
    if not committed:
        return {"ok": False, "detail": f"committed catalog has no '{name}' trials — regenerate via D.2"}
    artifact = f".claude/cook_probe_{name}.json"
    p = Path(ctx["wt"]) / artifact
    p.unlink(missing_ok=True)  # a stale artifact surviving a failed probe run must not fake a verdict
    rc, out, err = sh([ctx["hython"], "host/introspect_cook_truth.py",
                       "--context", name, "--out", artifact], cwd=ctx["wt"])
    if not p.exists():
        # probe contract: rc 0 iff the artifact was written — judge the FILE, never stdout
        # (hython banners pollute it); the tail is only failure evidence.
        return {"ok": False, "detail": f"probe wrote no artifact (rc={rc}): {(err or out).strip()[-300:]}"}
    try:
        observed = {(t.get("graph_fingerprint"), t.get("perturbation")): sorted(t.get("observed_dirty") or [])
                    for t in json.loads(p.read_text(encoding="utf-8")).get("trials", [])
                    if t.get("context") == name}
    except Exception as e:
        return {"ok": False, "detail": f"probe artifact unreadable/malformed for '{name}': {str(e)[:250]}"}
    for t in committed:
        key = (t.get("graph_fingerprint"), t.get("perturbation"))
        want = sorted(t.get("observed_dirty") or [])
        got = observed.get(key)
        if got is None:
            return {"ok": False, "detail": f"golden trial {key} not reproduced by the probe (missing from artifact)"}
        if got != want:
            return {"ok": False, "detail": (f"dirty-set divergence on {key}: cataloged {want[:4]}… vs live {got[:4]}… — "
                                            "fix forward (Commandment 7), never soften")[:500]}
    return {"ok": True, "detail": f"'{name}' golden reproduces all {len(committed)} cataloged trial(s) exactly"}

def check_cook_golden_sop(ctx):
    return _cook_golden(ctx, "sop")

def check_cook_golden_lop(ctx):
    return _cook_golden(ctx, "lop")

def check_cook_golden_cop(ctx):
    return _cook_golden(ctx, "cop")

def check_cook_golden_dop(ctx):
    return _cook_golden(ctx, "dop")

def check_tops_path_untouched(ctx):
    # Structural quarantine (spec: the TOPs dirty/cook surface is SHIPPED — D generalizes the
    # pattern WITHOUT touching the path; hou.pdg.* stays dead). Diff guard anchored at
    # merge-base(master, HEAD) — the human-promoted line — plus untracked adds.
    guard_dir = "python/synapse/server/handlers_tops/"
    mb_rc, mb_out, _ = sh(["git", "merge-base", "master", "HEAD"], cwd=ctx["wt"])
    if mb_rc != 0 or not mb_out.strip():
        # honest red, never a self-tip fallback: a HEAD anchor would blind the quarantine to
        # anything the sprint already committed.
        return {"ok": False, "detail": "cannot anchor the quarantine diff — master ref unresolvable; "
                                       "fetch/create master before trusting this guard"}
    anchor = mb_out.strip()
    rc_d, diff_out, err_d = sh(["git", "diff", "--name-only", anchor, "--", guard_dir], cwd=ctx["wt"])
    if rc_d != 0:
        return {"ok": False, "detail": f"diff guard could not run: {(err_d or diff_out).strip()[:200]}"}
    rc_u, untracked, _ = sh(["git", "ls-files", "--others", "--exclude-standard", "--", guard_dir], cwd=ctx["wt"])
    touched = [l for l in (diff_out + "\n" + (untracked if rc_u == 0 else "")).splitlines() if l.strip()]
    if touched:
        return {"ok": False, "detail": f"TOPs path touched ({len(touched)} file(s)): {', '.join(touched[:4])} — "
                                       "the shipped TOPs surface is quarantined; D generalizes the pattern elsewhere"}
    return {"ok": True, "detail": "handlers_tops/ untouched vs the promoted line"}


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
    # FIX_IS_REAL_PROBE: tests/test_residency_guard_fires.py::test_residency_guard_raises_on_rogue_planter
    #   Behavioral proof the residency guard actually FIRES. A PRESENCE gate greens on the marker
    #   string alone; this probe reddens the instant conftest's pytest_collection_finish hook is
    #   gutted (see the PRESENCE-gate standard pinned by tests/test_s_track.py).
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
    # ---- posture-aware verdict ----------------------------------------------------------------
    # The security criticals fingerprint REAL code defects (ungated execute_python, auto-approve
    # consent, no-RBAC) and stay individually RED regardless of posture — the defect is present.
    # What the declared posture changes is whether those defects BLOCK readiness. Under a declared
    # solo-localhost posture they are the repo's documented, test-pinned single-user trade-offs:
    # visible and named, but not blocking — and they snap straight back to HARD blockers the moment
    # the posture is studio/farm/undeclared. This keeps the gates truthful and the verdict honest
    # for the posture actually declared (never a rubber stamp: accepted != fixed, and it is listed).
    posture = _read_posture()
    mode = (posture or {}).get("mode")
    security_criticals = ("policy_single_source", "consent_enforced", "rbac_at_dispatch")
    findings_live = [name for name, ok in per_check.items() if ok is not True]

    if mode == "solo":
        # What blocks EVEN a single artist on localhost: the posture must be declared, and the
        # data-safety (PDG rollback) + catalog-integrity gates must hold. The security criticals
        # are accepted trade-offs; the memory/eval partials are open hygiene (non-blocking solo).
        solo_hard = ("posture_declared", "farm_headless", "context_review_clean")
        accepted = [c for c in security_criticals if per_check.get(c) is not True]
        hygiene = [c for c in ("memory_provenance", "eval_backbone") if per_check.get(c) is not True]
        blockers = [c for c in solo_hard if per_check.get(c) is not True]
        criticals_green = per_check.get("posture_declared") is True  # posture is the one hard req solo has
        ok = not blockers
        verdict = "READY (solo posture)" if ok else "NOT READY (solo posture)"
        detail_extra = (f"accepted solo trade-offs (WOULD block studio): {', '.join(accepted) or 'none'}; "
                        f"open hygiene (non-blocking): {', '.join(hygiene) or 'none'}")
        out_posture = {"posture": "solo", "accepted_under_posture": accepted, "open_hygiene": hygiene}
    else:
        # studio / farm / undeclared → strict: all 4 criticals green AND no aggregated gate red.
        criticals = ("posture_declared",) + security_criticals
        criticals_green = all(per_check.get(c) is True for c in criticals)
        blockers = list(findings_live)
        ok = criticals_green and not blockers
        verdict = "READY" if ok else "NOT READY"
        red_crit = [c for c in criticals if per_check.get(c) is not True]
        detail_extra = (f"criticals still red: {', '.join(red_crit)}" if red_crit else "criticals green")
        out_posture = {"posture": mode or "undeclared"}

    out = {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "per_check": per_check,
        "criticals_green": criticals_green,
        "findings_live": findings_live,
        "blockers": blockers,
        "verdict": verdict,
        **out_posture,
    }
    try:
        vp = Path(ctx["wt"]) / "harness" / "state" / "studio_readiness_verdict.json"
        vp.parent.mkdir(parents=True, exist_ok=True)
        vp.write_text(json.dumps(out, indent=2), encoding="utf-8")
    except Exception:
        pass  # a read-only fs must not crash the gate — the return value is the authority
    return {"ok": ok, "detail": (f"studio-readiness verdict: {verdict} — {detail_extra}; "
            f"live gates: {', '.join(findings_live) or 'none'}")[:500]}


# ---------- R — release-readiness (H22 RC) track (all stock python, no hython) ----------
# Each R-check is a DURABLE REGRESSION GATE around a finding of
# docs/reviews/synapse-h22-readiness-2026-07-10.md (external CTO review; every claim
# adversarially verified against the live tree 2026-07-10): RED while the finding's
# fingerprint is live in the product source, GREEN only when the review's required fix lands
# — then green forever, so a release-blocking defect can never silently regress. Fingerprints
# are static grep/regex over the worktree (ctx['wt']); none needs hython. The capstone
# computes the release LABEL: STABLE-READY only when every machine gate is green AND every
# live-Houdini gate has a human receipt (harness/state/release_receipts.json — human-authored
# runtime state, peer of posture.json). Contract: harness/notes/spec-R-release-readiness.md.
# These checks READ product code only; the fixes are the armed loop's / human's sprints.

def _receipts_path():
    # Release receipts are a MACHINE-LEVEL human declaration (peer of posture.json), read
    # from the MAIN repo, never ctx['wt'] — a live-Houdini drill attests the machine, not a
    # worktree. Module-level so tests can monkeypatch the seam to a tmp file.
    return Path(__file__).resolve().parents[1].parent / "harness" / "state" / "release_receipts.json"

def _drop_path():
    # drop.json (the Mode-B trigger) — main repo, module-level seam for tests.
    return Path(__file__).resolve().parents[1].parent / "harness" / "state" / "drop.json"

def _read_receipts():
    """Parsed receipts dict, or {} if absent/malformed. Never raises — a missing receipt just
    means that live gate is PENDING (never faked green)."""
    p = _receipts_path()
    try:
        if not p.exists():
            return {}
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def check_mutation_fail_closed(ctx):
    # R.1 FINGERPRINT (review P0.2 — "the most important code-level finding"): mutations fail
    # OPEN when the integrity bridge is unavailable. THREE sites (the sweep found one more than
    # the review): the twin `except ImportError → handler.handle` fallbacks in
    # panel/tool_executor.py + mcp/tools.py, and bridge_adapter's `bridge is None → direct
    # dispatch` (the LIVE path in practice: _BRIDGE_AVAILABLE=False silently disarms every
    # panel + /mcp mutation). The mcp/server.py lookalike is the read-only resources path
    # (its ImportError is hdefereval) — deliberately NOT matched.
    import re
    live = []
    imp_fall = re.compile(r"except ImportError:\s*\n\s*response = handler\.handle\(command\)")
    for rel, label in (("python/synapse/panel/tool_executor.py", "panel ToolExecutor"),
                       ("python/synapse/mcp/tools.py", "/mcp dispatch_tool")):
        src, _ = _read_src(ctx, rel)
        if src and imp_fall.search(src):
            live.append(f"{rel}: {label} falls back to direct handler.handle on bridge_adapter "
                        "ImportError — mutating tools dispatch with no bridge, no receipt")
    ba_src, _ = _read_src(ctx, "python/synapse/panel/bridge_adapter.py")
    # bounded lookahead: matches execute_through_bridge's None-branch (comment + return within
    # 80 chars), never get_session_report's `if bridge is None: return None` nor the
    # bridge-routed handler.handle further down.
    if ba_src and re.search(r"if bridge is None:[\s\S]{0,80}?return handler\.handle\(command\)", ba_src):
        live.append("python/synapse/panel/bridge_adapter.py: execute_through_bridge dispatches "
                    "direct when get_bridge() is None — the live fail-open path")
    if live:
        return {"ok": False, "detail": ("mutations fail OPEN: " + "; ".join(live) +
                " — fix: fail closed for non-read-only tools, classification from an "
                "import-independent source (e.g. handlers._READ_ONLY_COMMANDS)")[:500]}
    return {"ok": True, "detail": "no fail-open mutation path: ImportError fallbacks + the "
                                  "bridge-None direct dispatch are gone"}

def check_runtime_owns_heartbeat(ctx):
    # R.2 (review P0.3): the 1s freeze beat is a QTimer parented to the SynapsePanel widget —
    # close the panel, lose the beat; WORSE (sweep refinement): the Watchdog monitor thread
    # survives and reads the dead beat source as a freeze → false-positive breaker + emergency
    # halt on a healthy session ~35s after panel close. Two legs so a lazy fix can't green it:
    # leg 1 fires while the panel owns the beat; leg 2 fires if the panel timer is gone but NO
    # process-lifetime owner replaced it (deleting protection is not relocating it).
    import re
    panel_src, _ = _read_src(ctx, "python/synapse/panel/synapse_panel.py")
    if panel_src and re.search(r"self\._freeze_timer = QTimer\(self\)", panel_src):
        return {"ok": False, "detail": (
            "panel owns the freeze beat (synapse_panel.py: self._freeze_timer = QTimer(self)) — "
            "the beat dies with the widget AND the surviving Watchdog false-positives a freeze "
            "after panel close. Move the beat to a process-lifetime owner under "
            "python/synapse/server/ marked `# RUNTIME_BEAT_SOURCE` (or def ensure_beat_started) "
            "that also handles deliberate beat-source detach")[:500]}
    server_dir = Path(ctx["wt"]) / "python" / "synapse" / "server"
    owner = False
    if server_dir.is_dir():
        for f in server_dir.rglob("*.py"):
            try:
                src = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if "# RUNTIME_BEAT_SOURCE" in src or "def ensure_beat_started" in src:
                owner = True
                break
    if not owner:
        return {"ok": False, "detail": (
            "panel-parented beat timer is gone but NO process-lifetime beat owner exists under "
            "python/synapse/server/ (`# RUNTIME_BEAT_SOURCE` marker or def ensure_beat_started) "
            "— freeze protection was removed, not relocated")[:500]}
    return {"ok": True, "detail": "freeze beat owned by a process-lifetime service "
                                  "(RUNTIME_BEAT_SOURCE under server/); panel no longer "
                                  "constructs the beat timer"}

def check_hot_reload_gated(ctx):
    # R.3 (review P0.4): both .pypanel loaders purge sys.modules['synapse.*'] UNCONDITIONALLY
    # at module scope on every panel creation — production hot-reload: duplicate bridges, stale
    # callbacks, split singletons. RED per loader while the column-0 purge is live, or while a
    # purge exists with no SYNAPSE_DEV_HOT_RELOAD gate anywhere in the file (catches re-nesting
    # under an always-true block). A loader that no longer ships auto-greens its leg; deleting
    # the purge outright is also a valid fix (gate-or-delete, never unconditional).
    import re
    live = []
    for rel in ("houdini/python_panels/synapse_panel.pypanel",
                "python/synapse/panel/synapse_chat.pypanel"):
        src, _ = _read_src(ctx, rel)
        if src is None:
            continue  # loader removed entirely — leg green
        col0 = (re.search(r'^for \w+ in sorted\(k for k in sys\.modules if k\.startswith\("synapse\."\)\):',
                          src, re.M)
                or re.search(r'^sys\.modules\.pop\("synapse", None\)', src, re.M))
        ungated = "del sys.modules[" in src and "SYNAPSE_DEV_HOT_RELOAD" not in src
        if col0:
            live.append(f"{rel}: unconditional column-0 sys.modules purge")
        elif ungated:
            live.append(f"{rel}: sys.modules purge present with no SYNAPSE_DEV_HOT_RELOAD gate")
    if live:
        return {"ok": False, "detail": ("production hot-reload live: " + "; ".join(live) +
                ' — wrap the purge in `if os.environ.get("SYNAPSE_DEV_HOT_RELOAD") == "1":` '
                "or delete it")[:500]}
    return {"ok": True, "detail": "module purge gated behind SYNAPSE_DEV_HOT_RELOAD (or removed) "
                                  "in both loaders"}

def check_deps_isolated(ctx):
    # R.4 (review P0.1 — the H22 boot cliff): _vendor activates ONLY on cp311+win
    # (__init__.py strict equality); on H22's likely cp312/cp313 a clean install's brain dies
    # at daemon.py's manual-sidecar RuntimeError. Direction is DECIDED — gate-0.1 → sidecar
    # (docs/studio/DROP_DAY.md, 2026-07-10), built first post-release; the drop-window minimum
    # is versioned vendor roots from sys.version_info. GREEN on EITHER mechanism: the strict
    # equality replaced (versioned roots), or a real sidecar implementation under host/
    # (def/class lines only — the daemon's RuntimeError MESSAGE says "sidecar" and must never
    # satisfy this).
    import re
    init_src, _ = _read_src(ctx, "python/synapse/__init__.py")
    strict = bool(init_src and re.search(r"_synapse_sys\.version_info\[:2\] == \(3, 11\)", init_src))
    if not strict:
        return {"ok": True, "detail": "single-ABI strict gate gone from __init__.py — vendor root "
                                      "is version-derived (or vendoring retired for the sidecar)"}
    host_dir = Path(ctx["wt"]) / "python" / "synapse" / "host"
    sidecar = False
    if host_dir.is_dir():
        pat = re.compile(r"^\s*(def \w*sidecar\w*|class \w*Sidecar\w*)", re.M)
        for f in host_dir.rglob("*.py"):
            try:
                if pat.search(f.read_text(encoding="utf-8", errors="ignore")):
                    sidecar = True
                    break
            except Exception:
                continue
    if sidecar:
        return {"ok": True, "detail": "sidecar implementation present under host/ (gate-0.1's "
                                      "decided direction) — the cp311 strict gate is no longer "
                                      "the boot cliff"}
    return {"ok": False, "detail": (
        "H22 boot cliff live: _vendor activates only on Python 3.11+win (__init__.py "
        "`version_info[:2] == (3, 11)`) and no sidecar exists under host/ — a clean "
        "cp312/cp313 install dies at daemon.py's manual-sidecar RuntimeError. Fix: versioned "
        "vendor roots (wheel_cache cp312/cp313 payloads are pre-staged) or the decided "
        "sidecar")[:500]}

def check_installer_host_targeted(ctx):
    # R.5 PRESENCE gate (review P0.5): auto-detect only sees pref dirs that already exist — a
    # fresh H22 pref dir (created on first launch) is silently omitted — and nothing verifies
    # the written package from the host's side. GREEN needs BOTH: a --houdini-exe argument
    # (derive pref dir/hython from the executable, mkdir a missing pref dir) AND a post-install
    # verification surface (def verify_install/_host or an add_argument("--verify") line).
    # FIX_IS_REAL_PROBE: none (R.5 unbuilt — the fixing sprint adds a behavioral installer
    # test per spec §4; presence here, proof there once host-targeting lands)
    import re
    src, p = _read_src(ctx, "scripts/install_synapse_package.py")
    if src is None:
        return {"ok": False, "detail": f"installer missing: {p}"}
    missing = []
    if "--houdini-exe" not in src:
        missing.append("no --houdini-exe argument (derive pref dir + hython from the "
                       "executable; mkdir a fresh H22 pref dir instead of omitting it)")
    if not (re.search(r"def verify_(install|host)", src) or 'add_argument("--verify"' in src):
        missing.append("no post-install host verification (package parses, SYNAPSE_ROOT "
                       "correct, synapse importable, pypanel + shelf discoverable)")
    if missing:
        return {"ok": False, "detail": ("installer not host-targeted: " + "; ".join(missing))[:500]}
    return {"ok": True, "detail": "installer host-targeted: --houdini-exe + post-install "
                                  "verification present"}

def check_ci_covers_shipping_surface(ctx):
    # R.6 (review P0.6): CI runs ubuntu+macos only — the shipping platform (Windows, the ONLY
    # place the vendored cp311 binaries can even load) is never exercised; the vendored wheel
    # is asserted by FILENAME, never imported. GREEN needs a windows lane AND a vendored-load
    # probe (the workflow importing pydantic_core, not listing it). Host lanes (hython /
    # graphical smoke) need licensed runners — those are G6 receipts, deliberately not gated
    # here.
    src, p = _read_src(ctx, ".github/workflows/ci.yml")
    if src is None:
        return {"ok": False, "detail": f"CI workflow missing: {p}"}
    missing = []
    if "windows-latest" not in src:
        missing.append("no windows-latest lane (matrix is POSIX-only; the bundled native "
                       "wheels are win_amd64 and never load in CI)")
    if "pydantic_core" not in src:
        missing.append("no vendored-load probe (a Windows step must IMPORT the vendored "
                       "pydantic_core, not just assert the filename)")
    if missing:
        return {"ok": False, "detail": ("CI misses the shipping surface: " + "; ".join(missing))[:500]}
    return {"ok": True, "detail": "CI covers the shipping surface: windows lane + vendored-load probe"}

def check_shelf_current(ctx):
    # R.7 PRESENCE gate (review P1-shelf): the shelf clipboard helper imports PySide2 ONLY —
    # H21 ships PySide6 only, so clipboard silently returns False on the target platform — and
    # the missing-panel message names the wrong installer (`python install.py`). The
    # repo-standard fix keeps PySide2 as a FALLBACK, so the PySide2 literal survives — gate on
    # PySide6 presence + current-installer presence, never on PySide2 absence.
    # FIX_IS_REAL_PROBE: none (R.7 unbuilt — the fixing sprint adds a behavioral shelf test
    # proving PySide6-first clipboard + current installer message; presence here, proof there)
    src, p = _read_src(ctx, "houdini/scripts/python/synapse_shelf.py")
    if src is None:
        return {"ok": False, "detail": f"shelf helper missing: {p}"}
    missing = []
    if "from PySide6" not in src:
        missing.append("clipboard path never tries PySide6 (H21 ships PySide6 only — copy "
                       "always fails); add the PySide6-first fallback")
    if "install_synapse_package.py" not in src:
        missing.append("missing-panel message still says `python install.py` — the documented "
                       "installer is scripts/install_synapse_package.py")
    if missing:
        return {"ok": False, "detail": ("shelf stale: " + "; ".join(missing))[:500]}
    return {"ok": True, "detail": "shelf current: PySide6-first clipboard + current installer message"}

def check_tool_metadata_single_source(ctx):
    # R.8 FINGERPRINT (review P1-metadata; NOT covered by S.1 — check_policy_single_source
    # fingerprints shared/bridge.py's gate fallback and its taxonomy list omits
    # bridge_adapter): an UNKNOWN tool name silently classifies as "set_parameter" → INFORM,
    # the weakest gate — unknown capability executing with mere notification. Repo-unique
    # literal; its removal (fail-closed unknown handling / policy-source import) is the fix.
    src, _ = _read_src(ctx, "python/synapse/panel/bridge_adapter.py")
    if src and '_TOOL_TO_OPERATION.get(tool_name, "set_parameter")' in src:
        return {"ok": False, "detail": (
            "unknown tools default to set_parameter→INFORM (bridge_adapter.py "
            '`_TOOL_TO_OPERATION.get(tool_name, "set_parameter")`) — unknown capability must '
            "fail closed (refuse, or classify REVIEW-or-higher) and metadata should live in "
            "the single policy source (S.1)")[:500]}
    return {"ok": True, "detail": "no silent set_parameter default for unknown tools in bridge_adapter"}

def check_process_bridge_armed(ctx):
    # R.9a FINGERPRINT (review P1-consent, sweep refinement): the consent disarm exists at TWO
    # sites and S.2 sees only bridge_adapter's. get_process_bridge() constructs the
    # process-wide singleton gate-less with a blanket auto-approve lambda — deleting the panel
    # disarm alone would flip S.2 green while every consumer still shares a bridge born
    # disarmed. The `bridge.` prefix keeps the pattern off self._gate assignments.
    import re
    src, _ = _read_src(ctx, "shared/bridge.py")
    live = []
    if src and re.search(r"bridge\._gate = None", src):
        live.append("get_process_bridge constructs gate-less (`bridge._gate = None`)")
    if src and "consent_callback=lambda op: True" in src:
        live.append("blanket auto-approve baked in (`consent_callback=lambda op: True`)")
    if live:
        return {"ok": False, "detail": ("process bridge born disarmed: " + "; ".join(live) +
                " — arm construction with a real (non-blocking) consent path; solo "
                "auto-approve stays a posture choice, not a hardcode")[:500]}
    return {"ok": True, "detail": "process bridge constructed armed (no _gate=None / blanket lambda)"}

def check_auth_fail_closed(ctx):
    # R.9b FINGERPRINT (review P1-auth; ENTIRELY outside existing gates — no check references
    # auth.py or websocket auth): no key ⇒ every token passes; empty Origin ⇒ allow; the
    # handshake itself is skipped unless a key already exists. Under a solo posture these are
    # accepted trade-offs (the capstone lists, never hides them); under studio/farm they block.
    import re
    live = []
    auth_src, _ = _read_src(ctx, "python/synapse/server/auth.py")
    if auth_src and re.search(r"if expected_key is None:\s*\n\s*return True", auth_src):
        live.append("auth.py: no key ⇒ authenticate() returns True for every token")
    if auth_src and re.search(r"if not origin:\s*\n\s*return True", auth_src):
        live.append("auth.py: empty Origin unconditionally accepted")
    ws_src, _ = _read_src(ctx, "python/synapse/server/websocket.py")
    if ws_src and "auth_required = auth_key is not None" in ws_src:
        live.append("websocket.py: the auth handshake only runs when a key already exists")
    if live:
        return {"ok": False, "detail": ("auth defaults fail OPEN: " + "; ".join(live) +
                " — fail closed for mutating endpoints unless an explicit insecure-local flag "
                "is set")[:500]}
    return {"ok": True, "detail": "auth fail-closed: no token-always-passes default, no "
                                  "unconditional empty-Origin allow, handshake unconditional"}

def check_packaging_self_contained(ctx):
    # R.10 FINGERPRINT (review P1-packaging; the review's own scope: fix AFTER H22
    # stabilization — open hygiene, never blocks). Imports depend on checkout structure:
    # shared/ lives at the repo root, so both package-JSON writers carry a dual-path
    # PYTHONPATH and packaged product code imports top-level `shared` (plus an import-time
    # sys.path climb in integrity_envelope.py the review missed). The two-element PYTHONPATH
    # sequence never matches the SYNAPSE_ROOT env-var definition block.
    import re
    live = []
    pkg_src, _ = _read_src(ctx, "packages/synapse.json")
    if pkg_src and re.search(r'"\$SYNAPSE_ROOT/python",\s*"\$SYNAPSE_ROOT"', pkg_src):
        live.append("packages/synapse.json PYTHONPATH carries the bare repo root "
                    "(shared/ outside the package)")
    env_src, _ = _read_src(ctx, "python/synapse/server/integrity_envelope.py")
    if env_src and "from shared.bridge import IntegrityBlock" in env_src:
        live.append("integrity_envelope.py imports top-level `shared` (repo-root coupled)")
    if live:
        return {"ok": False, "detail": ("packaging repo-root coupled: " + "; ".join(live) +
                " — move shared/ into the installable package post-stabilization (the "
                "review's own sequencing)")[:500]}
    return {"ok": True, "detail": "packaging self-contained: no bare repo-root PYTHONPATH, no "
                                  "top-level shared import in packaged code"}

_RECEIPT_KEYS = ("g1_clean_install", "g5_lifecycle", "g6_core_smoke",
                 "g7_reversibility", "g8_restart", "g9_rollback")

def check_release_readiness_review(ctx):
    # R.R CAPSTONE — the review's "binary release gates" made executable. Aggregates the
    # other 11 R-checks + the human receipts + posture + drop state into the release LABEL:
    # STABLE-READY only when every machine gate is green, security legs are green-or-
    # posture-accepted, every live gate has a passing human receipt, host truth is stamped
    # (mode B), and the README's claim matches the receipts (G10 — the label may never outrun
    # the evidence). Anything less is an honest RC with the blockers named. Calls sub-checks
    # via global names (tests monkeypatch them). ok:true ONLY on STABLE-READY: R.R is the
    # stable-promotion gate, un-bankable until the drop is verified — by design.
    import datetime, re
    machine = {
        "mutation_fail_closed": check_mutation_fail_closed,
        "runtime_owns_heartbeat": check_runtime_owns_heartbeat,
        "hot_reload_gated": check_hot_reload_gated,
        "deps_isolated": check_deps_isolated,
        "installer_host_targeted": check_installer_host_targeted,
        "ci_covers_shipping_surface": check_ci_covers_shipping_surface,
        "shelf_current": check_shelf_current,
    }
    security = {
        "process_bridge_armed": check_process_bridge_armed,
        "auth_fail_closed": check_auth_fail_closed,
    }
    hygiene = {
        "tool_metadata_single_source": check_tool_metadata_single_source,
        "packaging_self_contained": check_packaging_self_contained,
    }
    per_check = {}
    for name, fn in {**machine, **security, **hygiene}.items():
        try:
            per_check[name] = fn(ctx).get("ok")
        except Exception:
            per_check[name] = None  # a broken sub-check is a down gate, not a silent pass

    machine_red = [n for n in machine if per_check.get(n) is not True]
    open_hygiene = [n for n in hygiene if per_check.get(n) is not True]

    # security legs mirror S.R's posture scoping: honest RED individually, accepted (named,
    # non-blocking) under a declared solo posture, hard blockers under studio/farm/undeclared.
    posture = _read_posture()
    mode_p = (posture or {}).get("mode")
    sec_red = [n for n in security if per_check.get(n) is not True]
    if mode_p == "solo":
        accepted, sec_block = sec_red, []
    else:
        accepted, sec_block = [], sec_red

    # live gates: human receipts only — a machine can't attest a fresh-account install or a
    # restart drill. Absent/failed ⇒ PENDING (never faked).
    receipts = _read_receipts()
    def _passed(k):
        r = receipts.get(k)
        return isinstance(r, dict) and r.get("result") == "pass"
    receipts_pending = [k for k in _RECEIPT_KEYS if not _passed(k)]

    # G3 host truth: no H22 exists in mode A — honestly pending-drop. Mode B: the per-major
    # symbol table must be committed in the worktree, stamped by the drop's major.
    g3 = "pending-drop"
    if ctx.get("mode") == "B":
        major = ""
        try:
            major = str(json.loads(_drop_path().read_text(encoding="utf-8"))
                        .get("houdini", "")).split(".")[0]
        except Exception:
            pass
        table = (Path(ctx["wt"]) / "python" / "synapse" / "cognitive" / "tools" / "data"
                 / f"h{major}_symbol_table.json")
        g3 = "green" if (major and table.is_file()) else f"missing h{major or '?'}_symbol_table.json"

    # G10 documentation truth: a README H22-verified claim is legitimate only once everything
    # above holds — a premature claim is itself a blocker.
    readme_src, _ = _read_src(ctx, "README.md")
    claims = bool(readme_src and re.search(
        r"H22[\s-]*(ready|verified)|Houdini\s*22[\s-]*(ready|verified)", readme_src, re.I))
    substance = not machine_red and not receipts_pending and g3 == "green"
    g10_ok = (not claims) or substance

    blockers = list(machine_red) + list(sec_block)
    blockers += [f"receipt:{k}" for k in receipts_pending]
    if g3 != "green":
        blockers.append(f"g3:{g3}")
    if not g10_ok:
        blockers.append("g10:README claims H22-ready without receipts")

    ok = not blockers
    if ok:
        verdict = "STABLE-READY"
    elif machine_red or sec_block:
        verdict = "RC — release-blocking gates red"
    elif receipts_pending or g3 != "green":
        verdict = "RC — machine gates green, live receipts/host truth pending"
    else:
        verdict = "RC — documentation claim outruns receipts"

    g_map = {
        "G1_clean_install": "pass" if _passed("g1_clean_install") else "pending",
        "G2_dependency_isolation": per_check.get("deps_isolated"),
        "G3_host_truth": g3,
        "G4_mutation_integrity": per_check.get("mutation_fail_closed"),
        "G5_lifecycle": {"machine": per_check.get("runtime_owns_heartbeat"),
                         "live": "pass" if _passed("g5_lifecycle") else "pending"},
        "G6_core_smoke": "pass" if _passed("g6_core_smoke") else "pending",
        "G7_reversibility": "pass" if _passed("g7_reversibility") else "pending",
        "G8_restart": "pass" if _passed("g8_restart") else "pending",
        "G9_rollback": "pass" if _passed("g9_rollback") else "pending",
        "G10_documentation_truth": g10_ok,
    }
    # read-only crossref: the studio verdict is CONTEXT (S.R owns it) — never recomputed or
    # re-aggregated here, so the two capstones can't double-count each other's gates.
    crossref = None
    try:
        sv = Path(ctx["wt"]) / "harness" / "state" / "studio_readiness_verdict.json"
        if sv.is_file():
            crossref = json.loads(sv.read_text(encoding="utf-8")).get("verdict")
    except Exception:
        pass

    out = {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "per_check": per_check,
        "receipts": {k: ("pass" if _passed(k) else "pending") for k in _RECEIPT_KEYS},
        "g_map": g_map,
        "blockers": blockers,
        "accepted_under_posture": accepted,
        "open_hygiene": open_hygiene,
        "verdict": verdict,
        "posture": mode_p or "undeclared",
        "mode": ctx.get("mode", "A"),
        "studio_readiness_crossref": crossref,
    }
    try:
        vp = Path(ctx["wt"]) / "harness" / "state" / "release_readiness_verdict.json"
        vp.parent.mkdir(parents=True, exist_ok=True)
        vp.write_text(json.dumps(out, indent=2), encoding="utf-8")
    except Exception:
        pass  # a read-only fs must not crash the gate — the return value is the authority
    return {"ok": ok, "detail": (f"release verdict: {verdict} — blockers: "
            f"{', '.join(blockers) or 'none'}; accepted (solo): {', '.join(accepted) or 'none'}; "
            f"open hygiene: {', '.join(open_hygiene) or 'none'}")[:500]}


# ---------- Ratchet guardrail: protect GREEN, catch collateral regressions ----------
# The "instinct" harness (harness-architect, 2026-07-07): the full-suite green
# baseline is the one primitive run.ts lacked. Per-check subset pytest runs are
# NOT gates — collection-order / fake-hou residency effects (see the residency
# trap note atop tests/conftest.py) — so this guardrail runs the FULL `pytest
# tests/` every sprint and ratchets the result against the COMMITTED baseline:
# failures may only go DOWN, passes only UP. A change that greens its own target
# but reddens N OTHER tests (the 4080->47-red collateral case that had to be
# caught by hand) fails the sprint deterministically, before the Evaluator. The
# baseline advances ONLY via a human-promoted commit that legitimately moves the
# counts. The floor is read at the HUMAN-PROMOTED line — merge-base(master, HEAD),
# mirroring check_phantom_clean's anchor — NOT the worktree's own HEAD: inside a
# harness sprint the agent has already made its atomic commit, so HEAD is the agent's
# tip and `git show HEAD:` would let a sprint commit a lowered floor and green its own
# regression. agent-settings.json also denies Edit of this file (belt + suspenders).
def check_suite_baseline(ctx):
    import re
    mb_rc, mb_out, _ = sh(["git", "merge-base", "master", "HEAD"], cwd=ctx["wt"])
    anchor = mb_out.strip() if mb_rc == 0 and mb_out.strip() else "HEAD"  # fall back only if master unresolvable
    rc_b, base_raw, _ = sh(["git", "show", f"{anchor}:harness/verify/suite_baseline.json"], cwd=ctx["wt"])
    if rc_b != 0 or not base_raw.strip():
        return {"ok": False, "detail": "no committed harness/verify/suite_baseline.json at the ratchet "
                                       "anchor (merge-base master HEAD) — seed it with current green counts"}
    try:
        base = json.loads(base_raw)
        passed_base, failed_base = int(base["passed"]), int(base["failed"])
    except Exception as e:
        return {"ok": False, "detail": f"baseline unreadable: {type(e).__name__}: {str(e)[:200]}"}
    rc, out, err = sh([sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider"],
                      cwd=ctx["wt"], env=_wt_env(ctx), timeout=1800)
    blob = out + "\n" + err
    def _n(pat):
        m = re.search(pat, blob)
        return int(m.group(1)) if m else 0
    passed_now = _n(r"\b(\d+) passed\b")
    failed_now = _n(r"\b(\d+) failed\b") + _n(r"\b(\d+) errors?\b")
    if passed_now == 0:
        # rc 0 alone lies: an all-skipped or collection-errored run is NOT green.
        tail = blob.strip().splitlines()
        return {"ok": False, "detail": f"ZERO tests passed (collection error / all skipped?) rc={rc} — "
                                       f"{(tail[-1] if tail else 'no pytest output')[:280]}"}
    ok = failed_now <= failed_base and passed_now >= passed_base
    detail = (f"passed {passed_now} (base {passed_base}), failed {failed_now} (base {failed_base}); "
              f"ratchet {'holds' if ok else 'BROKEN'}")
    if not ok and failed_now > failed_base:
        detail += f" — {failed_now - failed_base} NEW failure(s): collateral regression, protect green"
    elif not ok and passed_now < passed_base:
        detail += f" — {passed_base - passed_now} test(s) stopped passing (turned skip/error/removed)"
    return {"ok": ok, "detail": detail[:500]}


def run_one(name, task, ctx):
    fn = DISPATCH.get(name)
    if not fn:
        return {"ok": False, "detail": "no check implemented — ADAPT"}
    if name == "cook_node":
        return check_cook(ctx, node=(task.get("target_node", "") or "").replace("ADAPT: ", "") or None)
    return fn(ctx)


def check_knowledge_baseline_fresh(ctx):
    # K.0: corpus baseline snapshot must exist and be internally consistent — schema
    # v1 + blake2b recompute over the stats block. Read-only, no hython dependency
    # (corpus stats aren't Houdini-build-specific).
    wt = Path(ctx["wt"])
    fp = wt / "harness" / "notes" / "knowledge_baseline.json"
    if not fp.exists():
        return {"ok": False, "detail": "harness/notes/knowledge_baseline.json missing — run K.0 first"}
    try:
        import hashlib
        data = json.loads(fp.read_text(encoding="utf-8"))
        if data.get("schema") != "knowledge_baseline/v1":
            return {"ok": False, "detail": f"schema={data.get('schema')} != knowledge_baseline/v1"}
        digest = hashlib.blake2b(
            json.dumps(data.get("stats", {}), sort_keys=True, ensure_ascii=False).encode("utf-8"),
            digest_size=16).hexdigest()
        if digest != data.get("blake2b"):
            return {"ok": False, "detail": "baseline blake2b mismatch (corrupt/hand-edited)"}
    except Exception as e:
        return {"ok": False, "detail": f"baseline unreadable: {str(e)[:300]}"}
    stats = data.get("stats", {})
    return {"ok": True, "detail": f"baseline sound ({stats.get('reference_files', '?')} reference files, "
                                  f"{stats.get('corpus_entries', '?')} corpus entries)"}


def check_semantic_index_built(ctx):
    # K.1: the offline embedding index must exist and be internally consistent —
    # manifest declares a registered embedder, meta.jsonl row count matches the
    # manifest's declared entry count, embeddings.npy is present. Does not load
    # sentence-transformers itself (this check must pass even where that optional
    # dependency isn't installed — it's checking BUILD artifacts, not re-embedding).
    wt = Path(ctx["wt"])
    idx = wt / "rag" / "semantic_index"
    manifest_fp = idx / "manifest.json"
    meta_fp = idx / "meta.jsonl"
    npy_fp = idx / "embeddings.npy"
    if not manifest_fp.is_file():
        return {"ok": False, "detail": "rag/semantic_index/manifest.json missing — "
                                       "run scripts/build_semantic_index.py"}
    try:
        manifest = json.loads(manifest_fp.read_text(encoding="utf-8"))
    except Exception as e:
        return {"ok": False, "detail": f"manifest unreadable: {str(e)[:300]}"}
    if manifest.get("embedder") != "sentence-transformers":
        return {"ok": False, "detail": f"embedder={manifest.get('embedder')} not a registered scout embedder"}
    if not meta_fp.is_file() or not npy_fp.is_file():
        return {"ok": False, "detail": "meta.jsonl or embeddings.npy missing alongside manifest.json"}
    n_meta = sum(1 for l in meta_fp.read_text(encoding="utf-8").splitlines() if l.strip())
    declared = manifest.get("entries")
    if declared is not None and n_meta != declared:
        return {"ok": False, "detail": f"meta.jsonl has {n_meta} rows but manifest declares {declared} entries"}
    return {"ok": True, "detail": f"semantic index sound ({n_meta} embedded entries, model={manifest.get('model')})"}


def check_rewire_assessed(ctx):
    # K.6 Phase 1: the vex-corpus re-wire question is answered by MEASUREMENT, not
    # debate — this verifies the assessment scorecard exists and is well-formed (schema
    # rewire_assessment/v1), and surfaces its usable-entries number. Decision-support,
    # not a pass/fail gate on the number itself: the re-wire call is the maintainer's,
    # informed by the scorecard. Read-only, no hython. Mirrors check_knowledge_baseline_fresh.
    wt = Path(ctx["wt"])
    fp = wt / "harness" / "notes" / "rewire_assessment.json"
    if not fp.exists():
        return {"ok": False, "detail": "harness/notes/rewire_assessment.json missing — "
                                       "run scripts/rewire_assess.py (K.6 Phase 1)"}
    try:
        d = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        return {"ok": False, "detail": f"assessment unreadable: {str(e)[:200]}"}
    if d.get("schema") != "rewire_assessment/v1":
        return {"ok": False, "detail": f"schema={d.get('schema')} != rewire_assessment/v1"}
    for k in ("raw_code_blocks", "unique_snippets", "usable_entries_estimate"):
        if k not in d:
            return {"ok": False, "detail": f"assessment missing required field '{k}'"}
    return {"ok": True, "detail": f"re-wire assessed: {d['raw_code_blocks']} raw blocks -> "
                                  f"{d['usable_entries_estimate']} usable-entry estimate "
                                  f"({d.get('usable_rate_vs_raw_pct')}% ; vcc={d.get('vcc_available')})"}


def check_semantic_index_fresh(ctx):
    # K.5: the committed embedding index must match the CURRENT rag/ content it
    # claims to represent. build_semantic_index stamps manifest.json with a
    # content_digest over the embedded source (reference .md tree +
    # semantic_index.json, whose topic enrichment is folded into embedded text);
    # this recomputes it and compares. Stale (a reference file or topic was
    # edited/added but the vectors were not rebuilt — e.g. K.2 changed enrichment
    # after K.1 embedded) reads RED -> run scripts/refresh_knowledge.py. This is
    # THE "easy to update for H22" gate: it makes doc drift loud instead of silent.
    #
    # The digest formula below MUST stay identical to
    # scripts/build_semantic_index.py::embed_source_digest (pure file reads, no
    # synapse/torch import, so the gate runs anywhere the repo does).
    import hashlib
    wt = Path(ctx["wt"])
    rag = wt / "rag"
    manifest_fp = rag / "semantic_index" / "manifest.json"
    if not manifest_fp.is_file():
        return {"ok": False, "detail": "rag/semantic_index/manifest.json missing — "
                                       "run scripts/build_semantic_index.py (K.1)"}
    try:
        manifest = json.loads(manifest_fp.read_text(encoding="utf-8"))
    except Exception as e:
        return {"ok": False, "detail": f"manifest unreadable: {str(e)[:200]}"}
    recorded = manifest.get("content_digest")
    if not recorded:
        return {"ok": False, "detail": "manifest has no content_digest — rebuild via "
                                       "scripts/build_semantic_index.py to stamp the K.5 freshness anchor"}
    parts = []
    md_dir = rag / "skills" / "houdini21-reference"
    if md_dir.is_dir():
        for p in sorted(md_dir.glob("*.md"), key=lambda p: p.name):
            parts.append((p.name, hashlib.blake2b(p.read_bytes(), digest_size=16).hexdigest()))
    sem = rag / "documentation" / "_metadata" / "semantic_index.json"
    if sem.is_file():
        parts.append(("semantic_index.json",
                      hashlib.blake2b(sem.read_bytes(), digest_size=16).hexdigest()))
    live = hashlib.blake2b("\n".join(f"{n}:{h}" for n, h in parts).encode("utf-8"),
                           digest_size=16).hexdigest()
    if live != recorded:
        return {"ok": False, "detail": f"embeddings STALE — rag/ content changed since last embed "
                                       f"(manifest {recorded[:12]}… != live {live[:12]}…); "
                                       "run scripts/refresh_knowledge.py"}
    return {"ok": True, "detail": f"embeddings fresh vs rag/ content "
                                  f"({manifest.get('entries', '?')} entries, digest {live[:12]}…)"}


def check_knowledge_topic_coverage(ctx):
    # K.2: every reference .md file must have a topic in semantic_index.json whose
    # reference_file points at it — otherwise the Tier-1 fast path (keyword/no-LLM)
    # can only reach it by header-word luck. Read-only, no hython. Robust to adding
    # files: a new .md with no topic reads red, correctly prompting a topic entry.
    wt = Path(ctx["wt"])
    sem_fp = wt / "rag" / "documentation" / "_metadata" / "semantic_index.json"
    ref_dir = wt / "rag" / "skills" / "houdini21-reference"
    if not sem_fp.is_file() or not ref_dir.is_dir():
        return {"ok": False, "detail": "rag/ semantic_index.json or reference dir missing"}
    try:
        sem = json.loads(sem_fp.read_text(encoding="utf-8"))
    except Exception as e:
        return {"ok": False, "detail": f"semantic_index.json unreadable: {str(e)[:200]}"}
    topics = sem
    if isinstance(sem, dict) and isinstance(sem.get("semantic_index"), dict):
        topics = sem["semantic_index"].get("topics", sem["semantic_index"])
    pointed = {str(t.get("reference_file", "")).replace(".md", "").strip()
               for t in topics.values()
               if isinstance(t, dict) and str(t.get("reference_file", "")).strip()}
    md = sorted(p.stem for p in ref_dir.glob("*.md"))
    uncovered = [f for f in md if f not in pointed]
    if uncovered:
        return {"ok": False, "detail": f"{len(uncovered)}/{len(md)} reference files have no "
                                       f"topic pointer (Tier-1 header-luck only): {uncovered[:8]}"}
    return {"ok": True, "detail": f"topic coverage complete: {len(md)}/{len(md)} reference "
                                  "files reachable via a topic pointer"}


def check_knowledge_root_canonical(ctx):
    # K.3: scout's default RAG_ROOT must resolve to the repo rag/ tree, not the
    # legacy G:\HOUDINI21_RAG_SYSTEM store (whose corpus/ entries lack
    # searchable_text — a session defaulted there loads hollow). Source-pattern
    # check, matching the discipline R-track's deps_isolated/hot_reload_gated
    # checks already use for config-shape assertions.
    wt = Path(ctx["wt"])
    fp = wt / "python" / "synapse" / "cognitive" / "tools" / "scout.py"
    if not fp.is_file():
        return {"ok": False, "detail": "scout.py not found"}
    import re
    src = fp.read_text(encoding="utf-8")
    m = re.search(r'^RAG_ROOT\s*=\s*Path\(os\.environ\.get\("SYNAPSE_RAG_ROOT",\s*(.+?)\)\)', src, re.MULTILINE)
    if not m:
        return {"ok": False, "detail": "RAG_ROOT default assignment not found in expected form — "
                                       "ADAPT this check if scout.py's config seam changed shape"}
    default_expr = m.group(1)
    if "HOUDINI21_RAG_SYSTEM" in default_expr:
        return {"ok": False, "detail": f"RAG_ROOT still defaults to the legacy G:\\ store: {default_expr}"}
    return {"ok": True, "detail": f"RAG_ROOT default is canonical: {default_expr}"}


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
    # ratchet guardrail — full-suite green baseline (collateral-regression detector)
    "suite_baseline": check_suite_baseline,
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
    # D — diagnostic-truth track (dormant until D.0 ratified)
    "cook_api_confirmed": check_cook_api_confirmed,
    "cook_truth_fresh": check_cook_truth_fresh,
    "cook_review_clean": check_cook_review_clean,
    "cook_golden_sop": check_cook_golden_sop,
    "cook_golden_lop": check_cook_golden_lop,
    "cook_golden_cop": check_cook_golden_cop,
    "cook_golden_dop": check_cook_golden_dop,
    "tops_path_untouched": check_tops_path_untouched,
    # S — studio-readiness hardening track
    "posture_declared": check_posture_declared,
    "policy_single_source": check_policy_single_source,
    "consent_enforced": check_consent_enforced,
    "rbac_at_dispatch": check_rbac_at_dispatch,
    "memory_provenance": check_memory_provenance,
    "eval_backbone": check_eval_backbone,
    "farm_headless": check_farm_headless,
    "studio_readiness_review": check_studio_readiness_review,
    # R — release-readiness (H22 RC) track
    "mutation_fail_closed": check_mutation_fail_closed,
    "runtime_owns_heartbeat": check_runtime_owns_heartbeat,
    "hot_reload_gated": check_hot_reload_gated,
    "deps_isolated": check_deps_isolated,
    "installer_host_targeted": check_installer_host_targeted,
    "ci_covers_shipping_surface": check_ci_covers_shipping_surface,
    "shelf_current": check_shelf_current,
    "tool_metadata_single_source": check_tool_metadata_single_source,
    "process_bridge_armed": check_process_bridge_armed,
    "auth_fail_closed": check_auth_fail_closed,
    "packaging_self_contained": check_packaging_self_contained,
    "release_readiness_review": check_release_readiness_review,
    # K — knowledge/corpus-freshness track
    "knowledge_baseline_fresh": check_knowledge_baseline_fresh,
    "semantic_index_built": check_semantic_index_built,
    "semantic_index_fresh": check_semantic_index_fresh,
    "knowledge_topic_coverage": check_knowledge_topic_coverage,
    "knowledge_root_canonical": check_knowledge_root_canonical,
    "rewire_assessed": check_rewire_assessed,
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
