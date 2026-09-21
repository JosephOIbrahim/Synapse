# bump_version.py - 5.76.1 -> 5.77.0 in every pinned place, in Python (no PowerShell encoding round-trip).
# Lesson of v5.76.0: README's tag line is not touched by the version sync; patch it explicitly and verify.
import re
from pathlib import Path

OLD, NEW = "5.76.1", "5.77.0"
REPO = Path(r"C:\Users\User\SYNAPSE")
files = ["VERSION", "pyproject.toml", "python/synapse/__init__.py", "README.md", "CLAUDE.md"]
for f in files:
    p = REPO / f
    b = p.read_bytes()
    t = b.decode("utf-8")
    n = t.count(OLD)
    t2 = t.replace(OLD, NEW)
    if f == "README.md":
        # the "New in" paragraph: point it at the new notes, keep the old paragraph as history
        t2 = t2.replace("**New in 5.77.0** - no product change. The build harness learned to judge before it spends",
                        "**New in 5.77.0** - turn two answers: router tier timeouts enforced, panel response watchdog; the harness gained the JEV helm (see [release notes](docs/releases/v5.77.0.md)).\n\n**5.76.1** - no product change. The build harness learned to judge before it spends", 1)
    p.write_bytes(t2.encode("utf-8"))
    print(f"{f}: {n} -> replaced; remaining {OLD}: {t2.count(OLD)}")
left = [f for f in files if OLD in (REPO / f).read_text(encoding="utf-8")]
print("still pinned to old:", left or "none")
