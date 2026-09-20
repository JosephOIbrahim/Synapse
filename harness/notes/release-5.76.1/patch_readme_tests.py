# patch for v5.76.1: README release-tag line + notes link + "New in" block; test import.
# Download links stay on the v5.75.2 installer assets (no new installer in this release).
import re
from pathlib import Path

ROOT = Path(r"C:\Users\User\SYNAPSE")
MID = "\u00b7"

# 1) test import
t = ROOT / "tests" / "test_undob_live_undo_grouping.py"
s = t.read_text(encoding="utf-8")
if "\nimport re\n" not in s:
    s = s.replace("\nimport sys\n", "\nimport re\nimport sys\n", 1)
    t.write_text(s, encoding="utf-8")
    print("test: import re added")

# 2) README
r = ROOT / "README.md"
s = r.read_text(encoding="utf-8")
n0 = s.count("v5.75.2 is Latest")
s = s.replace("tags: v5.75.2 is Latest", "tags: v5.76.1 is Latest", 1)
old_block_head = "**New in 5.75.2** \u2014 no product change. The gates around releasing got honest."
new_block = (
    "**New in 5.76.1** \u2014 no product change. The build harness learned to judge before it spends.\n\n"
    "Jev (TypeSafe System One) now sits on the wave graph as typed guard nodes: it picks the execution tier for a "
    "harness mission and pre-reads builder receipts for the referee, every call ledgered, every failure falling "
    "closed to the previous behaviour. Nothing under `panel/` or `synapse/` imports it; the installer below is "
    "unchanged from 5.75.2. [Release details \u2192](docs/releases/v5.76.1.md)\n\n"
    "**New in 5.75.2** \u2014 no product change. The gates around releasing got honest."
)
assert old_block_head in s, "New in 5.75.2 head not found"
s = s.replace(old_block_head, new_block, 1)
s = s.replace("- [Release notes](docs/releases/v5.75.2.md)", "- [Release notes](docs/releases/v5.76.1.md)", 1)
r.write_text(s, encoding="utf-8")
print("readme: tag line", n0, "->", s.count("v5.76.1 is Latest"), "| notes link", "v5.76.1.md" in s)
