"""The third-party imports the shipped code makes that the payload does not carry, classified.

Why this exists: on the development machine a .pth file in Houdini 22.0.400's own site-packages
appends the checkout's ``.hython_deps`` folder to every Houdini Python's search path. An import
of a package the payload does not carry therefore still works on that machine, and only a clean
seat finds out (2026-11-09: the installed 5.99.0 seat loaded orjson from that folder).

Shipped means what ``installer/build_payload.py`` ships: its ``permitted()`` rule over the tracked
files, the same oracle the builder uses, never a second copy. SYNAPSE's own code is every shipped
``.py`` file outside ``python/synapse/_vendor``. Carried means one of:

* the standard library, or a first-party module of the payload;
* ``python/synapse/_vendor`` plus the build-time wheels in ``build_payload.WHEELS``;
* Moneta under ``dependencies/`` (added at build time, so named here);
* Houdini's own Python, listed in ``HOUDINI_PROVIDED`` (CI has no Houdini to look at).

Each remaining name must appear in ``UNSHIPPED`` with a classification, and no import site of
one may run at module import time without a guard. Literal ``importlib.import_module`` and
``__import__`` calls count; computed module names cannot be seen statically. The Python embedded
in the shipped .pypanel and .shelf files imports only sys, os, traceback, synapse, synapse_shelf
and PySide6/PySide2, and is not scanned.
"""
from __future__ import annotations

import ast
import functools
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_INSTALLER = str(ROOT / "installer")
sys.path.insert(0, _INSTALLER)
try:
    import build_payload  # noqa: E402 -- constants and functions only, no import-time effects
finally:
    sys.path.remove(_INSTALLER)

VENDOR = "python/synapse/_vendor/"

# Names SYNAPSE's own code imports that Houdini's Python provides. Listed from the
# python313/lib/site-packages, site-packages-forced and houdini/python3.13libs folders of a
# Houdini 22.0.400 install, and the python311 equivalents of 21.0.773, on 2026-11-09.
HOUDINI_PROVIDED = frozenset({
    "hou", "hdefereval", "hwebserver", "husd", "pdg", "pdgjob", "pxr", "PySide6",
    "numpy", "psutil", "PIL", "OpenImageIO", "cryptography",
})

# build_payload copies the Moneta bundle to dependencies/moneta/ and the native artifact to
# dependencies/moneta-native/ at build time; neither is a tracked file.
PAYLOAD_DEPENDENCIES = frozenset({"moneta", "moneta_native"})

# "optional": every site is guarded by try/except ImportError, is a fallback branch inside
#             such a handler, or is type-checking only. A clean seat runs without it.
# "path:<p>": imported inside a function on one path only, never at module import.
UNSHIPPED = {
    "orjson": "optional",                # 6 sites; stdlib json is the fallback (wire behaviour differs)
    "xxhash": "optional",                # routing cache keys
    "faiss": "optional",                 # Scout dense index
    "onnxruntime": "optional",           # local embedding model
    "tokenizers": "optional",            # local embedding model
    "cv2": "optional",                   # RETINA t1
    "pyexr": "optional",                 # frame evaluator
    "oiio": "optional",                  # alternate OpenImageIO module name
    "qtpy": "optional",                  # panel Qt shim fallback
    "PySide2": "optional",               # pre-PySide6 Houdini fallback
    "sentence_transformers": "path:dense-retrieval",  # scout._load_embedder catches ImportError
    "hanish": "path:loop",               # loop worker subprocess, from the loop's source_root
    "src": "path:loop",                  # loop worker subprocess, from the loop's source_root
}

_CATCHES = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}


@functools.lru_cache(maxsize=None)
def _shipped_files():
    """Tracked files the payload ships, exactly as build_payload.build() selects them."""
    try:
        out = subprocess.run(["git", "-c", "safe.directory=" + ROOT.as_posix(), "-C", str(ROOT),
                              "ls-files", "-z"], capture_output=True, check=True, timeout=60).stdout
        names = [n for n in out.decode("utf-8").split("\0") if n]
    except (OSError, subprocess.SubprocessError):  # no git: walk the payload's own trees
        names = [p.relative_to(ROOT).as_posix()
                 for tree in build_payload.RUNTIME_TREES for p in (ROOT / tree).rglob("*")
                 if p.is_file()]
        names += [name for name in build_payload.RUNTIME_FILES if (ROOT / name).is_file()]
    return tuple(sorted(n for n in names if build_payload.permitted(n)))


def _catches_import_error(handler):
    if handler.type is None:
        return True
    kinds = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any((k.attr if isinstance(k, ast.Attribute) else getattr(k, "id", None)) in _CATCHES
               for k in kinds)


def _is_type_checking(test):
    return (test.attr if isinstance(test, ast.Attribute) else getattr(test, "id", None)) == "TYPE_CHECKING"


def _sites(rel, source):
    """(top-level name, line, kind) for every absolute import; kind is one of
    module-level, lazy, guarded, fallback, type-only."""
    found = []

    def kind(state):
        if state["type_only"]:
            return "type-only"
        if state["guarded"]:
            return "guarded"
        if state["fallback"]:
            return "fallback"
        return "lazy" if state["function"] else "module-level"

    def visit(node, state):
        for field, value in ast.iter_fields(node):
            for child in value if isinstance(value, list) else [value]:
                if not isinstance(child, ast.AST):
                    continue
                inner = dict(state)
                if isinstance(node, ast.Try) or type(node).__name__ == "TryStar":
                    if field == "body" and any(_catches_import_error(h) for h in node.handlers):
                        inner["guarded"] = True
                if isinstance(node, ast.ExceptHandler) and field == "body" and _catches_import_error(node):
                    inner["fallback"] = True
                if isinstance(node, ast.If) and field == "body" and _is_type_checking(node.test):
                    inner["type_only"] = True
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    inner["function"] = True
                if isinstance(child, ast.Import):
                    found.extend((a.name.split(".")[0], child.lineno, kind(inner)) for a in child.names)
                elif isinstance(child, ast.ImportFrom) and not child.level and child.module:
                    found.append((child.module.split(".")[0], child.lineno, kind(inner)))
                elif (isinstance(child, ast.Call) and child.args
                      and isinstance(child.args[0], ast.Constant) and isinstance(child.args[0].value, str)
                      and (child.func.attr if isinstance(child.func, ast.Attribute)
                           else getattr(child.func, "id", None)) in ("import_module", "__import__")):
                    found.append((child.args[0].value.split(".")[0], child.lineno, kind(inner)))
                visit(child, inner)

    visit(ast.parse(source, filename=rel),
          {"guarded": False, "fallback": False, "type_only": False, "function": False})
    return found


def _top_level_names(shipped, base):
    """Modules and regular packages directly under ``base`` in the shipped file list."""
    names = set()
    for rel in shipped:
        if not rel.startswith(base):
            continue
        parts = rel[len(base):].split("/")
        if len(parts) == 1 and parts[0].endswith(".py"):
            names.add(parts[0][:-3])
        elif len(parts) == 2 and parts[1] == "__init__.py":
            names.add(parts[0])
    return names


def _carried(shipped):
    first_party = set()
    # The payload's import roots: python/ and the root are on PYTHONPATH (installer
    # registration), host/ is inserted by handlers_cache.py, scripts/python by Houdini.
    for base in ("python/", "", "host/", "houdini/scripts/python/"):
        first_party |= _top_level_names(shipped, base)
    vendored = _top_level_names(shipped, VENDOR)
    vendored |= {wheel.split("-")[0].lower() for wheel in build_payload.WHEELS}
    stdlib = set(sys.stdlib_module_names) | set(sys.builtin_module_names)
    return stdlib | first_party | vendored | PAYLOAD_DEPENDENCIES | HOUDINI_PROVIDED


@functools.lru_cache(maxsize=None)
def _unshipped_sites():
    shipped = _shipped_files()
    carried = _carried(shipped)
    sites = {}
    for rel in shipped:
        if not rel.endswith(".py") or rel.startswith(VENDOR):
            continue
        directory = (ROOT / rel).parent
        for top, line, kind in _sites(rel, (ROOT / rel).read_bytes()):
            if top in carried:
                continue
            # A script-mode import of a sibling file (farm/native_driver.py -> package).
            if (directory / f"{top}.py").is_file() or (directory / top / "__init__.py").is_file():
                continue
            sites.setdefault(top, []).append((rel, line, kind))
    return sites


def test_the_scan_sees_the_shipped_tree():
    shipped = _shipped_files()
    assert "python/synapse/core/protocol.py" in shipped
    assert "mcp_server.py" not in shipped  # the stdio MCP server is not part of the payload
    assert ("python/synapse/core/protocol.py", "guarded") in {
        (rel, kind) for rel, _line, kind in _unshipped_sites().get("orjson", [])}


def test_no_unshipped_package_is_needed_at_import_time():
    offenders = [f"{rel}:{line} imports {top}"
                 for top, rows in sorted(_unshipped_sites().items())
                 for rel, line, kind in rows if kind == "module-level"]
    assert not offenders, (
        "a module-level import of a package the payload does not carry fails a clean seat at "
        "import time (and passes on the development machine, whose Houdini Python can see the "
        "checkout's .hython_deps): " + "; ".join(offenders))


def test_the_unshipped_import_map_is_current():
    observed = set(_unshipped_sites())
    assert observed == set(UNSHIPPED), (
        f"new, unclassified: {sorted(observed - set(UNSHIPPED))}; "
        f"no longer imported: {sorted(set(UNSHIPPED) - observed)}")


def test_optional_unshipped_imports_stay_guarded():
    sites = _unshipped_sites()
    unguarded = [f"{rel}:{line} imports {top} ({kind})"
                 for top, kind_of in sorted(UNSHIPPED.items()) if kind_of == "optional"
                 for rel, line, kind in sites.get(top, [])
                 if kind not in ("guarded", "fallback", "type-only")]
    assert not unguarded, "an optional unshipped import lost its guard: " + "; ".join(unguarded)
