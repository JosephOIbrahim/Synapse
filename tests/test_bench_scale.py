"""test_bench_scale — contract pins for the scale-parameterized bench (R305 I1).

WHAT THIS FILE GUARDS (and what it deliberately does not):

  * The "extend, never rebuild" contract (docs/BENCHMARK_DESIGN.md:140): a
    no-argument run of either root bench issues EXACTLY today's op sequence.
    This is the binary check — if it fails, the bench was rebuilt.
  * The honesty boundary, enforced in the emitter rather than in prose: no
    OFFLINE record may carry a wall-clock key, no record of any tier may carry
    a share-of-turn field, no record may carry a number without a producer,
    and no rung may be parameterized by prim count alone (the H10 blind spot).
  * The offline tier runs with pxr IMPORT-BLOCKED — the CI condition.
  * The curve is monotonic in the scale term WITHIN a gate regime. Across a
    regime boundary it is not, on purpose, and the instrument says so.
  * --help exits 0 with no Houdini, no bridge and no pxr (the P5 gate,
    harness/latency/verify.py:192).

NOT guarded here: any wall-clock number. This bench is the MAP; the gate is
harness/verify/perf_ratchet.py, and nothing in this file reads or writes
harness/verify/perf_baseline.json.
"""
from __future__ import annotations

import builtins
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _load(name: str, relpath: str):
    path = REPO / relpath
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def bench():
    return _load("bench_scale", "scripts/bench_scale.py")


@pytest.fixture(scope="module")
def latency_bench():
    return _load("_benchmark_latency", "_benchmark_latency.py")


@pytest.fixture(scope="module")
def api_bench():
    return _load("_benchmark_api", "_benchmark_api.py")


# ── 1. extend, never rebuild ────────────────────────────────────────────────

# The legacy WS sequence, frozen. Every entry is (kind, name-or-type, payload
# fingerprint). Adding, removing or reordering a line here means the legacy
# behaviour changed — which is the thing docs/BENCHMARK_DESIGN.md:140 forbids.
LEGACY_WS_SEQUENCE = [
    ("benchmark", "ping", "ping", None),
    ("benchmark", "heartbeat", "heartbeat", None),
    ("benchmark", "get_health", "get_health", None),
    ("benchmark", "get_scene_info", "get_scene_info", None),
    ("benchmark", "get_selection", "get_selection", None),
    ("send", None, "execute_python", "createNode('null','bench_node')"),
    ("benchmark", "get_parm", "get_parm", "/obj/bench_node"),
    ("benchmark", "set_parm", "set_parm", "/obj/bench_node"),
    ("benchmark", "execute_python (2+2)", "execute_python", "result = 2 + 2"),
    ("benchmark", "execute_python (hou.ver)", "execute_python",
     "applicationVersionString"),
    ("benchmark", "create+delete node", "execute_python", "_tmp"),
    ("send", None, "execute_python", "hou.node('/obj/bench_node').destroy()"),
]

LEGACY_API_SEQUENCE = [
    ("call", None, "synapse.ping", None),
    ("benchmark", "ping", "synapse.ping", None),
    ("benchmark", "get_health", "synapse.get_health", None),
    ("benchmark", "get_scene_info", "synapse.get_scene_info", None),
    ("benchmark", "get_selection", "synapse.get_selection", None),
    ("call", None, "synapse.create_node", "api_bench_node"),
    ("benchmark", "get_parm", "synapse.get_parm", "/obj/api_bench_node"),
    ("benchmark", "set_parm", "synapse.set_parm", "/obj/api_bench_node"),
    ("benchmark", "execute_python (2+2)", "synapse.execute_python",
     "result = 2 + 2"),
    ("benchmark", "execute_python (hou.ver)", "synapse.execute_python",
     "applicationVersionString"),
    ("call", None, "synapse.delete_node", "/obj/api_bench_node"),
]


def _fingerprint(payload, needle_pool):
    """Reduce a payload to the frozen fingerprint token, so the pin survives
    whitespace edits but not semantic ones. LONGEST match wins — several
    needles are substrings of each other ('api_bench_node' inside
    '/obj/api_bench_node'), and a first-match scan silently picks the wrong
    one depending on list order."""
    blob = json.dumps(payload, sort_keys=True) if payload else ""
    hits = [n for n in needle_pool if n and n in blob]
    return max(hits, key=len) if hits else None


class TestLegacySequenceUnchanged:
    """The 'extend, never rebuild' binary check."""

    def test_ws_no_arg_run_issues_the_legacy_sequence(self, latency_bench,
                                                      monkeypatch):
        calls = []
        needles = [e[3] for e in LEGACY_WS_SEQUENCE if e[3]]

        class _FakeWS:
            def close(self):
                calls.append(("close", None, None, None))

        monkeypatch.setattr(latency_bench, "_connect",
                            lambda *a, **k: _FakeWS())
        monkeypatch.setattr(
            latency_bench, "benchmark",
            lambda ws, name, ctype, payload=None, iterations=None: calls.append(
                ("benchmark", name, ctype, _fingerprint(payload, needles))))
        monkeypatch.setattr(
            latency_bench, "send_command",
            lambda ws, ctype, payload=None, timeout=10: (
                calls.append(("send", None, ctype,
                              _fingerprint(payload, needles))),
                (0.0, True, None))[1])

        assert latency_bench.main([]) == 0
        assert [c for c in calls if c[0] != "close"] == LEGACY_WS_SEQUENCE

    def test_api_no_arg_run_issues_the_legacy_sequence(self, api_bench,
                                                       monkeypatch):
        calls = []
        needles = [e[3] for e in LEGACY_API_SEQUENCE if e[3]]

        monkeypatch.setattr(
            api_bench, "call_api",
            lambda fn, kwargs=None: (
                calls.append(("call", None, fn, _fingerprint(kwargs, needles))),
                (0.0, {"protocol_version": "4.0.0"}))[1])
        monkeypatch.setattr(
            api_bench, "benchmark",
            lambda name, fn, kwargs=None, iterations=None: calls.append(
                ("benchmark", name, fn, _fingerprint(kwargs, needles))))

        assert api_bench.main([]) == 0
        assert calls == LEGACY_API_SEQUENCE

    def test_bare_tier_flag_absent_still_runs_legacy(self, latency_bench,
                                                     monkeypatch):
        """Passing an unrelated flag must NOT silently switch tiers."""
        ran = []
        monkeypatch.setattr(latency_bench, "legacy_main",
                            lambda: ran.append("legacy"))
        assert latency_bench.main(["--iterations", "3"]) == 0
        assert ran == ["legacy"]


# ── 2. --help exits 0 with no Houdini / no bridge (the P5 gate) ─────────────

class TestHelpExitsZero:
    @pytest.mark.parametrize("script", ["_benchmark_latency.py",
                                        "_benchmark_api.py",
                                        "scripts/bench_scale.py"])
    def test_help_exit_zero_and_advertises_scale(self, script):
        p = subprocess.run([sys.executable, str(REPO / script), "--help"],
                           capture_output=True, text=True, timeout=180,
                           encoding="utf-8", errors="replace", cwd=str(REPO))
        assert p.returncode == 0, f"{script} --help exited {p.returncode}\n{p.stderr[-2000:]}"
        assert "--scale" in p.stdout
        assert "--volume" in p.stdout

    def test_websockets_is_not_imported_at_module_top(self):
        """A module-top websockets import is what made --help fail where
        websockets is absent (hython, a pxr-less CI leg)."""
        src = (REPO / "_benchmark_latency.py").read_text(encoding="utf-8")
        head = src.split("def _connect", 1)[0]
        assert "import websockets" not in head
        assert "from websockets" not in head


# ── 3. the honesty boundary, enforced by the emitter ───────────────────────

class TestEmitterHonesty:
    def _good(self, bench):
        return {
            "tier": "offline",
            "rung": {"prim_count": 4, "authored_elements": 100},
            "counters": {"prim_visits": 12},
            "producer": bench.producer_stamp("pytest"),
        }

    def test_a_well_formed_offline_record_passes(self, bench):
        assert bench.assert_record_honest(self._good(bench))

    @pytest.mark.parametrize("poison_key", [
        # suffix forms
        "avg_ms", "p95_ms", "hash_duration", "total_seconds", "wall_clock",
        "cook_latency", "elapsed",
        # LEADING / INFIX forms — a suffix-anchored rule let these through,
        # which is the whole class the rule exists to stop
        "ms_total", "duration_of_hash", "latency_p95", "sec_per_op",
        "elapsed_total", "us_per_prim",
    ])
    def test_offline_record_with_a_wallclock_key_is_rejected(self, bench,
                                                             poison_key):
        rec = self._good(bench)
        rec["counters"][poison_key] = 12.5
        with pytest.raises(bench.BenchScaleError, match="wall-clock"):
            bench.assert_record_honest(rec)

    def test_wallclock_key_is_rejected_at_any_nesting_depth(self, bench):
        rec = self._good(bench)
        rec["nested"] = {"deeper": [{"hash_ms": 3.0}]}
        with pytest.raises(bench.BenchScaleError, match="wall-clock"):
            bench.assert_record_honest(rec)

    def test_live_records_MAY_carry_wallclock(self, bench):
        rec = self._good(bench)
        rec["tier"] = "live"
        rec["timings_ms"] = {"avg_ms": 4.2}
        assert bench.assert_record_honest(rec)

    @pytest.mark.parametrize("share_key", ["t1_share", "percent_of_turn",
                                           "pct_wall", "turn_fraction"])
    def test_no_tier_may_emit_a_share_of_turn(self, bench, share_key):
        for tier in ("offline", "live"):
            rec = self._good(bench)
            rec["tier"] = tier
            rec[share_key] = 0.05
            with pytest.raises(bench.BenchScaleError,
                               match="share-of-turn|percent"):
                bench.assert_record_honest(rec)

    @pytest.mark.parametrize("field", ["cmd", "git", "interpreter",
                                       "builder_sha256", "producer_path"])
    def test_law2_a_row_without_a_producer_is_a_hard_error(self, bench, field):
        rec = self._good(bench)
        rec["producer"][field] = ""
        with pytest.raises(bench.BenchScaleError, match="Law 2"):
            bench.assert_record_honest(rec)

    @pytest.mark.parametrize("innocent_key", [
        "time_samples", "prim_visits", "value_reads", "n_points",
        "scale_points", "counters", "arrays_per_prim", "attrs_examined",
    ])
    def test_the_wallclock_rule_does_not_fire_on_real_schema_keys(
            self, bench, innocent_key):
        """A rule that also rejects the schema's own keys is unusable."""
        assert not bench._WALLCLOCK_KEY.search(innocent_key), innocent_key
        assert not bench._SHARE_KEY.search(innocent_key), innocent_key

    def test_a_prim_only_rung_is_rejected_as_the_H10_blind_spot(self, bench):
        """The whole reason this bench exists: a record parameterized by prim
        count alone reproduces the 16,677x gate miss."""
        rec = self._good(bench)
        del rec["rung"]["authored_elements"]
        with pytest.raises(bench.BenchScaleError, match="H10 blind spot"):
            bench.assert_record_honest(rec)


# ── 4. the offline tier runs with pxr import-blocked (the CI condition) ────

class TestOfflineTierNeedsNothing:
    def test_offline_sweep_runs_with_pxr_import_blocked(self, bench,
                                                        monkeypatch):
        """CI installs [dev,websocket,mcp] and has no pxr. Block the import
        outright and prove the offline tier still produces its integers."""
        real_import = builtins.__import__

        def _blocked(name, *a, **k):
            if name == "pxr" or name.startswith("pxr."):
                raise ImportError("pxr blocked by test_bench_scale")
            return real_import(name, *a, **k)

        monkeypatch.delitem(sys.modules, "pxr", raising=False)
        monkeypatch.setattr(builtins, "__import__", _blocked)

        recs = bench.sweep_volume((25_000, 250_000, 1_000_000))
        assert len(recs) == 3
        for r in recs:
            assert r["producer"]["pxr"] is None, \
                "producer must record pxr=None when pxr is unimportable"
            assert all(isinstance(v, int) for v in r["counters"].values())

    def test_offline_sweep_needs_no_hou(self, bench):
        assert "hou" not in sys.modules or sys.modules["hou"] is None or True
        recs = bench.sweep_prims((100, 1_000))
        assert all(r["producer"]["houdini"] is None for r in recs)

    def test_offline_run_emits_no_wallclock_key_anywhere(self, bench):
        """Scan the ENTIRE emitted run, not just the record the emitter saw."""
        run = bench.run_offline("both", prim_points=(100, 1_000, 10_000),
                                volume_points=(25_000, 250_000, 1_000_000))
        blob = json.dumps(run)
        for _path, key, _v in bench._walk_keys(run):
            assert not bench._WALLCLOCK_KEY.search(str(key)), \
                f"offline run leaked a wall-clock key: {key}"
            assert not bench._SHARE_KEY.search(str(key)), \
                f"offline run leaked a share-of-turn key: {key}"
        assert '"tier": "offline"' in blob


# ── 5. the curve ───────────────────────────────────────────────────────────

class TestCurve:
    def test_scale_points_are_strictly_increasing(self, bench):
        run = bench.run_offline("both")
        for axis, curve in run["curves"].items():
            xs = curve["scale_points"]
            assert xs == sorted(xs) and len(set(xs)) == len(xs), \
                f"{axis}: scale points not strictly increasing: {xs}"

    def test_every_counter_is_monotonic_within_a_gate_regime(self, bench):
        """Monotonicity is the contract WITHIN a regime. Across the gate it is
        not, by construction — crossing removes Flatten calls and adds
        traversal passes — and the instrument reports that instead of
        smoothing it."""
        run = bench.run_offline("both")
        for axis, curve in run["curves"].items():
            for regime, blk in curve["by_regime"].items():
                for cname, c in blk["counters"].items():
                    assert c["monotonic"] != "non-monotonic", (
                        f"{axis}/{regime}: counter {cname} is non-monotonic "
                        f"within one regime: {c['values']} over "
                        f"{blk['scale_points']}")

    def test_a_curve_needs_at_least_three_points(self, bench):
        recs = bench.sweep_prims((100, 1_000))
        with pytest.raises(bench.BenchScaleError, match=">= 3 scale points"):
            bench.fit_curve(recs)

    def test_a_refusal_is_an_exit_code_not_a_traceback(self, bench, capsys):
        """REFUSAL IS FIRST-CLASS: too few points must exit 1 with a stated
        reason and emit no numbers, not raise a raw traceback at the user."""
        rc = bench.main(["--axis", "prims", "--scale", "100,1000"])
        assert rc == 1
        assert "REFUSED" in capsys.readouterr().err

    def test_fit_refuses_to_mix_axes(self, bench):
        a = bench.sweep_prims((100, 1_000, 10_000))
        b = bench.sweep_volume((25_000, 250_000, 1_000_000))
        with pytest.raises(bench.BenchScaleError, match="across axes"):
            bench.fit_curve(a + b)

    def test_fit_refuses_to_mix_builders(self, bench):
        recs = bench.sweep_prims((100, 1_000, 10_000))
        recs[1]["producer"] = {**recs[1]["producer"],
                               "builder_sha256": "deadbeefdeadbeef"}
        with pytest.raises(bench.BenchScaleError, match="builder_sha256"):
            bench.fit_curve(recs)

    def test_curve_carries_an_intercept_and_a_slope_per_counter(self, bench):
        run = bench.run_offline("volume")
        curve = run["curves"][bench.AXIS_VOLUME]
        assert set(curve["counters"]) == set(bench.COUNTERS), \
            "the curve must cover the WHOLE ratchet vocabulary, not a subset"
        for cname, c in curve["counters"].items():
            assert "intercept" in c and "slope_per_unit" in c, cname


# ── 6. the volume axis is REAL — the measurement this bench exists for ─────

class TestVolumeAxisIsVisible:
    """The I1 design parameterized by prim count. H10 refuted that as the
    central axis. These pins prove the volume axis MOVES the instrument with
    the prim count held constant — i.e. the curve SHOWS the axis rather than
    asserting it."""

    def test_prims_are_held_constant_across_the_volume_sweep(self, bench):
        recs = bench.sweep_volume()
        prim_counts = {r["rung"]["prim_count"] for r in recs}
        assert prim_counts == {bench.VOLUME_AXIS_PRIMS}, \
            "the volume sweep must hold prims constant or it is not an axis"

    def test_authored_volume_grows_strictly(self, bench):
        recs = bench.sweep_volume()
        vols = [r["rung"]["authored_elements"] for r in recs]
        assert vols == sorted(vols) and len(set(vols)) == len(vols)
        assert len(vols) >= 3, "the brief requires >= 3 volume points"

    def test_the_gate_flips_on_volume_alone_with_prims_below_the_prim_gate(
            self, bench):
        """The H10 finding, pinned: at 4 prims the PRIM term can never fire,
        so any regime change along this sweep is the VOLUME term or nothing."""
        recs = bench.sweep_volume()
        modes = [r["gate"]["observed_mode"] for r in recs]
        assert bench.VOLUME_AXIS_PRIMS <= recs[0]["gate"]["prim_threshold"], \
            "the sweep's prim count must sit below the prim gate"
        assert "full" in modes and "reduced" in modes, (
            f"the volume sweep never crossed the volume gate: {modes} — it "
            f"cannot show the axis it exists to show")

    def test_flatten_calls_fall_to_zero_on_volume_alone(self, bench):
        recs = bench.sweep_volume()
        below = [r for r in recs if r["gate"]["observed_mode"] == "full"]
        above = [r for r in recs if r["gate"]["observed_mode"] == "reduced"]
        assert all(r["counters"]["flatten_exports"] == 2 for r in below)
        assert all(r["counters"]["flatten_exports"] == 0 for r in above)

    def test_prim_axis_also_spans_its_own_crossover(self, bench):
        modes = [r["gate"]["observed_mode"] for r in bench.sweep_prims()]
        assert "full" in modes and "reduced" in modes, (
            f"the prim sweep must span the prim gate too: {modes}")

    def test_the_array_handle_refuses_to_be_iterated(self, bench):
        """_stage_volume_exceeds is documented len()-only. If the bridge ever
        starts READING elements the fake must fail loudly, not under-count."""
        h = bench._ArrayHandle(10)
        assert len(h) == 10
        with pytest.raises(bench.BenchScaleError, match="len\\(\\)-only"):
            list(h)


# ── 7. one counter vocabulary, and the armed instrument left alone ─────────

class TestSharedVocabulary:
    """These read the RESIDENT perf_counters module (bench.pc) rather than
    re-loading it. A fresh importlib load would replace
    sys.modules['perf_counters'] mid-session and hand every later test a
    different module object — the same residency hazard tests/conftest.py
    documents for `hou`, one layer up."""

    def test_the_bench_uses_the_ratchets_counter_names(self, bench):
        assert bench.COUNTERS is bench.pc.COUNTERS, (
            "the bench must import the ratchet's vocabulary, not declare a "
            "second one — two vocabularies is how the ratchet and the bench "
            "drift apart")

    def test_the_bench_reuses_the_resident_perf_counters_module(self, bench):
        assert bench.pc is sys.modules.get("perf_counters"), (
            "the bench loaded a SECOND copy of perf_counters — the ratchet "
            "and the bench would then measure through different modules")

    def test_the_bench_does_not_mutate_perf_counters_scenarios(self, bench):
        before = sorted(bench.pc.SCENARIOS)
        bench.run_offline("volume", volume_points=(25_000, 250_000,
                                                   1_000_000))
        assert sorted(bench.pc.SCENARIOS) == before, \
            "the bench must not add scenarios to the ARMED ratchet instrument"

    # NOTE: a `git diff HEAD -- tests/perf_counters.py` assertion was written
    # here and DELETED before shipping. It only catches UNCOMMITTED edits, so
    # any future commit that changed the armed instrument would sail past it
    # green. A guard that cannot guard is worse than none; the real guard for
    # a changed floor is harness/verify/perf_ratchet.py::validate_promotion,
    # which reads at merge-base and demands a changed _why.

    def test_env_is_restored_after_a_sweep(self, bench):
        import os
        keys = ("SYNAPSE_STAGE_HASH_PRIM_THRESHOLD",
                "SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD",
                "SYNAPSE_STAGE_HASH_LARGE_MODE")
        before = {k: os.environ.get(k) for k in keys}
        bench.sweep_volume((25_000, 250_000, 1_000_000))
        assert {k: os.environ.get(k) for k in keys} == before, \
            "a sweep leaked its env pins — the next measurement is poisoned"

    def test_bridge_module_globals_are_restored_after_a_sweep(self, bench):
        import shared.bridge as b
        before = (b._HOU_AVAILABLE, b.hou, b._import_pxr_composition)
        bench.sweep_prims((100, 1_000, 10_000))
        assert (b._HOU_AVAILABLE, b.hou,
                b._import_pxr_composition) == before, \
            "a sweep leaked the fake-hou seam into the rest of the session"
