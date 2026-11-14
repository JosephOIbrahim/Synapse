"""The release verdict has exactly one implementation, and four outcomes.

A scratch runner once re-implemented this rule and applied the model's argmax
instead of the shipped policy. Four claims at 0.33-0.56 "unsupported" probability
were reported as defects: the model had said `unsupported`, and the runner treated
that label as the verdict. The policy says otherwise, and these pin it.
"""
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
GUARD = HERE.parent / "jev_release.py"

# No importorskip here. jev_release.py puts its own directory on sys.path before it
# imports jev_client, and jev_client is standard library only. The importorskip that
# stood here ran BEFORE that, so the whole file skipped ("1 skipped", exit 5) unless
# another test module had already put harness/jev on the path -- a targeted run or a
# per-file mutation check tested nothing (review finding R3, 2026-11-13).
_spec = importlib.util.spec_from_file_location("jev_release_under_test", GUARD)
jr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(jr)

POL = {"supported_min": 0.75, "unsupported_min": 0.6}


def test_a_low_probability_unsupported_label_is_a_partial():
    """The exact defect: the argmax said unsupported, the probability did not."""
    assert jr.classify_claim("unsupported", 0.35,
                             {"unsupported": 0.35, "partial": 0.4, "supported": 0.25}, POL) == "PARTIAL"


def test_a_supported_label_below_the_confidence_gate_is_a_partial():
    assert jr.classify_claim("supported", 0.51,
                             {"supported": 0.51, "partial": 0.4}, POL) == "PARTIAL"


def test_a_high_unsupported_probability_is_unsupported_whatever_the_label():
    for label in ("unsupported", "partial", "supported"):
        assert jr.classify_claim(label, 0.9, {"unsupported": 0.65}, POL) == "UNSUPPORTED"


def test_a_supported_label_above_the_gate_is_supported():
    assert jr.classify_claim("supported", 0.80, {"supported": 0.80}, POL) == "SUPPORTED"


def test_the_thresholds_come_from_the_policy_not_from_constants():
    """A tightened gate must change the verdict, or code is not reading the policy."""
    strict = {"supported_min": 0.95, "unsupported_min": 0.6}
    assert jr.classify_claim("supported", 0.80, {"supported": 0.80}, strict) == "PARTIAL"
    loose = {"supported_min": 0.10, "unsupported_min": 0.6}
    assert jr.classify_claim("supported", 0.20, {"supported": 0.20}, loose) == "SUPPORTED"


def test_notes_has_no_second_copy_of_the_rule():
    """The point of the extraction: one implementation, reached by the caller."""
    import inspect
    body = inspect.getsource(jr.notes)
    # notes() must reach the shared verdict, directly or through final_verdict
    # (which adds the existence gate and delegates the judgement to classify_claim).
    assert ("final_verdict(" in body) or ("classify_claim(" in body), (
        "notes() does not call the shared verdict")
    assert "unsupported_min" not in body, "notes() still carries its own threshold logic"


# ---- H-CLAIM-PATH: existence outranks the model -------------------------
# The guard judged a claim against a diff stat and commit subjects, neither of which
# can see whether a named path is in the tree. A note claiming a module shipped
# scored 0.84 supported while the module was absent from master.
#
# Review finding R2 (2026-11-13): the existence check then read the WORKING
# DIRECTORY, so a checkout holding the file -- untracked, ignored, or from another
# branch -- passed a claim the tagged tree contradicts. It now reads the committed
# tree of the ref being judged. These tests build their own repository: against
# the real tree the absent-module test would redden the day that module merges,
# for a reason unrelated to the control.

_MISSING = "python/synapse/host/retina_receipts.py"
_PRESENT = "harness/jev/jev_release.py"
_TAG = "v9.9.9"

# git's repository-local variables (`git rev-parse --local-env-vars`). A leaked
# GIT_DIR would point this fixture's init and commits at the repository it names.
_REPO_LOCATION_VARS = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT", "GIT_OBJECT_DIRECTORY", "GIT_DIR", "GIT_WORK_TREE",
    "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE", "GIT_INDEX_FILE",
    "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE", "GIT_PREFIX",
    "GIT_SHALLOW_FILE", "GIT_COMMON_DIR")


def _git(repo, *args):
    env = {k: v for k, v in os.environ.items() if k not in _REPO_LOCATION_VARS}
    p = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, env=env)
    assert p.returncode == 0, f"git {' '.join(args)}: {p.stderr}"
    return p.stdout.strip()


def _write(repo, rel, text="x\n"):
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


@pytest.fixture
def judged(tmp_path):
    """A repository whose tag v9.9.9 holds _PRESENT and not _MISSING."""
    if shutil.which("git") is None:
        pytest.skip("git is required to build the judged tree")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "master")
    _git(repo, "config", "user.email", "release@test.invalid")
    _git(repo, "config", "user.name", "release test")
    _git(repo, "config", "commit.gpgsign", "false")
    _write(repo, _PRESENT)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "the judged release")
    _git(repo, "tag", _TAG)
    return repo


def _verdict(claim, repo, ref=_TAG):
    return jr.final_verdict(claim, "supported", 0.85, {"supported": 0.85}, POL,
                            root=repo, ref=ref)


def test_a_claim_naming_an_absent_path_is_unsupported_even_when_the_model_says_supported(judged):
    verdict, missing = _verdict(f"One new product module ships, dormant, at {_MISSING}.", judged)
    assert verdict == "UNSUPPORTED", verdict
    assert missing == [_MISSING], missing


def test_a_claim_naming_a_present_path_keeps_the_model_verdict(judged):
    verdict, missing = _verdict(f"The guard lives at {_PRESENT}.", judged)
    assert verdict == "SUPPORTED", verdict
    assert missing == []


def test_a_claim_naming_no_path_is_left_to_the_model(judged):
    verdict, missing = _verdict("The scan is 12% of the work.", judged)
    assert verdict == "SUPPORTED"
    assert missing == []


def test_a_file_only_in_the_working_directory_is_still_missing(judged):
    """The exact R2 case: the checkout has the file, the judged tree does not."""
    _write(judged, _MISSING)
    verdict, missing = _verdict(f"The module ships at {_MISSING}.", judged)
    assert verdict == "UNSUPPORTED", verdict
    assert missing == [_MISSING]


def test_a_file_committed_after_the_tag_is_missing_at_the_tag(judged):
    _write(judged, _MISSING)
    _git(judged, "add", "-A")
    _git(judged, "commit", "-q", "-m", "after the tag")
    claim = f"The module ships at {_MISSING}."
    assert _verdict(claim, judged, ref=_TAG)[1] == [_MISSING]
    assert _verdict(claim, judged, ref="HEAD")[1] == []


def test_the_judged_tree_wins_over_a_working_copy_that_lost_the_file(judged):
    (judged / _PRESENT).unlink()
    verdict, missing = _verdict(f"The guard lives at {_PRESENT}.", judged)
    assert verdict == "SUPPORTED", verdict
    assert missing == []


def test_an_unreadable_tree_is_a_human_read_not_a_missing_list(judged):
    """Unverifiable is a different answer from absent."""
    verdict, missing = _verdict(f"The guard lives at {_PRESENT}.", judged, ref="v0.0.0-no-such-tag")
    assert verdict == "REFEREE", verdict
    assert missing == []


def _stub_jev(monkeypatch, asked):
    questions = {"guards": {"release": {
        "questions": {"claim": {"instructions": "claim c{i}", "criteria": []}},
        "policy": POL}}}
    monkeypatch.setattr(jr.jc, "load_questions", lambda: questions)

    def ask(state, spec, **_kw):
        asked.append(state)
        return {"choices": {k: {"choice": "supported", "confidence": 0.9,
                                "probabilities": {"supported": 0.9}} for k in spec}}
    monkeypatch.setattr(jr.jc, "ask", ask)


def test_notes_judges_named_paths_against_the_tag_it_was_given(judged, monkeypatch, capsys):
    """The wiring: notes() must pass its tag to the existence check. The module is
    committed AFTER the tag, so the working directory and HEAD both have it."""
    _write(judged, _MISSING)
    _git(judged, "add", "-A")
    _git(judged, "commit", "-q", "-m", "after the tag")
    _write(judged, f"docs/releases/{_TAG}.md",
           f"# {_TAG}\n\n## What ships\n\n"
           f"One new product module ships, dormant, at {_MISSING} in this release.\n\n"
           f"The release guard itself still lives at {_PRESENT} as before.\n")
    monkeypatch.setattr(jr, "REPO", judged)
    asked = []
    _stub_jev(monkeypatch, asked)

    rc = jr.notes(_TAG, _TAG)

    lines = capsys.readouterr().out.splitlines()
    shipped = [ln for ln in lines if _MISSING in ln and "ships" in ln]
    kept = [ln for ln in lines if "still lives" in ln]
    assert shipped and shipped[0].startswith("UNSUPPORTED"), lines
    assert f"[missing: {_MISSING}]" in shipped[0]
    assert kept and kept[0].startswith("SUPPORTED"), lines
    assert rc == 1
    assert len(asked) == 1


def test_notes_refuses_a_tag_that_does_not_resolve(judged, monkeypatch, capsys):
    _write(judged, "docs/releases/v0.0.0.md", "# v0.0.0\n\n## x\n\n" + "a claim " * 10 + "\n")
    monkeypatch.setattr(jr, "REPO", judged)
    asked = []
    _stub_jev(monkeypatch, asked)

    rc = jr.notes("v0.0.0", _TAG)

    out = capsys.readouterr().out
    assert rc == 1
    assert asked == [], "the model was asked to judge a tag that does not exist"
    assert "does not resolve" in out


def test_bare_filenames_are_not_treated_as_asserted_locations():
    """Naming `decide.py` asserts a thing, not a location; demanding it exist at the
    repo root would manufacture false defects in the opposite direction."""
    assert jr.claim_paths("see decide.py for the rule") == []
    assert jr.claim_paths("see harness/vision/qc_timing/decide.py") == ["harness/vision/qc_timing/decide.py"]
