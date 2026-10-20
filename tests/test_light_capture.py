"""Independent tiny authored-code controls; no Houdini or script execution."""
import os
import ctypes
import sys
import unittest
from synapse.recipes.light_capture import CaptureUnavailable, partition_exposure, process_peak_working_set


class LightCaptureTests(unittest.TestCase):
    def code(self, value="0", extra=""):
        return {'/stage': 'hou_node = hou.node("/stage/key")\n'
                'hou_node.setUserData("keep", "artist state")\n'
                'hou_parm = hou_node.parm("exposure")\n'
                'hou_parm.lock(False)\n'
                'hou_parm.deleteAllKeyframes()\n'
                f'hou_parm.set({value})\n'
                'hou_parm.setAutoscope(False)\n' + extra,
                '/obj': 'hou_node = hou.node("/obj")\n'}

    def test_only_literal_value_is_partitioned_and_input_is_unchanged(self):
        a, b = self.code(), self.code("1.25")
        original = dict(a)
        before, x = partition_exposure(a, "exposure")
        after, y = partition_exposure(b, "exposure")
        self.assertEqual((x, y), (0.0, 1.25))
        self.assertEqual(before, after)
        self.assertEqual(a, original)

    def test_userdata_lock_outside_context_and_other_parms_remain_captured(self):
        before, _ = partition_exposure(self.code(), "exposure")
        variants = [self.code(extra='hou_node.setUserData("foreign", "keep")\n'),
                    {**self.code(), '/obj': 'hou_node = hou.node("/obj")\nhou_node.setComment("outside")\n'},
                    self.code(extra='hou_parm = hou_node.parm("other")\nhou_parm.set(4)\n')]
        locked = self.code()
        locked['/stage'] = locked['/stage'].replace('lock(False)', 'lock(True)')
        variants.append(locked)
        for variant in variants:
            with self.subTest(variant=variant):
                after, _ = partition_exposure(variant, "exposure")
                self.assertNotEqual(before, after)

    def test_missing_duplicate_expression_and_nonfinite_refuse(self):
        variants = [self.code('True'), self.code('"1"'), self.code('float("nan")'),
                    {**self.code(), '/stage': self.code()['/stage'].replace('hou_parm.set(0)', 'hou_parm.setExpression("$F")')},
                    {**self.code(), '/duplicate': self.code()['/stage']}, {'/stage': ''}]
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(CaptureUnavailable):
                partition_exposure(variant, "exposure")

    @unittest.skipUnless(os.name == 'nt', 'Windows own-process counter test')
    def test_actual_windows_counter_has_explicit_lifetime_window(self):
        value = process_peak_working_set()
        self.assertEqual(value['pid'], os.getpid())
        self.assertGreater(value['peak_bytes'], 0)
        self.assertEqual(value['peak_memory_mb'], value['peak_bytes'] / 1_000_000)
        self.assertEqual(value['window'], 'PROCESS_LIFETIME_PEAK_WORKING_SET_AT_OBSERVATION')

    @unittest.skipUnless(os.name == 'nt' and sys.version_info[:2] == (3, 13),
                         'Resource-cache check targets qualified CPython 3.13; run in the H22 host suite')
    def test_repeated_observation_does_not_accumulate_native_pointer_types(self):
        process_peak_working_set()
        before = len(ctypes._pointer_type_cache)
        for _ in range(3):
            process_peak_working_set()
        self.assertEqual(len(ctypes._pointer_type_cache), before,
                         'Repeated telemetry must reuse its native counter type rather than grow the ctypes cache')


if __name__ == '__main__':
    unittest.main()
