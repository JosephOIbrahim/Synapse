"""Tests for synapse_hooks.py — safety validation and message enrichment."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from synapse_hooks import (
    validate_atomic_convention,
    validate_guard_usage,
    validate_execute_code,
)


# ── Atomic convention tests ──────────────────────────────────


def test_single_mutation_passes():
    code = "node = hou.node('/stage').createNode('null', 'test')"
    ok, msg = validate_atomic_convention(code)
    assert ok is True


def test_multiple_mutations_warns():
    code = (
        "node = hou.node('/stage').createNode('null', 'test')\n"
        "node.setInput(0, other_node)\n"
    )
    ok, msg = validate_atomic_convention(code)
    assert ok is False
    assert "multiple mutation types" in msg


def test_read_only_passes():
    code = "result = hou.node('/stage').children()"
    ok, msg = validate_atomic_convention(code)
    assert ok is True


def test_set_parm_only_passes():
    code = "hou.node('/stage/light').parm('intensity').set(2.0)"
    ok, msg = validate_atomic_convention(code)
    assert ok is True


# ── Guard usage tests ────────────────────────────────────────


def test_guard_create_passes():
    code = "node = ensure_node('/stage', 'null', 'test')"
    ok, msg = validate_guard_usage(code)
    assert ok is True


def test_raw_create_warns():
    code = "node = hou.node('/stage').createNode('null', 'test')"
    ok, msg = validate_guard_usage(code)
    assert ok is False
    assert "ensure_node()" in msg


def test_raw_connect_warns():
    code = "node.setInput(0, source)"
    ok, msg = validate_guard_usage(code)
    assert ok is False
    assert "ensure_connection()" in msg


def test_guard_connect_passes():
    code = "ensure_connection('/stage/source', '/stage/target', 0)"
    ok, msg = validate_guard_usage(code)
    assert ok is True


# ── Pre-validation integration ───────────────────────────────


def test_validate_clean_code_returns_none():
    code = "ensure_node('/stage', 'null', 'test')"
    result = validate_execute_code(code)
    assert result is None


def test_validate_multi_mutation_returns_warning():
    code = (
        "node = hou.node('/stage').createNode('null')\n"
        "node.destroy()\n"
    )
    result = validate_execute_code(code)
    assert result is not None
    assert "Safety note" in result
