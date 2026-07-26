"""ASSAYER independent probe -- LIVE BRIDGE leg. Sequential SINGLE-LINE probes only.
Handler returns exec_locals['result'], so every probe assigns `result`."""
import asyncio, json
import websockets

URL = "ws://localhost:9999/synapse"

PROBES = [
    ("BUILD",
     'import hou; result = "BUILD=" + hou.applicationVersionString() + " TUPLE=" + repr(hou.applicationVersion())'),
    ("CONTROLS",
     'import hou; result = "CTRL_POS=%r CTRL_NEG1=%r CTRL_NEG2=%r" % (hasattr(hou,"node"), hasattr(hou,"zzz_indep_control_must_not_exist"), hasattr(hou,"lopNetworks"))'),
    ("TARGET",
     'import hou; result = "SEG1_RopNode=%r SEG2_render=%r INDIR=%r" % (hasattr(hou,"RopNode"), hasattr(hou.RopNode,"render"), "render" in dir(hou.RopNode))'),
    ("TARGET_REPR",
     'import hou; result = "REPR=%r LEN_DIR_RopNode=%d" % (getattr(hou.RopNode,"render",None), len(dir(hou.RopNode)))'),
    ("RELATED",
     'import hou; result = "RELATED=" + ",".join(sorted(n for n in dir(hou.RopNode) if any(k in n.lower() for k in ("render","cancel","abort","interrupt","kill","stop","cook","background"))))'),
    ("MODLEVEL",
     'import hou; result = "MOD=" + ",".join("%s:%s" % (n, "EXISTS" if hasattr(hou,n) else "ABSENT") for n in ("InterruptableOperation","updateProgressAndCheckForInterrupt","OperationInterrupted","interruptRender","abortRender","killRender","setUpdateMode","updateModeSetting"))'),
]


async def main():
    async with websockets.connect(URL, open_timeout=15, max_size=None) as ws:
        for i, (label, code) in enumerate(PROBES):
            msg = {
                "id": "assayer_%d" % i,
                "type": "execute_python",
                "payload": {"content": code, "atomic": False},
            }
            await ws.send(json.dumps(msg))
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=60)
            except Exception as e:
                print("[%s] NO_REPLY %s" % (label, type(e).__name__))
                continue
            try:
                obj = json.loads(raw)
                print("[%s] success=%r result=%s" % (label, obj.get("success"),
                                                     (obj.get("data") or {}).get("result")))
                if obj.get("error"):
                    print("      error=%s" % obj["error"])
            except Exception:
                print("[%s] RAW %s" % (label, raw))
            print()

asyncio.run(main())
