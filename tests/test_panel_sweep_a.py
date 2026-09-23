"""SWEEP_A source receipts and real, isolated offscreen widget probes.

No fake Qt pass: a missing binding exits 77 and is reported as NOT_RUN.
The Qt probes exercise the production constructors and repeated state changes.
"""

import ast
from collections import Counter
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "python/synapse/panel"
BASE = "ce04dcb0"
# BP9-RETIRE (ruling 3): chat_panel.py and quick_actions.py are deleted; their
# rows left FILES / FACTORIES. The SWEEP_A qss block they selected stays (the
# sheet is append-only; test_qss_is_append_only_... still fences it).
FILES = ("face_review.py", "gate_widget.py", "context_bar.py", "face_work.py")
FACTORIES = ("face_review.FaceReview",
             "gate_widget.GateWidget", "gate_widget._ProposalCard",
             "context_bar.ContextChips", "context_bar.build_context_bar_widget",
             "face_work.FaceWork")


def _base(path):
    return subprocess.check_output(
        ["git", "show", BASE + ":" + path], cwd=ROOT).decode("utf-8")


def _calls(source):
    return [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Call)]


def _structure(source):
    """Inventory constructors, layout membership, parenting and signal wiring."""
    result = Counter()
    for call in _calls(source):
        name = ast.unparse(call.func)
        if (name.startswith(("QtWidgets.Q", "c.")) or
                name.endswith((".addWidget", ".insertWidget", ".addLayout",
                               ".addStretch", ".addSpacing", ".setParent", ".connect"))):
            result[ast.dump(call, include_attributes=False)] += 1
    return result


@pytest.mark.parametrize("filename", FILES)
def test_no_new_structure_and_every_residual_is_reasoned(filename):
    from test_panel_rhythm_owner import _scan

    path = "python/synapse/panel/" + filename
    source = (PANEL / filename).read_text(encoding="utf-8")
    if filename == "gate_widget.py":
        # bc-wave BC-6a (RULING_DIRECTION_BC.md item 2; REVIEW.md F4): the
        # proposal card was REBUILT in the panel's own vocabulary (a DsCard
        # `band`, tag badges, DsVerb verbs), so SWEEP_A's structural freeze
        # of this file ends there. What the sweep receipt still proves: the
        # card carries no inline styling (no sweep_a_style, no level hues)
        # and every spacing residual is reasoned (below).
        card = source[source.index("class _ProposalCard"):source.index("class GateWidget")]
        assert "sweep_a_style" not in card and "setStyleSheet" not in card
        assert "_LEVEL_COLORS" not in source
    elif filename == "face_work.py":
        # Approved first-session activity copy changes the existing row's text,
        # while preserving constructors, placement, and signal wiring.
        # CRIT.md 2026-09-15 #17 (P8 · Work face resting phrases) retires the
        # cookline's resting phrase. Recorded the way the merged type-ramp
        # branch recorded this same crit on master's append-only sheet guard
        # (CRIT_20260915_QSS_AMENDMENTS, which lands in this file on merge) -
        # an EXACT delta applied to the BASELINE, asserted to occur exactly once
        # there - so the structural freeze keeps full strength: face_work must
        # still equal baseline-plus-exactly-this-delta, and a stale amendment
        # reddens instead of silently no-opping.
        assert _structure(source.replace("tool_label(name)", "name")) == _structure(
            _amend(_base(path), CRIT_20260915_FACE_WORK_AMENDMENTS))
    else:
        assert _structure(source) == _structure(_base(path))
    for key, line, exempt in _scan(source, path):
        assert key[1] == "spacing" and exempt, (filename, line, key)
    assert 'setProperty("rhythm_role",' in source


def _scopes(source):
    scopes = {}

    class Visitor(ast.NodeVisitor):
        path = ()

        def visit_scope(self, node):
            previous = self.path
            self.path += (node.name,)
            if isinstance(node, ast.FunctionDef):
                scopes[self.path] = node
            self.generic_visit(node)
            self.path = previous

        visit_ClassDef = visit_FunctionDef = visit_scope

    Visitor().visit(ast.parse(source))
    return scopes


@pytest.mark.parametrize("filename", FILES)
def test_every_former_widget_layout_owner_has_a_role_in_its_own_scope(filename):
    old = _scopes(_base("python/synapse/panel/" + filename))
    new = _scopes((PANEL / filename).read_text(encoding="utf-8"))
    for scope, function in old.items():
        calls = [n for n in ast.walk(function) if isinstance(n, ast.Call)]
        changed_layouts = {ast.unparse(n.func.value) for n in calls
                           if isinstance(n.func, ast.Attribute) and n.func.attr in
                           ("setSpacing", "setContentsMargins", "setHorizontalSpacing",
                            "setVerticalSpacing")}
        for assignment in ast.walk(function):
            if not isinstance(assignment, ast.Assign):
                continue
            call = assignment.value
            if not (isinstance(call, ast.Call) and call.args and
                    ast.unparse(call.func).startswith("QtWidgets.Q") and
                    ast.unparse(call.func).endswith("Layout") and
                    ast.unparse(assignment.targets[0]) in changed_layouts):
                continue
            owner = ast.unparse(call.args[0])
            assert scope in new
            role_owners = {ast.unparse(n.func.value) for n in ast.walk(new[scope])
                           if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                           and n.func.attr == "setProperty" and n.args
                           and isinstance(n.args[0], ast.Constant)
                           and n.args[0].value == "rhythm_role"}
            assert owner in role_owners, (filename, scope, owner)




def _outside_rhythm_block(text):
    """The QSS module text with the LEVER role block (_rhythm_stylesheet) blanked.

    Landing r3 (CTO 2026-09-05, RULING-4e): that one function is the upstream
    region the landing edits under a written ruling (the dead 0.72x / 0.68x
    ratios). Everything else before the first sweep marker stays byte-identical
    to ce04dcb0, which is what "append-only" protects.
    """
    tree = ast.parse(text)
    node = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_rhythm_stylesheet")
    lines = text.splitlines()
    return "\n".join(lines[:node.lineno - 1] + lines[node.end_lineno:]).rstrip()


# bc-wave (RULING_DIRECTION_BC.md, 2026-09-05): the upstream sheet regions the
# wave edited under Joe's ruling - the same carve-out precedent as RULING-4e
# above, keyed by selector. BC-2: #DsAuthor (Addendum 2 target floor),
# #DsRailMeter retired; BC-3: the shared DsList / DsCommandResults row rule;
# BC-5: the #DsTabRow band and its density margins retired.
BC_WAVE_RULED_SELECTORS = (
    "QWidget#DsTabRow", "QPushButton#DsAuthor", "QListWidget#DsList::item",
    "QWidget#DsRailMeter",
    # 2026-09-16, CTO-ruled: the root drops its atmosphere gradient for a flat
    # PANEL fill. The gradient spanned 8 levels of 255 over 760px -- about one
    # level per 95 pixels -- and it was the one subtraction BOTH rendered
    # directions in CRIT.md agreed on, so it carries no contested design call.
    #
    # This entry is safe to make BY SELECTOR because QWidget#DsRoot names
    # exactly one rule block in the sheet. QWidget#DsHeader does NOT -- it names
    # four, including the live background/hairline rule -- which is why the
    # three dead #DsHeader margin rules were left in place rather than deleted:
    # exempting them here would have stopped guarding a rule that still ships.
    # Verify before adding any entry: the stripper removes whole rule blocks,
    # so a selector that matches more than its ruled rule silently widens the
    # hole. Measured, not assumed.
    "QWidget#DsRoot",
)


def _outside_ruled_regions(text):
    """_outside_rhythm_block, then the bc-wave ruled rule blocks and every
    comment blanked, whitespace normalised - what 'append-only' still
    protects is everything else in the upstream sheet."""
    text = _outside_rhythm_block(text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    for selector in BC_WAVE_RULED_SELECTORS:
        # The selector line (anything up to the first brace), then the
        # f-string rule body {{ ... }} through the end of its line. Built
        # from chr() so no escape sequence rides through a shell heredoc.
        nl, tab = chr(10), chr(9)
        pattern = ("^[^" + nl + "{]*" + re.escape(selector) + "[^" + nl + "]*?"
                   + re.escape("{{") + ".*?" + re.escape("}}") + "[ " + tab + "]*" + nl)
        text = re.sub(pattern, "", text, flags=re.S | re.M)
    return re.sub(r"\s+", " ", text).strip()


# The quiet local links add three rules to the upstream sheet. Match their
# entire declarations, not just a selector: changing a color, adding a
# property, or broadening a target must still fail.
#
# AMENDED BY PNL-L7 (ruling R2-B1, 2026-09-21): the two Doctor rows
#   QPushButton#DsVerb[tone="doctor"] -> HOUDINI_TAB_YELLOW / _HOVER
# left this tuple because they left the sheet. Doctor takes the shipped SIGNAL
# action family off the base #DsVerb rules instead of carrying its own yellow,
# so there is no longer a local addition here to approve. The guard does NOT
# weaken: the sheet must still equal baseline-plus-exactly-these-additions, so
# re-adding either row now reddens as unapproved drift.
_APPROVED_LOCAL_RULES = (
    '''QPushButton#DsFooterLink {{
    background: transparent; border: none; padding: 2px 0;
    min-height: {t.SPACE_LG}px;
    color: {t.TEXT_SECONDARY}; font-size: {s(t.SIZE_SMALL)}px;
    font-weight: {t.WEIGHT_REGULAR}; text-align: center;
}}''',
    'QPushButton#DsFooterLink:hover {{ color: {t.TEXT_ACCENT}; }}',
    'QPushButton#DsFooterLink:disabled {{ color: {t.TEXT_DISABLED}; }}',
)


# CRIT.md 2026-09-15 (harness/design_review/2026-09-15/CRIT.md) ranked changes
# 1, 5 and 6 edit rules inside the protected upstream sheet. They are recorded
# here as EXACT text amendments to the BASELINE, deliberately NOT as entries in
# BC_WAVE_RULED_SELECTORS: a selector carve-out retires the guard for that
# selector forever, and that list is keyed to Joe's rulings - these are crit
# changes, which are not rulings. Recorded this way the guard keeps full
# strength: the sheet must still equal baseline-plus-exactly-these-deltas,
# character for character, so any further drift on these same rules still
# reddens. Each `old` must still occur exactly once in the baseline, so a stale
# amendment reddens too instead of silently passing. Newlines are chr(10) for
# the same reason the bc-wave pattern above is: no escape sequence survives a
# shell heredoc intact.
_NL = chr(10)
CRIT_20260915_QSS_AMENDMENTS = (
    # rank 5 (one action family): DsStop rests WARM - the fill the rule's own
    # comment already claimed. HOT_SOFT retires from the action family.
    ("    background: {t.HOT_SOFT}; color: {t.TEXT_ON_ACCENT};",
     "    background: {t.WARM}; color: {t.TEXT_ON_ACCENT};"),
    # rank 5 residual (2026-09-15 crit close-out): retiring HOT_SOFT left
    # :hover painting the same WARM as rest, so hover feedback rode only on
    # :pressed. Hover steps to WARM_HOVER - the WARM ramp's own hover stop
    # (tokens.py:249), already the companion of the WARM_PRESS this rule pair
    # uses - so feedback returns WITHOUT a second hue. One family, three stops.
    ("QPushButton#DsStop:hover   {{ background: {t.WARM}; }}",
     "QPushButton#DsStop:hover   {{ background: {t.WARM_HOVER}; }}"),
    # rank 5: tone="hot" carries no hue - TEXT_PRIMARY at the verb's own weight.
    ('QPushButton#DsVerb[tone="hot"]    {{ color: {t.HOT_SOFT}; }}',
     'QPushButton#DsVerb[tone="hot"]    {{ color: {t.TEXT_PRIMARY}; }}'),
    # rank 1 (one type scale 11/12/15/19): SIZE_MICRO = 10 is deleted, so its
    # two consumers here step to SIZE_SMALL = 11 (= audit_panel.py:388
    # READABLE_FLOOR, the panel's new FONT_FLOOR_PX).
    ("    border-radius: 0px; padding: 3px 8px 3px 7px;" + _NL +
     "    font-size: {s(t.SIZE_MICRO)}px;",
     "    border-radius: 0px; padding: 3px 8px 3px 7px;" + _NL +
     "    font-size: {s(t.SIZE_SMALL)}px;"),
    ("    font-size: {s(t.SIZE_MICRO)}px; font-weight: {t.WEIGHT_SEMIBOLD};",
     "    font-size: {s(t.SIZE_SMALL)}px; font-weight: {t.WEIGHT_SEMIBOLD};"),
    # rank 6 (P8, dead code): the DsCard tone rows never painted. The only three
    # c.Card subclasses (gate_widget._ProposalCard:169, lookdev_suggestion:92,
    # recall_card:107) pass no `tone` to Card.__init__ (components.py:84-85) and
    # components.set_tone:87 has zero callers repo-wide; gate_widget.py:142 sets
    # tone on VERBS and its docstring :172 says the level is never a border hue.
    ('QWidget#DsCard[tone="warn"]  {{ border-color: {t.WARN}; }}' + _NL +
     'QWidget#DsCard[tone="approve"] {{ border-color: {t.FIRE}; }}' + _NL +
     'QWidget#DsCard[tone="critical"] {{ border-color: {t.ERROR}; }}' + _NL, ""),
)

# CRIT.md 2026-09-15 #17 (P8): the Work face cookline rests blank - "Standing
# by" one row above already says the face is idle, once. A delta, not a
# carve-out - see _amend below for what that keeps.
CRIT_20260915_FACE_WORK_AMENDMENTS = (
    ('self._cook_lbl = c.label("waiting for work", role="caption")',
     'self._cook_lbl = c.label("", role="caption")'),
)

# READABILITY.md 2026-09-15 D3b edits two more rules inside the protected
# upstream sheet, and gets its own tuple rather than rows appended to the CRIT
# one: that list is keyed to the crit, this is a readability-defect repair, and
# keeping the provenance separate is the whole reason the crit rows were not
# folded into BC_WAVE_RULED_SELECTORS either. Same mechanism, same strength -
# exact (old, new) text, each `old` asserted to occur EXACTLY ONCE in the
# baseline, so any further drift on these two rules still reddens and a stale
# amendment reddens instead of passing.
D3B_20260915_QSS_AMENDMENTS = (
    # TEXT_DISABLED is the INACTIVE-component ink: it sits below the AA floor
    # on the WCAG 2.1 SC 1.4.3 exemption, which covers inactive components and
    # nothing else. DsMeter and DsKHint at prominence=quiet are ACTIVE labels
    # borrowing that ink as a rung below tertiary - and the exemption with it.
    # They take TEXT_TERTIARY, the rung every other quiet rule already names.
    # Nothing moves on screen: since D3 both roles resolved to the same grey.
    ('QLabel#DsMeter[prominence="quiet"] {{ color: {t.TEXT_DISABLED}; }}',
     'QLabel#DsMeter[prominence="quiet"] {{ color: {t.TEXT_TERTIARY}; }}'),
    ('QLabel#DsKHint[prominence="quiet"] {{ color: {t.TEXT_DISABLED}; '
     'border-color: {t.HAIR}; }}',
     'QLabel#DsKHint[prominence="quiet"] {{ color: {t.TEXT_TERTIARY}; '
     'border-color: {t.HAIR}; }}'),
)


# PNL-L2 (harness/notes/bp9/missions_panel.json, leg PNL-L2): the SWEEP_A block
# came under ONE type scale. Its builders were invoked with no arguments, so the
# scale function s() was not in scope there and ~25 rules emitted raw
# {t.SIZE_*}px - 11-12 px beside 25-27 px chrome on the 2.25x host. The scale is
# now THREADED: stylesheet() passes it to every _sweep_a_builders entry and each
# builder binds its own floored s(). Also in this leg: the five rules spelling
# 700 as WEIGHT_SEMIBOLD + WEIGHT_MEDIUM - WEIGHT_REGULAR now name WEIGHT_BOLD,
# the five inert QSS letter-spacing declarations are deleted (Qt QSS has no
# letter-spacing property), and one /* */ comment stopped naming the bundled
# mono family - comments ship INSIDE the generated sheet, and that comment was
# the entire cause of the strict audit's 'no bundled font in QSS' failure
# (measured: qss.stylesheet(1.0).lower().find("space mono") == 10006, inside
# that comment; get_chat_display_stylesheet(1.0) is clean).
#
# Its own tuple, never rows appended to the 2026-09-15 CRIT / D3B lists: those
# are keyed to those documents and this is a different leg. It is deliberately
# NOT in _DECLARED_QSS_AMENDMENTS either - that list is applied to the ce04dcb0
# baseline, which predates the SWEEP_A block entirely (git show
# ce04dcb0:...qss.py has zero SWEEP_A markers), so these deltas have no `old` to
# match there. They are pinned against qss.py itself by the test below, at the
# same strength: each `new` exactly once, each `old` exactly once on the way
# back, through the same _amend helper.
PNL_20260921_QSS_AMENDMENTS = (
    ('   mono would request a DemiBold Space Mono does not ship (tokens.WEIGHT_BOLD',
     '   mono would request a DemiBold the bundled mono face does not ship (tokens.WEIGHT_BOLD'),
    ('        builder() for builder in _sweep_a_builders)',
     '        builder(scale) for builder in _sweep_a_builders)'),
    ('def _sweep_a_chat_panel_stylesheet():',
     'def _sweep_a_chat_panel_stylesheet(scale=t.FONT_SCALE_DEFAULT):' + _NL + '    s = lambda px: max(t.FONT_FLOOR_PX, t.scaled(px, scale))  # noqa: E731'),
    ('QTextEdit#HdaPromptInput {{  background: {t.FIELD_INSET};  color: {t.BONE};  border: 1px solid {t.GRAPHITE};  border-radius: 4px;  padding: 12px; font-size: {t.SIZE_BODY}px;  selection-background-color: {_sweep_a_legacy_argb(t.SIGNAL, "40")} ;}}',
     'QTextEdit#HdaPromptInput {{  background: {t.FIELD_INSET};  color: {t.BONE};  border: 1px solid {t.GRAPHITE};  border-radius: 4px;  padding: 12px; font-size: {s(t.SIZE_BODY)}px;  selection-background-color: {_sweep_a_legacy_argb(t.SIGNAL, "40")} ;}}'),
    ('QComboBox#HdaContextSelector {{  background: {t.CARBON};  color: {t.SILVER};  border: 1px solid {t.GRAPHITE};  border-radius: 4px;  padding: 6px 12px; font-size: {t.SIZE_LABEL}px;}}' + _NL + 'QPushButton#HdaGenerateBtn {{  background: {t.SIGNAL};  color: {t.VOID};  border: none;  border-radius: 4px;  padding: 10px 24px; font-size: {t.SIZE_LABEL}px;  font-weight: {t.WEIGHT_SEMIBOLD + t.WEIGHT_MEDIUM - t.WEIGHT_REGULAR};  letter-spacing: 1px;}}',
     'QComboBox#HdaContextSelector {{  background: {t.CARBON};  color: {t.SILVER};  border: 1px solid {t.GRAPHITE};  border-radius: 4px;  padding: 6px 12px; font-size: {s(t.SIZE_LABEL)}px;}}' + _NL + 'QPushButton#HdaGenerateBtn {{  background: {t.SIGNAL};  color: {t.VOID};  border: none;  border-radius: 4px;  padding: 10px 24px; font-size: {s(t.SIZE_LABEL)}px;  font-weight: {t.WEIGHT_BOLD};}}'),
    ('QLabel#StageLabel {{  font-size: {t.SIZE_LABEL}px;  letter-spacing: 0.5px;}}',
     'QLabel#StageLabel {{  font-size: {s(t.SIZE_LABEL)}px;}}'),
    ('QLabel#NodePathLabel {{  font-size: {t.SIZE_BODY}px;  color: {t.GROW};  padding: 8px 12px;  background: {_sweep_a_legacy_argb(t.GROW, "10")} ;  border-radius: 4px;}}' + _NL + 'QTableWidget#ParamTable {{  background: {t.CARBON};  color: {t.SILVER};  border: 1px solid {t.GRAPHITE};  gridline-color: {t.GRAPHITE}; font-size: {t.SIZE_LABEL}px;}}',
     'QLabel#NodePathLabel {{  font-size: {s(t.SIZE_BODY)}px;  color: {t.GROW};  padding: 8px 12px;  background: {_sweep_a_legacy_argb(t.GROW, "10")} ;  border-radius: 4px;}}' + _NL + 'QTableWidget#ParamTable {{  background: {t.CARBON};  color: {t.SILVER};  border: 1px solid {t.GRAPHITE};  gridline-color: {t.GRAPHITE}; font-size: {s(t.SIZE_LABEL)}px;}}'),
    ('QHeaderView::section {{  background: {t.GRAPHITE};  color: {t.BONE};  font-weight: {t.WEIGHT_SEMIBOLD + t.WEIGHT_MEDIUM - t.WEIGHT_REGULAR};  padding: 4px 8px;  border: none;}}' + _NL + 'QPushButton#ModeToggleActive {{  background: {_sweep_a_legacy_argb(t.SIGNAL, "26")} ;  border: 1px solid {_sweep_a_legacy_argb(t.SIGNAL, "66")} ;  color: {t.SIGNAL};  border-radius: 4px;  padding: 4px 12px; font-size: {t.SIZE_LABEL}px;  font-weight: {t.WEIGHT_SEMIBOLD + t.WEIGHT_MEDIUM - t.WEIGHT_REGULAR};}}' + _NL + 'QPushButton#ModeToggleInactive {{  background: transparent;  border: 1px solid {t.GRAPHITE};  color: {t.SLATE};  border-radius: 4px;  padding: 4px 12px; font-size: {t.SIZE_LABEL}px;}}',
     'QHeaderView::section {{  background: {t.GRAPHITE};  color: {t.BONE};  font-weight: {t.WEIGHT_BOLD};  padding: 4px 8px;  border: none;}}' + _NL + 'QPushButton#ModeToggleActive {{  background: {_sweep_a_legacy_argb(t.SIGNAL, "26")} ;  border: 1px solid {_sweep_a_legacy_argb(t.SIGNAL, "66")} ;  color: {t.SIGNAL};  border-radius: 4px;  padding: 4px 12px; font-size: {s(t.SIZE_LABEL)}px;  font-weight: {t.WEIGHT_BOLD};}}' + _NL + 'QPushButton#ModeToggleInactive {{  background: transparent;  border: 1px solid {t.GRAPHITE};  color: {t.SLATE};  border-radius: 4px;  padding: 4px 12px; font-size: {s(t.SIZE_LABEL)}px;}}'),
    ('QPushButton#HdaActionBtn {{  background: {t.CARBON};  color: {t.SILVER};  border: 1px solid {t.GRAPHITE};  border-radius: 4px;  padding: 8px 16px; font-size: {t.SIZE_LABEL}px;}}',
     'QPushButton#HdaActionBtn {{  background: {t.CARBON};  color: {t.SILVER};  border: 1px solid {t.GRAPHITE};  border-radius: 4px;  padding: 8px 16px; font-size: {s(t.SIZE_LABEL)}px;}}'),
    ('QPushButton#CancelBtn {{  background: transparent;  color: {t.SLATE};  border: 1px solid {t.GRAPHITE};  border-radius: 4px;  padding: 8px 16px; font-size: {t.SIZE_LABEL}px;}}',
     'QPushButton#CancelBtn {{  background: transparent;  color: {t.SLATE};  border: 1px solid {t.GRAPHITE};  border-radius: 4px;  padding: 8px 16px; font-size: {s(t.SIZE_LABEL)}px;}}'),
    ('QTextEdit {{  background: {t.VOID};  color: {t.BONE};  border: 1px solid {t.GRAPHITE};  border-radius: 6px;  padding: 8px 12px; font-size: {t.SIZE_UI}px;}}',
     'QTextEdit {{  background: {t.VOID};  color: {t.BONE};  border: 1px solid {t.GRAPHITE};  border-radius: 6px;  padding: 8px 12px; font-size: {s(t.SIZE_UI)}px;}}'),
    ('QPushButton {{  background: {t.SIGNAL};  color: {t.VOID};  border: none;  border-radius: 6px;  padding: 8px 20px; font-size: {t.SIZE_UI}px;  font-weight: {t.WEIGHT_SEMIBOLD + t.WEIGHT_MEDIUM - t.WEIGHT_REGULAR};  letter-spacing: 1px;}}',
     'QPushButton {{  background: {t.SIGNAL};  color: {t.VOID};  border: none;  border-radius: 6px;  padding: 8px 20px; font-size: {s(t.SIZE_UI)}px;  font-weight: {t.WEIGHT_BOLD};}}'),
    ('color: {color}; font-size: {t.GLYPH_MD}px; border: none;',
     'color: {color}; font-size: {s(t.GLYPH_MD)}px; border: none;'),
    ('color: {color};  font-size: {t.SIZE_SMALL}px; letter-spacing: 1px; border: none;',
     'color: {color};  font-size: {s(t.SIZE_SMALL)}px; border: none;'),
    ('QPushButton {{  background: transparent;  color: {t.FIRE};  border: 1px solid {t.FIRE};  border-radius: 3px;  padding: 4px 10px; font-size: {t.SIZE_LABEL}px;  font-weight: {t.WEIGHT_SEMIBOLD + t.WEIGHT_MEDIUM - t.WEIGHT_REGULAR};  letter-spacing: 1px;}}',
     'QPushButton {{  background: transparent;  color: {t.FIRE};  border: 1px solid {t.FIRE};  border-radius: 3px;  padding: 4px 10px; font-size: {s(t.SIZE_LABEL)}px;  font-weight: {t.WEIGHT_BOLD};}}'),
    ('QPushButton#connect_button {{  background: transparent;  color: {t.SIGNAL};  border: 1px solid {t.SIGNAL};  border-radius: 3px; font-size: {t.SIZE_SMALL}px;  padding: 4px 12px;  min-width: 100px;}}',
     'QPushButton#connect_button {{  background: transparent;  color: {t.SIGNAL};  border: 1px solid {t.SIGNAL};  border-radius: 3px; font-size: {s(t.SIZE_SMALL)}px;  padding: 4px 12px;  min-width: 100px;}}'),
    ('QPushButton#ws_path_button {{  background: transparent;  color: {t.SLATE};  border: 1px solid {t.GRAPHITE};  border-radius: 3px; font-size: {t.SIZE_LABEL}px;  padding: 4px 8px;}}',
     'QPushButton#ws_path_button {{  background: transparent;  color: {t.SLATE};  border: 1px solid {t.GRAPHITE};  border-radius: 3px; font-size: {s(t.SIZE_LABEL)}px;  padding: 4px 8px;}}'),
    ('def _sweep_a_face_review_stylesheet():',
     'def _sweep_a_face_review_stylesheet(scale=t.FONT_SCALE_DEFAULT):' + _NL + '    s = lambda px: max(t.FONT_FLOOR_PX, t.scaled(px, scale))  # noqa: E731'),
    ('color:{t.TEXT_TERTIARY}; font-size: {t.SIZE_LABEL}px;',
     'color:{t.TEXT_TERTIARY}; font-size: {s(t.SIZE_LABEL)}px;'),
    ('def _sweep_a_gate_widget_stylesheet():',
     'def _sweep_a_gate_widget_stylesheet(scale=t.FONT_SCALE_DEFAULT):' + _NL + '    s = lambda px: max(t.FONT_FLOOR_PX, t.scaled(px, scale))  # noqa: E731'),
    ('QPushButton {{  background: transparent; color: {t.SLATE}; border: none; text-align: left; min-height: {t.SPACE_LG}px; padding: {t.SPACE_XS}px {t.SPACE_SM}px;  font-size: {t.SIZE_LABEL}px; }}',
     'QPushButton {{  background: transparent; color: {t.SLATE}; border: none; text-align: left; min-height: {t.SPACE_LG}px; padding: {t.SPACE_XS}px {t.SPACE_SM}px;  font-size: {s(t.SIZE_LABEL)}px; }}'),
    ('color: {t.SILVER};  font-size: {t.SIZE_LABEL}px; border: none;',
     'color: {t.SILVER};  font-size: {s(t.SIZE_LABEL)}px; border: none;'),
    ('color: {t.SLATE};  font-size: {t.SIZE_LABEL}px; border: none;',
     'color: {t.SLATE};  font-size: {s(t.SIZE_LABEL)}px; border: none;'),
    ('color: {color};  font-size: {t.SIZE_LABEL}px; border: none;',
     'color: {color};  font-size: {s(t.SIZE_LABEL)}px; border: none;'),
    ('color: {color}; font-size: {t.GLYPH_SM}px; border: none;',
     'color: {color}; font-size: {s(t.GLYPH_SM)}px; border: none;'),
    ('def _sweep_a_context_bar_stylesheet():',
     'def _sweep_a_context_bar_stylesheet(scale=t.FONT_SCALE_DEFAULT):' + _NL + '    s = lambda px: max(t.FONT_FLOOR_PX, t.scaled(px, scale))  # noqa: E731'),
    ('color: {t.SIGNAL}; font-size: {t.SIZE_LABEL}px;  background: transparent;',
     'color: {t.SIGNAL}; font-size: {s(t.SIZE_LABEL)}px;  background: transparent;'),
    ('color: {color}; font-size: {t.SIZE_UI}px;  background: transparent; padding: 0 4px;',
     'color: {color}; font-size: {s(t.SIZE_UI)}px;  background: transparent; padding: 0 4px;'),
    ('        rules.append(_sweep_a_rule("context_health", f"""' + _NL + 'color: {color}; font-size: {t.SIZE_UI}px;  background: transparent;',
     '        rules.append(_sweep_a_rule("context_health", f"""' + _NL + 'color: {color}; font-size: {s(t.SIZE_UI)}px;  background: transparent;'),
    ('QPushButton {{  background: {t.NEAR_BLACK}; color: {t.TEXT_PRIMARY}; border: 1px solid {t.CARBON};  border-radius: 4px; padding: 2px 8px;  font-size: {t.SIZE_UI}px; }}',
     'QPushButton {{  background: {t.NEAR_BLACK}; color: {t.TEXT_PRIMARY}; border: 1px solid {t.CARBON};  border-radius: 4px; padding: 2px 8px;  font-size: {s(t.SIZE_UI)}px; }}'),
    ('color: {t.TEXT_SECONDARY}; font-size: {t.SIZE_UI}px;  background: transparent;',
     'color: {t.TEXT_SECONDARY}; font-size: {s(t.SIZE_UI)}px;  background: transparent;'),
    ('def _sweep_a_face_work_stylesheet():',
     'def _sweep_a_face_work_stylesheet(scale=t.FONT_SCALE_DEFAULT):' + _NL + '    s = lambda px: max(t.FONT_FLOOR_PX, t.scaled(px, scale))  # noqa: E731'),
    ('def _sweep_a_quick_actions_stylesheet():',
     'def _sweep_a_quick_actions_stylesheet(scale=t.FONT_SCALE_DEFAULT):' + _NL + '    s = lambda px: max(t.FONT_FLOOR_PX, t.scaled(px, scale))  # noqa: E731'),
    ('QPushButton {{  background: transparent; border: none; color: {t.TEXT_SECONDARY}; font-size: {t.GLYPH_SM}px; }}',
     'QPushButton {{  background: transparent; border: none; color: {t.TEXT_SECONDARY}; font-size: {s(t.GLYPH_SM)}px; }}'),
    ('QPushButton {{  background: {t.CARBON};  color: {t.BONE};  border: 1px solid {t.GRAPHITE};  border-radius: 14px;  padding: 7px 12px; font-size: {t.SIZE_LABEL}px;}}',
     'QPushButton {{  background: {t.CARBON};  color: {t.BONE};  border: 1px solid {t.GRAPHITE};  border-radius: 14px;  padding: 7px 12px; font-size: {s(t.SIZE_LABEL)}px;}}'),
)

# User-approved Soft Editorial (2026-09-23): neutral transcript, rounded
# composer, coral actions. Amend exact upstream rules; do not exempt whole
# selectors or re-anchor the historical baseline. Real disabled states and
# every unrelated declaration remain protected by the original comparison.
SOFT_EDITORIAL_20260923_QSS_AMENDMENTS = (
    ('QTextBrowser {{ background: {t.GROUND}; border: none; }}',
     'QTextBrowser {{ background: {t.GROUND}; border: none; }}' + _NL +
     'QTextBrowser#DsChatTranscript {{ background: {t.PANEL}; }}'),
    ('QPushButton#DsStop {{' + _NL +
     '    background: {t.WARM}; color: {t.TEXT_ON_ACCENT};' + _NL +
     '    border: none; border-radius: {t.RADIUS_SM}px;',
     'QPushButton#DsStop {{' + _NL +
     '    background: {t.WARM}; color: {t.TEXT_ON_ACCENT};' + _NL +
     '    border: none; border-radius: 12px; border-bottom-right-radius: 4px;'),
    ('QTextEdit#DsInput:focus, QLineEdit#DsField:focus {{ border-color: {t.SIGNAL}; }}',
     'QTextEdit#DsInput:focus, QLineEdit#DsField:focus {{ border-color: {t.SIGNAL}; }}' + _NL +
     'QTextEdit#DsInput[softEditorial="true"] {{' + _NL +
     '    border-color: {t.BORDER_STRONG};' + _NL +
     '    border-top-left-radius: 20px; border-top-right-radius: 20px;' + _NL +
     '    border-bottom-left-radius: 20px; border-bottom-right-radius: 6px;' + _NL +
     '}}' + _NL +
     'QTextEdit#DsInput[softEditorial="true"]:focus {{ border-color: {t.CHAT_ASSISTANT}; }}'),
    ('QPushButton#DsSend {{' + _NL +
     '    background: {t.SIGNAL_DEEP}; color: {t.TEXT_ON_ACCENT};' + _NL +
     '    border: none; border-radius: {t.RADIUS_SM}px;',
     'QPushButton#DsSend {{' + _NL +
     '    background: {t.WARM}; color: {t.TEXT_ON_ACCENT};' + _NL +
     '    border: none; border-radius: 12px; border-bottom-right-radius: 4px;'),
    ('QPushButton#DsSend:hover   {{ background: {t.SIGNAL}; }}',
     'QPushButton#DsSend:hover   {{ background: {t.WARM_HOVER}; }}'),
    ('QPushButton#DsSend:pressed {{ background: {t.SIGNAL_PRESS}; }}',
     'QPushButton#DsSend:pressed {{ background: {t.WARM_PRESS}; }}'),
)

_DECLARED_QSS_AMENDMENTS = (
    ("CRIT.md 2026-09-15", CRIT_20260915_QSS_AMENDMENTS),
    ("READABILITY.md 2026-09-15 D3b", D3B_20260915_QSS_AMENDMENTS),
    ("User-approved Soft Editorial 2026-09-23", SOFT_EDITORIAL_20260923_QSS_AMENDMENTS),
)

def _amend(original, amendments=None, label="CRIT.md 2026-09-15"):
    """The baseline with declared deltas applied, each exactly once.

    Two call shapes, both legitimate and both in use:
      _amend(text)                       -> every tuple in _DECLARED_QSS_AMENDMENTS,
                                            for the upstream QSS sheet
      _amend(text, SOME_TUPLE)           -> one named tuple, for a different baseline
                                            (face_work.py has its own, from #98)
    The one-argument form carries the label into the staleness message so a stale
    amendment says which document it came from.
    """
    if amendments is not None:
        declared = ((label, amendments),)
    else:
        declared = _DECLARED_QSS_AMENDMENTS
    for label, amendments in declared:
        for old, new in amendments:
            assert original.count(old) == 1, (
                "stale " + label + " amendment - the baseline no longer "
                "contains it exactly once: " + old
            )
            original = original.replace(old, new, 1)
    return original
def _assert_upstream_qss_unchanged(prefix, original):
    original = _amend(original)
    for rule in _APPROVED_LOCAL_RULES:
        assert prefix.count(rule) == 1, "approved local rule changed or duplicated: " + rule
        prefix = prefix.replace(rule, "", 1)
    assert _outside_ruled_regions(prefix) == _outside_ruled_regions(original)


def test_a_stale_qss_amendment_reddens_instead_of_passing():
    """The declared-delta mechanism is only honest if a delta that no longer
    matches the baseline FAILS. Proves it in both directions: an `old` that is
    absent, and an `old` that is present more than once."""
    original = _base("python/synapse/panel/designsystem/qss.py")
    saved = globals()["_DECLARED_QSS_AMENDMENTS"]
    try:
        globals()["_DECLARED_QSS_AMENDMENTS"] = (
            ("bogus", (("a rule the baseline never contained", "x"),)),)
        with pytest.raises(AssertionError, match="stale bogus amendment"):
            _amend(original)
        globals()["_DECLARED_QSS_AMENDMENTS"] = (("bogus", (("}}", "x"),)),)
        with pytest.raises(AssertionError, match="stale bogus amendment"):
            _amend(original)
    finally:
        globals()["_DECLARED_QSS_AMENDMENTS"] = saved
    # and the real list still applies cleanly
    _amend(original)


def test_qss_is_append_only_and_every_style_key_has_rules():
    from synapse.panel.designsystem import qss

    source = (PANEL / "designsystem/qss.py").read_text(encoding="utf-8")
    original = _base("python/synapse/panel/designsystem/qss.py")
    marker = "# --- SWEEP_A (chat_panel.py)"
    prefix, added = source[:source.index(marker)], source[source.index(marker):]
    _assert_upstream_qss_unchanged(prefix, original)
    # Landing r3 (CTO 2026-09-05, R2-03): SWEEP_A owns exactly its own marked
    # block; later sweeps append their own blocks after it, so the pin is
    # fence-scoped to SWEEP_A's block instead of the whole tail.
    assert added.strip().startswith("# --- SWEEP_A (chat_panel.py)")
    end = "# --- END SWEEP_A"
    assert end in added
    block_a = added[:added.index(end) + len(end)]
    assert not re.search(r"#[0-9a-fA-F]{6}(?![0-9a-zA-Z_])", block_a)
    # F-C1: families travel by QFont (fontload / rhythm), never by QSS.
    assert "font-family:" not in block_a
    sheet = qss.stylesheet()
    for filename in FILES:
        for call in _calls((PANEL / filename).read_text(encoding="utf-8")):
            if ast.unparse(call.func) == "qss.sweep_a_style":
                key = ast.literal_eval(call.args[1])
                assert '[sweep_a_style="%s"]' % key in sheet, key
    # A sweep must never mutate upstream QSS text or require its own caller.
    assert sheet.startswith(qss._sweep_a_base_stylesheet())


# AMENDED BY PNL-L7 (ruling R2-B1, 2026-09-21): rows 1 and 3 probed the two
# Doctor rules, which that ruling removed from the sheet, so their `before`
# text no longer occurs and the rows would assert on absence instead of on
# drift. Both are RE-AIMED, not dropped: same two drift shapes (a colour swap
# on a local rule, and a local selector broadened onto a shared target), now
# aimed at the surviving DsFooterLink local rules.
@pytest.mark.parametrize("before,after", [
    ("QPushButton#DsFooterLink:hover {{ color: {t.TEXT_ACCENT}; }}",
     "QPushButton#DsFooterLink:hover {{ color: {t.WARM}; }}"),
    ("    min-height: {t.SPACE_LG}px;\n    color: {t.TEXT_SECONDARY};",
     "    min-height: {t.SPACE_SM}px;\n    color: {t.TEXT_SECONDARY};"),
    ("QPushButton#DsFooterLink:disabled", "QPushButton#DsVerb:disabled"),
    ("color: {t.MUSHROOM};", "color: {t.TEXT_PRIMARY};"),
    # The approved editorial deltas remain frozen too: restoring a retired
    # color, broadening the composer selector, or dropping its geometry fails.
    ('QTextBrowser#DsChatTranscript {{ background: {t.PANEL}; }}',
     'QTextBrowser#DsChatTranscript {{ background: {t.GROUND}; }}'),
    ('QTextEdit#DsInput[softEditorial="true"] {{', 'QTextEdit#DsInput {{'),
    ('    border-bottom-left-radius: 20px; border-bottom-right-radius: 6px;',
     '    border-bottom-left-radius: 20px; border-bottom-right-radius: 20px;'),
    ('QPushButton#DsSend:hover   {{ background: {t.WARM_HOVER}; }}',
     'QPushButton#DsSend:hover   {{ background: {t.SIGNAL}; }}'),
])
def test_upstream_qss_guard_rejects_local_and_unrelated_style_drift(before, after):
    source = (PANEL / "designsystem/qss.py").read_text(encoding="utf-8")
    prefix = source[:source.index("# --- SWEEP_A (chat_panel.py)")]
    assert before in prefix
    with pytest.raises(AssertionError):
        _assert_upstream_qss_unchanged(prefix.replace(before, after, 1),
                                       _base("python/synapse/panel/designsystem/qss.py"))


def test_upstream_qss_guard_rejects_duplicate_local_rules():
    source = (PANEL / "designsystem/qss.py").read_text(encoding="utf-8")
    prefix = source[:source.index("# --- SWEEP_A (chat_panel.py)")]
    with pytest.raises(AssertionError, match="duplicated"):
        _assert_upstream_qss_unchanged(prefix + _APPROVED_LOCAL_RULES[0],
                                       _base("python/synapse/panel/designsystem/qss.py"))


def test_scoped_rules_keep_pseudo_states_on_the_target():
    from synapse.panel.designsystem import qss

    sheet = qss._sweep_a_rule(
        "probe", "QPushButton:hover {padding: 4px;} QMenu::item:selected {margin: 0;}")
    assert 'QPushButton[sweep_a_style="probe"]:hover' in sheet
    assert 'QMenu[sweep_a_style="probe"]::item:selected' in sheet
    assert 'QPushButton:hover[sweep_a_style=' not in sheet
    assert 'QPushButton:hover {' not in sheet


@pytest.mark.parametrize("suffix", ("20", "30", "CC"))
def test_legacy_argb_conversion_preserves_all_four_channels(suffix):
    from synapse.panel.designsystem import qss, tokens

    for color in (tokens.SIGNAL, tokens.GROW, tokens.ERROR):
        # Independent packed-word oracle: Qt's eight-digit order is ARGB.
        packed = int(color.lstrip("#") + suffix, 16)
        expected = ((packed >> 16) & 255, (packed >> 8) & 255,
                    packed & 255, (packed >> 24) & 255)
        output = qss._sweep_a_legacy_argb(color, suffix)
        channels = tuple(map(int, re.fullmatch(
            r"rgba\((\d+), (\d+), (\d+), (\d+)\)", output).groups()))
        assert channels == expected


def _run(factory, density, case="rhythm"):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", SYNAPSE_REDUCED_MOTION="1",
               PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [sys.executable, "-I", str(Path(__file__).resolve()), factory, density, case],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    if result.returncode == 77:
        pytest.skip(result.stdout.strip())
    assert result.returncode == 0, result.stdout + result.stderr
    payloads = [line[8:] for line in result.stdout.splitlines() if line.startswith("SWEEP_A=")]
    assert len(payloads) == 1, result.stdout + result.stderr
    return json.loads(payloads[0])


@pytest.mark.parametrize("density", ("airy", "standard", "tight"))
@pytest.mark.parametrize("factory", FACTORIES)
def test_production_layout_roles_density_sequence_and_removal(factory, density):
    result = _run(factory, density)
    assert result["layouts"] > 0
    assert result["role_removed_unchanged"] and result["sequence_restored"]


@pytest.mark.parametrize("factory", ("gate_widget.GateWidget", "gate_widget._ProposalCard",
                                     "context_bar.ContextChips", "face_work.FaceWork"))
def test_dynamic_states_still_select_paint_and_keep_controls(factory):
    assert _run(factory, "airy", "states")["states_verified"]


def _qt():
    for binding in ("PySide6", "PySide2"):
        try:
            widgets = importlib.import_module(binding + ".QtWidgets")
        except ImportError:
            continue
        assert "PySide" in widgets.QApplication.__module__, "Qt stub cannot certify layout"
        return widgets
    print("NOT_RUN: PySide6/PySide2 absent from bound Python; Qt measurement unavailable")
    raise SystemExit(77)


def _construct(widgets, factory, density):
    from synapse.panel.designsystem import qss

    module, name = factory.split(".")
    source = importlib.import_module("synapse.panel." + module)
    constructor = getattr(source, name)
    controller = None
    host = widgets.QWidget()
    host.setObjectName("DsRoot")
    host.setProperty("density", density)
    host.setStyleSheet(qss.stylesheet())
    box = widgets.QVBoxLayout(host)
    if name == "SynapseChatPanel":
        controller = constructor()
        child = controller.createInterface()  # never activate its bridge/timers
    elif name == "build_context_bar_widget":
        child = constructor(source.ContextBarState())
    elif name == "_ProposalCard":
        child = constructor({"proposal_id": "sweep-probe", "level": "approve",
                             "operation": "probe", "agent_id": "probe-agent",
                             "description": "A local display fixture"})
    else:
        child = constructor()
    box.addWidget(child)
    return host, child, controller


def _layout_sequence(widgets, host, child, density):
    from synapse.panel.designsystem import rhythm, tokens
    from synapse.panel import compositor

    compositor._repolish_tree(host)
    owners = [w for w in [child] + child.findChildren(widgets.QWidget)
              if w.property("rhythm_role") and w.layout() is not None]
    assert owners
    roles = [w.property("rhythm_role") for w in owners]
    # Independently chosen component bases, not copied from current ROLE_GAPS.
    # Shell is RULING-3's gap 16 and fixed 30/8/30/8 gutter, already present
    # in rhythm.py at the pre-first-session landing 47ffea0e.
    bases = {"group": 16, "parm_row": 4, "card": 16, "stack": 4, "band": 0, "shell": 16}
    # FaceWork / FaceReview use the existing shell gutter. Check it explicitly
    # instead of assuming every production layout is a flush interior band.
    margins = {"shell": (30, 8, 30, 8)}
    identities = [id(w) for w in owners]
    for level in (density, "tight", "airy", "standard", density):
        rhythm.apply(child, level)
        for w, role in zip(owners, roles):
            assert w.layout().spacing() == tokens.gap(bases[role], level)
            m = w.layout().contentsMargins()
            assert (m.left(), m.top(), m.right(), m.bottom()) == margins.get(role, (0, 0, 0, 0))
    assert identities == [id(w) for w in owners]
    before = [w.layout().spacing() for w in owners]
    for w in owners:
        w.setProperty("rhythm_role", None)
    rhythm.apply(child, "tight" if density != "tight" else "airy")
    assert before == [w.layout().spacing() for w in owners]
    for w, role in zip(owners, roles):
        w.setProperty("rhythm_role", role)
    return {"layouts": len(owners), "role_removed_unchanged": True,
            "sequence_restored": True}


def _states(widgets, host, child, controller, factory):
    from synapse.panel.designsystem import tokens, qss, rhythm
    from synapse.panel import compositor

    compositor._repolish_tree(host)
    rhythm.apply(host, "airy")

    def painted(widget, expected):
        widget.ensurePolished()
        assert widget.palette().color(widget.foregroundRole()).name().lower() == expected.lower()

    if factory == "gate_widget.GateWidget":
        for value, expected in ((None, tokens.SLATE), (1.0, tokens.GROW),
                                (0.1, tokens.ERROR), (None, tokens.SLATE)):
            child._render_fidelity(value)
            painted(child._fidelity_dot, expected)
        child.handle_ws_proposal({"proposal_id": "late", "level": "review"})
        card = child._cards["late"]
        # bc-wave BC-6a: the card is a `band` (bands touch); its header row
        # is the `stack` that carries the density gap.
        assert card.layout().spacing() == 0
        assert card._badge.parentWidget().layout().spacing() == tokens.gap(4, "airy")
        child.update_integrity({"operations_total": 1, "anchor_violations": 1})
        painted(child._violations_label, tokens.ERROR)
        child.update_integrity({"operations_total": 1, "anchor_violations": 0})
        painted(child._violations_label, tokens.SLATE)
    elif factory == "gate_widget._ProposalCard":
        # bc-wave BC-6a: outcomes read as tags (never a hue); the card is a
        # DsCard, no sweep_a state.
        buttons = child._approve_btn, child._reject_btn
        child.mark_gate_unreachable()
        assert child.isEnabled() and all(not b.isHidden() for b in buttons)
        assert child._decision_tag.text() == "NOT RECORDED"
        assert child._decision_tag.property("status") == "BLOCKED"
        child.mark_decided("approved")
        assert child._decision_tag.text() == "APPROVED"
        assert child._decision_tag.property("status") == ""
        assert all(b.isHidden() for b in buttons)
        assert not child.isEnabled()
        assert child.objectName() == "DsCard"
    elif factory == "context_bar.ContextChips":
        from synapse.panel.context_bar import ContextBarState, update_context_bar_widget

        for stage, expected in (("structured", tokens.SIGNAL), ("composed", tokens.GROW),
                                ("flat", tokens.TEXT_SECONDARY)):
            update_context_bar_widget(child._inner, ContextBarState(memory_stage=stage))
            painted(child._inner.findChild(widgets.QLabel, "ctx_memory"), expected)
    elif factory == "face_work.FaceWork":
        for phase, expected in (("running", tokens.SIGNAL), ("done", tokens.GROW),
                                ("error", tokens.ERROR)):
            child.set_tool_status("probe", phase)
            assert child._plan_box.count() == 1
            painted(child._plan_box.itemAt(0).widget(), expected)
        child.reset()
        painted(child._plan_box.itemAt(0).widget(), tokens.TEXT_TERTIARY)
    elif factory == "chat_panel.SynapseChatPanel":
        for connected, expected in ((True, tokens.GROW), (False, tokens.ERROR), (True, tokens.GROW)):
            controller._on_status_changed(connected)
            painted(controller._conn_dot, expected)
            painted(controller._conn_label, expected)
        for mode in ("hda", "chat", "hda", "chat"):
            controller._set_mode(mode)
            assert controller._mode_stack.currentIndex() == (mode == "hda")
    else:
        original = list(child._pills)
        for expanded in (False, True, False, True):
            child.set_expanded(expanded)
            assert child._pills_container.isHidden() != expanded
            assert original == child._pills
    return {"states_verified": True}


if __name__ == "__main__":
    assert os.environ["QT_QPA_PLATFORM"] == "offscreen"
    assert os.environ["SYNAPSE_REDUCED_MOTION"] == "1"
    sys.path.insert(0, str(ROOT / "python"))
    qt = _qt()
    app = qt.QApplication.instance() or qt.QApplication([])
    factory, density, case = sys.argv[1:]
    host, child, controller = _construct(qt, factory, density)
    try:
        result = (_layout_sequence(qt, host, child, density) if case == "rhythm"
                  else _states(qt, host, child, controller, factory))
        print("SWEEP_A=" + json.dumps(result, sort_keys=True))
    finally:
        if controller is not None:
            controller.onDestroyInterface()
        host.close()


def test_pnl_l2_sweep_a_is_one_scale_and_the_delta_is_exactly_declared():
    """PNL-L2's whole delta is the declared tuple - no more, no less.

    Round-trips through _amend in both directions: reverting requires every
    `new` to occur exactly once in the shipped file, and re-applying requires
    every `old` to occur exactly once in the reverted text. A stale pair or an
    undeclared edit reddens instead of passing.
    """
    source = (PANEL / "designsystem/qss.py").read_text(encoding="utf-8")
    reverted = _amend(
        source,
        tuple((new, old) for old, new in PNL_20260921_QSS_AMENDMENTS),
        label="PNL-L2 (reverse)")
    assert reverted != source
    assert _amend(reverted, PNL_20260921_QSS_AMENDMENTS,
                  label="PNL-L2") == source
    for old, _new in PNL_20260921_QSS_AMENDMENTS:
        assert old not in source, "undone PNL-L2 amendment: " + old


def test_sweep_a_block_carries_no_unscaled_size_and_no_inert_letter_spacing():
    """The invariant PNL-L2 lands, stated independently of the delta above."""
    source = (PANEL / "designsystem/qss.py").read_text(encoding="utf-8")
    block = source[source.index("def _sweep_a_chat_panel_stylesheet"):
                   source.index("# --- END SWEEP_A")]
    assert not re.search(r"\{t\.(SIZE|GLYPH)_[A-Z_]+\}px", block)
    assert "letter-spacing" not in block
    assert "WEIGHT_SEMIBOLD + t.WEIGHT_MEDIUM" not in block
    # every builder takes the scale; none closes over a module-level one
    for match in re.finditer(r"^def (_sweep_a_\w*_stylesheet)\(([^)]*)\)",
                             block, re.M):
        assert "scale" in match.group(2), match.group(1)


def test_sweep_a_rules_actually_move_with_the_user_font_scale():
    from synapse.panel.designsystem import qss

    key = '[sweep_a_style="chat_hda"]'
    one = qss.stylesheet(1.0)
    big = qss.stylesheet(2.25)
    assert one[one.index(key):] != big[big.index(key):]
    assert "font-size: 27px" in big[big.index(key):]


def test_generated_sheet_names_no_bundled_font_family():
    """audit_panel.py's 'no bundled font in QSS' row, pinned in the suite.

    Comments ship inside the generated string, so a comment naming the family
    fails this for the same reason a real font-family rule would.
    """
    from synapse.panel.designsystem import qss

    text = qss.stylesheet(1.0).lower()
    assert "space mono" not in text and "space grotesk" not in text
