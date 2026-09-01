# tests/test_drift.py - BP2-METER T3. Pins harness/battleplan/drift.py.
#
# acceptance #6: on a synthetic bus, one drifting leg -> a `refocus` is posted
# with its mission targets VERBATIM; two refocus with the leg still drifting ->
# a `halt` is posted. Plus: an on-target leg is left alone, a halt is never
# repeated, and drift writes nothing but bus posts (zero model calls, no manifest
# edits). Pure Python, stock pytest. The bus is redirected to a tmp dir so no
# post ever touches a live wave.
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "harness" / "battleplan"))

import bus     # noqa: E402
import drift   # noqa: E402

OFF = ["wandering into unrelated design", "chasing a side quest",
       "refactoring something else", "exploring memory latency",
       "polishing an off-scope panel", "reading old rulings"]


def _missions(tmp, leg, targets):
    d = tmp / "missions"
    d.mkdir()
    (d / f"{leg}.json").write_text(json.dumps({"id": leg, "targets": targets}),
                                   encoding="utf-8")
    return d


def _off(wave, leg, n):
    # off-target progress: the target field cites NO T<n> / acceptance index
    for i in range(n):
        bus.post(wave, leg, "progress", {"target": OFF[i % len(OFF)], "i": i}, "*")


def test_drifting_leg_gets_refocus_with_targets_verbatim(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "BUS_ROOT", tmp_path / "bus")
    wave, leg = "wdrift", "BP2-DEMO"
    targets = ["T1) measure the token spend from the transcript",
               "T2) resolve a model per leg by tier"]
    md = _missions(tmp_path, leg, targets)
    _off(wave, leg, 5)
    acted = drift.check(wave, missions_dir=md)
    assert ("refocus", leg) in acted
    posts = [m for m in bus.read(wave) if m["type"] == "refocus" and m["to"] == leg]
    assert len(posts) == 1
    assert posts[0]["frm"] == "orchestrator"
    assert posts[0]["body"]["targets"] == targets      # VERBATIM


def test_on_target_leg_is_left_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "BUS_ROOT", tmp_path / "bus")
    wave, leg = "wok", "BP2-DEMO"
    md = _missions(tmp_path, leg, ["T1"])
    for i in range(5):
        bus.post(wave, leg, "progress", {"target": "T%d" % (i + 1)}, "*")
    assert drift.check(wave, missions_dir=md) == []
    assert not [m for m in bus.read(wave) if m["type"] in ("refocus", "halt")]


def test_ratio_boundary_point_six_is_on_target(tmp_path, monkeypatch):
    # exactly 3/5 = 0.6 is NOT drifting (>= threshold); 2/5 = 0.4 IS drifting.
    monkeypatch.setattr(bus, "BUS_ROOT", tmp_path / "bus")
    md = _missions(tmp_path, "BP2-DEMO", ["T1"])
    w1 = "wbound_ok"
    for t in ["T1", "T2", "T3", "off one", "off two"]:
        bus.post(w1, "BP2-DEMO", "progress", {"target": t}, "*")
    assert drift.check(w1, missions_dir=md) == []       # 0.6 -> on target
    w2 = "wbound_drift"
    for t in ["T1", "T2", "off a", "off b", "off c"]:
        bus.post(w2, "BP2-DEMO", "progress", {"target": t}, "*")
    assert ("refocus", "BP2-DEMO") in drift.check(w2, missions_dir=md)  # 0.4 -> drift


def test_two_refocus_unimproved_escalates_to_halt(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "BUS_ROOT", tmp_path / "bus")
    wave, leg = "whalt", "BP2-DEMO"
    md = _missions(tmp_path, leg, ["T1"])
    _off(wave, leg, 5)
    # two prior refocus (distinct bodies so a coarse-clock dedup keeps both),
    # leg still drifting -> escalate to halt
    bus.post(wave, "orchestrator", "refocus", {"leg": leg, "seq": 1}, leg)
    bus.post(wave, "orchestrator", "refocus", {"leg": leg, "seq": 2}, leg)
    acted = drift.check(wave, missions_dir=md)
    assert ("halt", leg) in acted
    halts = [m for m in bus.read(wave) if m["type"] == "halt" and m["to"] == leg]
    assert len(halts) == 1 and halts[0]["frm"] == "orchestrator"


def test_halt_is_never_repeated(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "BUS_ROOT", tmp_path / "bus")
    wave, leg = "wnorehalt", "BP2-DEMO"
    md = _missions(tmp_path, leg, ["T1"])
    _off(wave, leg, 5)
    bus.post(wave, "orchestrator", "halt", {"leg": leg}, leg)
    assert drift.check(wave, missions_dir=md) == []     # already halted


def test_drift_writes_nothing_but_bus_posts(tmp_path, monkeypatch):
    # never edits a mission or a manifest (crucible criterion): the missions dir
    # is untouched, and only the bus grows.
    monkeypatch.setattr(bus, "BUS_ROOT", tmp_path / "bus")
    wave, leg = "wpure", "BP2-DEMO"
    md = _missions(tmp_path, leg, ["T1"])
    before = {p.name: p.read_bytes() for p in md.iterdir()}
    _off(wave, leg, 5)
    drift.check(wave, missions_dir=md)
    after = {p.name: p.read_bytes() for p in md.iterdir()}
    assert after == before                              # missions bytes unchanged
