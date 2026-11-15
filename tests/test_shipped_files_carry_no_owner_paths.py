"""Five files that reached users carry no owner or machine paths (v5.102.0).

v5.101.0 and v5.101.1 shipped four paths into this machine's account folder in three
files of the source archive, and the Setup shipped 409 extraction-workspace paths in
the SideFX Labs corpus plus one transcript location in a reference skill. v5.102.0
rewrote them: the account name became the repo's redaction token, the corpus paths
became relative, and the transcript keeps its title without its folder.

This test scans the five files with the release audit's widened account pattern (any
run of slash or backslash bytes as the separator, so a path escaped once, twice or
inside nested JSON still matches) and checks the two Setup files for any path rooted
on the drive the workspace and transcript lived on. A regenerated artifact that brings
a path back fails here instead of in a download.

The control samples are assembled from pieces so this file never matches its own
patterns: the release audit scans the source archive, and this file ships in it.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

SOURCE_ARCHIVE_FILES = (
    "docs/SYNAPSE_MULTI_PROVIDER_LEG1_PROBE_DATA.json",
    "tools/_hy_parity_gui.json",
    "tools/_hy_verbs_sweep_22.0.400.json",
)
SETUP_FILES = (
    "rag/corpus/sidefxlabs_entries.json",
    "rag/skills/houdini21-reference/solaris_compound_node_anatomy.md",
)
FIVE = SOURCE_ARCHIVE_FILES + SETUP_FILES

SEP = rb"[\\/]+"
ACCOUNT = re.compile(rb"[Cc]:" + SEP + rb"Users" + SEP + rb"User" + SEP)
WORKSPACE_DRIVE = re.compile(rb"(?<![A-Za-z])[Gg]:" + SEP + rb"[A-Za-z0-9_]")


def _path(drive: bytes, sep: bytes, *parts: bytes) -> bytes:
    return drive + b":" + sep + sep.join(parts) + sep


@pytest.mark.parametrize("sep", [b"/", b"\\", b"\\\\", b"\\\\\\\\"])
def test_patterns_match_every_escaping_of_a_path(sep):
    """Control: the patterns are not vacuous for any escaping depth the files use."""
    assert ACCOUNT.search(_path(b"C", sep, b"Users", b"User", b"probe"))
    assert WORKSPACE_DRIVE.search(_path(b"G", sep, b"workspace", b"labs"))


def test_patterns_spare_the_redaction_token_and_other_drives():
    """Control: the rewritten form and the vendor defaults left in place do not match."""
    assert not ACCOUNT.search(_path(b"C", b"\\\\", b"Users", b"Example", b"probe"))
    assert not WORKSPACE_DRIVE.search(_path(b"D", b"/", b"SideFX", b"Remote"))
    assert not WORKSPACE_DRIVE.search(b"see https://example.org/page")


@pytest.mark.parametrize("rel", FIVE)
def test_file_carries_no_account_folder_path(rel):
    data = (REPO / rel).read_bytes()
    hits = [m.start() for m in ACCOUNT.finditer(data)]
    assert not hits, f"{rel}: {len(hits)} account-folder path(s), first at byte {hits[0]}"


@pytest.mark.parametrize("rel", SETUP_FILES)
def test_setup_file_carries_no_workspace_drive_path(rel):
    data = (REPO / rel).read_bytes()
    hits = [m.start() for m in WORKSPACE_DRIVE.finditer(data)]
    assert not hits, f"{rel}: {len(hits)} workspace-drive path(s), first at byte {hits[0]}"
