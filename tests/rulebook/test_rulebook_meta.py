"""Rulebook meta-tests (Mile 0) — the five §4 discipline gates.

The enforcement layer exists before any content does. On the empty ratified
set every gate is trivially green; the enforcement is PROVEN live by the
meta-test-2 bad-manifest fixture — a ratified rule with a missing binding is
flagged BY RULE ID even while the real set is empty.

Commandment 7: an awkward meta-test means fix the implementation, never the test.

Cross-platform note: hashes normalize line endings (CRLF/CR -> LF) so the
amendment lock is stable across a Windows author and a Linux CI runner.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

_HERE = Path(__file__).resolve()
_REPO = _HERE.parent.parent.parent            # tests/rulebook/ -> tests/ -> repo root
_RULEBOOK = _REPO / "rulebook"
_MANIFEST = _RULEBOOK / "manifest.json"
_PHANTOMS = _RULEBOOK / "phantoms.json"
_CONTRACTS = _RULEBOOK / "contracts"
_SURFACES = _RULEBOOK / "surfaces"
_SYNAPSE_SRC = _REPO / "python" / "synapse"

_VALID_STATUSES = {"draft", "ratified", "rfc-gated", "superseded"}


# --------------------------------------------------------------------------- #
# shared helpers — the same code the real-manifest tests and the fixtures call #
# --------------------------------------------------------------------------- #

def _load_manifest() -> dict:
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))


def _norm(data: bytes) -> bytes:
    """Line-ending-normalized bytes (CRLF/CR -> LF): keeps the amendment-lock
    hash identical whether the tree was checked out on Windows or Linux."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def contracts_tree_hash(root: Path = _CONTRACTS) -> str:
    """Deterministic sha256 over every file under ``contracts/`` (sorted by
    POSIX relpath, line-ending-normalized). This is the value the manifest
    stores in ``contracts_checksum`` and meta-test 4 recomputes."""
    h = hashlib.sha256()
    if root.is_dir():
        files = sorted(
            (p for p in root.rglob("*") if p.is_file()),
            key=lambda q: q.relative_to(root).as_posix(),
        )
        for p in files:
            h.update(p.relative_to(root).as_posix().encode("utf-8"))
            h.update(b"\0")
            h.update(_norm(p.read_bytes()))
            h.update(b"\0")
    return h.hexdigest()


def _binding_exists(node_id: str) -> bool:
    """True iff the pytest node ID resolves to a real, defined test.

    Checks the file exists and the target function/method is defined (via AST —
    no import side effects, no nested pytest run). Node forms accepted:
    ``path::func`` and ``path::Class::method``. "Passes" is enforced separately
    by the suite's own greenness: a bound test that exists but fails turns the
    whole suite red, which CI catches. This gate enforces existence/collectability.
    """
    parts = node_id.split("::")
    if len(parts) < 2:
        return False
    rel_path, *qual = parts
    f = _REPO / rel_path
    if not f.is_file():
        return False
    try:
        tree = ast.parse(f.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return False
    funcs: set[str] = set()
    quals: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    quals.add(f"{node.name}::{sub.name}")
    return "::".join(qual) in quals or qual[-1] in funcs


def unbound_ratified_rules(manifest: dict) -> list[str]:
    """IDs of ``ratified`` rules lacking at least one existing test binding.
    Empty list == the binding discipline holds. A rule inherits its section's
    status when it declares none."""
    offenders: list[str] = []
    for section in manifest.get("sections", []):
        section_status = section.get("status")
        for rule in section.get("rules", []):
            status = rule.get("status", section_status)
            if status != "ratified":
                continue
            tests = rule.get("tests") or []
            if not any(_binding_exists(t) for t in tests):
                offenders.append(rule["id"])
    return offenders


# --------------------------------------------------------------------------- #
# Meta-test 1 — Schema                                                         #
# --------------------------------------------------------------------------- #

def test_meta1_manifest_schema_valid() -> None:
    m = _load_manifest()
    assert isinstance(m.get("rulebook_version"), str) and m["rulebook_version"]
    rb = m.get("runtime_baseline")
    assert isinstance(rb, dict)
    assert {"houdini_graphical", "hython", "python", "platform"} <= set(rb), rb
    assert isinstance(m.get("contracts_checksum"), str) and m["contracts_checksum"]
    assert isinstance(m.get("sections"), list)
    for section in m["sections"]:
        assert section["status"] in _VALID_STATUSES, (
            f"{section.get('id')}: status {section['status']!r} not in {_VALID_STATUSES}"
        )
        seg = _RULEBOOK / section["path"]
        assert seg.exists(), f"{section.get('id')}: path {section['path']!r} does not exist"
        for rule in section.get("rules", []):
            rstatus = rule.get("status", section["status"])
            assert rstatus in _VALID_STATUSES, (
                f"{rule.get('id')}: status {rstatus!r} not in {_VALID_STATUSES}"
            )


# --------------------------------------------------------------------------- #
# Meta-test 2 — Binding (+ fail-by-rule-ID proof)                              #
# --------------------------------------------------------------------------- #

def test_meta2_ratified_rules_have_green_bindings() -> None:
    """Every ratified rule in the LIVE manifest binds to an existing test.
    Empty ratified set => []."""
    offenders = unbound_ratified_rules(_load_manifest())
    assert offenders == [], f"ratified rules with no collectable binding: {offenders}"


def test_meta2_binding_gate_fails_by_rule_id() -> None:
    """PROOF the gate bites even on the empty set: inject a manifest whose
    ratified rule points at a non-existent test; the checker names it BY ID."""
    bad = {
        "rulebook_version": "0.1.0",
        "runtime_baseline": {
            "houdini_graphical": "21.0.671",
            "hython": "21.0.631",
            "python": "3.11",
            "platform": "win_amd64",
        },
        "contracts_checksum": "deadbeef",
        "sections": [
            {
                "id": "RB-BAD",
                "path": "contracts",
                "status": "ratified",
                "rules": [
                    {
                        "id": "RB-BAD-999",
                        "summary": "deliberately unbound ratified rule (fixture)",
                        "tests": ["tests/rulebook/test_does_not_exist.py::test_missing"],
                    }
                ],
            }
        ],
    }
    assert unbound_ratified_rules(bad) == ["RB-BAD-999"]


def test_meta2_binding_gate_accepts_a_real_binding() -> None:
    """Symmetric proof: a ratified rule pointing at THIS test is not flagged —
    the gate distinguishes real bindings from missing ones."""
    good = {
        "sections": [
            {
                "id": "RB-SELF",
                "status": "ratified",
                "rules": [
                    {
                        "id": "RB-SELF-001",
                        "tests": [
                            "tests/rulebook/test_rulebook_meta.py::"
                            "test_meta2_binding_gate_accepts_a_real_binding"
                        ],
                    }
                ],
            }
        ]
    }
    assert unbound_ratified_rules(good) == []


# --------------------------------------------------------------------------- #
# Meta-test 3 — Surface integrity                                             #
# --------------------------------------------------------------------------- #

def test_meta3_surface_checksums_match() -> None:
    """Every harvested surface file carries generated_by + a checksum in its
    build's _meta.json, and the recomputed checksum matches. Hand-edits die.
    Empty surfaces/ (Mile 0) => trivially green."""
    if not _SURFACES.is_dir():
        return
    for meta in _SURFACES.rglob("_meta.json"):
        data = json.loads(meta.read_text(encoding="utf-8"))
        assert data.get("generated_by"), f"{meta}: missing generated_by"
        for entry in data.get("files", []):
            target = meta.parent / entry["name"]
            assert target.is_file(), f"{target} listed in {meta} but not on disk"
            got = hashlib.sha256(_norm(target.read_bytes())).hexdigest()
            assert got == entry["sha256"], (
                f"{target}: checksum drift — surfaces/ is harvested, never hand-edited"
            )


# --------------------------------------------------------------------------- #
# Meta-test 4 — Amendment lock                                                #
# --------------------------------------------------------------------------- #

def test_meta4_contracts_amendment_lock() -> None:
    """The recomputed contracts/ tree hash must equal manifest.contracts_checksum.
    A contract edit without a same-commit rehash fails here."""
    m = _load_manifest()
    assert contracts_tree_hash() == m["contracts_checksum"], (
        "contracts/ tree hash != manifest.contracts_checksum — a contract "
        "changed without a manifest rehash. Rehash + bump in the same commit "
        "(rulebook amendment protocol, blueprint §4)."
    )


# --------------------------------------------------------------------------- #
# Meta-test 5 — Phantom lint                                                  #
# --------------------------------------------------------------------------- #

def test_meta5_phantom_lint() -> None:
    """No quarantined phantom symbol appears in python/synapse/ (excluding
    _vendor/). Mirrors tests/test_cognitive_boundary.py, pointed at the
    quarantine. Empty phantoms.json (Mile 0) => trivially green; Mile 2
    populates the quarantine and this gate arms."""
    phantoms = json.loads(_PHANTOMS.read_text(encoding="utf-8")).get("phantoms", [])
    symbols = [p["symbol"] for p in phantoms if p.get("symbol")]
    if not symbols or not _SYNAPSE_SRC.is_dir():
        return
    patterns = [(s, re.compile(r"(?<![\w.])" + re.escape(s))) for s in symbols]
    violators: list[str] = []
    for py in sorted(_SYNAPSE_SRC.rglob("*.py")):
        if "_vendor" in py.parts:
            continue
        src = py.read_text(encoding="utf-8", errors="ignore")
        for sym, pat in patterns:
            for m in pat.finditer(src):
                line = src[: m.start()].count("\n") + 1
                violators.append(f"{py.relative_to(_REPO)}:{line} -> {sym}")
    assert not violators, (
        "quarantined phantom symbols referenced (phantoms.json):\n  "
        + "\n  ".join(violators)
    )
