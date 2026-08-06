"""M5b probe 1 -- what does a $HIP-derived path LOOK LIKE in the composed USD?

Not a re-derivation of M5-F1: that $HIP leaks into the baseline is settled
(receipt M5.json, finding M5-F1, resume_token says do not re-derive it). This
probe answers the different question R-M5-1 actually needs answered before the
c3 rule can be written to evidence rather than to a guess:

    * is the authored text the LITERAL "$HIP/..." or the EXPANDED absolute path?
    * which line(s) carry it, and what is the surrounding USD syntax?
    * what do $HIP / $HIPNAME / $JOB / $TEMP expand to in this process, and
      which of those expansions actually appear in the composed text?

The answer decides the rule's shape. A literal "$HIP/..." needs no rule at all
(it would already hash identically everywhere). An EXPANDED path means the
canonicalizer has to recognise a machine-specific absolute prefix, which it
cannot do from the text alone -- it needs the environment to compare against.

    hython harness/notes/_m5b_envpath_probe.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import hou

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "python") not in sys.path:
    sys.path.insert(0, str(REPO / "python"))

from synapse.blocks.fixtures import box_name_for, load_fixture   # noqa: E402
from synapse.blocks.runtime import apply_fixture                 # noqa: E402

FIXTURE = "solaris.basic"
STAGE = "/stage"

VARS = ("$HIP", "$HIPNAME", "$JOB", "$TEMP", "$HFS", "$HOUDINI_TEMP_DIR")


def main() -> int:
    out = {"build": hou.applicationVersionString(), "cwd": str(Path.cwd())}

    # What does each variable expand to in THIS process?
    expansions = {}
    for v in VARS:
        try:
            expansions[v] = hou.text.expandString(v)
        except Exception as e:                       # noqa: BLE001
            expansions[v] = "<ERR %s>" % type(e).__name__
    out["expansions"] = expansions

    fx = load_fixture(FIXTURE)
    box = box_name_for(fx, FIXTURE)
    out["box"] = box

    stage = hou.node(STAGE)
    for child in list(stage.children()):
        child.destroy()
    for b in list(stage.networkBoxes()):
        b.destroy()

    r = apply_fixture(FIXTURE, STAGE)
    out["apply_status"] = r["status"]
    out["apply_applied"] = r["applied"]

    # The AUTHORED parm value on the render settings node, before composition.
    rs = stage.node("render_settings")
    authored = {}
    for pname in ("picture", "outputimage", "primpath", "camera"):
        p = rs.parm(pname)
        if p is None:
            authored[pname] = "<no such parm>"
            continue
        try:
            authored[pname] = {"unexpanded": p.unexpandedString(),
                               "eval": str(p.eval())}
        except Exception as e:                       # noqa: BLE001
            authored[pname] = "<ERR %s: %s>" % (type(e).__name__, e)
    out["render_settings_authored"] = authored

    tail = stage.node(fx["display"])
    text = tail.stage().Flatten().ExportToString()
    lines = text.splitlines()
    out["composed_line_count"] = len(lines)

    # Which lines carry a literal "$" variable reference?
    literal_var_lines = [(i, ln) for i, ln in enumerate(lines) if "$" in ln]
    out["lines_with_literal_dollar"] = literal_var_lines[:40]

    # Which lines carry an EXPANDED value of one of the variables?
    hits = {}
    for v, val in expansions.items():
        if not val or val.startswith("<ERR"):
            continue
        norm = val.replace("\\", "/")
        matched = []
        for i, ln in enumerate(lines):
            probe = ln.replace("\\", "/")
            if norm and norm in probe:
                matched.append((i, ln))
        if matched:
            hits[v] = {"expansion": val, "count": len(matched),
                       "lines": matched[:20]}
    out["lines_with_expanded_value"] = hits

    print(json.dumps(out, indent=2, sort_keys=True, default=str), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
