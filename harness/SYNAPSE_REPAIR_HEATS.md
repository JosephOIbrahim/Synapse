# SYNAPSE — REPAIR HEATS 01

**Harness ID** `REPAIR-01` · **Authored** 2026-07-25 · **Supersedes nothing; follows CTO-RELAY-01**
**Governed by** `harness/AGENT_CONSTITUTION.md` — read it first, it binds every agent here.
**Ruled by** `harness/notes/CTO_RULINGS_01.md` R1–R38. Those are decided. Execute, do not re-open.
**Baseline** `master @ 4abf68a` · pushed · 4873 passed / 128 skipped / 0 failed (system 3.14.2)

---

## 0 · Why this is shaped differently from CTO-RELAY-01

The relay was a **diagnostic instrument**. Six legs in a chain, discover state, batch decisions.
That shape was right because nothing was known.

This is a **repair instrument**, and the findings already exist. A chain would be wrong here —
the work is not sequential, it is *conditional*. So:

> **Nothing is repaired before it can be measured.**

That is the whole organizing principle, and it is not a preference. A repair you cannot verify
is a claim, not a fix — and today produced four of exactly those: F4 was "fixed" with a test
that could not fail; L1.F1 sent a healthy transport to the top of a ruling block; a Stop button
was ruled missing while sitting in the live rail; the panel was ruled untestable when one
neighbour file was poisoning it.

Every one was reproducible. **Reproducibility is what made them convincing.**

### The DAG, and why it is a DAG

    QUALIFIER  (blocking)          HEATS (parallel)              FINAL (converge)
    ─────────────────────          ────────────────              ────────────────
    Q1 unpoison the suite  ──┬──►  H1  schemas      ──┐
    Q2 shipping baseline     ├──►  H2  re-qualify   ──┼──►  F1  integrate + housekeep
                             └──►  H3  cook-cancel  ──┘      F2  tag decision
                                    (own worktrees)

Q gates everything because measurement gates verification. H1/H2/H3 touch disjoint surfaces and
run **simultaneously in separate worktrees** — Article V, now actually safe since the
`pythonpath` fix landed on master. F converges.

**This is what "dynamic workflow" means here, and it is not decoration:** the heats' scope is
*determined by Q's output*, not fixed in advance. See §4.

---

## 1 · Standing orders — the ones today paid for

- **Positive control before any finding is acted on.** If a probe cannot demonstrate success
  against a known-good target, its failure is uninterpretable. Nine identical failures are one
  failure with a sample size. *(D-R10, R34)*
- **Mutation testing on every regression pin.** A pin must be shown to FAIL against a
  deliberately broken implementation. A test that passes on both the fix and its inverse is a
  decoration. *(R34)*
- **Every check states its failure condition before it is written.** *(Law 1)*
- **Every number carries a producer path and an interpreter.** *(Law 2, R31)*
- **`status` describes what happened, never what was attempted.** *(Law 3)*
- **Commandment 7.** Test count strictly increases or holds. Fix forward.
- **Receipts record `model` and `settings_profile`.** *(R25)*
- **The constitution ships on the branch it governs.** Cherry-pick at worktree creation. *(R38)*
- **Never push, never merge, never tag.** Gate C was taken once today, by Joe's delegation, for
  a verified fast-forward. It is not open standing.

---

## 2 · The team

Use the thirteen in `.claude/agents/`. Do not invent roles. Article IV binds.

| Stage | Agents, in order |
|---|---|
| **Q1** unpoison | `cartographer` → `assayer` → `h22-forge` → `crucible` |
| **Q2** baseline | `h22-gatewarden` → `h22-forge` |
| **H1** schemas | `cartographer` → `h22-forge` → `crucible` |
| **H2** re-qualify | `assayer` → `seam-hunter` |
| **H3** cook-cancel | `prospector` → `assayer` → `h22-forge` → `seam-hunter` |
| **F1** integrate | `h22-gatewarden` → `crucible` |
| **F2** tag call | `sidefx-cto` → `h22-docsurgeon` |

ORCHESTRATOR holds receipts only, never reads source. One agent per Task subagent, never nested.
Skills per Article V. `rlm-navigator` mandatory above 50k tokens.

---

## 3 · QUALIFIER — blocking. Nothing else starts until both are green.

### Q1 · Unpoison the suite

**Anchor** `tests/test_hda_panel.py:20-40` plants `sys.modules["hou"]`, `["hdefereval"]`, and
per R30 the PySide6 family, at **module scope**. `:159-161` deletes keys — but pytest imports
every test module at collection, so the plant is resident before any panel test runs. R30's
minimal repro: `tests/panel/` alone → 27 passed; `tests/panel/ + test_hda_panel.py` → access
violation in `QApplication::font()`.

**Work**
1. `assayer` confirms the mechanism live under `hython3.13` before any edit. **Reproduce the
   crash first.** A fix for an unreproduced defect is F4 again.
2. Convert module-level stubbing to fixture scope with guaranteed teardown, **or** move the file
   to its own pytest session. Either is acceptable.
3. **Forbidden:** reordering tests, `-p no:randomly`, marking panel tests skip, or adding PySide
   to the dev environment. Each hides the coupling instead of removing it.

**Oracle — positive control on both sides, non-negotiable**
```
hython3.13 -m pytest tests/panel/                      -> passes (control: worked before)
hython3.13 -m pytest tests/panel/ tests/test_hda_panel.py -> passes (the fix)
hython3.13 -m pytest tests/test_hda_panel.py           -> passes (control: not broken by fix)
python     -m pytest -q                                -> 4873+ passed, 0 failed
```
All four. Three passing and one skipped is a failed leg.

**Receipt** `harness/notes/receipts/Q1.json`. **Exit** the shipping interpreter can run the suite.

### Q2 · The shipping baseline — a number that has never existed

**Anchor** `harness/verify/suite_baseline.json` reads `passed: 4275`, generated 2026-07-14.
HEAD is **4873**. The ratchet guardrail (`checks.py::check_suite_baseline`) has been comparing
against a floor **598 tests stale** — structurally unable to catch any regression smaller than
that. It is Law 1's failure mode in the guardrail that exists to enforce Law 1.

**Work**
1. Rewrite `suite_baseline.json` to the R31 tuple shape. **Both baselines required:**
   ```json
   {
     "gate":     { "interpreter": "system 3.14.2", "passed": N, "failed": 0, "skipped": N,
                   "commit": "sha", "producer": "python -m pytest -q" },
     "shipping": { "interpreter": "hython3.13 / 3.13.10", "passed": N, "failed": N, "skipped": N,
                   "commit": "sha", "producer": "harness/run_suite_shipping_python.ps1" }
   }
   ```
2. Update `checks.py::check_suite_baseline` to read the tuple. It must fail loudly on a bare
   integer rather than silently accepting the old shape.
3. The SHIPPING number is measured **after Q1**, on `hython3.13`, at HEAD. Record it even if it
   is lower than the gate number — especially then.

**Oracle**
```
suite_baseline.json parses; both keys present; both carry interpreter + commit + producer
checks.py --task <ID> --worktree . --mode B   -> green, and FAILS if fed the old scalar shape
```

**Receipt** `Q2.json`. **Exit** a release claim can cite a shipping number for the first time.

---

## 4 · HEATS — parallel, own worktrees. Scope is set by Q, not by this document.

**This is the dynamic part, and it is load-bearing.** Q2's shipping number determines what the
heats actually do:

| Q2 shipping result | Consequence |
|---|---|
| shipping ≈ gate (within ~2%) | run H1, H2, H3 as written below |
| shipping materially < gate | **STOP. The delta is the finding.** A large gap means whole modules do not load on the shipping interpreter. That outranks all three heats; re-scope H1 to diagnose it and hold H2/H3. |
| shipping > gate | investigate before proceeding — the gate suite is skipping something the shipping one runs |

The orchestrator makes this call from Q2's receipt and records the branch taken in `F1.json`.
**Do not run the heats blind.**

Each heat gets its own worktree: `git worktree add -b <branch> .claude/worktrees/<name> master`,
then cherry-pick `AGENT_CONSTITUTION.md` and `CTO_RULINGS_01.md` onto it (R38).

### H1 · Wire the schemas — `feat/repair-schemas`

Six `schema_*.py` under `python/synapse/mcp/tool_impls/solaris/`, **zero consumers**
(`grep TOOL_RETURN` outside the schema files finds nothing). `set_purpose`'s declared enum
`[set, already_set, not_found]` has drifted from an implementation returning
`set|updated|unchanged|noop|not_found`.

This is a **correctness surface, not documentation**: the schema is what the model is told a
tool returns, and it then reasons on it. A drifted schema misinforms the agent.

**Work** — extend M5's `test_schema_matches_implementation_contract` to all five real tools.
`schema_tool_audit.py` is excluded: F2 established `tool_audit` is a design document, not a tool.
**The test must fail on today's `set_purpose` drift before it counts as done.**

### H2 · Re-qualify F1–F11 — `feat/repair-requalify`

F4's premise is `REFUTED-LIVE`. One in eleven was a phantom, repaired with a green test that
could not fail. The other ten share its provenance and have not been individually re-probed.

**Work** — `assayer` re-probes each of F1–F11 against 22.0.368. Each returns
`CONFIRMED | REFUTED | UNVERIFIABLE` with a `file:line` anchor. Then `seam-hunter` applies
mutation testing to every existing regression pin: break the implementation deliberately,
confirm the pin fails. **Any pin that survives its own mutation is a decoration and is reported
as a finding, not quietly fixed.**

### H3 · Cook-cancel — `feat/repair-cook-cancel`

The real safety gap (R29). `_on_stop` aborts the agent loop cooperatively and is honest about
it, but **cannot cancel an in-flight cook** — deferred by its own comment: *"must run off the UI
thread against a live bridge."* An artist mid-Karma-render has a Stop that will not stop the
render.

**Work**
1. `prospector` specifies the contract; `assayer` confirms every `hou.*` symbol live —
   `tops_cancel_cook`, render-ROP interrupt, `cancelCook()` on the PDG graph. **Confirmed-absent
   APIs are quarantined, not worked around.**
2. `h22-forge` implements off-UI-thread dispatch against the live bridge.
3. Surface `EmergencyProtocol.trigger_emergency_halt` as a **second, distinct control** in the
   rail's overflow — not a rename of Stop, not competing with it (R29).
4. `seam-hunter` certifies against a real cook.

**If the live symbols are absent on 22.0.368, that is the deliverable.** Report it as a SideFX
ask, do not invent a workaround.

---

## 5 · FINAL

### F1 · Integrate + housekeep

1. Merge H1, H2, H3 into one integration branch **in that order**, suite green after each.
2. Remove the merged `solaris-repair` worktree and its branch.
3. Delete merged remote feature branches. **Keep `archive/root-scratch-2026-07-25` indefinitely**
   — it is the only copy of eleven deleted files outside history.
4. `git add --renormalize .` and commit alone, on a quiet tree, no agent running (R24). The repo
   has never complied with its own `.gitattributes`.
5. Note in the ledger that `4abf68a` carries a merge message naming `_merge_test`, a branch that
   no longer exists. **Do not amend** — master is public and the history is accurate; only the
   label is dead.

### F2 · The tag call

Ruled: no tag until H1 and H3 land. F2 verifies that and produces `docs/RELEASE_NOTES.md` stating
known-broken items plainly. **F2 does not tag.** It reports whether the conditions are met.

---

## 6 · Dispatch

```
Read harness/AGENT_CONSTITUTION.md, then harness/SYNAPSE_REPAIR_HEATS.md, and execute it.
You are ORCHESTRATOR. Dispatch the existing .claude/agents specialists per section 2.

Run Q1 and Q2 first - they BLOCK. Do not start any heat until both receipts are green.
Then read Q2's shipping number and take the section-4 branch it dictates. Record which
branch you took and why.

Heats run in separate worktrees off master, constitution cherry-picked onto each (R38).
Never push, never merge to master, never tag. Do not ask Joe anything until F2.
Begin at Q1.
```

**Resume:** read the receipts, restart at the first stage with none.

---

## 8 · AMENDMENT A1 — 2026-07-25, Joe-authorized. H4 added.

**Not visible to the running orchestrator.** REPAIR-HEATS-01 read this document at dispatch and
will not re-read it. H4 is therefore a **follow-on dispatch**, not a stage the current run will
execute. It commits now because F3 requires governing documents to precede the work they govern,
and H4 has not run.

### H4 · Panel finish — `feat/repair-panel-finish`

**Trigger** Joe, 2026-07-25: *"the UI is outdated."* Diagnosed rather than assumed.

**What is actually true.** L4 shipped rule 1 — the wordmark is weight 400 at ~4px BRAND tracking,
with the reasoning recorded in the code (`synapse_panel.py:398-400`). `MUSHROOM` landed as
`_warm_bias(_TXT["tertiary"])`. Monolinear and atmosphere tokens landed.

**What did not, and why.** The token collision at the head of
`design/cto_relay_01/L4_COHERE_SPEC.md` was never resolved, and L4 was **right not to paint over
it**. Measured on HEAD:

```
t.SIGNAL   (cyan #00D4FF)   11 sites
_ds.SIGNAL (blue #8FB3D9)   20 sites
```

Mile 7's de-cyan converted 20 of 31 at the **call sites** rather than at the source — its own
comment says *"token sources stay untouched (local fix)"*. **The panel therefore ships two
different accent colours today**, and that is most of what reads as outdated. `CONIFEROUS` never
landed, so `verified/ok` remains synthetic mint rather than the natural counterweight the palette
needs.

L4's receipt also records **40% of its gate ungraded** — the hython-offscreen permission was
granted after that leg had already started.

**Gated on Q1, not merely on the qualifier.** Until the suite runs on the shipping interpreter,
every panel edit ships unverified. Panel work before Q1 is how 17 ORPHAN and 7 SILENT affordances
accumulated in the first place. **Do not start H4 before Q1 is green.**

**Work**

1. **Resolve the collision at the source.** Convert the remaining 11 `t.SIGNAL` sites, then make
   `panel/tokens.py` re-export from `panel/designsystem/tokens.py` rather than redeclare. One
   authority. Fixing call sites again would produce a third state, not a fix.
2. Resolve the `SIZE_HERO` branch — `tokens.py:59` sets 44, `tokens.py:83` sets 19. Document which
   is live.
3. Land `CONIFEROUS = "#6E8F72"` and migrate the `OK_SOFT` call sites. Two accents per view remains
   the ceiling; the render is the only chromatic event.
4. Re-run L4's ungraded 40% now that hython-offscreen is permitted.
5. Screenshot-diff every view before/after into `design/repair_h4/`.

**Explicitly OUT of scope**

- **The v3 design study** — halt-is-the-mark, two surfaces, the Voronoi cook grid. R29 established
  that a working, honest Stop already exists in the live rail. Adding a second control blind, into
  a package with no verification, is precisely the error this harness exists to prevent. It waits
  for a test surface.
- Removing ORPHAN affordances. That is its own leg with its own evidence.

**Oracle**

```
grep -c 't\.SIGNAL' python/synapse/panel/*.py            ->  0
panel/tokens.py re-exports; declares no colour of its own
every token name present before is present after   (assert against
  harness/notes/panel_token_inventory_before.json, per R20 - styles.py defines none)
pytest -k panel   ->  0 failed
no import of routing/ or server/ added to panel/
```

**Receipt** `harness/notes/receipts/H4.json`.

**Dispatch when Q1 is green**

```
Read harness/AGENT_CONSTITUTION.md, then harness/SYNAPSE_REPAIR_HEATS.md section 8 (H4).
You are ORCHESTRATOR for the panel-finish heat. Own worktree off master, constitution
cherry-picked (R38). Dispatch panel-design-warden, then crucible.
Resolve the token collision at the SOURCE before any palette work. Do not implement the
v3 design study. Never push, never merge, never tag.
```
