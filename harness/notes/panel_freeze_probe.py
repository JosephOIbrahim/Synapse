"""Why is Houdini freezing during a SYNAPSE request?

Run this INSIDE Houdini's Python Shell, right after a request that froze.

THE ARCHITECTURE IS NOT OBVIOUSLY WRONG. The API call runs on a QThread
(ClaudeWorker) and _execute_tool_block prefers the local MCP endpoint, which is
worker-thread safe. So a freeze means one of two things, and they have different
fixes:

  A) MCP is unreachable, so every tool falls back to Qt signal dispatch -
     claude_worker.py:289 tool_requested.emit(request) - which is delivered ON
     THE MAIN THREAD, where run_on_main takes its second fast path and calls
     fn() INLINE. The GUI is blocked for the whole tool. main_thread.py names
     this itself: "C6: this is the dominant panel/bridge inline path".

  B) MCP is fine and individual hou.* operations are simply long.

SYNAPSE already instruments both. This reads its own instruments rather than
adding a third:

    main_thread_direct_stats()   the INLINE path - the freeze itself
    dispatch_wait_stats()        the C6 worker-marshal histogram
    stall_state()                the timeout/stall detector
    probe_main_thread()          is it responsive right now
"""
print("=" * 70)
print("SYNAPSE - main-thread freeze diagnosis")
print("=" * 70)

# --- is the bridge listening? -------------------------------------------
import socket
listening = []
for p in (9999, 8765, 9090):
    s = socket.socket()
    s.settimeout(0.4)
    if s.connect_ex(("127.0.0.1", p)) == 0:
        listening.append(p)
    s.close()
print("  bridge ports listening :", listening or "NONE")

try:
    from synapse.server import main_thread as mt
except Exception as e:
    print("  main_thread            : unavailable -", type(e).__name__)
    raise SystemExit

# --- the inline path: this IS the freeze --------------------------------
print()
print("  INLINE MAIN-THREAD WORK  (blocks the GUI while it runs)")
try:
    print("   ", mt.main_thread_direct_stats())
except Exception as e:
    print("    unavailable -", type(e).__name__)

# --- the worker marshal: healthy path -----------------------------------
print()
print("  C6 DISPATCH WAITS  (worker asked, main thread answered)")
try:
    print("   ", mt.dispatch_wait_stats())
except Exception as e:
    print("    unavailable -", type(e).__name__)

# --- stalls -------------------------------------------------------------
print()
print("  STALL DETECTOR")
try:
    print("    stalled now :", mt.is_main_thread_stalled())
    print("    state       :", mt.stall_state())
except Exception as e:
    print("    unavailable -", type(e).__name__)

# --- responsiveness right now -------------------------------------------
print()
try:
    import time
    t0 = time.perf_counter()
    ok = mt.probe_main_thread(timeout=2.0)
    print("  main thread responds   : %s  (%.0f ms)"
          % (ok, (time.perf_counter() - t0) * 1000))
except Exception as e:
    print("  probe_main_thread      : unavailable -", type(e).__name__)

print()
print("=" * 70)
print("  READING IT")
print()
print("  No bridge port listening, and INLINE stats showing most of the work")
print("  -> cause A. Every tool is taking the blocking fallback and the fix is")
print("     to get MCP up, not to optimise anything.")
print()
print("  Port listening, INLINE near zero, C6 waits high")
print("  -> cause B. The marshal is working and individual hou.* calls are")
print("     long. That is a per-tool problem, not an architecture one.")
print()
print("  Both high -> the fallback is firing SOMETIMES; the interesting")
print("  question is which tools, and tool_status in the panel names them.")
print("=" * 70)
