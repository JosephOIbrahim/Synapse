"""M2-E (pipeline citizen, report §4.3 + §5 M2 item 5): frame-token expander.

str.replace('$F4', ...) handled exactly one token spelling — artist paths
using $F, $F2, $F5 polled a literal token path and produced false "output
wasn't created" failures. handler_helpers._expand_frame_tokens now owns the
rule and is wired at the three handlers_render.py resolution sites. The
TOPS sequence validator's zfill(4) hardcode is replaced by padding-agnostic
directory matching — 3- or 5-digit shows no longer report every frame
missing (→ pointless farm resubmits).

Headless — pure path/string logic plus tmp_path fixtures.
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# Plant-or-enrich the resident hou fake BEFORE importing handler modules:
# importing them bare leaves `handlers.hou` undefined for every later test
# file (first-importer wins — docs/HARDENING_RUN_2026-06-10.md forensics).
if "hou" not in sys.modules:
    sys.modules["hou"] = ModuleType("hou")
_h = sys.modules["hou"]
for _attr in ("undos", "node", "ui"):
    if not hasattr(_h, _attr):
        setattr(_h, _attr, MagicMock())
if not hasattr(_h, "text"):
    # Sibling convention (test_autonomy_live_contract.py): expandString
    # returns a real str — later files' handlers Path() over it.
    _h.text = MagicMock()
    _h.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
if not hasattr(_h, "frame"):
    _h.frame = MagicMock(return_value=1)
if "hdefereval" not in sys.modules:
    _hd = ModuleType("hdefereval")
    _hd.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    sys.modules["hdefereval"] = _hd

from synapse.server.handler_helpers import _expand_frame_tokens  # noqa: E402
from synapse.server.handlers_tops import render_sequence as _rs  # noqa: E402
from synapse.server.handlers_tops.render_sequence import _validate_rendered_frames  # noqa: E402


@pytest.fixture(autouse=True)
def _no_hou_expansion(monkeypatch):
    """Validator tests use real tmp_path dirs — the resident fake hou's
    expandString (a MagicMock) must not garble them. Patch the module
    directly; residency is order-fragile."""
    monkeypatch.setattr(_rs, "HOU_AVAILABLE", False)


# ---------------------------------------------------------------------------
# _expand_frame_tokens
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pattern,frame,expected", [
    ("render.$F4.exr", 42, "render.0042.exr"),       # the old supported case
    ("render.$F.exr", 42, "render.42.exr"),          # bare $F
    ("render.$F2.exr", 7, "render.07.exr"),
    ("render.$F5.exr", 42, "render.00042.exr"),
    ("a_$F4/b.$F4.exr", 3, "a_0003/b.0003.exr"),     # multiple tokens
    ("no_tokens.exr", 1, "no_tokens.exr"),           # passthrough
])
def test_expand_frame_tokens(pattern, frame, expected):
    assert _expand_frame_tokens(pattern, frame) == expected


def test_expand_accepts_float_frame():
    assert _expand_frame_tokens("f.$F4.exr", 12.0) == "f.0012.exr"


def test_expand_leaves_other_tokens_alone():
    # $HIP/$JOB are NOT frame tokens — expansion of those is hou's job.
    assert _expand_frame_tokens("$HIP/render/f.$F4.exr", 5) == "$HIP/render/f.0005.exr"


# ---------------------------------------------------------------------------
# _validate_rendered_frames — padding-agnostic
# ---------------------------------------------------------------------------


def test_validator_four_digit_padding_still_works(tmp_path):
    (tmp_path / "shot.0001.exr").write_bytes(b"x")
    (tmp_path / "shot.0002.exr").write_bytes(b"x")
    res = _validate_rendered_frames(str(tmp_path), "shot", 1, 3, 1)
    assert res["found_frames"] == 2
    assert res["missing_frames"] == [3]


def test_validator_three_digit_padding(tmp_path):
    """The zfill(4) hardcode reported these as all-missing."""
    (tmp_path / "shot.001.exr").write_bytes(b"x")
    (tmp_path / "shot.002.exr").write_bytes(b"x")
    res = _validate_rendered_frames(str(tmp_path), "shot", 1, 2, 1)
    assert res["missing_frames"] == []
    assert res["found_frames"] == 2


def test_validator_five_digit_padding(tmp_path):
    (tmp_path / "shot.00042.exr").write_bytes(b"x")
    res = _validate_rendered_frames(str(tmp_path), "shot", 42, 42, 1)
    assert res["missing_frames"] == []
    assert res["found_frames"] == 1


def test_validator_zero_size_flagged(tmp_path):
    (tmp_path / "shot.0001.exr").write_bytes(b"")
    res = _validate_rendered_frames(str(tmp_path), "shot", 1, 1, 1)
    assert res["found_frames"] == 1
    assert res["zero_size_frames"] == [1]


def test_validator_prefix_with_regex_chars(tmp_path):
    (tmp_path / "shot(v2).0001.exr").write_bytes(b"x")
    res = _validate_rendered_frames(str(tmp_path), "shot(v2)", 1, 1, 1)
    assert res["missing_frames"] == []


def test_validator_missing_directory_reports_all_missing(tmp_path):
    res = _validate_rendered_frames(str(tmp_path / "nope"), "shot", 1, 2, 1)
    assert res["missing_frames"] == [1, 2]
    assert res["found_frames"] == 0


def test_validator_other_prefix_not_counted(tmp_path):
    (tmp_path / "other.0001.exr").write_bytes(b"x")
    res = _validate_rendered_frames(str(tmp_path), "shot", 1, 1, 1)
    assert res["missing_frames"] == [1]
