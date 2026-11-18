"""Isolation tests for the SIM plane.

The property: nothing on the runtime path may reach the SIM ledger, and the SIM
plane may not reach the held-out evaluation split. Today the first holds by
construction — no import path exists — and nothing asserts it. These tests turn
an accident into a property.

Each test also proves it bites: the same checker, run over a deliberately
poisoned snippet, must report a violation. A fence that cannot fail is not a
fence.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# Files and trees that constitute the runtime path. If any of these grows an
# import of the metrology plane, the isolation claim in the audit is false.
RUNTIME_SOURCES = (
    "mcp_server.py",
    "python/synapse",
)
PLANE_MODULES = ("harness.sim", "harness/sim")

# The SIM plane may not reach the held-out evaluation machinery.
HELDOUT_MODULES = ("synapse.loop.light_gate", "light_gate")


def _imports_in(path: Path) -> set[str]:
    """Every module name imported by a Python file, absolute form."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def _violations(paths, forbidden: tuple[str, ...]) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for path in paths:
        for name in _imports_in(path):
            if any(name == f or name.startswith(f + ".") for f in forbidden):
                hits.append((str(path), name))
    return hits


def _runtime_files() -> list[Path]:
    files: list[Path] = []
    for entry in RUNTIME_SOURCES:
        target = REPO / entry
        if target.is_file():
            files.append(target)
        elif target.is_dir():
            files.extend(sorted(target.rglob("*.py")))
    return files


def _plane_files() -> list[Path]:
    return sorted((REPO / "harness" / "sim").glob("*.py"))


class TestRuntimeCannotReachThePlane:
    def test_no_runtime_module_imports_the_sim_plane(self):
        hits = _violations(_runtime_files(), PLANE_MODULES)
        assert hits == [], f"runtime imports the metrology plane: {hits}"

    def test_the_checker_bites(self, tmp_path: Path):
        poisoned = tmp_path / "poisoned.py"
        poisoned.write_text("from harness.sim import store\n", encoding="utf-8")
        assert _violations([poisoned], PLANE_MODULES) != []

    def test_the_checker_accepts_a_clean_file(self, tmp_path: Path):
        clean = tmp_path / "clean.py"
        clean.write_text("import json\nfrom pathlib import Path\n", encoding="utf-8")
        assert _violations([clean], PLANE_MODULES) == []


class TestPlaneCannotReachHeldOut:
    def test_no_plane_module_imports_the_heldout_split(self):
        hits = _violations(_plane_files(), HELDOUT_MODULES)
        assert hits == [], f"SIM plane imports the held-out machinery: {hits}"

    def test_the_checker_bites_on_the_heldout_module(self, tmp_path: Path):
        poisoned = tmp_path / "poisoned.py"
        poisoned.write_text("from synapse.loop import light_gate\n", encoding="utf-8")
        assert _violations([poisoned], HELDOUT_MODULES) != []


class TestHeldOutSplitInLightGate:
    """`loop/light_gate.py` — the split is data, and the proposer view excludes it.

    The custody ledger keeps every OBSERVED row because it is an append-only audit
    chain. What the fix adds is the split: each round names its run ids, and the
    only proposer-facing view is `training_visible_runs`, which excludes any run
    that was ever held out.
    """

    def _result(self) -> dict:
        observations = [{"run_id": f"r{i}"} for i in range(12)]
        return {
            "observations": observations,
            "calibration_rounds": [
                {"training": 6, "fresh_heldout": 6,
                 "training_run_ids": [f"r{i}" for i in range(6)],
                 "holdout_run_ids": [f"r{i}" for i in range(6, 12)]},
            ],
        }

    def test_the_plane_can_read_the_split_helpers(self):
        sys.path.insert(0, str(REPO / "python"))
        from synapse.loop import light_gate

        assert callable(light_gate.training_visible_runs)
        assert callable(light_gate.holdout_runs)
        assert callable(light_gate.split_run_ids)

    def test_split_run_ids_takes_the_tail_as_holdout(self):
        sys.path.insert(0, str(REPO / "python"))
        from synapse.loop.light_gate import split_run_ids

        proofs = [{"run_id": f"r{i}"} for i in range(12)]
        train, holdout = split_run_ids(proofs, holdout=6)
        assert train == [f"r{i}" for i in range(6)]
        assert holdout == [f"r{i}" for i in range(6, 12)]

    def test_training_view_excludes_every_heldout_run(self):
        sys.path.insert(0, str(REPO / "python"))
        from synapse.loop.light_gate import holdout_runs, training_visible_runs

        result = self._result()
        assert set(holdout_runs(result)) == {f"r{i}" for i in range(6, 12)}
        visible = set(training_visible_runs(result))
        assert visible == {f"r{i}" for i in range(6)}
        assert not visible & set(holdout_runs(result))

    def test_a_run_held_out_in_any_round_stays_hidden(self):
        sys.path.insert(0, str(REPO / "python"))
        from synapse.loop.light_gate import training_visible_runs

        result = self._result()
        result["calibration_rounds"].append(
            {"training": 18, "fresh_heldout": 6,
             "training_run_ids": [f"r{i}" for i in range(12)] + ["r12", "r13", "r14", "r15", "r16", "r17"],
             "holdout_run_ids": ["r12", "r13", "r14", "r15", "r16", "r17"]})
        result["observations"].extend({"run_id": f"r{i}"} for i in range(12, 18))
        visible = training_visible_runs(result)
        # r6..r11 were held out in round 1; a later round calling them training
        # does not make their outcomes visible.
        assert not set(visible) & {f"r{i}" for i in range(6, 12)}
        assert not set(visible) & {f"r{i}" for i in range(12, 18)}


class TestBenchSplitManifest:
    """`harness/bench/manifest.json` — an explicit evolve/holdout split."""

    def _manifest(self) -> dict:
        import json

        return json.loads((REPO / "harness" / "bench" / "manifest.json").read_text(encoding="utf-8"))

    def test_split_exists_and_partitions_the_tasks(self):
        manifest = self._manifest()
        split = manifest["split"]
        ids = {task["id"] for task in manifest["tasks"]}
        evolve, holdout = set(split["evolve"]), set(split["holdout"])
        assert evolve and holdout
        assert not evolve & holdout, "a task cannot be both evolved against and held out"
        assert evolve | holdout == ids, "every task must be on one side of the split"

    def test_holdout_spans_more_than_one_category(self):
        manifest = self._manifest()
        by_id = {task["id"]: task for task in manifest["tasks"]}
        categories = {by_id[tid]["category"] for tid in manifest["split"]["holdout"]}
        assert len(categories) >= 2, f"holdout covers only {categories}"

    def test_the_ceiling_task_is_evolved_against_not_held_out(self):
        manifest = self._manifest()
        assert "exp-01" in manifest["split"]["evolve"]

    def test_every_listed_id_exists(self):
        manifest = self._manifest()
        ids = {task["id"] for task in manifest["tasks"]}
        split = manifest["split"]
        assert set(split["evolve"]) <= ids and set(split["holdout"]) <= ids


class TestThePlaneIsNotOnTheRuntimePath:
    def test_panel_context_assembly_does_not_import_harness_at_all(self):
        """Broader than SIM: the prompt builder must not pull in the harness tree."""
        system_prompt = REPO / "python" / "synapse" / "panel" / "system_prompt.py"
        assert system_prompt.is_file()
        hits = _violations([system_prompt], ("harness",))
        assert hits == []

    def test_mcp_server_does_not_import_harness(self):
        mcp = REPO / "mcp_server.py"
        if not mcp.is_file():  # pragma: no cover - layout guard
            pytest.skip("mcp_server.py not present in this checkout")
        assert _violations([mcp], ("harness",)) == []
