<!-- Verification of the "Moneta v4.0 Phase 0 Audit" against the moneta copy
SYNAPSE actually imports. 2026-07-21, 14-agent read-only workflow, 0 errors,
1.35M subagent tokens. All 7 audit findings + P0-6 CONFIRMED on the installed
copy; ZERO refutations. Headline: none of them are reachable on a stock SYNAPSE
install, because SYNAPSE_MEMORY_BACKEND defaults to jsonl and the moneta package
is never imported. See section 7 C1 -- an unresolved hard contradiction that
blocks execution item 5. Process caveat: the audit document itself is not on
disk in either repo; its claims were verified as relayed, not as written. -->

# MONETA AUDIT → SYNAPSE EXECUTION PLAN
**Synthesis of 13 independent verifications · installed copy `C:/Python314/Lib/site-packages/moneta` (moneta 1.2.0rc1) · SYNAPSE master `da4475d` (v5.33.0)**

---

## 1. MATCH VERDICT

**MATCH — the audit describes the code SYNAPSE imports.**

- Installed copy resolves at `C:/Python314/Lib/site-packages/moneta/__init__.py` (live-probed).
- `moneta-1.2.0rc1.dist-info/direct_url.json` pins commit `76da067` = `v1.2.0-rc2`. Audited clone is `2965e5d` = rc2+10, and those 10 are **doc-only** commits (STATE_OF_MONETA, patent-surface cleanup, patent-evidence move — per `git log`).
- Only functional delta: `usd_target.py` module docstring, one line. Installed = clone **+1** from line 18 onward. Every other file byte-identical.
- **Consequence:** every audit line number for `api.py`, `ecs.py`, `durability.py`, `consolidation.py`, `vector_index.py` transfers unchanged. `usd_target.py` cites shift +1.

**But:** SYNAPSE declares **no** moneta dependency (`grep moneta pyproject.toml requirements*.txt` → no match), exports **no** `__version__`, and `importlib.metadata.version("moneta")` returns `1.2.0rc1` for rc1, rc2, **and** rc2+10. The match is a coincidence of timing, not an enforced property. Nothing in SYNAPSE can observe it.

---

## 2. VERDICT TABLE

| ID | Claim | Verdict | Installed-copy anchor |
|---|---|---|---|
| **F1** | Version drift; no runtime version detection | **CONFIRMED** | No `__version__` anywhere in package; `METADATA:3`; truth unread in `direct_url.json` |
| **F2** | `vector_persist_path` accepted, never read | **CONFIRMED** | `api.py:134` (field), `api.py:215-218` (passed), `vector_index.py:75` (assigned), `:76-81` (warns + ignores). One-hit grep on `_persist_path` |
| **F3** | `deposit()` has no WAL write | **CONFIRMED** | `api.py:328-377` — no `durability` reference. Only WAL writer: `api.py:433`. Only snapshot trigger: `api.py:471`. WAL schema `durability.py:136-143` carries **no payload** |
| **F4** | `start_background()` never called | **CONFIRMED** | `durability.py:231-251` def; 2 grep hits package-wide, both internal. `api.py:300-307` close() docstring references the phantom daemon |
| **F5** | `cos_sim * utility` over unclamped cosine | **CONFIRMED** | `api.py:413` (product), `:414` (sort), `vector_index.py:165` (unclamped), `ecs.py:295` (duplicate) |
| **F6** | Attention weight unvalidated → **deletes** the memory | **CONFIRMED** | `api.py:430` `float(weight)`; `ecs.py:211-212` upper clamp only; `consolidation.py:54-55` prune thresholds; NaN/neg → utility 0.0 → pruned |
| **F7** | USD is write-only | **CONFIRMED** | `usd_target.py:164-166` `_prim_path`; zero read APIs package-wide; `api.py:220-249` hydrate = JSON snapshot + WAL only; `usd_target.py:137` `_token_to_state` zero callers |
| **P0-6** | protected_floor ≥ stage threshold → permanent stall | **CONFIRMED (CONTESTED — see C1)** | `decay.py:69` floor clamp; `consolidation.py:54-57` thresholds; `:110-119` classify; `moneta_store.py:36` floor `0.9` vs stage `0.3` |

**Zero refutations.** Every claim held on the installed copy.

---

## 3. WHAT SYNAPSE ACTUALLY INHERITS

### Gate 0 — the whole thing is off

`store.py:810`: `backend = os.environ.get("SYNAPSE_MEMORY_BACKEND", "jsonl")`.

Live probe, no env vars: `moneta in sys.modules = False` after both `import store` and `SynapseMemory()` construction. Every moneta import in SYNAPSE is function-local.

> **On a stock install, SYNAPSE inherits ZERO of these bugs. The package is never imported.**

Getting to Moneta requires one of three explicit operator actions: `SYNAPSE_MEMORY_BACKEND=moneta`, `=shadow`, or hand-running `seed_corpus` / `backfill --execute` (those two ignore the env var).

### Gate 1 — with the flag set, the reachable surface is 13 call sites

**REACHABLE — fix these:**

| # | What | Where | Real impact |
|---|---|---|---|
| **1** | **Deposits are not durable.** `add()` deposits to an in-memory ECS and returns. No `save()`, no `atexit`, no daemon, and the WAL is structurally dead (SYNAPSE never calls `signal_attention`, the only WAL writer). Loss window bounded only by how often a human fires `synapse_sleep_pass`. | `moneta_store.py:279` (deposit, no save); `:412-417` (close→save, CLI-only callers); no atexit — contrast `store.py:207` | **This is the only genuine bug SYNAPSE inherits.** Houdini crash = 100% loss since last snapshot. This repo has a crash harness because crashes happen. |
| **2** | **Unpinned + undeclared + version-undetectable dependency.** CI does `pip install -e ./_moneta` against an **unpinned branch tip** (`ci.yml:26-43`). The ratchet baseline (floor 4086) is measured against a moving dependency. | `pyproject.toml` (no moneta), `ci.yml:26-43`, `moneta_runtime.py:38` | Ops risk, live **regardless of backend**. |
| **3** | **API-drift failure is invisible.** `store.py:817-821` catches `Exception` and logs one WARNING. "moneta not installed" and "moneta upgraded and broke the API" produce the identical line, then SYNAPSE silently serves jsonl while the operator believes moneta is active. | `store.py:817-821`, `moneta_store.py:206-209` | Silent downgrade. |
| **4** | P0-6 protected stall — SYNAPSE's floor `0.9` vs stage threshold `0.3`. Protected set never leaves VOLATILE; `ecs.n` grows monotonically. **Contested by C1.** | `moneta_store.py:36`, `consolidation.py:57` | Under MockUsdTarget nothing is lost — just unbounded growth. Muted further because nothing evicts anyway. |
| **5** | Quota-demotion fallback silently re-deposits at `protected_floor=0.0` with a `logger.warning`. Zero test coverage. | `moneta_store.py:280-289` | Quota is 100k vs default 100 — boundary never approached in practice. |

**THEORETICAL — do not spend an hour on these:**

| # | Finding | Why unreachable |
|---|---|---|
| F5 | Cosine ranking inversion | `Moneta.query()` has **zero SYNAPSE callers**. `MonetaBackedStore.search` (`moneta_store.py:339-340`) uses SYNAPSE's own pure-Python `score_memories`. The vector index is written on every deposit and **never read** — pure write amplification. |
| F6 | NaN/negative attention deletes memories | `signal_attention` has **zero callers repo-wide** (prod + tests). Live-probed: attention log len 0 after add; WAL file never created. |
| F2 | `vector_persist_path` ignored | SYNAPSE never passes the field (`moneta_store.py:215-221` sets 5 of 11). The warning never even fires. |
| F7 | USD write-only cold log | `use_real_usd` is never set anywhere in SYNAPSE (1 grep hit, a docstring). Authoring target is always `MockUsdTarget` — a JSONL append log. `usd_target.py` (396 lines) is entirely unreached. |
| F4 | Dead snapshot daemon | Same root cause as #1. The *daemon* fix is upstream and is explicitly rejected SYNAPSE-side (`moneta_store.py:195-198`: it races the single-writer ECS). |

**Shadow mode note:** demotes data-loss bugs to "poisons a copy nobody reads" — reads served from jsonl primary, writes `except Exception`-isolated, `run_sleep_pass` structurally unreachable (`handlers_memory.py:280` hasattr-gate). Three escapes remain: `get`/`all`/`get_by_tag`/`get_linked` are undiffed passthrough, `except Exception` misses `BaseException`, and **a hang is not an exception** — a Moneta deadlock blocks the primary write. Given this repo's marshal-deadlock history, that last one is the only shadow-mode concern worth a line.

**Net for the week: one real bug (#1), one ops risk (#2-3), one latent growth issue (#4). Everything else is someone else's product.**

---

## 4. THE P0-1 DECISION — clamp vs shift

### Recommendation: **do NEITHER in SYNAPSE. If it lands upstream, `max(cos, 0.0)`.**

**Can negative cosine occur?** Yes, measured with SYNAPSE's real `HashEmbedder` (`embedding.py:100` uses a sign hash, so vectors are genuinely signed):

| Content | Negative-cosine rate |
|---|---|
| Long English sentences (3160 pairs) | **0%** (min +0.246) |
| Short tokens 1-4ch (44850 pairs) | 5.74% (min −1.0) |
| Realistic short-query × stored-memory | **6 / 64** |
| Mixed disjoint scripts/symbols | 36.4% |

So it is real, and it lands **precisely on short queries** — the normal usage pattern. The demonstrated inversion is not subtle: identical embeddings, only utility differs → the utility-1.00 copy ranks **below** the utility-0.05 copy. Reinforcing a memory buries it.

**Why clamp, not shift:**

- `max(cos, 0)` — negative cosine means *anti-correlated*, i.e. "the index says this is not relevant." Ordering among not-relevant items is not information. Clamping ties them at 0 and restores monotonicity in utility for all inputs. Cost: loses relative order inside a band whose order is meaningless. Semantics preserved: score = relevance × value.
- `(cos+1)/2` — monotone in both arguments, preserves full cosine order, and **breaks the ranker in a worse way**. It gives every item a relevance floor of 0.5 at cos=0. A perfectly irrelevant memory at max utility scores `0.5 × 1.0 = 0.5`; a perfectly relevant memory at low utility scores `1.0 × 0.05 = 0.05`. The affine shift converts a relevance ranker into a **utility ranker with a relevance tiebreak**. It also changes absolute score scale, forcing every downstream threshold to be re-tuned.

**Why not in SYNAPSE at all:** the expression is at `api.py:413`, inside `Moneta.query()`, which SYNAPSE never calls. Fixing it costs SYNAPSE hours and buys zero behavior change. File it upstream. **Guard instead:** if anyone later wires `MonetaBackedStore.search` to `self._handle.query(...)` — the obvious "use the index we're already populating" change — that PR must not land before the clamp does. Pin it with a short-query regression test in `tests/`.

---

## 5. EXECUTION ORDER

Smallest first. Total ~40 minutes of SYNAPSE work. Solaris keeps the rest of the week.

| # | Do | File | Test that proves it | Time |
|---|---|---|---|---|
| **0** | **Verify the gate.** Confirm `SYNAPSE_MEMORY_BACKEND` is unset in every shipped launcher, installer, deployment doc, and panel config. If unset everywhere, items 3-5 drop to P2 for this release. | grep-only | `tests/test_m3_env_conformance.py:214-250` (already green) | 5m |
| **1** | **Pin the dependency.** Add optional extra `moneta = ["moneta>=1.2.0rc1,<2.0"]`. Must be an *extra*, not core: moneta is `License: Proprietary` + `Private :: Do Not Upload` (not on PyPI) and `Requires-Python: >=3.11` vs SYNAPSE's `>=3.9`. | `pyproject.toml` | CI install succeeds on all matrix Pythons | 5m |
| **2** | **Pin CI.** Add `ref: v1.2.0-rc2` to the Moneta checkout step. Today it tracks branch tip — CI and this workstation can disagree about what "moneta" means on any given day, and the ratchet baseline is measured against it. | `.github/workflows/ci.yml:26-43` | CI green on the pinned ref | 5m |
| **3** | **THE REAL FIX — durability.** In `from_storage_dir`, after `handle = mr.Moneta(cfg)` (`:222`), register `atexit.register(self.close)`, mirroring `MemoryStore` at `store.py:207`. | `python/synapse/memory/moneta_store.py:222` | **NEW** in `tests/test_moneta_integration.py`: `from_storage_dir` → `add` → abandon handle **without** `save()` → reopen → assert count. **Fails today** (returns 0). The existing restart test at `:122-136` masks this by calling `s1.save()` at `:128`, which production never does. | 15m |
| **3b** | **Decide explicitly:** atexit covers clean exit only. It does **not** cover `kill -9` or the Houdini crash class this repo maintains a harness for. Full coverage = per-add `save()` (O(n) snapshot per add) or an upstream deposit-WAL. Ship 3 now; record 3b as a known bound in the release notes. | — | — | 0m (decision) |
| **4** | **Make drift loud.** Add `moneta_version()` (via `importlib.metadata`) + record resolved `moneta.__file__` — path beats version string, since the version string is provably non-discriminating. Then split `store.py:817-821`'s blanket `except Exception`: `ImportError` → quiet jsonl fallback (intended); `AttributeError`/`TypeError` → **ERROR** with resolved version + missing member. | `moneta_runtime.py` (after `:40`, `:51`), `store.py:817-821` | Extend the backend-selection test in `tests/test_moneta_crucible.py:276-290` | 10m |
| **5** | **Pin P0-6, do not fix it.** Assert `_DEFAULT_PROTECTED_FLOOR` (`moneta_store.py:36`) `< moneta.consolidation.STAGE_UTILITY_THRESHOLD`. There is **no safe floor value** SYNAPSE can pick: below 0.3 still stalls (needs 3 attention signals SYNAPSE never sends); below 0.1 the memory becomes **deletable**. Tuning is not available — only failing loud on upgrade. | new test in `tests/` | The assertion itself | 5m |

### DO NOT DO

| Don't | Why |
|---|---|
| Fix F5 (cosine clamp) in SYNAPSE | `query()` has zero SYNAPSE callers. Zero behavior change. Upstream issue. |
| Fix F2 / F6 / F7 | Unreachable. `vector_persist_path` never passed, `signal_attention` never called, `use_real_usd` never set. |
| Flip `use_real_usd = True` | Pulls a hard `pxr` import into the memory path (`api.py:256`), reversing a stated architectural constraint (`moneta_runtime.py:6-8`, harness AP9). The audit recommends this implicitly and silently. |
| Adopt the audit's Phase 1 "close the cold loop" | **Consolidation does not evict.** Live probe: a CONSOLIDATED row stays in the ECS and stays queryable; recovery came from `snapshot.json`, not the authored tier. There is no cold tier. Phase 1 closes a loop around nothing. Also: `usd_link` is **never assigned anywhere in the package** (7 carry-only sites) — no read path is constructible at any phase. |
| Call `durability.start_background()` | Snapshots from a non-main thread with no lock on `ecs.iter_rows()`. `moneta_store.py:195-198` already rejected it for exactly this reason, correctly. |
| Weaken the 6 tests that pin buggy-but-documented behavior | `test_moneta_crucible.py:52-62` (total prune), `:111-127` (total loss on corrupt snapshot), `:208-220` (id collision), `:223-227` (case-sensitive tags), the two search-parity locks (`test_moneta_store.py:103-114` + `crucible:238-249`), `test_moneta_integration.py:102-119` (URI lock). Each will fail if the corresponding bug is "fixed." If one is genuinely defective, edit the pin **deliberately in the same commit**. |
| Vendor Moneta | Precedent for vendoring (`_vendor/anthropic-0.96.0`) exists because that SDK ships Windows binaries. Moneta is pure-Python, co-developed by the same author. Vendoring forks the memory substrate. Declare + pin + probe. |

---

## 6. REPO SPLIT

**SYNAPSE repo — ships this week, blocks nothing:**
1. `pyproject.toml` — declare + pin the extra
2. `.github/workflows/ci.yml` — pin the Moneta ref
3. `moneta_store.py` — atexit durability
4. `moneta_runtime.py` + `store.py` — version/path provenance, split the exception arms
5. `tests/` — restart-without-save test, floor↔threshold coupling assertion
6. Doc line at `moneta_store.py:220`: the configured `wal_path` is **inert** because `signal_attention` is never called. Today it reads as "we have a WAL." A later audit will believe it.

**Moneta repo — file as issues, do NOT gate SYNAPSE's release:**
1. `__init__.py` — export `__version__`; adopt hatch-vcs so tag *is* version (kills the rc1/rc2 desync class)
2. `durability.py` + `api.py:363-374` — WAL v2 with a typed deposit record (payload/embedding/utility/floor/state). The current schema (`durability.py:136-143`) cannot reconstruct a deposit **in principle**.
3. `api.py:430` — reject non-finite / negative attention weights; `durability.py:136` — `json.dumps(..., allow_nan=False)` (currently writes literal `NaN`/`Infinity`, invalid JSON for any non-Python reader)
4. `consolidation.py:110-119` — make `protected_floor` a first-class staging signal; guard `0 < floor < PRUNE_THRESHOLD` at `api.py:350` (that band is "protected" and **deletable**)
5. `api.py:413` + `ecs.py:295` — `max(cos, 0.0)`; fix the docstring at `api.py:393-395` that documents the buggy convention
6. `api.py:134` — delete `vector_persist_path` or move it to the existing "Cloud-anticipated (do not implement)" block at `:139-141`
7. `sequential_writer.py:320-321` — write the authored prim path back to `usd_link`. **This is the true gate for any USD read path**, and it is upstream of both audit phases — inverting the audit's stated ordering.
8. Dead-code / stale-comment sweep: `_token_to_state` (`usd_target.py:137`, zero callers), `VectorIndex.restore` (`vector_index.py:187`, docstring names a caller that doesn't exist), `start_background` (`durability.py:231`, zero callers)

---

## 7. CONTRADICTIONS — flagged, not averaged

**C1 — HARD. Blocks P0-6. Resolve before acting on item 5.**
R5's live probe drove the **real** `run_pass` (fake clock, half_life 60, +600s) on an unprotected row and got `pruned=0, staged=1, state=CONSOLIDATED` at utility `0.00098`, `attention_updated=0`. P0-6 reads `consolidation.py:110-119` as *prune iff utility<0.1 AND attended_count<3* — under that rule the row should have **PRUNED**. It staged. Two reports, one file, incompatible outcomes.
Note the fidelity difference: P0-6's repro drove `classify()` directly; R5 drove `run_pass`. **R5's probe is the higher-fidelity one.**
*Resolution (10 min):* re-read `consolidation.py:107-125` and check for a second staging path — memory-pressure at `:89` is the likely candidate. Until then, P0-6's "fires on 100% of SYNAPSE's protected set" is **unverified**, and item 5's assertion may be pinning a rule that isn't the operative one.

**C2 — Scoping, not factual.** F2 rates `vector_persist_path` cosmetic because durability rebuilds the index from the hydrated ECS (`api.py:231-236`). True **only for rows that reached a snapshot**. F3 proves deposits don't reach snapshots. Combined: vectors deposited since the last snapshot are lost along with everything else. F2's severity rating stands; its "nothing is lost" phrasing does not.

**C3 — Framing.** F3 and F4 are one defect viewed twice (no WAL on deposit / no periodic snapshot). Track as **one** work item. F4's "dormant daemon" framing understates it — F3's "deposits are not durable between sleep passes" is the correct scope, and F4's own author says so.

**C4 / C5 — Severity axis, not a conflict.** F5 (major) and F6 (major) rate *upstream* severity. R1/R3/R5 independently prove both are unreachable from SYNAPSE (`query()` and `signal_attention` each have zero callers). Both are true on their own axis. **Do not let the audit's severity ratings be read as SYNAPSE severity** — that is the single most likely way this week's hours get spent wrong.

**C6 — Not a contradiction.** F3's probe produced a WAL file; R1's probe of the real SYNAPSE path found none. F3 injected a manual `signal_attention` to force it. Both correct; F3's is synthetic.

**C7 — Agreement worth noting.** F2 and R5 independently found the stale `"used by durability.py"` comment on `VectorIndex.snapshot`/`restore` (`vector_index.py:170`) pointing at two methods with zero callers. Two agents hit the same trap — it will mislead the next reader too. Cheap to fix upstream.

**Process caveat:** the "Moneta v4.0 Phase 0 Audit" document is **not on disk** in either repo. Two of thirteen agents searched for it and failed. F1-F7 were verified as *relayed*, not as *written*, and their original cited line numbers could not be diffed. All line numbers above are first-hand reads of the installed copy and are independently checkable.

---

## BOTTOM LINE

SYNAPSE ships this week with **~40 minutes** of memory-subsystem work: pin the dep, pin CI, add one `atexit`, split one exception arm, add two tests. The audit's dramatic findings — cosine inversion, NaN-deletes-memories, USD write-only cold log — are **real, confirmed, and unreachable**, because `SYNAPSE_MEMORY_BACKEND` defaults to `jsonl` and the moneta package is never imported on a stock install.

The audit's own conclusion ("adopt the causal composition seam + persistence") is **wrong twice**: the seam is already built (`usd_target.py:164-166`, `:233-263`), unreachable (`use_real_usd` never set), and gated behind a `pxr` import SYNAPSE exists to avoid — and Phase 1 presumes an eviction that consolidation never performs.

**Adopt nothing. Pin, add the atexit, and go do Solaris.**