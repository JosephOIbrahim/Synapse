"""Tests for the NR-QC-TIMING harness. Stdlib plus pytest; the cv2 test skips on
stock Python (no cv2) and runs under the R4 venv. Nothing here imports ``retina``
or ``synapse``, opens a real frame or times anything that matters.
"""
from __future__ import annotations

import builtins
import importlib.util
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name: str):
    spec = importlib.util.spec_from_file_location("qct_" + name, os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


decide = _load("decide")
stage = _load("stage")
run_timing = _load("run_timing")
make_receipt = _load("make_receipt")


def _fr(fid, T, RW, Floor, share, reaches=True):
    return {"id": fid, "reaches": reaches, "T": T, "RW": RW, "Floor": Floor, "share": share}


# ---------------------------------------------------------------- decide.py
def test_decide_branch_edges():
    b = decide.branch
    assert b(2.0, 9, 9, 1.0) == 1          # T = B
    assert b(2.1, 2.01, 2.5, 0.9) == 2
    assert b(2.1, 1.0, 2.0, 0.9) == 4      # Floor = B
    assert b(2.1, 1.0, 1.9, 0.5) == 3      # share = threshold
    assert b(2.1, 1.0, 1.9, 0.4999) == 5


def test_decide_frame_values_use_the_per_frame_medians():
    v = decide.frame_values({"R": 0.5, "S": 3.0, "S_dense": 2.4, "S_rest": 0.6, "W": 0.1})
    assert v["T"] == pytest.approx(3.6) and v["RW"] == pytest.approx(0.6)
    assert v["Floor"] == pytest.approx(1.2) and v["share"] == pytest.approx(2.4 / 3.6)


def test_decide_rows_and_verdicts():
    three = [_fr(i, 4.0, 1.0, 1.5, 0.8) for i in decide.TIER]
    d = decide.decide(three + [_fr("char-9", 4.0, 1.0, 1.5, 0.8), _fr("char-2", 4.0, 1.0, 1.5, 0.8)])
    assert (d["row"], d["verdict"], d["voting"]) == (3, "branch 3", ["char-2", "char-9", "tier"])
    two = three[:2] + [_fr("sib-v017", 0, 0, 0, 0, reaches=False)]
    assert decide.decide(two)["row"] == 2 and decide.decide(two)["verdict"] == "branch 3"
    one = three[:1] + [_fr(i, 0, 0, 0, 0, reaches=False) for i in decide.TIER[1:]]
    assert decide.decide(one)["verdict"] == "no verdict"          # char-9 and char-2 missing
    assert "tier" not in decide.decide(one)["units"]               # the lone still does not vote
    both = one + [_fr("char-9", 1.0, 0.5, 0.8, 0.9), _fr("char-2", 5.0, 1.0, 1.5, 0.9)]
    assert decide.decide(both)["verdict"] == "split"
    assert decide.decide([_fr(i, 0, 0, 0, 0, reaches=False) for i in decide.TIER])["verdict"] == "no verdict"


def test_decide_char2_even_median_is_the_mean():
    fr = [_fr("char-2", t, 1.0, 1.5, 0.8) for t in (1.0, 3.0, 5.0, 100.0)]
    u = decide.unit_value(fr)
    assert u["T"] == 4.0 and u["T_min"] == 1.0 and u["T_max"] == 100.0


# ---------------------------------------------------------------- process scan
def _procs(*rows):
    return json.dumps([{"ProcessId": p, "Name": n, "CommandLine": c} for p, n, c in rows])


def test_process_scan_blocks_husk_hython_houdini_and_pytest_under_python():
    text = _procs((1, "System", None), (2, "HUSK.exe", None), (3, "hython.exe", "x"), (4, "houdinifx.exe", "x"),
                  (5, "python.exe", "python -m pytest tests"), (6, "python3.12.exe", "run.py"))
    scan = run_timing.parse_process_list(text, own_pid=999)
    assert scan["scanned"] == 6
    assert [b["pid"] for b in scan["blocked"]] == [2, 3, 4, 5]
    assert all(set(b) == {"pid", "name"} for b in scan["blocked"])      # no command line kept


def test_process_scan_allows_licensing_and_excludes_own_pid():
    text = _procs((10, "hserver.exe", None), (11, "sesinetd.exe", None),
                  (12, "python.exe", "python -m pytest harness"), (13, "python.exe", "python run_timing.py"))
    scan = run_timing.parse_process_list(text, own_pid=12)
    assert scan["blocked"] == []


def test_process_scan_single_object_json_and_empty():
    assert run_timing.parse_process_list(json.dumps({"ProcessId": 2, "Name": "husk.exe"}), 1)["blocked"][0]["pid"] == 2
    assert run_timing.parse_process_list("", 1) == {"scanned": 0, "blocked": []}


def test_cpu_load_counts_kernel_as_including_idle():
    # 100 ticks idle, 150 kernel (idle included), 50 user: busy = (150-100)+50 of 200 total
    assert run_timing.cpu_load((0, 0, 0), (100, 150, 50)) == pytest.approx(0.5)
    assert run_timing.cpu_load((5, 5, 5), (5, 5, 5)) == 0.0


# ------------------------------------------------------------ call summaries
def test_summarize_calls_splits_by_line_and_lists_other_lines():
    ms = 1_000_000
    calls = [
        {"type": "medianBlur", "file": "firefly_scan.py", "line": 292, "inner_ns": 10 * ms},
        {"type": "connectedComponentsWithStats", "file": "firefly_scan.py", "line": 352, "inner_ns": 5 * ms},
        {"type": "dilate", "file": "firefly_scan.py", "line": 373, "inner_ns": 1 * ms},
        {"type": "dilate", "file": "firefly_scan.py", "line": 373, "inner_ns": 1 * ms},
        {"type": "imwrite", "file": "firefly_scan.py", "line": 458, "inner_ns": 7 * ms},
        {"type": "boxFilter", "file": "elsewhere.py", "line": 12, "inner_ns": 2 * ms},
    ]
    s = run_timing.summarize_calls(calls, overhead_ns=3 * ms)
    assert s["lines"]["373"]["calls"] == 2 and s["lines"]["352"]["calls"] == 1
    assert s["W"] == pytest.approx(0.007) and s["S_dense"] == pytest.approx(0.015)
    assert s["other_lines"] == [{"file": "elsewhere.py", "line": 12, "type": "boxFilter", "calls": 1,
                                 "inner_s": pytest.approx(0.002)}]
    assert s["types"]["dilate"]["calls"] == 2 and s["overhead_s"] == pytest.approx(0.003)


def test_order_voters_first():
    ents = [{"id": i, "frame": "single"} for i in ("char-12", "char-3", "char-2", "sib-v017", "char-8", "char-9")]
    assert [e["id"] for e in run_timing.order_entries(ents)] == [
        "char-8", "sib-v017", "char-9", "char-2", "char-3", "char-12"]


def test_git_blob_id_matches_git():
    assert run_timing.git_blob_id(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_wrapper_classifies_by_caller_file_and_line(tmp_path):
    try:
        import cv2
        import numpy as np
        ok = isinstance(cv2.__version__, str) and isinstance(np.__version__, str) and hasattr(cv2, "dilate")
    except ImportError:
        ok = False
    if not ok:
        pytest.skip("cv2 is not installed (stock Python): runs under the R4 venv")
    # a stand-in module named firefly_scan.py with calls on known lines
    src = tmp_path / "firefly_scan.py"
    src.write_text("import cv2\n\n\ndef go(img):\n    a = cv2.medianBlur(img, 5)\n"
                   "    n, lab, st, ce = cv2.connectedComponentsWithStats(\n        (a > 0).astype('uint8'), connectivity=8)\n"
                   "    return n\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("firefly_scan", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    inst = run_timing.Instrument(cv2)
    inst.install()
    try:
        inst.begin()
        n = mod.go(np.zeros((16, 16), dtype=np.float32))
        s = inst.end()
        cv2.dilate(np.zeros((4, 4), dtype=np.uint8), np.ones((3, 3), dtype=np.uint8))   # not active: not recorded
    finally:
        inst.restore()
    assert set(s["lines"]) == {"5", "6"}                    # the multi-line call is its first line
    assert inst.n_labels == n and s["other_lines"] == []
    assert cv2.dilate.__name__ == "dilate"                  # restored


# ----------------------------------------------------------------- stage.py
def test_placeholder_file_is_skipped_and_never_opened(tmp_path, monkeypatch):
    src = str(tmp_path / "never_here.exr")           # does not exist: any open would raise

    def boom(*a, **k):
        raise AssertionError("the source was opened")
    monkeypatch.setattr(builtins, "open", boom)
    for bit in (0x1000, 0x40000, 0x400000):
        r = stage.stage_one(src, str(tmp_path / "x" / "a.exr"), stat_fn=lambda p, b=bit: 0x20 | b)
        assert r["skipped"] is True and r["bits"] == bit
    assert not (tmp_path / "x").exists()


def test_stage_one_copies_hashes_and_matches(tmp_path):
    src = tmp_path / "a.exr"
    src.write_bytes(b"abc" * 1000)
    r = stage.stage_one(str(src), str(tmp_path / "id" / "a.exr"), stat_fn=lambda p: 0x20)
    assert r["skipped"] is False and r["source_sha256"] == r["copy_sha256"] and r["bytes"] == 3000
    assert (tmp_path / "id" / "a.exr").read_bytes() == src.read_bytes()


def test_expand_entry_and_rule_block():
    e = {"id": "char-3", "path": "d/OVOID_REACTION.####.exr", "frames": "0001-0003", "files": 3}
    assert [f["frame"] for f in stage.expand_entry(e)] == ["0001", "0002", "0003"]
    assert stage.expand_entry(e)[2]["path"] == "d/OVOID_REACTION.0003.exr"
    assert stage.expand_entry({"id": "x", "path": "d/a.exr", "frames": "single", "files": 1})[0]["frame"] == "single"
    with pytest.raises(ValueError):
        stage.expand_entry({**e, "files": 4})
    doc = "text\n```json\n" + json.dumps({"entries": [e]}) + "\n```\n"
    assert stage.extract_rule_entries(doc)[0]["id"] == "char-3"


def test_checksums_parse_and_rule_refusal(tmp_path, capsys):
    h = "ab" * 32
    assert stage.parse_checksums(f"{h}  exr/OVOID.f0336.exr\n{h.upper()} *exr\\OVOID.f0337.exr\nnot a line\n") == {
        "OVOID.f0336.exr": h, "OVOID.f0337.exr": h}
    rule = tmp_path / "rule.md"
    rule.write_text("not revision 2", encoding="utf-8")
    code = stage.main(["--rule", str(rule), "--stage-root", str(tmp_path / "s"),
                       "--manifest", str(tmp_path / "m.json"), "--summary", str(tmp_path / "s.json")])
    assert code == 1 and "not revision 2" in capsys.readouterr().err and not (tmp_path / "s").exists()


def test_header_problems_flags_a_wrong_shape():
    good = {"w": 3840, "h": 2880, "ch": 4, "parts": 1, "comp": "zips", "fmt": "half",
            "x": 0, "y": 0, "fx": 0, "fy": 0, "fw": 3840, "fh": 2880}
    assert stage.header_problems("char-8", good) == []
    assert stage.header_problems("char-8", {**good, "comp": "piz"}) == ["comp: 'piz' != 'zips'"]


# ------------------------------------------------------------- leak guard
def test_find_leaks_catches_paths_profiles_and_host_markers():
    assert make_receipt.find_leaks('{"a": "retina/firefly_scan.py", "b": "<R4_PYTHON> -B x.py"}') == []
    assert make_receipt.find_leaks('"C:/Users/x/y"')
    assert make_receipt.find_leaks('"D:\\\\data\\\\a.exr"')
    assert make_receipt.find_leaks('"in OneDrive"') and make_receipt.find_leaks('"synapse-build"')
    assert make_receipt.find_leaks('"Myth_and_Logic"')
    assert make_receipt.find_leaks('"a hostname-7"', host_markers=("hostname-7",))
    assert make_receipt.find_leaks('"a hostname-7"') == []


# -------------------------------------------------------- receipt composition
def _rec(fid, frame, index, seq, R, S_dense, S_rest, W, void=False, incl=False, kind="timed", exc=None):
    S = S_dense + S_rest
    r = {"kind": kind, "id": fid, "frame": frame, "index": index, "seq": seq, "void": void,
         "R": R, "wall": S + W, "W": W, "S": S, "S_dense": S_dense, "S_rest": S_rest,
         "lines": {"292": {"calls": 1, "inner_s": S_dense}, "458": {"calls": 1, "inner_s": W}},
         "other_lines": [], "types": {"medianBlur": {"calls": 1, "inner_s": S_dense}}, "overhead_s": 0.0,
         "inconclusive": incl, "n_labels": None if incl else 4, "count": None if incl else 2, "mask_pixels": 2,
         "exception": exc, "threads": {"oiio": 8, "exr": 8, "cv2": 8},
         "before": {"cpu_sample_s": 5.0, "cpu_load": 0.0, "scan": {"scanned": 9, "blocked": []}},
         "after": {"scan": {"scanned": 9, "blocked": []}}, "wall_clock": "2026-11-11T10:00:00", "monotonic_ns": seq}
    if void:
        r["void_reason"] = "scan shows ['husk.exe']"
    return r


def _canned_raw():
    raw, seq = [], 0
    for fid in decide.TIER:
        seq += 1
        raw.append(_rec(fid, "single", None, seq, 0.5, 2.0, 0.5, 0.1, kind="dry"))
    for fid in decide.TIER + ("char-9", "char-12"):
        for k, (R, SD) in enumerate([(0.5, 2.0), (0.6, 2.2), (0.55, 2.1)]):
            seq += 1
            raw.append(_rec(fid, "single", k, seq, R, SD, 0.5, 0.1))
    seq += 1
    raw.append(_rec("char-8", "single", 3, seq, 9.0, 0.0, 99.0, 9.0, void=True))      # void, must not count
    for fr in ("0336", "0337"):
        for k in range(3):
            seq += 1
            raw.append(_rec("char-2", fr, k, seq, 0.4, 2.0, 0.5, 0.1))
    return raw


def _run():
    return {"mode": "smoke", "environment": {
        "python": "3.12.10", "numpy": "2.4.4", "cv2": "5.0.0", "openimageio": "3.1.15.0", "logical_cores": 8,
        "threads": {"oiio": 8, "exr": 8, "cv2": 8}, "pythonpath": {"entries": 1, "resolves_to": "release tree"},
        "product": {"tree_commit": "7f8c5ec3cf6a794691d1df47b0b167f9147e7ac5", "blobs": {}}}}


def test_compose_medians_exclude_void_and_verdict_follows_decide():
    r = make_receipt.compose(_run(), _canned_raw(), None, {"commit": "a" * 40, "files": {}})
    f8 = next(f for f in r["frames"] if f["id"] == "char-8")
    assert len(f8["passes"]) == 4 and sum(1 for p in f8["passes"] if p["void"]) == 1
    assert f8["medians"]["R"] == pytest.approx(0.55) and f8["medians"]["S_rest"] == pytest.approx(0.5)
    assert f8["derived"]["T"] == pytest.approx(0.55 + 2.6 + 0.1)
    assert r["decision"]["row"] == 3 and r["decision"]["verdict"] == "branch 3"
    assert r["decision"]["voting"] == ["char-2", "char-9", "tier"]
    assert [f for f in r["frames"] if f["id"] == "char-12"][0]["non_voting"] is True
    assert r["mode"] == "smoke" and "wall_clock" not in json.dumps(r)


def test_compose_inconclusive_frame_is_excluded_from_the_votes():
    raw = [x for x in _canned_raw() if not (x["id"] == "sib-v017" and x["kind"] == "timed")]
    raw += [_rec("sib-v017", "single", k, 900 + k, 0.5, 0.1, 0.1, 0.0, incl=True) for k in range(3)]
    for x in raw:                                   # r2 3.8: the dry pass says so too
        if x["kind"] == "dry" and x["id"] == "sib-v017":
            x.update(inconclusive=True, n_labels=None, count=None)
    r = make_receipt.compose(_run(), raw, None, {"commit": "a" * 40, "files": {}})
    f = next(f for f in r["frames"] if f["id"] == "sib-v017")
    assert f["reaches_result"] is False and f["inconclusive"] is True and f["n_labels"] is None
    assert r["decision"]["row"] == 2 and r["decision"]["units"]["tier"]["n_frames"] == 2


def test_compose_is_deterministic_and_keeps_no_paths_from_exceptions():
    raw = _canned_raw() + [_rec("char-12", "single", 3, 999, 0.1, 0.1, 0.1, 0.0,
                                exc="scan: OSError: could not write C:/secret/place/mask.png")]
    a = make_receipt.compose(_run(), raw, None, {"commit": "a" * 40, "files": {}})
    b = make_receipt.compose(_run(), list(raw), None, {"commit": "a" * 40, "files": {}})
    ta, tb = json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True)
    assert ta == tb and make_receipt.find_leaks(ta) == []
    assert "scan: OSError" in ta and "secret" not in ta


# ======================================================================================
# Fix pass: the run loop driven with a fake reader and scanner (no cv2, no OIIO, no frames)
# ======================================================================================
class _RGB:
    shape = (4, 4, 3)


class _FakeReader:
    def read_frame(self, path, subimage=0):
        if "badread" in path:
            raise OSError("cannot read " + path)
        return _RGB(), {"origin": [0, 0], "reader": "fake"}


class _FakeScan:
    def __init__(self, fail_at=()):
        self.n, self.fail_at = 0, set(fail_at)

    def fireflies(self, rgb, origin=None, reader=None, mask_path=None):
        self.n += 1
        if self.n in self.fail_at:
            raise MemoryError("transient " + str(mask_path))
        return {"inconclusive": False, "count": 1, "pixel_count": 1, "nonfinite_pixels": 0}

    def firefly_check(self, result):
        return {"pass": True}


class _FakeOIIO:
    def get_int_attribute(self, k):
        return 48


class _FakeCV:
    def getNumThreads(self):
        return 48


_OK = {"scanned": 500, "blocked": []}
_BLK = {"scanned": 500, "blocked": [{"pid": 7, "name": "husk.exe"}]}


def _ent(*ids, bad=()):
    return [{"id": i, "frame": "single", "path": ("badread" if i in bad else "p_" + i)} for i in ids]


TIER3 = ["char-8", "sib-v016", "sib-v017"]


def _drive(tmp_path, monkeypatch, entries, scans=None, fail_at=(), resume=False, pre=None, scan_raises=None,
           jump_clock=False, passes=3):
    """Run ``Run.go`` with fakes. Returns (run, exit code, raw records)."""
    import argparse
    monkeypatch.setattr(run_timing.time, "sleep", lambda s: None)
    monkeypatch.setattr(run_timing, "cpu_sample", lambda s: {"cpu_sample_s": 5.0, "cpu_load": 0.01})
    if jump_clock:
        ticks = {"n": 0}

        def mono():
            ticks["n"] += 1
            return ticks["n"] * 3600.0
        monkeypatch.setattr(run_timing.time, "monotonic", mono)
    queue = list(scans or [])

    def scan(own_pid=None):
        if scan_raises is not None:
            raise scan_raises
        return queue.pop(0) if queue else dict(_OK)
    monkeypatch.setattr(run_timing, "process_scan", scan)
    out = str(tmp_path / "run")
    os.makedirs(out, exist_ok=True)
    if pre:
        with open(os.path.join(out, "raw.jsonl"), "w", encoding="utf-8") as fh:
            for r in pre:
                fh.write(json.dumps(r) + "\n")
    a = argparse.Namespace(out=out, passes=passes, cpu_sample_s=5.0, max_wait_min=1.0, resume=resume, smoke=False)
    run = run_timing.Run(a, {"threads": {"oiio": 48, "exr": 48, "cv2": 48}}, run_timing.Instrument(_FakeCV()),
                         _FakeReader(), _FakeScan(fail_at), _FakeOIIO(), _FakeCV())
    code = run.go([dict(e) for e in entries])
    p = os.path.join(out, "raw.jsonl")
    raw = [json.loads(x) for x in open(p, encoding="utf-8")] if os.path.exists(p) else []
    return run, code, raw


def _of(raw, fid):
    return [x for x in raw if x["id"] == fid]


def test_run_order_dry_then_untimed_then_three_timed_passes(tmp_path, monkeypatch):          # r4
    _, code, raw = _drive(tmp_path, monkeypatch, _ent(*TIER3, "char-9"))
    assert code == 0
    assert [x["kind"] for x in raw[:3]] == ["dry"] * 3
    assert [x["kind"] for x in _of(raw, "char-8")] == ["dry", "timed", "timed", "timed"]     # the dry pass is the warm-up
    assert [x["kind"] for x in _of(raw, "char-9")] == ["untimed", "timed", "timed", "timed"]  # r4: the warm-up pass exists
    assert [x["seq"] for x in raw] == sorted({x["seq"] for x in raw})


def test_dry_pass_exception_stops_the_run_before_any_timed_pass(tmp_path, monkeypatch):      # h6
    ents = [_ent("char-8")[0], _ent("sib-v016", bad=("sib-v016",))[0], _ent("sib-v017")[0]]
    _, code, raw = _drive(tmp_path, monkeypatch, ents)
    assert code == run_timing.EXIT_DRY_EXCEPTION == 3
    assert [x["kind"] for x in raw] == ["dry", "dry"] and not any(x["kind"] == "timed" for x in raw)


def test_failed_after_check_voids_the_pass_and_it_is_redone(tmp_path, monkeypatch):          # h7
    _, code, raw = _drive(tmp_path, monkeypatch, _ent("char-8"), scans=[_OK, _BLK, _OK])
    t = [x for x in raw if x["kind"] == "timed"]
    voids = [x for x in t if x["void"]]
    assert code == 0 and len(voids) == 1 and "after scan shows" in voids[0]["void_reason"]
    assert voids[0]["after"]["scan"]["blocked"][0]["name"] == "husk.exe"
    assert sum(1 for x in t if not x["void"]) == 3


def test_failed_before_check_voids_and_waits(tmp_path, monkeypatch):
    _, code, raw = _drive(tmp_path, monkeypatch, _ent("char-8"), scans=[_BLK, _OK])
    t = [x for x in raw if x["kind"] == "timed"]
    assert code == 0 and t[0]["void"] and "before scan shows" in t[0]["void_reason"] and "R" not in t[0]
    assert sum(1 for x in t if not x["void"]) == 3


def test_resume_never_counts_void_or_exception_passes(tmp_path, monkeypatch):               # h8
    ok = {"kind": "timed", "id": "char-9", "frame": "single", "void": False, "seq": 9}
    pre = ([{"kind": "timed", "id": "char-8", "frame": "single", "void": True, "seq": s} for s in (1, 2, 3)]
           + [dict(ok, exception="scan: MemoryError", seq=4), dict(ok, seq=5)])
    run, _, _ = _drive(tmp_path, monkeypatch, [], resume=True, pre=pre)
    counts, dry = run.done_counts()
    assert counts == {("char-9", "single"): 1} and dry == set()
    assert run.seq == 5


def test_one_exception_voids_the_pass_and_redoes_it_once(tmp_path, monkeypatch):            # F4
    _, code, raw = _drive(tmp_path, monkeypatch, _ent("char-8"), fail_at={4})      # calls 1 to 3 are the dry passes
    t = [x for x in raw if x["kind"] == "timed"]
    voids = [x for x in t if x["void"]]
    assert code == 0 and len(voids) == 1 and voids[0]["void_reason"] == "scan raised MemoryError"
    assert "/" not in voids[0]["void_reason"] and voids[0]["exception"].startswith("scan: MemoryError")
    assert sum(1 for x in t if not x["void"]) == 3 and not any(x.get("exception") for x in t if not x["void"])


def test_a_second_exception_on_the_same_frame_stops_the_run(tmp_path, monkeypatch):         # F4
    _, code, raw = _drive(tmp_path, monkeypatch, _ent(*TIER3, "char-9"), fail_at={4, 5})
    assert code == run_timing.EXIT_EXCEPTION_TWICE == 5 and code not in (2, 3, 4)
    t = [x for x in raw if x["kind"] == "timed"]
    assert len(t) == 2 and all(x["void"] for x in t) and not _of(raw, "char-9")       # what was recorded is kept


def test_a_read_exception_is_also_voided_not_kept(tmp_path, monkeypatch):                    # F4, read side
    _, code, raw = _drive(tmp_path, monkeypatch, _ent("char-8", "char-9", bad=("char-9",)))
    t = _of(raw, "char-9")
    assert code == 5 and [x["kind"] for x in t] == ["untimed", "timed", "timed"] and all(x["void"] for x in t[1:])
    assert t[1]["void_reason"] == "read raised OSError"


def test_process_scan_survives_a_timeout_and_undecodable_output(monkeypatch):               # F7
    import subprocess as sp

    def timeout(*a, **k):
        raise sp.TimeoutExpired("powershell", 120)
    monkeypatch.setattr(run_timing.subprocess, "run", timeout)
    assert run_timing.process_scan()["error"] == "process scan raised TimeoutExpired"

    class Out:
        returncode, stdout = 0, b"\xff\xfe\x00not json \x81"
    monkeypatch.setattr(run_timing.subprocess, "run", lambda *a, **k: Out())
    got = run_timing.process_scan()
    assert got["blocked"] == [] and got["error"].startswith("process scan raised")


def test_a_raising_scan_voids_the_pass_and_the_wait_gives_up(tmp_path, monkeypatch):         # F7
    import subprocess as sp
    _, code, raw = _drive(tmp_path, monkeypatch, _ent("char-8"), scan_raises=sp.TimeoutExpired("powershell", 120),
                          jump_clock=True)
    t = [x for x in raw if x["kind"] == "timed"]
    assert code == run_timing.EXIT_NOT_QUIET == 2
    assert len(t) == 1 and t[0]["void"] and "process scan raised TimeoutExpired" in t[0]["void_reason"]
    assert t[0]["before"]["scan"]["error"]
    sub = tmp_path / "b"
    sub.mkdir()
    _, code, raw = _drive(sub, monkeypatch, _ent("char-8"), scan_raises=UnicodeDecodeError("utf-8", b"x", 0, 1, "bad"),
                          jump_clock=True)
    assert code == 2


def test_resume_after_a_partial_dry_pass_redoes_it_for_the_missing_ids(tmp_path, monkeypatch):    # F9
    pre = [{"kind": "dry", "id": "char-8", "frame": "single", "seq": 1, "exception": None}]
    _, code, raw = _drive(tmp_path, monkeypatch, _ent(*TIER3), resume=True, pre=pre)
    dry = [x["id"] for x in raw if x["kind"] == "dry"]
    assert code == 0 and sorted(dry) == sorted(TIER3) and dry.count("char-8") == 1
    assert [x["kind"] for x in _of(raw, "char-8")][:3] == ["dry", "untimed", "timed"]           # warm-up after a restart
    assert [x["kind"] for x in _of(raw, "sib-v016")][:2] == ["dry", "timed"]


def test_a_dry_pass_that_raised_does_not_count_on_resume(tmp_path, monkeypatch):
    pre = [{"kind": "dry", "id": "char-8", "frame": "single", "seq": 1, "exception": "scan: OSError"}]
    run, _, _ = _drive(tmp_path, monkeypatch, [], resume=True, pre=pre)
    assert run.done_counts()[1] == set()


def test_manifest_with_problems_skips_or_wrong_count_is_refused(tmp_path):                  # F6
    import argparse
    man = tmp_path / "m.json"
    ok_files = [{"id": "char-8", "frame": "single", "staged_path": "x"}] * 124
    for body in ({"files": ok_files, "problems": ["bad"], "skipped": []}, {"files": ok_files, "problems": [], "skipped": [{}]},
                 {"files": ok_files[:123], "problems": [], "skipped": []}):
        man.write_text(json.dumps(body), encoding="utf-8")
        with pytest.raises(run_timing.StartupError):
            run_timing.load_entries(argparse.Namespace(smoke=False, manifest=str(man)))
    man.write_text(json.dumps({"files": ok_files, "problems": [], "skipped": []}), encoding="utf-8")
    assert len(run_timing.load_entries(argparse.Namespace(smoke=False, manifest=str(man)))) == 124


def test_file_sha256_folds_crlf_to_the_bytes_git_holds(tmp_path):                            # F5
    import hashlib
    a, b = tmp_path / "a.py", tmp_path / "b.py"
    a.write_bytes(b"x = 1\r\ny = 2\r\n")
    b.write_bytes(b"x = 1\ny = 2\n")
    assert run_timing.file_sha256(str(a)) == run_timing.file_sha256(str(b)) == hashlib.sha256(b"x = 1\ny = 2\n").hexdigest()


# ----------------------------------------------------------- make_receipt, fix pass
def test_compose_takes_the_deciding_stills_result_from_the_dry_pass(monkeypatch):           # F2
    raw = _canned_raw()
    for x in raw:
        if x["kind"] == "dry" and x["id"] == "sib-v017":
            x.update(inconclusive=True, n_labels=None, count=None)
    r = make_receipt.compose(_run(), raw, None, {"commit": "a" * 40, "files": {}})
    assert r["decision"]["row"] == 2 and r["decision"]["units"]["tier"]["n_frames"] == 2
    f = next(f for f in r["frames"] if f["id"] == "sib-v017")
    assert f["reaches_result"] is True          # the timed passes disagree with the dry pass: the predicate goes red


def test_compose_carries_untimed_records_staging_counts_rulings_and_the_bytes_that_ran():    # F3, F6, F5, F4
    raw = _canned_raw()
    raw.append(dict(_rec("char-9", "single", None, 5000, 0.1, 0.1, 0.1, 0.0, kind="untimed"), exception="scan: OSError: C:/x"))
    run = _run()
    run["harness_files"] = {"harness/vision/qc_timing/run_timing.py": "a" * 64}
    staging = {"distinct_files": 124, "problems": 0, "skipped": 0, "files": []}
    r = make_receipt.compose(run, raw, staging, {"commit": "a" * 40, "files": {}})
    assert r["untimed"] == [{"id": "char-9", "frame": "single", "seq": 5000, "exception": "scan: OSError"}]
    assert r["staging"]["problems"] == 0 and r["staging"]["skipped"] == 0
    assert r["harness"]["ran"] == {"harness/vision/qc_timing/run_timing.py": "a" * 64}
    assert "second exception stops the run" in r["rulings"]["F4"] and "blocked names as they are" in r["rulings"]["F11"]
    assert "hindie.exe" in r["rulings"]["F11_limit"]


def test_make_receipt_refuses_when_the_bytes_that_ran_differ_from_the_commit(tmp_path, monkeypatch, capsys):  # F5
    run = _run()
    run["harness_files"] = {"harness/vision/qc_timing/run_timing.py": "a" * 64}
    (tmp_path / "run.json").write_text(json.dumps(run), encoding="utf-8")
    (tmp_path / "raw.jsonl").write_text("".join(json.dumps(x) + "\n" for x in _canned_raw()), encoding="utf-8")
    monkeypatch.setattr(make_receipt, "harness_binding",
                        lambda root, commit: {"commit": "b" * 40, "files": {"harness/vision/qc_timing/run_timing.py": "c" * 64}})
    code = make_receipt.main(["--run", str(tmp_path), "--out", str(tmp_path / "r.json")])
    assert code == 2 and "differ from the blobs" in capsys.readouterr().err and not (tmp_path / "r.json").exists()
    monkeypatch.setattr(make_receipt, "harness_binding",
                        lambda root, commit: {"commit": "b" * 40, "files": {"harness/vision/qc_timing/run_timing.py": "a" * 64}})
    assert make_receipt.main(["--run", str(tmp_path), "--out", str(tmp_path / "r.json")]) == 0


def test_find_leaks_catches_unc_paths_in_both_slash_forms():                                  # F12
    assert make_receipt.find_leaks(json.dumps({"p": "\\\\fileserver\\share\\a.exr"}))
    assert make_receipt.find_leaks('"//fileserver/share/a.exr"')
    assert make_receipt.find_leaks('"https://example.org/a/b"') == []


# ------------------------------------------- the wrappers on a real fireflies() call (R4 venv only)
def test_wrappers_give_the_per_line_counts_the_predicate_requires_on_a_real_scan(tmp_path):   # r2, r3
    if sys.version_info[:2] != (3, 12):
        # Stock Python's editable install maps retina to the live checkout: never import it there.
        pytest.skip("runs under the R4 venv (CPython 3.12) with PYTHONPATH on the release tree")
    try:
        import cv2
        import numpy as np
        ok = isinstance(cv2.__version__, str) and isinstance(np.__version__, str) and hasattr(cv2, "boxFilter")
    except ImportError:
        ok = False
    if not ok:
        pytest.skip("cv2 is not installed (stock Python): runs under the R4 venv")
    try:
        import retina.firefly_scan as fs          # only reached when cv2 is real, i.e. under the R4 venv
    except ImportError:
        pytest.skip("retina is not on PYTHONPATH")
    rng = np.random.default_rng(1)
    xx = np.tile(np.linspace(0.2, 0.7, 320, dtype=np.float32), (240, 1))
    img = np.clip(np.stack([xx, xx * 0.9, xx * 0.8], axis=2) + rng.normal(0, 0.02, (240, 320, 3)).astype(np.float32), 0.01, None)
    for y, x in ((40, 40), (100, 200), (180, 90)):
        img[y, x, :] = 8.0
    inst = run_timing.Instrument(cv2)
    inst.install()
    try:
        inst.begin()
        res = fs.fireflies(img.astype(np.float32), mask_path=str(tmp_path / "m.png"))
        s = inst.end()
        tiny = np.zeros((240, 320, 3), dtype=np.float32)
        tiny[110:116, 150:156, :] = 0.5
        inst.begin()
        res2 = fs.fireflies(tiny, mask_path=str(tmp_path / "m2.png"))
        s2 = inst.end()
    finally:
        inst.restore()
    assert res["inconclusive"] is False and res["count"] >= 1
    L = {k: v["calls"] for k, v in s["lines"].items()}
    assert (L["292"], L["313"], L["314"], L["352"], L["458"]) == (1, 2, 1, 1, 1)
    assert L["373"] >= 1 and L["542"] >= 1 and L["549"] >= 1 and s["other_lines"] == []
    assert s["types"]["erode"]["calls"] == 1 and s["types"]["imwrite"]["calls"] == 1      # r2, r3: both are wrapped
    assert s["W"] > 0 and s["lines"]["458"]["inner_s"] == s["W"]
    assert res2["inconclusive"] is True and sorted(s2["lines"]) == ["292", "313", "314"] and s2["W"] == 0.0
