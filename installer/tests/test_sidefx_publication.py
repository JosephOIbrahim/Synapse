"""Publication exclusions with a real builder and synthetic dependency bytes.

No Houdini, native extension, installer executable or real Git command is run.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_payload

ROOT = Path(build_payload.__file__).resolve().parents[1]
DOC = "rag/documentation/"
RAW_NAMES = (
    "00_overview", "01_surface_tension", "02_auto_sleep", "03_continuous_emission",
    "04_friction_stickiness", "05_deforming_colliders", "06_mpmsurface",
    "07_mpmdebrissource", "08_mpmpostfracture", "09_mpmdeformpieces",
    "10_destruction_workflow", "11_paintball_impact", "12_pumpkin_smash",
    "13_car_rain", "14_wolf_snow", "15_creature_breach", "16_train_wreck",
    "17_building_attack",
)
GUIDE_NAMES = (
    "auto_sleep", "building_attack", "car_rain", "continuous_emission", "creature_breach",
    "deforming_colliders", "destruction_workflow", "friction_stickiness", "mpmdebrissource",
    "mpmdeformpieces", "mpmpostfracture", "mpmsurface", "overview", "paintball_impact",
    "pumpkin_smash", "surface_tension", "train_wreck", "wolf_snow",
)
EXCLUDED = (
    DOC + "_raw_documentation/sidefx_foundations_solaris_market.pdf",
    *(DOC + "_raw_documentation/mpm_masterclass/" + n + ".md" for n in RAW_NAMES),
    *(DOC + "tutorials/workflow_guides/mpm_" + n + ".md" for n in GUIDE_NAMES),
)
ASSETS = DOC + "_metadata/asset_manifest.json"
SEMANTIC = DOC + "_metadata/semantic_index.json"
AGENTS = DOC + "_metadata/agent_relevance_map.json"


class SidefxPublicationTests(unittest.TestCase):
    def test_each_owner_excluded_file_is_denied(self):
        for name in EXCLUDED:
            with self.subTest(name=name):
                self.assertFalse(build_payload.permitted(name))

    def test_personal_asset_manifest_is_not_in_payload(self):
        self.assertFalse(build_payload.permitted(ASSETS))

    def test_catalog_diagnostics_are_not_runtime_content(self):
        for name in ("dump_receipt.txt", "_docs_report.json"):
            self.assertFalse(build_payload.permitted("rag/catalog/h22.0.400/" + name))
        self.assertTrue(build_payload.permitted("rag/catalog/h22.0.400/Lop.json"))

    def test_remaining_runtime_inputs_stay_allowed(self):
        for name in (SEMANTIC, AGENTS, "rag/skills/houdini21-reference/mpm_solver.md",
                     "rag/skills/houdini21-reference/mpm_production_workflows.md",
                     DOC + "tutorials/workflow_guides/unrelated.md", "python/synapse/memory/store.py"):
            with self.subTest(name=name):
                self.assertTrue(build_payload.permitted(name))

    def test_index_has_no_pointer_to_removed_material(self):
        entries = json.loads((ROOT / SEMANTIC).read_text(encoding="utf-8"))
        removed_refs = {n.removeprefix(DOC) for n in EXCLUDED} | {ASSETS.removeprefix(DOC)}
        for topic, entry in entries.items():
            with self.subTest(topic=topic):
                self.assertNotIn(entry.get("reference_file"), removed_refs)

    def test_agent_routes_still_have_topics(self):
        entries = json.loads((ROOT / SEMANTIC).read_text(encoding="utf-8"))
        agents = json.loads((ROOT / AGENTS).read_text(encoding="utf-8"))
        self.assertLessEqual(set(agents), set(entries))

    def test_other_mpm_references_survive(self):
        entries = json.loads((ROOT / SEMANTIC).read_text(encoding="utf-8"))
        for stem in ("mpm_solver", "mpm_production_workflows"):
            self.assertEqual(entries[stem]["reference_file"], stem)

    def test_personal_asset_root_removed_from_source_metadata(self):
        assets = json.loads((ROOT / ASSETS).read_text(encoding="utf-8"))
        self.assertNotIn("project_root", assets["asset_manifest"])

    def test_payload_zip_excludes_content_and_preserves_indexes(self):
        # CPython files and ABI binaries here are inert text fixtures. Real
        # checksums/member validation still run; this is no runtime qualification.
        files = {
            "VERSION": b"0.0.1\n",
            "pyproject.toml": b'[project]\nname = "synthetic"\nversion = "0.0.1"\n',
            "python/synapse/__init__.py": b'__version__ = "0.0.1"\n',
            "shared/__init__.py": b"# fixture\n",
            "houdini/python_panels/synapse_panel.pypanel": b"<pythonPanelDocument/>",
            "houdini/toolbar/synapse.shelf": b"<shelfDocument/>",
            "houdini/scripts/python/synapse_shelf.py": b"# fixture\n",
            "houdini/scripts/python/tokens.py": b"# fixture\n",
            "houdini/scripts/python/synapse_styles.py": b"# fixture\n",
            "houdini/config/Icons/SYNAPSE_synapse.svg": b"<svg/>",
            "python/synapse/_vendor/pydantic_core/_pydantic_core.cp313-win_amd64.pyd": b"INERT fixture",
            "python/synapse/_vendor/jiter/jiter.cp313-win_amd64.pyd": b"INERT fixture",
            SEMANTIC: (ROOT / SEMANTIC).read_bytes(),
            AGENTS: (ROOT / AGENTS).read_bytes(),
            ASSETS: b'{"fixture": "not for publication"}\n',
            "rag/catalog/h22.0.400/Lop.json": b"{}\n",
            "rag/catalog/h22.0.400/dump_receipt.txt": b"Private build diagnostic marker\n",
            "rag/catalog/h22.0.400/_docs_report.json": b"{}\n",
            **{name: b"Excluded-content marker; no actual copyrighted text.\n" for name in EXCLUDED},
        }
        for name in ("anthropic", "httpx", "httpcore", "anyio", "pydantic", "idna", "sniffio"):
            files[f"python/synapse/_vendor/{name}/__init__.py"] = b"# fixture\n"
        with tempfile.TemporaryDirectory(prefix="synapse-sidefx-publication-") as directory:
            work = Path(directory)
            source = work / "source"
            for name, data in files.items():
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            icon = source / "design/icons/svg/synapse_32.svg"
            icon.parent.mkdir(parents=True)
            icon.write_bytes(b"<svg/>")
            listing = ("\0".join(sorted(files)) + "\0").encode()
            archive = work / "fixture-payload.zip"
            with patch.object(build_payload, "WHEELS", {}), patch.object(build_payload, "ui_assets", return_value=[]), \
                 patch.object(build_payload.subprocess, "run", return_value=SimpleNamespace(stdout=listing)) as listed, \
                 patch.object(build_payload.subprocess, "check_output", return_value="0" * 40 + "\n") as head:
                result = build_payload.build(archive, work / "no-wheels", source=source)
            self.assertEqual(listed.call_count, 1)
            self.assertEqual(head.call_count, 1)
            self.assertEqual(result["version"], "0.0.1")
            with zipfile.ZipFile(archive) as z:
                names = set(z.namelist())
                manifest = json.loads(z.read("payload-manifest.json"))
                self.assertFalse(names & (set(EXCLUDED) | {ASSETS, "rag/catalog/h22.0.400/dump_receipt.txt", "rag/catalog/h22.0.400/_docs_report.json"}))
                self.assertIn("rag/catalog/h22.0.400/Lop.json", names)
                self.assertTrue({SEMANTIC, AGENTS} <= names)
                self.assertEqual(z.read(SEMANTIC), files[SEMANTIC])
                self.assertEqual(z.read(AGENTS), files[AGENTS])
                self.assertEqual(names, set(manifest["files"]) | {"payload-manifest.json"})


if __name__ == "__main__":
    unittest.main()
