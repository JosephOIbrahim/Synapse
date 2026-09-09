"""Independent hostile lifecycle checks; synthetic payloads never load Houdini.

Run: python -B -m unittest discover -s installer/tests -p test_adversarial.py -v
All filesystem mutations are below one verified temporary test directory.
"""
from __future__ import annotations

import json
from contextlib import redirect_stdout
import io
from pathlib import Path
import shutil
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_payload
import setup_cli
from synapse_setup import discovery, engine, safety


class SimulatedProcessDeath(BaseException):
    """Bypass ordinary exception rollback, as termination/power loss would."""


def write_payload(path: Path, version="5.67.4", extra=None):
    # These are deliberately synthetic bytes. We test installer ownership and
    # transaction behavior, never advertise a native-runtime validation result.
    content = {
        "VERSION": (version + "\n").encode(),
        "python/synapse/__init__.py": b"# synthetic package\n",
        "shared/__init__.py": b"# synthetic shared package\n",
        "houdini/python_panels/synapse_panel.pypanel": b"<pythonPanelDocument/>",
        "houdini/toolbar/synapse.shelf": b"<shelfDocument/>",
        "houdini/scripts/python/synapse_shelf.py": b"# callbacks\n",
        "houdini/scripts/python/tokens.py": b"# tokens\n",
        "houdini/scripts/python/synapse_styles.py": b"# styles\n",
        "houdini/config/Icons/SYNAPSE_synapse.svg": b"<svg/>",
        "python/synapse/_vendor/pydantic_core/_pydantic_core.cp313-win_amd64.pyd": b"synthetic ABI fixture",
        "python/synapse/_vendor/jiter/jiter.cp313-win_amd64.pyd": b"synthetic ABI fixture",
    }
    for name in ("anthropic", "httpx", "httpcore", "anyio", "pydantic", "idna", "sniffio"):
        content[f"python/synapse/_vendor/{name}/__init__.py"] = b"# dependency fixture\n"
    content.update(extra or {})
    manifest = {
        "schema": "synapse-payload-1", "version": version,
        "tested_houdini": "22.0.400", "tested_python": "3.13",
        "moneta": None, "files": {name: safety.digest(data) for name, data in content.items()},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in content.items():
            archive.writestr(name, data)
        archive.writestr(engine.MANIFEST, safety.json_bytes(manifest))
    return path


class InstallerAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.temp_parent = Path(tempfile.gettempdir()).resolve()
        self.work = Path(tempfile.mkdtemp(prefix="synapse-adversarial-")).resolve()
        self.addCleanup(self._remove_temp)
        self.sandbox = self.work / "sandbox"
        self.app = self.sandbox / "Programs/SYNAPSE"
        self.pref = self.sandbox / "Documents/houdini22.0"
        self.home = self.sandbox / "Home"
        self.hfs = self.sandbox / "FakeHoudini"
        self.payload = write_payload(self.sandbox / "input/runtime.zip")
        self.target = {"hfs": str(self.hfs), "version": "22.0.400", "python": "3.13", "tested": True}
        self.validator = patch.object(discovery, "validate_houdini", side_effect=lambda _: dict(self.target))
        self.validator.start()
        self.addCleanup(self.validator.stop)

    def _remove_temp(self):
        # Verify the absolute recursive-cleanup target immediately before removal.
        target = self.work.resolve()
        if target.parent != self.temp_parent or not target.name.startswith("synapse-adversarial-"):
            raise AssertionError("Refusing cleanup outside the named test directory")
        shutil.rmtree(target)

    def install(self, *, payload=None, migrate=False):
        return engine.install(self.app, [self.pref], self.home, archive=payload or self.payload,
                              hfs=self.hfs, migrate=migrate, sandbox=self.sandbox)

    def test_interrupted_install_replays_and_preserves_user_data(self):
        registration = self.pref / "packages/synapse.json"
        real_apply = safety.apply_value

        def crash_after_registration(path, value):
            real_apply(path, value)
            if Path(path) == registration:
                raise SimulatedProcessDeath()

        with patch.object(safety, "apply_value", side_effect=crash_after_registration):
            with self.assertRaises(SimulatedProcessDeath):
                self.install()
        self.assertTrue((self.app / engine.JOURNAL).is_file())
        self.assertFalse((self.app / engine.STATE).exists())
        note = self.home / ".synapse/artist-notes.txt"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_bytes(b"artist owns this")
        result = self.install()
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["recovered_interrupted_transaction"])
        self.assertEqual(note.read_bytes(), b"artist owns this")
        self.assertFalse((self.app / engine.JOURNAL).exists())

    def test_uninstall_recovers_interrupted_first_install_before_refusing_no_receipt(self):
        registration = self.pref / "packages/synapse.json"
        real_apply = safety.apply_value

        def crash_after_registration(path, value):
            real_apply(path, value)
            if Path(path) == registration:
                raise SimulatedProcessDeath()

        with patch.object(safety, "apply_value", side_effect=crash_after_registration):
            with self.assertRaises(SimulatedProcessDeath):
                self.install()
        try:
            engine.uninstall(self.app, sandbox=self.sandbox)
        except safety.SetupError:
            pass  # No completed installation is a valid answer AFTER rollback.
        self.assertFalse(registration.exists(), "Uninstaller left an activated partial installation")
        self.assertFalse((self.app / engine.JOURNAL).exists())

    def test_interrupted_uninstall_transaction_replays(self):
        self.install()
        real_apply = safety.apply_value

        def crash_after_unregistered_state(path, value):
            real_apply(path, value)
            if Path(path) == self.app / engine.STATE:
                raise SimulatedProcessDeath()

        with patch.object(safety, "apply_value", side_effect=crash_after_unregistered_state):
            with self.assertRaises(SimulatedProcessDeath):
                engine.uninstall(self.app, sandbox=self.sandbox)
        self.assertTrue((self.app / engine.JOURNAL).exists())
        result = engine.uninstall(self.app, sandbox=self.sandbox)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse((self.pref / "packages/synapse.json").exists())
        self.assertFalse((self.app / engine.STATE).exists())

    def test_interrupted_runtime_removal_resumes(self):
        result = self.install()
        runtime_file = Path(result["runtime"]) / "VERSION"
        real_unlink = Path.unlink

        def fail_at_runtime(path, *args, **kwargs):
            if path == runtime_file:
                raise PermissionError("Synthetic file lock after registration was removed")
            return real_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", new=fail_at_runtime):
            with self.assertRaises(PermissionError):
                engine.uninstall(self.app, sandbox=self.sandbox)
        self.assertTrue(engine.state_for(self.app)["unregistered"])
        self.assertFalse((self.pref / "packages/synapse.json").exists())
        self.assertEqual(engine.uninstall(self.app, sandbox=self.sandbox)["status"], "PASS")
        self.assertFalse(runtime_file.exists())

    def test_uninstall_retains_unknown_and_changed_runtime_files(self):
        runtime = Path(self.install()["runtime"])
        changed = runtime / "shared/__init__.py"
        changed.write_bytes(b"artist customization")
        note = runtime / ".synapse/artist-notes.txt"
        note.parent.mkdir(parents=True)
        note.write_bytes(b"do not remove")
        result = engine.uninstall(self.app, sandbox=self.sandbox)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(changed.read_bytes(), b"artist customization")
        self.assertEqual(note.read_bytes(), b"do not remove")
        self.assertFalse((self.pref / "packages/synapse.json").exists())

    def test_repeat_migration_never_discards_recreated_legacy_file(self):
        legacy = self.pref / "packages/legacy-synapse.json"
        legacy.parent.mkdir(parents=True)
        first = safety.json_bytes({"name": "synapse", "hpath": "first-artist-location"})
        second = safety.json_bytes({"name": "synapse", "hpath": "new-artist-location"})
        legacy.write_bytes(first)
        self.install(migrate=True)
        self.assertFalse(legacy.exists())
        legacy.write_bytes(second)
        upgrade = write_payload(self.sandbox / "input/upgrade.zip", version="5.67.5")
        try:
            self.install(payload=upgrade, migrate=True)
        except safety.SetupError:
            self.assertEqual(legacy.read_bytes(), second)
            return  # Refusing a second conflicting owner is conservative.
        engine.uninstall(self.app, sandbox=self.sandbox)
        self.assertEqual(legacy.read_bytes(), second,
                         "Repeat migration discarded the later file and restored an obsolete backup")

    def test_recovery_preserves_file_changed_after_crash(self):
        target = self.sandbox / "user/setting.json"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"before")
        op = safety.change(target, b"installer")
        target.write_bytes(b"user edited after crash")
        journal = self.sandbox / "journal.json"
        safety.atomic_write(journal, safety.json_bytes({"schema": "synapse-transaction-1", "committed": False, "changes": [op]}))
        with self.assertRaises(safety.SetupError):
            safety.recover(journal)
        self.assertEqual(target.read_bytes(), b"user edited after crash")
        self.assertTrue(journal.exists())

    def test_sandbox_recovery_refuses_external_journal_target(self):
        outside = self.work / "outside-sandbox/artist-file.txt"
        outside.parent.mkdir()
        outside.write_bytes(b"valuable user data")
        self.app.mkdir(parents=True)
        op = {"path": str(outside), "before": None, "after": safety.encode(outside.read_bytes())}
        safety.atomic_write(self.app / engine.JOURNAL, safety.json_bytes({"schema": "synapse-transaction-1", "committed": False, "changes": [op]}))
        try:
            self.install()
        except safety.SetupError:
            pass
        self.assertTrue(outside.is_file(), "Recovery deleted a file outside the authorized sandbox")
        self.assertEqual(outside.read_bytes(), b"valuable user data")

    def test_sandbox_uninstall_refuses_external_stamp_in_receipt(self):
        self.install()
        outside = self.work / "outside-sandbox/artist-file.txt"
        outside.parent.mkdir()
        outside.write_bytes(b"current artist data")
        state = engine.state_for(self.app)
        state["stamp"] = {"path": str(outside), "sha256": safety.file_hash(outside), "original": safety.encode(b"obsolete data")}
        safety.atomic_write(self.app / engine.STATE, safety.json_bytes(state))
        try:
            engine.uninstall(self.app, sandbox=self.sandbox)
        except safety.SetupError:
            pass
        self.assertEqual(outside.read_bytes(), b"current artist data",
                         "Receipt-controlled stamp path escaped the sandbox")

    def test_payload_rejects_path_aliases_before_any_extraction(self):
        alias = write_payload(self.sandbox / "input/alias.zip",
                              extra={"shared/./__init__.py": b"# synthetic shared package\n"})
        with self.assertRaises(safety.SetupError):
            engine.load_manifest(alias)

    def test_member_path_rejects_traversal_ads_and_device_names(self):
        for name in ("../escape", "/absolute", "C:/drive", "x:stream", "a\\b", "NUL", "a/COM1.txt", "a/LPT9", "a/trailing.", "a/trailing "):
            with self.subTest(name=name), self.assertRaises(safety.SetupError):
                safety.member_path(self.sandbox, name)

    def test_no_links_rejects_reparse_ancestor(self):
        linked = self.sandbox / "junction"
        linked.mkdir(parents=True)
        real_lstat = Path.lstat

        def reparse_lstat(path, *args, **kwargs):
            value = real_lstat(path, *args, **kwargs)
            if path == linked:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
            return value

        with patch.object(Path, "lstat", new=reparse_lstat):
            with self.assertRaises(safety.SetupError):
                safety.no_links(linked / "new-child.txt")

    def test_cache_handler_runtime_dependency_is_packaged(self):
        # handlers_cache.py imports this top-level host helper at runtime.
        self.assertTrue(build_payload.permitted("host/cache_host_probe.py"))

    def test_runtime_discovery_rejects_python_314_even_for_matching_build(self):
        self.validator.stop()
        for rel in ("bin/hconfig.exe", "bin/houdini.exe", "python314/python.exe"):
            path = self.hfs / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic executable placeholder, never run")
        with patch.object(discovery, "file_version", return_value="22.0.400"), patch.object(discovery, "run", return_value=SimpleNamespace(returncode=0, stdout="3.14\n")):
            with self.assertRaises(ValueError):
                discovery.validate_houdini(self.hfs)

    def test_external_duplicate_reached_by_package_path_cannot_be_migrated(self):
        # SideFX's package_path is a queue of additional directories; it is not
        # equivalent to a recursive scan of the physical packages directory.
        # https://www.sidefx.com/docs/houdini/ref/plugins.html#package_path
        studio = self.work / "studio-packages"
        studio.mkdir()
        duplicate = studio / "synapse.json"
        duplicate.write_bytes(safety.json_bytes({"name": "synapse", "hpath": "studio-owned"}))
        packages = self.pref / "packages"
        packages.mkdir(parents=True)
        dispatcher = packages / "studio.json"
        dispatcher.write_bytes(safety.json_bytes({"package_path": studio.as_posix()}))
        with patch.object(discovery, "running_houdini", return_value=[]), patch.object(discovery, "external_package_dirs", return_value=[]):
            with self.assertRaises(safety.SetupError):
                engine.preflight(self.app, [self.pref], self.home, archive=self.payload,
                                 hfs=self.hfs, migrate=True)
        self.assertEqual(json.loads(duplicate.read_bytes())["hpath"], "studio-owned")

    def test_unreferenced_nested_package_backup_is_not_an_active_registration(self):
        packages = self.pref / "packages"
        backup = packages / "old-backups/synapse.json"
        backup.parent.mkdir(parents=True)
        backup.write_bytes(safety.json_bytes({"name": "synapse", "hpath": "old-backup"}))
        # SideFX explicitly does not scan subdirectories unless a package_path
        # entry names them: https://www.sidefx.com/docs/houdini/ref/plugins.html
        self.assertEqual(engine.registrations(packages), [])

    def test_recovery_cannot_delete_unrelated_tool_configuration(self):
        self.install()
        other_tool = self.pref / "packages/artist-other-tool.json"
        original = safety.json_bytes({"name": "unrelated-tool", "hpath": "artist-owned"})
        other_tool.write_bytes(original)
        # Being inside the same preferences/packages directory is not evidence
        # that SYNAPSE previously owned this unrelated tool's registration.
        op = {"path": str(other_tool), "before": None, "after": safety.encode(original)}
        safety.atomic_write(self.app / engine.JOURNAL, safety.json_bytes({
            "schema": "synapse-transaction-1", "committed": False, "changes": [op],
        }))
        try:
            self.install()
        except safety.SetupError:
            pass
        self.assertTrue(other_tool.exists(), "Recovery treated every package JSON as installer-owned")
        self.assertEqual(other_tool.read_bytes(), original)

    def test_cli_uninstall_check_uses_recovery_context_when_receipt_is_absent(self):
        registration = self.pref / "packages/synapse.json"
        real_apply = safety.apply_value

        def crash_after_registration(path, value):
            real_apply(path, value)
            if Path(path) == registration:
                raise SimulatedProcessDeath()

        with patch.object(safety, "apply_value", side_effect=crash_after_registration):
            with self.assertRaises(SimulatedProcessDeath):
                self.install()
        # Exactly the current Inno InitializeUninstall call: it passes app and
        # sandbox, but no --home argument. No real discovery process is run.
        with redirect_stdout(io.StringIO()) as output:
            code = setup_cli.main(["uninstall-check", "--app", str(self.app),
                                   "--sandbox", str(self.sandbox)])
        self.assertEqual(code, 0, output.getvalue())
        self.assertTrue(registration.exists(), "The check should leave rollback to actual uninstall")

    def test_cli_uninstall_resumes_after_engine_finished_before_windows_cleanup(self):
        self.install()
        note = self.home / ".synapse/artist-notes.txt"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_bytes(b"artist data survives the final uninstall boundary")
        self.assertEqual(engine.uninstall(self.app, sandbox=self.sandbox)["status"], "PASS")
        self.assertFalse((self.app / engine.STATE).exists())
        self.assertTrue((self.app / "uninstall-receipt.json").exists())
        # Inno can terminate after its engine subprocess finishes but before
        # deleting maintenance files/Windows registration. Its next launch must
        # pass both existing front doors and finish that remaining cleanup.
        for action in ("uninstall-check", "uninstall"):
            with self.subTest(action=action), redirect_stdout(io.StringIO()) as output:
                code = setup_cli.main([action, "--app", str(self.app),
                                       "--sandbox", str(self.sandbox)])
                self.assertEqual(code, 0, output.getvalue())
        self.assertEqual(note.read_bytes(), b"artist data survives the final uninstall boundary")

    def test_cli_uninstall_check_allows_valid_pending_upgrade_recovery(self):
        self.install()
        registration = self.pref / "packages/synapse.json"
        real_apply = safety.apply_value

        def crash_after_registration(path, value):
            real_apply(path, value)
            if Path(path) == registration:
                raise SimulatedProcessDeath()

        upgraded = write_payload(self.sandbox / "input/newer.zip", version="5.67.5")
        with patch.object(safety, "apply_value", side_effect=crash_after_registration):
            with self.assertRaises(SimulatedProcessDeath):
                self.install(payload=upgraded)
        self.assertTrue((self.app / engine.STATE).exists())
        self.assertTrue((self.app / engine.JOURNAL).exists())
        with redirect_stdout(io.StringIO()) as output:
            code = setup_cli.main(["uninstall-check", "--app", str(self.app),
                                   "--sandbox", str(self.sandbox)])
        self.assertEqual(code, 0, output.getvalue())
        self.assertEqual(engine.uninstall(self.app, sandbox=self.sandbox)["status"], "PASS")

    def test_first_install_rollback_keeps_context_until_completion_is_durable(self):
        registration = self.pref / "packages/synapse.json"
        real_apply = safety.apply_value

        def crash_after_registration(path, value):
            real_apply(path, value)
            if Path(path) == registration:
                raise SimulatedProcessDeath()

        with patch.object(safety, "apply_value", side_effect=crash_after_registration):
            with self.assertRaises(SimulatedProcessDeath):
                self.install()
        real_recover = engine.recover_install

        def crash_after_completed_rollback(*args, **kwargs):
            result = real_recover(*args, **kwargs)
            if kwargs.get("perform", True):
                raise SimulatedProcessDeath()
            return result

        with patch.object(engine, "recover_install", side_effect=crash_after_completed_rollback):
            with self.assertRaises(SimulatedProcessDeath):
                engine.uninstall(self.app, sandbox=self.sandbox)
        self.assertFalse(registration.exists())
        self.assertFalse((self.app / engine.STATE).exists())
        with redirect_stdout(io.StringIO()) as output:
            code = setup_cli.main(["uninstall-check", "--app", str(self.app),
                                   "--sandbox", str(self.sandbox)])
        self.assertEqual(code, 0, output.getvalue())
        self.assertEqual(engine.uninstall(self.app, sandbox=self.sandbox)["status"], "PASS")

    def test_completed_uninstall_rejects_external_receipt_context(self):
        self.install()
        self.assertEqual(engine.uninstall(self.app, sandbox=self.sandbox)["status"], "PASS")
        receipt = self.app / "uninstall-receipt.json"
        value = safety.read_json(receipt)
        outside = self.work / "outside-sandbox/artist-file.txt"
        outside.parent.mkdir()
        outside.write_bytes(b"keep this file")
        value["former_installation"]["stamp"]["path"] = str(outside)
        safety.atomic_write(receipt, safety.json_bytes(value))
        with redirect_stdout(io.StringIO()) as output:
            code = setup_cli.main(["uninstall-check", "--app", str(self.app),
                                   "--sandbox", str(self.sandbox)])
        self.assertEqual(code, 1, output.getvalue())
        self.assertEqual(outside.read_bytes(), b"keep this file")

    def test_cli_uninstall_check_refuses_user_edits_during_pending_recovery(self):
        registration = self.pref / "packages/synapse.json"
        real_apply = safety.apply_value

        def crash_after_registration(path, value):
            real_apply(path, value)
            if Path(path) == registration:
                raise SimulatedProcessDeath()

        with patch.object(safety, "apply_value", side_effect=crash_after_registration):
            with self.assertRaises(SimulatedProcessDeath):
                self.install()
        edited = b'{"artist": "edited the package after setup stopped"}'
        registration.write_bytes(edited)
        with redirect_stdout(io.StringIO()) as output:
            code = setup_cli.main(["uninstall-check", "--app", str(self.app),
                                   "--sandbox", str(self.sandbox)])
        self.assertEqual(code, 1, output.getvalue())
        self.assertEqual(registration.read_bytes(), edited)
        self.assertTrue((self.app / engine.JOURNAL).exists())

    def test_changed_maintenance_file_blocks_every_mutating_front_door(self):
        self.install()
        helper = self.app / "maintenance/getting-started.html"
        helper.parent.mkdir()
        helper.write_bytes(b"original helper")
        manifest = helper.parent / "maintenance-manifest.json"
        safety.atomic_write(manifest, safety.json_bytes({"schema": "synapse-maintenance-1",
                           "files": {helper.name: safety.file_hash(helper)}}))
        helper.write_bytes(b"artist modified helper")
        registration = self.pref / "packages/synapse.json"
        original_registration = registration.read_bytes()
        for action in ("preflight", "install", "uninstall-check", "uninstall"):
            arguments = [action, "--app", str(self.app), "--sandbox", str(self.sandbox)]
            if action in {"preflight", "install"}:
                arguments.extend(["--pref", str(self.pref), "--home", str(self.home),
                                  "--hfs", str(self.hfs), "--payload", str(self.payload)])
            with self.subTest(action=action), redirect_stdout(io.StringIO()) as output:
                code = setup_cli.main(arguments)
                self.assertEqual(code, 1, output.getvalue())
                self.assertEqual(helper.read_bytes(), b"artist modified helper")
                self.assertEqual(registration.read_bytes(), original_registration)

    def test_recovery_validates_all_embedded_receipts_before_touching_files(self):
        registration = self.pref / "packages/synapse.json"
        real_apply = safety.apply_value

        def crash_after_registration(path, value):
            real_apply(path, value)
            if Path(path) == registration:
                raise SimulatedProcessDeath()

        with patch.object(safety, "apply_value", side_effect=crash_after_registration):
            with self.assertRaises(SimulatedProcessDeath):
                self.install()
        present = registration.read_bytes()
        journal_path = self.app / engine.JOURNAL
        journal = safety.read_json(journal_path)
        state_op = next(op for op in journal["changes"] if Path(op["path"]) == self.app / engine.STATE)
        embedded = json.loads(safety.decode(state_op["after"]))
        embedded["stamp"]["path"] = str(self.work / "outside-sandbox/stamp.json")
        state_op["after"] = safety.encode(safety.json_bytes(embedded))
        safety.atomic_write(journal_path, safety.json_bytes(journal))
        with self.assertRaises(safety.SetupError):
            engine.uninstall(self.app, sandbox=self.sandbox)
        self.assertEqual(registration.read_bytes(), present)
        self.assertTrue(journal_path.exists())


if __name__ == "__main__":
    unittest.main()
