# jev_packet.py - JEV-PACKET: does each leg's token-saver packet cover each of its targets? (build-time, BP11)
# build_packets_bp11.py hands every leg a packet of exact code windows so Opus legs stop re-scouting what the
# seat already located. This guard asks one Noul per target: is the packet enough to START that target without
# searching the codebase? Code owns the decision (policy in packet_guard.json). A THIN target earns ONE bounded
# repair by the seat (add a window, rebuild, re-screen once) - never a loop. Fail closed: no key, network or SDK
# error -> UNSCREENED; the packet ships as built and the ledger says why. Jev never edits a packet or a mission.
# Ledger: harness/jev/ledger/<wave>.packet.jsonl (jev_client.ask writes the call row; this writes the decision).
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jev_client as jc  # noqa: E402

REPO = HERE.parents[1]
GUARD = json.loads((HERE / "packet_guard.json").read_text(encoding="utf-8"))


def spec(n_targets: int) -> dict:
    row = GUARD["questions"]["ready_row"]
    return {f"ready_{i}": {"type": "noul", "instructions": row["instructions"].replace("{i}", str(i))}
            for i in range(n_targets)}


def decide(n_targets: int, answers: dict | None, policy: dict) -> dict:
    if answers is None:
        return {"verdict": policy["fallback_verdict"], "thin": [], "grey": [], "missing": [], "p": [],
                "reason": "fallback: no Jev answer (see ledger)"}
    ps = [(answers.get("nouls", {}).get(f"ready_{i}") or {}).get("noul") for i in range(n_targets)]
    thin = [i for i, p in enumerate(ps) if p is not None and p < policy["thin_below"]]
    grey = [i for i, p in enumerate(ps) if p is not None and policy["thin_below"] <= p < policy["ready_min"]]
    missing = [i for i, p in enumerate(ps) if p is None]
    verdict = "THIN" if thin else ("GREY" if grey or missing else "READY")
    return {"verdict": verdict, "thin": thin, "grey": grey, "missing": missing, "p": ps,
            "reason": f"ready_min {policy['ready_min']}, thin_below {policy['thin_below']}"}


def main() -> int:
    ap = argparse.ArgumentParser(description="JEV-PACKET: screen token-saver packets per target")
    ap.add_argument("--wave", default="bp11")
    ap.add_argument("--packets", default=str(REPO / ".token-saver" / "bp11"))
    ap.add_argument("--legs", nargs="*", help="only these mission ids")
    a = ap.parse_args()
    policy = GUARD["policy"]
    missions = REPO / "harness" / "battleplan" / "missions"
    for f in sorted(missions.glob(f"{a.wave.upper()}-*.json")):
        m = json.loads(f.read_text(encoding="utf-8"))
        if a.legs and m["id"] not in a.legs:
            continue
        pk = Path(a.packets) / f"{m['id']}.packet.md"
        if not pk.exists():
            print(f"{m['id']:<14} NO PACKET")
            continue
        state = {"leg": {"name": m["name"], "targets": m["targets"]},
                 "packet": pk.read_text(encoding="utf-8")[: policy["max_packet_chars"]]}
        n = len(m["targets"])
        answers = jc.ask(state, spec(n), wave=a.wave, guard="packet", leg=m["id"])
        d = decide(n, answers, policy)
        jc.ledger(a.wave, "packet", {"leg": m["id"], "result": "decision", "decision": d})
        ps = " ".join("-" if p is None else f"{p:.2f}" for p in d["p"])
        print(f"{m['id']:<14} {d['verdict']:<11} p(ready) by target: {ps}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
