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
