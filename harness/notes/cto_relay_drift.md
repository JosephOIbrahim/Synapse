# CTO-RELAY-01 — drift log

Reality contradicting `harness/SYNAPSE_CTO_RELAY.md`. Cosmetic ⇒ resume. Structural ⇒ §5.

---

## D-R1 · checks.py oracle invocation is wrong in the relay doc — STRUCTURAL

**Leg** L0 (and L1, L2 — every leg whose oracle cites checks.py)
**Doc claim** `harness/SYNAPSE_CTO_RELAY.md:161` — `python harness/verify/checks.py --all`; `:191` — `--check lop_emission_grounded`; `:193` — `--check no_phantom_api`.
**Reality** `VERIFIED-RUNTIME` — `checks.py` accepts `--task TASK --worktree WORKTREE [--hython] [--mode]`. Neither `--all` nor `--check` exists; the process exits 2 on both.
**Impact** The L0/L1/L2 oracles cannot execute as literally written. The check *functions* (80 of them) exist; only the CLI surface differs.
**Disposition** Resumed. Oracles re-expressed against the real CLI (`--task`/`--worktree`). Escalated to §5 as a ruling item because three legs' acceptance criteria are affected, not one.

---

## D-R2 · baseline sha moved — COSMETIC

**Doc claim** `:6` — `Baseline master @ e4b5916`.
**Reality** `VERIFIED-RUNTIME` — branch HEAD is `25e0166`; `e4b5916` is 3 commits back. The intervening commits (`0b3e377`, `2f63e78`, `25e0166`) are relay-authoring/amendment commits, not product changes.
**Disposition** Resumed. L2's "re-run seam-gate acceptance on `e4b5916`" is honoured by running against the branch HEAD that *contains* `e4b5916` — running against a stale sha would answer a question nobody is asking.

---

## D-R3 · L1 gap-closure is gate-REFUSED — STRUCTURAL

**Doc claim** `:184-186` — L1 work item 4: "Close the top 5" LOP/COP gaps.
**Reality** `VERIFIED-STATIC` — `harness/state/flywheel_queue.json:80`, cycle `C.0`, `"ratified": false`. GATEWARDEN returns **REFUSE** for the per-context capability *rebuild* and for gap *closure*; the census and delta probe are ALLOW.
**Impact** L1 can produce the COP census, the LOP delta and the ranked gap list. It cannot author the closing code. `harness/agent-settings.json` is deny-listed and `flywheel_queue.json` sits under the fenced `harness/state/**` — the agent cannot and must not flip its own gate.
**Disposition** Leg proceeds in census-only scope. The unflippable half escalates to §5 as a ruling item; the human flip is one boolean at `flywheel_queue.json:80`.

---

## D-R4 · `_cto_recon.py` does not exist — COSMETIC

**Doc claim** `:154` names `_cto_recon.py` among the root-hygiene suspects.
**Reality** `VERIFIED-STATIC` — no such path on the tree. The suspect list is itself stale on this one item.
**Disposition** Resumed; recorded so the next census does not hunt a ghost.

---

## D-R5 · `untitled.hip/` is data, not debris — COSMETIC (but load-bearing)

**Doc claim** `:153` lists `untitled.hip` as a hygiene suspect alongside `MagicMock/`.
**Reality** `VERIFIED-STATIC` — it is a directory holding `claude/agent.usd` (6,220 B) + `claude/memory.md` + `.synapse/`: the live unsaved-scene memory store, previously flagged at `docs/SYNAPSE_CTO_REVIEW_2026-06-09.md:118`.
**Disposition** Reclassified `live — do not delete`. Deleting it on the doc's suggestion would have destroyed the only copy of the unsaved-scene ledger.

---

## D-R6 · the branch is not exclusively the relay's — STRUCTURAL (process)

**Leg** L4 (detected), affects all legs.
**Reality** `VERIFIED-RUNTIME` — a concurrent process committed `6b41e1a`, `19dca4d`, `5a88cee` and `aaf12fe` to `feat/cto-relay-01` while the relay was mid-leg, authored as `Joseph Ibrahim`. One of them silently undid a `git reset --soft` the L4 agent issued to split a commit.
**Impact** Cohere rules 2 and 5 share one commit (`8411aad`) instead of being separate. Rule 1 stayed isolated, which is the one that had to be. No work was lost — but only by luck.
**Disposition** Resumed. Escalated to §5 as L4.R2: the relay's premise is that subagents are a context-isolation device; branch isolation is the missing half. Recommend per-leg worktrees.

---

## D-R7 · a parallel ruling file already exists — COSMETIC

**Reality** `VERIFIED-STATIC` — `harness/notes/CTO_RULINGS_01.md` was created by the concurrent process and already carries rulings up to R24, including an L3 addendum (rulings 17–23) covering emergency halt and the consent gates.
**Impact** The relay's §5 deliverable is `harness/notes/CTO_RELAY_01_RULING.md` — a different file. No collision, but two ruling surfaces now exist for one run.
**Disposition** Resumed. `CTO_RELAY_01_RULING.md` is written as specified and cross-references the other file rather than merging into it. Reconciling the two is itself a ruling item.

---

## D-R8 · L4's ORPHAN-removal instruction was declined, deliberately — STRUCTURAL

**Doc claim** `:277` — "Anything the L3 matrix marks `ORPHAN` is **removed from the surface, not restyled**."
**Reality** `VERIFIED-DERIVED` — all 17 ORPHANs are the `chat_panel.py` tree, whose loader (`synapse_chat.pypanel`) is never installed. They are already invisible to users. Removing the tree decides what belongs on the product surface — a T.4-adjacent call — and T.4 is frozen by three concordant sources.
**Impact** The instruction and the T.4 freeze are in direct tension. The freeze wins.
**Disposition** Resumed; neither restyled nor removed. Escalated to §5.

---

## D-R9 · hython-offscreen denied for the whole panel arc — STRUCTURAL

**Reality** `VERIFIED-RUNTIME` — every `hython.exe` invocation was refused by the permission system across L3 and L4 (observed 4× in L3, again throughout L4).
**Impact** 2 of 5 G3 slices have no baseline and no after-state: the live offscreen build and the v9 invariants. No screenshots were produced. Nothing in the restyle has been seen rendering.
**Disposition** Resumed with the gap reported honestly rather than papered over. Escalated to §5 as L4.R1 — the cheapest unblock in the relay, being a permission grant rather than engineering work.
