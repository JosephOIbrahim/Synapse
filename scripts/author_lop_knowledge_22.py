#!/usr/bin/env python
"""C-U5 / R-026 — H22 LOP/Solaris knowledge author (catalogue-grounded, deterministic).

Sibling of scripts/mine_lop_knowledge.py for the H22 catalog. The H21 miner
grounds its authored block in a PROSE corpus (the Solaris reference); no H22
solaris_reference corpus exists, so for H22 the grounding source is the live
node catalogue the H22 drop actually ships:

  * rag/catalog/h22.0.400/Lop.json   (scripts/build_node_catalog.py phase A — the
                                      live hou.NodeType.parmTemplateGroup() walk:
                                      222 Lop types with tuple/parm template names)
  * rag/catalog/h22.0.400/Vop.json   (category placement for the Vop-resident
                                      shader types named in the entries)
  * python/synapse/cognitive/tools/data/connectivity_22.json  (the U.1-H22 probe;
                                      advisory probe_confirmed cross-check only)

Same determinism contract as the miner: the knowledge is an AUTHORED block —
extracted ONCE and committed here verbatim, carried with a provenance marker.
This script is DETERMINISTIC and re-runnable (no LLM, no wall-clock): it proves
every authored entry/category/key_parm/known_absent claim against the 22.0.400
catalogue (the consistency gate), computes ``source_digest`` over the grounding
files, stamps blake2b over the content, and writes the packaged copy + harness
twin byte-identically. A source_digest mismatch means the grounding truth
changed -> re-author (a human+LLM step), never a silent re-extract.
"Catalogue truth > authored prose", now literally: a claim the 22.0.400
catalogue does not carry FAILS the gate.

RE-AUTHORED for R-026 (2026-11-20): the catalog was stamped 22.0.368 against a
22.0.400 target. Type existence and the parm-template surface below are
re-proved on the 22.0.400 catalogue; the few claims a type/parm walk cannot
prove (createNode version resolution, materiallibrary's cook() behaviour) are
labelled as carried rather than silently restamped.

Usage:
  python scripts/author_lop_knowledge_22.py           # write artifact + packaged copy
  python scripts/author_lop_knowledge_22.py --check   # verify determinism, write nothing
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SCHEMA = "lop_solaris_knowledge/v1"
HOUDINI_BUILD = "22.0.400"
CATALOG_SCHEMA = "node_catalog_live/v1"

_REPO = Path(__file__).resolve().parents[1]
ARTIFACT = _REPO / "harness" / "notes" / f"verified_lop_solaris_knowledge_{HOUDINI_BUILD}.json"
PKG = (_REPO / "python" / "synapse" / "cognitive" / "tools" / "data"
       / "lop_solaris_knowledge_22.json")
_CATALOG_DIR = _REPO / "rag" / "catalog" / f"h{HOUDINI_BUILD}"
LOP_CATALOG = _CATALOG_DIR / "Lop.json"
VOP_CATALOG = _CATALOG_DIR / "Vop.json"
_PKG_CONNECTIVITY = (_REPO / "python" / "synapse" / "cognitive" / "tools"
                     / "data" / "connectivity_22.json")

# --------------------------------------------------------------------------
# AUTHORED content — extracted from the live 22.0.400 node catalogue, verbatim.
# NOT re-derived by this script. Re-author when source_digest changes.
# --------------------------------------------------------------------------
_PROVENANCE = (
    "authored from the committed live node catalogue rag/catalog/"
    f"h{HOUDINI_BUILD}/ (scripts/build_node_catalog.py on H{HOUDINI_BUILD}: the "
    "type-level hou.NodeType.parmTemplateGroup() walk — VERIFIED-RUNTIME by "
    "construction, 222 Lop types; Vop.json carries the Vop-resident shader "
    "types), with connectivity_22.json as the advisory probe_confirmed "
    "cross-check; carried verbatim, NOT re-derived by this script; re-author on "
    "source_digest mismatch. source_digest = blake2b over the sha256 of "
    "Lop.json + Vop.json plus connectivity_22.json's blake2b stamp. Tier notes: "
    "usd_type is semantic USD-schema knowledge carried at authored tier (the "
    "catalogue records parm templates, not USD prim classes); key_parms use "
    "TEMPLATE spellings (t/r/s tuple parms cover tx..sz components; multiparm "
    "templates carry '#', runtime instance 1 is '1'). Carried-not-re-proved on "
    f"{HOUDINI_BUILD}: createNode('domelight'/'distantlight'/'light') version "
    "resolution (recorded by the 22.0.368 creation probe; the catalogue records "
    "the type table only), and materiallibrary's cook(force=True) gotcha (H21-era "
    "operational knowledge; no catalogue walk can prove cook behaviour)."
)

# name -> role / usd_type / key_parms / gotchas [+ category, default Lop].
# Every claim below is gated against the live catalogue by _consistency_gate.
_ENTRIES = {
    # --- Geometry ---
    "sphere":    {"role": "geometry", "usd_type": "Sphere", "key_parms": ["radius", "t"], "gotchas": []},
    "cube":      {"role": "geometry", "usd_type": "Cube", "key_parms": ["size", "t"], "gotchas": []},
    "plane":     {"role": "geometry", "usd_type": "Plane",
                  "key_parms": ["axis", "length", "width", "t"],
                  "gotchas": ["real LOP type on 22.0.400 — NEW in H22; the H21 catalog "
                              "marked plane known_absent."]},
    "sopimport": {"role": "geometry", "usd_type": None, "key_parms": ["soppath"], "gotchas": []},
    "null":      {"role": "geometry", "usd_type": None, "key_parms": [], "gotchas": []},
    "merge":     {"role": "scene", "usd_type": None, "key_parms": [], "gotchas": []},
    # --- Lights (H22 consolidation: per-shape lights are gone, see known_absent) ---
    "domelight": {"role": "light", "usd_type": "DomeLight",
                  "key_parms": ["primpath", "xn__inputsexposure_vya",
                                "xn__inputsintensity_i0a", "xn__inputstexturefile_r3ah"],
                  "gotchas": ["On 22.0.400 the versioned domelight::3.0 template carries the "
                              "punycode-namespaced UsdLux inputs (xn__inputs*); the plain "
                              "intensity/exposure/xn__texturefile_0ta spellings live only on "
                              "the legacy unversioned domelight template. (createNode('domelight') "
                              "resolved to the ::3.0 type on the 22.0.368 creation probe; the "
                              "22.0.400 catalogue records the type table, not creation resolution.)"]},
    "distantlight": {"role": "light", "usd_type": "DistantLight",
                     "key_parms": ["primpath", "xn__inputsangle_zta",
                                   "xn__inputsexposure_vya", "xn__inputsintensity_i0a"],
                     "gotchas": ["On 22.0.400 the versioned distantlight::2.0 template carries "
                                 "the punycode-namespaced UsdLux inputs (xn__inputs*); the plain "
                                 "intensity/exposure spellings live only on the legacy unversioned "
                                 "distantlight template. (createNode('distantlight') resolved to "
                                 "the ::2.0 type on the 22.0.368 creation probe; the 22.0.400 "
                                 "catalogue records the type table, not creation resolution.)"]},
    "light": {"role": "light", "usd_type": None,
              "key_parms": ["lighttype", "primpath", "xn__inputsexposure_vya",
                            "xn__inputsintensity_i0a"],
              "gotchas": ["The consolidated light LOP supersedes the H21-era per-shape lights "
                          "(sphere/rect/disk/cylinder) — shape via the lighttype parm, so "
                          "usd_type varies with it. The versioned light::2.0 template on "
                          "22.0.400 carries the punycode-namespaced UsdLux inputs (xn__inputs*): "
                          "per-shape dims at xn__inputsradius_mva / xn__inputswidth_zta / "
                          "xn__inputsheight_mva / xn__inputslength_mva. (createNode('light') "
                          "resolved to light::2.0 on the 22.0.368 creation probe; the 22.0.400 "
                          "catalogue records the type table, not creation resolution.)"]},
    # --- Camera ---
    "camera": {"role": "camera", "usd_type": "Camera",
               "key_parms": ["fStop", "focalLength", "r", "t"],
               "gotchas": ["Transform templates are the t/r tuple parms on 22.0.400 — component "
                           "spellings (tx..rz) are not template names."]},
    # --- Materials ---
    "materiallibrary": {"role": "material", "usd_type": None,
                        "key_parms": ["matnode#", "matpath#"],
                        "gotchas": ["After creating materiallibrary, call matlib.cook(force=True) "
                                    "before creating child shader nodes, else createNode() returns "
                                    "None. (H21-era operational knowledge; NOT re-proved by the "
                                    "22.0.400 catalogue walk.)"]},
    "mtlxstandard_surface": {"role": "material", "usd_type": None, "category": "Vop",
                             "key_parms": [],
                             "gotchas": ["NOT a Lop type on 22.0.400 — it resolves only in the Vop "
                                         "category (rag/catalog/h22.0.400/Vop.json); create it "
                                         "INSIDE a materiallibrary as a child shader node. "
                                         "(Creation at /stage failed 'Invalid node type name' on "
                                         "the 22.0.368 creation probe.)"]},
    "assignmaterial": {"role": "material", "usd_type": None,
                       "key_parms": ["matspecpath#", "primpattern#"],
                       "gotchas": ["primpattern#/matspecpath# are multiparm TEMPLATES on "
                                   "22.0.400 — the H21 catalog carried the instance spellings "
                                   "primpattern1/matspecpath1, which have no parm template; "
                                   "created nodes expose instance 1 as primpattern1/matspecpath1."]},
    # --- Scene Structure ---
    "edit":      {"role": "scene", "usd_type": None,
                  "key_parms": ["primpattern", "r", "s", "t"], "gotchas": []},
    "reference": {"role": "scene", "usd_type": None,
                  "key_parms": ["filepath#", "primpath", "reftype"],
                  "gotchas": ["filepath# is a multiparm template — created nodes expose instance "
                              "1 as filepath1."]},
    "sublayer":  {"role": "scene", "usd_type": None,
                  "key_parms": ["filepath#", "positionindex", "positiontype"],
                  "gotchas": ["The H21-era 'position' parm is gone on 22.0.400 — use "
                              "positionindex/positiontype; filepath# is a multiparm template "
                              "(instance 1 is filepath1)."]},
    # --- Instancing family (W.3: H22 renamed the set-dressing LOPs) ---
    "copytopoints": {"role": "geometry", "usd_type": None,
                     "key_parms": ["method", "pointsoppath", "protoindexsrc", "seed"],
                     "gotchas": ["The H21-era 'instancer' spelling is gone from the 22.0.400 type "
                                 "table; the instancer tab resolves here — author the canonical "
                                 "'copytopoints' spelling."]},
    "pointinstancer": {"role": "geometry", "usd_type": "PointInstancer",
                       "key_parms": ["primpath", "protopattern", "protoreftype", "soppath"],
                       "gotchas": []},
    "paintinstances": {"role": "scene", "usd_type": None,
                       "key_parms": ["primpattern", "protopattern"], "gotchas": []},
    "scatterinstances": {"role": "scene", "usd_type": None,
                         "key_parms": ["protopattern", "scattercount", "scatterdensity",
                                       "scatterseed"], "gotchas": []},
    "modifypointinstances": {"role": "scene", "usd_type": None,
                             "key_parms": ["instances", "prunemethod", "soppath"], "gotchas": []},
    "mergepointinstancers": {"role": "scene", "usd_type": None,
                             "key_parms": ["instances", "primpath"], "gotchas": []},
    "splitpointinstancers": {"role": "scene", "usd_type": None,
                             "key_parms": ["attribute", "instancers", "splitmethod"],
                             "gotchas": []},
    "extractinstances": {"role": "scene", "usd_type": None,
                         "key_parms": ["instances", "method", "primpath", "prototypepath"],
                         "gotchas": []},
    "retimeinstances": {"role": "scene", "usd_type": None,
                        "key_parms": ["instances", "retimemethod", "soppath"], "gotchas": []},
    # --- Render ---
    "karmarenderproperties": {"role": "render", "usd_type": None, "key_parms": ["engine"],
                              "gotchas": ["DEPRECATED on 22.0.400 (catalogue deprecation flag) — "
                                          "still resolves; prefer karmarendersettings."]},
    "karmarendersettings": {"role": "render", "usd_type": None,
                            "key_parms": ["engine", "primpath"], "gotchas": []},
    "usdrender_rop": {"role": "render", "usd_type": None,
                      "key_parms": ["loppath", "outputimage"], "gotchas": []},
}

# Ordering constraints — carried verbatim from U.5 (the rule's participants all
# re-proved present on 22.0.400: materiallibrary/reference/sublayer in
# rag/catalog/h22.0.400/Lop.json + connectivity_22.json). The consumer treats
# this as an ADVISORY.
_ORDERING_RULES = [
    {
        "id": "assignmaterial_requires_material_source",
        "requires_type": "materiallibrary",
        "satisfied_by": ["reference", "sublayer"],
        "on_type": "assignmaterial",
        "relation": "upstream",
        "detail": ("assignmaterial binds material prims that must be authored upstream — "
                   "usually by a materiallibrary (cook it, matlib.cook(force=True), before its "
                   "shaders resolve), or brought in by a reference/sublayer composition arc; "
                   "materials may also already exist in a pre-composed stage."),
    },
]

# Types the 22.0.400 live catalogue affirmatively lacks (the walk enumerates the
# complete Lop type table, so absence there IS the measurement) — a proposal
# naming these is a known pitfall; each remediation names the canonical successor.
# NOTE 'instancer': absent from the 22.0.400 type table (the live .400 harvest
# records lop_has_instancer false AND 'instancer tab resolves to copytopoints');
# flagged per the W.3 "canonical spelling, never the opalias" rule.
_KNOWN_ABSENT = {
    "grid": {"remediation": "there is NO grid LOP on 22.0.400 (grid is a Sop type) — use the "
                            "plane LOP (a real LOP type on 22.0.400) or a cube scaled flat"},
    "spherelight": {"remediation": "no spherelight LOP on 22.0.400 — use the consolidated "
                                   "light LOP (versioned light::2.0) and set its lighttype "
                                   "parm to the sphere shape"},
    "rectlight": {"remediation": "no rectlight LOP on 22.0.400 — use the consolidated "
                                 "light LOP (versioned light::2.0) and set its lighttype "
                                 "parm to the rectangle shape"},
    "disklight": {"remediation": "no disklight LOP on 22.0.400 — use the consolidated "
                                 "light LOP (versioned light::2.0) and set its lighttype "
                                 "parm to the disk shape"},
    "cylinderlight": {"remediation": "no cylinderlight LOP on 22.0.400 — use the consolidated "
                                     "light LOP (versioned light::2.0) and set its lighttype "
                                     "parm to the cylinder shape"},
    "instancer": {"remediation": "gone from the 22.0.400 type table (lop_has_instancer false "
                                 "in the live .400 harvest) — the instancer tab resolves to "
                                 "copytopoints (a silent-success trap); author the canonical "
                                 "copytopoints (or pointinstancer for PointInstancer prims) "
                                 "instead"},
}

# Composition strengths — USD semantics (build-agnostic); key_parms re-proved
# against the 22.0.400 catalogue (sublayer's H21-era 'position' is gone).
_COMPOSITION = {
    "reference": {"strength": "stronger-overridable",
                  "key_parms": ["filepath#", "primpath", "reftype"],
                  "use": "import assets under a prim path; per-instance overrides"},
    "sublayer": {"strength": "strongest-direct-edit",
                 "key_parms": ["filepath#", "positionindex", "positiontype"],
                 "use": "merge a full layer (environments, lighting rigs, base layers)"},
}

# A canonical render-scene node sequence — advisory order used by the planner
# and asserted by the ordering rule. Uses karmarendersettings: the H21-era
# karmarenderproperties is deprecated on 22.0.400.
_RECIPES = [
    {"name": "solaris_render_scene",
     "sequence": ["sphere", "materiallibrary", "assignmaterial", "camera", "domelight",
                  "karmarendersettings", "null"],
     "note": "geo -> matlib (+child shader, cooked) -> assignmaterial -> camera -> light "
             "-> karmarendersettings (karmarenderproperties is deprecated on 22.0.400) "
             "-> OUTPUT null"},
]


def _content() -> dict:
    """The integrity-covered payload. blake2b is stamped over exactly this."""
    entries = {}
    for name, e in _ENTRIES.items():
        entries[name] = {
            "category": e.get("category", "Lop"),
            "type_name": name,
            "role": e["role"],
            "usd_type": e["usd_type"],
            "key_parms": list(e["key_parms"]),
            "gotchas": list(e["gotchas"]),
        }
    return {
        "entries": entries,
        "ordering_rules": _ORDERING_RULES,
        "known_absent": _KNOWN_ABSENT,
        "composition": _COMPOSITION,
        "recipes": _RECIPES,
        "authored": {"_provenance": _PROVENANCE},
    }


def _blake(obj) -> str:
    return hashlib.blake2b(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        digest_size=16,
    ).hexdigest()


def _load_catalog(path: Path, category: str) -> dict:
    """The committed live node catalogue for one category, stamped for the target
    build. A missing/stale/wrong-category catalogue FAILS the authoring — the
    live walk is the grounding truth, never a fallback to recalled names."""
    if not path.is_file():
        raise SystemExit(f"node catalogue missing: {path} — the {HOUDINI_BUILD} grounding "
                         f"truth; run scripts/build_node_catalog.py on the target build")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != CATALOG_SCHEMA:
        raise SystemExit(f"{path.name} schema {data.get('schema')!r} != {CATALOG_SCHEMA!r}")
    if data.get("build") != HOUDINI_BUILD:
        raise SystemExit(f"{path.name} is stamped build={data.get('build')!r}, not "
                         f"{HOUDINI_BUILD!r} — a catalog authored on another build is "
                         f"exactly the stale-truth class this gate exists to stop")
    if data.get("category") != category:
        raise SystemExit(f"{path.name} category {data.get('category')!r} != {category!r}")
    types = data.get("types")
    if not isinstance(types, dict) or not types:
        raise SystemExit(f"{path.name} carries no type table")
    return types


def _connectivity() -> tuple[set[str], str]:
    """(Lop type-name set, blake2b stamp) from the U.1-H22 connectivity catalog."""
    data = json.loads(_PKG_CONNECTIVITY.read_text(encoding="utf-8"))
    lop = {e.get("type_name", "").split("::")[0]
           for e in data.get("entries", {}).values() if e.get("category") == "Lop"}
    return lop, str(data.get("blake2b", ""))


def _source_digest(conn_blake: str) -> str:
    """blake2b over the two 22.0.400 catalogue files' sha256 + the connectivity
    stamp — the grounding inputs; any of them changing re-arms re-authoring."""
    parts = [hashlib.sha256(LOP_CATALOG.read_bytes()).hexdigest(),
             hashlib.sha256(VOP_CATALOG.read_bytes()).hexdigest(),
             conn_blake]
    return hashlib.blake2b("\0".join(parts).encode("utf-8"), digest_size=16).hexdigest()


def _grounded_parms(types: dict, name: str) -> set[str]:
    """The catalogue-verified parm-template surface for an authored type: the
    type's own row plus every versioned sibling the build also ships (e.g.
    domelight -> domelight::2.0 / domelight::3.0), because createNode() resolves
    the unversioned spelling onto the versioned template at runtime."""
    out: set[str] = set()
    for n, rec in types.items():
        if n == name or n.startswith(name + "::"):
            out.update(p.get("name") for p in (rec.get("parms") or []) if p.get("name"))
    return out


def _consistency_gate(content: dict, lop_types: dict, vop_types: dict,
                      conn_lop: set[str]) -> list[str]:
    """Catalogue truth > authored prose, enforced: every entry must exist on
    22.0.400 in its stated category; every key_parm must be a catalogue-recorded
    template name; every known_absent must be absent from the complete 22.0.400
    Lop type table AND absent from the connectivity Lop set; structural rules as
    in the H21 miner."""
    errors: list[str] = []
    for name, entry in content["entries"].items():
        if entry["category"] == "Lop":
            if name not in lop_types:
                errors.append(f"entry '{name}' does not resolve as a Lop type on "
                              f"{HOUDINI_BUILD} — the live catalogue has no such type")
                continue
            grounded = _grounded_parms(lop_types, name)
        elif entry["category"] == "Vop":
            if name not in vop_types:
                errors.append(f"entry '{name}' claims category 'Vop' but the live "
                              f"{HOUDINI_BUILD} Vop catalogue has no such type")
                continue
            grounded = _grounded_parms(vop_types, name)
        else:
            errors.append(f"entry '{name}' claims unsupported category "
                          f"{entry['category']!r}")
            continue
        for parm in entry["key_parms"]:
            if parm not in grounded:
                errors.append(f"entry '{name}' key_parm '{parm}' is not in the "
                              f"{HOUDINI_BUILD} catalogue parm surface — ungrounded claim")
    for name in content["known_absent"]:
        if name in content["entries"]:
            errors.append(f"'{name}' is in known_absent but also an entry — contradiction")
        if name in lop_types:
            errors.append(f"known_absent '{name}' IS in the {HOUDINI_BUILD} Lop type "
                          f"table — contradiction")
        if name in conn_lop:
            errors.append(f"known_absent '{name}' IS in the connectivity Lop set — contradiction")
    for r in content["ordering_rules"]:
        for key in ("requires_type", "on_type"):
            if r[key] not in content["entries"]:
                errors.append(f"ordering rule '{r['id']}' references unknown type '{r[key]}'")
        for t in r.get("satisfied_by", []):
            if t not in content["entries"]:
                errors.append(f"ordering rule '{r['id']}' satisfied_by references "
                              f"unknown type '{t}'")
    for recipe in content["recipes"]:
        for t in recipe.get("sequence", []):
            if t not in content["entries"]:
                errors.append(f"recipe '{recipe.get('name')}' sequence names unknown type '{t}'")
    return errors


def build_artifact() -> dict:
    content = _content()
    lop_types = _load_catalog(LOP_CATALOG, "Lop")
    vop_types = _load_catalog(VOP_CATALOG, "Vop")
    conn_lop, conn_blake = _connectivity()
    if not conn_lop or not conn_blake:
        raise SystemExit(f"connectivity catalog unusable at {_PKG_CONNECTIVITY} — the "
                         f"cross-check grounding input")
    errors = _consistency_gate(content, lop_types, vop_types, conn_lop)
    if errors:
        raise SystemExit("consistency gate FAILED (re-author):\n  - " + "\n  - ".join(errors))
    confirmed = sorted(n for n in content["entries"] if n in conn_lop)
    return {
        "schema": SCHEMA,
        "houdini_version": HOUDINI_BUILD,
        "source_digest": _source_digest(conn_blake),
        "blake2b": _blake(content),
        "probe_confirmed_types": confirmed,   # advisory: types also in the U.1-H22 probe
        "content": content,
    }


def _serialize(artifact: dict) -> str:
    # Deterministic: sorted keys, LF newline, no wall-clock. Byte-identical re-runs.
    return json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify the committed artifact is byte-identical to a fresh authoring; "
                         "write nothing")
    args = ap.parse_args(argv)

    artifact = build_artifact()
    text = _serialize(artifact)

    if args.check:
        if not ARTIFACT.is_file():
            print(f"MISSING artifact {ARTIFACT}", file=sys.stderr)
            return 1
        if ARTIFACT.read_text(encoding="utf-8") != text:
            print("DRIFT: committed artifact differs from a fresh authoring — re-run without "
                  "--check (or re-author if the catalogue/connectivity truth changed)",
                  file=sys.stderr)
            return 1
        if PKG.read_text(encoding="utf-8") != text:
            print("DRIFT: packaged copy differs from the harness artifact", file=sys.stderr)
            return 1
        print(f"OK {len(artifact['content']['entries'])} LOP types · "
              f"{len(artifact['probe_confirmed_types'])} probe-confirmed · byte-identical")
        return 0

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    PKG.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(text, encoding="utf-8", newline="\n")
    PKG.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {ARTIFACT.relative_to(_REPO)} + packaged copy · "
          f"{len(artifact['content']['entries'])} LOP types · "
          f"{len(artifact['probe_confirmed_types'])} probe-confirmed · "
          f"blake2b={artifact['blake2b']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
