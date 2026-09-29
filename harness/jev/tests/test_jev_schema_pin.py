"""BP12 item 11: jev tests validate against harness/battleplan/mission_schema.py, whatever else
a shared pytest process imported first (the apexforge tests cache a different mission_schema)."""
from pathlib import Path

from bp_mission_schema import PATH, ms, pin_battleplan_mission_schema  # noqa: F401


def test_a_bare_import_resolves_to_the_battleplan_copy_inside_a_jev_test():
    import mission_schema

    assert mission_schema is ms
    assert Path(PATH).parent.name == "battleplan"


def test_the_pinned_schema_accepts_a_repair_mission_and_rejects_junk():
    assert ms.validate_mission({"nope": 1}) != []
