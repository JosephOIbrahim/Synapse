#!/usr/bin/env python
"""C-U5 — H22 LOP/Solaris knowledge author (probe-grounded, deterministic).

Sibling of scripts/mine_lop_knowledge.py for the 22.0.368 catalog. The H21
miner grounds its authored block in a PROSE corpus (the Solaris reference);
no H22 solaris_reference corpus exists, so for H22 the grounding source shifts
to the banked hython probe artifact + the U.1 connectivity catalog:

  * harness/notes/lop_solaris_probe_22.0.368_2026-07-17.json  (the C-U5 probe)
  * python/synapse/cognitive/tools/data/connectivity_22.json  (the U.1-H22 probe)

Same determinism contract as the miner: the knowledge is an AUTHORED block —
extracted from the probe artifact ONCE, committed here verbatim, carried with a
provenance marker. This script is DETERMINISTIC and re-runnable (no LLM, no
wall-clock): it proves every authored entry/key_parm/known_absent claim against
the probe artifact (the consistency gate), computes ``source_digest`` over the
two grounding files, stamps blake2b over the content, and writes the packaged
copy + harness twin byte-identically. A source_digest mismatch means the
grounding truth changed -> re-author (a human+LLM step), never a silent
re-extract. "Probe truth > authored prose", now literally: a claim the probe
does not carry FAILS the gate.

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
HOUDINI_BUILD = "22.0.368"
PROBE_SCHEMA = "lop_solaris_probe/v1"

_REPO = Path(__file__).resolve().parents[1]
ARTIFACT = _REPO / "harness" / "notes" / f"verified_lop_solaris_knowledge_{HOUDINI_BUILD}.json"
PKG = (_REPO / "python" / "synapse" / "cognitive" / "tools" / "data"
       / "lop_solaris_knowledge_22.json")
PROBE = _REPO / "harness" / "notes" / f"lop_solaris_probe_{HOUDINI_BUILD}_2026-07-17.json"
_PKG_CONNECTIVITY = (_REPO / "python" / "synapse" / "cognitive" / "tools"
                     / "data" / "connectivity_22.json")

# --------------------------------------------------------------------------
# AUTHORED content — extracted from the PROBE artifact on 22.0.368, verbatim.
# NOT re-derived by this script. Re-author when source_digest changes.
# --------------------------------------------------------------------------
_PROVENANCE = (
    "authored from the banked hython probe harness/notes/"
    f"lop_solaris_probe_{HOUDINI_BUILD}_2026-07-17.json on H{HOUDINI_BUILD} "
    "(probe truth — no H22 solaris_reference corpus exists, so the H21 miner's "
    "corpus grounding does not transfer); carried verbatim, NOT re-derived by "
    "this script; re-author on source_digest mismatch. source_digest = blake2b "
    "over connectivity_22.json's blake2b stamp + the probe artifact's sha256. "
    "Tier notes: usd_type is semantic USD-schema knowledge carried at authored "
    "tier (the probe records node types + parm templates, not USD prim "
    "classes); key_parms use TEMPLATE spellings (t/r/s tuple parms cover "
    "tx..sz components; multiparm templates carry '#', runtime instance 1 is "
    "'1'); materiallibrary's cook(force=True) gotcha is H21-era operational "
    "knowledge carried NOT re-proved by this template-walk probe."
)

# name -> role / usd_type / key_parms / gotchas [+ category, default Lop].
# Every claim below is gated against the probe artifact by _consistency_gate.
_ENTRIES = {
    # --- Geometry ---
    "sphere":    {"role": "geometry", "usd_type": "Sphere", "key_parms": ["radius", "t"], "gotchas": []},
    "cube":      {"role": "geometry", "usd_type": "Cube", "key_parms": ["size", "t"], "gotchas": []},
    "plane":     {"role": "geometry", "usd_type": "Plane",
                  "key_parms": ["axis", "length", "width", "t"],
                  "gotchas": ["NEW on 22.0.368 — the H21 catalog marked plane known_absent; "
                              "it is now a real LOP type."]},
    "sopimport": {"role": "geometry", "usd_type": None, "key_parms": ["soppath"], "gotchas": []},
    "null":      {"role": "geometry", "usd_type": None, "key_parms": [], "gotchas": []},
    "merge":     {"role": "scene", "usd_type": None, "key_parms": [], "gotchas": []},
    # --- Lights (H22 consolidation: per-shape lights are gone, see known_absent) ---
    "domelight": {"role": "light", "usd_type": "DomeLight",
                  "key_parms": ["primpath", "xn__inputsexposure_vya",
                                "xn__inputsintensity_i0a", "xn__inputstexturefile_r3ah"],
                  "gotchas": ["createNode('domelight') resolves to domelight::3.0 on 22.0.368 — "
                              "its UsdLux inputs are punycode-namespaced (xn__inputs*); plain "
                              "intensity/exposure/xn__texturefile_0ta spellings live only on the "
                              "legacy unversioned template."]},
    "distantlight": {"role": "light", "usd_type": "DistantLight",
                     "key_parms": ["primpath", "xn__inputsangle_zta",
                                   "xn__inputsexposure_vya", "xn__inputsintensity_i0a"],
                     "gotchas": ["createNode('distantlight') resolves to distantlight::2.0 on "
                                 "22.0.368 — UsdLux inputs are punycode-namespaced (xn__inputs*); "
                                 "plain intensity/exposure live only on the legacy unversioned "
                                 "template."]},
    "light": {"role": "light", "usd_type": None,
              "key_parms": ["lighttype", "primpath", "xn__inputsexposure_vya",
                            "xn__inputsintensity_i0a"],
              "gotchas": ["The consolidated light LOP supersedes the H21-era per-shape lights "
                          "(sphere/rect/disk/cylinder) — shape via the lighttype parm, so "
                          "usd_type varies with it. createNode('light') resolves to light::2.0, "
                          "whose UsdLux inputs are punycode-namespaced (xn__inputs*): per-shape "
                          "dims at xn__inputsradius_mva / xn__inputswidth_zta / "
                          "xn__inputsheight_mva / xn__inputslength_mva."]},
    # --- Camera ---
    "camera": {"role": "camera", "usd_type": "Camera",
               "key_parms": ["fStop", "focalLength", "r", "t"],
               "gotchas": ["Transform templates are the t/r tuple parms on 22.0.368 — component "
                           "spellings (tx..rz) are not template names."]},
    # --- Materials ---
    "materiallibrary": {"role": "material", "usd_type": None,
                        "key_parms": ["matnode#", "matpath#"],
                        "gotchas": ["After creating materiallibrary, call matlib.cook(force=True) "
                                    "before creating child shader nodes, else createNode() returns "
                                    "None. (H21-era operational knowledge; NOT re-proved by the "
                                    "22.0.368 template-walk probe.)"]},
    "mtlxstandard_surface": {"role": "material", "usd_type": None, "category": "Vop",
                             "key_parms": [],
                             "gotchas": ["NOT a Lop type on 22.0.368 — resolves only in the Vop "
                                         "category (creation at /stage fails 'Invalid node type "
                                         "name'); create it INSIDE a materiallibrary as a child "
                                         "shader node."]},
    "assignmaterial": {"role": "material", "usd_type": None,
                       "key_parms": ["matspecpath#", "primpattern#"],
                       "gotchas": ["primpattern#/matspecpath# are multiparm TEMPLATES on "
                                   "22.0.368 — the H21 catalog carried the instance spellings "
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
                  "gotchas": ["The H21-era 'position' parm is gone on 22.0.368 — use "
                              "positionindex/positiontype; filepath# is a multiparm template "
                              "(instance 1 is filepath1)."]},
    # --- Instancing family (W.3: H22 renamed the set-dressing LOPs) ---
    "copytopoints": {"role": "geometry", "usd_type": None,
                     "key_parms": ["method", "pointsoppath", "protoindexsrc", "seed"],
                     "gotchas": ["The H21-era 'instancer' spelling is gone from the 22.0.368 type "
                                 "table; createNode('instancer') silently aliases here — author "
                                 "the canonical 'copytopoints' spelling."]},
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
                              "gotchas": ["DEPRECATED on 22.0.368 (nodeType deprecation flag) — "
                                          "still resolves; prefer karmarendersettings."]},
    "karmarendersettings": {"role": "render", "usd_type": None,
                            "key_parms": ["engine", "primpath"], "gotchas": []},
    "usdrender_rop": {"role": "render", "usd_type": None,
                      "key_parms": ["loppath", "outputimage"], "gotchas": []},
}

# Ordering constraints — carried verbatim from U.5 (the rule's participants all
# re-proved live on 22.0.368: materiallibrary/reference/sublayer in
# connectivity_22.json). The consumer treats this as an ADVISORY.
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

# Types the PROBE affirmatively marks ABSENT on 22.0.368 (resolves_in_lop false)
# — a proposal naming these is a known pitfall; each remediation names the
# canonical successor. NOTE 'instancer': absent from the type table, but
# createNode('instancer') SILENTLY aliases to copytopoints (creation-probe
# evidence) — flagged anyway per the W.3 "canonical spelling, never the
# opalias" rule; the remediation states both facts.
_KNOWN_ABSENT = {
    "grid": {"remediation": "there is NO grid LOP on 22.0.368 (grid is a Sop type) — use the "
                            "plane LOP (a real LOP type on 22.0.368) or a cube scaled flat"},
    "spherelight": {"remediation": "no spherelight LOP on 22.0.368 (creation fails) — use the "
                                   "consolidated light LOP (createNode('light') -> light::2.0) "
                                   "and set its lighttype parm to the sphere shape"},
    "rectlight": {"remediation": "no rectlight LOP on 22.0.368 (creation fails) — use the "
                                 "consolidated light LOP (createNode('light') -> light::2.0) "
                                 "and set its lighttype parm to the rectangle shape"},
    "disklight": {"remediation": "no disklight LOP on 22.0.368 (creation fails) — use the "
                                 "consolidated light LOP (createNode('light') -> light::2.0) "
                                 "and set its lighttype parm to the disk shape"},
    "cylinderlight": {"remediation": "no cylinderlight LOP on 22.0.368 (creation fails) — use "
                                     "the consolidated light LOP (createNode('light') -> "
                                     "light::2.0) and set its lighttype parm to the cylinder "
                                     "shape"},
    "instancer": {"remediation": "gone from the 22.0.368 type table — createNode('instancer') "
                                 "silently aliases to copytopoints (a silent-success trap); "
                                 "author the canonical copytopoints (or pointinstancer for "
                                 "PointInstancer prims) instead"},
}

# Composition strengths — USD semantics (build-agnostic); key_parms re-proved
# against the 22.0.368 template walk (sublayer's H21-era 'position' is gone).
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
# karmarenderproperties is deprecated on 22.0.368.
_RECIPES = [
    {"name": "solaris_render_scene",
     "sequence": ["sphere", "materiallibrary", "assignmaterial", "camera", "domelight",
                  "karmarendersettings", "null"],
     "note": "geo -> matlib (+child shader, cooked) -> assignmaterial -> camera -> light "
             "-> karmarendersettings (karmarenderproperties is deprecated on 22.0.368) "
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


def _load_probe() -> dict:
    if not PROBE.is_file():
        raise SystemExit(f"probe artifact missing: {PROBE} — the C-U5 grounding truth; "
                         f"re-run the hython probe before authoring")
    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    if probe.get("schema") != PROBE_SCHEMA:
        raise SystemExit(f"probe artifact schema {probe.get('schema')!r} != {PROBE_SCHEMA!r}")
    if probe.get("houdini_version") != HOUDINI_BUILD or not probe.get("houdini_version_match"):
        raise SystemExit(f"probe artifact is not a verified {HOUDINI_BUILD} probe "
                         f"(houdini_version={probe.get('houdini_version')!r}, "
                         f"match={probe.get('houdini_version_match')!r})")
    return probe


def _connectivity() -> tuple[set[str], str]:
    """(Lop type-name set, blake2b stamp) from the U.1-H22 connectivity catalog."""
    data = json.loads(_PKG_CONNECTIVITY.read_text(encoding="utf-8"))
    lop = {e.get("type_name", "").split("::")[0]
           for e in data.get("entries", {}).values() if e.get("category") == "Lop"}
    return lop, str(data.get("blake2b", ""))


def _source_digest(conn_blake: str) -> str:
    """blake2b over the connectivity stamp + the probe artifact's sha256 — the
    two grounding inputs; either changing re-arms re-authoring."""
    probe_sha = hashlib.sha256(PROBE.read_bytes()).hexdigest()
    return hashlib.blake2b(f"{conn_blake}\0{probe_sha}".encode("utf-8"),
                           digest_size=16).hexdigest()


def _grounded_parms(probe: dict, name: str) -> set[str]:
    """The probe-verified parm surface for an authored type: its own record plus
    the record of the type creation actually resolves to (e.g. domelight ->
    domelight::3.0), across parm_names / role_relevant_parms / exact-verdict
    h21_key_parms."""
    probes = probe.get("probes", {})
    names = [name]
    created = (probe.get("creation_resolution", {}).get(name) or {}).get("created_type")
    if created and created != name:
        names.append(created)
    out: set[str] = set()
    for n in names:
        rec = probes.get(n) or {}
        out.update(rec.get("parm_names") or [])
        out.update(rec.get("role_relevant_parms") or [])
        out.update(k for k, v in (rec.get("h21_key_parms") or {}).items() if v == "exact")
    return out


def _consistency_gate(content: dict, probe: dict, conn_lop: set[str]) -> list[str]:
    """Probe truth > authored prose, enforced: every entry must resolve on
    22.0.368 in its stated category; every key_parm must be a probe-recorded
    template name; every known_absent must be probe-proved absent AND absent
    from the connectivity Lop set; structural rules as in the H21 miner."""
    errors: list[str] = []
    probes = probe.get("probes", {})
    for name, entry in content["entries"].items():
        rec = probes.get(name)
        if rec is None:
            errors.append(f"entry '{name}' has no probe record — ungrounded claim")
            continue
        if entry["category"] == "Lop":
            if not rec.get("resolves_in_lop"):
                errors.append(f"entry '{name}' does not resolve as a Lop type on "
                              f"{HOUDINI_BUILD} — probe says absent")
        else:
            other = rec.get("found_in_other_categories") or {}
            if entry["category"] not in other:
                errors.append(f"entry '{name}' claims category '{entry['category']}' but the "
                              f"probe does not place it there")
        grounded = _grounded_parms(probe, name)
        for parm in entry["key_parms"]:
            if parm not in grounded:
                errors.append(f"entry '{name}' key_parm '{parm}' is not in the probe-verified "
                              f"parm surface — ungrounded claim")
    for name in content["known_absent"]:
        if name in content["entries"]:
            errors.append(f"'{name}' is in known_absent but also an entry — contradiction")
        rec = probes.get(name)
        if rec is None or rec.get("resolves_in_lop"):
            errors.append(f"known_absent '{name}' is not probe-proved absent on {HOUDINI_BUILD}")
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
    probe = _load_probe()
    conn_lop, conn_blake = _connectivity()
    if not conn_lop or not conn_blake:
        raise SystemExit(f"connectivity catalog unusable at {_PKG_CONNECTIVITY} — the "
                         f"cross-check grounding input")
    errors = _consistency_gate(content, probe, conn_lop)
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
                  "--check (or re-author if the probe/connectivity truth changed)",
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
