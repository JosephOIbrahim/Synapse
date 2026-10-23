"""The seat-attribution rule, tested against the numbers it was built for.

The rule decides whether a difference between two trees' seat-suite failure
counts means anything. It has to be able to fail: a rule that always says
"the tree did it" is a rule that cannot fail, and that is the same defect the
release-qualification gate was rebuilt for. Each branch is pinned here, and
the measured case from the release host is pinned as a case, not as prose.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import seat_attribution as sa  # noqa: E402


def counts(failed, error=0):
    return {"failed": failed, "error": error, "passed": 100, "skipped": 0}


def test_the_measured_release_host_case_is_not_attributed_to_the_tree():
    # release cdcef1b2: 126 failed on a quiet box, 125 with the artist's own
    # export jobs on the same machine. master 0c5a800d: 124 on a quiet box,
    # 131 with two other suite legs sharing the host.
    r = sa.attribute(counts(126, 4), counts(124, 4), counts(125, 4), counts(131, 4))
    assert r["release_failed"] == 126
    assert r["master_failed"] == 124
    assert r["between_tree_gap"] == 2
    assert r["host_run_to_run_spread"] == 7
    assert r["trees_separated_by_the_seat_numbers"] is False


def test_the_note_says_the_numbers_do_not_separate_the_trees():
    r = sa.attribute(counts(126, 4), counts(124, 4), counts(125, 4), counts(131, 4))
    assert "do NOT separate the two trees" in r["note"]
    assert "attributable to the tree" not in r["note"]
    assert "126 failed and 4 errors" in r["note"]
    assert "124 failed and 4 errors" in r["note"]


def test_a_gap_larger_than_the_spread_is_attributed_to_the_tree():
    r = sa.attribute(counts(150, 0), counts(100, 0), counts(150, 0), counts(101, 0))
    assert r["between_tree_gap"] == 50
    assert r["host_run_to_run_spread"] == 1
    assert r["trees_separated_by_the_seat_numbers"] is True
    assert "attributable to the tree" in r["note"]


def test_a_gap_equal_to_the_spread_is_not_attributed_to_the_tree():
    # Strictly larger, or it is not separated: the host moved as much as the
    # trees did, so the difference proves nothing.
    r = sa.attribute(counts(110, 0), counts(100, 0), counts(100, 0), counts(100, 0))
    assert r["between_tree_gap"] == 10
    assert r["host_run_to_run_spread"] == 10
    assert r["trees_separated_by_the_seat_numbers"] is False


def test_errors_are_counted_alongside_failures():
    r = sa.attribute(counts(10, 3), counts(10, 3), counts(10, 3), counts(10, 3))
    assert r["release_failing"] == 13
    assert r["master_failing"] == 13
    assert r["between_tree_gap"] == 0
    assert r["host_run_to_run_spread"] == 0
    assert r["trees_separated_by_the_seat_numbers"] is False


def test_the_note_points_at_the_release_note():
    r = sa.attribute(counts(126, 4), counts(124, 4), counts(125, 4), counts(131, 4),
                     "5.97.7")
    assert "docs/releases/v5.97.7.md" in r["note"]


def test_a_missing_count_is_treated_as_zero_not_as_a_crash():
    r = sa.attribute({}, counts(5), {}, counts(5))
    assert r["release_failing"] == 0
    assert r["master_failing"] == 5
    assert r["between_tree_gap"] == 5
