"""The summary-line rule, tested against the logs it was built for.

The public verification record publishes the counts each suite run measured.
Those counts have to come from the run's OWN summary line, and the rule that
finds it has to be able to fail: a reader that picks the wrong line publishes
a wrong count, and a wrong count in a published record is the same class of
defect the release-qualification gate was rebuilt for.

The two shapes are pinned as they were measured, and the trap is pinned as a
case rather than as prose: the seat log's own summary is framed with a single
"=" on each side, and further up the same log a failure detail carries a
subprocess's summary AND the local path of the interpreter that ran it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import seat_attribution as sa  # noqa: E402
import suite_counts as sc  # noqa: E402

# The seat run's own summary, exactly as the seat log prints it.
SEAT_SUMMARY = ("= 126 failed, 12425 passed, 171 skipped, 1 deselected, 11 xfailed, "
                "259 warnings, 4 errors in 2071.00s (0:34:31) =")

# The stock run's own summary - the same rule, the other padding width.
STOCK_SUMMARY = ("=== 12240 passed, 472 skipped, 11 xfailed, 635 warnings "
                 "in 638.82s (0:10:38) ===")

# Two lines from the seat log, verbatim in shape. The first is a nested run's
# summary; the second is the failure detail that carries it, together with the
# local path of the interpreter that ran it.
NESTED_SUMMARY = ("E     ============ 7 failed, 800 passed, 10 skipped, 1 warning "
                  "in 12.89s ============")
NESTED_DETAIL = (
    "E    +  where 1 = CompletedProcess(args=['C:\\\\Program Files\\\\Side Effects "
    "Software\\\\Houdini 22.0.400\\\\bin\\\\hython.exe', '-m', 'pytest', "
    "...nvalid_node_type_raises\\n============ 7 failed, 800 passed, 10 skipped, "
    "1 warning in 12.89s ============\\n', stderr='').returncode"
)

# The log as the reader sees it: the trap is ABOVE the run's own summary.
SEAT_LOG = "\n".join([
    "ERROR tests/test_tops.py",
    NESTED_SUMMARY,
    NESTED_DETAIL,
    "__________________ test_store_address_is_redirected_into_tmp __________________",
    SEAT_SUMMARY,
    "",
])


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_the_long_summary_shape_is_found(tmp_path):
    # The padding shrinks as the summary grows, so a long summary is framed
    # "= ... =" and a reader that looks for "==" never sees it.
    line, counts = sc.suite_counts(write(tmp_path, "seat.log", SEAT_LOG))
    assert line.startswith("126 failed")
    assert counts["failed"] == 126
    assert counts["passed"] == 12425
    assert counts["skipped"] == 171
    assert counts["deselected"] == 1
    assert counts["xfailed"] == 11
    assert counts["warnings"] == 259
    assert counts["error"] == 4


def test_the_short_summary_shape_is_found(tmp_path):
    line, counts = sc.suite_counts(write(tmp_path, "stock.log", STOCK_SUMMARY + "\n"))
    assert line.startswith("12240 passed")
    assert counts["passed"] == 12240
    assert counts["skipped"] == 472
    assert counts["xfailed"] == 11


def test_a_nested_summary_inside_a_failure_detail_is_never_the_suite_summary():
    line = sc.summary_line(SEAT_LOG)
    assert line.startswith("126 failed")
    assert "800 passed" not in line


def test_the_local_path_of_the_interpreter_never_reaches_the_output(tmp_path):
    line, counts = sc.suite_counts(write(tmp_path, "seat2.log", SEAT_LOG))
    assert "hython.exe" not in line
    assert "C:" not in line
    for value in counts.values():
        assert "hython" not in str(value)


def test_errors_are_keyed_as_error_because_that_is_the_key_the_attribution_reads(tmp_path):
    # "error" must be matched before "errors", or every error count is dropped
    # and the between-tree gap changes under the published record.
    _, counts = sc.suite_counts(write(tmp_path, "seat3.log", SEAT_LOG))
    assert counts["error"] == 4
    assert "errors" not in counts
    # The attribution rule reads exactly this key, so the record agrees with it.
    assert sa.failing(counts) == 130


def test_thousands_separators_are_removed(tmp_path):
    _, counts = sc.suite_counts(write(
        tmp_path, "commas.log",
        "= 126 failed, 12,425 passed, 171 skipped in 2071.00s =\n"))
    assert counts["passed"] == 12425
    assert counts["failed"] == 126


def test_a_bare_nested_summary_earlier_in_the_log_does_not_win():
    # pytest prints the run's own summary last, so a subprocess's summary -
    # framed the same way - is excluded by position.
    text = "\n".join([
        "============ 7 failed, 800 passed, 10 skipped in 12.89s ============",
        "some other output",
        SEAT_SUMMARY,
    ])
    line = sc.summary_line(text)
    assert line.startswith("126 failed")


def test_a_log_with_no_summary_fails_closed_and_names_the_file(tmp_path):
    path = write(tmp_path, "empty.log", "nothing to see here\n")
    try:
        sc.suite_counts(path)
    except SystemExit as exc:
        assert "empty.log" in str(exc)
    else:
        raise AssertionError("a log with no summary must fail closed")


def test_a_summary_with_no_passed_count_fails_closed(tmp_path):
    path = write(tmp_path, "nopass.log", "= 3 skipped in 1.00s =\n")
    try:
        sc.suite_counts(path)
    except SystemExit as exc:
        assert "nopass.log" in str(exc)
    else:
        raise AssertionError("a summary with no passed count must fail closed")


def test_the_composer_reads_every_suite_through_this_rule():
    # If the composer grows its own reader again, this fails. The record
    # publishes five suite summaries, and all five must come from here.
    source = Path(__file__).resolve().parents[1].joinpath("compose_assets.py")
    text = source.read_text(encoding="utf-8")
    assert '"==" in candidate' not in text
    assert text.count("sc.suite_counts(") == 5
