"""M3-D (studio-operable, report §4.5 + §5 item 10a/10b): egress + key docs.

DOC-1-style conformance: docs/studio/EGRESS.md answers the
what-leaves-the-building question, and these pins keep it true — a new
remote-egress call site in first-party code fails CI until the doc is
updated; the key-provisioning facts and the fingerprint artifacts both
docs and the doctor depend on are pinned against drift.

Headless, zero-hou, zero-Qt — deliberately imports NO handler or panel
module (text reads + importlib-spec loads only).
"""

import importlib.util
import re
import sys
import types
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_PKG = _ROOT / "python" / "synapse"


def _read(rel):
    return (_ROOT / rel).read_text(encoding="utf-8")


def test_egress_doc_exists_and_names_the_endpoint():
    doc = _read("docs/studio/EGRESS.md")
    provider_src = _read("python/synapse/panel/providers/anthropic_provider.py")
    m = re.search(r'_API_HOST\s*=\s*"([^"]+)"', provider_src)
    assert m, "anthropic_provider.py no longer defines _API_HOST — update this pin"
    host = m.group(1)
    assert host == "api.anthropic.com"
    assert host in doc


def test_remote_egress_sites_are_frozen():
    """A new remote-egress site fails here until EGRESS.md is updated."""
    https_sites = set()
    anthropic_sites = set()
    for py in _PKG.rglob("*.py"):
        rel = py.relative_to(_PKG).as_posix()
        if rel.startswith("_vendor/"):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        if "HTTPSConnection(" in text:
            https_sites.add(rel)
        if re.search(r"\bAnthropic\(", text):
            anthropic_sites.add(rel)
    assert https_sites == {
        "panel/providers/anthropic_provider.py",
        "panel/providers/gemini_provider.py",
    }, (
        f"New raw-HTTPS egress site(s): {https_sites - {'panel/providers/anthropic_provider.py', 'panel/providers/gemini_provider.py'}} "
        "— document in docs/studio/EGRESS.md, then extend this pin."
    )
    allowed = {"host/daemon.py", "routing/router.py"}
    assert anthropic_sites <= allowed, (
        f"New Anthropic() construction site(s): {anthropic_sites - allowed} "
        "— document in docs/studio/EGRESS.md, then extend this pin."
    )


def test_egress_doc_covers_all_three_lanes():
    doc = _read("docs/studio/EGRESS.md")
    for marker in ("claude_worker", "agent_loop", "router"):
        assert marker in doc, f"EGRESS.md missing the {marker} lane"
    assert "plaintext" in doc  # the encryption-doesn't-bound-egress caveat


def test_deployment_doc_has_key_provisioning():
    doc = _read("docs/studio/DEPLOYMENT.md")
    assert "SYNAPSE_ENCRYPTION_KEY" in doc
    assert "single-seat" in doc.lower()
    assert "key.fingerprint" in doc


def test_fingerprint_artifacts_pinned(tmp_path):
    """Pin the exact artifacts the docs + doctor check depend on."""
    crypto = pytest.importorskip("synapse.core.crypto")
    fp = crypto.key_fingerprint(b"x")
    assert re.fullmatch(r"[0-9a-f]{8}", fp)

    # Load store.py standalone (importlib-spec idiom, test_store_key_escrow precedent)
    spec = importlib.util.spec_from_file_location(
        "synapse.memory.store", _PKG / "memory" / "store.py"
    )
    store_mod = sys.modules.get("synapse.memory.store")
    if store_mod is None:
        store_mod = importlib.util.module_from_spec(spec)
        sys.modules["synapse.memory.store"] = store_mod
        spec.loader.exec_module(store_mod)
    store = store_mod.MemoryStore(storage_dir=tmp_path, background_load=False)
    assert store._keyfp_file.name == "key.fingerprint"
