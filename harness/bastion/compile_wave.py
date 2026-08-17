# compile_wave.py - BASTION harness v2. missions -> legs/v1 rows + prompt briefs.
# FORK of harness/autorevise/compile_wave.py (traced 2026-08-17, W8-SMITH).
# Emits waves/<wave>.rows.json and prompts/<ID>.md. It does NOT touch the live
# manifest: appending rows to harness/legs.json is a CTO act, done on a word.
# The shipped orchestrator re-reads its manifest every poll (orchestrate.ps1:484),
# so an appended row dispatches live - which is exactly why appending is gated.
#
# v2 DELTAS (W8-SMITH):
#   * target 3 - skills[] injection: a mission's skills[] paths are rendered into
#     the {SKILLS} slot of the prompt template, so a leg is armed with the skills
#     its mission declares. render_skills() below is the injector.
#   * testability - main()/fill_prompt() take optional dirs/paths so the pytest
#     self-test can compile a fixture into a tmp tree with zero global state. The
#     __main__ path is byte-for-byte the autorevise behaviour (module dirs).
import json, sys
from pathlib import Path
import mission_schema as ms

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

def leg_row(m: dict) -> dict:
    tag = m["id"].split("-", 1)[1].lower()
    wave = m["id"].split("-", 1)[0].lower().replace("w", "wave")
    return {
        "id": m["id"],
        "name": m["name"],
        "state": "ready",
        "receipt": m.get("receipt", f"{m['id']}.json"),
        "branch": m.get("branch", f"{wave}/{tag}"),
        "base": "master",
        "worktree": m.get("worktree", f".claude/worktrees/{m['id'].lower()}"),
        "prompt": f"harness/bastion/prompts/{m['id']}.md",
        "deps": m["deps"],
        "readonly": m["readonly"],
        "touches": m["touches"],
        "note": f"BASTION {m['source']['doc']} :: {m['source']['anchor']}. {m.get('note','')}".strip(),
    }

def render_skills(m: dict) -> str:
    """v2 skills[] injector. Renders a mission's declared skill paths into the
    brief so the leg is armed with them. UNKNOWN never faked: a mission with no
    skills[] renders an explicit 'none' line, not an empty section that reads as
    'forgot to list them'."""
    skills = m.get("skills") or []
    if not skills:
        return "_None declared for this mission._"
    lines = ["Load these skills before executing (repo-relative or /mnt paths):", ""]
    lines += [f"- `{s}`" for s in skills]
    return "\n".join(lines)

def fill_prompt(m: dict, row: dict, template_path: Path = None) -> str:
    tpl_path = template_path or (HERE / "prompts" / "_template.md")
    tpl = tpl_path.read_text(encoding="utf-8")
    wave = m["id"].split("-", 1)[0].lower().replace("w", "wave")
    body = json.dumps(m, indent=2, ensure_ascii=False)
    for k, v in {"{ID}": m["id"], "{NAME}": m["name"], "{BRANCH}": row["branch"],
                 "{WORKTREE}": row["worktree"], "{MISSION_JSON}": body,
                 "{WAVE}": wave, "{RECEIPT}": row["receipt"],
                 "{SKILLS}": render_skills(m)}.items():
        tpl = tpl.replace(k, v)
    return tpl

def main(wave_filter: str = None, mission_dir: Path = None,
         prompts_dir: Path = None, waves_dir: Path = None,
         template_path: Path = None) -> int:
    mission_dir = Path(mission_dir) if mission_dir else (HERE / "missions")
    prompts_dir = Path(prompts_dir) if prompts_dir else (HERE / "prompts")
    waves_dir = Path(waves_dir) if waves_dir else (HERE / "waves")
    if ms.validate_all(mission_dir) != 0:
        print("compile refused: missions failed validation")
        return 1
    prompts_dir.mkdir(parents=True, exist_ok=True)
    waves_dir.mkdir(parents=True, exist_ok=True)
    rows, wave = [], None
    for f in sorted(mission_dir.glob("*.json")):
        m = json.loads(f.read_text(encoding="utf-8"))
        row = leg_row(m)
        rows.append(row)
        wave = wave or m["id"].split("-", 1)[0].lower().replace("w", "wave")
        (prompts_dir / f"{m['id']}.md").write_text(
            fill_prompt(m, row, template_path), encoding="utf-8")
        print(f"wrote prompts/{m['id']}.md")
    out = waves_dir / f"{wave}.rows.json"
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        rel = out.relative_to(REPO)
    except ValueError:
        rel = out
    print(f"wrote {rel} ({len(rows)} rows) - append to harness/legs.json is a HUMAN-WORD act")
    return 0

if __name__ == "__main__":
    sys.exit(main())
