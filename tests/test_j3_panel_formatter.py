"""Two distinct voices at the formatter, amended by Soft Editorial 2026-09-23.

The user's approved panel assigns sea-green to YOU and coral to SYNAPSE.
The assistant carries a hollow-circle mark and an open body; only YOU keeps
a colored leading rule. This supersedes J3's blue/green assignment without
losing its protection against both speaker labels becoming grey.

Prose stays neutral, metadata stays quiet, and continuations do not repeat
speaker labels. The formatter remains Qt/hou-free; real document checks live
in tests/panel/test_j3_speakers.py.
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


def test_speaker_label_and_hollow_mark_use_the_approved_identity_colours():
    # The two speaker colours are distinct palette entries with real chroma,
    # or the assertions below prove nothing.
    assert len({t.CHAT_USER, t.CHAT_ASSISTANT, t.MODEL_ACCENT}) == 3

    you = mf._speaker_label("YOU", None, 1.0)
    assert t.CHAT_USER in you, you
    assert t.CHAT_ASSISTANT not in you, you
    assert t.MODEL_ACCENT not in you, you
    # The NAME carries the colour, not only the dot: with no timestamp there is
    # nothing left in the label that may be grey.
    assert t.TEXT_TERTIARY not in you, you

    syn = mf._speaker_label("SYNAPSE", None, 1.0)
    assert t.CHAT_ASSISTANT in syn, syn
    assert t.CHAT_USER not in syn, syn
    assert t.MODEL_ACCENT not in syn, syn
    # The native display supplies a ring image: Space Grotesk does not have
    # the hollow-circle glyph, so depending on U+25CB loses the mark entirely.
    assert 'src="synapse:assistant-ring"' in syn, syn
    assert "&#9679;" not in syn and "●" not in syn, syn
    assert t.TEXT_TERTIARY not in syn, syn

    # The timestamp is chrome and stays TEXT_TERTIARY beside a coloured name.
    stamped = mf._speaker_label("SYNAPSE", "1:00 PM", 1.0)
    assert t.CHAT_ASSISTANT in stamped and t.TEXT_TERTIARY in stamped, stamped


def test_user_keeps_a_rule_and_assistant_body_stays_open():
    # The user retains a colored hairline; the assistant's rule is transparent.
    user = mf.format_user_message("x")
    assert "background:" + t.CHAT_USER in user, user
    assert "background:" + t.CHAT_ASSISTANT not in user, user

    # Keep the shared table measure without painting an assistant hairline.
    syn = mf.format_synapse_message("x")
    assert "background:transparent" in syn, syn
    assert "background:" + t.CHAT_ASSISTANT not in syn, syn
    assert "background:" + t.CHAT_USER not in syn, syn
    assert 'width="2"' in syn and 'width="14"' in syn, syn
    # Coral identifies the speaker, while body text remains neutral.
    assert t.TEXT_PRIMARY in syn, syn
    assert t.CHAT_ASSISTANT in syn, syn
    # Grouped continuations carry no label and no rule (Slack anatomy holds).
    grouped = mf.format_synapse_message("x", grouped=True)
    assert "SYNAPSE" not in grouped, grouped
