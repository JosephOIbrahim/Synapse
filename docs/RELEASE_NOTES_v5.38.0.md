# v5.38.0 — it knows Copernicus, and the economist has a face

*Eighty-one commits. The corpus stopped being an artifact beside the product and became part of it; the token work stopped being measurements and became a surface. And the day's most instructive defect was mine, shipped and fixed inside thirty minutes.*

---

## "Does it know Copernicus?" — now yes

The frontier gap measured a day earlier: **Houdini 22's what's-new names 171 Copernicus node paths. SYNAPSE grounded 3.**

The corpus is now loaded by `knowledge_lookup` — **603 live node types, VERIFIED-DOC, pinned to 22.0.368**, each carrying its summary, its documented parameters and its build.

**The gate INGEST-01 demanded is applied at BUILD TIME**, which is the stronger placement. A read-time filter can be bypassed by a future caller; an entry that was never written cannot be served by anyone. One entry failed validation against the running catalogue and is absent.

**Two defects hid inside the wiring**, and neither was found by reasoning:

**51 type names exist in more than one context.** `blur`, `crop`, `chromakey` and `average` are in *both* `cop` and `cop2` — and insertion order let **legacy overwrite Copernicus.** An artist asking about `blur` would have been answered from the subsystem Copernicus replaced. Caught only because 603 keys from 659 entries did not add up.

**And the suite caught the placement.** Matching node types before keyword lookup broke 8 tests: `merge`, `wrangle` and `solver` are all live node types, so *"vex attribute wrangle"* was hijacked out of its topic into a datasheet. **The corpus answers when a query IS a node type, not when a sentence contains one.**

---

## The TOKEN face — T.4's freeze lifts

`verdict.py`, `voice_contract.py` and `probe.py` were built and rendering nowhere. There is now a **TOKEN tab** beside CHAT that renders them.

**It exists because the probe layer made the rail smaller, not because the rail was wrong.** The design called for `18.0k / 200k · $0.06` — and V3 established that **quota headroom is not obtainable** from any configured provider, and **no provider exposes per-token pricing over its API.** The rail was built around a fuel gauge with no readable level.

So the tab shows what was actually measured: **per-turn composition**, **cache behaviour** (invisible anywhere else, because a cache miss looks exactly like normal operation), and **local vs metered** — which matters because six of thirteen Ollama tags are metered by `ollama.com`, including the default pick, and the distinction is invisible in the name.

**A Voronoi field carries the proportion**, allocated by cumulative **area** rather than cell count, because Voronoi cells are unequal and counting them would misstate every share. Verified: 10.5% of tokens receives 10.0% of the area.

**And an unmeasured segment claims no cells.** Not a small region — none. A segment drawn small reads as *"this costs little"*; the truth is *"nobody measured this."* At nine cells the system prompt vanished entirely, so the count is 18 — where the aesthetic and the constraint intersect.

**Unobtainable renders as `unknown`. Never zero. A zero is a claim.**

---

## A render can be stopped

R48 recorded this as not implementable. **Refuted by working code** — 415 lines, 38 new pins.

**And the emergency halt was one step from shipping as a button.** `trigger_emergency_halt` returns `ALL_OPERATIONS_HALTED` in 0.0s while the cook it was asked to stop keeps running: it walks `/obj` only, and TOP networks live under `/tasks`. Caught because the leg probed the control against a real cook instead of wiring it and assuming.

**Stopping a mantra render leaves a valid, pixel-empty EXR.** `iinfo -v` exits 0 on a correct 1920×1080 header. It parses. It has no pixels. Karma is safe, so the hazard is renderer-specific — worse than universal, because it only appears sometimes. The stop now returns that hazard **as data**, so a caller cannot receive a clean-looking success without the residue it must check.

---

## Fixes

**An empty `ANTHROPIC_API_KEY` no longer shadows the repo `.env`.** `setdefault` is a no-op when the key exists, and an empty string exists — so the product reported itself unconfigured while holding a valid key. A user who has just funded an account and sees "unconfigured" concludes the funding failed.

**A modal progress dialog that froze Houdini.** Shipped at 18:02 to make a long operation legible, and it grabbed input for the entire application. Fixed at 18:31. The measurement that named it: `Responding: True`, 0.01 cores, every thread waiting — an app that responds at the OS level, does no work and will not accept a click is a modal grab.

**Five harness defects, each found by using the harness** — a status tool describing a board that stopped existing 23 legs earlier, a dispatch lock with no release, a liveness probe asking whether the *orchestrator* was alive, a check that could not tell a killed leg from a running one, and finished sessions idling for 85 minutes.

---

## What this release does not claim

**The economist's figures are proxy-measured within ~6%.** `count_tokens` now works and the exact counts differ from the character-derived ones; the panel says so in its own footnote rather than presenting them as precise.

**T.1 is not done and is not what it looked like.** The 2,000-token ceiling is about tool **count**, not tool **size** — 120 tool *names alone* measure 2,919 tokens. That is a product decision, not an optimisation.

**Seven MCP tools advertise `readOnlyHint=true` while the server treats them as mutating.** The check ships and gates; which side is wrong is a per-tool question that needs a handler read, not a grep.

**And nobody has used any of this.** Every judgement about what an artist would find valuable remains inference.

---

## Verifying it

```
harness/notes/rag_h22_control.py            the phantom is not served
harness/notes/panel_tokenfield_control.py   area tracks share, six assertions
harness/notes/longop_control.py             no UI means no-op, eight assertions
harness/verify/readonly_hint_agreement.py   annotations vs enforcement
harness/verify/branch_harvest.py            no leg's work stranded
```

Each was demonstrated failing before its pass was trusted. **Suite: 5,279 passed, 0 failed.**
