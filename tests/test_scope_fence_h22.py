"""H22 scope-fence — the dead-zone rigging PHRASE scan grafted into check_no_rigging_drift.

House pattern (mirrors tests/test_r_track.py:22-26): importlib-load checks.py under its own
alias (the harness verify dir is not a package), plant a SYNTHETIC worktree under tmp_path,
call the guardrail by its FROZEN name. Every rejection fixture plants an emitted node-type whose
type_name literally carries ONE dead phrase; the positive fixture plants a splat-GEOMETRY type
('gaussiansplat') that must stay IN scope — bare 'splat' never fires (COLLISION LAW).

Each fixture ALSO plants a VALID in-scope authoring_domains.json, so the allowlist clause passes
on its own — any ok:False therefore proves the new emitted-phrase clause fired, not the allowlist.
"""
import importlib.util
import json
import pathlib

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]
_CHECKS = _REPO / "harness" / "verify" / "checks.py"
_spec = importlib.util.spec_from_file_location("harness_checks_scope_fence", _CHECKS)
checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checks)

# the twelve H22 dead-zone rigging phrases the graft rejects (checks.py::check_no_rigging_drift)
DEAD_PHRASES = [
    "rig builder", "rig template", "biped retargeting", "mixamo retarget",
    "apex script", "ml deformer", "muscle transfer", "ragdoll",
    "splat rig", "splat capture", "guide deform", "short sculpt",
]


def _plant(root, rel, text):
    p = pathlib.Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _clean_authoring(wt):
    """VALID in-scope allowlist so the allowlist clause PASSES on its own."""
    _plant(wt, "python/synapse/server/authoring_domains.json",
           json.dumps({"domains": ["cop", "lop", "sop", "karma", "usd"]}))


def _emitted(wt, entries):
    _plant(wt, "python/synapse/cognitive/tools/data/emitted_node_types.json",
           json.dumps({"schema": "emitted_node_types/v1", "entries": entries}))


def _ctx(wt):
    return {"wt": str(wt), "hython": "", "mode": "A"}


@pytest.mark.parametrize("phrase", DEAD_PHRASES)
def test_dead_phrase_rejected(tmp_path, phrase):
    _clean_authoring(tmp_path)  # allowlist alone would pass -> False must come from the new clause
    _emitted(tmp_path, [{"category": "probe", "type_name": phrase}])
    res = checks.check_no_rigging_drift(_ctx(tmp_path))
    assert res["ok"] is False, f"{phrase!r} must fire the H22 rigging fence: {res!r}"
    assert phrase in res["detail"], f"detail must name the offending phrase: {res['detail']!r}"


def test_splat_geometry_in_scope(tmp_path):
    """Gaussian-splat GEOMETRY is IN scope; bare 'splat' must NOT fire (only 'splat rig' /
    'splat capture' do). Clean authoring_domains + no rig/capture token -> ok True."""
    _clean_authoring(tmp_path)
    _emitted(tmp_path, [{"category": "geo", "type_name": "gaussiansplat"}])
    res = checks.check_no_rigging_drift(_ctx(tmp_path))
    assert res["ok"] is True, f"splat geometry must stay in scope: {res!r}"
