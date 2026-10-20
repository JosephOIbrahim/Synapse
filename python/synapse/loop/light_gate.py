"""One measured LIGHT gate for a closed disposable headless H22 fixture.

This does not activate the RC+xi blueprint, artist GUI, external substrates or
an arbitrary scene/tool path. Calibration is an explicitly bounded experiment:
every candidate is rejected and independently restored. A later operation can
commit only through BuildTransaction's owned provisional decision seam.
"""
from __future__ import annotations

import logging as _boundary_logging
_boundary_log = _boundary_logging.getLogger(__name__)

from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import importlib
import math
import mmap
import os
import re
from pathlib import Path
import threading
import time
from uuid import uuid4

from .light_custody import CustodyUnavailable, LightCustody, digest
from .light_profile import HoldoutOutsideTraining, LocalLightReferee, MeasuredLightProfile, ProfileUnavailable, fit_observed_profile
from .ports import LedgerPort, PortResult
from .rcxi_light import LightRequest, histogram_entropy_ev, metric_vector
from .rcxi_ports import SixMetrics
from synapse.recipes.contracts import ActionId, RecoveryVerdict, TerminalVerdict
from synapse.recipes.light_capture import CaptureUnavailable, process_peak_working_set
from synapse.recipes.light_headless import EXPOSURE, HeadlessLightBackend, authored_digest
from synapse.recipes.transaction import BuildTransaction, PreparedOperation, ProvisionalDecision, state_diff


def source_identity():
    names = ("recipes.transaction", "recipes.instance", "recipes.contracts", "recipes.light_capture", "recipes.light_headless",
             "loop.light_custody", "loop.light_profile", "loop.light_gate", "loop.rcxi_light", "loop.rcxi_ports", "loop.ports",
             "server.main_thread", "server.marshal_guard")
    return digest({name: hashlib.sha256(Path(importlib.import_module("synapse." + name).__file__).read_bytes()).hexdigest() for name in names})


class HeadlessLightGate:
    """Own the controller/fuel; borrow existing host/lifecycle/ledger owners."""
    def __init__(self, *, backend, lifecycle, ledger):
        if type(backend) is not HeadlessLightBackend:
            raise CaptureUnavailable("The built-in closed headless backend is required")
        self.backend, self.lifecycle, self.ledger = backend, lifecycle, ledger
        self.referee = LocalLightReferee()
        self.profile = None
        self._certified_profile_sha = None
        self._certified_source = None
        self._certified_ledger = None
        self._certified_ledger_uri = None
        self._certified_dependencies = None
        self._cancel = threading.Event()
        self._control_lock = threading.RLock()
        self._active_transaction = None
        self._active = False

    def cancel(self):
        with self._control_lock:
            self._cancel.set()
            txn = self._active_transaction
            return txn.cancel() if txn is not None else not self._active

    def _execute_transaction(self, txn):
        with self._control_lock:
            old = self._active_transaction
            if old is not None and old.await_terminal(0) is None:
                raise ProfileUnavailable("Previous host transaction is still nonterminal")
            self._active_transaction = txn
            if self._cancel.is_set():
                txn.cancel()
        try:
            return txn.execute()
        finally:
            if txn.await_terminal(0) is not None:
                with self._control_lock:
                    if self._active_transaction is txn:
                        self._active_transaction = None

    def _context(self, snapshot=None):
        if type(self.ledger) is not LedgerPort or self.ledger.worker is not None:
            raise CustodyUnavailable("The existing explicit local ledger owner is unavailable")
        instance = self.lifecycle.discover()
        if instance is None:
            raise CaptureUnavailable("No committed captured recipe instance exists")
        return digest({"snapshot": snapshot if snapshot is not None else self.backend.snapshot(),
                       "instance": instance.instance_id, "revision": instance.graph_revision,
                       "source": source_identity(), "pid": os.getpid(), "dependencies": dict(self.backend.dependencies()),
                       "ledger_uri": str(Path(self.ledger.ledger).resolve()),
                       "memory_window": "PROCESS_LIFETIME_PEAK_WORKING_SET_AT_OBSERVATION"})

    def _transaction(self, target, request_id, callback, *, instance, dependencies, deadline_ns=None):
        operation = PreparedOperation("set_parm", self.backend.observer.node_path, target, EXPOSURE,
                                      (("nodes", self.backend.observer.node_path, "parms", EXPOSURE),))
        return BuildTransaction(request_id=request_id, instance=instance, lifecycle=self.lifecycle, backend=self.backend,
                                operations=(operation,), expected_revision=instance.graph_revision,
                                dependencies=dependencies, action=ActionId.LIGHT,
                                slots={"exposure": target}, approved=True, precommit=callback, deadline_ns=deadline_ns)

    def _measurement_bound(self, instance, dependencies, sources):
        # Both calibration and live trials pay for the SAME source/dependency/
        # exact metadata checks before their independent observation is timed.
        return (source_identity() == sources
                and dict(self.backend.dependencies()) == dependencies
                and self.lifecycle.discover() == instance)

    def _measure(self, before, after, target, started_ns, txn, histogram_width):
        # Independent host reread and Windows kernel sampler; ignore apply's
        # return value completely. No caller/mutator-supplied telemetry enters.
        current = self.backend.observer.capture()
        usd = self.backend.observer.usd_observation()
        peak = process_peak_working_set()
        elapsed = (time.perf_counter_ns() - started_ns) / 1_000_000
        path = self.backend.observer.node_path
        values = [node["parms"][EXPOSURE] for node in current["nodes"].values()]
        allowed = ("nodes", path, "parms", EXPOSURE)
        escaped = any(tuple(change["path"]) != allowed for change in state_diff(before, current))
        violation = int(bool(current != after or escaped or not txn._owned or self.backend.foreign_epoch() is None
                        or self.backend.foreign_epoch() != txn._foreign or self.backend.undo_enabled() is not True
                        or current["topology"] != before["topology"] or len(values) != 1
                        or usd["composition_errors"] or usd["node_errors"] or usd["exposure"] != usd["expected_usd_exposure"]))
        observed = usd["exposure"]
        if type(observed) not in (int, float) or not math.isfinite(observed):
            raise CaptureUnavailable("Actual USD exposure is unmeasurable")
        metrics = SixMetrics(abs(observed - target) / max(1.0, abs(target)), elapsed, peak["peak_memory_mb"],
                             current["topology"]["node_count"] + current["topology"]["edge_count"]
                             - before["topology"]["node_count"] - before["topology"]["edge_count"],
                             histogram_entropy_ev(values, histogram_width), violation)
        evidence = {"metrics": asdict(metrics), "execution_ms": elapsed, "clock": "perf_counter_ns:before_transaction_to_independent_observation",
                    "memory": peak, "before_sha256": authored_digest(before), "after_sha256": authored_digest(current),
                    "usd": usd, "transaction_run_id": txn.result.run_id}
        return metrics, evidence

    def _restored(self, txn, before, revision):
        if txn.await_terminal(0) is None:
            return False
        recovered = txn.recover()
        current = self.lifecycle.discover()
        return ((recovered == RecoveryVerdict.RESTORED or not txn._mutated) and self.backend.snapshot() == before
                and current is not None and current.graph_revision == revision)

    @staticmethod
    def _result(status, outcome, reason, **payload):
        data = {"outcome": outcome, "scope": "CLOSED_DISPOSABLE_HEADLESS_H22_ONLY", "artist_gui_qualified": False,
                "custody": "DURABLE_LOCAL_EXPOSED", "settlement": "UNAVAILABLE_UNCONFIGURED_EXISTING_PORT", **payload}
        return PortResult(status, data, None if status == "SUCCESS" else reason)

    def calibrate(self, *, targets, loss_tolerance, histogram_width_ev, minimum_exposure, maximum_exposure,
                  max_attempts, max_execution_ms, max_wall_ms, no_progress_limit, progress_epsilon,
                  referee_timeout_seconds, calibration_max_wall_ms, approved):
        """12 training + 6 held out; at most 30 actual restored measurements.

        Known constant dimensions use explicit discrete resolution 1; scalar
        loss uses its declared tolerance, costs use the clock and system page
        size. On a population-only validation failure, retain ALL old samples as
        training and acquire six NEW independent validation samples, at most
        three rounds total. No source/invariant/recovery failure is retried.
        No accepted profile exists before a complete independent round passes.
        """
        if threading.current_thread() is not threading.main_thread():
            return self._result("UNAVAILABLE", "CALIBRATION_NOT_STARTED", "Headless calibration requires existing main-thread dispatch")
        if approved is not True:
            return self._result("BLOCKED", "CALIBRATION_NOT_STARTED", "Explicit approval of disposable calibration required")
        if self._active or self._cancel.is_set():
            return self._result("UNAVAILABLE", "CALIBRATION_NOT_STARTED", "Controller busy or cancelled")
        self.profile = None
        self._certified_profile_sha = None
        self._certified_ledger = None
        self._certified_ledger_uri = None
        self._certified_dependencies = None
        try:
            choices = (loss_tolerance, histogram_width_ev, minimum_exposure, maximum_exposure, max_execution_ms,
                       max_wall_ms, progress_epsilon, referee_timeout_seconds, calibration_max_wall_ms)
            if (any(type(value) not in (int, float) or not math.isfinite(value) for value in choices)
                    or not -2 <= minimum_exposure < maximum_exposure <= 2 or loss_tolerance <= 0 or histogram_width_ev <= 0
                    or not 0 < max_execution_ms <= 60_000 or not 0 < max_wall_ms <= 60_000
                    or not 0 < referee_timeout_seconds <= 2 or progress_epsilon < 0
                    or type(max_attempts) is not int or not 1 <= max_attempts <= 4
                    or type(no_progress_limit) is not int or not 1 <= no_progress_limit <= 4):
                raise ProfileUnavailable("Explicit finite qualified bounds, decision choices and bounded fuel required before calibration")
            if (type(targets) not in (list, tuple) or len(targets) != 6 or len(set(targets)) != 6
                    or any(type(value) not in (int, float) or not math.isfinite(value) or not minimum_exposure <= value <= maximum_exposure for value in targets)
                    or type(calibration_max_wall_ms) not in (int, float) or not 0 < calibration_max_wall_ms <= 60_000):
                raise ProfileUnavailable("Six distinct finite calibration targets and a bounded experiment window required")
            before = self.backend.snapshot()
            instance = deepcopy(self.lifecycle.discover())
            revision, scope = instance.graph_revision, instance.instance_id
            current_value = before["nodes"][self.backend.observer.node_path]["parms"][EXPOSURE]
            if current_value in targets:
                raise ProfileUnavailable("Calibration targets must exercise changes, not no-op samples")
            context, sources = self._context(before), source_identity()
            dependencies = deepcopy(dict(self.backend.dependencies()))
            if (dependencies.get("source_sha256") != sources or self.lifecycle.discover() != instance
                    or dict(self.backend.dependencies()) != dependencies):
                raise ProfileUnavailable("Calibration instance/dependency binding changed before experiment")
            descriptor = {"schema": "synapse.light.calibration-experiment.v3", "context": context, "targets": list(targets),
                          "threshold_method": "TRAINING_ENVELOPE_WITH_INDEPENDENT_HELDOUT_VALIDATION",
                          "initial_training": 12, "heldout_per_round": 6, "maximum_rounds": 3, "maximum_samples": 30,
                          "prior_validation_failures_retained_as_training": True, "accepted_candidates": False, "loss_tolerance": loss_tolerance,
                          "histogram_width_ev": histogram_width_ev, "experiment_wall_ms": calibration_max_wall_ms}
            experiment_sha = digest(descriptor)
            rows, proofs, memory_baselines = [], [], []
            validation_rounds = []
            profile = None
            planned_targets = list(targets) * 3
            resolutions = (loss_tolerance, time.get_clock_info("perf_counter").resolution * 1000,
                           mmap.PAGESIZE / 1_000_000, 1, 1, 1)
            def fit_round():
                return fit_observed_profile(training=rows[:-6], holdout=rows[-6:], resolutions=resolutions,
                    profile_id="headless-light-v3-" + uuid4().hex, origin="HEADLESS_H22_MEASURED", process_pid=os.getpid(),
                    context_sha256=context, loss_weight=1, loss_tolerance=loss_tolerance, histogram_width_ev=histogram_width_ev,
                    minimum_exposure=minimum_exposure, maximum_exposure=maximum_exposure, max_attempts=max_attempts,
                    max_execution_ms=max_execution_ms, max_wall_ms=max_wall_ms, no_progress_limit=no_progress_limit,
                    progress_epsilon=progress_epsilon, referee_timeout_seconds=referee_timeout_seconds,
                    memory_baselines=memory_baselines)
            started = time.perf_counter_ns()
            self._active = True
            with LightCustody(self.ledger) as custody:
                for index, target in enumerate(planned_targets):
                    if self._cancel.is_set() or (time.perf_counter_ns() - started) / 1_000_000 > calibration_max_wall_ms:
                        raise ProfileUnavailable("Calibration cancelled or experiment deadline reached")
                    if self._context() != context or source_identity() != sources:
                        raise ProfileUnavailable("Calibration source/context changed")
                    run_id = "cal-" + uuid4().hex
                    custody.begin(run_id, scope, experiment_sha, experiment_sha, 1, max_execution_ms)
                    request_sha = experiment_sha
                    pre_peak = process_peak_working_set()
                    plan_ack = custody.append("DECISION", run_id, scope, request_sha, experiment_sha,
                                              {"purpose": "CALIBRATION_MEASUREMENT_PLAN_ALWAYS_RESTORE", "pretrial_peak": pre_peak,
                                               "target": target, "prestate_sha256": authored_digest(before)})
                    if (not custody.verify(plan_ack) or self._context() != context or source_identity() != sources
                            or self.lifecycle.discover() != instance or dict(self.backend.dependencies()) != dependencies):
                        custody.append("TERMINAL", run_id, scope, request_sha, experiment_sha,
                                       {"scope_reusable": False, "outcome": "CALIBRATION_BINDING_UNKNOWN"})
                        raise ProfileUnavailable("Calibration plan persistence changed original instance/source/dependencies")
                    acquired = []
                    trial_started = time.perf_counter_ns()
                    def measure_reject(prestate, candidate):
                        if not custody.verify(plan_ack) or not self._measurement_bound(instance, dependencies, sources):
                            raise ProfileUnavailable("Calibration measurement-plan/source custody lost")
                        metrics, evidence = self._measure(prestate, candidate, target, trial_started, txn, histogram_width_ev)
                        evidence["memory_before"] = pre_peak
                        if prestate != before:
                            raise CaptureUnavailable("Calibration prestate changed")
                        custody.append("OBSERVED", run_id, scope, request_sha, experiment_sha, evidence)
                        acquired.append((metrics, evidence))
                        return ProvisionalDecision(False, "calibration experiment: always restore, never accept")
                    txn = self._transaction(target, run_id, measure_reject, instance=instance, dependencies=dependencies,
                                            deadline_ns=started + int(calibration_max_wall_ms * 1_000_000))
                    result = self._execute_transaction(txn)
                    restored = self._restored(txn, before, revision)
                    custody.append("RECOVERY", run_id, scope, request_sha, experiment_sha,
                                   {"restored": restored, "transaction_recovery": result.recovery.value})
                    custody.append("TERMINAL", run_id, scope, request_sha, experiment_sha,
                                   {"scope_reusable": restored, "outcome": "CALIBRATION_MEASURED_RESTORED" if restored and acquired else "CALIBRATION_UNAVAILABLE"})
                    if not restored or len(acquired) != 1:
                        raise ProfileUnavailable("Calibration measurement/recovery incomplete: " + result.reason)
                    metrics, evidence = acquired[0]
                    if metrics.invariant_violation or metrics.task_loss > loss_tolerance:
                        raise ProfileUnavailable("Calibration observed a failed invariant/objective")
                    rows.append(metrics)
                    memory_baselines.append(pre_peak["peak_memory_mb"])
                    proofs.append({"target": target, "run_id": run_id, **evidence})
                    if len(rows) == len(planned_targets):
                        try:
                            profile = fit_round()
                        except HoldoutOutsideTraining as exc:
                            validation_rounds.append({"training": len(rows) - 6, "fresh_heldout": 6,
                                                      "verdict": "UNAVAILABLE_OUTSIDE_POPULATION", "reason": str(exc),
                                                      "all_samples_sha256": digest([asdict(row) for row in rows])})
                            if len(rows) >= 30:
                                raise
                            planned_targets.extend(tuple(targets))
                        else:
                            validation_rounds.append({"training": len(rows) - 6, "fresh_heldout": 6,
                                                      "verdict": "PASS_INDEPENDENT_VALIDATION",
                                                      "all_samples_sha256": digest([asdict(row) for row in rows])})
            if self._context() != context or source_identity() != sources:
                raise ProfileUnavailable("Final calibration context drift")
            if profile is None:
                raise ProfileUnavailable("No independently validated profile within the bounded experiment")
            with self._control_lock:
                if self._cancel.is_set() or (time.perf_counter_ns() - started) / 1_000_000 > calibration_max_wall_ms:
                    raise ProfileUnavailable("Calibration cancelled or deadline reached before profile publication")
                self.profile = profile
                self._certified_profile_sha, self._certified_source = profile.sha256, sources
                self._certified_dependencies = tuple(sorted(dependencies.items()))
                self._certified_ledger = self.ledger
                self._certified_ledger_uri = str(Path(self.ledger.ledger).resolve())
            return self._result("SUCCESS", "CALIBRATION_MEASURED_ALL_CANDIDATES_RESTORED", "",
                                profile=asdict(profile), profile_sha256=profile.sha256, observations=proofs,
                                calibration_rounds=validation_rounds, maximum_samples=30,
                                limits="Same process, exact initial authored context/revision only; training envelope fixed first and independently held-out validated, not a future population coverage guarantee")
        except Exception as exc:
            _boundary_log.warning("Bounded LIGHT boundary %s caught %s", 'light_gate.calibrate', type(exc).__name__[:120])
            return self._result("UNAVAILABLE", "CALIBRATION_UNAVAILABLE", type(exc).__name__ + ": " + str(exc))
        finally:
            self._active = False

    def run(self, request, *, run_id, approved, forecasts=None):
        trials, spent, stagnant = [], 0.0, 0
        if threading.current_thread() is not threading.main_thread():
            return self._result("UNAVAILABLE", "NOT_DISPATCHED", "Headless gate requires existing main-thread dispatch")
        if self._active:
            return self._result("UNAVAILABLE", "NOT_DISPATCHED", "Controller already active")
        try:
            if type(request) is not LightRequest or approved is not True:
                raise ProfileUnavailable("Typed captured request and explicit approval required")
            if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9_:-]{1,100}", run_id):
                raise ProfileUnavailable("A fresh bounded run identity is required")
            if type(self.referee) is not LocalLightReferee or type(self.profile) is not MeasuredLightProfile:
                raise ProfileUnavailable("Measured calibration and trusted local evaluator required")
            if self.ledger is not self._certified_ledger:
                raise ProfileUnavailable("The measured ledger owner changed; no replay through a replacement ledger")
            profile = replace(self.profile)
            expected_profile = self._certified_profile_sha
            if profile.origin != "HEADLESS_H22_MEASURED" or profile.sha256 != expected_profile or profile.process_pid != os.getpid():
                raise ProfileUnavailable("Profile is not this controller's measured process-bound calibration")
            instance = deepcopy(self.lifecycle.discover())
            if (instance.instance_id != request.instance_id or instance.graph_revision != request.expected_revision
                    or request.key_light_binding != "key_exposure" or not profile.minimum_exposure <= request.target_exposure <= profile.maximum_exposure):
                raise ProfileUnavailable("Request is stale or outside its captured exposure binding/bounds")
            before = self.backend.snapshot()
            if self._context(before) != profile.context_sha256 or source_identity() != self._certified_source:
                raise ProfileUnavailable("Calibration context/source changed; remeasure before another action")
            original_value = before["nodes"][self.backend.observer.node_path]["parms"][EXPOSURE]
            if original_value == request.target_exposure:
                return self._result("BLOCKED", "NOT_DISPATCHED", "The bounded gate requires a changed exposure target")
            if forecasts is not None and (type(forecasts) not in (tuple, list) or not 1 <= len(forecasts) <= profile.max_attempts):
                raise ProfileUnavailable("A bounded explicit forecast list is required")
            plans = None if forecasts is None else tuple(replace(row) for row in forecasts if type(row) is SixMetrics)
            if plans is not None and (not plans or len(plans) > profile.max_attempts or len(plans) != len(forecasts)):
                raise ProfileUnavailable("One to max_attempts typed forecasts required")
            dependencies = dict(self._certified_dependencies or ())
            if (not dependencies or dependencies.get("source_sha256") != self._certified_source
                    or dict(self.backend.dependencies()) != dependencies):
                raise ProfileUnavailable("Certified original dependency binding is unavailable or changed")
            scope, revision = instance.instance_id, instance.graph_revision
            best_loss = abs(original_value - request.target_exposure) / max(1.0, abs(request.target_exposure))
            started = time.perf_counter_ns()
            deadline_ns = started + int(profile.max_wall_ms * 1_000_000)
            self._active = True
            def policy_current(expected_instance=instance):
                return (type(self.profile) is MeasuredLightProfile and self.profile.sha256 == expected_profile
                        and profile.sha256 == expected_profile
                        and type(self.referee) is LocalLightReferee and self.ledger is self._certified_ledger
                        and type(self.ledger) is LedgerPort and self.ledger.worker is None
                        and str(Path(self.ledger.ledger).resolve()) == self._certified_ledger_uri
                        and tuple(sorted(dependencies.items())) == self._certified_dependencies
                        and self._measurement_bound(expected_instance, dependencies, self._certified_source))
            with LightCustody(self.ledger) as custody:
                custody.begin(run_id, scope, request.sha256, expected_profile, profile.max_attempts, profile.max_execution_ms)
                def finish(status, outcome, reason, reusable):
                    custody.append("TERMINAL", run_id, scope, request.sha256, expected_profile,
                                   {"scope_reusable": reusable, "outcome": outcome, "reason": reason})
                    return self._result(status, outcome, reason, trials=trials, measured_execution_ms=spent,
                                        profile_sha256=expected_profile, revision=self.lifecycle.discover().graph_revision)
                for index in range(profile.max_attempts):
                    if self._cancel.is_set():
                        return finish("BLOCKED", "CANCELLED_BEFORE_DISPATCH", "Cancellation requested", True)
                    if not policy_current() or self.backend.snapshot() != before or self._context(before) != profile.context_sha256:
                        return finish("UNAVAILABLE", "CONTEXT_UNKNOWN", "Policy or original authored context changed", False)
                    if (time.perf_counter_ns() - started) / 1_000_000 >= profile.max_wall_ms:
                        return finish("BLOCKED", "WALL_FUEL_EXHAUSTED", "Whole-run deadline reached before dispatch", True)
                    pre_peak = process_peak_working_set()
                    forecast = profile.forecast_for(pre_peak["peak_memory_mb"]) if plans is None else plans[min(index, len(plans) - 1)]
                    ack = custody.forecast(run_id, scope, request.sha256, expected_profile,
                                           metric_vector(forecast), authored_digest(before), pretrial_peak=pre_peak)
                    if self._cancel.is_set():
                        return finish("BLOCKED", "CANCELLED_BEFORE_DISPATCH", "Cancellation requested after forecast persistence", True)
                    if time.perf_counter_ns() >= deadline_ns:
                        return finish("BLOCKED", "WALL_FUEL_EXHAUSTED", "Deadline reached during forecast persistence; no host dispatch", True)
                    if (not policy_current() or not custody.verify(ack) or self.backend.snapshot() != before
                            or self._context(before) != profile.context_sha256):
                        return finish("UNAVAILABLE", "CONTEXT_UNKNOWN", "Original certified binding changed during forecast persistence; no host dispatch", False)
                    observed = []
                    trial_started = time.perf_counter_ns()
                    def evaluate(prestate, candidate):
                        nonlocal spent
                        if not custody.verify(ack) or not policy_current() or prestate != before:
                            raise ProfileUnavailable("Forecast/profile/prestate custody lost")
                        metrics, evidence = self._measure(prestate, candidate, request.target_exposure, trial_started, txn, profile.histogram_width_ev)
                        evidence["memory_before"] = pre_peak
                        custody.append("OBSERVED", run_id, scope, request.sha256, expected_profile, evidence)
                        spent += metrics.execution_ms
                        decision = self.referee.evaluate(forecast, metrics, profile)
                        allowed = (decision.accepted and not self._cancel.is_set() and policy_current() and custody.verify(ack)
                                   and spent <= profile.max_execution_ms
                                   and (time.perf_counter_ns() - started) / 1_000_000 <= profile.max_wall_ms)
                        custody.append("DECISION", run_id, scope, request.sha256, expected_profile,
                                       {"accepted": allowed, "tension": decision.tension, "worker_thread": decision.worker_thread,
                                        "forecast_sha256": decision.forecast_sha256, "observed_sha256": decision.observed_sha256})
                        if not policy_current() or not custody.verify(ack):
                            raise ProfileUnavailable("Policy/source/custody changed during durable decision persistence")
                        observed.append((metrics, evidence, decision, allowed, deepcopy(candidate)))
                        return ProvisionalDecision(allowed, "measured local objective/tension/fuel/custody" if allowed else "measured candidate not accepted")
                    txn = self._transaction(request.target_exposure, run_id + ":" + str(index + 1), evaluate, instance=instance, dependencies=dependencies, deadline_ns=deadline_ns)
                    result = self._execute_transaction(txn)
                    if txn.await_terminal(0) is None:
                        return finish("UNAVAILABLE", "HOST_TERMINAL_UNKNOWN", "Host operation is not terminal; no undo/retry", False)
                    if result.outcome == "committed":
                        if (not policy_current(txn._instance_committed) or not custody.verify(ack)
                                or len(observed) != 1 or not observed[0][3] or result.verdict != TerminalVerdict.VERIFIED
                                or self.backend.snapshot() != observed[0][4] or self.lifecycle.discover().graph_revision != revision + 1):
                            return finish("UNAVAILABLE", "COMMITTED_EVIDENCE_UNKNOWN", "Committed effect lacks complete gate evidence; no blind post-commit undo", False)
                        metrics, evidence, decision, _, _ = observed[0]
                        trials.append({"attempt": index + 1, "decision": "ACCEPTED", "metrics": asdict(metrics), "tension": decision.tension,
                                       "transaction_run_id": result.run_id, "forecast_ack": ack, "observation": evidence})
                        return finish("SUCCESS", "HEADLESS_ACCEPTED_UNSETTLED", "", True)
                    restored = self._restored(txn, before, revision)
                    custody.append("RECOVERY", run_id, scope, request.sha256, expected_profile,
                                   {"restored": restored, "transaction_recovery": result.recovery.value})
                    if not restored:
                        return finish("UNAVAILABLE", "QUARANTINED", "Ownership or exact recovery is unknown; no retry", False)
                    if self._cancel.is_set():
                        return finish("BLOCKED", "CANCELLED_RESTORED", "Cancellation requested; exact original state restored", True)
                    if time.perf_counter_ns() >= deadline_ns:
                        return finish("BLOCKED", "DEADLINE_RESTORED", "Operation deadline reached; exact original state restored", True)
                    if len(observed) != 1:
                        return finish("UNAVAILABLE", "INCOMPLETE_EVALUATION_RESTORED", result.reason, True)
                    metrics, evidence, decision, _, _ = observed[0]
                    improved = metrics.task_loss < best_loss - profile.progress_epsilon
                    best_loss = min(best_loss, metrics.task_loss)
                    stagnant = 0 if improved else stagnant + 1
                    more = (not self._cancel.is_set() and not metrics.invariant_violation and policy_current()
                            and stagnant < profile.no_progress_limit and spent < profile.max_execution_ms
                            and index + 1 < profile.max_attempts
                            and (time.perf_counter_ns() - started) / 1_000_000 < profile.max_wall_ms)
                    trials.append({"attempt": index + 1, "decision": "MORE_FUEL" if more else "RESTORED_REJECTED",
                                   "metrics": asdict(metrics), "tension": decision.tension, "forecast_ack": ack,
                                   "transaction_run_id": result.run_id, "observation": evidence})
                    if not more:
                        outcome = "CANCELLED_RESTORED" if self._cancel.is_set() else "THRASH_RESTORED" if stagnant >= profile.no_progress_limit else "REJECTED_RESTORED"
                        return finish("BLOCKED", outcome, "Measured gate rejected candidate; exact original state restored", True)
            return self._result("UNAVAILABLE", "NO_TERMINAL", "No complete terminal decision")
        except Exception as exc:
            _boundary_log.warning("Bounded LIGHT boundary %s caught %s", 'light_gate.run', type(exc).__name__[:120])
            return self._result("UNAVAILABLE", "CUSTODY_OR_PROFILE_UNKNOWN", type(exc).__name__ + ": " + str(exc), trials=trials)
        finally:
            self._active = False
