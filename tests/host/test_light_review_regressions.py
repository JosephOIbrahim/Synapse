"""Deterministic race/deadline controls on disposable H22, one process per case."""
from copy import deepcopy
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from .light_fixture import make_context, require_disposable_case
from .test_light_gate_matrix import calibration
from synapse.loop import light_gate as gate_source
from synapse.loop.light_custody import LightCustody
from synapse.loop.light_profile import LocalLightReferee
from synapse.loop.ports import LedgerPort
from synapse.loop.rcxi_light import LightRequest
from synapse.server.main_thread import run_on_main


def context():
    observer, lifecycle, backend, setup_txn, setup = make_context()
    assert setup.outcome == 'committed', setup.reason
    ledger = LedgerPort(Path(os.environ['SYNAPSE_LOOP_LEDGER_DIR']) / 'cancel-foreign-light')
    return lifecycle, backend, gate_source.HeadlessLightGate(backend=backend, lifecycle=lifecycle, ledger=ledger)


def save(name, data):
    path = Path(os.environ['SYNAPSE_LOG_DIR']).parent / name
    path.write_text(json.dumps(data, default=str, indent=2) + '\n', encoding='utf-8')


def test_cancel_during_actual_decision_persistence_restores_before_terminal():
    require_disposable_case('cancel_foreign')
    def qualify():
        lifecycle, backend, gate = context()
        measured = calibration(gate)
        assert measured.status == 'SUCCESS', measured.error_message
        before, revision = backend.snapshot(), lifecycle.discover().graph_revision
        real_append, real_evaluate = LightCustody.append, LocalLightReferee.evaluate
        fired = []
        # This isolates cancellation ordering from forecast variability. The
        # actual pure worker evaluates an explicit zero-residual counterfactual;
        # all host observation/custody/commit/undo paths remain real. It is not
        # evidence for the normal predictor's acceptance probability.
        def zero_residual(self, forecast, observed, profile):
            assert observed.invariant_violation == 0 and observed.task_loss <= profile.loss_tolerance
            return real_evaluate(self, observed, observed, profile)
        def persist_then_cancel(custody, kind, *args):
            acknowledgement = real_append(custody, kind, *args)
            if kind == 'DECISION' and args[-1].get('accepted') is True:
                fired.append(gate.cancel())
            return acknowledgement
        instance = lifecycle.discover()
        request = LightRequest(instance.instance_id, revision, 'key_exposure', 1.0)
        with patch.object(LocalLightReferee, 'evaluate', zero_residual), patch.object(LightCustody, 'append', persist_then_cancel):
            result = gate.run(request, run_id='cancel-during-decision-persistence', approved=True)
        report = {'scope': 'Actual disposable H22 with explicitly controlled pure zero-residual decision for deterministic cancellation race',
                  'result': result._asdict(), 'cancel_injected_after_durable_decision': bool(fired), 'cancel_returns': fired,
                  'exact_state_restored': backend.snapshot() == before, 'revision_before': revision, 'revision_after': lifecycle.discover().graph_revision}
        save('review-cancel-persistence.json', report)
        assert fired, 'The control must reach an accepted durable DECISION before cancelling'
        assert result.status == 'BLOCKED' and result.payload['outcome'] == 'CANCELLED_RESTORED'
        assert backend.snapshot() == before and lifecycle.discover().graph_revision == revision
    run_on_main(qualify, label='qualification:cancel during actual decision persistence')


@pytest.mark.parametrize('late', ('deadline', 'cancel'))
def test_final_calibration_publication_refuses_late_abort(late):
    require_disposable_case('cancel_foreign')
    def qualify():
        lifecycle, backend, gate = context()
        before, revision = backend.snapshot(), lifecycle.discover().graph_revision
        real_fit = gate_source.fit_observed_profile
        real_clock = gate_source.time.perf_counter_ns
        fired = []
        def fit_then_abort(**kwargs):
            profile = real_fit(**kwargs)  # retain real independent validation
            fired.append(True)
            if late == 'cancel':
                gate.cancel()
            return profile
        def clock():
            return real_clock() + (61_000_000_000 if fired and late == 'deadline' else 0)
        with patch.object(gate_source, 'fit_observed_profile', fit_then_abort), patch.object(gate_source.time, 'perf_counter_ns', clock):
            result = calibration(gate)
        report = {'scope': 'Actual restored H22 calibration; controlled late clock advance or cancellation after successful real fitting',
                  'injection': late, 'injected_after_successful_independent_fit': bool(fired), 'result': result._asdict(),
                  'profile_created': gate.profile is not None, 'exact_state_restored': backend.snapshot() == before,
                  'revision_before': revision, 'revision_after': lifecycle.discover().graph_revision}
        save('review-calibration-final-' + late + '.json', report)
        assert fired, 'The control must reach a successful independent fit before injecting the late abort'
        assert result.status == 'UNAVAILABLE' and gate.profile is None
        assert backend.snapshot() == before and lifecycle.discover().graph_revision == revision
    run_on_main(qualify, label='qualification:final calibration abort before publication')


@pytest.mark.parametrize('boundary', ('forecast', 'decision'))
def test_operation_deadline_crossed_during_durable_persistence(boundary):
    require_disposable_case('cancel_foreign')
    def qualify():
        lifecycle, backend, gate = context()
        measured = calibration(gate)
        assert measured.status == 'SUCCESS', measured.error_message
        before, revision = backend.snapshot(), lifecycle.discover().graph_revision
        real_append, real_evaluate = LightCustody.append, LocalLightReferee.evaluate
        real_clock, real_apply = gate_source.time.perf_counter_ns, backend.apply
        fired, applied = [], []
        def zero_residual(self, forecast, observed, profile):
            assert observed.invariant_violation == 0 and observed.task_loss <= profile.loss_tolerance
            return real_evaluate(self, observed, observed, profile)
        def persist_then_advance(custody, kind, *args):
            acknowledgement = real_append(custody, kind, *args)
            if ((boundary == 'forecast' and kind == 'FORECAST') or
                    (boundary == 'decision' and kind == 'DECISION' and args[-1].get('accepted') is True)):
                fired.append(True)
            return acknowledgement
        def clock():
            return real_clock() + (61_000_000_000 if fired else 0)
        def count_apply(operation):
            applied.append(operation.target)
            return real_apply(operation)
        instance = lifecycle.discover()
        request = LightRequest(instance.instance_id, revision, 'key_exposure', 1.0)
        backend.apply = count_apply
        try:
            with patch.object(LocalLightReferee, 'evaluate', zero_residual), patch.object(LightCustody, 'append', persist_then_advance), patch.object(gate_source.time, 'perf_counter_ns', clock):
                result = gate.run(request, run_id='deadline-during-' + boundary + '-persistence', approved=True)
        finally:
            backend.apply = real_apply
        report = {'scope': 'Actual disposable H22; real durable persistence then deterministic 61-second clock advance; explicit zero-residual pure decision',
                  'boundary': boundary, 'injected_after_durable_persistence': bool(fired), 'result': result._asdict(),
                  'actual_apply_calls': len(applied), 'exact_state_restored': backend.snapshot() == before,
                  'revision_before': revision, 'revision_after': lifecycle.discover().graph_revision}
        save('review-operation-deadline-' + boundary + '.json', report)
        assert fired, 'The control must pass actual persistence before advancing the clock'
        assert result.status == 'BLOCKED'
        if boundary == 'forecast':
            assert not applied, 'An expired durable forecast must not dispatch a host mutation'
        else:
            assert len(applied) == 1 and result.payload['outcome'] == 'DEADLINE_RESTORED'
        assert backend.snapshot() == before and lifecycle.discover().graph_revision == revision
    run_on_main(qualify, label='qualification:operation deadline after durable ' + boundary)


def test_source_drift_during_decision_persistence_quarantines_without_commit():
    require_disposable_case('cancel_foreign')
    def qualify():
        lifecycle, backend, gate = context()
        measured = calibration(gate)
        assert measured.status == 'SUCCESS', measured.error_message
        before, revision = backend.snapshot(), lifecycle.discover().graph_revision
        real_append, real_evaluate = LightCustody.append, LocalLightReferee.evaluate
        real_identity, real_undo = gate_source.source_identity, backend.perform_undo
        fired, undo_calls = [], []
        def zero_residual(self, forecast, observed, profile):
            assert observed.invariant_violation == 0 and observed.task_loss <= profile.loss_tolerance
            return real_evaluate(self, observed, observed, profile)
        def persist_then_drift(custody, kind, *args):
            acknowledgement = real_append(custody, kind, *args)
            if kind == 'DECISION' and args[-1].get('accepted') is True:
                fired.append(True)
            return acknowledgement
        def identity():
            return '0' * 64 if fired else real_identity()
        def count_undo():
            undo_calls.append(True)
            return real_undo()
        instance = lifecycle.discover()
        request = LightRequest(instance.instance_id, revision, 'key_exposure', 1.0)
        backend.perform_undo = count_undo
        try:
            with patch.object(LocalLightReferee, 'evaluate', zero_residual), patch.object(LightCustody, 'append', persist_then_drift), patch.object(gate_source, 'source_identity', identity):
                result = gate.run(request, run_id='source-drift-during-persistence', approved=True)
            after = backend.snapshot()
            retry = gate.run(request, run_id='retry-after-source-binding-restored', approved=True)
        finally:
            backend.perform_undo = real_undo
        report = {'scope': 'Actual disposable H22 persistence; deterministic source-identity seam change models on-disk drift without editing product files',
                  'injected_after_durable_decision': bool(fired), 'result': result._asdict(), 'retry_after_source_binding_restored': retry._asdict(),
                  'undo_calls': len(undo_calls), 'exact_state_restored': after == before,
                  'quarantined_state_preserved_on_retry': backend.snapshot() == after,
                  'revision_before': revision, 'revision_after': lifecycle.discover().graph_revision}
        save('review-source-persistence.json', report)
        assert fired
        assert result.status == 'UNAVAILABLE' and result.payload['outcome'] == 'QUARANTINED'
        assert not undo_calls and after != before
        assert lifecycle.discover().graph_revision == revision
        assert retry.status == 'UNAVAILABLE' and backend.snapshot() == after
    run_on_main(qualify, label='qualification:source drift during actual decision persistence')


@pytest.mark.parametrize('boundary', ('forecast', 'calibration_plan'))
@pytest.mark.parametrize('drift', ('source', 'revision'))
def test_certified_bindings_are_not_adopted_after_plan_persistence(boundary, drift):
    require_disposable_case('cancel_foreign')
    def qualify():
        from dataclasses import replace
        lifecycle, backend, gate = context()
        if boundary == 'forecast':
            measured = calibration(gate)
            assert measured.status == 'SUCCESS', measured.error_message
        before = backend.snapshot()
        original_metadata = deepcopy(lifecycle.discover())
        revision = original_metadata.graph_revision
        original_dependencies = deepcopy(dict(backend.dependencies()))
        expected_metadata = (replace(original_metadata, graph_revision=revision + 1)
                             if drift == 'revision' else deepcopy(original_metadata))
        drift_source = '0' * 64
        expected_dependencies = deepcopy(original_dependencies)
        if drift == 'source':
            expected_dependencies['source_sha256'] = drift_source
        real_append, real_identity = LightCustody.append, gate_source.source_identity
        real_apply, real_evaluate = backend.apply, LocalLightReferee.evaluate
        fired, applied = [], []
        def identity():
            return drift_source if fired and drift == 'source' else real_identity()
        def zero_residual(self, forecast, observed, profile):
            assert observed.invariant_violation == 0 and observed.task_loss <= profile.loss_tolerance
            return real_evaluate(self, observed, observed, profile)
        def persist_then_drift(custody, kind, *args):
            acknowledgement = real_append(custody, kind, *args)
            hit = (boundary == 'forecast' and kind == 'FORECAST') or (
                boundary == 'calibration_plan' and kind == 'DECISION' and
                args[-1].get('purpose') == 'CALIBRATION_MEASUREMENT_PLAN_ALWAYS_RESTORE')
            if hit and not fired:
                fired.append(True)
                if drift == 'revision':
                    live = lifecycle.discover()
                    token = lifecycle._tokens[live.instance_id]
                    lifecycle.store.save(token, deepcopy(expected_metadata))
            return acknowledgement
        def count_apply(operation):
            applied.append(operation.target)
            return real_apply(operation)
        live = lifecycle.discover()
        request = LightRequest(live.instance_id, revision, 'key_exposure', 1.0)
        backend.apply = count_apply
        try:
            with patch.object(LightCustody, 'append', persist_then_drift), patch.object(gate_source, 'source_identity', identity), patch.object(LocalLightReferee, 'evaluate', zero_residual):
                result = calibration(gate) if boundary == 'calibration_plan' else gate.run(
                    request, run_id='binding-' + boundary + '-' + drift, approved=True)
                dependencies_after_refusal = deepcopy(dict(backend.dependencies()))
        finally:
            backend.apply = real_apply
        expected_revision = revision + int(drift == 'revision')
        report = {'scope': 'Actual disposable H22 persistence; deterministic source-identity or disposable MemoryInstanceStore revision change; product files unchanged',
                  'boundary': boundary, 'drift': drift, 'injected_after_real_persistence': bool(fired), 'actual_apply_calls': len(applied),
                  'result': result._asdict(), 'exact_state_preserved': backend.snapshot() == before,
                  'expected_revision_preserving_injected_change': expected_revision,
                  'revision_after': lifecycle.discover().graph_revision}
        save('review-binding-' + boundary + '-' + drift + '.json', report)
        assert fired
        assert not applied, 'Changed certified source/revision must refuse host dispatch, not adopt a new baseline'
        assert result.status == 'UNAVAILABLE'
        assert backend.snapshot() == before and lifecycle.discover().graph_revision == expected_revision
        assert lifecycle.discover() == expected_metadata
        assert dependencies_after_refusal == expected_dependencies
        assert dict(backend.dependencies()) == original_dependencies
        if boundary == 'calibration_plan':
            assert gate.profile is None
            assert gate._certified_profile_sha is None
            assert gate._certified_dependencies is None
    run_on_main(qualify, label='qualification:certified binding after ' + boundary + ':' + drift)
