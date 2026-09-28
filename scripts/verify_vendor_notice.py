#!/usr/bin/env python3
"""Verify fxhoudinimcp NOTICE.md hashes against upstream git blobs.

Recomputes SHA256 for each file listed in NOTICE.md by cloning the upstream
repository at the specified commit and hashing the actual file content.
Exits with status 0 if all hashes match, 1 if any mismatch is found.
"""

import sys
import re
import tempfile
import subprocess
import hashlib
from pathlib import Path


def parse_notice(notice_path):
    """Parse NOTICE.md to extract upstream commit and hashes."""
    with open(notice_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract commit hash
    commit_match = re.search(r'\*\*Commit:\*\*\s+([a-f0-9]{40})', content)
    if not commit_match:
        raise ValueError("Could not find commit hash in NOTICE.md")
    commit = commit_match.group(1)

    # Extract hashes from table
    hashes = {}
    for line in content.split('\n'):
        if line.startswith('|') and ('|' in line[1:]):  # Table row with at least one |
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3 and parts[1] and parts[2]:
                filename = parts[1]
                filehash = parts[2]
                if len(filehash) == 64:  # SHA256 is 64 hex chars
                    hashes[filename] = filehash

    return commit, hashes


def compute_hashes(commit, upstream_url="https://github.com/healkeiser/fxhoudinimcp"):
    """Clone upstream repo and compute hashes for all files."""
    hashes = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        # Clone and checkout
        subprocess.run(
            ["git", "clone", "--depth", "1", upstream_url, tmpdir],
            check=True, capture_output=True
        )
        subprocess.run(
            ["git", "fetch", "origin", commit],
            cwd=tmpdir, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", commit],
            cwd=tmpdir, check=True, capture_output=True
        )

        tmpdir_path = Path(tmpdir)

        # Compute hashes for guide files
        workflows_dir = tmpdir_path / "python" / "fxhoudinimcp" / "prompts" / "markdown" / "workflows"
        if workflows_dir.exists():
            for md_file in sorted(workflows_dir.glob("*.md")):
                filename = md_file.name
                with open(md_file, 'rb') as f:
                    content = f.read()
                hashes[filename] = hashlib.sha256(content).hexdigest()

        # Compute hash for LICENSE
        license_file = tmpdir_path / "LICENSE"
        if license_file.exists():
            with open(license_file, 'rb') as f:
                content = f.read()
            hashes["LICENSE"] = hashlib.sha256(content).hexdigest()

    return hashes


def main():
    """Main verifier."""
    repo_root = Path(__file__).parent.parent
    notice_path = repo_root / "python" / "synapse" / "_vendor" / "fxhoudinimcp" / "NOTICE.md"

    if not notice_path.exists():
        print(f"Error: NOTICE.md not found at {notice_path}", file=sys.stderr)
        return 1

    try:
        expected_commit, expected_hashes = parse_notice(notice_path)
        print(f"[info] verifying {len(expected_hashes)} files from commit {expected_commit[:8]}")
    except ValueError as e:
        print(f"Error parsing NOTICE.md: {e}", file=sys.stderr)
        return 1

    try:
        computed_hashes = compute_hashes(expected_commit)
    except subprocess.CalledProcessError as e:
        print(f"Error cloning/checking out upstream: {e}", file=sys.stderr)
        return 1

    # Compare
    mismatches = []
    for filename, expected_hash in sorted(expected_hashes.items()):
        if filename not in computed_hashes:
            mismatches.append(f"Missing: {filename}")
        elif computed_hashes[filename] != expected_hash:
            mismatches.append(
                f"Mismatch {filename}: expected {expected_hash[:8]}..., got {computed_hashes[filename][:8]}..."
            )

    for filename in computed_hashes:
        if filename not in expected_hashes:
            mismatches.append(f"Unexpected: {filename}")

    if mismatches:
        print(f"[err] {len(mismatches)} mismatches found:", file=sys.stderr)
        for msg in mismatches:
            print(f"  {msg}", file=sys.stderr)
        return 1

    print(f"[ok] all {len(expected_hashes)} hashes verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
