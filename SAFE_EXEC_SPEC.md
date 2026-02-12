# Synapse Safe Execution — Implementation Spec

## Problem
When `houdini_execute_python` scripts error midway, mutations before the error
line are already committed. Synapse reports "error" with no info about what
succeeded. Blind retry creates duplicates and corrupt state.

## Solution: Three-Layer Safety

### Layer 1: Atomic Scripts (Convention)
- Claude sends one mutation per `houdini_execute_python` call
- Read-only operations can combine freely
- This is a prompting/behavior convention, not code

### Layer 2: Idempotent Guards (`guards.py`)
Helper functions that check state before mutating:

```python
# guards.py — importable from any Synapse script
import hou

def ensure_node(parent_path, node_type, node_name):
    """Create node only if it doesn't exist. Returns node."""
    existing = hou.node(f"{parent_path}/{node_name}")
    if existing:
        return existing
    parent = hou.node(parent_path)
    return parent.createNode(node_type, node_name)

def ensure_connection(source_path, target_path, target_input=None):
    """Connect source→target only if not already connected."""
    source = hou.node(source_path)
    target = hou.node(target_path)
    if not source or not target:
        return False
    existing = target.inputs()
    for inp in existing:
        if inp and inp.path() == source.path():
            return True  # already connected
    if target_input is not None:
        target.setInput(target_input, source)
    else:
        next_idx = len([i for i in existing if i is not None])
        target.setInput(next_idx, source)
    return True

def ensure_parm(node_path, parm_name, value):
    """Set parm only if current value differs."""
    node = hou.node(node_path)
    if not node:
        return False
    parm = node.parm(parm_name)
    if not parm:
        return False
    if parm.eval() == value:
        return True
    parm.set(value)
    return True

def node_exists(path):
    return hou.node(path) is not None
```

### Layer 3: Transaction Wrapper (Server Middleware)
Modify the `houdini_execute_python` handler to auto-wrap in undo group:

```python
# In Synapse's handler for execute_python:
def handle_execute_python(code):
    with hou.undos.group("synapse_operation"):
        try:
            exec(code, namespace)
            return namespace.get('result')
        except Exception as e:
            hou.undos.performUndo()
            raise e
```

This means: if ANY line errors, the entire script's mutations roll back.

## File Locations
- `guards.py` → deploy to Synapse's Python path so scripts can `from guards import *`
- Transaction wrapper → modify Synapse server's execute handler
- Synapse source likely at: `C:/Users/User/.synapse/` or check `synapse` MCP config

## Test Protocol
1. Create a node via `ensure_node` — verify created
2. Call again — verify NOT duplicated
3. Wire via `ensure_connection` — verify wired
4. Call again — verify NOT duplicated
5. Run a script that errors midway — verify undo rolled back all mutations
