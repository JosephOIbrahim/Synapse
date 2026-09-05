"""Hand-counted source fixtures; run the CLI in isolated stock Python too."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "harness/notes/panel_rhythm_census.py"
spec = importlib.util.spec_from_file_location("panel_rhythm_census", SCRIPT)
census = importlib.util.module_from_spec(spec)
spec.loader.exec_module(census)


@pytest.mark.parametrize("snippet,counter,expected", [
    ("lay.setSpacing(4)\nlay.setContentsMargins(1, 2, 3, 4)", "spacing_sites", 2),
    ('# lay.setSpacing(4)\nnote = "lay.setContentsMargins(1,2,3,4)"', "spacing_sites", 0),
    ('w.setStyleSheet("opaque")', "inline_stylesheet_sites", 1),
    ('# w.setStyleSheet("opaque")\nw.setStyleSheets("opaque")', "inline_stylesheet_sites", 0),
    ('w.setObjectName("DsFixture")\nx.setObjectName("plain")', "object_name_sites", 2),
    ('# w.setObjectName("DsFixture")\nx.objectName()', "object_name_sites", 0),
    ('w.setObjectName("DsFixture")\nx.setObjectName("DsFixture")', "ds_object_name_sites", 2),
    ('w.setObjectName("dsFixture")\nx.setObjectName(variable)', "ds_object_name_sites", 0),
    ('w.setObjectName("DsFixture")\nx.setObjectName("DsFixture")', "ds_distinct_count", 1),
    ('w.setObjectName("plain")', "ds_distinct_count", 0),
    ('lay.setSpacing(4) # rhythm-exempt: fixture reason', "exempt_tags", 1),
    ('note = "# rhythm-exempt: not a comment"\n# rhythm exempt: typo', "exempt_tags", 0),
    ('grid.setHorizontalSpacing(8)\ngrid.setVerticalSpacing(4)', "grid_spacing_sites", 2),
    ('# grid.setVerticalSpacing(4)\ngrid.setSpacing(4)', "grid_spacing_sites", 0),
])
def test_counter_positive_and_negative(snippet, counter, expected):
    assert census.scan_source(snippet)["counts"][counter] == expected


def test_hex_raw_and_distinct_positive_and_negative():
    # Construct fixture colours; never introduce a palette literal into the tree.
    colour = chr(35) + "a" * 6
    snippet = f'one = "{colour}"\ntwo = "{colour.upper()}"\n# {chr(35) + "b" * 6}'
    result = census.scan_source(snippet)
    assert result["counts"]["hex_raw_sites"] == 3
    assert result["counts"]["hex_distinct_count"] == 2
    assert [s["line"] for s in result["hex_sites"]] == [1, 2, 3]
    # Short, long, and identifier suffixes are not six-digit colour literals.
    negatives = [chr(35) + "a" * n for n in (3, 5, 7, 8)] + [colour + "xyz"]
    result = census.scan_source("\n".join(repr(s) for s in negatives))
    assert result["counts"]["hex_raw_sites"] == 0
    assert result["counts"]["hex_distinct_count"] == 0


def test_values_owners_scopes_and_same_line_exemptions():
    source = '''class Demo:
    def build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setSpacing(tokens.GAP) # rhythm-exempt: host seam
        lay.setContentsMargins(
            0, 4, 8, 12)
        w.setObjectName("DsFixture")
        w.setStyleSheet("opaque")
'''
    result = census.scan_source(source)
    spacing, margins = result["spacing"]
    assert spacing["line"] == 4
    assert spacing["scope"] == "Demo.build"
    assert spacing["receiver"] == "lay"
    assert spacing["values"] == [{"expression": "tokens.GAP"}]
    assert spacing["exempt_reason"] == "host seam"
    assert margins["values"] == [0, 4, 8, 12]
    assert margins["line"] == 5 and margins["end_line"] == 6
    assert margins["exempt_reason"] is None
    assert result["layouts"][0]["owner"] == "self"
    assert result["object_names"][0]["name"] == "DsFixture"


def test_density_blocks_selectors_and_comment_negative():
    source = '''sheet = f\"\"\"
/* #DsRoot[density="fake"] X {{ color: ignored; }} */
#DsRoot[density="airy"] A,
#DsRoot[density="airy"] B {{ margin-top: {gap}px; }}
#DsRoot[density="tight"] A {{ padding: {gap}px; }}
A {{ margin: {gap}px; }}
\"\"\"'''
    result = census.density_rules(source)
    assert result["rule_blocks"] == 2
    assert result["selectors"] == 3
    assert result["margin_rule_blocks"] == 1
    assert result["padding_rule_blocks"] == 1
    assert result["rules"][0]["line"] == 3
    assert census.density_rules('sheet = "A { margin: 4px; }"')["rule_blocks"] == 0


def test_density_repeated_selector_preserves_each_owner_line():
    result = census.density_rules('''sheet = """
#DsRoot[density="airy"] A { padding: 4px; }
#DsRoot[density="airy"] A { margin: 8px; }
"""''')
    assert [r["line"] for r in result["rules"]] == [2, 3]


def test_camera_reachability_and_missing_owner_negative():
    source = '''class SynapsePanel:
    def _build_mode_bar(self):
        w.setObjectName("DsTabRow")
        lay = QtWidgets.QHBoxLayout(w)
        lay.setSpacing(28)
        w.setStyleSheet("opaque")
'''
    report = census.camera_regions([census.scan_source(source, "python/synapse/panel/synapse_panel.py")])
    tab = report[0]
    assert tab["status"] == "VERIFIED_STATIC"
    assert all(tab["reachability"][key] is True for key in ("named", "styled_inline", "layout_owned"))
    assert report[1]["status"] == "UNKNOWN"
    missing = census.camera_regions([])[0]
    assert missing["status"] == "UNKNOWN"
    assert missing["reachability"]["layout_owned"] == "UNKNOWN"


def test_cli_stock_python_excludes_designsystem_and_never_imports_fixture(tmp_path):
    panel = tmp_path / "panel"
    (panel / "designsystem").mkdir(parents=True)
    (panel / "example.py").write_text(
        'raise RuntimeError("must never execute")\nimport nonexistent_host\n'
        'lay.setSpacing(4)\nw.setStyleSheet("opaque")\nw.setObjectName("DsFixture")\n', encoding="utf-8")
    (panel / "designsystem/tokens.py").write_text('lay.setSpacing(32)', encoding="utf-8")
    output, md = tmp_path / "out.json", tmp_path / "out.md"
    result = subprocess.run([sys.executable, "-I", "-S", str(SCRIPT), "--panel-dir", str(panel),
                             "--json", str(output), "--md", str(md)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["measurement_complete"] is True
    assert report["totals"]["files"] == 1
    assert report["totals"]["spacing_sites"] == 1
    assert report["totals"]["inline_stylesheet_sites"] == 1
    assert report["totals"]["ds_object_name_sites"] == 1
    assert report["camera_regions"][4]["status"] == "ABSENT"
    assert "example.py" in md.read_text(encoding="utf-8")


def test_missing_invalid_sources_and_cli_errors_remain_honest(tmp_path, capsys):
    assert census.census(tmp_path / "missing")["measurement_complete"] is False
    (tmp_path / "bad.py").write_text('w.setSpacing(', encoding="utf-8")
    report = census.census(tmp_path)
    assert report["measurement_complete"] is False and report["errors"]
    assert census.main(["--not-a-real-flag"]) == 0
    assert "unrecognized arguments" in capsys.readouterr().err
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    assert census.main(["--panel-dir", str(tmp_path), "--json", str(occupied),
                        "--md", str(tmp_path / "report.md")]) == 0
    assert "UNKNOWN: cannot write" in capsys.readouterr().err
