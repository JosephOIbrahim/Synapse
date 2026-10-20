"""Exercise real Git archive filtering; no checkout/history or live data used."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which("git"), "UNAVAILABLE: Git is required to test source archive policy")
class SourceArchivePolicyTests(unittest.TestCase):
    def test_real_archive_omits_local_history_and_keeps_portable_source(self):
        portable = {
            "LICENSE": b"SYNTHETIC notice must survive unchanged\n",
            "README.md": b"SYNTHETIC portable readme\n",
            ".github/workflows/ci.yml": b"name: synthetic-ci\n",
            "installer/build_payload.py": b"# SYNTHETIC portable release tooling\n",
            "python/synapse/example.py": b"# SYNTHETIC portable runtime source\n",
            "tests/test_portable.py": b"# SYNTHETIC portable test\n",
        }
        private = {
            ".claude/never-publish-new-local-config.json": b"SYNTHETIC PRIVATE CONFIGURATION\n",
            "harness/notes/never-publish-new-history.json": b"SYNTHETIC HISTORICAL RECORD\n",
            ".mcp.json": b"SYNTHETIC LOCAL CLIENT CONFIGURATION\n",
            "tests/test_rope_graph_routed_replay.json": b"SYNTHETIC FROZEN HISTORICAL QUOTE\n",
            "tests/test_rope_graph_routed_replay.py": b"# SYNTHETIC MATCHING HISTORICAL REPLAY\n",
        }
        with tempfile.TemporaryDirectory(prefix="source-archive-policy-") as directory:
            case = Path(directory)
            repo = case / "repo"
            repo.mkdir()
            policy = (ROOT / ".gitattributes").read_bytes()
            (repo / ".gitattributes").write_bytes(policy)
            for name, data in {**portable, **private}.items():
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
            def git(*args):
                return subprocess.check_output(["git", "-C", str(repo), *args],
                    env=env, stderr=subprocess.PIPE, timeout=30)
            git("init", "--quiet")
            git("add", "--all")
            tree = git("write-tree").decode().strip()
            output = case / "source.zip"
            git("archive", "--format=zip", "--output=" + str(output), tree)
            with zipfile.ZipFile(output) as archive:
                files = {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}
            self.assertEqual(files, {".gitattributes": policy, **portable},
                "Private fixture history/configuration leaked or portable source/notice/tooling was omitted")


if __name__ == "__main__":
    unittest.main(verbosity=2)
