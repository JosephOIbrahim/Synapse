"""
host/introspect_connectivity.py  —  U.1 probe: network-wiring truth (HOST LAYER)
================================================================================

Utility-flywheel cycle U.1, EXPLORE phase (``harness/notes/
spec-U1-wiring-flywheel.md``). For every node-type string SYNAPSE emits
(``python/synapse/cognitive/tools/data/emitted_node_types.json``) PLUS every
Sop type whose name matches ``solver|merge|switch|blend``, resolve it against
the live catalog and record the wiring surface per resolved (category, type):

    min_inputs / max_inputs      — type-level (hou.NodeType.minNumInputs/
                                   maxNumInputs; variadic reports a large
                                   finite cap, e.g. Sop/merge=9999, NOT -1)
    output_count                 — type-level (hou.NodeType.maxNumOutputs)
    input_labels / output_labels — INSTANCE-level only in 21.0.671
                                   (hou.Node.inputLabels()/outputLabels();
                                   the type-level accessors are PHANTOM —
                                   see verified_connectivity v1). The probe
                                   instantiates one throwaway node per type
                                   in a category-appropriate container,
                                   reads the labels, destroys the node.

All three probe APIs scout-verified against the introspected 21.0.671 symbol
table (exists_in_runtime=true): hou.Node.inputLabels, hou.Node.outputLabels,
hou.NodeType.{minNumInputs,maxNumInputs,maxNumOutputs}.

RUN IT INSIDE THE TARGET BUILD:

    "C:/Program Files/Side Effects Software/Houdini 21.0.671/bin/hython.exe" \
        host/introspect_connectivity.py

Writes ``harness/notes/verified_connectivity_<build>.json`` with schema
``verified_connectivity/v2``. The v1 payload (Mile-2 §2.5 preflight: symbol
presence, phantom list, spot-checked arity values) is PRESERVED under
``v1_preserved`` with a provenance marker — the probe does not re-derive
dir()-membership facts, so it never discards them.

DETERMINISM: a second run on the same build is byte-identical — entries and
keys are sorted, and there is NO wall-clock stamp (``generated`` describes the
generator, not the moment). The blake2b stamp covers the sorted entries.

Zero-``synapse``-import, like host/introspect_nodetypes.py — the host layer
never imports the package. ``hou`` is imported inside functions so this module
also imports cleanly on stock Python for the pure test suite.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = "verified_connectivity/v2"
_REPO = Path(__file__).resolve().parents[1]
EMITTED_JSON = (_REPO / "python" / "synapse" / "cognitive" / "tools" / "data"
                / "emitted_node_types.json")
NOTES_DIR = _REPO / "harness" / "notes"

# Sop pattern expansion: wiring bugs cluster on multi-input types.
SOP_NAME_PATTERN = re.compile(r"solver|merge|switch|blend", re.IGNORECASE)

_VERSION_COMPONENT = re.compile(r"^[0-9][0-9.]*$")


def _strip_version(full_name: str) -> str:
    parts = full_name.split("::")
    if len(parts) > 1 and _VERSION_COMPONENT.match(parts[-1]):
        return "::".join(parts[:-1])
    return full_name


def _matches(emitted: str, full_name: str) -> bool:
    """Does catalog ``full_name`` satisfy the emitted spelling? Lockstep with
    host/introspect_nodetypes._matches (what createNode(emitted) accepts)."""
    if full_name == emitted:
        return True
    base = _strip_version(full_name)
    if base == emitted:
        return True
    if "::" not in emitted and base.split("::")[-1] == emitted:
        return True
    return False


# ---------------------------------------------------------------------------
# Containers — one throwaway parent per category, created lazily, destroyed
# at the end. Headless-safe: this runs in an isolated hython process; the
# user's session is never touched (same posture as the nodetype probe).
# ---------------------------------------------------------------------------

def _make_container(hou, cat_name: str):
    """A parent network that can host nodes of category ``cat_name``, or None."""
    if cat_name == "Object":
        return hou.node("/obj")
    if cat_name == "Lop":
        return hou.node("/stage")
    if cat_name == "Driver":
        return hou.node("/out")
    if cat_name == "Sop":
        return hou.node("/obj").createNode("geo", "u1_probe_sop")
    if cat_name == "Dop":
        return hou.node("/obj").createNode("dopnet", "u1_probe_dop")
    if cat_name == "Cop":
        return hou.node("/obj").createNode("copnet", "u1_probe_cop")
    if cat_name == "Cop2":
        img = hou.node("/img")
        return img.createNode("img", "u1_probe_cop2") if img else None
    if cat_name == "Top":
        return hou.node("/obj").createNode("topnet", "u1_probe_top")
    if cat_name == "Vop":
        return hou.node("/mat")
    return None  # Chop/Shop/Manager/...: not needed by the emitted surface


class _Containers:
    def __init__(self, hou):
        self._hou = hou
        self._cache: dict = {}
        self._created: list = []

    def get(self, cat_name: str):
        if cat_name not in self._cache:
            try:
                parent = _make_container(self._hou, cat_name)
            except Exception:  # noqa: BLE001 — container is best-effort
                parent = None
            self._cache[cat_name] = parent
            if parent is not None and parent.path().startswith("/obj/u1_probe"):
                self._created.append(parent)
        return self._cache[cat_name]

    def teardown(self) -> None:
        for node in self._created:
            try:
                node.destroy()
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# Per-type probe
# ---------------------------------------------------------------------------

def _probe_instance(hou, parent, full_name: str, errors: list) -> dict:
    """Instantiate ``full_name`` under ``parent``, read the instance-level
    wiring surface, destroy the node. Returns the instance fields."""
    out = {"instantiated": False, "input_labels": None, "output_labels": None}
    if parent is None:
        out["note"] = "no container for this category"
        return out
    try:
        node = parent.createNode(full_name)
    except Exception as e:  # noqa: BLE001 — best-effort; recorded, not fatal
        out["note"] = f"createNode failed: {type(e).__name__}"
        return out
    try:
        out["instantiated"] = True
        try:
            out["input_labels"] = [str(l) for l in node.inputLabels()]
        except Exception as e:  # noqa: BLE001
            errors.append(f"inputLabels failed on {full_name}: {e}")
        try:
            out["output_labels"] = [str(l) for l in node.outputLabels()]
        except Exception as e:  # noqa: BLE001
            errors.append(f"outputLabels failed on {full_name}: {e}")
    finally:
        try:
            node.destroy()
        except Exception:  # noqa: BLE001
            pass
    return out


def _type_entry(hou, node_type, cat_name: str, full_name: str,
                sources: list, containers: _Containers, errors: list) -> dict:
    entry = {
        "category": cat_name,
        "type_name": full_name,
        "sources": sorted(set(sources)),
        "min_inputs": None,
        "max_inputs": None,
        "output_count": None,
    }
    try:
        entry["min_inputs"] = node_type.minNumInputs()
        entry["max_inputs"] = node_type.maxNumInputs()
    except Exception as e:  # noqa: BLE001
        errors.append(f"arity read failed for {cat_name}/{full_name}: {e}")
    try:
        entry["output_count"] = node_type.maxNumOutputs()
    except Exception as e:  # noqa: BLE001
        errors.append(f"maxNumOutputs failed for {cat_name}/{full_name}: {e}")
    entry.update(_probe_instance(hou, containers.get(cat_name), full_name, errors))
    return entry


# ---------------------------------------------------------------------------
# Target collection: emitted types (all categories) + Sop pattern expansion
# ---------------------------------------------------------------------------

def _collect_targets(hou, emitted_path: Path, errors: list) -> dict:
    """{(cat_name, full_name): {"node_type": ..., "sources": [...]}}"""
    targets: dict = {}

    def add(cat_name, full_name, node_type, source):
        key = (cat_name, full_name)
        if key not in targets:
            targets[key] = {"node_type": node_type, "sources": []}
        targets[key]["sources"].append(source)

    emitted = json.loads(Path(emitted_path).read_text(encoding="utf-8"))
    cats = hou.nodeTypeCategories()
    for src in emitted["entries"]:
        spelling = src["type_name"]
        for cat_name in sorted(cats):
            category = cats[cat_name]
            hits = {}
            try:
                exact = hou.nodeType(category, spelling)
            except Exception as e:  # noqa: BLE001
                errors.append(f"nodeType({cat_name}, {spelling!r}) raised: {e}")
                exact = None
            if exact is not None:
                hits[exact.name()] = exact
            try:
                for full_name, node_type in category.nodeTypes().items():
                    if full_name not in hits and _matches(spelling, full_name):
                        hits[full_name] = node_type
            except Exception as e:  # noqa: BLE001
                errors.append(f"nodeTypes() scan failed in {cat_name}: {e}")
            for full_name, node_type in hits.items():
                add(cat_name, full_name, node_type, f"emitted:{spelling}")

    # Sop pattern expansion
    sop_cat = cats.get("Sop")
    if sop_cat is not None:
        for full_name, node_type in sop_cat.nodeTypes().items():
            if SOP_NAME_PATTERN.search(full_name):
                add("Sop", full_name, node_type, "sop_pattern")
    else:  # pragma: no cover — a Houdini without SOPs
        errors.append("no Sop category in this build")

    # Full Lop sweep. Seeding Solaris coverage from the emitted list alone made
    # the catalog circular: it could only describe wiring for node types SYNAPSE
    # already built, so it could never learn one it had not already shipped
    # (37 of 218 on 22.0.368). Solaris is the wiring surface artists drive, so
    # the whole category is swept — same posture as the Sop pattern expansion
    # above, widened from a name pattern to the category.
    lop_cat = cats.get("Lop")
    if lop_cat is not None:
        for full_name, node_type in lop_cat.nodeTypes().items():
            add("Lop", full_name, node_type, "lop_sweep")
    else:  # pragma: no cover — a Houdini without LOPs
        errors.append("no Lop category in this build")
    return targets


# ---------------------------------------------------------------------------
# Catalog assembly
# ---------------------------------------------------------------------------

def build_catalog(emitted_path: Path = EMITTED_JSON) -> dict:
    import hou

    errors: list = []
    containers = _Containers(hou)
    # Simulation guard (rag_dop_simulation_guard): instantiating DOP types must
    # not cook a simulation mid-probe. hou.setSimulationEnabled is scout-verified
    # (exists_in_runtime=true, documented) on 21.0.671.
    sim_was = True
    try:
        sim_was = hou.simulationEnabled()
        hou.setSimulationEnabled(False)
    except Exception as e:  # noqa: BLE001 — guard is best-effort, surfaced
        errors.append(f"simulation guard unavailable: {e}")
    try:
        targets = _collect_targets(hou, emitted_path, errors)
        entries = {}
        for (cat_name, full_name) in sorted(targets):
            info = targets[(cat_name, full_name)]
            entries[f"{cat_name}/{full_name}"] = _type_entry(
                hou, info["node_type"], cat_name, full_name,
                info["sources"], containers, errors)
    finally:
        containers.teardown()
        try:
            hou.setSimulationEnabled(sim_was)
        except Exception:  # noqa: BLE001
            pass

    # Fold in every v1 key the probe cannot re-derive (dir()-membership facts,
    # the phantom list, the §2.5 spot checks) — provenance-marked, not discarded.
    v1_preserved = None
    v1_fp = NOTES_DIR / f"verified_connectivity_{hou.applicationVersionString()}.json"
    if v1_fp.exists():
        try:
            prior = json.loads(v1_fp.read_text(encoding="utf-8"))
            if prior.get("schema") == SCHEMA:          # already v2 — keep its fold
                v1_preserved = prior.get("v1_preserved")
            else:                                       # genuine v1 payload
                v1_preserved = {
                    "_provenance": (
                        "carried verbatim from verified_connectivity v1 (Mile-2 "
                        "§2.5 preflight, dir()-confirmed on live 21.0.671; "
                        "harness/notes/mile2_2_5_introspect.py) — NOT re-derived "
                        "by host/introspect_connectivity.py"
                    ),
                    "_doc": prior.get("_doc"),
                    "symbols_present": prior.get("symbols_present"),
                    "symbols_PHANTOM_do_not_use": prior.get("symbols_PHANTOM_do_not_use"),
                    "verified_values": prior.get("verified_values"),
                }
        except Exception as e:  # noqa: BLE001 — surface, don't silently drop v1
            errors.append(f"could not fold prior file: {e}")

    stamp = hashlib.blake2b(
        json.dumps(entries, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        digest_size=16,
    ).hexdigest()
    return {
        "schema": SCHEMA,
        "houdini_version": hou.applicationVersionString(),
        "blake2b": stamp,
        "generated": {
            "by": "host/introspect_connectivity.py",
            "from": str(Path(emitted_path).relative_to(_REPO)).replace("\\", "/"),
            "note": ("deterministic: no wall-clock stamp — a second run on the "
                     "same build must be byte-identical (the U.1 determinism pin)"),
        },
        "entries": entries,
        "v1_preserved": v1_preserved,
        "probe_errors": sorted(errors),
    }


def main() -> int:
    catalog = build_catalog()
    build = catalog["houdini_version"]
    out_fp = NOTES_DIR / f"verified_connectivity_{build}.json"
    out_fp.parent.mkdir(parents=True, exist_ok=True)
    out_fp.write_text(
        json.dumps(catalog, sort_keys=True, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n",
    )

    entries = catalog["entries"]
    n_inst = sum(1 for e in entries.values() if e.get("instantiated"))
    n_lab = sum(1 for e in entries.values() if e.get("input_labels"))
    errors = catalog["probe_errors"]
    sys.stdout.write(
        f"CONNECTIVITY: build={build} types={len(entries)} instantiated={n_inst} "
        f"with_input_labels={n_lab} probe_errors={len(errors)} "
        f"blake2b={catalog['blake2b'][:12]} -> {out_fp}\n"
    )
    for err in errors:
        sys.stdout.write(f"  ERROR: {err}\n")
    for probe_key in ("Sop/vellumsolver", "Sop/rbdbulletsolver"):
        e = entries.get(probe_key)
        if e:
            sys.stdout.write(
                f"  {probe_key}: in[{e['min_inputs']},{e['max_inputs']}] "
                f"out={e['output_count']} labels={e['input_labels']}\n"
            )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
