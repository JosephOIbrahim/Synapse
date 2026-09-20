# bp8_repro_ws.py - CTO seat, 2026-09-20. Server-side half of the BP7_VERDICT.md GUI repro, run over
# SYNAPSE's own websocket so the ONE UNKNOWN in the verdict gets a number: does the server block on
# turn 2? This does NOT observe the panel (H1's spinner is Joe's to see); it measures what the panel
# would have received: elapsed seconds per turn, and whether the reply carries `response`/`tier`
# (ws_bridge.py drops any dict without them). No Save-As is performed, so a turn-2 stall here is
# NOT the H6 memory-store path. Sends the verdict's two messages verbatim; they act on the open scene.
import json, sys, time, uuid
from websockets.sync.client import connect

URL = "ws://localhost:9999/synapse"
WAIT = 45.0  # past the server's 30 s slow-op budget
TURNS = ["scatter rocks on the ground", "add size variation"]


def turn(ws, seq, text):
    cid = uuid.uuid4().hex[:16]
    ws.send(json.dumps({"id": cid, "payload": {"message": text, "context": {}}, "protocol_version": "4.0.0",
                        "sequence": seq, "timestamp": time.time(), "type": "route_chat"}))
    t0, seen = time.monotonic(), []
    while time.monotonic() - t0 < WAIT:
        try:
            raw = ws.recv(timeout=max(0.1, WAIT - (time.monotonic() - t0)))
        except TimeoutError:
            break
        try:
            msg = json.loads(raw)
        except ValueError:
            continue
        inner = msg.get("data") if isinstance(msg.get("data"), dict) else {}
        seen.append({"t": round(time.monotonic() - t0, 2), "id_match": msg.get("id") == cid,
                     "keys": sorted(msg)[:8], "data_keys": sorted(inner)[:10]})
        if msg.get("id") == cid:
            return {"text": text, "replied": True, "elapsed_s": round(time.monotonic() - t0, 2),
                    "success": msg.get("success"), "error": str(msg.get("error"))[:200] if msg.get("error") else None,
                    "has_response_key": "response" in inner, "has_tier_key": "tier" in inner, "tier": inner.get("tier"),
                    "response_head": str(inner.get("response", ""))[:160], "other_messages": seen[:-1]}
    return {"text": text, "replied": False, "elapsed_s": round(time.monotonic() - t0, 2), "other_messages": seen}


out = {"url": URL, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "turns": []}
try:
    with connect(URL, open_timeout=5) as ws:
        for i, text in enumerate(TURNS, 1):
            out["turns"].append(turn(ws, i, text))
except Exception as e:  # noqa: BLE001
    out["error"] = f"{type(e).__name__}: {e}"[:300]
print(json.dumps(out, indent=1))
