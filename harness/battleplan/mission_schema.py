# mission_schema.py - BATTLEPLAN mission validation (cloned from autorevise 2026-08-17). Plain Python, zero deps.
# A mission is a REVISION WORK ORDER derived from a review document. It compiles
# (compile_wave.py) into a legs/v1 row + a prompt brief for the shipped
# orchestrator (harness/orchestrate.ps1). This file is the admission gate:
# nothing un-validated reaches the manifest. Mirrors the stance of
# harness/autoresearch/mission_schema.py - validation before dispatch.
import json, sys, re
from pathlib import Path

REQUIRED = ["id", "name", "band", "source", "targets", "acceptance",
            "deps", "readonly", "touches", "crucible_criteria"]
OPTIONAL = ["spawn_classes", "note", "receipt", "branch", "worktree", "class", "tier", "team", "probe_cmd", "probe_timeout"]
BANDS = {"BUILD", "TRUST", "TRUTH", "PAPER"}
ID_RE = re.compile(r"^BP\d+-[A-Z0-9]{2,12}$")

def _err(errors, mid, msg):
    errors.append(f"[{mid}] {msg}")

def validate_mission(m: dict) -> list:
    errors = []
    mid = m.get("id", "<no id>")
    for k in REQUIRED:
        if k not in m:
            _err(errors, mid, f"missing required field '{k}'")
    unknown = set(m) - set(REQUIRED) - set(OPTIONAL)
    if unknown:
        _err(errors, mid, f"unknown fields {sorted(unknown)}")
    if errors:
        return errors  # shape first; content checks need the shape
    if not ID_RE.match(m["id"]):
        _err(errors, mid, "id must match WA<wave>-<TAG> e.g. BP1-TRUTH (battleplan family)")
    if m["band"] not in BANDS:
        _err(errors, mid, f"band must be one of {sorted(BANDS)}")
    if m["band"] == "TRUST" and not m.get("readonly", False):
        _err(errors, mid, "TRUST band (crucible/review) must be readonly:true")
    src = m.get("source", {})
    if not (isinstance(src, dict) and src.get("doc") and src.get("anchor")):
        _err(errors, mid, "source must be {doc, anchor} pointing at the review paper")
    elif not Path(src["doc"]).exists() and not (REPO / src["doc"]).exists():
        _err(errors, mid, f"source doc not found: {src['doc']}")
    if not isinstance(m.get("targets"), list) or not m["targets"]:
        _err(errors, mid, "targets must be a non-empty list of files/subsystems")
    acc = m.get("acceptance")
    if not isinstance(acc, list) or not acc:
        _err(errors, mid, "acceptance must be a non-empty list")
    else:
        for i, a in enumerate(acc):
            if not isinstance(a, dict) or "predicate" not in a or "evidence" not in a:
                _err(errors, mid, f"acceptance[{i}] needs predicate + evidence")
            elif a["evidence"] not in {"probe", "check", "test", "receipt", "gui_probe"}:
                _err(errors, mid, f"acceptance[{i}].evidence must be probe|check|test|receipt|gui_probe")
    # HOUSE RULE (unobtainable renders UNKNOWN): any gui_probe predicate must
    # declare it, so a headless run reports UNKNOWN - never a pass, never a 0.
    for i, a in enumerate(acc if isinstance(acc, list) else []):
        if isinstance(a, dict) and a.get("evidence") == "gui_probe" and not a.get("gui_required"):
            _err(errors, mid, f"acceptance[{i}] evidence gui_probe requires gui_required:true")
    if not isinstance(m.get("touches"), list):
        _err(errors, mid, "touches must be a list (coarse is fine; discovery is recorded)")
    # JEV-ROUTE (2026-09-19): tier must be a rails_exec.json tier name or 'auto'. rails_exec
    # stays the only source of names; 'auto' is resolved to one of them at compile time.
    if "tier" in m:
        try:
            tiers = set(json.loads((REPO / "harness" / "rails_exec.json").read_text(encoding="utf-8")).get("tiers", {}))
        except Exception:
            tiers = set()
        if tiers and m["tier"] not in tiers | {"auto"}:
            _err(errors, mid, f"tier must be one of {sorted(tiers)} or 'auto'")
    # BP9-NONETIER (ruling 2): tier 'none' launches no model. The orchestrator runs the
    # mission's probe_cmd itself, so a none-tier mission MUST carry one (a non-empty string);
    # a probe_cmd on any other tier is a contradiction and is refused rather than ignored.
    if m.get("tier") == "none":
        pc = m.get("probe_cmd")
        if not (isinstance(pc, str) and pc.strip()):
            _err(errors, mid, "tier 'none' requires probe_cmd: a non-empty string the orchestrator runs")
    elif "probe_cmd" in m:
        _err(errors, mid, "probe_cmd is only valid with tier 'none'")
    if "probe_timeout" in m and not (isinstance(m["probe_timeout"], int) and m["probe_timeout"] > 0):
        _err(errors, mid, "probe_timeout must be a positive int (seconds)")
    # JEV-TEAM (2026-09-20, notes/JEV_HELM.md mile 2): OPTIONAL. 'auto' is resolved at compile
    # time; a literal is {max_subagents: 0..4, subagent_tier: <rails tier>}. Absent = a plain
    # single-session leg, byte-identical to before. Referee and tidy legs work alone.
    if "team" in m and m["team"] != "auto":
        t = m["team"]
        if not (isinstance(t, dict) and isinstance(t.get("max_subagents"), int) and 0 <= t["max_subagents"] <= 4):
            _err(errors, mid, "team must be 'auto' or {max_subagents: 0..4, subagent_tier}")
        else:
            try:
                tiers = set(json.loads((REPO / "harness" / "rails_exec.json").read_text(encoding="utf-8")).get("tiers", {}))
            except Exception:
                tiers = set()
            if t["max_subagents"] > 0 and tiers and t.get("subagent_tier") not in tiers:
                _err(errors, mid, f"team.subagent_tier must be one of {sorted(tiers)}")
            elif t["max_subagents"] > 0 and t.get("subagent_tier") == "none":
                _err(errors, mid, "team.subagent_tier cannot be 'none' (a subagent is a model)")
            if t["max_subagents"] > 0 and m.get("class") in ("crucible", "tidy"):
                _err(errors, mid, "referee and tidy legs work alone: team.max_subagents must be 0")
    if not isinstance(m.get("crucible_criteria"), list) or not m["crucible_criteria"]:
        _err(errors, mid, "crucible_criteria must be a non-empty list")
    return errors

REPO = Path(__file__).resolve().parents[2]
MISSIONS = Path(__file__).resolve().parent / "missions"

def validate_all(mission_dir: Path = MISSIONS) -> int:
    files = sorted(mission_dir.glob("*.json"))
    if not files:
        print(f"no missions in {mission_dir}")
        return 1
    total = 0
    seen_ids = {}
    for f in files:
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"FAIL {f.name}: unparseable JSON ({e})")
            total += 1
            continue
        errs = validate_mission(m)
        mid = m.get("id", f.name)
        if mid in seen_ids:
            errs.append(f"[{mid}] duplicate id (also in {seen_ids[mid]})")
        seen_ids[mid] = f.name
        if errs:
            total += len(errs)
            for e in errs:
                print(f"FAIL {f.name}: {e}")
        else:
            print(f"OK   {f.name}: {mid}")
    print(f"-- {len(files)} missions, {total} errors")
    return 0 if total == 0 else 1

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] != "--all":
        p = Path(sys.argv[1])
        m = json.loads(p.read_text(encoding="utf-8"))
        errs = validate_mission(m)
        for e in errs: print("FAIL", e)
        sys.exit(1 if errs else print(f"OK {m['id']}") or 0)
    sys.exit(validate_all())
