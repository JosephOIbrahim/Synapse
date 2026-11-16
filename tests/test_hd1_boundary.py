"""HD1 boundary (SPEC 2.1, 10; design 8.6): the physical package stays pure and dormant.

The four pure modules and the package ``__init__`` import neither Houdini nor
OpenUSD, touch no network and no file at import, register no tool, and nothing
outside the package imports it. The fixture and the HD1 tests never earn the
``needs_houdini`` marker and never evict the resident ``hou``. Every forbidden
token below is assembled from pieces, so this file never carries one itself.
"""
from __future__ import annotations

import ast
import builtins
import importlib.util
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
from unittest.mock import patch

import pytest

from synapse.mcp import _tool_registry as registry
from synapse.worldlabs import physical as hd1_physical

_REPO = Path(__file__).resolve().parents[1]
_TESTS = Path(__file__).resolve().parent
_PACKAGE = _REPO / "python" / "synapse" / "worldlabs" / "physical"
_MODULES = ("__init__", "depth", "level", "scale", "cloud")
_FORBIDDEN_ROOTS = frozenset({"hou", "pxr", "hdefereval", "pdg", "PySide2", "PySide6", "toolutils"})


def _source(name):
    return (_PACKAGE / (name + ".py")).read_text(encoding="utf-8")


def _hd1_test_files():
    return sorted(_TESTS.glob("test_hd1_*.py"))


def test_the_tree_under_test_is_this_checkout():
    """SR1 M2: the editable install points at the primary checkout; this run must read the worktree."""
    root = (_REPO / "python").resolve()
    for module in (hd1_physical, sys.modules["synapse.worldlabs.physical.depth"],
                   sys.modules["synapse.worldlabs.physical.level"],
                   sys.modules["synapse.worldlabs.physical.scale"],
                   sys.modules["synapse.worldlabs.physical.cloud"]):
        assert Path(module.__file__).resolve().is_relative_to(root), module.__name__
    assert Path(hd1_physical.__file__).resolve().parent == _PACKAGE.resolve()
    assert sorted(p.stem for p in _PACKAGE.glob("*.py")) == sorted(_MODULES)


def test_pure_modules_never_import_houdini_or_usd():
    for name in _MODULES:
        tree = ast.parse(_source(name))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in _FORBIDDEN_ROOTS, (name, alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    assert node.module.split(".")[0] not in _FORBIDDEN_ROOTS, (name, node.module)
                else:
                    assert node.level <= 2, (name, node.lineno)   # inside synapse.worldlabs only
            elif isinstance(node, ast.Call):
                func = node.func
                dynamic = (isinstance(func, ast.Name) and func.id in {"__import__", "exec", "eval"}) or (
                    isinstance(func, ast.Attribute) and func.attr in {"import_module", "__import__"})
                assert not dynamic, (name, node.lineno)


def test_pure_modules_import_under_a_houdini_network_and_file_guard():
    """Execute each file afresh while Houdini/Qt imports, sockets and file I/O all raise.

    The pattern of test_atlas_scaffold.py's import test. ``"hou" in sys.modules`` cannot
    be the check (the canonical fake is resident and evicting it is banned), so the
    check is that no new top-level module appears while the files execute.
    """
    real_import = builtins.__import__

    def guard(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name.split(".")[0] in _FORBIDDEN_ROOTS:
            raise AssertionError("forbidden import: " + name)
        return real_import(name, globals, locals, fromlist, level)

    def refuse(*args, **kwargs):
        raise AssertionError("network or file access at import")

    before = {name.split(".")[0] for name in sys.modules}
    executed = {}
    with patch.dict(sys.modules), \
            patch.object(socket, "socket", side_effect=refuse), \
            patch("builtins.open", side_effect=refuse), \
            patch.object(Path, "open", side_effect=refuse), \
            patch.object(Path, "mkdir", side_effect=refuse), \
            patch.object(Path, "write_text", side_effect=refuse), \
            patch.object(Path, "write_bytes", side_effect=refuse), \
            patch("builtins.__import__", side_effect=guard):
        for name in ("depth", "level", "scale", "cloud"):
            probe = "synapse.worldlabs.physical._hd1_import_probe_" + name
            spec = importlib.util.spec_from_file_location(probe, _PACKAGE / (name + ".py"))
            fresh = importlib.util.module_from_spec(spec)
            sys.modules[probe] = fresh
            spec.loader.exec_module(fresh)
            executed[name] = sorted(vars(fresh))
        # The package itself, afresh: this re-executes all four modules as its submodules too.
        package = "synapse.worldlabs._hd1_import_probe_physical"
        spec = importlib.util.spec_from_file_location(package, _PACKAGE / "__init__.py",
                                                      submodule_search_locations=[str(_PACKAGE)])
        fresh = importlib.util.module_from_spec(spec)
        sys.modules[package] = fresh
        spec.loader.exec_module(fresh)
        executed["__init__"] = sorted(vars(fresh))
        submodules = sorted(n for n in sys.modules if n.startswith(package + "."))
        new_roots = {name.split(".")[0] for name in sys.modules} - before
    assert new_roots == set(), sorted(new_roots)
    assert all(executed.values()) and set(executed) == set(_MODULES)
    assert submodules == sorted(package + "." + m for m in ("cloud", "depth", "level", "scale"))


def test_importing_the_package_registers_nothing():
    def snapshot():
        return {
            "TOOL_DEFS": len(registry.TOOL_DEFS),
            "TOOL_NAMES": list(registry.TOOL_NAMES),
            "TOOL_DISPATCH": sorted(registry.TOOL_DISPATCH),
            "TOOL_JSON": sorted(registry.TOOL_JSON),
            "PENDING_TOOL_DEFS": list(registry.PENDING_TOOL_DEFS),
            "PENDING_TOOL_REASONS": dict(registry.PENDING_TOOL_REASONS),
            "PENDING_TOOL_NAMES": list(registry.PENDING_TOOL_NAMES),
        }

    before = snapshot()
    with patch.dict(sys.modules):
        name = "synapse.worldlabs._hd1_physical_fresh"
        spec = importlib.util.spec_from_file_location(name, _PACKAGE / "__init__.py",
                                                      submodule_search_locations=[str(_PACKAGE)])
        fresh = importlib.util.module_from_spec(spec)
        sys.modules[name] = fresh
        spec.loader.exec_module(fresh)
        fresh_all = list(fresh.__all__)
        fresh_submodules = sorted(n for n in sys.modules if n.startswith(name + "."))
    assert snapshot() == before
    assert registry.PENDING_TOOL_DEFS == [] == registry.PENDING_TOOL_NAMES
    assert registry.PENDING_TOOL_REASONS == {}
    assert not [n for n in registry.TOOL_NAMES if "hd1" in n.lower() or "physical" in n.lower()]
    assert fresh_all == list(hd1_physical.__all__)
    assert fresh_submodules == sorted(name + "." + m for m in ("cloud", "depth", "level", "scale"))
    # Exports only: the package body is its docstring, imports and __all__, nothing that runs.
    body = ast.parse(_source("__init__")).body
    for node in body:
        is_docstring = isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
        is_import = isinstance(node, ast.ImportFrom) and node.level in (0, 1)
        is_all = isinstance(node, ast.Assign) and [t.id for t in node.targets] == ["__all__"]
        assert is_docstring or is_import or is_all, node.lineno
    exported = {name for name in hd1_physical.__all__}
    assert len(exported) == len(hd1_physical.__all__)
    assert all(hasattr(hd1_physical, name) for name in exported)


def test_nothing_outside_the_package_imports_it():
    pattern = re.compile(r"worldlabs\.physical|from \.+physical\b|\bimport physical\b")
    files = [p for p in (_REPO / "python").rglob("*.py") if _PACKAGE not in p.parents]
    for folder in ("shared", "host", "scripts"):
        files += sorted((_REPO / folder).rglob("*.py"))
    files += sorted(_REPO.glob("*.py"))
    importers = [p.relative_to(_REPO).as_posix() for p in files
                 if pattern.search(p.read_text(encoding="utf-8", errors="ignore"))]
    assert importers == []


def test_package_text_keeps_the_repo_pins():
    spatial = "synapse" + ".spatial"
    tokens = (spatial, "synapse" + "_spatial_", "SYNAPSE" + "_SPATIAL_LANE", "os." + "environ",
              "get" + "env", "HTTPS" + "Connection", "url" + "lib", "sock" + "et")
    jsonrpc_code = re.compile("-" + "32" + r"\d{3}")
    for name in _MODULES:
        text = _source(name)
        for token in tokens:
            assert token not in text, (name, token)
        assert not jsonrpc_code.search(text), name
        for number, line in enumerate(text.splitlines(), 1):
            assert not line.strip().startswith("print" + "("), (name, number)
    # The same pins over the fixture and the HD1 tests, minus the package-only network words.
    for path in [_TESTS / "fixtures" / "hd1_scene.py", *_hd1_test_files()]:
        text = path.read_text(encoding="utf-8")
        for token in tokens[:5]:
            assert token not in text, (path.name, token)
        assert not jsonrpc_code.search(text), path.name


def _evicts_hou(tree):
    """The three eviction idioms test_hou_reimport_guard.py bans: del, pop and delitem of 'hou'."""
    def is_sys_modules_hou(node):
        return (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute)
                and node.value.attr == "modules" and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "sys" and isinstance(node.slice, ast.Constant)
                and node.slice.value == "hou")

    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Delete) and any(is_sys_modules_hou(t) for t in node.targets):
            found.append(node.lineno)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            args = [a.value for a in node.args if isinstance(a, ast.Constant)]
            if node.func.attr in ("pop", "delitem", "__delitem__") and "hou" in args:
                found.append(node.lineno)
    return found


def test_fixture_and_hd1_tests_stay_off_the_houdini_marker():
    from conftest import module_runtime_requirement

    paths = [_TESTS / "fixtures" / "hd1_scene.py", *_hd1_test_files()]
    names = {p.name for p in paths}
    assert {"hd1_scene.py", "test_hd1_fixture.py", "test_hd1_depth.py", "test_hd1_level.py",
            "test_hd1_scale.py", "test_hd1_cloud.py", "test_hd1_boundary.py"} <= names
    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert module_runtime_requirement(source) is None, path.name
        assert _evicts_hou(ast.parse(source)) == [], path.name
    # The detector is live: it does see an eviction and a module-level Houdini import.
    planted = "import sys\n" + "sys.modules." + "pop('hou', None)\n"
    assert _evicts_hou(ast.parse(planted)) == [2]
    assert module_runtime_requirement("import " + "hou\n") == "hou"


# --- review R-1, R-2 and R-4 (2026-11-15) --------------------------------------------------

# The package's import graph, pinned exactly (R-1, R-4). Design 4 drew "depth -> (none)", but depth
# imports the contract's ContractError and mask_depth, which design 3.1 and claim HD-05 need.
_IMPORT_GRAPH = {
    "__init__": {"__future__", ".depth", ".level", ".scale", ".cloud"},
    "depth": {"__future__", "dataclasses", "math", "numbers", "typing", "numpy", "..atlas_contracts"},
    "level": {"__future__", "dataclasses", "math", "numbers", "typing", "numpy", "..atlas_contracts",
              "..importer"},
    "scale": {"__future__", "dataclasses", "math", "numbers", "types", "typing", "..atlas_contracts",
              ".level"},
    "cloud": {"__future__", "dataclasses", "math", "numbers", "typing", "numpy", "..atlas_contracts",
              ".level", ".scale"},
}
# What the package takes from the World Labs code outside itself: these names, never a module.
_OUTSIDE_NAMES = {
    "depth": {"..atlas_contracts": {"ContractError", "mask_depth"}},
    "level": {"..atlas_contracts": {"ContractError"}, "..importer": {"ground_transform"}},
    "scale": {"..atlas_contracts": {"ContractError", "PosedRGBDFrame"}},
    "cloud": {"..atlas_contracts": {"ContractError", "PosedRGBDFrame"}},
}
_HD1_MODULE_NAMES = sorted("synapse.worldlabs.physical" + tail
                           for tail in ("", ".cloud", ".depth", ".level", ".scale"))


def _imports(source):
    """{module: names taken from it} over every Import and ImportFrom at any depth; relative names keep their dots."""
    found = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.setdefault(alias.name, set())
        elif isinstance(node, ast.ImportFrom):
            found.setdefault("." * node.level + (node.module or ""), set()).update(a.name for a in node.names)
    return found


def test_the_import_graph_is_exactly_the_pinned_one():
    """R-1 (2026-11-15): an import outside the pinned graph, at any depth of any module, goes red here.

    The runtime checks above start after the registry and the package are resident, so a module that
    reached the registry (or Houdini or OpenUSD through it) at its first import passed them all.
    """
    for name in _MODULES:
        found = _imports(_source(name))
        assert set(found) == _IMPORT_GRAPH[name], (name, sorted(set(found) ^ _IMPORT_GRAPH[name]))
        for outside, names in _OUTSIDE_NAMES.get(name, {}).items():
            assert found[outside] == names, (name, outside, sorted(found[outside] ^ names))
    # The detector is live: a planted import of sys and of the registry are both seen.
    assert set(_imports("import sys\nfrom synapse.mcp import _tool_registry\n")) == {"sys", "synapse.mcp"}


# The FIRST import of the package, in a fresh interpreter (R-1). It runs from stdin with -B, so it
# writes no bytecode. argv: the python tree under test, the mode, the forbidden roots. It inherits
# this process's environment, puts the tree first on sys.path, and prints one marked JSON line.
_FIRST_IMPORT_PROBE = '''
import json
import sys
import types

root, mode, forbidden = sys.argv[1], sys.argv[2], set(sys.argv[3].split(','))
sys.path.insert(0, root)
import synapse.worldlabs
import synapse.worldlabs.atlas_contracts
import synapse.worldlabs.importer
if mode == 'registry_resident':
    import synapse.mcp._tool_registry
import __future__, dataclasses, math, numbers, typing
try:
    import numpy
except ImportError:
    numpy = None

PHYSICAL = 'synapse.worldlabs.physical'


def containers(modules):
    out = {}
    for name, module in sorted(modules.items()):
        if module is None or not name.startswith('synapse') or name.startswith(PHYSICAL):
            continue
        for attr, value in sorted(vars(module).items()):
            if attr.startswith('__'):
                continue
            if isinstance(value, dict):
                out[name + ':' + attr] = sorted((repr(key), id(item)) for key, item in value.items())
            elif isinstance(value, (list, set, frozenset, tuple)):
                out[name + ':' + attr] = len(value)
    return out


def changed(before, after):
    return sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))


class Recorder:
    def __init__(self):
        self.names = []

    def find_spec(self, name, path=None, target=None):
        self.names.append(name)
        return None


assert PHYSICAL not in sys.modules
resident = set(sys.modules)
before = containers(sys.modules)
recorder = Recorder()
sys.meta_path.insert(0, recorder)
import synapse.worldlabs.physical as physical
sys.meta_path.remove(recorder)
after = containers(sys.modules)
control = types.ModuleType('synapse_hd1_probe_control')
control.table = {}
plain = {'synapse_hd1_probe_control': control}
first = containers(plain)
control.table['planted'] = None
record = {
    'file': physical.__file__,
    'mode': mode,
    'numpy': numpy is not None,
    'registry_resident': 'synapse.mcp._tool_registry' in resident,
    'registry_scanned': any(key.startswith('synapse.mcp._tool_registry:') for key in before),
    'containers': len(before),
    'changed': changed(before, after),
    'new_modules': sorted(set(sys.modules) - resident),
    'attempts': sorted(set(recorder.names)),
    'forbidden_attempts': sorted({name for name in recorder.names if name.split('.')[0] in forbidden}),
    'control_changed': changed(first, containers(plain)),
}
print('HD1-FIRST-IMPORT ' + json.dumps(record, sort_keys=True))
'''


def _first_import(mode):
    """Run the probe in a fresh interpreter on this checkout's python tree; return its record."""
    result = subprocess.run(
        [sys.executable, "-B", "-", str(_REPO / "python"), mode, ",".join(sorted(_FORBIDDEN_ROOTS))],
        input=_FIRST_IMPORT_PROBE, cwd=str(_REPO / "python"), capture_output=True, encoding="utf-8",
        errors="replace", timeout=300)
    assert result.returncode == 0, result.stderr[-4000:]
    marked = [line for line in result.stdout.splitlines() if line.startswith("HD1-FIRST-IMPORT ")]
    assert len(marked) == 1, result.stdout[-4000:]
    return json.loads(marked[0][len("HD1-FIRST-IMPORT "):])


@pytest.mark.parametrize("mode", ["registry_resident", "registry_absent"])
def test_first_import_in_a_fresh_interpreter(mode):
    """R-1 (2026-11-15): the FIRST import registers nothing and reaches no module beyond the package's five.

    registry_resident: the MCP registry is loaded first, as in a live session and at the top of this
    file, and every module-level container of every synapse module is compared before and after the
    import, so an idempotent registration made at first import is seen. registry_absent: nothing
    outside the package's own graph is loaded first, so an import that would reach the registry (and
    Houdini or OpenUSD through it) is recorded by a meta-path finder that finds nothing.
    """
    record = _first_import(mode)
    assert Path(record["file"]).resolve().parent == _PACKAGE.resolve()
    assert record["control_changed"] == ["synapse_hd1_probe_control:table"]      # the comparison is live
    assert record["registry_resident"] is record["registry_scanned"] is (mode == "registry_resident")
    assert record["containers"] > 0
    assert record["changed"] == []
    assert record["forbidden_attempts"] == []
    assert [name for name in record["new_modules"] if name.startswith("synapse")] == _HD1_MODULE_NAMES
    assert [name for name in record["attempts"] if name.startswith("synapse")] == _HD1_MODULE_NAMES


def test_without_numpy_every_entry_point_is_blocked_or_pure():
    """R-2 (2026-11-15): hard rule 3 on the real path, in every environment.

    numpy's import is refused while a fresh copy of the package executes and runs, so each module
    takes its ``except ImportError`` branch and holds ``np = None``. The other BLOCKED tests switch
    NUMPY_AVAILABLE off after a normal import, with the real numpy still bound, and five of the six
    HD1 test files skip without numpy. Every input here is plain Python.
    """
    from synapse.worldlabs.atlas_contracts import AssetRef, CameraIntrinsics, CameraPose, PosedRGBDFrame

    real_import = builtins.__import__

    def no_numpy(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name.split(".")[0] == "numpy":
            raise ImportError("numpy refused for this check")
        return real_import(name, globals, locals, fromlist, level)

    digest = "0" * 64
    frame = PosedRGBDFrame(
        "SYNTHETIC-hd1-no-numpy", AssetRef("SYNTHETIC-hd1-no-numpy-rgb", digest, "image/png"),
        AssetRef("SYNTHETIC-hd1-no-numpy-depth", digest, "image/x-exr"),
        AssetRef("SYNTHETIC-hd1-no-numpy-confidence", digest, "image/png"),
        CameraIntrinsics(2, 2, 1.0, 1.0, 1.0, 1.0),
        CameraPose((0.0, 1.5, 0.0), (0.0, 0.0, 0.0, 1.0), "rub", "SYNTHETIC-hd1-no-numpy-world"),
        "linear_exr_half", "top_down", metres_per_unit=None)
    grid = [[1.0, 1.0], [1.0, 1.0]]
    keep = [[True, True], [True, True]]
    package = "synapse.worldlabs._hd1_no_numpy_probe"
    with patch.dict(sys.modules), patch("builtins.__import__", side_effect=no_numpy):
        spec = importlib.util.spec_from_file_location(package, _PACKAGE / "__init__.py",
                                                      submodule_search_locations=[str(_PACKAGE)])
        fresh = importlib.util.module_from_spec(spec)
        sys.modules[package] = fresh
        spec.loader.exec_module(fresh)
        depth, level, scale, cloud = (sys.modules[package + "." + name] for name in ("depth", "level", "scale", "cloud"))
        assert [m.NUMPY_AVAILABLE for m in (depth, level, cloud)] == [False, False, False]
        assert depth.np is None and level.np is None and cloud.np is None
        fields = dict.fromkeys(level.FloorFit.__dataclass_fields__)
        fields.update(status="SUCCESS", normal=(0.0, 1.0, 0.0), offset=-0.925, level_xyzw=(0.0, 0.0, 0.0, 1.0),
                      tilt_deg=0.0, camera_height=3.75, floor_height=0.925, first_row=1, grid_rows=2, seed=1,
                      iterations=1, rows_fraction=0.25, inlier_rel=0.01, min_inlier_fraction=0.3,
                      max_tilt_deg=30.0)
        fit = level.FloorFit(**fields)
        claim = scale.asserted_fixture(0.4, probe="R-2 no-numpy probe")
        framed = scale.apply_claim(frame, claim)
        raw = cloud.RawCloud("SYNTHETIC-hd1-no-numpy", (2, 2), [1], [0], [1.0], [[0.0, 0.0, 0.0]], (0.0, 1.5, 0.0))
        statuses = {
            "condition_depth": depth.condition_depth(grid, [[1.0, 1.0], [1.0, 1.0]]).status,
            "DepthMask.as_dict": depth.condition_depth(grid).as_dict()["status"],
            "above_half_float_difference": depth.above_half_float_difference(grid)["status"],
            "fit_floor": level.fit_floor([[0.0, 0.0, 0.0]], [1], [1.0], grid_rows=2,
                                         camera_position=(0.0, 1.5, 0.0)).status,
            "floor_of": cloud.floor_of(raw).status,
        }
        raising = {
            "rotation_matrix": lambda: level.rotation_matrix((0.0, 0.0, 0.0, 1.0)),
            "unproject_raw": lambda: cloud.unproject_raw(frame, grid, keep),
            "unproject_scaled": lambda: cloud.unproject_scaled(framed, grid, keep),
            "choose_stride": lambda: cloud.choose_stride(keep),
            "footprint_radius": lambda: cloud.footprint_radius([1.0], 1, 1.0),
            "physical_cloud": lambda: cloud.physical_cloud(frame, grid, keep, claim, fit),
            "half_pixel_delta": lambda: cloud.half_pixel_delta(framed, grid, keep),
        }
        for call in raising.values():
            with pytest.raises(level.PhysicalBlocked, match="^BLOCKED: "):
                call()
        # The pure-Python steps work as they do with numpy.
        assert level.smallest_rotation_to_up((0.0, 1.0, 0.0)) == (0.0, 0.0, 0.0, 1.0)
        assert level.normal_angle_deg((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)) == 90.0
        assert level.quaternion_angle_deg((0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, -1.0)) == 0.0
        assert level.ground_offset(0.4, fit) == -0.4 * 0.925
        assert scale.from_camera_height(1.5, fit).value == 1.5 / 3.75
        assert scale.from_reference_length((0.0, 0.0, 0.0), (2.5, 0.0, 0.0), 1.0).value == 1.0 / 2.5
        assert framed.metres_per_unit == 0.4 and scale.unknown_scale().value is None
        with pytest.raises(scale.ScaleRefused):
            scale.require_metric(scale.unknown_scale())
        with pytest.raises(scale.ScaleMethodNotEnabled):
            scale.make_claim("derived:moge2")
    assert statuses == dict.fromkeys(statuses, "BLOCKED")
