# meter_transcript.py - measure a Claude Code transcript for a leg the ledger could not settle
# (ledger closed at blocked:budget). Read-only. Output is MEASURED, never estimated.
#
# BP9-CAPBASIS (ruling 5): prints BOTH bases, labelled. The rails total sums every usage
# field at 1x (unchanged from BP2-METER, kept for comparison); the cost_weighted total
# multiplies each raw field by its weight from harness/rails_exec.json 'cost_weights'
# (the basis the 70M cap is enforced on); max_ctx is the largest single call's
# input + cache_creation + cache_read.
# Usage: python harness/battleplan/meter_transcript.py <transcript.jsonl> [--json]
from __future__ import annotations

import json
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

from rails import (  # noqa: E402
    RAW_USAGE_FIELDS, UNKNOWN, cost_weighted, load_cost_weights, measure_transcript_usage,
)


def meter(path, weights: dict | None = None) -> dict:
    """Measure one transcript -> the four raw fields, rails_total, cost_weighted, max_ctx.

    Every value is a measured int, or the literal UNKNOWN when the transcript is absent
    or carries no usage record. 'weights' defaults to the rails_exec.json table.
    """
    w = weights or load_cost_weights()
    raw = measure_transcript_usage(path)
    if raw is None:
        out = {f: UNKNOWN for f in RAW_USAGE_FIELDS}
        out.update({"rails_total": UNKNOWN, "cost_weighted": UNKNOWN, "max_ctx": UNKNOWN,
                    "messages_with_usage": 0})
    else:
        out = {f: raw[f] for f in RAW_USAGE_FIELDS}
        out.update({"rails_total": raw["rails_total"],
                    "cost_weighted": cost_weighted(raw, w),
                    "max_ctx": raw["max_ctx"],
                    "messages_with_usage": raw["messages_with_usage"]})
    out["cost_weights"] = dict(w)
    out["basis"] = ("rails = input+cache_creation+cache_read+output at 1x; "
                    "cost_weighted = sum(field * cost_weights[field]); "
                    "max_ctx = max per-call input+cache_creation+cache_read")
    out["transcript"] = str(path)
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__ or "usage: meter_transcript.py <transcript.jsonl> [--json]")
        return 2
    as_json = "--json" in argv
    path = [a for a in argv if a != "--json"][0]
    m = meter(path)
    if as_json:
        print(json.dumps(m, indent=2))
        return 0
    print(f"input_tokens={m['input_tokens']} cache_creation_input_tokens={m['cache_creation_input_tokens']} "
          f"cache_read_input_tokens={m['cache_read_input_tokens']} output_tokens={m['output_tokens']} "
          f"messages_with_usage={m['messages_with_usage']}")
    print(f"rails_total={m['rails_total']} (all fields at 1x, comparison only)")
    print(f"cost_weighted={m['cost_weighted']} (the enforced basis; weights={m['cost_weights']})")
    print(f"max_ctx={m['max_ctx']} (largest single-call input incl. cache fields)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
