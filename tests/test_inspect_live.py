"""SYNAPSE 2.0 Inspector — Live smoke tests.

Requires a running Houdini 21.0.631 graphical session with the SYNAPSE
WebSocket server active on ws://localhost:9999.

Run from a terminal (with Houdini open and server running):
    pytest tests/test_inspect_live.py -v -s -m live

All tests in this module are marked ``live``. By default pytest collects
all tests but skips live ones unless ``-m live`` is passed. This prevents
CI from failing on missing Houdini.

Integration
-----------
Before running, either:

  1. Call ``configure_transport(<your transport>)`` in a conftest, OR
  2. Set SYNAPSE_INSPECTOR_LIVE_TRANSPORT_MODULE env var to the dotted
     import path of your transport module (module must expose an
     ``execute_python`` callable).

If neither is configured, the entire module is skipped with a clear
message — not a collection error.

Fixture path
------------
By default, tests load:
    tests/fixtures/inspector_week1_flat.hip

Override with SYNAPSE_INSPECTOR_FIXTURE_PATH env var if needed.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json as _json
import os
import textwrap
import time as _time
from pathlib import Path
from typing import Callable, Optional

import pytest

from synapse.inspector import (
    ASTNode,
    StageAST,
    configure_transport,
    is_transport_configured,
    synapse_inspect_stage,
)
from synapse.inspector.exceptions import TransportError, TransportTimeoutError

# Apply 'live' marker to every test in this module.
pytestmark = pytest.mark.live


# -----------------------------------------------------------------------------
# Configuration via env vars
# -----------------------------------------------------------------------------

DEFAULT_FIXTURE = (
    Path(__file__).parent / "fixtures" / "inspector_week1_flat.hip"
)

FIXTURE_PATH = Path(
    os.environ.get(
        "SYNAPSE_INSPECTOR_FIXTURE_PATH",
        str(DEFAULT_FIXTURE),
    )
)

TRANSPORT_MODULE = os.environ.get("SYNAPSE_INSPECTOR_LIVE_TRANSPORT_MODULE")

# WebSocket endpoint for the fallback sync transport. Matches mcp_server.py
# defaults and SynapseServer's default bind (9999 / /synapse).
_LIVE_WS_URL = os.environ.get(
    "SYNAPSE_INSPECTOR_LIVE_WS_URL",
    "ws://localhost:9999/synapse",
)
_LIVE_PROTOCOL_VERSION = "5.4.0"


# -----------------------------------------------------------------------------
# Sync→Async bridge transport
# -----------------------------------------------------------------------------


def _wrap_with_stdout_capture(code: str) -> str:
    """Wrap transport-bound code so stdout is captured INSIDE Houdini.

    The Inspector's extraction script emits JSON via ``print(...)``, but the
    server-side ``_handle_execute_python`` returns ``exec_locals.get("result",
    "executed")`` — print() alone would be discarded. We bridge by redirecting
    stdout into a per-call ``io.StringIO`` and binding its contents to
    ``result`` so the response's ``data.result`` field carries the captured
    output.

    Per-call isolation is guaranteed: every wrapped script constructs its own
    ``io.StringIO`` locally inside Houdini. No module-level buffer, no shared
    state, no accumulation across synapse_inspect_stage() invocations.
    """
    indented = textwrap.indent(code, "    ")
    return (
        "import io as _synapse_io\n"
        "import contextlib as _synapse_cl\n"
        "_synapse_buf = _synapse_io.StringIO()\n"
        "with _synapse_cl.redirect_stdout(_synapse_buf):\n"
        f"{indented}\n"
        "result = _synapse_buf.getvalue()"
    )


def _live_execute_python(code: str, *, timeout: Optional[float] = None) -> str:
    """Synchronous SYNAPSE WebSocket transport for the Inspector.

    Contract (``TransportFn``):
        code:    Python source to run in Houdini.
        timeout: Optional per-call timeout in seconds.
        returns: stdout captured during execution (string).

    Implementation:
      - Wraps ``code`` with an isolated per-call stdout capture (see
        ``_wrap_with_stdout_capture``).
      - Opens a short-lived synchronous WebSocket connection to the running
        SYNAPSE server (``_LIVE_WS_URL``, default ws://localhost:9999/synapse).
      - Sends one ``execute_python`` SynapseCommand and reads the response.
      - Maps SYNAPSE wire errors onto the Inspector's typed exceptions.

    Errors:
        TransportTimeoutError   if the WebSocket round-trip exceeds timeout
        TransportError          for connection failure, auth failure, or
                                SynapseResponse.success == False
    """
    try:
        from websockets.sync.client import connect as _ws_connect
    except ImportError as e:
        raise TransportError(
            "websockets package not installed — cannot reach SYNAPSE. "
            "Install with: pip install websockets>=11.0",
            underlying=e,
        ) from e

    wrapped_code = _wrap_with_stdout_capture(code)
    effective_timeout = timeout if timeout is not None else 30.0
    command = {
        "type": "execute_python",
        "id": f"inspector-live-{int(_time.time() * 1000)}",
        "payload": {"content": wrapped_code, "atomic": False},
        "sequence": 0,
        "timestamp": _time.time(),
        "protocol_version": _LIVE_PROTOCOL_VERSION,
    }

    try:
        with _ws_connect(
            _LIVE_WS_URL,
            open_timeout=3.0,
            close_timeout=2.0,
            max_size=None,
        ) as ws:
            ws.send(_json.dumps(command))
            try:
                raw = ws.recv(timeout=effective_timeout)
            except TimeoutError as e:
                raise TransportTimeoutError(
                    f"execute_python exceeded {effective_timeout}s timeout",
                    underlying=e,
                ) from e
    except (TransportError, TransportTimeoutError):
        raise
    except Exception as e:
        raise TransportError(
            f"WebSocket transport to {_LIVE_WS_URL!r} failed: {e}",
            underlying=e,
        ) from e

    try:
        response = _json.loads(raw)
    except Exception as e:
        raise TransportError(
            f"SYNAPSE returned non-JSON response: {raw!r}",
            underlying=e,
        ) from e

    if not response.get("success", False):
        raise TransportError(
            f"SYNAPSE execute_python failed: "
            f"{response.get('error', 'unknown error')}"
        )

    data = response.get("data") or {}
    return data.get("result", "") or ""


# -----------------------------------------------------------------------------
# Transport resolution
# -----------------------------------------------------------------------------


def _resolve_live_transport() -> Optional[Callable]:
    """Return the live transport callable, or None if unavailable.

    Resolution order:
      1. A transport already registered via configure_transport()
      2. Import from SYNAPSE_INSPECTOR_LIVE_TRANSPORT_MODULE env var
      3. Built-in _live_execute_python (sync WebSocket bridge to SYNAPSE
         server at SYNAPSE_INSPECTOR_LIVE_WS_URL, default
         ws://localhost:9999/synapse). Probed with a 0.5s open attempt —
         if Houdini isn't listening, returns None and tests skip cleanly.

    If none succeed, returns None and tests are skipped.
    """
    if is_transport_configured():
        from synapse.inspector import get_transport
        return get_transport()

    if TRANSPORT_MODULE:
        try:
            mod = importlib.import_module(TRANSPORT_MODULE)
        except ImportError as e:
            pytest.skip(
                f"Could not import transport module "
                f"{TRANSPORT_MODULE!r}: {e}"
            )
        if not hasattr(mod, "execute_python"):
            pytest.skip(
                f"Module {TRANSPORT_MODULE!r} has no 'execute_python' "
                f"attribute"
            )
        return mod.execute_python

    # Final fallback: built-in sync WebSocket bridge. Probe first so a missing
    # Houdini server produces a clean skip instead of a hard failure.
    try:
        from websockets.sync.client import connect as _probe_connect
    except ImportError:
        return None
    try:
        with _probe_connect(
            _LIVE_WS_URL, open_timeout=0.5, close_timeout=0.5, max_size=None
        ):
            pass
    except Exception:
        return None
    return _live_execute_python


@pytest.fixture(scope="module")
def live_transport():
    """The live WebSocket transport function.

    Skips the module if no transport is available.
    """
    transport = _resolve_live_transport()
    if transport is None:
        pytest.skip(
            "No live transport configured. Either call "
            "configure_transport(fn) in a conftest before collection, "
            "or set SYNAPSE_INSPECTOR_LIVE_TRANSPORT_MODULE to the "
            "dotted path of a module exposing execute_python()."
        )
    return transport


@pytest.fixture(autouse=True)
def load_fixture(live_transport):
    """Load the golden fixture into the running Houdini session.

    Runs before every test. The fixture file is loaded fresh each time
    so individual tests cannot pollute each other.
    """
    if not FIXTURE_PATH.exists():
        pytest.skip(f"Fixture file not found: {FIXTURE_PATH}")

    hip_path_hou = str(FIXTURE_PATH).replace("\\", "/")
    load_cmd = (
        "import hou; "
        "hou.hipFile.clear(suppress_save_prompt=True); "
        f"hou.hipFile.load('{hip_path_hou}', suppress_save_prompt=True); "
        "print('FIXTURE_LOADED')"
    )

    try:
        result = live_transport(load_cmd)
    except Exception as e:
        pytest.fail(f"Transport failed during fixture load: {e}")

    if "FIXTURE_LOADED" not in (result or ""):
        pytest.fail(
            f"Fixture load did not produce expected marker. "
            f"Transport returned: {result!r}"
        )


# -----------------------------------------------------------------------------
# Live tests
# -----------------------------------------------------------------------------


def test_live_returns_stage_ast(live_transport):
    ast = synapse_inspect_stage(execute_python_fn=live_transport)
    assert isinstance(ast, StageAST)


def test_live_extracts_eight_nodes(live_transport):
    ast = synapse_inspect_stage(execute_python_fn=live_transport)
    assert len(ast) == 8


def test_live_all_nodes_are_astnode_instances(live_transport):
    ast = synapse_inspect_stage(execute_python_fn=live_transport)
    for node in ast:
        assert isinstance(node, ASTNode)


def test_live_error_state_on_reference(live_transport):
    """Reference node with missing file produces error_state."""
    ast = synapse_inspect_stage(execute_python_fn=live_transport)
    assert ast["ref"].error_state == "error"
    assert ast["ref"].usd_prim_paths == []


def test_live_lastmodifiedprims_on_xform(live_transport):
    """Xform correctly reports /geo via lastModifiedPrims()."""
    ast = synapse_inspect_stage(execute_python_fn=live_transport)
    assert ast["xf"].error_state == "clean"
    assert ast["xf"].usd_prim_paths == ["/geo"]


def test_live_merge_indexed_inputs(live_transport):
    """Merge node has three correctly indexed inputs."""
    ast = synapse_inspect_stage(execute_python_fn=live_transport)
    multi = ast["multi"]
    assert len(multi.inputs) == 3
    assert multi.inputs[0].index == 0
    assert multi.inputs[0].path == "/stage/xf"
    assert multi.inputs[1].index == 1
    assert multi.inputs[1].path == "/stage/mats"
    assert multi.inputs[2].index == 2
    assert multi.inputs[2].path == "/stage/ref"


def test_live_bypass_flag(live_transport):
    ast = synapse_inspect_stage(execute_python_fn=live_transport)
    assert ast["bypassed_node"].bypass_flag is True


def test_live_display_flag(live_transport):
    ast = synapse_inspect_stage(execute_python_fn=live_transport)
    display = ast.display_node()
    assert display is not None
    assert display.node_name == "comp"


def test_live_schema_version_matches(live_transport):
    from synapse.inspector.models import SCHEMA_VERSION
    ast = synapse_inspect_stage(execute_python_fn=live_transport)
    assert ast.schema_version == SCHEMA_VERSION


def test_live_determinism_repeated_calls(live_transport):
    """Two calls against the same scene must produce identical JSON."""
    ast1 = synapse_inspect_stage(execute_python_fn=live_transport)
    ast2 = synapse_inspect_stage(execute_python_fn=live_transport)
    assert ast1.to_json() == ast2.to_json()
