"""SYNAPSE 2.0 Inspector — Mock tests.

Runs WITHOUT Houdini. Mocks the transport layer and validates:
  - Happy path extraction against the golden fixture
  - Schema compliance (Pydantic validation)
  - StageAST query helpers
  - Error propagation through the node chain
  - Transport error handling
  - Schema version compatibility
  - Input sanitization (target_path validation)
  - Graceful fallback for legacy transport (no timeout kwarg)
  - Configured vs. injected transport precedence

Every test uses fixtures from conftest.py — no inline golden JSON.
"""

from __future__ import annotations

import json

import pytest

from synapse.inspector import (
    ASTNode,
    DEFAULT_TIMEOUT_SECONDS,
    HoudiniExtractionError,
    InputConnection,
    InvalidTargetPathError,
    SchemaValidationError,
    SchemaVersionMismatchError,
    StageAST,
    StageNotFoundError,
    TransportError,
    TransportNotConfiguredError,
    configure_transport,
    is_transport_configured,
    synapse_inspect_stage,
)
from synapse.inspector.models import SCHEMA_VERSION
from conftest import make_mock_transport


# -----------------------------------------------------------------------------
# Happy path — structural assertions against the golden fixture
# -----------------------------------------------------------------------------


class TestHappyPath:
    def test_returns_stage_ast_instance(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert isinstance(ast, StageAST)

    def test_extracts_all_eight_nodes(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert len(ast) == 8

    def test_carries_schema_version(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast.schema_version == SCHEMA_VERSION

    def test_carries_target_path(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast.target_path == "/stage"

    def test_all_nodes_are_ast_node_instances(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        for node in ast:
            assert isinstance(node, ASTNode)


# -----------------------------------------------------------------------------
# Node identity — types and naming
# -----------------------------------------------------------------------------


class TestNodeIdentity:
    def test_node_types_match_golden(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast["geo"].node_type == "sopcreate"
        assert ast["mats"].node_type == "materiallibrary"
        assert ast["xf"].node_type == "xform"
        assert ast["ref"].node_type == "reference::2.0"
        assert ast["multi"].node_type == "merge"
        assert ast["comp"].node_type == "sublayer"
        assert ast["orphan"].node_type == "null"
        assert ast["bypassed_node"].node_type == "xform"

    def test_all_hou_paths_absolute(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        for node in ast:
            assert node.hou_path.startswith("/stage/")


# -----------------------------------------------------------------------------
# USD prim paths via lastModifiedPrims()
# -----------------------------------------------------------------------------


class TestUSDPrimPaths:
    def test_sopcreate_authors_geo(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast["geo"].usd_prim_paths == ["/geo"]

    def test_xform_modifies_existing_prim(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast["xf"].usd_prim_paths == ["/geo"]

    def test_error_node_has_empty_prims(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast["ref"].usd_prim_paths == []

    def test_bypassed_node_has_empty_prims(self, mock_transport):
        """Bypassed nodes contribute nothing to the composed stage."""
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast["bypassed_node"].usd_prim_paths == []

    def test_materiallibrary_empty_without_shaders(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast["mats"].usd_prim_paths == []

    def test_orphan_has_no_prims(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast["orphan"].usd_prim_paths == []


# -----------------------------------------------------------------------------
# Error state propagation
# -----------------------------------------------------------------------------


class TestErrorPropagation:
    def test_reference_errors_on_missing_file(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast["ref"].error_state == "error"

    def test_error_cascades_to_merge(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast["multi"].error_state == "error"

    def test_error_cascades_through_bypass(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast["bypassed_node"].error_state == "error"

    def test_error_cascades_to_display(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast["comp"].error_state == "error"

    def test_clean_nodes_remain_clean(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast["geo"].error_state == "clean"
        assert ast["mats"].error_state == "clean"
        assert ast["xf"].error_state == "clean"
        assert ast["orphan"].error_state == "clean"

    def test_error_message_populated_on_ref(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast["ref"].error_message is not None
        assert "does_not_exist" in ast["ref"].error_message

    def test_clean_nodes_have_null_error_message(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast["geo"].error_message is None
        assert ast["xf"].error_message is None


# -----------------------------------------------------------------------------
# Flags
# -----------------------------------------------------------------------------


class TestFlags:
    def test_only_comp_has_display_flag(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        display = [n for n in ast if n.display_flag]
        assert len(display) == 1
        assert display[0].node_name == "comp"

    def test_only_bypassed_node_is_bypassed(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        bypassed = [n for n in ast if n.bypass_flag]
        assert len(bypassed) == 1
        assert bypassed[0].node_name == "bypassed_node"


# -----------------------------------------------------------------------------
# Topology and indexed inputs
# -----------------------------------------------------------------------------


class TestTopology:
    def test_merge_has_three_indexed_inputs(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        multi = ast["multi"]
        assert len(multi.inputs) == 3
        assert multi.inputs[0] == InputConnection(index=0, path="/stage/xf")
        assert multi.inputs[1] == InputConnection(index=1, path="/stage/mats")
        assert multi.inputs[2] == InputConnection(index=2, path="/stage/ref")

    def test_xform_fans_out_to_two_outputs(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert set(ast["xf"].outputs) == {"/stage/multi", "/stage/ref"}

    def test_orphan_has_no_connections(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast["orphan"].inputs == []
        assert ast["orphan"].outputs == []

    def test_geo_has_no_inputs(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast["geo"].inputs == []


# -----------------------------------------------------------------------------
# StageAST query helpers
# -----------------------------------------------------------------------------


class TestStageASTHelpers:
    def test_by_name_finds_node(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        node = ast.by_name("geo")
        assert node is not None
        assert node.node_name == "geo"

    def test_by_name_returns_default_when_missing(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast.by_name("nonexistent") is None

    def test_by_type_filters_correctly(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        xforms = ast.by_type("xform")
        assert len(xforms) == 2  # xf and bypassed_node
        assert {n.node_name for n in xforms} == {"xf", "bypassed_node"}

    def test_display_node_returns_single(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast.display_node().node_name == "comp"

    def test_error_nodes_filtered(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        errors = ast.error_nodes()
        assert {n.node_name for n in errors} == {
            "ref", "multi", "bypassed_node", "comp",
        }

    def test_clean_nodes_filtered(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        clean = ast.clean_nodes()
        assert {n.node_name for n in clean} == {
            "geo", "mats", "xf", "orphan",
        }

    def test_warning_nodes_empty_in_fixture(self, mock_transport):
        """Golden fixture has no warning-state nodes."""
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast.warning_nodes() == []

    def test_orphans(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        orphans = ast.orphans()
        assert [n.node_name for n in orphans] == ["orphan"]

    def test_roots(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        roots = ast.roots()
        assert {n.node_name for n in roots} == {"geo", "mats"}

    def test_leaves(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        leaves = ast.leaves()
        assert [n.node_name for n in leaves] == ["comp"]

    def test_authoring_nodes(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        authoring = ast.authoring_nodes()
        assert {n.node_name for n in authoring} == {"geo", "xf"}

    def test_prims_at(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        touched = ast.prims_at("/geo")
        assert {n.node_name for n in touched} == {"geo", "xf"}

    def test_contains_by_name(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert "geo" in ast
        assert "nonexistent" not in ast

    def test_getitem_by_int_index(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        # Nodes sorted by hou_path, so index 0 is bypassed_node
        assert ast[0].node_name == "bypassed_node"

    def test_getitem_rejects_float(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        with pytest.raises(TypeError, match="str .* or int"):
            ast[1.5]  # type: ignore[index]


# -----------------------------------------------------------------------------
# Reserved fields are empty in Week 1
# -----------------------------------------------------------------------------


class TestReservedFields:
    def test_children_empty_in_week1(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        for node in ast:
            assert node.children == []

    def test_key_parms_empty_in_week1(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        for node in ast:
            assert node.key_parms == {}

    def test_provenance_none_in_week1(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        for node in ast:
            assert node.provenance is None


# -----------------------------------------------------------------------------
# Serialization round-trip
# -----------------------------------------------------------------------------


class TestSerialization:
    def test_to_json_produces_valid_json(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        serialized = ast.to_json()
        roundtrip = json.loads(serialized)
        assert roundtrip["schema_version"] == SCHEMA_VERSION
        assert len(roundtrip["nodes"]) == 8

    def test_to_json_is_deterministic(self, mock_transport):
        """Same input must produce byte-identical output."""
        ast1 = synapse_inspect_stage(execute_python_fn=mock_transport)
        ast2 = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast1.to_json() == ast2.to_json()

    def test_to_payload_has_envelope(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        payload = ast.to_payload()
        assert "schema_version" in payload
        assert "target_path" in payload
        assert "nodes" in payload


# -----------------------------------------------------------------------------
# Houdini error routing
# -----------------------------------------------------------------------------


class TestHoudiniErrorRouting:
    def test_stage_not_found_routes_correctly(self):
        transport = make_mock_transport(
            '{"synapse_error": "stage_not_found", "target_path": "/stage"}'
        )
        with pytest.raises(StageNotFoundError) as exc_info:
            synapse_inspect_stage(execute_python_fn=transport)
        assert exc_info.value.path == "/stage"

    def test_children_enumeration_failure_routes_correctly(self):
        transport = make_mock_transport(json.dumps({
            "synapse_error": "children_enumeration_failed",
            "target_path": "/stage",
            "detail": "whatever went wrong",
        }))
        with pytest.raises(HoudiniExtractionError) as exc_info:
            synapse_inspect_stage(execute_python_fn=transport)
        assert exc_info.value.detail == "whatever went wrong"

    def test_script_crash_preserves_traceback(self):
        transport = make_mock_transport(json.dumps({
            "synapse_error": "extraction_script_crash",
            "detail": "boom",
            "traceback": "Traceback (most recent call last):\n  ...",
        }))
        with pytest.raises(HoudiniExtractionError) as exc_info:
            synapse_inspect_stage(execute_python_fn=transport)
        assert exc_info.value.traceback is not None
        assert "Traceback" in exc_info.value.traceback

    def test_unknown_error_code(self):
        transport = make_mock_transport(
            '{"synapse_error": "mystery_error"}'
        )
        with pytest.raises(HoudiniExtractionError, match="Unknown Houdini error"):
            synapse_inspect_stage(execute_python_fn=transport)


# -----------------------------------------------------------------------------
# Schema version checking
# -----------------------------------------------------------------------------


class TestSchemaVersionChecking:
    def test_missing_schema_version_raises(self):
        transport = make_mock_transport('{"target_path": "/stage", "nodes": []}')
        with pytest.raises(SchemaValidationError, match="schema_version"):
            synapse_inspect_stage(execute_python_fn=transport)

    def test_non_string_schema_version_raises(self):
        transport = make_mock_transport(
            '{"schema_version": 1.0, "target_path": "/stage", "nodes": []}'
        )
        with pytest.raises(SchemaValidationError, match="must be str"):
            synapse_inspect_stage(execute_python_fn=transport)

    def test_version_mismatch_raises(self):
        transport = make_mock_transport(
            '{"schema_version": "9.9.9", "target_path": "/stage", "nodes": []}'
        )
        with pytest.raises(SchemaVersionMismatchError) as exc_info:
            synapse_inspect_stage(execute_python_fn=transport)
        assert exc_info.value.expected == SCHEMA_VERSION
        assert exc_info.value.received == "9.9.9"


# -----------------------------------------------------------------------------
# Target path validation (input sanitization)
# -----------------------------------------------------------------------------


class TestTargetPathValidation:
    def test_default_path_accepted(self, mock_transport):
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert ast is not None

    def test_relative_path_rejected(self, mock_transport):
        with pytest.raises(InvalidTargetPathError):
            synapse_inspect_stage("stage", execute_python_fn=mock_transport)

    def test_empty_path_rejected(self, mock_transport):
        with pytest.raises(InvalidTargetPathError):
            synapse_inspect_stage("", execute_python_fn=mock_transport)

    def test_non_string_path_rejected(self, mock_transport):
        with pytest.raises(InvalidTargetPathError):
            synapse_inspect_stage(
                123,  # type: ignore[arg-type]
                execute_python_fn=mock_transport,
            )

    @pytest.mark.parametrize("injection", [
        "/stage'; import os; os.system('rm -rf /'); '",
        "/stage\"',hou.hipFile.clear(),'",
        "/stage\nprint('injected')",
        "/stage; evil_code",
        "/stage with space",
        "/stage\x00null",
    ])
    def test_injection_attempts_rejected(self, mock_transport, injection):
        """Sanitization blocks anything that could escape repr() in the script."""
        with pytest.raises(InvalidTargetPathError):
            synapse_inspect_stage(
                injection, execute_python_fn=mock_transport,
            )

    def test_nested_context_accepted(self, mock_transport):
        """Nested paths like /stage/subnet should be accepted by validator."""
        # Will succeed validation; transport mock returns golden data regardless.
        ast = synapse_inspect_stage(
            "/obj/geo1", execute_python_fn=mock_transport,
        )
        assert ast is not None


# -----------------------------------------------------------------------------
# Transport layer integration
# -----------------------------------------------------------------------------


class TestTransportIntegration:
    def test_raises_when_no_transport_configured(self):
        # autouse cleanup_transport has already reset global state.
        assert not is_transport_configured()
        with pytest.raises(TransportNotConfiguredError):
            synapse_inspect_stage()

    def test_configured_transport_used(self, mock_transport):
        configure_transport(mock_transport)
        assert is_transport_configured()
        ast = synapse_inspect_stage()
        assert len(ast) == 8

    def test_explicit_transport_overrides_configured(self, mock_transport):
        """Explicit execute_python_fn wins over configured transport."""
        def broken_transport(code: str, *, timeout=None) -> str:
            raise AssertionError("Configured transport should not be called")
        configure_transport(broken_transport)
        # Pass mock_transport explicitly — should NOT touch configured
        ast = synapse_inspect_stage(execute_python_fn=mock_transport)
        assert len(ast) == 8

    def test_legacy_transport_fallback(self, mock_transport_legacy):
        """Transport without timeout kwarg still works via TypeError fallback."""
        ast = synapse_inspect_stage(execute_python_fn=mock_transport_legacy)
        assert len(ast) == 8

    def test_transport_error_wrapped(self):
        """Unknown transport exceptions are wrapped in TransportError."""
        def broken(code: str, *, timeout=None) -> str:
            raise ConnectionRefusedError("Houdini not running")
        with pytest.raises(TransportError) as exc_info:
            synapse_inspect_stage(execute_python_fn=broken)
        assert isinstance(exc_info.value.underlying, ConnectionRefusedError)

    def test_timeout_passed_to_modern_transport(self):
        received = {}
        def capturing(code: str, *, timeout=None) -> str:
            received["timeout"] = timeout
            return '{"schema_version": "' + SCHEMA_VERSION + '", "target_path": "/stage", "nodes": []}'
        synapse_inspect_stage(execute_python_fn=capturing, timeout=5.0)
        assert received["timeout"] == 5.0

    def test_default_timeout_applied(self):
        received = {}
        def capturing(code: str, *, timeout=None) -> str:
            received["timeout"] = timeout
            return '{"schema_version": "' + SCHEMA_VERSION + '", "target_path": "/stage", "nodes": []}'
        synapse_inspect_stage(execute_python_fn=capturing)
        assert received["timeout"] == DEFAULT_TIMEOUT_SECONDS


# -----------------------------------------------------------------------------
# Response parsing edge cases
# -----------------------------------------------------------------------------


class TestResponseParsing:
    def test_empty_response_raises(self):
        transport = make_mock_transport("")
        with pytest.raises(SchemaValidationError, match="empty"):
            synapse_inspect_stage(execute_python_fn=transport)

    def test_whitespace_only_response_raises(self):
        transport = make_mock_transport("   \n\t\n   ")
        with pytest.raises(SchemaValidationError, match="empty"):
            synapse_inspect_stage(execute_python_fn=transport)

    def test_malformed_json_raises(self):
        transport = make_mock_transport("not valid json at all")
        with pytest.raises(SchemaValidationError, match="not valid JSON"):
            synapse_inspect_stage(execute_python_fn=transport)

    def test_non_object_root_raises(self):
        transport = make_mock_transport("[1, 2, 3]")
        with pytest.raises(SchemaValidationError, match="must be a JSON object"):
            synapse_inspect_stage(execute_python_fn=transport)

    def test_nodes_field_wrong_type_raises(self):
        transport = make_mock_transport(
            '{"schema_version": "' + SCHEMA_VERSION + '", "target_path": "/stage", "nodes": "not a list"}'
        )
        with pytest.raises(SchemaValidationError, match="must be a list"):
            synapse_inspect_stage(execute_python_fn=transport)

    def test_invalid_node_schema_raises(self):
        transport = make_mock_transport(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "target_path": "/stage",
            "nodes": [{"node_name": "incomplete"}],  # missing required fields
        }))
        with pytest.raises(SchemaValidationError, match="validation failed"):
            synapse_inspect_stage(execute_python_fn=transport)

    def test_empty_nodes_list_is_valid(self):
        """An empty /stage is a legitimate response, not an error."""
        transport = make_mock_transport(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "target_path": "/stage",
            "nodes": [],
        }))
        ast = synapse_inspect_stage(execute_python_fn=transport)
        assert len(ast) == 0
        assert ast.display_node() is None
        assert ast.error_nodes() == []


# -----------------------------------------------------------------------------
# Model-level validation
# -----------------------------------------------------------------------------


class TestModelValidation:
    def test_ast_node_rejects_relative_hou_path(self):
        with pytest.raises(ValueError, match="absolute"):
            ASTNode(
                node_name="bad",
                node_type="null",
                hou_path="relative/path",
                display_flag=False,
                bypass_flag=False,
                error_state="clean",
            )

    def test_ast_node_rejects_relative_usd_prim_path(self):
        with pytest.raises(ValueError, match="absolute"):
            ASTNode(
                node_name="bad",
                node_type="null",
                hou_path="/stage/bad",
                usd_prim_paths=["relative_prim"],
                display_flag=False,
                bypass_flag=False,
                error_state="clean",
            )

    def test_ast_node_rejects_invalid_error_state(self):
        with pytest.raises(Exception):  # pydantic.ValidationError
            ASTNode(
                node_name="bad",
                node_type="null",
                hou_path="/stage/bad",
                display_flag=False,
                bypass_flag=False,
                error_state="catastrophic",  # not in Literal
            )

    def test_input_connection_rejects_negative_index(self):
        with pytest.raises(Exception):
            InputConnection(index=-1, path="/stage/x")

    def test_ast_node_is_frozen(self):
        """Immutability: can't mutate after construction."""
        node = ASTNode(
            node_name="x",
            node_type="null",
            hou_path="/stage/x",
            display_flag=False,
            bypass_flag=False,
            error_state="clean",
        )
        with pytest.raises(Exception):  # ValidationError on frozen model
            node.node_name = "mutated"  # type: ignore[misc]

    def test_error_message_length_capped(self):
        """error_message has max_length=500 to prevent unbounded growth."""
        with pytest.raises(Exception):
            ASTNode(
                node_name="x",
                node_type="null",
                hou_path="/stage/x",
                display_flag=False,
                bypass_flag=False,
                error_state="error",
                error_message="x" * 501,
            )
