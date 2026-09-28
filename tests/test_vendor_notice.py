"""Test that fxhoudinimcp NOTICE.md hashes are correct."""

import subprocess
import sys
from pathlib import Path


def test_verify_vendor_notice():
    """Run verify_vendor_notice.py and assert exit 0."""
    repo_root = Path(__file__).parent.parent
    verifier = repo_root / "scripts" / "verify_vendor_notice.py"

    assert verifier.exists(), f"Verifier not found at {verifier}"

    result = subprocess.run(
        [sys.executable, str(verifier)],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, (
        f"Verifier failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


def test_verify_vendor_notice_mutation_fails():
    """Verify that mutating a hash causes the verifier to fail.

    This test mutates NOTICE.md temporarily and confirms the verifier exits 1.
    """
    repo_root = Path(__file__).parent.parent
    notice_path = repo_root / "python" / "synapse" / "_vendor" / "fxhoudinimcp" / "NOTICE.md"
    verifier = repo_root / "scripts" / "verify_vendor_notice.py"

    assert notice_path.exists(), f"NOTICE.md not found at {notice_path}"

    # Read the original file
    original_content = notice_path.read_text(encoding='utf-8')

    try:
        # Mutate one hash: flip the first hex digit
        mutated_content = original_content
        # Find the first SHA256 hash in the table and flip one digit
        import re
        match = re.search(r'\| anim\.md \| ([a-f0-9]{64})', mutated_content)
        if match:
            old_hash = match.group(1)
            # Flip first digit
            new_digit = '0' if old_hash[0] != '0' else '1'
            new_hash = new_digit + old_hash[1:]
            mutated_content = mutated_content.replace(old_hash, new_hash)

            # Write mutated version
            notice_path.write_text(mutated_content, encoding='utf-8')

            # Run verifier
            result = subprocess.run(
                [sys.executable, str(verifier)],
                capture_output=True,
                text=True
            )

            # Verifier should fail
            assert result.returncode == 1, (
                f"Verifier should fail on mutated hash but got exit code {result.returncode}\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

    finally:
        # Restore original file
        notice_path.write_text(original_content, encoding='utf-8')
