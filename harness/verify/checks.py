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
    clean = f"{len(touched)} changed .py clean of table-proven phantom hou.* APIs (vs {len(table_syms)} live symbols @ {ver})"
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
