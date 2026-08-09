"""Phase 0c / DOC-1: SYNAPSE version is single-sourced and the docs conform.

v4 §4a.4: a version string is a claim ABOUT the system -- it must bind to code, not
drift. Canonical source = pyproject.toml [project].version. This test asserts the
chain pyproject == __init__.__version__ == __init__ docstring == CLAUDE.md banner.
If any drifts (the v5.8.0-vs-5.10.0 banner the CTO review flagged) it fails loud.

Reads files by path -> stock-CI-safe (no package import). This is the version slice
of DOC-1; the tool-count slice (108/110/117 ambiguity) is a separate follow-up.
"""
import re
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent


def _read(rel):
    return (_ROOT / rel).read_text(encoding="utf-8")


def _canonical_version():
    m = re.search(r'^\s*version\s*=\s*"([^"]+)"', _read("pyproject.toml"), re.M)
    assert m, "pyproject.toml has no [project] version"
    return m.group(1)


def test_version_single_sourced_and_docs_conform():
    canonical = _canonical_version()  # e.g. 5.10.0

    init = _read("python/synapse/__init__.py")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', init)
    assert m, "__init__.py has no __version__"
    assert m.group(1) == canonical, (
        f"__version__ ({m.group(1)}) != pyproject version ({canonical})"
    )

    # The package front-matter docstring must not contradict __version__.
    assert f"Version: {canonical}" in init, (
        f"__init__.py docstring does not state 'Version: {canonical}'"
    )

    # CLAUDE.md must state the canonical version, not a stale banner.
    claude = _read("CLAUDE.md")
    assert f"v{canonical}" in claude, (
        f"CLAUDE.md does not state the canonical SYNAPSE version v{canonical} "
        "(DOC-1: update the banner -- or this test if the version changed)."
    )

    # README banner -- the live v5.42.0 leg of the three-way split
    # (SYN-NEXT-001 adjudication row 1; W0 closes it). Anchored to the banner
    # line so a historical mention elsewhere in README cannot satisfy it.
    readme = _read("README.md")
    assert re.search(
        rf"^> v{re.escape(canonical)} \u00b7 Houdini", readme, re.M
    ), (
        f"README.md banner does not state v{canonical} "
        "(the '> vX.Y.Z \u00b7 Houdini ...' line is a live surface, not a "
        "historical receipt; scripts/sync_version.py --write sets it)."
    )


# ─────────────────────────────────────────────────────────────────
# The drift this file could NOT see: the tree vs the PUBLISHED tag
# ---------------------------------------------------------------------------
# The test above compares four in-tree locations against each other. They can
# all agree perfectly and still all be wrong together, which is exactly what
# happened: v5.43.0 was tagged on the M5b merge commit c4187d01 without the
# release ritual (.claude/release_v5420_notes.md:57 — "edit VERSION -> commit
# -> gh release create"), so a release was published while every in-tree
# location still said 5.42.0. Four checks agreeing is not a quorum when nothing
# in the loop reads the outside world.
#
# So: the newest published release tag may never be GREATER than the canonical
# version. The reverse IS legitimate and must stay allowed — inside the release
# ritual the bump commit lands before the tag is pushed, and a check that
# forbade that window would fire on every correct release.
# ─────────────────────────────────────────────────────────────────

_RELEASE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def parse_release_tag(tag: str):
    """`v5.43.0` -> (5, 43, 0). Anything else -> None.

    The repo carries 66 tags, most of them `archive/...` refs that are not
    releases at all, so this is a filter as much as a parser.
    """
    m = _RELEASE_TAG.match(tag.strip())
    return tuple(int(g) for g in m.groups()) if m else None


def parse_version(version: str):
    """`5.43.0` -> (5, 43, 0). Raises on a shape this file cannot compare."""
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version.strip())
    assert m, f"canonical version {version!r} is not a comparable X.Y.Z"
    return tuple(int(g) for g in m.groups())


def newest_release_tag(tags):
    """Highest release tag as (name, tuple), or None when there are none.

    Sorted in Python rather than by `git --sort=-v:refname` so the ordering is
    the same on every git version and is directly testable below.
    """
    parsed = [(t, parse_release_tag(t)) for t in tags]
    parsed = [(t, v) for t, v in parsed if v is not None]
    return max(parsed, key=lambda pair: pair[1]) if parsed else None


def _git_tags():
    """Every tag git knows about, or None if that question can't be answered."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(_ROOT), "tag", "--list"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def test_version_file_agrees_with_pyproject():
    """FAILS IF: VERSION and pyproject.toml disagree.

    Two documents each claim to be the source of truth — harness/CLAUDE.md says
    "VERSION is canonical; pyproject.toml and the demo script follow it", while
    this file's own docstring says "Canonical source = pyproject.toml". Nothing
    was checking that the two canonicity claims agree, so this pins it. Which
    one is canonical stops mattering once they are provably identical.
    """
    version_file = _read("VERSION").strip()
    canonical = _canonical_version()
    assert version_file == canonical, (
        f"VERSION says {version_file!r} and pyproject.toml says {canonical!r}. "
        "Both are documented as canonical, so they must be identical."
    )


def test_newest_release_tag_ignores_non_release_tags():
    """FAILS IF: the filter starts treating branch-archive refs as releases.

    The repo really does carry `archive/harness/0.5` and friends; a naive
    `git tag --list "v*"` sort has picked up worse.
    """
    tags = ["archive/harness/0.5", "v5.41.0", "archive/feat/h22-prep",
            "v5.43.0", "v5.40.1", "not-a-tag", "v5.9.0"]
    name, version = newest_release_tag(tags)
    assert name == "v5.43.0", name
    assert version == (5, 43, 0)
    # Numeric, not lexical: "v5.9.0" must not beat "v5.43.0".
    assert newest_release_tag(["v5.9.0", "v5.43.0"])[0] == "v5.43.0"
    assert newest_release_tag(["archive/harness/0.5", "nope"]) is None


@pytest.mark.parametrize("tag,canonical", [
    ("v5.43.0", "5.42.0"),   # the case that motivated this check
    ("v6.0.0", "5.43.0"),
    ("v5.43.1", "5.43.0"),
    ("v5.44.0", "5.43.0"),
])
def test_tag_ahead_of_tree_is_detected(tag, canonical):
    """FAILS IF: the comparison stops catching a published release the tree
    knows nothing about — the only direction that matters."""
    assert parse_release_tag(tag) > parse_version(canonical)


@pytest.mark.parametrize("tag,canonical", [
    ("v5.43.0", "5.43.0"),   # steady state between releases
    ("v5.42.0", "5.43.0"),   # the release ritual's own window: bump, then tag
    ("v5.9.0", "5.43.0"),
])
def test_tree_level_or_ahead_is_allowed(tag, canonical):
    """FAILS IF: the check tightens into something that fires on a correct
    release. The bump commit legitimately precedes the tag push."""
    assert not (parse_release_tag(tag) > parse_version(canonical))


def test_no_published_tag_outruns_the_canonical_version():
    """FAILS IF: a release tag exists that the tree's version does not reflect.

    This is the live half. It goes red the moment someone tags a release
    without running the version bump — which is precisely how v5.43.0 got
    published against a tree that said 5.42.0.

    Skips (loudly, with a reason) rather than passing vacuously when the
    question cannot be asked: no git, or a checkout carrying no tags. A source
    tarball has no tags and must not therefore report "no drift".
    """
    tags = _git_tags()
    if tags is None:
        pytest.skip("git unavailable — cannot compare the tree to published tags")
    newest = newest_release_tag(tags)
    if newest is None:
        pytest.skip(
            "no vX.Y.Z tags in this checkout (shallow clone without tags, or a "
            "source export) — nothing to compare the canonical version against"
        )
    tag_name, tag_version = newest
    canonical = _canonical_version()
    assert not (tag_version > parse_version(canonical)), (
        f"published release {tag_name} outruns the canonical version {canonical}: "
        "a release was tagged without the version bump, so every in-tree version "
        "location is stale while the release is public.\n"
        f"  Fix: set VERSION, pyproject.toml, python/synapse/__init__.py "
        f"(__version__ AND the docstring) and the CLAUDE.md banner to "
        f"{'.'.join(str(p) for p in tag_version)}, then re-run.\n"
        "  Do NOT bump the v-prefixed strings in harness/rope/, "
        "panel/manifests/expert.py or panel/designsystem/qss.py — those name a "
        "historical UI baseline, not the current version."
    )
