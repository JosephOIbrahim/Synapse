"""SR1 M3 — run the Solaris LIVE tier inside hython 22.0.368.

    "C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe" \
        tests/solaris/run_live.py

Without Houdini the live tests SKIP (Constitution Law 1: a skip is honest, a
pass is a lie). This runner is how we prove they are not ONLY ever skipping —
a suite that can only skip is as vacuous as one that can only pass.

Exit code is pytest's. A RED result here is a finding (Law 7), not a reason to
weaken a test.
"""

import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "python"))

import pytest  # noqa: E402

os.chdir(_REPO)

sys.exit(pytest.main([
    str(_REPO / "tests" / "solaris" / "test_live_wiring.py"),
    "-p", "no:cacheprovider",
    "-v", "-rA",
    "--no-header",
    "--basetemp", os.environ.get("SR1_BASETEMP", str(_REPO / ".pytest_sr1_live")),
    "--confcutdir", str(_REPO / "tests" / "solaris"),
] + sys.argv[1:]))
