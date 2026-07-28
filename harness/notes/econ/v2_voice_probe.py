"""V2 · the voice contract's FALSE-NEGATIVE surface, measured rather than asserted.

The ten rules meet the brief's enumerated list — one sentence, outcome first,
names the change, no preamble, no hedging, no restating the request, a ceiling.
They are lexical, and lexical rules catch lexical violations. This producer
measures what gets through anyway.

    python harness/notes/econ/v2_voice_probe.py
    -> harness/notes/econ/V2_voice_probe.json

WHY THIS EXISTS RATHER THAN MORE RULES
--------------------------------------
Adding rules tuned against verdicts I wrote myself would be over-fitting to a
sample of one author, and the leg already declares that its tier-characteristic
prose is a FIXTURE, NOT A SAMPLE. So the holes are measured, named, and handed
up as a ruling item with a reproduction each — not closed by guesswork that would
then be cited as coverage.

The corpus is committed so the next pass has a regression target: a rule added
later must move this number, and moving it is how anyone will know it worked.

FAILS WHEN: a verdict labelled `good` is rejected (a false positive — the worse
error, because it teaches a model to write worse), or the false-negative rate
moves without anyone noticing.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "V2_voice_probe.json")

# (text, why it is bad). Register failures that the ten lexical rules do not name.
BAD = [
    ("Dark_Glass was assigned to the shader by the agent after a full review of "
     "the scene IOR values", "agent-centric, passive, padded"),
    ("The Dark_Glass material has now been successfully applied across the "
     "entire stage as requested", "'successfully', 'as requested' — status theatre"),
    ("Dark_Glass, which is a glass material, was put on the shader and the "
     "render was also updated", "two clauses in one sentence, apposition padding"),
    ("Everything went fine with Dark_Glass", "vacuous — names the change, says nothing"),
    ("Dark_Glass", "a bare noun is not a verdict"),
    ("dark_glass", "a bare lowercase token is not a verdict"),
    ("The operation on /stage/matlib completed", "reports that something ran, not what changed"),
    ("Work on Dark_Glass is now complete", "completion status standing in for an outcome"),
    ("All good on /stage/matlib", "vacuous"),
    ("The Dark_Glass task finished without any issues at all", "padded non-statement"),
]

# (text, why it is good). Realistic Houdini/VFX register with numbers, paths,
# units and material names — the surface a false positive would hit hardest.
GOOD = [
    ("Dark_Glass drives the shader at 1.52 IOR, matched to the dome.", "specific"),
    ("matlib now carries Dark_Glass, replacing Diamond.", "leaf name, outcome first"),
    ("Karma XPU renders /stage/matlib at 1920x1080, 128 samples.", "numbers and a path"),
    ("Dark_Glass reads 0.01 roughness on the key light at 6500K.", "decimals and units"),
    ("The 25mm camera now frames /stage/matlib for the lookdev pass.", "mm unit"),
    ("Dark_Glass replaced Diamond on the shader; the dome exposure held at 0.25.",
     "semicolon is one sentence"),
    ("/stage/matlib lost its Diamond binding and picked up Dark_Glass.", "path leads"),
    ("Dark_Glass sits on the shader, e.g. the dome and the key.", "abbreviation"),
]


def main():
    sys.path.insert(0, os.path.join(REPO, "python"))
    from synapse.panel import voice_contract as vc
    from synapse.panel.verdict import By, Decision, Verdict, Via

    verdict = Verdict(
        by=By(model="claude-sonnet-4-6", tier="workhorse"),
        decision=Decision(chose="Dark_Glass", over="Diamond",
                          because="closer to scene IOR"),
        via=Via(node_path="/stage/matlib", mechanism="synapse_solaris_build_graph"),
        paths=("/stage/matlib",),
    )
    request = "make the glass darker and swap the material"

    false_negatives, caught, false_positives, ok = [], [], [], []
    for text, why in BAD:
        result = vc.validate(text, verdict, request)
        row = {"text": text, "why_bad": why, "rules_fired": list(result.rules_broken())}
        (caught if not result.ok else false_negatives).append(row)
    for text, why in GOOD:
        result = vc.validate(text, verdict, request)
        row = {"text": text, "why_good": why, "rules_fired": list(result.rules_broken())}
        (false_positives if not result.ok else ok).append(row)

    report = {
        "schema": "v2_voice_probe/v1",
        "producer": "harness/notes/econ/v2_voice_probe.py",
        "rules_under_test": list(vc.RULE_IDS),
        "bad_corpus": len(BAD),
        "good_corpus": len(GOOD),
        "caught": len(caught),
        "false_negatives": len(false_negatives),
        "false_negative_rate": round(len(false_negatives) / len(BAD), 3),
        "false_positives": len(false_positives),
        "false_positive_rate": round(len(false_positives) / len(GOOD), 3),
        "reading": (
            "A false POSITIVE is the worse error — it rejects good output and "
            "teaches the model to write worse, and it burns a re-ask. A false "
            "NEGATIVE lets mediocre register through, which the templated "
            "fallback never sees because the sentence passed."
        ),
        "shape_of_the_gap": (
            "The rules are LEXICAL. They catch banned words, sentence breaks, "
            "length and markup. They do not catch a sentence that is grammatical, "
            "specific-looking and empty — 'Everything went fine with Dark_Glass' "
            "satisfies names_change because the token is present, not because the "
            "sentence is about it."
        ),
        "detail": {
            "false_negatives": false_negatives,
            "false_positives": false_positives,
            "caught": caught,
        },
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print("bad corpus  : %d, caught %d, MISSED %d  (fn rate %.0f%%)"
          % (len(BAD), len(caught), len(false_negatives),
             100 * report["false_negative_rate"]))
    print("good corpus : %d, passed %d, WRONGLY REJECTED %d  (fp rate %.0f%%)"
          % (len(GOOD), len(ok), len(false_positives),
             100 * report["false_positive_rate"]))
    for row in false_negatives:
        print("  MISSED  %-58s (%s)" % (row["text"][:58], row["why_bad"]))
    for row in false_positives:
        print("  WRONG   %-58s fired %s" % (row["text"][:58], row["rules_fired"]))
    print("->", OUT)
    # A false POSITIVE is a defect in the shipped rules and fails this producer.
    # A false NEGATIVE is the measured gap this producer exists to report, and is
    # escalated (V2-F9) rather than silently patched.
    return 1 if false_positives else 0


if __name__ == "__main__":
    raise SystemExit(main())
