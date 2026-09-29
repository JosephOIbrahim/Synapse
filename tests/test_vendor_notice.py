"""Test that fxhoudinimcp NOTICE.md hashes are correct.

The verifier hashes the *committed git blob* (LF bytes) for each vendored file,
never a working-tree checkout. On Windows ``core.autocrlf=true`` rewrites LF to
CRLF on checkout, so a table of CRLF-computed hashes (the BP11-FIXFWD defect)
must be rejected -- ``test_verify_vendor_notice_crlf_table_fails`` pins that.
"""

import hashlib
import re
import subprocess
import sys
from pathlib import Path

VENDOR = "python/synapse/_vendor/fxhoudinimcp"


def _repo_root():
    return Path(__file__).parent.parent


def _blob_path_for(filename):
    if filename == "LICENSE":
        return f"{VENDOR}/LICENSE"
    return f"{VENDOR}/guides/{filename}"


def _git_blob(repo_root, repo_path):
    result = subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{repo_path}"],
        cwd=str(repo_root),
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


def _table_hashes(content):
    """{filename: hash} for every 64-hex table row in NOTICE.md content."""
    hashes = {}
    for line in content.split("\n"):
        if line.startswith("|") and "|" in line[1:]:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3 and parts[1] and re.fullmatch(r"[0-9a-f]{64}", parts[2]):
                hashes[parts[1]] = parts[2]
    return hashes


def test_verify_vendor_notice():
    """Run verify_vendor_notice.py and assert exit 0."""
    repo_root = _repo_root()
    verifier = repo_root / "scripts" / "verify_vendor_notice.py"

    assert verifier.exists(), f"Verifier not found at {verifier}"

    result = subprocess.run(
        [sys.executable, str(verifier)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"Verifier failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


def _notice_path(repo_root):
    return repo_root / "python" / "synapse" / "_vendor" / "fxhoudinimcp" / "NOTICE.md"


def _run_verifier(repo_root, *args):
    verifier = repo_root / "scripts" / "verify_vendor_notice.py"
    assert verifier.exists(), f"Verifier not found at {verifier}"
    return subprocess.run([sys.executable, str(verifier), *args],
                          capture_output=True, text=True)


def _copy_with(tmp_path, content):
    """A NOTICE.md copy holding *content*, written as bytes (no newline translation).

    The mutation and CRLF tests check this copy through ``--notice`` and never
    write the tracked file (ruling R-D; CRUX F7: a text-mode rewrite left the
    tracked NOTICE.md CRLF on Windows after every run).
    """
    copy = tmp_path / "NOTICE.md"
    copy.write_bytes(content.encode("utf-8"))
    return copy


def test_verify_vendor_notice_accepts_an_unmodified_copy(tmp_path):
    """Control for the two tests below: ``--notice`` on a faithful copy passes."""
    repo_root = _repo_root()
    before = _notice_path(repo_root).read_bytes()
    result = _run_verifier(repo_root, "--notice", str(_copy_with(tmp_path, before.decode("utf-8"))))
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert _notice_path(repo_root).read_bytes() == before


def test_verify_vendor_notice_mutation_fails(tmp_path):
    """Mutating one hash in a copy of NOTICE.md makes the verifier exit 1."""
    repo_root = _repo_root()
    notice_path = _notice_path(repo_root)
    assert notice_path.exists(), f"NOTICE.md not found at {notice_path}"
    before = notice_path.read_bytes()
    original_content = before.decode("utf-8")

    match = re.search(r"\| anim\.md \| ([a-f0-9]{64})", original_content)
    assert match, "anim.md row not found in NOTICE.md"
    old_hash = match.group(1)
    new_hash = ("0" if old_hash[0] != "0" else "1") + old_hash[1:]
    copy = _copy_with(tmp_path, original_content.replace(old_hash, new_hash))

    result = _run_verifier(repo_root, "--notice", str(copy))
    assert result.returncode == 1, (
        f"Verifier should fail on mutated hash but got exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    assert notice_path.read_bytes() == before, "the tracked NOTICE.md was touched"


def test_verify_vendor_notice_crlf_table_fails(tmp_path):
    """A NOTICE table whose hashes are computed from CRLF bytes must be REJECTED.

    This reproduces the BP11-FIXFWD defect exactly: hashes taken from a Windows
    checkout (core.autocrlf LF->CRLF) instead of the committed LF blob. Each
    table hash is replaced by sha256 of the same blob converted to CRLF; the
    verifier, which hashes the LF blob, must exit 1.
    """
    repo_root = _repo_root()
    notice_path = _notice_path(repo_root)
    assert notice_path.exists(), f"NOTICE.md not found at {notice_path}"
    before = notice_path.read_bytes()
    original_content = before.decode("utf-8")
    lf_hashes = _table_hashes(original_content.replace("\r\n", "\n"))
    assert lf_hashes, "no hashes parsed from NOTICE.md"

    # Build the CRLF-hashed table: for each file, sha256 of its blob as CRLF.
    crlf_content = original_content
    swapped = 0
    changed_anim = False
    for filename, lf_hash in lf_hashes.items():
        blob = _git_blob(repo_root, _blob_path_for(filename))
        assert blob is not None, f"missing blob for {filename}"
        crlf_bytes = blob.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        crlf_hash = hashlib.sha256(crlf_bytes).hexdigest()
        if crlf_hash != lf_hash:
            crlf_content = crlf_content.replace(lf_hash, crlf_hash)
            swapped += 1
            if filename == "anim.md":
                changed_anim = True

    # The guides contain newlines, so CRLF hashes must genuinely differ from LF.
    assert changed_anim, "anim.md CRLF hash equalled its LF hash -- CRLF swap was a no-op"
    assert swapped >= 1, "no CRLF hash differed from its LF hash"

    result = _run_verifier(repo_root, "--notice", str(_copy_with(tmp_path, crlf_content)))
    assert result.returncode == 1, (
        f"Verifier must reject a CRLF-hashed table but got exit code "
        f"{result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert notice_path.read_bytes() == before, "the tracked NOTICE.md was touched"
