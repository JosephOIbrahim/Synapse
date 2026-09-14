"""CRUCIBLE blast-radius probe: F2 direct-tool held state. Headless, no PySide."""
import ast, sys, types
sys.path.insert(0, "C:/Users/User/SYNAPSE/python")
from synapse.panel.designsystem import tokens as t

TREE = sys.argv[1]
SRC = TREE + "/python/synapse/panel/synapse_panel.py"
src = open(SRC, encoding="utf-8").read()
tree = ast.parse(src)

WANT_FN = {"_run_direct_tool", "_hold_direct_state", "_release_direct_state",
           "_render_state", "_set_header", "_on_emergency_halt", "_on_cancel_cook",
           "_on_direct_tool_done", "_on_direct_tool_failed", "_sentence_fits"}
WANT_MOD = {"_header_sentence", "_direct_tool_status", "_default_phrase", "_state_phrases"}
body = []
for n in ast.walk(tree):
    if isinstance(n, ast.FunctionDef) and n.name in (WANT_FN | WANT_MOD):
        body.append(n)
for n in tree.body:
    if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") in (
            "_DONE_PHRASE", "_STOPPING_PHRASE", "_HALTING_PHRASE", "_VERSION",
            "_TOOL_DONE_STATUSES", "_TOOL_ERROR_STATUSES"):
        body.append(n)
ns = {"t": t, "frozenset": frozenset}
exec(compile(ast.Module(body=body, type_ignores=[]), "panel", "exec"), ns)


class Widget:
    def __init__(self): self.text = None; self.tip = None
    def setText(self, v): self.text = v
    def setToolTip(self, v): self.tip = v


class Call:
    started = 0
    def __init__(self, name, args, parent=None):
        self.name = name; self.running = True
        self.finished_ok = types.SimpleNamespace(connect=lambda f: None)
        self.failed = types.SimpleNamespace(connect=lambda f: None)
    def isRunning(self): return self.running
    def start(self): Call.started += 1


class Panel:
    """A fake self with only what the probed methods touch."""
    def __init__(self, fits=lambda s: len(s) <= 13):
        self._header_status = Widget()
        self._mark = types.SimpleNamespace(state=None,
                                           set_state=lambda s: setattr(self._mark, "state", s))
        self._chat = types.SimpleNamespace(append_system_message=lambda m: self.said.append(m))
        self.said = []
        self._direct_call = None
        self._direct_phrase = None
        self._was_busy = False
        self._stopping = False
        self._turn_state = "idle"
        self._conn_state = "disconnected"
        self._gate_stale_reason = None
        self._last_tool = None
        self._last_tool_node = "/obj/geo1/topnet1"
        self._fits = fits
    # bind probed methods
    def __getattr__(self, name):
        if name in ns and name in WANT_FN:
            return lambda *a, **k: ns[name](self, *a, **k)
        raise AttributeError(name)
    def _sentence_fits(self, text): return self._fits(text)
    def _render_token_state(self): pass


def rail(p):
    return (p._header_status.text, p._header_status.tip, p._mark.state)


print("### TREE:", TREE)
print("### _HALTING_PHRASE present:", "_HALTING_PHRASE" in ns)

# --- PROBE A: emergency halt clicked while a cancel-cook is in flight -------
ns_call = ns.setdefault("DirectToolCall", Call)
ns["DirectToolCall"] = Call
Call.started = 0
p = Panel()
p._on_cancel_cook()
print("[A] after Cancel cook click   rail=%r tip=%r   calls_started=%d"
      % (rail(p)[0], rail(p)[1], Call.started))
# the cancel thread is still running; artist now hits EMERGENCY HALT
p._direct_call.running = True
before = Call.started
p._on_emergency_halt()
print("[A] after EMERGENCY HALT      rail=%r tip=%r   calls_started=%d (delta %d)"
      % (rail(p)[0], rail(p)[1], Call.started, Call.started - before))
print("[A] halt actually dispatched :", Call.started - before == 1)
# tick: the context tick re-states the held sentence
p._render_state()
print("[A] after one 2000ms tick     rail=%r tip=%r" % (rail(p)[0], rail(p)[1]))
# the CANCEL (not the halt) reports back
p._on_direct_tool_done("tops_cancel_cook", {"status": "ok"})
print("[A] cancel reports back       rail=%r tip=%r mark=%r" % rail(p))
print("[A] chat said                :", p.said)

# --- PROBE B: the failure handler's hardcoded 'done' through the new fallback
for label, fits in (("fits=True ", lambda s: True), ("fits=False", lambda s: False)):
    q = Panel(fits=fits)
    q._on_direct_tool_failed("tops_cancel_cook", "server unreachable")
    print("[B] %s  failure handler -> rail=%r tip=%r mark=%r"
          % (label, q._header_status.text, q._header_status.tip, q._mark.state))

# --- PROBE C: hold is taken BEFORE the call is constructed ------------------
class Boom(Call):
    def __init__(self, *a, **k): raise RuntimeError("thread construction failed")
ns["DirectToolCall"] = Boom
r = Panel()
try:
    r._on_cancel_cook()
except Exception as e:
    print("[C] _run_direct_tool raised :", type(e).__name__, e)
print("[C] held phrase after raise  :", r._direct_phrase)
r._conn_state = "disconnected"
r._render_state()
print("[C] rail after the next tick :", rail(r)[0], "| tip:", rail(r)[1])
