"""
Tests for Synapse Multi-User Sessions.

Sprint D Phase 2: UserSession, SessionManager, user directory, deploy config.
"""

import hashlib
import json
import os
import sys
import importlib.util
import tempfile
import time

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: stub hou module before importing sessions
# ---------------------------------------------------------------------------
if "hou" not in sys.modules:
    from unittest.mock import MagicMock
    sys.modules["hou"] = MagicMock()

# Import via importlib to avoid package resolution issues
_SESSIONS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "python", "synapse", "server", "sessions.py"
)
_RBAC_PATH = os.path.join(
    os.path.dirname(__file__), "..", "python", "synapse", "server", "rbac.py"
)
_DETERMINISM_PATH = os.path.join(
    os.path.dirname(__file__), "..", "python", "synapse", "core", "determinism.py"
)

# Save original sys.modules state BEFORE any patching
_PATCHED_KEYS = ("synapse", "synapse.core", "synapse.core.determinism",
                 "synapse.server", "synapse.server.rbac")
_saved_modules = {k: sys.modules[k] for k in _PATCHED_KEYS if k in sys.modules}
_absent_keys = [k for k in _PATCHED_KEYS if k not in sys.modules]

# Load determinism first (dependency)
spec_det = importlib.util.spec_from_file_location("synapse.core.determinism", os.path.abspath(_DETERMINISM_PATH))
det_mod = importlib.util.module_from_spec(spec_det)
sys.modules["synapse.core.determinism"] = det_mod
spec_det.loader.exec_module(det_mod)

# Load rbac (dependency)
spec_rbac = importlib.util.spec_from_file_location("synapse.server.rbac", os.path.abspath(_RBAC_PATH))
rbac_mod = importlib.util.module_from_spec(spec_rbac)
sys.modules["synapse.server.rbac"] = rbac_mod
spec_rbac.loader.exec_module(rbac_mod)

# Temporarily patch package stubs so sessions.py relative imports resolve.
# Use setdefault to avoid clobbering the real synapse package if already imported
# (unconditional assignment during collection corrupts sys.modules for later tests).
sys.modules.setdefault("synapse", type(sys)("synapse"))
sys.modules.setdefault("synapse.core", type(sys)("synapse.core"))
sys.modules.setdefault("synapse.core.determinism", det_mod)
sys.modules.setdefault("synapse.server", type(sys)("synapse.server"))
sys.modules.setdefault("synapse.server.rbac", rbac_mod)

# Load sessions
spec_sess = importlib.util.spec_from_file_location("synapse.server.sessions", os.path.abspath(_SESSIONS_PATH))
sess_mod = importlib.util.module_from_spec(spec_sess)
spec_sess.loader.exec_module(sess_mod)

# Immediately restore sys.modules — prevent pollution of other test files
for _k, _v in _saved_modules.items():
    sys.modules[_k] = _v
for _k in _absent_keys:
    sys.modules.pop(_k, None)

Role = rbac_mod.Role
UserSession = sess_mod.UserSession
SessionManager = sess_mod.SessionManager
hash_api_key = sess_mod.hash_api_key
load_user_directory = sess_mod.load_user_directory
lookup_user_by_key = sess_mod.lookup_user_by_key
DeployConfig = sess_mod.DeployConfig
load_deploy_config = sess_mod.load_deploy_config


# =========================================================================
# SessionManager
# =========================================================================


class TestSessionManager:
    def setup_method(self):
        self.mgr = SessionManager(session_timeout=60.0)

    def test_create_session(self):
        s = self.mgr.create_session("alice", Role.ARTIST, "client_001")
        assert s.user_id == "alice"
        assert s.role is Role.ARTIST
        assert s.client_id == "client_001"
        assert s.session_id  # non-empty

    def test_get_session(self):
        s = self.mgr.create_session("alice", Role.ARTIST, "client_001")
        fetched = self.mgr.get_session(s.session_id)
        assert fetched is s

    def test_get_session_not_found(self):
        assert self.mgr.get_session("nonexistent") is None

    def test_get_by_client(self):
        s = self.mgr.create_session("bob", Role.VIEWER, "client_002")
        fetched = self.mgr.get_by_client("client_002")
        assert fetched is s

    def test_get_by_client_not_found(self):
        assert self.mgr.get_by_client("unknown") is None

    def test_touch_updates_last_active(self):
        s = self.mgr.create_session("alice", Role.ARTIST, "client_001")
        old_active = s.last_active
        time.sleep(0.01)
        self.mgr.touch(s.session_id)
        assert s.last_active > old_active

    def test_remove_session(self):
        s = self.mgr.create_session("alice", Role.ARTIST, "client_001")
        self.mgr.remove_session(s.session_id)
        assert self.mgr.get_session(s.session_id) is None
        assert self.mgr.get_by_client("client_001") is None

    def test_remove_by_client(self):
        s = self.mgr.create_session("alice", Role.ARTIST, "client_001")
        removed = self.mgr.remove_by_client("client_001")
        assert removed is s
        assert self.mgr.count == 0

    def test_remove_by_client_not_found(self):
        assert self.mgr.remove_by_client("unknown") is None

    def test_expire_stale(self):
        # Create session with effectively expired timeout
        s = self.mgr.create_session("alice", Role.ARTIST, "client_001")
        expired = self.mgr.expire_stale(max_idle=0.0)
        assert expired == 1
        assert self.mgr.count == 0

    def test_expire_stale_keeps_active(self):
        self.mgr.create_session("alice", Role.ARTIST, "client_001")
        expired = self.mgr.expire_stale(max_idle=9999.0)
        assert expired == 0
        assert self.mgr.count == 1

    def test_active_sessions_sorted(self):
        self.mgr.create_session("charlie", Role.VIEWER, "client_003")
        self.mgr.create_session("alice", Role.ARTIST, "client_001")
        self.mgr.create_session("bob", Role.LEAD, "client_002")
        sessions = self.mgr.active_sessions()
        names = [s.user_id for s in sessions]
        assert names == ["alice", "bob", "charlie"]

    def test_count_property(self):
        assert self.mgr.count == 0
        self.mgr.create_session("alice", Role.ARTIST, "client_001")
        assert self.mgr.count == 1
        self.mgr.create_session("bob", Role.VIEWER, "client_002")
        assert self.mgr.count == 2

    def test_deterministic_session_ids(self):
        """Same inputs at same counter produce same ID."""
        mgr1 = SessionManager()
        mgr2 = SessionManager()
        s1 = mgr1.create_session("alice", Role.ARTIST, "c1")
        s2 = mgr2.create_session("alice", Role.ARTIST, "c1")
        assert s1.session_id == s2.session_id

    def test_display_name_defaults_to_user_id(self):
        s = self.mgr.create_session("alice", Role.ARTIST, "client_001")
        assert s.display_name == "alice"

    def test_display_name_override(self):
        s = self.mgr.create_session("alice", Role.ARTIST, "client_001", display_name="Alice Chen")
        assert s.display_name == "Alice Chen"

    def test_metadata_stored(self):
        meta = {"ip": "192.168.1.10", "user_agent": "claude-code/1.0"}
        s = self.mgr.create_session("alice", Role.ARTIST, "client_001", metadata=meta)
        assert s.metadata["ip"] == "192.168.1.10"


# =========================================================================
# User Directory
# =========================================================================


class TestUserDirectory:
    def test_hash_api_key(self):
        h = hash_api_key("my-secret-key")
        assert h.startswith("sha256:")
        assert len(h) == 7 + 64  # "sha256:" + 64 hex chars

    def test_hash_deterministic(self):
        assert hash_api_key("test") == hash_api_key("test")

    def test_load_user_directory(self, tmp_path):
        users_file = tmp_path / "users.json"
        data = {
            "users": [
                {"id": "alice", "name": "Alice Chen", "role": "lead", "key_hash": "sha256:abc"},
                {"id": "bob", "name": "Bob Kim", "role": "artist", "key_hash": "sha256:def"},
            ]
        }
        users_file.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")

        users = load_user_directory(users_file)
        assert len(users) == 2
        assert users["alice"]["name"] == "Alice Chen"
        assert users["bob"]["role"] == "artist"

    def test_load_user_directory_missing_file(self, tmp_path):
        users = load_user_directory(tmp_path / "nonexistent.json")
        assert users == {}

    def test_load_user_directory_invalid_json(self, tmp_path):
        bad_file = tmp_path / "users.json"
        bad_file.write_text("not json", encoding="utf-8")
        users = load_user_directory(bad_file)
        assert users == {}

    def test_lookup_user_by_key(self, tmp_path):
        key = "secret-key-123"
        key_hash = hash_api_key(key)
        users = {
            "alice": {"id": "alice", "role": "lead", "key_hash": key_hash},
        }
        result = lookup_user_by_key(key, users)
        assert result is not None
        assert result["id"] == "alice"

    def test_lookup_user_by_key_not_found(self):
        users = {
            "alice": {"id": "alice", "role": "lead", "key_hash": "sha256:wrong"},
        }
        result = lookup_user_by_key("bad-key", users)
        assert result is None

    def test_lookup_user_by_key_empty_token(self):
        users = {"alice": {"id": "alice", "key_hash": "sha256:abc"}}
        assert lookup_user_by_key("", users) is None

    def test_lookup_user_by_key_empty_directory(self):
        assert lookup_user_by_key("any-key", {}) is None


# =========================================================================
# Deploy Configuration
# =========================================================================


class TestDeployConfig:
    def test_local_mode_defaults(self):
        cfg = DeployConfig(mode="local")
        assert cfg.bind == "127.0.0.1"
        assert cfg.auth_required is False
        assert cfg.tls_enabled is False

    def test_studio_lan_mode_defaults(self):
        cfg = DeployConfig(mode="studio-lan")
        assert cfg.bind == "0.0.0.0"
        assert cfg.auth_required is True
        assert cfg.tls_enabled is False

    def test_studio_vpn_mode_defaults(self):
        cfg = DeployConfig(mode="studio-vpn")
        assert cfg.bind == "0.0.0.0"
        assert cfg.auth_required is True
        assert cfg.tls_enabled is True

    def test_explicit_bind_preserved(self):
        cfg = DeployConfig(mode="studio-lan", bind="10.0.0.1")
        assert cfg.bind == "10.0.0.1"

    def test_default_users_file(self):
        cfg = DeployConfig()
        assert "users.json" in cfg.users_file

    def test_load_deploy_config_from_file(self, tmp_path):
        cfg_file = tmp_path / "deploy.json"
        data = {
            "mode": "studio-lan",
            "bind": "192.168.1.100",
            "port": 8888,
            "auth_required": True,
            "session_timeout": 7200.0,
        }
        cfg_file.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        cfg = load_deploy_config(str(cfg_file))
        assert cfg.mode == "studio-lan"
        assert cfg.bind == "192.168.1.100"
        assert cfg.port == 8888
        assert cfg.session_timeout == 7200.0

    def test_load_deploy_config_missing_file(self, monkeypatch):
        monkeypatch.delenv("SYNAPSE_DEPLOY_CONFIG", raising=False)
        monkeypatch.delenv("SYNAPSE_DEPLOY_MODE", raising=False)
        cfg = load_deploy_config("/nonexistent/deploy.json")
        assert cfg.mode == "local"

    def test_load_deploy_config_from_env_mode(self, monkeypatch):
        monkeypatch.delenv("SYNAPSE_DEPLOY_CONFIG", raising=False)
        monkeypatch.setenv("SYNAPSE_DEPLOY_MODE", "studio-lan")
        cfg = load_deploy_config("/nonexistent/path.json")
        assert cfg.mode == "studio-lan"
        assert cfg.auth_required is True
