"""S1 producer path — how much of the test suite can disagree with the host.

The single fact that governs every WORKS verdict in this leg:
``tests/conftest.py`` plants a CANONICAL FAKE ``hou`` into ``sys.modules`` at
collection time when no real one is resident. So under plain ``pytest`` every
``import hou`` succeeds — and ``pytest.importorskip("hou")`` is NOT a live gate
anywhere in this suite. The only honest gate is a HOST-IDENTITY probe: the
planted fake carries ``__synapse_canonical__``; real Houdini does not.

Emits harness/notes/forensic/s1_test_honesty.json.

Law 1 — how this can fail: if the fake-planting block disappears from
conftest.py, ``planter_found`` goes False and the premise of this whole
measurement is void; the script says so instead of quietly reporting numbers.
"""

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]
TESTS = ROOT / "tests"

test_files = sorted(
    p for p in TESTS.rglob("*.py") if "__pycache__" not in p.parts
)

conftest = (TESTS / "conftest.py").read_text(encoding="utf-8", errors="replace")
planter_found = bool(
    re.search(r'if\s+"hou"\s+not\s+in\s+sys\.modules', conftest)
    and re.search(r'sys\.modules\["hou"\]\s*=\s*_build_canonical_hou\(\)', conftest)
)

MOCK = re.compile(r"MagicMock|\bMock\(", re.I)
IMPORTORSKIP_HOU = re.compile(r'importorskip\(\s*["\']hou["\']')
HOST_IDENTITY = re.compile(r"__synapse_canonical__")

rows = []
for p in test_files:
    src = p.read_text(encoding="utf-8", errors="replace")
    rel = str(p.relative_to(ROOT)).replace("\\", "/")
    rows.append({
        "file": rel,
        "mock_hou": bool(MOCK.search(src)),
        "importorskip_hou": bool(IMPORTORSKIP_HOU.search(src)),
        "host_identity_gate": bool(HOST_IDENTITY.search(src)),
    })

gated = [r["file"] for r in rows if r["host_identity_gate"]]
# conftest.py PLANTS the fake; two files are meta-guards ABOUT the fixture
# rather than host-behaviour assertions on a tool.
INFRA = {
    "tests/conftest.py",
    "tests/test_hou_reimport_guard.py",
    "tests/test_residency_guard_fires.py",
}
host_behaviour = [f for f in gated if f not in INFRA]

out = {
    "producer": "harness/notes/forensic/_s1_test_honesty.py",
    "premise": {
        "planter_found": planter_found,
        "anchor": "tests/conftest.py:132-135",
        "statement": (
            "tests/conftest.py plants a canonical fake `hou` into sys.modules "
            "when none is resident, so `import hou` always succeeds under plain "
            "pytest and importorskip('hou') cannot gate anything."
        ),
        "void_if_false": (
            "If planter_found is False the fixture changed and every number "
            "below must be re-derived before it is cited."
        ),
    },
    "test_files_total": len(rows),
    "files_using_mock": sum(1 for r in rows if r["mock_hou"]),
    "files_using_importorskip_hou": sum(1 for r in rows if r["importorskip_hou"]),
    "files_with_host_identity_gate": len(gated),
    "host_identity_gate_files": gated,
    "host_behaviour_files": host_behaviour,
    "host_behaviour_file_count": len(host_behaviour),
    "headline": (
        f"{len(host_behaviour)} of {len(rows)} test files carry a gate that can "
        f"disagree with the live host. {sum(1 for r in rows if r['mock_hou'])} "
        f"build a mock."
    ),
}

dest = ROOT / "harness" / "notes" / "forensic" / "s1_test_honesty.json"
dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "host_identity_gate_files"}, indent=1))
