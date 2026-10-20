"""Installer choice/sequence controls; fixtures are disposable and non-executable."""
import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_adversarial as hostile
from synapse_setup import engine, safety, native_check, native_policy, registration


class NativeChoiceTests(unittest.TestCase):
    setUp = hostile.InstallerAdversarialTests.setUp
    _remove_temp = hostile.InstallerAdversarialTests._remove_temp
    install = hostile.InstallerAdversarialTests.install

    @property
    def registration(self):
        return self.pref / "packages/synapse.json"

    def seed(self, env):
        old = self.sandbox / "old-source"
        package = {"name": "synapse", "enable": True, "load_package_once": True,
                   "env": [{"var": "SYNAPSE_ROOT", "value": old.as_posix()}, *env],
                   "hpath": (old / "houdini").as_posix()}
        self.registration.parent.mkdir(parents=True, exist_ok=True)
        data = safety.json_bytes(package)
        self.registration.write_bytes(data)
        return data

    def values(self):
        package = json.loads(self.registration.read_text())
        return {row["var"]: row.get("value") for row in package["env"]}

    def test_fresh_without_native_artifact_sets_explicit_off(self):
        self.install()
        self.assertEqual(self.values().get("MONETA_NATIVE"), "0")

    def test_manual_off_and_custom_choices_survive_repeat_and_uninstall(self):
        original = self.seed([{"var": "MONETA_NATIVE", "value": "off"},
                              {"var": "SYNTHETIC_ARTIST_CHOICE", "value": "retain-exactly"}])
        self.install(migrate=True)
        self.assertEqual(self.values().get("MONETA_NATIVE"), "off")
        self.assertEqual(self.values().get("SYNTHETIC_ARTIST_CHOICE"), "retain-exactly")
        before = self.registration.read_bytes()
        self.install()
        self.assertEqual(self.registration.read_bytes(), before)
        engine.uninstall(self.app, sandbox=self.sandbox)
        self.assertEqual(self.registration.read_bytes(), original)

    def test_shorthand_off_is_preserved(self):
        self.seed([{"MONETA_NATIVE": "no"}, {"SYNTHETIC_ARTIST_CHOICE": "keep"}])
        self.install(migrate=True)
        self.assertEqual(self.values().get("MONETA_NATIVE"), "no")
        self.assertEqual(self.values().get("SYNTHETIC_ARTIST_CHOICE"), "keep")

    def test_extra_import_path_survives_but_old_runtime_paths_do_not(self):
        old = self.sandbox / "old-source"
        extra = (self.sandbox / "artist-modules").as_posix()
        self.seed([{"var": "MONETA_NATIVE", "value": "0"},
                   {"var": "PYTHONPATH", "value": [(old / "python").as_posix(), old.as_posix(), extra], "method": "prepend"}])
        result = self.install(migrate=True)
        paths = self.values()["PYTHONPATH"]
        self.assertIn(extra, paths)
        self.assertIn((Path(result["runtime"]) / "python").as_posix(), paths)
        self.assertNotIn(old.as_posix(), paths)
        self.assertNotIn((old / "python").as_posix(), paths)

    def test_unqualified_existing_on_refuses_without_changing_registration(self):
        original = self.seed([{"var": "MONETA_NATIVE", "value": "1"}])
        with self.assertRaisesRegex(safety.SetupError, "[Nn]ative.*(artifact|qualification)"):
            self.install(migrate=True)
        self.assertEqual(self.registration.read_bytes(), original)
        self.assertFalse((self.home / ".synapse/install_stamp.json").exists())
        self.assertFalse((self.app / engine.STATE).exists())

    def test_duplicate_native_choices_refuse_before_mutation(self):
        original = self.seed([{"var": "MONETA_NATIVE", "value": "0"},
                              {"var": "MONETA_NATIVE", "value": "1"}])
        with self.assertRaisesRegex(safety.SetupError, "[Dd]uplicate.*MONETA_NATIVE"):
            self.install(migrate=True)
        self.assertEqual(self.registration.read_bytes(), original)

    def test_conditional_native_choice_refuses_before_mutation(self):
        original = self.seed([{"var": "MONETA_NATIVE", "value": "${MONETA_NATIVE-0}"}])
        with self.assertRaisesRegex(safety.SetupError, "MONETA_NATIVE.*(literal|conditional)"):
            self.install(migrate=True)
        self.assertEqual(self.registration.read_bytes(), original)

    def test_existing_managed_edit_still_refuses_unchanged(self):
        self.install()
        package = json.loads(self.registration.read_text())
        package["env"].append({"var": "MONETA_NATIVE", "value": "1"})
        original = safety.json_bytes(package)
        self.registration.write_bytes(original)
        with self.assertRaisesRegex(safety.SetupError, "changed or removed outside Setup"):
            self.install()
        self.assertEqual(self.registration.read_bytes(), original)

    def test_failed_native_check_preserves_existing_registration_and_stamp(self):
        original = self.seed([{"var": "MONETA_NATIVE", "value": "1"}])
        stamp = self.home / ".synapse/install_stamp.json"
        stamp.parent.mkdir(parents=True)
        stamp.write_bytes(b'{"synthetic_prior_stamp":true}\n')
        stamp_before = stamp.read_bytes()
        choice = {"status": "PENDING_EXECUTION", "value": "1", "site": str(self.sandbox / "unexecuted-native"),
                  "files": {}, "pyd_sha256": "synthetic-not-a-binary", "reason": "transaction fixture only"}
        with patch.object(native_policy, "resolve", return_value=choice), patch.object(native_check, "qualify", side_effect=safety.SetupError("Native qualification deliberately failed")):
            with self.assertRaisesRegex(safety.SetupError, "deliberately failed"):
                self.install(migrate=True)
        self.assertEqual(self.registration.read_bytes(), original)
        self.assertEqual(stamp.read_bytes(), stamp_before)
        self.assertFalse((self.app / engine.STATE).exists())

    def test_noncanonical_hpath_is_refused_without_discarding_it(self):
        original = json.loads(self.seed([{"var": "MONETA_NATIVE", "value": "0"}]))
        original["hpath"] = (self.sandbox / "artist-custom-houdini-path").as_posix()
        before = safety.json_bytes(original)
        self.registration.write_bytes(before)
        with self.assertRaisesRegex(safety.SetupError, "hpath"):
            self.install(migrate=True)
        self.assertEqual(self.registration.read_bytes(), before)

    def test_native_precedence_survives_houdini_list_prepend_order(self):
        old_native = (self.sandbox / "existing-native").as_posix()
        new_native = (self.sandbox / "reviewed-bundled-native").as_posix()
        previous = json.loads(self.seed([{"var": "MONETA_NATIVE", "value": "1"},
                                        {"var": "PYTHONPATH", "value": [old_native], "method": "prepend"}]))
        result = registration.installed_package(self.sandbox / "new-runtime", {"moneta": None}, self.home,
                                                 previous=previous, native_value="1", native_site=new_native)
        row = next(r for r in result["env"] if r["var"] == "PYTHONPATH")
        # Measured H22 package behavior: list+prepend reverses the entries;
        # a semicolon-delimited string retains its internal path order.
        order = list(reversed(row["value"])) if isinstance(row["value"], list) else row["value"].split(";")
        self.assertLess(order.index(new_native), order.index(old_native))

    def test_off_edit_during_native_check_is_preserved_and_activation_refused(self):
        original = json.loads(self.seed([{"var": "MONETA_NATIVE", "value": "1"}]))
        edited = {**original, "env": [{**r, "value": "0"} if r["var"] == "MONETA_NATIVE" else r for r in original["env"]]}
        edited_bytes = safety.json_bytes(edited)
        choice = {"status": "PENDING_EXECUTION", "value": "1", "site": str(self.sandbox / "unexecuted-native"),
                  "files": {}, "pyd_sha256": "synthetic-not-a-binary", "reason": "transaction fixture only"}
        def edit_while_qualifying(*args):
            self.registration.write_bytes(edited_bytes)
            return {"status": "synthetic qualifier response; no host executed"}
        with patch.object(native_policy, "resolve", return_value=choice), patch.object(native_check, "qualify", side_effect=edit_while_qualifying):
            with self.assertRaisesRegex(safety.SetupError, "changed"):
                self.install(migrate=True)
        self.assertEqual(self.registration.read_bytes(), edited_bytes)
        self.assertFalse((self.home / ".synapse/install_stamp.json").exists())
        self.assertFalse((self.app / engine.STATE).exists())

    def test_new_registration_during_native_check_is_preserved_and_activation_refused(self):
        original = self.seed([{"var": "MONETA_NATIVE", "value": "1"}])
        extra = self.pref / "packages/second-synapse.json"
        choice = {"status": "PENDING_EXECUTION", "value": "1", "site": str(self.sandbox / "unexecuted-native"),
                  "files": {}, "pyd_sha256": "synthetic-not-a-binary", "reason": "namespace fixture only"}
        def add_while_qualifying(*args):
            extra.write_bytes(original)
            return {"status": "synthetic qualifier response; no host executed"}
        with patch.object(native_policy, "resolve", return_value=choice), patch.object(native_check, "qualify", side_effect=add_while_qualifying):
            with self.assertRaisesRegex(safety.SetupError, "changed|Multiple"):
                self.install(migrate=True)
        self.assertEqual(self.registration.read_bytes(), original)
        self.assertEqual(extra.read_bytes(), original)
        self.assertFalse((self.app / engine.STATE).exists())

    def test_managed_on_plus_foreign_off_registration_is_ambiguous(self):
        choice = {"status": "PENDING_EXECUTION", "value": "1", "site": str(self.sandbox / "unexecuted-native"),
                  "files": {}, "pyd_sha256": "synthetic-not-a-binary", "reason": "ownership fixture only"}
        # Mock only the expensive qualifier boundary; this exercises ownership,
        # never claims that these synthetic bytes are an executed native module.
        with patch.object(native_policy, "resolve", side_effect=lambda *a, **k: dict(choice)), patch.object(native_check, "qualify", return_value={}):
            self.install()
            owned_before = self.registration.read_bytes()
            foreign = self.pref / "packages/artist-synapse-off.json"
            off = json.loads(owned_before)
            for row in off["env"]:
                if row["var"] == "MONETA_NATIVE":
                    row["value"] = "0"
            off.pop("synapse_setup_owner", None)
            foreign_bytes = safety.json_bytes(off)
            foreign.write_bytes(foreign_bytes)
            with self.assertRaisesRegex(safety.SetupError, "Multiple"):
                self.install(migrate=True)
        self.assertEqual(self.registration.read_bytes(), owned_before)
        self.assertEqual(foreign.read_bytes(), foreign_bytes)


class NativeSelectionTests(unittest.TestCase):
    """Selection states only; no fixture here claims installed native execution."""
    def setUp(self):
        self.manifest = {"native": {"synthetic_selection_fixture": True}, "moneta": {
            "version": "1.3.0", "source_revision": "4f7afc73736aecce6d55d5e03f28fb3137d474d3"}}
        self.target = {"houdini": "22.0.400", "python_full": "3.13.10", "platform": "win32", "bits": 64}
        self.runtime = Path("synthetic-unexecuted-runtime")

    def test_supported_fresh_artifact_is_pending_never_a_pass(self):
        result = native_policy.resolve(self.manifest, self.target, self.runtime, environ={})
        self.assertEqual(result["status"], "PENDING_EXECUTION")
        self.assertEqual(result["value"], "1")
        self.assertNotIn("execution", result)

    def test_unsupported_fresh_is_off_and_existing_on_is_refused(self):
        unsupported = {**self.target, "python_full": "3.14.0"}
        result = native_policy.resolve(self.manifest, unsupported, self.runtime, environ={})
        self.assertEqual((result["status"], result["value"]), ("UNAVAILABLE", "0"))
        previous = {"env": [{"var": "MONETA_NATIVE", "value": "1"}]}
        with self.assertRaisesRegex(safety.SetupError, "unavailable"):
            native_policy.resolve(self.manifest, unsupported, self.runtime, previous, environ={})

    def test_explicit_off_and_legacy_default_are_preserved_with_bundle(self):
        for previous, value in (({"env": [{"var": "MONETA_NATIVE", "value": "off"}]}, "off"),
                                ({"name": "synapse", "env": []}, "0")):
            with self.subTest(previous=previous):
                result = native_policy.resolve(self.manifest, self.target, self.runtime, previous, environ={})
                self.assertEqual((result["status"], result["value"]), ("OFF", value))


class NativeProofContractTests(unittest.TestCase):
    setUp = hostile.InstallerAdversarialTests.setUp
    _remove_temp = hostile.InstallerAdversarialTests._remove_temp

    def test_complete_report_requires_real_scan_and_decay_witnesses(self):
        # Actual Rust exports/observed c_call names are scan and decay_batch;
        # Moneta's Python query wrapper is not the compiled scan callable.
        report = {"status": "PASS", "phase": "write", "primary_backend": "moneta",
                  "source_commit": "synthetic-commit", "native_pyd_sha256": "synthetic-pyd",
                  "native_value": "1", "encrypted_records": 3, "scene_save_or_reopen": True,
                  "preference_isolated": True, "source_or_backend_injected": False,
                  "native_fallbacks": {}, "native_calls_delta": {"scan": 3, "decay": 3},
                  "native_c_call_witness": {"scan": 3, "decay_batch": 3}}
        manifest, choice = {"source_revision": "synthetic-commit"}, {"pyd_sha256": "synthetic-pyd", "value": "1"}
        self.assertTrue(native_check.accepted_report(report, "write", manifest, choice))
        for key, wrong in (("primary_backend", "jsonl"), ("source_commit", "different-commit"),
                           ("native_pyd_sha256", "different-binary"), ("preference_isolated", False),
                           ("source_or_backend_injected", True), ("native_fallbacks", {"scan": 1}),
                           ("native_calls_delta", {"scan": 0, "decay": 3}),
                           ("native_calls_delta", {"scan": True, "decay": 3}),
                           ("native_c_call_witness", {"query": 3, "decay_batch": 3}),
                           ("native_c_call_witness", {"scan": 3})):
            with self.subTest(key=key, wrong=wrong):
                self.assertFalse(native_check.accepted_report({**report, key: wrong}, "write", manifest, choice))

    def test_isolated_preferences_use_houdinis_required_version_token(self):
        runtime = self.sandbox / "unexecuted-runtime"
        manifest = {"moneta": None, "source_revision": "synthetic-contract-fixture"}
        planned = registration.installed_package(runtime, manifest, self.home)
        choice = {"value": "1", "site": str(self.sandbox / "unexecuted-native"), "files": {}, "pyd_sha256": "synthetic-not-a-binary"}
        root = self.sandbox / "synapse-native-check-pref-contract"
        def owned_temp(**kwargs):
            root.mkdir(parents=True)
            return str(root)
        def inspect_launch(command, **kwargs):
            pref = kwargs["env"]["HOUDINI_USER_PREF_DIR"]
            self.assertIn("__HVER__", pref, "Houdini ignores a preference override without its version token")
            self.assertTrue((Path(pref.replace("__HVER__", "22.0")) / "packages/synapse.json").is_file())
            config = json.loads(Path(command[-1]).read_text())
            Path(config["output"]).write_bytes(safety.json_bytes({"status": "FAIL", "error": "synthetic launch inspection only"}))
            return SimpleNamespace(returncode=1, stdout=b"no host executed")
        with patch.object(native_check.tempfile, "mkdtemp", side_effect=owned_temp), patch.object(native_check.subprocess, "run", side_effect=inspect_launch):
            with self.assertRaisesRegex(safety.SetupError, "[Nn]ative qualification"):
                native_check.qualify(runtime, manifest, {"hfs": str(self.hfs), "houdini": "22.0.400"}, planned, choice)

    def test_a_zero_exit_and_incomplete_pass_are_not_native_evidence(self):
        runtime = self.sandbox / "unexecuted-runtime"
        manifest = {"moneta": None, "source_revision": "synthetic-contract-fixture"}
        planned = registration.installed_package(runtime, manifest, self.home)
        choice = {"value": "1", "site": str(self.sandbox / "unexecuted-native"), "files": {}, "pyd_sha256": "synthetic-not-a-binary"}
        root = self.sandbox / "synapse-native-check-contract"
        def owned_temp(**kwargs):
            root.mkdir(parents=True)
            return str(root)
        def untrusted_pass(command, **kwargs):
            config = json.loads(Path(command[-1]).read_text())
            Path(config["output"]).write_bytes(safety.json_bytes({"status": "PASS", "phase": config["phase"]}))
            return SimpleNamespace(returncode=0, stdout=b"synthetic incomplete receipt; no interpreter was executed")
        with patch.object(native_check.tempfile, "mkdtemp", side_effect=owned_temp), patch.object(native_check.subprocess, "run", side_effect=untrusted_pass):
            with self.assertRaisesRegex(safety.SetupError, "[Nn]ative qualification"):
                native_check.qualify(runtime, manifest, {"hfs": str(self.hfs), "houdini": "22.0.400"}, planned, choice)


if __name__ == "__main__":
    unittest.main()
