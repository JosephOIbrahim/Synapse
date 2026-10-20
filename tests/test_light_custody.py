"""Real disposable LedgerPort files; no production ledger or substrate call."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from synapse.loop.ports import LedgerPort, PortResult
from synapse.loop.light_custody import CustodyUnavailable, LightCustody


class LightCustodyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synapse-light-custody-')
        self.addCleanup(self.temp.cleanup)
        self.port = LedgerPort(Path(self.temp.name))
        self.args = ('run-1', 'scope-1', 'a' * 64, 'b' * 64)

    def test_actual_port_persists_bound_forecast_before_dispatch(self):
        with LightCustody(self.port) as custody:
            custody.begin(*self.args, 2, 200)
            ack = custody.forecast(*self.args, [0, 1, 2, 0, 0, 0], 'c' * 64)
            self.assertTrue(custody.verify(ack))
            self.assertEqual(len(self.port.ledger.read_bytes().splitlines()), 2)
            self.assertEqual(custody.records()[-1]['kind'], 'FORECAST')
            self.assertEqual(self.port.settle('run-1').status, 'UNAVAILABLE')

    def test_restart_replay_and_unknown_prior_scope_refuse(self):
        with LightCustody(self.port) as custody:
            custody.begin(*self.args, 2, 200)
            custody.forecast(*self.args, [0] * 6, 'c' * 64)
        with LightCustody(self.port) as custody:
            with self.assertRaisesRegex(CustodyUnavailable, 'replay/restart'):
                custody.begin(*self.args, 2, 200)
            with self.assertRaisesRegex(CustodyUnavailable, 'interrupted'):
                custody.begin('run-2', *self.args[1:], 2, 200)

    def test_status_without_a_persisted_record_is_rejected(self):
        with LightCustody(self.port) as custody:
            custody.begin(*self.args, 2, 200)
            with patch.object(self.port, 'author_precommit', return_value=PortResult.ok({'seq': 2})):
                with self.assertRaisesRegex(CustodyUnavailable, 'persist'):
                    custody.forecast(*self.args, [0] * 6, 'c' * 64)

    def test_missing_truncated_corrupt_and_changed_ledger_refuse(self):
        for content in (b'', b'{broken}\n', b'{}'):
            with self.subTest(content=content):
                with tempfile.TemporaryDirectory() as directory:
                    port = LedgerPort(Path(directory))
                    with LightCustody(port) as custody:
                        custody.begin(*self.args, 2, 200)
                    port.ledger.write_bytes(content)
                    with self.assertRaises(CustodyUnavailable):
                        with LightCustody(port):
                            pass
        with LightCustody(self.port) as custody:
            custody.begin(*self.args, 2, 200)
            self.port.ledger.write_bytes(self.port.ledger.read_bytes() + b'{}\n')
            with self.assertRaisesRegex(CustodyUnavailable, 'drift'):
                custody.verify('x')

    def test_fuel_and_recovery_are_persisted_not_controller_counters(self):
        with LightCustody(self.port) as custody:
            custody.begin(*self.args, 1, 200)
            custody.forecast(*self.args, [0] * 6, 'c' * 64)
            with self.assertRaises(CustodyUnavailable):
                custody.forecast(*self.args, [0] * 6, 'c' * 64)
            custody.append('OBSERVED', *self.args, {'execution_ms': 20})
            custody.append('RECOVERY', *self.args, {'restored': True})
            with self.assertRaisesRegex(CustodyUnavailable, 'Fuel'):
                custody.forecast(*self.args, [0] * 6, 'c' * 64)

    def test_claim_contention_never_clears_another_owner(self):
        with LightCustody(self.port) as custody:
            custody.begin(*self.args, 1, 200)
            before = custody.lock.read_bytes()
            with self.assertRaisesRegex(CustodyUnavailable, 'busy or interrupted'):
                with LightCustody(self.port):
                    pass
            self.assertEqual(custody.lock.read_bytes(), before)

    def test_an_unmarked_existing_ledger_is_never_adopted(self):
        self.port.ledger.write_text('{}\n', encoding='utf-8')
        with self.assertRaisesRegex(CustodyUnavailable, 'never adopt'):
            with LightCustody(self.port):
                pass

    def test_nonfinite_forecast_negative_cost_or_identity_drift_refuses(self):
        with LightCustody(self.port) as custody:
            custody.begin(*self.args, 2, 200)
            with self.assertRaises(CustodyUnavailable):
                custody.forecast(*self.args, [float('nan')] * 6, 'c' * 64)
            with self.assertRaises(CustodyUnavailable):
                custody.append('OBSERVED', *self.args, {'execution_ms': -20})
            custody.identity.write_bytes(b'{}\n')
            with self.assertRaisesRegex(CustodyUnavailable, 'identity changed'):
                custody.verify('x')

    def test_quarantined_terminal_cannot_reopen_scope_or_mint_fuel(self):
        with LightCustody(self.port) as custody:
            custody.begin(*self.args, 1, 200)
            custody.append('TERMINAL', *self.args, {'scope_reusable': False, 'outcome': 'QUARANTINED'})
        with LightCustody(self.port) as custody:
            with self.assertRaisesRegex(CustodyUnavailable, 'interrupted/unknown'):
                custody.begin('new-run', *self.args[1:], 1, 200)

    def test_actual_usd_tuple_payload_is_frozen_as_json_before_binding(self):
        payload = {'execution_ms': 12.0, 'usd': {'composition_errors': (), 'prim_paths': ('/lights/key',)}}
        with LightCustody(self.port) as custody:
            custody.begin(*self.args, 1, 200)
            try:
                ack = custody.append('OBSERVED', *self.args, payload)
            except CustodyUnavailable as exc:
                self.fail('The actual existing-port JSON roundtrip must accept equivalent tuple/array data: ' + str(exc))
            self.assertTrue(custody.verify(ack))
            self.assertEqual(custody.records()[-1]['payload']['usd']['prim_paths'], ['/lights/key'])
            self.assertEqual(payload['usd']['prim_paths'], ('/lights/key',))

    def test_valid_nonempty_prefix_rollback_cannot_restore_run_fuel(self):
        with LightCustody(self.port) as custody:
            custody.begin(*self.args, 1, 200)
            custody.append('RECOVERY', *self.args, {'restored': True})
            custody.append('TERMINAL', *self.args, {'scope_reusable': True})
        acknowledged_prefix = self.port.ledger.read_bytes()
        second = ('run-2', *self.args[1:])
        with LightCustody(self.port) as custody:
            custody.begin(*second, 1, 200)
            custody.append('RECOVERY', *second, {'restored': True})
            custody.append('TERMINAL', *second, {'scope_reusable': True})
        self.assertGreater(len(self.port.ledger.read_bytes()), len(acknowledged_prefix))
        # Every retained row is valid, nonempty, correctly sequenced and hashed.
        # Only independent acknowledged-tail evidence can detect the lost run.
        self.port.ledger.write_bytes(acknowledged_prefix)
        with self.assertRaises(CustodyUnavailable):
            with LightCustody(self.port) as custody:
                custody.begin(*second, 1, 200)

    def test_missing_changed_or_pending_acknowledgement_is_never_adopted(self):
        for failure in ('missing', 'changed', 'pending'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                port = LedgerPort(Path(directory))
                with LightCustody(port) as custody:
                    custody.begin(*self.args, 1, 200)
                    custody.append('TERMINAL', *self.args, {'scope_reusable': True})
                if failure == 'missing':
                    custody.ack.unlink()
                elif failure == 'changed':
                    custody.ack.write_bytes(b'{}\n')
                else:
                    custody.ack_pending.write_bytes(b'INTERRUPTED FIXTURE ACK UPDATE\n')
                with self.assertRaises(CustodyUnavailable):
                    with LightCustody(port):
                        pass

    def test_interrupted_ack_update_preserves_gap_evidence_and_refuses_reentry(self):
        for stage in ('before_pending', 'before_replace'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                port = LedgerPort(Path(directory))
                with LightCustody(port) as custody:
                    custody.begin(*self.args, 1, 200)
                    old_ledger, old_ack = port.ledger.read_bytes(), custody.ack.read_bytes()
                    real_open = Path.open
                    def fail_pending(path, *args, **kwargs):
                        if path == custody.ack_pending:
                            raise OSError('injected before pending file creation')
                        return real_open(path, *args, **kwargs)
                    fault = (patch.object(Path, 'open', fail_pending) if stage == 'before_pending' else
                             patch('synapse.loop.light_custody.os.replace', side_effect=OSError('injected before atomic acknowledgement replacement')))
                    with fault, self.assertRaises(CustodyUnavailable):
                        custody.append('TERMINAL', *self.args, {'scope_reusable': True})
                    self.assertTrue(port.ledger.read_bytes().startswith(old_ledger))
                    self.assertGreater(len(port.ledger.read_bytes()), len(old_ledger))
                    self.assertEqual(custody.ack.read_bytes(), old_ack)
                    self.assertEqual(custody.ack_pending.exists(), stage == 'before_replace')
                files = [path for path in (port.ledger, custody.ack, custody.ack_pending) if path.exists()]
                evidence = {path: path.read_bytes() for path in files}
                with self.assertRaises(CustodyUnavailable):
                    with LightCustody(port):
                        pass
                self.assertEqual({path: path.read_bytes() for path in files}, evidence)

    def test_corrupt_next_record_is_not_independently_acknowledged(self):
        with LightCustody(self.port) as custody:
            custody.begin(*self.args, 1, 200)
            before = custody.ack.read_bytes()
            author = self.port.author_precommit
            def corrupt(*args):
                result = author(*args)
                with self.port.ledger.open('ab') as stream:
                    stream.write(b'{}\n')
                return result
            with patch.object(self.port, 'author_precommit', corrupt), self.assertRaises(CustodyUnavailable):
                custody.append('TERMINAL', *self.args, {'scope_reusable': True})
            self.assertEqual(custody.ack.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
