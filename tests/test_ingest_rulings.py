"""scripts/ingest_rulings.py - the landing zone for a human's one-word rulings.

Closeout 2026-09-15, artist lens "decisions", DEC-3: answering `A1 ratify` on
PR #82 changed nothing in the repo because nothing read RULINGS-OPEN.md. This
pins that it now lands on the decisions board through decisions.resolve() -
same key machinery, same resolved.json, board re-rendered - and that every
refusal writes nothing.

The roster under test is the REAL 2026-09-14 roster (tracked since PR #82
merged as 329bd5b3). It is copied into a temp design_review/ dir and the board
is pointed there, with temp copies of resolved.json and DECISIONS.md, so no
test touches harness/state/. A missing roster FAILS, never skips.

Every test states the condition under which it FAILS.
"""
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "ingest_rulings.py")
REAL_ROSTER = os.path.join(ROOT, "harness", "design_review", "2026-09-14", "RULINGS-OPEN.md")
REAL_RESOLVED = os.path.join(ROOT, "harness", "state", "resolved.json")
UTC = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")


def _roster_source():
    if not os.path.isfile(REAL_ROSTER):
        pytest.fail("the real roster is missing: %s (PR #82 / 329bd5b3)" % REAL_ROSTER)
    return REAL_ROSTER


def _load_script():
    spec = importlib.util.spec_from_file_location("ingest_rulings", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


@pytest.fixture
def board(tmp_path, monkeypatch):
    """The board pointed at a temp design_review/ holding one roster, with
    temp copies of resolved.json and DECISIONS.md; no receipts, no flywheel,
    no git subprocess."""
    ing = _load_script()
    d = ing.decisions
    rosters = tmp_path / "design_review"
    (rosters / "2026-09-14").mkdir(parents=True)
    roster = rosters / "2026-09-14" / "RULINGS-OPEN.md"
    shutil.copyfile(_roster_source(), roster)
    (tmp_path / "receipts").mkdir()
    resolved = tmp_path / "resolved.json"
    if os.path.isfile(REAL_RESOLVED):
        shutil.copyfile(REAL_RESOLVED, resolved)          # temp copy of the record
    monkeypatch.setattr(d, "ROSTERS", str(rosters))
    monkeypatch.setattr(d, "RDIR", str(tmp_path / "receipts"))
    monkeypatch.setattr(d, "FLYWHEEL", str(tmp_path / "no_flywheel.json"))
    monkeypatch.setattr(d, "RESOLVED", str(resolved))
    monkeypatch.setattr(d, "OUT", str(tmp_path / "DECISIONS.md"))
    monkeypatch.setattr(d, "file_ages", lambda: {})
    d.write_markdown(d.collect())                          # temp copy of the board
    return SimpleNamespace(d=d, ing=ing, roster=str(roster),
                           resolved=str(resolved), out=str(tmp_path / "DECISIONS.md"))


def _run(b, reply, *extra):
    out = io.StringIO()
    rc = b.ing.ingest(b.roster, reply, out=out, **dict(extra))
    return rc, out.getvalue()


def _entries(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["resolutions"]


def _open_ids(b):
    return {i["leg"] for i in b.d.collect(with_ages=False) if i["kind"] == "design"}


# --- known ids parse -----------------------------------------------------

def test_roster_ids_parse_from_headings_and_table(board):
    """FAILS IF: the real roster's ids do not reach the board, or the heading
    title is not stripped of its **[RATIFY]** tag (the key must hash the
    question, not its markdown)."""
    with open(board.roster, encoding="utf-8") as fh:
        ids = board.d.roster_ids(fh.read())
    assert {"A1", "B2", "C2a"} <= set(ids), sorted(ids)
    assert len(ids) >= 16, sorted(ids)
    assert ids["A1"] == "Airy is specification, not binding", ids["A1"]
    assert "[" not in "".join(ids.values())
    on_board = {i["leg"]: i for i in board.d.collect(with_ages=False)
                if i["kind"] == "design"}
    assert set(on_board) == set(ids)
    assert len({i["key"] for i in on_board.values()}) == len(ids), "keys collide"


def test_table_only_ids_fall_back_to_the_table_cell(board):
    """FAILS IF: an id present only in the at-a-glance table is dropped."""
    text = ("| **Z9** | a call with no heading yet |\n\n"
            "## A1 \u2014 Airy is specification **[RATIFY]**\n")
    ids = board.d.roster_ids(text)
    assert ids == {"Z9": "a call with no heading yet", "A1": "Airy is specification"}


# --- known ids record ----------------------------------------------------

def test_known_rulings_land_with_who_when_evidence_and_verbatim_word(board):
    """FAILS IF: `A1 ratify` no longer changes the repo - the ruling must land
    in resolved.json through decisions.resolve(), keyed like every other item,
    carrying who / when (UTC) / roster path + sha / the verbatim word - and the
    derived board must be re-rendered without the ruled items."""
    n0 = len(_entries(board.resolved))
    board_before = _bytes(board.out)
    rc, text = _run(board, "A1 ratify\n\n# a comment\nB2 keep the accent, retarget the pin\nC2a ship\n")
    assert rc == 0, text
    entries = _entries(board.resolved)
    assert len(entries) == n0 + 3
    by_id = {e["item_snapshot"]["leg"]: e for e in entries[n0:]}
    assert set(by_id) == {"A1", "B2", "C2a"}
    a1 = by_id["A1"]
    assert a1["word"] == "ratify"
    assert a1["by"] == "human"
    assert UTC.match(a1["resolved_at_utc"]), a1["resolved_at_utc"]
    assert a1["evidence"]["sha256"] == _sha(board.roster)
    assert a1["evidence"]["roster"].endswith("2026-09-14/RULINGS-OPEN.md")
    assert a1["item_snapshot"]["kind"] == "design"
    assert a1["key"] == board.d.item_key(a1["item_snapshot"])
    assert by_id["B2"]["word"] == "keep the accent, retarget the pin"
    assert by_id["C2a"]["word"] == "ship"
    assert not ({"A1", "B2", "C2a"} & _open_ids(board)), "ruled items still open"
    after = _bytes(board.out)
    assert after != board_before, "DECISIONS.md was not re-rendered"
    assert b"`A1`" in board_before and b"`A1`" not in after
    assert "recorded" in text and "A1" in text


def test_who_is_recorded_as_given(board):
    """FAILS IF: --who does not reach the record."""
    rc, text = _run(board, "A1 ratify\n", ("who", "joe"))
    assert rc == 0, text
    assert _entries(board.resolved)[-1]["by"] == "joe"


def test_reply_line_shapes(board):
    """FAILS IF: the PR-comment shapes people actually type are not read."""
    rulings, errors = board.ing.parse_reply(
        "A1 ratify\n- B2: keep the accent\n**C2a** ship\nC4 \u2014 fallback\n")
    assert errors == []
    assert [(r[1], r[2]) for r in rulings] == [
        ("A1", "ratify"), ("B2", "keep the accent"), ("C2a", "ship"), ("C4", "fallback")]


# --- refusals write nothing ----------------------------------------------

def test_unknown_id_is_refused_and_nothing_is_written(board):
    """FAILS IF: an id the roster does not carry is recorded, or a valid line
    in the same reply is recorded despite the refusal."""
    r0, o0 = _bytes(board.resolved), _bytes(board.out)
    rc, text = _run(board, "A1 ratify\nZ9 ship\n")
    assert rc == 2
    assert "Z9" in text and "REFUSED" in text
    assert _bytes(board.resolved) == r0 and _bytes(board.out) == o0
    assert "A1" in _open_ids(board)


def test_dry_run_writes_nothing(board):
    """FAILS IF: --dry-run touches resolved.json or DECISIONS.md."""
    r0, o0 = _bytes(board.resolved), _bytes(board.out)
    rc, text = _run(board, "A1 ratify\nC2a ship\n", ("dry_run", True))
    assert rc == 0, text
    assert "DRY RUN" in text and "A1" in text and "C2a" in text
    assert _bytes(board.resolved) == r0 and _bytes(board.out) == o0
    assert {"A1", "C2a"} <= _open_ids(board)


def test_second_identical_ruling_is_refused_as_duplicate(board):
    """FAILS IF: the same ruling can be recorded twice - the record would then
    carry two answers for one question."""
    assert _run(board, "A1 ratify\n")[0] == 0
    r1, o1 = _bytes(board.resolved), _bytes(board.out)
    rc, text = _run(board, "A1 ratify\n")
    assert rc == 2
    assert "already" in text and "A1" in text
    assert _bytes(board.resolved) == r1 and _bytes(board.out) == o1
    assert sum(1 for e in _entries(board.resolved)
               if e["item_snapshot"]["leg"] == "A1") == 1


def test_repeated_id_inside_one_reply_is_refused(board):
    """FAILS IF: `A1 ratify` twice in one reply records either line."""
    r0 = _bytes(board.resolved)
    rc, text = _run(board, "A1 ratify\nA1 ratify\n")
    assert rc == 2 and "A1" in text
    assert _bytes(board.resolved) == r0


def test_malformed_lines_are_refused(board):
    """FAILS IF: an id with no word, or a line with no id, slips through."""
    r0 = _bytes(board.resolved)
    for reply in ("A1\n", "hello world\n", "   \n"):
        rc, text = _run(board, reply)
        assert rc == 2, (reply, text)
        assert _bytes(board.resolved) == r0


def test_roster_outside_the_board_is_refused(board, tmp_path):
    """FAILS IF: a roster the board cannot see is accepted - its rulings
    would land in resolved.json with keys no board item ever carries."""
    stray = tmp_path / "elsewhere" / "RULINGS-OPEN.md"
    stray.parent.mkdir()
    shutil.copyfile(board.roster, stray)
    r0 = _bytes(board.resolved)
    out = io.StringIO()
    rc = board.ing.ingest(str(stray), "A1 ratify\n", out=out)
    assert rc == 2 and "does not read" in out.getvalue()
    assert _bytes(board.resolved) == r0


def test_cli_entry_point_runs():
    """FAILS IF: the script cannot be invoked from a shell (import path or
    argparse broken)."""
    r = subprocess.run([sys.executable, SCRIPT, "--help"], capture_output=True,
                       text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "--dry-run" in r.stdout and "--who" in r.stdout
