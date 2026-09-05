"""Catalog-checked Solaris v2 definitions; no host imports or scene mutation.

Structural acceptance is not golden qualification. A PENDING_HUMAN definition
loads as a RecipeSpec with BLOCKED availability. Publication and runtime
execution must remain closed until a separately verified golden exists.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from synapse.blocks.fixtures import FixtureError, repo_root, validate_fixture
from synapse.recipes import canon
from synapse.recipes.contracts import (
    ActionId, ActionSpec, Availability, CheckId, DEMO_PHRASES, PermissionCategory,
    RecipeSpec, RECIPE_ID, REQUIRED_CHECKS, SCHEMA_VERSION, SUPPORTED_BUILD, SlotSchema,
)


class RecipeSpecError(FixtureError):
    """A definition is malformed or cannot be resolved against pinned evidence."""


@dataclass(frozen=True)
class LoadedRecipeSpec(RecipeSpec):
    """Seam-compatible view; availability is derived, never a JSON assertion."""

    @property
    def availability(self) -> Availability:
        return recipe_availability(self)

    @property
    def availability_reason(self) -> str:
        if self.golden_reference["status"] == "PENDING_HUMAN":
            return "PENDING_HUMAN: golden HIP, reference render and dependency record are absent"
        return "Golden capture is recorded; independent rebuild/render qualification is NOT_RUN"


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise RecipeSpecError(reason)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def catalog_digest(path: Path | str | None = None) -> str:
    """SHA256 of the actual catalog file, not its embedded pre-doc-join hash."""
    path = Path(path) if path is not None else repo_root() / "rag/catalog/h22.0.400/Lop.json"
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise RecipeSpecError(f"catalog unavailable: {path}: {exc}") from exc


def _catalogs(directory: Path | None) -> tuple[dict, dict]:
    directory = directory if directory is not None else repo_root() / "rag/catalog/h22.0.400"
    catalogs, digests = {}, {}
    for category in ("Lop", "Vop"):
        path = directory / f"{category}.json"
        try:
            raw = path.read_bytes()
            catalog = json.loads(raw)
        except (OSError, ValueError) as exc:
            raise RecipeSpecError(f"{category} catalog unavailable: {exc}") from exc
        _require(catalog.get("build") == SUPPORTED_BUILD and catalog.get("category") == category,
                 f"wrong supported_build/category in {category} catalog")
        catalogs[category] = catalog["types"]
        digests[category] = hashlib.sha256(raw).hexdigest()
    return catalogs, digests


def catalog_ports(entry: Mapping[str, Any]) -> dict:
    """The instantiated VOP signature outranks misleading max_inputs (e.g. 0).

    H22 mtlxsurfacematerial has max_inputs=0 but an instantiated three-input
    wire_signature. Never infer VOP ports from a parameter list or type limits.
    """
    signature = entry.get("wire_signature")
    _require(isinstance(signature, Mapping) and signature.get("instantiated") is True,
             "unresolved VOP ports: no instantiated catalog signature")
    ports = {}
    for direction in ("input", "output"):
        names, types = signature.get(f"{direction}_names"), signature.get(f"{direction}_data_types")
        _require(isinstance(names, list) and isinstance(types, list) and len(names) == len(types),
                 "unresolved VOP ports: incomplete catalog signature")
        ports[direction + "s"] = [
            {"index": index, "name": name, "data_type": data_type}
            for index, (name, data_type) in enumerate(zip(names, types))
        ]
    return ports


def _parm_template(entry: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    for parm in entry["parms"]:
        pattern = re.escape(parm["name"]).replace(r"\#", "[1-9][0-9]*")
        if re.fullmatch(pattern, name):
            return parm
    raise RecipeSpecError(f"unresolved parameter {name!r} in catalog")


def _validate_parm(name: str, parm: Mapping[str, Any], template: Mapping[str, Any]) -> None:
    _require(isinstance(parm, Mapping) and "type" in parm and "value" in parm,
             f"typed parameter required: {name}")
    _require(set(parm) <= {"type", "value", "expression"}, f"unknown parameter fields: {name}")
    kind, value = parm["type"], parm["value"]
    sizes = {"float": 1, "int": 1, "bool": 1, "str": 1, "path": 1,
             "enum": 1, "color3": 3, "float2": 2, "float3": 3, "int2": 2}
    _require(kind in sizes, f"unknown parameter type: {name}")
    size = sizes[kind]
    values = value if size > 1 and isinstance(value, (list, tuple)) else [value]
    _require(len(values) == size, f"parameter component count: {name}")
    if kind in ("float", "float2", "float3", "color3"):
        valid = all(_number(v) for v in values)
    elif kind in ("int", "int2"):
        valid = all(type(v) is int for v in values)
    elif kind == "bool":
        valid = type(value) is bool
    else:
        valid = isinstance(value, str)
    _require(valid, f"parameter type/nonfinite value: {name}")
    _require(template.get("type") not in ("Button", "FolderSet", "Label"),
             f"non-authorable parameter: {name}")
    expected = template.get("data_type")
    compatible = (expected == "Float" and kind in ("float", "float2", "float3", "color3") or
                  expected == "Int" and kind in ("int", "int2", "bool") or
                  expected == "String" and kind in ("str", "path", "enum") or
                  template.get("menu_tokens") and kind == "enum")
    _require(bool(compatible) and template["num_components"] == size,
             f"parameter catalog type mismatch: {name}")
    if template.get("menu_tokens"):
        _require(value in template["menu_tokens"], f"unresolved menu token: {name}")
    if "expression" in parm:
        expression = parm["expression"]
        _require(isinstance(expression, Mapping) and set(expression) == {"language", "text"}
                 and expression["language"] in ("hscript", "python")
                 and isinstance(expression["text"], str) and bool(expression["text"]),
                 f"invalid authored expression: {name}")


# One baseline, not an arbitrary asset-ingest schema. These are graph roles,
# not scene names: IDs remain stable references selected by the curated author.
_ROLES = {
    "hero": ("Lop", "sphere"), "ground": ("Lop", "plane"),
    "materials": ("Lop", "materiallibrary"), "bindings": ("Lop", "assignmaterial"),
    "hero_shader": ("Vop", "mtlxstandard_surface"),
    "hero_material": ("Vop", "mtlxsurfacematerial"),
    "ground_shader": ("Vop", "mtlxstandard_surface"),
    "ground_material": ("Vop", "mtlxsurfacematerial"),
    "dome_light": ("Lop", "domelight::3.0"), "key_light": ("Lop", "light::2.0"),
    "camera": ("Lop", "camera"), "render_settings": ("Lop", "karmarendersettings"),
    "render": ("Lop", "usdrender_rop"), "output": ("Lop", "null"),
}


def _nodes_and_wires(spec: RecipeSpec, catalogs: dict) -> dict:
    _require(bool(spec.nodes), "missing subgraphs: nodes are empty")
    by_id, roles = {}, {}
    for node in spec.nodes:
        _require(isinstance(node, Mapping) and all(key in node for key in (
            "id", "parent_id", "category", "type", "parms", "flags", "position", "role",
        )), "node missing required fields")
        _require(set(node) <= {"id", "parent_id", "category", "type", "parms", "flags", "position", "role", "ports"},
                 "unknown node fields; expressions belong to typed parameters")
        nid = node["id"]
        _require(isinstance(nid, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", nid) is not None,
                 "node id must be a local identifier")
        _require(nid not in by_id, f"duplicate node id: {nid}")
        category, node_type = node["category"], node["type"]
        _require(category in catalogs and node_type in catalogs[category],
                 f"unresolved type alias: {category}/{node_type}")
        entry = catalogs[category][node_type]
        role = node["role"]
        _require(role in _ROLES and role not in roles, f"missing subgraphs/duplicate or unknown role: {role}")
        _require((category, node_type) == _ROLES[role], f"wrong baseline type for {role}")
        roles[role], by_id[nid] = node, node
        pos = node["position"]
        _require(isinstance(pos, (list, tuple)) and len(pos) == 2 and all(_number(v) for v in pos),
                 f"invalid position: {nid}")
        flags = node["flags"]
        _require(isinstance(flags, Mapping) and set(flags) == {"display", "render", "bypass", "material"}
                 and all(type(v) is bool for v in flags.values()), f"invalid flags: {nid}")
        _require(not flags["bypass"], f"missing subgraphs: bypassed {nid}")
        _require(isinstance(node["parms"], Mapping), f"invalid parms: {nid}")
        for name, parm in node["parms"].items():
            _validate_parm(name, parm, _parm_template(entry, name))
        if category == "Vop":
            _require(canon.plain(node.get("ports")) == catalog_ports(entry),
                     f"unresolved VOP ports: {nid} does not match catalog")
        else:
            _require("ports" not in node, f"LOP named ports were not captured in catalog: {nid}")
    _require(set(roles) == set(_ROLES), "missing subgraphs: " + ", ".join(sorted(set(_ROLES) - set(roles))))
    for node in spec.nodes:
        expected = roles["materials"]["id"] if node["category"] == "Vop" else None
        _require(node["parent_id"] == expected, f"missing subgraphs/wrong parent: {node['id']}")
    edges, destinations = set(), set()
    for wire in spec.connections:
        _require(isinstance(wire, Mapping) and all(key in wire for key in ("src_id", "src_output", "dst_id", "dst_input")),
                 "connection missing required fields")
        _require(set(wire) <= {"src_id", "src_output", "dst_id", "dst_input", "src_port", "dst_port"},
                 "unknown connection fields")
        _require(wire["src_id"] in by_id and wire["dst_id"] in by_id, "connection references missing node")
        src, dst = by_id[wire["src_id"]], by_id[wire["dst_id"]]
        _require(src["parent_id"] == dst["parent_id"], "connection crosses parent scope")
        for node, direction, key in ((src, "outputs", "src_output"), (dst, "inputs", "dst_input")):
            index = wire[key]
            _require(type(index) is int and index >= 0, "connection port index must be nonnegative integer")
            if node["category"] == "Vop":
                ports = node["ports"][direction]
                _require(index < len(ports) and wire.get("src_port" if key == "src_output" else "dst_port") == ports[index]["name"],
                         "unresolved VOP ports: connection identity/index mismatch")
            else:
                limit = catalogs["Lop"][node["type"]]["max_" + direction]
                _require(index < limit, "connection outside catalog port limits")
        if src["category"] == "Vop":
            _require(src["ports"]["outputs"][wire["src_output"]]["data_type"] == dst["ports"]["inputs"][wire["dst_input"]]["data_type"],
                     "unresolved VOP ports: incompatible data types")
        destination = (dst["id"], wire["dst_input"])
        _require(destination not in destinations, "duplicate destination input")
        destinations.add(destination)
        edges.add((src["role"], wire["src_output"], dst["role"], wire["dst_input"]))
    chain = ["hero", "ground", "materials", "bindings", "dome_light", "key_light", "camera", "render_settings", "output"]
    expected_edges = {(a, 0, b, 0) for a, b in zip(chain, chain[1:])}
    expected_edges.add(("render_settings", 0, "render", 0))
    for prefix in ("hero", "ground"):
        shader, material = roles[prefix + "_shader"], roles[prefix + "_material"]
        outputs, inputs = shader["ports"]["outputs"], material["ports"]["inputs"]
        output_index = next(p["index"] for p in outputs if p["name"] == "out")
        input_index = next(p["index"] for p in inputs if p["name"] == "surfaceshader")
        expected_edges.add((shader["role"], output_index, material["role"], input_index))
    _require(edges == expected_edges, "missing subgraphs: incomplete material or render branch topology")
    return roles


def _value(node: Mapping[str, Any], name: str) -> Any:
    _require(name in node["parms"], f"empty required material/parameter definition: {node['id']}.{name}")
    return node["parms"][name]["value"]


def _prim_path(value: Any) -> bool:
    # This one curated scene uses absolute ASCII prim identifiers. Patterns,
    # properties and relative paths cannot stand in for binding destinations.
    return isinstance(value, str) and re.fullmatch(r"(?:/[A-Za-z_][A-Za-z0-9_]*)+", value) is not None


def _baseline(roles: dict) -> None:
    library, binding = roles["materials"], roles["bindings"]
    _require(_value(library, "materials") == 2 and _value(binding, "nummaterials") == 2,
             "empty required material definitions: exactly two materials/bindings required")
    for index, role in enumerate(("hero", "ground"), 1):
        suffix = str(index)
        material, shader, geo = roles[role + "_material"], roles[role + "_shader"], roles[role]
        color = _value(shader, "base_color")
        _require(shader["parms"]["base_color"]["type"] == "color3" and all(0 <= v <= 1 for v in color),
                 "empty required material definitions: bounded base_color required")
        _require(material["flags"]["material"], "material output flag required")
        _require(_value(library, "matnode" + suffix) == material["id"], "material VOP target is not declared output")
        path = _value(library, "matpath" + suffix)
        _require(_prim_path(path), "material path must be an explicit prim path")
        _require(_value(binding, "matspecpath" + suffix) == path and
                 _value(binding, "primpattern" + suffix) == _value(geo, "primpath"), "invalid material binding")
        _require(_value(binding, "matspecmethod" + suffix) == "path" and
                 _value(library, "assign" + suffix) is False, "material bindings must use the explicit binding node")
    paths = [_value(roles[role], "primpath") for role in ("hero", "ground", "dome_light", "key_light", "camera", "render_settings")]
    _require(len(set(paths)) == len(paths) and all(_prim_path(p) for p in paths),
             "prim paths must be distinct explicit paths")
    _require(_value(library, "matpath1") != _value(library, "matpath2"), "materials must have distinct paths")
    _require(_value(roles["render_settings"], "camera") == _value(roles["camera"], "primpath"), "invalid render camera binding")
    _require(_value(roles["render"], "rendersettings") == _value(roles["render_settings"], "primpath"), "render settings target missing")
    _require(_value(roles["render"], "loppath") == "", "render branch must use its explicit input")
    _require(_value(roles["render_settings"], "engine") == "cpu", "one pinned Karma engine required")
    for role in ("key_light", "dome_light"):
        _require(_value(roles[role], "xn__inputsexposure_control_wcb") == "set", "exposure must be authored")
        _value(roles[role], "xn__inputsexposure_vya")
    for role, node in roles.items():
        _require(node["flags"]["display"] == (role == "output"), "display output must be unique")


def _actions(spec: RecipeSpec, roles: dict) -> None:
    actions = {action.action_id: action for action in spec.actions}
    _require(len(spec.actions) == len(ActionId) and set(actions) == set(ActionId), "all four actions required exactly once")
    expected_slots = {
        ActionId.BUILD: {},
        ActionId.LIGHT: {"exposure": ("float", "key_light", "xn__inputsexposure_vya")},
        ActionId.MATERIAL: {"color": ("color3", "hero_shader", "base_color")},
        ActionId.RENDER: {"resolution": ("enum", "render_settings", "resolution"),
                          "samples": ("int", "render_settings", "pathtracedsamples"),
                          "engine": ("enum", "render_settings", "engine")},
    }
    for aid, action in actions.items():
        _require(action.required_checks == REQUIRED_CHECKS[aid], f"required_checks mismatch: {aid.value}")
        _require(action.phrases == DEMO_PHRASES[aid], f"phrases mismatch: {aid.value}")
        scope = "graph" if aid == ActionId.BUILD else "render" if aid == ActionId.RENDER else "field"
        _require(action.effect_scope == scope, f"effect_scope mismatch: {aid.value}")
        permission = PermissionCategory.APPROVE if aid == ActionId.RENDER else PermissionCategory.REVIEW
        _require(action.permission == permission, f"permission mismatch: {aid.value}")
        slots = {slot.key: slot for slot in action.slots}
        _require(len(slots) == len(action.slots) and set(slots) == set(expected_slots[aid]), f"slot keys mismatch: {aid.value}")
        for key, (kind, role, parameter) in expected_slots[aid].items():
            slot = slots[key]
            _require(slot.type == kind and slot.binding == roles[role]["id"] + "." + parameter,
                     f"slot binding/type mismatch: {key}")
            if kind == "enum":
                _require(bool(slot.enum) and len(set(slot.enum)) == len(slot.enum) and all(isinstance(v, str) for v in slot.enum), "invalid slot enum")
                _require(slot.min is None and slot.max is None, "enum bounds belong to typed presets")
                if key == "engine":
                    _require(slot.enum == ("cpu",), "one pinned engine enum required")
            else:
                _require(_number(slot.min) and _number(slot.max) and slot.min <= slot.max and not slot.enum,
                         f"finite slot bounds required: {key}")
                if kind == "int":
                    _require(type(slot.min) is int and type(slot.max) is int and 1 <= slot.min <= slot.max <= 64, "positive bounded integer samples required")
                if kind == "float":
                    _require(-10 <= slot.min <= slot.max <= 10, "exposure bounds exceed curated limits")
                if kind == "color3":
                    _require(slot.min == 0 and slot.max == 1, "color bounds must be 0..1")
                current = _value(roles[role], parameter)
                values = current if kind == "color3" else [current]
                _require(all(slot.min <= value <= slot.max for value in values), f"default outside slot bounds: {key}")
    presets = spec.presentation.get("resolution_presets")
    resolutions = {slot.key: slot for slot in actions[ActionId.RENDER].slots}["resolution"].enum
    _require(isinstance(presets, Mapping) and set(presets) == set(resolutions), "resolution enum requires exact typed presets")
    for key, size in presets.items():
        _require(isinstance(size, (list, tuple)) and len(size) == 2 and all(type(v) is int and 1 <= v <= 256 for v in size)
                 and key == f"{size[0]}x{size[1]}", "resolution preset must be a bounded int2")
    _require(canon.plain(_value(roles["render_settings"], "resolution")) in [canon.plain(v) for v in presets.values()], "default resolution outside presets")


def recipe_availability(spec: RecipeSpec) -> Availability:
    """No pure schema check can promote a real-host qualification to READY."""
    return Availability.BLOCKED if spec.golden_reference.get("status") == "PENDING_HUMAN" else Availability.EXPERIMENTAL


def _validate_recipe_spec(spec: RecipeSpec, *, catalog_dir: Path | None = None) -> Availability:
    _require(isinstance(spec, RecipeSpec), "expected RecipeSpec")
    _require(spec.recipe_id == RECIPE_ID and spec.schema_version == SCHEMA_VERSION, "wrong recipe/schema version")
    _require(isinstance(spec.version, str) and re.fullmatch(r"\d+\.\d+\.\d+", spec.version) is not None, "invalid recipe version")
    _require(spec.supported_build == SUPPORTED_BUILD, "wrong supported_build")
    catalogs, digests = _catalogs(catalog_dir)
    _require(spec.catalog_digest == digests["Lop"], "catalog_digest mismatch: Lop.json bytes changed")
    _require(spec.presentation.get("vop_catalog_digest") == digests["Vop"], "catalog_digest mismatch: Vop.json bytes changed")
    _require(spec.canonicalizer == canon.CANONICALIZER_VERSION and spec.presentation.get("canonicalizer_digest") == canon.canonicalizer_digest(), "canonicalizer digest/version mismatch")
    reference = spec.golden_reference
    _require(isinstance(reference, Mapping) and all(key in reference for key in ("status", "hip", "reference_render", "dependency_record")), "golden_reference is required and must be complete")
    if reference["status"] == "PENDING_HUMAN":
        _require(all(reference[key] is None for key in ("hip", "reference_render", "dependency_record")), "PENDING_HUMAN cannot claim golden artifacts")
    else:
        _require(reference["status"] == "CAPTURED" and all(reference[key] for key in ("hip", "reference_render", "dependency_record")), "invalid golden_reference status/artifacts")
    roles = _nodes_and_wires(spec, catalogs)
    _baseline(roles)
    _actions(spec, roles)
    _require(spec.semantic_digest == canon.semantic_digest(spec), "semantic_digest mismatch")
    _require(spec.layout_digest == canon.layout_digest(spec), "layout_digest mismatch")
    return recipe_availability(spec)


def validate_recipe_spec(spec: RecipeSpec, *, catalog_dir: Path | None = None) -> Availability:
    """Reject malformed seam objects consistently, including hand-built objects."""
    try:
        return _validate_recipe_spec(spec, catalog_dir=catalog_dir)
    except RecipeSpecError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, StopIteration) as exc:
        raise RecipeSpecError(f"malformed recipe definition: {exc}") from exc


def recipe_spec_from_dict(raw: Mapping[str, Any], *, catalog_dir: Path | None = None) -> RecipeSpec:
    """Parse, validate and freeze one definition without mutating the input."""
    _require(isinstance(raw, Mapping), "recipe root must be an object")
    _require("golden_reference" in raw, "golden_reference key is required")
    try:
        actions = tuple(ActionSpec(
            action_id=ActionId(action["action_id"]),
            slots=tuple(SlotSchema(**dict(slot, enum=tuple(slot.get("enum", ())))) for slot in action["slots"]),
            required_checks=tuple(CheckId(check) for check in action["required_checks"]),
            effect_scope=action["effect_scope"], permission=PermissionCategory(action["permission"]),
            phrases=tuple(action["phrases"]),
        ) for action in raw["actions"])
        spec = LoadedRecipeSpec(**{key: raw[key] for key in (
            "recipe_id", "version", "schema_version", "supported_build", "catalog_digest",
            "canonicalizer", "semantic_digest", "layout_digest",
        )}, golden_reference=_freeze(raw["golden_reference"]), nodes=_freeze(raw["nodes"]),
            connections=_freeze(raw["connections"]), actions=actions,
            presentation=_freeze(raw.get("presentation", {})))
        validate_recipe_spec(spec, catalog_dir=catalog_dir)
    except RecipeSpecError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, StopIteration) as exc:
        raise RecipeSpecError(f"malformed recipe definition: {exc}") from exc
    return spec


def spec_to_fixture_v1(spec: RecipeSpec) -> dict:
    """Project ONLY the outer graph to the unchanged BLOCKS fixture vocabulary.

    This is a planning adapter, not a complete scene or publication permit.
    Nested records are retained under recipe_subgraphs for the lifecycle owner.
    A caller must enforce availability and build/verify those subgraphs before
    reporting completion. Nonzero outer source outputs and expressions cannot
    be represented by v1 and are refused instead of silently losing state.
    """
    availability = validate_recipe_spec(spec)
    outer = {node["id"]: node for node in spec.nodes if node["parent_id"] is None}
    nodes = []
    remaining = dict(outer)
    while remaining:
        ready = [node for nid, node in remaining.items() if not any(
            wire["dst_id"] == nid and wire["src_id"] in remaining for wire in spec.connections)]
        _require(bool(ready), "outer graph cycle")
        for node in ready:
            _require(not node.get("expressions") and not any("expression" in p for p in node["parms"].values()), "v1 adapter cannot represent expressions")
            nodes.append({"name": node["id"], "type": node["type"],
                          "parms": {key: canon.plain(parm["value"]) for key, parm in node["parms"].items()},
                          "position": canon.plain(node["position"]), "flags": canon.plain(node["flags"])})
            del remaining[node["id"]]
    wires, nested_wires = [], []
    for wire in spec.connections:
        if wire["src_id"] in outer and wire["dst_id"] in outer:
            _require(wire["src_output"] == 0, "v1 adapter cannot represent nonzero source output")
            wires.append([wire["dst_id"], wire["dst_input"], wire["src_id"]])
        else:
            nested_wires.append(canon.plain(wire))
    fixture = {"fixture": spec.recipe_id, "version": spec.version, "target_build": spec.supported_build,
               "ownership": {"network_box": "BLOCKS_solaris_spine"}, "nodes": nodes, "wires": wires,
               "display": next(n["id"] for n in outer.values() if n["flags"]["display"]),
               "recipe_availability": availability.value,
               "recipe_subgraphs": {"nodes": [canon.plain(n) for n in spec.nodes if n["parent_id"] is not None],
                                    "connections": nested_wires},
               "recipe_contract_only": True}
    validate_fixture(fixture)
    return fixture
