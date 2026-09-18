"""The product surface is a claim, and this pins its width in both directions.

``scripts/product_surface.py`` defines what "the product" means for the release
ritual's *product unchanged* sentence. A gate like that fails two ways, and the
repo has been bitten by the first:

  TOO NARROW -- the pathspec ``-- python installer``, copy-forwarded into every
    release producer since v5.70.1, cannot see the nineteen tracked ``.py``
    files at the repository root. Seven are the shipped MCP surface. Commit
    c6221f3b ("asyncio.run() was disabling every MCP tool call under Houdini")
    moved 65 lines of ``mcp_server.py`` and nothing else; the narrow pathspec
    returns EMPTY for it, so the ritual would have reported the product
    unchanged over a fix to the MCP entry point.

  TOO WIDE -- a pathspec that grows until it covers ``harness/`` or ``tools/``
    reports a product change on every release and stops carrying information.
    Today's cleanup work touches ``tools/``; a gate that flagged it would be
    noise, not signal.

These tests read the git index only -- no history, no network -- so they run on
a depth-1 CI checkout. None of them can pass vacuously: each asserts against a
resolved, non-empty file set.
"""
from __future__ import annotations

import importlib.util
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODULE_PATH = os.path.join(REPO, "scripts", "product_surface.py")


def _load():
    spec = importlib.util.spec_from_file_location("product_surface", _MODULE_PATH)
    assert spec and spec.loader, "cannot load %s" % _MODULE_PATH
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ps():
    assert os.path.exists(_MODULE_PATH), (
        "scripts/product_surface.py is the one definition of the product surface; "
        "the release ritual's 'product unchanged' claim reads it"
    )
    return _load()


@pytest.fixture(scope="module")
def matched(ps):
    """Every tracked file the product pathspec resolves to."""
    files = set()
    for term in ps.PRODUCT_PATHSPEC:
        files.update(ps.tracked(term))
    assert files, "the product pathspec resolved to nothing at all"
    return files


def test_no_dead_terms(ps):
    """A term matching zero files makes the gate abstain while printing a pass."""
    dead = [t for t, n in ps.resolve() if n == 0]
    assert not dead, (
        "pathspec term(s) %s match no tracked file. An empty diff from a dead "
        "term is indistinguishable from an unchanged tree, and git reports "
        "neither -- the gate would print PASS over anything." % dead
    )


def test_covers_every_shipped_entry_point(matched):
    """The narrowing regression. These are the files the old pathspec missed."""
    required = {
        "mcp_server.py",       # .mcp.json launches exactly this
        "mcp_tools_cops.py",
        "mcp_tools_memory.py",
        "mcp_tools_render.py",
        "mcp_tools_scene.py",
        "mcp_tools_tops.py",
        "mcp_tools_usd.py",
        "install.py",
        "run_panel.py",
    }
    missing = sorted(required - matched)
    assert not missing, (
        "the product surface no longer covers %s. c6221f3b changed 65 lines of "
        "mcp_server.py and nothing under python/ or installer/ -- dropping these "
        "restores the exact blind spot this definition was written to close." % missing
    )


def test_covers_the_package_and_the_installer(matched):
    """The two trees the original pathspec did get right."""
    assert any(f.startswith("python/synapse/") for f in matched), \
        "the product surface no longer covers python/synapse/"
    assert any(f.startswith("installer/") for f in matched), \
        "the product surface no longer covers installer/"


def test_vendored_code_is_product(matched):
    """_vendor is a NON-SURFACE for version sync and still part of the product.

    sync_version.py skips python/synapse/_vendor/* because upstream packages do
    not carry SYNAPSE's version string. That is a versioning decision, not a
    shipping one: vendored code is in the payload, so if it moves the product
    moved. Conflating the two lists is how _vendor would fall out of the delta.
    """
    assert any(f.startswith("python/synapse/_vendor/") for f in matched), (
        "vendored code dropped out of the product surface. It ships in the "
        "payload; a change there is a product change even though version sync "
        "correctly ignores it."
    )


def test_does_not_creep_into_non_product_trees(ps, matched):
    """The widening regression. A gate covering everything carries no signal."""
    offenders = {}
    for prefix in ps.NON_PRODUCT:
        hits = sorted(f for f in matched if f.startswith(prefix))
        if hits:
            offenders[prefix] = hits[:3]
    assert not offenders, (
        "the product surface has grown into declared non-product trees: %r. "
        "A pathspec that covers harness/ or tools/ reports a product change on "
        "every release and stops meaning anything." % offenders
    )


def test_reported_command_is_the_command_that_runs(ps):
    """release-5.71.0/compose_assets.py:143 records a check naming v5.70.0 while
    :144 runs v5.70.1, and that label shipped in installer-verification.json.
    The command string must be derived from the same terms the diff uses."""
    cmd = ps.command("vA", "vB")
    assert cmd.startswith("git diff --stat vA vB -- "), cmd
    for term in ps.PRODUCT_PATHSPEC:
        assert term in cmd, (
            "reported command omits pathspec term %r; a recorded check that does "
            "not name what it ran is how a published claim drifts from its "
            "producer" % term
        )
