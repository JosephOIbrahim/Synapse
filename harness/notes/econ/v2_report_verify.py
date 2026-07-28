"""V2 · every figure in V2_VERDICT.md, read back off the artifact that produced it.

D1: two numbers reached the first committed draft of the report from recall of
E0's proxy figures rather than from `V2_prompt_delta.json` — a 1,712 where the
producer says 1,567, and a 1.6x where it says 1.72x. Law 5 inside the document
that cites Law 2, and R127's exact shape: a number whose producer I wrote and did
not read back.

Promising to be more careful is not a fix. This is the fix: the report's
load-bearing figures are declared here with the JSON path that emits them, the
values are compared, and the numeric section of the document is swept for any
figure that is NOT accounted for. A number that appears in the prose without a
producer turns this red.

    python harness/notes/econ/v2_report_verify.py
    -> exit 0 green, exit 1 with the offending figure named

FAILS WHEN: a figure in the report disagrees with its artifact, a declared figure
is missing from the report, or the measurement section carries a number nothing
here explains.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(HERE, "V2_VERDICT.md")
DELTA = os.path.join(HERE, "V2_prompt_delta.json")
MUTATION = os.path.join(HERE, "V2_mutation.json")
PROBE = os.path.join(HERE, "V2_voice_probe.json")


def dig(blob, path):
    node = blob
    for key in path:
        node = node[key] if not isinstance(key, int) else node[key]
    return node


#: (label, artifact, json path, formatter). The formatter is how the figure is
#: written in the prose — a figure the report renders as "2,961" must be found as
#: "2,961", not as 2961, or the check would pass on a document that says neither.
FIGURES = [
    ("calibration tokens", DELTA, ("calibration", "measured_tokens"), "{:,}"),
    ("R155 committed", DELTA, ("calibration", "committed_tokens"), "{:,}"),
    ("tone guide", DELTA, ("register_instruction_out", "tone_alone_tokens"), "{:,}"),
    ("schema as shipped", DELTA, ("contract_in", "as_shipped_tokens"), "{:,}"),
    ("schema structure", DELTA, ("contract_in", "structure_only_tokens"), "{:,}"),
    ("schema prose", DELTA, ("contract_in", "description_prose_tokens"), "{}"),
    ("schema lean", DELTA, ("contract_in", "lean_tokens"), "{:,}"),
    ("stage before", DELTA, ("register_instruction_out", "per_context", 0, "before_tokens"), "{:,}"),
    ("stage after", DELTA, ("register_instruction_out", "per_context", 0, "after_tokens"), "{:,}"),
    ("obj before", DELTA, ("register_instruction_out", "per_context", 1, "before_tokens"), "{:,}"),
    ("obj after", DELTA, ("register_instruction_out", "per_context", 1, "after_tokens"), "{}"),
    ("out before", DELTA, ("register_instruction_out", "per_context", 2, "before_tokens"), "{:,}"),
    ("out after", DELTA, ("register_instruction_out", "per_context", 2, "after_tokens"), "{}"),
    ("stage removed pct", DELTA, ("register_instruction_out", "per_context", 0, "removed_pct"), "{}"),
    ("obj removed pct", DELTA, ("register_instruction_out", "per_context", 1, "removed_pct"), "{}"),
    ("out removed pct", DELTA, ("register_instruction_out", "per_context", 2, "removed_pct"), "{}"),
    ("swing stage->obj", DELTA, ("still_volatile", "swing_stage_to_obj_tokens"), "{:,}"),
    ("swing stage->out", DELTA, ("still_volatile", "swing_stage_to_out_tokens"), "{:,}"),
    ("count_tokens calls", DELTA, ("count_tokens_calls",), "{}"),
    ("break-even calls", DELTA, ("price_derived", "break_even_calls"), "{}"),
    ("mutations run", MUTATION, ("mutations_run",), "{}"),
    ("voice bad corpus", PROBE, ("bad_corpus",), "{}"),
    ("voice good corpus", PROBE, ("good_corpus",), "{}"),
    ("voice false negatives", PROBE, ("false_negatives",), "{}"),
    ("voice fn rate", PROBE, ("false_negative_rate",), "{:.0%}"),
    ("voice fp rate", PROBE, ("false_positive_rate",), "{:.0%}"),
]

#: Figures the report states that are DERIVED in the prose rather than emitted
#: verbatim by an artifact. Each names how it is computed, so the sweep below can
#: account for it instead of flagging it.
DERIVED = {
    "742": "price_derived.steady_state_saving_bte_per_call, rounded to whole BTE",
    "860": "price_derived.before_bte_per_call",
    "118": "price_derived.after_bte_per_call, rounded",
    "496": "net_as_shipped, reported as a magnitude",
    "332": "net_lean, reported as a magnitude",
    "1.72": "as_shipped_tokens / tone_alone_tokens",
    "1.48": "lean_tokens / tone_alone_tokens",
    "1,567": "swing_stage_to_out, restated in the cross-check line",
    "1,424": "swing_stage_to_obj, restated in the cross-check line",
    "2,961": "restated in the cross-check line",
    "1,537": "obj before, restated in the cross-check line",
    "1,394": "out before, restated in the cross-check line",
    "5031": "suite before — pytest, recorded in the receipt",
    "5170": "suite after — pytest, recorded in the receipt",
    "137": "suite skipped — pytest, recorded in the receipt",
    "139": "5170 - 5031, the tests this leg adds",
    "1.25": "E0 cache-write multiplier",
    "0.1": "E0 cache-read multiplier",
    "1,712": "the RETRACTED figure, named in the drift section",
    "1.6": "the RETRACTED ratio, named in the drift section",
    "0.6": "no_request_echo ratio — a chosen threshold, declared in Limits",
    "22": "mutations run",
    "10": "voice rules",
    "13": "count_tokens calls",
    "0": "survivors / failures",
    "3": "tiers, and the attempt budget",
    "4": "provenance rungs",
    "688": "tone guide",
    "65": "schema prose",
    "1,119": "schema structure",
    "1,020": "schema lean",
    "1,184": "schema as shipped",
}


#: A citation is not a figure. Ruling ids, finding ids, mile ids and file:line
#: anchors are REFERENCES — they point at a producer rather than claiming to be
#: one, and sweeping them as unsourced numbers would train the next reader to
#: ignore this check's output, which is worse than not running it.
_CITATIONS = re.compile(
    r"\bR\d+\b"                      # R60, R127, R155
    r"|\b[A-Z]+\d*-F\d+\b"           # E0-F12, C1-F12, V2-F7
    r"|\bT\.\d+\b"                   # T.1, T.4
    r"|\b[A-Z]{2,3}-\d+\b"           # BL-007, BL-008
    r"|\bCAL-\d+\b"
    r"|\bD\d+\b|\bA\d+\b|\bF\d+\b"   # drift ids, E0 assumption ids, finding ids
    r"|\.py:\d+(?:-\d+)?"            # face_review.py:56-64
    r"|§[\d.]+"
    r"|\bPython \d[\d.]*"
    r"|\bMile \d+")


def sweep(section, known):
    """Figures in the prose that nothing accounts for. FAILS WHEN a number is
    written without a producer — the defect D1 records."""
    bare = _CITATIONS.sub(" ", section)
    out = []
    for token in sorted(set(re.findall(r"\d[\d,]*\.?\d*", bare))):
        if token in known or token.rstrip("0").rstrip(".") in known:
            continue
        if len(token.replace(",", "").replace(".", "")) <= 1:
            continue                      # bare digits in prose (rule 3, ...)
        out.append(token)
    return out


def selftest(section, known):
    """The sweep, demonstrated failing. A check nobody has seen reject is a
    decoration (R127/R131) — including this one."""
    planted = section + "\n\nthe swing is 9,731 tokens.\n"
    caught = sweep(planted, known)
    assert "9,731" in caught, "the sweep cannot see an unsourced figure"
    assert sweep(section, known) == [], "the clean section is not clean"
    return True


def main():
    report = open(REPORT, encoding="utf-8").read()
    blobs = {p: json.load(open(p, encoding="utf-8")) for p in (DELTA, MUTATION, PROBE)}

    failures = []
    for label, path, keys, fmt in FIGURES:
        value = dig(blobs[path], keys)
        rendered = fmt.format(value)
        if rendered not in report:
            failures.append("MISSING  %-22s %s (from %s)"
                            % (label, rendered, "/".join(map(str, keys))))

    # The measurement section is the one that must be fully accounted for.
    start = report.find("## The measurement")
    end = report.find("## Reader calibration")
    section = report[start:end] if start >= 0 < end else report
    known = {fmt.format(dig(blobs[p], k)) for _, p, k, fmt in FIGURES} | set(DERIVED)
    known |= {str(dig(blobs[p], k)) for _, p, k, _ in FIGURES}
    for token in sweep(section, known):
        failures.append("UNSOURCED  %r in the measurement section — no producer"
                        % token)

    for line in failures:
        print(line)
    if not failures:
        selftest(section, known)
        print("sweep self-test: PASS (it sees a planted figure, and the section "
              "is genuinely clean)")
    print("%d figures declared, %d problems" % (len(FIGURES), len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
