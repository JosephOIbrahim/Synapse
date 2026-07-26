"""Probe every cancel candidate the doc sweep surfaced. Runtime is decisive.

The sweep found four things the SideFX ask did not account for:
  hou.ActiveRender.kill / suspend / resume   - documented, #status: ni
  hou.activeRenders()                        - documented, #status: ni
  hou.IPRViewer.killRender                   - status unknown
  rkill / rps hscript commands               - ActiveRender says it REPLACES these,
                                               which implies they exist today

#status: ni is SideFX markup for "not implemented". Do not take that on trust -
the whole point of R50 is that a documented claim needs a runtime control.
"""
import hou

print("PYTHON:", __import__("sys").version.split()[0])
print("BUILD :", hou.applicationVersionString())
print()

print("=" * 66)
print("A. hou.ActiveRender / hou.activeRenders")
print("=" * 66)
print("  hou.ActiveRender present :", hasattr(hou, "ActiveRender"))
if hasattr(hou, "ActiveRender"):
    print("  methods:", [m for m in dir(hou.ActiveRender) if not m.startswith("_")])
print("  hou.activeRenders present:", hasattr(hou, "activeRenders"))
if hasattr(hou, "activeRenders"):
    try:
        r = hou.activeRenders()
        print("  activeRenders() ->", type(r).__name__, len(r) if hasattr(r, "__len__") else "")
    except Exception as e:
        print("  activeRenders() RAISED:", type(e).__name__, str(e)[:120])

print()
print("=" * 66)
print("B. hou.IPRViewer.killRender")
print("=" * 66)
print("  hou.IPRViewer present:", hasattr(hou, "IPRViewer"))
if hasattr(hou, "IPRViewer"):
    ms = [m for m in dir(hou.IPRViewer) if not m.startswith("_")]
    print("  killRender present   :", "killRender" in ms)
    print("  kill-ish methods     :", [m for m in ms if "kill" in m.lower() or "stop" in m.lower()])

print()
print("=" * 66)
print("C. rkill / rps hscript commands")
print("=" * 66)
for cmd in ("rps", "rkill"):
    try:
        out, err = hou.hscript("help " + cmd)
        ok = bool(out.strip()) and "Unknown command" not in out
        print("  %-6s -> %s" % (cmd, ("EXISTS: " + " ".join(out.split())[:110]) if ok
                                else ("absent / " + " ".join((out + err).split())[:90])))
    except Exception as e:
        print("  %-6s RAISED %s" % (cmd, type(e).__name__))

print()
print("=" * 66)
print("D. RopNode - the original claim, re-confirmed")
print("=" * 66)
ms = [m for m in dir(hou.RopNode) if not m.startswith("_")]
print("  cancel-like on RopNode:",
      [m for m in ms if any(k in m.lower() for k in ("cancel", "abort", "interrupt", "kill", "stop"))] or "NONE")
