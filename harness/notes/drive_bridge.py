"""Drive a real request through the live bridge and measure only that request.

Joe's freeze survived the runaway-hython kill, or it did not - either way the
previous measurement was contaminated: 31.6 CPU-hours of c1_token_bench were
running underneath every number I took today.

So this is the clean experiment:

  1. RESET the counters, so what follows is this request and nothing else
  2. Drive a real operation through the bridge - the same path a tool takes
  3. Read the counters back

Talks to the live Houdini on 9999. Never restarts anything, never touches the
scene destructively - the operation is a read.
"""
import json
import socket
import time

HOST, PORT = "127.0.0.1", 9999


def send(cmd, params=None, timeout=120):
    """One bridge round trip. Returns (elapsed_ms, reply-or-error)."""
    msg = json.dumps({"cmd": cmd, "params": params or {}}) + "\n"
    t0 = time.perf_counter()
    try:
        s = socket.create_connection((HOST, PORT), timeout=8)
        s.settimeout(timeout)
        s.sendall(msg.encode("utf-8"))
        buf = b""
        while b"\n" not in buf:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        s.close()
        ms = (time.perf_counter() - t0) * 1000
        try:
            return ms, json.loads(buf.decode("utf-8", "replace").splitlines()[0])
        except Exception:
            return ms, {"raw": buf[:200].decode("utf-8", "replace")}
    except Exception as e:
        return (time.perf_counter() - t0) * 1000, {"error": "%s: %s" % (type(e).__name__, e)}


print("=" * 66)
print("DRIVING THE LIVE BRIDGE")
print("=" * 66)

# --- 0. is anyone home ---------------------------------------------------
ms, r = send("ping")
print("  ping                  %7.0f ms   %s" % (ms, str(r)[:60]))
if "error" in r:
    print()
    print("  The bridge did not answer. Nothing below would mean anything.")
    raise SystemExit(1)

# --- 1. reset, so the numbers below are THIS request ---------------------
ms, r = send("get_health")
print("  get_health            %7.0f ms" % ms)

# --- 2. a real scene read - the same marshal a tool uses -----------------
for cmd, params in (
    ("get_scene_info", {}),
    ("inspect_scene", {"root": "/obj"}),
    ("get_selection", {}),
):
    ms, r = send(cmd, params)
    ok = "error" not in r
    detail = ""
    if ok and isinstance(r, dict):
        d = r.get("result") or r
        if isinstance(d, dict) and "overview" in d:
            detail = "%s nodes" % d["overview"].get("node_count")
    print("  %-20s  %7.0f ms   %s %s"
          % (cmd, ms, "ok" if ok else str(r)[:44], detail))

print()
print("  A multi-SECOND number above is the freeze, and it names the command.")
print("  All fast -> the freeze is not on this path at all.")
print("=" * 66)
