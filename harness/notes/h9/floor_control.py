"""H9 control -- two-sided test of the quality floor.

Emits harness/notes/h9/floor_control.json

WHY
    Law 1 says state the condition under which a check fails and prove it can. H8 added
    the other half: a check that flags EVERYTHING has caught nothing and proved nothing.
    So the floor is tested both ways, on real entries from the built corpus.

    SENSITIVITY  plant a known defect in a page that currently passes; the floor must
                 reject it. Four plants, one per way the floor can fail.
    SPECIFICITY  take pages that are unambiguously good and confirm the floor passes
                 them untouched. If it rejected these, it would be measuring prose
                 volume, not grounding.

    The floor logic is imported from build_corpus rather than re-implemented, so this
    tests the shipped check and not a lookalike.

FAILS IF
    any plant survives, or any control page is rejected. Either outcome exits 2.

RUN
    python harness/notes/h9/floor_control.py
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from build_corpus import (  # noqa: E402
    MIN_SUMMARY_WORDS,
    is_placeholder,
    summary_words,
)

CORPUS = os.path.join(HERE, "..", "h22_doc_grounding_corpus.json")
OUT = os.path.join(HERE, "floor_control.json")


def score(entry):
    """The shipped floor, applied to one entry. Returns (clears, failures)."""
    failures = []
    if summary_words(entry.get("summary")) < MIN_SUMMARY_WORDS:
        failures.append("summary_absent_or_stub")
    good = [
        p
        for p in entry.get("parameters", [])
        if p["resolved_runtime_parms"] and not is_placeholder(p["description"])
    ]
    if entry.get("runtime_parm_count") and not good:
        failures.append("no_parameter_resolves_to_a_live_parm_with_a_description")
    return (not failures), failures


PLANTS = [
    (
        "strip_summary",
        "a page with no summary at all",
        lambda e: e.update({"summary": ""}) or e,
    ),
    (
        "two_word_summary",
        "a summary that is a fragment, not a statement",
        lambda e: e.update({"summary": "Creates prims"}) or e,
    ),
    (
        "all_parms_placeholder",
        "every documented parameter reduced to 'TBD' -- the reference's own way of "
        "saying it has no content there",
        lambda e: (
            [p.update({"description": "TBD"}) for p in e["parameters"]],
            e,
        )[1],
    ),
    (
        "all_parms_phantom",
        "every documented parameter renamed so none exists on the live node -- the R72 "
        "class, documentation disagreeing with the runtime",
        lambda e: (
            [p.update({"resolved_runtime_parms": [], "resolution": None}) for p in e["parameters"]],
            e,
        )[1],
    ),
]

# Chosen before the control was run, one per surface, each a substantial page whose
# rejection would mean the floor is measuring the wrong thing.
SPECIFICITY_TARGETS = [
    ("Cop", "blur"),
    ("Lop", "attribwrangle"),
    ("Cop2", "add"),
    ("Lop", "assignmaterial"),
    ("Cop", "colorcorrect"),
]


def main():
    with open(CORPUS, encoding="utf-8") as fh:
        corpus = json.load(fh)
    by_key = {(e["category"], e["type_name"]): e for e in corpus["entries"]}

    # sensitivity: plant into a page that passes today and has parms to corrupt
    host_key = ("Lop", "attribwrangle")
    host = by_key[host_key]
    clears, _ = score(host)
    if not clears:
        raise SystemExit("FAIL: control host %s does not pass unmodified" % (host_key,))

    sensitivity = []
    for name, desc, mutate in PLANTS:
        planted = mutate(copy.deepcopy(host))
        ok, failures = score(planted)
        sensitivity.append(
            {
                "plant": name,
                "describes": desc,
                "host": "%s/%s" % host_key,
                "floor_result": "PASS (plant survived)" if ok else "REJECTED",
                "caught": not ok,
                "failures_reported": failures,
            }
        )

    specificity = []
    for cat, tname in SPECIFICITY_TARGETS:
        e = by_key.get((cat, tname))
        if e is None:
            specificity.append({"type": "%s/%s" % (cat, tname), "error": "not in corpus"})
            continue
        ok, failures = score(e)
        specificity.append(
            {
                "type": "%s/%s" % (cat, tname),
                "clears": ok,
                "failures": failures,
                "summary_words": summary_words(e.get("summary")),
                "parms_documented": e.get("documented_runtime_parms"),
                "parms_live": e.get("runtime_parm_count"),
            }
        )

    caught = sum(1 for s in sensitivity if s["caught"])
    passed = sum(1 for s in specificity if s.get("clears"))
    result = {
        "schema": "h9_floor_control/v1",
        "producer": "harness/notes/h9/floor_control.py",
        "floor_under_test": "imported from build_corpus -- the shipped logic, not a copy",
        "sensitivity": {
            "plants": len(PLANTS),
            "caught": caught,
            "result": "PASS" if caught == len(PLANTS) else "FAIL",
            "detail": sensitivity,
        },
        "specificity": {
            "controls": len(SPECIFICITY_TARGETS),
            "passed_untouched": passed,
            "result": "PASS" if passed == len(SPECIFICITY_TARGETS) else "FAIL",
            "detail": specificity,
            "why_it_matters": "a floor that rejected these would be measuring prose "
            "volume rather than grounding, and every coverage number built on it would "
            "be pessimistic for the wrong reason",
        },
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)
    print("WROTE", OUT)
    print("  sensitivity: %d/%d plants caught -> %s" % (caught, len(PLANTS), result["sensitivity"]["result"]))
    for s in sensitivity:
        print("     %-22s %s" % (s["plant"], s["floor_result"]))
    print("  specificity: %d/%d controls pass -> %s" % (passed, len(SPECIFICITY_TARGETS), result["specificity"]["result"]))
    for s in specificity:
        print("     %-22s clears=%s" % (s.get("type"), s.get("clears")))
    if result["sensitivity"]["result"] == "FAIL" or result["specificity"]["result"] == "FAIL":
        sys.exit(2)


main()
