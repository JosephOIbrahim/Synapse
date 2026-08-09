"""tests/assay_h22_cache_insert.py -- R-CACHE-1 insert slice, live H22.0.400 undoability assay.

Runs in a real hython (never plain python). Exercises the REAL insert path
(``synapse.server.handlers_cache.insert_cache_core`` seeded by the REAL
``assess_cache_core``) against a live ``filecache`` SOP, then proves the whole insertion is
reversed by a single ``hou.undos.performUndo()`` -- the blueprint §13.3 / §16 Phase-2
"insertion is undoable" exit clause.

NOT collected by pytest: filename does not match ``test_*.py`` (pyproject.toml
python_files), so ``pytest tests/`` never imports it -- same "assay script, not a test"
convention as tests/assay_h22_cache_contract.py and host/introspect_cook_*.py.

Scope (binding): insertion ONLY. This assay SETS the File Cache output-path parameter and
asserts NOTHING is written to disk; it never cooks or saves the File Cache. The bake half is
out of scope (adjudication e3).

Run (real hython, never plain python):
    hython tests/assay_h22_cache_insert.py [--out <path>]

Residue-free (matching assay_h22_cache_contract.py): every trial node lives under a
disposable container destroyed (and verified absent) before exit, on success AND failure.

Artifact contract (byte-for-byte with the contract assay):
    {schema: "cache_h22_insert_assay/v1", houdini_version, platform, command, exit_status,
     items: [{item, description, status, detail}, ...], blake2b}
    status in {"pass","fail","not_run"} -- "not_run" only if hou could not be imported;
    NEVER "pass" without a real assertion having executed. blake2b over
    json.dumps({"items": items}, sort_keys=True), digest_size=16.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import traceback

try:
    import hou  # hython interpreter -- the live build IS the authority
    HOU_AVAILABLE = True
except ImportError:
    hou = None  # type: ignore
    HOU_AVAILABLE = False

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(_REPO_ROOT, "python"), os.path.join(_REPO_ROOT, "host"), _REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


class _AssayItem:
    def __init__(self, item: int, description: str):
        self.item = item
        self.description = description
        self.status = "not_run"
        self.detail = ""

    def to_dict(self) -> dict:
        return {"item": self.item, "description": self.description,
                "status": self.status, "detail": self.detail}


def _record_pass(result: _AssayItem, detail: str) -> None:
    result.status = "pass"
    result.detail = detail


def _record_fail(result: _AssayItem, detail: str) -> None:
    result.status = "fail"
    result.detail = detail


# --------------------------------------------------------------------------- fixtures

def _build_chain(container):
    """box (source) -> null (downstream) inside `container`. Returns (source, downstream)."""
    box = container.createNode("box", "src_box")
    downstream = container.createNode("null", "DOWNSTREAM_OUT")
    downstream.setInput(0, box)
    return box, downstream


# --------------------------------------------------------------------------- runner

def _run_all() -> list:
    import synapse.server.handlers_cache as hc

    items = []
    container = None

    def _new_item(n, desc):
        """Append-on-create: every item is in `items` BEFORE it is evaluated, so an early
        return can never silently drop a failure (the false-pass trap this assay hit once)."""
        it = _AssayItem(n, desc)
        items.append(it)
        return it

    try:
        container = hou.node("/obj").createNode("geo", "cache_h22_insert_assay")
        source, downstream = _build_chain(container)
        pre_children = sorted(c.name() for c in container.children())

        item1 = _new_item(1, "build a real SOP chain (source -> downstream) in a disposable container")
        _record_pass(item1, f"container={container.path()!r} source={source.path()!r} "
                            f"downstream={downstream.path()!r} children={pre_children}")

        # --- item 2: issue a decision via the REAL assess path ---
        item2 = _new_item(2, "issue a decision via the real assess_cache_core; verify it is recorded")
        store = hc.IssuedDecisionStore()
        machine = hc._detect_machine_profile(cache_root=hou.getenv("HIP"))
        resp = hc.assess_cache_core(
            source, node_path=source.path(), node_type=source.type().name(), machine=machine,
            context="sop", is_solver_result=True, frame_range=(1001, 1240),
            issued_decision_store=store,
        )
        decision_id = resp["decision"]["decision_id"]
        recorded = store.lookup(decision_id)
        if recorded is not None and recorded["strategy_id"] == "sop_filecache_solver_result_v1":
            _record_pass(item2, f"decision_id={decision_id!r} recorded; "
                                f"strategy_id={recorded['strategy_id']!r} verdict={resp['verdict']!r}")
        else:
            _record_fail(item2, f"decision not recorded correctly: recorded={recorded!r}")
            return items  # nothing downstream is meaningful

        # --- item 3: insert via the REAL insert core, under a real undo group ---
        item3 = _new_item(3, "insert+wire a live File Cache via insert_cache_core (source->cache->downstream)")
        ins = hc.insert_cache_core(
            decision_id=decision_id,
            resolve_source_node=lambda: source,
            store=store,
            undo_context_factory=lambda: hou.undos.group("SYNAPSE insert_cache"),
        )
        if ins["status"] != "ok":
            _record_fail(item3, f"insert rejected: {ins!r}")
            return items
        cache_node = hou.node(ins["created_node_path"])
        # Compare by .path(), never `is`: HOM returns a FRESH Python wrapper per call, so two
        # wrappers for the same node are never identity-equal.
        wired_ok = (
            cache_node is not None
            and cache_node.type().name().startswith("filecache")
            and cache_node.inputs() and cache_node.inputs()[0].path() == source.path()
            and downstream.inputs() and downstream.inputs()[0].path() == cache_node.path()
        )
        if wired_ok:
            _record_pass(item3, f"created={ins['created_node_path']!r} type={cache_node.type().name()!r} "
                                f"source->cache->downstream wired; rewired={ins['downstream_rewired']!r}")
        else:
            _record_fail(item3, f"wiring wrong: created={ins.get('created_node_path')!r} "
                                f"cache_inputs={[n.path() for n in (cache_node.inputs() if cache_node else [])]!r} "
                                f"downstream_inputs={[n.path() for n in downstream.inputs()]!r}")
            return items

        # --- item 4: parms set to strategy-correct values on the LIVE node ---
        item4 = _new_item(4, "verify File Cache parms set to expected values (Simulation/Time Dependent/format)")
        def _menu(name):
            p = cache_node.parm(name)
            return p.evalAsString() if p is not None else None
        def _tog(name):
            p = cache_node.parm(name)
            return p.eval() if p is not None else None
        observed = {
            "filemethod": _menu("filemethod"), "filetype": _menu("filetype"),
            "trange": _menu("trange"), "cachesim": _tog("cachesim"),
            "timedependent": _tog("timedependent"),
            "file_raw": cache_node.parm("file").rawValue() if cache_node.parm("file") else None,
        }
        expected_ok = (
            observed["filemethod"] == "explicit"
            and observed["filetype"] == ".bgeo.sc"          # solver strategy -> bgeo.sc
            and observed["cachesim"] == 1                     # Simulation ON (sequential state)
            and observed["timedependent"] == 1               # Time Dependent ON
            and observed["trange"] == "normal"               # frame range 1001..1240
            and observed["file_raw"] and observed["file_raw"].endswith(".bgeo.sc")
        )
        if expected_ok:
            _record_pass(item4, f"parms={observed!r} (solver strategy: bgeo.sc + Simulation ON + "
                                f"Time Dependent ON + Frame Range)")
        else:
            _record_fail(item4, f"parms not as expected: {observed!r}")

        # --- item 5: NOTHING written to disk ---
        item5 = _new_item(5, "assert no cache files exist on disk (insert never writes/cooks)")
        resolved_file = cache_node.parm("file").eval()  # $HIP/$F4 expanded
        cache_dir = os.path.dirname(resolved_file)
        if not os.path.isdir(cache_dir):
            _record_pass(item5, f"resolved file={resolved_file!r}; cache dir does not exist "
                                f"(nothing written), cooked={ins['cooked']!r} path_written={ins['path_written']!r}")
        else:
            files = os.listdir(cache_dir)
            if not files:
                _record_pass(item5, f"cache dir {cache_dir!r} exists but is empty (nothing written)")
            else:
                _record_fail(item5, f"cache dir {cache_dir!r} contains files after insert (should be "
                                    f"none -- insert must never write): {files!r}")

        # --- item 6: undo fully restores the graph ---
        item6 = _new_item(6, "hou.undos.performUndo() fully restores the graph (cache gone, wiring back)")
        top_label = list(hou.undos.undoLabels())[:1]
        hou.undos.performUndo()
        post_children = sorted(c.name() for c in container.children())
        cache_gone = hou.node(ins["created_node_path"]) is None
        downstream_restored = (downstream.inputs()
                               and downstream.inputs()[0].path() == source.path())
        topology_restored = post_children == pre_children
        if cache_gone and downstream_restored and topology_restored:
            _record_pass(item6, f"undo label={top_label!r}; after undo children={post_children} "
                                f"(== pre-insert {pre_children}); cache node gone; downstream re-wired to "
                                f"source -- fully reversed by one performUndo")
        else:
            _record_fail(item6, f"undo did NOT fully restore: cache_gone={cache_gone!r} "
                                f"downstream_restored={downstream_restored!r} "
                                f"topology_restored={topology_restored!r} "
                                f"post_children={post_children} pre_children={pre_children}")
    except Exception:
        failure = _AssayItem(0, "unhandled exception during insert assay run")
        _record_fail(failure, traceback.format_exc())
        items.append(failure)
    finally:
        if container is not None:
            path = container.path()
            container.destroy()
            if hou.node(path) is not None:
                print(f"WARNING: assay container {path!r} still present after destroy()",
                      file=sys.stderr)
    return items


def _write_artifact(doc: dict, out: str) -> None:
    tmp = out + ".tmp"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, out)


def main() -> int:
    out = None
    args = sys.argv[1:]
    if "--out" in args:
        out = args[args.index("--out") + 1]

    if not HOU_AVAILABLE:
        # §17.4: "If Houdini is unavailable, report the assay as not run, never passed."
        doc = {
            "schema": "cache_h22_insert_assay/v1",
            "houdini_version": "unknown",
            "platform": platform.platform(),
            "command": " ".join([sys.executable or "python"] + sys.argv),
            "exit_status": "not_run",
            "items": [],
            "blake2b": hashlib.blake2b(
                json.dumps({"items": []}, sort_keys=True, ensure_ascii=False).encode("utf-8"),
                digest_size=16).hexdigest(),
        }
        print("CACHE_H22_INSERT_ASSAY: hou unavailable -- reporting NOT RUN (never passed)")
        if out:
            _write_artifact(doc, out)
        return 1

    build = hou.applicationVersionString()
    if out is None:
        out = os.path.join("harness", "notes", f"cache_h22_insert_assay_{build}.json")

    items = _run_all()
    items_dicts = [i.to_dict() for i in items]
    any_fail = any(i.status != "pass" for i in items)

    doc = {
        "schema": "cache_h22_insert_assay/v1",
        "houdini_version": build,
        "platform": platform.platform(),
        "command": " ".join([sys.executable or "hython"] + sys.argv),
        "exit_status": "fail" if any_fail else "pass",
        "items": items_dicts,
        "blake2b": hashlib.blake2b(
            json.dumps({"items": items_dicts}, sort_keys=True, ensure_ascii=False).encode("utf-8"),
            digest_size=16).hexdigest(),
    }
    _write_artifact(doc, out)
    print(f"CACHE_H22_INSERT_ASSAY build={build} status={doc['exit_status']} -> {out}")
    for i in items_dicts:
        print(f"  [{i['status']}] item {i['item']}: {i['description']}")
    return 0 if not any_fail else 1


if __name__ == "__main__":
    sys.exit(main())
