"""Independent Solaris recipe predicates (blueprint v3, p05/p08).

All six classes implement contracts.Verifier.run. No writer is called here.
Host reads are injected through ObservationReader or collected by HostObserver
on run_on_main. Raw observations may be injected for deterministic tests.
An unavailable/incomplete producer is UNKNOWN, never a successful fallback.

The frozen RecipeSpec has no predicate-specific fields. The additive adapter is
spec.golden_reference["verification"]; see VERIFY_TOLERANCES.md for its schema.
No captured expectations are inferred from node names or a first USD prim.
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Protocol

from .contracts import (
    ActionId, CheckId, CheckResult, CheckStatus, RecipeInstance, RecipeSpec,
    RecoveryVerdict,
)

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    hou = None
    HOU_AVAILABLE = False

try:
    from pxr import Sdf, UsdShade, UsdUtils
    PXR_AVAILABLE = True
except ImportError:
    Sdf = UsdShade = UsdUtils = None
    PXR_AVAILABLE = False


def _is_anonymous_layer_identifier(identifier: str) -> bool:
    """True for in-memory (``anon:``) layer identifiers; false for anything file-backed."""
    if Sdf is not None:
        return bool(Sdf.Layer.IsAnonymousLayerIdentifier(identifier))
    return identifier.startswith("anon:")


def _missing_file_assets(unresolved) -> list:
    """Keep only file-backed unresolved dependencies.

    Every live LOP stage is built from anonymous layers (``anon:...:LOP:rootlayer``,
    the session layer, per-node ``anon:...:LOP`` layers). ``UsdUtils.ComputeAllDependencies``
    reports the anonymous sublayers of those root/session layers as *unresolved*
    because they are not files -- they are not missing assets (VERIFIED-RUNTIME
    hython 22.0.400, 2026-09-05). A real missing file referenced from an anonymous
    LOP layer still surfaces here by its file path, so it is not dropped.
    """
    return [str(path) for path in unresolved if not _is_anonymous_layer_identifier(str(path))]


class EvidenceUnavailable(RuntimeError):
    """The required measurement has no trustworthy producer."""


class ObservationReader(Protocol):
    def observe(self, kind: str, instance: RecipeInstance,
                spec: RecipeSpec, **context: Any) -> Mapping[str, Any]: ...


def _json(value):
    # JSON roundtrip also detaches mutable writer-owned containers.
    return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _requirements(spec):
    value = spec.golden_reference.get("verification")
    if not isinstance(value, Mapping) or not value:
        raise EvidenceUnavailable("golden_reference.verification is not captured")
    return value


def _edge(edge):
    return tuple(edge[k] for k in ("src_id", "src_output", "dst_id", "dst_input"))


def _slot_value(slot, value):
    # Match the authored storage type declared by the slot, not JSON's choice
    # of integer spelling for a float parameter.
    if slot.type == "float":
        return float(value)
    if slot.type == "color3":
        return [float(component) for component in value]
    return value


def _expected_nodes(instance, spec, context):
    nodes = {n["id"]: copy.deepcopy(dict(n)) for n in spec.nodes}
    if not nodes or len(nodes) != len(spec.nodes):
        raise EvidenceUnavailable("spec must have nonempty, unique captured node IDs")
    bindings, slot_targets = {}, {}
    for action in spec.actions:
        for slot in action.slots:
            prior_target = slot_targets.setdefault(slot.key, slot.binding)
            if prior_target != slot.binding:
                raise EvidenceUnavailable("ambiguous slot key across actions: " + slot.key)
            if slot.key in instance.committed_slots:
                normalized = _slot_value(slot, instance.committed_slots[slot.key])
                old = bindings.get(slot.binding, normalized)
                if old != normalized:
                    raise EvidenceUnavailable("ambiguous committed slot binding")
                bindings[slot.binding] = normalized
    slots = context.get("slots", {})
    if slots:
        action = next((a for a in spec.actions if a.action_id == context.get("action")), None)
        if action is None or not set(slots) <= {s.key for s in action.slots}:
            raise EvidenceUnavailable("slot values require a declared action and bindings")
        bindings.update({s.binding: _slot_value(s, slots[s.key]) for s in action.slots if s.key in slots})
    for binding, value in bindings.items():
        node_id, parm = binding.rsplit(".", 1)
        if node_id not in nodes or parm not in nodes[node_id].get("parms", {}):
            raise EvidenceUnavailable("slot binding does not address a captured parameter: " + binding)
        old = nodes[node_id]["parms"][parm]
        if isinstance(old, Mapping) and "value" in old:
            # A value edit replaces expression authorship as well.
            nodes[node_id]["parms"][parm] = {**old, "value": value}
            for k in ("expression", "language"):
                nodes[node_id]["parms"][parm].pop(k, None)
        else:
            nodes[node_id]["parms"][parm] = value
    return nodes


class _Check:
    check_id: CheckId
    kind = ""

    def __init__(self, observer: ObservationReader | None = None):
        self.observer = observer

    def run(self, check: CheckId, instance: RecipeInstance,
            spec: RecipeSpec, **context: Any) -> CheckResult:
        if check != self.check_id:
            return CheckResult(check, CheckStatus.NOT_RUN,
                               "verifier does not implement " + str(check),
                               {"implemented": self.check_id.value})
        try:
            return self._run(instance, spec, context)
        except EvidenceUnavailable as exc:
            return CheckResult(check, CheckStatus.UNKNOWN, str(exc),
                               {"producer": self.kind, "diagnosis": str(exc)})
        except Exception as exc:
            diagnosis = type(exc).__name__ + ": " + str(exc)
            return CheckResult(check, CheckStatus.UNKNOWN,
                               "measurement failed: " + diagnosis,
                               {"producer": self.kind, "diagnosis": diagnosis})

    def _observe(self, instance, spec, context):
        observation = context.get("observation")
        if observation is None:
            observer = context.get("observer") or self.observer or HostObserver()
            observation = observer.observe(self.kind, instance, spec, **context)
        if not isinstance(observation, Mapping):
            raise EvidenceUnavailable(self.kind + " observation unavailable")
        if observation.get("available") is not True:
            raise EvidenceUnavailable(str(observation.get("reason") or self.kind + " unavailable"))
        if observation.get("complete") is not True:
            raise EvidenceUnavailable(str(observation.get("reason") or self.kind + " observation incomplete"))
        return observation

    def _result(self, failures, evidence):
        return CheckResult(self.check_id, CheckStatus.FAIL if failures else CheckStatus.PASS,
                           "; ".join(failures), _json(evidence))


class GraphVerifier(_Check):
    check_id = CheckId.P1_GRAPH
    kind = "graph"

    def _run(self, instance, spec, context):
        observed = self._observe(instance, spec, context)
        expected = _expected_nodes(instance, spec, context)
        actual = observed["nodes"]
        failures, mismatches = [], []
        if instance.recipe_id != spec.recipe_id or instance.recipe_version != spec.version:
            failures.append("instance/spec identity mismatch")
        if set(expected) != set(instance.owned_node_ids):
            failures.append("owned IDs differ from captured spec")
        if len(set(instance.owned_node_ids.values())) != len(instance.owned_node_ids):
            failures.append("owned IDs alias the same scene path")
        if set(actual) != set(expected):
            failures.append("observed owned IDs differ from spec")
        for node_id, wanted in expected.items():
            got = actual.get(node_id)
            if not isinstance(got, Mapping):
                mismatches.append({"node": node_id, "field": "node", "expected": wanted, "actual": got})
                continue
            fields = {k: wanted[k] for k in ("type", "category", "parent_id", "parms", "flags")}
            fields["path"] = instance.owned_node_ids.get(node_id)
            for optional in ("input_names", "output_names"):
                if optional in wanted:
                    fields[optional] = wanted[optional]
            for name, value in fields.items():
                if name not in got or _json(got[name]) != _json(value):
                    mismatches.append({"node": node_id, "field": name,
                                       "expected": value, "actual": got.get(name)})
        expected_edges = sorted((_edge(e) for e in spec.connections), key=repr)
        observed_edges = sorted((_edge(e) for e in observed["connections"]), key=repr)
        if expected_edges != observed_edges:
            failures.append("connection/port mismatch")
        if mismatches:
            failures.append("owned node state mismatch")
        return self._result(failures, {"source": observed.get("source", "injected"),
                           "nodes": actual, "mismatches": mismatches,
                           "expected_connections": expected_edges,
                           "observed_connections": observed_edges,
                           "blocks": observed.get("blocks")})


class USDVerifier(_Check):
    check_id = CheckId.P2_USD
    kind = "usd"

    def _run(self, instance, spec, context):
        observation = self._observe(instance, spec, context)
        expected = _requirements(spec).get("expected_prims")
        if not expected:
            raise EvidenceUnavailable("expected USD prims and bindings are not captured")
        if observation.get("live") is not True:
            raise EvidenceUnavailable("USD observation is not from a live stage")
        failures, rows = [], []
        for wanted in expected:
            path = wanted["path"]
            got = observation["prims"].get(path, {})
            problems = []
            for flag in ("valid", "active", "defined"):
                if got.get(flag) is not True:
                    problems.append(flag)
            if not wanted.get("type"):
                raise EvidenceUnavailable("expected USD type missing: " + path)
            if got.get("type") != wanted["type"]:
                problems.append("type")
            if not set(wanted.get("schemas", ())) <= set(got.get("schemas", ())):
                problems.append("schemas")
            if "material" in wanted:
                if not wanted["material"]:
                    raise EvidenceUnavailable("empty intended material: " + path)
                if got.get("bound_material") != wanted["material"] or got.get("material_valid") is not True:
                    problems.append("computed material binding")
                if got.get("surface_source_valid") is not True:
                    problems.append("material surface does not resolve")
                if wanted.get("surface_shader") and got.get("surface_shader") != wanted["surface_shader"]:
                    problems.append("surface shader")
                if wanted.get("shader_id") and got.get("shader_id") != wanted["shader_id"]:
                    problems.append("surface shader ID")
            if problems:
                failures.append(path + ": " + ", ".join(problems))
            rows.append({"expected": wanted, "observed": got, "problems": problems})
        return self._result(failures, {"source": observation.get("source", "injected"),
                                      "stage": observation.get("stage"), "prims": rows})


class RenderReadinessVerifier(_Check):
    check_id = CheckId.P3_RENDER_READY
    kind = "render_ready"
    required_clauses = ("rendersettings", "camera", "products_authored", "aovs",
                        "output_path", "two_authored_lights", "render_input_branch",
                        "traversal_complete")

    def _run(self, instance, spec, context):
        observation = self._observe(instance, spec, context)
        requirements = _requirements(spec)
        path = requirements.get("render_settings_path")
        if not path:
            raise EvidenceUnavailable("intended RenderSettings path not captured")
        branch = requirements.get("render_input_connections")
        if not branch or not all(_edge(e) in {_edge(s) for s in spec.connections} for e in branch):
            raise EvidenceUnavailable("explicit render-input branch must be captured in spec.connections")
        graph = observation.get("graph")
        if not graph or graph.get("complete") is not True:
            raise EvidenceUnavailable("render branch node observation incomplete")
        branch_nodes = {e[k] for e in branch for k in ("src_id", "dst_id")}
        spec_nodes = {n["id"]: n for n in spec.nodes}
        branch_mismatches = []
        for node_id in branch_nodes:
            expected_node = spec_nodes.get(node_id)
            actual_node = graph.get("nodes", {}).get(node_id)
            if not expected_node or not actual_node:
                branch_mismatches.append(node_id + ": missing branch node")
                continue
            if any(_json(actual_node.get(k)) != _json(expected_node[k])
                   for k in ("type", "category", "parent_id", "flags")):
                branch_mismatches.append(node_id + ": branch node type/parent/flags mismatch")
            if actual_node.get("path") != instance.owned_node_ids.get(node_id):
                branch_mismatches.append(node_id + ": branch path mismatch")
        report = observation["assessment"]
        if observation.get("live") is not True:
            raise EvidenceUnavailable("render readiness has no live-stage observation")
        if report.get("details", {}).get("render_settings_path") != path:
            return self._result(["assessor did not inspect intended RenderSettings"], report)
        clauses = report["clauses"]
        if clauses.get("traversal_complete") == "fail":
            raise EvidenceUnavailable("stage traversal exceeded measurement limit")
        unknown = [k for k in self.required_clauses if clauses.get(k) not in ("pass", "fail")]
        if unknown:
            raise EvidenceUnavailable("required readiness clauses unmeasured: " + ", ".join(unknown))
        branch_details = report["details"].get("render_input_branch", {})
        if {_edge(e) for e in branch_details.get("expected", [])} != {_edge(e) for e in branch}:
            raise EvidenceUnavailable("assessor branch does not match captured branch")
        failures = [k for k, v in clauses.items() if v == "fail"] + branch_mismatches
        if branch_details.get("complete") is not True:
            raise EvidenceUnavailable("render-input connection observation incomplete")
        observed_edges = {_edge(e) for e in branch_details.get("observed", [])}
        graph_edges = {_edge(e) for e in graph.get("connections", [])}
        if any(_edge(e) not in observed_edges or _edge(e) not in graph_edges for e in branch):
            if "render_input_branch" not in failures:
                failures.append("render_input_branch")
        return self._result(failures, {**report, "branch_nodes": graph["nodes"]})


class CompositionVerifier(_Check):
    check_id = CheckId.P4_COMPOSITION
    kind = "composition"

    def _run(self, instance, spec, context):
        observation = self._observe(instance, spec, context)
        for key in ("composition_errors", "node_errors", "missing_assets", "payloads"):
            if key not in observation:
                raise EvidenceUnavailable(key + " was not measured")
        if observation.get("dependencies_checked") is not True:
            raise EvidenceUnavailable("dependency resolution was not measured")
        if set(observation["node_errors"]) != set(instance.owned_node_ids.values()):
            raise EvidenceUnavailable("relevant node error coverage is incomplete")
        failures = []
        if observation["composition_errors"]:
            failures.append("composition errors")
        if any(observation["node_errors"].values()):
            failures.append("relevant node errors")
        if observation["missing_assets"]:
            failures.append("missing assets")
        unloaded = [p["path"] for p in observation["payloads"] if p["loaded"] is not True]
        if unloaded:
            failures.append("unloaded payloads")
        return self._result(failures, {**observation, "unloaded_payloads": unloaded})


def file_identity(path):
    """Read-only identity; reject a file changing during the digest read."""
    path = Path(path).resolve(strict=True)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    keys = ("st_dev", "st_ino", "st_mtime_ns", "st_size")
    if any(getattr(before, k) != getattr(after, k) for k in keys):
        raise EvidenceUnavailable("output changed while hashing")
    return {"path": str(path), "device": after.st_dev, "inode": after.st_ino,
            "mtime_ns": after.st_mtime_ns, "size": after.st_size,
            "sha256": digest.hexdigest()}


def read_image(path, *, expected_resolution=None, expected_channels=None):
    """Use the existing OIIO reader idiom (autonomy/evaluator.py:116-147).

    No dependency is installed and no alternate decoder is silently used.
    Named RGB channels are selected by ImageSmokeVerifier, not by channel order.
    """
    try:
        import OpenImageIO as oiio
    except ImportError as exc:
        raise EvidenceUnavailable("OpenImageIO is not installed") from exc
    inp = oiio.ImageInput.open(str(path))
    if inp is None:
        raise ValueError("image unreadable: " + str(oiio.geterror()))
    try:
        image_spec = inp.spec()
        if expected_resolution is not None and (image_spec.width, image_spec.height) != tuple(expected_resolution):
            raise ValueError("unexpected image dimensions")
        if expected_channels is not None and list(image_spec.channelnames) != list(expected_channels):
            raise ValueError("unexpected image channels")
        pixels = inp.read_image(0, 0, 0, image_spec.nchannels, oiio.FLOAT)
        if pixels is None:
            raise ValueError("OpenImageIO returned no pixels")
        return {"width": image_spec.width, "height": image_spec.height,
                "channels": list(image_spec.channelnames), "pixels": pixels.tolist()}
    finally:
        inp.close()


def _rgb_image(image, width, height, channels):
    if (image["width"], image["height"]) != (width, height):
        raise ValueError("unexpected image dimensions")
    if list(image["channels"]) != list(channels):
        raise ValueError("unexpected image channels")
    indices = [list(channels).index(c) for c in ("R", "G", "B")]
    pixels = image["pixels"]
    if len(pixels) != height or any(len(row) != width for row in pixels):
        raise ValueError("pixel array dimensions differ from header")
    rgb = []
    for row in pixels:
        values = []
        for pixel in row:
            if len(pixel) != len(channels):
                raise ValueError("pixel channel count differs from header")
            sample = [float(pixel[i]) for i in indices]
            if not all(math.isfinite(v) for v in sample):
                raise ValueError("RGB contains non-finite values")
            values.append(sample)
        rgb.append(values)
    return rgb


def _region_stats(rgb, bounds, threshold):
    height, width = len(rgb), len(rgb[0])
    if len(bounds) != 4 or any(type(v) is not int for v in bounds):
        raise EvidenceUnavailable("region bounds must be integer [x0,y0,x1,y1]")
    x0, y0, x1, y1 = bounds
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        raise EvidenceUnavailable("region bounds outside image")
    samples = [rgb[y][x] for y in range(y0, y1) for x in range(x0, x1)]
    count = len(samples)
    visible = sum((0.2126*r + 0.7152*g + 0.0722*b) > threshold for r, g, b in samples)
    return {"pixels": count, "coverage": visible / count,
            "mean_rgb": [sum(p[i] for p in samples) / count for i in range(3)]}


class ImageSmokeVerifier(_Check):
    check_id = CheckId.P5_IMAGE_SMOKE
    kind = "image"

    def _run(self, instance, spec, context):
        job = context.get("render_job")
        if not isinstance(job, Mapping):
            raise EvidenceUnavailable("terminal render job not observed")
        state = str(job.get("state", "")).upper()
        if job.get("terminal") is not True:
            raise EvidenceUnavailable("render job has no established terminal state")
        if state not in ("SUCCEEDED", "COMPLETED") or job.get("exit_code") != 0:
            return self._result(["render job did not succeed"], {"render_job": job})
        plan_path = context.get("output_path")
        if not plan_path or not job.get("output_path"):
            raise EvidenceUnavailable("planned output path and terminal job output required")
        if Path(plan_path).resolve() != Path(job["output_path"]).resolve():
            return self._result(["job output differs from planned path"], {"render_job": job})
        prior = context.get("prior_artifacts")
        if prior is None:
            raise EvidenceUnavailable("prior output identity inventory missing (explicit [] required for first run)")
        image_req = _requirements(spec).get("image")
        if not image_req:
            raise EvidenceUnavailable("reference-derived image criteria are not captured")
        started_ns = job.get("started_ns")
        if type(started_ns) is not int:
            raise EvidenceUnavailable("render job start timestamp not measured")
        try:
            identity = file_identity(plan_path)
        except (FileNotFoundError, IsADirectoryError) as exc:
            return self._result(["output file missing"], {"diagnosis": str(exc), "render_job": job})
        failures = []
        if identity["size"] <= 0 or identity["mtime_ns"] < started_ns:
            failures.append("output is empty or predates render job")
        stale = []
        for old in prior:
            if not all(k in old for k in ("inode", "mtime_ns", "size", "sha256")):
                raise EvidenceUnavailable("prior artifact lacks full measured identity")
            same_file = all(identity[k] == old[k] for k in ("inode", "mtime_ns", "size"))
            same_content = identity["sha256"] == old["sha256"]
            if same_file or same_content:
                stale.append({"prior": old, "same_file": same_file, "same_content": same_content})
        if stale:
            failures.append("output reuses prior artifact identity/content")
        evidence = {"render_job": job, "file": identity, "stale_matches": stale}
        # A stale file is independently conclusive, even without a decoder.
        if failures:
            return self._result(failures, evidence)
        width, height = image_req.get("resolution", (64, 64))
        samples = image_req.get("samples", 1)
        if job.get("resolution") != [width, height] and job.get("resolution") != (width, height):
            failures.append("job resolution differs from qualification")
        if job.get("samples") != samples:
            failures.append("job samples differ from qualification")
        channels = image_req.get("channels", ("R", "G", "B"))
        reader = context.get("image_reader")
        if reader is None:
            reader = lambda path: read_image(path, expected_resolution=(width, height),
                                             expected_channels=channels)
        try:
            rgb = _rgb_image(reader(plan_path), width, height, channels)
        except ValueError as exc:
            return self._result(failures + [str(exc)], evidence)
        reference_path = image_req.get("reference_path")
        reference_digest = image_req.get("reference_sha256")
        if not reference_path or not reference_digest:
            raise EvidenceUnavailable("pinned reference path and content digest required")
        reference_id = file_identity(reference_path)
        if reference_id["sha256"] != reference_digest:
            raise EvidenceUnavailable("reference content does not match pinned digest")
        if reference_id["path"] == identity["path"]:
            raise EvidenceUnavailable("reference cannot be the current output")
        reference = _rgb_image(reader(reference_path), width, height, channels)
        regions = image_req.get("regions", [])
        if not {"hero", "ground"} <= {r["name"] for r in regions}:
            raise EvidenceUnavailable("reference-derived hero and ground regions are required")
        threshold = image_req.get("luminance_threshold", 0.01)
        coverage_tol = image_req.get("coverage_tolerance", 0.10)
        color_tol = image_req.get("mean_rgb_tolerance", 0.05)
        if not all(isinstance(v, (float, int)) and math.isfinite(v) and v >= 0
                   for v in (threshold, coverage_tol, color_tol)) or coverage_tol >= 1:
            raise EvidenceUnavailable("invalid image tolerances")
        comparisons = []
        for region in regions:
            target = _region_stats(reference, region["bounds"], threshold)
            actual = _region_stats(rgb, region["bounds"], threshold)
            if target["coverage"] <= coverage_tol:
                raise EvidenceUnavailable("reference region has insufficient visible coverage: " + region["name"])
            coverage_delta = abs(actual["coverage"] - target["coverage"])
            color_delta = max(abs(a-b) for a, b in zip(actual["mean_rgb"], target["mean_rgb"]))
            passed = coverage_delta <= coverage_tol and color_delta <= color_tol
            if not passed:
                failures.append("reference content mismatch: " + region["name"])
            comparisons.append({"name": region["name"], "bounds": region["bounds"],
                                "reference": target, "observed": actual,
                                "coverage_delta": coverage_delta, "mean_rgb_delta": color_delta,
                                "pass": passed})
        if file_identity(plan_path) != identity or file_identity(reference_path) != reference_id:
            raise EvidenceUnavailable("image changed during verification")
        evidence.update({"reference": reference_id, "regions": comparisons,
                         "dimensions": [width, height], "channels": list(channels),
                         "tolerances": {"coverage": coverage_tol, "mean_rgb": color_tol,
                                        "luminance_threshold": threshold}})
        return self._result(failures, evidence)


def _field_token(value):
    return str(value).replace("~", "~0").replace("/", "~1")


def semantic_snapshot(nodes, connections, *, scope, complete):
    """Canonical field digests, not layout. Caller must observe the whole scope.

    Nodes are keyed by stable IDs, including artist nodes. Include every authored
    semantic field/opinion in the scope. This helper does not attest completeness.
    """
    fields = {}
    for node_id, node in nodes.items():
        for key, value in node.items():
            if key in ("position", "id"):
                continue
            if key == "parms":
                for parm, parm_value in value.items():
                    fields["node/" + _field_token(node_id) + "/parms/" + _field_token(parm)] = _digest(parm_value)
            else:
                fields["node/" + _field_token(node_id) + "/" + _field_token(key)] = _digest(value)
    # Connections are keyed by destination port. Reject an ambiguous observation.
    for connection in connections:
        src, output, dst, input_index = _edge(connection)
        key = "connection/" + _field_token(dst) + "/" + str(input_index)
        if key in fields:
            raise ValueError("duplicate destination input in semantic observation")
        fields[key] = _digest([src, output])
    return {"fields": fields, "digest": _digest(fields), "scope": scope,
            "complete": complete, "canonicalizer": "verify-fields-v1"}


class LocalityVerifier(_Check):
    check_id = CheckId.P6_LOCALITY
    kind = "locality"

    @staticmethod
    def _snapshot(value):
        if not isinstance(value, Mapping) or value.get("complete") is not True:
            raise EvidenceUnavailable("complete semantic scope snapshot required")
        if value.get("canonicalizer") != "verify-fields-v1":
            raise EvidenceUnavailable("semantic snapshot canonicalizer mismatch")
        if value.get("digest") != _digest(value["fields"]):
            raise EvidenceUnavailable("semantic digest does not match field digests")
        return value

    def _run(self, instance, spec, context):
        before = self._snapshot(context.get("before"))
        after = self._snapshot(context.get("after"))
        if not before.get("scope") or before["scope"] != after["scope"]:
            raise EvidenceUnavailable("before/after semantic scopes differ or are unnamed")
        action_id = context.get("action")
        action = next((a for a in spec.actions if a.action_id == action_id), None)
        if action is None:
            raise EvidenceUnavailable("declared action required for locality")
        changed = sorted(k for k in before["fields"].keys() | after["fields"].keys()
                         if before["fields"].get(k) != after["fields"].get(k))
        slots = context.get("slots", {})
        if not set(slots) <= {s.key for s in action.slots}:
            raise EvidenceUnavailable("undeclared slots in locality request")
        allowed = set()
        expected = _expected_nodes(instance, spec, context)
        expected_values = {}
        semantic_nodes = {node_id: {**node, "path": instance.owned_node_ids[node_id]}
                          for node_id, node in expected.items()}
        if action_id == ActionId.BUILD:
            baseline = semantic_snapshot(semantic_nodes, spec.connections, scope=before["scope"], complete=True)
            # BUILD may add its declared state, never reset existing authored state.
            allowed = set(baseline["fields"]) - set(before["fields"])
            expected_values = baseline["fields"]
        else:
            minimum = semantic_snapshot(semantic_nodes, spec.connections,
                                        scope=before["scope"], complete=True)["fields"]
            missing_before = sorted(set(minimum) - set(before["fields"]))
            if missing_before:
                raise EvidenceUnavailable("pre-state omits captured semantic fields: " + ", ".join(missing_before))
            for slot in action.slots:
                if slot.key in slots:
                    node, parm = slot.binding.rsplit(".", 1)
                    key = "node/" + _field_token(node) + "/parms/" + _field_token(parm)
                    allowed.add(key)
                    expected_values[key] = _digest(expected[node]["parms"][parm])
        forbidden = [k for k in changed if k not in allowed]
        failures = ["unrelated or undeclared semantic changes"] if forbidden else []
        wrong_values = [k for k, v in expected_values.items() if after["fields"].get(k) != v]
        recovery = context.get("recovery")
        if recovery is None:
            raise EvidenceUnavailable("recovery outcome not supplied")
        residue = None
        if recovery != RecoveryVerdict.NOT_NEEDED:
            if context.get("mutation_terminal") is not True:
                raise EvidenceUnavailable("mutation terminal state not established before recovery")
            rollback = self._snapshot(context.get("rollback"))
            if rollback["scope"] != before["scope"]:
                raise EvidenceUnavailable("rollback scope differs from pre-state")
            residue = sorted(k for k in before["fields"].keys() | rollback["fields"].keys()
                             if before["fields"].get(k) != rollback["fields"].get(k))
            if residue:
                failures.append("measured rollback residue")
            if recovery == RecoveryVerdict.UNKNOWN:
                raise EvidenceUnavailable("recovery outcome remains UNKNOWN")
            if recovery not in (RecoveryVerdict.RESTORED, RecoveryVerdict.RESIDUE):
                raise EvidenceUnavailable("unrecognized recovery outcome")
            if recovery == RecoveryVerdict.RESIDUE and not residue:
                failures.append("reported recovery residue contradicts observation")
        elif wrong_values:
            failures.append("requested values not observed")
        return self._result(failures, {"before_digest": before["digest"], "after_digest": after["digest"],
                                      "scope": before["scope"], "changed": changed,
                                      "allowed": sorted(allowed), "forbidden": forbidden,
                                      "wrong_values": wrong_values, "recovery": recovery,
                                      "rollback_residue": residue})


class HostObserver:
    """Read-only adapter; the host owns all hou access through run_on_main.

    No automatic bridge connection or host launch. stage_node_id is a captured
    owned LOP ID; reading a stage is never a search for any available output.
    """

    def observe(self, kind, instance, spec, **context):
        if not HOU_AVAILABLE or not getattr(hou, "__file__", None):
            raise EvidenceUnavailable("real hou is not resident")
        from synapse.server.main_thread import run_on_main
        return run_on_main(lambda: self._observe_main(kind, instance, spec, context),
                           timeout=context.get("observation_timeout", 10.0),
                           record_stall=False, record_wait=False, label="recipe.verify." + kind)

    def _observe_main(self, kind, instance, spec, context):
        if hou.applicationVersionString() != spec.supported_build:
            raise EvidenceUnavailable("resident Houdini build differs from recipe")
        if kind == "graph":
            return self._graph(instance, spec)
        if not PXR_AVAILABLE:
            raise EvidenceUnavailable("pxr is not available")
        requirements = _requirements(spec)
        stage_id = requirements.get("stage_node_id")
        if stage_id not in instance.owned_node_ids:
            raise EvidenceUnavailable("captured stage_node_id is not an owned node")
        node = hou.node(instance.owned_node_ids[stage_id])
        if node is None:
            raise EvidenceUnavailable("stage LOP is missing: " + instance.owned_node_ids[stage_id])
        from synapse.server.solaris_compose import read_stage
        stage = read_stage(node)
        base = {"available": True, "complete": True, "live": True,
                "source": "host:run_on_main", "stage": node.path()}
        if kind == "usd":
            prims = {}
            for wanted in requirements.get("expected_prims", []):
                p = stage.GetPrimAtPath(wanted["path"])
                row = {"valid": bool(p and p.IsValid())}
                if row["valid"]:
                    row.update({"active": p.IsActive(), "defined": p.IsDefined(),
                                "type": p.GetTypeName(), "schemas": list(p.GetAppliedSchemas())})
                    if "material" in wanted:
                        material = UsdShade.MaterialBindingAPI(p).ComputeBoundMaterial()[0]
                        row["material_valid"] = bool(material and material.GetPrim().IsValid()
                                                     and material.GetPrim().IsActive()
                                                     and material.GetPrim().IsDefined())
                        row["bound_material"] = str(material.GetPath()) if row["material_valid"] else None
                        row["surface_source_valid"] = False
                        if row["material_valid"]:
                            shader = material.ComputeSurfaceSource(wanted.get("render_context", ""))[0]
                            if shader:
                                shader_prim = shader.GetPrim()
                                shader_id = shader.GetIdAttr()
                                row["shader_id"] = str(shader_id.Get()) if shader_id and shader_id.Get() else None
                                row["surface_shader"] = str(shader.GetPath())
                                row["surface_source_valid"] = bool(
                                    shader_prim and shader_prim.IsValid() and shader_prim.IsActive()
                                    and shader_prim.IsDefined() and row["shader_id"])
                prims[wanted["path"]] = row
            return {**base, "prims": prims}
        if kind == "render_ready":
            from synapse.server.solaris_compose_tools import _assess_stage
            graph = self._graph(instance, spec)
            report = _assess_stage(
                stage, engine_hint=context.get("engine"), max_prims=context.get("max_prims", 5000),
                render_settings_path=requirements.get("render_settings_path", ""),
                render_input_branch={"expected": requirements.get("render_input_connections", []),
                                     "observed": graph["connections"], "complete": graph["complete"]})
            return {**base, "assessment": report, "graph": graph}
        if kind == "composition":
            limit = context.get("max_prims", 5000)
            prims = list(itertools.islice(stage.TraverseAll(), limit + 1))
            if len(prims) > limit:
                raise EvidenceUnavailable("payload traversal exceeded measurement limit")
            # Compute dependencies under the stage's bound resolver context.
            from pxr import Ar
            with Ar.ResolverContextBinder(stage.GetPathResolverContext()):
                missing, ignored_anonymous = [], []
                for layer in stage.GetUsedLayers():
                    _layers, _assets, unresolved = UsdUtils.ComputeAllDependencies(layer.identifier)
                    file_backed = _missing_file_assets(unresolved)
                    missing.extend(file_backed)
                    ignored_anonymous.extend(
                        str(path) for path in unresolved if str(path) not in file_backed)
            errors = {}
            for path in instance.owned_node_ids.values():
                relevant = hou.node(path)
                if relevant is None:
                    raise EvidenceUnavailable("relevant node unavailable: " + path)
                errors[path] = list(relevant.errors())
            return {**base, "composition_errors": [str(e) for e in stage.GetCompositionErrors()],
                    "node_errors": errors, "dependencies_checked": True,
                    "missing_assets": sorted(set(missing)),
                    "ignored_anonymous_dependencies": sorted(set(ignored_anonymous)),
                    "payloads": [{"path": str(p.GetPath()), "loaded": bool(p.IsLoaded())}
                                 for p in prims if p.HasPayload()]}
        raise EvidenceUnavailable("no host observation adapter for " + kind)

    def _graph(self, instance, spec):
        nodes, connections = {}, []
        inverse = {path: node_id for node_id, path in instance.owned_node_ids.items()}
        for wanted in spec.nodes:
            node_id = wanted["id"]
            path = instance.owned_node_ids.get(node_id)
            node = hou.node(path) if path else None
            if node is None:
                continue
            parms = {}
            for name, expected in wanted["parms"].items():
                parm = node.parm(name)
                if parm is not None:
                    value = self._parm(parm)
                    template = parm.parmTemplate()
                    component_count = 1
                else:
                    pt = node.parmTuple(name)
                    if pt is None:
                        continue
                    components = [self._parm(p) for p in pt]
                    if any(isinstance(value, Mapping) for value in components):
                        raise EvidenceUnavailable("animated tuple needs per-component capture: " + name)
                    value, template = components, pt.parmTemplate()
                    component_count = template.numComponents()
                if isinstance(expected, Mapping) and "value" in expected:
                    if not isinstance(value, Mapping):
                        value = {"value": value}
                    if "type" in expected:
                        kind = str(template.type()).split(".")[-1].lower()
                        value["type"] = self._parameter_type(kind, component_count, expected["type"])
                parms[name] = value
            flags = {}
            for name in wanted["flags"]:
                flag = getattr(hou.nodeFlag, name.capitalize(), None)
                if flag is None:
                    raise EvidenceUnavailable("unsupported captured flag: " + name)
                flags[name] = bool(node.isGenericFlagSet(flag))
            parent = node.parent().path()
            row = {"path": path, "type": node.type().name(),
                   "category": node.type().category().name(), "parent_id": inverse.get(parent),
                   "parms": parms, "flags": flags}
            if "input_names" in wanted:
                row["input_names"] = list(node.inputNames())
            if "output_names" in wanted:
                row["output_names"] = list(node.outputNames())
            nodes[node_id] = row
            for wire in node.inputConnections():
                connections.append({"src_id": inverse.get(wire.inputNode().path(), wire.inputNode().path()),
                                    "src_output": wire.outputIndex(), "dst_id": node_id,
                                    "dst_input": wire.inputIndex()})
        blocks = None
        # BLOCKS observes outer ownership/display without pretending it covers
        # nested VOP nodes or source-output indices. Supplement, never substitute.
        if instance.network_box and nodes:
            from synapse.blocks.runtime import observe
            outer = [n for n in spec.nodes if n["parent_id"] is None]
            parents = {str(Path(instance.owned_node_ids[n["id"]]).parent).replace("\\", "/")
                       for n in outer if n["id"] in instance.owned_node_ids}
            if len(parents) == 1:
                fixture = {"nodes": [{"name": instance.owned_node_ids[n["id"]].rsplit("/", 1)[-1],
                                      "parms": {}} for n in outer]}
                blocks = observe(fixture, instance.network_box, next(iter(parents)))
        return {"available": True, "complete": True, "source": "host:run_on_main",
                "nodes": nodes, "connections": connections, "blocks": blocks}

    @staticmethod
    def _parameter_type(kind, count, declared):
        """Normalize captured aliases only after checking the observed shape."""
        aliases = {"float": {"float"}, "int": {"int", "integer"},
                   "string": {"str", "string"}, "menu": {"enum", "menu"},
                   "toggle": {"bool", "boolean", "toggle"}}
        if count == 1 and declared in aliases.get(kind, set()):
            return declared
        if kind == "float" and count == 3 and declared in ("color3", "float3"):
            return declared
        return kind + (str(count) if count != 1 else "")

    @staticmethod
    def _parm(parm):
        try:
            expression = parm.expression()
        except hou.OperationFailed:
            expression = None
        if expression is not None:
            return {"expression": expression, "language": str(parm.expressionLanguage()),
                    "value": parm.eval()}
        if parm.keyframes():
            raise EvidenceUnavailable("animated parameter requires captured keyframes: " + parm.path())
        if parm.parmTemplate().type() == hou.parmTemplateType.String:
            return parm.unexpandedString()
        return parm.eval()


VERIFIERS = {
    CheckId.P1_GRAPH: GraphVerifier,
    CheckId.P2_USD: USDVerifier,
    CheckId.P3_RENDER_READY: RenderReadinessVerifier,
    CheckId.P4_COMPOSITION: CompositionVerifier,
    CheckId.P5_IMAGE_SMOKE: ImageSmokeVerifier,
    CheckId.P6_LOCALITY: LocalityVerifier,
}
