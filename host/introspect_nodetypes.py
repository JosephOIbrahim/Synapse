"""
host/introspect_nodetypes.py  —  H22 probe: node-type catalog (HOST LAYER)
==========================================================================

Task 0.2, deliverable B. For every node-type string SYNAPSE emits
(``python/synapse/cognitive/tools/data/emitted_node_types.json``, deliverable
A), resolve it against the live catalog (``hou.nodeTypeCategories()`` +
``hou.nodeType(category, name)`` + a deterministic component-scan for
namespaced/versioned spellings) and record existence plus the
parm-template-group fingerprint: the ordered ``[(parm_name, template_type,
default)]`` list and a BLAKE2b of it.

For LOP light/camera types it additionally instantiates one node in a
throwaway ``/stage`` network (headless-safe) and walks ``node.parmTuples()``
to capture the **live punycode ``xn__`` parm names** — the same probe method
that produced ``harness/notes/verified_usdlux_encodings_21.0.671.json``.

RUN IT INSIDE THE TARGET BUILD (H21.0.671 for the Mode-A identity proof):

    "C:/Program Files/Side Effects Software/Houdini 21.0.671/bin/hython.exe" \
        host/introspect_nodetypes.py

Writes ``harness/notes/verified_nodetype_catalog_<build>.json``,
version-stamped like the symbol table (``houdini_version``, ``blake2b``).
Mode-A gate (enforced by ``main()``'s exit code): every emitted type exists,
zero probe errors, and the punycode section byte-matches the verified
encodings file for every alias key they share.

Zero-``synapse``-import, like ``host/introspect_runtime.py`` — the host layer
never imports the package. The bootstring decoder + alias rule below are
lockstep copies of ``python/synapse/cognitive/tools/api_delta.py``; the pure
suite (``tests/test_h22_api_delta.py``) pins both against the 27 live-probed
pairs so they cannot silently diverge. ``hou`` is imported inside functions so
this module also imports cleanly on stock Python for those tests.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = "verified_nodetype_catalog/v1"
_REPO = Path(__file__).resolve().parents[1]
EMITTED_JSON = (_REPO / "python" / "synapse" / "cognitive" / "tools" / "data"
                / "emitted_node_types.json")
NOTES_DIR = _REPO / "harness" / "notes"

# Canonical punycode reference types — the probe set behind
# verified_usdlux_encodings_21.0.671.json, always probed (best-effort) even
# if no emitter currently names them, so the byte-match keeps full coverage.
PUNYCODE_REFERENCE_TYPES = ("light::2.0", "domelight::3.0", "distantlight")
CAMERA_TYPE = "camera"

# The six camera aliases. Standard UsdGeomCamera attrs (NOT in ``inputs:``),
# probe-confirmed plain camelCase on 21.0.671 (2026-07-01) and single-sourced
# in usd_punycode.USD_ATTR_NAMES — the probe keeps reporting what the live
# camera LOP exposes so any drift stays visible.
CAMERA_ALIASES = {
    "focal_length": "focalLength",
    "focus_distance": "focusDistance",
    "fstop": "fStop",
    "horizontal_aperture": "horizontalAperture",
    "vertical_aperture": "verticalAperture",
    "clipping_range": "clippingRange",
}

_DEFAULT_REPR_CAP = 200
_VERSION_COMPONENT = re.compile(r"^[0-9][0-9.]*$")

# ---------------------------------------------------------------------------
# Punycode (Houdini xn__ variant) decoding — LOCKSTEP copy of
# python/synapse/cognitive/tools/api_delta.py (host layer is zero-synapse;
# tests/test_h22_api_delta.py pins the two against the verified pairs).
# ---------------------------------------------------------------------------

_BOOTSTRING_BASE = 36
_TMIN = 1
_TMAX = 26
_SKEW = 38
_DAMP = 700
_INITIAL_BIAS = 72
_INITIAL_N = 1  # Houdini deviation: vanilla RFC 3492 uses 128


def _adapt(delta: int, numpoints: int, firsttime: bool) -> int:
    delta = delta // _DAMP if firsttime else delta // 2
    delta += delta // numpoints
    k = 0
    while delta > ((_BOOTSTRING_BASE - _TMIN) * _TMAX) // 2:
        delta //= _BOOTSTRING_BASE - _TMIN
        k += _BOOTSTRING_BASE
    return k + (((_BOOTSTRING_BASE - _TMIN + 1) * delta) // (delta + _SKEW))


def _digit(ch: str) -> int:
    o = ord(ch)
    if 0x61 <= o <= 0x7A:
        return o - 0x61
    if 0x41 <= o <= 0x5A:
        return o - 0x41
    if 0x30 <= o <= 0x39:
        return o - 0x30 + 26
    raise ValueError(f"invalid bootstring digit {ch!r}")


def decode_parm_name(encoded: str) -> str:
    """``xn__inputsintensity_i0a`` -> ``inputs:intensity`` (see api_delta)."""
    if not encoded.startswith("xn__"):
        return encoded
    body = encoded[4:]
    base, sep, ext = body.rpartition("_")
    if not sep:
        base, ext = "", body
    out = list(base)
    i, n, bias = 0, _INITIAL_N, _INITIAL_BIAS
    pos, first = 0, True
    while pos < len(ext):
        oldi, w, k = i, 1, _BOOTSTRING_BASE
        while True:
            if pos >= len(ext):
                raise ValueError(f"truncated bootstring extension in {encoded!r}")
            d = _digit(ext[pos])
            pos += 1
            i += d * w
            t = _TMIN if k <= bias else (_TMAX if k >= bias + _TMAX else k - bias)
            if d < t:
                break
            w *= _BOOTSTRING_BASE - t
            k += _BOOTSTRING_BASE
        bias = _adapt(i - oldi, len(out) + 1, first)
        first = False
        n += i // (len(out) + 1)
        i %= len(out) + 1
        out.insert(i, chr(n))
        i += 1
    return "".join(out)


_CAMEL_SPLIT = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def alias_from_raw(raw: str) -> str:
    """``inputs:colorTemperature_control`` -> ``color_temperature_control``
    (lockstep with api_delta.alias_from_raw)."""
    body = raw[len("inputs:"):] if raw.startswith("inputs:") else raw
    body = body.replace(":", "_")
    return _CAMEL_SPLIT.sub("_", body).lower()


# ---------------------------------------------------------------------------
# Catalog resolution
# ---------------------------------------------------------------------------

def _strip_version(full_name: str) -> str:
    parts = full_name.split("::")
    if len(parts) > 1 and _VERSION_COMPONENT.match(parts[-1]):
        return "::".join(parts[:-1])
    return full_name


def _matches(emitted: str, full_name: str) -> bool:
    """Does catalog ``full_name`` satisfy the emitted spelling? Mirrors what
    ``createNode(emitted)`` accepts: exact, version-elided, or bare-name."""
    if full_name == emitted:
        return True
    base = _strip_version(full_name)
    if base == emitted:
        return True
    if "::" not in emitted and base.split("::")[-1] == emitted:
        return True
    return False


def _default_repr(template) -> "str | None":
    try:
        value = template.defaultValue()
    except AttributeError:
        return None
    except Exception as e:  # noqa: BLE001 — surface, don't crash the probe
        return f"<defaultValue error: {type(e).__name__}>"
    text = repr(value)
    if len(text) > _DEFAULT_REPR_CAP:
        digest = hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()
        return text[:_DEFAULT_REPR_CAP] + f"…blake2b:{digest}"
    return text


def _walk_templates(templates, out) -> None:
    for t in templates:
        ttype = str(t.type()).rsplit(".", 1)[-1]
        out.append([t.name(), ttype, _default_repr(t)])
        sub = getattr(t, "parmTemplates", None)
        if callable(sub):
            try:
                _walk_templates(sub(), out)
            except Exception:  # noqa: BLE001 — folder without children
                pass


def _fingerprint(node_type) -> dict:
    parms: list = []
    _walk_templates(node_type.parmTemplates(), parms)
    digest = hashlib.blake2b(
        json.dumps(parms, ensure_ascii=False).encode("utf-8"), digest_size=16
    ).hexdigest()
    return {"parms": parms, "parm_blake2b": digest}


def _resolve(hou, emitted: str, errors: list) -> list:
    """All catalog matches for an emitted spelling, across every category."""
    resolved = []
    for cat_name in sorted(hou.nodeTypeCategories()):
        category = hou.nodeTypeCategories()[cat_name]
        hits = {}
        try:
            exact = hou.nodeType(category, emitted)
        except Exception as e:  # noqa: BLE001
            errors.append(f"nodeType({cat_name}, {emitted!r}) raised: {e}")
            exact = None
        if exact is not None:
            hits[exact.name()] = exact
        try:
            for full_name, node_type in category.nodeTypes().items():
                if full_name not in hits and _matches(emitted, full_name):
                    hits[full_name] = node_type
        except Exception as e:  # noqa: BLE001
            errors.append(f"nodeTypes() scan failed in {cat_name}: {e}")
        for full_name in sorted(hits):
            entry = {"category": cat_name, "full_name": full_name}
            try:
                entry.update(_fingerprint(hits[full_name]))
            except Exception as e:  # noqa: BLE001
                errors.append(f"fingerprint failed for {cat_name}/{full_name}: {e}")
            resolved.append(entry)
    return resolved


# ---------------------------------------------------------------------------
# Punycode + camera live probes (instantiate in a throwaway /stage network)
# ---------------------------------------------------------------------------

def _probe_node_tuples(hou, stage, type_name: str, errors: list) -> "dict | None":
    """Instantiate ``type_name`` under /stage, return {parm_tuple_name: ...},
    destroy the node. None if the type does not instantiate."""
    try:
        node = stage.createNode(type_name)
    except Exception:  # noqa: BLE001 — candidate types are best-effort
        return None
    try:
        return {pt.name(): len(pt) for pt in node.parmTuples()}
    except Exception as e:  # noqa: BLE001
        errors.append(f"parmTuples walk failed on {type_name}: {e}")
        return None
    finally:
        try:
            node.destroy()
        except Exception:  # noqa: BLE001
            pass


def _probe_punycode(hou, light_types, errors: list) -> dict:
    """``{aliases, raw, per_type}`` from live-instantiated light LOPs —
    the probe method behind verified_usdlux_encodings_21.0.671.json."""
    stage = hou.node("/stage")
    aliases: dict = {}
    raw_map: dict = {}
    per_type: dict = {}
    for type_name in light_types:
        names = _probe_node_tuples(hou, stage, type_name, errors)
        if names is None:
            per_type[type_name] = {"instantiated": False}
            continue
        xn = sorted(n for n in names if n.startswith("xn__"))
        per_type[type_name] = {"instantiated": True, "parm_tuples": len(names),
                               "xn_count": len(xn)}
        for encoded in xn:
            try:
                raw = decode_parm_name(encoded)
            except ValueError as e:
                errors.append(f"undecodable parm on {type_name}: {encoded} ({e})")
                continue
            alias = alias_from_raw(raw)
            if aliases.get(alias, encoded) != encoded:
                errors.append(
                    f"alias conflict for {alias!r}: {aliases[alias]} vs {encoded} "
                    f"(on {type_name})"
                )
                continue
            aliases[alias] = encoded
            raw_map[raw] = encoded
    return {
        "aliases": dict(sorted(aliases.items())),
        "raw": dict(sorted(raw_map.items())),
        "per_type": per_type,
    }


def _probe_camera(hou, errors: list) -> dict:
    """The camera-LOP probe: what does the live build call the six camera
    attrs single-sourced in usd_punycode.USD_ATTR_NAMES?"""
    stage = hou.node("/stage")
    try:
        node = stage.createNode(CAMERA_TYPE)
    except Exception as e:  # noqa: BLE001
        errors.append(f"camera LOP did not instantiate: {e}")
        return {"instantiated": False}
    try:
        tuple_names = [pt.name() for pt in node.parmTuples()]
        decoded_xn = {}
        for n in tuple_names:
            if n.startswith("xn__"):
                try:
                    decoded_xn[decode_parm_name(n)] = n
                except ValueError:
                    pass
        report: dict = {"instantiated": True, "entries": {}}
        for alias, attr in sorted(CAMERA_ALIASES.items()):
            plain = attr if attr in tuple_names else None
            xn_hits = sorted(
                enc for raw, enc in decoded_xn.items()
                if raw == attr or raw == f"inputs:{attr}"
            )
            report["entries"][alias] = {
                "usd_attr": attr,
                "plain_parm": plain,
                "xn_parm": xn_hits[0] if xn_hits else None,
            }
        return report
    finally:
        try:
            node.destroy()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Catalog assembly + Mode-A checks
# ---------------------------------------------------------------------------

def build_catalog(emitted_path: Path = EMITTED_JSON) -> dict:
    """The full catalog payload, in memory (``main()`` writes it; the delta
    probe ``scripts/h22_api_delta.py`` consumes it directly)."""
    import hou

    emitted = json.loads(Path(emitted_path).read_text(encoding="utf-8"))
    errors: list = []
    entries = []
    light_probe_types = set(PUNYCODE_REFERENCE_TYPES)
    for src in emitted["entries"]:
        resolved = _resolve(hou, src["type_name"], errors)
        entries.append({
            "type_name": src["type_name"],
            "category_hint": src["category"],
            "source_files": src["source_files"],
            "exists": bool(resolved),
            "resolved": resolved,
        })
        for match in resolved:
            if match["category"] == "Lop" and (
                "light" in match["full_name"] or "camera" in match["full_name"]
            ):
                light_probe_types.add(match["full_name"])

    punycode = _probe_punycode(hou, sorted(light_probe_types), errors)
    camera = _probe_camera(hou, errors)

    stamp = hashlib.blake2b(
        json.dumps({"entries": entries, "punycode": punycode}, sort_keys=True,
                   ensure_ascii=False).encode("utf-8"),
        digest_size=16,
    ).hexdigest()
    return {
        "schema": SCHEMA,
        "houdini_version": hou.applicationVersionString(),
        "generated_from": str(Path(emitted_path).relative_to(_REPO)).replace("\\", "/"),
        "blake2b": stamp,
        "entries": entries,
        "punycode": punycode,
        "camera_probe": camera,
        "probe_errors": errors,
    }


def _flatten_verified(verified: dict) -> dict:
    """Lockstep with api_delta.flatten_verified_encodings (zero-synapse here)."""
    flat: dict = {}
    for section, payload in verified.items():
        if not section.endswith("_verified") or not isinstance(payload, dict):
            continue
        for alias, value in payload.items():
            if isinstance(value, str):
                flat[alias] = value
            elif isinstance(value, dict) and "tuple_base" in value:
                flat[alias] = value["tuple_base"]
    return flat


def check_against_verified(catalog: dict, verified_path: Path) -> list:
    """Byte-match the punycode section against the curated verified-encodings
    file for every alias key they share. Returns mismatch strings."""
    verified = _flatten_verified(
        json.loads(verified_path.read_text(encoding="utf-8"))
    )
    live = catalog["punycode"]["aliases"]
    return [
        f"{alias}: verified={verified[alias]} live={live[alias]}"
        for alias in sorted(set(verified) & set(live))
        if verified[alias] != live[alias]
    ]


def main() -> int:
    catalog = build_catalog()
    build = catalog["houdini_version"]
    out_fp = NOTES_DIR / f"verified_nodetype_catalog_{build}.json"
    out_fp.parent.mkdir(parents=True, exist_ok=True)
    out_fp.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")

    missing = [e["type_name"] for e in catalog["entries"] if not e["exists"]]
    errors = list(catalog["probe_errors"])

    verified_fp = NOTES_DIR / f"verified_usdlux_encodings_{build}.json"
    if verified_fp.exists():
        mismatches = check_against_verified(catalog, verified_fp)
        errors.extend(f"punycode mismatch vs {verified_fp.name}: {m}" for m in mismatches)
        shared_note = f"byte-match vs {verified_fp.name}: {len(mismatches)} mismatch(es)"
    else:
        shared_note = f"no {verified_fp.name} — byte-match skipped (new build?)"

    sys.stdout.write(
        f"CATALOG: build={build} types={len(catalog['entries'])} "
        f"missing={len(missing)} probe_errors={len(errors)} "
        f"punycode_aliases={len(catalog['punycode']['aliases'])} "
        f"blake2b={catalog['blake2b'][:12]} -> {out_fp}\n"
    )
    sys.stdout.write(f"  {shared_note}\n")
    for name in missing:
        sys.stdout.write(f"  MISSING: {name}\n")
    for err in errors:
        sys.stdout.write(f"  ERROR: {err}\n")
    cam = catalog["camera_probe"]
    if cam.get("instantiated"):
        for alias, info in cam["entries"].items():
            sys.stdout.write(
                f"  camera {alias:22} attr={info['usd_attr']:20} "
                f"plain={info['plain_parm']} xn={info['xn_parm']}\n"
            )
    return 1 if (missing or errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
