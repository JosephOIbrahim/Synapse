"""Tests for synapse_tone.py — coaching language formatting."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from synapse_tone import enrich_error_message, format_success_message


# ── Error enrichment tests ───────────────────────────────────


def test_node_not_found_enriched():
    msg = enrich_error_message("Node not found at '/stage/foo'", "")
    assert "Couldn't find" in msg
    assert "/stage/foo" in msg
    assert "search the scene" in msg


def test_couldnt_find_enriched():
    msg = enrich_error_message("Couldn't find node at /stage/bar", "")
    assert "Couldn't find" in msg
    assert "/stage/bar" in msg


def test_parameter_error_enriched():
    msg = enrich_error_message("Parameter 'intensity' does not exist", "")
    assert "parameter" in msg.lower()
    assert "xn__" in msg


def test_permission_error_enriched():
    msg = enrich_error_message("Permission denied: not writable", "")
    assert "permissions" in msg.lower()
    assert ".synapse" in msg


def test_nonetype_error_enriched():
    msg = enrich_error_message("AttributeError: 'NoneType' has no attribute 'path'", "")
    assert "wasn't there yet" in msg


def test_generic_error_gets_next_step():
    msg = enrich_error_message("Something broke unexpectedly", "")
    assert "different approach" in msg


def test_error_with_next_step_not_doubled():
    msg = enrich_error_message("I can try something else", "")
    # Already has a next step, shouldn't add another
    assert "different approach" not in msg


# ── Success formatting tests ─────────────────────────────────


def test_success_basic():
    msg = format_success_message("Created light", {"result": "/stage/light"})
    assert "Created light" in msg
    assert "done" in msg


def test_success_with_verification_ok():
    msg = format_success_message("Created light", {
        "result": "/stage/light",
        "verification": {
            "/stage/light": {"exists": True, "errors": None},
        },
    })
    assert "Verified" in msg


def test_success_with_verification_missing():
    msg = format_success_message("Created light", {
        "result": "/stage/light",
        "verification": {
            "/stage/light": {"exists": False, "errors": None},
        },
    })
    assert "Heads up" in msg
    assert "/stage/light" in msg


def test_success_non_dict():
    msg = format_success_message("Did something", "string result")
    assert "Did something" in msg
    assert "done" in msg
