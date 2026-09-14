"""The session journal must date-stamp every line.

INTENT.md Section 9 lists what qualification MUST record -- "Time to an
accepted, editable result", "Measured dispatch-stop and actual-control-return
latency".  None of it is computable from an append-only log whose entries carry
only a time of day: two lines reading 14:32:05 from two different days are
indistinguishable, so sessions cannot be bounded and no per-task median can be
derived.  Section 6's record clause wants an operation's record to connect to
its actual changes; a record that cannot be placed on a calendar is not that.

These tests pin the *written* format and the one in-repo reader that parses it
positionally.  Both are able to fail: before the fix the stamp is `%H:%M:%S`
and carries no date at all.
"""

from __future__ import annotations

import datetime
import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "python"))

from synapse.panel.session_journal import SessionJournal  # noqa: E402

# The stamp the journal is required to write.  Local wall clock plus an
# explicit UTC offset: unambiguous about zone, and elapsed-time arithmetic
# across a DST boundary stays correct.
STAMP_FORMAT = "%Y-%m-%d %H:%M:%S%z"

# Every journal line is `[<stamp>] <KIND> ...`.
_BRACKET = re.compile(r"^\[([^\]]+)\]\s")

# A line as the journal wrote them before this fix.  Existing production logs
# are full of these and must stay machine-readable.
LEGACY_LINE = "[14:32:05] TOOL houdini_create_node: Created geo at /obj/box1 (12 ms)"

# A line in the required format, written out literally.  Asserting only against
# a journal-produced line could not fail before the fix -- the journal was
# producing legacy lines, so the old reader matched them and the test passed
# while proving nothing.
DATED_LINE = (
    "[2026-09-14 14:32:05-0400] TOOL houdini_create_node: "
    "Created geo at /obj/box1 (12 ms)"
)


def _stamp_of(line: str) -> str:
    match = _BRACKET.match(line)
    assert match, f"journal line has no bracketed stamp: {line!r}"
    return match.group(1)


def _read_lines(journal: SessionJournal) -> list[str]:
    return Path(journal._log_path).read_text(encoding="utf-8").splitlines()


def test_every_written_line_carries_a_parseable_date(tmp_path):
    """A freshly written line must place itself on a calendar day.

    Fails before the fix: `_timestamp()` returns `%H:%M:%S`, so strptime
    against a dated format raises and the day is unrecoverable.
    """
    journal = SessionJournal(str(tmp_path))
    journal.log_tool("houdini_create_node", {"type": "geo", "path": "/obj/box1"}, None)
    journal.log_command("/journal", "opened")
    journal.log_event("shot_login", "scene opened")

    lines = _read_lines(journal)
    assert len(lines) == 3, f"expected one line per writer, got {lines!r}"

    today = datetime.datetime.now().astimezone().date()
    for line in lines:
        stamp = _stamp_of(line)
        try:
            parsed = datetime.datetime.strptime(stamp, STAMP_FORMAT)
        except ValueError as exc:
            pytest.fail(
                f"journal stamp {stamp!r} is not parseable as {STAMP_FORMAT!r} "
                f"-- the entry cannot be bound to a session or a day: {exc}"
            )
        assert parsed.tzinfo is not None, (
            f"stamp {stamp!r} carries no UTC offset; elapsed time across a DST "
            "boundary would be silently wrong"
        )
        assert parsed.date() == today, (
            f"stamp {stamp!r} resolved to {parsed.date()}, expected {today}"
        )


def test_search_can_bound_entries_by_calendar_day(tmp_path):
    """Section 9 needs sessions bounded across days; searching a date is the
    cheapest form of that and is impossible before the fix."""
    journal = SessionJournal(str(tmp_path))
    journal.log_tool("houdini_render", {"rop_path": "/stage/karma1"}, None)

    today = datetime.datetime.now().astimezone().strftime("%Y-%m-%d")
    hits = journal.search(today)
    assert hits, (
        f"no journal entry matches today's date {today!r}; entries cannot be "
        "grouped into a session"
    )
    assert "houdini_render" in hits[0]


def _load_econ_reader():
    """Load the one in-repo reader that parses the stamp positionally."""
    path = REPO_ROOT / "harness" / "notes" / "econ" / "econ_call_evidence.py"
    spec = importlib.util.spec_from_file_location("_econ_call_evidence", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_econ_reader_parses_dated_and_legacy_tool_lines(tmp_path):
    """econ_call_evidence.JOURNAL_TOOL_RE is anchored on the stamp shape.

    Fails before the fix for the dated line: the old pattern is
    `^\\[\\d\\d:\\d\\d:\\d\\d\\]` and simply does not match, which would make the
    call-evidence artifact report zero production dispatches -- a wrong number
    that looks like a measurement.  Both formats must match, because existing
    logs keep the old one forever.
    """
    econ = _load_econ_reader()

    literal_match = econ.JOURNAL_TOOL_RE.match(DATED_LINE)
    assert literal_match, (
        f"econ reader rejects the required stamp format: {DATED_LINE!r}"
    )
    assert literal_match.group(1) == "houdini_create_node"

    journal = SessionJournal(str(tmp_path))
    journal.log_tool("houdini_create_node", {"type": "geo", "path": "/obj/box1"}, None)
    dated_line = _read_lines(journal)[0]

    dated_match = econ.JOURNAL_TOOL_RE.match(dated_line)
    assert dated_match, (
        f"econ reader cannot parse a current journal line: {dated_line!r} -- "
        "it would silently count zero tool records"
    )
    assert dated_match.group(1) == "houdini_create_node"

    legacy_match = econ.JOURNAL_TOOL_RE.match(LEGACY_LINE)
    assert legacy_match, (
        "econ reader must keep reading pre-fix lines; existing production "
        "journals are full of them"
    )
    assert legacy_match.group(1) == "houdini_create_node"
