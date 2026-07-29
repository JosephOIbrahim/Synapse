"""S0 · native-floor delta — the producer path for every H21-vs-H22 figure cited in
harness/notes/forensic/S0_SCOUT.md.

Inputs (both written by s0_typedump.py, run under each build's own hython):
    typedump_21.0.773.json
    typedump_22.0.368.json

LAW 1 — the conditions under which the delta claim is VOID:
  (a) THIRD_PARTY types are excluded. A registered node-type surface contains whatever HDAs
      the environment loaded; H21 here carries RenderMan, ComfyUI, Modeler and a camera-rig
      package. An unfiltered A-vs-B count is not a vendor delta.
  (b) NATIVE_COMPILED is NOT a pure SideFX bucket. Compiled third-party DSO plugins register
      node types with no HDA definition and land in it — V-Ray VOPs are present in the H21
      dump by exactly this route. So the NET count is reported as bounded, not exact, and
      only the SideFX-NAMESPACED delta rows are cited as vendor facts.
  (c) The AI-absence claim is void unless the same-mechanism positive control returns hits.

Run:  python harness/notes/forensic/s0_native_delta.py
Emits: s0_native_delta.json  +  a human-readable summary on stdout.
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
OLD, NEW = "21.0.773", "22.0.368"

# Namespaces that are unambiguously SideFX-authored in the type name itself.
SIDEFX_NS = re.compile(r"(^|/)(sidefx::|apex|kinefx::|ml_|neural|onnx|labs::)", re.I)

# The vocabulary the absence claim is about.
ABSENCE_VOCAB = [
    "llm", "gpt", "chatgpt", "claude", "copilot", "assistant", "mcp",
    "genai", "languagemodel", "chatbot", "naturallanguage",
]
# Same-class control: must be present, by the identical mechanism, or (c) voids the claim.
CONTROL_VOCAB = ["karma", "apex", "onnx", "vellum", "pyro"]

ML_VOCAB = re.compile(r"ml_|neural|onnx|gsplat|tensor", re.I)


def load(v):
    with open(os.path.join(HERE, "typedump_%s.json" % v), encoding="utf-8") as fh:
        return json.load(fh)


def native(d):
    return {k: v for k, v in d["types"].items()
            if v["bucket"] in ("NATIVE_COMPILED", "NATIVE_HDA")}


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def vocab_hits(types, vocab):
    out = {t: [] for t in vocab}
    for k, v in types.items():
        blob = norm(k) + " " + norm(v["label"])
        for t in vocab:
            if t in blob:
                out[t].append("%s (%s)" % (k, v["label"]))
    return out


a, b = load(OLD), load(NEW)
na, nb = native(a), native(b)

added = sorted(set(nb) - set(na))
removed = sorted(set(na) - set(nb))

added_sidefx = [k for k in added if SIDEFX_NS.search(k)]
added_ml = [k for k in added if ML_VOCAB.search(k) or ML_VOCAB.search(nb[k]["label"])]

absence_new = vocab_hits(nb, ABSENCE_VOCAB)
control_new = vocab_hits(nb, CONTROL_VOCAB)
control_ok = all(len(control_new[t]) > 0 for t in CONTROL_VOCAB)

result = {
    "producer": "harness/notes/forensic/s0_native_delta.py",
    "inputs": ["typedump_%s.json" % OLD, "typedump_%s.json" % NEW],
    "builds": {
        OLD: {"python": a["python"], "total": a["count_total"], "buckets": a["buckets"]},
        NEW: {"python": b["python"], "total": b["count_total"], "buckets": b["buckets"]},
    },
    "native_only_counts": {OLD: len(na), NEW: len(nb), "net": len(nb) - len(na)},
    "net_is_bounded_not_exact": (
        "NATIVE_COMPILED includes compiled third-party DSO plugins (V-Ray VOPs appear in the "
        "H21 dump by this route), so the net figure is an upper bound on churn, not a clean "
        "vendor delta. Only the SideFX-namespaced rows below are cited as vendor facts."
    ),
    "added_native": len(added),
    "removed_native": len(removed),
    "added_sidefx_namespaced": len(added_sidefx),
    "added_ml_vocabulary": {
        "count": len(added_ml),
        "types": sorted("%s  (%s)" % (k, nb[k]["label"]) for k in added_ml),
    },
    "ml_surface_size": {
        OLD: sum(1 for k, v in na.items() if ML_VOCAB.search(k) or ML_VOCAB.search(v["label"])),
        NEW: sum(1 for k, v in nb.items() if ML_VOCAB.search(k) or ML_VOCAB.search(v["label"])),
    },
    "absence_sweep_on_%s" % NEW: {
        "vocabulary": ABSENCE_VOCAB,
        "counts": {t: len(v) for t, v in absence_new.items()},
        "hits": {t: v for t, v in absence_new.items() if v},
    },
    "positive_control_on_%s" % NEW: {
        "passed": control_ok,
        "vocabulary": CONTROL_VOCAB,
        "counts": {t: len(v) for t, v in control_new.items()},
        "meaning": "If passed is false the absence sweep proves nothing and must not be cited.",
    },
    "third_party_libraries_present": {
        OLD: a["third_party_libraries"],
        NEW: b["third_party_libraries"],
    },
}

with open(os.path.join(HERE, "s0_native_delta.json"), "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=1, sort_keys=False)

print("native-only  H%s=%d  H%s=%d  net=%+d"
      % (OLD, len(na), NEW, len(nb), len(nb) - len(na)))
print("added=%d  removed=%d  added-sidefx-namespaced=%d  added-ML-vocab=%d"
      % (len(added), len(removed), len(added_sidefx), len(added_ml)))
print("ML surface: H%s=%d -> H%s=%d"
      % (OLD, result["ml_surface_size"][OLD], NEW, result["ml_surface_size"][NEW]))
print("ABSENCE counts: %s" % json.dumps(result["absence_sweep_on_%s" % NEW]["counts"]))
print("ABSENCE hits:   %s" % json.dumps(result["absence_sweep_on_%s" % NEW]["hits"]))
print("CONTROL passed=%s  %s"
      % (control_ok, json.dumps(result["positive_control_on_%s" % NEW]["counts"])))
