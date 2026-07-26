# ASSAYER live-bridge corroboration for hou.Node.getPDGGraphContext (H3a).
# SEQUENTIAL SINGLE-LINE probes only -- execute_python breaks on multi-line literals.
import asyncio, json, sys
import websockets

URL = "ws://localhost:9999/synapse"

LINES = [
    "import hou; print('BUILD=' + hou.applicationVersionString())",
    "import hou; print('CTRL_POS_hou.node=' + str(hasattr(hou, 'node')))",
    "import hou; print('CTRL_NEG_zzz=' + str(hasattr(hou, 'zzz_indep_control_must_not_exist')))",
    "import hou; print('CTRL_NEG_lopNetworks=' + str(hasattr(hou, 'lopNetworks')))",
    "import hou; print('hasattr_hou_Node=' + str(hasattr(hou, 'Node')))",
    "import hou; print('TARGET_hasattr_hou.Node.getPDGGraphContext=' + str(hasattr(hou.Node, 'getPDGGraphContext')))",
    "import hou; print('TARGET_in_dir_hou.Node=' + str('getPDGGraphContext' in dir(hou.Node)))",
    "import hou; print('dir_len_hou.Node=' + str(len(dir(hou.Node))))",
    "import hou; print('hasattr_hou_TopNode=' + str(hasattr(hou, 'TopNode')))",
    "import hou; print('TopNode_hasattr_getPDGGraphContext=' + str(hasattr(hou.TopNode, 'getPDGGraphContext')))",
    "import hou; print('TopNode_related=' + repr(sorted(a for a in dir(hou.TopNode) if any(k in a.lower() for k in ('pdg','cook','task','dirty','cancel')))))",
]


async def main():
    try:
        ws = await websockets.connect(URL, open_timeout=8, max_size=None)
    except Exception as e:
        print("BRIDGE_UNREACHABLE %s: %s" % (type(e).__name__, e))
        return 3
    async with ws:
        try:
            g = await asyncio.wait_for(ws.recv(), timeout=3)
            print("GREETING: " + str(g)[:200])
        except Exception:
            print("GREETING: (none)")
        for i, code in enumerate(LINES):
            msg = {"id": "assayer%d" % i, "type": "execute_python",
                   "command": "execute_python", "payload": {"content": code}}
            await ws.send(json.dumps(msg))
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=40)
            except Exception as e:
                print("PROBE %d NO_REPLY %s" % (i, type(e).__name__))
                continue
            print("PROBE %d >> %s" % (i, str(r)[:900]))
    return 0

sys.exit(asyncio.run(main()))
