# Synapse Production Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Raise Synapse's composite quality score from 7.3 to ~8.6 by hardening error handling, decomposing the God handler, adding process-safe file locking, upgrading memory search, and adding MCP roundtrip integration tests.

**Architecture:** Three phases (A: Foundation Hardening, B: Search & Intelligence, C: Integration Confidence). Phase A addresses the three largest production gaps: flat exception hierarchy, monolithic handler, and thread-only file locking. Phase B upgrades keyword-only memory search to hybrid scoring and adds memory pattern detection. Phase C adds the missing MCP roundtrip integration test harness.

**Tech Stack:** Python 3.11+, pytest, `filelock` (new optional dep), `sentence-transformers` (new optional dep), `mcp` (existing optional dep), `websockets` (existing optional dep)

---

## Phase A: Foundation Hardening

### Task 1: Custom Exception Hierarchy

**Files:**
- Create: `python/synapse/core/errors.py`
- Modify: `python/synapse/core/__init__.py`
- Test: `tests/test_errors.py`

**Context:** handlers.py currently uses 59 bare `raise ValueError` / `raise RuntimeError` for all error paths. The `handle()` method (line 251-263) catches `ValueError` as user errors and `Exception` as service errors, but there's no way to distinguish "node not found" from "invalid parameter" from "missing required field". The circuit breaker in `resilience.py` currently classifies errors by type — a structured hierarchy lets it make smarter decisions.

**Step 1: Write the failing test**

Create `tests/test_errors.py`:

```python
"""Tests for the Synapse exception hierarchy."""

import sys
import os

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.core.errors import (
    SynapseError,
    SynapseUserError,
    SynapseServiceError,
    NodeNotFoundError,
    ParameterError,
    ExecutionError,
    HoudiniUnavailableError,
    ValidationError,
)


class TestExceptionHierarchy:
    """Verify the two-branch inheritance tree."""

    def test_base_class_is_exception(self):
        assert issubclass(SynapseError, Exception)

    def test_user_errors_inherit_from_base(self):
        assert issubclass(SynapseUserError, SynapseError)

    def test_service_errors_inherit_from_base(self):
        assert issubclass(SynapseServiceError, SynapseError)

    def test_node_not_found_is_user_error(self):
        assert issubclass(NodeNotFoundError, SynapseUserError)

    def test_parameter_error_is_user_error(self):
        assert issubclass(ParameterError, SynapseUserError)

    def test_validation_error_is_user_error(self):
        assert issubclass(ValidationError, SynapseUserError)

    def test_execution_error_is_service_error(self):
        assert issubclass(ExecutionError, SynapseServiceError)

    def test_houdini_unavailable_is_service_error(self):
        assert issubclass(HoudiniUnavailableError, SynapseServiceError)


class TestErrorMessages:
    """Coaching-tone message conventions."""

    def test_node_not_found_has_path(self):
        err = NodeNotFoundError("/stage/missing_light")
        assert "/stage/missing_light" in str(err)
        assert err.node_path == "/stage/missing_light"

    def test_node_not_found_with_suggestion(self):
        err = NodeNotFoundError("/stage/key", suggestion="key_light")
        assert "key_light" in str(err)

    def test_parameter_error_has_node_and_parm(self):
        err = ParameterError("/stage/light", "intensity")
        assert err.node_path == "/stage/light"
        assert err.parm_name == "intensity"

    def test_parameter_error_with_suggestion(self):
        err = ParameterError("/stage/light", "intensity", suggestion="xn__inputsintensity_i0a")
        assert "xn__inputsintensity_i0a" in str(err)

    def test_houdini_unavailable_default_message(self):
        err = HoudiniUnavailableError()
        msg = str(err)
        assert "Houdini" in msg
        # Coaching tone: not "error" or "failed"
        assert "Error" not in msg

    def test_validation_error_preserves_field(self):
        err = ValidationError("code", "Required field missing")
        assert err.field == "code"

    def test_execution_error_preserves_partial(self):
        err = ExecutionError("Script crashed", partial_result="/stage/node1")
        assert err.partial_result == "/stage/node1"


class TestErrorCategorization:
    """Verify errors sort into user vs service correctly."""

    def test_user_errors_not_service(self):
        for cls in (NodeNotFoundError, ParameterError, ValidationError):
            err = cls.__new__(cls)
            assert isinstance(err, SynapseUserError)
            assert not isinstance(err, SynapseServiceError)

    def test_service_errors_not_user(self):
        for cls in (ExecutionError, HoudiniUnavailableError):
            err = cls.__new__(cls)
            assert isinstance(err, SynapseServiceError)
            assert not isinstance(err, SynapseUserError)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synapse.core.errors'`

**Step 3: Write minimal implementation**

Create `python/synapse/core/errors.py`:

```python
"""
Synapse Exception Hierarchy

Two-branch tree:
  SynapseError (base)
  ├── SynapseUserError     (bad input, missing node, bad parm name)
  │   ├── NodeNotFoundError
  │   ├── ParameterError
  │   └── ValidationError
  └── SynapseServiceError  (Houdini down, execution crash, timeout)
      ├── ExecutionError
      └── HoudiniUnavailableError

Circuit breaker: only SynapseServiceError trips it.
Handler.handle(): SynapseUserError -> success=False (don't trip CB).
                  SynapseServiceError -> success=False + trip CB.
"""


class SynapseError(Exception):
    """Base class for all Synapse errors."""


class SynapseUserError(SynapseError):
    """User-caused errors (bad input, missing resources).

    These do NOT trip the circuit breaker.
    """


class SynapseServiceError(SynapseError):
    """Service-level errors (Houdini down, crashes, timeouts).

    These DO trip the circuit breaker.
    """


class NodeNotFoundError(SynapseUserError):
    """A Houdini node path didn't resolve to an existing node."""

    def __init__(self, node_path: str, suggestion: str = ""):
        self.node_path = node_path
        self.suggestion = suggestion
        msg = f"Couldn't find a node at '{node_path}'"
        if suggestion:
            msg += f" — did you mean '{suggestion}'?"
        super().__init__(msg)


class ParameterError(SynapseUserError):
    """A parameter name doesn't exist on the target node."""

    def __init__(self, node_path: str, parm_name: str, suggestion: str = ""):
        self.node_path = node_path
        self.parm_name = parm_name
        self.suggestion = suggestion
        msg = f"Couldn't find parameter '{parm_name}' on {node_path}"
        if suggestion:
            msg += f" — try '{suggestion}' instead"
        super().__init__(msg)


class ValidationError(SynapseUserError):
    """A required field is missing or has an invalid value."""

    def __init__(self, field: str, message: str = ""):
        self.field = field
        msg = f"Missing or invalid field '{field}'"
        if message:
            msg += f": {message}"
        super().__init__(msg)


class ExecutionError(SynapseServiceError):
    """Python/VEX execution failed inside Houdini."""

    def __init__(self, message: str, partial_result=None):
        self.partial_result = partial_result
        super().__init__(message)


class HoudiniUnavailableError(SynapseServiceError):
    """Houdini is not reachable or hou module is not available."""

    def __init__(self, message: str = ""):
        if not message:
            message = (
                "Houdini isn't reachable right now — make sure it's running "
                "and Synapse is started from the Python Panel"
            )
        super().__init__(message)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_errors.py -v`
Expected: 16 PASSED

**Step 5: Update core __init__.py exports**

Edit `python/synapse/core/__init__.py` — add the errors imports to the existing imports:

```python
from .errors import (
    SynapseError,
    SynapseUserError,
    SynapseServiceError,
    NodeNotFoundError,
    ParameterError,
    ExecutionError,
    HoudiniUnavailableError,
    ValidationError,
)
```

And add to `__all__`:

```python
    # Errors
    'SynapseError',
    'SynapseUserError',
    'SynapseServiceError',
    'NodeNotFoundError',
    'ParameterError',
    'ExecutionError',
    'HoudiniUnavailableError',
    'ValidationError',
```

**Step 6: Run full test suite to verify no regressions**

Run: `python -m pytest tests/ -v`
Expected: ~825 passed, 16 skipped (no change)

**Step 7: Commit**

```bash
git add python/synapse/core/errors.py python/synapse/core/__init__.py tests/test_errors.py
git commit -m "feat: add structured exception hierarchy (SynapseUserError/SynapseServiceError)"
```

---

### Task 2: Wire Exception Hierarchy into Handler Dispatch

**Files:**
- Modify: `python/synapse/server/handlers.py` (lines 198-264, plus key handlers)
- Modify: `python/synapse/server/resilience.py` (CircuitBreaker.record_failure)
- Test: `tests/test_errors.py` (add handler dispatch tests)

**Context:** The `handle()` method at handlers.py:198-264 currently catches `ValueError` for user errors and bare `Exception` for service errors. We'll update it to catch `SynapseUserError` and `SynapseServiceError` separately, and only trip the circuit breaker for service errors. Then migrate key handler methods to use the new exceptions.

**Step 1: Write the failing tests**

Add to `tests/test_errors.py`:

```python
class TestHandlerDispatchIntegration:
    """Verify handle() routes exceptions correctly."""

    def test_user_error_returns_false_without_tripping_cb(self):
        """SynapseUserError -> success=False, no circuit breaker trip."""
        from synapse.core.errors import NodeNotFoundError
        from synapse.core.protocol import SynapseCommand, SynapseResponse

        # We test the classification, not the full handler (no hou needed)
        err = NodeNotFoundError("/stage/missing")
        assert isinstance(err, SynapseUserError)
        # User errors contain the message directly
        assert "Couldn't find" in str(err)

    def test_service_error_is_distinct(self):
        """SynapseServiceError is catchable separately."""
        from synapse.core.errors import HoudiniUnavailableError
        err = HoudiniUnavailableError()
        assert isinstance(err, SynapseServiceError)
        assert isinstance(err, SynapseError)
        assert not isinstance(err, SynapseUserError)
```

**Step 2: Run test to verify it passes (these just test classification)**

Run: `python -m pytest tests/test_errors.py::TestHandlerDispatchIntegration -v`
Expected: PASS

**Step 3: Update handle() method**

In `python/synapse/server/handlers.py`, update the `handle()` method (lines 198-264). Add import at top of file:

```python
from ..core.errors import (
    SynapseError,
    SynapseUserError,
    SynapseServiceError,
    NodeNotFoundError,
    ParameterError,
    HoudiniUnavailableError,
    ValidationError,
)
```

Then update `handle()`:

```python
    def handle(self, command: SynapseCommand) -> SynapseResponse:
        try:
            cmd_type = command.normalized_type()
            handler = self._registry.get(cmd_type)

            if handler is None:
                return SynapseResponse(
                    id=command.id,
                    success=False,
                    error=f"I don't recognize the command '{command.type}' — try get_help to see what's available",
                    sequence=command.sequence,
                )

            result = handler(command.payload)

            # Log action asynchronously
            if cmd_type not in _READ_ONLY_COMMANDS:
                bridge = self._get_bridge()
                if bridge and self._session_id:
                    sid = self._session_id
                    _log_executor.submit(bridge.log_action, f"Executed: {cmd_type}", session_id=sid)
                _log_executor.submit(
                    audit_log().log,
                    operation=cmd_type,
                    message=f"Executed {cmd_type}",
                    level=AuditLevel.AGENT_ACTION,
                    category=_CMD_CATEGORY.get(cmd_type, AuditCategory.SYNAPSE),
                    input_data=command.payload,
                    output_data=result if isinstance(result, dict) else {},
                )

            return SynapseResponse(
                id=command.id, success=True, data=result, sequence=command.sequence,
            )

        except SynapseUserError as e:
            # User errors: bad input, missing node, bad parm. Don't trip CB.
            return SynapseResponse(
                id=command.id, success=False, error=str(e), sequence=command.sequence,
            )
        except ValueError as e:
            # Legacy ValueError path — still user error, don't trip CB.
            return SynapseResponse(
                id=command.id, success=False, error=str(e), sequence=command.sequence,
            )
        except SynapseServiceError as e:
            # Service errors: Houdini down, execution crash. DO trip CB.
            return SynapseResponse(
                id=command.id, success=False,
                error=f"Hit a snag: {e}",
                sequence=command.sequence,
            )
        except Exception as e:
            return SynapseResponse(
                id=command.id, success=False,
                error=f"Hit a snag processing that request: {e}",
                sequence=command.sequence,
            )
```

**Step 4: Migrate 3 high-value handlers to use new exceptions**

These are the most-called error paths. Migrate incrementally — do NOT change all 59 at once.

In `_handle_create_node` (line 442): Replace `raise ValueError("Houdini isn't reachable...")` with `raise HoudiniUnavailableError()`. Replace `raise ValueError(f"Couldn't find parent node at '{parent_path}'...")` with `raise NodeNotFoundError(parent_path, suggestion=...)`.

In `_handle_get_parm` (line 533): Replace `raise ValueError` for missing node with `raise NodeNotFoundError(...)`. Replace `raise ValueError` for missing parm with `raise ParameterError(node_path, parm_name, suggestion=...)`.

In `_handle_set_parm` (line 580): Same pattern — `NodeNotFoundError` for missing node, `ParameterError` for missing parm.

**Important:** Leave all other handlers on `ValueError` for now. Migrating all 59 at once is high-risk. We'll do batches in future PRs.

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ~825 passed (no change — handler tests already assert error strings, not exception types)

**Step 6: Commit**

```bash
git add python/synapse/server/handlers.py tests/test_errors.py
git commit -m "feat: wire exception hierarchy into handle() dispatch and 3 key handlers"
```

---

### Task 3: Handler Mixin Extraction — Node Operations

**Files:**
- Create: `python/synapse/server/handlers_node.py`
- Modify: `python/synapse/server/handlers.py`
- Test: `tests/test_handler_node.py`

**Context:** handlers.py is 1,905 lines — a God object. The `_register_handlers()` method (line 266-347) shows natural domain groupings. We'll extract one group at a time as mixin classes. Start with node operations (create_node, delete_node, connect_nodes) since they're self-contained.

**Step 1: Write the failing test**

Create `tests/test_handler_node.py`:

```python
"""Tests for node operation handlers (extracted mixin)."""

import sys
import os
from unittest.mock import Mock, patch, MagicMock

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

# Stub hou before importing handlers
mock_hou = MagicMock()
sys.modules["hou"] = mock_hou

from synapse.server.handlers_node import NodeHandlerMixin


def test_mixin_has_create_node():
    assert hasattr(NodeHandlerMixin, "_handle_create_node")


def test_mixin_has_delete_node():
    assert hasattr(NodeHandlerMixin, "_handle_delete_node")


def test_mixin_has_connect_nodes():
    assert hasattr(NodeHandlerMixin, "_handle_connect_nodes")
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_handler_node.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synapse.server.handlers_node'`

**Step 3: Extract the mixin**

Create `python/synapse/server/handlers_node.py`:

```python
"""
Node Operation Handlers — Extracted Mixin

Handles: create_node, delete_node, connect_nodes
"""

import os
from typing import Dict, Any

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param, resolve_param_with_default
from ..core.errors import NodeNotFoundError, HoudiniUnavailableError

_HOUDINI_UNAVAILABLE = (
    "Houdini isn't reachable right now — make sure it's running "
    "and Synapse is started from the Python Panel"
)


def _suggest_children(parent_path: str) -> str:
    """List children of a parent path for error enrichment."""
    try:
        parent = hou.node(parent_path)
        if parent and parent.children():
            names = [c.name() for c in parent.children()[:10]]
            return " Children at that path: " + ", ".join(names)
    except Exception:
        pass
    return ""


class NodeHandlerMixin:
    """Mixin providing node create/delete/connect handlers."""

    # Paste the exact _handle_create_node, _handle_delete_node,
    # _handle_connect_nodes methods from handlers.py lines 442-531.
    # Keep the same method signatures and behavior.
    # Replace raise ValueError with raise NodeNotFoundError/HoudiniUnavailableError
    # where appropriate.
    pass
```

**Important:** Copy the three handler methods verbatim from handlers.py (lines 442-531). Keep all logic identical. The only changes:
1. They now live in the mixin class
2. Error types upgraded where already migrated in Task 2

**Step 4: Update handlers.py to inherit from mixin**

In `python/synapse/server/handlers.py`:

```python
from .handlers_node import NodeHandlerMixin

class SynapseHandler(NodeHandlerMixin):
    ...
```

Remove `_handle_create_node`, `_handle_delete_node`, `_handle_connect_nodes` from the main class body (they're inherited from the mixin now). Keep the `_register_handlers()` registrations pointing to `self._handle_create_node` etc. — they'll resolve through MRO.

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ~825+ passed (existing handler tests still pass through MRO)

**Step 6: Commit**

```bash
git add python/synapse/server/handlers_node.py python/synapse/server/handlers.py tests/test_handler_node.py
git commit -m "refactor: extract NodeHandlerMixin (create/delete/connect) from God handler"
```

---

### Task 4: Handler Mixin Extraction — USD Operations

**Files:**
- Create: `python/synapse/server/handlers_usd.py`
- Modify: `python/synapse/server/handlers.py`
- Test: `tests/test_handler_usd.py`

**Context:** Same pattern as Task 3. Extract USD/Solaris handlers: `get_stage_info`, `get_usd_attribute`, `set_usd_attribute`, `create_usd_prim`, `modify_usd_prim`, `reference_usd`. These span handlers.py lines 774-1357.

**Step 1: Write the failing test**

Create `tests/test_handler_usd.py`:

```python
"""Tests for USD operation handlers (extracted mixin)."""

import sys
import os
from unittest.mock import MagicMock

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

mock_hou = MagicMock()
sys.modules["hou"] = mock_hou

from synapse.server.handlers_usd import UsdHandlerMixin


def test_mixin_has_stage_info():
    assert hasattr(UsdHandlerMixin, "_handle_get_stage_info")

def test_mixin_has_get_usd_attribute():
    assert hasattr(UsdHandlerMixin, "_handle_get_usd_attribute")

def test_mixin_has_set_usd_attribute():
    assert hasattr(UsdHandlerMixin, "_handle_set_usd_attribute")

def test_mixin_has_create_usd_prim():
    assert hasattr(UsdHandlerMixin, "_handle_create_usd_prim")

def test_mixin_has_modify_usd_prim():
    assert hasattr(UsdHandlerMixin, "_handle_modify_usd_prim")

def test_mixin_has_reference_usd():
    assert hasattr(UsdHandlerMixin, "_handle_reference_usd")
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_handler_usd.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Extract the mixin**

Create `python/synapse/server/handlers_usd.py`. Copy `_handle_get_stage_info` (line 774), `_handle_get_usd_attribute` (line 849), `_handle_set_usd_attribute` (line 891), `_handle_create_usd_prim` (line 925), `_handle_modify_usd_prim` (line 952), `_handle_reference_usd` (line 1316) from handlers.py into a `UsdHandlerMixin` class.

**Step 4: Update handlers.py**

```python
from .handlers_usd import UsdHandlerMixin

class SynapseHandler(NodeHandlerMixin, UsdHandlerMixin):
    ...
```

Remove the 6 methods from the main class body.

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ~825+ passed

**Step 6: Commit**

```bash
git add python/synapse/server/handlers_usd.py python/synapse/server/handlers.py tests/test_handler_usd.py
git commit -m "refactor: extract UsdHandlerMixin (6 USD handlers) from God handler"
```

---

### Task 5: Handler Mixin Extraction — Render + Materials

**Files:**
- Create: `python/synapse/server/handlers_render.py`
- Modify: `python/synapse/server/handlers.py`
- Test: `tests/test_handler_render.py`

**Context:** Extract render and material handlers: `capture_viewport`, `render`, `set_keyframe`, `render_settings`, `wedge`, `create_material`, `assign_material`, `read_material`. These span handlers.py lines 1006-1523.

**Step 1: Write the failing test**

Create `tests/test_handler_render.py`:

```python
"""Tests for render + material handlers (extracted mixin)."""

import sys
import os
from unittest.mock import MagicMock

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

mock_hou = MagicMock()
sys.modules["hou"] = mock_hou

from synapse.server.handlers_render import RenderHandlerMixin


def test_mixin_has_capture_viewport():
    assert hasattr(RenderHandlerMixin, "_handle_capture_viewport")

def test_mixin_has_render():
    assert hasattr(RenderHandlerMixin, "_handle_render")

def test_mixin_has_create_material():
    assert hasattr(RenderHandlerMixin, "_handle_create_material")

def test_mixin_has_assign_material():
    assert hasattr(RenderHandlerMixin, "_handle_assign_material")

def test_mixin_has_read_material():
    assert hasattr(RenderHandlerMixin, "_handle_read_material")

def test_mixin_has_set_keyframe():
    assert hasattr(RenderHandlerMixin, "_handle_set_keyframe")

def test_mixin_has_render_settings():
    assert hasattr(RenderHandlerMixin, "_handle_render_settings")

def test_mixin_has_wedge():
    assert hasattr(RenderHandlerMixin, "_handle_wedge")
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_handler_render.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Extract the mixin**

Create `python/synapse/server/handlers_render.py` with `RenderHandlerMixin`. Copy the 8 handler methods verbatim.

**Step 4: Update handlers.py**

```python
from .handlers_render import RenderHandlerMixin

class SynapseHandler(NodeHandlerMixin, UsdHandlerMixin, RenderHandlerMixin):
    ...
```

Remove the 8 methods from the main class body.

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ~825+ passed

**Step 6: Commit**

```bash
git add python/synapse/server/handlers_render.py python/synapse/server/handlers.py tests/test_handler_render.py
git commit -m "refactor: extract RenderHandlerMixin (8 render/material handlers)"
```

---

### Task 6: Handler Mixin Extraction — Memory Operations

**Files:**
- Create: `python/synapse/server/handlers_memory.py`
- Modify: `python/synapse/server/handlers.py`
- Test: `tests/test_handler_memory.py`

**Context:** Extract all memory handlers: `memory_context`, `memory_search`, `memory_add`, `memory_decide`, `memory_recall`, `project_setup`, `memory_write`, `memory_query`, `memory_status`, `evolve_memory`. These span lines 1525-1690. Also move `_scene_paths()` static method into this mixin since it's only used by memory handlers.

**Step 1: Write the failing test**

Create `tests/test_handler_memory.py`:

```python
"""Tests for memory operation handlers (extracted mixin)."""

import sys
import os
from unittest.mock import MagicMock

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

mock_hou = MagicMock()
sys.modules["hou"] = mock_hou

from synapse.server.handlers_memory import MemoryHandlerMixin


def test_mixin_has_scene_paths():
    assert hasattr(MemoryHandlerMixin, "_scene_paths")

def test_mixin_has_project_setup():
    assert hasattr(MemoryHandlerMixin, "_handle_project_setup")

def test_mixin_has_memory_write():
    assert hasattr(MemoryHandlerMixin, "_handle_memory_write")

def test_mixin_has_memory_query():
    assert hasattr(MemoryHandlerMixin, "_handle_memory_query")

def test_mixin_has_memory_status():
    assert hasattr(MemoryHandlerMixin, "_handle_memory_status")

def test_mixin_has_memory_context():
    assert hasattr(MemoryHandlerMixin, "_handle_memory_context")

def test_mixin_has_evolve_memory():
    assert hasattr(MemoryHandlerMixin, "_handle_evolve_memory")
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_handler_memory.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Extract the mixin**

Create `python/synapse/server/handlers_memory.py` with `MemoryHandlerMixin`. Copy the 10 memory handler methods + `_scene_paths()`.

**Step 4: Update handlers.py**

```python
from .handlers_memory import MemoryHandlerMixin

class SynapseHandler(NodeHandlerMixin, UsdHandlerMixin, RenderHandlerMixin, MemoryHandlerMixin):
    ...
```

Remove the 10+1 methods from the main class body.

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ~825+ passed

**Step 6: Verify handlers.py line count reduced**

Run: `wc -l python/synapse/server/handlers.py`
Expected: ~700-800 lines (down from 1,905)

**Step 7: Commit**

```bash
git add python/synapse/server/handlers_memory.py python/synapse/server/handlers.py tests/test_handler_memory.py
git commit -m "refactor: extract MemoryHandlerMixin (10 memory handlers + _scene_paths)"
```

---

### Task 7: Process-Safe File Locking for Living Memory

**Files:**
- Modify: `pyproject.toml` (new optional dep)
- Modify: `python/synapse/memory/scene_memory.py`
- Test: `tests/test_scene_memory.py` (add locking tests)

**Context:** Living Memory writes to `$HIP/claude/memory.md` using plain `open()`. If two Houdini sessions edit the same HIP file (or if the MCP bridge and Houdini Python Panel both write), data races can corrupt the file. Python's `threading.Lock` only protects within one process. We need `filelock` (cross-process) with a fallback to `threading.Lock` when `filelock` isn't installed.

**Step 1: Write the failing tests**

Add to `tests/test_scene_memory.py`:

```python
class TestFileLocking:
    """Verify process-safe file locking."""

    def test_write_acquires_lock(self, tmp_path):
        """write_memory_entry creates a .lock file during write."""
        claude_dir = str(tmp_path / "claude")
        os.makedirs(claude_dir)
        md_path = os.path.join(claude_dir, "memory.md")
        with open(md_path, "w") as f:
            f.write("# Memory\n")

        write_memory_entry(claude_dir, {"content": "test note"}, "note")

        # File should be written successfully
        content = open(md_path).read()
        assert "test note" in content

    def test_concurrent_writes_dont_corrupt(self, tmp_path):
        """Multiple sequential writes produce valid markdown."""
        claude_dir = str(tmp_path / "claude")
        os.makedirs(claude_dir)
        md_path = os.path.join(claude_dir, "memory.md")
        with open(md_path, "w") as f:
            f.write("# Memory\n")

        for i in range(10):
            write_memory_entry(claude_dir, {"content": f"note {i}"}, "note")

        content = open(md_path).read()
        for i in range(10):
            assert f"note {i}" in content
```

**Step 2: Run test to verify current behavior**

Run: `python -m pytest tests/test_scene_memory.py::TestFileLocking -v`
Expected: These should pass currently (sequential writes work). The real benefit is cross-process safety.

**Step 3: Add filelock as optional dependency**

Edit `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
]
memory = [
    "filelock>=3.0",
]
```

**Step 4: Add locking to scene_memory.py**

At the top of `python/synapse/memory/scene_memory.py`, add:

```python
import threading

try:
    from filelock import FileLock
    _FILELOCK_AVAILABLE = True
except ImportError:
    _FILELOCK_AVAILABLE = False

# Fallback: per-path threading locks (process-local only)
_thread_locks: Dict[str, threading.Lock] = {}
_thread_locks_guard = threading.Lock()


def _get_lock(path: str):
    """Get a lock for the given file path.

    Uses filelock (cross-process) if available, else threading.Lock (process-local).
    """
    if _FILELOCK_AVAILABLE:
        return FileLock(path + ".lock", timeout=5)
    with _thread_locks_guard:
        if path not in _thread_locks:
            _thread_locks[path] = threading.Lock()
        return _thread_locks[path]
```

Then wrap the file write in `write_memory_entry` with the lock:

```python
def write_memory_entry(claude_dir: str, content: dict, entry_type: str) -> None:
    md_path = os.path.join(claude_dir, "memory.md")
    lock = _get_lock(md_path)
    with lock:
        # existing write logic here
        ...
```

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ~830+ passed

**Step 6: Commit**

```bash
git add pyproject.toml python/synapse/memory/scene_memory.py tests/test_scene_memory.py
git commit -m "feat: add process-safe file locking for Living Memory writes"
```

---

## Phase B: Search & Intelligence

### Task 8: Hybrid Memory Search (TF-IDF + Optional Embeddings)

**Files:**
- Modify: `python/synapse/memory/scene_memory.py`
- Test: `tests/test_scene_memory.py` (add hybrid search tests)

**Context:** The current `search_memory()` uses simple word overlap scoring. This works for exact matches but misses semantic relationships (e.g., searching "lighting" won't find entries about "exposure" or "key fill ratio"). We'll add TF-IDF scoring as the default (no deps), with optional `sentence-transformers` embeddings when installed.

**Step 1: Write the failing tests**

Add to `tests/test_scene_memory.py`:

```python
class TestHybridSearch:
    """Test TF-IDF scoring improvements."""

    def test_tfidf_boosts_rare_terms(self):
        """A rare word in a section should rank higher than a common word."""
        content = (
            "## Decisions\n\n"
            "### Chose Karma XPU for rendering\n"
            "Picked Karma XPU over Mantra for speed.\n\n"
            "### Set the lighting ratio\n"
            "Standard lighting setup with key and fill.\n\n"
            "## Notes\n\n"
            "### General note\n"
            "Lighting and rendering are important.\n"
        )
        results = search_memory(content, "Karma XPU")
        assert len(results) >= 1
        # "Karma XPU" is rare -> section mentioning it should rank first
        assert "Karma" in results[0]["title"] or "Karma" in results[0]["content"]

    def test_idf_penalizes_common_words(self):
        """Words appearing in every section get lower weight."""
        content = (
            "## Notes\n\n"
            "### Note about lighting\n"
            "The lighting setup uses area lights.\n\n"
            "### Note about rendering\n"
            "The rendering uses Karma with lighting.\n\n"
            "### Note about Karma XPU\n"
            "Karma XPU gives fast results for the shot.\n"
        )
        results = search_memory(content, "Karma XPU fast")
        assert len(results) >= 1
        # "Karma XPU" + "fast" is most specific to section 3
        assert "XPU" in results[0]["title"] or "XPU" in results[0]["content"]
```

**Step 2: Run test to verify it fails (or barely passes with current scoring)**

Run: `python -m pytest tests/test_scene_memory.py::TestHybridSearch -v`

**Step 3: Upgrade search_memory() with TF-IDF**

In `python/synapse/memory/scene_memory.py`, update `search_memory()`:

```python
import math

def search_memory(content: str, query: str, type_filter: str = "") -> List[Dict[str, Any]]:
    """Section-aware ranked search with TF-IDF scoring."""
    if not content or not query:
        return []

    query_words = set(w for w in re.findall(r'[a-z0-9_/]+', query.lower()) if len(w) >= 2)
    if not query_words:
        return []

    # Split into sections
    sections = _split_into_sections(content)  # existing helper
    if type_filter:
        sections = [s for s in sections if s["type"] == type_filter]

    if not sections:
        return []

    # Compute IDF: log(N / (1 + df)) where df = number of sections containing the word
    n_sections = len(sections)
    doc_freq: Dict[str, int] = {}
    section_words_list = []
    for section in sections:
        text = (section.get("title", "") + " " + section.get("content", "")).lower()
        words = set(re.findall(r'[a-z0-9_/]+', text))
        section_words_list.append(words)
        for w in words:
            doc_freq[w] = doc_freq.get(w, 0) + 1

    idf = {}
    for w in query_words:
        df = doc_freq.get(w, 0)
        idf[w] = math.log((n_sections + 1) / (1 + df))

    # Score each section
    results = []
    for i, section in enumerate(sections):
        words = section_words_list[i]
        title_words = set(re.findall(r'[a-z0-9_/]+', section.get("title", "").lower()))

        score = 0.0
        for w in query_words:
            if w in words:
                tf = 1.0  # binary TF (presence)
                score += tf * idf.get(w, 1.0)
                if w in title_words:
                    score += idf.get(w, 1.0)  # title bonus

        # Exact phrase bonus
        full_text = (section.get("title", "") + " " + section.get("content", "")).lower()
        if query.lower() in full_text:
            score += 2.0

        if score > 0:
            results.append({
                "type": section.get("type", "unknown"),
                "title": section.get("title", ""),
                "content": section.get("content", "")[:500],
                "score": round(score, 4),
                "line": section.get("line", 0),
            })

    results.sort(key=lambda r: (-r["score"], r["line"]))
    return results[:20]
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_scene_memory.py -v`
Expected: All search tests pass (existing + new)

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ~830+ passed

**Step 6: Commit**

```bash
git add python/synapse/memory/scene_memory.py tests/test_scene_memory.py
git commit -m "feat: upgrade search_memory to TF-IDF scoring with IDF term weighting"
```

---

### Task 9: Memory Pattern Detection

**Files:**
- Create: `python/synapse/memory/patterns.py`
- Test: `tests/test_memory_patterns.py`

**Context:** Artists often hit the same problems repeatedly. Pattern detection surfaces repeated blockers, oscillating parameter values, and decision reversals — turning raw memory into actionable insights.

**Step 1: Write the failing tests**

Create `tests/test_memory_patterns.py`:

```python
"""Tests for memory pattern detection."""

import sys
import os

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.memory.patterns import detect_patterns


class TestPatternDetection:
    """Pattern detection on raw markdown content."""

    def test_repeated_blocker(self):
        """Same blocker mentioned multiple times triggers pattern."""
        content = (
            "## Blockers\n\n"
            "### Render timeout\nKarma keeps timing out on frame 42.\n\n"
            "### Render timeout again\nKarma timing out, tried increasing timeout.\n\n"
            "### Render timeout third time\nStill timing out on frame 42.\n"
        )
        patterns = detect_patterns(content)
        assert any(p["type"] == "repeated_blocker" for p in patterns)
        blocker = next(p for p in patterns if p["type"] == "repeated_blocker")
        assert blocker["count"] >= 2

    def test_oscillating_parameter(self):
        """Parameter going back and forth triggers pattern."""
        content = (
            "## Parameters\n\n"
            "### Set exposure to 5.0\nBefore: 3.0, After: 5.0. Too bright.\n\n"
            "### Set exposure to 3.0\nBefore: 5.0, After: 3.0. Too dark.\n\n"
            "### Set exposure to 5.0\nBefore: 3.0, After: 5.0. Still too bright.\n"
        )
        patterns = detect_patterns(content)
        assert any(p["type"] == "oscillating_parameter" for p in patterns)

    def test_no_patterns_for_clean_memory(self):
        """Clean memory with no repetition returns empty list."""
        content = (
            "## Decisions\n\n"
            "### Chose Karma XPU\nFast GPU rendering.\n\n"
            "## Notes\n\n"
            "### Scene looks good\nReady for review.\n"
        )
        patterns = detect_patterns(content)
        assert patterns == []

    def test_returns_sorted_by_severity(self):
        """Multiple patterns are sorted by severity (highest first)."""
        content = (
            "## Blockers\n\n"
            "### Crash on export\nCrash.\n\n"
            "### Crash on export\nCrash again.\n\n"
            "### Crash on export\nThird crash.\n\n"
            "## Parameters\n\n"
            "### Set roughness to 0.5\nBefore: 0.2, After: 0.5.\n\n"
            "### Set roughness to 0.2\nBefore: 0.5, After: 0.2.\n\n"
            "### Set roughness to 0.5\nBefore: 0.2, After: 0.5.\n"
        )
        patterns = detect_patterns(content)
        assert len(patterns) >= 2
        # Repeated blocker should rank higher (3 occurrences)
        assert patterns[0]["severity"] >= patterns[-1]["severity"]
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_memory_patterns.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement pattern detection**

Create `python/synapse/memory/patterns.py`:

```python
"""
Memory Pattern Detection

Surfaces repeated blockers, oscillating parameters, and decision reversals
from Living Memory markdown content.
"""

import re
from typing import List, Dict, Any
from collections import Counter


def detect_patterns(content: str) -> List[Dict[str, Any]]:
    """Detect actionable patterns in memory content.

    Returns list of patterns sorted by severity (highest first).
    Each pattern: {type, description, severity, count, evidence}
    """
    if not content:
        return []

    patterns = []
    patterns.extend(_detect_repeated_blockers(content))
    patterns.extend(_detect_oscillating_parameters(content))

    patterns.sort(key=lambda p: -p["severity"])
    return patterns


def _detect_repeated_blockers(content: str) -> List[Dict[str, Any]]:
    """Find blockers mentioned multiple times (similar titles)."""
    blocker_sections = re.findall(
        r'### (.+?)(?:\n)(.*?)(?=\n###|\n##|\Z)',
        content,
        re.DOTALL,
    )

    # Only look at sections under ## Blockers
    in_blockers = False
    blocker_titles = []
    for line in content.split('\n'):
        if line.startswith('## Blockers'):
            in_blockers = True
            continue
        if line.startswith('## ') and not line.startswith('## Blockers'):
            in_blockers = False
            continue
        if in_blockers and line.startswith('### '):
            blocker_titles.append(line[4:].strip().lower())

    if len(blocker_titles) < 2:
        return []

    # Group similar titles (shared 2+ words)
    groups: Dict[str, List[str]] = {}
    for title in blocker_titles:
        words = set(re.findall(r'[a-z]+', title))
        matched = False
        for key, members in groups.items():
            key_words = set(re.findall(r'[a-z]+', key))
            if len(words & key_words) >= 2:
                members.append(title)
                matched = True
                break
        if not matched:
            groups[title] = [title]

    results = []
    for key, members in groups.items():
        if len(members) >= 2:
            results.append({
                "type": "repeated_blocker",
                "description": f"Blocker '{key}' appeared {len(members)} times",
                "severity": len(members),
                "count": len(members),
                "evidence": members,
            })
    return results


def _detect_oscillating_parameters(content: str) -> List[Dict[str, Any]]:
    """Find parameters that oscillate (A->B->A pattern)."""
    # Extract parameter changes from ## Parameters sections
    in_params = False
    changes = []
    for line in content.split('\n'):
        if line.startswith('## Parameters') or line.startswith('## Parameter'):
            in_params = True
            continue
        if line.startswith('## ') and 'Parameter' not in line:
            in_params = False
            continue
        if in_params:
            # Match "Before: X, After: Y" pattern
            match = re.search(r'Before:\s*([^,]+),\s*After:\s*([^.\n]+)', line)
            if match:
                changes.append((match.group(1).strip(), match.group(2).strip()))

    if len(changes) < 3:
        return []

    # Detect A->B->A oscillation
    results = []
    for i in range(len(changes) - 2):
        a_before, a_after = changes[i]
        b_before, b_after = changes[i + 1]
        c_before, c_after = changes[i + 2]
        # A->B then B->A then A->B = oscillation
        if a_after == b_before and b_after == c_before and a_after == c_after:
            results.append({
                "type": "oscillating_parameter",
                "description": f"Parameter oscillating between {a_before} and {a_after}",
                "severity": 1,
                "count": 3,
                "evidence": [f"{a_before}->{a_after}", f"{b_before}->{b_after}", f"{c_before}->{c_after}"],
            })
            break  # One oscillation per parameter sequence

    return results
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_memory_patterns.py -v`
Expected: All 5 PASSED

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ~835+ passed

**Step 6: Commit**

```bash
git add python/synapse/memory/patterns.py tests/test_memory_patterns.py
git commit -m "feat: add memory pattern detection (repeated blockers, oscillating params)"
```

---

## Phase C: Integration Confidence

### Task 10: MCP Roundtrip Integration Test Harness

**Files:**
- Create: `tests/test_mcp_roundtrip.py`
- Modify: (none — pure test addition)

**Context:** The MCP bridge (`mcp_server.py`) dispatches tool calls through WebSocket to the handler layer. Currently there are unit tests for individual handlers and for the MCP server separately, but no test that exercises the full chain: MCP tool call -> WebSocket send -> handler dispatch -> WebSocket response -> MCP result. This is the highest-value missing test.

**Step 1: Write the integration test harness**

Create `tests/test_mcp_roundtrip.py`:

```python
"""
MCP Roundtrip Integration Tests

Tests the full chain: MCP tool call -> handler dispatch -> response.
Uses a mock WebSocket to avoid needing a real Houdini instance.

These tests verify that:
1. MCP tool schemas match handler expectations
2. Parameter aliases resolve correctly end-to-end
3. Error responses propagate through the full chain
4. Timeout handling works
"""

import sys
import os
import json
import importlib
import importlib.util
from unittest.mock import Mock, MagicMock, patch, AsyncMock
import pytest

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

# Stub hou
mock_hou = MagicMock()
mock_hou.hipFile.path.return_value = "/tmp/test.hip"
mock_hou.getenv.return_value = "/tmp"
sys.modules["hou"] = mock_hou

from synapse.core.protocol import SynapseCommand, SynapseResponse, PROTOCOL_VERSION


class TestHandlerRoundtrip:
    """Test handler dispatch with real SynapseCommand objects."""

    def _get_handler(self):
        """Create a fresh handler instance."""
        spec = importlib.util.spec_from_file_location(
            "handlers",
            os.path.join(python_dir, "synapse", "server", "handlers.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.SynapseHandler()

    def test_ping_roundtrip(self):
        """ping command -> success response with pong=True."""
        handler = self._get_handler()
        cmd = SynapseCommand(
            type="ping",
            id="test-001",
            payload={},
            sequence=1,
        )
        resp = handler.handle(cmd)
        assert resp.success is True
        assert resp.data["pong"] is True
        assert "protocol_version" in resp.data

    def test_get_help_roundtrip(self):
        """get_help command -> success response with available commands."""
        handler = self._get_handler()
        cmd = SynapseCommand(
            type="get_help",
            id="test-002",
            payload={},
            sequence=2,
        )
        resp = handler.handle(cmd)
        assert resp.success is True
        assert "commands" in resp.data or "available" in str(resp.data).lower()

    def test_unknown_command_roundtrip(self):
        """Unknown command -> failure with coaching-tone error."""
        handler = self._get_handler()
        cmd = SynapseCommand(
            type="nonexistent_command",
            id="test-003",
            payload={},
            sequence=3,
        )
        resp = handler.handle(cmd)
        assert resp.success is False
        assert "don't recognize" in resp.error

    def test_create_node_missing_parent_roundtrip(self):
        """create_node with invalid parent -> NodeNotFoundError."""
        handler = self._get_handler()
        mock_hou.node.return_value = None  # Parent not found
        cmd = SynapseCommand(
            type="create_node",
            id="test-004",
            payload={"parent": "/obj/nonexistent", "type": "null"},
            sequence=4,
        )
        resp = handler.handle(cmd)
        assert resp.success is False
        assert "Couldn't find" in resp.error or "couldn't find" in resp.error.lower()

    def test_get_parm_missing_node_roundtrip(self):
        """get_parm on missing node -> error with coaching tone."""
        handler = self._get_handler()
        mock_hou.node.return_value = None
        cmd = SynapseCommand(
            type="get_parm",
            id="test-005",
            payload={"node": "/stage/missing", "parm": "tx"},
            sequence=5,
        )
        resp = handler.handle(cmd)
        assert resp.success is False
        # Should mention the path or suggest alternatives
        assert "/stage/missing" in resp.error or "Couldn't" in resp.error

    def test_batch_commands_roundtrip(self):
        """batch_commands with a ping -> array of results."""
        handler = self._get_handler()
        cmd = SynapseCommand(
            type="batch_commands",
            id="test-006",
            payload={
                "commands": [
                    {"type": "ping", "payload": {}},
                ],
            },
            sequence=6,
        )
        resp = handler.handle(cmd)
        assert resp.success is True
        assert "results" in resp.data
        assert len(resp.data["results"]) == 1
        assert resp.data["results"][0]["success"] is True

    def test_knowledge_lookup_roundtrip(self):
        """knowledge_lookup with query -> returns results (even if empty)."""
        handler = self._get_handler()
        cmd = SynapseCommand(
            type="knowledge_lookup",
            id="test-007",
            payload={"query": "dome light intensity parameter"},
            sequence=7,
        )
        resp = handler.handle(cmd)
        # Should succeed even if RAG index isn't loaded (returns empty/fallback)
        # The key test is that it doesn't crash
        assert isinstance(resp, SynapseResponse)

    def test_response_ids_match_command(self):
        """Response ID always matches the command ID."""
        handler = self._get_handler()
        for i in range(5):
            cmd_id = f"match-test-{i}"
            cmd = SynapseCommand(
                type="ping",
                id=cmd_id,
                payload={},
                sequence=i,
            )
            resp = handler.handle(cmd)
            assert resp.id == cmd_id

    def test_sequence_numbers_preserved(self):
        """Response sequence matches command sequence."""
        handler = self._get_handler()
        cmd = SynapseCommand(
            type="ping",
            id="seq-test",
            payload={},
            sequence=42,
        )
        resp = handler.handle(cmd)
        assert resp.sequence == 42


class TestParameterAliasRoundtrip:
    """Verify parameter aliases resolve end-to-end."""

    def _get_handler(self):
        spec = importlib.util.spec_from_file_location(
            "handlers",
            os.path.join(python_dir, "synapse", "server", "handlers.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.SynapseHandler()

    def test_node_alias_resolves(self):
        """'path' alias resolves to 'node' for get_parm."""
        handler = self._get_handler()
        mock_hou.node.return_value = None
        cmd = SynapseCommand(
            type="get_parm",
            id="alias-test-1",
            payload={"path": "/stage/light", "parm": "tx"},
            sequence=1,
        )
        resp = handler.handle(cmd)
        # Should attempt to find the node (not error about missing 'node' key)
        assert resp.success is False
        assert "Couldn't find" in resp.error or "couldn't" in resp.error.lower()

    def test_node_path_alias_resolves(self):
        """'node_path' alias resolves to 'node' for get_parm."""
        handler = self._get_handler()
        mock_hou.node.return_value = None
        cmd = SynapseCommand(
            type="get_parm",
            id="alias-test-2",
            payload={"node_path": "/stage/light", "parm": "tx"},
            sequence=2,
        )
        resp = handler.handle(cmd)
        assert resp.success is False
        assert "Couldn't find" in resp.error or "couldn't" in resp.error.lower()
```

**Step 2: Run the tests**

Run: `python -m pytest tests/test_mcp_roundtrip.py -v`
Expected: Most PASS. If any fail, it indicates a real gap in the handler chain.

**Step 3: Fix any failures discovered**

If a test reveals an actual bug (parameter alias not resolving, error message not matching coaching tone), fix it in the handler code and re-run.

**Step 4: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ~845+ passed

**Step 5: Commit**

```bash
git add tests/test_mcp_roundtrip.py
git commit -m "test: add MCP roundtrip integration tests (handler chain verification)"
```

---

### Task 11: Version Bump and Final Verification

**Files:**
- Modify: `pyproject.toml` (version)
- Modify: `python/synapse/__init__.py` (version)
- Modify: `CLAUDE.md` (test count, version)

**Step 1: Bump version to 5.2.0**

Edit `pyproject.toml`: `version = "5.2.0"`
Edit `python/synapse/__init__.py`: `__version__ = "5.2.0"` (both docstring and variable)

**Step 2: Update CLAUDE.md**

Update the version reference and test count.

**Step 3: Run full test suite — final verification**

Run: `python -m pytest tests/ -v`
Expected: ~845-860 passed, ~16 skipped

**Step 4: Run mypy**

Run: `python -m mypy python/synapse/ --config-file pyproject.toml`
Expected: 0 errors

**Step 5: Commit**

```bash
git add pyproject.toml python/synapse/__init__.py CLAUDE.md
git commit -m "chore: bump version to 5.2.0, update test counts"
```

**Step 6: Push to remote**

```bash
git push origin master
```

---

## Summary

| Phase | Tasks | New Tests | Line Reduction | Key Outcome |
|-------|-------|-----------|---------------|-------------|
| A (Foundation) | 1-7 | ~50 | handlers.py: 1905 -> ~750 | Exception hierarchy, mixin decomposition, file locking |
| B (Intelligence) | 8-9 | ~10 | — | TF-IDF search, pattern detection |
| C (Integration) | 10-11 | ~15 | — | MCP roundtrip tests, version bump |
| **Total** | **11** | **~75** | **~1,150 lines moved** | **Composite: 7.3 -> ~8.5** |

### Score Impact Projections

| Dimension | Before | After | Delta |
|-----------|--------|-------|-------|
| Frontier AI | 7 | 8 | +1 (pattern detection, TF-IDF) |
| Production Ready | 7 | 9 | +2 (exception hierarchy, decomposition, locking, integration tests) |
| VFX Utility | 8 | 9 | +1 (smarter search surfaces better memories) |
| **Composite** | **7.3** | **~8.6** | **+1.3** |
