"""Synapse Hooks — Houdini-side event writer.

Registers hou callbacks across three layers and writes events to a JSONL
file that the Claude Code-side bridge reads on each prompt.

Usage from Houdini Python Shell:
    import sys
    sys.path.insert(0, "C:/Users/User/SYNAPSE/synapse")
    from hooks.synapse_hooks_houdini import register_scene_callbacks
    register_scene_callbacks()

To add node-level callbacks on /stage:
    from hooks.synapse_hooks_houdini import register_node_callbacks_recursive
    register_node_callbacks_recursive("/stage")

To unregister everything:
    from hooks.synapse_hooks_houdini import unregister_all
    unregister_all()
"""

import json
import os
import time

EVENTS_DIR = os.path.join(os.environ.get("TEMP", "/tmp"), "synapse_hooks")
EVENTS_FILE = os.path.join(EVENTS_DIR, "houdini_events.jsonl")

MAX_EVENTS = 200

# Track registered callbacks for clean teardown
_registered_callbacks = {}
_registered_nodes = set()


def _write_event(event_type, detail="", data=None):
    """Append a timestamped event to the JSONL file."""
    os.makedirs(EVENTS_DIR, exist_ok=True)
    event = {
        "type": event_type,
        "detail": detail,
        "timestamp": time.time(),
    }
    if data:
        event["data"] = data
    line = json.dumps(event, sort_keys=True) + "\n"

    try:
        with open(EVENTS_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        return

    _maybe_rotate()


def _maybe_rotate():
    """Keep only the last MAX_EVENTS lines."""
    try:
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > MAX_EVENTS:
            with open(EVENTS_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines[-MAX_EVENTS:])
    except OSError:
        pass


# ── Layer 1: Scene Events ──

def _on_hip_file_event(event_type):
    """Callback for hou.hipFile events."""
    import hou

    name = str(event_type)
    if "." in name:
        name = name.split(".")[-1]

    detail = ""
    try:
        detail = hou.hipFile.name()
    except Exception:
        pass

    _write_event(f"hip_{name}", detail)


# ── Layer 2: Node Events ──

# Full set of watched node events per the blueprint
_WATCHED_ROOT_EVENTS = None  # Lazy — set on first use
_WATCHED_CHILD_EVENTS = None


def _get_root_events():
    """Event tuple for root containers (/obj, /stage, /out)."""
    global _WATCHED_ROOT_EVENTS
    if _WATCHED_ROOT_EVENTS is None:
        import hou
        _WATCHED_ROOT_EVENTS = (
            hou.nodeEventType.ChildCreated,
            hou.nodeEventType.ChildDeleted,
        )
    return _WATCHED_ROOT_EVENTS


def _get_child_events():
    """Event tuple for individual nodes (parm changes, wiring, etc)."""
    global _WATCHED_CHILD_EVENTS
    if _WATCHED_CHILD_EVENTS is None:
        import hou
        _WATCHED_CHILD_EVENTS = (
            hou.nodeEventType.ParmTupleChanged,
            hou.nodeEventType.InputChanged,
            hou.nodeEventType.NameChanged,
            hou.nodeEventType.BeingDeleted,
            hou.nodeEventType.FlagChanged,
        )
    return _WATCHED_CHILD_EVENTS


def _on_root_event(node, event_type, **kwargs):
    """Callback for root container events (child create/delete)."""
    name = str(event_type)
    if "." in name:
        name = name.split(".")[-1]

    try:
        path = node.path()
    except Exception:
        path = "unknown"

    detail = path
    data = {}

    # Auto-register new children
    if name == "ChildCreated":
        child = kwargs.get("child_node")
        if child is not None:
            try:
                child_path = child.path()
                detail = child_path
                data["child_type"] = child.type().name()
                # Register parm callbacks on the new child and its descendants
                _register_single_node(child)
                for desc in child.allSubChildren():
                    _register_single_node(desc)
            except Exception:
                pass

    _write_event(f"node_{name}", detail, data if data else None)


def _on_child_event(node, event_type, **kwargs):
    """Callback for individual node events (parm change, rename, etc)."""
    name = str(event_type)
    if "." in name:
        name = name.split(".")[-1]

    try:
        path = node.path()
    except Exception:
        path = "unknown"

    data = {}

    if name == "ParmTupleChanged":
        parm_tuple = kwargs.get("parm_tuple")
        if parm_tuple is not None:
            data["parm"] = parm_tuple.name()
            try:
                val = parm_tuple.eval()
                # Keep values compact
                data["value"] = str(val) if len(str(val)) < 200 else "<long>"
            except Exception:
                data["value"] = "<eval_error>"
        else:
            data["parm"] = None
            data["note"] = "bulk_change"

    if name == "BeingDeleted":
        _registered_nodes.discard(path)

    _write_event(f"node_{name}", path, data if data else None)


def _register_single_node(node):
    """Register child-event callbacks on one node. Idempotent."""
    try:
        path = node.path()
    except Exception:
        return
    if path in _registered_nodes:
        return
    try:
        node.addEventCallback(_get_child_events(), _on_child_event)
        _registered_nodes.add(path)
    except Exception:
        pass


def register_node_callbacks_recursive(root_path="/stage"):
    """Register parm/wiring/rename callbacks on all nodes under root.

    Call this after register_scene_callbacks() to add Layer 2 depth.
    Safe to call multiple times — skips already-registered nodes.
    """
    import hou

    root = hou.node(root_path)
    if root is None:
        print(f"[synapse hooks] {root_path} not found, skipping node callbacks.")
        return

    count = 0
    for node in root.allSubChildren():
        path = node.path()
        if path not in _registered_nodes:
            _register_single_node(node)
            count += 1

    print(f"[synapse hooks] Registered node callbacks on {count} nodes under {root_path}.")


# ── Layer 3: PDG Events (stub — activate when TOPs available) ──

def register_pdg_callbacks(topnet_path="/tasks/topnet1"):
    """Register PDG event handlers. Requires cooked TOP network."""
    try:
        import hou
        import pdg
    except ImportError:
        print("[synapse hooks] pdg module not available, skipping PDG callbacks.")
        return

    topnet = hou.node(topnet_path)
    if topnet is None:
        print(f"[synapse hooks] {topnet_path} not found, skipping PDG callbacks.")
        return

    try:
        import hdefereval
    except ImportError:
        hdefereval = None

    def _pdg_handler(event):
        event_name = str(event.type)
        if "." in event_name:
            event_name = event_name.split(".")[-1]
        data = {}
        if hasattr(event, "node") and event.node is not None:
            data["pdg_node"] = event.node.name
        if hasattr(event, "message") and event.message:
            data["message"] = event.message
        _write_event(f"pdg_{event_name}", topnet_path, data if data else None)

    try:
        ctx = topnet.getPDGGraphContext()
        if ctx is not None:
            for evt in (pdg.EventType.CookComplete, pdg.EventType.CookError):
                ctx.addEventHandler(_pdg_handler, evt)
            _registered_callbacks["pdg_context"] = (_pdg_handler, ctx)
            print(f"[synapse hooks] Registered PDG callbacks on {topnet_path}.")
    except Exception as e:
        print(f"[synapse hooks] PDG registration failed: {e}")


# ── Registration / Teardown ──

def register_scene_callbacks():
    """Register Layer 1 (scene) + Layer 2 (root containers).

    Safe to call multiple times — skips if already registered.
    """
    import hou

    if "hipFile" in _registered_callbacks:
        print("[synapse hooks] Callbacks already registered, skipping.")
        return

    # Layer 1: Hip file events
    try:
        hou.hipFile.addEventCallback(_on_hip_file_event)
        _registered_callbacks["hipFile"] = _on_hip_file_event
        print("[synapse hooks] Registered hipFile event callback.")
    except Exception as e:
        print(f"[synapse hooks] Could not register hipFile callback: {e}")

    # Layer 2: Root container events (child create/delete)
    for root_path in ("/obj", "/stage", "/out"):
        try:
            node = hou.node(root_path)
            if node is not None:
                node.addEventCallback(_get_root_events(), _on_root_event)
                _registered_callbacks[root_path] = _on_root_event
                print(f"[synapse hooks] Registered root callback on {root_path}.")
        except Exception as e:
            print(f"[synapse hooks] Could not register callback on {root_path}: {e}")

    # Layer 2 depth: register on existing children of /stage
    register_node_callbacks_recursive("/stage")

    _write_event("hooks_registered", f"Houdini {hou.applicationVersionString()}")
    print(f"[synapse hooks] Bridge active. Events -> {EVENTS_FILE}")


def unregister_all():
    """Remove all registered callbacks."""
    import hou

    # Layer 1
    if "hipFile" in _registered_callbacks:
        try:
            hou.hipFile.removeEventCallback(_registered_callbacks["hipFile"])
            print("[synapse hooks] Removed hipFile callback.")
        except Exception:
            pass

    # Layer 2 roots
    for root_path in ("/obj", "/stage", "/out"):
        if root_path in _registered_callbacks:
            try:
                node = hou.node(root_path)
                if node is not None:
                    node.removeEventCallback(
                        _get_root_events(),
                        _registered_callbacks[root_path],
                    )
                    print(f"[synapse hooks] Removed root callback on {root_path}.")
            except Exception:
                pass

    # Layer 2 children
    for node_path in list(_registered_nodes):
        try:
            node = hou.node(node_path)
            if node is not None:
                node.removeEventCallback(_get_child_events(), _on_child_event)
        except Exception:
            pass
    _registered_nodes.clear()

    # Layer 3 PDG
    if "pdg_context" in _registered_callbacks:
        try:
            handler, ctx = _registered_callbacks["pdg_context"]
            ctx.removeEventHandler(handler)
            print("[synapse hooks] Removed PDG callbacks.")
        except Exception:
            pass

    _registered_callbacks.clear()
    _write_event("hooks_unregistered")
    print("[synapse hooks] All callbacks removed.")


# Keep old name as alias
unregister_scene_callbacks = unregister_all
