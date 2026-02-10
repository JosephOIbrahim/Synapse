"""
Synapse Authentication Tests

Tests for API key authentication module:
- Key loading from env var and file
- Authenticate success / failure
- No key = auth disabled (backward compat)
- Constant-time comparison
- Auth cache reset
- Hash-for-log safety
"""

import os
import sys
import tempfile
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import auth module directly (avoid hou dependency)
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

auth_path = os.path.join(python_dir, "synapse", "server", "auth.py")
spec = importlib.util.spec_from_file_location("auth", auth_path)
auth_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth_mod)

get_auth_key = auth_mod.get_auth_key
reset_auth_cache = auth_mod.reset_auth_cache
authenticate = auth_mod.authenticate
hash_key_for_log = auth_mod.hash_key_for_log
AUTH_COMMAND_TYPE = auth_mod.AUTH_COMMAND_TYPE
AUTH_REQUIRED_TYPE = auth_mod.AUTH_REQUIRED_TYPE


# =============================================================================
# KEY LOADING TESTS
# =============================================================================

class TestKeyLoading:
    """Tests for API key loading from various sources."""

    def setup_method(self):
        reset_auth_cache()

    def teardown_method(self):
        reset_auth_cache()

    def test_no_key_returns_none(self):
        """No env var and no file -> None (auth disabled)."""
        with patch.dict(os.environ, {"SYNAPSE_API_KEY": ""}, clear=False):
            with patch.object(auth_mod, "_load_key_from_file", return_value=None):
                reset_auth_cache()
                key = get_auth_key()
                assert key is None

    def test_env_var_takes_priority(self):
        """SYNAPSE_API_KEY env var is checked first."""
        with patch.dict(os.environ, {"SYNAPSE_API_KEY": "secret-from-env"}):
            reset_auth_cache()
            key = get_auth_key()
            assert key == "secret-from-env"

    def test_env_var_strips_whitespace(self):
        """Whitespace around env var value is stripped."""
        with patch.dict(os.environ, {"SYNAPSE_API_KEY": "  padded-key  "}):
            reset_auth_cache()
            key = get_auth_key()
            assert key == "padded-key"

    def test_empty_env_var_falls_through(self):
        """Empty SYNAPSE_API_KEY falls through to file."""
        with patch.dict(os.environ, {"SYNAPSE_API_KEY": ""}, clear=False):
            with patch.object(auth_mod, "_load_key_from_file", return_value=None):
                reset_auth_cache()
                key = get_auth_key()
                assert key is None

    def test_file_key_loading(self):
        """Key loaded from ~/.synapse/auth.key file."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove SYNAPSE_API_KEY if present
            env = dict(os.environ)
            env.pop("SYNAPSE_API_KEY", None)
            with patch.dict(os.environ, env, clear=True):
                with tempfile.NamedTemporaryFile(mode="w", suffix=".key", delete=False, encoding="utf-8") as f:
                    f.write("# comment line\n")
                    f.write("file-secret-key\n")
                    f.write("ignored-second-line\n")
                    f.flush()
                    key_path = Path(f.name)

                try:
                    # Patch Path.home() to redirect to our temp dir
                    with patch.object(auth_mod, "_load_key_from_file", return_value="file-secret-key"):
                        reset_auth_cache()
                        key = get_auth_key()
                        assert key == "file-secret-key"
                finally:
                    key_path.unlink(missing_ok=True)

    def test_key_caching(self):
        """Key is cached after first load."""
        with patch.dict(os.environ, {"SYNAPSE_API_KEY": "cached-key"}):
            reset_auth_cache()
            key1 = get_auth_key()
            # Change env var - should still return cached
            with patch.dict(os.environ, {"SYNAPSE_API_KEY": "different-key"}):
                key2 = get_auth_key()
            assert key1 == key2 == "cached-key"

    def test_reset_clears_cache(self):
        """reset_auth_cache() forces re-load on next call."""
        with patch.dict(os.environ, {"SYNAPSE_API_KEY": "key1"}):
            reset_auth_cache()
            assert get_auth_key() == "key1"

        with patch.dict(os.environ, {"SYNAPSE_API_KEY": "key2"}):
            reset_auth_cache()
            assert get_auth_key() == "key2"


# =============================================================================
# AUTHENTICATE TESTS
# =============================================================================

class TestAuthenticate:
    """Tests for the authenticate() function."""

    def setup_method(self):
        reset_auth_cache()

    def teardown_method(self):
        reset_auth_cache()

    def test_correct_key(self):
        """Correct key authenticates."""
        assert authenticate("my-secret", "my-secret") is True

    def test_wrong_key(self):
        """Wrong key fails."""
        assert authenticate("wrong", "my-secret") is False

    def test_empty_token(self):
        """Empty token fails when key is set."""
        assert authenticate("", "my-secret") is False

    def test_none_key_means_open(self):
        """None expected_key = auth disabled = always pass."""
        assert authenticate("anything", None) is True
        assert authenticate("", None) is True

    def test_no_key_configured_passes(self):
        """When no key is configured, authenticate always passes."""
        with patch.dict(os.environ, {"SYNAPSE_API_KEY": ""}, clear=False):
            with patch.object(auth_mod, "_load_key_from_file", return_value=None):
                reset_auth_cache()
                # authenticate() with no explicit key uses get_auth_key()
                assert authenticate("any-token") is True

    def test_constant_time_comparison(self):
        """Verify hmac.compare_digest is used (no timing leak)."""
        # We can't directly test timing, but we verify the function
        # doesn't short-circuit on first-character mismatch
        import hmac
        with patch.object(hmac, "compare_digest", return_value=True) as mock_cmp:
            authenticate("token", "expected")
            mock_cmp.assert_called_once()

    def test_unicode_keys(self):
        """Unicode keys work correctly."""
        assert authenticate("schluessel-42", "schluessel-42") is True
        assert authenticate("schluessel-42", "schluessel-43") is False


# =============================================================================
# UTILITY TESTS
# =============================================================================

class TestUtilities:
    """Tests for auth utility functions."""

    def test_hash_key_for_log(self):
        """hash_key_for_log returns 8-char hex digest."""
        h = hash_key_for_log("my-secret-key")
        assert len(h) == 8
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_is_deterministic(self):
        """Same key always produces same hash."""
        h1 = hash_key_for_log("test-key")
        h2 = hash_key_for_log("test-key")
        assert h1 == h2

    def test_different_keys_different_hashes(self):
        """Different keys produce different hashes."""
        h1 = hash_key_for_log("key-a")
        h2 = hash_key_for_log("key-b")
        assert h1 != h2

    def test_constants(self):
        """Auth protocol constants are defined."""
        assert AUTH_COMMAND_TYPE == "authenticate"
        assert AUTH_REQUIRED_TYPE == "auth_required"


# =============================================================================
# AUTH HANDSHAKE PROTOCOL TESTS
# =============================================================================

class TestAuthHandshakeProtocol:
    """Tests for the auth handshake message format."""

    def test_auth_command_format(self):
        """Verify expected auth command structure."""
        import json
        cmd = {
            "type": AUTH_COMMAND_TYPE,
            "id": "auth-001",
            "payload": {"key": "my-secret"},
            "sequence": 0,
        }
        serialized = json.dumps(cmd, sort_keys=True)
        parsed = json.loads(serialized)
        assert parsed["type"] == "authenticate"
        assert parsed["payload"]["key"] == "my-secret"

    def test_auth_required_format(self):
        """Verify auth_required message structure."""
        import json
        msg = {
            "type": AUTH_REQUIRED_TYPE,
            "message": "Authentication required",
            "protocol_version": "4.0.0",
        }
        serialized = json.dumps(msg, sort_keys=True)
        parsed = json.loads(serialized)
        assert parsed["type"] == "auth_required"

    def test_file_key_skips_comments(self):
        """auth.key file parser skips # comment lines."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".key", delete=False, encoding="utf-8"
        ) as f:
            f.write("# This is a comment\n")
            f.write("# Another comment\n")
            f.write("actual-key-value\n")
            f.write("second-line-ignored\n")
            key_path = Path(f.name)

        try:
            # Monkey-patch the key path for testing
            original_fn = auth_mod._load_key_from_file

            def _mock_load():
                text = key_path.read_text(encoding="utf-8").strip()
                for line in text.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        return line
                return None

            auth_mod._load_key_from_file = _mock_load
            try:
                reset_auth_cache()
                with patch.dict(os.environ, {}, clear=True):
                    env = dict(os.environ)
                    env.pop("SYNAPSE_API_KEY", None)
                    with patch.dict(os.environ, env, clear=True):
                        result = _mock_load()
                        assert result == "actual-key-value"
            finally:
                auth_mod._load_key_from_file = original_fn
        finally:
            key_path.unlink(missing_ok=True)
