"""hy_parity.py -- GUI vs headless parity diff for the read-only verb surface.

The resilience signal is not "headless is green". It is the DELTA between the
two lanes: a verb that behaves differently through the WebSocket transport than
it does called in-process is a bug in the abstraction, every time, with no
judgement call required.

Plain Python. No hou, no hython, no license seat -- it is a WebSocket client
against the SYNAPSE server already running inside the GUI session. Endpoint is
resolved from ~/.synapse/bridge.json (the sidecar bridge_endpoint.py publishes),
falling back to localhost:9999.

SAFETY: two verbs are excluded from the live run even though _READ_ONLY_COMMANDS
contains them. emergency_halt and render_farm_cancel are named like actions and
render_farm_cancel took 834ms headless, which is not the shape of a no-op.
Firing those at a working artist session is not the same as firing them in a
throwaway process. They are reported as 'excluded', never as 'ok'.

Run:  python tools/hy_parity.py
"""

import asyncio
import json
import os
import sys
import time
import uuid

import websockets

HERE = os.path.dirname(os.path.abspath(__file__))
HEADLESS = os.path.join(HERE, "_hy_verbs_sweep.json")
OUT = os.path.join(HERE, "_hy_parity_gui.json")

EXCLUDED = {"emergency_halt", "render_farm_cancel"}
RECV_TIMEOUT = 20.0
# hwebserver backend (production, inside Houdini) serves at /synapse; the
# standalone websocket.py backend accepts any path, so /synapse works for both.
# Connecting to the bare root gets an HTTP 400 from hwebserver.
SYNAPSE_PATH = os.environ.get("SYNAPSE_PATH", "/synapse")


UI_MARKERS = ("hou.ui", "isUIAvailable", "SceneViewer", "curDesktop",
              "paneTabOfType", "flipbook", "graphical")


def resolve_endpoint():
    p = os.path.join(os.path.expanduser("~"), ".synapse", "bridge.json")
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return d.get("host", "localhost"), int(d.get("port", 9999)), d
    except Exception:
        return "localhost", 9999, {"note": "sidecar absent, using default"}


def classify_error(msg):
    """Same buckets the headless sweep used, so the two tables are comparable."""
    low = str(msg).lower()
    if any(m.lower() in low for m in UI_MARKERS):
        return "headless_fail"
    hints = ("missing required", "expected one of", "couldn't find",
            "provide", "must be", "invalid", "no node", "isn't a")
    if any(h in low for h in hints):
        return "needs_params"
    return "error"


def unpack(resp):
    """SynapseResponse is {id, success, data, ...}. Be liberal about the
    error field name -- the point is comparability, not schema archaeology."""
    if resp.get("success"):
        return "ok", json.dumps(resp.get("data"), default=str)[:220]
    err = (resp.get("error") or resp.get("message")
           or resp.get("data") or "unsuccessful, no error field")
    if isinstance(err, dict):
        err = err.get("message") or json.dumps(err, default=str)
    return classify_error(err), str(err)[:220]


async def call(ws, verb):
    cid = str(uuid.uuid4())
    await ws.send(json.dumps({"type": verb, "id": cid, "payload": {}}))
    deadline = time.time() + RECV_TIMEOUT
    while time.time() < deadline:
        raw = await asyncio.wait_for(ws.recv(), timeout=max(0.1, deadline - time.time()))
        try:
            msg = json.loads(raw)
        except Exception:
            continue
        # Match by id: the server may emit greetings/telemetry unsolicited.
        if isinstance(msg, dict) and msg.get("id") == cid:
            return msg
    raise asyncio.TimeoutError("no response matching id within %.0fs" % RECV_TIMEOUT)


async def main():
    with open(HEADLESS, encoding="utf-8") as f:
        head = json.load(f)
    head_status = {r["verb"]: r["status"] for r in head["results"]}
    verbs = sorted(head_status)

    host, port, sidecar = resolve_endpoint()
    url = "ws://%s:%d%s" % (host, port, SYNAPSE_PATH)
    print("[parity] headless artifact build %s (%d verbs)" % (head["build"], len(verbs)))
    print("[parity] GUI endpoint %s  sidecar=%s" % (url, sidecar))

    report = {"endpoint": url, "sidecar": sidecar,
              "headless_build": head["build"], "results": [], "excluded": sorted(EXCLUDED)}

    async with websockets.connect(url, max_size=None, open_timeout=15,
                                  ping_interval=None, compression=None,
                                  close_timeout=5.0) as ws:
        for i, verb in enumerate(verbs, 1):
            if verb in EXCLUDED:
                rec = {"verb": verb, "gui": "excluded", "headless": head_status[verb]}
                report["results"].append(rec)
                print("  [%2d/%2d] %-40s EXCLUDED (live-session safety)" % (i, len(verbs), verb))
                continue
            t = time.perf_counter()
            try:
                resp = await call(ws, verb)
                status, detail = unpack(resp)
            except Exception as e:
                status, detail = "transport_error", "%s: %s" % (type(e).__name__, e)
            rec = {"verb": verb, "gui": status, "headless": head_status[verb],
                   "detail": detail, "ms": round((time.perf_counter() - t) * 1000, 1)}
            report["results"].append(rec)
            flag = "" if rec["gui"] == rec["headless"] else "   <-- DIFF"
            print("  [%2d/%2d] %-40s gui=%-15s headless=%-15s%s"
                  % (i, len(verbs), verb, status, rec["headless"], flag))
    return report


if __name__ == "__main__":
    rep = asyncio.run(main())

    compared = [r for r in rep["results"] if r["gui"] != "excluded"]
    diffs = [r for r in compared if r["gui"] != r["headless"]]
    # A verb that fails headless but works in the GUI is the interesting class:
    # it is a real environmental dependency, not noise.
    gui_only = [r for r in diffs if r["gui"] == "ok" and r["headless"] != "ok"]
    head_only = [r for r in diffs if r["headless"] == "ok" and r["gui"] != "ok"]
    rep["summary"] = {
        "compared": len(compared),
        "excluded": len(rep["excluded"]),
        "agree": len(compared) - len(diffs),
        "diff": len(diffs),
        "gui_ok_headless_not": [r["verb"] for r in gui_only],
        "headless_ok_gui_not": [r["verb"] for r in head_only],
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2, default=str)

    s = rep["summary"]
    print()
    print("=== PARITY SUMMARY ===")
    print("  compared %d  agree %d  diff %d  excluded %d"
          % (s["compared"], s["agree"], s["diff"], s["excluded"]))
    if s["gui_ok_headless_not"]:
        print("  GUI-only (real environmental dependency): %s"
              % ", ".join(s["gui_ok_headless_not"]))
    if s["headless_ok_gui_not"]:
        print("  HEADLESS-only (transport or GUI-state defect): %s"
              % ", ".join(s["headless_ok_gui_not"]))
    for r in diffs:
        print("  DIFF %-38s gui=%-15s headless=%-15s %s"
              % (r["verb"], r["gui"], r["headless"], (r.get("detail") or "")[:90]))
    print("=== report: %s ===" % OUT)
    sys.exit(0)
