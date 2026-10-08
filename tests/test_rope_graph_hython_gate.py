"""The rope gate refuses, in code, a new hython script that imports synapse without the stub.

Post-demo loop 3 shipped the HYTHON rule as prompt text plus a referee DROP line, so the only
thing standing between a fixer's bare `import synapse.cv` under hython and a kept commit was a
model. graph.py's own law 3 says keep or discard is decided by checks, never by a model; these
tests pin the check.

No git runs and no model starts: `_changed`, `_free_slot` and `_dropped_logging` (the three
that call git) are replaced, rope.verdict is a recorder, and every file lives in tmp_path.
"""
import importlib.util
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH = os.path.join(REPO, "harness", "rope", "graph.py")

BARE = "import hou\nimport synapse.cv\n\nprint(synapse.cv)\n"
STUBBED = ("import sys, types\nimport hou\n"
           "pkg = types.ModuleType(\"synapse\"); pkg.__path__ = [\"python/synapse\"]\n"
           "sys.modules.setdefault(\"synapse\", pkg)\nimport synapse.cv\n")
NAMED = '"""Run me with hython."""\nfrom synapse.cv import probe\n'
PLAIN = "from synapse.cv import probe\n\ndef test_probe():\n    assert probe\n"
MODULE = "import hou\nfrom synapse.core import x\n\nVALUE = 1\n"


def _write(path, text):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(str(path), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


@pytest.fixture
def run_gate(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("_rope_graph_hython_gate", GRAPH)
    G = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(G)
    slot, root = tmp_path / "slot", tmp_path / "root"
    root.mkdir()
    calls = []

    def verdict(task):
        calls.append(task)
        return False, [], ["verdict reached"]

    monkeypatch.setattr(G.rope, "verdict", verdict)
    monkeypatch.setattr(G.rope, "revert", lambda task, existed: None)
    monkeypatch.setattr(G, "_free_slot", lambda st, s, changed: None)
    monkeypatch.setattr(G, "_dropped_logging", lambda s, changed, card: [])   # it runs git diff

    def go(rel, text, code="??"):
        _write(slot / rel, text)
        monkeypatch.setattr(G, "_changed", lambda tree, declared=(): [(code, rel)])
        st = {"root": str(root)}
        it = {"id": "F01", "slot": str(slot), "files": [rel], "title": "t", "change": "c"}
        return G.gate(st, it), calls

    return go


def test_a_new_hython_script_with_a_bare_synapse_import_is_refused(run_gate):
    """Fails on the old graph: nothing in gate() looked at hython imports, so it reached rope.verdict."""
    (v, note), calls = run_gate("scripts/measure_cv.py", BARE)
    assert v == "hython_bare"
    assert "scripts/measure_cv.py" in note
    assert calls == [], "the gate ran the tests on a file it should have refused"


def test_a_script_that_only_names_hython_is_refused_too(run_gate):
    """The loop-2 measurement imported synapse.cv under hython without importing hou."""
    (v, _), calls = run_gate("tests/test_cv_hython_probe.py", NAMED)
    assert v == "hython_bare" and calls == []


def test_the_taught_stub_passes_the_check(run_gate):
    (v, note), calls = run_gate("scripts/measure_cv.py", STUBBED)
    assert v == "fail" and note == "verdict reached"
    assert len(calls) == 1


def test_a_plain_test_with_no_hython_signal_is_not_flagged(run_gate):
    (v, _), calls = run_gate("tests/test_new_probe.py", PLAIN)
    assert v == "fail" and len(calls) == 1


def test_an_edited_package_module_is_not_flagged(run_gate):
    """Modules inside python/synapse import hou and synapse.<sub> by right; only NEW files are read."""
    (v, _), calls = run_gate("python/synapse/cv/probe.py", MODULE, code=" M")
    assert v == "fail" and len(calls) == 1


def test_a_new_package_module_is_not_flagged(run_gate):
    """A new module inside python/synapse runs after the package is loaded; a stub there would be wrong."""
    guarded = "try:\n    import hou\nexcept ImportError:\n    hou = None\nfrom synapse.core import x\n"
    (v, _), calls = run_gate("python/synapse/cv/helper.py", guarded)
    assert v == "fail" and len(calls) == 1


def test_the_referee_criterion_stays_beside_the_check():
    """The gate is added to the referee's DROP line, never a replacement for it."""
    with open(GRAPH, encoding="utf-8") as f:
        text = f.read()
    drop = text.split("DROP a commit when", 1)[1].split("Otherwise KEEP", 1)[0]
    assert "hython" in drop and "stub" in drop
