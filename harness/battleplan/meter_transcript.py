# meter_transcript.py - measure a Claude Code transcript on the rails basis (input + cache_creation + cache_read; output)
# for a leg the ledger could not settle (ledger closed at blocked:budget). Read-only. Output is MEASURED, never estimated.
# Usage: python harness/battleplan/meter_transcript.py <transcript.jsonl>
import json, sys
p = sys.argv[1]
i = o = n = 0
for line in open(p, encoding="utf-8"):
    try:
        j = json.loads(line)
    except Exception:
        continue
    m = j.get("message")
    u = m.get("usage") if isinstance(m, dict) else None
    if u:
        i += u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
        o += u.get("output_tokens", 0)
        n += 1
print(f"tokens_in={i} tokens_out={o} messages_with_usage={n} basis=rails (input+cache_creation+cache_read / output)")
