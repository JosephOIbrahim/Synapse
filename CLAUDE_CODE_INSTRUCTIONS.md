# SYNAPSE SAFE EXECUTION — Claude Code Implementation Brief

## Context

You are modifying **Synapse**, a WebSocket bridge between Claude (AI) and SideFX Houdini 21.
Synapse runs as a Python server inside Houdini, receiving JSON commands over `ws://localhost:9999`
and executing them in Houdini's Python environment (with full `hou` module access).

### The Problem We're Solving

When Claude sends Python code via `houdini_execute_python`, the code executes line-by-line
inside Houdini. If the script errors on line 15, lines 1-14 have already mutated scene state
(created nodes, connected wires, changed parameters). Synapse reports "error" but doesn't
indicate which lines succeeded. When Claude retries, duplicate nodes/connections are created.

**Real example that caused this:** A single script that (1) wired two lights into a merge node,
then (2) inspected material parameters. Step 2 errored on a variable name bug. Claude retried
the whole script. Lights got wired 3x into the same merge. The merge had 10 inputs instead of 6.

### What We're Building

Three-layer safety system:

| Layer | What | Where |
|-------|------|-------|
| 1. Atomic | One mutation per call convention | Claude behavior (already saved to memory) |
| 2. Idempotent Guards | Helper functions that check-before-mutate | `guards.py` module |
| 3. Transaction Wrapper | Auto undo-group around all execute_python calls | Server handler modification |

---

## Step 0: Locate the Synapse Source

The Synapse server source is likely in one of these locations:
- C:/Users/User/.synapse/
- C:/Users/User/Documents/synapse/
- C:/Users/User/OneDrive/Documents/houdini_shared_tools/synapse/

Search for the file that contains the `houdini_execute_python` handler. It will have code
resembling `exec(code, namespace)` and `namespace.get('result')`.

**Important:** Read the full server source before making changes. Understand:
- How the WebSocket handler dispatches commands
- How `houdini_execute_python` currently works
- What namespace/globals are passed to `exec()`
- How errors are currently caught and reported
- Whether there's already any undo integration

---

## Step 1: Implement `guards.py` (Idempotent Helpers)

Create `guards.py` in Synapse's Python module path. This module will be auto-imported
into the execution namespace (see Step 2) so Claude's scripts can use these functions
without explicit imports.

### guards.py — Full Implementation

```python
"""
guards.py — Synapse Idempotent Operation Guards

These functions check scene state before mutating, making every operation
safe to re-run. If the desired state already exists, they no-op and return
the existing object/True.

Usage (from any Synapse-executed script):
    node = ensure_node('/stage', 'distantlight::2.0', 'rim_light')
    ensure_connection('/stage/rim_light', '/stage/scene_merge')
    ensure_parm('/stage/rim_light', 'xn__inputsintensity_i0a', 5.0)
"""

import hou
from typing import Optional, Union


def ensure_node(parent_path, node_type, node_name):
    """Create node only if it doesn't already exist. Returns the node."""
    full_path = f"{parent_path}/{node_name}"
    existing = hou.node(full_path)
    if existing is not None:
        return existing
    parent = hou.node(parent_path)
    if parent is None:
        raise ValueError(f"Parent node not found: {parent_path}")
    return parent.createNode(node_type, node_name)


def ensure_node_deleted(node_path):
    """Delete node only if it exists. Returns True if deleted or already gone."""
    node = hou.node(node_path)
    if node is None:
        return True
    node.destroy()
    return True


def node_exists(path):
    """Check if a node exists at the given path."""
    return hou.node(path) is not None


def ensure_connection(source_path, target_path, source_output=0, target_input=None):
    """
    Connect source to target only if not already connected.
    If target_input is None, appends to next available input index.
    Returns True if connection exists (whether new or pre-existing).
    """
    source = hou.node(source_path)
    target = hou.node(target_path)
    if not source or not target:
        raise ValueError(f"Node not found: {source_path if not source else target_path}")
    existing_inputs = target.inputs()
    for idx, inp in enumerate(existing_inputs):
        if inp and inp.path() == source.path():
            return True
    if target_input is not None:
        target.setInput(target_input, source, source_output)
    else:
        next_idx = len(existing_inputs)
        target.setInput(next_idx, source, source_output)
    return True


def ensure_disconnected(target_path, source_path):
    """Disconnect source from target's inputs. Removes ALL connections from source to target."""
    target = hou.node(target_path)
    if not target:
        return True
    inputs = target.inputs()
    for idx in range(len(inputs) - 1, -1, -1):
        inp = inputs[idx]
        if inp and inp.path() == source_path:
            target.setInput(idx, None)
    return True


def deduplicate_inputs(merge_path):
    """Remove duplicate connections on a merge node. Returns report dict."""
    merge = hou.node(merge_path)
    if not merge:
        raise ValueError(f"Node not found: {merge_path}")
    seen = set()
    to_disconnect = []
    inputs = merge.inputs()
    for idx, inp in enumerate(inputs):
        if inp is None:
            continue
        if inp.path() in seen:
            to_disconnect.append(idx)
        else:
            seen.add(inp.path())
    for idx in reversed(to_disconnect):
        merge.setInput(idx, None)
    return {'removed': len(to_disconnect), 'remaining': list(seen)}


def ensure_parm(node_path, parm_name, value):
    """Set parameter only if current value differs. Returns True on success."""
    node = hou.node(node_path)
    if not node:
        raise ValueError(f"Node not found: {node_path}")
    parm = node.parm(parm_name)
    if not parm:
        raise ValueError(f"Parameter not found: {node_path}/{parm_name}")
    current = parm.eval()
    if isinstance(value, float):
        if abs(current - value) < 1e-7:
            return True
    elif current == value:
        return True
    parm.set(value)
    return True


def ensure_parm_tuple(node_path, parm_names, values):
    """Set multiple related parameters (e.g. color rgb). Only sets if any differ."""
    node = hou.node(node_path)
    if not node:
        raise ValueError(f"Node not found: {node_path}")
    needs_update = False
    for parm_name, value in zip(parm_names, values):
        parm = node.parm(parm_name)
        if not parm:
            continue
        current = parm.eval()
        if isinstance(value, float):
            if abs(current - value) > 1e-7:
                needs_update = True
                break
        elif current != value:
            needs_update = True
            break
    if not needs_update:
        return True
    for parm_name, value in zip(parm_names, values):
        parm = node.parm(parm_name)
        if parm:
            parm.set(value)
    return True


def describe_inputs(node_path):
    """Return list of input connection paths for a node."""
    node = hou.node(node_path)
    if not node:
        return []
    return [inp.path() if inp else None for inp in node.inputs()]


def describe_node(node_path):
    """Return basic info about a node."""
    node = hou.node(node_path)
    if not node:
        return {'exists': False}
    return {
        'exists': True,
        'path': node.path(),
        'type': node.type().name(),
        'inputs': len([i for i in node.inputs() if i]),
        'outputs': len(node.outputs()),
    }
```

---

## Step 2: Implement Transaction Wrapper (Server Handler Modification)

Find the `houdini_execute_python` handler in the Synapse server source.
Modify it to wrap in an undo group with rollback on error:

```python
# AFTER (with transaction safety)
import guards

def handle_execute_python(code):
    namespace = {
        "hou": hou,
        # Auto-inject guards so scripts don't need to import them
        "ensure_node": guards.ensure_node,
        "ensure_connection": guards.ensure_connection,
        "ensure_disconnected": guards.ensure_disconnected,
        "ensure_parm": guards.ensure_parm,
        "ensure_parm_tuple": guards.ensure_parm_tuple,
        "ensure_node_deleted": guards.ensure_node_deleted,
        "node_exists": guards.node_exists,
        "deduplicate_inputs": guards.deduplicate_inputs,
        "describe_inputs": guards.describe_inputs,
        "describe_node": guards.describe_node,
    }
    
    with hou.undos.group("synapse_operation"):
        try:
            exec(code, namespace)
            return {
                "result": namespace.get("result"),
                "executed": True
            }
        except Exception as e:
            hou.undos.performUndo()
            raise e
```

### Critical Implementation Notes:

1. **Import guards at server startup**, not per-call
2. **Preserve existing namespace items** — only ADD guard functions to existing namespace
3. **Add fallback** if `hou.undos.group()` isn't available:
   ```python
   try:
       with hou.undos.group("synapse_operation"):
           exec(code, namespace)
   except AttributeError:
       exec(code, namespace)  # fallback without undo
   ```
4. **The error re-raise is critical** — after undo, error must still propagate to Claude
5. **Add guards.py to Python path** if not auto-discoverable:
   ```python
   import sys, os
   sys.path.insert(0, os.path.dirname(__file__))
   import guards
   ```

---

## Step 3: Test Protocol

Run these against the **live Houdini scene** (Synapse at ws://localhost:9999).
Scene: `synapse_demo_2026.hip`, nodes at `/stage/`.

### Test 1: Idempotent Node Creation
```python
node = ensure_node('/stage', 'null', 'safety_test_null')
result = f"Node: {node.path()}"
```
Run TWICE. Expected: Same path returned both times. Only one node exists.

### Test 2: Idempotent Connection
```python
ensure_node('/stage', 'null', 'safety_test_null')
ensure_connection('/stage/safety_test_null', '/stage/scene_merge')
result = describe_inputs('/stage/scene_merge')
```
Run TWICE. Expected: safety_test_null appears exactly once in merge inputs.

### Test 3: Transaction Rollback
```python
node = ensure_node('/stage', 'null', 'rollback_test')
x = undefined_variable_that_will_crash
```
Expected: Error reported. `/stage/rollback_test` does NOT exist (undo rolled it back).

### Test 4: Parameter Idempotency
```python
ensure_parm('/stage/hero_sphere', 'radius', 1.0)
result = "Parm set (no-op if already 1.0)"
```

### Test 5: Cleanup
```python
ensure_node_deleted('/stage/safety_test_null')
ensure_node_deleted('/stage/rollback_test')
result = "Cleaned up"
```

---

## Architecture Note

This is intentionally lightweight. We're NOT building:
- A full ORM for Houdini's node graph
- A command queue or replay system
- Persistent operation logging

We ARE building:
- Defensive helpers that make re-runs safe
- An undo safety net that prevents partial-mutation corruption
- Functions auto-injected into Claude's execution namespace

**The goal: Claude can be sloppy and nothing breaks.**
