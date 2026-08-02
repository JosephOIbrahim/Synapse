# CTO RULINGS — DECISION-LIST TAKEOVER

**Ruled** 2026-08-02 · **Authority** Joe, "Can you take over as CTO on the decision list"
**Scope** the standing decision list as of master `9d7bd17` (post PR #66; PRs #67/#68 closed with receipts).
These are decisions, not proposals. Each names its executor: LANE (dispatched now), INLINE (done in this
sitting), or PASTE (fenced file — the decision is made here; the file edit stays human by the anti-runaway
anchor's own design, which survives delegation because its purpose is that no agent hand writes `ratified`,
however authorized the agent).

---

## R201 — The phantom-sweep review branches MERGE, gates executed, not waved

`clear/l5-phantom-scanner` (now @ `65fbe73`: scanner + salvage + the unwalked-pxr soundness fix, 29/29) and
`fix/corpus-usdrender-rop` (14 commits, thrice-attacked SOUND on 2026-07-31) have been "in review" since
July 31 while master moved ~20 merges past them. A review branch that rots is worse than either merging or
rejecting it.

**Ruling:** merge both — with the named gates from `harness/phantoms/QUARANTINE-PACKET-2026-07-31.md`
executed as merge *conditions*, not waved: corpus digest rebuild, quarantine-list population, and the
hdefereval headless-blind allowlist carried with the L5 merge. Each branch first absorbs current master and
proves the full suite green on the merged result. If a gate condition turns out to be unexecutable as
documented, that lane REFUSES and reports — a refusal correcting the packet is a better outcome than a
merge that fakes a gate. **Executor: LANE ×2 + crucible each.**

## R202 — protocol.py: cut, but only after the gate-map truth is traced

The retire round left `python/synapse/agent/protocol.py` alive because `tests/test_set_usd_primvar.py:266`
imports `DEFAULT_GATE_LEVELS` / `classify_gate_level`. That test's own comment calls it "Wiring site 1:
gate map (protocol.py)" — which means it may be pinning a gate table that **nothing live consults** (the
agent subsystem around it is deleted; the live gate authority is the bridge/`shared/constants.py` family).
A test asserting REVIEW in a dead table is pinning a fiction and hiding it under a green check.

**Ruling:** trace where `set_usd_primvar`'s gate level is *actually* enforced at runtime. If protocol.py's
map is dead wiring: repoint the test at the live authority (preserving test independence — expected values
stated literally in the test, never read from the module under test), delete `python/synapse/agent/`
entirely, tombstone note in the commit. If the map turns out live: REFUSE, report the consumer, ruling
void. **Executor: LANE + crucible.**

## R203 — The seven H21-probed capabilities get their H22 records

PR #68's triage confirmed all seven scout capabilities live on master — verified on **H21.0.671 only**.
House rule: re-probe per build.

**Ruling:** symbol-table + registry re-verification of all seven against H22 (`22.0.397` table, 35,908
symbols): every `hou.*`/`pdg.*` call each handler emits, checked; any phantom → named for quarantine.
Read-only. **Executor: LANE.**

## R204 — H4 (panel IntegrityBlock readout) is RATIFIED as the next panel build — and not built tonight

The last `!1 attention` is real: the receipts are the product differentiator (`harness/CLAUDE.md`: "every
action reversible and **recorded**" — recorded-but-invisible is half a promise). **Ruling:** ratified as
the next panel work item, to be built in a fresh session under the panel discipline (hython-offscreen
verification, full-suite gate — the panel-redesign memory's rules). The bar keeps showing `!1` until it
ships; that is the bar telling the truth. **Executor: queued, next session.**

## R205 — Flywheel decisions (fenced file → PASTE hunks below)

Decided now, recorded here; `flywheel_queue.json` receives them by human paste per its own `_doc`.

- **C-substrate: ADD + RATIFY.** The RL-3 ruling is executed reality (C-0 merged, backend live).
- **C.0 (context-capability probe): DEFER.** Real value, wrong moment — behind R201 and R204. Reopen
  condition: both landed.
- **U.2 (parm-name truth): RATIFY.** Phantom parms are the #1 failure family's nearest sibling; the
  catalog already carries the fingerprints. One cycle, real defect class.
- **U.3 / U.4 (output-index + arity guard): DEFER** until U.2 lands — same machinery, sequenced, or the
  queue becomes theater again.

**Paste-ready hunks** (append to `cycles` / edit in place):

```json
{"id": "C.SUB", "title": "Memory substrate: moneta ratified (RATIFY-AND-STABILIZE); C-0 address fix merged PR #60",
 "status": "done", "ratified": true,
 "evidence": ["harness/rsi/briefs/C-substrate-decision-brief-2026-08-01.md", "harness/notes/CTO_RULINGS_02.md#R205"],
 "note": "Ruled 2026-08-01/02 under delegated CTO authority; human paste = the ratified flip."}
```
```
C.0  -> add: "deferred": true, "note": "DEFERRED 2026-08-02 (CTO_RULINGS_02 R205): reopen after R201 merges + H4 ships."
U.2  -> set: "ratified": true   (note: RATIFIED 2026-08-02 per CTO_RULINGS_02 R205)
U.3  -> add: "deferred": true   (reopen: U.2 landed)
U.4  -> add: "deferred": true   (reopen: U.2 landed)
```

## R206 — legs.json: dead worktree paths cleared

The 13 closed/orphaned legs still point at deleted husk directories. Harmless today, but a stale path is a
future false-armed waiting for any directory to reappear. **Ruling:** clear `worktree` on legs whose state
is `done`/`held` and whose path no longer exists. **Executor: INLINE.**

## R207 — The 286 decisions board: no bulk action, ever

The resolution channel (#58) is the only exit, one item at a time, evidence per entry. A bulk sweep would
recreate the false-open problem in reverse. **Ruling:** standing instruction, no action.
