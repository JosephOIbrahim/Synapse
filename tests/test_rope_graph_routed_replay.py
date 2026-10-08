"""The veto, replayed over every finding the cto run of 2026-10-07 routed -- all 86, not the 12 seeds.

Each shape (file, line, evidence) is snapshotted in test_rope_graph_routed_replay.json beside this
file, with the veto's verdict, the line it settles on, and the evidence it keeps. The files come
from the run's own base tree (ed01db41), read out of git, so the replay is the run as it was.

The golden matches what the veto at 58a4295c gives on every shape but one: IR-04 names a file under
C:/Program Files, which os.path.join let through to the host's own Houdini install, so on a box
with Houdini the old veto passed it and a fixer would have been sent there. It now reads
"outside the repo". Known and pinned as they stand, not endorsed: PUX-02 cites a line range
(demo-repairs.md:53-55 `...`), which the span reader does not take, and SC-9 cites a file with no
line; both are vetoed though their quotes are real. A change there must update the golden on
purpose.

Beyond the golden, every pass is checked on its own terms: the kept evidence is more than one
word and occurs in the file within the window around the line the veto settled on.
"""
import importlib.util
import io
import json
import os
import re
import subprocess
import tarfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH = os.path.join(REPO, "harness", "rope", "graph.py")
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_rope_graph_routed_replay.json")

with open(DATA, encoding="utf-8") as _f:
    _DOC = json.load(_f)
SHAPES = _DOC["shapes"]
TREE = _DOC["tree"]


def _norm(s):
    return re.sub(r"\s+", " ", str(s)).strip()


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    """The run's base tree, only the files the shapes name, extracted from git."""
    if subprocess.run(["git", "-C", REPO, "cat-file", "-e", TREE + "^{commit}"],
                      capture_output=True).returncode:
        pytest.skip("base tree %s is not in this clone" % TREE)
    files = sorted({s["file"] for s in SHAPES if not re.match(r"(?:[A-Za-z]:)?/", s["file"])})
    tar = subprocess.run(["git", "-C", REPO, "archive", "--format=tar", TREE, "--", *files],
                         capture_output=True, check=True).stdout
    root = tmp_path_factory.mktemp("ed01db41")
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        if hasattr(tarfile, "data_filter"):
            t.extractall(root, filter="data")
        else:                                  # pre-3.11.4: git archive of our own tree
            t.extractall(root)
    return str(root)


def _graph(root):
    spec = importlib.util.spec_from_file_location("_rope_graph_routed_replay", GRAPH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROOT = mod.rope.ROOT = root
    return mod


@pytest.fixture(scope="module")
def G(base):
    return _graph(base)


def test_the_snapshot_holds_every_routed_shape():
    """Fails if the snapshot is cut back toward the seeds: the replay is over all 86 findings."""
    assert len(SHAPES) == 86
    assert len({s["id"] for s in SHAPES}) == 86
    assert {s["route"] for s in SHAPES} >= {"fix_now", "demo_risk", "owner_call", "post_demo"}


@pytest.mark.parametrize("shape", SHAPES, ids=[s["id"] for s in SHAPES])
def test_the_veto_gives_the_pinned_verdict(G, shape):
    """Fails if any routed shape changes verdict, settles on another line, or keeps other evidence."""
    c = {"file": shape["file"], "line": shape["line"], "evidence": shape["evidence"]}
    got = {"veto": G.veto(c), "line": c["line"], "evidence": c["evidence"]}
    assert got == shape["expect"]


@pytest.mark.parametrize("shape", [s for s in SHAPES if s["expect"]["veto"] == ""],
                         ids=[s["id"] for s in SHAPES if s["expect"]["veto"] == ""])
def test_every_pass_keeps_a_real_line_near_where_it_settles(G, base, shape):
    """Fails if a pass keeps one word, or evidence that is not in the file near its settled line."""
    c = {"file": shape["file"], "line": shape["line"], "evidence": shape["evidence"]}
    assert G.veto(c) == ""
    kept = _norm(c["evidence"])
    assert not re.fullmatch(r"""["'`]?\w+["'`]?""", kept)
    with open(os.path.join(base, c["file"]), encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    ln = int(c["line"])
    assert kept in _norm(" ".join(lines[max(0, ln - 9): ln + 8]))


def test_an_absolute_path_never_reaches_the_host_file(tmp_path):
    """Fails if a finding naming a file outside the repo is read off the host instead of vetoed."""
    G = _graph(str(tmp_path))
    for f in ("C:/Program Files/Side Effects Software/Houdini 22.0.400/python313/x.pth",
              "/etc/hosts", "C:\\Windows\\win.ini", "../outside.py", "python/../../outside.py"):
        assert G.veto({"file": f, "line": 1, "evidence": "anything at all here"}) == "outside the repo"
