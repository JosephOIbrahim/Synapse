# ASSAYER live-bridge corroboration, phase 2: the live interpreter writes its own
# verdict file (execute_python returns {"executed": true} only -- no stdout capture).
# SINGLE-LINE probe. Controls embedded in the same line as the target.
import asyncio, json, sys
import websockets

URL = "ws://localhost:9999/synapse"
OUT = "C:/Users/User/SYNAPSE/.claude/worktrees/h3a-cancel-probe/harness/notes/h3a/bridge_result.json"

CODE = (
    'import hou, json; '
    'D = {"build": hou.applicationVersionString(), '
    '"ctrl_pos_hou_node": hasattr(hou, "node"), '
    '"ctrl_neg_zzz": hasattr(hou, "zzz_indep_control_must_not_exist"), '
    '"ctrl_neg_hou_lopNetworks": hasattr(hou, "lopNetworks"), '
    '"hasattr_hou_Node": hasattr(hou, "Node"), '
    '"TARGET_hasattr_hou_Node_getPDGGraphContext": hasattr(hou.Node, "getPDGGraphContext"), '
    '"TARGET_in_dir_hou_Node": "getPDGGraphContext" in dir(hou.Node), '
    '"dir_len_hou_Node": len(dir(hou.Node)), '
    '"hou_Node_related": sorted(a for a in dir(hou.Node) if any(k in a.lower() for k in ("pdg", "cook", "task", "dirty", "cancel"))), '
    '"hasattr_hou_TopNode": hasattr(hou, "TopNode"), '
    '"TopNode_hasattr_getPDGGraphContext": hasattr(hou.TopNode, "getPDGGraphContext"), '
    '"TopNode_getPDGGraphContext_in_dir": "getPDGGraphContext" in dir(hou.TopNode), '
    '"dir_len_hou_TopNode": len(dir(hou.TopNode)), '
    '"hou_TopNode_related": sorted(a for a in dir(hou.TopNode) if any(k in a.lower() for k in ("pdg", "cook", "task", "dirty", "cancel")))}; '
    'open("%s", "w").write(json.dumps(D, indent=2, sort_keys=True))' % OUT
)


async def main():
    async with websockets.connect(URL, open_timeout=8, max_size=None) as ws:
        msg = {"id": "assayer_dump", "type": "execute_python", "payload": {"content": CODE}}
        await ws.send(json.dumps(msg))
        r = await asyncio.wait_for(ws.recv(), timeout=60)
        print("REPLY: " + str(r)[:600])
    return 0

sys.exit(asyncio.run(main()))
