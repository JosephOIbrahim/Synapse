# Ruling R-CACHE-1 — resource-aware-cache adjudication disposition

**Ruled:** 2026-08-09, Joe (CTO), in-session word: "Approved" on presented option 2.
**Recorded by:** Claude, acting as instrument under engineering delegation for this wave.
**Adjudication:** `docs/intake/adjudication-resource-aware-cache.md` (ADOPT 16 · ADAPT 6 · CORRECT 16 · REJECT 5 · 19/19 challenges sustained · recommended REVIEW_ONLY).

## Disposition: adopt-with-amendments

1. The ADOPTed core is **authorized for build by this ruling** — Phase 0 (trustworthy
   observation) and Phase 1 (read-only advisor) only. Authorization flows from this
   human ruling, not from the artifact's own §0 operating prompt (REJECT e1 stands).
2. Every CORRECT row in the adjudication is a **binding build constraint**.
3. REJECTs stand: e1 (self-authorization), e3 (Phase 2 bake/cancel — blocked pending
   SideFX; no cancellation API on this build), d6 (cured only by naming a live caller,
   see below), e4 (Phases 3–4 deferred), e7 (worked example must never be fixtured).
4. **Live caller (d6 cure):** `synapse_assess_cache` registers through the existing
   bridge tool registry (`bridge_adapter.py`) and the advice card renders through the
   existing panel result surface. No new orphan panel module. This commitment is
   engineering-delegated and open to CTO review.
5. Human gates unchanged: push, merge, ratified flips, `drop.json` remain per-act
   human words. Nothing in this ruling or any delegation transfers them.

## Wave consequence

Mile 2 = Phase 0 build in worktree `feat/cache-advisor-p0`, local commits only.
Mile 3 = live H22 assay (22.0.400). Mile 4 = Phase 1 advisor + regression sweep.
Phase 2 does not enter this wave.
