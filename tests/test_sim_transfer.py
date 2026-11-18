"""Transfer-boundary tests.

The scenario the architecture names: switching the policy model must flag a
MODEL_SPECIFIC_REPAIR as PROVISIONAL_REVALIDATE, must leave a DOMAIN_HEURISTIC
alone when the split has not moved, and must keep an INVARIANT_GATE as an anchor
with its binding flagged for re-verification. Changing the split mirrors that.
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.sim import cli  # noqa: E402
from harness.sim.schema import (  # noqa: E402
    AttemptRecord,
    ClusterStatus,
    EditScope,
    Observation,
    Prediction,
    ProblemCluster,
    SelectorVerdict,
    cluster_id_for,
)
from harness.sim.setting import SettingFingerprint  # noqa: E402
from harness.sim.store import SIMStore  # noqa: E402
from harness.sim.transfer import (  # noqa: E402
    Disposition,
    TransferBoundaryController,
    TransferPolicy,
    revalidation_list,
)

SIG = "transfer boundary test: the same edit behaves differently after a switch"
HASH_A = "a" * 64
HASH_B = "b" * 64

SOURCE = SettingFingerprint(model_id="claude-opus-5-5", eval_split_id="bench-12/evo", harness_hash=HASH_A)
TARGET_MODEL = SettingFingerprint(model_id="claude-sonnet-5-5", eval_split_id="bench-12/evo", harness_hash=HASH_A)
TARGET_SPLIT = SettingFingerprint(model_id="claude-opus-5-5", eval_split_id="bench-12-eval", harness_hash=HASH_A)


def _cluster() -> ProblemCluster:
    return ProblemCluster(
        cluster_id=cluster_id_for(SIG),
        symptom_signature=SIG,
        root_cause_diagnosis="edits tuned to one setting fail on the next",
        status=ClusterStatus.OPEN,
        created_utc="2026-11-18T12:00:00+00:00",
    )


def _attempt(scope: EditScope, artifact: str, setting: SettingFingerprint, attempt_id: str,
             verdict: SelectorVerdict = SelectorVerdict.RETAIN, created: str = "2026-11-18T12:05:00+00:00") -> AttemptRecord:
    return AttemptRecord(
        attempt_id=attempt_id,
        cluster_id=_cluster().cluster_id,
        round_id="round-1",
        parent_harness_hash=HASH_A,
        candidate_harness_hash=HASH_B,
        setting=setting,
        edit_scope=scope,
        target_artifact=artifact,
        diff_patch="--- a\n+++ b\n@@\n-x\n+y\n",
        edit_rationale="because the failure said so",
        ex_ante_prediction=Prediction(expected_delta=0.1, target_metric="bench", max_regression=0.02),
        ex_post_observation=Observation(measured_delta=0.1),
        selector_verdict=verdict,
        created_utc=created,
    )


@pytest.fixture()
def store(tmp_path: Path) -> SIMStore:
    s = SIMStore(tmp_path / "ledger")
    s.declare_cluster(_cluster())
    s.append(_attempt(EditScope.INVARIANT_GATE, "python/synapse/panel/worker_policy.py", SOURCE, "att-gate"))
    s.append(_attempt(EditScope.MODEL_SPECIFIC_REPAIR, "python/synapse/panel/system_prompt.py", SOURCE, "att-repair"))
    s.append(_attempt(EditScope.DOMAIN_HEURISTIC, "harness/bench/recipes/a.yaml", SOURCE, "att-heuristic"))
    return s


class TestModelSwitch:
    def test_repair_becomes_provisional(self, store: SIMStore):
        plan = TransferBoundaryController(store).plan(SOURCE, TARGET_MODEL)
        repair = next(i for i in plan.items if i.attempt_id == "att-repair")
        assert repair.disposition is Disposition.PROVISIONAL_REVALIDATE
        assert plan.transition == {"model_changed": True, "split_changed": False, "harness_changed": False}

    def test_gate_stays_an_anchor_and_asks_for_a_binding_review(self, store: SIMStore):
        plan = TransferBoundaryController(store).plan(SOURCE, TARGET_MODEL)
        gate = next(i for i in plan.items if i.attempt_id == "att-gate")
        assert gate.disposition is Disposition.ANCHOR
        assert gate.binding_review is True

    def test_heuristic_is_carried_when_the_split_did_not_move(self, store: SIMStore):
        plan = TransferBoundaryController(store).plan(SOURCE, TARGET_MODEL)
        heuristic = next(i for i in plan.items if i.attempt_id == "att-heuristic")
        assert heuristic.disposition is Disposition.CARRIED

    def test_plan_requires_revalidation(self, store: SIMStore):
        plan = TransferBoundaryController(store).plan(SOURCE, TARGET_MODEL)
        assert plan.requires_revalidation
        assert [i.attempt_id for i in revalidation_list(plan)] == ["att-repair"]


class TestSplitSwitch:
    def test_heuristic_becomes_provisional(self, store: SIMStore):
        plan = TransferBoundaryController(store).plan(SOURCE, TARGET_SPLIT)
        heuristic = next(i for i in plan.items if i.attempt_id == "att-heuristic")
        assert heuristic.disposition is Disposition.PROVISIONAL_REVALIDATE

    def test_repair_is_carried_when_the_model_did_not_move(self, store: SIMStore):
        plan = TransferBoundaryController(store).plan(SOURCE, TARGET_SPLIT)
        repair = next(i for i in plan.items if i.attempt_id == "att-repair")
        assert repair.disposition is Disposition.CARRIED

    def test_gate_is_still_an_anchor(self, store: SIMStore):
        plan = TransferBoundaryController(store).plan(SOURCE, TARGET_SPLIT)
        gate = next(i for i in plan.items if i.attempt_id == "att-gate")
        assert gate.disposition is Disposition.ANCHOR


class TestBothChange:
    def test_both_volatile_scopes_are_flagged(self, store: SIMStore):
        plan = TransferBoundaryController(store).plan(SOURCE, SettingFingerprint(
            model_id="claude-sonnet-5-5", eval_split_id="bench-12-eval", harness_hash=HASH_A))
        flagged = {i.attempt_id for i in plan.items if i.disposition is Disposition.PROVISIONAL_REVALIDATE}
        assert flagged == {"att-repair", "att-heuristic"}


class TestNoChangeAndScope:
    def test_no_transition(self, store: SIMStore):
        plan = TransferBoundaryController(store).plan(SOURCE, SOURCE)
        assert plan.is_transition is False
        assert plan.requires_revalidation is False
        assert all(i.disposition is not Disposition.PROVISIONAL_REVALIDATE for i in plan.items)

    def test_only_retained_edits_are_inherited(self, store: SIMStore):
        store.append(_attempt(EditScope.MODEL_SPECIFIC_REPAIR, "python/synapse/panel/claude_worker.py",
                              SOURCE, "att-removed", verdict=SelectorVerdict.REMOVE))
        plan = TransferBoundaryController(store).plan(SOURCE, TARGET_MODEL)
        assert "att-removed" not in {i.attempt_id for i in plan.items}

    def test_the_latest_retained_edit_wins_per_artifact(self, store: SIMStore):
        store.append(_attempt(EditScope.MODEL_SPECIFIC_REPAIR, "python/synapse/panel/system_prompt.py",
                              SOURCE, "att-repair-2", created="2026-11-18T13:00:00+00:00"))
        plan = TransferBoundaryController(store).plan(SOURCE, TARGET_MODEL)
        repairs = [i for i in plan.items if i.target_artifact == "python/synapse/panel/system_prompt.py"]
        assert [i.attempt_id for i in repairs] == ["att-repair-2"]
        assert plan.superseded == ("att-repair",)

    def test_context_orchestration_is_carried_by_default_and_flaggable(self, store: SIMStore):
        store.append(_attempt(EditScope.CONTEXT_ORCHESTRATION, "harness/bench/prompts/p.md", SOURCE, "att-ctx"))
        default_plan = TransferBoundaryController(store).plan(SOURCE, TARGET_MODEL)
        ctx = next(i for i in default_plan.items if i.attempt_id == "att-ctx")
        assert ctx.disposition is Disposition.CARRIED

        widened = TransferBoundaryController(store, TransferPolicy(flag_context_on=frozenset({"model"})))
        ctx2 = next(i for i in widened.plan(SOURCE, TARGET_MODEL).items if i.attempt_id == "att-ctx")
        assert ctx2.disposition is Disposition.PROVISIONAL_REVALIDATE


class TestCli:
    def _argv(self, ledger: Path, to_model: str = "claude-sonnet-5-5", to_split: str = "bench-12/evo") -> list[str]:
        return [
            "transfer", "--ledger", str(ledger),
            "--from-model", SOURCE.model_id, "--from-split", SOURCE.eval_split_id,
            "--from-harness", SOURCE.harness_hash,
            "--to-model", to_model, "--to-split", to_split, "--to-harness", HASH_A,
            "--json",
        ]

    def test_json_plan_lists_the_flagged_repair(self, store: SIMStore):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cli.main(self._argv(store.root))
        assert rc == 0
        payload = json.loads(out.getvalue())
        flagged = [i for i in payload["items"] if i["disposition"] == "PROVISIONAL_REVALIDATE"]
        assert [i["attempt_id"] for i in flagged] == ["att-repair"]
        assert payload["requires_revalidation"] is True

    def test_no_change_exits_two(self, store: SIMStore):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cli.main(self._argv(store.root, to_model=SOURCE.model_id, to_split=SOURCE.eval_split_id))
        assert rc == 2

    def test_a_missing_ledger_exits_one(self, tmp_path: Path):
        import contextlib

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = cli.main(self._argv(tmp_path / "nope"))
        assert rc == 1
        assert "error:" in err.getvalue()
