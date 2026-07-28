"""Re-derive the leg's typed mutation-test claim as a produced number.

i1b_receipt.py:298 hardcodes `guards_reverted_to_controls_red` as six literals.
This runs it: revert each guard in a private copy of the committed reader, re-run
the committed calibration, count how many controls turn red.

Law 1 form: a guard whose reversion turns NO control red is not pinned.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\User\.i1verify")
SRC = ROOT / "notes"
MUT = ROOT / "mut"

# (label, old, new) -- each `old` must appear exactly once in the reader.
GUARDS = [
    ("utf-8-sig (BOM)",
     'b.decode("utf-8-sig")',
     'b.decode("utf-8")'),
    ("EOL normalisation",
     'text = text.replace("\\r\\n", "\\n").replace("\\r", "\\n")',
     'text = text  # GUARD REVERTED'),
    ("item-scope close (:vimeo:)",
     'p.colon_directives.append((idx, m.group("name"), m.group("arg").strip()))\n'
     '            pending = None\n'
     '            continue',
     'p.colon_directives.append((idx, m.group("name"), m.group("arg").strip()))\n'
     '            continue  # GUARD REVERTED'),
    ("column-0 page directives (D4)",
     'if cur_section is None and ind == 0:',
     'if cur_section is None:  # GUARD REVERTED'),
    ("#channels as internal name",
     'if self.channels:\n'
     '            out.extend(c.lstrip("/") for c in self.channels.split() if c.strip())',
     'if False:  # GUARD REVERTED\n'
     '            out.extend(c.lstrip("/") for c in self.channels.split() if c.strip())'),
    ("@section include anchors",
     'helpdoc._anchored_block = _anchored_block_or_section',
     'helpdoc._anchored_block = _ORIG_ANCHORED_BLOCK  # GUARD REVERTED'),
]

PUBLISHED = {
    "utf-8-sig (BOM)": 2,
    "EOL normalisation": 9,
    "item-scope close (:vimeo:)": 1,
    "column-0 page directives (D4)": 2,
    "#channels as internal name": 5,
    "@section include anchors": 2,
}


def run_calibration(workdir: Path):
    ing = workdir / "notes" / "ingest"
    r = subprocess.run([sys.executable, "i1b_calibrate.py"], cwd=str(ing),
                       capture_output=True, text=True)
    art = ing / "_i1b_calibration.json"
    if not art.exists():
        return None, r.stdout + r.stderr
    return json.loads(art.read_text(encoding="utf-8")), r.stdout


if MUT.exists():
    shutil.rmtree(MUT)
MUT.mkdir(parents=True)

# ---- control: unmutated baseline ------------------------------------------
base_dir = MUT / "_baseline"
base_dir.mkdir()
shutil.copytree(SRC, base_dir / "notes")
cal, out = run_calibration(base_dir)
base_fail = cal["failed"]
print("BASELINE  controls=%d passed=%d failed=%d" % (cal["total"], cal["passed"], base_fail))
if base_fail != 0:
    print("baseline is not green -- mutation results are meaningless")
    sys.exit(2)
print()

rows = []
for i, (label, old, new) in enumerate(GUARDS):
    d = MUT / ("g%d" % i)
    d.mkdir()
    shutil.copytree(SRC, d / "notes")
    rp = d / "notes" / "ingest" / "i1b_reader.py"
    txt = rp.read_text(encoding="utf-8")
    n = txt.count(old)
    if n != 1:
        rows.append((label, None, PUBLISHED[label],
                     "MUTATION SITE NOT UNIQUE (%d matches)" % n))
        print("%-32s SKIP  site matched %d times" % (label, n))
        continue
    rp.write_text(txt.replace(old, new), encoding="utf-8")
    cal, out = run_calibration(d)
    if cal is None:
        rows.append((label, "crash", PUBLISHED[label], out.strip().splitlines()[-1:]))
        print("%-32s CRASH" % label)
        continue
    red = cal["failed"]
    names = [c["control"] for c in cal["controls"] if not c["ok"]]
    rows.append((label, red, PUBLISHED[label], names))
    verdict = "OK" if red == PUBLISHED[label] else "DISAGREE"
    print("%-32s reverted -> %2d control(s) red   published=%d  %s"
          % (label, red, PUBLISHED[label], verdict))
    print("      red controls: %s" % ", ".join(names[:8]) + (" ..." if len(names) > 8 else ""))

print()
bad = [r for r in rows if r[1] != r[2]]
unpinned = [r for r in rows if r[1] == 0]
print("guards whose reversion turns NOTHING red (unpinned):",
      [r[0] for r in unpinned] or "none")
print("guards disagreeing with the published count:", [(r[0], r[1], r[2]) for r in bad] or "none")
(ROOT / "mutation_result.json").write_text(json.dumps(
    {"baseline_failed": base_fail,
     "guards": [{"guard": r[0], "controls_red_when_reverted": r[1],
                 "published": r[2], "red_control_names": r[3]} for r in rows]},
    indent=1), encoding="utf-8")
print("\nwrote", ROOT / "mutation_result.json")
