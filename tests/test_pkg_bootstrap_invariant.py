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

R310 — THE SECOND COSTUME
=========================

The R307 crucible was right that the class was not dead.  The sweep that
followed found the same invariant broken by a *different* idiom in six more
files: pop the module, re-import it for real (importlib binds the fresh copy on
the parent), then restore only the ``sys.modules`` entry.  Both halves then
exist and name **different objects**.

That form does not raise — it resolves successfully to the wrong module.  It
was reproduced end to end at base::

    pytest tests/panel/test_theme_source.py tests/test_hda_panel.py
    -> FAILED TestRegression::test_tokens_import_cleanly
       assert '#1F1F1F' == '#BDBDBD'

``import synapse.panel.designsystem.tokens as ds`` walked the parent attribute
to a headless reload while ``synapse.panel.tokens`` re-exported from the
host-seeded resident, so two names in one test came from two module objects.

The RUNTIME checks below are what generalise: the source regex in section 4
guards one shape only, and none of the R310 costumes match it.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import types
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
# 1b. R310 — the RESTORE half of the same invariant
# ---------------------------------------------------------------------------

def test_snapshot_keeps_absent_distinct_from_none():
    """``sys.modules.get(k)`` conflates 'missing' with the None sentinel.

    That conflation is what turns a deliberate absence into a plain removal on
    restore (or vice versa), so the snapshot has to keep them apart.
    """
    sys.modules.pop("_r310_absent", None)
    sys.modules["_r310_none"] = None
    try:
        snap = pkgbootstrap.snapshot_modules(["_r310_absent", "_r310_none"])
        assert snap["_r310_absent"] is pkgbootstrap.ABSENT
        assert snap["_r310_none"] is None
        # The naive dict cannot tell them apart — this is the contrast.
        naive = {k: sys.modules.get(k) for k in ("_r310_absent", "_r310_none")}
        assert naive["_r310_absent"] == naive["_r310_none"] is None
    finally:
        sys.modules.pop("_r310_none", None)


def test_restore_modules_rebinds_the_parent():
    """The R310 defect, reproduced in miniature and then fixed by the helper.

    A real re-import binds the FRESH module on the parent. Restoring only the
    ``sys.modules`` entry — what every hand-rolled teardown in the tree did —
    leaves the parent attribute on the throwaway.
    """
    root = pkgbootstrap.ensure_package("_r310_restore", REPO)
    original = pkgbootstrap.ensure_package("_r310_restore.leaf", REPO)
    try:
        saved = pkgbootstrap.snapshot_modules(["_r310_restore.leaf"])

        # Simulate the re-import: a NEW module object bound on the parent, the
        # way importlib._bootstrap._find_and_load would leave it.
        throwaway = types.ModuleType("_r310_restore.leaf")
        sys.modules["_r310_restore.leaf"] = throwaway
        setattr(root, "leaf", throwaway)

        # The old teardown: sys.modules only.
        sys.modules["_r310_restore.leaf"] = original
        assert getattr(root, "leaf") is throwaway, (
            "precondition: the naive restore must leave the parent attribute "
            "on the throwaway — otherwise this test proves nothing"
        )
        assert pkgbootstrap.divergent_modules("_r310_restore") == [
            "_r310_restore.leaf"]

        # The helper: both halves.
        pkgbootstrap.restore_modules(saved)
        assert sys.modules["_r310_restore.leaf"] is original
        assert getattr(root, "leaf") is original
        assert pkgbootstrap.divergent_modules("_r310_restore") == []
    finally:
        sys.modules.pop("_r310_restore.leaf", None)
        sys.modules.pop("_r310_restore", None)


def test_restore_modules_absent_clears_both_halves():
    """A name that was ABSENT before must be absent BOTH ways after —
    leaving the parent attribute behind is the divergence's other direction."""
    root = pkgbootstrap.ensure_package("_r310_absent_pkg", REPO)
    try:
        saved = pkgbootstrap.snapshot_modules(["_r310_absent_pkg.leaf"])
        assert saved["_r310_absent_pkg.leaf"] is pkgbootstrap.ABSENT
        pkgbootstrap.ensure_package("_r310_absent_pkg.leaf", REPO)
        assert hasattr(root, "leaf")

        pkgbootstrap.restore_modules(saved)
        assert "_r310_absent_pkg.leaf" not in sys.modules
        assert not hasattr(root, "leaf"), (
            "restore left the parent attribute pointing at a module that is no "
            "longer in sys.modules — divergence in the other direction")
    finally:
        sys.modules.pop("_r310_absent_pkg.leaf", None)
        sys.modules.pop("_r310_absent_pkg", None)


def test_restore_modules_never_deletes_a_legitimate_reexport():
    """``from pkg.mod import name`` shadowing a same-named submodule is legal
    Python and production ``synapse.cognitive`` does it. Clearing an ABSENT
    entry must not delete that attribute to tidy up."""
    root = pkgbootstrap.ensure_package("_r310_shadow", REPO)
    root.leaf = lambda: "re-export"          # non-module attribute
    try:
        pkgbootstrap.restore_modules({"_r310_shadow.leaf": pkgbootstrap.ABSENT})
        assert callable(getattr(root, "leaf", None)), (
            "restore_modules deleted a non-module re-export")
    finally:
        sys.modules.pop("_r310_shadow", None)


def test_install_module_binds_an_already_built_object():
    """``install_module`` is the setdefault-shaped planter for a module object
    you already hold (loaded by hand, or a deliberate stub)."""
    root = pkgbootstrap.ensure_package("_r310_install", REPO)
    built = types.ModuleType("_r310_install.leaf")
    try:
        got = pkgbootstrap.install_module("_r310_install.leaf", built)
        assert got is built
        assert sys.modules["_r310_install.leaf"] is built
        assert getattr(root, "leaf") is built
        # An existing entry wins, exactly like sys.modules.setdefault.
        other = types.ModuleType("_r310_install.leaf")
        assert pkgbootstrap.install_module("_r310_install.leaf", other) is built
    finally:
        sys.modules.pop("_r310_install.leaf", None)
        sys.modules.pop("_r310_install", None)


def test_rebind_modules_repairs_a_restore_it_did_not_own():
    """``rebind_modules`` is the reconciliation for restores this module does
    not perform — chiefly monkeypatch's ``setitem``/``delitem`` undo."""
    root = pkgbootstrap.ensure_package("_r310_rebind", REPO)
    original = pkgbootstrap.ensure_package("_r310_rebind.leaf", REPO)
    try:
        setattr(root, "leaf", types.ModuleType("_r310_rebind.leaf"))  # the undo gap
        assert pkgbootstrap.divergent_modules("_r310_rebind") == ["_r310_rebind.leaf"]
        pkgbootstrap.rebind_modules(["_r310_rebind.leaf"])
        assert getattr(root, "leaf") is original
        assert pkgbootstrap.divergent_modules("_r310_rebind") == []
    finally:
        sys.modules.pop("_r310_rebind.leaf", None)
        sys.modules.pop("_r310_rebind", None)


_ORDER_CHILD = '''
"""Does an autouse fixture's teardown run AFTER monkeypatch's undo?"""
import sys, types
import pytest

PARENT = types.ModuleType("_r310_ord")
PARENT.__path__ = []
ORIGINAL = types.ModuleType("_r310_ord.leaf")
sys.modules["_r310_ord"] = PARENT
sys.modules["_r310_ord.leaf"] = ORIGINAL
PARENT.leaf = ORIGINAL


@pytest.fixture(autouse=True)
def _autouse_rebind():
    yield
    # If monkeypatch has NOT undone yet, this is the replacement and the
    # rebind-after-undo strategy in the two converted files is unsound.
    assert sys.modules["_r310_ord.leaf"] is ORIGINAL, (
        "autouse teardown ran BEFORE monkeypatch.undo()")
    import pkgbootstrap
    pkgbootstrap.rebind_modules(["_r310_ord.leaf"])
    assert PARENT.leaf is ORIGINAL


def test_body(monkeypatch):
    replacement = types.ModuleType("_r310_ord.leaf")
    monkeypatch.setitem(sys.modules, "_r310_ord.leaf", replacement)
    PARENT.leaf = replacement            # what a real re-import would do
'''


def test_autouse_rebind_runs_after_monkeypatch_undo(tmp_path):
    """The ordering assumption two converted files depend on, PINNED.

    ``tests/test_g1a_followup_job_root_discovery.py`` and
    ``tests/test_start_hwebserver_durable_ref.py`` repair the parent binding
    from an autouse fixture, because monkeypatch exposes no teardown hook. That
    only works if autouse finalization happens AFTER monkeypatch's undo. It
    does — autouse fixtures set up first and therefore tear down last — but
    those two files would silently stop being fixed if that ever changed, so
    the ordering is asserted rather than assumed.
    """
    child = tmp_path / "test_r310_order.py"
    child.write_text(_ORDER_CHILD, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(child), "-p", "no:randomly",
         "-q", "--no-header", "-p", "no:cacheprovider",
         "-p", "no:cov", "--rootdir", str(tmp_path)],
        cwd=str(REPO), capture_output=True, text=True, timeout=300,
        env={**os.environ, "PYTHONPATH": str(TESTS)},
    )
    assert proc.returncode == 0, (
        "autouse-teardown-after-monkeypatch-undo no longer holds; the rebind "
        "fixtures in test_g1a_followup_job_root_discovery.py and "
        "test_start_hwebserver_durable_ref.py are unsound.\n"
        f"stdout:\n{proc.stdout[-2500:]}\nstderr:\n{proc.stderr[-1000:]}")


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
# 3b. R310 — RUNTIME divergence across the shapes the fresh-import probe
#     cannot see, and the victim order that reproduced at base
# ---------------------------------------------------------------------------

# Files whose planting/restoring happens in a FIXTURE or a TEST BODY, not at
# import time. Section 2's fresh-interpreter probe only imports a module, so it
# is structurally blind to all of these — which is why they survived R307.
R310_PERPETRATORS = [
    "tests/test_scene_memory.py",                    # setdefault plant (MISSING)
    "tests/test_mcp_protocol.py",                    # test-body plant (MISSING)
    "tests/test_resilience_fixes.py",                # test-body plant (MISSING)
    "tests/test_cops.py",                            # test-body plant
    "tests/test_tops.py",                            # test-body plant
    "tests/test_hda.py",                             # test-body plant
    "tests/test_routing.py",                         # pop/re-import/restore
    "tests/test_context_poll_offmain.py",            # fixture pop/re-import
    "tests/test_offmain_fallback.py",                # fixture pop/re-import
    "tests/test_g1a_followup_job_root_discovery.py",  # monkeypatch + reload
    "tests/test_start_hwebserver_durable_ref.py",    # monkeypatch + import
    "tests/panel/test_theme_source.py",              # reload + restore
    # These two were MASKED: they plant the same divergence as the file above
    # them in this list, so the "newly introduced" attribution credited the
    # first perpetrator only. They surfaced the moment their sibling was fixed
    # — which is the argument for a runtime gate over a fixed file list.
    "tests/panel/test_token_seeding.py",             # reload + restore
    "tests/test_worker_tool_policy.py",              # fixture pop/re-import
]

_RUNTIME_PLUGIN = '''
"""Fail the run if any dotted synapse module diverges from its parent
attribute once the tests have actually EXECUTED."""
import sys
import pkgbootstrap


def pytest_sessionfinish(session, exitstatus):
    bad = pkgbootstrap.divergent_modules("synapse.")
    if bad:
        print("R310-RUNTIME-DIVERGENT " + ",".join(bad))
'''


def test_r310_shapes_leave_no_runtime_divergence(tmp_path):
    """Run every R310 perpetrator and assert none leaves a divergent module.

    This is the check that GENERALISES. Section 4's regex guards a single
    source shape and none of the R310 costumes match it; section 2 imports a
    module and cannot see residue authored inside a fixture or a test body.
    Only executing the tests and inspecting the result covers both.

    Measured at base, this reported (per file, run alone):
    synapse.memory.evolution + synapse.memory.scene_memory, synapse.server.auth,
    synapse.mcp (all MISSING — dotted resolution RAISES), and
    synapse.server.handlers_memory, synapse.server.start_hwebserver,
    synapse.panel.designsystem.tokens (all WRONG-MOD — dotted resolution
    SUCCEEDS and returns a different object).
    """
    plugin_dir = tmp_path / "plug"
    plugin_dir.mkdir()
    (plugin_dir / "r310runtime.py").write_text(_RUNTIME_PLUGIN, encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(plugin_dir), str(TESTS), env.get("PYTHONPATH", "")])
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *R310_PERPETRATORS,
         "-p", "no:randomly", "-p", "r310runtime",
         "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=str(REPO), capture_output=True, text=True, env=env, timeout=1800,
    )
    # NB: pytest's progress line carries no trailing newline, so the plugin's
    # first line is glued to it — a startswith() filter silently drops it.
    # (That exact mistake made two probes disagree while chasing this class.)
    marker = "R310-RUNTIME-DIVERGENT "
    assert marker not in proc.stdout, (
        "an R310 perpetrator left a dotted synapse module diverging from its "
        "parent attribute:\n  "
        + proc.stdout.split(marker, 1)[1].split("\n")[0]
        + "\nPlant with pkgbootstrap.ensure_package/load_module/install_module; "
          "RESTORE with pkgbootstrap.restore_modules (or rebind_modules after a "
          "monkeypatch undo).")
    assert proc.returncode == 0, (
        "the R310 perpetrator set does not pass on its own:\n"
        f"{proc.stdout[-3000:]}")


def test_theme_source_then_hda_panel_passes():
    """The R310 victim order, end to end, in a fresh pytest process.

    At base this failed::

        FAILED tests/test_hda_panel.py::TestRegression::test_tokens_import_cleanly
        assert '#1F1F1F' == '#BDBDBD'

    ``import synapse.panel.designsystem.tokens as ds`` resolved through the
    parent attribute (left pointing at test_theme_source's headless reload)
    while ``synapse.panel.tokens`` re-exported from the host-seeded resident in
    ``sys.modules``. Two module objects, one dotted name — the quiet form of
    this defect, which returns the wrong thing instead of raising.

    Whole FILES, for the same reason section 3 keeps that form: a
    ``file::test`` node id makes pytest import the victim first, which
    pre-imports the module for real and hides the residue.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/panel/test_theme_source.py", "tests/test_hda_panel.py",
         "-p", "no:randomly", "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=str(REPO), capture_output=True, text=True, timeout=600,
    )
    if proc.returncode != 0:
        known = "test_tokens_import_cleanly" in proc.stdout
        raise AssertionError(
            ("the R310 tokens divergence is BACK — the known victim failed "
             "behind tests/panel/test_theme_source.py.\n"
             if known else
             "`pytest tests/panel/test_theme_source.py tests/test_hda_panel.py` "
             "failed, but NOT on the known victim test — an unrelated failure "
             "in the pair run.\n")
            + f"stdout tail:\n{proc.stdout[-3000:]}")


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
