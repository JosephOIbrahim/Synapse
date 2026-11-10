"""runtime_provenance: the Doctor names code a seat runs from outside its own runtime folder.

Evidence (live readback, 2026-11-09): the installed 5.99.0 seat loaded orjson's compiled module
from the development checkout's ``.hython_deps`` folder. Houdini 22.0.400's own Python carries a
``.pth`` file in its site-packages that appends that folder to every Houdini Python's search path,
so the seat silently ran a package its payload does not ship (orjson is an optional import,
python/synapse/core/protocol.py). Nothing in the Doctor could see it.

The check reads ``sys.modules`` and never imports. A module counts as foreign when its file lies
outside the running SYNAPSE runtime root (a dot-folder under that root is never payload) and
outside Houdini's install folder ($HFS) and Houdini's Python. The Doctor's wire statuses stay
ok / fail / skipped; the panel's Doctor dialog shows ``fail`` as NEEDS ATTENTION.

These tests drive the check with fake modules whose ``__file__`` sits under fake roots in
tmp_path; the relative-name tests use the relative ``__file__`` strings a headless Houdini
reported. Every name that is new in this change is imported inside its test, so on the old code
the tests fail instead of the file failing to collect.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# fake module for the runtime_provenance tests\n", encoding="utf-8")
    return path


def _module(name: str, file) -> ModuleType:
    module = ModuleType(name)
    module.__file__ = str(file)
    return module


@pytest.fixture
def seat(tmp_path):
    """An installed-seat layout: runtime under versions/<id>, Houdini elsewhere, a checkout."""
    runtime = tmp_path / "Programs" / "SYNAPSE" / "versions" / "5.99.0-test"
    hfs = tmp_path / "Houdini 22.0.400"
    inside = {
        "synapse": _touch(runtime / "python" / "synapse" / "__init__.py"),
        "synapse.server.doctor": _touch(runtime / "python" / "synapse" / "server" / "doctor.py"),
        "pydantic": _touch(runtime / "python" / "synapse" / "_vendor" / "pydantic" / "__init__.py"),
        "moneta": _touch(runtime / "dependencies" / "moneta" / "src" / "moneta" / "__init__.py"),
        "shared": _touch(runtime / "shared" / "__init__.py"),
        "mcp_tools_scene": _touch(runtime / "mcp_tools_scene.py"),
    }
    houdini = {
        "numpy": _touch(hfs / "python313" / "lib" / "site-packages" / "numpy" / "__init__.py"),
        "hou": _touch(hfs / "houdini" / "python3.13libs" / "hou.py"),
    }
    return SimpleNamespace(runtime=runtime, hfs=hfs, checkout=tmp_path / "checkout",
                           inside=inside, houdini=houdini, tmp=tmp_path)


def _modules(*groups):
    return {name: _module(name, file) for group in groups for name, file in group.items()}


def _run(seat, modules, sys_path=()):
    from synapse.server.doctor import _check_runtime_provenance
    return _check_runtime_provenance(modules=modules, runtime_root=seat.runtime,
                                     houdini_root=seat.hfs,
                                     sys_path=[str(p) for p in sys_path],
                                     interpreter_roots=[])


def _foreign_names(check):
    return [row["name"] for row in check["result"]["foreign"]]


# -- the two red tests the lane was opened for ------------------------------------------------

def test_flags_a_module_loaded_from_a_hython_deps_folder(seat):
    deps = seat.checkout / ".hython_deps"
    modules = _modules(seat.inside, seat.houdini)
    modules["orjson"] = _module("orjson", _touch(deps / "orjson" / "__init__.py"))
    modules["orjson.orjson"] = _module(
        "orjson.orjson", _touch(deps / "orjson" / "orjson.cp313-win_amd64.pyd"))

    check = _run(seat, modules, sys_path=[seat.runtime / "python", deps])

    assert check["name"] == "runtime_provenance"
    assert check["status"] == "fail", check["detail"]  # the panel shows fail as NEEDS ATTENTION
    assert _foreign_names(check) == ["orjson"]
    row = check["result"]["foreign"][0]
    assert row["modules"] == 2
    assert Path(row["origin"]) == deps
    assert "orjson" in check["detail"] and ".hython_deps" in check["detail"]


def test_stays_ok_when_every_module_lives_under_the_runtime_root(seat):
    modules = _modules(seat.inside)

    check = _run(seat, modules, sys_path=[seat.runtime / "python", seat.runtime])

    assert check["status"] == "ok", check["detail"]
    assert check["result"]["foreign"] == []
    assert check["result"]["checked"] == len(modules)


# -- what counts as inside -------------------------------------------------------------------

def test_houdini_install_modules_are_houdini_own(seat):
    check = _run(seat, _modules(seat.inside, seat.houdini))
    assert check["status"] == "ok", check["detail"]
    assert check["result"]["checked"] == len(seat.inside) + len(seat.houdini)


def test_a_dot_folder_inside_the_runtime_root_is_not_payload(seat):
    """A repo-direct seat's root is the checkout, and .hython_deps sits inside it. The payload
    never ships a dot-folder (installer/build_payload.py), so it still counts as outside."""
    modules = _modules(seat.inside, seat.houdini)
    modules["xxhash"] = _module("xxhash", _touch(seat.runtime / ".hython_deps" / "xxhash" / "__init__.py"))

    check = _run(seat, modules)

    assert check["status"] == "fail", check["detail"]
    assert _foreign_names(check) == ["xxhash"]


def test_first_party_code_from_another_checkout_is_flagged(seat):
    modules = _modules({k: v for k, v in seat.inside.items() if k != "shared"}, seat.houdini)
    modules["shared"] = _module("shared", _touch(seat.checkout / "shared" / "__init__.py"))
    modules["shared.bridge"] = _module("shared.bridge", _touch(seat.checkout / "shared" / "bridge.py"))

    check = _run(seat, modules)

    assert check["status"] == "fail", check["detail"]
    assert _foreign_names(check) == ["shared"]
    assert check["result"]["foreign"][0]["modules"] == 2


def test_the_same_folder_through_dot_dot_segments_is_inside(seat):
    modules = _modules(seat.inside, seat.houdini)
    detour = seat.runtime / "python" / ".." / "python" / "synapse" / "_vendor" / "anyio" / "__init__.py"
    _touch(seat.runtime / "python" / "synapse" / "_vendor" / "anyio" / "__init__.py")
    modules["anyio"] = _module("anyio", detour)

    check = _run(seat, modules)

    assert check["status"] == "ok", check["detail"]


@pytest.mark.skipif(sys.platform != "win32", reason="8.3 short names exist only on Windows")
def test_a_windows_short_path_names_the_same_folder(seat):
    """Houdini's own search path mixes C:/PROGRA~1/... with long forms; one folder, two names."""
    import ctypes

    def short(path):
        buffer = ctypes.create_unicode_buffer(2048)
        size = ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, 2048)
        return buffer.value if 0 < size < 2048 else ""

    numpy_file = seat.houdini["numpy"]
    short_file, short_hfs = short(numpy_file), short(seat.hfs)
    if not short_file or short_file.lower() == str(numpy_file).lower() or not short_hfs:
        pytest.skip("8.3 short names are disabled on this volume")
    from synapse.server.doctor import _check_runtime_provenance

    modules = _modules(seat.inside, seat.houdini)
    modules["numpy"] = _module("numpy", short_file)
    check = _run(seat, modules)
    assert check["status"] == "ok", check["detail"]

    reverse = _check_runtime_provenance(modules=_modules(seat.inside, seat.houdini),
                                        runtime_root=seat.runtime, houdini_root=short_hfs,
                                        sys_path=[], interpreter_roots=[])
    assert reverse["status"] == "ok", reverse["detail"]


# -- what is not third-party, and what is never touched ---------------------------------------

def test_standard_library_and_fileless_entries_are_not_third_party(seat):
    class Tripwire:
        def __getattribute__(self, name):
            raise AssertionError(f"the check touched a non-module entry ({name})")

    elsewhere = seat.tmp / "elsewhere"
    modules = _modules(seat.inside, seat.houdini)
    modules["json"] = _module("json", _touch(elsewhere / "json" / "__init__.py"))
    modules["__main__"] = _module("__main__", _touch(elsewhere / "script.py"))
    namespace = ModuleType("namespace_portion")
    namespace.__file__ = None
    modules["namespace_portion"] = namespace
    modules["blocked_import"] = None
    modules["tripwire"] = Tripwire()

    check = _run(seat, modules)

    assert check["status"] == "ok", check["detail"]
    assert check["result"]["foreign"] == []


#: The ``__file__`` values a Doctor run inside headless Houdini 22.0.400 reported on 2026-11-09
#: (the leg D probe of a seat build of 9cba9a6a). None is an absolute path: PySide6's shiboken
#: support modules report names such as ``shibokensupport/feature.py``, and one ``hou`` module
#: reports ``hou.session``. The check resolved these names against the working folder, so it
#: named PySide6, shibokensupport, __feature__, signature_bootstrap and hou as foreign. The probe
#: records each package's name and one file, so the module names under PySide6 and hou are
#: inferred from those files.
_RELATIVE_FILES = {
    "shibokensupport": "shibokensupport/__init__.py",
    "__feature__": "shibokensupport/feature.py",
    "PySide6.support.__feature__": "shibokensupport/feature.py",
    "signature_bootstrap": "signature_bootstrap.py",
    "hou.session": "hou.session",
}
#: The rule is the form of the name, not these packages: one relative name the probe did not see.
_ALL_RELATIVE_FILES = {**_RELATIVE_FILES, "made_up_embedded": "made_up_embedded/__init__.py"}


def _with_relative_files(seat):
    """The seat's modules, PySide6's own package under $HFS, and every relative name above."""
    modules = _modules(seat.inside, seat.houdini)
    pyside = _touch(seat.hfs / "python313" / "lib" / "site-packages" / "PySide6" / "__init__.py")
    modules["PySide6"] = _module("PySide6", pyside)
    modules.update({name: _module(name, file) for name, file in _ALL_RELATIVE_FILES.items()})
    return modules


@pytest.mark.parametrize("cwd", ["outside_both_roots", "outside_with_those_files_present",
                                 "inside_the_runtime_root"])
def test_a_module_whose_file_is_not_absolute_counts_as_having_no_file(seat, monkeypatch, cwd):
    """A relative ``__file__`` counts as no file, like a built-in: not checked, not unlocated,
    never foreign, wherever the working folder is and whatever lies there. Outside both roots
    the old check read fail; inside the runtime root it read ok but counted the relative names
    as checked runtime files."""
    folder = seat.runtime if cwd == "inside_the_runtime_root" else seat.checkout
    folder.mkdir(parents=True, exist_ok=True)
    if cwd == "outside_with_those_files_present":
        for file in _ALL_RELATIVE_FILES.values():
            _touch(folder / file)
    monkeypatch.chdir(folder)

    check = _run(seat, _with_relative_files(seat))

    assert check["status"] == "ok", check["detail"]
    assert check["result"]["foreign"] == []
    # Only modules whose file has an absolute path count: the seat's, Houdini's and PySide6's own.
    assert check["result"]["checked"] == len(seat.inside) + len(seat.houdini) + 1
    assert check["result"]["unlocated"] == 0


def test_sidefx_labs_beside_houdini_stays_flagged(seat, monkeypatch):
    """Owner ruling (2026-11-10): "Keep SideFX Labs flagged." On the probed machine Labs sits
    beside $HFS, not inside it, and its files have absolute paths, so the relative-name rule
    leaves it foreign. Here the old check named seven packages, the probe's six and one made-up
    relative name; now it names only labutils."""
    seat.checkout.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(seat.checkout)
    labs = seat.tmp / "sidefx_packages" / "SideFXLabs22.0" / "scripts" / "python"
    modules = _with_relative_files(seat)
    modules["labutils"] = _module("labutils", _touch(labs / "labutils.py"))

    check = _run(seat, modules, sys_path=[seat.runtime / "python", labs])

    assert check["status"] == "fail", check["detail"]  # the panel shows fail as NEEDS ATTENTION
    assert _foreign_names(check) == ["labutils"]
    assert Path(check["result"]["foreign"][0]["origin"]) == labs
    assert "labutils" in check["detail"] and "shibokensupport" not in check["detail"]


def test_an_absolute_file_with_nothing_on_disk_is_still_checked(seat):
    """Only the form of the name decides. An absolute ``__file__`` with no file behind it (a
    module imported from a zip archive on an absolute ``sys.path`` entry, or a file deleted
    after import) is still placed by its folder, and flagged when that folder is outside."""
    ghost = seat.checkout / ".hython_deps" / "deps.zip" / "orjson" / "__init__.py"  # never created
    modules = _modules(seat.inside, seat.houdini)
    modules["orjson"] = _module("orjson", ghost)

    check = _run(seat, modules)

    assert not ghost.exists()
    assert check["status"] == "fail", check["detail"]
    assert _foreign_names(check) == ["orjson"]
    assert check["result"]["checked"] == len(seat.inside) + len(seat.houdini) + 1


def test_reading_a_lazy_module_never_executes_it(seat):
    import importlib.util

    marker = seat.tmp / "lazy_module_executed.txt"
    source = _touch(seat.checkout / ".hython_deps" / "lazy_pkg.py")
    source.write_text(f"open({str(marker)!r}, 'w').close()\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("lazy_pkg", source)
    loader = importlib.util.LazyLoader(spec.loader)
    spec.loader = loader
    lazy = importlib.util.module_from_spec(spec)
    loader.exec_module(lazy)  # arms the lazy load; the module body has not run yet
    modules = _modules(seat.inside, seat.houdini)
    modules["lazy_pkg"] = lazy

    check = _run(seat, modules)

    assert not marker.exists(), "the check executed a lazily loaded module"
    assert _foreign_names(check) == ["lazy_pkg"]


def test_the_live_check_adds_nothing_to_sys_modules(seat):
    from synapse.server.doctor import _check_runtime_provenance

    before = set(sys.modules)
    check = _check_runtime_provenance(houdini_root=seat.hfs)
    assert set(sys.modules) - before == set()
    assert check["status"] in ("ok", "fail"), check["detail"]
    assert Path(check["result"]["runtime_root"]) == Path(__file__).resolve().parents[1]


# -- skipped is not ok -------------------------------------------------------------------------

def test_outside_houdini_the_check_is_skipped_not_passed(seat, monkeypatch):
    from synapse.server.doctor import _check_runtime_provenance

    monkeypatch.delenv("HFS", raising=False)
    check = _check_runtime_provenance(modules=_modules(seat.inside), runtime_root=seat.runtime,
                                      sys_path=[], interpreter_roots=[])
    assert check["status"] == "skipped"
    assert "HFS" in check["detail"]


def test_an_unknown_runtime_root_is_skipped_not_passed(seat):
    from synapse.server.doctor import _check_runtime_provenance

    stray = _module("orjson", _touch(seat.checkout / ".hython_deps" / "orjson" / "__init__.py"))
    check = _check_runtime_provenance(modules={"orjson": stray}, houdini_root=seat.hfs,
                                      sys_path=[], interpreter_roots=[])
    assert check["status"] == "skipped"
    assert "runtime root" in check["detail"]


def test_a_search_path_folder_outside_is_named_before_anything_loads_from_it(seat):
    deps = seat.checkout / ".hython_deps"
    deps.mkdir(parents=True)
    site = seat.hfs / "python313" / "lib" / "site-packages"

    check = _run(seat, _modules(seat.inside, seat.houdini),
                 sys_path=[seat.runtime / "python", deps, site])

    assert check["status"] == "ok", check["detail"]
    assert [Path(p) for p in check["result"]["search_path_outside"]] == [deps]
    assert ".hython_deps" in check["detail"]


# -- wiring --------------------------------------------------------------------------------------

def test_run_doctor_runs_the_check(tmp_path, monkeypatch):
    from synapse.server import doctor

    def stub(*_args, **_kwargs):
        return {"name": "stub", "status": "ok", "detail": "stubbed for this test"}

    # Only the new check runs for real; the others touch stores, sockets and hou.
    for attr in dir(doctor):
        if attr.startswith("_check_") and attr != "_check_runtime_provenance":
            monkeypatch.setattr(doctor, attr, stub)
    monkeypatch.setattr(doctor, "_wrap_memory_key_check", stub)
    monkeypatch.delenv("HFS", raising=False)

    result = doctor.run_doctor({}, home=tmp_path)

    rows = [c for c in result["checks"] if c["name"] == "runtime_provenance"]
    assert len(rows) == 1, [c["name"] for c in result["checks"]]
    assert rows[0]["status"] == "skipped" and "HFS" in rows[0]["detail"]
    assert sum(result["summary"].values()) == len(result["checks"])
