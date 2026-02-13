"""
Synapse Design System — Shelf Callbacks

Python functions invoked by synapse.shelf toolbar buttons.
Runs inside Houdini's embedded Python, so `hou` is available globally.

All functions are safe to call at any time — they handle missing
selections, empty scenes, and connection failures gracefully.
"""

import hou
import json
import os
import sys
import time


# ── Bootstrap Synapse package path ────────────────────────────

_SYNAPSE_ROOT = os.environ.get(
    "SYNAPSE_ROOT",
    os.path.join(os.path.expanduser("~"), "SYNAPSE"),
)
_SYNAPSE_PYTHON = os.path.join(_SYNAPSE_ROOT, "python")
if os.path.isdir(_SYNAPSE_PYTHON) and _SYNAPSE_PYTHON not in sys.path:
    sys.path.insert(0, _SYNAPSE_PYTHON)


# ── RAG path persistence ─────────────────────────────────────
# Auto-set SYNAPSE_RAG_ROOT from persisted file on import,
# so the knowledge index picks it up before any lookups happen.

_RAG_PATH_FILE = os.path.join(os.path.expanduser("~"), ".synapse", "rag_path")


def _load_rag_path():
    """Load persisted RAG folder path and set env var. Returns path or None."""
    if os.path.isfile(_RAG_PATH_FILE):
        try:
            with open(_RAG_PATH_FILE, "r") as f:
                path = f.read().strip()
            if path and os.path.isdir(path):
                os.environ["SYNAPSE_RAG_ROOT"] = path
                return path
        except Exception:
            pass
    return None


_load_rag_path()


# ── Helpers ────────────────────────────────────────────────────

def _copy_to_clipboard(text):
    """Copy text to system clipboard. Uses clip.exe on Windows (reliable
    in Houdini's PySide6 environment), falls back to Qt."""
    import platform
    import subprocess

    # Windows: clip.exe bypasses PySide6 QApplication.instance() issues
    if platform.system() == "Windows":
        try:
            p = subprocess.run(
                ["clip"],
                input=text.encode("utf-8"),
                creationflags=0x08000000,  # CREATE_NO_WINDOW
                timeout=5,
            )
            if p.returncode == 0:
                return True
        except Exception:
            pass

    # Qt fallback (works on Linux/macOS, and older Houdini)
    try:
        try:
            from PySide6 import QtWidgets, QtGui
        except ImportError:
            from PySide2 import QtWidgets, QtGui
        app = QtWidgets.QApplication.instance() or QtGui.QGuiApplication.instance()
        if app:
            app.clipboard().setText(text)
            return True
    except Exception:
        pass
    return False


def _notify(title, message, severity=hou.severityType.Message):
    """Show a Houdini notification dialog."""
    hou.ui.displayMessage(message, title=title, severity=severity)


def _node_summary(node):
    """Build a compact summary dict for a single node."""
    info = {
        "path": node.path(),
        "type": node.type().name(),
        "name": node.name(),
    }

    # Collect modified parameters (non-default values)
    modified = {}
    for parm_template in node.type().parmTemplates():
        pname = parm_template.name()
        try:
            parm = node.parm(pname)
            if parm is None:
                continue
            if not parm.isAtDefault():
                # Use evalParm on the node to avoid bare eval() call
                modified[pname] = node.evalParm(pname)
        except Exception:
            continue

    if modified:
        info["modified_parms"] = modified

    # Input connections
    inputs = []
    for conn in node.inputConnections():
        inputs.append({
            "from": conn.inputNode().path(),
            "output_index": conn.outputIndex(),
            "input_index": conn.inputIndex(),
        })
    if inputs:
        info["inputs"] = inputs

    # Warnings/errors
    warnings = node.warnings()
    errors = node.errors()
    if warnings:
        info["warnings"] = warnings
    if errors:
        info["errors"] = errors

    return info


# ── Shelf Functions ───────────────────────────────────────────

def open_panel():
    """Open the Synapse AI Co-Pilot panel in a new pane tab."""
    # Look for existing Synapse panel type
    panel_type = None
    for pt in hou.pypanel.interfacesInFile(
        hou.findFile("python_panels/synapse_panel.pypanel") or ""
    ):
        if pt.name() == "synapse_panel":
            panel_type = pt
            break

    if panel_type is None:
        # Try to install it
        try:
            pypanel_path = hou.findFile("python_panels/synapse_panel.pypanel")
            if pypanel_path:
                hou.pypanel.installFile(pypanel_path)
                for pt in hou.pypanel.interfaces():
                    if pt.name() == "synapse_panel":
                        panel_type = pt
                        break
        except Exception:
            pass

    if panel_type is None:
        _notify(
            "Synapse Panel",
            "Couldn't find the Synapse panel.\n\n"
            "Run the Synapse installer to set it up:\n"
            "  python install.py",
            hou.severityType.Warning,
        )
        return

    # Open in current pane or create new tab
    desktop = hou.ui.curDesktop()
    pane = desktop.paneTabOfType(hou.paneTabType.PythonPanel)
    if pane is None:
        # Create a new pane tab
        pane = desktop.createFloatingPaneTab(
            hou.paneTabType.PythonPanel,
            size=(320, 600),
        )
    pane.setActiveInterface(panel_type)


def inspect_selection():
    """Analyze selected nodes and copy structured context to clipboard."""
    selected = hou.selectedNodes()

    if not selected:
        _notify(
            "Inspect Selection",
            "No nodes selected.\n\nSelect one or more nodes and try again.",
        )
        return

    results = []
    for node in selected:
        results.append(_node_summary(node))

    context = {
        "type": "selection_inspection",
        "timestamp": time.time(),
        "hip_file": hou.hipFile.name(),
        "node_count": len(results),
        "nodes": results,
    }

    text = json.dumps(context, indent=2, default=str, sort_keys=True)
    if _copy_to_clipboard(text):
        _notify(
            "Inspect Selection",
            "Copied {} node{} to clipboard.\n\n"
            "Paste into Claude for analysis.".format(
                len(results), "s" if len(results) != 1 else ""
            ),
        )
    else:
        _notify(
            "Inspect Selection",
            "Couldn't access clipboard.\n\n"
            "Node data:\n{}".format(text[:2000]),
        )


def inspect_scene():
    """Analyze the full scene structure and copy to clipboard."""
    scene = {
        "type": "scene_inspection",
        "timestamp": time.time(),
        "hip_file": hou.hipFile.name(),
        "frame": hou.frame(),
        "fps": hou.fps(),
        "frame_range": list(hou.playbar.frameRange()),
    }

    # Walk top-level contexts
    contexts = {}
    for context_path in ["/obj", "/stage", "/out", "/shop", "/ch"]:
        try:
            context_node = hou.node(context_path)
            if context_node is None:
                continue
            children = context_node.children()
            if children:
                contexts[context_path] = []
                for child in children:
                    entry = {
                        "name": child.name(),
                        "type": child.type().name(),
                    }
                    warn_count = len(child.warnings())
                    err_count = len(child.errors())
                    if warn_count:
                        entry["warnings"] = warn_count
                    if err_count:
                        entry["errors"] = err_count
                    contexts[context_path].append(entry)
        except Exception:
            continue

    scene["contexts"] = contexts

    # Count total nodes
    total = sum(len(v) for v in contexts.values())
    scene["total_top_level_nodes"] = total

    text = json.dumps(scene, indent=2, default=str, sort_keys=True)
    if _copy_to_clipboard(text):
        _notify(
            "Inspect Scene",
            "Copied scene overview to clipboard.\n"
            "{} top-level nodes across {} contexts.\n\n"
            "Paste into Claude for analysis.".format(
                total, len(contexts)
            ),
        )
    else:
        _notify(
            "Inspect Scene",
            "Couldn't access clipboard.\n\n"
            "Scene data:\n{}".format(text[:2000]),
        )


def copy_last_result():
    """Copy last Synapse execution result from hou.session to clipboard."""
    result = getattr(hou.session, "_synapse_last_result", None)

    if result is None:
        _notify(
            "Last Result",
            "No Synapse results stored yet.\n\n"
            "Execute a Synapse command first.",
        )
        return

    if isinstance(result, dict):
        text = json.dumps(result, indent=2, default=str, sort_keys=True)
    else:
        text = str(result)

    if _copy_to_clipboard(text):
        _notify(
            "Last Result",
            "Copied last Synapse result to clipboard.\n\n"
            "Preview:\n{}".format(text[:500]),
        )
    else:
        _notify(
            "Last Result",
            "Couldn't access clipboard.\n\n"
            "Result:\n{}".format(text[:2000]),
        )


def health_check():
    """Run a basic scene health check and copy results to clipboard."""
    issues = []

    # Check for nodes with errors
    error_nodes = []
    for context_path in ["/obj", "/stage", "/out"]:
        try:
            context_node = hou.node(context_path)
            if context_node is None:
                continue
            for child in context_node.allSubChildren():
                errs = child.errors()
                if errs:
                    error_nodes.append({
                        "path": child.path(),
                        "errors": errs,
                    })
        except Exception:
            continue

    if error_nodes:
        issues.append({
            "severity": "error",
            "category": "node_errors",
            "message": "{} node{} with errors".format(
                len(error_nodes), "s" if len(error_nodes) != 1 else ""
            ),
            "nodes": error_nodes[:20],
        })

    # Check for nodes with warnings
    warning_nodes = []
    for context_path in ["/obj", "/stage", "/out"]:
        try:
            context_node = hou.node(context_path)
            if context_node is None:
                continue
            for child in context_node.allSubChildren():
                warns = child.warnings()
                if warns:
                    warning_nodes.append({
                        "path": child.path(),
                        "warnings": warns,
                    })
        except Exception:
            continue

    if warning_nodes:
        issues.append({
            "severity": "warning",
            "category": "node_warnings",
            "message": "{} node{} with warnings".format(
                len(warning_nodes), "s" if len(warning_nodes) != 1 else ""
            ),
            "nodes": warning_nodes[:20],
        })

    # Check render output paths
    for rop in (hou.node("/out") or hou.node("/stage")).children() if hou.node("/out") or hou.node("/stage") else []:
        try:
            if rop.type().name() in ("karma", "usdrender_rop", "ifd"):
                out_parm = rop.parm("picture") or rop.parm("outputimage")
                if out_parm:
                    out_path = out_parm.unexpandedString()
                    if not out_path or out_path == "ip":
                        issues.append({
                            "severity": "info",
                            "category": "render_output",
                            "message": "ROP {} has no file output set".format(
                                rop.path()
                            ),
                        })
        except Exception:
            continue

    # Check HIP file saved state
    if hou.hipFile.hasUnsavedChanges():
        issues.append({
            "severity": "info",
            "category": "unsaved_changes",
            "message": "HIP file has unsaved changes",
        })

    report = {
        "type": "health_check",
        "timestamp": time.time(),
        "hip_file": hou.hipFile.name(),
        "issue_count": len(issues),
        "status": "clean" if not issues else "issues_found",
        "issues": issues,
    }

    text = json.dumps(report, indent=2, default=str, sort_keys=True)
    if _copy_to_clipboard(text):
        if issues:
            _notify(
                "Health Check",
                "Found {} issue{}. Copied to clipboard.\n\n"
                "Paste into Claude for recommendations.".format(
                    len(issues), "s" if len(issues) != 1 else ""
                ),
                hou.severityType.Warning,
            )
        else:
            _notify(
                "Health Check",
                "Scene looks clean. No issues found.",
            )
    else:
        _notify(
            "Health Check",
            "Couldn't access clipboard.\n\n"
            "Report:\n{}".format(text[:2000]),
        )


def generate_docs():
    """Generate documentation for selected nodes and copy to clipboard."""
    selected = hou.selectedNodes()

    if not selected:
        _notify(
            "Generate Docs",
            "No nodes selected.\n\nSelect nodes to document.",
        )
        return

    docs = []
    for node in selected:
        doc = {
            "name": node.name(),
            "path": node.path(),
            "type": node.type().name(),
            "type_label": node.type().description(),
        }

        # Help text
        help_text = node.type().helpUrl()
        if help_text:
            doc["help_url"] = help_text

        # All parameters grouped by folder
        parm_groups = {}
        current_folder = "General"
        for pt in node.type().parmTemplates():
            if pt.type() == hou.parmTemplateType.FolderSet:
                continue
            if pt.type() == hou.parmTemplateType.Folder:
                current_folder = pt.label()
                continue
            pname = pt.name()
            parm = node.parm(pname)
            if parm is None:
                continue
            entry = {
                "name": pname,
                "label": pt.label(),
                "value": node.evalParm(pname),
                "is_default": parm.isAtDefault(),
            }
            if current_folder not in parm_groups:
                parm_groups[current_folder] = []
            parm_groups[current_folder].append(entry)

        doc["parameters"] = parm_groups

        # Input/output connections
        doc["inputs"] = [
            {"from": c.inputNode().path(), "index": c.inputIndex()}
            for c in node.inputConnections()
        ]
        doc["outputs"] = [
            {"to": c.outputNode().path(), "index": c.outputIndex()}
            for c in node.outputConnections()
        ]

        docs.append(doc)

    result = {
        "type": "node_documentation",
        "timestamp": time.time(),
        "hip_file": hou.hipFile.name(),
        "node_count": len(docs),
        "nodes": docs,
    }

    text = json.dumps(result, indent=2, default=str, sort_keys=True)
    if _copy_to_clipboard(text):
        _notify(
            "Generate Docs",
            "Generated documentation for {} node{}.\n"
            "Copied to clipboard.\n\n"
            "Paste into Claude or save to file.".format(
                len(docs), "s" if len(docs) != 1 else ""
            ),
        )
    else:
        _notify(
            "Generate Docs",
            "Couldn't access clipboard.\n\n"
            "Documentation:\n{}".format(text[:2000]),
        )


def _pick_project_folder(default_path):
    """Show a folder picker dialog for project setup. Returns chosen path or None."""
    chosen = hou.ui.selectFile(
        start_directory=default_path,
        title="Choose Synapse Project Folder",
        file_type=hou.fileType.Directory,
        chooser_mode=hou.fileChooserMode.Read,
    )
    if not chosen:
        return None
    # hou.ui.selectFile returns a path with trailing slash sometimes
    chosen = chosen.rstrip("/").rstrip("\\")
    # Expand Houdini variables ($HIP, $JOB, etc.)
    chosen = hou.text.expandString(chosen)
    return chosen


def project_setup():
    """Initialize SYNAPSE project structure for the current scene.

    On first run (no existing claude/ directory), prompts the user to choose
    a project folder. On subsequent runs, loads existing context silently.
    Copies handshake payload to clipboard.
    """
    hip_path = hou.hipFile.path()
    hip_dir = os.path.dirname(hip_path)
    hip_name = hou.hipFile.basename()
    job_path = hou.getenv("JOB", hip_dir)

    # Detect unsaved/untitled scene
    is_untitled = "untitled" in hip_path.lower() and not os.path.isfile(hip_path)

    # Check if project structure already exists
    existing_project = os.path.join(job_path, "claude")
    first_run = not os.path.isdir(existing_project)

    if first_run:
        # First time -- prompt for project folder
        if is_untitled:
            msg = (
                "Scene hasn't been saved yet.\n\n"
                "Pick a project folder for Synapse memory,\n"
                "or save your scene first and try again."
            )
        else:
            msg = (
                "First time setup for this project.\n\n"
                "Pick the project folder where Synapse\n"
                "will store memory and context files.\n\n"
                "A 'claude/' directory will be created there."
            )
        hou.ui.displayMessage(msg, title="Synapse Project Setup")

        default_dir = job_path if not is_untitled else os.path.expanduser("~")
        chosen = _pick_project_folder(default_dir)

        if chosen is None:
            _notify(
                "Project Setup",
                "Setup cancelled -- no folder selected.",
                hou.severityType.Warning,
            )
            return

        job_path = chosen
    # else: claude/ exists, use it silently

    # Try the installed synapse package first
    try:
        from synapse.memory.scene_memory import (
            ensure_scene_structure,
            load_full_context,
        )
        paths = ensure_scene_structure(hip_path, job_path)
        ctx = load_full_context(hip_dir, job_path)
    except ImportError:
        # Synapse package not installed -- basic directory setup
        project_dir = os.path.join(job_path, "claude")
        scene_dir = os.path.join(hip_dir, "claude") if not is_untitled else project_dir
        os.makedirs(project_dir, exist_ok=True)
        if scene_dir != project_dir:
            os.makedirs(scene_dir, exist_ok=True)
        paths = {"project_dir": project_dir, "scene_dir": scene_dir}
        ctx = {
            "summary": "Synapse package not installed -- basic setup only.",
            "agent": {},
        }
    except Exception as e:
        _notify(
            "Project Setup",
            "Memory setup hit a snag: {}\n\n"
            "Basic directories will still be created.".format(e),
            hou.severityType.Warning,
        )
        project_dir = os.path.join(job_path, "claude")
        scene_dir = os.path.join(hip_dir, "claude") if not is_untitled else project_dir
        os.makedirs(project_dir, exist_ok=True)
        if scene_dir != project_dir:
            os.makedirs(scene_dir, exist_ok=True)
        paths = {"project_dir": project_dir, "scene_dir": scene_dir}
        ctx = {"summary": "Error loading memory.", "agent": {}}

    # Build handshake payload
    lines = [
        "SYNAPSE CONNECT",
        "=" * 50,
        "Scene: {}".format(hip_name),
        "HIP: {}".format(hip_path),
        "JOB: {}".format(job_path),
        "FPS: {} | Range: {}".format(hou.fps(), list(hou.playbar.frameRange())),
        "Frame: {}".format(hou.frame()),
        "",
        "-- MEMORY --",
        str(ctx.get("summary", "No memory loaded."))[:4000],
        "",
        "=" * 50,
    ]
    payload = "\n".join(lines)

    if _copy_to_clipboard(payload):
        agent = ctx.get("agent", {})
        msg = "Project structure ready at:\n{}\n\nContext copied to clipboard.".format(
            job_path
        )
        if agent.get("has_suspended_tasks"):
            msg += "\n\n{} suspended tasks from last session.".format(
                agent["suspended_count"]
            )
        _notify("Project Setup", msg)
    else:
        _notify(
            "Project Setup",
            "Directories created but couldn't access clipboard.\n\n"
            "Paths:\n{}".format(json.dumps(paths, indent=2, sort_keys=True)),
        )


def start_mcp():
    """Start the MCP HTTP endpoint via hwebserver.

    Imports the MCP server module (which registers the /mcp URL handler),
    then starts hwebserver on a configurable port. The MCP endpoint runs
    alongside the existing WebSocket server -- no conflict.
    """
    mcp_port = int(os.environ.get("SYNAPSE_MCP_PORT", "8008"))

    try:
        import hwebserver
    except ImportError:
        _notify(
            "MCP Server",
            "hwebserver not available.\n\n"
            "MCP requires Houdini's built-in web server.",
            hou.severityType.Error,
        )
        return

    # Import the MCP module to register the /mcp URL handler
    try:
        from synapse.mcp.server import get_mcp_server
        get_mcp_server()  # ensure singleton is created
    except ImportError as e:
        _notify(
            "MCP Server",
            "Couldn't load SYNAPSE MCP module: {}\n\n"
            "Make sure SYNAPSE is installed:\n"
            "  pip install -e \".[dev]\"".format(e),
            hou.severityType.Error,
        )
        return

    # Start hwebserver (idempotent -- won't fail if already running)
    try:
        hwebserver.run(
            port=mcp_port,
            debug=False,
            in_background=True,
            max_num_threads=4,
        )
    except Exception as e:
        # Already running on this port is fine
        if "already" in str(e).lower() or "in use" in str(e).lower():
            pass
        else:
            _notify(
                "MCP Server",
                "hwebserver couldn't start on port {}: {}\n\n"
                "The port may be in use.".format(mcp_port, e),
                hou.severityType.Warning,
            )
            return

    _notify(
        "MCP Server",
        "MCP endpoint is live.\n\n"
        "URL: http://localhost:{}/mcp\n"
        "Transport: Streamable HTTP (MCP 2025-06-18)\n\n"
        "Any MCP client can now connect.".format(mcp_port),
    )


def rag_folder():
    """Set the RAG knowledge folder for Synapse lookups.

    Opens a folder picker, persists the chosen path to ~/.synapse/rag_path,
    and sets SYNAPSE_RAG_ROOT for the current session. The knowledge index
    will use this folder for all subsequent lookups.
    """
    current = os.environ.get("SYNAPSE_RAG_ROOT", "")

    # Show current state
    if current and os.path.isdir(current):
        choice = hou.ui.displayMessage(
            "RAG folder is currently set to:\n{}\n\n"
            "Change it or clear the connection?".format(current),
            title="Synapse RAG Folder",
            buttons=("Change", "Clear", "Cancel"),
        )
        if choice == 2:  # Cancel
            return
        if choice == 1:  # Clear
            # Remove persisted path and env var
            if os.path.isfile(_RAG_PATH_FILE):
                os.remove(_RAG_PATH_FILE)
            os.environ.pop("SYNAPSE_RAG_ROOT", None)
            _notify("RAG Folder", "RAG folder connection cleared.\n\n"
                    "Synapse will use its built-in knowledge only.")
            return

    # Folder picker
    start_dir = current if current and os.path.isdir(current) else _SYNAPSE_ROOT
    chosen = hou.ui.selectFile(
        start_directory=start_dir,
        title="Choose RAG Knowledge Folder",
        file_type=hou.fileType.Directory,
        chooser_mode=hou.fileChooserMode.Read,
    )

    if not chosen:
        return

    chosen = chosen.rstrip("/").rstrip("\\")
    chosen = hou.text.expandString(chosen)

    if not os.path.isdir(chosen):
        _notify(
            "RAG Folder",
            "That path doesn't exist:\n{}".format(chosen),
            hou.severityType.Warning,
        )
        return

    # Persist the path
    rag_dir = os.path.dirname(_RAG_PATH_FILE)
    os.makedirs(rag_dir, exist_ok=True)
    with open(_RAG_PATH_FILE, "w") as f:
        f.write(chosen)

    # Set env var for the current session
    os.environ["SYNAPSE_RAG_ROOT"] = chosen

    _notify(
        "RAG Folder",
        "RAG knowledge folder set to:\n{}\n\n"
        "Synapse will use this for knowledge lookups.".format(chosen),
    )
