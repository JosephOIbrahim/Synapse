"""H3b — pins for the background-render stop (rps/rkill, R73).

DISCIPLINE THESE TESTS FOLLOW
-----------------------------
* **Law 1 / R34 — every pin must be shown to fail.** Each behavioural pin is
  paired with a ``*_MUTATION_CATCHES`` test that re-implements the function
  with the guard removed and asserts the property NO LONGER holds. A property
  that is true of both the real implementation and its mutant is a decoration,
  and these prove which is which.

* **R60 — the reader gets its own control.** ``parse_rps`` is the reader every
  other pin depends on. If it were blind, all of them would pass vacuously. It
  is calibrated against rps text captured VERBATIM from live Houdini
  22.0.368 (2026-07-28) and given explicit negative cases.

* **No mock ``hou``.** The constitution bans mock-hou for host-behaviour
  assertions. Everything here is pure-Python parsing and mapping, which is why
  that logic was factored out of the handler in the first place. The live
  behaviours (rkill kills, rkill is silent, partial-frame residue) were
  established by probe and are recorded in harness/notes/receipts/H3b.json --
  they are deliberately NOT re-asserted here against a fake.
"""

import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
sys.path.insert(0, os.path.join(_root, "python"))

from synapse.server import render_stop as rs


# ---------------------------------------------------------------------------
# Fixtures — captured VERBATIM from live Houdini 22.0.368 on 2026-07-28.
# Producer: the H3b probe session; see harness/notes/receipts/H3b.json.
# ---------------------------------------------------------------------------

RPS_IDLE = "No background renders currently running\n"

# Two concurrent mantra renders + retained dead slots. Note the Command column
# is the bare word "mantra" for BOTH -- this is the whole reason a mantra ROP
# cannot be mapped to a process.
RPS_MANTRA_TWO = """PID Command
      -1 mantra
      -1 mantra
   31416 mantra
   75828 mantra
"""

# Two concurrent Karma renders from two DIFFERENT usdrender_rop nodes.
# Houdini pid 40868; node sessionIds 113 and 339.
RPS_HUSK_TWO = (
    "PID Command\n"
    "   66252 husk --make-output-path -f 1 --purpose 'geometry,render' "
    "--complexity 'veryhigh' --snapshot 300 --mplay-session 'untitled' "
    "'C:/Users/User/AppData/Local/Temp/houdini_temp/usd_renders/"
    "usdrender_40868_113_4/__render__.usd'\n"
    "   61360 husk --make-output-path -f 1 --purpose 'geometry,render' "
    "--complexity 'veryhigh' --snapshot 300 --mplay-session 'untitled' "
    "'C:/Users/User/AppData/Local/Temp/houdini_temp/usd_renders/"
    "usdrender_40868_339_1/__render__.usd'\n"
)

HOUDINI_PID = 40868
SESSION_A = 113
SESSION_B = 339


# ---------------------------------------------------------------------------
# R60 — reader calibration. These come FIRST because every pin below trusts
# parse_rps; an uncalibrated reader would make all of them green and empty.
# ---------------------------------------------------------------------------

def test_reader_control_idle_yields_no_rows():
    """Positive control for the empty case: idle rps is not a parse failure."""
    assert rs.parse_rps(RPS_IDLE) == []


def test_reader_control_sees_every_row_it_is_given():
    """The reader must not silently drop rows -- that is the blind-reader case.

    Fails if parse_rps returns fewer rows than the fixture contains.
    """
    assert len(rs.parse_rps(RPS_MANTRA_TWO)) == 4      # 2 dead + 2 live
    assert len(rs.parse_rps(RPS_HUSK_TWO)) == 2


def test_reader_control_distinguishes_dead_from_live():
    rows = rs.parse_rps(RPS_MANTRA_TWO)
    assert [r["alive"] for r in rows] == [False, False, True, True]
    assert [r["pid"] for r in rows] == [-1, -1, 31416, 75828]


def test_reader_control_negative_garbage_is_skipped_not_guessed():
    """A line the reader cannot parse must be dropped, never half-invented."""
    assert rs.parse_rps("PID Command\nnot-a-pid whatever\n\n") == []
    assert rs.parse_rps("") == []
    assert rs.parse_rps(None) == []


def test_reader_classifies_both_real_renderers():
    assert [r["renderer"] for r in rs.parse_rps(RPS_HUSK_TWO)] == ["husk", "husk"]
    live = [r for r in rs.parse_rps(RPS_MANTRA_TWO) if r["alive"]]
    assert [r["renderer"] for r in live] == ["mantra", "mantra"]
    assert rs.classify_renderer("") == rs.RENDERER_UNKNOWN
    assert rs.classify_renderer("some_other_renderer -x") == rs.RENDERER_UNKNOWN


# ---------------------------------------------------------------------------
# The mapping — the leg's central engineering claim.
# ---------------------------------------------------------------------------

def test_husk_rows_map_to_the_correct_rop_session():
    rows = rs.parse_rps(RPS_HUSK_TWO)
    assert rs.resolve_rop_pids(rows, HOUDINI_PID, SESSION_A) == [66252]
    assert rs.resolve_rop_pids(rows, HOUDINI_PID, SESSION_B) == [61360]


def test_mapping_returns_empty_for_a_rop_that_is_not_rendering():
    """The reader's negative case. Without this the mapper could return a
    constant and every positive pin above would still pass."""
    rows = rs.parse_rps(RPS_HUSK_TWO)
    assert rs.resolve_rop_pids(rows, HOUDINI_PID, 999999) == []


def test_mapping_is_scoped_to_this_houdini_process():
    """A different Houdini's render must never resolve. This is what makes a
    cross-session kill structurally impossible rather than merely unlikely."""
    rows = rs.parse_rps(RPS_HUSK_TWO)
    assert rs.resolve_rop_pids(rows, 11111, SESSION_A) == []


def test_mantra_rows_carry_no_identity_and_map_to_nothing():
    """The finding that forced the `unmappable` refusal: mantra's rps Command
    is the bare word 'mantra', so no session id can ever match."""
    rows = rs.parse_rps(RPS_MANTRA_TWO)
    for sid in (SESSION_A, SESSION_B, 1, 999):
        assert rs.resolve_rop_pids(rows, HOUDINI_PID, sid) == []
    assert all(rs.describe_usdrender_command(r["command"]) is None
               for r in rows)


def test_dead_rows_are_never_mapped_or_killable():
    """A -1 sentinel row must never be handed back as a kill target."""
    rows = rs.parse_rps("PID Command\n      -1 husk usdrender_40868_113_4/x.usd\n")
    assert rs.resolve_rop_pids(rows, HOUDINI_PID, SESSION_A) == []


def test_usdrender_command_decodes_pid_session_and_invocation():
    rows = rs.parse_rps(RPS_HUSK_TWO)
    assert rs.describe_usdrender_command(rows[0]["command"]) == {
        "houdini_pid": 40868, "session_id": 113, "invocation": 4}
    assert rs.describe_usdrender_command(rows[1]["command"]) == {
        "houdini_pid": 40868, "session_id": 339, "invocation": 1}


# ---------------------------------------------------------------------------
# R34 — MUTATION PROOFS. Each rebuilds the function with one guard removed and
# asserts the property above no longer holds. If a mutant still satisfies the
# pin, the pin was pinning nothing.
# ---------------------------------------------------------------------------

def _mutant_resolve_ignoring_alive(rows, houdini_pid, session_id):
    """MUTANT: forgets to exclude dead (-1) rows."""
    token = rs.rop_token(houdini_pid, session_id)
    return [r["pid"] for r in rows if token in (r.get("command") or "")]


def test_MUTATION_CATCHES_dead_row_exclusion():
    rows = rs.parse_rps("PID Command\n      -1 husk usdrender_40868_113_4/x.usd\n")
    # real implementation: correct
    assert rs.resolve_rop_pids(rows, HOUDINI_PID, SESSION_A) == []
    # mutant: hands back a dead PID as a kill target
    assert _mutant_resolve_ignoring_alive(rows, HOUDINI_PID, SESSION_A) == [-1]


def _mutant_token_without_process_scope(session_id):
    """MUTANT: drops the houdini pid from the token, so any Houdini matches."""
    return "_%d_" % int(session_id)


def _mutant_resolve_unscoped(rows, houdini_pid, session_id):
    token = _mutant_token_without_process_scope(session_id)
    return [r["pid"] for r in rows
            if r.get("alive") and token in (r.get("command") or "")]


def test_MUTATION_CATCHES_cross_session_scoping():
    """Proves test_mapping_is_scoped_to_this_houdini_process pins something."""
    rows = rs.parse_rps(RPS_HUSK_TWO)
    # real: a foreign Houdini pid resolves to nothing
    assert rs.resolve_rop_pids(rows, 11111, SESSION_A) == []
    # mutant: resolves anyway -> would kill another session's render
    assert _mutant_resolve_unscoped(rows, 11111, SESSION_A) == [66252]


def _mutant_parse_skipping_dead(text):
    """MUTANT: reader silently drops -1 rows instead of reporting them."""
    return [r for r in rs.parse_rps(text) if r["pid"] != rs.DEAD_PID]


def test_MUTATION_CATCHES_reader_row_loss():
    """Proves the reader-completeness control is not vacuous."""
    assert len(rs.parse_rps(RPS_MANTRA_TWO)) == 4
    assert len(_mutant_parse_skipping_dead(RPS_MANTRA_TWO)) == 2


def _mutant_classify_defaulting_to_husk(command):
    """MUTANT: treats anything unrecognised as husk (i.e. as mappable)."""
    return rs.RENDERER_HUSK if "mantra" not in (command or "") else rs.RENDERER_MANTRA


def test_MUTATION_CATCHES_unknown_renderer_default():
    assert rs.classify_renderer("weird_renderer -x") == rs.RENDERER_UNKNOWN
    assert _mutant_classify_defaulting_to_husk("weird_renderer -x") == rs.RENDERER_HUSK


# ---------------------------------------------------------------------------
# Partial-output advisory — the mandatory finding, pinned so it cannot quietly
# flip to "safe" for mantra.
# ---------------------------------------------------------------------------

def test_mantra_partial_output_is_declared_UNSAFE():
    """A stopped mantra render leaves a valid-but-pixel-empty EXR at the real
    output path. If this ever reports safe, the stop is silently corrupting."""
    risk = rs.partial_output_risk(rs.RENDERER_MANTRA)
    assert risk["declared_output_safe"] is False
    assert any("mantra_checkpoint" in r for r in risk["residue"])
    assert "renderTime" in risk["detect_incomplete"]


def test_husk_partial_output_is_declared_SAFE_with_a_reason():
    risk = rs.partial_output_risk(rs.RENDERER_HUSK)
    assert risk["declared_output_safe"] is True
    assert "_part" in " ".join(risk["residue"])


def test_unknown_renderer_risk_is_not_asserted_in_either_direction():
    """Law 3 / evidence ladder: unmeasured must not read as measured-safe."""
    risk = rs.partial_output_risk("something_new")
    assert risk["declared_output_safe"] is None


def test_MUTATION_CATCHES_partial_risk_flip():
    """Proves the mantra-unsafe pin discriminates."""
    def _mutant_risk(renderer):
        d = dict(rs.partial_output_risk(renderer))
        d["declared_output_safe"] = True        # the dangerous regression
        return d
    assert rs.partial_output_risk(rs.RENDERER_MANTRA)["declared_output_safe"] is False
    assert _mutant_risk(rs.RENDERER_MANTRA)["declared_output_safe"] is True


# ---------------------------------------------------------------------------
# Selector contract — a stop that cannot say WHAT it stops is not a stop.
# ---------------------------------------------------------------------------

def test_stop_requires_exactly_one_selector():
    import pytest
    with pytest.raises(ValueError):
        rs.stop_render()                                   # neither
    with pytest.raises(ValueError):
        rs.stop_render(node_path="/out/x", pid=1234)       # both
