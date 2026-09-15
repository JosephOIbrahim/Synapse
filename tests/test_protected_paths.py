"""harness/protected_paths.py - the one parser + matcher for the protected set
(upgrade path 1h, harness-review 2026-09-15, finding FENCE-4).

run.ts and orchestrate.ps1 both shell out to this module, so its glob semantics
ARE the fence. These pin: the file format, the exact three globs the review
names, whole-path anchoring (VERSION never matches docs/VERSION), `**` depth,
path normalisation, and the CLI exit-code contract (0 clean / 1 hit / 2 error).
Stock python, no repo imports, no hython.
"""
import importlib.util
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "harness", "protected_paths.py")
TXT = os.path.join(ROOT, "harness", "protected_paths.txt")


def _mod():
    spec = importlib.util.spec_from_file_location("protected_paths_under_test", MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_shipped_file_declares_exactly_the_review_set():
    """The review's protected set, verbatim. A fourth glob or a dropped one is a
    policy change and must show up here, not slip in."""
    globs = _mod().load(TXT)
    assert globs == ["VERSION", "harness/state/**", "harness/verify/*_baseline.json"]


def test_parse_skips_comments_and_blanks_and_normalises():
    m = _mod()
    text = "# header\n\n  VERSION  \n#  harness/state/**\n.\\harness\\verify\\*_baseline.json\n"
    assert m.parse(text) == ["VERSION", "harness/verify/*_baseline.json"]


@pytest.mark.parametrize("glob,path,expected", [
    ("VERSION", "VERSION", True),
    ("VERSION", "docs/VERSION", False),          # anchored: root file only
    ("VERSION", "VERSION.bak", False),
    ("VERSION", "./VERSION", True),               # leading ./ dropped
    ("VERSION", "VERSION\n", True),               # git diff line ending tolerated
    ("harness/state/**", "harness/state/done.json", True),
    ("harness/state/**", "harness/state/a/b/c.json", True),
    ("harness/state/**", "harness\\state\\done.json", True),   # backslash normalised
    ("harness/state/**", "harness/state_x/y.json", False),
    ("harness/state/**", "harness/stated", False),
    ("harness/verify/*_baseline.json", "harness/verify/suite_baseline.json", True),
    ("harness/verify/*_baseline.json", "harness/verify/_baseline.json", True),
    ("harness/verify/*_baseline.json", "harness/verify/sub/x_baseline.json", False),  # * never crosses /
    ("harness/verify/*_baseline.json", "harness/verify/checks.py", False),
    ("a/**/b.txt", "a/b.txt", True),              # ** matches zero directories
    ("a/**/b.txt", "a/x/b.txt", True),
    ("a/**/b.txt", "a/x/y/b.txt", True),
    ("a/**/b.txt", "a/x/b.txt.bak", False),
    ("*.md", "README.md", True),
    ("*.md", "docs/x.md", False),
    ("f?o", "foo", True),
    ("f?o", "f/o", False),
])
def test_glob_semantics(glob, path, expected):
    assert _mod().is_protected(path, [glob]) is expected


def test_protected_hits_keeps_order_and_dedupes():
    m = _mod()
    globs = m.load(TXT)
    paths = ["python/x.py", "harness/state/done.json", "VERSION", "harness/state/done.json",
             "harness/verify/checks.py", "harness/verify/suite_baseline.json", "", "  "]
    assert m.protected_hits(paths, globs) == [
        "harness/state/done.json", "VERSION", "harness/verify/suite_baseline.json"]


def _cli(*args, stdin=None):
    return subprocess.run([sys.executable, MOD, *args], input=stdin,
                          capture_output=True, text=True, timeout=60)


def test_cli_check_args_exit_1_and_prints_hits():
    r = _cli("--check", "python/x.py", "VERSION", "harness/state/done.json")
    assert r.returncode == 1, r.stderr
    assert r.stdout.splitlines() == ["VERSION", "harness/state/done.json"]


def test_cli_check_stdin_clean_exit_0():
    r = _cli("--check", "-", stdin="python/x.py\r\ndocs/VERSION\n\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == ""


def test_cli_check_stdin_hit_exit_1():
    r = _cli("--check", "-", stdin="python/x.py\nharness/verify/suite_baseline.json\n")
    assert r.returncode == 1
    assert r.stdout.splitlines() == ["harness/verify/suite_baseline.json"]


def test_cli_list_prints_the_set():
    r = _cli("--list")
    assert r.returncode == 0
    assert r.stdout.splitlines() == ["VERSION", "harness/state/**", "harness/verify/*_baseline.json"]


def test_cli_missing_or_empty_set_file_exit_2(tmp_path):
    r = _cli("--file", str(tmp_path / "nope.txt"), "--check", "VERSION")
    assert r.returncode == 2 and "cannot read" in r.stderr
    empty = tmp_path / "empty.txt"
    empty.write_text("# nothing here\n", encoding="utf-8")
    r = _cli("--file", str(empty), "--check", "VERSION")
    assert r.returncode == 2 and "empty set" in r.stderr
