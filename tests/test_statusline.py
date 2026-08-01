"""The statusline is a reporting tool, and this repo retired one of those for lying.

`harness/heats_status.py` read real receipts into a layout that no longer
described anything. It never errored and never looked stale. A status surface
that is always on screen earns more trust than one you have to run, so it needs
more proof, not less.

Every test states the condition under which it FAILS.
"""
import importlib
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SL = os.path.join(ROOT, "harness", "statusline.py")


def _mod(name):
    sys.path.insert(0, os.path.join(ROOT, "harness"))
    try:
        return importlib.import_module(name)
    finally:
        sys.path.pop(0)


def render(payload="{}"):
    return subprocess.run([sys.executable, SL], input=payload, cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


# ------------------------------------------------- the two-sources-agree test

def test_bar_agrees_with_the_authoritative_guard():
    """FAILS IF: the bar's armed count disagrees with worktree_guard.

    The bar uses a cheap registry read; the guard runs the full resolution
    probe. They answer the same question by different routes and must not
    diverge - a bar that under-reports armed legs is worse than no bar, because
    it is read as an all-clear.
    """
    s = _mod("statusline")
    g = _mod("worktree_guard")
    reg = g.registered_worktrees()
    authoritative = sum(1 for l in g._legs() if not g.verify(l.get("worktree"), reg)[0])
    assert s.armed_count(s.legs()) == authoritative, (
        "bar says %s armed, guard says %s" % (s.armed_count(s.legs()), authoritative))


def test_branch_read_without_git_matches_git():
    """FAILS IF: the subprocess-free branch read drifts from git's answer.

    The bar reads .git/HEAD directly to stay under 100ms. That shortcut is only
    legitimate while it agrees with the tool it replaced.
    """
    s = _mod("statusline")
    real = subprocess.run(["git", "-C", ROOT, "rev-parse", "--abbrev-ref", "HEAD"],
                          capture_output=True, text=True, encoding="utf-8").stdout.strip()

    if real == "HEAD":
        # DETACHED HEAD — what CI checks out for a pull request. git reports the
        # literal string "HEAD" because there is no branch to name, while the
        # file read returns the commit sha. The two cannot agree, and that is
        # not drift: the question "do these name the same branch" is ill-posed
        # when no branch exists. Assert the useful property instead — the bar
        # still renders something that identifies the commit, rather than
        # echoing a meaningless "HEAD" or going blank.
        got = s.branch()
        assert got and got != "HEAD", (
            "detached HEAD: the bar must still identify the commit, got %r" % got)
        return

    assert s.branch() == real, "%r != %r" % (s.branch(), real)


def test_registry_matches_git_worktree_list():
    """FAILS IF: reading .git/worktrees/ misses a worktree git knows about."""
    s = _mod("statusline")
    out = subprocess.run(["git", "-C", ROOT, "worktree", "list", "--porcelain"],
                         capture_output=True, text=True, encoding="utf-8").stdout
    from_git = {s._norm(ln[len("worktree "):])
                for ln in out.splitlines() if ln.startswith("worktree ")}
    assert s.registered_paths() == from_git, (
        "missing: %s | extra: %s"
        % (from_git - s.registered_paths(), s.registered_paths() - from_git))


# --------------------------------------------------------------- the contract

def test_render_path_spawns_no_subprocess(monkeypatch):
    """FAILS IF: rendering shells out.

    The first draft called git once per orphan directory and took 919ms per
    turn. This pins the fix: any subprocess on the render path fails here
    before it reaches a user's terminal.
    """
    s = _mod("statusline")

    def boom(*a, **k):
        raise AssertionError("render path spawned a subprocess: %r" % (a[:1],))

    monkeypatch.setattr(s.subprocess, "run", boom)
    s.render({})  # must not raise


def test_never_raises_on_garbage_input():
    """FAILS IF: bad stdin produces a traceback or an empty bar.

    Claude Code pipes a JSON payload whose shape can change. A statusline that
    dies leaves a blank strip and no explanation of why.
    """
    for payload in ("", "{}", "not json", '{"transcript_path": null}',
                    '{"transcript_path": 12345}', '{"deeply": {"nested": []}}'):
        out = render(payload)
        assert out.returncode == 0, "exit %d on %r" % (out.returncode, payload)
        assert out.stdout.strip(), "empty bar on %r" % payload
        assert "Traceback" not in out.stderr, out.stderr


def test_zero_segments_are_hidden(monkeypatch, tmp_path):
    """FAILS IF: a zero-valued segment renders.

    A bar that prints '0 armed' every day trains the eye past it, and then it
    is not read on the day it says 14.

    The counters are FORCED to zero here. An earlier draft asserted against the
    live tree, where every counter happened to be non-zero - so `if True` and
    `if count` were indistinguishable and the test passed against a mutant that
    rendered every zero segment. It could not fail, which made it a decoration
    in exactly the sense Law 1 names.
    """
    s = _mod("statusline")
    monkeypatch.setattr(s, "armed_count", lambda legs: 0)
    monkeypatch.setattr(s, "attention_count", lambda legs: 0)
    monkeypatch.setattr(s, "running_legs", lambda: [])
    monkeypatch.setattr(s, "live_agents", lambda p: 0)
    monkeypatch.setattr(s, "decision_count", lambda: 0)
    monkeypatch.setattr(s, "STAMP", str(tmp_path / "none.json"))

    out = s.render({})
    for word in ("armed", "running", "attention", "agents", "decisions", " ok "):
        assert word not in out, "rendered an empty segment %r in %r" % (word, out)
    # The branch must survive on its own - an all-clear bar is not a blank one.
    assert s.branch() in out, "branch vanished from an all-clear bar: %r" % out
    assert "│" not in out and "|" not in out, \
        "separator rendered with nothing to separate: %r" % out


def test_suite_segment_absent_without_a_stamp(tmp_path, monkeypatch):
    """FAILS IF: a suite figure appears with no producer behind it.

    Law 2. The figure comes from a stamp written by piping a real pytest run;
    with no stamp the segment must not render rather than show a stale or
    invented number.
    """
    s = _mod("statusline")
    monkeypatch.setattr(s, "STAMP", str(tmp_path / "absent.json"))
    assert s.suite() is None
    assert " ok " not in s.render({})


def test_stamp_requires_a_real_pytest_summary():
    """FAILS IF: --stamp accepts input with no pytest summary in it.

    The number must come from pytest's own output, never from a hand-typed
    argument. Feeding it prose must be refused.
    """
    out = subprocess.run([sys.executable, SL, "--stamp"],
                         input="the suite is fine, trust me", cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8")
    assert out.returncode != 0, "accepted a summary-free stdin"


def test_stamp_records_its_producer_and_commit(tmp_path):
    """FAILS IF: a stamp lands without provenance.

    A figure in an always-visible bar needs to say where it came from and which
    tree it measured, or it is the heats_status.py defect with a new face.

    Writes to a redirected path - an earlier draft of this test overwrote the
    real stamp while a full-suite run was writing the same file.
    """
    target = tmp_path / "stamp.json"
    env = dict(os.environ, SYNAPSE_SUITE_STAMP=str(target))
    out = subprocess.run([sys.executable, SL, "--stamp"],
                         input="== 5 passed, 1 skipped in 0.10s ==", cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8", env=env)
    assert out.returncode == 0, out.stderr
    with open(target, encoding="utf-8") as fh:
        rec = json.load(fh)
    assert rec["passed"] == 5 and rec["skipped"] == 1
    assert rec.get("producer") and rec.get("commit") and rec.get("at")


def test_stamp_reads_the_summary_line_not_the_whole_stream(tmp_path):
    """FAILS IF: a count is taken from anywhere but pytest's summary line.

    A plain search over the whole stream matches the first occurrence in it.
    Against a real run that reported '137 skipped' in its summary, an earlier
    draft stamped 2 - picked up from noise further up the output.
    """
    noisy = "\n".join([
        "warning: 2 skipped checks in some unrelated preamble",
        "  99 passed, 3 failed earlier in a quoted log line",
        "",
        "===== 5296 passed, 137 skipped, 553 warnings in 124.12s =====",
    ])
    target = tmp_path / "s.json"
    out = subprocess.run([sys.executable, SL, "--stamp"], input=noisy, cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8",
                         env=dict(os.environ, SYNAPSE_SUITE_STAMP=str(target)))
    assert out.returncode == 0, out.stderr
    rec = json.load(open(target, encoding="utf-8"))
    assert rec["passed"] == 5296, "took passed from noise: %r" % rec
    assert rec["skipped"] == 137, "took skipped from noise: %r" % rec
    assert rec["failed"] == 0, "took failed from noise: %r" % rec


def test_head_sha_matches_git():
    """FAILS IF: the subprocess-free HEAD read drifts from git's answer."""
    s = _mod("statusline")
    real = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"],
                          capture_output=True, text=True, encoding="utf-8").stdout.strip()
    assert s.head_sha() == real, "%r != %r" % (s.head_sha(), real)


def test_suite_figure_from_another_commit_is_not_shown_as_fresh(tmp_path, monkeypatch):
    """FAILS IF: a figure measured on a different tree renders as a fresh pass.

    This shipped broken. The bar showed '5307 ok 17m' in confident green while
    the stamp named a commit two behind HEAD - a green suite asserted for a tree
    it had never run against, with an age that read as current.

    Age is the wrong axis when the tree moves underneath you. A figure from
    another commit is not old evidence, it is evidence about something else.
    """
    s = _mod("statusline")
    stamp = tmp_path / "s.json"
    monkeypatch.setattr(s, "STAMP", str(stamp))

    def write(commit):
        stamp.write_text(json.dumps({"at": __import__("time").time(), "passed": 5307,
                                     "failed": 0, "commit": commit}), encoding="utf-8")

    # Same tree -> green, with an age.
    write(s.head_sha()[:12])
    assert s.suite()["same_tree"] is True
    out_same = s.render({})
    assert "other tree" not in out_same
    assert "5307 ok" in out_same

    # Different tree -> must NOT read as fresh.
    write("0" * 12)
    assert s.suite()["same_tree"] is False
    out_drift = s.render({})
    assert "other tree" in out_drift, "drifted figure rendered as current: %r" % out_drift
    assert s.GRN not in out_drift.split("5307")[0][-12:], \
        "drifted figure still rendered in the pass colour"


def test_stamp_refuses_to_write_a_zero_pass_summary():
    """FAILS IF: a run that passed nothing is stamped as a suite figure.

    '0 passed' with errors is a collection failure, not a green suite. Letting
    it through would put a confident-looking figure on screen for a tree whose
    tests never ran.
    """
    out = subprocess.run([sys.executable, SL, "--stamp"],
                         input="== 0 passed, 3 errors in 1.2s ==", cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8",
                         env=dict(os.environ, SYNAPSE_SUITE_STAMP=os.devnull))
    assert out.returncode != 0, "stamped a zero-pass run"
