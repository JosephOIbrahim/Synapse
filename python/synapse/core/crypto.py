"""
Synapse Encryption Layer

Optional Fernet (AES-128-CBC + HMAC-SHA256) encryption for data at rest.
Requires: pip install synapse[encryption]  (cryptography>=41.0.0)

Key sources (priority order):
1. SYNAPSE_ENCRYPTION_KEY environment variable (base64-encoded Fernet key)
2. ~/.synapse/encryption.key file
3. Auto-generate and save to ~/.synapse/encryption.key

Encryption modes:
- Line encryption: Each JSONL line encrypted independently (memory, audit, gates)
- File encryption: Entire file content encrypted (index.json, context.md, decisions.md)

Backward compatibility:
- Lines/files without the SYNAPSE_ENC_V1: prefix are treated as plaintext
- Encrypted data always starts with SYNAPSE_ENC_V1: followed by the Fernet token
"""

import os
import stat
import threading
from pathlib import Path
from typing import Optional

# Magic prefix to detect encrypted content
MAGIC_PREFIX = "SYNAPSE_ENC_V1:"

# Optional dependency — follows existing pattern (SERVER_AVAILABLE, UI_AVAILABLE)
try:
    from cryptography.fernet import Fernet
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    Fernet = None  # type: ignore[assignment,misc]


class CryptoEngine:
    """
    Singleton encryption engine using Fernet symmetric encryption.

    Thread-safe. Lazy-initialized on first use.
    """

    _instance: Optional['CryptoEngine'] = None
    _lock = threading.Lock()

    def __init__(self, key: Optional[bytes] = None):
        if not ENCRYPTION_AVAILABLE:
            raise RuntimeError(
                "cryptography package not installed. "
                "Install with: pip install synapse[encryption]"
            )
        self._key = key or self._resolve_key()
        self._fernet = Fernet(self._key)

    @classmethod
    def get_instance(cls) -> 'CryptoEngine':
        """Get or create singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        with cls._lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_key() -> bytes:
        """Resolve encryption key from env, file, or auto-generate."""
        # 1. Environment variable
        env_key = os.environ.get("SYNAPSE_ENCRYPTION_KEY")
        if env_key:
            return env_key.encode("utf-8") if isinstance(env_key, str) else env_key

        # 2. Key file
        key_dir = Path.home() / ".synapse"
        key_file = key_dir / "encryption.key"

        if key_file.exists():
            return key_file.read_bytes().strip()

        # 3. Auto-generate
        key = Fernet.generate_key()
        key_dir.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(key)

        # Best-effort owner-only permissions (works on Unix, best-effort on Windows)
        try:
            key_file.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        except OSError:
            pass

        return key

    # ------------------------------------------------------------------
    # Line encryption (for JSONL append-only files)
    # ------------------------------------------------------------------

    def encrypt_line(self, plaintext: str) -> str:
        """Encrypt a single line. Returns MAGIC_PREFIX + Fernet token."""
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return MAGIC_PREFIX + token.decode("utf-8")

    def decrypt_line(self, line: str) -> str:
        """Decrypt a single line. Returns plaintext if not encrypted."""
        if line.startswith(MAGIC_PREFIX):
            token = line[len(MAGIC_PREFIX):].encode("utf-8")
            return self._fernet.decrypt(token).decode("utf-8")
        # Plaintext passthrough (backward compatibility)
        return line

    # ------------------------------------------------------------------
    # File encryption (for JSON/MD files)
    # ------------------------------------------------------------------

    def encrypt_file_content(self, plaintext: str) -> str:
        """Encrypt entire file content."""
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return MAGIC_PREFIX + token.decode("utf-8")

    def decrypt_file_content(self, content: str) -> str:
        """Decrypt file content. Returns plaintext if not encrypted."""
        if content.startswith(MAGIC_PREFIX):
            token = content[len(MAGIC_PREFIX):].encode("utf-8")
            return self._fernet.decrypt(token).decode("utf-8")
        return content


def get_crypto() -> Optional['CryptoEngine']:
    """Get CryptoEngine if encryption is available, else None."""
    if ENCRYPTION_AVAILABLE:
        return CryptoEngine.get_instance()
    return None
