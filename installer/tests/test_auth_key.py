"""SIDEFXCTO-1 / R-011: a fresh install mints the local API auth key.

Uses the adversarial suite's synthetic payload/harness — no Houdini, no native
runtime, every filesystem mutation below one verified temporary directory.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import test_adversarial as hostile  # noqa: E402
from synapse_setup import engine  # noqa: E402
from synapse_setup.auth_key import ensure_auth_key  # noqa: E402


class AuthKeyMintTests(unittest.TestCase):
    setUp = hostile.InstallerAdversarialTests.setUp
    _remove_temp = hostile.InstallerAdversarialTests._remove_temp
    install = hostile.InstallerAdversarialTests.install

    def test_fresh_install_mints_the_key_and_a_repeat_preserves_it(self):
        report = self.install()
        self.assertEqual(report["auth_key"]["status"], "CREATED")
        path = self.home / ".synapse/auth.key"
        self.assertTrue(path.is_file())
        first = path.read_text(encoding="utf-8").strip()
        self.assertGreaterEqual(len(first), 20)
        self.assertFalse(first.startswith("#"))

        repeat = self.install()
        self.assertEqual(repeat["auth_key"]["status"], "PRESENT")
        self.assertEqual(path.read_text(encoding="utf-8").strip(), first)

    def test_uninstall_keeps_the_key_as_user_data(self):
        self.install()
        path = self.home / ".synapse/auth.key"
        first = path.read_text(encoding="utf-8").strip()
        self.assertEqual(engine.uninstall(self.app, sandbox=self.sandbox)["status"], "PASS")
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_text(encoding="utf-8").strip(), first)

    def test_existing_operator_key_is_never_rotated(self):
        path = self.home / ".synapse/auth.key"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("operator-issued-key\n", encoding="utf-8")
        self.assertEqual(ensure_auth_key(self.home)["status"], "PRESENT")
        self.assertEqual(path.read_text(encoding="utf-8"), "operator-issued-key\n")

    def test_empty_or_comment_only_key_file_is_replaced(self):
        path = self.home / ".synapse/auth.key"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n# only a comment\n", encoding="utf-8")
        self.assertEqual(ensure_auth_key(self.home)["status"], "CREATED")
        value = path.read_text(encoding="utf-8").strip()
        self.assertTrue(value)
        self.assertFalse(value.startswith("#"))


if __name__ == "__main__":
    unittest.main()
