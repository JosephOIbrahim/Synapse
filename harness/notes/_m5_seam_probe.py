"""M5 VERIFIED-RUNTIME probe #2: the two questions the design rests on.

Q1 (F-1 feasibility)  Does adding a NETWORK BOX change the composed USD?
    The fixture's baseline sha256 was produced by a builder that created NO
    box (probes.py::_build_fixture_once). The reconciler DOES create one
    (D1). If a box perturbs the composed stage, F-1 can never be green and
    the ownership ruling and the oracle are in direct conflict.

Q2 (D3 provability)  What exactly does box.nodes(recurse=...) enumerate,
    and does a node nested inside a member subnet count as a box member?
    D3 permits deleting box members ONLY, so the enumeration semantics ARE
    the safety boundary.

Q3 (canonicalizer seam) Is `synapse.blocks.canonical` importable from the
    autoresearch harness cheaply, or does layering forbid it?

Run:  hython harness/notes/_m5_seam_probe.py
"""
import hashlib
import json
import sys
import time
from pathlib import Path

import hou

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "harness" / "autoresearch"))

from probes import canonicalize_usda  # noqa: E402

out = {"build": hou.applicationVersionString()}

FX = json.loads((REPO / "fixtures" / "solaris.basic.json").read_text(encoding="utf-8"))
BASELINE = FX["baseline"]["sha256"]
out["baseline_from_fixture"] = BASELINE

stage = hou.node("/stage")


def _build(with_box):
    """Build the fixture exactly as probes._build_fixture_once does, with an
    optional network box wrapped around it. Returns (sha256, cleanup_fn)."""
    nodes = {}
    order = []
    for spec in FX["nodes"]:
        n = stage.createNode(spec["type"], spec["name"])
        nodes[spec["name"]] = n
        order.append(n)
    for spec in FX["nodes"]:
        for pname, pval in spec.get("parms", {}).items():
            p = nodes[spec["name"]].parm(pname)
            if p is None:
                raise RuntimeError("missing parm %s.%s" % (spec["name"], pname))
            p.set(pval)
    for dst, idx, src in FX.get("wires", []):
        nodes[dst].setInput(int(idx), nodes[src])
    for spec in FX["nodes"]:
        pos = spec.get("position")
        if pos:
            nodes[spec["name"]].setPosition(
                hou.Vector2(float(pos[0]), float(pos[1])))
    box = None
    if with_box:
        box = stage.createNetworkBox(FX["ownership"]["network_box"])
        for n in order:
            box.addItem(n)
    tail = nodes[FX["display"]]
    tail.setDisplayFlag(True)
    composed = tail.stage()
    canon = canonicalize_usda(composed.Flatten().ExportToString())
    sha = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    return sha, order, box


# --- Q1 -------------------------------------------------------------------
sha_nobox, order, _ = _build(False)
for n in reversed(order):
    n.destroy()
out["sha_without_box"] = sha_nobox
out["sha_without_box_matches_baseline"] = (sha_nobox == BASELINE)

sha_box, order, box = _build(True)
out["sha_with_box"] = sha_box
out["sha_with_box_matches_baseline"] = (sha_box == BASELINE)
out["box_is_usd_neutral"] = (sha_box == sha_nobox)

# --- Q2 -------------------------------------------------------------------
out["box_nodes_recurse_default"] = sorted(n.name() for n in box.nodes())
out["box_nodes_recurse_false"] = sorted(n.name() for n in box.nodes(recurse=False))

sub = stage.createNode("subnet", "m5_probe_subnet")
box.addItem(sub)
inner = sub.createNode("null", "m5_probe_inner")
out["with_subnet_recurse_true"] = sorted(n.name() for n in box.nodes(recurse=True))
out["with_subnet_recurse_false"] = sorted(n.name() for n in box.nodes(recurse=False))
out["inner_parentNetworkBox"] = (
    inner.parentNetworkBox().name() if inner.parentNetworkBox() else None
)
sub.destroy()

# outside node must NOT appear
outsider = stage.createNode("null", "m5_probe_outsider")
out["outsider_in_box"] = "m5_probe_outsider" in [n.name() for n in box.nodes()]
out["outsider_parentNetworkBox"] = (
    outsider.parentNetworkBox().name() if outsider.parentNetworkBox() else None
)
outsider.destroy()

for n in reversed(order):
    n.destroy()
box.destroy()
out["stage_clean_after"] = (
    [c.name() for c in stage.children()],
    [b.name() for b in stage.networkBoxes()],
)

# --- Q3 -------------------------------------------------------------------
sys.path.insert(0, str(REPO / "python"))
t0 = time.time()
try:
    import synapse  # noqa: F401
    out["import_synapse_secs"] = round(time.time() - t0, 3)
    out["synapse_path"] = list(getattr(synapse, "__path__", []))
    out["synapse_file"] = getattr(synapse, "__file__", None)
except Exception as e:
    out["import_synapse_error"] = "%s: %s" % (type(e).__name__, e)

print("SYNAPSE_PROBE_JSON_START")
print(json.dumps(out, indent=2, sort_keys=True, default=str))
print("SYNAPSE_PROBE_JSON_END")
