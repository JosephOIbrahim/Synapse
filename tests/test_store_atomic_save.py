"""C2 (CTO Remediation Mile 1) — MemoryStore.save() is crash-atomic + backed up.

save() used to truncate memory.jsonl/index.json via open('w'); a crash mid-write
left a truncated (corrupt) file with no recovery point. C2 routes save() through
write_report (tmp + fsync + os.replace, backups=1). These pins prove: a failed
replace leaves the PRIOR file byte-intact (no truncation, no leftover .tmp), and
a normal save keeps one generational .bak.

Loaded via importlib spec to avoid the package __init__ eager-hou import.
"""

import importlib.util
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
        "id": f"mem-{i}", "memory_type": "note", "content": f"c{i}", "summary": f"s{i}",
        "tags": [], "keywords": [], "source": "user", "tier": "shot",
        "created_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z",
        "hip_file": "", "hip_version": 0, "frame": None, "node_paths": [], "links": [],
        "access_count": 0, "is_consolidated": False, "metadata": {},
    }


@pytest.fixture(autouse=True)
def _isolate_key():
    """Use a throwaway key so the test never reads/writes the real ~/.synapse key."""
    try:
        from cryptography.fernet import Fernet
        from synapse.core.crypto import CryptoEngine
        os.environ["SYNAPSE_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
        CryptoEngine.reset_instance()
        yield
        CryptoEngine.reset_instance()
        os.environ.pop("SYNAPSE_ENCRYPTION_KEY", None)
    except Exception:
        yield  # cryptography absent → plaintext store, nothing to isolate


def _store_with(tmp_path, n):
    mod = _load_store()
    store = mod.MemoryStore(storage_dir=str(tmp_path), background_load=False)
    for i in range(n):
        m = mod.Memory.from_dict(_mem_dict(i))
        store._memories[m.id] = m
    store.save()
    return mod, store


def test_failed_replace_leaves_prior_file_intact(tmp_path, monkeypatch):
    mod, store = _store_with(tmp_path, 1)
    mem_file = tmp_path / "memory.jsonl"
    v1 = mem_file.read_bytes()

    # Mutate, then simulate a crash at the atomic replace step.
    m = mod.Memory.from_dict(_mem_dict(99))
    store._memories[m.id] = m
    import importlib
    wr = importlib.import_module("synapse.cognitive.tools.write_report")  # module, not the re-exported fn

    def boom(src, dst):
        raise RuntimeError("simulated crash at os.replace")
    monkeypatch.setattr(wr.os, "replace", boom)

    with pytest.raises(RuntimeError):
        store.save()

    assert mem_file.read_bytes() == v1                      # NOT truncated — prior content intact
    assert not list(tmp_path.glob("*.tmp"))                 # tmp cleaned up, no debris


def test_save_keeps_one_generational_backup(tmp_path):
    mod, store = _store_with(tmp_path, 1)
    mem_file = tmp_path / "memory.jsonl"
    first = mem_file.read_bytes()

    m = mod.Memory.from_dict(_mem_dict(2))
    store._memories[m.id] = m
    store.save()                                            # second save rotates a .bak.1

    bak = tmp_path / "memory.jsonl.bak.1"
    assert bak.exists()
    assert bak.read_bytes() == first                        # the recovery point is the prior content
    assert mem_file.read_bytes() != first                   # live file moved forward
