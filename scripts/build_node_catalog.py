"""Dump the full live node-type schema catalog for the RUNNING Houdini major.

FP1 -- never recall what the binary can tell you. Every parm name, label, type,
default, range and menu token in this catalog is read from the live binary via
``hou.NodeType.parmTemplateGroup()`` (type-level, instantiation-free), so a row
authored from model memory is impossible by construction: the dump either read
the value off the running Houdini or it did not run at all. That is the whole
point of the substrate -- the domain waves (dop/vop/chop/cop/apex) stay gated on
it precisely because catalog rows are verified-by-construction.

Modeled on ``scripts/harvest_lop_catalog.py`` (same determinism + per-field
guard discipline), widened from one category to the full
``hou.nodeTypeCategories()`` walk, and deepened from arity-only to the full parm
template surface.

THREE PHASES, ONE hython PROCESS (one dump):

  A. NODE + PARM WALK -- every category ``hou.nodeTypeCategories()`` returns;
     for every type: label / arity / manager+generator flags + the flattened
     parm template surface (name, label, type, data_type, num_components,
     default, min/max + strictness, menu tokens+labels, binary parm help).
     Type-level, instantiation-free. -> ``<Category>.json`` per category.

  B. VOP WIRE SIGNATURES -- the parm templates do NOT carry a VOP's wiring
     surface, so each Vop type is instantiated in a throwaway matnet, its
     inputNames/outputNames/inputDataTypes/outputDataTypes read, then destroyed.
     Merged into ``Vop.json`` rows as ``wire_signature``. Industrializes the
     ad-hoc conn_mtlx probes. Instantiation is best-effort: a type that will not
     build in a matnet records ``instantiated: false`` with the failure class,
     never crashes the dump.

  C. APEX CALLBACK PORTS -- ``apex.callbackRegistry()`` typed-callback surface:
     every callback definition's Signature inputs/outputs (the typed ports the
     node catalog cannot carry), parm defaults, and overload set.
     -> ``apex_callbacks.json``.

RUN IT INSIDE THE TARGET BUILD (hython, headless, isolated process -- the
artist's session is never touched):

    "C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe" \\
        scripts/build_node_catalog.py

Writes ``rag/catalog/h<build>/`` -- ONE file per category + ``apex_callbacks.json``
+ ``_manifest.json``. The build-keyed path (e.g. ``rag/catalog/h22.0.400/``) is
load-bearing: staleness-by-construction depends on it -- a catalog under
``h22.0.400/`` is, by its path alone, a claim about 22.0.400 and nothing else.

DETERMINISM: a second run on the same build is byte-identical -- keys sorted, no
wall-clock stamp (``generated`` describes the generator, not the moment). Each
file carries a blake2b over its sorted ``types`` map; ``_manifest.json`` carries
the per-file hashes. Same convention as harvest_lop_catalog / verified_connectivity.

FLAGS (for cheap iteration; default is the full dump):
    --categories A,B   only these categories (phase A)
    --limit N          cap types per category to the first N (smoke run)
    --no-vop           skip phase B
    --no-apex          skip phase C
    --out DIR          override output dir (default rag/catalog/h<build>/)

PHANTOM DISCIPLINE: every accessor is individually try/excepted so one missing
API on a future build degrades that field to absent instead of killing the dump.
The parm/VOP/APEX accessors used here were dir()-confirmed live on 22.0.400
(scripts smoke + discovery probes, 2026-08-16).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

SCHEMA = "node_catalog_live/v1"
APEX_SCHEMA = "apex_callback_catalog_live/v1"
_REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Parm template extraction -- type-level, instantiation-free
# ---------------------------------------------------------------------------

def _jsonable(v):
    """Coerce a HOM return into a JSON-safe value. Tuples->lists; hou enums and
    anything exotic -> str(); leaves scalars/str/bool/None as-is."""
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


def _read(obj, attr):
    """Read ``obj.attr`` whether it is a property or a nullary method. Raises on
    absence -- callers wrap in try/except so an absent accessor drops the field."""
    val = getattr(obj, attr)
    return val() if callable(val) else val


def _parm_record(t, folder: tuple) -> dict:
    """One flattened parm template -> a JSON record. Every field guarded.

    Field access is BY NAME so the ``getattr`` happens INSIDE the try -- a
    template class that lacks an accessor (e.g. FolderParmTemplate has no
    ``minValue``) drops that field instead of raising before the guard runs.
    """
    rec: dict = {}

    def field(key, attr, transform=None):
        try:
            val = _read(t, attr)
            rec[key] = _jsonable(transform(val) if transform else val)
        except Exception:  # noqa: BLE001 -- per-field, never fatal
            pass

    _name = lambda x: x.name()
    field("name", "name")
    field("label", "label")
    field("type", "type", _name)
    field("data_type", "dataType", _name)
    field("num_components", "numComponents")
    field("default", "defaultValue")
    # Numeric range surface (FloatParmTemplate / IntParmTemplate only).
    field("min", "minValue")
    field("max", "maxValue")
    field("min_strict", "minIsStrict")
    field("max_strict", "maxIsStrict")
    # Menu surface -- present on Menu templates AND string/int parms with menus.
    try:
        items = t.menuItems()
        if items:
            rec["menu_tokens"] = _jsonable(items)
            try:
                rec["menu_labels"] = _jsonable(t.menuLabels())
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass
    # Binary parm help (tooltip) -- from-binary parm doc, complements help-cache.
    try:
        h = t.help()
        if h:
            rec["help"] = str(h)
    except Exception:  # noqa: BLE001
        pass
    if folder:
        rec["folder"] = list(folder)
    return rec


def _walk_templates(entries, folder: tuple, errors: list, type_name: str):
    """Yield (template, folder_path) flattening Folder nesting. Structural
    templates (folders/separators/labels) are yielded too -- their presence and
    order is part of the schema truth -- but folders also recurse."""
    for t in entries:
        try:
            tt = t.type().name()
        except Exception as e:  # noqa: BLE001
            errors.append(f"{type_name}: template.type() failed: {type(e).__name__}")
            tt = None
        if tt in ("Folder", "FolderSet"):
            try:
                label = t.label()
            except Exception:  # noqa: BLE001
                label = ""
            yield t, folder
            try:
                sub = t.parmTemplates()
            except Exception as e:  # noqa: BLE001
                errors.append(f"{type_name}: parmTemplates() failed on folder "
                              f"{label!r}: {type(e).__name__}")
                sub = ()
            for x in _walk_templates(sub, folder + (label,), errors, type_name):
                yield x
        else:
            yield t, folder


def _type_parms(node_type, type_name: str, errors: list) -> list:
    try:
        group = node_type.parmTemplateGroup()
    except Exception as e:  # noqa: BLE001
        errors.append(f"{type_name}: parmTemplateGroup() failed: {type(e).__name__}: {e}")
        return []
    try:
        entries = group.entries()
    except Exception as e:  # noqa: BLE001
        errors.append(f"{type_name}: group.entries() failed: {type(e).__name__}")
        return []
    return [_parm_record(t, folder)
            for t, folder in _walk_templates(entries, (), errors, type_name)]


_TYPE_FIELDS = (
    ("label", lambda t: t.description()),
    ("min_inputs", lambda t: t.minNumInputs()),
    ("max_inputs", lambda t: t.maxNumInputs()),
    ("max_outputs", lambda t: t.maxNumOutputs()),
    ("deprecated", lambda t: t.deprecated()),
    ("is_manager", lambda t: t.isManager()),
    ("is_generator", lambda t: t.isGenerator()),
)


def _type_record(node_type, type_name: str, errors: list) -> dict:
    # Asymmetry with _parm_record is DELIBERATE: type-level fields (label/arity/
    # flags) are a FIXED schema every node has, so a failure is real and is
    # marked with None + a probe_error. Parm-level fields vary by parm kind
    # (min only on numerics, menu only on menus), so absence is normal and the
    # field is OMITTED. None here means "expected but failed"; omitted there
    # means "not applicable". probe_errors distinguishes the two.
    rec: dict = {}
    for key, read in _TYPE_FIELDS:
        try:
            rec[key] = _jsonable(read(node_type))
        except Exception as e:  # noqa: BLE001
            rec[key] = None
            errors.append(f"{type_name}.{key}: {type(e).__name__}: {e}")
    rec["parms"] = _type_parms(node_type, type_name, errors)
    return rec


# ---------------------------------------------------------------------------
# VOP wire signatures -- instantiation-based (phase B)
# ---------------------------------------------------------------------------

def _vop_signature(node, errors: list, type_name: str) -> dict:
    sig: dict = {}
    for key, attr in (("input_names", "inputNames"),
                      ("output_names", "outputNames"),
                      ("input_data_types", "inputDataTypes"),
                      ("output_data_types", "outputDataTypes")):
        try:
            sig[key] = _jsonable(_read(node, attr))
        except Exception as e:  # noqa: BLE001
            errors.append(f"Vop/{type_name}.{attr}: {type(e).__name__}")
    return sig


def _make_matnet(hou):
    """A throwaway matnet to host VOP instantiation. Prefer a fresh /obj/matnet;
    fall back to the top-level /mat network."""
    try:
        obj = hou.node("/obj")
        if obj is not None:
            return obj.createNode("matnet", "w5_catalog_vop_probe"), True
    except Exception:  # noqa: BLE001
        pass
    return hou.node("/mat"), False


def add_vop_signatures(hou, vop_types: dict, errors: list, log) -> dict:
    """Instantiate each Vop type in a throwaway matnet, read its wiring surface,
    destroy it. Returns {type_name: wire_signature}."""
    container, disposable = _make_matnet(hou)
    out: dict = {}
    if container is None:
        errors.append("Vop: no matnet container could be created -- phase B skipped")
        return out
    total = len(vop_types)
    done = inst = 0
    for type_name in sorted(vop_types):
        done += 1
        try:
            node = container.createNode(type_name)
        except Exception as e:  # noqa: BLE001 -- context-specific VOPs won't build here
            out[type_name] = {"instantiated": False,
                              "note": f"createNode failed: {type(e).__name__}"}
            continue
        try:
            sig = _vop_signature(node, errors, type_name)
            sig["instantiated"] = True
            out[type_name] = sig
            inst += 1
        finally:
            try:
                node.destroy()
            except Exception:  # noqa: BLE001
                pass
        if done % 200 == 0:
            log(f"    [phase B] vop {done}/{total} instantiated={inst}")
    if disposable:
        try:
            container.destroy()
        except Exception:  # noqa: BLE001
            pass
    log(f"    [phase B] vop done: {inst}/{total} instantiated")
    return out


# ---------------------------------------------------------------------------
# APEX callback ports (phase C)
# ---------------------------------------------------------------------------

def _port_record(port) -> dict:
    rec = {}
    for key, attr in (("name", "name"), ("type", "type_name")):
        try:
            rec[key] = _jsonable(_read(port, attr))
        except Exception:  # noqa: BLE001
            pass
    for key, attr in (("in_place", "isInplace"),):
        try:
            rec[key] = _jsonable(_read(port, attr))
        except Exception:  # noqa: BLE001
            pass
    return rec


def build_apex_catalog(log, build) -> dict:
    import apex

    errors: list = []
    reg = apex.callbackRegistry()
    try:
        names = sorted(reg.callbackDefinitions())
    except Exception as e:  # noqa: BLE001
        errors.append(f"callbackDefinitions() failed: {type(e).__name__}: {e}")
        names = []
    try:
        subgraphs = sorted(reg.subGraphNames())
    except Exception as e:  # noqa: BLE001
        errors.append(f"subGraphNames() failed: {type(e).__name__}")
        subgraphs = []
    try:
        n_regs = len(apex.getRegistries())
    except Exception as e:  # noqa: BLE001
        errors.append(f"getRegistries() failed: {type(e).__name__}")
        n_regs = None

    callbacks: dict = {}
    total = len(names)
    done = 0
    for name in names:
        done += 1
        entry: dict = {}
        try:
            sig = reg.getSignature(name)
            entry["inputs"] = [_port_record(p) for p in sig.inputs()]
            entry["outputs"] = [_port_record(p) for p in sig.outputs()]
            try:
                entry["is_generic"] = _jsonable(_read(sig, "isGeneric"))
            except Exception:  # noqa: BLE001
                pass
        except Exception as e:  # noqa: BLE001
            errors.append(f"getSignature({name!r}): {type(e).__name__}")
        try:
            pd = reg.getParmDefaults(name)
            entry["parm_defaults"] = {str(k): _jsonable(v) for k, v in dict(pd).items()}
        except Exception:  # noqa: BLE001
            pass
        try:
            ov = reg.getOverloadSet(name)
            if ov is not None:
                entry["overloads"] = _jsonable(ov.getCallbacks())
        except Exception:  # noqa: BLE001
            pass
        callbacks[name] = entry
        if done % 500 == 0:
            log(f"    [phase C] apex callbacks {done}/{total}")
    log(f"    [phase C] apex done: {len(callbacks)} callbacks, {len(subgraphs)} subgraphs")

    stamp = hashlib.blake2b(
        json.dumps(callbacks, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        digest_size=16,
    ).hexdigest()
    return {
        "schema": APEX_SCHEMA,
        "build": build,
        "count": len(callbacks),
        "subgraph_count": len(subgraphs),
        "registry_count": n_regs,
        "blake2b": stamp,
        "generated": {"by": "scripts/build_node_catalog.py (phase C)",
                      "note": "deterministic: sorted, no wall-clock stamp"},
        "callbacks": callbacks,
        "subgraph_names": subgraphs,
        "probe_errors": sorted(errors),
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _stamp_types(types: dict) -> str:
    return hashlib.blake2b(
        json.dumps(types, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        digest_size=16,
    ).hexdigest()


def _write_json(fp: Path, payload: dict) -> None:
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n",
    )


def _parse_args(argv):
    opts = {"categories": None, "limit": None, "vop": True, "apex": True, "out": None}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--categories" and i + 1 < len(argv):
            opts["categories"] = set(argv[i + 1].split(",")); i += 1
        elif a == "--limit" and i + 1 < len(argv):
            opts["limit"] = int(argv[i + 1]); i += 1
        elif a == "--no-vop":
            opts["vop"] = False
        elif a == "--no-apex":
            opts["apex"] = False
        elif a == "--out" and i + 1 < len(argv):
            opts["out"] = Path(argv[i + 1]); i += 1
        i += 1
    return opts


def main() -> int:
    import hou

    opts = _parse_args(sys.argv[1:])
    log = lambda s: sys.stdout.write(s + "\n") or sys.stdout.flush()

    build = hou.applicationVersionString()
    out_dir = opts["out"] or (_REPO / "rag" / "catalog" / f"h{build}")
    cats = hou.nodeTypeCategories()
    log(f"NODE CATALOG DUMP: build={build} categories={len(cats)} -> {out_dir}")

    manifest_files: dict = {}
    grand_errors: list = []
    vop_types_cache: dict = {}

    # -- Phase A: node + parm walk, one file per category --
    for cat_name in sorted(cats):
        if opts["categories"] and cat_name not in opts["categories"]:
            continue
        category = cats[cat_name]
        try:
            node_types = category.nodeTypes()
        except Exception as e:  # noqa: BLE001
            grand_errors.append(f"{cat_name}: nodeTypes() failed: {type(e).__name__}")
            node_types = {}
        names = sorted(node_types)
        if opts["limit"] is not None:
            names = names[: opts["limit"]]
        errors: list = []
        types: dict = {}
        for type_name in names:
            types[type_name] = _type_record(node_types[type_name], type_name, errors)
        if cat_name == "Vop":
            vop_types_cache = {n: node_types[n] for n in names}
        payload = {
            "schema": SCHEMA,
            "build": build,
            "category": cat_name,
            "count": len(types),
            "blake2b": _stamp_types(types),
            "generated": {"by": "scripts/build_node_catalog.py (phase A)",
                          "note": "deterministic: sorted keys, no wall-clock stamp"},
            "types": types,
            "probe_errors": sorted(errors),
        }
        fp = out_dir / f"{cat_name}.json"
        _write_json(fp, payload)
        manifest_files[f"{cat_name}.json"] = {
            "category": cat_name, "count": len(types),
            "blake2b": payload["blake2b"], "probe_errors": len(errors)}
        grand_errors.extend(errors)
        log(f"  [phase A] {cat_name}: {len(types)} types, {len(errors)} errors "
            f"-> {fp.name}")

    # -- Phase B: VOP wire signatures merged into Vop.json --
    if opts["vop"] and vop_types_cache and (not opts["categories"] or "Vop" in opts["categories"]):
        log("  [phase B] instantiating Vop types for wire signatures...")
        verrors: list = []
        sigs = add_vop_signatures(hou, vop_types_cache, verrors, log)
        vop_fp = out_dir / "Vop.json"
        vop_payload = json.loads(vop_fp.read_text(encoding="utf-8"))
        inst = 0
        for tn, rec in vop_payload["types"].items():
            if tn in sigs:
                rec["wire_signature"] = sigs[tn]
                if sigs[tn].get("instantiated"):
                    inst += 1
        vop_payload["vop_signatures"] = {"instantiated": inst,
                                         "total": len(vop_payload["types"]),
                                         "probe_errors": len(verrors)}
        # Re-stamp: the signatures are part of Vop.json's verified surface now.
        vop_payload["blake2b"] = _stamp_types(vop_payload["types"])
        _write_json(vop_fp, vop_payload)
        manifest_files["Vop.json"]["blake2b"] = vop_payload["blake2b"]
        manifest_files["Vop.json"]["vop_instantiated"] = inst
        grand_errors.extend(verrors)
        log(f"  [phase B] merged signatures into Vop.json ({inst} instantiated)")

    # -- Phase C: APEX callback ports --
    if opts["apex"] and (not opts["categories"] or "apex" in {c.lower() for c in opts["categories"]} or opts["categories"] is None):
        try:
            import apex  # noqa: F401
            apex_ok = True
        except Exception as e:  # noqa: BLE001
            apex_ok = False
            grand_errors.append(f"apex import failed: {type(e).__name__}: {e}")
            log(f"  [phase C] SKIPPED -- apex import failed: {e}")
        if apex_ok:
            log("  [phase C] dumping apex callback registry...")
            apex_cat = build_apex_catalog(log, build)
            _write_json(out_dir / "apex_callbacks.json", apex_cat)
            manifest_files["apex_callbacks.json"] = {
                "count": apex_cat["count"],
                "subgraph_count": apex_cat["subgraph_count"],
                "blake2b": apex_cat["blake2b"],
                "probe_errors": len(apex_cat["probe_errors"])}
            grand_errors.extend(apex_cat["probe_errors"])

    # -- Manifest --
    manifest = {
        "schema": "node_catalog_manifest/v1",
        "build": build,
        "category_count": len(cats),
        "files": dict(sorted(manifest_files.items())),
        "generated": {"by": "scripts/build_node_catalog.py",
                      "note": "deterministic: sorted, no wall-clock stamp"},
        "total_probe_errors": len(grand_errors),
    }
    _write_json(out_dir / "_manifest.json", manifest)

    cat_files = [f for f in manifest_files.values() if "category" in f]
    total_types = sum(f.get("count", 0) for f in cat_files)
    log(f"DONE: build={build} category_files={len(cat_files)} "
        f"node_types={total_types} probe_errors={len(grand_errors)} -> {out_dir}")
    for err in grand_errors[:40]:
        log(f"  ERROR: {err}")
    if len(grand_errors) > 40:
        log(f"  ... and {len(grand_errors) - 40} more errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
