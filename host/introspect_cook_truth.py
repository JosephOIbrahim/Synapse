"""D.2 (Mile 2) — cook-truth perturbation catalog probe. hython-only, ZERO synapse imports.

Spec: harness/notes/spec-D-diagnostic-truth.md §2. For each context (sop, lop, cop, dop —
TOP excluded: shipped surface; MAT folded under LOP) build a tiny throwaway graph and run
PERTURBATION TRIALS: set one parm / rewire one input / toggle a time-dependent expression,
recording which nodes observably report needs-cook, the cookCount deltas after a forced
recook, and time-dependence propagation. expected_dirty is the probe's static PREDICTION
(perturbed node + transitive downstream closure); observed_dirty is what hou actually
reports — divergence between them IS the diagnostic truth this catalog exists to capture.

Discipline (introspect_context_capability.py verbatim): every trial is undo-wrapped AND its
container is destroyed + verified absent afterward (residue-free, twice over); the artifact
is written .tmp + os.replace, rc 0 iff written; the FILE is the verdict, never stdout.
API usage is confined to the D.1-CONFIRMED set (hou.OpNode.{cook,cookCount,needsToCook,
isTimeDependent}, hou.Parm.evalAsString — hou.Node-spelled cook APIs are quarantined
phantoms on 21.x, see verified_cook_api_21.0.671.json).

Artifact contract (must match check_cook_truth_fresh byte-for-byte):
  {schema: "cook_truth/v1", houdini_version, blake2b, trials: [...]}
  blake2b over json.dumps(trials, sort_keys=True, ensure_ascii=False), digest_size=16.
Trial: {context, graph_fingerprint, perturbation, expected_dirty, observed_dirty,
        cookcount_deltas, time_dependent}
Node paths in trials are container-RELATIVE (deterministic across runs and sessions).

CLI: no args -> full catalog to harness/notes/cook_truth_<major>.json;
     --context <name> [--out <path>] -> only that context's trials (the golden re-run).
"""
import hashlib
import json
import os
import sys

import hou  # hython interpreter

CONTEXTS = ("sop", "lop", "cop", "dop")


# ---------------------------------------------------------------------------
# graph builders — one frozen tiny graph per context (C.0 golden species)
# ---------------------------------------------------------------------------

def _build_sop():
    geo = hou.node("/obj").createNode("geo", "d_cook_sop")
    box = geo.createNode("box", "box1")
    sc = geo.createNode("scatter", "scatter1")
    out = geo.createNode("null", "OUT")
    sc.setInput(0, box)
    out.setInput(0, sc)
    return geo, {"box1": box, "scatter1": sc, "OUT": out}, out, "sop:box>scatter>OUT"


def _build_lop():
    net = hou.node("/obj").createNode("lopnet", "d_cook_lop")
    sph = net.createNode("sphere", "sphere1")
    ml = net.createNode("materiallibrary", "matlib1")
    out = net.createNode("null", "OUT")
    ml.setInput(0, sph)
    out.setInput(0, ml)
    return net, {"sphere1": sph, "matlib1": ml, "OUT": out}, out, "lop:sphere>materiallibrary>OUT"


def _build_cop():
    net = hou.node("/obj").createNode("copnet", "d_cook_cop")
    src = net.createNode("file", "file1")
    blur = net.createNode("blur", "blur1")
    out = net.createNode("null", "OUT")
    blur.setInput(0, src)
    out.setInput(0, blur)
    return net, {"file1": src, "blur1": blur, "OUT": out}, out, "cop:file>blur>OUT"


def _build_dop():
    net = hou.node("/obj").createNode("dopnet", "d_cook_dop")
    eo = net.createNode("emptyobject", "eo1")
    return net, {"eo1": eo}, eo, "dop:emptyobject"


BUILDERS = {"sop": _build_sop, "lop": _build_lop, "cop": _build_cop, "dop": _build_dop}

# Frozen perturbations per context: (kind, node, detail). Deterministic values only.
# parm names verified live on 21.0.671 (recon 2026-07-07); a missing parm records a gap.
PERTURBATIONS = {
    "sop": [("parm", "box1", ("scale", 2.0)),
            ("rewire", "OUT", ("box1", 0)),
            ("time", "box1", ("tx", "$F"))],
    "lop": [("parm", "sphere1", ("radius", 3.0)),
            ("rewire", "OUT", ("sphere1", 0)),
            ("time", "sphere1", ("radius", "$F"))],
    "cop": [("parm", "blur1", ("size", 4.0)),
            ("rewire", "OUT", ("file1", 0))],
    "dop": [("parm", "eo1", ("solvefirstframe", 1))],
}


# ---------------------------------------------------------------------------
# trial machinery
# ---------------------------------------------------------------------------

def _downstream_closure(name, nodes):
    """expected_dirty: the perturbed node + everything transitively downstream of it."""
    rev = {n: node for n, node in nodes.items()}
    hit, stack = set(), [name]
    while stack:
        cur = stack.pop()
        if cur in hit:
            continue
        hit.add(cur)
        for other, node in rev.items():
            if other not in hit and rev[cur] in node.inputs():
                stack.append(other)
    return sorted(hit)


def _first_float_parm(node, preferred):
    p = node.parm(preferred)
    if p is not None:
        return p
    for cand in node.parms():
        try:
            float(cand.eval())
            return cand
        except Exception:
            continue
    return None


def _run_trial(context, kind, target, detail):
    container, nodes, cook_node, fingerprint = BUILDERS[context]()
    try:
        try:
            cook_node.cook(force=True)  # clean baseline (dop/cop may refuse — flags still work)
        except hou.OperationFailed:
            pass
        base_counts = {n: node.cookCount() for n, node in nodes.items()}

        perturbation = None
        with hou.undos.group(f"cook_truth {context} {kind}"):
            if kind == "parm":
                pname, val = detail
                p = _first_float_parm(nodes[target], pname)
                if p is None:
                    return None  # gap: species lacks the parm — record nothing, never lie
                p.set(val)
                perturbation = f"parm:{target}/{p.name()}"
            elif kind == "rewire":
                src, idx = detail
                nodes[target].setInput(idx, nodes[src])
                perturbation = f"rewire:{target}<-{src}"
            elif kind == "time":
                pname, expr = detail
                p = nodes[target].parm(pname)
                if p is None:
                    return None
                p.setExpression(expr, language=hou.exprLanguage.Hscript)
                perturbation = f"time:{target}/{pname}={expr}"

            observed = sorted(n for n, node in nodes.items() if node.needsToCook())
            try:
                cook_node.cook(force=True)
            except hou.OperationFailed:
                pass
            deltas = {n: node.cookCount() - base_counts[n] for n, node in nodes.items()}
            timedep = sorted(n for n, node in nodes.items() if node.isTimeDependent())

        hou.undos.performUndo()  # revert the perturbation (spec: undo-wrapped, reverted)
        return {
            "context": context,
            "graph_fingerprint": fingerprint,
            "perturbation": perturbation,
            "expected_dirty": _downstream_closure(target, nodes),
            "observed_dirty": observed,
            "cookcount_deltas": deltas,
            "time_dependent": timedep,
        }
    finally:
        path = container.path()
        container.destroy()
        if hou.node(path) is not None:  # residue-free or the whole probe is invalid
            raise RuntimeError(f"residue after trial: {path} still exists")


def main():
    args = sys.argv[1:]
    only = args[args.index("--context") + 1] if "--context" in args else None
    out = args[args.index("--out") + 1] if "--out" in args else None
    build = hou.applicationVersionString()
    if out is None:
        out = os.path.join("harness", "notes", f"cook_truth_{build.split('.')[0]}.json")

    trials, gaps = [], []
    for context in CONTEXTS:
        if only and context != only:
            continue
        for kind, target, detail in PERTURBATIONS[context]:
            try:
                t = _run_trial(context, kind, target, detail)
            except Exception as e:
                gaps.append(f"{context}/{kind}:{target} -> {type(e).__name__}: {e}")
                continue
            if t is None:
                gaps.append(f"{context}/{kind}:{target} -> parm missing on species")
            else:
                trials.append(t)

    wanted = [only] if only else list(CONTEXTS)
    missing = [ctxname for ctxname in wanted
               if not any(t["context"] == ctxname for t in trials)]
    for g in gaps:
        print(f"probe-gap {g}")
    if missing:  # a context with ZERO trials is an incomplete catalog — no artifact, rc 1
        print(f"COOK_TRUTH_PROBE FAILED — no trials for: {', '.join(missing)}")
        return 1

    doc = {
        "schema": "cook_truth/v1",
        "houdini_version": build,
        "blake2b": hashlib.blake2b(
            json.dumps(trials, sort_keys=True, ensure_ascii=False).encode("utf-8"),
            digest_size=16).hexdigest(),
        "trials": trials,
    }
    tmp = out + ".tmp"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, out)
    print(f"COOK_TRUTH_PROBE ok build={build} trials={len(trials)} gaps={len(gaps)} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
