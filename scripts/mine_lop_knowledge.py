#!/usr/bin/env python
"""Flywheel cycle U.5 EXPLORE — LOP/Solaris knowledge miner.

Mirrors host/introspect_connectivity.py's determinism contract, but the source
is a PROSE corpus (the Solaris reference), not a live probe. The resolution
(harness/notes/spec-U5-lop-solaris-flywheel.md):

  * The knowledge is an AUTHORED block — LLM-extracted from the named corpus
    files ONCE, committed here verbatim, carried with a provenance marker. This
    is the only non-deterministic step and it is human-ratified (flywheel_queue).
  * This miner is DETERMINISTIC and re-runnable (no LLM, no wall-clock): it
    reads the corpus to compute a `source_digest`, proves every authored entry
    is grounded in the corpus OR live probe truth (the consistency gate), stamps
    blake2b over the content, and writes byte-identical output. A source_digest
    mismatch means the corpus changed -> re-author (a human+LLM step), never a
    silent re-extract. "Probe truth > authored prose": a type the connectivity
    catalog affirmatively lacks is FLAGGED, not trusted.

Usage:
  python scripts/mine_lop_knowledge.py                 # write artifact + packaged copy
  python scripts/mine_lop_knowledge.py --check         # verify determinism, write nothing
  python scripts/mine_lop_knowledge.py --corpus-root G:/HOUDINI21_RAG_SYSTEM
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

SCHEMA = "lop_solaris_knowledge/v1"
HOUDINI_BUILD = "21.0.671"

_REPO = Path(__file__).resolve().parents[1]
ARTIFACT = _REPO / "harness" / "notes" / f"verified_lop_solaris_knowledge_{HOUDINI_BUILD}.json"
PKG = _REPO / "python" / "synapse" / "cognitive" / "tools" / "data" / "lop_solaris_knowledge_21.json"
_PKG_CONNECTIVITY = (_REPO / "python" / "synapse" / "cognitive" / "tools"
                     / "data" / "connectivity_21.json")

# Corpus files this cycle is authored from — relative to the corpus root. The
# source_digest is computed over exactly these; editing them re-arms re-authoring.
CORPUS_FILES = [
    "documentation/solaris_reference/solaris_nodes.md",
    "documentation/solaris_reference/scene_assembly.md",
]
DEFAULT_CORPUS_ROOT = os.environ.get("SYNAPSE_RAG_ROOT_G", "G:/HOUDINI21_RAG_SYSTEM")

# --------------------------------------------------------------------------
# AUTHORED content — LLM-extracted from CORPUS_FILES on 21.0.671, verbatim.
# NOT re-derived by this miner. Re-author when source_digest changes.
# --------------------------------------------------------------------------
_PROVENANCE = ("authored (LLM-extracted from documentation/solaris_reference/"
               "{solaris_nodes,scene_assembly}.md on H21.0.671); carried verbatim, "
               "NOT re-derived by the miner; re-author on source_digest mismatch")

# role -> the LOP node types + their key parms + gotchas, from solaris_nodes.md.
# usd_type is null where the corpus does not state one.
_ENTRIES = {
    # --- Geometry ---
    "sphere":       {"role": "geometry", "usd_type": "Sphere", "key_parms": ["tx", "ty", "tz"], "gotchas": []},
    "cube":         {"role": "geometry", "usd_type": "Cube", "key_parms": ["tx", "ty", "tz"], "gotchas": []},
    "sopimport":    {"role": "geometry", "usd_type": None, "key_parms": ["soppath"], "gotchas": []},
    "null":         {"role": "geometry", "usd_type": None, "key_parms": [], "gotchas": []},
    "merge":        {"role": "scene", "usd_type": None, "key_parms": [], "gotchas": []},
    # --- Lights ---
    "domelight":     {"role": "light", "usd_type": "DomeLight", "key_parms": [], "gotchas": []},
    "distantlight":  {"role": "light", "usd_type": "DistantLight", "key_parms": [], "gotchas": []},
    "rectlight":     {"role": "light", "usd_type": "RectLight", "key_parms": [], "gotchas": []},
    "disklight":     {"role": "light", "usd_type": "DiskLight", "key_parms": [], "gotchas": []},
    "cylinderlight": {"role": "light", "usd_type": "CylinderLight", "key_parms": [], "gotchas": []},
    "spherelight":   {"role": "light", "usd_type": "SphereLight", "key_parms": [], "gotchas": []},
    # --- Camera ---
    "camera": {"role": "camera", "usd_type": "Camera",
               "key_parms": ["focalLength", "fStop", "tx", "ty", "tz", "rx", "ry", "rz"], "gotchas": []},
    # --- Materials ---
    "materiallibrary": {"role": "material", "usd_type": None, "key_parms": [],
                        "gotchas": ["After creating materiallibrary, call matlib.cook(force=True) "
                                    "before creating child shader nodes, else createNode() returns None."]},
    "mtlxstandard_surface": {"role": "material", "usd_type": None,
                             "key_parms": ["base_colorr", "base_colorg", "base_colorb",
                                           "metalness", "specular_roughness"], "gotchas": []},
    "assignmaterial": {"role": "material", "usd_type": None,
                       "key_parms": ["primpattern1", "matspecpath1"], "gotchas": []},
    # --- Scene Structure ---
    "edit":      {"role": "scene", "usd_type": None,
                  "key_parms": ["primpattern", "tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"], "gotchas": []},
    "reference": {"role": "scene", "usd_type": None, "key_parms": ["filepath1", "primpath", "reftype"], "gotchas": []},
    "sublayer":  {"role": "scene", "usd_type": None, "key_parms": ["filepath1", "position"], "gotchas": []},
    # --- Render ---
    "karmarenderproperties": {"role": "render", "usd_type": None, "key_parms": ["engine"], "gotchas": []},
    "usdrender_rop":         {"role": "render", "usd_type": None, "key_parms": ["loppath", "outputimage"], "gotchas": []},
}

# Ordering constraints the corpus states or directly implies. The validator
# consumer enforces these on a proposed LOP graph.
_ORDERING_RULES = [
    {
        "id": "assignmaterial_requires_material_source",
        "requires_type": "materiallibrary",
        # Material prims can also arrive via a composition arc (a referenced or
        # sublayered USD layer that already authors them) — not only a
        # materiallibrary LOP. These satisfy the rule too. The consumer treats this
        # as an ADVISORY (a common-pattern heuristic, not a provable invariant).
        "satisfied_by": ["reference", "sublayer"],
        "on_type": "assignmaterial",
        "relation": "upstream",
        "detail": ("assignmaterial binds material prims that must be authored upstream — "
                   "usually by a materiallibrary (cook it, matlib.cook(force=True), before its "
                   "shaders resolve), or brought in by a reference/sublayer composition arc; "
                   "materials may also already exist in a pre-composed stage."),
    },
]

# Types the corpus affirmatively marks ABSENT — a proposal naming these is a
# known pitfall, and the remediation is corpus-grounded.
_KNOWN_ABSENT = {
    "grid":  {"remediation": "there is NO grid LOP — use a cube with sy=0.01 for a ground plane"},
    "plane": {"remediation": "there is NO plane LOP — use a cube with sy=0.01 for a ground plane"},
}

# Composition strengths (scene_assembly.md) — reference vs sublayer.
_COMPOSITION = {
    "reference": {"strength": "stronger-overridable", "key_parms": ["filepath1", "primpath", "reftype"],
                  "use": "import assets under a prim path; per-instance overrides"},
    "sublayer": {"strength": "strongest-direct-edit", "key_parms": ["filepath1", "position"],
                 "use": "merge a full layer (environments, lighting rigs, base layers)"},
}

# A canonical render-scene node sequence (solaris_nodes + scene_assembly) — advisory
# order used by the planner and asserted by the ordering rule.
_RECIPES = [
    {"name": "solaris_render_scene",
     "sequence": ["sphere", "materiallibrary", "assignmaterial", "camera", "domelight",
                  "karmarenderproperties", "null"],
     "note": "geo -> matlib (+child shader, cooked) -> assignmaterial -> camera -> light "
             "-> karmarenderproperties -> OUTPUT null"},
]


def _content() -> dict:
    """The integrity-covered payload. blake2b is stamped over exactly this."""
    entries = {}
    for name, e in _ENTRIES.items():
        entries[name] = {
            "category": "Lop",
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


def _source_digest(root: Path) -> tuple[str, list[str]]:
    """blake2b over the sorted (relpath, sha256) of every corpus source file.
    Returns (digest, missing[]). A missing source is fatal to a fresh mine."""
    pairs, missing = [], []
    for rel in sorted(CORPUS_FILES):
        fp = root / rel
        if not fp.is_file():
            missing.append(rel)
            continue
        h = hashlib.sha256(fp.read_bytes()).hexdigest()
        pairs.append(f"{rel}\0{h}")
    digest = hashlib.blake2b("\n".join(pairs).encode("utf-8"), digest_size=16).hexdigest()
    return digest, missing


def _consistency_gate(content: dict, root: Path, conn_lop: set[str]) -> list[str]:
    """Every authored entry must be GROUNDED: its type_name appears in the corpus
    text OR in the live connectivity catalog's Lop types. An entry grounded in
    NEITHER is an ungrounded claim -> fail. known_absent types must NOT also be
    entries. (Probe truth > authored prose.)"""
    errors = []
    corpus_text = ""
    for rel in CORPUS_FILES:
        fp = root / rel
        if fp.is_file():
            corpus_text += fp.read_text(encoding="utf-8", errors="replace")
    for name in content["entries"]:
        if name not in corpus_text and name not in conn_lop:
            errors.append(f"entry '{name}' is grounded in neither the corpus nor the "
                          f"connectivity catalog — ungrounded claim")
    for name in content["known_absent"]:
        if name in content["entries"]:
            errors.append(f"'{name}' is in known_absent but also an entry — contradiction")
    # ordering rules must reference real entries
    for r in content["ordering_rules"]:
        for key in ("requires_type", "on_type"):
            if r[key] not in content["entries"]:
                errors.append(f"ordering rule '{r['id']}' references unknown type '{r[key]}'")
        for t in r.get("satisfied_by", []):
            if t not in content["entries"]:
                errors.append(f"ordering rule '{r['id']}' satisfied_by references "
                              f"unknown type '{t}'")
    return errors


def _connectivity_lop_types() -> set[str]:
    """The Lop type names the live connectivity probe recorded (advisory cross-check)."""
    try:
        data = json.loads(_PKG_CONNECTIVITY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    out = set()
    for entry in data.get("entries", {}).values():
        if entry.get("category") == "Lop":
            tn = entry.get("type_name", "")
            out.add(tn.split("::")[0])
    return out


def build_artifact(root: Path) -> dict:
    content = _content()
    src_digest, missing = _source_digest(root)
    if missing:
        raise SystemExit(f"corpus source(s) missing under {root}: {missing} — "
                         f"pass --corpus-root or set SYNAPSE_RAG_ROOT_G")
    conn_lop = _connectivity_lop_types()
    errors = _consistency_gate(content, root, conn_lop)
    if errors:
        raise SystemExit("consistency gate FAILED (re-author):\n  - " + "\n  - ".join(errors))
    confirmed = sorted(n for n in content["entries"] if n in conn_lop)
    return {
        "schema": SCHEMA,
        "houdini_version": HOUDINI_BUILD,
        "source_digest": src_digest,
        "blake2b": _blake(content),
        "probe_confirmed_types": confirmed,   # advisory: types also seen live
        "content": content,
    }


def _serialize(artifact: dict) -> str:
    # Deterministic: sorted keys, LF newline, no wall-clock. Byte-identical re-runs.
    return json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-root", default=DEFAULT_CORPUS_ROOT)
    ap.add_argument("--check", action="store_true",
                    help="verify the committed artifact is byte-identical to a fresh mine; write nothing")
    args = ap.parse_args(argv)

    root = Path(args.corpus_root)
    artifact = build_artifact(root)
    text = _serialize(artifact)

    if args.check:
        if not ARTIFACT.is_file():
            print(f"MISSING artifact {ARTIFACT}", file=sys.stderr)
            return 1
        on_disk = ARTIFACT.read_text(encoding="utf-8")
        if on_disk != text:
            print("DRIFT: committed artifact differs from a fresh mine — re-run without --check "
                  "(or re-author if the corpus changed)", file=sys.stderr)
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
