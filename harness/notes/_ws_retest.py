"""L1.F1 re-test: is the WS bridge actually reachable, or only advertised?"""
import asyncio, json, sys

try:
    import websockets
except ImportError:
    print("RESULT: websockets lib absent - cannot test")
    sys.exit(3)

URLS = ["ws://localhost:9999", "ws://localhost:9999/synapse", "ws://127.0.0.1:9999"]


async def probe(url):
    try:
        async with websockets.connect(url, open_timeout=6, max_size=None) as ws:
            try:
                g = await asyncio.wait_for(ws.recv(), timeout=3)
                greet = str(g)[:180]
            except Exception:
                greet = "(no greeting)"
            msg = {"id": "probe1", "type": "execute_python", "command": "execute_python",
                   "params": {"code": "import hou; print('BUILD=' + hou.applicationVersionString())"},
                   "code": "import hou; print('BUILD=' + hou.applicationVersionString())"}
            await ws.send(json.dumps(msg))
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=25)
                return ("OK", greet, str(r)[:400])
            except Exception as e:
                return ("CONNECTED_NO_REPLY", greet, type(e).__name__)
    except Exception as e:
        return ("FAIL", type(e).__name__, str(e)[:180])


async def main():
    for u in URLS:
        status, a, b = await probe(u)
        print(f"--- {u}")
        print(f"    {status}")
        print(f"    greeting: {a}")
        print(f"    reply   : {b}")
        print()

asyncio.run(main())
