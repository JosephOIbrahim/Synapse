"""C1 (CTO Remediation Mile 1) — degraded-load guard for the memory store.

The data-loss chain the harness targets: a wrong SYNAPSE_ENCRYPTION_KEY (or a
missing `cryptography`) makes _load skip every encrypted line, then the next
save() truncates the file and destroys the still-recoverable ciphertext. The
guard must: detect the unreadable-encrypted lines, set _degraded_load, REFUSE
save(), and leave the original bytes intact (plus a quarantine copy).

Loaded via importlib spec to avoid the package __init__ eager-hou import (the
same isolation the other store/bridge tests use).
"""

import importlib.util
import json
import os
from pathlib import Path

import pytest

_base = Path(__file__).resolve().parents[1] / "python" / "synapse"


def _load_store():
    spec = importlib.util.spec_from_file_location(
        "synapse.memory.store", _base / "memory" / "store.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mem_dict(i):
    return {
        "id": f"mem-{i}", "memory_type": "note", "content": f"secret {i}",
        "summary": f"s{i}", "tags": [f"t{i}"], "keywords": [], "source": "user",
        "tier": "shot", "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z", "hip_file": "", "hip_version": 0,
        "frame": None, "node_paths": [], "links": [], "access_count": 0,
        "is_consolidated": False, "metadata": {},
    }


@pytest.fixture()
def crypto():
    cr = pytest.importorskip("synapse.core.crypto")
    if not cr.ENCRYPTION_AVAILABLE:
        pytest.skip("cryptography not installed — encryption path inert")
    cr.CryptoEngine.reset_instance()
    os.environ.pop("SYNAPSE_ENCRYPTION_KEY", None)
    yield cr
    cr.CryptoEngine.reset_instance()
    os.environ.pop("SYNAPSE_ENCRYPTION_KEY", None)


def _write_under_key(tmp_path, key):
    os.environ["SYNAPSE_ENCRYPTION_KEY"] = key
    from synapse.core.crypto import CryptoEngine
    CryptoEngine.reset_instance()
    mod = _load_store()
    store = mod.MemoryStore(storage_dir=str(tmp_path), background_load=False)
    mem = mod.Memory.from_dict(_mem_dict(0))
    store._memories[mem.id] = mem
    store.save()
    return mod, store


def test_wrong_key_is_degraded_refuses_save_preserves_ciphertext(tmp_path, crypto):
    from cryptography.fernet import Fernet
    key_a = Fernet.generate_key().decode()
    key_b = Fernet.generate_key().decode()

    # --- session 1: write under key A (encrypted on disk) ---
    _write_under_key(tmp_path, key_a)
    mem_file = tmp_path / "memory.jsonl"
    original = mem_file.read_bytes()
    assert b"SYNAPSE_ENC_V1:" in original          # it really is ciphertext

    # --- session 2 (fresh): load under the WRONG key B ---
    os.environ["SYNAPSE_ENCRYPTION_KEY"] = key_b
    crypto.CryptoEngine.reset_instance()
    mod_b = _load_store()
    store_b = mod_b.MemoryStore(storage_dir=str(tmp_path), background_load=False)

    assert store_b._degraded_load is True           # detected
    assert len(store_b._memories) == 0              # nothing decrypted

    with pytest.raises(RuntimeError):               # save is refused
        store_b.save()

    assert mem_file.read_bytes() == original        # CIPHERTEXT PRESERVED — the wipe is dead
    quarantines = [p for p in tmp_path.iterdir() if p.name.startswith("memory.jsonl.degraded-")]
    assert quarantines, "expected a quarantine recovery copy"
    assert quarantines[0].read_bytes() == original  # the copy is the real ciphertext


def test_correct_key_loads_cleanly_and_saves(tmp_path, crypto):
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    _write_under_key(tmp_path, key)

    # reload under the SAME key — not degraded, save() works
    os.environ["SYNAPSE_ENCRYPTION_KEY"] = key
    crypto.CryptoEngine.reset_instance()
    mod = _load_store()
    store = mod.MemoryStore(storage_dir=str(tmp_path), background_load=False)
    assert store._degraded_load is False
    assert len(store._memories) == 1
    store.save()                                    # no raise


def test_plaintext_garble_is_not_treated_as_degraded(tmp_path, crypto):
    # A torn/garbled PLAINTEXT line (no MAGIC_PREFIX) is a separate concern (C32),
    # not an encrypted-key failure — it must NOT trip the degraded guard.
    (tmp_path / "memory.jsonl").write_text("{ this is not valid json\n", encoding="utf-8")
    mod = _load_store()
    store = mod.MemoryStore(storage_dir=str(tmp_path), background_load=False)
    assert store._degraded_load is False
    store.save()                                    # allowed
