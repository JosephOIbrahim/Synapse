# SYNAPSE CTO Remediation Harness — v1

**Status:** ARCHITECT artifact → runnable under constitutional dispatch (ARCHITECT→FORGE→CRUCIBLE).
**Date:** 2026-06-09 · **HEAD at authoring:** `83f098b`
**Sources fused:** `docs/SYNAPSE_CTO_REVIEW_2026-06-09.md` (the backlog), Science Harness v3 §0/§4a discipline (the Floor — stable through v4/v5; this doc inherits the lineage, it does not fork it).
**Relationship to the Field Readiness relay:** this harness **is the Leg 2 / Track H execution instrument** for the C1–C11 slice. It does not supersede `SYNAPSE_FIELD_READINESS_HARNESS_v1.md`; it runs inside it.
**Commit this file to `docs/` before running it.** A harness pasted ephemerally violates its own provenance thesis (F3 class).

> **Read order (4 min):** §0 is the one idea. §1 sorts the backlog through the admission gate. §3 is the run order. §4 is what halts it. Skip the rest until a gate fires.

---

## §0 — First principles: the review's honesty problem is the harness's first job

The 06-09 review carries its own caveat in bold: **24 of ~46 findings were adversarially verified; ~22 were not** (spend-limit truncation), and the live WS transport was never exercised. Under the Floor — *an artifact may not assert what it has not verified* — those tags are not metadata. They are **verification provenance**, and they map directly onto the harness's existing scale:

| Review tag | Harness meaning | What the harness does with it |
|---|---|---|
| **[VERIFIED]** | V1 — open-file confirmed against HEAD | Fix may proceed directly. Reproduction step still required (see Floor rule 2). |
| **[VERIFIED↓]** | V1, severity adjudicated down | Same as VERIFIED. Severity is sequencing input, not a verification question. |
| **[UNVERIFIED]** | **V0-lead.** Well-evidenced, never adjudicated | **May not drive a mutation until re-ground live.** Phase 0 converts each in-scope lead to V1 or kills it. |
| **[REFUTED]** | Dead | Ledger `DeadEnd`. Never re-litigated. |

**The one-line thesis:** the review handed over a backlog standing partly on V0. This harness re-grounds the V0 slice *before* fixing anything that depends on it, fixes the V1 slice under reproduce→fix→reproduce-clean discipline, and writes every verdict to the Ledger so the next review starts from V1, not from transcripts.

**The second principle — the fix must not become the failure.** Phase 1 mutates the memory persistence path: the exact artifact whose loss mode is "one bad write destroys months." So the harness's hardest invariant is **quarantine-before-touch** (§2, rule Q): no code that can write `memory.jsonl`, `index.json`, or `encryption.key` runs until timestamped copies of all three exist outside the repo tree. The fix to the data-loss chain is not permitted to be a data-loss event.

---

## §1 — Admission gate: sort the backlog

Per the v3 §3 test — *target defined AND eval signal noisy with unknown direction → search; otherwise → build on the Floor.*

### The one admitted search: **C6 (the ~2 s dispatch floor)**

- **Target:** per-call dispatch latency, `run_on_main` enqueue → `_on_main` start.
- **Eval signal:** `dispatch_wait_ms` histogram — *which does not exist yet.* Direction unknown: the review's hypothesis (panel's 2000 ms `_ctx_timer` / `executeDeferred` wake) is corroborated by the 8.6 ms direct-handler probe but **never measured on the live dispatch path** (the WS server was down during the review). [UNVERIFIED] + corroborating data = exactly search-shaped.
- **Hypothesis tracks, critiqued before spend:**
  - **T1** — wake starvation: `executeDeferred` payload sits until the next natural event-loop wake; the panel's 2 s `_ctx_timer` is the metronome. *Predicted signature: dispatch_wait clusters at ≈0–2000 ms uniform, mean ≈1 s, or hard mode at ~2 s.*
  - **T2** — queue contention / GIL: payload delayed by cook or competing deferred work. *Predicted signature: dispatch_wait correlates with scene cook activity, not with timer phase.*
  - **T3** — transport, not dispatch: the floor lives in WS round-trip or panel-side wait, and `run_on_main` is innocent. *Predicted signature: dispatch_wait small; gap appears between client send and server receive timestamps.*
- **Promotion rule (second-seed form):** the fix (e.g. `QCoreApplication.postEvent` wake after `executeDeferred`) is champion only when the measured floor drops on the live path **and reproduces on a second fresh Houdini session**. A one-session win inside noise is not a promotion.

### Everything else: builds, FORGE on the Floor

C1–C5, C7–C11 all have deterministic eval signals (*bug reproduces, then doesn't*). No hypothesis space. No ceremony beyond the Floor. Same ruling as v3 gave S1–S3.

### Explicitly out of scope for this harness

- **C12–C27 (P2) and C28–C35 (P3)** — sequenced behind this run; not touched.
- **SEC-1** (hwebserver permission gap) — **owner decision D4** (§6). Localhost-single-user posture is documented; closing it is mandatory *before any non-local mode*, which is a posture change, not a bug fix.
- **EmergencyProtocol fate** — folded into C10 as **owner decision D3** (§6): wire it or banner it; the harness refuses the third option (let it rot).
- **Michael Gold's USD schema zone** — nothing in C1–C11 touches attribute schema conventions. No RFC required for this run. If any fix drifts toward `customData` or typed-schema territory: **halt-and-surface** (§4, trigger H6).

---

## §2 — Invariants for this run

### The Floor (Tier 0, unconditional — inherited, restated for this backlog)

1. **API-verified-or-quarantined.** Every `hou.*` / Qt / `pdg` surface a fix touches is confirmed by live `dir()`/`hasattr` against **graphical H21.0.671** (and **hython 21.0.631** where the path runs headless) before the line is written. The four quarantined phantoms (`hou.pdg.*`, `hou.secure`, `hou.lopNetworks()`, `hou.updateGraphTick()`) stay quarantined. **Note `QCoreApplication.postEvent` is itself an unverified assumption until probed in-process** — the C6 fix candidate goes through the same gate as everything else.
2. **Reproduce → fix → reproduce-clean.** A [VERIFIED] tag licenses *starting* the fix, not *claiming* it. Every C-item, verified or not, follows: bug reproduced live (or its precondition demonstrated) → smallest fix → clean on re-run → **clean on a second fresh session** for anything touching persistence, undo, or dispatch. The "verified" stamp on the commit is a `VerifiedClaim` struct (eval signal fired, V1, in-repo path, against-build) — not prose.
3. **Provenance-or-it-didn't-happen.** Every phase lands as an atomic commit, race-safe push (fetch+rebase, max 3, halt on conflict). Every verdict — including *negative* ones from Phase 0 — is a Ledger entry.

### Run-specific execution invariants (Tier 1 for this harness)

- **Q — Quarantine-before-touch (blocking, Phase 1 gate).** Before any code that can write the memory store runs: timestamped copies of `memory.jsonl`, `index.json`, `encryption.key`, **and the two divergent sibling stores noted in C27's evidence** to a path *outside* the repo and outside `$HOUDINI_TEMP_DIR`. Copy paths recorded in the Ledger. No copy → no Phase 1.
- **S — Suite floor.** 3,377 green at HEAD. The count **strictly increases or holds** — every fix lands with its regression pin (C9's failure-path test, C4's abandoned-flag test, C1's degraded-load test, …). CRUCIBLE never weakens a test; fix-forward only.
- **A — One mutation class per commit.** C1+C2+C3 are one *unit* but land as three commits in dependency order (guard → atomic save → escrow), each independently green. If C2 must precede C1 mechanically, FORGE surfaces that in the Phase 1 plan line, not silently.
- **M — Measure before mutate (C6 only).** The instrumentation commit (timestamps + histogram) lands and produces live numbers **before** any wake-path change. If T3 wins (transport, not dispatch), the `postEvent` fix is *never written* and the search retires with a `DeadEnd`.
- **L — Honest latency claims.** No commit message or doc line claims a latency win without the before/after histogram in the Ledger entry.

---

## §3 — Run order (mile markers)

Four miles. Estimated wall-clock per the review: ~2 days for Miles 1–3; Mile 4 is M-effort.

```
MILE 0 — RE-GROUND                                [probe-first · gates everything]
   0.1  Commit this harness to docs/. (You are reading the F3 lesson.)
   0.2  Start the Synapse WS server. synapse_ping / _health / _metrics —
        the live-transport telemetry the review never got. Record to Ledger.
   0.3  Convert in-scope V0-leads:
        · C9  — open handlers_tops/cook.py:6-19,69. logger undefined? → V1 or DeadEnd. (minutes)
        · C10 — confirm v9 panel has no server.heartbeat() caller; confirm
                Watchdog arm path in resilience.py:543-575. → V1 or DeadEnd.
        · C11 — confirm _render_on_main's file-poll + iconvert run on the main
                thread (read the code; do NOT run a render yet). → V1 or DeadEnd.
        · C6  — no code-read can settle it; it converts via Mile 3's
                instrumentation. Mark "V0 → instrumented at Mile 3" in Ledger.
   0.4  CAPSULE → HUMAN GATE 1. Scorecard: which leads survived, which died,
        live telemetry baseline. Joe authorizes Miles 1–3 to run continuously.

MILE 1 — THE MEMORY-LOSS CHAIN                    [C1 → C2 → C3 · one unit, three commits]
   gate: invariant Q satisfied (quarantine copies exist, paths in Ledger).
   1.1  C1  degraded-load guard: count failed SYNAPSE_ENC_V1 decrypts; >0 ⇒
            degraded_load flag refuses save()/rewrite + quarantine-copies the
            store (reuse moneta_store._quarantine_if_corrupt). + pin test.
   1.2  C2  route MemoryStore.save() through write_report (tmp+fsync+os.replace,
            backups=1). + pin test proving a kill mid-save leaves a valid file.
   1.3  C3  key escrow: encryption.key.bak on generation + one-time backup log;
            sha256[:8] fingerprint into index.json; refuse rewrite on mismatch.
   exit: second-fresh-session reproduction — wrong-key load attempt leaves the
         store intact and refuses the save. The original wipe path is dead.

MILE 2 — MUTATION CORRECTNESS + LIFECYCLE HONESTY [C4, C5, C8, C9 · all S-effort]
   2.1  C4  zombie kill: per-call abandoned flag under lock; _on_main checks
            before fn(). Retry message carries command id for mutating ops.
   2.2  C5  one module-level threading.Lock in SynapseHandler.handle() for
            non-read-only commands, skipped on main thread. DO NOT build a
            queue — batching was refuted; the review is explicit. (And C31
            later removes the phantom queue; do not add a real one first.)
   2.3  C8  honest Stop: busy-state held until worker.finished; "Stopping —
            waiting on current tool…"; best-effort tops_cancel_cook / render
            cancel when the running tool matches tops_*/render*.
   2.4  C9  (if Mile 0 confirmed) one-line logger import + failure-path test.
   exit: suite ≥ baseline + pins; zombie repro (forced timeout) shows the
         abandoned payload returning without effect.

MILE 3 — THE LATENCY SEARCH                       [C6 · the admitted search]
   3.1  Instrument: t_enqueue in run_on_main, t_start in _on_main,
        dispatch_wait_ms histogram exported. Commit. Collect live numbers
        across ≥30 mutating calls in a working session.
   3.2  Adjudicate T1/T2/T3 against the predicted signatures (§1).
   3.3  If T1: dir()-verify the wake surface in-process, apply the post-
        executeDeferred wake, re-measure. Promotion only on second-session
        reproduction of the drop. If T2/T3: write the DeadEnd/redirect and
        STOP — C7/C11 may proceed; the wake fix does not.
   3.4  C7  per-tool timeouts (share _SLOW_COMMANDS); timeout returns "still
            running — do not retry" tool-error, never None. Kills the
            double-dispatch C4 only half-covers.
   3.5  C11 (if Mile 0 confirmed) split _render_on_main: hou.* stays on main;
            file-poll + iconvert move to the WS handler thread.
   exit: histograms in Ledger (before/after if T1 won), C7 retry-storm repro
         clean, render no longer freezes UI for the flush window.

MILE 4 — DECISION GATES SURFACED                  [no autonomous mutation]
   4.1  C10: present D3 to Joe — (a) wire the 1 s QTimer heartbeat re-arming
        Watchdog/backpressure/_on_freeze, or (b) banner §1.8 not-live, the
        same honesty treatment the bridge got. Build ONLY after the call.
   4.2  Surface D4 (SEC-1 timing) with the posture trade stated. No code.
   4.3  FINAL CAPSULE: WHERE WE ARE / MILE MARKER / BLOCKERS / NEXT ACTION,
        + the Ledger delta (every Confirmation/DeadEnd written this run),
        + what re-verification the spend-limit leftovers still need (C16,
        C24, C25 remain V0-leads outside this scope).
```

---

## §4 — Halt-and-surface triggers

The loop halts and hands back — it does not improvise — on:

- **H1** Any `hou.*`/Qt surface a fix needs fails the live `dir()` gate (phantom class).
- **H2** Suite count regresses, or a fix is only achievable by weakening an existing test.
- **H3** Undo-depth anomaly observed during any reproduction (the S1 class resurfacing).
- **H4** Any write touches `memory.jsonl`/`index.json`/`encryption.key` while invariant Q is unsatisfied — including by a *test*.
- **H5** Merge conflict on push (after 3 fetch+rebase attempts).
- **H6** A fix drifts toward USD attribute-schema territory (Gold's RFC-only zone).
- **H7** Mile 3 measurement contradicts all three signatures — the search has no live hypothesis; surface rather than fish.
- **H8** Live probe at 0.2 reveals transport behavior that invalidates a Mile 1–2 assumption (e.g. multi-line transport class resurfacing).

---

## §5 — Ledger entries this run must write

Minimum set; every entry carries `verified_by`:

- `Confirmation` per C-item fixed (with `VerifiedClaim`: eval signal, V1, in-repo path, against-build, second-session note where required).
- `DeadEnd` for: the refuted P3 worker-bypass claim (carry it in from the review so it is never re-litigated), any Mile 0 lead that dies, and the C6 tracks that lose.
- `SubstrateAssumption` flips: "memory save is atomic + backed" (holds=false → true at Mile 1 exit), "dispatch floor is intrinsic" (the review's PR #28 folklore — probe decides), "Stop terminates work" (false → true at 2.3).
- `Canonical` pointer: this harness supersedes nothing; it **instruments** Field Readiness Leg 2. Record the relationship so the two docs never read as rivals.

---

## §6 — Owner decisions (gates, not work items)

| ID | Decision | Blocks | Default if unmade |
|---|---|---|---|
| **D3** | EmergencyProtocol: wire to re-armed Watchdog (C10-a) or banner not-live (C10-b) | Mile 4.1 build | **None — the harness refuses to default this.** Rotting is the named anti-pattern. |
| **D4** | SEC-1 close-before timing (now vs. gate-on-non-local-mode) | nothing in this run | Documented posture stands; re-surfaces at any deploy-mode change. |

---

## One-line synthesis

The review handed over a backlog standing half on V1 and half on transcripts; this harness re-grounds the transcript half before mutating anything, fixes the memory-loss chain under a quarantine-before-touch gate so the cure cannot be the disease, treats the 2-second floor as the one genuine search with measurement before mutation, and refuses to let the two safety-wiring decisions rot by making them explicit owner gates — the Floor, applied to a review that was honest enough to tag its own gaps.

---

*End v1. Run via the kickoff prompt in the session that produced this document. HEAD `83f098b` · suite baseline 3,377 · GATE 6 green (false_phantom_rate 0.0 / true_phantom_recall 1.0).*
