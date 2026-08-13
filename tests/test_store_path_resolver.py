"""W1 store-path resolver: never join an UNEXPANDED env token to disk.

The literal ``C:/Users/User/Synapse/$HOUDINI_TEMP_DIR/untitled/.synapse`` store
that W1 recovered was created by joining a raw ``$HOUDINI_TEMP_DIR`` token (which
``expandString`` returns UNCHANGED when the variable is undefined) as a path
segment. These tests feed literal-unexpanded inputs to the resolver and assert it
never produces a path with a residual ``$VAR`` / ``${VAR}`` / ``%VAR%`` segment --
it either expands, or falls back to a resolved, writable base, loudly.
"""

import os
import sys
from pathlib import Path

import pytest

_PY = Path(__file__).resolve().parents[1] / "python"
if str(_PY) not in sys.path:
    sys.path.insert(0, str(_PY))

from synapse.memory import store as store_mod  # noqa: E402


# --- the token detector ----------------------------------------------------

@pytest.mark.parametrize("literal", [
    "$HOUDINI_TEMP_DIR/untitled",
    "C:/x/%APPDATA%/y",
    "${VAR}/z",
    "$SYNAPSE_ROOT",
    "%TEMP%",
])
def test_has_literal_env_segment_detects_all_forms(literal):
    assert store_mod._has_literal_env_segment(literal)


@pytest.mark.parametrize("clean", [
    r"C:/Users/User/.synapse",
    "/tmp/synapse/untitled",
    r"C:/Users/User/AppData/Local/Temp/houdini_temp/untitled/.synapse",
])
def test_has_literal_env_segment_passes_resolved_paths(clean):
    assert not store_mod._has_literal_env_segment(clean)


# --- expand-and-validate ---------------------------------------------------

def test_expand_and_validate_rejects_undefined_token(monkeypatch):
    monkeypatch.delenv("SYNAPSE_ROOT", raising=False)
    # undefined -> expandvars returns the token unchanged -> rejected (None)
    assert store_mod._expand_and_validate("$SYNAPSE_ROOT/proj") is None
    assert store_mod._expand_and_validate("${SYNAPSE_ROOT}/proj") is None


def test_expand_and_validate_expands_defined_var(monkeypatch, tmp_path):
    monkeypatch.setenv("SYNAPSE_ROOT", str(tmp_path))
    out = store_mod._expand_and_validate("$SYNAPSE_ROOT/proj")
    assert out is not None
    assert not store_mod._has_literal_env_segment(out)
    assert str(tmp_path).replace("\\", "/") in str(out).replace("\\", "/")


def test_expand_and_validate_passthrough_plain_path(tmp_path):
    target = tmp_path / "x"
    assert store_mod._expand_and_validate(str(target)) == Path(str(target))


# --- the unsaved base ------------------------------------------------------

def test_safe_unsaved_base_never_literal(monkeypatch):
    # Undefined HOUDINI_TEMP_DIR -> base must resolve to a real, absolute,
    # token-free writable dir, never a literal "$HOUDINI_TEMP_DIR" directory.
    monkeypatch.delenv("HOUDINI_TEMP_DIR", raising=False)
    base = store_mod._safe_unsaved_base()
    assert not store_mod._has_literal_env_segment(base)
    assert base.is_absolute()


# --- the resolver method itself --------------------------------------------

def _bare_memory():
    # object.__new__ bypasses the heavy __init__ (which builds a store); the
    # resolver method reads only module globals + its argument, never self.
    return object.__new__(store_mod.SynapseMemory)


def test_resolve_project_path_explicit_literal_falls_back(monkeypatch):
    monkeypatch.delenv("SYNAPSE_ROOT", raising=False)
    out = _bare_memory()._resolve_project_path("$SYNAPSE_ROOT/proj")
    assert not store_mod._has_literal_env_segment(out)


def test_resolve_project_path_defined_env_expands(monkeypatch, tmp_path):
    monkeypatch.setenv("SYNAPSE_ROOT", str(tmp_path))
    out = _bare_memory()._resolve_project_path("$SYNAPSE_ROOT/proj")
    assert not store_mod._has_literal_env_segment(out)
    assert Path(out).is_absolute()


@pytest.mark.parametrize("raw", [
    "$SYNAPSE_ROOT/p", "$HOUDINI_TEMP_DIR", "${VAR}", "$UNDEFINED_X/y/z",
])
def test_resolve_project_path_never_creates_literal_dir(monkeypatch, tmp_path, raw):
    # The acceptance gate: feeding a literal token to the resolver must never
    # yield a path with a literal-env segment, and must never create one on disk.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HOUDINI_TEMP_DIR", raising=False)
    monkeypatch.delenv("SYNAPSE_ROOT", raising=False)
    monkeypatch.delenv("VAR", raising=False)
    monkeypatch.delenv("UNDEFINED_X", raising=False)
    out = _bare_memory()._resolve_project_path(raw)
    assert not store_mod._has_literal_env_segment(out), (
        "resolver returned a literal-env path for %r -> %s" % (raw, out))
    # nothing literal-env-shaped was created under the working directory
    for entry in Path(tmp_path).rglob("*"):
        assert not store_mod._LITERAL_ENV_SEG.match(entry.name), (
            "resolver created a literal-env directory: %s" % entry)
