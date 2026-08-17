# mission_schema.py - BASTION harness v2 mission validation. Plain Python, zero deps.
# FORK of harness/autorevise/mission_schema.py (traced 2026-08-17, W8-SMITH). The
# only v2 delta is the optional `skills[]` field (see SKILLS below); every other
# rule is carried verbatim from the autorevise admission gate. A mission is a
# REVISION WORK ORDER derived from a review document. It compiles (compile_wave.py)
# into a legs/v1 row + a prompt brief for the shipped orchestrator
# (harness/orchestrate.ps1). This file is the admission gate: nothing un-validated
# reaches the manifest.
#
# v2 DELTA (W8-SMITH target 3): `skills` - optional list of repo-relative or /mnt
# skill paths. compile_wave.py injects them into the leg prompt brief so a leg is
# armed with the skills its mission needs. Validated for SHAPE only (list of
# non-empty strings): a /mnt skill path is not resolvable in this checkout, so
# asserting on-disk existence would be a phantom check - shape is the honest bar.
import json, sys, re
from pathlib import Path

REQUIRED = ["id", "name", "band", "source", "targets", "acceptance",
            "deps", "readonly", "touches", "crucible_criteria"]
OPTIONAL = ["spawn_classes", "note", "receipt", "branch", "worktree", "class",
            "skills"]
BANDS = {"BUILD", "TRUST", "TRUTH", "PAPER"}
ID_RE = re.compile(r"^W\d+-[A-Z0-9]{2,12}$")

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
        _err(errors, mid, "id must match W<wave>-<TAG> e.g. W1-HSTRIP")
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
    if not isinstance(m.get("crucible_criteria"), list) or not m["crucible_criteria"]:
        _err(errors, mid, "crucible_criteria must be a non-empty list")
    # v2 SKILLS (optional): a list of repo-relative or /mnt skill paths. Shape-only
    # validation - each entry a non-empty string. Existence is NOT asserted: /mnt
    # skills are not on this checkout, and a green "exists" check we cannot run
    # would be a phantom surface. compile_wave.py injects these into the brief.
    if "skills" in m:
        sk = m["skills"]
        if not isinstance(sk, list):
            _err(errors, mid, "skills must be a list of skill paths (repo-relative or /mnt)")
        else:
            for i, s in enumerate(sk):
                if not isinstance(s, str) or not s.strip():
                    _err(errors, mid, f"skills[{i}] must be a non-empty string path")
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
