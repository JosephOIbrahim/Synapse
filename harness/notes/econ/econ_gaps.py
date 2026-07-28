#!/usr/bin/env python3
"""E0 A3 - how long is the gap between SYNAPSE operations, really?

The first draft of E0 asserted that "VFX think-time between turns routinely
exceeds five minutes" and used it to argue that the 5-minute ephemeral cache TTL
would usually be cold. That sentence had NO PRODUCER. It was a plausible-sounding
empirical claim about artist behaviour, asserted rather than measured, and it
carried real weight - it was the whole support for "the strongest honest argument
FOR T.1". Law 2 exists for exactly this.

The measurement was available the entire time. ~/.synapse/audit/ holds Fernet
lines that decrypt with the key SYNAPSE itself writes beside them, and every
entry carries timestamp_utc.

READ-ONLY and AGGREGATE-ONLY. This reads the audit log and emits nothing but
timing statistics - no operation content, no node paths, no parameter values,
no session identifiers. The artifact it writes contains histograms and nothing
else.

WHAT THIS IS NOT: these are TOOL-OPERATION bursts, not chat turns. SYNAPSE's
audit log records Houdini operations, and a chat turn may contain many of them
or none. So this is a PROXY for inter-turn gaps, and its direction of bias is
stated below rather than hidden. It replaces an unsourced assertion with a
measured proxy - a strict improvement, not a settled answer.

Usage:
    python harness/notes/econ/econ_gaps.py
Writes:
    harness/notes/econ/E0_gaps.json
"""
from __future__ import annotations

import json
import os
import statistics
from datetime import datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent / "E0_gaps.json"
AUDIT = Path(os.path.expanduser("~/.synapse/audit"))
KEYFILE = Path(os.path.expanduser("~/.synapse/encryption.key"))
MAGIC = "SYNAPSE_ENC_V1:"
TTL_SECONDS = 300  # the default ephemeral prompt-cache window (assumption A1)


def load_timestamps():
    """Return (sorted timestamps, diagnostics). Content is never retained."""
    from cryptography.fernet import Fernet

    fernet = Fernet(KEYFILE.read_bytes().strip())
    stamps, files, lines, decrypted, parsed, key_census = [], 0, 0, 0, 0, set()

    for fp in sorted(AUDIT.glob("*.jsonl")):
        files += 1
        for raw in fp.read_text(encoding="utf-8", errors="replace").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            lines += 1
            if raw.startswith(MAGIC):
                try:
                    raw = fernet.decrypt(raw[len(MAGIC):].encode()).decode("utf-8")
                    decrypted += 1
                except Exception:
                    continue
            try:
                rec = json.loads(raw)
            except Exception:
                continue
            parsed += 1
            key_census.update(rec.keys())
            ts = rec.get("timestamp_utc") or rec.get("timestamp")
            if not ts:
                continue
            try:
                stamps.append(datetime.fromisoformat(str(ts).replace("Z", "+00:00")))
            except Exception:
                continue

    stamps.sort()
    return stamps, {
        "files": files, "lines": lines, "decrypted": decrypted, "parsed": parsed,
        "with_timestamp": len(stamps),
        # Does the audit log carry request payloads? This settles whether REAL
        # turns are recoverable, which is E0 Q4's evidence question.
        "carries_message_payloads": any(
            k in key_census for k in ("messages", "system", "input_tokens",
                                      "cache_read_input_tokens", "tool_result")),
        "top_level_keys_present": sorted(key_census),
    }


def bursts(stamps, threshold_s):
    """Collapse ops into bursts, then measure the gaps BETWEEN bursts.

    A chat turn fires many operations in quick succession. Treating every
    op-to-op gap as a turn gap would report a median of seconds and make the
    cache look perfect. Collapsing into bursts is the conservative reading, and
    the threshold is swept rather than chosen, because choosing it would let the
    analyst pick the answer.
    """
    gaps = []
    prev = None
    for t in stamps:
        if prev is not None:
            d = (t - prev).total_seconds()
            if d > threshold_s:
                gaps.append(d)
        prev = t
    return gaps


def summarize(gaps):
    if not gaps:
        return None
    s = sorted(gaps)
    over = sum(1 for g in s if g > TTL_SECONDS)
    return {
        "n_gaps": len(s),
        "median_s": round(statistics.median(s), 1),
        "mean_s": round(statistics.fmean(s), 1),
        "p25_s": round(s[len(s) // 4], 1),
        "p75_s": round(s[3 * len(s) // 4], 1),
        "frac_over_ttl": round(over / len(s), 4),
        "frac_within_ttl": round(1 - over / len(s), 4),
        "pct_over_ttl": round(100.0 * over / len(s), 1),
    }


def controls(stamps):
    """Mutation-tested. A gap reader that cannot fail would report any TTL as fine."""
    cals = []

    # CTL-G1: the reader must see a synthetic gap it is given.
    from datetime import timedelta
    base = stamps[0] if stamps else datetime.now().astimezone()
    synth = [base, base + timedelta(seconds=10), base + timedelta(seconds=1000)]
    g = bursts(synth, 30)
    cals.append({
        "id": "CTL-G1",
        "what": "reader detects a gap that exceeds the TTL",
        "fails_if": "a synthetic 1000s gap is not reported as over-TTL",
        "observed": {"gaps": g, "summary": summarize(g)},
        "verdict": "PASS" if g and g[0] > TTL_SECONDS else "FAIL",
        "mutation": "injected a 1000s gap between two ops",
    })

    # CTL-G2: false-positive control - tightly spaced ops must yield NO burst gap.
    synth2 = [base + timedelta(seconds=i) for i in range(0, 20, 2)]
    g2 = bursts(synth2, 30)
    cals.append({
        "id": "CTL-G2",
        "what": "reader does NOT manufacture gaps from tightly spaced ops",
        "fails_if": "ops 2s apart produce a burst gap, which would inflate the "
                    "over-TTL fraction and make the cache look worse than it is",
        "observed": {"gaps": g2},
        "verdict": "PASS" if not g2 else "FAIL",
        "mutation": "ten ops at 2s spacing",
    })

    # CTL-G3: the threshold sweep must actually move the answer, or sweeping it
    # is theatre and a single threshold would have been honest.
    return cals


def main() -> int:
    if not AUDIT.exists() or not KEYFILE.exists():
        out = {"schema": "e0_gaps/v1", "status": "UNAVAILABLE",
               "why": f"audit dir exists={AUDIT.exists()} key exists={KEYFILE.exists()}"}
        OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print("[econ_gaps] audit log or key absent - nothing measured")
        return 0

    stamps, diag = load_timestamps()
    cals = controls(stamps)

    sweep = {}
    for th in (10, 30, 60, 120, 300):
        sweep[f"burst_threshold_{th}s"] = summarize(bursts(stamps, th))

    moved = len({v["pct_over_ttl"] for v in sweep.values() if v}) > 1
    cals.append({
        "id": "CTL-G3",
        "what": "the burst threshold materially changes the answer",
        "fails_if": "every threshold yields the same over-TTL fraction, in which "
                    "case sweeping it is theatre and one number should be quoted",
        "observed": {th: (v["pct_over_ttl"] if v else None) for th, v in sweep.items()},
        "verdict": "PASS" if moved else "FAIL",
        "mutation": "swept 10/30/60/120/300s",
    })

    span = {"first": stamps[0].isoformat() if stamps else None,
            "last": stamps[-1].isoformat() if stamps else None}

    out = {
        "schema": "e0_gaps/v1",
        "produced_by": "harness/notes/econ/econ_gaps.py",
        "status": "MEASURED",
        "what_this_measures": "Gaps between bursts of SYNAPSE TOOL OPERATIONS, from the "
                              "audit log. NOT chat turns.",
        "bias_direction": "An artist may think for a long time WITHOUT firing an operation, "
                          "and a single chat turn fires several operations. Collapsing ops "
                          "into bursts corrects the second and cannot correct the first, so "
                          "this figure is best read as a LOWER BOUND on how often the cache "
                          "is cold - the true cold fraction is at least this and possibly "
                          "higher. It is a proxy, and it replaces an assertion that had no "
                          "evidence at all.",
        "ttl_seconds_assumed": TTL_SECONDS,
        "source": {"dir": str(AUDIT), "key": str(KEYFILE),
                   "read_only": True,
                   "content_retained": "NONE - timing statistics only; no operation "
                                       "content, paths, values or session ids are read "
                                       "into the artifact"},
        "diagnostics": diag,
        "span": span,
        "controls": cals,
        "sweep": sweep,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[econ_gaps] wrote {OUT}")
    for c in cals:
        print(f"  {c['id']} {c['verdict']:4}  {c['what']}")
    print(f"\n  {diag['parsed']:,} entries parsed from {diag['files']} files "
          f"({diag['decrypted']:,} decrypted); {diag['with_timestamp']:,} carry a timestamp")
    print(f"  audit log carries model-request payloads: {diag['carries_message_payloads']}")
    print(f"  span {span['first']} .. {span['last']}\n")
    print(f"  {'burst threshold':<22}{'n gaps':>9}{'median s':>11}{'% over 300s TTL':>18}")
    for th, v in sweep.items():
        if v:
            print(f"  {th:<22}{v['n_gaps']:>9}{v['median_s']:>11}{v['pct_over_ttl']:>17}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
