"""SYNAPSE husk export-fidelity spike — the render-freeze harness's FIRST MOVE.

WHAT THIS PROVES (the three questions that gate the whole fix)
-------------------------------------------------------------
  Q1  NON-FREEZE   Does husk (out-of-process) remove the freeze? -> watch
                   render_watch.ps1 in a second window: Responding must stay
                   True the entire time. (The Python Shell prompt also returns
                   immediately — the poll runs on a background thread.)
  Q2  EXPORT       Does the exported USD capture UNSAVED in-process LOP edits?
                   This script makes a deliberate, loud edit FIRST (nudges the
                   distant light + moves the sphere), then exports+renders. If
                   the EXR reflects the edit, the export is faithful.
  Q3  ASSETS       Do referenced assets resolve? The bare sphere has none — add
                   a textured material and re-run to test the relative-path
                   caveat the crucible flagged (Flatten anchors paths to cwd).

WHY A SPIKE, NOT THE FIX
------------------------
The freeze diagnosis is already code-confirmed (handlers_render.py:497/:536).
The OPEN risk is the FIX's export fidelity + no-freeze delivery — so we prove
that one shot before wiring the kill switch, hardcaps, or the merge spec. If
husk renders the unsaved edit while Responding stays True, the plan holds. If
it renders a stale/grey stage, the plan pivots to the ROP lopoutput-write
export before anything else.

HOW TO RUN (at the desk)
------------------------
  1. Open the repro scene (scripts/build_freeze_repro.py, or any /stage with a
     usdrender_rop).
  2. In a PowerShell window:  pwsh -File scripts\render_watch.ps1
  3. In Houdini's Python Shell:
        exec(open(r'C:\\Users\\User\\SYNAPSE\\scripts\\husk_spike.py').read())
  4. Read the verdict this prints when husk finishes; cross-check the watcher.

SAFETY: husk is a CHILD process — it cannot freeze Houdini. Worst case it
no-ops (Indie) or errors; both are detected and reported, never silent. The
deliberate scene edit is intended for the REPRO scene, not production work.
"""

import os
import subprocess
import threading
import time
from pathlib import Path

import hou

# ---- config (override before exec if you like) ------------------------------
ROP_PATH   = None       # None = auto-find a usdrender/usdrender_rop in /stage then /out
FRAME      = 1
POLL_DEADLINE_S = 180   # generous: a COLD XPU OptiX compile is documented up to ~120s
MAKE_EDIT  = True       # make a loud unsaved edit to test Q2 (export fidelity)


def _find_rop():
    if ROP_PATH:
        n = hou.node(ROP_PATH)
        if n is None:
            raise ValueError("ROP_PATH %r not found" % ROP_PATH)
        return n
    types = {"usdrender", "usdrender_rop", "karma", "karmarendersettings"}
    for parent in ("/stage", "/out"):
        p = hou.node(parent)
        if p is None:
            continue
        for c in p.children():
            if c.type().name() in types:
                return c
    raise ValueError("No usdrender/karma ROP found in /stage or /out — build the "
                     "repro scene first (scripts/build_freeze_repro.py).")


def _lop_stage(rop):
    """Resolve the live composed stage feeding this ROP (captures unsaved edits)."""
    lp = rop.parm("loppath")
    lop = None
    if lp and lp.eval():
        lop = hou.node(lp.eval())
    if lop is None:
        st = hou.node("/stage")
        if st and st.children():
            disp = [c for c in st.children()
                    if hasattr(c, "isDisplayFlagSet") and c.isDisplayFlagSet()]
            lop = disp[0] if disp else st.children()[-1]
    if lop is None:
        raise ValueError("Couldn't resolve a LOP stage for %s" % rop.path())
    return lop


def _detect_engine(rop):
    for pname in ("engine", "renderer", "karmarenderertype", "renderengine"):
        p = rop.parm(pname)
        if p is None:
            # engine parm usually lives on the karmarendersettings LOP
            lp = rop.parm("loppath")
            if lp and lp.eval():
                lop = hou.node(lp.eval())
                if lop:
                    p = lop.parm(pname)
        if p is not None:
            v = str(p.eval()).lower()
            if "xpu" in v:
                return "xpu"
            if "cpu" in v:
                return "cpu"
    return "cpu"  # safe default: CPU has no OptiX cold-compile


def _make_loud_edit(lop_stage_owner):
    """Nudge the light + sphere so the render VISIBLY differs from the base scene.
    Returns a human description of what changed (so you know what to look for)."""
    changed = []
    st = hou.node("/stage")
    if st is None:
        return "no /stage — skipped edit"
    for c in st.children():
        tn = c.type().name()
        if tn == "distantlight" or tn == "light" or "light" in tn:
            for pn in ("xn__inputsintensity_i0a", "intensity", "inputs:intensity"):
                p = c.parm(pn)
                if p:
                    p.set(6.0)
                    changed.append("%s.%s=6.0" % (c.name(), pn))
                    break
        if tn == "sphere":
            p = c.parm("tx") or c.parmTuple("t")
            try:
                if c.parm("tx"):
                    c.parm("tx").set(0.35)
                    changed.append("%s.tx=0.35" % c.name())
            except Exception:
                pass
    return ", ".join(changed) if changed else "nothing editable found (bare scene)"


def _husk_argv(husk_exe, engine, temp_usd, out_exr, frame):
    """Doc-verified husk flags (ref/utils/husk.html, H22). Short forms -f/-n/-o
    are stable H18->22; --renderer/--engine/--gpu are the H22-doc spellings.
    If husk errors on a flag, re-probe with synapse_scout and adjust here."""
    argv = [
        str(husk_exe),
        "--verbose", "2",
        "--renderer", "karma",
        "--frame", str(frame),
        "--frame-count", "1",
        "--output", out_exr,
        "--make-output-path",
    ]
    if engine == "xpu":
        argv += ["--engine", "xpu", "--gpu"]   # --gpu REQUIRED for XPU device context
    else:
        argv += ["--engine", "cpu"]
    argv += [temp_usd]                          # positional USD last
    return argv


def _poll_and_report(proc, out_exr, temp_usd, edit_desc, t_spawn):
    """Background thread: decide success by OUTPUT FILE, not exit code (Indie
    exits 0 having written nothing). Prints the verdict when husk finishes."""
    deadline = time.time() + POLL_DEADLINE_S
    render_ok = False
    while True:
        rc = proc.poll()
        f = Path(out_exr)
        has_out = f.exists() and f.stat().st_size > 0
        if rc is not None:
            for _ in range(8):                  # brief flush grace after exit
                if Path(out_exr).exists() and Path(out_exr).stat().st_size > 0:
                    break
                time.sleep(0.25)
            render_ok = Path(out_exr).exists() and Path(out_exr).stat().st_size > 0
            break
        if time.time() > deadline:
            try:
                proc.kill()
            except Exception:
                pass
            print("\n[husk_spike] DEADLINE %ss hit — killed husk (pid %s)."
                  % (POLL_DEADLINE_S, proc.pid))
            break
        time.sleep(0.25)

    elapsed = time.time() - t_spawn
    try:
        tail = (proc.stdout.read() or b"")[-1200:].decode("utf-8", "replace") if proc.stdout else ""
    except Exception:
        tail = ""
    size = Path(out_exr).stat().st_size if Path(out_exr).exists() else 0

    print("\n" + "=" * 68)
    print("[husk_spike] VERDICT after %.1fs (exit=%s)" % (elapsed, proc.returncode))
    print("  Q1 NON-FREEZE : check render_watch.ps1 — Responding stayed True? -> husk removes the freeze")
    if render_ok:
        print("  RESULT        : husk WROTE %s (%d bytes)" % (out_exr, size))
        print("  Q2 EXPORT     : open it — does it show the edit? [%s]" % edit_desc)
        print("                  if yes -> Flatten().Export() captured unsaved in-process edits (GOOD)")
        print("  Q3 ASSETS     : bare sphere has none; add a textured material + re-run to test path resolution")
    else:
        print("  RESULT        : husk produced NO output file.")
        print("  LIKELY        : Indie/Apprentice license no-op (husk exits 0, writes nothing) OR a husk error.")
        print("                  -> read hou.licenseCategory() in THIS session; if Indie, husk is not a viable")
        print("                     default and the fix needs the Commercial-tier branch + an Indie preview path.")
    if tail.strip():
        print("  husk stdout tail:\n    " + tail.strip().replace("\n", "\n    "))
    print("  temp USD      : %s" % temp_usd)
    print("=" * 68)


def main():
    rop = _find_rop()
    engine = _detect_engine(rop)
    lop = _lop_stage(rop)

    hfs = Path(hou.text.expandString("$HFS"))
    husk_exe = hfs / "bin" / ("husk.exe" if os.name == "nt" else "husk")
    if not husk_exe.exists():
        raise RuntimeError("husk not found at %s — cannot run the spike." % husk_exe)

    lic = "unknown"
    try:
        lic = str(hou.licenseCategory())   # THE fork: Indie -> husk likely no-ops
    except Exception:
        pass

    edit_desc = _make_loud_edit(lop) if MAKE_EDIT else "no edit (MAKE_EDIT=False)"

    temp_dir = Path(hou.text.expandString("$HOUDINI_TEMP_DIR"))
    ts = int(time.time())
    temp_usd = str(temp_dir / ("synapse_huskspike_%d.usd" % ts))
    out_exr = str(temp_dir / ("synapse_huskspike_%d.exr" % ts))

    # --- main-thread work: setFrame + flatten-export the LIVE composed stage ---
    prev = hou.frame()
    try:
        hou.setFrame(FRAME)
        stage = lop.stage()
        if stage is None:
            raise RuntimeError("lop.stage() is None — cook the LOP first (display flag).")
        flat = stage.Flatten()             # inlines composition arcs -> husk-resolvable
        flat.Export(temp_usd)
    finally:
        hou.setFrame(prev)

    usd_size = Path(temp_usd).stat().st_size if Path(temp_usd).exists() else 0
    argv = _husk_argv(husk_exe, engine, temp_usd, out_exr, FRAME)

    print("=" * 68)
    print("[husk_spike] SYNAPSE husk export-fidelity spike")
    print("  ROP           : %s (engine=%s)" % (rop.path(), engine))
    print("  license       : %s   %s" % (lic, "(Indie -> husk may no-op!)" if "ndie" in lic or "pprentice" in lic else ""))
    print("  unsaved edit  : %s" % edit_desc)
    print("  exported USD  : %s (%d bytes)" % (temp_usd, usd_size))
    print("  husk cmd      : %s" % " ".join(argv))
    print("-" * 68)

    t_spawn = time.time()
    proc = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=os.environ, cwd=str(hfs / "bin"),
        creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
    )
    print("[husk_spike] husk SPAWNED pid=%s. Python Shell is FREE — keep typing to prove non-freeze." % proc.pid)
    print("[husk_spike] Watch render_watch.ps1: 'husk=1 OUT-OF-PROCESS' should appear and Responding stay True.")
    print("[husk_spike] To kill:  import subprocess; subprocess.run(['taskkill','/PID','%s','/F'])" % proc.pid)

    threading.Thread(
        target=_poll_and_report,
        args=(proc, out_exr, temp_usd, edit_desc, t_spawn),
        name="husk_spike_poll", daemon=True,
    ).start()


main()
