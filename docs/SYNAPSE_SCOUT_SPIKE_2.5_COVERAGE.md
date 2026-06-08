# SYNAPSE — Scout · Spike 2.5: Coverage Remediation · dispatch
*Inserts into `SYNAPSE_SCOUT_HARNESS_v1.md` between Spike 2 and the HUMAN EMBEDDER GATE. Closes the release-blocking false-phantom Sev-1 surfaced by the Spike 2 eval. **Commit this doc before running it** (F3). Claude Code under ARCHITECT → FORGE → CRUCIBLE.*

---

## Why this spike exists — first principles
The eval found `false_phantom_rate = 0.667` — scout tells the model 8 of 12 real APIs are fake (`hou.LopNode`, `hou.SopNode`, `pdg.EventType`, `pxr.Usd`, …). The capsule reads this as "thin corpus, add more docs." It is not a doc-volume failure. It is an **instrument failure**: scout answers *"does this API exist?"* by substring-matching prose, and prose mentions only what it happens to mention.

Existence is a **membership** question, and its authority is `dir()` against the live H21.0.671 runtime — the hard gate. So the fix is not "more docs"; it is to **move the membership verdict off the corpus onto an introspected symbol table**, and keep the doc corpus for the *usage/retrieval* question it's actually good at. Two questions, two instruments.

This is a **straight build** (introspect → materialize → repoint → re-eval). No search loop, no embedder — semantic stays deferred behind this. Admission gate honored.

---

## Invariants — the Floor for this spike
- **The introspected symbol table is the sole membership authority.** Corpus presence is demoted to a retrieval hint (`documented`), never the existence verdict.
- **Phantoms must not resurrect.** All six (incl. the four quarantined) stay flagged-absent under the new source — they are genuinely absent from the runtime, so the table excludes them by construction.
- **Introspect in the interpreter scout runs in.** 671 ≠ 631 is possible; confirm parity by `dir()` before trusting a 631 table for a 671 runtime. Default: build in graphical **H21.0.671**.
- **Run introspection as a host-layer script, not over the WS transport** — multi-line transport fails; a file run inside Houdini sidesteps it. `cognitive.tools.*` stays zero-`hou`: introspection emits data; scout reads data.
- **The table is version-stamped and fails loud.** Host layer validates the running Houdini version against the table stamp at startup → warn|refuse (mirror Spike 1). Missing/corrupt/version-mismatched table reads stale, never silent-valid.
- **The eval is the verdict.** Landing criterion is `false_phantom_rate == 0`; any residual is surfaced and reasoned, never silently allowlisted.
- **Don't re-muddy the corpus.** Symbols do not get injected as corpus entries here — that conflates membership and retrieval, which is the bug. Retrieval is the semantic spike's problem.
- `cognitive.tools.*` zero-`hou`; atomic commits; race-safe push (fetch + rebase, max 3, halt on conflict); halt-and-surface before irreversible.

---

## SPIKE 2.5 — Introspected symbol table = membership authority

**ARCHITECT**
- Confirm **671 vs 631 parity** for `hou`/`pdg`/`pxr` by `dir()`; decide the introspection interpreter (default 671). HALT-and-surface if they diverge in a way that matters.
- **Depth is bounded by the eval.** Introspect deep enough that *every symbol in eval bucket (a) resolves* — modules + classes + class-level callables — no deeper. Cycle-guarded (visited set), skip dunders and `_private`, hard node cap (USD's graph is large and cyclic).
- Table schema: `{ symbols: set[str], houdini_version, depth, introspected_at, blake2b }`. Location: in the canonical store, read at load alongside the corpus.
- Repoint contract: `exists_in_runtime` (from table) = the verdict; corpus presence becomes a secondary `documented` hint. **Rename** `found_in_corpus` → `exists_in_runtime`.
- Freshness contract: host startup compares live Houdini version → table stamp; warn|refuse per Spike 1 policy. (Version read is host-layer — boundary preserved.)

**FORGE**
- `host/introspect_runtime.py`: bounded recursive `dir()` over `hou`/`pdg`/`pxr` → emit the table json into the store. Run it inside H21.0.671 → materialize.
- Repoint scout's membership check at the table; apply the flag rename; keep corpus presence as `documented`.
- Extend the host freshness check to validate the table's version stamp.
- Basic tests: table loads; a known class token resolves; rename surfaced in the result schema.

**CRUCIBLE** (adversarial, fix-forward, never weaken)
- Every eval bucket-(a) real API **resolves** in the table → `false_phantom_rate` drops.
- All six phantoms (incl. four quarantined) **still flag absent** under the new source — no resurrection.
- **Real-but-undocumented** (in table, absent from corpus) → `exists_in_runtime=true`. *(This is the exact case that was broken.)*
- **Documented-but-fake** (adversarial: present in corpus prose, absent from runtime) → flagged absent. Table is authority, corpus is not.
- Missing / corrupt / **version-mismatched** table → host surfaces, never silent-valid.
- Introspection **terminates** under cycles / large graph (cap + visited-set) — no hang, no OOM.

**GATE 6 — re-run the eval (the verdict)**
- `false_phantom_rate == 0` (or surfaced residual from dynamically-created attrs, handled by an *explicit, reasoned* allowlist — not a fudge).
- `true_phantom_recall == 1.0` held.
- `conceptual_topk_hitrate` unchanged (membership fix doesn't touch retrieval — sanity check; it should not move).
- Convert the Spike 2 **strict-xfail on `false_phantom_rate == 0`** into a hard green pin.

**COMMIT**
- Atomic — introspection script + membership repoint + freshness extension.
- Message: `spike 2.5  introspected symbol table = membership authority (false-phantom -> 0)`
- Race-safe push.

---

## MILE MARKER — capsule out
**WHERE WE ARE** · **MILE MARKER** (false-phantom Sev-1 closed; symbol table is the membership authority) · **BLOCKERS** (any residual real-API non-resolution; any 671/631 divergence) · **NEXT ACTION**.

**This spike un-blocks the deferred HUMAN EMBEDDER GATE.** Coverage is now clean, so semantic is no longer outranked. The standing signal carried forward is `conceptual_topk_hitrate = 0.333` — poor, so semantic is likely justified. Hand back to the v1 harness: Joe reviews the clean scorecard + the 0.333, makes the embedder call, then Spike 3 (conditional) runs.
