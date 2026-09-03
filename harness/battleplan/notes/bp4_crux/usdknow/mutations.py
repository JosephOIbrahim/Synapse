"""BP4-CRUX USDKNOW T-H: mutation battery against bp4_usdknow_check.py.

Scratch clone ONLY. Each mutation is an exact-string edit on the raw seed text,
then the checker runs, then the file is restored from `git show HEAD:<path>` and
asserted byte-identical to the pristine sha256 before the next case.

Cases tagged REDDEN are the contract the checker claims. Cases tagged PROBE are
adversarial: they test whether the checker's SUBSTRING matching lets a wrong
value through. A PROBE that SURVIVES is a checker weakness, not a builder lie.
"""
import hashlib, subprocess

SEED = "harness/bench/corpus/usd/usd_composition_worldlabs_22.0.400.json"
CHECK = ["python", "harness/battleplan/notes/bp4_usdknow_check.py", "--quiet"]
PRISTINE_SHA = hashlib.sha256(open(SEED, "rb").read()).hexdigest()


def run():
    r = subprocess.run(CHECK, capture_output=True, text=True)
    return r.returncode, [l for l in r.stderr.split("\n") if "FAIL" in l], r.stdout


def restore():
    out = subprocess.run(["git", "show", "HEAD:" + SEED], capture_output=True)
    open(SEED, "wb").write(out.stdout)
    ok = hashlib.sha256(open(SEED, "rb").read()).hexdigest() == PRISTINE_SHA
    st = subprocess.run(["git", "status", "--short", SEED], capture_output=True, text=True).stdout.strip()
    return ok, st


def mutate(old, new, after=None):
    t = open(SEED, encoding="utf-8").read()
    if after is None:
        assert t.count(old) == 1, "expected 1 occurrence of {!r}, found {}".format(old, t.count(old))
        j = t.index(old)
    else:
        j = t.index(old, t.index(after))
    t2 = t[:j] + new + t[j + len(old):]
    assert t2 != t, "no-op mutation"
    open(SEED, "w", encoding="utf-8").write(t2)


# (id, description, old, new, expectation, after-anchor-or-None)
CASES = [
 ("USDKNOW-M1", "strip an anchor -- row 'kind-component': anchor 'stdout.txt:30' -> 'probe Part A'",
  '"anchor": "stdout.txt:30",', '"anchor": "probe Part A",', "REDDEN", None),

 ("USDKNOW-M2a", "promote a PROPOSED row -- 'instanceable-false' PROPOSED -> VERIFIED-RUNTIME "
                 "(keeps its prose 'reasoning:' anchor)",
  '"tier": "PROPOSED"', '"tier": "VERIFIED-RUNTIME"', "REDDEN", '"id": "instanceable-false"'),

 ("USDKNOW-M2b", "promote a PROPOSED row -- 'variantset-splattier' PROPOSED -> FIXTURE-VERIFIED "
                 "(keeps its blueprint#2.5 doc anchor)",
  '"tier": "PROPOSED"', '"tier": "FIXTURE-VERIFIED"', "REDDEN", '"id": "variantset-splattier"'),

 ("USDKNOW-M2c", "promote a DOC-STATED row -- 'frame-conversion-order' DOC-STATED -> VERIFIED-RUNTIME",
  '"tier": "DOC-STATED"', '"tier": "VERIFIED-RUNTIME"', "REDDEN", '"id": "frame-conversion-order"'),

 ("USDKNOW-M3", "change the arc on a VERIFIED row -- 'livrps-reference-over-payload' reference -> payload "
                "(stdout.txt:66 reads arc=reference)",
  '"arc": "reference",', '"arc": "payload",', "REDDEN", '"id": "livrps-reference-over-payload"'),

 ("USDKNOW-M3b", "change the arc on a FIXTURE row -- 'variantsets-absent-in-sop-build' variant -> local "
                 "(stdout.txt:34 reads arc=variant)",
  '"arc": "variant",', '"arc": "local",', "REDDEN", '"id": "variantsets-absent-in-sop-build"'),

 ("USDKNOW-M4", "ratified false -> true",
  '"ratified": false,', '"ratified": true,', "REDDEN", None),

 ("USDKNOW-M5", "anchor a promotable row at a BLANK line -- 'purpose-collider-proxy' -> stdout.txt:2",
  '"anchor": "stdout.txt:31",', '"anchor": "stdout.txt:2",', "REDDEN", None),

 ("USDKNOW-M5b", "anchor a promotable row PAST the end -- 'purpose-render-scope' -> stdout.txt:9999",
  '"anchor": "stdout.txt:32",', '"anchor": "stdout.txt:9999",', "REDDEN", None),

 ("USDKNOW-M5c", "point a row at a real but WRONG evidence line -- 'livrps-specialize-weakest' "
                 "stdout.txt:68 -> stdout.txt:67 (67 is the payload-over-specialize line)",
  '"anchor": "stdout.txt:68",', '"anchor": "stdout.txt:67",', "REDDEN", None),

 # --- adversarial: does substring matching admit a WRONG value? ---
 ("USDKNOW-M6", "ADVERSARIAL prefix -- arc 'specialize' -> 'spec' on 'livrps-specialize-weakest'. "
                "stdout.txt:68 literally contains 'arc=specialize', so the needle 'arc=spec' "
                "substring-matches an arc name that does not exist",
  '"arc": "specialize",', '"arc": "spec",', "PROBE", None),

 ("USDKNOW-M7", "ADVERSARIAL inversion -- verify 'reference_unloadable=False' -> 'unloadable=True' on "
                "'payload-vs-reference-unloadable'. stdout.txt:46 contains 'payload_unloadable=True', so "
                "the semantically INVERTED token substring-matches",
  '"verify": "reference_unloadable=False",', '"verify": "unloadable=True",', "PROBE", None),

 ("USDKNOW-M8", "ADVERSARIAL wrong value -- verify 'dropped=9' -> 'loaded=1' on 'payload-splat-collider'. "
                "stdout.txt:43 reads 'loaded=10', so the false claim 'loaded=1' substring-matches",
  '"verify": "dropped=9",', '"verify": "loaded=1",', "PROBE", None),
]

print("PRISTINE seed sha256:", PRISTINE_SHA)
rc0, _, so0 = run()
print("BASELINE exit:", rc0, "|", [l for l in so0.split("\n") if "RESULT" in l][0])
assert rc0 == 0, "baseline not green -- abort"
print()

results = []
for mid, desc, old, new, expect, after in CASES:
    print("=" * 104)
    print("{}  {}".format(mid, desc))
    mutate(old, new, after)
    rc, fails, so = run()
    verdict = "REDDENED" if rc == 1 else "SURVIVED"
    print("  mutated      : {!r}  ->  {!r}{}".format(old, new, "   [within row " + after + "]" if after else ""))
    print("  checker exit : {}".format(rc))
    if fails:
        for l in fails:
            print("  FAIL line    : {}".format(l.strip()))
    else:
        print("  FAIL line    : (none)")
        for l in so.split("\n"):
            if "RESULT" in l:
                print("  RESULT line  : {}".format(l.strip()))
    print("  verdict      : {}   (expected: {})".format(verdict, expect))
    ok, st = restore()
    rc2, _, _ = run()
    print("  restored     : byte-identical={}  git status={!r}  re-run exit={}".format(ok, st, rc2))
    assert ok and rc2 == 0, "restore failed for " + mid
    results.append((mid, verdict, expect, "; ".join(l.strip() for l in fails)[:220]))
    print()

print("=" * 104)
print("SUMMARY")
for mid, v, e, f in results:
    if e == "REDDEN":
        flag = "contract holds" if v == "REDDENED" else "!!! GAP -- contract does NOT hold"
    else:
        flag = "checker WEAKNESS (false green)" if v == "SURVIVED" else "checker stricter than feared"
    print("  {:<12} {:<9} expect={:<7} {}".format(mid, v, e, flag))
