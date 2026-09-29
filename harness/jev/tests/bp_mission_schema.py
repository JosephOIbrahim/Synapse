"""The battleplan mission_schema, loaded by path (BP12 item 11).

Six harness packages each ship a mission_schema.py and import it by the bare name, so whichever
one a process imports first wins sys.modules["mission_schema"]. In a single pytest process that
was the apexforge copy (tests/test_apex_*_wa1.py), and the jev tests validated against a schema
that is not theirs. Loading harness/battleplan/mission_schema.py by path gives them their own.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / "battleplan" / "mission_schema.py"
_NAME = "_jev_battleplan_mission_schema"

if _NAME in sys.modules:
    ms = sys.modules[_NAME]
else:
    _spec = importlib.util.spec_from_file_location(_NAME, PATH)
    ms = importlib.util.module_from_spec(_spec)
    sys.modules[_NAME] = ms
    _spec.loader.exec_module(ms)


@pytest.fixture(autouse=True)
def pin_battleplan_mission_schema(monkeypatch):
    """jev_edge.py imports mission_schema by the bare name inside a function, so the tests' own
    copy is not enough: sys.modules["mission_schema"] must be the battleplan one while a jev test
    runs. monkeypatch ends the pin with the test, so nothing leaks into tests/ in the same process.
    Imported (not defined) by each jev test module that reaches mission_schema; a conftest.py here
    would shadow tests/conftest.py, both being the bare module name "conftest"."""
    monkeypatch.setitem(sys.modules, "mission_schema", ms)
