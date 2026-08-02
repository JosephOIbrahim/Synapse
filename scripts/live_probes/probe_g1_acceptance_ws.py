"""LIVE PROBE — G1 acceptance re-probe over the WS transport (no MCP needed).

    python scripts/live_probes/probe_g1_acceptance_ws.py

Runs OUTSIDE Houdini against the live bridge on ws://127.0.0.1:9999.
Binary verdict against the cold-boot baseline in .claude/g1_acceptance.md:

  PASS  memory_write ok, no 'Program Files' in any returned path
  FAIL  the same WinError 5 on ...\\bin\\claude

Ping-first per house rule (a stale 'connected' signal is a known incident
class — memory: synapse-bridge-verification). Exit 0 only on PASS.
"""
import json
import os
import sys
import uuid
from pathlib import Path

try:
    from websockets.sync.client import connect
except ImportError:
    print("NEED the websockets package in this interpreter")
    sys.exit(2)


def _auth_key():
    k = os.environ.get("SYNAPSE_API_KEY", "").strip()
    if k:
        return k
    f = Path.home() / ".synapse" / "auth.key"
    if f.is_file():
        return f.read_text(encoding="utf-8").strip()
    return None


def rpc(ws, command, payload=None, timeout=30):
    mid = uuid.uuid4().hex[:12]
    ws.send(json.dumps({"id": mid, "type": command, "command": command,
                        "payload": payload or {}}))
    while True:
        msg = json.loads(ws.recv(timeout=timeout))
        if msg.get("id") == mid or msg.get("success") is not None:
            return msg


def main():
    # hwebserver mounts the handler at /synapse (hwebserver_adapter.py:93);
    # the bare root answers HTTP 400 to a WS upgrade.
    with connect("ws://127.0.0.1:9999/synapse", open_timeout=8) as ws:
        # Auth handshake only if the server opens with auth_required.
        try:
            first = json.loads(ws.recv(timeout=3))
        except Exception:
            first = None
        if first and first.get("type") == "auth_required":
            key = _auth_key()
            if not key:
                print("AUTH REQUIRED but no key found")
                return 2
            ws.send(json.dumps({"id": uuid.uuid4().hex[:12],
                                "type": "authenticate",
                                "payload": {"key": key}}))
            print("auth:", json.loads(ws.recv(timeout=8)).get("type"))

        pong = rpc(ws, "ping")
        print("PING:", json.dumps(pong)[:200])
        if not (pong.get("success") or (pong.get("data") or {}).get("pong")):
            print("VERDICT: NO-BRIDGE (ping failed)")
            return 1

        st = rpc(ws, "memory_status")
        print("STATUS-BEFORE:", json.dumps(st.get("data", st))[:300])

        w = rpc(ws, "memory_write", {
            "content": "G1 acceptance re-probe after fc1c9e1 merge + restart",
            "entry_type": "decision",
            "tags": ["g1-acceptance"],
        })
        print("WRITE:", json.dumps(w)[:500])

        st2 = rpc(ws, "memory_status")
        print("STATUS-AFTER:", json.dumps(st2.get("data", st2))[:300])

        blob = json.dumps(w)
        ok = bool(w.get("success"))
        winerr = "WinError 5" in blob or "Access is denied" in blob
        in_pf = "Program Files" in blob
        if ok and not winerr and not in_pf:
            print("VERDICT: PASS — write ok, no Program Files path, no WinError 5")
            return 0
        if winerr:
            print("VERDICT: FAIL — WinError 5 still present")
            return 1
        print(f"VERDICT: INSPECT — ok={ok} program_files_in_reply={in_pf}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
