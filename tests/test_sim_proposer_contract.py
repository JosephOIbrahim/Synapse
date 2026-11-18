"""Phase 3 contract tests: candidate validation, the two hooks, and stage 2.

The proposer contract is the thing that makes a candidate falsifiable, so it is
tested by refusal: a candidate missing a cluster, a prediction, a scope, a target
or a diff must not pass. The hooks are tested both ways — a known negative cannot
be adopted or cleared, and with no ledger supplied nothing changes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "harness" / "harness2", REPO / "harness" / "jev"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from harness.sim.propose import rejected_ids, validate_candidate, validate_candidates  # noqa: E402
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
from harness.sim.select import SelectorPolicy, finalize, verdict_for  # noqa: E402
from harness.sim.setting import SettingFingerprint  # noqa: E402
from harness.sim.store import SIMStore  # noqa: E402

SIG = "proposer contract: candidate cites no failure it addresses"
HASH_A = "a" * 64
HASH_B = "b" * 64


def _setting(model: str = "claude-opus-5-5") -> SettingFingerprint:
    return SettingFingerprint(model_id=model, eval_split_id="bench-12/evo", harness_hash=HASH_A)


def _cluster() -> ProblemCluster:
    return ProblemCluster(
        cluster_id=cluster_id_for(SIG),
        symptom_signature=SIG,
        root_cause_diagnosis="proposals arrive without a failure to attach to",
        status=ClusterStatus.OPEN,
        created_utc="2026-11-18T12:00:00+00:00",
    )


def _candidate(**overrides) -> dict:
    base = {
        "id": "cand-1",
        "cluster_id": _cluster().cluster_id,
        "edit_scope": EditScope.CONTEXT_ORCHESTRATION.value,
        "target_artifact": "python/synapse/core/tool_results.py",
        "diff_patch": CANDIDATE_DIFF,
        "ex_ante_prediction": {
            "expected_delta": 0.04,
            "target_metric": "bench.valid_json_rate",
            "max_regression": 0.01,
        },
    }
    base.update(overrides)
    return base


@pytest.fixture()
def store(tmp_path: Path) -> SIMStore:
    s = SIMStore(tmp_path / "ledger")
    s.declare_cluster(_cluster())
    return s


CANDIDATE_DIFF = "--- a\n+++ b\n@@\n-96_000\n+120_000\n"
OTHER_DIFF = "--- a\n+++ b\n@@\n-raise\n+return\n"


def _negative_attempt(cluster: ProblemCluster, target: str, setting: SettingFingerprint, attempt_id: str,
                      diff: str = CANDIDATE_DIFF) -> AttemptRecord:
    return AttemptRecord(
        attempt_id=attempt_id,
        cluster_id=cluster.cluster_id,
        round_id="round-1",
        parent_harness_hash=HASH_A,
        candidate_harness_hash=HASH_B,
        setting=setting,
        edit_scope=EditScope.CONTEXT_ORCHESTRATION,
        target_artifact=target,
        diff_patch=diff,
        edit_rationale="raised the cap without rebinding the reader",
        ex_ante_prediction=Prediction(expected_delta=0.4, target_metric="bench.valid_json_rate", max_regression=0.0),
        ex_post_observation=Observation(measured_delta=-0.02),
        selector_verdict=SelectorVerdict.REMOVE,
        created_utc="2026-11-18T12:10:00+00:00",
    )


class TestCandidateContract:
    def test_a_complete_candidate_passes(self):
        result = validate_candidate(_candidate())
        assert result.ok, result.reasons
        assert result.cluster_id == _cluster().cluster_id
        assert result.edit_scope is EditScope.CONTEXT_ORCHESTRATION

    def test_no_cluster_is_refused(self):
        result = validate_candidate(_candidate(cluster_id=None))
        assert not result.ok
        assert any("cluster" in reason for reason in result.reasons)

    def test_no_prediction_is_refused(self):
        result = validate_candidate(_candidate(ex_ante_prediction=None))
        assert not result.ok
        assert any("prediction" in reason for reason in result.reasons)

    def test_no_scope_is_refused(self):
        result = validate_candidate(_candidate(edit_scope=None))
        assert not result.ok
        assert any("scope" in reason for reason in result.reasons)

    def test_unknown_scope_is_refused(self):
        result = validate_candidate(_candidate(edit_scope="PROMPT_VIBES"))
        assert not result.ok

    def test_no_target_artifact_is_refused(self):
        result = validate_candidate(_candidate(target_artifact=None))
        assert not result.ok
        assert any("target" in reason for reason in result.reasons)

    def test_no_diff_is_refused(self):
        result = validate_candidate(_candidate(diff_patch=""))
        assert not result.ok

    def test_a_new_cluster_can_be_declared(self):
        result = validate_candidate(
            _candidate(
                cluster_id=None,
                new_cluster={"symptom_signature": "fresh symptom", "root_cause_diagnosis": "unknown yet"},
            )
        )
        assert result.ok, result.reasons
        assert result.cluster_id == cluster_id_for("fresh symptom")
        assert result.new_cluster is not None


class TestClusterCitation:
    """The contract's first rule: cite a cluster that exists."""

    def test_a_malformed_cluster_id_is_refused(self):
        result = validate_candidate(_candidate(cluster_id="not-a-cluster"))
        assert not result.ok
        assert any("is not a cluster id" in reason for reason in result.reasons)

    def test_a_well_formed_but_undeclared_cluster_is_refused(self, store: SIMStore):
        result = validate_candidate(_candidate(cluster_id="pc-" + "0" * 16), store=store)
        assert not result.ok
        assert any("not declared in the ledger" in reason for reason in result.reasons)

    def test_a_declared_cluster_passes(self, store: SIMStore):
        result = validate_candidate(_candidate(), store=store)
        assert result.ok, result.reasons


class TestDuplicateRule:
    def test_a_known_negative_under_the_same_setting_is_refused(self, store: SIMStore):
        target = "python/synapse/core/tool_results.py"
        store.append(_negative_attempt(_cluster(), target, _setting(), "att-prior"))
        result = validate_candidate(_candidate(), store=store, setting=_setting())
        assert not result.ok
        assert any("known negative" in reason for reason in result.reasons)

    def test_a_different_edit_on_the_same_artifact_is_allowed(self, store: SIMStore):
        """The rule is about an edit, not a file.

        A rejected patch must not block every future change to the same
        artifact - which is what a file-scoped rule did.
        """
        target = "python/synapse/core/tool_results.py"
        store.append(_negative_attempt(_cluster(), target, _setting(), "att-prior", diff=OTHER_DIFF))
        result = validate_candidate(_candidate(), store=store, setting=_setting())
        assert result.ok, result.reasons

    def test_the_same_edit_under_a_different_model_is_not_refused(self, store: SIMStore):
        target = "python/synapse/core/tool_results.py"
        store.append(_negative_attempt(_cluster(), target, _setting("claude-sonnet-5-5"), "att-prior"))
        result = validate_candidate(_candidate(), store=store, setting=_setting("claude-opus-5-5"))
        assert result.ok, result.reasons

    def test_validation_never_writes(self, store: SIMStore):
        before = {p.name: p.read_bytes() for p in store.root.glob("*")}
        validate_candidate(_candidate(), store=store, setting=_setting())
        after = {p.name: p.read_bytes() for p in store.root.glob("*")}
        assert before == after

    def test_batch_helpers(self, store: SIMStore):
        results = validate_candidates([_candidate(), _candidate(id="cand-2", cluster_id=None)], store=store)
        assert set(results) == {"cand-1", "cand-2"}
        rejects = rejected_ids(results)
        assert "cand-2" in rejects and "cand-1" not in rejects


class TestComposeHook:
    """harness/harness2/compositor.py — a ledger refusal cannot be adopted."""

    def _answers(self, choice: str = "cand-1", conf: float = 0.9, strength: float = 3.0,
                 probe: float = 0.8, composable: float = 0.8) -> dict:
        return {
            "choices": {"adopt": {"choice": choice, "confidence": conf, "probabilities": {}}},
            "scores": {"strength_cand-1": {"score": strength}},
            "nouls": {"probe_cand-1": {"noul": probe}, "composable_cand-1": {"noul": composable}},
        }

    _POLICY = {
        "adopt_min_confidence": 0.6,
        "min_strength": 2,
        "min_probe_support": 0.6,
        "min_composable": 0.5,
        "max_adoptions": 3,
        "fallback": "NO ADOPTION",
    }

    def test_without_a_ledger_nothing_changes(self):
        import compositor as C

        decision = C.decide_compose(self._answers(), [_candidate()], self._POLICY)
        assert [c["id"] for c in decision["adopted"]] == ["cand-1"]
        assert "sim_rejected" not in decision

    def test_a_refused_candidate_cannot_be_adopted(self):
        import compositor as C

        decision = C.decide_compose(
            self._answers(), [_candidate()], self._POLICY,
            sim_rejects={"cand-1": ["known negative under this setting"]},
        )
        assert decision["adopted"] == []
        assert "sim:" in decision["reason"]
        assert decision["sim_rejected"]["cand-1"] == ["known negative under this setting"]

    def _two_candidates(self) -> list[dict]:
        return [
            _candidate(id="cand-1"),
            _candidate(id="cand-2", target_artifact="harness/bench/prompts/p.md"),
        ]

    def _two_answers(self) -> dict:
        answers = self._answers(choice="cand-1")
        answers["scores"]["strength_cand-2"] = {"score": 3.0}
        answers["nouls"]["probe_cand-2"] = {"noul": 0.8}
        answers["nouls"]["composable_cand-2"] = {"noul": 0.8}
        return answers

    def test_a_refused_secondary_cannot_ride_in_beside_a_clean_primary(self):
        """The refusal applies to every adoption, not only to Jev's primary.

        Without this check a refused candidate was co-adopted and the decision
        read adopted=[cand-1, cand-2], which falsified the plane's own claim
        that a refused candidate cannot be adopted.
        """
        import compositor as C

        decision = C.decide_compose(
            self._two_answers(), self._two_candidates(), self._POLICY,
            sim_rejects={"cand-2": ["known negative under this setting"]},
        )
        assert [c["id"] for c in decision["adopted"]] == ["cand-1"]
        assert "cand-2: refused by the SIM ledger" in decision["reason"]

    def test_a_clean_secondary_is_still_adopted(self):
        import compositor as C

        decision = C.decide_compose(self._two_answers(), self._two_candidates(), self._POLICY)
        assert [c["id"] for c in decision["adopted"]] == ["cand-1", "cand-2"]


class TestScreenHook:
    """harness/jev/jev_screen.py — a known negative cannot CLEAR."""

    _POLICY = {
        "fallback_verdict": "REFEREE",
        "flag_does_not_support_min": 0.6,
        "weak_below_support": 0.6,
        "clear_max_self_contradiction": 0.2,
        "clear_max_crux_need": 0.4,
    }

    def _clear_answers(self) -> dict:
        return {
            "choices": {"acc_0": {"choice": "supports", "confidence": 0.9,
                                  "probabilities": {"supports": 0.9}}},
            "nouls": {"self_contradiction": {"noul": 0.0}},
            "scores": {"crux_need": {"score": 0.1}},
        }

    def test_clear_without_a_ledger(self):
        import jev_screen as S

        assert S.decide(1, self._clear_answers(), self._POLICY)["verdict"] == "CLEAR"

    def test_a_known_negative_downgrades_clear_to_referee(self):
        import jev_screen as S

        d = S.decide(1, self._clear_answers(), self._POLICY, sim_rejects=["att-prior"])
        assert d["verdict"] == "REFEREE"
        assert d["sim_rejects"] == ["att-prior"]

    def test_flag_is_never_softened(self):
        import jev_screen as S

        answers = self._clear_answers()
        answers["choices"]["acc_0"]["probabilities"] = {"does_not_support": 0.9, "supports": 0.1}
        answers["choices"]["acc_0"]["choice"] = "supports"
        d = S.decide(1, answers, self._POLICY, sim_rejects=["att-prior"])
        assert d["verdict"] == "FLAG"


class TestStageTwo:
    def _prediction(self, expected: float = 0.1, max_regression: float = 0.0) -> Prediction:
        return Prediction(expected_delta=expected, target_metric="bench", max_regression=max_regression)

    def test_no_observation_means_screened_out(self):
        assert verdict_for(self._prediction(), None) is SelectorVerdict.REJECTED_SCREENING

    def test_no_improvement_is_removed(self):
        assert verdict_for(self._prediction(), Observation(measured_delta=0.0)) is SelectorVerdict.REMOVE

    def test_worse_than_the_regression_bound_is_removed(self):
        obs = Observation(measured_delta=-0.2)
        assert verdict_for(self._prediction(max_regression=0.1), obs) is SelectorVerdict.REMOVE

    def test_named_regression_with_zero_bound_is_removed(self):
        obs = Observation(measured_delta=0.2, regressions=("latency",))
        assert verdict_for(self._prediction(max_regression=0.0), obs) is SelectorVerdict.REMOVE

    def test_hitting_half_the_prediction_is_retained(self):
        obs = Observation(measured_delta=0.06)
        assert verdict_for(self._prediction(expected=0.1), obs) is SelectorVerdict.RETAIN

    def test_missing_the_prediction_is_revised(self):
        obs = Observation(measured_delta=0.02)
        assert verdict_for(self._prediction(expected=0.1), obs) is SelectorVerdict.REVISE

    def test_beating_an_incumbent_replaces_it(self):
        obs = Observation(measured_delta=0.2)
        assert verdict_for(self._prediction(expected=0.1), obs, incumbent_delta=0.1) is SelectorVerdict.REPLACE

    def test_finalize_is_immutable_and_sets_the_verdict(self):
        record = AttemptRecord(
            attempt_id="att-1",
            cluster_id=_cluster().cluster_id,
            round_id="round-1",
            parent_harness_hash=HASH_A,
            candidate_harness_hash=HASH_B,
            setting=_setting(),
            edit_scope=EditScope.INVARIANT_GATE,
            target_artifact="python/synapse/panel/worker_policy.py",
            diff_patch="--- a\n+++ b\n",
            edit_rationale="tighten the deny list",
            ex_ante_prediction=self._prediction(),
            selector_verdict=SelectorVerdict.REVISE,
            created_utc="2026-11-18T12:00:00+00:00",
            ex_post_observation=Observation(measured_delta=0.05),
        )
        final = finalize(record, Observation(measured_delta=0.2), policy=SelectorPolicy())
        assert final.selector_verdict is SelectorVerdict.RETAIN
        assert record.selector_verdict is SelectorVerdict.REVISE  # the input is untouched
