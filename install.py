"""
Synapse Design System — Installer

Detects Houdini preferences directory and installs:
  - Shelf toolbar (synapse.shelf)
  - Python panel (synapse_panel.pypanel)
  - Shelf callbacks module (synapse_shelf.py)
  - SVG icons with SYNAPSE_ namespace
  - Design system modules (tokens, styles)

Supports: install, uninstall, verify, dry-run.

Usage:
    python install.py                  # Install
    python install.py --verify         # Verify installation
    python install.py --uninstall      # Remove Synapse files
    python install.py --dry-run        # Show what would be done
    python install.py --houdini-prefs PATH  # Override prefs location
"""

import argparse
import os
import platform
import shutil
import sys
import glob


# ── Constants ─────────────────────────────────────────────

_VERSION = "1.0.0"
_SYNAPSE_HOME = os.path.dirname(os.path.abspath(__file__))

# Source locations relative to SYNAPSE_HOME
_SOURCES = {
    "shelf": os.path.join(_SYNAPSE_HOME, "houdini", "toolbar", "synapse.shelf"),
    "panel": os.path.join(_SYNAPSE_HOME, "houdini", "python_panels", "synapse_panel.pypanel"),
    "shelf_callbacks": os.path.join(_SYNAPSE_HOME, "houdini", "scripts", "python", "synapse_shelf.py"),
    "tokens": os.path.join(_SYNAPSE_HOME, "design", "tokens.py"),
    "styles": os.path.join(_SYNAPSE_HOME, "design", "synapse_styles.py"),
    "svg_dir": os.path.join(_SYNAPSE_HOME, "design", "icons", "svg"),
}

# Houdini target subdirectories
_TARGETS = {
    "shelf": os.path.join("toolbar", "synapse.shelf"),
    "panel": os.path.join("python_panels", "synapse_panel.pypanel"),
    "shelf_callbacks": os.path.join("scripts", "python", "synapse_shelf.py"),
    "tokens": os.path.join("scripts", "python", "tokens.py"),
    "styles": os.path.join("scripts", "python", "synapse_styles.py"),
}

# Icon name mapping: remove size suffix for Houdini registration
# Houdini looks for SYNAPSE_iconname.svg in config/Icons/
_ICON_NAMESPACE = "SYNAPSE"


# ── Houdini Prefs Detection ──────────────────────────────

def _detect_houdini_prefs():
    """
    Detect the Houdini user preferences directory.

    Search order:
      1. $HOUDINI_USER_PREF_DIR (if set)
      2. Platform-specific defaults for Houdini 21.x, 20.x, 19.x
    """
    # Check environment variable first
    env_prefs = os.environ.get("HOUDINI_USER_PREF_DIR")
    if env_prefs and os.path.isdir(env_prefs):
        return env_prefs

    # Platform-specific default locations
    system = platform.system()
    home = os.path.expanduser("~")

    if system == "Windows":
        documents = os.path.join(home, "Documents")
        search_root = documents
    elif system == "Darwin":
        search_root = os.path.join(home, "Library", "Preferences", "houdini")
    else:  # Linux
        search_root = home

    # Search for houdini21.x, 20.x, etc. (newest first)
    candidates = []
    for major in [21, 20, 19]:
        for minor in range(9, -1, -1):
            if system == "Windows":
                path = os.path.join(search_root, f"houdini{major}.{minor}")
            elif system == "Darwin":
                path = os.path.join(search_root, f"{major}.{minor}")
            else:
                path = os.path.join(search_root, f"houdini{major}.{minor}")
            if os.path.isdir(path):
                candidates.append(path)

    if candidates:
        return candidates[0]  # Return newest version found

    return None


# ── File Operations ───────────────────────────────────────

def _copy_file(src, dst, dry_run=False):
    """Copy a single file, creating parent directories as needed."""
    if not os.path.exists(src):
        print(f"  SKIP  {os.path.basename(src)} (source missing)")
        return False

    if dry_run:
        print(f"  COPY  {src}")
        print(f"     -> {dst}")
        return True

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  OK    {os.path.basename(dst)}")
    return True


def _remove_file(path, dry_run=False):
    """Remove a file if it exists."""
    if not os.path.exists(path):
        return False

    if dry_run:
        print(f"  DEL   {path}")
        return True

    os.remove(path)
    print(f"  DEL   {os.path.basename(path)}")
    return True


# ── Install ───────────────────────────────────────────────

def install(prefs_dir, dry_run=False):
    """Install Synapse files into Houdini preferences."""
    print(f"\n{'DRY RUN: ' if dry_run else ''}Installing Synapse v{_VERSION}")
    print(f"  Target: {prefs_dir}\n")

    count = 0

    # Core files
    print("--- Core Files ---")
    for key, rel_target in _TARGETS.items():
        src = _SOURCES[key]
        dst = os.path.join(prefs_dir, rel_target)
        if _copy_file(src, dst, dry_run):
            count += 1

    # Icons — copy 32px SVGs as SYNAPSE_<name>.svg
    print("\n--- Icons ---")
    icons_dst_dir = os.path.join(prefs_dir, "config", "Icons")
    svg_dir = _SOURCES["svg_dir"]

    if os.path.isdir(svg_dir):
        svg_32_files = sorted(glob.glob(os.path.join(svg_dir, "*_32.svg")))
        for svg_path in svg_32_files:
            basename = os.path.basename(svg_path)
            # e.g., "synapse_32.svg" -> "SYNAPSE_synapse.svg"
            icon_name = basename.replace("_32.svg", "")
            dst_name = f"{_ICON_NAMESPACE}_{icon_name}.svg"
            dst_path = os.path.join(icons_dst_dir, dst_name)
            if _copy_file(svg_path, dst_path, dry_run):
                count += 1
    else:
        print("  SKIP  No SVG directory found (run generate_icons.py first)")

    print(f"\n{'Would install' if dry_run else 'Installed'}: {count} files")
    return count


# ── Uninstall ─────────────────────────────────────────────

def uninstall(prefs_dir, dry_run=False):
    """Remove Synapse files from Houdini preferences."""
    print(f"\n{'DRY RUN: ' if dry_run else ''}Uninstalling Synapse")
    print(f"  Target: {prefs_dir}\n")

    count = 0

    # Core files
    print("--- Core Files ---")
    for key, rel_target in _TARGETS.items():
        path = os.path.join(prefs_dir, rel_target)
        if _remove_file(path, dry_run):
            count += 1

    # Icons
    print("\n--- Icons ---")
    icons_dir = os.path.join(prefs_dir, "config", "Icons")
    if os.path.isdir(icons_dir):
        for icon_file in glob.glob(os.path.join(icons_dir, f"{_ICON_NAMESPACE}_*.svg")):
            if _remove_file(icon_file, dry_run):
                count += 1

    print(f"\n{'Would remove' if dry_run else 'Removed'}: {count} files")
    return count


# ── Verify ────────────────────────────────────────────────

def verify(prefs_dir):
    """Verify Synapse installation integrity."""
    print(f"\nVerifying Synapse installation")
    print(f"  Target: {prefs_dir}\n")

    ok_count = 0
    fail_count = 0

    # Core files
    print("--- Core Files ---")
    for key, rel_target in _TARGETS.items():
        path = os.path.join(prefs_dir, rel_target)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  OK    {rel_target} ({size} bytes)")
            ok_count += 1
        else:
            print(f"  MISS  {rel_target}")
            fail_count += 1

    # Icons
    print("\n--- Icons ---")
    icons_dir = os.path.join(prefs_dir, "config", "Icons")
    expected_icons = ["synapse", "inspect", "execute", "verify", "document", "profile"]
    for icon_name in expected_icons:
        path = os.path.join(icons_dir, f"{_ICON_NAMESPACE}_{icon_name}.svg")
        if os.path.exists(path):
            print(f"  OK    {_ICON_NAMESPACE}_{icon_name}.svg")
            ok_count += 1
        else:
            print(f"  MISS  {_ICON_NAMESPACE}_{icon_name}.svg")
            fail_count += 1

    # Python importability
    print("\n--- Import Check ---")
    scripts_python = os.path.join(prefs_dir, "scripts", "python")
    if scripts_python not in sys.path:
        sys.path.insert(0, scripts_python)
    for module_name in ["tokens", "synapse_styles", "synapse_shelf"]:
        try:
            __import__(module_name)
            print(f"  OK    import {module_name}")
            ok_count += 1
        except Exception as e:
            print(f"  FAIL  import {module_name}: {e}")
            fail_count += 1

    # Shelf XML validity
    print("\n--- Shelf Validation ---")
    shelf_path = os.path.join(prefs_dir, "toolbar", "synapse.shelf")
    if os.path.exists(shelf_path):
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(shelf_path)
            root = tree.getroot()
            tools = root.findall(".//tool")
            print(f"  OK    synapse.shelf ({len(tools)} tools)")
            ok_count += 1
        except Exception as e:
            print(f"  FAIL  synapse.shelf: {e}")
            fail_count += 1
    else:
        print(f"  MISS  synapse.shelf")
        fail_count += 1

    # Summary
    total = ok_count + fail_count
    print(f"\n--- Summary ---")
    print(f"  Passed: {ok_count}/{total}")
    if fail_count:
        print(f"  Failed: {fail_count}/{total}")
        print(f"\n  Run 'python install.py' to fix missing files.")
    else:
        print(f"  Installation looks good.")

    return fail_count == 0


# ── CLI ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Synapse Design System Installer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python install.py                     Install to auto-detected Houdini prefs\n"
            "  python install.py --dry-run            Show what would be installed\n"
            "  python install.py --verify             Check existing installation\n"
            "  python install.py --uninstall          Remove Synapse files\n"
            "  python install.py --houdini-prefs PATH Override prefs directory\n"
        ),
    )
    parser.add_argument("--verify", action="store_true", help="Verify installation")
    parser.add_argument("--uninstall", action="store_true", help="Remove Synapse files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--houdini-prefs", type=str, help="Override Houdini prefs directory")

    args = parser.parse_args()

    # Detect or use provided prefs directory
    prefs_dir = args.houdini_prefs or _detect_houdini_prefs()

    if prefs_dir is None:
        print("Couldn't find Houdini preferences directory.")
        print("\nTry one of:")
        print("  python install.py --houdini-prefs /path/to/houdiniXX.X")
        print("  Set HOUDINI_USER_PREF_DIR environment variable")
        sys.exit(1)

    print(f"Houdini prefs: {prefs_dir}")

    if not os.path.isdir(prefs_dir):
        print(f"Directory doesn't exist: {prefs_dir}")
        sys.exit(1)

    if args.verify:
        success = verify(prefs_dir)
        sys.exit(0 if success else 1)
    elif args.uninstall:
        uninstall(prefs_dir, dry_run=args.dry_run)
    else:
        install(prefs_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
