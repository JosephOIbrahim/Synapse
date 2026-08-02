"""R307 — pins the sys.modules / parent-attribute invariant in tests/.

THE DEFECT THIS PINS
====================

``pytest tests/test_tops.py tests/test_websocket_cancel_reachable.py`` used to
fail ``test_handle_client_cancel_mid_frame``::

    python\\synapse\\__init__.py:450: in __getattr__
        raise AttributeError(f"module 'synapse' has no attribute {name!r}")
    E   AttributeError: module 'synapse' has no attribute 'server'
    ...
    E   AttributeError: 'module' object at synapse.server has no attribute 'server'

Cause: 25 test modules hand-planted ``sys.modules["synapse.server"]`` without
binding ``server`` on the ``synapse`` package — half of what importlib does.
``monkeypatch.setattr("synapse.server.websocket.get_bridge", ...)`` walks that
dotted string with ``getattr``, and its ``importlib.import_module`` fallback
returns the cached module without ever performing the missing binding.

The residue outlives the test that planted it, so the victim is always some
later, unrelated test.  The full suite hid it: by the time the websocket test
runs there, an earlier real import has already made ``synapse.server`` a proper
package.  Green-by-ordering is exactly what these tests refuse to accept.

Fix: ``tests/pkgbootstrap.py`` plants *and* binds.  These tests fail if any of
that comes undone.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

import pkgbootstrap

REPO = Path(__file__).resolve().parent.parent
TESTS = REPO / "tests"

# The victim, and the exact dotted target its monkeypatch resolves.
VICTIM_FILE = "tests/test_websocket_cancel_reachable.py"
VICTIM_TEST = "test_handle_client_cancel_mid_frame"
VICTIM_TARGET = "synapse.server.websocket.get_bridge"

# Perpetrators named in the R307 brief, plus one sibling proving the defect was
# never a ``test_tops`` property — any bootstrap file reproduced it.
PERPETRATORS = ["test_tops.py", "test_tops_assembly.py", "test_cops.py"]


# ---------------------------------------------------------------------------
# 1. The helper itself keeps both halves together
# ---------------------------------------------------------------------------

def test_ensure_package_binds_on_parent():
    """``ensure_package`` must leave sys.modules and the attribute identical."""
    root = pkgbootstrap.ensure_package("_r307_pkg", REPO)
    child = pkgbootstrap.ensure_package("_r307_pkg.sub", REPO)
    try:
        assert sys.modules["_r307_pkg.sub"] is child
        assert getattr(root, "sub") is child, (
            "ensure_package planted sys.modules['_r307_pkg.sub'] without "
            "binding `sub` on its parent — the R307 divergence"
        )
        assert pkgbootstrap.divergent_modules("_r307_pkg") == []
    finally:
        sys.modules.pop("_r307_pkg.sub", None)
        sys.modules.pop("_r307_pkg", None)


def test_load_module_binds_on_parent(tmp_path):
    """``load_module`` must bind the file-loaded module on its parent too."""
    (tmp_path / "leaf.py").write_text("VALUE = 307\n", encoding="utf-8")
    root = pkgbootstrap.ensure_package("_r307_load", tmp_path)
    try:
        leaf = pkgbootstrap.load_module("_r307_load.leaf", tmp_path / "leaf.py")
        assert leaf.VALUE == 307
        assert sys.modules["_r307_load.leaf"] is leaf
        assert getattr(root, "leaf") is leaf
        assert pkgbootstrap.divergent_modules("_r307_load") == []
    finally:
        sys.modules.pop("_r307_load.leaf", None)
        sys.modules.pop("_r307_load", None)


def test_divergent_modules_actually_detects_divergence():
    """The detector must not be vacuously green — plant the bug and see it."""
    root = pkgbootstrap.ensure_package("_r307_detect", REPO)
    child = pkgbootstrap.ensure_package("_r307_detect.sub", REPO)
    try:
        assert pkgbootstrap.divergent_modules("_r307_detect") == []
        delattr(root, "sub")  # exactly what the raw sys.modules idiom left behind
        assert pkgbootstrap.divergent_modules("_r307_detect") == ["_r307_detect.sub"]
        pkgbootstrap.bind_to_parent("_r307_detect.sub", child)
        assert pkgbootstrap.divergent_modules("_r307_detect") == []
    finally:
        sys.modules.pop("_r307_detect.sub", None)
        sys.modules.pop("_r307_detect", None)


# ---------------------------------------------------------------------------
# 2. No bootstrap file leaves residue behind — checked in a clean interpreter
# ---------------------------------------------------------------------------

_RESIDUE_CHILD = r"""
import importlib.util, sys
from pathlib import Path

repo, target = Path(sys.argv[1]), sys.argv[2]
sys.path.insert(0, str(repo / "python"))
sys.path.insert(0, str(repo / "tests"))

spec = importlib.util.spec_from_file_location("_r307_target", repo / "tests" / target)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

import pkgbootstrap
bad = pkgbootstrap.divergent_modules("synapse")
if bad:
    print("DIVERGENT " + ",".join(bad))
    raise SystemExit(1)

# The victim's monkeypatch target must resolve the same way pytest resolves it.
from _pytest.monkeypatch import derive_importpath
derive_importpath(sys.argv[3], raising=True)
print("CLEAN")
"""


@pytest.mark.parametrize("perpetrator", PERPETRATORS)
def test_bootstrap_leaves_no_parent_attribute_divergence(tmp_path, perpetrator):
    """Import a bootstrap test module in a fresh interpreter; nothing under
    ``synapse.`` may end up in sys.modules without being bound on its parent,
    and the victim's monkeypatch target must still resolve.

    A fresh interpreter is the whole point: inside the running suite an earlier
    real import masks the divergence, which is how this survived unnoticed.
    """
    child = tmp_path / "residue_child.py"
    child.write_text(_RESIDUE_CHILD, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(child), str(REPO), perpetrator, VICTIM_TARGET],
        capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0 and "CLEAN" in proc.stdout, (
        f"{perpetrator} left the R307 residue behind.\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr[-2000:]}"
    )


# ---------------------------------------------------------------------------
# 3. The reported ordering, end to end
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("perpetrator", ["tests/test_tops.py", "tests/test_tops_assembly.py"])
def test_failing_order_passes(perpetrator):
    """Run the exact order from the R307 brief in a fresh pytest process.

    Not a reordering and not an xfail — the real pair, in the order that used
    to fail.  If the residue returns, this goes red.

    Both arguments are whole FILES on purpose.  Passing the victim as a
    ``file::test`` node id instead makes pytest import the victim module before
    the perpetrator, which pre-imports ``synapse.server`` for real and hides the
    defect — verified against the reverted perpetrator.  A pin that cannot fail
    is worse than no pin, so this one keeps the reproducing argument form.
    """
    proc = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            perpetrator,
            VICTIM_FILE,
            "-p", "no:randomly", "-q", "--no-header", "-p", "no:cacheprovider",
        ],
        cwd=str(REPO), capture_output=True, text=True, timeout=600,
    )
    if proc.returncode != 0:
        # Disambiguate (attack-O nit): a failure of the KNOWN VICTIM test is
        # the ordering defect returning; any other failure in the pair run is
        # its own problem and must not masquerade as one. Whole-file argument
        # form is kept deliberately — node-id form pre-imports the victim and
        # hides the defect (verified against the reverted perpetrator).
        ordering = "test_handle_client_cancel_mid_frame" in proc.stdout
        raise AssertionError(
            (f"the R307 ordering defect is BACK — the known victim failed "
             f"behind {perpetrator}.\n"
             if ordering else
             f"`pytest {perpetrator} {VICTIM_FILE}` failed, but NOT on the "
             f"known victim test — an unrelated failure in the pair run, "
             f"not (necessarily) the ordering defect.\n")
            + f"stdout tail:\n{proc.stdout[-3000:]}\n"
              f"stderr tail:\n{proc.stderr[-1500:]}")


# ---------------------------------------------------------------------------
# 4. The raw idiom must not be copy-pasted back in
# ---------------------------------------------------------------------------

# Optional indentation (attack-O nit: requiring leading whitespace let a
# top-level copy of the same four lines through).
_RAW_PKG_IDIOM = re.compile(
    r"^(?P<ind>[ \t]*)if (?P<key>[A-Za-z_]\w*) not in sys\.modules:\n"
    r"(?P=ind)[ \t]+(?P<pkg>[A-Za-z_]\w*) = types\.ModuleType\((?P=key)\)\n"
    r"(?P=ind)[ \t]+(?P=pkg)\.__path__ = \[str\([^\n]+?\)\]\n"
    r"(?P=ind)[ \t]+sys\.modules\[(?P=key)\] = (?P=pkg)\n",
    re.MULTILINE,
)


def test_raw_namespace_package_idiom_is_not_reintroduced():
    """Guards ONE SHAPE: the canonical four-line copy-paste block that spread
    to 25 files. A source-shape tripwire, not the invariant itself (attack-O:
    the first docstring over-claimed exactly that way). Variants — different
    variable dances, spec_from_file_location shapes, guard-less plants — pass
    this regex freely; they are caught at RUNTIME by the divergence checks in
    this file, and the remaining in-tree shapes are R310's sweep. Use
    ``pkgbootstrap.ensure_package`` / ``load_module`` instead."""
    offenders = [
        p.name for p in sorted(TESTS.glob("test_*.py"))
        if _RAW_PKG_IDIOM.search(p.read_text(encoding="utf-8", errors="replace"))
    ]
    assert offenders == [], (
        "these test modules plant a namespace package into sys.modules without "
        "binding it on its parent package (R307): " + ", ".join(offenders) +
        " — call pkgbootstrap.ensure_package(name, path) instead."
    )
