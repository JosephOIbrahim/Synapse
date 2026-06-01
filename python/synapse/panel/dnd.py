"""Native Houdini drag-and-drop helpers for the SYNAPSE panel.

Verified against H21's shipping examples (clonecontrol/model.py, stagemanager
mimedatautils, and help/examples/python_panels/dragdrop.pypanel):
  * node drags carry hou.qt.mimeType.nodePath (TAB-separated node paths), with
    mimeData().text() as the simple fallback the example panel uses;
  * file/image drags carry text/uri-list;
  * the Network Editor is a native C++ pane (no Qt drop target) — you PLACE
    nodes programmatically via the hou.NetworkEditor API, you don't drop onto it.

Pure helpers here are headless-testable; the hou-touching ones are guarded.
"""

try:
    from PySide6 import QtCore  # noqa: F401  (binding parity with the panel)
except ImportError:  # pragma: no cover - Houdini ships PySide6
    from PySide2 import QtCore  # noqa: F401


def node_mime_type():
    """The MIME type Houdini uses for node-path drags (GUI-resolved, guarded)."""
    try:
        import hou
        return hou.qt.mimeType.nodePath
    except Exception:
        return "application/sidefx-houdini-node-path"


def extract_node_paths(mime):
    """Node/prim paths from a drag's mime data — node MIME first, text fallback.

    Houdini packs multiple paths TAB-separated in the node MIME; the example
    panel's text() form is comma-separated. We tolerate tab / comma / newline.
    """
    paths = []
    nm = node_mime_type()
    try:
        if mime.hasFormat(nm):
            raw = bytes(mime.data(nm)).decode("utf-8", "ignore")
            paths = raw.replace(",", "\t").replace("\n", "\t").split("\t")
    except Exception:
        pass
    if not paths and mime.hasText():
        txt = mime.text()
        for chunk in txt.replace(",", "\t").replace("\n", "\t").split("\t"):
            paths.append(chunk)
    # node + USD prim paths both start with "/"; keep those.
    return [p.strip() for p in paths if p.strip().startswith("/")]


def extract_files(mime):
    """Local file paths from a text/uri-list drag."""
    try:
        return [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
    except Exception:
        return []


def mime_is_acceptable(mime):
    """True if a drag carries something the panel can use."""
    try:
        if mime.hasUrls() or mime.hasText():
            return True
        return mime.hasFormat(node_mime_type())
    except Exception:
        return False


def place_in_network(node_path):
    """Results-OUT: locate/place a node in the active Network Editor.

    The network editor is native C++ (no Qt drop), so placement is programmatic
    via the verified hou.NetworkEditor API. Selects + frames the node, dropping
    it at the editor's cursor when the contexts match. GUI-only; returns False
    off-GUI or on any failure (never raises).
    """
    try:
        import hou
        node = hou.node(node_path)
        if node is None:
            return False
        editor = None
        for pane in hou.ui.paneTabs():
            if pane.type() == hou.paneTabType.NetworkEditor:
                editor = pane
                break
        if editor is not None:
            try:
                if editor.pwd() == node.parent():
                    node.setPosition(editor.cursorPosition())
                else:
                    node.moveToGoodPosition()
            except Exception:
                pass
        node.setSelected(True, clear_all_selected=True)
        return True
    except Exception:
        return False


def transcript_to_markdown(messages, title="SYNAPSE conversation"):
    """Text-COPY-OUT: serialize the chat to clean markdown for reports / LLMs."""
    lines = ["# %s\n" % title]
    for m in messages:
        role = m.get("role", "?") if isinstance(m, dict) else "?"
        content = m.get("content", "") if isinstance(m, dict) else str(m)
        if isinstance(content, list):  # Anthropic content blocks
            parts = []
            for b in content:
                if isinstance(b, dict):
                    parts.append(b.get("text") or "")
                else:
                    parts.append(str(b))
            content = " ".join(p for p in parts if p)
        who = {"user": "**You**", "assistant": "**SYNAPSE**"}.get(role, "**%s**" % role)
        lines.append("%s: %s\n" % (who, content))
    return "\n".join(lines)
