"""RETINA worker-boundary guards (NR-VG-RETINA-GUARDS).

Slice 1 of the G0 receipt, section 11 (docs/reviews/opencv51-gpu-g0-receipt-2026-11-07.md).
ADR-0002 (PROPOSED) lets an optional CUDA backend land in the RETINA worker tree; these
guards pin what such a backend can never be reached from. Every check parses source with
``ast``: nothing under ``retina/`` or ``installer/`` is imported or executed, and the file
needs no cv2, numpy, OpenImageIO or hou, so it runs in stock CI.

* ``test_in_host_retina_modules_cannot_reach_a_backend``: the static import closure of the
  four modules the Houdini host loads (``retina/__init__.py``, ``t0.py``, ``events.py``,
  ``exr_header.py``) stays inside that set plus the standard library. Relative imports,
  ``from . import x``, ``import retina.x``, function-level and conditional imports all
  count. Any dynamic-import or exec surface in those four files fails it outright, because
  a static closure cannot see through one.
* ``test_retina_worker_tree_imports_no_hou``: no module under ``retina/`` imports ``hou``
  at any indentation; aliased, conditional and string-named dynamic forms included.
* ``test_host_payload_ships_no_new_retina_module``: the ``retina/`` entries of
  ``RUNTIME_FILES`` in ``installer/build_payload.py`` equal today's exact eight, no other
  path literal in that file names ``retina``, and no runtime tree covers ``retina/``. A
  node that changes the host payload on purpose updates ``_HOST_PAYLOAD_RETINA_FILES`` in
  the same commit.

``harness/vision/retina_guards/run_mutations.py`` proves each guard can fail; its
``mutation_receipt.json`` pins this file by sha256, so any edit here means a re-run.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PACKAGE = "retina"
_PAYLOAD = "installer/build_payload.py"

# Module name -> repo-relative file, for every RETINA module the Houdini host loads.
_IN_HOST = {
    "retina": "retina/__init__.py",
    "retina.t0": "retina/t0.py",
    "retina.events": "retina/events.py",
    "retina.exr_header": "retina/exr_header.py",
}

# Today's retina/ entries of RUNTIME_FILES in installer/build_payload.py.
_HOST_PAYLOAD_RETINA_FILES = frozenset({
    "retina/__init__.py", "retina/events.py", "retina/exr_header.py", "retina/t0.py",
    "retina/t1.py", "retina/ingest.py", "retina/qc_profiles.py", "retina/qc_profiles.toml",
})

_STDLIB = frozenset(sys.stdlib_module_names) | frozenset(sys.builtin_module_names)

# Dynamic import and exec surfaces. In an in-host module any reference to one fails the
# first guard, called or not, because a static closure cannot see through it.
_DYNAMIC_NAMES = frozenset({"__import__", "import_module", "exec", "eval"})
_DYNAMIC_ATTRS = frozenset({
    "__import__", "import_module", "exec_module", "load_module", "module_from_spec",
    "spec_from_file_location", "spec_from_loader", "resolve_name", "run_module", "run_path",
})
_DYNAMIC_STRINGS = frozenset({"__import__", "import_module"})  # getattr(module, "...") forms

# A path literal naming the retina tree: "retina", "retina/x", "a/retina/b", "retina\\x".
_RETINA_PATH = re.compile(r"(?:^|[/\\])retina(?:$|[/\\])")
_BACKEND_PROBE = "retina/backend_cuda.py"  # the worker module ADR-0002 proposes


def _parse(rel: str) -> ast.Module:
    return ast.parse((_REPO_ROOT / rel).read_bytes(), filename=rel)


def _package_attributes(tree: ast.Module) -> set[str]:
    """Names bound at module level of a package ``__init__``: module-level if, try and
    with blocks count; def, class, lambda and comprehension scopes do not."""
    names: set[str] = set()
    pending: list[ast.AST] = list(tree.body)
    scopes = (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            continue
        if isinstance(node, scopes):
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(a.asname or a.name.partition(".")[0] for a in node.names)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        pending.extend(ast.iter_child_nodes(node))
    return names


def _from_base(node: ast.ImportFrom, rel: str) -> str | None:
    """The absolute module a ``from`` import reads; None when it climbs above the
    top-level package."""
    if not node.level:
        return node.module or ""
    package = rel[: -len(".py")].split("/")[:-1]  # containing package, module or __init__
    keep = len(package) - (node.level - 1)
    if keep < 1:
        return None
    base = ".".join(package[:keep])
    return f"{base}.{node.module}" if node.module else base


def _in_host_breaches(rel: str, tree: ast.Module, package_attrs: set[str]) -> list[str]:
    out: list[str] = []

    def edge(line: int, target: str) -> None:
        top = target.partition(".")[0]
        if top == _PACKAGE:
            if target not in _IN_HOST:
                out.append(f"{rel}:{line} reaches {target}, outside the in-host set")
        elif top not in _STDLIB:
            out.append(f"{rel}:{line} imports {target}, neither in-host RETINA nor stdlib")

    def package_member(line: int, name: str) -> None:
        # ``from retina import name``: a submodule when one exists on disk, otherwise an
        # attribute bound in retina/__init__.py; a name that is neither is unresolved and
        # fails too (a module this branch does not have yet is still out of bounds).
        sub = f"{_PACKAGE}.{name}"
        if sub in _IN_HOST:
            return
        pkg = _REPO_ROOT / _PACKAGE
        if (pkg / f"{name}.py").exists() or (pkg / name).is_dir() or name not in package_attrs:
            out.append(f"{rel}:{line} reaches {sub}, outside the in-host set")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                edge(node.lineno, alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = _from_base(node, rel)
            if base is None:
                out.append(f"{rel}:{node.lineno} relative import climbs out of the {_PACKAGE} package")
                continue
            edge(node.lineno, base)
            if base == _PACKAGE:
                for alias in node.names:
                    if alias.name == "*":
                        out.append(f"{rel}:{node.lineno} star import from {_PACKAGE} cannot be closed statically")
                    else:
                        package_member(node.lineno, alias.name)
        elif isinstance(node, ast.Name) and node.id in _DYNAMIC_NAMES:
            out.append(f"{rel}:{node.lineno} dynamic import or exec surface {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in _DYNAMIC_ATTRS:
            out.append(f"{rel}:{node.lineno} dynamic import or exec surface .{node.attr}")
        elif isinstance(node, ast.alias) and node.name.rpartition(".")[2] in _DYNAMIC_ATTRS:
            out.append(f"{rel}:{node.lineno} dynamic import or exec surface {node.name}")
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
              and node.value in _DYNAMIC_STRINGS):
            out.append(f"{rel}:{node.lineno} dynamic import or exec surface {node.value!r}")
    return out


def test_in_host_retina_modules_cannot_reach_a_backend():
    package_attrs = _package_attributes(_parse(_IN_HOST[_PACKAGE]))
    breaches = [b for rel in sorted(_IN_HOST.values())
                for b in _in_host_breaches(rel, _parse(rel), package_attrs)]
    # Every edge out of the four lands back in the four or on a stdlib leaf, so the
    # closure is the four plus the stdlib; the first edge anywhere else is a breach.
    assert not breaches, "in-host RETINA import closure breached: " + " | ".join(breaches)


def _is_hou(name: str | None) -> bool:
    return name == "hou" or (name or "").startswith("hou.")


def _hou_imports(rel: str, tree: ast.Module) -> list[str]:
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            hits += [f"{rel}:{node.lineno} import {a.name}" for a in node.names if _is_hou(a.name)]
        elif isinstance(node, ast.ImportFrom):
            if not node.level and _is_hou(node.module):
                hits.append(f"{rel}:{node.lineno} from {node.module} import ...")
            hits += [f"{rel}:{node.lineno} from {'.' * node.level}{node.module or ''} import hou"
                     for a in node.names if a.name == "hou"]
        elif isinstance(node, ast.Call):
            func = node.func
            called = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if called in ("__import__", "import_module"):
                args = list(node.args[:1]) + [k.value for k in node.keywords if k.arg == "name"]
                hits += [f"{rel}:{node.lineno} {called}({a.value!r})" for a in args
                         if isinstance(a, ast.Constant) and isinstance(a.value, str) and _is_hou(a.value)]
    return hits


def test_retina_worker_tree_imports_no_hou():
    rels = sorted(p.relative_to(_REPO_ROOT).as_posix()
                  for p in (_REPO_ROOT / _PACKAGE).rglob("*.py"))
    expected = set(_IN_HOST.values()) | {"retina/t1.py"}
    assert expected <= set(rels), f"retina/ is not where this guard looks: missing {sorted(expected - set(rels))}"
    hits = [h for rel in rels for h in _hou_imports(rel, _parse(rel))]
    assert not hits, "retina/ imports hou: " + " | ".join(hits)


def _literal_elements(node: ast.AST | None) -> list[ast.expr] | None:
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in ("set", "frozenset", "tuple", "list")
            and len(node.args) == 1 and not node.keywords):
        node = node.args[0]
    return list(node.elts) if isinstance(node, (ast.Set, ast.List, ast.Tuple)) else None


def _module_value(tree: ast.Module, name: str) -> ast.AST | None:
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            targets = stmt.targets
        elif isinstance(stmt, ast.AnnAssign):
            targets = [stmt.target]
        else:
            continue
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            return stmt.value
    return None


def test_host_payload_ships_no_new_retina_module():
    tree = _parse(_PAYLOAD)
    problems: list[str] = []
    # One literal definition each, never re-bound or grown in place; otherwise the checks
    # below would read a value the installer does not ship.
    for name in ("RUNTIME_FILES", "RUNTIME_TREES"):
        binds = [n.lineno for n in ast.walk(tree)
                 if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Store)]
        grows = [n.lineno for n in ast.walk(tree)
                 if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                 and n.value.id == name and n.attr in ("add", "update")]
        if len(binds) != 1 or grows:
            problems.append(f"{_PAYLOAD}: {name} bound at lines {binds} and grown at lines "
                            f"{grows}; expected one literal definition")
    files = _literal_elements(_module_value(tree, "RUNTIME_FILES"))
    trees = _literal_elements(_module_value(tree, "RUNTIME_TREES"))
    assert files is not None and trees is not None, (
        f"{_PAYLOAD}: RUNTIME_FILES or RUNTIME_TREES is no longer a literal collection; "
        "update this guard with it")
    declared = [e for e in files if isinstance(e, ast.Constant) and isinstance(e.value, str)
                and e.value.startswith("retina/")]
    shipped = {e.value for e in declared}
    if shipped != _HOST_PAYLOAD_RETINA_FILES:
        problems.append(f"RUNTIME_FILES retina/ entries changed: added "
                        f"{sorted(shipped - _HOST_PAYLOAD_RETINA_FILES)}, removed "
                        f"{sorted(_HOST_PAYLOAD_RETINA_FILES - shipped)}")
    declared_ids = {id(e) for e in declared}
    stray = [f"{_PAYLOAD}:{n.lineno} {n.value!r}" for n in ast.walk(tree)
             if isinstance(n, ast.Constant) and isinstance(n.value, str)
             and id(n) not in declared_ids and _RETINA_PATH.search(n.value)]
    if stray:
        problems.append("retina path literal outside the RUNTIME_FILES entries: " + ", ".join(stray))
    covering = [ast.unparse(e) for e in trees
                if not (isinstance(e, ast.Constant) and isinstance(e.value, str))
                or _BACKEND_PROBE.startswith(e.value)]
    if covering:
        problems.append(f"RUNTIME_TREES entries that cover or hide retina/: {covering}")
    assert not problems, "host payload retina/ allowlist breached: " + " | ".join(problems)
