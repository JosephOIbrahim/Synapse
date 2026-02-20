#!/usr/bin/env python3
"""Phase 0: Clone SideFXLabs repo and create attribution."""

import os
import subprocess
import sys
from pathlib import Path

STAGING_ROOT = Path(os.environ.get("STAGING_ROOT", r"G:\SYNAPSE_STAGING\SideFXLabs"))
CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", r"G:\HOUDINI21_RAG_SYSTEM\corpus\sidefxlabs"))
REPO_URL = os.environ.get("REPO_URL", "https://github.com/sideeffects/SideFXLabs.git")
REPO_BRANCH = os.environ.get("REPO_BRANCH", "Development")


def clone_repo():
    """Clone or update the SideFXLabs repository."""
    if STAGING_ROOT.exists() and (STAGING_ROOT / ".git").exists():
        print(f"Repo already exists at {STAGING_ROOT}, pulling latest...")
        subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=str(STAGING_ROOT),
            check=True,
        )
    elif STAGING_ROOT.exists():
        print(f"Directory exists but not a git repo: {STAGING_ROOT}")
        print("Remove it manually or point STAGING_ROOT elsewhere.")
        sys.exit(1)
    else:
        print(f"Cloning {REPO_URL} (branch: {REPO_BRANCH})...")
        STAGING_ROOT.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "git", "clone",
                "--branch", REPO_BRANCH,
                "--depth", "1",
                REPO_URL,
                str(STAGING_ROOT),
            ],
            check=True,
        )
    print(f"Repo ready at {STAGING_ROOT}")


def verify_expanded_format():
    """Confirm HDAs are in expanded directory format, not binary blobs."""
    otls = STAGING_ROOT / "otls"
    if not otls.exists():
        print("WARNING: otls/ directory not found")
        return False

    hda_dirs = [d for d in otls.glob("*.hda") if d.is_dir()]
    hda_files = [f for f in otls.glob("*.hda") if f.is_file()]

    print(f"Found {len(hda_dirs)} expanded HDAs, {len(hda_files)} binary HDAs")

    if hda_files:
        print("WARNING: Some HDAs are binary format, not expanded.")
        print("Only expanded HDAs will be processed.")

    return len(hda_dirs) > 0


def verify_license():
    """Read and confirm license is BSD 2-Clause."""
    license_file = STAGING_ROOT / "LICENSE.md"
    if not license_file.exists():
        print("WARNING: LICENSE.md not found")
        return False

    content = license_file.read_text(errors="replace")
    if "Redistribution and use" in content and "Side Effects Software" in content:
        print("License verified: BSD 2-Clause (Side Effects Software)")
        return True
    else:
        print("WARNING: License content unexpected. Review manually.")
        print(content[:500])
        return False


def create_attribution():
    """Create attribution file in corpus root."""
    CORPUS_ROOT.mkdir(parents=True, exist_ok=True)

    attribution = CORPUS_ROOT / "ATTRIBUTION.md"

    # Read actual license text
    license_file = STAGING_ROOT / "LICENSE.md"
    license_text = ""
    if license_file.exists():
        license_text = license_file.read_text(errors="replace").strip()

    attribution.write_text(
        f"""# SideFX Labs Corpus Attribution

**Source:** {REPO_URL}
**Branch:** {REPO_BRANCH}
**Extracted by:** SYNAPSE SideFXLabs Extraction Pipeline

## License

{license_text}

## Usage Context

Extracted parameter patterns, VEX idioms, Python scripting patterns, and HDA
structural conventions for use in SYNAPSE AI-Houdini bridge RAG system.
Not redistributed as standalone tools.
""",
        encoding="utf-8",
    )
    print(f"Attribution written to {attribution}")


def inventory():
    """Quick inventory of what's available."""
    dirs_of_interest = [
        "otls",
        "scripts",
        "python_panels",
        "viewer_states",
        "vex/include",
        "help",
        "hip",
        "inlinecpp",
    ]

    print("\nRepository inventory:")
    for d in dirs_of_interest:
        path = STAGING_ROOT / d
        if path.exists():
            if path.is_dir():
                count = sum(1 for _ in path.rglob("*") if _.is_file())
                print(f"  {d}/  ({count} files)")
            else:
                print(f"  {d}  (file)")
        else:
            print(f"  {d}/  (not found)")


def main():
    clone_repo()
    verify_license()
    verify_expanded_format()
    create_attribution()
    inventory()


if __name__ == "__main__":
    main()
