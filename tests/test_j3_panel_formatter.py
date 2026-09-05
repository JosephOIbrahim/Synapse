"""J3 (RULING_JOE_FIVE, 2026-09-05) - two speakers, two colours, at the formatter.

Joe: "The chat used to have a color for USER and a color for SYNAPSE now its
grey for both. That is confusing for the user."

The formatter is the ONE colour owner for the transcript. The speaker label
(dot AND name) and the turn's leading 2px rule both take the speaker's colour:

  USER    = SIGNAL      the accent that already means "the artist"
  SYNAPSE = CONIFEROUS  design warden's pick - 4.58:1 on GROUND (>= 4.5 AA at
                        SIZE_BODY 12 / weight 500); MUSHROOM measures 4.64:1
                        but its chroma is exactly 24, NOT > 24, so the panel's
                        own chromatic predicate (tests/panel/test_bc_wave
                        ._hue_buckets, REVIEW P1) reads it as GREY - it would
                        reproduce the complaint.

Body text stays TEXT_PRIMARY; the timestamp stays TEXT_TERTIARY. No new hex:
every colour is a ``tokens.<NAME>``. The rule keeps the existing 2px cell and
14px gap cells - no new literal.

Pure string tests: message_formatter imports no Qt and no hou, so this runs
under stock CPython. The Qt half (chat_display's label merge, the grab's hue
buckets) is tests/panel/test_j3_speakers.py under hython.

Committed RED first. Before the fix ``_speaker_label`` painted YOU's dot
CONIFEROUS and SYNAPSE's dot WARM with the NAME in TEXT_TERTIARY for both, and
``format_synapse_message`` carried no rule cell at all ("no rule, no bubble").
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from synapse.panel import message_formatter as mf
from synapse.panel.designsystem import tokens as t


def test_speaker_label_paints_dot_and_name_in_the_speaker_colour():
    # The two speaker colours are distinct palette entries with real chroma,
    # or the assertions below prove nothing.
    assert t.SIGNAL != t.CONIFEROUS
    assert t.CONIFEROUS != t.WARM

    you = mf._speaker_label("YOU", None, 1.0)
    assert t.SIGNAL in you, you
    assert t.CONIFEROUS not in you, you
    # The NAME carries the colour, not only the dot: with no timestamp there is
    # nothing left in the label that may be grey.
    assert t.TEXT_TERTIARY not in you, you

    syn = mf._speaker_label("SYNAPSE", None, 1.0)
    assert t.CONIFEROUS in syn, syn
    assert t.WARM not in syn, syn
    assert t.SIGNAL not in syn, syn
    assert t.TEXT_TERTIARY not in syn, syn

    # The timestamp is chrome and stays TEXT_TERTIARY beside a coloured name.
    stamped = mf._speaker_label("SYNAPSE", "1:00 PM", 1.0)
    assert t.CONIFEROUS in stamped and t.TEXT_TERTIARY in stamped, stamped


def test_each_turn_leads_with_a_rule_in_the_speaker_colour():
    # The user turn keeps its 2px SIGNAL cell (test_chat_panel pins the hex).
    user = mf.format_user_message("x")
    assert "background:" + t.SIGNAL in user, user
    assert "background:" + t.CONIFEROUS not in user, user

    # The SYNAPSE turn gains the same two-cell table with a CONIFEROUS rule.
    syn = mf.format_synapse_message("x")
    assert "background:" + t.CONIFEROUS in syn, syn
    assert "background:" + t.SIGNAL not in syn, syn
    assert 'width="2"' in syn and 'width="14"' in syn, syn
    # Body text never changes colour, and warm coral leaves the transcript.
    assert t.TEXT_PRIMARY in syn, syn
    assert t.WARM not in syn, syn
    # Grouped continuations carry no label and no rule (Slack anatomy holds).
    grouped = mf.format_synapse_message("x", grouped=True)
    assert "SYNAPSE" not in grouped, grouped
