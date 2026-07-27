"""S1 live read-only sweep, phase 2.

Every registry tool with read_only=True, minus three exclusions (see EXCLUDE).
One connection per command so a hang cannot poison the sweep.
Nothing is created, deleted, or written to disk in the Houdini process.

Emits scratchpad/live_probe_ro2.json
"""
import asyncio
import json
import os
import sys
import time

REPO = r"C:\Users\User\SYNAPSE"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "s1_artifacts", "ws_readonly_sweep.json")
sys.path.insert(0, os.path.join(REPO, "python"))

import websockets  # noqa: E402
from synapse.mcp import _tool_registry as R  # noqa: E402

URL = "ws://localhost:9999/synapse"
PROTOCOL_VERSION = "5.4.0"

EXCLUDE = {
    "houdini_capture_viewport": "writes an image file to disk -- outside the S1 fence",
    "synapse_propose_graph": "requires a graph proposal payload; would mutate the ProposalStore",
    "synapse_validate_frame": "requires an on-disk image path; no read-only fixture",
}

# Arguments chosen so the command exercises the handler on paths that EXIST in
# the live (empty) scene. /obj and /stage always exist in a Houdini session.
ARGS = {
    "houdini_get_parm": {"node": "/obj", "parm": "tx"},
    "houdini_stage_info": {},
    "houdini_get_usd_attribute": {"prim_path": "/", "attribute_name": "kind"},
    "tops_get_work_items": {"node": "/tasks"},
    "tops_get_dependency_graph": {"topnet_path": "/tasks"},
    "tops_get_cook_stats": {"node": "/tasks"},
    "tops_query_items": {"node": "/tasks", "query_attribute": "id", "filter_value": "0"},
    "tops_diagnose": {"node": "/tasks"},
    "tops_pipeline_status": {"topnet_path": "/tasks"},
    "houdini_query_prims": {},
    "synapse_validate_ordering": {},
    "houdini_read_material": {"prim_path": "/"},
    "synapse_knowledge_lookup": {"query": "karma render settings"},
    "synapse_inspect_selection": {},
    "synapse_inspect_scene": {},
    "synapse_inspect_node": {"node": "/obj"},
    "houdini_network_explain": {"root_path": "/obj"},
    "synapse_search": {"query": "lighting"},
    "synapse_recall": {"query": "lighting"},
    "synapse_memory_query": {"query": "lighting"},
    "synapse_live_metrics": {},
    "cops_read_layer_info": {"node": "/obj"},
    "cops_analyze_render": {"node": "/obj"},
    "cops_temporal_analysis": {"node": "/obj"},
}

DEFAULT_TIMEOUT = 20.0
TIMEOUTS = {
    "inspect_scene": 30.0, "knowledge_lookup": 45.0,
    "search": 30.0, "recall": 30.0, "memory_query": 30.0,
}

_seq = 0


def envelope(cmd_type, payload):
    global _seq
    _seq += 1
    return {"type": cmd_type, "id": f"{cmd_type}-s1probe2-{_seq}", "payload": payload or {},
            "sequence": 0, "timestamp": time.time(), "protocol_version": PROTOCOL_VERSION}


async def one_shot(cmd_type, payload, timeout):
    t0 = time.time()
    try:
        async with websockets.connect(URL, open_timeout=8, close_timeout=2) as ws:
            await ws.send(json.dumps(envelope(cmd_type, payload)))
            deadline = time.time() + timeout
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise asyncio.TimeoutError()
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                msg = json.loads(raw)
                if msg.get("type") in ("auth_required", "auth_ok", "welcome", "hello"):
                    continue
                return {"elapsed": round(time.time() - t0, 2), "response": msg}
    except asyncio.TimeoutError:
        return {"elapsed": round(time.time() - t0, 2), "error": "TIMEOUT",
                "detail": f"no response within {timeout}s"}
    except Exception as e:
        return {"elapsed": round(time.time() - t0, 2), "error": type(e).__name__, "detail": str(e)[:300]}


async def main():
    out = {"_meta": {"url": URL, "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "scene": "untitled.hip (empty)", "exclusions": EXCLUDE}}
    ro = [(n, c, b) for n, c, b, d, s, r, de, i in R.TOOL_DEFS if r]
    print(f"sweeping {len(ro)} read_only tools ({len(EXCLUDE)} excluded)")
    for name, cmd, builder in ro:
        if name in EXCLUDE:
            out[name] = {"skipped": EXCLUDE[name], "cmd": cmd}
            print(f"  SKIP  {name}")
            continue
        raw_args = ARGS.get(name, {})
        try:
            payload = builder(raw_args)
        except Exception as e:
            out[name] = {"cmd": cmd, "error": "PAYLOAD_BUILDER_RAISED",
                         "detail": f"{type(e).__name__}: {e}", "args": raw_args}
            print(f"  BUILDER-FAIL {name}: {e}")
            continue
        res = await one_shot(cmd, payload, TIMEOUTS.get(cmd, DEFAULT_TIMEOUT))
        res["cmd"] = cmd
        res["args"] = raw_args
        out[name] = res
        resp = res.get("response") or {}
        ok = resp.get("success")
        err = resp.get("error") or res.get("error")
        data = resp.get("data")
        size = len(json.dumps(data, default=str)) if data is not None else 0
        print(f"  {name:32s} ok={ok!s:5s} {res['elapsed']:5.1f}s bytes={size:6d} err={str(err)[:90]}")
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=str)
    print("done ->", OUT)


if __name__ == "__main__":
    asyncio.run(main())
