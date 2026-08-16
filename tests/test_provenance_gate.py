"""W6-PROV — pins check_provenance_not_bypassed wired FAIL-CLOSED to the FloorGate chokepoint.

The guardrail was a 0a'-track warn-only ADAPT stub (``ok:None``) across the whole R-track: the
real live gateway it needed to anchor to — the FloorGate (``python/synapse/core/floor_gate.py``),
which every mutating command passes through at ``registry.invoke() -> self._floor_gate.wrap(...)``,
writing one durable provenance record per mutating op — was built on the SAME 0a'-prime track but
the guardrail was never pointed at it. W6-PROV wires it. GREEN when the dispatch chokepoint is
intact; RED (a deterministic guardrail FAIL that run.ts short-circuits to a repair ticket) the
moment a mutation can reach ``hou.*`` with no provenance record.

Seam discipline mirrors tests/test_r_track.py: synthetic worktrees planted under ``tmp_path``
(``ctx['wt'] = tmp_path``) — no sys.modules fakes, no monkeypatch; ``detail`` assertions are
SUBSTRING matches; every RED fixture reproduces a real bypass shape and every GREEN fixture the
intact wiring. The live-tree test asserts the wired guardrail reads GREEN on the real repo today
(the honest counterpart of test_r_track.py::test_live_tree_gates_read_red_now).
"""
import importlib.util
import json
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[1]
_CHECKS = _REPO / "harness" / "verify" / "checks.py"
_spec = importlib.util.spec_from_file_location("harness_checks_prov", _CHECKS)
checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checks)

# guardrails.checks frozen surface — provenance is a GUARDRAIL, wiring it must not touch the list.
GUARDRAILS_FROZEN = [
    "scout_no_apex_corpus",
    "no_rigging_drift",
    "provenance_not_bypassed",
    "phantom_clean",
    "suite_baseline",
]

# Synthetic sources carrying the exact load-bearing literals of the real chokepoint. Minimal on
# purpose (test_r_track.py precedent): the fingerprint judges presence/absence of the wiring, not
# behavior, so tiny faithful stand-ins are the correct fixture.
CLEAN_HANDLERS = (
    "class CommandHandlerRegistry:\n"
    "    def __init__(self):\n"
    "        self._floor_gate = FloorGate()\n"
    "    def invoke(self, command_type, payload, ctx=None):\n"
    "        handler = self.get(command_type)\n"
    "        return self._floor_gate.wrap(command_type, payload, handler, ctx=ctx)\n"
    "\n"
    "class SynapseHandler:\n"
    "    def handle(self, command):\n"
    "        handler = self._registry.get(command.type)\n"
    "        if handler is None:\n"
    "            return None\n"
    "        result = self._registry.invoke(command.type, command.payload,\n"
    "                                        ctx=FloorContext(origin='handler'))\n"
    "        return result\n"
)
CLEAN_FLOOR = (
    "class FloorGate:\n"
    "    def wrap(self, cmd_type, payload, fn, ctx=None):\n"
    "        read_only = self._is_read_only(cmd_type)\n"
    "        result = fn(payload)\n"
    "        if not read_only:\n"
    "            self._record(op_id, cmd_type, payload, result=result, outcome='ok')\n"
    "        return result\n"
    "    def _record(self, *a, **k):\n"
    "        from synapse.cognitive.tools.write_report import write_report\n"
    "        write_report('x.json', '{}', base_dir=self.provenance_dir)\n"
)


def _ctx(wt):
    return {"wt": str(wt), "hython": "", "mode": "A"}


def _plant(root, rel, text):
    p = pathlib.Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _clean(root):
    _plant(root, "python/synapse/server/handlers.py", CLEAN_HANDLERS)
    _plant(root, "python/synapse/core/floor_gate.py", CLEAN_FLOOR)


def _run(wt):
    return checks.check_provenance_not_bypassed(_ctx(wt))


# ---------------- conformance: wired into DISPATCH, guardrails frozen ----------------

def test_in_dispatch():
    assert "provenance_not_bypassed" in checks.DISPATCH
    assert checks.DISPATCH["provenance_not_bypassed"] is checks.check_provenance_not_bypassed


def test_guardrails_list_unchanged_by_wiring():
    doc = json.loads((_REPO / "harness" / "tasks.json").read_text(encoding="utf-8"))
    assert doc["guardrails"]["checks"] == GUARDRAILS_FROZEN
    assert "provenance_not_bypassed" in doc["guardrails"]["checks"]


# ---------------- GREEN: intact chokepoint ----------------

def test_green_clean_chokepoint(tmp_path):
    _clean(tmp_path)
    res = _run(tmp_path)
    assert res["ok"] is True
    assert "FloorGate" in res["detail"]


# ---------------- RED: one bypass per leg ----------------

def test_red_leg1_registry_skips_floorgate(tmp_path):
    # invoke() dispatches the handler directly and the gate is never constructed.
    _clean(tmp_path)
    _plant(tmp_path, "python/synapse/server/handlers.py",
           CLEAN_HANDLERS
           .replace("self._floor_gate = FloorGate()", "pass  # gate gone")
           .replace("return self._floor_gate.wrap(command_type, payload, handler, ctx=ctx)",
                    "return handler(payload)"))
    res = _run(tmp_path)
    assert res["ok"] is False
    assert "FloorGate" in res["detail"]
    assert "handlers.py" in res["detail"]


def test_red_leg2_gateway_not_persisted(tmp_path):
    # the gate still wraps, but _record no longer writes the durable provenance file.
    _clean(tmp_path)
    _plant(tmp_path, "python/synapse/core/floor_gate.py",
           CLEAN_FLOOR.replace("write_report('x.json', '{}', base_dir=self.provenance_dir)",
                               "pass  # no persist"))
    res = _run(tmp_path)
    assert res["ok"] is False
    assert "passthrough" in res["detail"] or "write_report" in res["detail"]


def test_red_leg3a_get_and_call_sidedoor(tmp_path):
    # the pre-FloorGate get-and-call idiom introduced anywhere under server/.
    _clean(tmp_path)
    _plant(tmp_path, "python/synapse/server/handlers_sneaky.py",
           "def go(self, cmd, payload):\n    return self._registry.get(cmd)(payload)\n")
    res = _run(tmp_path)
    assert res["ok"] is False
    assert "handlers_sneaky.py" in res["detail"]
    assert "outside the FloorGate" in res["detail"]


def test_red_leg3b_handle_direct_dispatch(tmp_path):
    # handle() dispatches the bound handler directly, skipping invoke() -> the gate.
    _clean(tmp_path)
    _plant(tmp_path, "python/synapse/server/handlers.py",
           CLEAN_HANDLERS.replace(
               "result = self._registry.invoke(command.type, command.payload,\n"
               "                                        ctx=FloorContext(origin='handler'))",
               "result = handler(command.payload)"))
    res = _run(tmp_path)
    assert res["ok"] is False
    assert "handle()" in res["detail"]


def test_normalized_get_argument_is_not_a_false_sidedoor(tmp_path):
    # a legitimate registry.get(normalize(x)) None-check (nested parens, no trailing call) must
    # NOT trip the get-and-call regex — the exact live-tree idiom at handlers.py:495.
    _clean(tmp_path)
    _plant(tmp_path, "python/synapse/server/handlers_norm.py",
           "def probe(self, command):\n"
           "    handler = self._registry.get(normalize_command_type(command.type))\n"
           "    return handler is None\n")
    res = _run(tmp_path)
    assert res["ok"] is True, res["detail"]


# ---------------- fail-closed, never the pre-W6 warn-only ok:None ----------------

def test_never_warn_only_none(tmp_path):
    _clean(tmp_path)
    assert _run(tmp_path)["ok"] is not None  # clean -> True, never None
    empty = tmp_path / "empty"
    empty.mkdir()
    res = _run(empty)  # unreadable dispatch surface fails CLOSED, never warns
    assert res["ok"] is False
    assert "fail-closed" in res["detail"]


# ---------------- _method_body helper (scopes leg 3b to handle()) ----------------

def test_method_body_slices_one_method():
    body = checks._method_body(CLEAN_HANDLERS, "def handle(self, command")
    assert body is not None
    assert "self._registry.invoke(" in body
    assert "def invoke(" not in body  # sibling method excluded
    assert checks._method_body(CLEAN_HANDLERS, "def nonexistent(") is None


# ---------------- live-tree honesty: the wired guardrail reads GREEN today ----------------

def test_live_tree_provenance_not_bypassed():
    """On the real repo every mutating command routes through the FloorGate (server registry
    invoke() -> _floor_gate.wrap; all three invoke sites provenance-routed; zero side-door
    dispatch). The wired guardrail must read GREEN — a false RED here means the fingerprint is
    mis-located, and a None means it regressed to warn-only."""
    res = checks.check_provenance_not_bypassed(_ctx(_REPO))
    assert res["ok"] is True, res["detail"]
