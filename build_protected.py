"""
Synapse Protected Build — Cython compilation for IP-sensitive modules.

Compiles 7 HIGH IP modules to .pyd (Windows) / .so (Linux) native extensions.
Source is unrecoverable from compiled output.

Usage:
    python build_protected.py              # Compile in-place (for dev/testing)
    python build_protected.py --dist       # Build distributable package (no source)
    python build_protected.py --clean      # Remove all compiled artifacts

The compiled .pyd files are importable identically to .py files.
Python's import system prefers .pyd/.so over .py when both exist.
"""

import os
import sys
import shutil
import argparse
from pathlib import Path

# ============================================================================
# HIGH IP Modules — these get compiled to native extensions
# ============================================================================

PROTECTED_MODULES = [
    "python/synapse/routing/router.py",
    "python/synapse/routing/cache.py",
    "python/synapse/memory/store.py",
    "python/synapse/memory/markdown.py",
    "python/synapse/agent/executor.py",
    "python/synapse/agent/learning.py",
    "python/synapse/core/determinism.py",
]

# ============================================================================
# Build
# ============================================================================

ROOT = Path(__file__).parent


def get_ext_modules():
    """Create Cython Extension objects for each protected module."""
    from Cython.Build import cythonize
    from setuptools import Extension

    extensions = []
    for mod_path in PROTECTED_MODULES:
        full_path = ROOT / mod_path
        if not full_path.exists():
            print(f"  SKIP {mod_path} (not found)")
            continue

        # Convert file path to dotted module name
        # python/synapse/routing/router.py -> synapse.routing.router
        parts = Path(mod_path).with_suffix("").parts
        # Strip leading "python/" from module name
        if parts[0] == "python":
            parts = parts[1:]
        module_name = ".".join(parts)

        extensions.append(
            Extension(
                module_name,
                sources=[str(full_path)],
            )
        )

    return cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
        },
        quiet=False,
    )


def build_inplace():
    """Compile protected modules in-place (.pyd next to .py)."""
    print("=" * 60)
    print("Synapse Protected Build — In-Place Compilation")
    print("=" * 60)
    print()
    print(f"Target: {len(PROTECTED_MODULES)} HIGH IP modules")
    print()

    # Use setuptools to build extensions in-place
    from setuptools import setup, Distribution

    ext_modules = get_ext_modules()
    if not ext_modules:
        print("ERROR: No modules to compile.")
        return False

    dist = Distribution({
        "name": "synapse-protected",
        "ext_modules": ext_modules,
        "package_dir": {"": "python"},
    })

    # Build in-place
    cmd = dist.get_command_obj("build_ext")
    cmd.inplace = True
    cmd.ensure_finalized()

    try:
        cmd.run()
    except Exception as e:
        print(f"\nBUILD FAILED: {e}")
        print("\nEnsure you have a C compiler installed:")
        print("  - Windows: Visual Studio Build Tools (MSVC)")
        print("  - Linux: gcc / build-essential")
        print("  - macOS: Xcode Command Line Tools")
        return False

    print()
    print("=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)

    # Report what was built
    for mod_path in PROTECTED_MODULES:
        py_file = ROOT / mod_path
        # Look for .pyd (Windows) or .so (Linux/macOS)
        stem = py_file.stem
        parent = py_file.parent
        pyd_files = list(parent.glob(f"{stem}*.pyd")) + list(parent.glob(f"{stem}*.so"))
        if pyd_files:
            for pyd in pyd_files:
                size_kb = pyd.stat().st_size / 1024
                print(f"  COMPILED  {pyd.name} ({size_kb:.0f} KB)")
        else:
            print(f"  MISSING   {mod_path}")

    return True


def build_dist():
    """Build a distributable package with .pyd replacing .py for protected modules."""
    dist_dir = ROOT / "dist" / "synapse-protected"

    print("=" * 60)
    print("Synapse Protected Build — Distribution Package")
    print("=" * 60)
    print()
    print(f"Output: {dist_dir}")
    print()

    # Step 1: Compile in-place first
    if not build_inplace():
        return False

    # Step 2: Create dist directory
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True)

    # Step 3: Copy entire python/synapse/ tree
    src = ROOT / "python" / "synapse"
    dst = dist_dir / "python" / "synapse"
    shutil.copytree(src, dst)

    # Step 4: Copy package files
    for f in ["pyproject.toml", "README.md", "LICENSE"]:
        src_file = ROOT / f
        if src_file.exists():
            shutil.copy2(src_file, dist_dir / f)

    # Step 5: Copy assets
    assets_src = ROOT / "assets"
    if assets_src.exists():
        shutil.copytree(assets_src, dist_dir / "assets")

    # Step 6: Copy houdini directory
    houdini_src = ROOT / "houdini"
    if houdini_src.exists():
        shutil.copytree(houdini_src, dist_dir / "houdini")

    # Step 7: Remove .py source for protected modules (keep .pyd only)
    removed = 0
    for mod_path in PROTECTED_MODULES:
        # mod_path is relative to ROOT: "python/synapse/routing/router.py"
        # In dist, it's at: dist_dir / "python/synapse/routing/router.py"
        rel = Path(mod_path)
        py_file = dist_dir / rel
        parent = py_file.parent
        stem = py_file.stem

        # Check that .pyd/.so exists before removing .py
        compiled = list(parent.glob(f"{stem}*.pyd")) + list(parent.glob(f"{stem}*.so"))
        if compiled and py_file.exists():
            py_file.unlink()
            removed += 1
            print(f"  PROTECTED {rel.name} -> {compiled[0].name}")
        elif py_file.exists():
            print(f"  WARNING   {rel.name} has no compiled version, keeping .py")

    # Step 8: Remove build artifacts (Cython/MSVC intermediates) from dist
    for pattern in ["*.c", "*.lib", "*.exp", "*.obj"]:
        for artifact in (dist_dir / "python").rglob(pattern):
            artifact.unlink()

    print()
    print("=" * 60)
    print(f"DISTRIBUTION READY: {dist_dir}")
    print(f"  {removed} modules compiled (source removed)")
    print(f"  {len(PROTECTED_MODULES) - removed} modules kept as source")
    print("=" * 60)

    return True


def clean():
    """Remove all compiled artifacts."""
    print("Cleaning compiled artifacts...")

    removed = 0
    for mod_path in PROTECTED_MODULES:
        py_file = ROOT / mod_path
        parent = py_file.parent
        stem = py_file.stem

        # Remove .pyd, .so, .c, .lib, .exp, .obj files
        for pattern in [f"{stem}*.pyd", f"{stem}*.so", f"{stem}.c",
                        f"{stem}*.lib", f"{stem}*.exp", f"{stem}*.obj"]:
            for f in parent.glob(pattern):
                f.unlink()
                print(f"  REMOVED {f.relative_to(ROOT)}")
                removed += 1

    # Remove build/ directory
    build_dir = ROOT / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
        print("  REMOVED build/")
        removed += 1

    # Remove dist/synapse-protected/
    dist_dir = ROOT / "dist" / "synapse-protected"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
        print("  REMOVED dist/synapse-protected/")
        removed += 1

    print(f"\nCleaned {removed} artifacts.")


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Synapse Protected Build — Cython compilation for IP-sensitive modules"
    )
    parser.add_argument(
        "--dist", action="store_true",
        help="Build distributable package (compiled .pyd, no source for protected modules)"
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Remove all compiled artifacts"
    )

    args = parser.parse_args()

    if args.clean:
        clean()
    elif args.dist:
        build_dist()
    else:
        build_inplace()


if __name__ == "__main__":
    main()
