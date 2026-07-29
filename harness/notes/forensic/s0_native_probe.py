"""S0 · native-floor probe — what Houdini 22.0.368 ships, observed on the live build.

READ-ONLY. Opens no scene, writes no scene state, creates no nodes. It enumerates the
registered node-type surface and the `hou` module surface and pattern-matches them.

LAW 1 — state the condition under which this check fails:
  The AI/agent sweep fails (i.e. reports a presence) if any registered node type or any
  `hou` attribute name matches the AI vocabulary. It reports an ABSENCE only when the
  POSITIVE CONTROL in the same class returns hits with the identical mechanism — the
  control searches for terms known to exist on this build (karma, apex, rig, ml).
  If the control returns zero, the search mechanism is broken and the absence is void.

Producer path for every number this emits: this file, run under
  "C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython3.13.exe"

Emits JSON on stdout between the BEGIN_JSON / END_JSON markers.
"""

import json
import re
import sys

import hou

# ---------------------------------------------------------------- vocabularies

# The thing we are testing for the absence of.
AI_VOCAB = [
    "ai", "llm", "gpt", "chatgpt", "claude", "copilot", "assistant", "agent",
    "chat", "prompt", "mcp", "naturallanguage", "natural_language", "genai",
    "diffusion", "stablediffusion", "texttoimage", "text_to_image",
]

# Same-class positive control: terms that MUST be present on a healthy H22 build.
# If any of these returns zero the search mechanism is broken and no absence claim stands.
CONTROL_VOCAB = ["karma", "apex", "rig", "ml", "usd", "copernicus", "solaris"]

# Machine-learning + rig-generation surface, enumerated rather than pattern-matched.
ML_PREFIXES = ["ml", "onnx", "tensor", "neural"]
RIG_PREFIXES = ["apex", "autorig", "rig", "kinefx", "character"]

WORD = re.compile(r"[^a-z0-9]+")


def norm(s):
    return WORD.sub("", s.lower())


def all_node_types():
    """[(category_name, type_name, label)] over every registered node type category."""
    out = []
    for cat_name, cat in hou.nodeTypeCategories().items():
        try:
            types = cat.nodeTypes()
        except Exception as exc:  # pragma: no cover - defensive on an unknown category
            out.append((cat_name, "<ENUMERATION FAILED>", repr(exc)))
            continue
        for tname, ntype in types.items():
            try:
                label = ntype.description()
            except Exception:
                label = ""
            out.append((cat_name, tname, label))
    return out


def sweep(types, vocab):
    """token -> list of 'category/typename  (label)' whose name OR label matches."""
    hits = {t: [] for t in vocab}
    for cat_name, tname, label in types:
        ntok = norm(tname)
        ltok = norm(label)
        for token in vocab:
            if token in ntok or token in ltok:
                hits[token].append("%s/%s  (%s)" % (cat_name, tname, label))
    return hits


def by_prefix(types, prefixes):
    out = []
    for cat_name, tname, label in types:
        base = tname.split("::")[0].lower()
        for p in prefixes:
            if base.startswith(p):
                out.append("%s/%s  (%s)" % (cat_name, tname, label))
                break
    return sorted(set(out))


def hou_surface(vocab):
    names = dir(hou)
    hits = {t: [] for t in vocab}
    for n in names:
        tok = norm(n)
        for token in vocab:
            if token in tok:
                hits[token].append(n)
    return hits, len(names)


def main():
    types = all_node_types()

    ai_hits = sweep(types, AI_VOCAB)
    control_hits = sweep(types, CONTROL_VOCAB)
    hou_ai, hou_attr_count = hou_surface(AI_VOCAB)
    hou_control, _ = hou_surface(CONTROL_VOCAB)

    control_ok = all(len(control_hits[t]) > 0 for t in CONTROL_VOCAB)

    cat_counts = {}
    for cat_name, tname, _ in types:
        if tname == "<ENUMERATION FAILED>":
            continue
        cat_counts[cat_name] = cat_counts.get(cat_name, 0) + 1

    result = {
        "build": {
            "applicationVersionString": hou.applicationVersionString(),
            "applicationName": hou.applicationName(),
            "applicationVersion": list(hou.applicationVersion()),
            "python": sys.version.split()[0],
            "hfs": hou.getenv("HFS"),
            "isUIAvailable": hou.isUIAvailable(),
        },
        "surface_size": {
            "node_types_total": len([t for t in types if t[1] != "<ENUMERATION FAILED>"]),
            "categories": len(cat_counts),
            "per_category": dict(sorted(cat_counts.items())),
            "hou_attributes": hou_attr_count,
        },
        "positive_control": {
            "passed": control_ok,
            "note": "Absence claims below are VOID unless this is true. Same mechanism, same corpus.",
            "counts": {t: len(v) for t, v in control_hits.items()},
            "sample": {t: v[:3] for t, v in control_hits.items()},
            "hou_module_counts": {t: len(v) for t, v in hou_control.items()},
        },
        "ai_sweep_node_types": {
            "counts": {t: len(v) for t, v in ai_hits.items()},
            "hits": {t: v for t, v in ai_hits.items() if v},
        },
        "ai_sweep_hou_module": {
            "counts": {t: len(v) for t, v in hou_ai.items()},
            "hits": {t: v for t, v in hou_ai.items() if v},
        },
        "ml_node_types": by_prefix(types, ML_PREFIXES),
        "rig_node_types": by_prefix(types, RIG_PREFIXES),
        "enumeration_failures": [
            "%s: %s" % (c, l) for (c, t, l) in types if t == "<ENUMERATION FAILED>"
        ],
    }

    print("BEGIN_JSON")
    print(json.dumps(result, indent=1))
    print("END_JSON")


main()
