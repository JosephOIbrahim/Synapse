"""Full bounded headless gate sequence: negative controls and composed actions."""
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
from types import MethodType

from .light_fixture import make_context, require_disposable_case
from synapse.loop.light_gate import HeadlessLightGate
from synapse.loop.ports import LedgerPort
from synapse.loop.rcxi_light import LightRequest
from synapse.loop.rcxi_ports import SixMetrics
from synapse.recipes.light_headless import authored_digest
from synapse.server.main_thread import run_on_main


def calibration(gate):
    return gate.calibrate(targets=(-2, -1, -.5, .5, 1, 2), loss_tolerance=.001,
                          histogram_width_ev=1, minimum_exposure=-2, maximum_exposure=2,
                          max_attempts=3, max_execution_ms=12_000, max_wall_ms=20_000,
                          no_progress_limit=2, progress_epsilon=1e-9, referee_timeout_seconds=.5,
                          calibration_max_wall_ms=60_000, approved=True)


def test_complete_bounded_headless_light_sequence():
    require_disposable_case('matrix')
    def qualify():
        observer, lifecycle, backend, setup_txn, setup = make_context()
        assert setup.outcome == 'committed', setup.reason
        base = Path(os.environ['SYNAPSE_LOG_DIR']).parent
        output = base / 'light-gate-matrix.json'
        ledger = LedgerPort(Path(os.environ['SYNAPSE_LOOP_LEDGER_DIR']) / 'protected-light-matrix')
        gate = HeadlessLightGate(backend=backend, lifecycle=lifecycle, ledger=ledger)
        report = {'scope': 'Actual closed headless H22 only; no artist GUI/render/substrate activation', 'cases': []}
        def save():
            output.write_text(json.dumps(report, default=str, indent=2) + '\n', encoding='utf-8')
        def request(target=1.1):
            instance = lifecycle.discover()
            return LightRequest(instance.instance_id, instance.graph_revision, 'key_exposure', target)
        def refusal(label, result, before, revision, statuses=('UNAVAILABLE', 'BLOCKED')):
            report['cases'].append({'case': label, 'result': result._asdict(),
                                    'exact_state_preserved': backend.snapshot() == before,
                                    'revision': lifecycle.discover().graph_revision})
            save()
            assert result.status in statuses, (label, result)
            assert backend.snapshot() == before and lifecycle.discover().graph_revision == revision, label
        before = backend.snapshot()
        refusal('missing-calibration', gate.run(request(), run_id='missing-profile', approved=True), before, 1)
        first_cal = calibration(gate)
        report['first_calibration'] = first_cal._asdict()
        save()
        assert first_cal.status == 'SUCCESS', first_cal.error_message
        refusal('approval-required', gate.run(request(), run_id='unapproved', approved=False), before, 1)
        wrong_revision = replace(request(), expected_revision=99)
        refusal('stale-revision', gate.run(wrong_revision, run_id='stale-revision', approved=True), before, 1)
        wrong_binding = replace(request(), key_light_binding='unqualified_field')
        refusal('wrong-field-binding', gate.run(wrong_binding, run_id='wrong-binding', approved=True), before, 1)
        refusal('outside-qualified-range', gate.run(request(2.1), run_id='outside-range', approved=True), before, 1)
        original_referee = gate.referee
        gate.referee = None
        refusal('missing-evaluator', gate.run(request(), run_id='missing-evaluator', approved=True), before, 1)
        gate.referee = original_referee
        original_profile = gate.profile
        gate.profile = replace(original_profile, max_attempts=4)
        refusal('policy-content-tamper', gate.run(request(), run_id='changed-policy', approved=True), before, 1)
        gate.profile = original_profile
        gate.ledger = LedgerPort(base / 'replacement-ledger')
        refusal('ledger-owner-replacement', gate.run(request(), run_id='replacement-ledger', approved=True), before, 1)
        assert not gate.ledger.ledger.exists()
        gate.ledger = ledger
        # The test owner mutates/restores ONLY its own known disposable fixture
        # bytes between independent corruption controls. The product never
        # repairs, clears or adopts a corrupt/interrupted ledger automatically.
        ledger_bytes = ledger.ledger.read_bytes()
        ledger.ledger.write_bytes(ledger_bytes + b'{invalid-custody}\n')
        refusal('corrupt-custody', gate.run(request(), run_id='corrupt-custody', approved=True), before, 1)
        (base / 'PRIVATE-corrupted-fixture-ledger.jsonl').write_bytes(ledger.ledger.read_bytes())
        ledger.ledger.write_bytes(ledger_bytes)
        identity = ledger.ledger.with_name(ledger.ledger.name + '.light.identity')
        identity_bytes = identity.read_bytes()
        ledger.ledger.write_bytes(b'')
        refusal('truncated-custody', gate.run(request(), run_id='truncated-custody', approved=True), before, 1)
        ledger.ledger.write_bytes(ledger_bytes)
        assert identity.read_bytes() == identity_bytes
        claim = ledger.ledger.with_name(ledger.ledger.name + '.light.claim')
        with claim.open('xb') as stream:
            stream.write(b'OWNED DISPOSABLE INTERRUPTION CONTROL\n')
        refusal('interrupted-claim', gate.run(request(), run_id='interrupted-claim', approved=True), before, 1)
        assert claim.read_bytes() == b'OWNED DISPOSABLE INTERRUPTION CONTROL\n'
        claim.unlink()  # exact fixture created above, not product auto-recovery
        wrong_forecast = SixMetrics(10, 1_000_000, 1_000_000, 100, 100, 1)
        thrash = gate.run(request(), run_id='bounded-thrash', approved=True, forecasts=(wrong_forecast,))
        refusal('finite-thrash-exact-recovery', thrash, before, 1, statuses=('BLOCKED',))
        assert thrash.payload['outcome'] == 'THRASH_RESTORED' and len(thrash.payload['trials']) == 3
        after_thrash_bytes = ledger.ledger.read_bytes()
        replay = gate.run(request(), run_id='bounded-thrash', approved=True)
        refusal('persisted-run-replay', replay, before, 1, statuses=('UNAVAILABLE',))
        assert ledger.ledger.read_bytes() == after_thrash_bytes
        # A mutator's fabricated green telemetry is ignored. The trusted reader
        # must observe the actual wrong exposure and reject/recover it.
        real_apply = backend.apply
        def lying_apply(operation):
            real_apply(replace(operation, value=-.25))
            return {'status': 'SUCCESS', 'metrics': [0, 0, 0, 0, 0, 0]}
        backend.apply = lying_apply
        try:
            forged = gate.run(request(), run_id='forged-mutator-report', approved=True)
            refusal('forged-mutator-telemetry-ignored', forged, before, 1, statuses=('BLOCKED',))
            assert all(trial['metrics']['task_loss'] > .001 for trial in forged.payload['trials'])
        finally:
            backend.apply = real_apply
        # One actual decimal exposure edit; expected USD float32 is derived
        # independently: round((11/10-1)*2^23)=838861, hence 1+838861/2^23.
        accepted = gate.run(request(1.1), run_id='decimal-accepted', approved=True)
        report['cases'].append({'case': 'actual-decimal-acceptance', 'result': accepted._asdict()})
        save()
        assert accepted.status == 'SUCCESS', accepted.error_message
        usd = observer.usd_observation()
        assert usd['exposure'] == 1 + 838861 / (2 ** 23) and usd['attribute_type'] == 'float'
        assert lifecycle.discover().graph_revision == 2
        second_before = backend.snapshot()
        refusal('stale-profile-after-accepted-action', gate.run(request(1.5), run_id='stale-next', approved=True), second_before, 2)
        # New controller has no volatile entitlement. Remeasure the exact new
        # prestate; durable run identities remain unavailable for replay.
        second = HeadlessLightGate(backend=backend, lifecycle=lifecycle, ledger=ledger)
        refusal('controller-replacement-needs-measurement', second.run(request(1.5), run_id='unmeasured-new-controller', approved=True), second_before, 2)
        second_cal = calibration(second)
        report['second_calibration'] = second_cal._asdict()
        save()
        assert second_cal.status == 'SUCCESS', second_cal.error_message
        refusal('replay-after-requalified-controller', second.run(request(1.5), run_id='decimal-accepted', approved=True), second_before, 2)
        second_result = second.run(request(1.5), run_id='second-composed-accepted', approved=True)
        report['cases'].append({'case': 'second-composed-acceptance', 'result': second_result._asdict()})
        save()
        assert second_result.status == 'SUCCESS', second_result.error_message
        assert observer.usd_observation()['exposure'] == 1.5 and lifecycle.discover().graph_revision == 3
        report.update(verdict='PASS_BOUNDED_HEADLESS_GATE_MATRIX', source_scope='Exact isolated H22 source binding and postchecks are separate launcher artifacts',
                      could_not_verify=['Cancellation and foreign-edit gate controls in a separate fresh fixture', 'Independent exact LIGHT review',
                                        'Artist GUI, reference render, external settlement, actual final installer/release'])
        save()
        backend.close()
    run_on_main(qualify, label='release:bounded LIGHT complete sequence matrix')
