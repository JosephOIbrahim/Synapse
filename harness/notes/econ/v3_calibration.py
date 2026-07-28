#!/usr/bin/env python
"""V3 producer — R60: calibrate every reader BEFORE its output is trusted.

    python harness/notes/econ/v3_calibration.py

Emits ``harness/notes/econ/V3_calibration.json``. Exits non-zero if any reader
fails calibration, so a drifted reader cannot quietly publish numbers.

This leg publishes counts — "63 rows classified by live id token, 10 by
parameter size, 54 unclassified". R60 says a reader is calibrated before it is
trusted, and I1 found a control that pinned nothing by doing exactly this. So
each reader below is run against a HAND-LABELLED set drawn from the recorded
live payloads, with both halves present:

* **positive** — inputs whose correct answer is known, which the reader must get
  right;
* **negative** — inputs whose correct answer is *refusal*, which the reader must
  not classify. A classifier with no negative half will happily label anything,
  and its coverage number is then a statement about its own eagerness.

Every block states the condition under which it fails (Law 1).
"""
from __future__ import annotations

import dataclasses
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "python"))

from synapse.panel.providers import probe as P    # noqa: E402


# ---------------------------------------------------------------------------
# Ground truth. Hand-labelled from the recorded live payloads (2026-07-28):
#   Ollama    GET /api/tags            -> details.parameter_size
#   Anthropic GET /v1/models?limit=100 -> id, display_name
# ---------------------------------------------------------------------------

PARAM_TRUTH = [
    # (live string, expected billions) — the exact strings Ollama returned
    ("2.81T", 2810.0),
    ("756b", 756.0),
    ("550b", 550.0),
    ("123.6B", 123.6),
    ("70.6B", 70.6),
    ("31.6B", 31.6),
    ("31.1B", 31.1),
    ("20.9B", 20.9),
    ("8.0B", 8.0),
    ("4.2B", 4.2),
]
PARAM_REFUSALS = [
    # Ollama returned an EMPTY parameter_size for four :cloud tags. The reader
    # must return None, not 0.0 — a 0.0 would tier a 700B model as FAST.
    ("", None),
    (None, None),
    ("large", None),
    ("unknown", None),
    ("B", None),
    ("many", None),
]

# Anthropic publishes no parameter_size, so these exercise the WEAK signal.
TIER_TRUTH_BY_TOKEN = [
    ("claude-opus-5", P.TIER_FRONTIER),
    ("claude-opus-4-8", P.TIER_FRONTIER),
    ("claude-opus-4-7", P.TIER_FRONTIER),
    ("claude-opus-4-6", P.TIER_FRONTIER),
    ("claude-opus-4-5-20251101", P.TIER_FRONTIER),
    ("claude-opus-4-1-20250805", P.TIER_FRONTIER),
    ("claude-sonnet-5", P.TIER_BALANCED),
    ("claude-sonnet-4-6", P.TIER_BALANCED),
    ("claude-sonnet-4-5-20250929", P.TIER_BALANCED),
    ("claude-haiku-4-5-20251001", P.TIER_FAST),
    ("nvidia/nemotron-3-super-120b-a12b", P.TIER_BALANCED),
    ("nvidia/nemotron-3-nano-30b-a3b", P.TIER_FAST),
]

# The reader MUST refuse these. claude-fable-5 and glm-5:cloud are REAL, live,
# registry-declared models that carry no family token and no published size —
# they are the honest limit of the weak signal, and the refusal is the correct
# answer, not a miss to be papered over with a default tier.
TIER_REFUSALS = [
    "claude-fable-5",
    "glm-5:cloud",
    "kimi-k2.5:cloud",
    "baai/bge-m3",
    "zzz-model-that-does-not-exist",
    "",
]

# Paired positive/negative for the capability gate. Same model string, same
# size, opposite capability lists — so the gate is shown firing on evidence
# rather than on the name.
GATE_PAIR = {
    "model": "nemotron-3-ultra:cloud",
    "parameter_size": "550b",
    "with_tools": ["completion", "tools", "thinking"],
    "without_tools": ["completion", "thinking"],
}


def calibrate_param_reader() -> dict:
    hits, misses = 0, []
    for text, expect in PARAM_TRUTH:
        got = P.parse_parameter_size(text)
        if got is not None and abs(got - expect) < 1e-6:
            hits += 1
        else:
            misses.append({"input": text, "expected": expect, "got": got})
    refused, wrong_refusals = 0, []
    for text, _ in PARAM_REFUSALS:
        got = P.parse_parameter_size(text)
        if got is None:
            refused += 1
        else:
            wrong_refusals.append({"input": text, "got": got})
    return {
        "reader": "probe.parse_parameter_size",
        "condition_under_which_this_fails":
            "the parser returns a number for an unparseable size (a 0.0 would "
            "tier a 700B model as FAST), or misreads a live suffix",
        "positive": {"n": len(PARAM_TRUTH), "hits": hits, "misses": misses},
        "negative": {"n": len(PARAM_REFUSALS), "refused": refused,
                     "wrongly_classified": wrong_refusals},
        "pass": hits == len(PARAM_TRUTH) and refused == len(PARAM_REFUSALS),
    }


def calibrate_tier_reader() -> dict:
    hits, misses = 0, []
    for model, expect in TIER_TRUTH_BY_TOKEN:
        tiers, basis = P.tier_candidates_for(model)
        if tiers == (expect,) and basis == "live_id_token":
            hits += 1
        else:
            misses.append({"model": model, "expected": expect,
                           "got": list(tiers), "basis": basis})
    refused, wrong = 0, []
    for model in TIER_REFUSALS:
        tiers, basis = P.tier_candidates_for(model)
        if tiers == () and basis == "unclassified":
            refused += 1
        else:
            wrong.append({"model": model, "got": list(tiers), "basis": basis})

    # size outranks token: a FAST-named model the provider says is 600B
    override, _ = P.tier_candidates_for("nemotron-mini:latest",
                                        parameter_size="600B")

    # the gate, both halves
    with_tools, basis_with = P.tier_candidates_for(
        GATE_PAIR["model"], parameter_size=GATE_PAIR["parameter_size"],
        capabilities=GATE_PAIR["with_tools"])
    without_tools, basis_without = P.tier_candidates_for(
        GATE_PAIR["model"], parameter_size=GATE_PAIR["parameter_size"],
        capabilities=GATE_PAIR["without_tools"])

    return {
        "reader": "probe.tier_candidates_for",
        "condition_under_which_this_fails":
            "the classifier defaults an unknown model to a tier instead of "
            "refusing, or a family token overrides a published parameter size, "
            "or the tool-capability gate does not fire",
        "positive": {"n": len(TIER_TRUTH_BY_TOKEN), "hits": hits, "misses": misses},
        "negative": {"n": len(TIER_REFUSALS), "refused": refused,
                     "wrongly_classified": wrong},
        "size_outranks_token": {"got": list(override),
                                "pass": override == (P.TIER_FRONTIER,)},
        "capability_gate_pair": {
            "with_tools": {"tiers": list(with_tools), "basis": basis_with},
            "without_tools": {"tiers": list(without_tools), "basis": basis_without},
            "pass": with_tools == (P.TIER_FRONTIER,)
                    and without_tools == ()
                    and basis_without == "no_tool_capability",
        },
        "pass": (hits == len(TIER_TRUTH_BY_TOKEN)
                 and refused == len(TIER_REFUSALS)
                 and override == (P.TIER_FRONTIER,)
                 and without_tools == ()),
    }


def calibrate_quota_reader() -> dict:
    """The header parser publishes ``None`` on every live response measured.

    A reader that ONLY ever returns None is indistinguishable from a broken
    one, so the positive half feeds it headers it must parse.
    """
    live_absent = P._quota_from_headers({
        # the exact header names api.anthropic.com returned on GET /v1/models
        "date": "Tue, 28 Jul 2026 16:33:00 GMT", "content-type": "application/json",
        "request-id": "req_x", "anthropic-organization-id": "org_x",
        "server": "cloudflare", "cf-ray": "x",
    })
    synthetic = P._quota_from_headers({
        "anthropic-ratelimit-requests-remaining": "12",
        "anthropic-ratelimit-requests-limit": "50",
    })
    openai_style = P._quota_from_headers({
        "x-ratelimit-remaining-requests": "0",
        "x-ratelimit-limit-requests": "500",
    })
    malformed = P._quota_from_headers({"x-ratelimit-remaining": "plenty"})
    return {
        "reader": "probe._quota_from_headers",
        "condition_under_which_this_fails":
            "the parser fabricates a 0 when no rate-limit header is present "
            "(every provider would then read RED), or fails to parse one that is",
        "negative_live_headers": {"got": list(live_absent),
                                  "pass": live_absent[0] is None
                                          and live_absent[2] == "unavailable_at_zero_cost"},
        "positive_anthropic_style": {"got": list(synthetic),
                                     "pass": synthetic[0] == 12 and synthetic[1] == 50},
        "positive_openai_style": {"got": list(openai_style),
                                  "pass": openai_style[0] == 0 and openai_style[1] == 500},
        "negative_malformed": {"got": list(malformed), "pass": malformed[0] is None},
        "pass": (live_absent[0] is None and synthetic[0] == 12
                 and openai_style[0] == 0 and malformed[0] is None),
    }


def calibrate_colour_reader() -> dict:
    """A truth table over the three inputs colour_for is allowed to read."""
    now = 1_800_000_000.0
    base = dict(model="m", tier_candidates=(), available=True,
                quota_remaining=None, quota_total=None, cost_per_1k_in=None,
                cost_per_1k_out=None, latency_ms=1.0, probed_at=now)
    cases = [
        ("fresh + available + no quota signal", dict(), now, "green"),
        ("fresh + available + quota 5", dict(quota_remaining=5), now, "green"),
        ("fresh + available + quota 0", dict(quota_remaining=0), now, "red"),
        ("fresh + unavailable", dict(available=False), now, "red"),
        ("stale + available", dict(), now + P.PROBE_TTL_S + 1, "grey"),
        ("stale + unavailable", dict(available=False), now + P.PROBE_TTL_S + 1, "grey"),
        ("stale + quota 0", dict(quota_remaining=0), now + P.PROBE_TTL_S + 1, "grey"),
        ("never probed", dict(probed_at=None), now, "grey"),
        ("future stamp (skew)", dict(probed_at=now + 3600), now, "grey"),
        ("exactly at ttl", dict(), now + P.PROBE_TTL_S, "green"),
        ("cost is huge", dict(cost_per_1k_in=999.0), now, "green"),
        ("cost is zero", dict(cost_per_1k_in=0.0), now, "green"),
    ]
    rows, wrong = [], []
    for label, over, read_at, expect in cases:
        r = P.ProbeResult(**{**base, **over})
        got = P.colour_for(r, now=read_at)
        rows.append({"case": label, "expected": expect, "got": got})
        if got != expect:
            wrong.append(rows[-1])
    covered = {c["got"] for c in rows}
    return {
        "reader": "probe.colour_for",
        "condition_under_which_this_fails":
            "availability is checked before age (a stale row would read green), "
            "or an unknown quota is read as exhausted, or cost reaches the "
            "colour at all",
        "truth_table": rows,
        "wrong": wrong,
        "all_three_colours_exercised": sorted(covered) == ["green", "grey", "red"],
        "pass": not wrong and sorted(covered) == ["green", "grey", "red"],
    }


def calibrate_refresh_reader() -> dict:
    now = 1_800_000_000.0
    r = P.ProbeResult(model="m", tier_candidates=(), available=True,
                      quota_remaining=None, quota_total=None, cost_per_1k_in=None,
                      cost_per_1k_out=None, latency_ms=1.0, probed_at=now)
    cases = [
        ("no result at all", None, now, True),
        ("never probed", dataclasses.replace(r, probed_at=None), now, True),
        ("just probed", r, now, False),
        ("just under the interval", r, now + P.REFRESH_INTERVAL_S - 0.001, False),
        ("at the interval", r, now + P.REFRESH_INTERVAL_S, True),
        ("well past", r, now + 10_000, True),
        ("future stamp (skew)", dataclasses.replace(r, probed_at=now + 500), now, True),
    ]
    rows, wrong = [], []
    for label, res, read_at, expect in cases:
        got = P.should_refresh(res, now=read_at)
        rows.append({"case": label, "expected": expect, "got": got})
        if got != expect:
            wrong.append(rows[-1])
    return {
        "reader": "probe.should_refresh",
        "condition_under_which_this_fails":
            "the interval floor is not enforced — a caller in a hot loop could "
            "then hammer a provider and the probe becomes the thing that trips "
            "the rate limit it reports on",
        "truth_table": rows,
        "wrong": wrong,
        "pass": not wrong,
    }


def declared_model_coverage() -> dict:
    """The number this leg actually needs the classifier for.

    127 live rows is a catalogue; what the panel can SELECT is the registry's
    declared rows. Of those, how many carry a tier?
    """
    from synapse.panel.providers import registry as R
    out, unclassified = {}, []
    for pid in P._PROBES:
        rows = []
        for mid, _label in R.models_for(pid):
            tiers, basis = P.tier_candidates_for(mid)
            rows.append({"model": mid, "tiers": list(tiers), "basis": basis})
            if not tiers:
                unclassified.append({"provider": pid, "model": mid})
        out[pid] = rows
    total = sum(len(v) for v in out.values())
    return {
        "what": "tier coverage over REGISTRY-DECLARED (panel-selectable) models",
        "declared_total": total,
        "unclassified": unclassified,
        "unclassified_count": len(unclassified),
        "per_provider": out,
    }


def main() -> int:
    blocks = {
        "parameter_size": calibrate_param_reader(),
        "tier_classifier": calibrate_tier_reader(),
        "quota_headers": calibrate_quota_reader(),
        "colour": calibrate_colour_reader(),
        "refresh": calibrate_refresh_reader(),
    }
    out = {
        "schema": "v3_calibration/v1",
        "producer": "harness/notes/econ/v3_calibration.py",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "rule": "R60 — every reader is calibrated before it is trusted; every "
                "block carries a positive AND a negative half.",
        "readers": blocks,
        "declared_model_coverage": declared_model_coverage(),
        "all_pass": all(b["pass"] for b in blocks.values()),
    }
    dest = HERE.parent / "V3_calibration.json"
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote %s" % dest)
    for name, b in blocks.items():
        print("  %-16s %s" % (name, "PASS" if b["pass"] else "FAIL"))
        if not b["pass"]:
            print("     ", json.dumps(b, indent=2)[:1200])
    cov = out["declared_model_coverage"]
    print("  declared models: %d, unclassified: %d -> %s"
          % (cov["declared_total"], cov["unclassified_count"],
             [u["model"] for u in cov["unclassified"]]))
    return 0 if out["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
