"""C3 (CTO Remediation Mile 1) — key escrow + fingerprint guard.

Two protections: (1) generating a key writes encryption.key.bak + a loud one-time
'back this up' log, so one lost 44-byte file isn't a total memory loss; (2) a
plaintext key.fingerprint sidecar lets _load detect a CHANGED key even when the
store is empty / all-plaintext (the case C1's failed-decrypt counter misses) and
refuse the rewrite (prevents a mixed-key file).
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


@pytest.fixture()
def crypto():
    cr = pytest.importorskip("synapse.core.crypto")
    if not cr.ENCRYPTION_AVAILABLE:
        pytest.skip("cryptography not installed")
    cr.CryptoEngine.reset_instance()
    os.environ.pop("SYNAPSE_ENCRYPTION_KEY", None)
    yield cr
    cr.CryptoEngine.reset_instance()
    os.environ.pop("SYNAPSE_ENCRYPTION_KEY", None)


def test_key_generation_writes_bak(tmp_path, monkeypatch, crypto):
    # Redirect HOME so generation lands in tmp, never the real ~/.synapse.
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SYNAPSE_ENCRYPTION_KEY", raising=False)
    crypto.CryptoEngine.reset_instance()

    eng = crypto.CryptoEngine.get_instance()                 # triggers _resolve_key → generate
    key_file = tmp_path / ".synapse" / "encryption.key"
    bak_file = tmp_path / ".synapse" / "encryption.key.bak"
    assert key_file.exists() and bak_file.exists()
    assert key_file.read_bytes() == bak_file.read_bytes()    # escrow copy is the real key
    assert len(eng.fingerprint()) == 8


def test_changed_key_on_empty_store_is_degraded(tmp_path, crypto):
    from cryptography.fernet import Fernet
    key_a, key_b = Fernet.generate_key().decode(), Fernet.generate_key().decode()

    # Save an EMPTY store under key A → 0 encrypted lines, but a key.fingerprint=fpA.
    os.environ["SYNAPSE_ENCRYPTION_KEY"] = key_a
    crypto.CryptoEngine.reset_instance()
    mod_a = _load_store()
    store_a = mod_a.MemoryStore(storage_dir=str(tmp_path), background_load=False)
    store_a.save()
    assert (tmp_path / "key.fingerprint").exists()

    # Reload under key B. No line fails (store is empty) — only the fingerprint catches it.
    os.environ["SYNAPSE_ENCRYPTION_KEY"] = key_b
    crypto.CryptoEngine.reset_instance()
    mod_b = _load_store()
    store_b = mod_b.MemoryStore(storage_dir=str(tmp_path), background_load=False)
    assert store_b._degraded_load is True
    with pytest.raises(RuntimeError):
        store_b.save()


def test_same_key_not_degraded(tmp_path, crypto):
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    os.environ["SYNAPSE_ENCRYPTION_KEY"] = key
    crypto.CryptoEngine.reset_instance()
    mod = _load_store()
    s = mod.MemoryStore(storage_dir=str(tmp_path), background_load=False)
    s.save()

    crypto.CryptoEngine.reset_instance()      # same key still in env
    mod2 = _load_store()
    s2 = mod2.MemoryStore(storage_dir=str(tmp_path), background_load=False)
    assert s2._degraded_load is False
    s2.save()                                  # no raise
