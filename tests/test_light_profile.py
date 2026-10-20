"""Hand-computed correlated six-dimensional controls; labelled synthetic inputs."""
from dataclasses import replace
import math
import os
import threading
import unittest
from synapse.loop.light_profile import LocalLightReferee, ProfileUnavailable, fit_observed_profile
from synapse.loop.rcxi_light import tension
from synapse.loop.rcxi_ports import SixMetrics


class MeasuredProfileMathTests(unittest.TestCase):
    def profile(self):
        # Two rows: cost mean=(11,102), unbiased covariance=[[2,4],[4,8]].
        # Unit ridge gives [[3,4],[4,9]], determinant=11. For delta=(1,2),
        # the independent inverse quadratic is (9-16+12)/11 = 5/11.
        return fit_observed_profile(training=(SixMetrics(0, 10, 100, 0, 0, 0), SixMetrics(0, 12, 104, 0, 0, 0)),
                                    holdout=(SixMetrics(0, 12, 104, 0, 0, 0),), resolutions=(1,) * 6,
                                    profile_id='unit-arithmetic-v1', origin='UNIT_SYNTHETIC_ARITHMETIC', process_pid=os.getpid(),
                                    context_sha256='a' * 64, loss_weight=1, loss_tolerance=.001, histogram_width_ev=1,
                                    minimum_exposure=-2, maximum_exposure=2, max_attempts=3, max_execution_ms=1000,
                                    max_wall_ms=2000, no_progress_limit=2, progress_epsilon=.000001, referee_timeout_seconds=.5)

    def test_correlated_covariance_and_training_envelope_are_derived(self):
        profile = self.profile()
        self.assertEqual(profile.covariance[1][1], 3)
        self.assertEqual(profile.covariance[2][2], 9)
        self.assertEqual(profile.covariance[1][2], 4)
        expected = math.sqrt(5 / 11)
        self.assertAlmostEqual(tension(profile.forecast, SixMetrics(0, 12, 104, 0, 0, 0), profile), expected)
        self.assertAlmostEqual(profile.tension_limit, math.nextafter(expected, math.inf))

    def test_every_dimension_participates_and_invariant_never_allows(self):
        profile = self.profile()
        base = profile.forecast
        fields = ('task_loss', 'execution_ms', 'peak_memory_mb', 'complexity_delta', 'state_entropy', 'invariant_violation')
        for field in fields:
            with self.subTest(field=field):
                changed = replace(base, **{field: getattr(base, field) + 1})
                self.assertGreater(tension(base, changed, profile), 0)
        result = LocalLightReferee().evaluate(base, replace(base, invariant_violation=1), replace(profile, tension_limit=1000))
        self.assertFalse(result.accepted)

    def test_worker_is_off_thread_and_binds_all_inputs(self):
        profile = self.profile()
        result = LocalLightReferee().evaluate(profile.forecast, profile.forecast, profile)
        self.assertTrue(result.accepted)
        self.assertNotEqual(result.worker_thread, threading.get_ident())
        self.assertEqual(result.profile_sha256, profile.sha256)
        self.assertNotEqual(replace(profile, max_attempts=2).sha256, profile.sha256)

    def test_invalid_covariance_or_unbounded_choices_refuse(self):
        profile = self.profile()
        for choices in ({'covariance': ((0,) * 6,) * 6}, {'max_attempts': 1000}, {'max_wall_ms': float('nan')},
                        {'referee_timeout_seconds': 100}, {'resolutions': (0,) * 6}):
            with self.subTest(choices=choices), self.assertRaises((ProfileUnavailable, ValueError)):
                replace(profile, **choices)

    def test_lifetime_peak_is_conditioned_without_hiding_trial_growth(self):
        # Observed absolute peaks rise by 900 MB as the process ages, while each
        # operation's measured new high-water growth stays exactly 1 MB.
        kwargs = dict(profile_id='conditional-unit-v1', origin='UNIT_SYNTHETIC_ARITHMETIC', process_pid=os.getpid(),
                      context_sha256='a' * 64, loss_weight=1, loss_tolerance=.001, histogram_width_ev=1,
                      minimum_exposure=-2, maximum_exposure=2, max_attempts=3, max_execution_ms=1000,
                      max_wall_ms=2000, no_progress_limit=2, progress_epsilon=.000001, referee_timeout_seconds=.5)
        profile = fit_observed_profile(training=(SixMetrics(0, 10, 101, 0, 0, 0), SixMetrics(0, 12, 1001, 0, 0, 0)),
                                       holdout=(SixMetrics(0, 11, 201, 0, 0, 0),), resolutions=(1,) * 6,
                                       memory_baselines=(100, 1000, 200), **kwargs)
        self.assertEqual(profile.mean_peak_growth_mb, 1)
        self.assertEqual(profile.covariance[2][2], 1)
        self.assertEqual(profile.forecast_for(2000).peak_memory_mb, 2001)
        self.assertEqual(tension(profile.forecast_for(2000), SixMetrics(0, 11, 2001, 0, 0, 0), profile), 0)
        self.assertFalse(LocalLightReferee().evaluate(profile.forecast_for(2000), SixMetrics(0, 11, 2002, 0, 0, 0), profile).accepted)

    def test_validation_outlier_cannot_widen_its_own_acceptance_limit(self):
        # Independent inverse calculation above gives the training boundary
        # sqrt(5/11). This held-out point has quadratic 30325/11, far outside.
        # Validation must reject the profile rather than set a larger limit.
        with self.assertRaises(ProfileUnavailable):
            fit_observed_profile(training=(SixMetrics(0, 10, 100, 0, 0, 0), SixMetrics(0, 12, 104, 0, 0, 0)),
                                 holdout=(SixMetrics(0, 100, 200, 0, 0, 0),), resolutions=(1,) * 6,
                                 profile_id='bad-validation-v1', origin='UNIT_SYNTHETIC_ARITHMETIC', process_pid=os.getpid(),
                                 context_sha256='a' * 64, loss_weight=1, loss_tolerance=.001, histogram_width_ev=1,
                                 minimum_exposure=-2, maximum_exposure=2, max_attempts=3, max_execution_ms=1000,
                                 max_wall_ms=2000, no_progress_limit=2, progress_epsilon=.000001, referee_timeout_seconds=.5)


if __name__ == '__main__':
    unittest.main()
