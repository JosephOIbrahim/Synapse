"""Cognitive tools: ``synapse_apply_fixture`` / ``synapse_remove_fixture``.

The M5 BLOCKS reconciler mounted on the Dispatcher seam, in the same shape as
``synapse.cognitive.tools.inspect_stage``: a pure function per tool, a schema
registered alongside it, and an adapter branch in ``mcp_server.call_tool``.

Zero ``hou`` -- enforced by ``tests/test_cognitive_boundary.py``. The Houdini
work lives in ``synapse.blocks.runtime``; this module composes a three-line
script that calls it and ships that through an injected transport, exactly as
the Inspector does.

Why a three-line script and not an embedded implementation
----------------------------------------------------------
The Inspector inlines its whole extraction routine into a template string. The
reconciler must not: its invariants (F-1..F-5) are proved by a headless hython
harness that imports ``synapse.blocks.runtime`` directly. If the logic also
existed as a string in this file, the harness would be proving something other
than what the tool runs. One implementation, two callers.

Split-globals hazard
--------------------
The bridge execs injected code with ``exec(code, G, L)`` where ``G is not L``
(see ``synapse/inspector/tool_inspect_stage.py`` for the full account). Top-level
statements resolve names via LOAD_NAME and are safe; functions defined in the
script would resolve via ``__globals__`` and would not see the script's own
imports. The template below is therefore deliberately FLAT -- no ``def``.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

__all__ = [
    "APPLY_FIXTURE_SCHEMA",
    "REMOVE_FIXTURE_SCHEMA",
    "BlocksToolError",
    "BlocksHoudiniError",
    "apply_fixture",
    "remove_fixture",
]

# Mirrors synapse.blocks.fixtures._VALID_NAME_RE. Duplicated here rather than
# imported so the trust boundary is visible at the point the value is
# interpolated into injected source; tests/test_blocks_seam.py asserts the two
# patterns stay identical.
_VALID_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
_VALID_PATH_RE = re.compile(r"^/[a-zA-Z0-9_][a-zA-Z0-9_/]*$")

DEFAULT_TIMEOUT_SECONDS: float = 60.0
"""Higher than the Inspector's 30s: a cold apply creates and cooks LOP nodes,
where the Inspector only reads."""


class BlocksToolError(RuntimeError):
    """Bad input, transport failure, or an unparseable response."""


class BlocksHoudiniError(BlocksToolError):
    """The reconciler raised inside Houdini. Carries its traceback."""

    def __init__(self, error_type: str, message: str, traceback: str = "") -> None:
        super().__init__("%s: %s" % (error_type, message))
        self.error_type = error_type
        self.message = message
        self.traceback = traceback


_SCRIPT_TEMPLATE = (
    "import json\n"
    "import synapse.blocks.runtime as _syn_blocks_rt\n"
    "try:\n"
    "    _syn_result = _syn_blocks_rt.%(fn)s(%(name)r, stage_path=%(stage)r)\n"
    "except Exception as _syn_exc:\n"
    "    import traceback as _syn_tb\n"
    "    _syn_result = {'synapse_error': type(_syn_exc).__name__,\n"
    "                   'message': str(_syn_exc)[:800],\n"
    "                   'traceback': _syn_tb.format_exc()[:2000]}\n"
    "print(json.dumps(_syn_result, sort_keys=True, default=str))\n"
)


_COMMON_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "fixture": {
            "type": "string",
            "description": (
                "Name of a committed BLOCKS fixture, without the .json "
                "extension - e.g. 'solaris.basic'. Must match "
                "[a-z0-9][a-z0-9_.-]*."
            ),
        },
        "stage_path": {
            "type": "string",
            "description": (
                "Houdini context to reconcile. Defaults to '/stage'."
            ),
        },
        "timeout": {
            "type": "number",
            "description": "Per-call transport timeout in seconds (default 60).",
        },
    },
    "required": ["fixture"],
}

APPLY_FIXTURE_SCHEMA: Dict[str, Any] = {
    "description": (
        "Reconcile a Houdini stage to a committed BLOCKS fixture definition. "
        "Builds the fixture's nodes with exact names, parms, wires, positions "
        "and display flag inside a network box named BLOCKS_<fixture>, which "
        "is what marks them as ours. Idempotent: re-applying an already-"
        "applied fixture performs zero operations. If any fixture node name "
        "already exists outside the box, NOTHING is created or deleted and a "
        "named-collision report comes back instead. Nodes outside the box are "
        "never modified or deleted. A node the artist dragged INTO the box "
        "that the fixture does not declare is EJECTED from the box and left "
        "alive in the stage - never deleted - and is reported by name in "
        "result['ejected']."
    ),
    "input_schema": _COMMON_INPUT_SCHEMA,
}

REMOVE_FIXTURE_SCHEMA: Dict[str, Any] = {
    "description": (
        "Remove a previously applied BLOCKS fixture: deletes the members of "
        "its BLOCKS_<fixture> network box and then the box itself. Nothing "
        "outside the box is touched. Removing a fixture that is not applied "
        "is a no-op reported as status 'absent'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            k: v for k, v in _COMMON_INPUT_SCHEMA["properties"].items()
        },
        "required": ["fixture"],
    },
}


def _validate(fixture: Any, stage_path: Any) -> None:
    if not isinstance(fixture, str) or not _VALID_NAME_RE.match(fixture):
        raise BlocksToolError(
            "fixture name failed validation: %r. Must match "
            "[a-z0-9][a-z0-9_.-]* -- it is interpolated into injected source."
            % (fixture,)
        )
    if ".." in fixture:
        raise BlocksToolError("fixture name may not contain '..': %r" % (fixture,))
    if not isinstance(stage_path, str) or not _VALID_PATH_RE.match(stage_path):
        raise BlocksToolError(
            "stage_path failed validation: %r. Must be absolute and contain "
            "only [a-zA-Z0-9_/]." % (stage_path,)
        )


def _run(fn_name: str, fixture: str, stage_path: str,
         timeout: Optional[float],
         execute_python_fn: Optional[Any]) -> Dict[str, Any]:
    """Compose, ship, parse. The single code path both tools share."""
    _validate(fixture, stage_path)

    from synapse.blocks.transport import get_transport, wrap_script_base64

    transport = execute_python_fn if execute_python_fn is not None else get_transport()
    effective = timeout if timeout is not None else DEFAULT_TIMEOUT_SECONDS

    script = _SCRIPT_TEMPLATE % {
        "fn": fn_name, "name": fixture, "stage": stage_path,
    }
    payload = wrap_script_base64(script)

    try:
        raw = transport(payload, timeout=effective)
    except TypeError as e:
        if "timeout" not in str(e):
            raise
        raw = transport(payload)          # legacy transport without timeout

    if not isinstance(raw, str) or not raw.strip():
        raise BlocksToolError(
            "transport returned %s -- expected the reconciler's JSON on "
            "stdout. An empty response usually means the Houdini process "
            "never ran the script." % (type(raw).__name__,)
        )
    try:
        parsed = json.loads(raw.strip())
    except json.JSONDecodeError as e:
        raise BlocksToolError(
            "reconciler response is not valid JSON: %s at position %d. "
            "Snippet: %r" % (e.msg, e.pos, raw.strip()[:200])
        ) from e
    if not isinstance(parsed, dict):
        raise BlocksToolError(
            "reconciler response root must be an object, got %s"
            % type(parsed).__name__
        )
    if "synapse_error" in parsed:
        raise BlocksHoudiniError(
            parsed.get("synapse_error", "UnknownError"),
            parsed.get("message", ""),
            parsed.get("traceback", ""),
        )
    return parsed


def apply_fixture(
    fixture: str,
    stage_path: str = "/stage",
    *,
    timeout: Optional[float] = None,
    execute_python_fn: Optional[Any] = None,
) -> Dict[str, Any]:
    """Reconcile ``stage_path`` to the named fixture.

    Returns the reconciler's structured result:
    ``{applied, ops, collisions, box, per_node, status, verdict, ...}``.
    A name collision comes back as ``status == "collision"`` with
    ``ops == 0`` -- it is data, not an exception.
    """
    return _run("apply_fixture", fixture, stage_path, timeout, execute_python_fn)


def remove_fixture(
    fixture: str,
    stage_path: str = "/stage",
    *,
    timeout: Optional[float] = None,
    execute_python_fn: Optional[Any] = None,
) -> Dict[str, Any]:
    """Delete the fixture's box members and its box. Nothing else."""
    return _run("remove_fixture", fixture, stage_path, timeout, execute_python_fn)
