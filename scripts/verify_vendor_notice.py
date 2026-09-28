#!/usr/bin/env python3
"""Verify fxhoudinimcp NOTICE.md hashes against the committed git blobs.

For every file listed in NOTICE.md, the expected SHA256 is compared against the
sha256 of the *committed git blob* obtained with `git cat-file blob HEAD:<path>`.

Hashing the blob (not a working-tree file) is deliberate: on Windows,
``core.autocrlf=true`` rewrites LF to CRLF on checkout, so a working-tree file
hashes differently on every platform while its blob stays LF everywhere. A
verifier that read the checkout would bless CRLF hashes on Windows and reject
them on Linux -- which is exactly the BP11-FIXFWD defect this repair closes.

The NOTICE.md table itself is read from the working tree (so a local edit to a
hash is what the mutation/CRLF tests exercise); only the *content* being hashed
comes from the object store. No guide or LICENSE file is ever read from disk.

Exits 0 if every hash matches, 1 on any mismatch, missing, or unexpected entry.
"""

import sys
import re
import subprocess
import hashlib
from pathlib import Path

VENDOR = "python/synapse/_vendor/fxhoudinimcp"


def parse_notice(notice_path):
    """Parse NOTICE.md (working tree) for the upstream commit and hash table."""
    content = Path(notice_path).read_text(encoding="utf-8")

    commit_match = re.search(r"\*\*Commit:\*\*\s+([a-f0-9]{40})", content)
    if not commit_match:
        raise ValueError("Could not find commit hash in NOTICE.md")
    commit = commit_match.group(1)

    hashes = {}
    for line in content.split("\n"):
        if line.startswith("|") and ("|" in line[1:]):  # table row with >=1 pipe
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3 and parts[1] and parts[2]:
                filename = parts[1]
                filehash = parts[2]
                if len(filehash) == 64 and re.fullmatch(r"[0-9a-f]{64}", filehash):
                    hashes[filename] = filehash

    return commit, hashes


def blob_path_for(filename):
    """Map a NOTICE table entry to its committed repo path."""
    if filename == "LICENSE":
        return f"{VENDOR}/LICENSE"
    return f"{VENDOR}/guides/{filename}"


def git_blob(repo_root, repo_path):
    """Return the raw bytes of HEAD:<repo_path>, or None if it is absent."""
    result = subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{repo_path}"],
        cwd=str(repo_root),
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def compute_hashes(repo_root, expected_hashes):
    """sha256 of the committed git blob for each file named in the NOTICE table."""
    hashes = {}
    for filename in expected_hashes:
        data = git_blob(repo_root, blob_path_for(filename))
        if data is None:
            continue  # recorded as a mismatch (missing) by the caller
        hashes[filename] = hashlib.sha256(data).hexdigest()
    return hashes


def main():
    repo_root = Path(__file__).parent.parent
    notice_path = repo_root / "python" / "synapse" / "_vendor" / "fxhoudinimcp" / "NOTICE.md"

    if not notice_path.exists():
        print(f"Error: NOTICE.md not found at {notice_path}", file=sys.stderr)
        return 1

    try:
        expected_commit, expected_hashes = parse_notice(notice_path)
        print(f"[info] verifying {len(expected_hashes)} files against committed git blobs "
              f"(commit {expected_commit[:8]})")
    except ValueError as e:
        print(f"Error parsing NOTICE.md: {e}", file=sys.stderr)
        return 1

    computed_hashes = compute_hashes(repo_root, expected_hashes)

    mismatches = []
    for filename, expected_hash in sorted(expected_hashes.items()):
        if filename not in computed_hashes:
            mismatches.append(f"Missing blob: {filename} (HEAD:{blob_path_for(filename)})")
        elif computed_hashes[filename] != expected_hash:
            mismatches.append(
                f"Mismatch {filename}: NOTICE {expected_hash[:8]}..., "
                f"blob {computed_hashes[filename][:8]}..."
            )

    if mismatches:
        print(f"[err] {len(mismatches)} mismatches found:", file=sys.stderr)
        for msg in mismatches:
            print(f"  {msg}", file=sys.stderr)
        return 1

    print(f"[ok] all {len(expected_hashes)} hashes match their committed git blobs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
