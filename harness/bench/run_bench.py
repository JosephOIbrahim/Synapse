#!/usr/bin/env python
"""SYNAPSE competence bench v3 -- the scorer.

    hython harness/bench/run_bench.py                 full bench
    hython harness/bench/run_bench.py --only expression
    hython harness/bench/run_bench.py --baseline      record the incumbent

NOT EDITABLE BY THE LOOP. Editing the scorer to raise the score is CRUCIBLE
weakening a hostile test, one level up. If a task is wrong, say so in the
ledger and stop.

WHY PERTURBATION. Structure checks ask "did the right nodes appear, wired the
right way". A static graph satisfies that -- and a static graph is exactly the
failure being hunted. So after the structure check we MOVE an upstream
parameter, cook, and require downstream to respond. A literal-wired network
does not move; a procedurally coupled one does. Behaviour cannot be faked by
producing plausible nodes.

Scoring, per task:
    structure fails            -> FAIL   (never got off the ground)
    structure passes, no perturb -> PASS  (structure was the whole test)
    structure + perturb pass   -> PASS
    structure passes, perturb no-op -> FAIL, reason 'not procedural'
    anything raises            -> INCONCLUSIVE, excluded from the denominator

UNMEASURABLE IS NOT ZERO. An inconclusive leaves the denominator entirely. A
zero would let an infrastructure failure look like incompetence and send the
loop optimising the wrong thing (face_token.py rule, applied to evaluation).
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BENCH = os.path.join(ROOT, "harness", "bench")
MANIFEST = os.path.join(BENCH, "manifest.json")

PASS, FAIL, INC = "pass", "fail", "inconclusive"


def _reset():
    import hou
    hou.hipFile.clear(suppress_save_prompt=True)


def _run_prompt(prompt, timeout):
    """Same entry point an artist hits -- not a raw tool call.

    The bench measures the whole stack (routing, recipes, corpus, model),
    because that is what competence means to the person in the chair.
    """
    from synapse.panel.claude_worker import run_turn_blocking
    return run_turn_blocking(prompt, timeout=timeout)


def _check_structure(lines):
    import hou
    ns = {"hou": hou}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        head = line.split("(")[0]
        if "=" in head and "==" not in head and "!=" not in head \
                and not line.startswith(("assert", "not ")):
            exec(line, ns)              # binding line
            continue
        if not bool(eval(line, ns)):
            return FAIL, "structure: %s" % line[:80]
    return PASS, ""


def _find(kind):
    import hou
    for n in hou.node("/obj").allSubChildren():
        if kind in n.type().name():
            return n
    return None


def _display():
    import hou
    for n in hou.node("/obj").allSubChildren():
        if n.isDisplayFlagSet():
            return n
    return None


def _observe(spec):
    """Read the downstream quantity a perturbation should move."""
    import hou
    if spec.get("observe_display") or spec.get("observe_metric"):
        n = _display()
        if n is None:
            raise RuntimeError("no display node to observe")
        g = n.geometry()
        m = spec.get("observe_metric", "point_count")
        if m == "point_count":
            return len(g.points())
        if m == "bbox":
            b = g.boundingBox()
            return tuple(round(v, 4) for v in
                         (b.minvec() + b.maxvec()))
        raise RuntimeError("unknown metric %s" % m)
    n = _find(spec["observe_type"])
    if n is None:
        raise RuntimeError("no %s to observe" % spec["observe_type"])
    p = n.parm(spec["observe_parm"])
    if p is None:
        raise RuntimeError("no parm %s" % spec["observe_parm"])
    return round(p.eval(), 6)


def _perturb(spec):
    """Move one upstream thing, cook, and require downstream to respond.

    Returns (verdict, note). A no-op downstream is a REAL FAILURE, not an
    error: the network was authored correct-once and is not coupled.
    """
    import hou
    before = _observe(spec)

    if spec.get("target_frame"):
        hou.setFrame(hou.frame() + spec["delta"])
    else:
        n = _find(spec["target_type"])
        if n is None:
            raise RuntimeError("no %s to perturb" % spec["target_type"])
        p = n.parm(spec["parm"])
        if p is None:
            raise RuntimeError("no parm %s on %s" % (spec["parm"], n.name()))
        p.set(p.eval() + spec["delta"])

    d = _display()
    if d is not None:
        d.cook(force=True)
    after = _observe(spec)

    if after == before:
        return FAIL, ("NOT PROCEDURAL: upstream moved, downstream did not "
                      "(%r unchanged)" % (before,))
    return PASS, "responded %r -> %r" % (before, after)


def score_task(t, budget):
    t0 = time.time()
    try:
        _reset()
        _run_prompt(t["prompt"], budget)
        verdict, note = _check_structure(t.get("structure", []))
        if verdict == PASS and t.get("perturb"):
            verdict, note = _perturb(t["perturb"])
    except Exception as e:
        verdict, note = INC, "%s: %s" % (type(e).__name__, str(e)[:90])
    return {"id": t["id"], "category": t["category"], "weight": t["weight"],
            "verdict": verdict, "note": note,
            "seconds": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    man = json.load(open(MANIFEST, encoding="utf-8"))
    tasks = [t for t in man["tasks"]
             if not a.only or t["category"] == a.only]
    budget = man.get("timeout_seconds", 90)

    results = []
    for t in tasks:
        r = score_task(t, budget)
        results.append(r)
        print("  %-8s %-11s %-12s %s"
              % (r["id"], r["category"], r["verdict"], r["note"][:70]),
              file=sys.stderr)
    return _report(results, a)


def _report(results, args):
    # Inconclusive leaves the denominator -- never counted as failure.
    scored = [r for r in results if r["verdict"] in (PASS, FAIL)]
    tw = sum(r["weight"] for r in scored)
    pw = sum(r["weight"] for r in scored if r["verdict"] == PASS)
    # Zero scored tasks is NOT zero competence -- it is no measurement at all.
    # Same rule as face_token.py and the doctor's fidelity probe: unobtainable
    # renders as UNKNOWN, never zero and never an estimate. A 0.0 here lets an
    # infrastructure failure read as total incompetence and sends the loop
    # optimising against a number that means nothing.
    competence = (pw / tw) if tw else None

    cats = {}
    for r in scored:
        c = cats.setdefault(r["category"], [0, 0])
        c[1] += r["weight"]
        if r["verdict"] == PASS:
            c[0] += r["weight"]
    per_cat = {k: round(v[0] / v[1], 4) for k, v in sorted(cats.items())}
    n_inc = sum(1 for r in results if r["verdict"] == INC)
    n_static = sum(1 for r in results if "NOT PROCEDURAL" in r["note"])

    out = {"competence": round(competence, 4) if competence is not None
           else "unknown", "categories": per_cat,
           "scored": len(scored), "inconclusive": n_inc,
           "not_procedural": n_static, "results": results}

    if args.json:
        print(json.dumps(out, indent=1))
    else:
        print("")
        if competence is None:
            print("competence: UNKNOWN   (0 scored, %d inconclusive)" % n_inc)
            print("  Nothing could be measured. This is NOT a score of zero.")
            print("  The loop must not run against this number -- fix the")
            print("  harness first, then re-baseline.")
        else:
            print("competence: %.4f   (%d scored, %d inconclusive)"
                  % (competence, len(scored), n_inc))
        for k, v in per_cat.items():
            print("  %-12s %.4f" % (k, v))
        if n_static:
            print("")
            print("  %d network(s) built but NOT PROCEDURAL -- upstream moved,"
                  " downstream did not." % n_static)
            print("  That is the T4 ceiling. No prompt or corpus change fixes"
                  " it; the expression tool has to exist.")
        if n_inc:
            print("")
            print("  %d task(s) could not be measured and were EXCLUDED, not"
                  " failed." % n_inc)
            print("  Fix the harness before trusting this number.")

    if args.baseline:
        if competence is None:
            # An unknown incumbent is worse than no incumbent: every later run
            # would compare against a number that was never measured.
            print("\nrefusing to record an incumbent: nothing was measured.")
            return 1
        with open(os.path.join(BENCH, "incumbent.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"competence": out["competence"],
                       "categories": per_cat,
                       "at": time.strftime("%Y-%m-%d %H:%M")}, f, indent=1)
        print("\nincumbent recorded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
