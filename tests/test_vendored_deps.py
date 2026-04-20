"""Sprint 3 Spike 2.2 — vendored dependency tests.

Pins the contract that ``python/synapse/_vendor/`` exists, carries
the Anthropic SDK stack compiled for Python 3.11 win_amd64, and is
wired into ``sys.path`` when and only when the host interpreter
matches that ABI.

Why the version gate matters
----------------------------
Stock Python 3.14 (the 2684-test interpreter) cannot load the
``_pydantic_core.cp311-win_amd64.pyd`` binary shipped in
``_vendor/pydantic_core/``. If the prepend were unconditional, the
entire Inspector suite would break on import. The version gate in
``python/synapse/__init__.py`` keeps the vendor tree passive under
Python 3.14 — system pydantic (CP314 user-site) continues to
resolve unchanged.

On Python 3.11 (every current Houdini point release — 21.0.631,
21.0.671, 21.5.x share this interpreter), the prepend activates
and the agent-loop daemon picks up anthropic straight from the
vendor tree, independent of whether any given Houdini install has
its own site-packages-level install of the SDK.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

import synapse


# ---------------------------------------------------------------------------
# _vendor/ directory layout
# ---------------------------------------------------------------------------


class TestVendorLayout:
    """The _vendor directory exists and contains the packages we expect."""

    def test_vendor_dir_exists(self):
        assert os.path.isdir(synapse._vendor_path), (
            f"Expected vendored deps at {synapse._vendor_path}. "
            f"Run: hython -m pip install --target {synapse._vendor_path} "
            f"--upgrade anthropic"
        )

    @pytest.mark.parametrize("pkg", [
        "anthropic",
        "httpx",
        "httpcore",
        "anyio",
        "pydantic",
        "pydantic_core",
        "idna",
        "sniffio",
    ])
    def test_vendored_package_present(self, pkg: str):
        pkg_path = Path(synapse._vendor_path) / pkg
        assert pkg_path.is_dir(), (
            f"Expected {pkg!r} under {synapse._vendor_path}"
        )
        init_file = pkg_path / "__init__.py"
        assert init_file.is_file(), f"{pkg!r} missing __init__.py"

    def test_pydantic_core_has_cp311_binary(self):
        """The vendored binary must match Python 3.11 + win_amd64."""
        pydantic_core_dir = Path(synapse._vendor_path) / "pydantic_core"
        binaries = list(pydantic_core_dir.glob("_pydantic_core.*.pyd"))
        assert binaries, (
            "No compiled pydantic_core binary in vendor tree — "
            "pip install dropped source but not the .pyd?"
        )
        # We pin the ABI explicitly; if Houdini ever ships Python 3.12
        # we re-vendor with a matching binary.
        names = [b.name for b in binaries]
        assert any("cp311-win_amd64" in n for n in names), (
            f"Expected cp311-win_amd64 binary in vendor tree, "
            f"got: {names}. Refresh via: "
            f"PYTHONNOUSERSITE=1 hython -m pip install --target "
            f"{synapse._vendor_path} --upgrade anthropic"
        )

    def test_pycache_under_vendor_is_gitignored(self):
        """Guard the .gitignore rule — no Python build artefacts tracked.

        Runtime Python (pytest, hython, any ``import`` chain) creates
        ``__pycache__`` inside ``_vendor/`` on import. That's normal
        and we cannot prevent it without ``PYTHONDONTWRITEBYTECODE=1``
        at the interpreter level. What matters is that these runtime
        artefacts are never committed. This test asks git directly
        whether the .gitignore rule catches them.
        """
        import subprocess

        repo_root = Path(synapse._vendor_path).parent.parent.parent
        probe = (
            Path(synapse._vendor_path) / "__pycache__" / "probe.cpython-311.pyc"
        )
        # --no-index + explicit path: ask "would this be ignored?"
        # regardless of whether the file currently exists on disk.
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--verbose", str(probe)],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
        # Exit code 0 means the path IS ignored (git prints the matching rule).
        assert result.returncode == 0, (
            f"Expected .gitignore to catch __pycache__ under _vendor/. "
            f"git check-ignore returned {result.returncode}; "
            f"stdout={result.stdout!r}, stderr={result.stderr!r}"
        )

    def test_pyc_files_under_vendor_are_gitignored(self):
        """Companion to pycache rule — individual .pyc files too."""
        import subprocess

        repo_root = Path(synapse._vendor_path).parent.parent.parent
        probe = Path(synapse._vendor_path) / "anthropic" / "__init__.cpython-311.pyc"
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--verbose", str(probe)],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
        assert result.returncode == 0, (
            f"Expected .gitignore to catch *.pyc under _vendor/. "
            f"stdout={result.stdout!r}, stderr={result.stderr!r}"
        )


# ---------------------------------------------------------------------------
# sys.path prepend behaviour
# ---------------------------------------------------------------------------


class TestVendorPathActivation:
    """The prepend fires on Python 3.11 and stays passive elsewhere."""

    def test_vendor_path_exported(self):
        assert hasattr(synapse, "_vendor_path")
        assert isinstance(synapse._vendor_path, str)

    def test_vendor_path_points_into_package(self):
        """_vendor_path must live under the synapse package directory."""
        package_dir = os.path.dirname(synapse.__file__)
        assert synapse._vendor_path.startswith(package_dir)
        assert synapse._vendor_path.endswith("_vendor")

    def test_activation_gated_by_python_311(self):
        """Under Python 3.11, the vendor path is prepended to sys.path.
        Under any other version, it is NOT on sys.path.

        The 2684-test suite runs on Python 3.14; this test asserts
        the passive-on-3.14 behaviour so the suite keeps resolving
        pydantic from the user site.
        """
        on_path = synapse._vendor_path in sys.path
        if sys.version_info[:2] == (3, 11):
            assert on_path, (
                "Python 3.11 detected but vendor path is not on "
                "sys.path — import synapse should have prepended it"
            )
        else:
            assert not on_path, (
                f"Python {sys.version_info.major}.{sys.version_info.minor} "
                f"detected; vendor path should NOT be on sys.path "
                f"(vendored binaries are CP311 ABI-specific). "
                f"If this test fails, stock-Python tests will likely "
                f"crash on pydantic_core import."
            )

    def test_prepend_is_idempotent(self):
        """Re-importing synapse must not accumulate duplicate entries.

        Other tests in the suite (test_v5_features bootstraps a
        stubbed ``synapse`` module in ``sys.modules`` to break a
        hou-import cycle) can leave ``sys.modules['synapse']``
        pointing at something other than the real module.
        ``importlib.reload`` refuses to run in that state with
        ``ImportError: module synapse not in sys.modules``. Restore
        the real reference explicitly before reloading so we test
        the idempotency property instead of the test-order accident.
        """
        sys.modules["synapse"] = synapse
        before = sys.path.count(synapse._vendor_path)
        for _ in range(3):
            importlib.reload(synapse)
        after = sys.path.count(synapse._vendor_path)
        assert after == before, (
            f"sys.path count for vendor went {before} -> {after} "
            f"across 3 reloads; prepend is not idempotent"
        )


# ---------------------------------------------------------------------------
# Resolution (Python 3.11 only — skipped on 3.14 CI)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    sys.version_info[:2] != (3, 11),
    reason="Vendored CP311 binaries require Python 3.11 interpreter",
)
class TestVendorResolution:
    """On Python 3.11, imports must actually resolve into _vendor/.

    These tests only run under Python 3.11 (hython). Under the
    Python 3.14 test runner they skip cleanly — the vendor is
    inactive and so is anything that would prove the resolution.
    """

    def test_anthropic_resolves_to_vendor(self):
        import anthropic
        anthropic_file = getattr(anthropic, "__file__", "") or ""
        vendor_marker = os.path.sep + "_vendor" + os.path.sep
        assert vendor_marker in anthropic_file, (
            f"anthropic imported from {anthropic_file!r} — expected a "
            f"path containing {vendor_marker!r}. Vendor path prepend "
            f"may not be active, or an earlier-registered anthropic "
            f"is shadowing the vendored one."
        )

    def test_pydantic_core_binary_loads(self):
        from pydantic_core import _pydantic_core  # type: ignore[attr-defined]
        # Smoke: can we call into the binary? SchemaValidator is
        # defined in the extension module.
        assert hasattr(_pydantic_core, "SchemaValidator")