"""Hour3 design M3 (2026-10-06): the stylesheet is composed in one place.

Before: nine ``def stylesheet`` in qss.py, eight of them wrapping the previous
binding through ``_X_base_stylesheet = stylesheet`` aliases, so the section
order lived only in file position. After: the core sheet at the top of the
module (unchanged - it sits in the append-only prefix that
test_panel_sweep_a.py:530-555 guards, so it keeps its name) plus ONE composer
at the bottom that walks an ordered ``_SECTIONS`` tuple.

Not 9 -> 1: renaming the core def would move that guarded prefix, which is an
existing pin. Two defs, one alias (``_sweep_a_base_stylesheet``, which test
:555 reads) is the floor without moving it.

The composed string is byte-identical to b4a5fe3a at six scales (goldens from
design_proof/base_a.log).
"""
import ast
import hashlib
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_QSS = os.path.join(_ROOT, "python", "synapse", "panel", "designsystem", "qss.py")
GOLDEN = {
    1.0: "db6564a64232ba86f4ed2b63953dfdc81d90ce1ccbd04357d42cd07a71ba6d3b",
    1.15: "9b293ba872a7a0767b21a3a9fd33a52e897c6c1db03e5d8316336963a6323c75",
    1.25: "5fd2ccca8e8a8ca6a6af9a4c9ce6a406934dfc09745ceed942397d21e4ce1d7e",
    1.4: "29f82763390ae7cdd685f2b8ac9ff6f8fc89ba28ec14e592a99896b94b9383ef",
    1.6: "98cc871515c9e3a9dcc856ea997ced5984cd81c54a5873358ff6585472c3bf5d",
    2.25: "dc014c5cb813a8e06790a94a86edef90d1c427851ed02d2ed773dafe8b275dae",
}


def _tree():
    return ast.parse(open(_QSS, encoding="utf-8").read())


@pytest.mark.parametrize("scale", sorted(GOLDEN))
def test_composer_output_is_byte_identical_to_the_chain_it_replaced(scale):
    from synapse.panel.designsystem import qss
    assert hashlib.sha256(qss.stylesheet(scale).encode("utf-8")).hexdigest() == GOLDEN[scale]


def test_two_stylesheet_defs_and_one_alias_remain():
    tree = _tree()
    defs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "stylesheet"]
    assert len(defs) == 2, [d.lineno for d in defs]
    aliases = [n for n in tree.body if isinstance(n, ast.Assign)
               and isinstance(n.value, ast.Name) and n.value.id == "stylesheet"]
    assert [a.targets[0].id for a in aliases] == ["_sweep_a_base_stylesheet"]
    # the composer follows every section it names (it sits inside the last
    # panel fence; submenu_stylesheet must stay the module's final statement)
    picker = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == "_model_picker_section")
    assert defs[-1].lineno > picker.lineno


def test_sections_are_ordered_in_one_tuple_and_all_resolve():
    from synapse.panel.designsystem import qss
    assert [sep for sep, _ in qss._SECTIONS] == ["\n", "", "\n", "\n", "", "", "", ""]
    assert all(callable(build) for _, build in qss._SECTIONS)
    sheet = qss.stylesheet(1.0)
    core = qss._sweep_a_base_stylesheet(1.0)
    assert sheet.startswith(core)
    assert sheet == core + "".join(sep + build(1.0) for sep, build in qss._SECTIONS)
