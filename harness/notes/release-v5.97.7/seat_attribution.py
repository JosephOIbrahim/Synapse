"""seat_attribution - decide whether the seat numbers separate two trees.

The seat suite runs on a real host, and it is allowed to be red. It is never
called green. The control is the same seat on the published master commit.

The question this module answers is NOT "how many failures did each tree
have". It is "does the difference between the two trees mean anything". On
the release host it does not, and the reason is measurable rather than
arguable: the SAME unchanged tree does not give the same count twice. A
difference between two trees is therefore a tree difference only when it is
larger than the host's own run-to-run spread.

That spread is measured from a second run of each unchanged tree, so it is an
input and not an opinion. This module is pure arithmetic over counts: it
reads no files, starts no processes, and can be tested directly.
"""
from __future__ import annotations

DOC = "docs/releases/v%s.md"


def failing(counts: dict) -> int:
    """Failures plus errors: the two the pytest summary reports separately."""
    return int(counts.get("failed", 0)) + int(counts.get("error", 0))


def attribute(seat: dict, master: dict, seat_alt: dict, master_alt: dict,
              version: str = "") -> dict:
    """Return the attribution record for one release-vs-master seat comparison.

    seat / master         the primary pair: one run of each tree
    seat_alt / master_alt a SECOND run of the SAME unchanged tree each

    `trees_separated_by_the_seat_numbers` is True only when the between-tree
    gap is strictly larger than the host's own run-to-run spread. A gap
    exactly equal to the spread is not separated: the host moved as much as
    the trees did.
    """
    seat_failed = int(seat.get("failed", 0))
    master_failed = int(master.get("failed", 0))
    seat_errors = int(seat.get("error", 0))
    master_errors = int(master.get("error", 0))
    seat_red = seat_failed + seat_errors
    master_red = master_failed + master_errors

    release_spread = abs(seat_red - failing(seat_alt))
    master_spread = abs(master_red - failing(master_alt))
    host_spread = max(release_spread, master_spread)
    tree_gap = abs(seat_red - master_red)
    separated = tree_gap > host_spread

    where = DOC % version if version else "the release note"
    if separated:
        note = (
            "the same host on the published master commit. %d failed and %d errors on the "
            "release tree against %d failed and %d errors on master. The host's own "
            "run-to-run spread across two runs of each unchanged tree is %d, so the "
            "difference of %d is larger than it and is attributable to the tree"
            % (seat_failed, seat_errors, master_failed, master_errors, host_spread, tree_gap)
        )
    else:
        note = (
            "the same host on the published master commit. %d failed and %d errors on the "
            "release tree against %d failed and %d errors on master. The difference of %d "
            "is NOT larger than the host's own run-to-run spread - %d on the release tree "
            "and %d on master, each measured on a second run of an unchanged tree - so the "
            "seat numbers do NOT separate the two trees, and the difference is a property "
            "of the run, not of the tree. The node-level evidence is in %s"
            % (seat_failed, seat_errors, master_failed, master_errors, tree_gap,
               release_spread, master_spread, where)
        )
    return {
        "release_failed": seat_failed,
        "release_errors": seat_errors,
        "master_failed": master_failed,
        "master_errors": master_errors,
        "release_failing": seat_red,
        "master_failing": master_red,
        "release_run_to_run_spread": release_spread,
        "master_run_to_run_spread": master_spread,
        "host_run_to_run_spread": host_spread,
        "between_tree_gap": tree_gap,
        "trees_separated_by_the_seat_numbers": separated,
        "note": note,
    }
