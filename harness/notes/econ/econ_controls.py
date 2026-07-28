#!/usr/bin/env python3
"""E1 - mutation controls for every E1 reader (R60, R133, Law 1).

READ-ONLY with respect to the repo. Writes one artifact under harness/notes/econ/
and scratch copies of the producers' artifacts into a temp dir that is deleted.

WHY THIS FILE EXISTS. I1 found a control that pinned nothing, and Law 1 was paid
for by four checks that reported healthy while proving nothing. A number is only
worth quoting if the instrument that produced it demonstrably MOVES when reality
moves. So every control here does two things, and a control that does only the
first is a decoration:

  1. states the condition under which the reader would be wrong
  2. CREATES that condition and shows the reader's verdict flips

Method: each control runs the REAL producer end to end - not a re-implementation -
against a deliberately mutated registry, by patching synapse.mcp.tools.get_tools
and the producer's output path. Testing a re-implementation would only prove that
two copies of my own assumption agree.

Emits: harness/notes/econ/E1_controls.json
Exit code is non-zero if ANY control fails to flip. A control that cannot fail is
reported as a FAILURE of the control, not a pass of the reader.

Usage: python harness/notes/econ/econ_controls.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT / "python"))

OUT_FP = HERE / "E1_controls.json"


def _load(mod_name: str):
    spec = importlib.util.spec_from_file_location(mod_name, HERE / f"{mod_name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


census = _load("econ_surface_census")
dupes = _load("econ_schema_dupes")
floor = _load("econ_floor")

import synapse.mcp.tools as live_tools  # noqa: E402


def _run(module, tools, tmpdir: Path, name: str, **patches):
    """Run a producer against `tools`, returning its artifact dict + exit code."""
    real_get = live_tools.get_tools
    real_out = module.OUT_FP
    saved = {k: getattr(module, k) for k in patches}
    try:
        live_tools.get_tools = lambda: tools
        module.OUT_FP = tmpdir / f"{name}.json"
        for k, v in patches.items():
            setattr(module, k, v)
        rc = module.main()
        return json.loads(module.OUT_FP.read_text(encoding="utf-8")), rc
    finally:
        live_tools.get_tools = real_get
        module.OUT_FP = real_out
        for k, v in saved.items():
            setattr(module, k, v)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="econ_controls_"))
    base = list(live_tools.get_tools())
    controls = []

    def record(cid, reader, claim, fails_when, baseline, mutated, flipped, detail=""):
        controls.append({
            "id": cid, "reader": reader, "claim": claim,
            "fails_when": fails_when,
            "baseline": baseline, "under_mutation": mutated,
            "verdict_flipped": bool(flipped),
            "control_status": "PASS" if flipped else "FAIL - control pinned nothing",
            "detail": detail,
        })

    # ---- C1: census G1 historical calibration can fail --------------------
    hist = census._historical_tools(census.T0_COMMIT)
    a0, rc0 = _run(census, base, tmp, "c1_base")
    g1_0 = a0["stats"]["calibration"]["G1_historical"]

    mutated_hist = copy.deepcopy(hist)
    mutated_hist[0]["description"] = mutated_hist[0]["description"] + " extra words here"
    a1, rc1 = _run(census, base, tmp, "c1_mut",
                   _historical_tools=lambda _c: mutated_hist)
    g1_1 = a1["stats"]["calibration"]["G1_historical"]
    record(
        "C1", "econ_surface_census G1",
        "the reader reproduces T.0's 17,310 from T.0's own registry",
        "it would be wrong if its serialisation or tokenizer differed from T.0's; "
        "mutation adds 3 words to one historical description",
        {"tokens": g1_0["measured_tokens"], "tokens_match": g1_0["tokens_match"], "exit": rc0},
        {"tokens": g1_1["measured_tokens"], "tokens_match": g1_1["tokens_match"], "exit": rc1},
        g1_0["tokens_match"] and not g1_1["tokens_match"] and rc0 == 0 and rc1 != 0,
        "a calibration gate that stays green under a mutated input is not a gate",
    )

    # ---- C2: census fragment decomposition detects an unknown key ---------
    five_key = copy.deepcopy(base)
    five_key[0]["outputSchema"] = {"type": "object"}
    a2, rc2 = _run(census, five_key, tmp, "c2_mut")
    record(
        "C2", "econ_surface_census G2",
        "the four decomposed fragments rebuild each wire object byte-for-byte",
        "it would be wrong if a tool carried a fifth key whose mass vanished into "
        "the structural residual; mutation adds outputSchema to one tool",
        {"all_rebuild": a0["stats"]["aggregate"]["all_four_key_shape_ok"]},
        {"all_rebuild": a2["stats"]["aggregate"]["all_four_key_shape_ok"]},
        a0["stats"]["aggregate"]["all_four_key_shape_ok"]
        and not a2["stats"]["aggregate"]["all_four_key_shape_ok"],
    )

    # ---- C3: census component totals track an injected description -------
    inject = copy.deepcopy(base)
    probe_desc = ("This synthetic probe description exists only to verify that the "
                  "description component total moves by exactly the tokens added.")
    inject.append({
        "name": "econ_control_probe",
        "description": probe_desc,
        "inputSchema": {"type": "object", "properties": {}, "required": []},
        "annotations": {"title": "Econ Control Probe", "readOnlyHint": True,
                        "destructiveHint": False, "idempotentHint": True,
                        "openWorldHint": False},
    })
    a3, rc3 = _run(census, inject, tmp, "c3_mut")
    d0 = a0["stats"]["aggregate"]["component_totals_wire"]["description_tokens"]
    d3 = a3["stats"]["aggregate"]["component_totals_wire"]["description_tokens"]
    expected = census._tokenizer()[1](census._frag("description", probe_desc))
    record(
        "C3", "econ_surface_census component totals",
        "the description component total is the sum of real per-tool description fragments",
        "it would be wrong if it double-counted or dropped tools; mutation appends "
        "one tool with a description of independently-computed token cost",
        {"description_tokens": d0, "n_tools": a0["stats"]["aggregate"]["n_tools"]},
        {"description_tokens": d3, "n_tools": a3["stats"]["aggregate"]["n_tools"],
         "delta": d3 - d0, "predicted_delta": expected},
        (d3 - d0) == expected and a3["stats"]["aggregate"]["n_tools"] == len(base) + 1,
        "exact-delta control: an approximate match would indicate mis-attribution",
    )

    # ---- C4a: dupes repeat counting responds to an added duplicate -------
    b4, _ = _run(dupes, base, tmp, "c4_base")
    top0 = b4["stats"]["duplication"]["property_fragments"]["top"][0]
    donor_frag = top0["fragment"]
    donor_tool = next(t for t in base if t["name"] == top0["sample_tools"][0])
    donor_prop = top0["property_names"][0]
    donor_body = copy.deepcopy(donor_tool["inputSchema"]["properties"][donor_prop])

    dup = copy.deepcopy(base)
    host = next(t for t in dup if donor_prop not in (t["inputSchema"].get("properties") or {}))
    host["inputSchema"].setdefault("properties", {})[donor_prop] = donor_body
    m4, _ = _run(dupes, dup, tmp, "c4_mut")
    top1 = next((f for f in m4["stats"]["duplication"]["property_fragments"]["top"]
                 if f["fragment"] == donor_frag), None)
    flipped4 = (top1 is not None
                and top1["repeat_count"] == top0["repeat_count"] + 1
                and top1["ceiling_saving_tokens"]
                == top0["ceiling_saving_tokens"] + top0["fragment_tokens"])
    record(
        "C4a", "econ_schema_dupes repeat counting",
        "repeat_count and ceiling_saving reflect real repetition",
        "it would be wrong if it counted per-tool rather than per-instance; mutation "
        f"copies the property '{donor_prop}' into one additional tool",
        {"repeat_count": top0["repeat_count"],
         "ceiling": top0["ceiling_saving_tokens"], "fragment_tokens": top0["fragment_tokens"]},
        {"repeat_count": top1["repeat_count"] if top1 else None,
         "ceiling": top1["ceiling_saving_tokens"] if top1 else None},
        flipped4,
        "predicted ceiling delta = exactly one fragment's tokens",
    )

    # ---- C4b: dupes reports ZERO on an all-unique surface -----------------
    # The uniquifier must recurse. A first attempt renamed only top-level
    # properties and the control did NOT flip - nested bodies under
    # properties/items stayed identical across tools and the reader correctly
    # kept reporting duplication. The control was wrong, not the reader; that
    # is exactly the failure Law 1 asks you to find before quoting a number.
    _ctr = iter(range(10 ** 6))

    def _uniquify(node):
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                if k == "properties" and isinstance(v, dict):
                    out[k] = {f"{pk}_u{next(_ctr)}": _uniquify(pv) for pk, pv in v.items()}
                elif k == "description" and isinstance(v, str):
                    out[k] = f"{v} :: unique-{next(_ctr)}"
                elif k == "required" and isinstance(v, list):
                    out[k] = []          # old names no longer exist
                elif k == "enum" and isinstance(v, list):
                    out[k] = list(v) + [f"unique_{next(_ctr)}"]
                else:
                    out[k] = _uniquify(v)
            return out
        if isinstance(node, list):
            return [_uniquify(x) for x in node]
        return node

    uniq = []
    for t in base:
        c = copy.deepcopy(t)
        c["inputSchema"] = _uniquify(c["inputSchema"])
        uniq.append(c)
    m4b, _ = _run(dupes, uniq, tmp, "c4b_mut")
    zero = m4b["stats"]["duplication"]["property_fragments"]["ceiling_saving_tokens"]
    record(
        "C4b", "econ_schema_dupes negative control",
        "a surface with no repeated fragments reports no duplication saving",
        "it would be wrong if it reported savings on unique input - the classic "
        "check-that-cannot-fail; mutation makes every property name and description unique",
        {"ceiling_saving": b4["stats"]["duplication"]["property_fragments"]["ceiling_saving_tokens"]},
        {"ceiling_saving": zero},
        b4["stats"]["duplication"]["property_fragments"]["ceiling_saving_tokens"] > 0 and zero == 0,
        "paired negative control - the thing probe_phase3_layout was missing",
    )

    # ---- C5: floor verdict is data-driven, not hardcoded ------------------
    f0a, _ = _run(floor, base, tmp, "c5_base")
    v0 = f0a["stats"]["verdict"]
    fake_ceiling = tmp / "fake_ceiling.json"
    fake_ceiling.write_text(json.dumps({"max_preload_tokens": 99999}), encoding="utf-8")
    f1a, _ = _run(floor, base, tmp, "c5_mut", CEILING_FP=fake_ceiling)
    v1 = f1a["stats"]["verdict"]
    record(
        "C5", "econ_floor verdict",
        "'2,000 is not reachable' is computed against the committed ceiling file",
        "it would be wrong if the verdict were hardcoded; mutation raises the "
        "ceiling file to 99,999 and the verdict must flip to reachable",
        {"ceiling": v0["ceiling"], "reachable": v0["reachable_as_flat_catalog"]},
        {"ceiling": v1["ceiling"], "reachable": v1["reachable_as_flat_catalog"]},
        (not v0["reachable_as_flat_catalog"]) and v1["reachable_as_flat_catalog"],
    )

    # ---- C6: floor responds to tool COUNT, which is the whole claim -------
    half, _ = _run(floor, base[:60], tmp, "c6_mut")
    hv = half["stats"]["floors"]["F4_names_only_legal"]["tokens"]
    fv = f0a["stats"]["floors"]["F4_names_only_legal"]["tokens"]
    record(
        "C6", "econ_floor scaling",
        "the catalog floor scales with tool COUNT, which is why the ceiling is a "
        "count statement rather than a size statement",
        "it would be wrong if the floor were insensitive to tool count; mutation "
        "halves the registry to 60 tools",
        {"n_tools": 120, "F4_tokens": fv, "fits_2000": fv <= 2000},
        {"n_tools": 60, "F4_tokens": hv, "fits_2000": hv <= 2000},
        fv > 2000 and hv < fv and hv <= 2000,
        "halving the count moves the floor from over-ceiling to under-ceiling",
    )

    # ---- C7: monotonicity of the floor ladder ----------------------------
    fl = f0a["stats"]["floors"]
    order = ["F0_as_shipped", "F1_no_annotations", "F2_no_property_descriptions",
             "F3_empty_schemas", "F4_names_only_legal", "F5_bare_name_array"]
    toks = [fl[k]["tokens"] for k in order]
    mono = all(a > b for a, b in zip(toks, toks[1:]))
    record(
        "C7", "econ_floor ladder",
        "each floor is strictly cheaper than the one above it",
        "it would be wrong if a 'reduction' step increased cost, which would mean "
        "the payload construction is not doing what its label says",
        {"ladder": dict(zip(order, toks))},
        {"strictly_decreasing": mono},
        mono,
        "structural self-check; no external mutation needed",
    )

    passed = sum(1 for c in controls if c["control_status"] == "PASS")
    stats = {
        "n_controls": len(controls),
        "passed": passed,
        "failed": len(controls) - passed,
        "all_readers_calibrated": passed == len(controls),
        "readers_covered": sorted({c["reader"].split()[0] for c in controls}),
        "method": "each control runs the REAL producer end to end against a mutated "
                  "registry (synapse.mcp.tools.get_tools patched), never a "
                  "re-implementation",
        "controls": controls,
    }
    digest = hashlib.blake2b(
        json.dumps(stats, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"),
        digest_size=16).hexdigest()
    out = {"schema": "e1_controls/v1",
           "producer": "harness/notes/econ/econ_controls.py",
           "stats": stats, "blake2b": digest}
    OUT_FP.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str),
                      encoding="utf-8")

    print(f"[econ_controls] wrote {OUT_FP}")
    for c in controls:
        print(f"  {c['control_status']:<28} {c['id']:<5} {c['reader']}")
    print(f"  {passed}/{len(controls)} controls flipped under mutation")

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if passed == len(controls) else 3


if __name__ == "__main__":
    raise SystemExit(main())
