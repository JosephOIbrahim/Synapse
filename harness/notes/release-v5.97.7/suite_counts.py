"""suite_counts - read a pytest run's OWN summary line out of its log.

WHY THIS MODULE EXISTS
----------------------

The public verification record publishes the counts each suite run measured,
and those counts have to come from the run's own summary line.

The trap: pytest frames its final summary with "=" padding, and the padding
SHRINKS as the summary grows. A short summary is framed

    == 12240 passed, 472 skipped, 11 xfailed, 635 warnings in 638.82s ===

a long one is framed

    = 126 failed, 12425 passed, 171 skipped, 1 deselected, 11 xfailed,
      259 warnings, 4 errors in 2071.00s (0:34:31) =

A reader that looks for "==" therefore finds the short summaries and MISSES
the long ones - and then finds, further up the same log, a different summary
belonging to a subprocess that a failing test ran, and publishes that one's
counts as the suite's.

The seat logs are exactly that shape. Their true summary is the "= ... =" line
above, and the line a "==" filter picks instead is a pytest failure detail
carrying a nested run's "7 failed, 800 passed" AND the local path of the
interpreter that ran it. So the record published a wrong count and a local
path, and the composer's own redaction check stopped the release over it. A
gate that stops the release is a gate that works; a gate that finds the wrong
line first is a gate that has to be fixed.

THE RULE HERE
-------------

A summary line is a line that, stripped, is framed by "=" at BOTH ends and
carries at least one count. A pytest failure detail never is: it is prefixed
with "E", "F" or "ERROR", and it is not framed.

The LAST such line in the log is the run's own summary. pytest prints its
summary last, and a subprocess's summary - which is framed the same way -
appears EARLIER, so "the last framed count line" excludes it. That is the
second half of the fix: the "==" filter did not merely prefer the wrong
shape, it also had to walk backwards past the run's own summary to find a
line at all.

A failure detail can CARRY a subprocess's summary in its own text, and that
text is where the local path of the interpreter came from. Reading a
summary out of such a line is how a path gets into a published record.

Two more details are load-bearing:

* the count alternation lists "error" BEFORE "errors", so "4 errors" is
  recorded under the key "error" - the key ``seat_attribution`` reads.
  Reversing the order silently drops every error count, changes the
  between-tree gap, and makes the record disagree with the release note;
* counts may carry thousands separators, so "12,425 passed" is 12425.
"""
from __future__ import annotations

import os
import re

# The alternation order is load-bearing: "error" must come before "errors", so
# that "4 errors" lands under the key "error" that seat_attribution reads.
COUNT_RE = re.compile(
    r"(\d[\d,]*) (passed|failed|error|errors|skipped|deselected|xfailed|xpassed"
    r"|warnings)")


def is_summary_line(line: str) -> bool:
    """True when the line is a pytest summary, not a failure detail.

    A summary is framed by "=" at both ends and carries at least one count.
    A failure detail is prefixed with "E", "F" or "ERROR" and is not framed,
    so neither shape can be mistaken for the other.
    """
    stripped = line.strip()
    if not stripped.startswith("=") or not stripped.endswith("="):
        return False
    return bool(COUNT_RE.search(stripped))


def summary_line(text: str) -> str:
    """The run's own summary line, without the "=" framing. "" if there is none."""
    for candidate in reversed(text.splitlines()):
        if is_summary_line(candidate):
            return candidate.strip().strip("= ").strip()
    return ""


def counts(line: str) -> dict:
    """The counts a summary line reports, keyed by the word that names them."""
    return {key: int(value.replace(",", ""))
            for value, key in COUNT_RE.findall(line)}


def suite_counts(path) -> tuple:
    """(summary line, counts) for the pytest run logged at ``path``.

    Fails closed: a log with no summary line, or a summary line with no
    passed count, raises rather than publishing a partial record.
    """
    name = os.path.basename(str(path))
    with open(path, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    line = summary_line(text)
    if not line:
        raise SystemExit("compose: %s has no summary line" % name)
    parsed = counts(line)
    if not parsed.get("passed"):
        raise SystemExit("compose: %s names no passed count" % name)
    return line, parsed
