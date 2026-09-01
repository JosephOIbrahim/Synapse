# compile_wave.py - BATTLEPLAN missions -> legs/v1 rows + prompt briefs (cloned from autorevise).
# Emits waves/<wave>.rows.json and prompts/<ID>.md. It does NOT touch the live
# manifest: appending rows to harness/legs.json is a CTO act, done on a word.
# The shipped orchestrator re-reads its manifest every poll (orchestrate.ps1:484),
# so an appended row dispatches live - which is exactly why appending is gated.
import json, sys
from pathlib import Path
import mission_schema as ms

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

def leg_row(m: dict) -> dict:
    tag = m["id"].split("-", 1)[1].lower()
    wave = m["id"].split("-", 1)[0].lower().replace("w", "wave")
    row = {
        "id": m["id"],
        "name": m["name"],
        "state": "ready",
        "receipt": m.get("receipt", f"{m['id']}.json"),
        "branch": m.get("branch", f"{wave}/{tag}"),
        "base": "master",
        "worktree": m.get("worktree", f".claude/worktrees/{m['id'].lower()}"),
        "prompt": f"harness/battleplan/prompts/{m['id']}.md",
        "deps": m["deps"],
        "readonly": m["readonly"],
        "touches": m["touches"],
        "note": f"BATTLEPLAN {m['source']['doc']} :: {m['source']['anchor']}. {m.get('note','')}".strip(),
    }
    # BP2-METER T2: carry an OPTIONAL tier onto the row so orchestrate.ps1 can
    # resolve $leg.tier -> model via `rails.py resolve <tier>`. Omitted when the
    # mission has none, so a tier-less row is byte-identical to before.
    if m.get("tier"):
        row["tier"] = m["tier"]
    return row

def fill_prompt(m: dict, row: dict) -> str:
    tpl = (HERE / "prompts" / "_template.md").read_text(encoding="utf-8")
    wave = m["id"].split("-", 1)[0].lower().replace("w", "wave")
    body = json.dumps(m, indent=2, ensure_ascii=False)
    for k, v in {"{ID}": m["id"], "{NAME}": m["name"], "{BRANCH}": row["branch"],
                 "{WORKTREE}": row["worktree"], "{MISSION_JSON}": body,
                 "{WAVE}": wave, "{RECEIPT}": row["receipt"]}.items():
        tpl = tpl.replace(k, v)
    return tpl

def main(wave_arg: str = "") -> int:
    # 2026-09-01 (BP2 scaffold): optional wave argument. `compile_wave.py bp2`
    # compiles ONLY missions whose id prefix is that wave, so a second wave in
    # missions/ cannot clobber the first wave's rows file. No argument = the
    # original behaviour (every mission, wave named from the first file).
    if ms.validate_all() != 0:
        print("compile refused: missions failed validation")
        return 1
    rows, wave = [], None
    want = wave_arg.lower() if wave_arg else ""
    for f in sorted((HERE / "missions").glob("*.json")):
        m = json.loads(f.read_text(encoding="utf-8"))
        if want and m["id"].split("-", 1)[0].lower().replace("w", "wave") != want:
            continue
        row = leg_row(m)
        rows.append(row)
        wave = wave or m["id"].split("-", 1)[0].lower().replace("w", "wave")
        (HERE / "prompts" / f"{m['id']}.md").write_text(fill_prompt(m, row), encoding="utf-8")
        print(f"wrote prompts/{m['id']}.md")
    out = HERE / "waves" / f"{wave}.rows.json"
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out.relative_to(REPO)} ({len(rows)} rows) - append to harness/legs.json is a HUMAN-WORD act")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
