"""Which Moneta native path is this process on? Read it; never trigger it.

NATIVE-STATUS (R3 audit). Moneta ships an optional Rust extension,
``moneta_native``. When it imports, Moneta switches it on by default:
``vector_index._resolve_backend("auto")`` picks the native scan and
``ECS.__init__`` the native decay kernel, unless ``MONETA_NATIVE=0``. Nothing in
SYNAPSE reported that -- memory_status, get_health, doctor and
moneta_provenance carried no native, backend or demotion field -- so the day a
wheel lands on a Houdini-visible path the Rust code would switch on with no
signal anywhere.

:func:`native_status` reports it from what is already in the process:

* the ``sys.modules`` entry: ``not_loaded`` (absent), ``blocked`` (``None``, the
  import system's "never import this") or ``loaded``;
* for a loaded module, ``__file__`` and ``__version__``, read from the module's
  namespace dict so no module-level ``__getattr__`` runs, and the size and
  mtime of that file from one ``os.stat`` (no hashing). For the maturin package
  layout ``__file__`` is the package ``__init__.py``;
* ``MONETA_NATIVE`` as the environment holds it;
* given a Moneta handle, or a store holding one, the vector backend its index
  runs and whether its ECS uses the native decay kernel. ``vector_backend ==
  "python"`` beside a loaded module means the index is not on the native scan:
  demoted (``VectorIndex._demote``) or never promoted.

It never imports anything: importing the wheel to describe it would be the
activation this exists to report, so the reading only looks.

It never raises. A failure is recorded as ``error`` (``repr`` of the exception)
beside whatever was read before it; every other key is always present and
``None`` when unknown. ``BaseException`` is caught because PyO3 raises
``PanicException``, a ``BaseException``, when Rust code panics.
``KeyboardInterrupt`` and ``SystemExit`` still propagate: they are the process
being stopped, not a failed reading.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Callable, Dict

_MODULE = "moneta_native"
_ENV = "MONETA_NATIVE"
_ABSENT = object()

# Every key, always present. None means not known.
_FIELDS = (
    "state",              # "not_loaded" | "blocked" | "loaded"
    "file",               # the module's __file__
    "version",            # the module's __version__
    "size",               # os.stat(file).st_size
    "mtime",              # os.stat(file).st_mtime, epoch seconds
    "env_MONETA_NATIVE",  # os.environ.get("MONETA_NATIVE")
    "handle_via",         # where the Moneta handle was found on the object given
    "vector_backend",     # handle.vector_index.backend: "native" | "python"
    "native_decay",       # handle.ecs.native_decay
    "error",              # repr() of what went wrong
)

# Where a Moneta handle sits on each object this may be given, nearest first:
# the handle itself, then each store shape SYNAPSE builds (memory/store.py
# _make_store, memory/writethrough_store.py). A fixed list, one hop at a time:
# no recursion and no __dict__ walk, the same rule as write_plane's
# _HEALTH_CONTRACT_MEMBERS.
_HANDLE_PATHS = (
    ("handle", ()),
    ("_handle", ("_handle",)),                    # MonetaBackedStore
    ("primary._handle", ("primary", "_handle")),  # WriteThroughStore
    ("shadow._handle", ("shadow", "_handle")),    # ShadowMemoryStore
)

_STOPPING = (KeyboardInterrupt, SystemExit)


def native_status(handle: Any = None) -> Dict[str, Any]:
    """Report the Moneta native path. Never imports anything, never raises.

    ``handle`` is optional: a Moneta handle, or a store that holds one (see
    ``_HANDLE_PATHS``). Without it, or when none is reachable on it,
    ``handle_via``, ``vector_backend`` and ``native_decay`` are ``None``.
    """
    reading: Dict[str, Any] = dict.fromkeys(_FIELDS)
    _attempt(reading, _read_module)
    if handle is not None:
        _attempt(reading, lambda out: _read_handle(out, handle))
    return reading


def _read_module(reading: Dict[str, Any]) -> None:
    reading["env_MONETA_NATIVE"] = os.environ.get(_ENV)
    entry = sys.modules.get(_MODULE, _ABSENT)
    if entry is _ABSENT:
        reading["state"] = "not_loaded"
        return
    if entry is None:
        reading["state"] = "blocked"
        return
    reading["state"] = "loaded"
    namespace = getattr(entry, "__dict__", None)
    if not isinstance(namespace, dict):
        return
    path = namespace.get("__file__")
    version = namespace.get("__version__")
    reading["file"] = path if isinstance(path, str) else None
    reading["version"] = version if isinstance(version, str) else None
    if reading["file"]:
        stat = os.stat(reading["file"])
        reading["size"] = stat.st_size
        reading["mtime"] = stat.st_mtime


def _read_handle(reading: Dict[str, Any], obj: Any) -> None:
    for label, path in _HANDLE_PATHS:
        candidate = obj
        for name in path:
            candidate = getattr(candidate, name, None)
            if candidate is None:
                break
        if candidate is None:
            continue
        vector_index = getattr(candidate, "vector_index", None)
        ecs = getattr(candidate, "ecs", None)
        if vector_index is None and ecs is None:
            continue
        reading["handle_via"] = label
        backend = getattr(vector_index, "backend", None)
        decay = getattr(ecs, "native_decay", None)
        reading["vector_backend"] = backend if isinstance(backend, str) else None
        reading["native_decay"] = decay if isinstance(decay, bool) else None
        return


def _attempt(reading: Dict[str, Any],
             read: Callable[[Dict[str, Any]], None]) -> None:
    """Run one part of the reading. What it raises is recorded, not raised."""
    try:
        read(reading)
    except _STOPPING:
        raise
    except BaseException as exc:  # noqa: BLE001 -- PyO3's PanicException is a BaseException
        _record_error(reading, exc)


def _record_error(reading: Dict[str, Any], exc: BaseException) -> None:
    """Add ``repr(exc)`` to the reading's ``error`` text."""
    try:
        text = repr(exc)
    except _STOPPING:
        raise
    except BaseException as unprintable:  # noqa: BLE001 -- a broken __repr__ still gets recorded
        _record_error_text(reading, "<%s; repr() raised %s>" % (
            type(exc).__name__, type(unprintable).__name__))
        return
    _record_error_text(reading, text)


def _record_error_text(reading: Dict[str, Any], text: str) -> None:
    prior = reading["error"]
    reading["error"] = text if prior is None else "%s; %s" % (prior, text)
