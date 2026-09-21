"""Invariant 5 (harness/jev/README.md, amended 2026-09-21): nothing under the product
package imports the build-time Jev harness. A product-path judgment, if one ever ships, goes
through a package-side adapter under python/synapse/ that meets conditions (a)-(f) in the
README; it never reaches back into harness/jev. This test pins the retained half of the
invariant so the amendment cannot silently widen into "import the harness client".
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_DIRS = [ROOT / "python" / "synapse", ROOT / "shared"]
FORBIDDEN = re.compile(
    r"(from\s+harness(\.|\s)|import\s+harness\b|harness.jev|\bjev_client\b|\bjev_route\b|\bjev_screen\b)"
)


def _product_files():
    for d in PRODUCT_DIRS:
        for p in d.rglob("*.py"):
            if "_vendor" in p.parts or "__pycache__" in p.parts:
                continue
            yield p


def test_product_package_never_imports_harness_jev():
    hits = []
    for p in _product_files():
        text = p.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if FORBIDDEN.search(stripped):
                hits.append(f"{p.relative_to(ROOT)}:{i}: {stripped[:100]}")
    assert not hits, "product code reaches into harness/jev (invariant 5):\n" + "\n".join(hits)


def test_readme_states_the_amended_invariant():
    readme = (ROOT / "harness" / "jev" / "README.md").read_text(encoding="utf-8")
    assert "off the product path by default" in readme
    assert "tests/test_jev_product_boundary.py" in readme
    for cond in ("(a)", "(b)", "(c)", "(d)", "(e)", "(f)"):
        assert cond in readme, f"condition {cond} missing from invariant 5"
