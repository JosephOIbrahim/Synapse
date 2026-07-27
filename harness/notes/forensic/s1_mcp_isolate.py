"""S1: isolate the two /mcp hangs and re-run the three COP calls with real args.

Each tool gets a FRESH mcp_server process and is the FIRST tool called, so
ordering, stream desync and connection reuse are all ruled out. 180s ceiling
distinguishes "slow" from "does not return".

Emits scratchpad/mcp_isolate.json
"""
import json
import os
import queue
import subprocess
import sys
import threading
import time

REPO = r"C:\Users\User\SYNAPSE"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "s1_artifacts", "mcp_isolate.json")

CASES = [
    ("synapse_scout", {"query": "hou.LopNode editableStage", "k": 2}, 180.0),
    ("synapse_inspect_stage", {"target_path": "/stage", "timeout": 20}, 180.0),
    ("cops_read_layer_info", {"node": "/obj"}, 45.0),
    ("cops_analyze_render", {"node": "/obj"}, 45.0),
    ("cops_temporal_analysis", {"node": "/obj"}, 45.0),
]


def run_case(tool, args, timeout):
    proc = subprocess.Popen(
        [sys.executable, "mcp_server.py"], cwd=REPO,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", bufsize=1,
    )
    q = queue.Queue()
    errbuf = []

    def rd(stream, tag):
        for line in stream:
            q.put((tag, line))
        q.put((tag, None))

    threading.Thread(target=rd, args=(proc.stdout, "out"), daemon=True).start()
    threading.Thread(target=rd, args=(proc.stderr, "err"), daemon=True).start()

    state = {"id": 0}

    def send(method, params=None, notify=False):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if not notify:
            state["id"] += 1
            msg["id"] = state["id"]
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        return None if notify else state["id"]

    def wait_for(want, tmo):
        t0 = time.time()
        while time.time() - t0 < tmo:
            try:
                tag, line = q.get(timeout=1.0)
            except queue.Empty:
                continue
            if line is None:
                continue
            if tag == "err":
                errbuf.append(line.rstrip())
                continue
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == want:
                msg["__elapsed__"] = round(time.time() - t0, 2)
                return msg
        return {"__timeout__": True, "elapsed": round(time.time() - t0, 2)}

    rec = {"tool": tool, "args": args, "ceiling_s": timeout}
    try:
        i = send("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                "clientInfo": {"name": "s1-isolate", "version": "1"}})
        init = wait_for(i, 60)
        if "result" not in init:
            rec["result"] = "INIT_FAILED"
            return rec
        send("notifications/initialized", {}, notify=True)
        t0 = time.time()
        i = send("tools/call", {"name": tool, "arguments": args})
        res = wait_for(i, timeout)
        if res.get("__timeout__"):
            rec.update(result="NO_RESPONSE", elapsed=res["elapsed"])
        else:
            try:
                text = res["result"]["content"][0].get("text", "")
            except Exception:
                text = json.dumps(res.get("result") or res.get("error"), default=str)
            rec.update(result="RESPONDED", elapsed=round(time.time() - t0, 2),
                       bytes=len(text), head=text[:700])
    finally:
        rec["stderr_tail"] = errbuf[-14:]
        try:
            proc.terminate(); proc.wait(timeout=5)
        except Exception:
            proc.kill()
    return rec


out = {"_meta": {"surface": "external MCP stdio, ONE fresh server per case, tool called FIRST",
                 "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "scene": "untitled.hip (empty)"}}
for tool, args, tmo in CASES:
    print(f"\n=== {tool} (ceiling {tmo}s) ===")
    r = run_case(tool, args, tmo)
    out[tool] = r
    print(f"  -> {r.get('result')} in {r.get('elapsed')}s "
          f"bytes={r.get('bytes')} head={str(r.get('head'))[:160]!r}")
    for line in r.get("stderr_tail", [])[-6:]:
        print("   stderr|", line[:200])
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=str)
print("\nwrote", OUT)
