# ADJUDICATION — "Refactor SYNAPSE Memory Sub-System (LOOP v5.1)"

> Intake date 2026-08-21. Adjudicated against ratified law:
> `docs/THE_LOOP_v5.1.md` (RATIFIED 2026-08-20), `.synapse/contracts/loop-v00.yaml`
> (RATIFIED 2026-08-20), `harness/loop/SPEC.md`, `CLAUDE.md`.
> The blueprint is **accepted in substance and amended in three places.**

---

## 1 · Where it lands

The submitted spec is **not a new programme.** It is:

- **Phase 1 (audit/cleanup)** → new work; no rung owns it. → `harness/memory/` board, rung **M0**.
- **Phase 2 (`MemoryPort` PG-DRM + decay + settlement)** → this *is* LOOP rung **V0.2**, verbatim from the ratified ladder: *"PG-DRM active inside MemoryPort; first BLIND calibration samples logged to Hanish."*
- **Phase 3 (tests)** → the pinning layer for both.

`V0.2` is currently `blocked: needs v01 closed + Hanish substrate present`
(`harness/loop/STATE.json`). The ladder is ratified and **never re-sorted**.

---

## 2 · Three structural conflicts

### C1 — Fabricated SUCCESS (blocking)

Three of the four proposed methods return `SUCCESS` without a substrate:

| Method | What it returns | Substrate actually touched |
|---|---|---|
| `wake_scene_relations` | `SUCCESS`, payload = **its own input echoed back** | none |
| `query_and_filter` | `SUCCESS` over `_fetch_raw_memories() → []` | none |
| `deposit_settlement` | `SUCCESS`, `{"deposited": …}` | **none — nothing is written** |

`deposit_settlement` returning `SUCCESS` while writing nothing is the exact
failure the honest-seam law exists to prevent, and Hanish is `absent` in
`substrate_presence`. Under ratified law these must report `UNAVAILABLE` with a
reason.

**Amendment:** apply *Absence has a shape* (`AGENTS.md` §2).
Hanish is **write-side** → durable local **outbox** + `UNAVAILABLE`, drained when
Hanish lands. Absence costs latency, never truth.

### C2 — Ladder ordering (blocking)

V0.2 sits behind V0.1 (SALUS) and Hanish. Neither is installed. Building V0.2
now means either re-sorting a ratified ladder or shipping it un-gated.

**Amendment:** split the work by *what substrate it actually needs*.

| Blueprint element | Needs | Status |
|---|---|---|
| Legacy audit + disposition | nothing | **unblocked → M0** |
| Single-handle enforcement | **Moneta (LIVE)** | **unblocked → M1** |
| PG-DRM filter *kernel* (decay + token + distance, pure function) | nothing | **unblocked → M2** |
| PG-DRM wired into `MemoryPort.query_and_filter` | Moneta headless seam | LOOP V0.2 |
| `deposit_settlement` returning SUCCESS | **Hanish** | LOOP V0.2, gated |
| `wake_scene_relations` over real USD relations | Octavius/stage | LOOP V0.3 |

The kernel is buildable, testable and falsifiable **today** as a pure function.
The *port* stays `UNAVAILABLE` until its substrate resolves. That is the honest
split: prove the math, don't fake the wire.

### C3 — Contract change without ratification (gated)

`.synapse/contracts/loop-v00.yaml` binds the §4 surface with **param names
verbatim**; `tests/test_loop_contracts.py:61` pins
`MemoryPort.query_and_filter(relation_keys, task_context_tokens)`.

The blueprint adds `distance_threshold` and two new methods. That is a change to
ratified text — **Joe's word, per act.** It is not a code change an agent makes.

**Amendment:** the new surface is drafted as a **contract amendment proposal**
(`harness/memory/notes/CONTRACT_AMENDMENT_v02.md`, to be authored at M3) and
lands only after ratification. Until then `distance_threshold` lives on the
**kernel**, not the port — no pinned surface moves.

---

## 3 · Code-level defects in the submitted implementation

Fixed in the harness's version; recorded so the corrections are visible.

| # | Defect | Evidence | Correction |
|---|---|---|---|
| D1 | Error message says *"Max 1 handle per storage_uri"* but the code raises when a **different** URI is requested — i.e. max 1 handle **per process**. The message and the law disagree. | proposed `__init__` | State the real invariant. One handle *per URI* means a **registry keyed by URI**, not a scalar. |
| D2 | `tests/test_memory_port_v51.py` uses `time.time()` with no `import time` | proposed test | `NameError` at collection |
| D3 | Test imports `from python.synapse.loop.ports import …`; repo convention is `sys.path.insert(…/python)` then `from synapse.loop.ports import …` | `tests/test_loop_contracts.py:1-24` | Follow the existing convention |
| D4 | `distance_threshold` is accepted and **never used** — the "vector distance metrics" claim is unimplemented | proposed `query_and_filter` | Implement it in the kernel or drop the parameter. A dead param is a false capability claim. |
| D5 | Decay branch is unreachable in the test: fresh `timestamp` + λ=1e-5 ⇒ `utility ≈ 1.0` ⇒ never below `protected_floor`. The decay law is asserted, never exercised. | proposed test | Table-drive decay with **hand-computed** expectations (never read back from the implementation) |
| D6 | `protected_floor` is used as an *eviction threshold* (`utility < floor` ⇒ drop). The blueprint elsewhere defines it as a **floor that protects a deposit from decaying out**. Inverted semantics. | spec §1 vs code | Pin one definition, then test it |
| D7 | Process-global singleton breaks `MonetaConfig.ephemeral()`, which "auto-generates a unique `storage_uri`" for tests (`moneta_runtime.py:689`). Any second ephemeral store raises. | `moneta_runtime.py:689` | URI-keyed registry, not a scalar global |
| D8 | The proposed singleton is a **third** authority; the two real ones (`store.py:1514`, `ledger.py:320`) are untouched, and `store.py`'s is **unlocked** | AUDIT §C | Fix the real one first (M1) |

---

## 4 · Accepted without amendment

- Zero-LLM operation for retrieval filtering. Correct, and already the stated law.
- Decay-driven lifecycle over background prune threads. Correct.
- Main thread owns store init and execution. Correct, and already `CLAUDE.md` law.
- Panel observes over the WebSocket channel rather than constructing a store.
  Correct — and `panel/health_strip.py` already implements it; make it the
  enforced pattern rather than a new one.
- `HIT | MISS | UNRESOLVABLE` settlement vocabulary with a protected floor.
  Correct, and matches `docs/THE_LOOP_v5.1.md` step 9.

---

## 5 · Verdict

**ACCEPTED WITH AMENDMENTS.** Substance is sound and the four Moneta laws are
right. The implementation as written would fabricate three SUCCESS verdicts,
re-sort a ratified ladder, silently amend a ratified contract, and add a third
handle authority without fixing either real one.

The amended programme is `harness/memory/SPEC.md`, rungs **M0 → M4**.
