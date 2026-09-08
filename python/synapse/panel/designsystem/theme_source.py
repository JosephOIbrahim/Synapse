"""theme_source — the ONE seam between the design tokens and the live host theme.

Historically ``designsystem/tokens.py`` read the Houdini Color Scheme inline: it
called ``hou.qt.color("PaneEmptyApp")`` to seed the panel surface from the
artist's active ``.hcs`` scheme (``UIDark.hcs`` for the stock dark theme), with
a hardcoded grey as the headless fallback. That read now lives HERE, behind a
backend selector, so exactly one module touches the host theme and an H22 Theme
Editor (QML) source can be swapped in without editing the token table.

Backends
--------
``hcs``        Read ``hou.qt.getColor(role)`` from the active
               Houdini Color Scheme (the ``.hcs`` / ``UIDark.hcs`` greys).
               Legacy ``color`` hosts retain their accessor fallback; missing
               roles or an unavailable host still return None.
               The active backend under MODE A.
``qml_theme``  Pending H22 Theme Editor introspection. Stub — raises
               ``NotImplementedError``. Do NOT switch to it under MODE A.

Pure stdlib. ``hou`` is imported LAZILY inside the hcs backend (never at module
load), so this module stays importable + testable headless exactly like
``tokens.py`` — any failure degrades to ``None`` and the caller's fallback.
"""

import threading

# The Houdini color-scheme role the panel surface is seeded from. Kept here so
# the single read site owns the role name.
# ADAPT: 'PaneEmptyApp' is a placeholder color-scheme role — tune it to the
# exact scheme entry that reads your build's pane grey (CRUCIBLE can cross-check
# the live host color). Any failure -> None -> the caller's hardcoded fallback.
SURFACE_ROLE = "PaneEmptyApp"

# The backend active under MODE A. 'qml_theme' is reserved for the H22 Theme
# Editor and stubbed.
ACTIVE_BACKEND = "hcs"


def _hcs_surface_rgb(role):
    """Host pane-background as ``(r, g, b)``, or ``None`` when headless/unavailable.

    Reads the active Houdini Color Scheme (the ``.hcs`` / ``UIDark.hcs`` greys)
    via the live-verified H22 getColor accessor, with the legacy color accessor
    retained as a fallback. Missing roles, unavailable hosts, and worker-thread
    callers return None; querying a host theme must stay on Houdini's main thread.
    """
    if threading.current_thread() is not threading.main_thread():
        return None
    try:
        import hou
        get_color = getattr(hou.qt, "getColor", None) or getattr(hou.qt, "color", None)
        c = get_color(role)
    except Exception:
        return None
    if c is None:
        return None
    try:
        return (int(c.red()), int(c.green()), int(c.blue()))
    except Exception:
        try:
            r, g, b = c.getRgb()[:3]
            return (int(r), int(g), int(b))
        except Exception:
            return None


def _qml_theme_surface_rgb(role):
    """H22 Theme Editor (QML) backend — pending introspection of the new theme
    source. Not implemented; do not select this backend under MODE A."""
    raise NotImplementedError(
        "theme_source 'qml_theme' backend is pending H22 Theme Editor "
        "introspection; the 'hcs' backend is active under MODE A"
    )


# Backend registry — name -> reader. New sources register here; callers never
# import a backend function directly.
_BACKENDS = {
    "hcs": _hcs_surface_rgb,
    "qml_theme": _qml_theme_surface_rgb,
}

# Public, read-only view of the registered backend names.
AVAILABLE_BACKENDS = tuple(_BACKENDS)


def host_surface_rgb(role=SURFACE_ROLE, backend=ACTIVE_BACKEND):
    """The host pane-background as ``(r, g, b)``, or ``None`` headless/unavailable.

    Routes the host-theme read through the selected ``backend`` (default the
    MODE-A-active ``'hcs'``). The ``'hcs'`` backend reads the current host theme
    on the main thread and otherwise returns None; ``'qml_theme'`` is a stub that raises
    ``NotImplementedError``. Unknown backends raise ``ValueError``."""
    try:
        reader = _BACKENDS[backend]
    except KeyError:
        raise ValueError(
            "unknown theme_source backend %r (available: %s)"
            % (backend, ", ".join(AVAILABLE_BACKENDS))
        )
    return reader(role)
