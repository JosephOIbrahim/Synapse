"""
Tests for Sprint D Studio Integration.

End-to-end tests verifying DeployConfig -> RBAC -> Sessions wiring.
"""

import json
import os
import sys
import importlib.util
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: stub hou module
# ---------------------------------------------------------------------------
if "hou" not in sys.modules:
    from unittest.mock import MagicMock
    sys.modules["hou"] = MagicMock()

# ---------------------------------------------------------------------------
# Import modules via importlib — through the R307 bootstrap helpers.
#
# The old open-coded shape here was the exact class R307 killed in 25 files,
# in a different costume: it planted synapse/synapse.core/synapse.server via
# bare setdefault (no parent-attribute binding) AND planted the leaf modules
# BEFORE the parents, so the parents' attributes never pointed at the leaves.
# The attack-O crucible demonstrated this file was a LIVE surviving
# reproduction at HEAD: `pytest tests/test_studio_integration.py
# tests/test_websocket_cancel_reachable.py` -> ModuleNotFoundError. Same
# fix-at-the-perpetrator discipline; the remaining ~20 other-shape sites are
# R310's sweep.
# ---------------------------------------------------------------------------
from pkgbootstrap import ensure_package, load_module

_BASE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "python", "synapse"))

ensure_package("synapse", _BASE)
ensure_package("synapse.core", os.path.join(_BASE, "core"))
ensure_package("synapse.server", os.path.join(_BASE, "server"))

det_mod = load_module("synapse.core.determinism",
                      os.path.join(_BASE, "core", "determinism.py"))
rbac_mod = load_module("synapse.server.rbac",
                       os.path.join(_BASE, "server", "rbac.py"))
sess_mod = load_module("synapse.server.sessions",
                       os.path.join(_BASE, "server", "sessions.py"))

Role = rbac_mod.Role
check_permission = rbac_mod.check_permission
is_rbac_enabled = rbac_mod.is_rbac_enabled
SessionManager = sess_mod.SessionManager
DeployConfig = sess_mod.DeployConfig
load_deploy_config = sess_mod.load_deploy_config
hash_api_key = sess_mod.hash_api_key
load_user_directory = sess_mod.load_user_directory
lookup_user_by_key = sess_mod.lookup_user_by_key


# =========================================================================
# Integration: Deploy Config -> RBAC -> Sessions
# =========================================================================


class TestStudioIntegration:
    """End-to-end flow: config loaded, users resolved, permissions enforced."""

    def _make_studio_setup(self, tmp_path):
        """Create a complete studio config + user directory."""
        # API keys
        alice_key = "alice-studio-key-2025"
        bob_key = "bob-studio-key-2025"

        # users.json
        users_file = tmp_path / "users.json"
        users_data = {
            "users": [
                {
                    "id": "alice",
                    "name": "Alice Chen",
                    "role": "lead",
                    "key_hash": hash_api_key(alice_key),
                },
                {
                    "id": "bob",
                    "name": "Bob Kim",
                    "role": "viewer",
                    "key_hash": hash_api_key(bob_key),
                },
            ]
        }
        users_file.write_text(json.dumps(users_data, sort_keys=True), encoding="utf-8")

        # deploy.json
        deploy_file = tmp_path / "deploy.json"
        deploy_data = {
            "mode": "studio-lan",
            "bind": "0.0.0.0",
            "port": 9999,
            "auth_required": True,
            "users_file": str(users_file),
            "session_timeout": 300.0,
        }
        deploy_file.write_text(json.dumps(deploy_data, sort_keys=True), encoding="utf-8")

        return deploy_file, alice_key, bob_key

    def test_full_flow_lead_user(self, tmp_path, monkeypatch):
        """Lead user authenticates, creates session, passes RBAC for write commands."""
        deploy_file, alice_key, bob_key = self._make_studio_setup(tmp_path)

        # Load config
        cfg = load_deploy_config(str(deploy_file))
        assert cfg.mode == "studio-lan"
        assert cfg.auth_required is True

        # Enable RBAC
        monkeypatch.setenv("SYNAPSE_DEPLOY_MODE", cfg.mode)
        assert is_rbac_enabled() is True

        # Load users
        from pathlib import Path
        users = load_user_directory(Path(cfg.users_file))
        assert len(users) == 2

        # Authenticate Alice
        alice_info = lookup_user_by_key(alice_key, users)
        assert alice_info is not None
        assert alice_info["id"] == "alice"

        # Create session
        mgr = SessionManager(session_timeout=cfg.session_timeout)
        session = mgr.create_session(
            user_id=alice_info["id"],
            role=Role(alice_info["role"]),
            client_id="client_001",
            display_name=alice_info["name"],
        )
        assert session.role is Role.LEAD

        # RBAC: lead can write
        assert check_permission(session.role, "execute_python") is True
        assert check_permission(session.role, "create_node") is True
        assert check_permission(session.role, "manage_users") is True
        # Lead cannot server_config
        assert check_permission(session.role, "server_config") is False

    def test_full_flow_viewer_user(self, tmp_path, monkeypatch):
        """Viewer user authenticates but is blocked from write commands."""
        deploy_file, alice_key, bob_key = self._make_studio_setup(tmp_path)

        cfg = load_deploy_config(str(deploy_file))
        monkeypatch.setenv("SYNAPSE_DEPLOY_MODE", cfg.mode)

        from pathlib import Path
        users = load_user_directory(Path(cfg.users_file))

        # Authenticate Bob (viewer)
        bob_info = lookup_user_by_key(bob_key, users)
        assert bob_info is not None
        assert bob_info["id"] == "bob"

        mgr = SessionManager(session_timeout=cfg.session_timeout)
        session = mgr.create_session(
            user_id=bob_info["id"],
            role=Role(bob_info["role"]),
            client_id="client_002",
        )
        assert session.role is Role.VIEWER

        # RBAC: viewer can read
        assert check_permission(session.role, "get_parm") is True
        assert check_permission(session.role, "capture_viewport") is True
        # Viewer cannot write
        assert check_permission(session.role, "create_node") is False
        assert check_permission(session.role, "execute_python") is False

    def test_local_mode_skips_rbac(self, monkeypatch):
        """Local mode (default) disables RBAC -- backward compatible."""
        monkeypatch.delenv("SYNAPSE_DEPLOY_MODE", raising=False)
        cfg = DeployConfig(mode="local")
        assert cfg.bind == "127.0.0.1"
        assert cfg.auth_required is False
        assert is_rbac_enabled() is False

    def test_bad_key_not_authenticated(self, tmp_path):
        """Invalid API key fails user lookup."""
        deploy_file, alice_key, bob_key = self._make_studio_setup(tmp_path)

        from pathlib import Path
        cfg = load_deploy_config(str(deploy_file))
        users = load_user_directory(Path(cfg.users_file))

        result = lookup_user_by_key("wrong-key-entirely", users)
        assert result is None

    def test_session_lifecycle(self, tmp_path):
        """Session create -> touch -> expire lifecycle."""
        deploy_file, alice_key, bob_key = self._make_studio_setup(tmp_path)

        from pathlib import Path
        cfg = load_deploy_config(str(deploy_file))
        users = load_user_directory(Path(cfg.users_file))

        alice_info = lookup_user_by_key(alice_key, users)
        mgr = SessionManager(session_timeout=0.001)  # Very short timeout

        session = mgr.create_session(
            user_id=alice_info["id"],
            role=Role(alice_info["role"]),
            client_id="client_001",
        )
        assert mgr.count == 1

        # Let it expire
        import time
        time.sleep(0.01)
        expired = mgr.expire_stale()
        assert expired == 1
        assert mgr.count == 0

    def test_multiple_concurrent_sessions(self, tmp_path):
        """Multiple users can have sessions simultaneously."""
        deploy_file, alice_key, bob_key = self._make_studio_setup(tmp_path)

        from pathlib import Path
        cfg = load_deploy_config(str(deploy_file))
        users = load_user_directory(Path(cfg.users_file))

        mgr = SessionManager(session_timeout=3600.0)

        alice_info = lookup_user_by_key(alice_key, users)
        bob_info = lookup_user_by_key(bob_key, users)

        s1 = mgr.create_session("alice", Role.LEAD, "client_001")
        s2 = mgr.create_session("bob", Role.VIEWER, "client_002")

        assert mgr.count == 2
        sessions = mgr.active_sessions()
        user_ids = [s.user_id for s in sessions]
        assert user_ids == ["alice", "bob"]  # Sorted

    def test_deploy_config_studio_vpn_enables_tls(self):
        """VPN mode auto-enables TLS."""
        cfg = DeployConfig(mode="studio-vpn")
        assert cfg.tls_enabled is True
        assert cfg.bind == "0.0.0.0"
        assert cfg.auth_required is True

    def test_deploy_config_from_json(self, tmp_path):
        """Full deploy.json round-trip."""
        cfg_file = tmp_path / "deploy.json"
        data = {
            "mode": "studio-lan",
            "bind": "10.0.1.50",
            "port": 8888,
            "auth_required": True,
            "default_role": "viewer",
            "session_timeout": 1800.0,
        }
        cfg_file.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")

        cfg = load_deploy_config(str(cfg_file))
        assert cfg.mode == "studio-lan"
        assert cfg.bind == "10.0.1.50"
        assert cfg.port == 8888
        assert cfg.default_role == "viewer"
        assert cfg.session_timeout == 1800.0

    def test_hash_api_key_roundtrip(self):
        """Key hash can be generated and verified."""
        raw_key = "my-secret-key-2025"
        hashed = hash_api_key(raw_key)

        # Simulate lookup
        users = {"test_user": {"id": "test_user", "role": "artist", "key_hash": hashed}}
        result = lookup_user_by_key(raw_key, users)
        assert result is not None
        assert result["id"] == "test_user"

        # Wrong key fails
        assert lookup_user_by_key("wrong-key", users) is None
