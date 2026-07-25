# CTO RULINGS — CTO-RELAY-01

**Ruled** 2026-07-25 · **Authority** Joe, "approved. you are CTO."
**Consumed by** L5. These are decisions, not proposals. Where a ruling reverses or narrows a
question as posed, the reasoning is stated — a ruling that only answers the question asked is
not doing the job.

---

## RULING 1 — Gate 0.1 is SPLIT. The question as posed is half-answered already.

**Posed:** sidecar vs abi3 for the cp311 vendored seam. Open since drop week, brief written,
decision never committed.

**Evidence that reframes it.** `_vendor` ships cp311 **and cp313**. `drop.json` pins the host at
Python **3.13.10**. So inside Houdini 22.0.368, the cp313 wheels *match* — the vendor tree is
live and correct on the surface that ships. The suite that reported 4716/0 ran on **3.14.2**,
where nothing matches and the vendor tree is inactive.

The live defect is therefore **not** the architecture fork. It is that the test interpreter is a
Python the product never runs on. Every green run has been exercising pip-installed
pydantic/anthropic instead of the artifact artists receive.

**Ruled:**
- **1a — immediate, non-architectural.** Pin the suite to the host's Python 3.13. This is a CI
  and tooling change, not a fork, and it needs no architecture gate. Until it lands, no suite
  result may be cited as evidence about vendored behaviour. Label such results
  `VERIFIED-RUNTIME (non-shipping interpreter)`.
- **1b — the fork stays a human gate**, and becomes materially less urgent once 1a lands,
  because the vendor tree will finally be under test. Do not force it now. A fork chosen to
  escape a problem that was actually test-environment drift is a fork chosen for the wrong
  reason.

**Anti-ruling:** do not "fix" this by re-vendoring for 3.14. That chases the test environment
instead of the shipping one.

---

## RULING 2 — D2 ∪ D3 is canonical. D1 is retired.

D1 is 100% by construction: `verified_connectivity_22.0.368.json` contains the entire live
catalogue, so D1 = 218/218 and cannot report anything else. It is not an optimistic number, it
is a number structurally incapable of being false.

**Ruled:** the grounded-coverage denominator is **D2 ∪ D3**. LOP stands at **40/218 = 18.3%**.
D1 is struck from every artifact, dashboard and claim. Any surviving D1 reference is a defect.

**Standing rule, adopted from L1.R5 and applied to myself:** no number enters a governing
document without a producer path beside it. The relay's own "39 of 218" had none, sat in a CTO
document, and was within one node of correct — which is worse than being wrong, because luck is
not a method.

---

## RULING 3 — `Cop` is the target surface. `Cop2` is maintenance-only.

384 live Copernicus types, 0 deprecated, 167 generators, against 169 legacy Cop2 types.

SYNAPSE's moat is access parity with the host. SideFX put H22's centre of mass in Copernicus;
betting the next year of COP work on the legacy surface forfeits parity by choice.

**Ruled:**
- `Cop` (384) is the target. All new COP grounding, emission and semantic work goes here.
- `Cop2` (169) freezes at its current 13.6%. Bugs only. No new coverage investment.
- Coverage reporting states the category explicitly. "COP coverage" as a bare phrase is banned —
  it has meant two different denominators in the same document today.

**Accepted cost:** studios still on COP2-era pipelines get nothing new. `drop.json` targets
22.0.368; that is the bet already placed.

---

## RULING 4 — Author the grounding gate. Highest leverage item in the set.

There is no grounding check for either context. `emitted_node_types.json` has exactly one
consumer in the tree and it is a rigging phrase-scan. The oracles the relay named
(`lop_emission_grounded`, `no_phantom_api`) do not exist.

This is the machinery whose absence let an unsourced number sit in a governing document and
survive to dispatch.

**Ruled:** author both checks into `harness/verify/checks.py`. Per L1, the halves already exist —
`harvest_lop_catalog.py` is a one-symbol swap from a COP harvester and the extractor is
category-agnostic. Scope: emit a coverage integer per category against the live catalogue, and
fail on any emitted type absent from it.

**This is not gap closure and is not gate-refused.** It builds the instrument, not the coverage.

---

## RULING 5 — C.0 stays frozen. The gate is not the blocker; the catalogue is.

L1 delivered the census. Gap *closure* is gate-refused at `flywheel_queue.json:80`
(`ratified:false`), which sits inside the deny fence.

**Ruled: do not flip.** Flipping C.0 alone would close gaps against C.1–C.6, which are armed off
an **H21-vintage capability catalogue for a Houdini build that is no longer installed**. The gate
is not what is stopping good work — a stale base is. Sequence:

1. Re-ratify the context catalogues against 22.0.368 (the LOP and COP catalogues now exist).
2. Then flip C.0.
3. Then close gaps, `Cop`-first per Ruling 3.

The flip remains one boolean and remains yours. I am not reaching into it, and this ruling means
you do not need to today.

---

## RULING 6 — Provenance (task 2.5) blocks the panel change.

Writers are built and dormant — no live callers. Cutting the Review surface (Amendment A1)
removes the only place a decision's reasoning currently appears to a human.

**Ruled: 2.5 wires before L4 ships.** Not "alongside" — before. Shipping A1 first would produce a
panel that is cleaner and tells the artist less about why the agent did what it did. That trade
is unacceptable and it is one I introduced.

If 2.5 cannot land in this relay, L4 ships **without** removing the credit block, and the Review
tab's removal waits. The design is not worth the regression.

---

## RULING 7 — Deprecated LOP emission is a bug, not a flywheel deposit.

`karma` and `karmarenderproperties` are the build's only two deprecated LOPs and SYNAPSE emits
both — the latter in ≥11 places.

**Ruled:** fix as a defect in L2's slipstream, not as a candidate deposit. It is mechanical and
bounded. **Condition:** the successor type must be confirmed by live `dir()` before substitution.
Replacing a deprecated literal with an assumed one converts a decay clock into a phantom, and
that is the failure class this project has already been burned by.

---

## RULING 8 — Namespace the ledger IDs. Live footgun.

`tasks.json` C.3/C.4 (COP/TOP gaps, blocked) collide with `flywheel_queue.json`
C.3-H22-neural-cops / C.4-H22-scaffold-rebuild (`ratified:true`). Same IDs, different work,
opposite gate states. Any dispatch citing "C.3" resolves differently by ledger — and L1 just
worked in that exact namespace.

**Ruled:** prefix flywheel cycle IDs (`FW-C.3`) or task IDs (`T-C.3`). Either, consistently, this
relay. Cheap now; a mis-dispatch later is not.

---

## RULING 9 — `ui/` goes. Rewrite the pin, don't weaken it.

`python/synapse/ui/` (8 files, 1,076 LOC) is dead but held alive by `tests/test_v5_features.py:54`.
Commandment 7 forbids weakening a test to make work pass.

**Ruled:** the test is pinning the wrong thing — it asserts a location, not a behaviour. Rewrite
it to assert the behaviour at its current home in `panel/`, confirm green, then remove `ui/`.
Test count holds or rises. C7 is satisfied in spirit and letter; deleting the test would satisfy
neither.

---

## RULING 10 — Token collision blocks the palette pass. Confirmed.

Already standing in `design/cto_relay_01/L4_COHERE_SPEC.md`. Restated as a ruling: finish the
Mile 7 de-cyan (11 remaining `t.SIGNAL` sites), then make `panel/tokens.py` re-export from
`designsystem/tokens.py` rather than redeclare. One authority. No Cohere rule proceeds first.

---

## RULING 11 — The WS bridge defect outranks everything else in this relay.

L1.F1, `REFUTED-LIVE`: `bridge.json` current (pid 61208, port 9999, today), port Established,
**9 of 9 WebSocket upgrades returned `InvalidStatus`**. Every indicator reads green and the
transport is dead. L1 got its census only by falling back to direct `hou` import.

**Ruled:** L2 diagnoses this before its seam work. It is in the transport layer L2 already
touches, and it is the failure mode with the widest blast radius in the system — a health signal
that reports healthy while the surface it describes is unreachable is worse than an outage,
because it defeats the check that would have caught it.

Escalate to a blocker on the release track. `synapse_doctor` (task 1.5, open) must detect this
exact condition or it is not doing its job.

---

## What is NOT ruled here

- **Gate C — merge to main.** Yours. Untouched.
- **Gate 0.1b — the sidecar/abi3 fork.** Deliberately held per Ruling 1. Ask me again after 1a.
- **`drop.json` MODE flips.** Yours by constitution.

Nine of eleven ruling items are now decided. The two that remain open are open on purpose.
