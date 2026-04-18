"""SYNAPSE 2.0 Inspector — ``synapse_inspect_stage`` tool.

Extracts the Abstract Syntax Tree (AST) of a Houdini Solaris context
via the WebSocket transport. Returns a validated ``StageAST`` with
query helpers.

Architecture
------------

    Caller
      │
      ▼
    synapse_inspect_stage(target_path)
      │
      ├─ _validate_target_path()    ← input sanitization
      ├─ _build_extraction_payload() ← Base64-wrapped Python
      ├─ transport(payload)          ← single WebSocket call
      │
      ▼
    Houdini 21.0.631 (graphical)
      │
      │ Per-node try/except — partial failures logged, don't abort
      │ Sorted output for determinism
      │ Schema-versioned JSON envelope
      ▼
    raw JSON string
      │
      ├─ _parse_response()            ← JSON decode
      ├─ _check_for_houdini_errors() ← routes to typed exceptions
      ├─ _check_schema_version()     ← version compatibility
      ├─ _build_stage_ast()           ← Pydantic validation
      ▼
    StageAST

Production properties
---------------------
- Input sanitization: target_path matched against regex before dispatch
- Schema versioning: SCHEMA_VERSION envelope prevents silent drift
- Graceful degradation: per-node try/except in extraction script
- Deterministic output: nodes sorted by hou_path, JSON sort_keys=True
- Timeout support: passed through when transport accepts it
- Structured logging: INFO on entry/exit, DEBUG on transport details
- Typed exceptions: consumers route on type, not string message
- No silent failures: every exception path produces a specific error class

API verification
----------------
All Houdini APIs called by the extraction script were verified against
H21.0.631 in Sprint 1 + 2a. See docs/verification_ledger.md.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import re
from typing import Any, Dict, Optional

from synapse.inspector.exceptions import (
    HoudiniExtractionError,
    InvalidTargetPathError,
    SchemaValidationError,
    SchemaVersionMismatchError,
    StageNotFoundError,
    TransportError,
    TransportNotConfiguredError,
    TransportTimeoutError,
)
from synapse.inspector.models import (
    SCHEMA_VERSION,
    ASTNode,
    StageAST,
)
from synapse.inspector.transport import (
    TransportFn,
    configure_transport,
    get_transport,
    wrap_script_base64,
)

logger = logging.getLogger(__name__)

# Env var naming a module that exposes a callable `execute_python` matching
# the Inspector TransportFn contract. Used by _resolve_fallback_transport()
# as a last-resort when no transport was registered via configure_transport()
# and no execute_python_fn was passed explicitly. Opt-in; unset by default.
_ENV_TRANSPORT_MODULE = "SYNAPSE_INSPECTOR_TRANSPORT_MODULE"


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

DEFAULT_TIMEOUT_SECONDS: float = 30.0
"""Default transport timeout. Tunable per-call via ``timeout`` kwarg."""

# Valid Houdini context paths: absolute, slash-separated, alphanumeric
# + underscores + forward slashes only. Rejects quotes, semicolons,
# newlines, unicode, etc. — anything that could escape the repr() in
# the extraction script and enable code injection.
_VALID_PATH_RE = re.compile(r"^/[a-zA-Z0-9_][a-zA-Z0-9_/]*$")


# -----------------------------------------------------------------------------
# The extraction script — runs INSIDE Houdini's Python interpreter.
#
# Design notes:
#   - Each node wrapped in try/except so one bad node doesn't abort the AST
#   - sorted(...) for deterministic node order
#   - sort_keys=True in json.dumps for deterministic key order
#   - String templating with explicit named substitutions, not f-strings,
#     to avoid confusion between Python-side and Houdini-side interpolation
#   - error_message capped at 500 chars to prevent unbounded payload growth
#   - Schema version emitted in envelope for version checking
# -----------------------------------------------------------------------------

_EXTRACTION_SCRIPT_TEMPLATE = '''
import hou
import json
import traceback

SCHEMA_VERSION = "%(schema_version)s"
_MAX_ERR_LEN = 500


def _synapse_extract_node(n):
    """Extract a single node, catching per-field failures gracefully."""
    data = {
        "node_name": n.name(),
        "node_type": n.type().name(),
        "hou_path": n.path(),
        "usd_prim_paths": [],
        "display_flag": False,
        "bypass_flag": False,
        "error_state": "clean",
        "error_message": None,
        "inputs": [],
        "outputs": [],
        "children": [],
        "key_parms": {},
        "provenance": None,
    }
    try:
        # --- Error / warning detection ---
        try:
            errs = n.errors()
            warns = n.warnings()
        except Exception:
            errs, warns = [], []
        if errs:
            data["error_state"] = "error"
            data["error_message"] = str(errs[0])[:_MAX_ERR_LEN]
        elif warns:
            data["error_state"] = "warning"
            data["error_message"] = str(warns[0])[:_MAX_ERR_LEN]

        # --- Flags ---
        try:
            data["display_flag"] = bool(n.isDisplayFlagSet())
        except Exception:
            pass
        try:
            data["bypass_flag"] = bool(n.isBypassed())
        except Exception:
            pass

        # --- USD prims (skip error / bypassed nodes) ---
        if data["error_state"] != "error" and not data["bypass_flag"]:
            try:
                prims = n.lastModifiedPrims()
                data["usd_prim_paths"] = sorted(str(p) for p in prims)
            except Exception:
                pass

        # --- Topology ---
        try:
            inputs_list = []
            for i, inp in enumerate(n.inputs()):
                if inp is not None:
                    inputs_list.append({"index": i, "path": inp.path()})
            data["inputs"] = inputs_list
        except Exception:
            pass
        try:
            outs = [o.path() for o in n.outputs() if o is not None]
            data["outputs"] = sorted(outs)
        except Exception:
            pass

    except Exception as ex:
        # Last-resort per-node catch — record rather than abort
        data["error_state"] = "error"
        data["error_message"] = ("Inspector extraction failed: "
                                 + str(ex)[:_MAX_ERR_LEN - 32])
    return data


def _synapse_extract_flat_ast(target_path):
    parent = hou.node(target_path)
    if parent is None:
        return json.dumps({
            "synapse_error": "stage_not_found",
            "target_path": target_path,
        }, sort_keys=True)
    try:
        children = list(parent.children())
    except Exception as ex:
        return json.dumps({
            "synapse_error": "children_enumeration_failed",
            "target_path": target_path,
            "detail": str(ex)[:500],
        }, sort_keys=True)
    # Deterministic order: sort children by path
    children.sort(key=lambda c: c.path())
    nodes = [_synapse_extract_node(c) for c in children]
    return json.dumps({
        "schema_version": SCHEMA_VERSION,
        "target_path": target_path,
        "nodes": nodes,
    }, sort_keys=True)


try:
    print(_synapse_extract_flat_ast(%(target_path_literal)s))
except Exception as ex:
    print(json.dumps({
        "synapse_error": "extraction_script_crash",
        "detail": str(ex)[:500],
        "traceback": traceback.format_exc()[:2000],
    }, sort_keys=True))
'''


# -----------------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------------


def _validate_target_path(target_path: Any) -> None:
    """Sanity-check the target path before sending to Houdini.

    Blocks trivial injection attempts via path parameter. The regex
    rejects anything that could escape ``repr()`` in the extraction
    script.

    Raises:
        InvalidTargetPathError on any validation failure.
    """
    if not isinstance(target_path, str):
        raise InvalidTargetPathError(
            f"target_path must be str, got {type(target_path).__name__}",
            target_path=target_path,
        )
    if not _VALID_PATH_RE.match(target_path):
        raise InvalidTargetPathError(
            f"target_path failed validation: {target_path!r}. "
            f"Must be absolute and contain only [a-zA-Z0-9_/].",
            target_path=target_path,
        )


def _build_extraction_payload(target_path: str) -> str:
    """Construct the Base64-wrapped extraction script for transport."""
    script = _EXTRACTION_SCRIPT_TEMPLATE % {
        "schema_version": SCHEMA_VERSION,
        # repr() is safe here because target_path passed validation above.
        # Belt-and-suspenders: the regex ensures no quotes or newlines,
        # and repr() would escape them anyway.
        "target_path_literal": repr(target_path),
    }
    return wrap_script_base64(script)


def _parse_response(raw: Any) -> Dict[str, Any]:
    """Parse the JSON response from Houdini.

    Raises:
        SchemaValidationError: non-string input, empty, or invalid JSON.
    """
    if not isinstance(raw, str):
        raise SchemaValidationError(
            f"Transport returned non-string: {type(raw).__name__}"
        )
    raw_stripped = raw.strip()
    if not raw_stripped:
        raise SchemaValidationError("Transport returned empty response")
    try:
        parsed = json.loads(raw_stripped)
    except json.JSONDecodeError as e:
        raise SchemaValidationError(
            f"Response is not valid JSON: {e.msg} at position {e.pos}. "
            f"Response snippet: {raw_stripped[:200]!r}"
        ) from e
    if not isinstance(parsed, dict):
        raise SchemaValidationError(
            f"Response root must be a JSON object, got {type(parsed).__name__}"
        )
    return parsed


def _check_for_houdini_errors(payload: Dict[str, Any], target_path: str) -> None:
    """Route ``synapse_error`` markers to typed exceptions.

    Raises:
        StageNotFoundError: target path doesn't exist in Houdini
        HoudiniExtractionError: Houdini-side error during extraction
    """
    err = payload.get("synapse_error")
    if err is None:
        return

    if err == "stage_not_found":
        raise StageNotFoundError(target_path)

    if err == "children_enumeration_failed":
        raise HoudiniExtractionError(
            f"Failed to enumerate children of {target_path!r}",
            detail=payload.get("detail"),
        )

    if err == "extraction_script_crash":
        raise HoudiniExtractionError(
            "Extraction script crashed in Houdini",
            detail=payload.get("detail"),
            traceback=payload.get("traceback"),
        )

    raise HoudiniExtractionError(
        f"Unknown Houdini error code: {err!r}",
        detail=payload.get("detail"),
    )


def _check_schema_version(payload: Dict[str, Any]) -> str:
    """Verify the response schema version matches this Inspector build.

    Raises:
        SchemaValidationError: version field missing
        SchemaVersionMismatchError: version present but incompatible
    """
    version = payload.get("schema_version")
    if version is None:
        raise SchemaValidationError(
            "Response missing required 'schema_version' field"
        )
    if not isinstance(version, str):
        raise SchemaValidationError(
            f"schema_version must be str, got {type(version).__name__}"
        )
    if version != SCHEMA_VERSION:
        raise SchemaVersionMismatchError(
            expected=SCHEMA_VERSION,
            received=version,
        )
    return version


def _build_stage_ast(payload: Dict[str, Any]) -> StageAST:
    """Build the validated StageAST from a parsed payload.

    Raises:
        SchemaValidationError: nodes field missing, wrong type, or
            individual node fails Pydantic validation.
    """
    raw_nodes = payload.get("nodes")
    if not isinstance(raw_nodes, list):
        raise SchemaValidationError(
            f"Response 'nodes' field must be a list, got "
            f"{type(raw_nodes).__name__}"
        )
    try:
        nodes = [ASTNode(**n) for n in raw_nodes]
    except Exception as e:
        raise SchemaValidationError(
            f"Node schema validation failed: {e}"
        ) from e
    target_path = payload.get("target_path", "/stage")
    return StageAST(
        nodes,
        schema_version=payload["schema_version"],
        target_path=target_path,
    )


def _invoke_transport(
    transport: TransportFn,
    payload_code: str,
    timeout: float,
) -> str:
    """Call the transport, gracefully handling missing timeout support.

    Raises:
        TransportError: transport layer failure
        TransportTimeoutError: timeout exceeded
    """
    try:
        return transport(payload_code, timeout=timeout)
    except TypeError as e:
        # Transport doesn't accept timeout kwarg — legacy signature.
        if "timeout" in str(e):
            logger.debug("Transport does not accept timeout kwarg, falling back")
            return transport(payload_code)
        # TypeError from some other cause — re-raise
        raise
    except (TransportError, TransportTimeoutError):
        raise  # propagate as-is
    except Exception as e:
        # Wrap unknown transport exceptions so callers can catch TransportError
        raise TransportError(
            f"Transport failed: {type(e).__name__}: {e}",
            underlying=e,
        ) from e


def _resolve_fallback_transport() -> Optional[TransportFn]:
    """Attempt to auto-resolve a transport from SYNAPSE_INSPECTOR_TRANSPORT_MODULE.

    Reads the env var naming a dotted module path. The module must expose
    an ``execute_python`` callable matching the Inspector TransportFn
    contract. If the env var is unset, the module can't be imported, or
    the attribute is missing, returns None — the caller re-raises
    TransportNotConfiguredError.

    This is the last-resort "get_transport fallback path" wired into
    ``synapse_inspect_stage``. The explicit ``execute_python_fn`` kwarg
    and prior ``configure_transport()`` still take precedence; this only
    fires when both are absent.
    """
    module_path = os.environ.get(_ENV_TRANSPORT_MODULE, "").strip()
    if not module_path:
        return None
    try:
        mod = importlib.import_module(module_path)
    except ImportError as e:
        logger.warning(
            "Inspector fallback transport: could not import %r: %s",
            module_path,
            e,
        )
        return None
    fn = getattr(mod, "execute_python", None)
    if fn is None or not callable(fn):
        logger.warning(
            "Inspector fallback transport: module %r has no callable "
            "'execute_python' attribute",
            module_path,
        )
        return None
    logger.info(
        "Inspector fallback transport: auto-wired from %s.execute_python",
        module_path,
    )
    resolved: TransportFn = fn
    return resolved


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------


def synapse_inspect_stage(
    target_path: str = "/stage",
    *,
    execute_python_fn: Optional[TransportFn] = None,
    timeout: Optional[float] = None,
) -> StageAST:
    """Extract the flat AST of a Houdini context from a live session.

    This is the MCP tool's core implementation. The MCP wrapper in
    ``mcp_server.py`` serializes the returned StageAST to JSON for
    delivery to Claude.

    Args:
        target_path: The Houdini context to inspect. Defaults to
            ``/stage`` (Solaris). Must match ``/[a-zA-Z0-9_/]+``.
        execute_python_fn: Optional transport function. If None, uses
            the globally configured transport from
            ``configure_transport()``. Tests should pass explicit
            fixtures here rather than mutating global state.
        timeout: Optional timeout in seconds. Defaults to
            ``DEFAULT_TIMEOUT_SECONDS`` (30s). Passed through to the
            transport if the transport supports it.

    Returns:
        StageAST with query helpers (``.by_name()``, ``.display_node()``,
        ``.error_nodes()``, etc.)

    Raises:
        InvalidTargetPathError: target_path failed validation
        TransportNotConfiguredError: no transport registered and none passed
        TransportError: transport layer failure
        TransportTimeoutError: transport timeout exceeded
        StageNotFoundError: target_path doesn't exist in Houdini
        HoudiniExtractionError: Houdini-side script raised
        SchemaValidationError: response didn't match schema
        SchemaVersionMismatchError: schema version incompatible

    Example:
        >>> from synapse.inspector import (
        ...     configure_transport, synapse_inspect_stage,
        ... )
        >>> from synapse.server.websocket import execute_python
        >>> configure_transport(execute_python)
        >>> ast = synapse_inspect_stage()
        >>> print(f"Display node: {ast.display_node().node_name}")
        >>> for err in ast.error_nodes():
        ...     print(f"Error on {err.hou_path}: {err.error_message}")
    """
    _validate_target_path(target_path)

    if execute_python_fn is not None:
        transport = execute_python_fn
    else:
        try:
            transport = get_transport()
        except TransportNotConfiguredError:
            fallback = _resolve_fallback_transport()
            if fallback is None:
                raise
            configure_transport(fallback)
            transport = fallback
    effective_timeout = (
        timeout if timeout is not None else DEFAULT_TIMEOUT_SECONDS
    )

    logger.info(
        "synapse_inspect_stage: target=%s timeout=%s",
        target_path,
        effective_timeout,
    )

    payload_code = _build_extraction_payload(target_path)
    raw_response = _invoke_transport(transport, payload_code, effective_timeout)

    logger.debug(
        "synapse_inspect_stage: received %d chars from transport",
        len(raw_response) if raw_response else 0,
    )

    payload = _parse_response(raw_response)
    _check_for_houdini_errors(payload, target_path)
    _check_schema_version(payload)
    ast = _build_stage_ast(payload)

    logger.info(
        "synapse_inspect_stage: extracted %d nodes "
        "(clean=%d, warning=%d, error=%d)",
        len(ast),
        len(ast.clean_nodes()),
        len(ast.warning_nodes()),
        len(ast.error_nodes()),
    )
    return ast
