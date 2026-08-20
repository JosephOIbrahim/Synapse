# bus.py - LOOP inter-agent bus (cloned verbatim from harness/apexforge/bus.py).
# Teams talk THROUGH FILES: auditable, greppable, survives any DC/session drop.
# Nobody edits another agent's post; nobody deletes; the bus is evidence.
#
#   harness/loop/bus/<wave>/bus.jsonl        - the shared channel (all posts)
#   harness/loop/bus/<wave>/<agent>.jsonl    - targeted copies for `to:`
#
# Message: {ts, wave, frm, to, type, body}
#   type: claim    - "I am about to edit these files" (post BEFORE touching a
#                    shared seam; peers with an overlapping open claim -> STOP,
#                    post a block, wait. R91/R134 discipline in-band.)
#         finding  - evidence with anchors (file:line, receipt, probe path)
#         request  - ask a peer/orchestrator for something
#         block    - crucible/peer BLOCK; must be answered before merge review
#         spawn    - proposal for a follow-up leg (also lands in the receipt)
#         status   - progress marker
import json, sys, time
from pathlib import Path

BUS_ROOT = Path(__file__).resolve().parent / "bus"

def _wave_dir(wave: str) -> Path:
    d = BUS_ROOT / wave
    d.mkdir(parents=True, exist_ok=True)
    return d

def post(wave: str, frm: str, mtype: str, body, to: str = "*") -> dict:
    msg = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "n": f"{time.time_ns():x}",
           "wave": wave, "frm": frm, "to": to, "type": mtype, "body": body}
    line = json.dumps(msg, ensure_ascii=False)
    d = _wave_dir(wave)
    with open(d / "bus.jsonl", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    if to != "*":
        with open(d / f"{to}.jsonl", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    return msg

def read(wave: str, agent: str = "*", since: str = "", types: str = "") -> list:
    """Read the shared channel (+ targeted inbox if agent given). Filters are
    substring-simple on purpose - agents grep, they don't query."""
    d = _wave_dir(wave)
    out, seen = [], set()
    paths = [d / "bus.jsonl"]
    if agent != "*":
        paths.append(d / f"{agent}.jsonl")
    tset = {t for t in types.split(",") if t}
    for p in paths:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                m = json.loads(line)
            except Exception:
                continue  # a torn write is skipped, never fatal
            key = (m.get("n") or m.get("ts"), m.get("frm"), m.get("type"), json.dumps(m.get("body")))
            if key in seen:
                continue
            seen.add(key)
            if since and m.get("ts", "") < since:
                continue
            if tset and m.get("type") not in tset:
                continue
            if agent != "*" and m.get("to") not in ("*", agent):
                continue
            out.append(m)
    return sorted(out, key=lambda m: m.get("ts", ""))

def open_claims(wave: str) -> list:
    """Claims not yet released (a later status from the same frm with
    body.release matching the claim files closes it)."""
    claims, released = [], set()
    for m in read(wave):
        if m["type"] == "status" and isinstance(m.get("body"), dict) and m["body"].get("release"):
            released.add((m["frm"], json.dumps(sorted(m["body"]["release"]))))
    for m in read(wave, types="claim"):
        files = m.get("body", {}).get("files", []) if isinstance(m.get("body"), dict) else []
        if (m["frm"], json.dumps(sorted(files))) not in released:
            claims.append(m)
    return claims

def has_release(wave: str, frm: str) -> bool:
    """True if <frm> has posted an explicit RELEASE line on <wave> - a status
    message with a non-empty body.release. The close-side twin of a claim."""
    for m in read(wave, types="status"):
        if m.get("frm") != frm:
            continue
        body = m.get("body")
        if isinstance(body, dict) and body.get("release"):
            return True
    return False

if __name__ == "__main__":
    # bus.py post <wave> <frm> <type> <json-body> [to]
    # bus.py read <wave> [agent] [--types a,b] [--since ISO]
    # bus.py claims <wave>
    # bus.py released <wave> <frm>     -> exit 0 if <frm> posted a RELEASE line
    a = sys.argv[1:]
    if not a:
        print(__doc__ or "post|read|claims"); sys.exit(2)
    cmd = a[0]
    if cmd == "post" and len(a) >= 5:
        try:
            body = json.loads(a[4])
        except Exception:
            body = {"msg": a[4]}
            print("WARN: body was not valid JSON after shell quoting; recorded as {'msg': raw}. Use '{\\\"k\\\": ...}' form in PowerShell.", file=sys.stderr)
        to = a[5] if len(a) > 5 else "*"
        print(json.dumps(post(a[1], a[2], a[3], body, to)))
    elif cmd == "read" and len(a) >= 2:
        agent = a[2] if len(a) > 2 and not a[2].startswith("--") else "*"
        kw = {"since": "", "types": ""}
        for i, t in enumerate(a):
            if t == "--types" and i + 1 < len(a): kw["types"] = a[i + 1]
            if t == "--since" and i + 1 < len(a): kw["since"] = a[i + 1]
        for m in read(a[1], agent, kw["since"], kw["types"]):
            print(json.dumps(m, ensure_ascii=False))
    elif cmd == "claims" and len(a) >= 2:
        for m in open_claims(a[1]):
            print(json.dumps(m, ensure_ascii=False))
    elif cmd == "released" and len(a) >= 3:
        ok = has_release(a[1], a[2])
        print("released" if ok else "no-release")
        sys.exit(0 if ok else 1)
    else:
        print("usage: post <wave> <frm> <type> <json-body> [to] | read <wave> [agent] | claims <wave> | released <wave> <frm>")
        sys.exit(2)
