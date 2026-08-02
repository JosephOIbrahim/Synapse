"""Shared bootstrap for tests that hand-plant ``synapse.*`` modules.

WHY THIS EXISTS (R307)
======================

Many test modules pre-plant lightweight namespace packages into ``sys.modules``
so that a handler module can be loaded straight from its file without executing
the real package ``__init__`` chain (which pulls ``websockets``, ``hou``, and
friends).  The idiom that spread by copy-paste through 25 test files was::

    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg          # <-- only HALF the job

Writing ``sys.modules["synapse.server"]`` is only half of what Python's import
system does.  ``importlib._bootstrap._find_and_load`` also binds the freshly
loaded module as an **attribute of its parent package**::

    setattr(sys.modules["synapse"], "server", module)

Skipping that half leaves ``sys.modules["synapse.server"]`` populated while the
attribute ``synapse.server`` does not exist.  The two halves are supposed to be
the same object; once they diverge, every consumer that walks a dotted path with
``getattr`` breaks — and it breaks for a *later, unrelated* test, because the
residue outlives the module that planted it.

The reported victim was ``tests/test_websocket_cancel_reachable.py::
test_handle_client_cancel_mid_frame``, which does::

    monkeypatch.setattr("synapse.server.websocket.get_bridge", ...)

``_pytest.monkeypatch.resolve()`` walks that dotted string with ``getattr`` and,
on ``AttributeError``, falls back to ``importlib.import_module(prefix)``.  The
fallback finds ``synapse.server`` already in ``sys.modules`` and returns it
**without** performing the parent-attribute binding a real load would have done,
so the retry raises::

    AttributeError: 'module' object at synapse.server has no attribute 'server'

Any of the 25 bootstrap files running before the victim reproduces it — it is
not a ``test_tops`` property.  Verified: both ``pytest tests/test_tops.py
tests/test_websocket_cancel_reachable.py`` and ``pytest tests/test_cops.py
tests/test_websocket_cancel_reachable.py`` fail the same way.

THE RULE
========

If you put a dotted module name into ``sys.modules`` by hand, bind it on its
parent package in the same breath.  Use the helpers below instead of
open-coding it; ``tests/test_pkg_bootstrap_invariant.py`` pins the invariant.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from typing import Iterable, Tuple, Union

__all__ = [
    "bind_to_parent",
    "ensure_package",
    "ensure_packages",
    "load_module",
    "load_modules",
    "divergent_modules",
]

_PathLike = Union[str, "os.PathLike[str]"]  # noqa: F821 - runtime-irrelevant alias


def bind_to_parent(mod_name: str, module: types.ModuleType) -> None:
    """Bind ``module`` as ``<parent>.<leaf>``, the way importlib would.

    A no-op for top-level names and for parents that are not themselves in
    ``sys.modules`` yet.  Idempotent, and safe to call on a module that was
    already bound — it re-asserts that the attribute and the ``sys.modules``
    entry are the *same object*, which is the invariant that matters.
    """
    parent_name, _, leaf = mod_name.rpartition(".")
    if not parent_name:
        return
    parent = sys.modules.get(parent_name)
    if parent is None:
        return
    setattr(parent, leaf, module)


def ensure_package(mod_name: str, mod_path: _PathLike) -> types.ModuleType:
    """Plant a namespace package at ``mod_name`` rooted at ``mod_path``.

    Reuses an existing ``sys.modules`` entry when one is present (so a real
    package already imported by conftest or another test always wins), and
    binds the result on its parent either way.
    """
    module = sys.modules.get(mod_name)
    if module is None:
        module = types.ModuleType(mod_name)
        module.__path__ = [str(mod_path)]
        sys.modules[mod_name] = module
    bind_to_parent(mod_name, module)
    return module


def ensure_packages(specs: Iterable[Tuple[str, _PathLike]]) -> None:
    """``ensure_package`` over an iterable of ``(name, path)`` pairs."""
    for mod_name, mod_path in specs:
        ensure_package(mod_name, mod_path)


def load_module(mod_name: str, file_path: _PathLike) -> types.ModuleType:
    """Load ``mod_name`` from ``file_path`` unless it is already imported.

    Mirrors ``importlib._bootstrap._load`` ordering: the module goes into
    ``sys.modules`` *before* ``exec_module`` (so intra-package imports resolve),
    and the parent-attribute binding happens *after* a successful exec.
    """
    module = sys.modules.get(mod_name)
    if module is None:
        spec = importlib.util.spec_from_file_location(mod_name, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)
    bind_to_parent(mod_name, module)
    return module


def load_modules(specs: Iterable[Tuple[str, _PathLike]]) -> None:
    """``load_module`` over an iterable of ``(name, file_path)`` pairs."""
    for mod_name, file_path in specs:
        load_module(mod_name, file_path)


def divergent_modules(prefix: str = "synapse.") -> list:
    """Return every ``sys.modules`` key under ``prefix`` whose parent attribute
    is not the same object as the ``sys.modules`` entry.

    The diagnostic form of the invariant.  An empty list is the healthy state.
    """
    bad = []
    for key in sorted(k for k in list(sys.modules) if k.startswith(prefix)):
        module = sys.modules.get(key)
        if module is None:
            continue
        parent_name, _, leaf = key.rpartition(".")
        parent = sys.modules.get(parent_name)
        if parent is None:
            continue
        if getattr(parent, leaf, None) is not module:
            bad.append(key)
    return bad
