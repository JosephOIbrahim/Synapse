# CTO-RELAY-01 — THE RULING BLOCK

**Run** `CTO-RELAY-01` · **Branch** `feat/cto-relay-01` · **Delivered** 2026-07-25
**Legs** L0 GROUND · L1 CONTEXT · L2 SOLARIS · L3 PANEL TRUTH · L4 PANEL SKIN
**Status** L0 amber · L1 amber · L2 **red** · L3 amber · L4 amber
**Suite** 4716 → 4744 passed, **0 failed**, 100 skipped. Commandment 7 held throughout, independently re-verified by the orchestrator at each leg.
**Gates** Nothing pushed. Nothing merged. No PR opened. **GATE C is yours.**

> Ranked by **cost of delay**, not by leg order. 18 items.
> A parallel ruling surface exists at `harness/notes/CTO_RULINGS_01.md` (rulings up to R24, written by a concurrent process). This file is the relay's §5 deliverable; reconciling the two is item **R18**.

---

## THE HEADLINE

Three legs went looking for coverage gaps and wiring bugs. They found those. But the two findings that actually matter are about **claims, not code**:

1. **`hou.undos.group` is a grouping primitive, not a transaction.** It does not roll back on the exception path — and it never promised to. SYNAPSE's stated core guarantee, *"every mutation is reversible,"* is **overstated as written**. This is misuse, not a Houdini regression.
2. **Three panel affordances report safety decisions they did not make.** COMMIT-to-/stage announces consent-gate routing that never happens; gate Approve and Reject fire their "decided" signal unconditionally after a swallowed exception.

SYNAPSE's differentiator is receipts. Both findings attack the receipt.

---

## R1 · The reversibility guarantee is overstated

**Question.** `hou.undos.group` groups undo entries; it does not roll back when the wrapped block raises. L2 proved it live: failed Solaris builds orphan partial networks and the undo group does not clean up. CLAUDE.md §1.1 states the Undo Safety anchor as *"Every mutation wrapped in `hou.undos.group()`"* and the core guarantee as *"every mutation is reversible."* **Wrapping is not reversing.** On the exception path SYNAPSE produces a partial network, an undo entry that may or may not restore it, and an `IntegrityBlock` reporting `undo_group_active=True` with fidelity 1.0 — for a state that was never reversed.

**Options.**
1. Correct the doc now, then implement explicit unwind (delete-what-we-created bookkeeping) behind a probe.
2. Implement unwind first, leave the doc.
3. Accept grouping as the guarantee and rewrite the claim to what it actually delivers.

**Recommendation.** **Option 1.** Correct the claim today — it costs a paragraph and it stops the overstatement propagating into release copy. Then probe the unwind: firing undo from an exception handler on the main thread has its own hazards, and this project already has a logged marshal-deadlock class. Do not ship a reflexive `performUndo()` without one.

**Cost of delay.** Highest in the relay. Every day the doc stands, the claim can end up in a demo, a README, or a patent filing. It is also the one defect that, if a customer found it, would be read as dishonesty rather than a bug.

**What unblocks it.** `CLAUDE.md` §1/§1.1, `shared/bridge.py` (human-authored — the relay did not touch it).

---

## R2 · Three panel surfaces lie about consent

**Question.** COMMIT-TO-/STAGE announces *"routing through the consent gate"* and creates no `GateProposal`, issues no `/stage` write, queues nothing — it sets a UI substate (`synapse_panel.py:1180`). Gate Approve and Gate Reject call `mark_decided()` and emit `decision_announced` **unconditionally**, after an `except` that only logs (`gate_widget.py:490`, `:509`). If `HumanGate` is absent or `decide()` raises, the artist sees a decision that never reached the gate. A rejection that never landed still reads as rejected.

**Options.**
1. Hotfix the two gate paths now (three lines that should be conditional); fold COMMIT into the R3 doctrine work.
2. Fix all three together under the R3 contract.
3. Defer to post-T.1.

**Recommendation.** **Option 1.** The gate widget fix is small, safe and high-value — make the unconditional emits conditional on the gate call succeeding. COMMIT is a larger missing implementation and belongs with R3.

**Cost of delay.** Extreme. This is consent theatre on the exact surface whose purpose is receipts. It is worse than a missing feature because it actively misinforms.

**What unblocks it.** `python/synapse/panel/gate_widget.py:490`.

---

## R3 · Does a failed operation owe the caller truth, and a clean network?

**Question.** A doctrine question the relay hit from three directions. L2: failures orphan partial state, and the idempotency guard then latches onto that wreckage — *including another tool's wreckage* — and reports `already_exists` forever, so `import_megascans` never imports anything yet reports success permanently. L2 again: `set_purpose` returns `status="set"` having set nothing. L3: four panel affordances return success having done nothing. SIDEFX-CTO adds the compounding case: locked-HDA `createNode` failures are now a live exception class, and those exceptions leave orphans.

**Options.**
1. Ratify one contract: a failed operation destroys what it created before re-raising, and never returns a success status for a no-op.
2. Per-surface decisions.
3. Accept — partial state is the artist's to clean up.

**Recommendation.** **Option 1, ratified as a family-wide law.** This is CLAUDE.md §11.6 *"Fidelity = 1.0 or stop"* applied literally. It binds far beyond Solaris, and it is the same root as R1 and R2 — three legs found one disease.

**Cost of delay.** Very high and compounding: every new tool inherits the pattern.

**What unblocks it.** A written contract in `CLAUDE.md`, then `python/synapse/mcp/tools/solaris/*`.

---

## R4 · Copernicus is a rewrite, not a port — hold all COP work behind one probe

**Question.** L1 gave COPs their first coverage number: **6.2% of 384 live `Cop` types, 13.6% of 169 `Cop2`, zero semantic grounding for either.** The obvious response is a grounding sprint. SIDEFX-CTO says stop: `hou.CopNode` and `hou.Cop2Node` are **different data models, not two versions of one API.** Copernicus's HOM surface is a SOP-shaped verb/layer/cable model — `layer()`, `geometry()`, `vdb()`, `verb()`, `cable()`, `outputDataTypes()`. It has **no `planes()`, no pixel read, no `saveImage()`**. The pixels live on the GPU and SideFX deliberately exposed no CPU scrape path. Meanwhile SideFX has publicly committed to deprecating and removing the legacy COP network.

**Options.**
1. Run one probe first — *how do you get an image out of a Copernicus node from HOM on 22.0.368* — and scope all COP work behind the answer.
2. Ground the 384 `Cop` types now, resolve contracts later.
3. Target `Cop2` where SYNAPSE's 17 existing handler literals already live.

**Recommendation.** **Option 1, emphatically.** Option 3 is writing a year of work against a surface SideFX has committed to deleting. Option 2 grounds 384 types against a contract the tool inventory does not match — any SYNAPSE COP tool whose contract is *"read pixels / enumerate planes / save an image"* has **no Copernicus destination** and needs re-specification, not porting.

**Cost of delay.** High but inverted: **delay is cheaper than haste here.** The wrong answer costs a year.

**What unblocks it.** One hython probe. Then the COP half of C.1–C.6.

---

## R5 · Typed COP cables invalidate the wiring model

**Question.** `hou.CopNode` exposes `cable()`, `inputCableStructure()`, `inputDataTypes()`, `outputDataTypes()` — a **typed, structured connection model** where cables carry declared data types. Nothing in SYNAPSE's wiring layer models typed ports; every connectivity catalogue assumes untyped index-to-index wiring. Copernicus networks will "connect" successfully and be semantically wrong.

**Options.**
1. Probe the cable/type model and extend the connectivity schema before any COP wiring work.
2. Wire untyped and validate after.
3. Defer with R4.

**Recommendation.** **Option 1, folded into R4's single probe.** Same trip, same interpreter.

**Cost of delay.** High — it is the COP-side twin of the ambiguity in R6: connects fine, wrong graph, no exception.

**What unblocks it.** The R4 probe.

---

## R6 · Ambiguous type names create wrong nodes silently

**Question.** **41 of 97** emitted type names resolve in two or more node categories; `null` and `subnet` resolve in **all ten**. The emission corpus records no category axis. Today the right node gets made by luck of call-site ordering. The moment a recipe builds in the wrong network context it creates a real node of the wrong flavour and **succeeds** — no exception, wrong graph, no signal.

**Options.**
1. Category-qualify every entry in the emission catalogue; make `createNode` assert the resolved category.
2. Qualify the catalogue only.
3. Leave.

**Recommendation.** **Option 1.** This is the quietest bug class the relay found, and the fix is mechanical — L1's disambiguation probe already produced the per-name category resolution for all 97.

**Cost of delay.** High. Failures are invisible by construction, so the bug count is unknown rather than low.

**What unblocks it.** `python/synapse/cognitive/tools/data/emitted_node_types.json`.

---

## R7 · The test suite certifies a code path production never runs

**Question.** The suite runs on system Python **3.14.2**, where the vendored cp311+cp313 tree is **ABI-INACTIVE** (warning on every run). `drop.json` declares the supported runtime as **3.13.10**. H22's bundled python313 cannot currently run the suite — 54 collection errors from missing test dependencies. So every test touching a vendored extension exercises the pure-Python fallback: **the fallback is pinned and the production path is untested.** 4744 green tests are green for the wrong reason.

**Options.**
1. Install the test dependencies into H22's bundled python313 and make `$HFS/bin/hython` the canonical suite runner.
2. Keep 3.14.2 as the runner and accept the vendored tree is untested.
3. Go sidecar — own pinned interpreter, decoupled from Houdini's Python permanently.

**Recommendation.** **Option 1 now, option 3 as the architecture call.** SIDEFX-CTO's read: vendoring against a Houdini-bundled Python is a per-major re-vendor tax forever, since SideFX moves the bundled Python on major boundaries and does not commit to abi3. This finding is evidence for the sidecar — which is the gate-0.1 decision already on the books.

**Cost of delay.** High and silent. Every green run increases confidence in evidence that does not cover the shipped path.

**What unblocks it.** Test-dependency install into `$HFS/python313`.

---

## R8 · L2 delivered evidence that certifies nothing yet

**Question.** L2 shipped five Solaris wiring verifiers and **+28 green tests**. Then SEAM-HUNTER showed the greens are largely hollow: the **static tier never reads the tool** — every expected topology is a hand-written literal graded against the catalogue, never against `execute()`; the declared topology has 7 nodes, the tool emits 6, and `verify_static` still says PASS. The **live tier grades only the child delta**, so damage to pre-existing nodes is structurally invisible — three tools into one `/stage` leaving 4 terminal LOPs returned PASS with an empty failure list. And **one of the 28 new tests pins a defect that live probing refutes** (`copyNodesTo` does carry inputs on 22.0.368).

**Options.**
1. Re-derive every expected topology from live emission, grade the whole network not the delta, retire the false pin.
2. Rename them as documentation tests so they stop claiming to verify.
3. Revert the leg.

**Recommendation.** **Option 1. Do not revert.** The verifiers can all go red and the live tier works — what is missing is that the static tier compares a hand-written literal against the catalogue instead of against the tool. That is a fixable seam, not a design failure, and L2's findings are the single most valuable output of the whole relay.

**Cost of delay.** High and actively misleading: 28 green tests currently certify nothing about Solaris wiring, which is the exact *"isolated-green hides composed regressions"* failure the seam-gate exists to prevent.

**What unblocks it.** `tests/test_solaris_wiring_verifiers.py:139`, `python/synapse/validation/solaris/verify_wiring_common.py`.

---

## R9 · Five Solaris tools are unreachable, and their tests are never collected

**Question.** None of the five appear in the MCP registry — zero matches in `_tool_registry.py`. Their tests live in `synapse/tests/solaris/`, which `pyproject.toml:102` (`testpaths=["tests"]`) never collects, and they are mock-only anyway. That is the root cause the rest sits on: a mock `hou` cannot raise `PermissionError` or report a missing parm, which is why `import_megascans` (cannot run at all) and `set_purpose` (sets nothing) survived. `import_megascans` additionally creates SOPs directly inside `componentgeometry` instead of its `sopnet/geo` child, hitting the locked-asset contract.

**Options.**
1. Register the tools, move their tests under `tests/`, repair the wiring bugs — finish an undelivered feature.
2. Quarantine the tree and strike the "five Solaris tools delivered" claim.
3. Leave.

**Recommendation.** **Decide only after R8.** Registering tools behind vacuous verifiers converts unreachable-and-broken into **reachable**-and-broken, which is strictly worse. If the appetite for the repair is not there, option 2 is honest and cheap.

**Cost of delay.** Medium — nothing is reachable today, so nothing breaks for users. The live cost is a false capability claim.

**What unblocks it.** R8, then `python/synapse/mcp/_tool_registry.py`.

---

## R10 · Emergency halt has no artist-reachable surface

**Question.** CLAUDE.md Safety Rule 11 says *"Emergency halt is immediate."* HALT exists only in `chat_panel.py:595` — the tree whose loader is never installed. **The shipped panel has no halt control.**

**Options.**
1. Restore HALT to `synapse_panel.py` as a persistent affordance.
2. Accept LLM-mediated halt.
3. Add it to the Ctrl+K palette.

**Recommendation.** **Option 1.** A stop button you have to search for is not a stop button, which rules out option 3. This is the one ORPHAN worth reviving on safety grounds, and reviving a single safety control is **not** a T.4 product-identity decision.

**Cost of delay.** High — a stated safety rule with no implementation on the shipped surface.

**What unblocks it.** `python/synapse/panel/synapse_panel.py`.

---

## R11 · Twenty-one slash commands send prose instead of dispatching

**Question.** Each palette entry's `send` string is its **description text**, not a dispatch (`tool_palette.py:119`). Picking `/diagnose` sends prose to the LLM; `scene_doctor.py` (737 LOC) never runs. This bypasses ~7,500 LOC of implemented feature modules across 21 commands.

**Options.**
1. Wire the entries to real dispatch.
2. Remove them from the palette until they dispatch.
3. Leave.

**Recommendation.** **Option 2 now, option 1 later.** Removal is honest and cheap; wiring 21 entries is real work. A menu entry that silently does something other than its name is precisely what L4's own scope fence calls *"how a panel lies."*

**Cost of delay.** Medium-high. Every use is a silent capability failure the artist reads as an LLM shortcoming.

**What unblocks it.** `python/synapse/panel/tool_palette.py:119`.

---

## R12 · SYNAPSE is a major behind on Karma, and the successor is named

**Question.** `karma` and `karmarenderproperties` are the **only two deprecated LOPs** on 22.0.368, and SYNAPSE emits `karmarenderproperties` in **≥11 places**. SideFX's docs are explicit: *"deprecated … scheduled to be deleted in an upcoming revision. Replaced by Karma Render Settings and USD Render. (Since version 21.0.)"* The successor is `karmarendersettings`, which **is** live. The split is structural — scene configuration (LOP) separated from render execution (ROP) — so it is **not** a like-for-like parm swap. A recipe assuming the old node's product-authoring parms will silently author nothing.

**Options.**
1. Probe `karmarendersettings`' parm set, then migrate all 11 sites.
2. Deposit as a candidate and migrate after the C.0 ruling.
3. Accept — deprecated is not removed.

**Recommendation.** **Option 1.** Deprecated *since 21.0* means SYNAPSE is a major behind, not merely current-with-a-warning. This is the class of thing that becomes a phantom at the next major, and this project has been burned by exactly that before.

**Cost of delay.** Low today, total at the next Houdini major.

**What unblocks it.** A parm-set probe on `karmarendersettings`.

---

## R13 · L1's gap closure is gate-refused, and the gate is inside the fence

**Question.** GATEWARDEN REFUSED the per-context capability rebuild and gap closure: `flywheel_queue.json:80`, cycle C.0, `"ratified": false`. That file sits inside the deny-list fence, so the agent cannot — and must not — flip its own gate. L1 therefore delivered the census and stopped.

**Options.**
1. Flip C.0 and close the top-5 gaps in a follow-on leg.
2. Leave frozen — the census was the deliverable.
3. Flip C.0 **and** re-ratify the H21-vintage catalogues C.1–C.6 depend on.

**Recommendation.** **Option 3, sequenced.** The census now exists on H22 truth, but C.1–C.6 are still armed off an H21 catalogue for an **uninstalled** build. Flipping C.0 alone would close gaps against a stale base. Re-ratify first, then flip. And hold the COP half behind R4.

**Cost of delay.** Medium.

**What unblocks it.** One boolean: `harness/state/flywheel_queue.json:80`.

---

## R14 · Live verification is owed for the entire panel arc

**Question.** `hython.exe` was **permission-denied throughout both L3 and L4**. Two of five G3 slices — the live offscreen build and the v9 invariants — have neither a baseline nor an after-state. No screenshots were produced. Nothing in the restyle has been seen rendering: QSS parsing, glyph rasterisation, real font metrics, gradient appearance all unverified. `drawArc`/`drawPath`/`Qt.PenCapStyle.RoundCap` were newly emitted and remain UNVERIFIED-LIVE.

**Options.**
1. Grant the hython-offscreen invocation, re-run G3, produce the screenshot diffs.
2. Accept L4 on static + full-suite evidence and verify at next Houdini launch.
3. Revert L4.

**Recommendation.** **Option 1 — the cheapest unblock in the relay**, being a permission grant rather than engineering work. Panel verification is hython-offscreen-only by standing convention, and the two ungraded slices are exactly the ones that catch interactive-target and same-pane-law regressions. Do not revert: the suite is green, all 162 tokens are intact, and the changes are token-level and reversible.

**Cost of delay.** L4 ships unverifiable on 40% of its own gate; defects surface to you in the live panel instead of to the harness.

**What unblocks it.** A permission grant for `hython.exe`.

---

## R15 · The live WS bridge advertises a service it does not provide

**Question.** `~/.synapse/bridge.json` is fresh (pid 61208, port 9999, today's timestamp) and the port is open — but **9 of 9** WebSocket upgrades return `HTTP 400` and **4 of 4** plain HTTP paths return 404. Something HTTP-ish holds the port and does not serve the SYNAPSE transport. The SessionStart hook reported *"bridge connected."* Mitigating: L3 proved the panel dispatches **in-process**, so panel capability is not gated by this.

**Options.**
1. Fix the sidecar handshake so a stale/wrong listener cannot present as connected.
2. Make the SessionStart hook ping rather than read the sidecar file.
3. Both.

**Recommendation.** **Option 3.** The sidecar advertising a bridge that does not serve is the defect; the hook trusting the file without a ping is what makes it invisible. Cheap on both sides.

**Cost of delay.** Medium. It cost this relay real time — every leg needing live truth fell back to hython.

**What unblocks it.** `~/.synapse/bridge.json` handshake + the SessionStart hook.

---

## R16 · The harness has no completion memory

**Question.** `harness/state/done.json` — the `run.ts` completion ledger — **does not exist**. There is no machine-recorded completion claim for any of the 80 tasks; L0's reconcile (30 done / 44 open / 0 stale / 6 superseded) is static reconstruction from git log and verdict files.

**Options.**
1. Seed `done.json` from the 30 `done` verdicts.
2. Track `harness/notes/ledger_truth.json` as the durable ledger and have `run.ts` read it.
3. Leave memoryless.

**Recommendation.** **Option 2.** An untracked ledger under `harness/state/` is exactly why the last one vanished. Put the ledger where it is version-controlled.

**Cost of delay.** Medium — every harness run re-attempts 30 banked tasks.

**What unblocks it.** `harness/notes/ledger_truth.json` (written by L0), `harness/run.ts:64`.

---

## R17 · Public-claim accuracy: three claims that measurement corrected

**Question.** Three documented claims did not survive probing. (a) `providers/` is **1,506 LOC, not 136**, with all five engines implemented — but only **one** (claude) works without configuration. (b) The relay's *"39 of 218 = 18%"* LOP coverage has **no producing script and no artifact** anywhere in the tree; the live number is 40/218 = **18.3%**, so the prose was approximately right and entirely unsourced. (c) `ui/` is **1,347 LOC, not 1,076**, and the import graph **confirms** it is dead — zero functional inbound imports; the only thing keeping it alive is an import-smoke test.

**Options.**
1. Restate all three: "five engines, one configured out of the box"; quote 18.3% with its basis named; archive `ui/`.
2. Fix the code instead of the claims.
3. Leave.

**Recommendation.** **Option 1.** For providers the code is not the problem — the out-of-box experience is, and *"five swappable engines"* is true and misleading at once. For coverage, the defect is not the number but that a number with no producer sat in a governing document. Archive `ui/` — the claim that it is dead is correct, so make the tree match.

**Cost of delay.** Low individually; corrosive in aggregate. Unsourced numbers in governing documents is the failure mode that produced this item.

**What unblocks it.** `README.md`, `docs/reviews/solaris-wiring-gap-ledger-2026-07-21.md:198`, `python/synapse/ui/`.

---

## R18 · Housekeeping — five decisions that need one word each

**Question.** Five small items, batched to avoid five interruptions.

| # | Item | Recommendation |
|---|---|---|
| a | **Issue #3** "Installation issues", 88 days open. Does **not** reproduce — root cause was a missing `hpath` entry pointing Houdini at `<repo>/houdini`; `install_synapse_package.py --verify` now asserts exactly that. | **Close** with the installer comment. It is the only open public thread on the repo. |
| b | **Root hygiene.** 8 delete-classed tracked dirs (`_solaris_fix/`, `SYNAPSE-asm-*` ×4, `SYNAPSE-fx-*` ×3 = 11 tracked files, all md5-identical duplicates). **`untitled.hip/` must NOT be deleted** — it is the live unsaved-scene memory store, despite appearing on the relay's own suspect list. `_cto_recon.py` does not exist. | **Archive branch, then delete.** Nothing was deleted this run. |
| c | **`checks.py` oracles.** The relay cites `--all` and `--check X`; the real CLI is `--task/--worktree`, and `lop_emission_grounded`/`no_phantom_api` **do not exist**. Three legs had literally unrunnable acceptance criteria. | **Amend the relay doc**, and author real grounding checks (R6's fix supplies the machinery). |
| d | **Branch contention.** A concurrent process committed four times to `feat/cto-relay-01` mid-run and silently undid a `git reset --soft`, costing L4 its commit granularity. | **Per-leg worktrees.** The relay's premise is context isolation; branch isolation is the missing half. |
| e | **Two ruling surfaces.** `harness/notes/CTO_RULINGS_01.md` (R1–R24, concurrent process) and this file. | **Reconcile into one.** Two ruling surfaces for one run defeats the purpose of batching. |

**Cost of delay.** Low each. (a) is public-facing; (d) risks losing work on every future run.

---

## STILL FROZEN — not decided, by design

**T.4 — panel: product or reference implementation.** Untouched. Three concordant sources hold the freeze, GATEWARDEN re-confirmed it, and both panel legs explicitly declined any product-identity assertion. **Do not decide until T.1 and T.2 land.**

Consequence worth naming: L4 was instructed to *remove* ORPHAN affordances from the surface. All 17 are the `chat_panel.py` tree, already invisible because its loader is never installed. Removing it would decide what belongs on the product surface — a T.4 call. **The freeze won: they were neither restyled nor removed.** That tension is recorded as drift D-R8 and resolves itself once T.4 unfreezes.

---

## WHAT THE RELAY DID NOT DO

Stated plainly, so nothing is assumed finished:

- **Closed zero LOP/COP gaps** — gate-refused at C.0. The census is the deliverable.
- **Fixed zero Solaris source bugs** — gate condition was evidence-only. All 11 are deposited.
- **Removed nothing** in the root hygiene census — classify-only, as instructed.
- **Produced no screenshots** and verified nothing rendering — hython denied.
- **Pushed nothing, merged nothing, opened no PR.** GATE C is yours.

---

## THE THREE THINGS, IF YOU ONLY DO THREE

1. **R1** — correct the reversibility claim. A paragraph, today, before it reaches release copy.
2. **R2** — make the two gate emits conditional. Three lines. It is the difference between a consent gate and consent theatre.
3. **R14** — grant the hython permission. It is not engineering work, and it unblocks the verification the last two legs are missing.
