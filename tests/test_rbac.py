"""
Tests for Synapse RBAC (Role-Based Access Control).

Sprint D Phase 1: Role enum, permission matrix, check_permission(), is_rbac_enabled().
"""

import os
import sys
import importlib.util

import pytest


# ---------------------------------------------------------------------------
# Import rbac module via importlib (no hou dependency)
# ---------------------------------------------------------------------------
_RBAC_PATH = os.path.join(
    os.path.dirname(__file__), "..", "python", "synapse", "server", "rbac.py"
)

spec = importlib.util.spec_from_file_location("synapse.server.rbac", os.path.abspath(_RBAC_PATH))
rbac_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rbac_mod)

Role = rbac_mod.Role
check_permission = rbac_mod.check_permission
get_role_permissions = rbac_mod.get_role_permissions
get_role_wildcard_patterns = rbac_mod.get_role_wildcard_patterns
is_rbac_enabled = rbac_mod.is_rbac_enabled
role_at_least = rbac_mod.role_at_least


# =========================================================================
# Role Enum
# =========================================================================


class TestRoleEnum:
    def test_role_values(self):
        assert Role.VIEWER.value == "viewer"
        assert Role.ARTIST.value == "artist"
        assert Role.LEAD.value == "lead"
        assert Role.ADMIN.value == "admin"

    def test_role_from_string(self):
        assert Role("viewer") is Role.VIEWER
        assert Role("admin") is Role.ADMIN

    def test_role_invalid_raises(self):
        with pytest.raises(ValueError):
            Role("superuser")


# =========================================================================
# VIEWER Permissions
# =========================================================================


class TestViewerPermissions:
    """Viewer can read, cannot write."""

    @pytest.mark.parametrize("cmd", [
        "ping", "get_health", "get_help",
        "get_parm", "get_scene_info", "get_selection",
        "capture_viewport", "knowledge_lookup",
        "inspect_selection", "inspect_scene", "inspect_node",
        "read_material", "get_metrics", "router_stats",
        "tops_get_work_items", "tops_get_cook_stats",
    ])
    def test_viewer_allowed_read_commands(self, cmd):
        assert check_permission(Role.VIEWER, cmd) is True

    @pytest.mark.parametrize("cmd", [
        "create_node", "delete_node", "set_parm",
        "execute_python", "execute_vex",
        "render", "create_material",
        "server_config", "manage_users",
    ])
    def test_viewer_denied_write_commands(self, cmd):
        assert check_permission(Role.VIEWER, cmd) is False

    def test_viewer_wildcard_inspect(self):
        """Viewer wildcards match inspect_* and get_*."""
        assert check_permission(Role.VIEWER, "inspect_foo") is True
        assert check_permission(Role.VIEWER, "get_something") is True

    def test_viewer_wildcard_does_not_grant_write(self):
        """Wildcards don't bypass deny set."""
        assert check_permission(Role.VIEWER, "execute_python") is False


# =========================================================================
# ARTIST Permissions
# =========================================================================


class TestArtistPermissions:
    """Artist can read + write, cannot manage users or configure server."""

    @pytest.mark.parametrize("cmd", [
        "create_node", "delete_node", "set_parm",
        "execute_python", "execute_vex",
        "render", "render_settings", "wedge",
        "create_material", "assign_material",
        "tops_cook_node", "tops_generate_items",
        "batch_commands",
    ])
    def test_artist_allowed_write_commands(self, cmd):
        assert check_permission(Role.ARTIST, cmd) is True

    @pytest.mark.parametrize("cmd", [
        "server_config", "manage_users", "reload_config",
    ])
    def test_artist_denied_admin_commands(self, cmd):
        assert check_permission(Role.ARTIST, cmd) is False

    def test_artist_inherits_viewer_reads(self):
        assert check_permission(Role.ARTIST, "get_parm") is True
        assert check_permission(Role.ARTIST, "capture_viewport") is True

    def test_artist_tops_wildcard(self):
        assert check_permission(Role.ARTIST, "tops_setup_wedge") is True


# =========================================================================
# LEAD Permissions
# =========================================================================


class TestLeadPermissions:
    """Lead can do everything artist can + manage users."""

    def test_lead_can_manage_users(self):
        assert check_permission(Role.LEAD, "manage_users") is True

    def test_lead_can_list_sessions(self):
        assert check_permission(Role.LEAD, "list_sessions") is True

    def test_lead_cannot_server_config(self):
        assert check_permission(Role.LEAD, "server_config") is False

    def test_lead_inherits_artist(self):
        assert check_permission(Role.LEAD, "execute_python") is True
        assert check_permission(Role.LEAD, "render") is True


# =========================================================================
# ADMIN Permissions
# =========================================================================


class TestAdminPermissions:
    """Admin has unrestricted access."""

    def test_admin_can_server_config(self):
        assert check_permission(Role.ADMIN, "server_config") is True

    def test_admin_can_manage_users(self):
        assert check_permission(Role.ADMIN, "manage_users") is True

    def test_admin_wildcard_matches_everything(self):
        assert check_permission(Role.ADMIN, "some_future_command") is True

    def test_admin_no_denials(self):
        """Admin deny set is empty."""
        assert check_permission(Role.ADMIN, "execute_python") is True
        assert check_permission(Role.ADMIN, "delete_node") is True


# =========================================================================
# Permission Utilities
# =========================================================================


class TestPermissionUtilities:
    def test_get_role_permissions_returns_set(self):
        perms = get_role_permissions(Role.VIEWER)
        assert isinstance(perms, set)
        assert "ping" in perms
        # Denied commands should be excluded
        assert "execute_python" not in perms

    def test_get_role_permissions_artist_includes_writes(self):
        perms = get_role_permissions(Role.ARTIST)
        assert "create_node" in perms
        assert "server_config" not in perms

    def test_get_wildcard_patterns(self):
        patterns = get_role_wildcard_patterns(Role.VIEWER)
        assert "inspect_*" in patterns
        assert "get_*" in patterns

    def test_admin_wildcard_star(self):
        patterns = get_role_wildcard_patterns(Role.ADMIN)
        assert "*" in patterns


# =========================================================================
# is_rbac_enabled
# =========================================================================


class TestRbacEnabled:
    def test_local_mode_disables_rbac(self, monkeypatch):
        monkeypatch.setenv("SYNAPSE_DEPLOY_MODE", "local")
        assert is_rbac_enabled() is False

    def test_no_env_defaults_to_local(self, monkeypatch):
        monkeypatch.delenv("SYNAPSE_DEPLOY_MODE", raising=False)
        assert is_rbac_enabled() is False

    def test_studio_lan_enables_rbac(self, monkeypatch):
        monkeypatch.setenv("SYNAPSE_DEPLOY_MODE", "studio-lan")
        assert is_rbac_enabled() is True

    def test_studio_vpn_enables_rbac(self, monkeypatch):
        monkeypatch.setenv("SYNAPSE_DEPLOY_MODE", "studio-vpn")
        assert is_rbac_enabled() is True

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("SYNAPSE_DEPLOY_MODE", "LOCAL")
        assert is_rbac_enabled() is False

    def test_whitespace_stripped(self, monkeypatch):
        monkeypatch.setenv("SYNAPSE_DEPLOY_MODE", "  local  ")
        assert is_rbac_enabled() is False


# =========================================================================
# Role Hierarchy
# =========================================================================


class TestRoleHierarchy:
    def test_admin_at_least_viewer(self):
        assert role_at_least(Role.ADMIN, Role.VIEWER) is True

    def test_viewer_not_at_least_artist(self):
        assert role_at_least(Role.VIEWER, Role.ARTIST) is False

    def test_artist_at_least_artist(self):
        assert role_at_least(Role.ARTIST, Role.ARTIST) is True

    def test_lead_at_least_artist(self):
        assert role_at_least(Role.LEAD, Role.ARTIST) is True

    def test_artist_not_at_least_lead(self):
        assert role_at_least(Role.ARTIST, Role.LEAD) is False
