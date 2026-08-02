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

THE SECOND COSTUME (R310)
=========================

R307 killed one shape: *plant without binding*.  The sweep that followed found
the class alive in a second, quieter costume — *restore without re-binding*::

    saved = {k: sys.modules.get(k) for k in touched}
    sys.modules.pop("synapse.panel.ws_bridge", None)
    import synapse.panel.ws_bridge as wsb          # importlib binds the NEW
                                                  # module on synapse.panel
    ...
    for k, v in saved.items():
        sys.modules[k] = v                        # <-- only HALF the job again

The fresh import is a *real* one, so importlib does both halves and binds the
throwaway module on the parent.  Restoring only the ``sys.modules`` entry
leaves the parent attribute pointing at the throwaway.  Both halves exist —
they just name **different objects**.

That is worse than the R307 shape in one specific way.  R307 made dotted
resolution *raise*; this makes it **succeed and return the wrong module**.  A
``monkeypatch.setattr("pkg.mod.fn", ...)`` lands on a module nobody reads, the
patch silently does nothing, and the test that relied on it passes or fails for
reasons unrelated to what it is testing.  Measured, not assumed — see
``tests/test_pkg_bootstrap_invariant.py``.

The ambiguous snapshot above hides a second trap: ``sys.modules.get(k)``
returns ``None`` both for *absent* and for this repo's deliberate-absence
sentinel ``sys.modules[k] = None``.  Use :func:`snapshot_modules` /
:func:`restore_modules`, which keep those apart with an explicit ``ABSENT``.

THE RULE
========

If you put a dotted module name into ``sys.modules`` by hand — planting it,
*or putting one back* — bind it on its parent package in the same breath.  Use
the helpers below instead of open-coding it;
``tests/test_pkg_bootstrap_invariant.py`` pins the invariant.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from typing import Iterable, Mapping, Tuple, Union

__all__ = [
    "ABSENT",
    "bind_to_parent",
    "ensure_package",
    "ensure_packages",
    "install_module",
    "load_module",
    "load_modules",
    "rebind_modules",
    "restore_modules",
    "snapshot_modules",
    "swapped_modules",
    "divergent_modules",
]


class _Absent:
    """Sentinel for 'this name was not in sys.modules at all'.

    Distinct from a stored ``None``, which is this repo's *deliberate absence*
    idiom (CPython raises ImportError on a None entry without consulting
    meta_path — see the HOU_REIMPORT_GUARD note in tests/conftest.py). The
    plain ``{k: sys.modules.get(k)}`` snapshot conflates the two and silently
    converts one into the other on restore.
    """

    __slots__ = ()

    def __repr__(self):  # pragma: no cover - debugging aid only
        return "<ABSENT>"


ABSENT = _Absent()

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

    A ``None`` entry is NOT "absent": ``sys.modules[name] = None`` is this
    repo's deliberate-absence idiom (see the fake-residency rule for ``hou``),
    and Python's own import machinery raises ``ImportError`` on it. Silently
    replacing the sentinel with a synthetic package would undo somebody's
    deliberate eviction, so we refuse loudly instead (attack-O crucible nit:
    the first version's ``.get(name) is None`` guard did exactly that).
    """
    if mod_name in sys.modules:
        module = sys.modules[mod_name]
        if module is None:
            raise ImportError(
                f"{mod_name} carries a None sentinel in sys.modules "
                f"(deliberate absence) — refusing to replace it with a "
                f"synthetic package; evict the sentinel first if you mean to")
    else:
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

    Same ``None``-sentinel refusal as :func:`ensure_package` — a deliberate
    eviction is never silently overwritten.
    """
    if mod_name in sys.modules:
        module = sys.modules[mod_name]
        if module is None:
            raise ImportError(
                f"{mod_name} carries a None sentinel in sys.modules "
                f"(deliberate absence) — refusing to load over it; evict the "
                f"sentinel first if you mean to")
    else:
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


def install_module(mod_name: str, module: types.ModuleType) -> types.ModuleType:
    """Install an ALREADY-BUILT ``module`` object at ``mod_name`` and bind it.

    The ``sys.modules.setdefault(name, obj)`` of the raw idiom: an existing
    entry wins, and the result is bound on its parent either way. Use this when
    you hold the module object already (loaded by hand, or a deliberate stub)
    and :func:`load_module` therefore does not apply.

    Same ``None``-sentinel refusal as :func:`ensure_package`.
    """
    if mod_name in sys.modules:
        existing = sys.modules[mod_name]
        if existing is None:
            raise ImportError(
                f"{mod_name} carries a None sentinel in sys.modules "
                f"(deliberate absence) — refusing to install over it; evict "
                f"the sentinel first if you mean to")
        module = existing
    else:
        sys.modules[mod_name] = module
    bind_to_parent(mod_name, module)
    return module


def _unbind_from_parent(mod_name: str) -> None:
    """Remove ``<parent>.<leaf>`` when it currently holds a MODULE.

    Leaving the attribute behind after removing the ``sys.modules`` entry is
    the divergence in its other direction. A NON-module attribute is left
    alone: that is the ordinary ``from pkg.mod import name`` re-export
    shadowing a same-named submodule (production ``synapse.cognitive`` does
    exactly this), and deleting it would break the package to tidy a test.
    """
    parent_name, _, leaf = mod_name.rpartition(".")
    if not parent_name:
        return
    parent = sys.modules.get(parent_name)
    if parent is None:
        return
    attr = getattr(parent, leaf, None)
    if isinstance(attr, types.ModuleType):
        try:
            delattr(parent, leaf)
        except AttributeError:  # pragma: no cover - inherited/read-only attr
            pass


def snapshot_modules(names: Iterable[str]) -> dict:
    """Capture ``sys.modules`` for ``names``, keeping ABSENT distinct from None.

    Feed the result to :func:`restore_modules`. Unlike
    ``{k: sys.modules.get(k) for k in names}`` this does not silently turn a
    missing entry and a deliberate ``None`` sentinel into the same thing.
    """
    return {name: sys.modules.get(name, ABSENT) for name in names}


def restore_modules(saved: Mapping) -> None:
    """Restore a :func:`snapshot_modules` result — BOTH halves.

    For each name:

    * a module object -> put it back in ``sys.modules`` **and re-bind it on its
      parent**, because whatever ran in between almost certainly imported a
      fresh copy and left importlib's binding pointing at that copy;
    * ``ABSENT`` -> remove the entry *and* the parent's module attribute, so a
      name that was absent before is absent both ways after;
    * ``None`` -> restore the deliberate-absence sentinel, and drop the parent
      module attribute (a None entry has no object to bind).
    """
    for name, value in saved.items():
        if value is ABSENT:
            sys.modules.pop(name, None)
            _unbind_from_parent(name)
        elif value is None:
            sys.modules[name] = None
            _unbind_from_parent(name)
        else:
            sys.modules[name] = value
            bind_to_parent(name, value)


def rebind_modules(names: Iterable[str]) -> None:
    """Re-assert ``sys.modules[name] is <parent>.<leaf>`` for each name.

    For restores this module does NOT own — chiefly
    ``monkeypatch.setitem/delitem(sys.modules, ...)``, whose ``undo()`` puts the
    original object back in ``sys.modules`` and stops there. There is no hook
    into monkeypatch's teardown, so the reconciliation runs after it, from an
    autouse fixture (autouse fixtures set up first and therefore finalize
    last). Names that are absent, or hold the None sentinel, are skipped.
    """
    for name in names:
        module = sys.modules.get(name)
        if isinstance(module, types.ModuleType):
            bind_to_parent(name, module)


# NOTE: an earlier draft of R310 also added a `swapped_modules` context
# manager (snapshot + restore around a block). Every call site that wanted it
# is a generator FIXTURE whose snapshot and restore already straddle a `yield`,
# so none of them could use it — it would have shipped with zero callers. This
# repo deletes mechanisms that have no consumer rather than keeping them for
# later (see the retired router auto-promotion, CLAUDE.md §2.3 / RSI loop F),
# so it is not here. snapshot_modules + restore_modules in a try/finally is the
# supported shape.


def divergent_modules(prefix: str = "synapse.") -> list:
    """Return every ``sys.modules`` key under ``prefix`` whose parent attribute
    diverges from the ``sys.modules`` entry in the way that BREAKS dotted
    resolution: the attribute is missing, or it is a *different module*.

    Deliberately NOT flagged (attack-O crucible: the first version
    false-positived on these, and its "empty list is the healthy state" claim
    was false for this repo):

    * a parent attribute that is a non-module object — the ordinary
      ``from pkg.mod import name`` re-export shadowing a same-named submodule
      (production ``synapse.cognitive`` does this legitimately);
    * a ``None`` sentinel entry (deliberate absence, skipped above).

    So: an empty list means no dotted MODULE binding diverges. It does not
    mean the tree is free of shadows — shadows are legal Python.
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
        attr = getattr(parent, leaf, None)
        if attr is module:
            continue
        if attr is not None and not isinstance(attr, types.ModuleType):
            # Legitimate function/class re-export shadowing the submodule name.
            continue
        bad.append(key)
    return bad
