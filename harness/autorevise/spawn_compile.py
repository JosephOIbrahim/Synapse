# spawn_compile.py - dynamic edges, gated. Reads a wave receipt, validates its
# spawn[] proposals, and compiles them into legs/v1 rows:
#   - class IN the source mission's spawn_classes -> state "ready"
#   - class absent/off-playbook                   -> state "held"  (Joe's flip)
# Default is PRINT ONLY. --append <manifest> writes rows into the manifest's
# legs[] - run that form only on a human word. The orchestrator's live re-read
# (orchestrate.ps1:484) makes an append a dispatch.
import json, sys
from pathlib import Path
import mission_schema as ms
from compile_wave import leg_row, fill_prompt

HERE = Path(__file__).resolve().parent

def compile_spawns(receipt_path: str, append_to: str = "") -> int:
    r = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    src_id = r.get("leg", "")
    src = None
    for f in (HERE / "missions").glob("*.json"):
        m = json.loads(f.read_text(encoding="utf-8"))
        if m["id"] == src_id:
            src = m
            break
    allowed = set((src or {}).get("spawn_classes", []))
    rows = []
    for i, sp in enumerate(r.get("spawn", [])):
        errs = ms.validate_mission(sp)
        if errs:
            print(f"REJECT spawn[{i}]: " + "; ".join(errs))
            continue
        row = leg_row(sp)
        row["state"] = "ready" if sp.get("class") in allowed else "held"
        if row["state"] == "held":
            row["note"] = f"HELD: class '{sp.get('class')}' outside {src_id} playbook {sorted(allowed)}. " + row["note"]
        (HERE / "prompts" / f"{sp['id']}.md").write_text(fill_prompt(sp, row), encoding="utf-8")
        rows.append(row)
        print(f"{row['state'].upper():5s} {row['id']} <- spawned by {src_id}")
    if not rows:
        print("no valid spawns")
        return 0
    print(json.dumps(rows, indent=2, ensure_ascii=False))
    if append_to:
        mp = Path(append_to)
        manifest = json.loads(mp.read_text(encoding="utf-8"))
        have = {l["id"] for l in manifest["legs"]}
        new = [x for x in rows if x["id"] not in have]
        manifest["legs"].extend(new)
        mp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"appended {len(new)} rows -> {append_to} (live dispatch surface)")
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: spawn_compile.py <receipt.json> [--append <manifest.json>]")
        sys.exit(2)
    ap = sys.argv[sys.argv.index("--append") + 1] if "--append" in sys.argv else ""
    sys.exit(compile_spawns(sys.argv[1], ap))
