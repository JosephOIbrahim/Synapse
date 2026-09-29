# calibrate_screen.py - replay JEV-SCREEN's recorded decisions against CRUX's verdicts (offline).
#
# Every screen decision in harness/jev/ledger/*screen.jsonl keeps Jev's per-row answers. Joined
# with the leg verdicts in the CRUX verdict notes, they are the answer key for the screen's
# policy: a BROKEN leg must never be CLEAR, and every sound leg the screen clears is a full
# referee read saved. No Jev call is made; nothing is billed. BP12 item 8.
#
#   python harness/jev/calibrate_screen.py           # print the table for the current policy
#   python harness/jev/calibrate_screen.py --write   # also refresh the test fixture
#
# The fixture (harness/jev/tests/fixtures/screen_calibration_cases.json) is what
# test_jev_screen_calibration.py replays, so the calibration is checked on every run.
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jev_client as jc  # noqa: E402
import jev_screen as js  # noqa: E402

LEDGER = HERE / "ledger"
FIXTURE = HERE / "tests" / "fixtures" / "screen_calibration_cases.json"
_VERDICT = re.compile(r"(BP\d+-[A-Z0-9]+)\b[^\n]{0,80}?\b(SOUND-WITH-NITS|SOUND|BROKEN)\b")


def crux_verdicts() -> dict:
    """{leg: verdict} from every CRUX verdict note, plus waves whose note lives on a crux branch."""
    texts = [p.read_text(encoding="utf-8", errors="replace")
             for p in sorted(js.NOTES.glob("*-CRUX*_verdicts.md"))]
    for ledger in sorted(LEDGER.glob("*.screen.jsonl")):
        wave = ledger.name.split(".")[0]
        if not list(js.NOTES.glob(f"{wave.upper()}-CRUX*_verdicts.md")):
            shown = subprocess.run(
                ["git", "-C", str(jc.REPO), "show",
                 f"{wave}/crux:harness/battleplan/notes/{wave.upper()}-CRUX_verdicts.md"],
                capture_output=True, text=True, encoding="utf-8", errors="replace")
            if shown.returncode == 0:
                texts.append(shown.stdout)
    out: dict = {}
    for text in texts:
        for leg, verdict in _VERDICT.findall(text):
            out.setdefault(leg, verdict)
    return out


def cases() -> list:
    """One case per CRUX-judged leg: its last live screen decision, else its last shadow one."""
    verdicts = crux_verdicts()
    live, shadow = {}, {}
    for ledger in sorted(LEDGER.glob("*screen.jsonl")):
        target = shadow if ".shadow." in ledger.name else live
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            decision = row.get("decision") or {}
            jev = decision.get("jev")
            if row.get("result") != "decision" or not jev or row.get("leg") not in verdicts:
                continue
            target[row["leg"]] = (ledger.name, decision, jev)
    out = []
    for leg in sorted(set(live) | set(shadow)):
        source, decision, jev = live.get(leg) or shadow[leg]
        answers = {
            "choices": {f"acc_{r['i']}": {"choice": r.get("choice"), "confidence": r.get("confidence"),
                                          "probabilities": r.get("p") or {}} for r in jev["rows"]},
            "nouls": {"self_contradiction": {"noul": jev.get("self_contradiction")}},
            "scores": {"crux_need": {"score": jev.get("crux_need")}},
        }
        out.append({"leg": leg, "source": source, "crux": verdicts[leg],
                    "recorded_verdict": decision.get("verdict"), "n_rows": len(jev["rows"]),
                    "code_flags": bool(decision.get("code_flags")), "answers": answers})
    return out


def replay(case: dict, policy: dict) -> str:
    """The verdict the screen gives this case today; a code count mismatch always FLAGs."""
    if case["code_flags"]:
        return "FLAG"
    return js.decide(case["n_rows"], case["answers"], policy)["verdict"]


def main() -> int:
    policy = jc.load_questions()["guards"]["screen"]["policy"]
    rows = cases()
    print(f"{'leg':16} {'crux':16} {'recorded':9} now")
    for c in rows:
        print(f"{c['leg']:16} {c['crux']:16} {c['recorded_verdict']:9} {replay(c, policy)}")
    broken = [c for c in rows if c["crux"] == "BROKEN"]
    sound = [c for c in rows if c["crux"] != "BROKEN"]
    print(f"-- {len(rows)} legs: BROKEN cleared {sum(replay(c, policy) == 'CLEAR' for c in broken)}"
          f" of {len(broken)}; sound cleared {sum(replay(c, policy) == 'CLEAR' for c in sound)}"
          f" of {len(sound)}")
    if "--write" in sys.argv:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps({"generated": date.today().isoformat(),
                                       "producer": "harness/jev/calibrate_screen.py --write",
                                       "cases": rows}, indent=1) + "\n",
                           encoding="utf-8", newline="\n")
        print(f"-- wrote {FIXTURE.relative_to(jc.REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
