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
from conftest import VENDOR_ABI_TAG, VENDOR_ABI_TAGS, VENDOR_PY, VENDOR_PYS


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

    @pytest.mark.parametrize("pkg,stem", [
        ("pydantic_core", "_pydantic_core"),
        ("jiter", "jiter"),
    ])
    def test_native_package_has_all_vendored_abis(self, pkg: str, stem: str):
        """Each native package ships a .pyd for EVERY vendored ABI tag.

        As of the H22 drop (2026-07-15) the tree carries both cp311
        (H20.5/21.0/21.5) and cp313 (H22) binaries side by side at the same
        package versions. Re-vendoring a new Houdini Python line adds its tag
        to conftest ``VENDOR_ABI_TAGS`` and drops the matching .pyd here in
        the same commit (docs/studio/UPGRADE.md Step 2a).
        """
        pkg_dir = Path(synapse._vendor_path) / pkg
        binaries = [b.name for b in pkg_dir.glob(f"{stem}.*.pyd")]
        assert binaries, (
            f"No compiled {pkg} binary in vendor tree — "
            "pip install dropped source but not the .pyd?"
        )
        for tag in VENDOR_ABI_TAGS:
            assert any(tag in n for n in binaries), (
                f"Expected a {tag} {pkg} binary in the vendor tree, got: "
                f"{binaries}. Re-vendor per docs/studio/UPGRADE.md Step 2a."
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

    def test_activation_gated_by_vendored_abi_and_windows(self):
        """The vendor path is prepended on a vendored ABI + Windows only.

        Per ``python/synapse/__init__.py``: the vendor tree carries a
        native ``.pyd`` for each ABI in ``_VENDOR_PYS`` (cp311 + cp313 as
        of the H22 drop), so the gate checks both Python version AND
        platform. On a vendored Python line + Windows the prepend fires;
        on a vendored line + Linux/macOS the gate skips (vendored native
        binary is win_amd64-only, real pydantic from pip resolves via
        site-packages instead); on any Python line OUTSIDE the set the
        gate also skips.

        The test suite runs on Python 3.14 stock (outside the set); this
        test asserts the passive-on-3.14 behaviour so the suite keeps
        resolving pydantic from the user site. Linux CI runs on a vendored
        line but the gate skips there too — this test pins that branch
        explicitly.
        """
        on_path = synapse._vendor_path in sys.path
        is_vendor_py = sys.version_info[:2] in VENDOR_PYS
        is_windows = sys.platform.startswith("win")

        if is_vendor_py and is_windows:
            assert on_path, (
                "A vendored Python line + Windows detected but vendor path "
                "is not on sys.path — import synapse should have prepended it"
            )
        else:
            reason = (
                "non-Windows (vendored binary is win_amd64 only)"
                if is_vendor_py
                else (
                    f"Python {sys.version_info.major}."
                    f"{sys.version_info.minor} (outside the vendored ABI set "
                    f"{sorted(VENDOR_PYS)})"
                )
            )
            assert not on_path, (
                f"Vendor path should NOT be on sys.path on this "
                f"platform — gate skipped due to: {reason}. "
                f"If this test fails, stock-Python or non-Windows "
                f"tests will likely crash on pydantic_core import."
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
    sys.version_info[:2] not in VENDOR_PYS or not sys.platform.startswith("win"),
    reason=(
        "Vendored binaries require a vendored ABI (cp311/cp313) + Windows "
        "(see python/synapse/__init__.py vendor gate). On Linux/macOS "
        "the gate skips and pydantic / anthropic resolve from pip; "
        "these resolution tests are Windows-only by design."
    ),
)
class TestVendorResolution:
    """On a vendored ABI + Windows, imports must actually resolve into _vendor/.

    These tests only run under a vendored Python line + Windows (hython on
    H21 cp311 / H22 cp313, plus Windows local dev). Under the Python 3.14
    test runner OR Linux CI they skip cleanly — the vendor is inactive on
    those platforms by design (see ``python/synapse/__init__.py`` gate).
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