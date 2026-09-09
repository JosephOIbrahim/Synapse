"""Lifecycle/failure tests use synthetic files, never the artist installation."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile

import test_adversarial as hostile
from test_adversarial import write_payload
from synapse_setup import discovery, engine, safety, registration
import build_payload


class LifecycleTests(unittest.TestCase):
    setUp = hostile.InstallerAdversarialTests.setUp
    _remove_temp = hostile.InstallerAdversarialTests._remove_temp
    install = hostile.InstallerAdversarialTests.install
    def test_fresh_repeat_upgrade_and_uninstall_preserve_user_data(self):
        old = write_payload(self.sandbox / "old.zip", "5.66.0", {"retired/module.py": b"old code"})
        first = self.install(payload=old)
        old_runtime = Path(first["runtime"])
        repeat = self.install(payload=old)
        self.assertEqual(first["runtime"], repeat["runtime"])
        user_files = [self.home / ".synapse/encryption.key", self.home / ".synapse/panel_settings.json",
                      self.pref / "houdini.env", self.sandbox / "projects/work.hip",
                      self.sandbox / "projects/.synapse/memory.jsonl", old_runtime / ".synapse/history.json"]
        for path in user_files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"artist data: must survive")
        upgrade = self.install()
        self.assertNotEqual(first["runtime"], upgrade["runtime"])
        package = json.loads((self.pref / "packages/synapse.json").read_text())
        self.assertEqual(package["hpath"], (Path(upgrade["runtime"]) / "houdini").as_posix())
        self.assertFalse((Path(upgrade["runtime"]) / "retired/module.py").exists())
        self.assertEqual(len(list((self.pref / "packages").glob("*.json"))), 1)
        self.assertEqual(engine.uninstall(self.app, sandbox=self.sandbox)["status"], "PASS")
        self.assertTrue(all(p.read_bytes() == b"artist data: must survive" for p in user_files))
        self.assertFalse((self.pref / "packages/synapse.json").exists())

    def test_downgrade_fails_without_changing_active_registration(self):
        self.install()
        path = self.pref / "packages/synapse.json"
        before = path.read_bytes()
        with self.assertRaisesRegex(safety.SetupError, "downgrade"):
            self.install(payload=write_payload(self.sandbox / "older.zip", "1.0.0"))
        self.assertEqual(path.read_bytes(), before)

    def test_missing_required_dependency_rejected_before_registration(self):
        path = self.sandbox / "missing.zip"
        with zipfile.ZipFile(self.payload) as src:
            data = {name: src.read(name) for name in src.namelist()}
        missing = "python/synapse/_vendor/anthropic/__init__.py"
        del data[missing]
        manifest = json.loads(data[engine.MANIFEST])
        del manifest["files"][missing]
        data[engine.MANIFEST] = safety.json_bytes(manifest)
        build_payload.zip_bytes(path, data)
        with self.assertRaisesRegex(safety.SetupError, "dependencies are missing"):
            self.install(payload=path)
        self.assertFalse((self.pref / "packages/synapse.json").exists())

    def test_corrupt_payload_rejected(self):
        with zipfile.ZipFile(self.payload) as src:
            data = {name: src.read(name) for name in src.namelist()}
        data["VERSION"] = b"tampered\n"
        bad = self.sandbox / "bad.zip"
        build_payload.zip_bytes(bad, data)
        with self.assertRaisesRegex(safety.SetupError, "checksum"):
            self.install(payload=bad)

    def test_running_houdini_is_never_terminated(self):
        with patch.object(discovery, "running_houdini", return_value=[{"name": "houdini.exe", "pid": "123"}]):
            with self.assertRaisesRegex(safety.SetupError, "Save your work"):
                engine.install(self.app, [self.pref], self.home, archive=self.payload, hfs=self.hfs)
        self.assertFalse(self.app.exists())

    def test_unwritable_destination_failure_preserves_registration(self):
        self.install()
        package = self.pref / "packages/synapse.json"
        before = package.read_bytes()
        with patch.object(engine, "check_writable", side_effect=safety.SetupError("Cannot write to destination")):
            with self.assertRaisesRegex(safety.SetupError, "Cannot write"):
                self.install()
        self.assertEqual(package.read_bytes(), before)

    def test_file_as_destination_is_a_real_os_failure(self):
        blocked = self.sandbox / "blocked"
        blocked.write_bytes(b"user file")
        with self.assertRaises((safety.SetupError, OSError)):
            engine.install(blocked / "application", [self.pref], self.home, archive=self.payload,
                           hfs=self.hfs, sandbox=self.sandbox)
        self.assertEqual(blocked.read_bytes(), b"user file")
        self.assertFalse((self.pref / "packages/synapse.json").exists())

    def test_unverified_compatibility_requires_acknowledgement(self):
        self.target.update(version="22.0.429", tested=False)
        with self.assertRaisesRegex(safety.SetupError, "unverified"):
            self.install()
        result = engine.install(self.app, [self.pref], self.home, archive=self.payload,
                     hfs=self.hfs, allow_unverified=True, sandbox=self.sandbox)
        self.assertEqual(result["status"], "PASS")

    def test_verify_is_read_only_and_models_are_manual(self):
        self.install()
        paths = [self.app / engine.STATE, self.pref / "packages/synapse.json", self.home / ".synapse/install_stamp.json"]
        before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths]
        with patch.dict("os.environ", {}, clear=True):
            report = engine.verify(self.app)
        self.assertEqual(before, [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths])
        self.assertTrue(any("credentials" in item for item in report["manual"]))

    def test_preferences_expand_version_and_include_redirected_documents(self):
        paths = discovery.preference_candidates("22.0.400", {"HOUDINI_USER_PREF_DIR": str(self.sandbox / "custom/__HVER__")}, self.home, self.sandbox / "redirected")
        self.assertEqual(paths[0]["path"], str(self.sandbox / "custom/22.0"))
        self.assertTrue(any(x["path"] == str(self.sandbox / "redirected/houdini22.0") for x in paths))

    def test_moneta_distribution_paths_do_not_use_sibling_checkout(self):
        data = registration.installed_package(self.app / "versions/build", {"moneta": {"version": "1.2.0rc1"}}, self.home)
        env = {item["var"]: item for item in data["env"]}
        self.assertIn("dependencies/moneta/src", env["PYTHONPATH"]["value"][0])
        self.assertEqual(env["PXR_PLUGINPATH_NAME"]["method"], "prepend")
        self.assertTrue(env["SYNAPSE_PANEL_SETTINGS"]["value"].startswith("${SYNAPSE_PANEL_SETTINGS-"))


if __name__ == "__main__":
    unittest.main()
