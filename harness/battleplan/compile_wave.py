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
    # JEV-ROUTE (2026-09-19, notes/JEV_BLUEPRINT.md sec.3.1): "tier": "auto" asks Jev to
    # choose among rails_exec.json's tier NAMES; any failure resolves to reasoning and is
    # ledgered under harness/jev/ledger/. A literal tier never enters this branch.
    if row.get("tier") == "auto":
        sys.path.insert(0, str(REPO / "harness" / "jev"))
        import jev_route
        row["tier"] = jev_route.resolve_tier(m, wave)
    # BP9-NONETIER (ruling 2): a literal tier 'none' passes through UNTOUCHED (JEV invariant 2:
    # a literal tier is byte-identical) together with its probe_cmd - the command
    # orchestrate.ps1 runs in place of spawning claude. Jev can never emit 'none' (rails marks
    # it routable:false and jev_route honours the flag), so only an author puts it here.
    if row.get("tier") == 'none':
        row["probe_cmd"] = m["probe_cmd"]
        if m.get("probe_timeout"):
            row["probe_timeout"] = m["probe_timeout"]
    # JEV-TEAM (2026-09-20, notes/JEV_HELM.md mile 2): an OPTIONAL "team". "auto" asks Jev how
    # parallelizable the leg is and code maps that to 0/2/4 subagents, rounding DOWN on doubt;
    # a literal {max_subagents, subagent_tier} passes through. No team field -> no key on the
    # row and no section in the prompt, so such a leg is byte-identical to before.
    if m.get("team"):
        team = m["team"]
        if team == "auto":
            sys.path.insert(0, str(REPO / "harness" / "jev"))
            import jev_team
            d = jev_team.resolve_team(m, wave)
            team = {"max_subagents": d["max_subagents"], "subagent_tier": d["subagent_tier"]}
        row["team"] = team
    return row

def screen_lines(m: dict, wave: str) -> str:
    """JEV-SCREEN pre-read for the CRUX brief (BP6-JEV T2, notes/JEV_BLUEPRINT.md sec.3.2).
    Only a crucible leg gets a block; every other leg gets an empty string, so a non-crucible
    prompt - and any prompt for a wave with no screen ledger - is byte-identical to a pre-JEV
    compile. The block is one brief_line per screened builder from
    harness/jev/ledger/<wave>.screen.jsonl. An ABSENT ledger renders empty (the byte-identical
    case the crucible diffs against master); a PRESENT ledger with no decision rows renders the
    'screen not run' sentinel rather than a silent blank."""
    if m.get("class") != "crucible":
        return ""
    led = REPO / "harness" / "jev" / "ledger" / f"{wave}.screen.jsonl"
    if not led.exists():
        return ""
    lines = []
    for raw in led.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if entry.get("result") == "decision":
            bl = (entry.get("decision") or {}).get("brief_line")
            if bl:
                lines.append(bl)
    body = "\n".join(lines) if lines else "screen: none - JEV screen not run"
    return f"\n## JEV screen pre-read\n\n{body}\n"

def fill_prompt(m: dict, row: dict) -> str:
    tpl = (HERE / "prompts" / "_template.md").read_text(encoding="utf-8")
    wave = m["id"].split("-", 1)[0].lower().replace("w", "wave")
    body = json.dumps({**m, "team": row["team"]} if "team" in row else m, indent=2, ensure_ascii=False)
    for k, v in {"{ID}": m["id"], "{NAME}": m["name"], "{BRANCH}": row["branch"],
                 "{WORKTREE}": row["worktree"], "{MISSION_JSON}": body,
                 "{WAVE}": wave, "{RECEIPT}": row["receipt"],
                 "{SCREEN_LINES}": screen_lines(m, wave)}.items():
        tpl = tpl.replace(k, v)
    if "team" in row:  # JEV-TEAM: appended, never templated, so a team-less prompt cannot change
        sys.path.insert(0, str(REPO / "harness" / "jev"))
        import jev_team
        tpl += jev_team.team_lines(row["team"])
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
