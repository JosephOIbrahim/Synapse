"""Cancellation and unknown foreign ownership on actual disposable H22 data."""
from dataclasses import asdict
import json
import os
from pathlib import Path

from .light_fixture import make_context, require_disposable_case
from .test_light_gate_matrix import calibration
from synapse.loop.light_gate import HeadlessLightGate
from synapse.loop.ports import LedgerPort
from synapse.loop.rcxi_light import LightRequest
from synapse.recipes.light_headless import authored_digest
from synapse.server.main_thread import run_on_main


def test_real_cancel_recovery_and_foreign_quarantine():
    require_disposable_case('cancel_foreign')
    def qualify():
        import hou
        observer, lifecycle, backend, setup_txn, setup = make_context()
        assert setup.outcome == 'committed', setup.reason
        base = Path(os.environ['SYNAPSE_LOG_DIR']).parent
        output = base / 'light-gate-cancel-foreign.json'
        ledger = LedgerPort(Path(os.environ['SYNAPSE_LOOP_LEDGER_DIR']) / 'cancel-foreign-light')
        gate = HeadlessLightGate(backend=backend, lifecycle=lifecycle, ledger=ledger)
        report = {'scope': 'Actual closed disposable H22; no artist scene or renderer', 'cases': []}
        def save():
            output.write_text(json.dumps(report, default=str, indent=2) + '\n', encoding='utf-8')
        def request():
            instance = lifecycle.discover()
            return LightRequest(instance.instance_id, instance.graph_revision, 'key_exposure', 1.25)
        measured = calibration(gate)
        report['calibration'] = measured._asdict()
        save()
        assert measured.status == 'SUCCESS', measured.error_message
        before = backend.snapshot()
        real_apply = backend.apply
        apply_calls = []
        def cancel_after_apply(operation):
            real_apply(operation)
            apply_calls.append(operation.target)
            gate.cancel()
        backend.apply = cancel_after_apply
        try:
            cancelled = gate.run(request(), run_id='cancel-after-real-apply', approved=True)
        finally:
            backend.apply = real_apply
        report['cases'].append({'case': 'cancel-after-actual-write', 'result': cancelled._asdict(),
                                'exact_state_restored': backend.snapshot() == before, 'actual_apply_calls': len(apply_calls)})
        save()
        assert len(apply_calls) == 1
        assert cancelled.status == 'BLOCKED' and cancelled.payload['outcome'] == 'CANCELLED_RESTORED'
        assert backend.snapshot() == before and lifecycle.discover().graph_revision == 1
        labels = backend.undo_labels()
        already_cancelled = gate.run(request(), run_id='cancel-before-dispatch', approved=True)
        report['cases'].append({'case': 'cancel-before-dispatch', 'result': already_cancelled._asdict()})
        save()
        assert already_cancelled.status == 'BLOCKED' and already_cancelled.payload['outcome'] == 'CANCELLED_BEFORE_DISPATCH'
        assert backend.snapshot() == before and backend.undo_labels() == labels
        second = HeadlessLightGate(backend=backend, lifecycle=lifecycle, ledger=ledger)
        next_cal = calibration(second)
        report['foreign_calibration'] = next_cal._asdict()
        save()
        assert next_cal.status == 'SUCCESS', next_cal.error_message
        # An unowned edit is injected outside the prepared field after the real
        # mutator returns. Actual userdata capture must refuse global undo even
        # though H22 supplied no userdata callback and the group label is ours.
        real_undo = backend.perform_undo
        undo_calls = []
        def count_undo():
            undo_calls.append(True)
            return real_undo()
        def foreign_after_apply(operation):
            real_apply(operation)
            hou.node('/obj').setUserData('foreign_fixture_opinion', 'KEEP_FOREIGN_FIXTURE_EDIT')
        backend.apply = foreign_after_apply
        backend.perform_undo = count_undo
        try:
            quarantined = second.run(request(), run_id='foreign-after-write', approved=True)
        finally:
            backend.apply = real_apply
            backend.perform_undo = real_undo
        actual = backend.snapshot()
        actual_labels = backend.undo_labels()
        report['cases'].append({'case': 'foreign-userdata-no-undo', 'result': quarantined._asdict(),
                                'undo_calls': len(undo_calls), 'foreign_tracking': backend.foreign_epoch(),
                                'actual_sha256': authored_digest(actual), 'undo_labels': actual_labels})
        save()
        assert quarantined.status == 'UNAVAILABLE' and quarantined.payload['outcome'] == 'QUARANTINED'
        assert not undo_calls and backend.foreign_epoch() is None
        assert hou.node('/obj').userData('foreign_fixture_opinion') == 'KEEP_FOREIGN_FIXTURE_EDIT'
        assert observer.usd_observation()['exposure'] == 1.25
        assert lifecycle.discover().graph_revision == 1
        retry = second.run(request(), run_id='quarantined-retry-refused', approved=True)
        report['cases'].append({'case': 'quarantined-retry-no-mutation', 'result': retry._asdict()})
        save()
        assert retry.status == 'UNAVAILABLE'
        assert backend.snapshot() == actual and backend.undo_labels() == actual_labels
        report.update(verdict='PASS_REAL_CANCEL_AND_FOREIGN_QUARANTINE',
                      could_not_verify=['Independent source review', 'Artist GUI/foreign plugin races outside the closed cooperative scope',
                                        'Reference render, external settlement, final installer/publication'])
        save()
        backend.close()
    run_on_main(qualify, label='release:actual bounded LIGHT cancellation and foreign ownership')
