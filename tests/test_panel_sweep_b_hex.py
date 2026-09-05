"""Audit removed color sites against Git, rather than trusting the mapping table."""

from collections import Counter
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE = "ce04dcb0"
PANEL = "python/synapse/panel/"
MIGRATED = (
    "hda_views", "tool_palette", "command_palette", "working_indicator",
    "vex_tutor", "apex_trace", "apex_explainer", "scene_doctor",
    "performance_profiler", "network_trace", "cross_scene", "message_formatter",
    # landing r3 (RULING-1d): the side modules
    "bookmarks", "dependency_map", "apex_recipes", "save_shot", "session_integrity",
    "recipe_book", "error_translator", "session_journal", "styles",
)
HEX = re.compile(r"(?<!&)#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-zA-Z_])")
TABLE = ROOT / "docs/panel_pd/HEX_MAPPING_SWEEP_B.md"


def _base(path):
    return subprocess.check_output(
        ["git", "show", BASE + ":" + path], cwd=ROOT,
        text=True, encoding="utf-8")


def _rows(text):
    rows = []
    for line in text.splitlines():
        if not line.startswith("| `python/"):
            continue
        fields = [field.strip().strip("`") for field in line.strip("|").split("|")]
        assert len(fields) == 5, line
        path, number, color, token, rationale = fields
        assert HEX.fullmatch(color) and rationale and token.isidentifier(), line
        rows.append((path, int(number), color, token, rationale))
    assert rows, "mapping table is empty"
    return rows


def test_every_removed_hex_has_an_exact_mapping_site():
    expected = Counter()
    for name in MIGRATED:
        path = PANEL + name + ".py"
        for number, line in enumerate(_base(path).splitlines(), 1):
            expected.update((path, number, match[0]) for match in HEX.finditer(line))
    actual = Counter(row[:3] for row in _rows(TABLE.read_text(encoding="utf-8")))
    assert actual == expected, {"unmapped": expected - actual, "invented": actual - expected}


@pytest.mark.parametrize("name", MIGRATED)
def test_migrated_source_has_no_remaining_hex(name):
    source = (ROOT / (PANEL + name + ".py")).read_text(encoding="utf-8")
    assert not HEX.findall(source), name


def test_mapping_targets_exist_in_unchanged_vendored_tokens():
    # Compile the source inventory without importing the host theme seam.
    import ast
    path = PANEL + "designsystem/tokens.py"
    before = _base(path)
    assert (ROOT / path).read_text(encoding="utf-8") == before, "a token was added or changed"
    assignments = {
        target.id
        for node in ast.walk(ast.parse(before)) if isinstance(node, ast.Assign)
        for target in node.targets if isinstance(target, ast.Name)
    }
    assert {row[3] for row in _rows(TABLE.read_text(encoding="utf-8"))} <= assignments


def test_mapping_parser_does_not_accept_an_empty_table():
    with pytest.raises(AssertionError, match="empty"):
        _rows("| file | line | hex | token | role rationale |")


def test_shorthand_scan_preserves_numeric_html_entities():
    assert not HEX.search("&#160;&#183;&#160;")
    assert HEX.fullmatch("#" + "abc")


def test_html_token_substitutions_are_interpolated():
    import ast
    for name in MIGRATED:
        source = (ROOT / (PANEL + name + ".py")).read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not re.search(r"\{_(?:ds|t)\.[A-Z]", node.value), (name, node.lineno)


def test_existing_message_output_remains_byte_identical():
    # This module was already tokenized. Removing dead fallbacks/documentation
    # literals must not change the speaker, grouping or escaping behavior.
    path = PANEL + "message_formatter.py"
    inherited, migrated = {}, {}
    exec(compile(_base(path), "inherited_message_formatter", "exec"), inherited)
    exec(compile((ROOT / path).read_text(encoding="utf-8"), path, "exec"), migrated)
    for name in ("format_user_message", "format_synapse_message"):
        for grouped in (False, True, False):
            args = ("<b>hello</b>\nA node: /obj/geo1",)
            kwargs = dict(grouped=grouped, timestamp="12:34", font_scale=1.0)
            assert migrated[name](*args, **kwargs) == inherited[name](*args, **kwargs)


def test_protected_source_is_unchanged():
    # Landing r3 (CTO 2026-09-05, R2-03): fontload.py and the shelf launcher stay
    # frozen against the master merge-base (master never touched them). The
    # CAMERA files synapse_panel.py / face_token.py are edited by the landing
    # under written rulings, so the SWEEP_B guarantee is stated as what it is:
    # SWEEP_B's own commit did not touch them.
    merge_base = subprocess.check_output(
        ["git", "merge-base", "master", "HEAD"], cwd=ROOT, text=True).strip()
    for path in (PANEL + "designsystem/fontload.py", "houdini/scripts/python/synapse_shelf.py"):
        frozen = subprocess.check_output(["git", "show", merge_base + ":" + path],
                                         cwd=ROOT, text=True, encoding="utf-8")
        assert (ROOT / path).read_text(encoding="utf-8") == frozen, path
    sweep_b = "ae046513"
    assert subprocess.check_output(
        ["git", "diff", sweep_b + "~1", sweep_b, "--", PANEL + "synapse_panel.py",
         PANEL + "face_token.py"], cwd=ROOT) == b"", "SWEEP_B touched a CAMERA file"
