#!/usr/bin/env python
"""BP1-TRIAGE - silent-recall four-gate probe (Gate 0).

ONE script, two ways to run it. The demo runs in the GUI; a probe that passes
only under the shim is the false-green lesson (docs/BATTLEPLAN.md:41), so the
same file must run both places and stamp WHICH one it ran in.

  1. HEADLESS (agent lane), through the hytest shim:

       python .synapse/hytest.py \
           harness/battleplan/notes/probe_silent_recall.py \
           -o python_files=probe_silent_recall.py -s

     -> runs under Houdini's hython (PySide+pytest), collects test_silent_recall,
        writes harness/battleplan/runs/<date>/silent_recall_hython.json
        (four gate rows + a DONE sentinel written LAST).

  2. GUI (Joe's hands), pasted into the Houdini Python shell:

       Windows menu > Python Shell (or the Python Source Editor). Paste this
       whole file and run. It prints four JSON lines (one gate row each) and,
       if it can locate the repo, writes
       harness/battleplan/runs/<date>/silent_recall_gui.json.

The four gates discriminate WHERE silent recall hides, in order. The FIRST gate
whose verdict is `fail` names the bucket (env|plugin|layer|recall). A gate that
cannot be measured - substrate absent, pxr missing, no deposit possible -
renders UNKNOWN: a measurement, NOT a fail, and UNKNOWN never names the bucket
(docs/BATTLEPLAN.md sec.2 line 43; harness/memory/STATE.json substrate_presence
- headless Moneta is UNAVAILABLE by construction).

  G1 ENV     PXR_PLUGINPATH_NAME set, pointing at the Moneta schema dir; the
             synapse package present under the OneDrive prefs dir, absent from
             the classic ~/houdini22.0.
  G2 PLUGIN  pxr.Plug.Registry().GetAllPlugins() has a 'moneta'-named plugin.
  G3 LAYER   after a deposit + stage reopen, the memory layer
             (<store>/.moneta/cortex_root.usda, moneta_store.py:300,327-334) is
             in stage.GetLayerStack().
  G4 RECALL  MemoryPort.query_and_filter(...) of a known deposit returns it.
             deposit SUCCESS but recall EMPTY is the silent-empty defect -> fail.

Each gate emits ONE JSON object with exactly these keys:
  {gate, verdict, environment, build, observed, exception}
    verdict     : "pass" | "fail" | "UNKNOWN"
    environment : "hython" | "gui"            (hou.isUIAvailable())
    build       : hou.applicationVersionString() at runtime - NEVER typed
    observed    : gate-specific evidence dict
    exception   : the exception text, or null

Read-only w.r.t. product code: this probe imports SYNAPSE's own MemoryPort and
Moneta runtime but changes nothing in them. It writes only its run artifact
under harness/battleplan/runs/ and scratch Moneta stores under a temp dir it
deletes. Every hou/pxr/synapse import is guarded and done inside a function, so
the module imports cleanly under stock CPython too (all gates then UNKNOWN).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# gate label -> bucket vocabulary (docs/BATTLEPLAN.md sec.2 table, lines 45-50).
GATE_BUCKET = {
    "G1 ENV": "env",
    "G2 PLUGIN": "plugin",
    "G3 LAYER": "layer",
    "G4 RECALL": "recall",
}


# --------------------------------------------------------------------------- #
# environment / build / paths (runtime truth, never typed)
# --------------------------------------------------------------------------- #

def _detect_env() -> str:
    """'gui' when a Houdini UI is available, else 'hython' (the shim lane)."""
    try:
        import hou
        return "gui" if hou.isUIAvailable() else "hython"
    except Exception:
        return "hython"  # no hou at all -> headless posture


def _build():
    """hou.applicationVersionString() read at runtime. None when hou is absent.

    This is the crucible anchor: the build stamp must equal what the crucible's
    own shim run observes, so it is READ, never assumed."""
    try:
        import hou
        return hou.applicationVersionString()
    except Exception:
        return None


def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


def _run_date() -> str:
    d = os.environ.get("BP1_RUN_DATE")
    if d:
        return d
    from datetime import date
    return date.today().isoformat()


def _repo_root():
    """Repo root from this file's location, or None when pasted (no __file__).

    harness/battleplan/notes/probe_silent_recall.py -> parents[3] = repo root."""
    f = globals().get("__file__")
    if not f:
        return None
    try:
        root = Path(f).resolve().parents[3]
        if (root / "harness" / "battleplan").is_dir():
            return root
    except Exception:
        pass
    return None


def _bootstrap_synapse() -> None:
    """Make `import synapse` resolve. Under the shim, pyproject pythonpath=['python']
    already does this; when pasted in the GUI the package env's PYTHONPATH does.
    This is the belt-and-suspenders fallback for a bare `hython file.py` run:
    insert <repo>/python ONLY if synapse is not already importable, so the GUI
    never gets its live package shadowed by this worktree."""
    try:
        import synapse  # noqa: F401
        return
    except Exception:
        pass
    root = _repo_root()
    if root is None:
        return
    py = root / "python"
    if py.is_dir() and str(py) not in sys.path:
        sys.path.insert(0, str(py))


def _claim_id_of(row):
    """Extract claim_id from a recall/raw row.

    Corrects the BP1 G4 false-negative (BP1_G4_FALSE_FAIL.md, 2026-08-31):
    the settlement fields are JSON-serialized inside payload.content (a string),
    there is no top-level payload.claim_id. The old predicate
    `(r.get("payload") or {}).get("claim_id") == known` was false-negative
    forever on this shape. Forward-compat: honor a flattened claim_id if the
    shape ever changes.
    """
    p = row.get("payload") or {}
    cid = p.get("claim_id")
    if cid:
        return cid
    try:
        return json.loads(p.get("content") or "{}").get("claim_id")
    except Exception:
        return None


def _row(gate, verdict, environment, build, observed, exception):
    """One gate row in the exact shape target 1 pins."""
    return {
        "gate": gate,
        "verdict": verdict,
        "environment": environment,
        "build": build,
        "observed": observed,
        "exception": exception,
    }


# --------------------------------------------------------------------------- #
# G1 ENV
# --------------------------------------------------------------------------- #

def gate1_env(environment, build):
    observed = {}
    exception = None
    verdict = "UNKNOWN"
    try:
        pxr_path = os.environ.get("PXR_PLUGINPATH_NAME")
        observed["PXR_PLUGINPATH_NAME"] = pxr_path
        schema_ok = False
        entries = []
        if pxr_path:
            entries = [e for e in pxr_path.split(os.pathsep) if e]
            schema_ok = any((Path(e) / "plugInfo.json").is_file() for e in entries)
        observed["pxr_entries"] = entries
        observed["schema_dir_has_plugInfo"] = schema_ok
        observed["MONETA_SRC"] = os.environ.get("MONETA_SRC")
        observed["SYNAPSE_MEMORY_BACKEND"] = os.environ.get("SYNAPSE_MEMORY_BACKEND")

        # The OneDrive-redirect tell: which prefs dir is this session reading?
        try:
            import hou
            observed["homeHoudiniDirectory"] = hou.homeHoudiniDirectory()
        except Exception:
            observed["homeHoudiniDirectory"] = None

        # Package placement (rig-specific; overridable for portability).
        onedrive_pkg = os.environ.get(
            "BP1_ONEDRIVE_PKG",
            "C:/Users/User/OneDrive/Documents/houdini22.0/packages/synapse.json")
        classic_pkg = os.environ.get(
            "BP1_CLASSIC_PKG",
            "C:/Users/User/houdini22.0/packages/synapse.json")
        present_onedrive = Path(onedrive_pkg).is_file()
        absent_classic = not Path(classic_pkg).is_file()
        observed["onedrive_pkg"] = onedrive_pkg
        observed["package_present_onedrive"] = present_onedrive
        observed["classic_pkg"] = classic_pkg
        observed["package_absent_classic"] = absent_classic

        env_var_ok = bool(pxr_path) and schema_ok
        observed["env_var_set_and_points_at_schema"] = env_var_ok

        # A definite negative (env var unset / wrong dir / package misplaced) is
        # a measured fail, not UNKNOWN. UNKNOWN is reserved for a check that
        # could not run at all (handled by the except below).
        if env_var_ok and present_onedrive and absent_classic:
            verdict = "pass"
        else:
            verdict = "fail"
    except Exception as e:
        verdict = "UNKNOWN"
        exception = f"{type(e).__name__}: {e}"
    return _row("G1 ENV", verdict, environment, build, observed, exception)


# --------------------------------------------------------------------------- #
# G2 PLUGIN
# --------------------------------------------------------------------------- #

def gate2_plugin(environment, build):
    observed = {}
    exception = None
    verdict = "UNKNOWN"
    try:
        from pxr import Plug
        names = []
        for p in Plug.Registry().GetAllPlugins():
            try:
                names.append(p.name)
            except Exception:
                pass
        moneta = [n for n in names if isinstance(n, str) and "moneta" in n.lower()]
        observed["plugin_total"] = len(names)
        observed["moneta_plugins"] = moneta

        # Corroborate: does the USD runtime resolve the concrete MonetaMemory
        # schema? (moneta_runtime.py:100 SCHEMA_TYPE_NAME, :230 the query.)
        try:
            from pxr import Usd
            pd = Usd.SchemaRegistry().FindConcretePrimDefinition("MonetaMemory")
            observed["schema_registered_MonetaMemory"] = pd is not None
        except Exception as e2:
            observed["schema_registered_MonetaMemory"] = None
            observed["schema_check_error"] = f"{type(e2).__name__}: {e2}"

        # pxr answered and there is no moneta plugin -> a real fail (attribute
        # reads would return None with no exception - the silent class).
        verdict = "pass" if moneta else "fail"
    except Exception as e:
        # pxr itself unimportable -> unobtainable, not a fail.
        verdict = "UNKNOWN"
        exception = f"{type(e).__name__}: {e}"
    return _row("G2 PLUGIN", verdict, environment, build, observed, exception)


# --------------------------------------------------------------------------- #
# G3 LAYER
# --------------------------------------------------------------------------- #

def gate3_layer(environment, build):
    observed = {}
    exception = None
    verdict = "UNKNOWN"
    port = None
    tmp = None
    uri = None
    try:
        _bootstrap_synapse()
        try:
            from pxr import Usd
        except Exception as e2:
            observed["reason"] = f"pxr.Usd unimportable: {type(e2).__name__}: {e2}"
            return _row("G3 LAYER", "UNKNOWN", environment, build, observed, None)

        from synapse.loop.ports import MemoryPort, MONETA_URI_SCHEME
        import tempfile
        import uuid

        tmp = tempfile.mkdtemp(prefix="bp1_triage_g3_")
        uri = MONETA_URI_SCHEME + Path(tmp).as_posix()
        observed["store_dir"] = tmp
        MemoryPort.release(uri)
        port = MemoryPort(uri)

        if port.handle is None:
            probe = port.query_and_filter([], [])
            observed["bind_status"] = probe.status
            observed["bind_reason"] = probe.error_message
            observed["reason"] = (
                "Moneta store did not bind: no deposit possible, so no memory "
                "layer can be authored or reopened. Headless Moneta is "
                "UNAVAILABLE by construction (STATE.json substrate_presence). "
                "Unobtainable -> UNKNOWN, not fail.")
            verdict = "UNKNOWN"
        else:
            dep = port.deposit_settlement("BP1-TRIAGE-G3-" + uuid.uuid4().hex[:8], "HIT")
            observed["deposit_status"] = dep.status
            observed["deposit_error"] = dep.error_message
            # The SYNAPSE-authored cortex: <store>/.moneta/cortex_root.usda
            # (moneta_store.py:300 use_real_usd=True, :327-334 UsdCortexStore).
            cortex = Path(tmp) / ".moneta" / "cortex_root.usda"
            observed["cortex_path"] = cortex.as_posix()
            observed["cortex_exists"] = cortex.is_file()
            layer_ids = []
            memory_layer_present = False
            if cortex.is_file():
                stage = Usd.Stage.Open(cortex.as_posix())
                if stage is not None:
                    for lyr in stage.GetLayerStack():
                        try:
                            layer_ids.append(lyr.identifier)
                        except Exception:
                            pass
                    memory_layer_present = any(
                        "cortex" in (i or "").lower() for i in layer_ids)
            observed["layer_stack"] = layer_ids
            observed["memory_layer_present"] = memory_layer_present

            if cortex.is_file():
                verdict = "pass" if memory_layer_present else "fail"
                if verdict == "fail":
                    observed["reason"] = (
                        "cortex_root.usda opened but no cortex-* layer in "
                        "stage.GetLayerStack().")
            else:
                if dep.status == "SUCCESS":
                    verdict = "fail"
                    observed["reason"] = (
                        "deposit acknowledged (SUCCESS) but no cortex_root.usda "
                        "authored - use_real_usd may have fallen back to False "
                        "(moneta_store.py:304-323, schema-blind without "
                        "PXR_PLUGINPATH_NAME). Store reopened without composing "
                        "its own layer -> layer/handle-law bucket.")
                else:
                    verdict = "UNKNOWN"
                    observed["reason"] = (
                        f"deposit did not succeed ({dep.status}); cannot assert "
                        "a memory layer should exist.")
    except Exception as e:
        verdict = "UNKNOWN"
        exception = f"{type(e).__name__}: {e}"
    finally:
        _cleanup_store(port, uri, tmp)
    return _row("G3 LAYER", verdict, environment, build, observed, exception)


# --------------------------------------------------------------------------- #
# G4 RECALL
# --------------------------------------------------------------------------- #

def gate4_recall(environment, build):
    observed = {}
    exception = None
    verdict = "UNKNOWN"
    port = None
    tmp = None
    uri = None
    try:
        _bootstrap_synapse()
        from synapse.loop.ports import MemoryPort, MONETA_URI_SCHEME
        import tempfile
        import uuid

        tmp = tempfile.mkdtemp(prefix="bp1_triage_g4_")
        uri = MONETA_URI_SCHEME + Path(tmp).as_posix()
        observed["store_dir"] = tmp
        MemoryPort.release(uri)
        port = MemoryPort(uri)

        known = "BP1-TRIAGE-known-" + uuid.uuid4().hex[:8]
        observed["known_claim_id"] = known

        if port.handle is None:
            probe = port.query_and_filter([], [])
            observed["recall_status"] = probe.status
            observed["reason"] = probe.error_message
            verdict = "UNKNOWN"  # substrate unreachable -> mechanism untestable
        else:
            dep = port.deposit_settlement(known, "HIT")
            observed["deposit_status"] = dep.status
            observed["deposit_error"] = dep.error_message

            # Raw-row diagnostic (before PG-DRM filtering) so a fail is
            # diagnosable: store-split silent-empty vs a utility/token filter.
            try:
                raw = port._fetch_raw_memories([])
                observed["raw_row_count"] = len(raw)
                observed["known_in_raw"] = any(
                    _claim_id_of(r) == known for r in raw)
            except Exception as e3:
                observed["raw_probe_error"] = f"{type(e3).__name__}: {e3}"

            rec = port.query_and_filter([], [])
            observed["recall_status"] = rec.status
            if rec.status == "SUCCESS":
                payload = rec.payload or {}
                mems = payload.get("filtered_memories", [])
                observed["recall_count"] = payload.get("count")
                observed["dropped"] = payload.get("dropped")
                found = any(
                    _claim_id_of(m) == known for m in mems)
                observed["known_recalled"] = found
                if dep.status == "SUCCESS" and found:
                    verdict = "pass"
                elif dep.status == "SUCCESS" and not found:
                    verdict = "fail"
                    observed["reason"] = (
                        "deposit SUCCESS but query_and_filter did not return the "
                        "known deposit - the green-light-that-cannot-report-"
                        "failure class this wave exists to kill.")
                else:
                    verdict = "UNKNOWN"
                    observed["reason"] = (
                        f"deposit did not succeed ({dep.status}); recall of a "
                        "known item is not assertable.")
            else:
                verdict = "UNKNOWN"  # UNAVAILABLE / BLOCKED - honest, not empty
                observed["reason"] = rec.error_message
    except Exception as e:
        verdict = "UNKNOWN"
        exception = f"{type(e).__name__}: {e}"
    finally:
        _cleanup_store(port, uri, tmp)
    return _row("G4 RECALL", verdict, environment, build, observed, exception)


def _cleanup_store(port, uri, tmp):
    try:
        if port is not None and uri is not None:
            from synapse.loop.ports import MemoryPort
            MemoryPort.release(uri)
    except Exception:
        pass
    try:
        if tmp:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# orchestration / emit
# --------------------------------------------------------------------------- #

def run_probe():
    environment = _detect_env()
    build = _build()
    rows = [
        gate1_env(environment, build),
        gate2_plugin(environment, build),
        gate3_layer(environment, build),
        gate4_recall(environment, build),
    ]
    return rows, environment, build


def bucket_from_rows(rows):
    """First gate whose verdict is `fail` names the bucket (sec.2 line 39).
    UNKNOWN never names it. All-pass -> 'none' (green; silent recall not
    reproduced). No fail but some UNKNOWN -> 'UNKNOWN'."""
    for r in rows:
        if r["verdict"] == "fail":
            return GATE_BUCKET.get(r["gate"], "UNKNOWN")
    if all(r["verdict"] == "pass" for r in rows):
        return "none"
    return "UNKNOWN"


def emit(rows, environment, build, write=True):
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    bucket = bucket_from_rows(rows)
    path = None
    root = _repo_root()
    if write and root is not None:
        run_dir = root / "harness" / "battleplan" / "runs" / _run_date()
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / f"silent_recall_{environment}.json"
        sentinel = {
            "sentinel": "DONE",
            "environment": environment,
            "build": build,
            "gate_count": len(rows),
            "bucket": bucket,
            "bucket_rule": ("first gate whose verdict==fail; UNKNOWN never names "
                            "it (docs/BATTLEPLAN.md sec.2 line 39/43)"),
            "verdicts": {r["gate"]: r["verdict"] for r in rows},
            "completed": _now_iso(),
        }
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:                       # four gate rows first
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.write(json.dumps(sentinel, ensure_ascii=False) + "\n")  # DONE last
        print(f"# wrote {path.as_posix()}")
    print(f"# environment={environment} build={build} bucket={bucket}")
    return path, bucket


# pytest entry point: collected by the hytest shim (hython -m pytest). The
# probe RUNNING is the pass contract; gate verdicts are DATA, never asserted -
# UNKNOWN/fail are legitimate measurements this test must not coerce.
def test_silent_recall():
    rows, environment, build = run_probe()
    assert len(rows) == 4, rows
    assert all(r["verdict"] in ("pass", "fail", "UNKNOWN") for r in rows), rows
    assert all(r["environment"] in ("hython", "gui") for r in rows), rows
    assert all(set(r.keys()) == {"gate", "verdict", "environment", "build",
                                 "observed", "exception"} for r in rows), rows
    path, bucket = emit(rows, environment, build, write=True)
    assert path is not None, "repo root unresolved under the shim"
    lines = [ln for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 5, lines                      # 4 rows + DONE
    assert json.loads(lines[-1]).get("sentinel") == "DONE"


if __name__ == "__main__":
    _rows, _env, _build_ = run_probe()
    emit(_rows, _env, _build_, write=True)
