"""Source-bound redistribution notices; synthetic Moneta trees, no installs."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_payload as builder
from synapse_setup import engine


class MonetaLicenseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synapse-moneta-license-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "moneta"
        self.originals = {"src/moneta/__init__.py": b"# synthetic source\n",
                          "schema/plugInfo.json": b"{}\n", "schema/generatedSchema.usda": b"#usda 1.0\n",
                          "schema/MonetaSchema.usda": b"#usda 1.0\n"}
        self.policy = builder.license_policy()
        self.archive = self.root / "moneta.zip"
        self.set_source_license("Proprietary")
        # Only the synthetic fixture grant differs; the downstream validator is real.
        runtime_policy = patch.object(engine, "moneta_policy", side_effect=lambda: copy.deepcopy(self.policy))
        runtime_policy.start()
        self.addCleanup(runtime_policy.stop)

    def set_source_license(self, license_name):
        self.originals["pyproject.toml"] = (f'[project]\nname = "moneta"\nversion = "1.3.0"\nlicense = {{text = "{license_name}"}}\n').encode()
        for name, data in self.originals.items():
            p = self.source / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        # Independent fixture producer hashes exactly the author-supplied bytes.
        hashes = {n: builder.digest(v) for n, v in self.originals.items()}
        self.policy["source_identity_sha256"] = builder.digest(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode())

    def export(self, revision=None):
        def fixture_git(command, **kwargs):
            if command[-2:] == ["rev-parse", "HEAD"]:
                return (revision or self.policy["source_commit"]) + "\n"
            if command[-2] == "show":
                return self.originals[command[-1].split(":", 1)[1]]
            raise AssertionError("Unexpected Git fixture command")
        with patch.object(builder, "license_policy", return_value=copy.deepcopy(self.policy)), \
             patch.object(builder.subprocess, "check_output", side_effect=fixture_git):
            return builder.export_moneta(self.source, self.archive)

    def members(self):
        with zipfile.ZipFile(self.archive) as z:
            return {n: z.read(n) for n in z.namelist()}

    def validate_members(self, files):
        changed = self.root / "changed.zip"
        builder.zip_bytes(changed, files)
        with patch.object(builder, "license_policy", return_value=copy.deepcopy(self.policy)), zipfile.ZipFile(changed) as z:
            return builder.validate_moneta_grant(z, json.loads(z.read("moneta-bundle.json")))

    def payload_for_members(self, members, label):
        """Exercise the real consumer and downstream manifest validator.

        SDK/ABI files are inert text: no module, native code or installer runs.
        Only Git listing/revision and external wheel/UI inputs are replaced.
        """
        source = self.root / (label + "-source")
        runtime = {
            "VERSION": b"0.0.1\n",
            "pyproject.toml": b'[project]\nname = "synthetic"\nversion = "0.0.1"\n',
            "python/synapse/__init__.py": b'__version__ = "0.0.1"\n',
            "shared/__init__.py": b"# SYNTHETIC\n",
            "houdini/python_panels/synapse_panel.pypanel": b"<pythonPanelDocument/>",
            "houdini/toolbar/synapse.shelf": b"<shelfDocument/>",
            **{f"houdini/scripts/python/{n}.py": b"# SYNTHETIC\n" for n in ("synapse_shelf", "tokens", "synapse_styles")},
            "houdini/config/Icons/SYNAPSE_synapse.svg": b"<svg/>",
            "python/synapse/_vendor/pydantic_core/_pydantic_core.cp313-win_amd64.pyd": b"INERT SYNTHETIC ABI FIXTURE",
            "python/synapse/_vendor/jiter/jiter.cp313-win_amd64.pyd": b"INERT SYNTHETIC ABI FIXTURE",
            **{f"python/synapse/_vendor/{n}/__init__.py": b"# SYNTHETIC\n" for n in ("anthropic", "httpx", "httpcore", "anyio", "pydantic", "idna", "sniffio")},
        }
        for name, data in runtime.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        icon = source / "design/icons/svg/synapse_32.svg"
        icon.parent.mkdir(parents=True)
        icon.write_bytes(b"<svg/>")
        dependency = self.root / (label + "-moneta.zip")
        output = self.root / (label + "-payload.zip")
        builder.zip_bytes(dependency, members)
        listing = ("\0".join(sorted(runtime)) + "\0").encode()
        with patch.object(builder, "license_policy", return_value=copy.deepcopy(self.policy)), \
             patch.object(builder, "WHEELS", {}), patch.object(builder, "ui_assets", return_value=[]), \
             patch.object(builder.subprocess, "run", return_value=SimpleNamespace(stdout=listing)), \
             patch.object(builder.subprocess, "check_output", return_value="0" * 40 + "\n"):
            builder.build(output, self.root / "no-wheels", dependency,
                          builder.digest(dependency.read_bytes()), source=source)
        return output

    def test_notice_keeps_full_independent_mit_text_and_original_sources(self):
        self.export()
        files = self.members()
        expected_mit = (builder.ROOT / "LICENSE").read_text(encoding="utf-8").replace("Copyright (c) 2025-2026", "Copyright (c) 2026")
        self.assertEqual(self.policy["license_text"].strip(), expected_mit.strip())
        self.assertTrue(files["LICENSE-NOTICE.txt"].decode().strip().endswith(expected_mit.strip()))
        record = json.loads(files["moneta-bundle.json"])
        self.assertEqual(record["license"], "MIT")
        self.assertEqual(record["source_license"], "Proprietary")
        for name, data in self.originals.items():
            exported = "upstream/pyproject.toml" if name == "pyproject.toml" else name
            self.assertEqual(files[exported], data)
        self.validate_members(files)

    def test_generated_metadata_reads_source_declaration(self):
        for name in ("Proprietary", "MIT"):
            with self.subTest(source_license=name):
                self.set_source_license(name)
                self.export()
                files = self.members()
                self.assertIn(("License: " + name + "\n").encode(), files["src/moneta-1.3.0.dist-info/METADATA"])

    def test_changed_source_is_not_covered_by_original_grant(self):
        (self.source / "src/moneta/__init__.py").write_bytes(b"changed source\n")
        with self.assertRaisesRegex(builder.SetupError, "exact content"):
            self.export()
        self.assertFalse(self.archive.exists())

    def test_wrong_revision_is_not_exported(self):
        with self.assertRaisesRegex(builder.SetupError, "exact content"):
            self.export("0" * 40)
        self.assertFalse(self.archive.exists())

    def test_wrong_grant_digest_is_not_exported(self):
        self.policy["source_identity_sha256"] = "0" * 64
        with self.assertRaisesRegex(builder.SetupError, "exact content"):
            self.export()
        self.assertFalse(self.archive.exists())

    def test_crlf_checkout_exports_exact_committed_bytes(self):
        for name, data in self.originals.items():
            (self.source / name).write_bytes(data.replace(b"\n", b"\r\n"))
        self.export()
        files = self.members()
        for name, data in self.originals.items():
            exported = "upstream/pyproject.toml" if name == "pyproject.toml" else name
            self.assertEqual(files[exported], data)

    def test_upstream_notice_is_copied_without_rewriting(self):
        self.originals["NOTICE"] = b"Upstream synthetic notice\n"
        self.set_source_license("Proprietary")
        self.export()
        self.assertEqual(self.members()["NOTICE"], self.originals["NOTICE"])

    def test_consumer_rejects_source_changed_even_if_ordinary_checksum_is_updated(self):
        self.export()
        files = self.members()
        files["src/moneta/__init__.py"] = b"altered after export\n"
        record = json.loads(files["moneta-bundle.json"])
        record["files"]["src/moneta/__init__.py"] = builder.digest(files["src/moneta/__init__.py"])
        files["moneta-bundle.json"] = json.dumps(record).encode()
        with self.assertRaisesRegex(builder.SetupError, "source identity mismatch"):
            self.validate_members(files)

    def test_consumer_rejects_missing_mit_body(self):
        self.export()
        files = self.members()
        files["LICENSE-NOTICE.txt"] = b"MIT\n"
        with self.assertRaisesRegex(builder.SetupError, "notice differs"):
            self.validate_members(files)

    def test_consumer_rejects_distribution_metadata_that_hides_source_declaration(self):
        self.export()
        files = self.members()
        files["src/moneta-1.3.0.dist-info/METADATA"] = b"License: MIT\n"
        with self.assertRaisesRegex(builder.SetupError, "distribution metadata"):
            self.validate_members(files)

    def test_consumer_rejects_forged_grant_fields(self):
        self.export()
        original = self.members()
        for field, value in (("grant_date", "2000-01-01"), ("distribution", "unreviewed grant"),
                             ("source_identity_sha256", "0" * 64), ("license", "Proprietary")):
            with self.subTest(field=field):
                files = dict(original)
                record = json.loads(files["moneta-bundle.json"])
                record[field] = value
                files["moneta-bundle.json"] = json.dumps(record).encode()
                with self.assertRaisesRegex(builder.SetupError, "source-bound MIT grant"):
                    self.validate_members(files)

    def test_payload_contains_every_authorized_source_and_generated_notice(self):
        self.originals["NOTICE"] = b"SYNTHETIC upstream notice: preserve exactly\n"
        self.set_source_license("Proprietary")
        self.export()
        members = self.members()
        output = self.payload_for_members(members, "canonical")
        with zipfile.ZipFile(output) as payload:
            copied = {name.removeprefix("dependencies/moneta/"): payload.read(name)
                      for name in payload.namelist() if name.startswith("dependencies/moneta/")}
        self.assertEqual(copied, members)

    def test_payload_rejects_extra_python_or_native_content_with_valid_checksums(self):
        self.export()
        original = self.members()
        for i, name in enumerate(("src/moneta/extra.py", "src/moneta_native/moneta_native.pyd")):
            with self.subTest(name=name):
                members = dict(original)
                members[name] = b"INERT UNAPPROVED CONTENT\n"
                record = json.loads(members["moneta-bundle.json"])
                record["files"][name] = builder.digest(members[name])
                members["moneta-bundle.json"] = builder.json_bytes(record)
                with self.assertRaisesRegex(builder.SetupError, "inventory"):
                    self.payload_for_members(members, "extra-%d" % i)

    def test_payload_rejects_validated_source_or_notice_omitted_from_copy_inventory(self):
        self.originals["src/moneta/required_module.py"] = b"# SYNTHETIC authorized source\n"
        self.originals["NOTICE"] = b"SYNTHETIC required upstream notice\n"
        self.set_source_license("Proprietary")
        self.export()
        original = self.members()
        for i, name in enumerate(("src/moneta/required_module.py", "NOTICE", "upstream/pyproject.toml",
                                  "src/moneta-1.3.0.dist-info/METADATA")):
            with self.subTest(name=name):
                members = dict(original)
                record = json.loads(members["moneta-bundle.json"])
                del record["files"][name]
                members["moneta-bundle.json"] = builder.json_bytes(record)
                with self.assertRaisesRegex(builder.SetupError, "inventory"):
                    self.payload_for_members(members, "omitted-%d" % i)

    def test_payload_rejects_unlisted_archive_member(self):
        self.export()
        members = self.members()
        members["unlisted-private-note.txt"] = b"SYNTHETIC UNLISTED CONTENT\n"
        with self.assertRaisesRegex(builder.SetupError, "inventory"):
            self.payload_for_members(members, "unlisted")

    def test_downstream_rejects_direct_payload_tampering_with_updated_checksums(self):
        self.export()
        output = self.payload_for_members(self.members(), "direct-downstream")
        with zipfile.ZipFile(output) as archive:
            original = {name: archive.read(name) for name in archive.namelist()}
        cases = ("source", "notice", "omit", "extra-native", "hide-summary")
        for label in cases:
            with self.subTest(attack=label):
                members = dict(original)
                manifest = json.loads(members[engine.MANIFEST])
                base = "dependencies/moneta/"
                if label == "source":
                    members[base + "src/moneta/__init__.py"] = b"# unauthorized altered source\n"
                elif label == "notice":
                    members[base + "LICENSE-NOTICE.txt"] = b"MIT\n"
                elif label == "omit":
                    del members[base + "upstream/pyproject.toml"]
                elif label == "extra-native":
                    members[base + "src/moneta_native/unapproved.pyd"] = b"INERT UNAPPROVED ABI FIXTURE"
                else:
                    manifest["moneta"] = None
                manifest["files"] = {name: builder.digest(data) for name, data in members.items() if name != engine.MANIFEST}
                members[engine.MANIFEST] = builder.json_bytes(manifest)
                attack = self.root / ("downstream-" + label + ".zip")
                builder.zip_bytes(attack, members)
                with self.assertRaisesRegex(builder.SetupError, "Moneta"):
                    engine.load_manifest(attack)

    def test_downstream_rejects_windows_case_aliases_in_dependency_namespace(self):
        self.export()
        output = self.payload_for_members(self.members(), "case-downstream")
        with zipfile.ZipFile(output) as archive:
            original = {name: archive.read(name) for name in archive.namelist()}
        for label, path, hide in (
            ("mixed-directory", "dependencies/Moneta/src/moneta/extra.py", False),
            ("mixed-root-native", "Dependencies/moneta/src/moneta_native/extra.pyd", False),
            ("hidden-case-only", "DEPENDENCIES/MONETA/src/moneta/extra.py", True),
        ):
            with self.subTest(attack=label):
                members = dict(original)
                manifest = json.loads(members[engine.MANIFEST])
                if hide:
                    members = {name: data for name, data in members.items() if not name.startswith("dependencies/moneta/")}
                    manifest["moneta"] = None
                members[path] = b"INERT UNAPPROVED WINDOWS CASE-ALIAS FIXTURE\n"
                manifest["files"] = {name: builder.digest(data) for name, data in members.items() if name != engine.MANIFEST}
                members[engine.MANIFEST] = builder.json_bytes(manifest)
                attack = self.root / ("downstream-" + label + ".zip")
                builder.zip_bytes(attack, members)
                with self.assertRaisesRegex(builder.SetupError, "Moneta"):
                    engine.load_manifest(attack)


if __name__ == "__main__":
    unittest.main()
