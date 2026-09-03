# make_control.py - build a throwaway control manifest for orchestrate.ps1 -DryRun.
# The control carries the compiled wave rows plus DONE-pinned stubs for external
# deps (BASE, FRZ live on the real board; pinning them done here keeps the
# control self-contained and guarantees the dry run can never dispatch them).
# Assertion the control proves: rows parse as legs/v1, dependency gating holds
# (every wave leg reads 'blocked' until real receipts exist), no crash.
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

def main(wave: str = "wave1") -> int:
    rows = json.loads((HERE / "waves" / f"{wave}.rows.json").read_text(encoding="utf-8"))
    ext = sorted({d for r in rows for d in r["deps"]} - {r["id"] for r in rows})
    stubs = [{"id": d, "name": f"{d} (control stub)", "state": "done",
              "receipt": f"{d}.json",
              "note": "control stub - real leg lives on harness/legs.json; pinned done so the dry run cannot touch it"}
             for d in ext]
    manifest = {
        "_comment": f"CONTROL manifest for {wave} dry-run. Never dispatch for real from this file.",
        "_schema": "legs/v1",
        "repo": str(REPO),
        "settings": str(REPO / "harness" / "relay-settings.json"),
        "effort": "max",  # BP4 2026-09-03: was 'ultracode', not a level Claude Code 2.1.259 lists (low|medium|high|xhigh|max); control now matches the live manifest
        "base": "master",
        "model": "claude-opus-4-8",
        "legs": stubs + rows,
    }
    out = HERE / "waves" / f"{wave}.control.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out} ({len(stubs)} stubs + {len(rows)} rows)")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "wave1"))
