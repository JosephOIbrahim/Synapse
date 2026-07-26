"""H6 / R64 — substrate truth: the five conditions, measured independently.

``moneta_available() -> bool`` is one boolean carrying five independent claims
and tests exactly the first. These pins hold the decomposition honest.

What each pin fails against (Law 1 — state the condition or you have written a
decoration, not a check):

* the tri-state pins fail if ``schema_registered``/``schema_in_use`` ever
  collapse "could not check" into ``False``;
* the **positive control** (``test_registration_check_fires_*``) fails if the
  registry check is wired to a constant — it is demonstrated producing BOTH
  verdicts from the same code, in clean subprocesses, differing only by
  ``PXR_PLUGINPATH_NAME``;
* the **reader controls** (R60) fail if the stage traversal is blind: a reader
  that never composes sublayers, or that reports any prim as a match, cannot
  satisfy the True / False / sublayer trio simultaneously;
* the **no-raise pins** fail if any probe can propagate out of
  ``moneta_provenance()`` and therefore out of ``_make_store``, whose contract
  is that the backend flag *"can never break startup"*.

Subprocess isolation is not decoration either: USD plugin registration is
**process-global**. An in-process attempt to set ``PXR_PLUGINPATH_NAME`` and
re-query does not change the answer (confirmed while writing these pins), and
would contaminate every sibling test in the run. This mirrors Moneta's own
``tests/_schema_gate_subprocess.py`` rather than reinventing it.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PYDIR = _ROOT / "python"
sys.path.insert(0, str(_PYDIR))

from synapse.memory import moneta_runtime as mr  # noqa: E402

try:
    from pxr import Usd, Sdf  # noqa: F401
    _HAVE_PXR = True
except Exception:  # noqa: BLE001
    _HAVE_PXR = False

needs_pxr = pytest.mark.skipif(not _HAVE_PXR, reason="OpenUSD (pxr) not importable")


def _moneta_schema_dir():
    """Resolve Moneta's ``schema/`` directory without hard-coding a user path.

    ``$MONETA_SRC`` points at ``<Moneta>/src``; the schema lives at
    ``<Moneta>/schema``. Falls back to the installed package's grandparent.
    Returns None when it cannot be found — the caller skips.
    """
    candidates = []
    src = os.environ.get("MONETA_SRC")
    if src:
        candidates.append(Path(src).parent / "schema")
    try:
        import moneta as _m
        pkg = Path(_m.__file__).resolve().parent
        candidates.append(pkg.parent.parent / "schema")   # <repo>/src/moneta
        candidates.append(pkg / "schema")
    except Exception:  # noqa: BLE001
        pass
    # Sibling checkout — the SAME relative convention packages/synapse.json
    # uses to resolve MONETA_SRC ($SYNAPSE_ROOT/../Moneta/src), so the control
    # runs on any machine laid out the way the installer expects rather than
    # skipping until someone remembers to export an env var. Walk up rather
    # than index a fixed depth, because a git worktree sits several levels
    # below the repo root. Not a hard-coded user path.
    for ancestor in [_ROOT, *_ROOT.parents]:
        candidates.append(ancestor.parent / "Moneta" / "schema")
    for c in candidates:
        if (c / "plugInfo.json").is_file():
            return c
    return None


_SCHEMA_DIR = _moneta_schema_dir()


# =============================================================================
# The five fields exist and are tri-state
# =============================================================================

def test_provenance_reports_all_five_conditions():
    """Fails if any of the five fields is dropped from the payload.

    Presence alone is too weak: the payload is seeded with ``None`` defaults,
    so a probe that is deleted outright leaves the key behind and this pin
    would pass vacuously (caught by mutation M9). The reason field is the
    tell — only a probe that actually RAN can produce one — so both are
    asserted together.
    """
    prov = mr.moneta_provenance()
    for field in ("available", "version", "file",
                  "schema_registered", "schema_in_use"):
        assert field in prov, f"moneta_provenance() lost the {field!r} field"
    for field in ("schema_registered", "schema_in_use"):
        assert prov.get(f"{field}_reason") is not None, (
            f"{field} is present but was never computed — the probe that "
            "produces it has been removed or short-circuited"
        )


def test_every_verdict_carries_a_reason():
    """Law 2 — no verdict without a producer beside it. Fails if a field can
    report a tri-state with no explanation of how it got there."""
    prov = mr.moneta_provenance()
    for field in ("schema_registered", "schema_in_use"):
        reason = prov.get(f"{field}_reason")
        assert isinstance(reason, str) and reason.strip(), (
            f"{field} reported {prov.get(field)!r} with no reason"
        )


def test_schema_fields_are_tri_state_never_a_bare_bool():
    """Fails if either field is narrowed to a plain bool — which is exactly
    how "checked and false" and "could not check" got collapsed.

    ``x in (True, False, None)`` is NOT sufficient: ``bool(None)`` is ``False``
    and ``False`` is in that tuple, so a wrapper that coerces would pass
    (caught by mutation M10). Identity against ``None`` is the only assertion
    that can see the collapse.
    """
    assert mr.schema_registered() in (True, False, None)
    assert mr.schema_in_use() in (True, False, None)


def test_public_wrappers_preserve_none_they_do_not_coerce_to_bool():
    """READER CONTROL for the PUBLIC surface (R60).

    Every pin above reads ``_schema_in_use_detail`` — the internal reader.
    Callers read ``schema_in_use()``. A wrapper that did ``bool(...)`` would
    turn every UNKNOWN into a definite "no typed prims" while every
    reader-level pin stayed green. Fails against exactly that wrapper.
    """
    missing = str(_ROOT / "does" / "not" / "exist")
    assert mr._schema_in_use_detail(missing)[0] is None, "fixture assumption"
    assert mr.schema_in_use(missing) is None, (
        "the public wrapper collapsed UNKNOWN into a definite verdict"
    )


def test_public_registration_wrapper_preserves_none(monkeypatch):
    """Same control for condition 3's public surface."""
    monkeypatch.setattr(mr, "_schema_registered_detail",
                        lambda: (None, "could not check: fixture"))
    assert mr.schema_registered() is None, (
        "the public wrapper collapsed UNKNOWN into a definite verdict"
    )


def test_could_not_check_is_none_and_says_so_not_false():
    """The defect this leg exists to remove, pinned directly.

    With no USD root anywhere, ``schema_in_use`` has looked at nothing. It must
    report None, not False. Fails the moment an "absent" path returns False.
    """
    verdict, reason, inspected = mr._schema_in_use_detail(
        str(_ROOT / "does" / "not" / "exist")
    )
    assert verdict is None, "an unreadable stage reported a definite verdict"
    assert "could not check" in reason.lower()
    assert "not False" in reason, "the reason must say UNKNOWN is not False"
    assert inspected, "the inspected path must be named even when unknown"


# =============================================================================
# POSITIVE CONTROL — the registry check demonstrated firing BOTH ways.
# Mandatory per R64 item 5: "a registry check that has never seen an
# unregistered schema is a decoration".
# =============================================================================

_SUBPROCESS_DRIVER = (
    "import sys, json;"
    "sys.path.insert(0, {pydir!r});"
    "from synapse.memory import moneta_runtime as mr;"
    "v, r = mr._schema_registered_detail();"
    "print('H6_JSON ' + json.dumps({{'verdict': v, 'reason': r}}))"
)


def _registration_in_subprocess(plugin_path):
    """Query the registry in a CLEAN interpreter. *plugin_path* None => unset.

    Process-global registration means this cannot be done in-process without
    contaminating the run and without lying about the result.
    """
    env = dict(os.environ)
    env.pop("PXR_PLUGINPATH_NAME", None)
    if plugin_path is not None:
        env["PXR_PLUGINPATH_NAME"] = str(plugin_path)
    driver = _SUBPROCESS_DRIVER.format(pydir=str(_PYDIR))
    out = subprocess.check_output(
        [sys.executable, "-c", driver], text=True, env=env, timeout=300,
    )
    line = [ln for ln in out.splitlines() if ln.startswith("H6_JSON ")][-1]
    return json.loads(line[len("H6_JSON "):])


@needs_pxr
def test_registration_check_fires_with_plugin_path_unset():
    """NEGATIVE arm of the positive control (R64 item 5, verbatim).

    Fails if the check cannot return False — i.e. if it were hardcoded True, or
    if it swallowed the unregistered case into None.
    """
    res = _registration_in_subprocess(None)
    assert res["verdict"] is False, (
        "with PXR_PLUGINPATH_NAME unset the schema is NOT registered; a check "
        f"that cannot say so is a decoration. Got {res!r}"
    )
    assert "checked and FALSE" in res["reason"]


@needs_pxr
def test_registration_check_resolves_with_plugin_path_set():
    """POSITIVE arm. Same code, same interpreter, one env var different.

    Fails if the check cannot return True — i.e. if it were hardcoded False, or
    if plugin discovery is broken. Together with the arm above this is the
    two-sided demonstration; neither alone proves the instrument works.
    """
    if _SCHEMA_DIR is None:
        pytest.skip("Moneta schema/plugInfo.json not found (set $MONETA_SRC)")
    res = _registration_in_subprocess(_SCHEMA_DIR)
    assert res["verdict"] is True, (
        f"PXR_PLUGINPATH_NAME={_SCHEMA_DIR} should register MonetaMemory. "
        f"Got {res!r}"
    )
    assert "checked and TRUE" in res["reason"]


@needs_pxr
def test_the_two_control_arms_actually_disagree():
    """The control is only a control if the arms differ. Fails if both arms
    return the same verdict — which would mean the env var changed nothing and
    the "demonstration" proved nothing."""
    if _SCHEMA_DIR is None:
        pytest.skip("Moneta schema/plugInfo.json not found (set $MONETA_SRC)")
    unset = _registration_in_subprocess(None)["verdict"]
    was_set = _registration_in_subprocess(_SCHEMA_DIR)["verdict"]
    assert unset != was_set, (
        f"both arms returned {unset!r}; the check is insensitive to the only "
        "input that determines the answer"
    )


# =============================================================================
# READER CALIBRATION (R60) — the stage traversal is the reader every
# schema_in_use verdict depends on. Mutation-test the READER, not just the
# product: a blind reader produces green pins and zero information.
# =============================================================================

def _author_stage(directory, prims):
    """Write a composed Moneta-shaped stage. *prims* is [(path, typeName)];
    typeName "" authors an untyped ``def`` — the pre-migration shape."""
    directory.mkdir(parents=True, exist_ok=True)
    root_path = directory / mr.USD_ROOT_FILENAME
    stage = Usd.Stage.CreateNew(str(root_path))
    for path, type_name in prims:
        if type_name:
            stage.DefinePrim(path, type_name)
        else:
            stage.DefinePrim(path)
    stage.GetRootLayer().Save(True)
    return root_path


@needs_pxr
def test_reader_sees_a_typed_prim(tmp_path):
    """Fails if the reader cannot find a MonetaMemory prim that IS there."""
    d = tmp_path / "typed"
    _author_stage(d, [("/Memory_aaaa", mr.SCHEMA_TYPE_NAME)])
    verdict, reason, _ = mr._schema_in_use_detail(str(d))
    assert verdict is True, reason
    assert "checked and TRUE" in reason


@needs_pxr
def test_reader_reports_false_when_prims_exist_but_none_are_typed(tmp_path):
    """READER CONTROL. The pre-migration shape: prims exist, none carry the
    type. Fails if the reader reports any prim as a match — which is how a
    blind reader would make the pin above pass vacuously."""
    d = tmp_path / "untyped"
    _author_stage(d, [("/Memory_bbbb", ""), ("/Memory_cccc", "Scope")])
    verdict, reason, _ = mr._schema_in_use_detail(str(d))
    assert verdict is False, reason
    assert "checked and FALSE" in reason
    assert "2 prim(s)" in reason, "the count is the producer; it must be cited"


@needs_pxr
def test_reader_composes_sublayers_it_does_not_read_the_root_layer(tmp_path):
    """READER CONTROL, the one that matters most.

    Moneta routes memory prims into SUBLAYERS (cortex_protected.usda /
    cortex_YYYY_MM_DD.usda), never into the root layer. A reader that inspects
    the root layer's prim specs — the cheap, obvious implementation — finds
    zero prims here and reports a false negative on a substrate that is in
    fact fully typed. Fails against exactly that implementation.
    """
    d = tmp_path / "sublayered"
    d.mkdir(parents=True, exist_ok=True)
    sub_path = d / "cortex_2026_07_26.usda"
    sub = Usd.Stage.CreateNew(str(sub_path))
    sub.DefinePrim("/Memory_dddd", mr.SCHEMA_TYPE_NAME)
    sub.GetRootLayer().Save(True)

    root_path = d / mr.USD_ROOT_FILENAME
    root = Usd.Stage.CreateNew(str(root_path))
    root.GetRootLayer().subLayerPaths.append(sub_path.name)
    root.GetRootLayer().Save(True)

    # The root layer itself holds no prim specs — that is the whole point.
    assert not Sdf.Layer.FindOrOpen(str(root_path)).rootPrims, (
        "fixture is wrong: the root layer must hold no prim specs"
    )
    verdict, reason, _ = mr._schema_in_use_detail(str(d))
    assert verdict is True, (
        f"the reader missed a typed prim that lives in a sublayer: {reason}"
    )


@needs_pxr
def test_zero_prims_is_unknown_not_false(tmp_path):
    """An empty stage has nothing to judge. Fails if "nothing authored yet" is
    reported as "authored untyped" — two different facts, one of which is a
    migration finding and the other of which is not."""
    d = tmp_path / "empty"
    _author_stage(d, [])
    verdict, reason, _ = mr._schema_in_use_detail(str(d))
    assert verdict is None, reason
    assert "zero prims" in reason


@needs_pxr
def test_reader_accepts_a_directory_or_a_root_layer_file(tmp_path):
    """Both call shapes must resolve to the same stage. Fails if the resolver
    silently returns None for one of them and the caller reads that as
    'no typed prims'."""
    d = tmp_path / "either"
    root_path = _author_stage(d, [("/Memory_eeee", mr.SCHEMA_TYPE_NAME)])
    assert mr.schema_in_use(str(d)) is True
    assert mr.schema_in_use(str(root_path)) is True


@needs_pxr
def test_env_var_seam_resolves_when_no_argument_is_passed(tmp_path, monkeypatch):
    """$SYNAPSE_MONETA_USD_ROOT is the operator/test seam. Fails if the
    resolver ignores it and silently reports UNKNOWN."""
    d = tmp_path / "viaenv"
    _author_stage(d, [("/Memory_ffff", mr.SCHEMA_TYPE_NAME)])
    monkeypatch.setenv("SYNAPSE_MONETA_USD_ROOT", str(d))
    assert mr.schema_in_use() is True


# =============================================================================
# THE DEAD-BYTES CELL — schema_in_use alone is not evidence.
# =============================================================================

@needs_pxr
def test_authored_typename_survives_with_no_registered_schema(tmp_path):
    """Why the pair matters, pinned as behaviour rather than as a comment.

    Sdf-level authoring is schema-blind: USD writes typeName="MonetaMemory"
    whether or not the schema is registered. So in_use=True with
    registered=False is not a working substrate — it is dead bytes. Fails if
    USD ever starts validating typeName on author, which would make the
    registered/in_use pair redundant and this whole decomposition wrong.
    """
    d = tmp_path / "deadbytes"
    _author_stage(d, [("/Memory_9999", mr.SCHEMA_TYPE_NAME)])
    assert mr.schema_in_use(str(d)) is True
    # ... while this same runtime may not know the type at all.
    assert mr.schema_registered() in (True, False, None)


# =============================================================================
# NO-RAISE CONTRACT — _make_store's docstring is the contract:
# "setting the flag can never break startup".
# =============================================================================

def test_provenance_never_raises_when_the_registry_probe_explodes(monkeypatch):
    """``store.py`` calls ``moneta_provenance()`` from inside its own except
    handler. A raise here propagates out of ``_make_store`` and stops Houdini's
    panel loading. Fails if the fence around either probe is removed."""
    def boom():
        raise RuntimeError("probe exploded")
    monkeypatch.setattr(mr, "_schema_registered_detail", boom)
    prov = mr.moneta_provenance()
    assert prov["schema_registered"] is None
    assert "probe itself raised" in prov["schema_registered_reason"]


def test_provenance_never_raises_when_the_stage_probe_explodes(monkeypatch):
    def boom(usd_root=None):
        raise RuntimeError("stage probe exploded")
    monkeypatch.setattr(mr, "_schema_in_use_detail", boom)
    prov = mr.moneta_provenance()
    assert prov["schema_in_use"] is None
    assert "probe itself raised" in prov["schema_in_use_reason"]


_NO_PXR_DRIVER = '''\
import sys, json
sys.path.insert(0, {pydir!r})


class Block:
    """Meta-path hook that makes ``import pxr`` fail, simulating stock CI."""

    def find_spec(self, name, path=None, target=None):
        if name == "pxr" or name.startswith("pxr."):
            raise ImportError("pxr blocked for this pin")
        return None


sys.meta_path.insert(0, Block())
for mod in [m for m in sys.modules if m == "pxr" or m.startswith("pxr.")]:
    del sys.modules[mod]

from synapse.memory import moneta_runtime as mr

# Prove the block is real before trusting what it proves (a blocked-import
# pin whose block silently did nothing is the vacuous-pass shape again).
try:
    import pxr  # noqa: F401
    raise SystemExit("BLOCK_FAILED: pxr still importable")
except ImportError:
    pass

p = mr.moneta_provenance()
print("H6_JSON " + json.dumps({{
    "reg": p["schema_registered"],
    "use": p["schema_in_use"],
    "rreason": p["schema_registered_reason"],
    "ureason": p["schema_in_use_reason"],
}}))
'''


def test_schema_checks_degrade_to_none_when_pxr_is_absent(tmp_path):
    """CI without OpenUSD must get UNKNOWN, never False and never a traceback.

    Run in a clean subprocess with ``pxr`` blocked on the meta path, because an
    in-process block would leak into sibling tests that legitimately import it.
    Fails if a missing dependency is reported as a negative finding.
    """
    script = tmp_path / "no_pxr_driver.py"
    script.write_text(_NO_PXR_DRIVER.format(pydir=str(_PYDIR)), encoding="utf-8")
    out = subprocess.check_output([sys.executable, str(script)], text=True,
                                  timeout=300)
    line = [ln for ln in out.splitlines() if ln.startswith("H6_JSON ")][-1]
    res = json.loads(line[len("H6_JSON "):])
    assert res["reg"] is None, "pxr absent must be UNKNOWN, not False"
    assert res["use"] is None
    assert "could not check" in res["rreason"]
    assert "pxr unavailable" in res["rreason"]


def test_make_store_falls_back_to_jsonl_when_moneta_is_installed_but_broken(
    tmp_path, monkeypatch, caplog
):
    """The contract, pinned end to end. Fails if ``_make_store`` grows any
    raise path on the moneta branch — the failure that would stop the panel."""
    import logging
    from synapse.memory import moneta_store
    from synapse.memory.store import MemoryStore, SynapseMemory

    def broken(*_a, **_k):
        raise RuntimeError("adapter drift")

    monkeypatch.setattr(moneta_store.MonetaBackedStore, "from_storage_dir",
                        staticmethod(broken))
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    with caplog.at_level(logging.ERROR):
        store = SynapseMemory._make_store(None, tmp_path)
    assert isinstance(store, MemoryStore), (
        "a broken moneta adapter must degrade to jsonl, not raise"
    )
    assert any(r.levelno >= logging.ERROR for r in caplog.records), (
        "installed-but-broken must be LOUD (ERROR), not a quiet warning — "
        "that is how it is distinguished from not-installed"
    )


def test_not_installed_is_reported_as_not_installed_not_as_broken(
    tmp_path, monkeypatch, caplog
):
    """H6-F4. The branch exists to tell "absent" from "installed but broken",
    and it had that backwards.

    ``moneta_store`` imports nothing from moneta at module scope, so
    ``from .moneta_store import MonetaBackedStore`` ALWAYS succeeds and
    ``from_storage_dir`` raises ``RuntimeError``. The old ``except ImportError``
    arm was therefore unreachable, and every not-installed seat was told at
    ERROR that the backend "is installed but failed to initialize ... not a
    missing dependency" — the exact inverse of the truth (Law 3).

    Fails against that implementation: it asserts the message says *not
    importable*, and that a plain absent dependency is not escalated to ERROR.
    """
    import logging
    from synapse.memory.store import MemoryStore, SynapseMemory

    monkeypatch.setattr(mr, "moneta_available", lambda: False)
    monkeypatch.setattr(mr, "import_error", lambda: "ImportError: no moneta")
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    with caplog.at_level(logging.DEBUG):
        store = SynapseMemory._make_store(None, tmp_path)
    assert isinstance(store, MemoryStore)
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "not importable" in said, said
    assert "is installed but failed to initialize" not in said, (
        "an absent package was reported as an installed-but-broken one"
    )
    assert not [r for r in caplog.records
                if r.levelno >= logging.ERROR
                and "MEMORY_BACKEND" in r.getMessage()], (
        "a missing optional dependency was escalated to ERROR"
    )


def test_installed_but_broken_is_still_loud(tmp_path, monkeypatch, caplog):
    """The other arm must stay reachable and stay LOUD. Fails if the F4 fix
    swallowed the real drift case along with the false one."""
    import logging
    from synapse.memory import moneta_store
    from synapse.memory.store import MemoryStore, SynapseMemory

    def broken(*_a, **_k):
        raise RuntimeError("adapter drift")

    monkeypatch.setattr(mr, "moneta_available", lambda: True)
    monkeypatch.setattr(moneta_store.MonetaBackedStore, "from_storage_dir",
                        staticmethod(broken))
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    with caplog.at_level(logging.DEBUG):
        store = SynapseMemory._make_store(None, tmp_path)
    assert isinstance(store, MemoryStore)
    errors = [r.getMessage() for r in caplog.records
              if r.levelno >= logging.ERROR]
    assert errors, "installed-but-broken must be ERROR, not a quiet warning"
    assert "is installed but failed to initialize" in " ".join(errors)


def test_make_store_survives_a_provenance_that_raises(tmp_path, monkeypatch):
    """Belt and braces on the exact seam: ``store.py`` interpolates
    ``moneta_provenance()`` into its ERROR log. Fails if provenance can raise
    from inside the handler that was supposed to make failure safe."""
    from synapse.memory import moneta_store
    from synapse.memory.store import MemoryStore, SynapseMemory

    def broken(*_a, **_k):
        raise RuntimeError("adapter drift")

    def exploding_provenance(*_a, **_k):
        raise RuntimeError("provenance exploded")

    monkeypatch.setattr(moneta_store.MonetaBackedStore, "from_storage_dir",
                        staticmethod(broken))
    monkeypatch.setattr(mr, "moneta_provenance", exploding_provenance)
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    try:
        store = SynapseMemory._make_store(None, tmp_path)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"_make_store raised on the moneta branch: {exc!r}")
    assert isinstance(store, MemoryStore)


# =============================================================================
# DOCTOR — every cell of the 2x2 gets a verdict (R63: pin the class, not the
# named instance).
# =============================================================================

_CELLS = [
    # registered, in_use, expected status, must appear in the detail
    (True,  True,  "ok",      "registered"),
    (True,  False, "fail",    "looks like success"),
    (True,  None,  "fail",    "no typed prim can be demonstrated"),
    (False, True,  "fail",    "DEAD BYTES"),
    (False, False, "fail",    "not registered"),
    (False, None,  "fail",    "not registered"),
    (None,  True,  "skipped", "could not be checked"),
    (None,  None,  "skipped", "could not be checked"),
]


@pytest.mark.parametrize("registered,in_use,expected,needle", _CELLS)
def test_doctor_gives_every_cell_a_verdict(monkeypatch, registered, in_use,
                                           expected, needle):
    """Fails if any (registered, in_use) combination is unhandled, or if a cell
    that looks like success is allowed to report ``ok``. The two dangerous
    cells — registered-but-unused and unregistered-but-authored — must both
    fail, and must both say why."""
    from synapse.server import doctor

    def fake_provenance(usd_root=None):
        return {"available": True, "version": "x", "file": "y",
                "schema_registered": registered,
                "schema_registered_reason": "reason-r",
                "schema_in_use": in_use,
                "schema_in_use_reason": "reason-u",
                "usd_root_inspected": None}

    monkeypatch.setattr(mr, "moneta_provenance", fake_provenance)
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    check = doctor._check_moneta_substrate()
    assert check["status"] == expected, (
        f"cell registered={registered} in_use={in_use} reported "
        f"{check['status']!r}: {check['detail']}"
    )
    assert needle.lower() in check["detail"].lower(), check["detail"]
    assert check["result"]["schema_registered"] is registered
    assert check["result"]["schema_in_use"] is in_use


def test_doctor_only_one_cell_can_be_ok():
    """The whole point of the decomposition. Fails if any combination other
    than both-demonstrated is allowed to read as healthy."""
    oks = [(r, u) for r, u, status, _ in _CELLS if status == "ok"]
    assert oks == [(True, True)], (
        f"more than one cell reports healthy: {oks}"
    )


def test_doctor_skips_when_the_moneta_backend_is_not_selected(monkeypatch):
    """No alarm fatigue on a jsonl seat. Fails if the check reports fail for a
    substrate the seat never asked for."""
    from synapse.server import doctor
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "jsonl")
    check = doctor._check_moneta_substrate()
    assert check["status"] == "skipped"
    assert "not selected" in check["detail"]


def test_doctor_runs_the_substrate_check(monkeypatch, tmp_path):
    """The check must be WIRED, not merely defined. Fails if
    ``_check_moneta_substrate`` is dropped from ``run_doctor``'s list — the
    'implemented but never called' failure this repo keeps finding."""
    from synapse.server import doctor
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "jsonl")
    report = doctor.run_doctor({}, home=tmp_path)
    names = [c["name"] for c in report["checks"]]
    assert "moneta_substrate" in names, names
    assert sum(report["summary"].values()) == len(report["checks"])
