"""Schema tests for the SIM ledger: identity, required fields, round-trip."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.sim.schema import (  # noqa: E402
    JSON_SCHEMA,
    SCHEMA_VERSION,
    AttemptRecord,
    ClusterStatus,
    EditScope,
    Observation,
    Prediction,
    ProblemCluster,
    SchemaError,
    SelectorVerdict,
    cluster_id_for,
    normalize_signature,
)
from harness.sim.setting import SettingFingerprint  # noqa: E402

SIG = "tool result truncated: 96k cap reached mid-JSON"
HASH_A = "a" * 64
HASH_B = "b" * 64


def _setting() -> SettingFingerprint:
    return SettingFingerprint(model_id="claude-opus-5-5", eval_split_id="bench-12/evo", harness_hash=HASH_A)


def _cluster(signature: str = SIG) -> ProblemCluster:
    return ProblemCluster(
        cluster_id=cluster_id_for(signature),
        symptom_signature=signature,
        root_cause_diagnosis="tool-result cap applied before JSON completion",
        status=ClusterStatus.OPEN,
        created_utc="2026-11-18T12:00:00+00:00",
    )


def _record(**overrides) -> AttemptRecord:
    base = dict(
        attempt_id="att-0001",
        cluster_id=cluster_id_for(SIG),
        round_id="round-1",
        parent_harness_hash=HASH_A,
        candidate_harness_hash=HASH_B,
        setting=_setting(),
        edit_scope=EditScope.CONTEXT_ORCHESTRATION,
        target_artifact="python/synapse/core/tool_results.py",
        diff_patch="--- a\n+++ b\n@@\n-96_000\n+120_000\n",
        edit_rationale="raise the cap so a mid-JSON result can complete",
        ex_ante_prediction=Prediction(
            expected_delta=0.04, target_metric="bench.valid_json_rate", max_regression=0.01
        ),
        ex_post_observation=Observation(measured_delta=0.03, latency_delta_s=-0.2, token_delta=140),
        selector_verdict=SelectorVerdict.RETAIN,
        created_utc="2026-11-18T12:05:00+00:00",
    )
    base.update(overrides)
    return AttemptRecord(**base)


class TestClusterIdentity:
    def test_id_is_deterministic(self):
        assert cluster_id_for(SIG) == cluster_id_for(SIG)

    def test_normalisation_collapses_case_and_whitespace(self):
        assert normalize_signature("  Tool   Result   TRUNCATED ") == "tool result truncated"
        assert cluster_id_for(" Tool  Result TRUNCATED ") == cluster_id_for("tool result truncated")

    def test_different_signatures_do_not_collide(self):
        assert cluster_id_for("a") != cluster_id_for("b")

    def test_cluster_rejects_mismatched_id(self):
        with pytest.raises(SchemaError):
            ProblemCluster(
                cluster_id="pc-" + "0" * 16,
                symptom_signature=SIG,
                root_cause_diagnosis="x",
                status=ClusterStatus.OPEN,
                created_utc="2026-11-18T12:00:00+00:00",
            )

    def test_empty_signature_refused(self):
        with pytest.raises(SchemaError):
            normalize_signature("   ")

    def test_cluster_id_rejects_a_trailing_newline(self):
        """`$` matches before a trailing newline; a shape check must use `\\Z`.

        With `$`, "pc-<16 hex>\\n" passed a check whose whole purpose is exact
        shape, so the id was accepted here and refused later by the store.
        """
        from harness.sim.schema import CLUSTER_ID_RE

        good = "pc-" + "0" * 16
        assert CLUSTER_ID_RE.match(good)
        assert CLUSTER_ID_RE.match(good + "\n") is None


class TestAttemptRecord:
    def test_round_trip(self):
        record = _record()
        again = AttemptRecord.from_dict(record.to_dict())
        assert again == record

    def test_target_artifact_is_required(self):
        with pytest.raises(SchemaError, match="target_artifact"):
            _record(target_artifact="")

    def test_scope_must_be_known(self):
        with pytest.raises((SchemaError, ValueError)):
            _record(edit_scope="SOMETHING_ELSE")

    def test_observation_required_unless_screened_out(self):
        with pytest.raises(SchemaError, match="ex_post_observation"):
            _record(ex_post_observation=None)

    def test_screened_out_candidate_needs_no_observation(self):
        record = _record(
            ex_post_observation=None,
            selector_verdict=SelectorVerdict.REJECTED_SCREENING,
        )
        assert record.ex_post_observation is None

    def test_harness_hashes_must_be_full(self):
        with pytest.raises(SchemaError, match="parent_harness_hash"):
            _record(parent_harness_hash="abc")

    def test_prediction_must_be_falsifiable(self):
        with pytest.raises(SchemaError):
            _record(ex_ante_prediction={"expected_delta": 1})

    def test_unknown_field_in_payload_is_ignored_not_trusted(self):
        payload = _record().to_dict()
        payload["selector_verdict"] = "NOT_A_VERDICT"
        with pytest.raises(SchemaError):
            AttemptRecord.from_dict(payload)


class TestJsonSchema:
    def test_required_fields_match_the_dataclass_contract(self):
        assert "target_artifact" in JSON_SCHEMA["required"]
        assert set(JSON_SCHEMA["properties"]["edit_scope"]["enum"]) == {s.value for s in EditScope}

    def test_schema_id_carries_the_version(self):
        assert SCHEMA_VERSION in JSON_SCHEMA["$id"]
