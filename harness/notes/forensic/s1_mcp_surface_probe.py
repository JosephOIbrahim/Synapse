"""S1: probe the ACTUAL external /mcp surface, not the /synapse WS path.

Spawns `python mcp_server.py` as an MCP stdio server and speaks JSON-RPC to it.
Read-only tools only. Every call is bounded; a hang is recorded as a RESULT
(v5.36.3 documents synapse_inspect_scene hanging on exactly this surface while
working over WS, so "it hangs" is a finding, not a probe failure).

Emits scratchpad/mcp_surface_probe.json
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
OUT = os.path.join(HERE, "s1_artifacts", "mcp_surface_probe.json")
sys.path.insert(0, os.path.join(REPO, "python"))
from synapse.mcp import _tool_registry as R  # noqa: E402

EXCLUDE = {
    "houdini_capture_viewport": "writes an image file to disk -- outside the S1 fence",
    "synapse_propose_graph": "would mutate the ProposalStore",
    "synapse_validate_frame": "requires an on-disk image fixture",
}

ARGS = {
    "houdini_get_parm": {"node": "/obj", "parm": "tx"},
    "houdini_get_usd_attribute": {"prim_path": "/", "attribute_name": "kind"},
    "tops_get_work_items": {"node": "/tasks"},
    "tops_get_dependency_graph": {"topnet_path": "/tasks"},
    "tops_get_cook_stats": {"node": "/tasks"},
    "tops_query_items": {"node": "/tasks", "query_attribute": "id", "filter_value": "0"},
    "tops_diagnose": {"node": "/tasks"},
    "tops_pipeline_status": {"topnet_path": "/tasks"},
    "houdini_read_material": {"prim_path": "/"},
    "synapse_knowledge_lookup": {"query": "karma render settings"},
    "synapse_inspect_node": {"node": "/obj"},
    "houdini_network_explain": {"root_path": "/obj"},
    "synapse_search": {"query": "lighting"},
    "synapse_recall": {"query": "lighting"},
    "synapse_memory_query": {"query": "lighting"},
    # the 8 tools advertised by list_tools() but absent from the 120-entry registry
    "synapse_scout": {"query": "hou.LopNode editableStage", "k": 2},
    "synapse_inspect_stage": {"target_path": "/stage", "timeout": 20},
}
EXTRA_TOOLS = [
    "synapse_group_scene", "synapse_group_render", "synapse_group_usd",
    "synapse_group_tops", "synapse_group_memory", "synapse_group_cops",
    "synapse_scout", "synapse_inspect_stage",
]

CALL_TIMEOUT = 45.0

proc = subprocess.Popen(
    [sys.executable, "mcp_server.py"], cwd=REPO,
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    text=True, encoding="utf-8", bufsize=1,
)

q: "queue.Queue[str]" = queue.Queue()


def reader():
    for line in proc.stdout:
        q.put(line)
    q.put(None)


threading.Thread(target=reader, daemon=True).start()

_id = 0


def send(method, params=None, notify=False):
    global _id
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if not notify:
        _id += 1
        msg["id"] = _id
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    return None if notify else _id


def wait_for(want_id, timeout):
    t0 = time.time()
    while True:
        remaining = timeout - (time.time() - t0)
        if remaining <= 0:
            return {"__timeout__": True, "elapsed": round(time.time() - t0, 2)}
        try:
            line = q.get(timeout=min(remaining, 1.0))
        except queue.Empty:
            continue
        if line is None:
            return {"__eof__": True, "elapsed": round(time.time() - t0, 2)}
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == want_id:
            msg["__elapsed__"] = round(time.time() - t0, 2)
            return msg


out = {"_meta": {"surface": "external MCP stdio (python mcp_server.py)",
                 "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "call_timeout_s": CALL_TIMEOUT,
                 "scene": "untitled.hip (empty)",
                 "exclusions": EXCLUDE}}

try:
    i = send("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                            "clientInfo": {"name": "s1-probe", "version": "1"}})
    init = wait_for(i, 45)
    out["_initialize"] = {"ok": "result" in init, "elapsed": init.get("__elapsed__"),
                          "raw": json.dumps(init)[:400]}
    print("initialize:", out["_initialize"])
    if "result" not in init:
        raise SystemExit("initialize failed")

    send("notifications/initialized", {}, notify=True)

    i = send("tools/list")
    tl = wait_for(i, 60)
    advertised = [t["name"] for t in tl.get("result", {}).get("tools", [])]
    out["_tools_list"] = {"count": len(advertised), "elapsed": tl.get("__elapsed__"),
                          "names": advertised}
    print(f"tools/list: {len(advertised)} advertised in {tl.get('__elapsed__')}s")
    registry = {n for n, *_ in R.TOOL_DEFS}
    out["_delta"] = {
        "advertised_not_in_registry": sorted(set(advertised) - registry),
        "registry_not_advertised": sorted(registry - set(advertised)),
    }
    print("advertised beyond the 120-entry registry:", out["_delta"]["advertised_not_in_registry"])

    targets = [n for n, c, b, d, s, ro, de, idm in R.TOOL_DEFS if ro] + EXTRA_TOOLS
    print(f"\ncalling {len(targets)} read-only tools over /mcp\n")
    for name in targets:
        if name in EXCLUDE:
            out[name] = {"skipped": EXCLUDE[name]}
            print(f"  SKIP  {name}")
            continue
        if name not in advertised:
            out[name] = {"error": "NOT_ADVERTISED"}
            print(f"  NOT-ADVERTISED {name}")
            continue
        i = send("tools/call", {"name": name, "arguments": ARGS.get(name, {})})
        res = wait_for(i, CALL_TIMEOUT)
        if res.get("__timeout__"):
            out[name] = {"result": "HANG", "elapsed": res["elapsed"],
                         "detail": f"no JSON-RPC response within {CALL_TIMEOUT}s"}
            print(f"  {name:32s} *** HANG *** ({res['elapsed']}s)")
            # drain whatever late reply arrives so it does not desync the stream
            continue
        if res.get("__eof__"):
            out[name] = {"result": "SERVER_EOF", "elapsed": res["elapsed"]}
            print(f"  {name:32s} *** SERVER DIED ***")
            break
        body = res.get("result") or res.get("error")
        text = ""
        try:
            text = body["content"][0].get("text", "")
        except Exception:
            text = json.dumps(body, default=str)
        out[name] = {"result": "OK", "elapsed": res.get("__elapsed__"),
                     "is_error": bool(res.get("error")) or bool((res.get("result") or {}).get("isError")),
                     "bytes": len(text), "head": text[:600],
                     "args": ARGS.get(name, {})}
        print(f"  {name:32s} {res.get('__elapsed__'):5.1f}s bytes={len(text):6d} "
              f"head={text[:80]!r}")
finally:
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
    print("\nwrote", OUT)
