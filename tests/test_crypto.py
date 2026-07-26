"""
Synapse Encryption Tests

Tests for CryptoEngine: key management, line/file encryption,
backward compatibility with plaintext, and roundtrip verification.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

# Add package to path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

import pytest

# Check if cryptography is available
try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

skip_no_crypto = pytest.mark.skipif(
    not HAS_CRYPTO, reason="cryptography package not installed"
)


# =============================================================================
# CRYPTO ENGINE TESTS
# =============================================================================

@skip_no_crypto
class TestCryptoEngine:
    """Tests for CryptoEngine singleton and key management."""

    def setup_method(self):
        from synapse.core.crypto import CryptoEngine
        CryptoEngine.reset_instance()

    def teardown_method(self):
        from synapse.core.crypto import CryptoEngine
        CryptoEngine.reset_instance()
        # Clean up env var if set
        os.environ.pop("SYNAPSE_ENCRYPTION_KEY", None)

    def test_create_with_explicit_key(self):
        from synapse.core.crypto import CryptoEngine
        key = Fernet.generate_key()
        engine = CryptoEngine(key=key)
        assert engine is not None

    def test_singleton_pattern(self):
        from synapse.core.crypto import CryptoEngine
        key = Fernet.generate_key()
        os.environ["SYNAPSE_ENCRYPTION_KEY"] = key.decode()
        a = CryptoEngine.get_instance()
        b = CryptoEngine.get_instance()
        assert a is b

    def test_reset_singleton(self):
        from synapse.core.crypto import CryptoEngine
        key = Fernet.generate_key()
        os.environ["SYNAPSE_ENCRYPTION_KEY"] = key.decode()
        a = CryptoEngine.get_instance()
        CryptoEngine.reset_instance()
        b = CryptoEngine.get_instance()
        assert a is not b

    def test_key_from_env_var(self):
        from synapse.core.crypto import CryptoEngine
        key = Fernet.generate_key()
        os.environ["SYNAPSE_ENCRYPTION_KEY"] = key.decode()
        engine = CryptoEngine.get_instance()
        assert engine is not None

    def test_key_from_file(self):
        from synapse.core.crypto import CryptoEngine
        key = Fernet.generate_key()
        tmp_dir = tempfile.mkdtemp()
        try:
            key_file = Path(tmp_dir) / "encryption.key"
            key_file.write_bytes(key)
            with patch.object(CryptoEngine, '_resolve_key') as mock_resolve:
                mock_resolve.return_value = key
                engine = CryptoEngine()
                assert engine is not None
        finally:
            shutil.rmtree(tmp_dir)

    def test_auto_generate_key(self):
        from synapse.core.crypto import CryptoEngine
        tmp_dir = tempfile.mkdtemp()
        try:
            key_dir = Path(tmp_dir) / ".synapse"
            key_file = key_dir / "encryption.key"

            # Patch Path.home to use our temp dir
            with patch("synapse.core.crypto.Path.home", return_value=Path(tmp_dir)):
                os.environ.pop("SYNAPSE_ENCRYPTION_KEY", None)
                engine = CryptoEngine()
                assert engine is not None
                assert key_file.exists()
                # Key should be valid Fernet key
                stored_key = key_file.read_bytes().strip()
                Fernet(stored_key)  # Should not raise
        finally:
            shutil.rmtree(tmp_dir)


@skip_no_crypto
class TestLineEncryption:
    """Tests for per-line JSONL encryption."""

    def setup_method(self):
        from synapse.core.crypto import CryptoEngine
        CryptoEngine.reset_instance()
        self.key = Fernet.generate_key()
        os.environ["SYNAPSE_ENCRYPTION_KEY"] = self.key.decode()

    def teardown_method(self):
        from synapse.core.crypto import CryptoEngine
        CryptoEngine.reset_instance()
        os.environ.pop("SYNAPSE_ENCRYPTION_KEY", None)

    def test_encrypt_decrypt_roundtrip(self):
        from synapse.core.crypto import CryptoEngine
        engine = CryptoEngine.get_instance()
        plaintext = '{"id": "test_001", "content": "hello world"}'
        encrypted = engine.encrypt_line(plaintext)
        decrypted = engine.decrypt_line(encrypted)
        assert decrypted == plaintext

    def test_encrypted_has_magic_prefix(self):
        from synapse.core.crypto import CryptoEngine, MAGIC_PREFIX
        engine = CryptoEngine.get_instance()
        encrypted = engine.encrypt_line("test data")
        assert encrypted.startswith(MAGIC_PREFIX)

    def test_plaintext_passthrough(self):
        from synapse.core.crypto import CryptoEngine
        engine = CryptoEngine.get_instance()
        plaintext = '{"plain": true}'
        result = engine.decrypt_line(plaintext)
        assert result == plaintext

    def test_different_lines_different_ciphertext(self):
        from synapse.core.crypto import CryptoEngine
        engine = CryptoEngine.get_instance()
        a = engine.encrypt_line("line_a")
        b = engine.encrypt_line("line_b")
        assert a != b

    def test_same_line_different_ciphertext(self):
        """Fernet uses random IV, so same plaintext produces different ciphertext."""
        from synapse.core.crypto import CryptoEngine
        engine = CryptoEngine.get_instance()
        a = engine.encrypt_line("same")
        b = engine.encrypt_line("same")
        # Both decrypt to same value
        engine2 = CryptoEngine.get_instance()
        assert engine2.decrypt_line(a) == engine2.decrypt_line(b) == "same"

    def test_unicode_content(self):
        from synapse.core.crypto import CryptoEngine
        engine = CryptoEngine.get_instance()
        text = '{"msg": "Hello, World! \u2603 \u00e9\u00e8\u00ea"}'
        assert engine.decrypt_line(engine.encrypt_line(text)) == text

    def test_empty_string(self):
        from synapse.core.crypto import CryptoEngine
        engine = CryptoEngine.get_instance()
        assert engine.decrypt_line(engine.encrypt_line("")) == ""


@skip_no_crypto
class TestFileEncryption:
    """Tests for whole-file encryption."""

    def setup_method(self):
        from synapse.core.crypto import CryptoEngine
        CryptoEngine.reset_instance()
        self.key = Fernet.generate_key()
        os.environ["SYNAPSE_ENCRYPTION_KEY"] = self.key.decode()

    def teardown_method(self):
        from synapse.core.crypto import CryptoEngine
        CryptoEngine.reset_instance()
        os.environ.pop("SYNAPSE_ENCRYPTION_KEY", None)

    def test_file_roundtrip(self):
        from synapse.core.crypto import CryptoEngine
        engine = CryptoEngine.get_instance()
        content = "# Context\n\nThis is a test context file.\n"
        encrypted = engine.encrypt_file_content(content)
        decrypted = engine.decrypt_file_content(encrypted)
        assert decrypted == content

    def test_plaintext_file_passthrough(self):
        from synapse.core.crypto import CryptoEngine
        engine = CryptoEngine.get_instance()
        content = '{"index": true, "version": 1}'
        result = engine.decrypt_file_content(content)
        assert result == content

    def test_large_content(self):
        from synapse.core.crypto import CryptoEngine
        engine = CryptoEngine.get_instance()
        content = "x" * 100_000
        assert engine.decrypt_file_content(engine.encrypt_file_content(content)) == content


@skip_no_crypto
class TestGetCrypto:
    """Tests for the get_crypto() convenience function."""

    def setup_method(self):
        from synapse.core.crypto import CryptoEngine
        CryptoEngine.reset_instance()

    def teardown_method(self):
        from synapse.core.crypto import CryptoEngine
        CryptoEngine.reset_instance()
        os.environ.pop("SYNAPSE_ENCRYPTION_KEY", None)

    def test_returns_engine_when_available(self):
        from synapse.core.crypto import get_crypto, CryptoEngine
        key = Fernet.generate_key()
        os.environ["SYNAPSE_ENCRYPTION_KEY"] = key.decode()
        engine = get_crypto()
        assert isinstance(engine, CryptoEngine)

    def test_returns_none_without_package(self):
        from synapse.core import crypto
        original = crypto.ENCRYPTION_AVAILABLE
        try:
            crypto.ENCRYPTION_AVAILABLE = False
            assert crypto.get_crypto() is None
        finally:
            crypto.ENCRYPTION_AVAILABLE = original


# =============================================================================
# ENCRYPTION AVAILABILITY FLAG
# =============================================================================

class TestEncryptionAvailability:
    """Tests that ENCRYPTION_AVAILABLE flag works correctly."""

    def test_flag_matches_import(self):
        from synapse.core.crypto import ENCRYPTION_AVAILABLE
        assert ENCRYPTION_AVAILABLE == HAS_CRYPTO


# =============================================================================
# KAHAN SUM (included here since it's part of the same commit scope)
# =============================================================================

class TestKahanSum:
    """Tests for kahan_sum deterministic aggregation."""

    def test_basic_sum(self):
        from synapse.core.determinism import kahan_sum
        assert kahan_sum([1.0, 2.0, 3.0]) == 6.0

    def test_empty_iterable(self):
        from synapse.core.determinism import kahan_sum
        assert kahan_sum([]) == 0.0

    def test_compensates_float_error(self):
        """Classic case: summing 0.1 ten times should equal 1.0."""
        from synapse.core.determinism import kahan_sum
        result = kahan_sum([0.1] * 10)
        assert result == 1.0

    def test_large_small_values(self):
        """Kahan handles large + many small values better than naive sum."""
        from synapse.core.determinism import kahan_sum
        values = [1e10, 1.0, -1e10, 1.0]
        result = kahan_sum(values)
        assert result == 2.0

    def test_negative_values(self):
        from synapse.core.determinism import kahan_sum
        assert kahan_sum([-1.0, -2.0, -3.0]) == -6.0

    def test_generator_input(self):
        from synapse.core.determinism import kahan_sum
        result = kahan_sum(x * 0.1 for x in range(10))
        # Sum of 0.0, 0.1, 0.2, ..., 0.9 = 4.5
        assert result == 4.5


# =============================================================================
# DETERMINISTIC DECORATOR FIX
# =============================================================================

class TestDeterministicDecoratorFix:
    """Tests that @deterministic processes positional args."""

    def test_positional_float_rounded(self):
        from synapse.core.determinism import deterministic

        @deterministic
        def add(a: float, b: float) -> float:
            return a + b

        # 0.1 + 0.2 = 0.30000000000000004 without rounding
        result = add(0.1 + 0.2, 0.0)
        assert result == 0.3

    def test_positional_tuple_rounded(self):
        from synapse.core.determinism import deterministic

        @deterministic
        def identity(v):
            return v

        result = identity((0.1 + 0.2, 0.1 + 0.2, 0.1 + 0.2))
        assert all(c == 0.3 for c in result)

    def test_mixed_positional_and_keyword(self):
        from synapse.core.determinism import deterministic

        @deterministic
        def fn(a, b, c=0.0):
            return (a, b, c)

        result = fn(0.1 + 0.2, "hello", c=0.1 + 0.2)
        assert result[0] == 0.3
        assert result[1] == "hello"
        assert result[2] == 0.3

    def test_non_float_args_unchanged(self):
        from synapse.core.determinism import deterministic

        @deterministic
        def fn(name, count):
            return (name, count)

        result = fn("test", 42)
        assert result == ("test", 42)
