"""Independent check of E0-F2: is the token baseline stale, and does a gate read it?

E0 reported that harness/notes/token_baseline.json records a registry hash which
no longer matches the live registry - 115 tools then, 120 now - and that
harness/verify/token_ceiling.json gates against it.

That is R2's shape in a new subsystem: a ratchet whose floor describes a
previous tree. Verified here from the main tree rather than taken from E0's
receipt, because E0's lock is still held and its receipt is a draft (R146).
"""
import hashlib, json, os, sys

BASE = "harness/notes/token_baseline.json"
CEIL = "harness/verify/token_ceiling.json"

b = json.load(open(BASE, encoding="utf-8-sig"))
c = json.load(open(CEIL, encoding="utf-8-sig"))

print("BASELINE")
print("  recorded blake2b :", b.get("blake2b"))
print("  method           :", (b.get("stats") or {}).get("method", "?")[:60])
print("  generated        :", b.get("generated", "?"))
print()
print("CEILING")
print("  max_preload      :", c.get("max_preload_tokens"))
print("  surfaces         :", c.get("measured_surfaces"))
print("  set_by           :", c.get("set_by", "?"))
print("  generated        :", c.get("generated", "?"))
print()

# What does the baseline's hash actually describe? Find the registry it names.
stats = b.get("stats") or {}
print("BASELINE STATS")
for k, v in list(stats.items())[:10]:
    print("   %-22s %s" % (k, str(v)[:70]))
print()

# The live registry, hashed the same way.
CAND = [
    "python/synapse/mcp/_tool_registry.py",
    "python/synapse/mcp/tool_registry.py",
]
live = None
for p in CAND:
    if os.path.exists(p):
        live = p
        break

if live:
    h = hashlib.blake2b(open(live, "rb").read(), digest_size=16).hexdigest()
    print("LIVE REGISTRY")
    print("  path             :", live)
    print("  blake2b(16)      :", h)
    print("  matches baseline :", h == b.get("blake2b"))
else:
    print("LIVE REGISTRY      : not found at", CAND)

print()
print("THE POINT: a ceiling that gates against a baseline taken from a registry")
print("that no longer exists is measuring a tree nobody is working in.")
