# bus.py - BASTION harness v2 inter-agent bus. Append-only JSONL, file-per-wave.
# FORK of harness/autorevise/bus.py (traced 2026-08-17, W8-SMITH). Teams talk
# THROUGH FILES: auditable, greppable, survives any DC/session drop. Nobody edits
# another agent's post; nobody deletes; the bus is evidence.
#
#   harness/bastion/bus/<wave>/bus.jsonl        - the shared channel (all posts)
#   harness/bastion/bus/<wave>/<agent>.jsonl    - targeted copies for `to:`
#
# Message: {ts, n, wave, frm, to, type, body}
#
# v2 DELTA (W8-SMITH target 3): TYPED MESSAGE KINDS with a validator ON WRITE.
# The named v2 vocabulary is CLAIM / FINDING / HANDOFF / BLOCK / RELEASE. It is
# case-insensitive on input and canonicalised to lowercase on storage, so the
# format stays byte-identical to the autorevise bus and to what the shipped
# orchestrator reads (orchestrate.ps1:206,211 close-gate). The autorevise
# operational kinds (request / spawn / status) are carried verbatim - dropping
# them would break the orchestrator close-gate + the SPEC-2 spawn flow, which is
# not a faithful fork. post() REFUSES any kind outside the vocabulary (ValueError
# programmatically; exit 2 on the CLI): that refusal is the "validator on write".
#
#   type meanings (canonical lowercase):
#     claim    - "I am about to edit these files" (post BEFORE touching a shared
#                seam; overlapping open claim -> STOP, block, wait. R91/R134.)
#     finding  - evidence with anchors (file:line, receipt, probe path)
#     handoff  - NEW in v2: cross-agent state transfer (mirrors AgentHandoff in
#                shared/bridge.py: body carries from/to/task_id/context/guidance)
#     block    - crucible/peer BLOCK; must be answered before merge review
#     release  - NEW first-class kind in v2: closes a claim + signals completion.
#                has_release()/open_claims() ALSO honour the autorevise idiom
#                (a `status` with body.release) so a leg armed the old way still
#                closes its gate - full back-compat with orchestrate.ps1.
#     request  - ask a peer/orchestrator for something (autorevise, carried)
#     spawn    - proposal for a follow-up leg (autorevise, carried)
#     status   - progress marker; {release:[files]} closes a claim (autorevise)
import json, sys, time
from pathlib import Path

BUS_ROOT = Path(__file__).resolve().parent / "bus"

# v2 typed vocabulary. Named kinds (target 3) + carried autorevise operational
# kinds. Case-insensitive input, lowercase canonical storage.
NAMED_KINDS = {"claim", "finding", "handoff", "block", "release"}
OPERATIONAL_KINDS = {"request", "spawn", "status"}
VALID_KINDS = NAMED_KINDS | OPERATIONAL_KINDS

class BusKindError(ValueError):
    """Raised when a post() kind is outside the v2 vocabulary."""

def canonical_kind(mtype: str) -> str:
    """Normalise + validate a message kind. Returns the canonical lowercase kind
    or raises BusKindError. This IS the validator-on-write (target 3)."""
    if not isinstance(mtype, str) or not mtype.strip():
        raise BusKindError(f"empty/invalid message kind: {mtype!r}")
    k = mtype.strip().lower()
    if k not in VALID_KINDS:
        raise BusKindError(
            f"unknown bus kind {mtype!r}; valid: {sorted(VALID_KINDS)}")
    return k

def _wave_dir(wave: str) -> Path:
    d = BUS_ROOT / wave
    d.mkdir(parents=True, exist_ok=True)
    return d

def post(wave: str, frm: str, mtype: str, body, to: str = "*") -> dict:
    kind = canonical_kind(mtype)  # v2: refuse an off-vocabulary kind on write
    msg = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "n": f"{time.time_ns():x}",
           "wave": wave, "frm": frm, "to": to, "type": kind, "body": body}
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

def _closes_claim(m: dict) -> bool:
    """True if message m closes a claim. Two idioms, both honoured (back-compat):
      * v2 first-class `release` kind with body.release (or body.files)
      * autorevise `status` with body.release"""
    body = m.get("body")
    if not isinstance(body, dict):
        return False
    if m.get("type") == "release" and (body.get("release") or body.get("files")):
        return True
    if m.get("type") == "status" and body.get("release"):
        return True
    return False

def _released_files(m: dict) -> list:
    body = m.get("body") if isinstance(m.get("body"), dict) else {}
    return body.get("release") or body.get("files") or []

def open_claims(wave: str) -> list:
    """Claims not yet released. A later release (v2 `release` kind, or the
    autorevise `status`+body.release) from the same frm whose file set matches
    the claim closes it."""
    released = set()
    for m in read(wave):
        if _closes_claim(m):
            released.add((m["frm"], json.dumps(sorted(_released_files(m)))))
    claims = []
    for m in read(wave, types="claim"):
        files = m.get("body", {}).get("files", []) if isinstance(m.get("body"), dict) else []
        if (m["frm"], json.dumps(sorted(files))) not in released:
            claims.append(m)
    return claims

def has_release(wave: str, frm: str) -> bool:
    """True if <frm> has posted an explicit RELEASE on <wave> - either the v2
    first-class `release` kind or the autorevise `status`+body.release idiom.
    The close-side twin of a claim. The shipped orchestrator's close gate
    (orchestrate.ps1 Test-CloseGate -> `bus.py released`) treats the PRESENCE of
    a release as a required completion signal, so a leg that never posts one
    holds at 'closing' instead of reading 'done'."""
    for m in read(wave):
        if m.get("frm") != frm:
            continue
        if _closes_claim(m):
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
        try:
            print(json.dumps(post(a[1], a[2], a[3], body, to)))
        except BusKindError as e:
            print(f"REFUSED: {e}", file=sys.stderr)
            sys.exit(2)
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
        # Close-gate probe. Exit 0 if <frm> posted an explicit RELEASE line on
        # <wave>, else 1. A shell `if` reads the EXIT CODE; stdout is a human hint
        # only. Consumed by orchestrate.ps1's Test-CloseGate.
        ok = has_release(a[1], a[2])
        print("released" if ok else "no-release")
        sys.exit(0 if ok else 1)
    else:
        print("usage: post <wave> <frm> <type> <json-body> [to] | read <wave> [agent] | claims <wave> | released <wave> <frm>")
        sys.exit(2)
