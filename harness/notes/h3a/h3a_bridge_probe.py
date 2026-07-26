"""H3a group-C existence probe over the LIVE SYNAPSE WS bridge.

Sequential SINGLE-LINE probes only (each payload is one physical line: exec(<repr>)).
Read-only: dir()/getattr introspection, atomic=False, no mutation.
Build string is derived from the probe itself, never assumed.
"""
import asyncio, json, sys, os

import websockets

URL = "ws://localhost:9999/synapse"

SRC = r'''
import json as _j, difflib as _dl, importlib as _il
_path = {path!r}
_parts = _path.split('.')
_root = _parts[0]
try:
    _obj = _il.import_module(_root)
except Exception as _e:
    result = _j.dumps({{"symbol": _path, "verdict": "UNVERIFIABLE", "resolved_through": _root, "evidence": "import %s failed -> %s: %s" % (_root, type(_e).__name__, _e), "type": None, "signature": None, "dir_size_of_parent": None, "near_misses": None}})
else:
    _cur = _root
    _out = None
    for _seg in _parts[1:]:
        _d = dir(_obj)
        if _seg not in _d:
            _nm = _dl.get_close_matches(_seg, _d, n=5, cutoff=0.5)
            _out = {{"symbol": _path, "verdict": "ABSENT", "resolved_through": _cur, "evidence": "'%s' not in dir(%s) (%d names); nearest existing: %s" % (_seg, _cur, len(_d), _nm if _nm else 'none within cutoff 0.5'), "type": None, "signature": None, "dir_size_of_parent": len(_d), "near_misses": _nm}}
            break
        _obj = getattr(_obj, _seg)
        _cur = _cur + '.' + _seg
    if _out is None:
        try:
            import inspect as _in
            _sig = str(_in.signature(_obj))
        except Exception:
            _sig = None
        _doc = (getattr(_obj, '__doc__', '') or '')[:160]
        _out = {{"symbol": _path, "verdict": "EXISTS", "resolved_through": _cur, "evidence": "resolved; __doc__[:160]=%r" % _doc, "type": type(_obj).__name__, "signature": _sig, "dir_size_of_parent": None, "near_misses": None}}
    result = _j.dumps(_out)
'''

POSITIVE = ["hou.node", "hou.Node.type", "hou.undos.group"]
NEGATIVE = ["hou.zzz_h3a_control_must_not_exist", "hou.pdg", "hou.secure",
            "hou.lopNetworks", "hou.updateGraphTick"]


def one_liner(path):
    return "exec(" + repr(SRC.format(path=path)) + ")"


async def send(ws, mid, code):
    msg = {"id": mid, "type": "execute_python",
           "payload": {"content": code, "atomic": False, "dry_run": False}}
    await ws.send(json.dumps(msg))
    raw = await asyncio.wait_for(ws.recv(), timeout=60)
    return json.loads(raw)


async def probe_symbol(ws, mid, path):
    resp = await send(ws, mid, one_liner(path))
    if not resp.get("success"):
        return {"symbol": path, "verdict": "UNVERIFIABLE", "resolved_through": None,
                "evidence": "bridge transport error -> %s" % str(resp.get("error"))[:220],
                "type": None, "signature": None,
                "dir_size_of_parent": None, "near_misses": None}
    inner = (resp.get("data") or {}).get("result")
    try:
        return json.loads(inner)
    except Exception:
        return {"symbol": path, "verdict": "UNVERIFIABLE", "resolved_through": None,
                "evidence": "unparseable probe result -> %s" % str(inner)[:220],
                "type": None, "signature": None,
                "dir_size_of_parent": None, "near_misses": None}


async def main():
    manifest = json.load(open("harness/notes/h3a_symbols.json"))
    group = sys.argv[sys.argv.index("--group") + 1]
    out_path = sys.argv[sys.argv.index("--out") + 1]
    entries = manifest["groups"][group]

    async with websockets.connect(URL, open_timeout=15, max_size=None) as ws:
        r = await send(ws, "build", "result = __import__('hou').applicationVersionString()")
        build = (r.get("data") or {}).get("result") if r.get("success") else None
        r2 = await send(ws, "uiavail", "result = str(__import__('hou').isUIAvailable())")
        ui_avail = (r2.get("data") or {}).get("result") if r2.get("success") else None
        r3 = await send(ws, "pyver", "result = __import__('sys').version")
        pyver = (r3.get("data") or {}).get("result") if r3.get("success") else None
        r4 = await send(ws, "exe", "result = __import__('sys').executable")
        exe = (r4.get("data") or {}).get("result") if r4.get("success") else None
        r5 = await send(ws, "thr", "result = str(__import__('threading').current_thread() is __import__('threading').main_thread())")
        on_main = (r5.get("data") or {}).get("result") if r5.get("success") else None

        pos = [await probe_symbol(ws, "p%d" % i, s) for i, s in enumerate(POSITIVE)]
        neg = [await probe_symbol(ws, "n%d" % i, s) for i, s in enumerate(NEGATIVE)]
        results = [await probe_symbol(ws, "s%d" % i, e["symbol"])
                   for i, e in enumerate(entries)]

    positive_ok = all(x["verdict"] == "EXISTS" for x in pos)
    negative_ok = all(x["verdict"] == "ABSENT" for x in neg)
    counts = {}
    for x in results:
        counts[x["verdict"]] = counts.get(x["verdict"], 0) + 1

    doc = {
        "schema": "h3a_probe/v1",
        "producer": "harness/notes/h3a/h3a_bridge_probe.py",
        "group": group,
        "probe_path": "LIVE_BRIDGE ws://localhost:9999/synapse",
        "interpreter": {
            "executable": exe, "python": pyver,
            "thread_is_main": on_main,
            "houdini_build": build,
            "ui_available": ui_avail,
        },
        "controls_ok": bool(positive_ok and negative_ok),
        "controls": {"positive_ok": positive_ok, "negative_ok": negative_ok,
                     "positive": pos, "negative": neg},
        "counts": dict(counts, total=len(results)),
        "results": results,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(doc, f, indent=2)
    print(json.dumps(doc, indent=2))

asyncio.run(main())
