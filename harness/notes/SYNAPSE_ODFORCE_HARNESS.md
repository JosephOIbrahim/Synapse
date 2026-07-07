# SYNAPSE_ODFORCE_HARNESS.md

> **What this is:** The harness for SYNAPSE **additions** — the intake contract every proposed capability runs through before it can touch `flywheel_queue.json`. Refined from the grounded scour pass; every anchor re-verified against **HEAD `d34f2f7` · `master` · VERSION `5.20.0`**.
> **What it produces:** One queue-eligible track. The ODFORCE scour's surviving crown jewels enter as the **D track (DIAGNOSTIC truth)** via the companion artifact `spec-D-diagnostic-truth.md` — the evidence file the schema demands.
> **Supersedes:** `SYNAPSE_ODFORCE_SCOUR.md` (memory-built Filter 1, invalid queue schema) and refines `SYNAPSE_ODFORCE_SCOUR_GROUNDED.md` (reported, didn't govern).
> **One-line thesis:** A candidate is not a feature request — it's a claim about truth SYNAPSE doesn't yet hold. The harness's job is to make every claim earn its evidence artifact *before* it can ask a human for ratification.

---

## 00 · Corrections ledger — what this refinement pass caught

The grounded doc was re-audited against source. Four findings change dispositions; carried per the truth contract:

| # | Finding | Consequence | Anchor |
|---|---|---|---|
| 1 | The **declared** allowlist is `{cop, lop, sop, karma, usd}` — narrower than the checker's in-scope ceiling (`{…, mat, solaris, obj}`). The file is the authority; the ceiling is tolerance. | Filter 1 quotes the file. Material authoring rides the LOP/USD/Karma umbrella (materiallibrary/assignmaterial are LOP nodes), not a standalone `mat` claim. | `python/synapse/server/authoring_domains.json`; `checks.py:327-331` |
| 2 | **`kinefx` is an enforced drift term** — `{apex, rig, rigging, kinefx, muscle, cfx}` entering the allowlist is a *deterministic guardrail failure*. | **KineFX skeleton repair (scout O.12) is DEAD.** Not "needs scope confirm" — structurally out, same class as APEX. | `checks.py:332` (`drift_terms`); allowlist `note` field |
| 3 | **`cops_to_materialx` already ships** (audited: exactly **21** COP tools — memory's count verified to the digit). | Scout's COP↔MaterialX candidate (O.8-adjacent) reclassifies **shipped**, not new. | `mcp_tools_cops.py` `TOOL_NAMES` (21 entries) |
| 4 | Diagnostic surface is greenfield **except TOPs**: `handlers_tops/diagnostics.py` already does dirty→recook diagnosis for TOP nodes, and `dispatcher.py` carries a `traceback_str` error envelope. | The D track **extends a precedent** (TOPs diagnostics → all contexts) and **builds on a substrate** (dispatcher traceback). Not invention — extension. Anti-phantom-hardening satisfied. | `handlers_tops/diagnostics.py:36`; `handlers_tops/cook.py:361`; `cognitive/dispatcher.py:71-91` |

Plus one binding trap inherited from spec-C, now honored here: **renders are never part of a golden** — *"Indie husk silently no-ops — a render golden would be dishonest headless."* (`spec-C-context-capability.md`, Ground truth §.)

---

## 01 · The operating basis — Reading A, and why D.0 doesn't care

**Assumption, one line:** the ratified boundary (`SYNAPSE_H22_BOUNDARY.md`, RATIFIED 2026-06-27) + the enforced allowlist govern over the memory-doctrine "never materials/renderer" — per the F3 rule, the committed and ratified artifact wins.

**The robustness property worth naming:** the D track is **scope-safe under both readings.** Reading cook flags, dirty-propagation, and callback tracebacks is *pure procedural-logic-layer observation* — no material authored, no render invoked, no pixel touched. If you later decide the forward scope narrows to procedural-only (Reading B), D survives unchanged. It is the one track from the scour that is decision-proof. That's another reason it goes first.

If Reading B *is* your intent, it's a positioning decision with its own artifact (an update to `authoring_domains.json` + the boundary doc) — a separate cycle, not a blocker here.

---

## 02 · The intake contract — four filters, one evidence rule, one ladder

Every proposed addition — scour-sourced, forum-sourced, or your own — runs this in order. **First failure stops the candidate.**

### Filter 1 — Declared scope
In-scope = the **declared** set: `{cop, lop, sop, karma, usd}` (`authoring_domains.json`). Hard-out = drift terms `{apex, rig, rigging, kinefx, muscle, cfx}` (deterministic failure, `checks.py:332`). Out on **process boundary** (not scope): anything requiring another DCC's process — Nuke, Maya, Substance. CHOP/OBJ: excluded per spec-C ("low creation leverage"), revisitable only with its own evidence.

### Filter 2 — Moat tier
*Does solving it require in-process probe-verified truth?* **CROWN** = impossible without live cook-state/runtime context. **STRONG** = needs live introspection or undo-safe mutation. **COMMODITY** = knowledge lookup any external LLM approximates → folds into existing tools, never queues standalone.

### Filter 3 — Phantom gate
No confirmed-absent API on the critical path (`hou.pdg.*`, `hou.secure`, `hou.lopNetworks()`, `hou.updateGraphTick()` — auto-quarantined, never re-litigated). Every *new* `hou.*` symbol a candidate depends on enters its spec as **UNVERIFIED** until a `dir()` probe against live 21.0.671 confirms it — the spec-0.2 pattern. Enforcement is already free: `check_phantom_clean` (`checks.py:425`) runs on every sprint's added lines.

### Filter 4 — Anti-phantom-hardening (the "already shipped?" audit)
Grep the handler surface before designing. A candidate overlapping a shipped mixin/tool reclassifies as **EXTENSION** (logged against the mixin, smaller shape) or **DONE** (dropped). This filter is what caught `cops_to_materialx`, the MCP provider (D-H22-1, built), and the TOPs diagnostics precedent.

### The evidence rule *(the schema's own law — the scout's queue died on this)*
`flywheel_queue/v1`: **"Every entry must carry evidence (artifact paths) — evidence-free entries are invalid."** A surviving candidate's *first deliverable is always a `spec-*` note* in `harness/notes/` — that note **is** the evidence that makes the queue entry legal. No spec, no entry. This is how C.0 and S.0 were born; D.0 follows the same birth canal.

### The graduation ladder
1. **Filters 1–4 passed**, each verdict cited to an anchor.
2. **Spec note committed** (evidence exists).
3. **Queued `ratified:false`** — a proposal, never a work order.
4. **Human ratifies** — the anti-runaway anchor. Never automated.
5. **Track trigger armed** — the track's own state-file/catalog trigger (pattern: `drop.json` → Mode B; `context_capability_21.json` → C.1+; `posture.json` → S track). D's trigger is defined in its spec.

The three untouchable human gates, confirmed in source: ratification (`flywheel_queue.json` `_doc`), `drop.json` (drop.json.example `_doc`, armed on existence by run.ts), merge (S.0 note: "never merges").

---

## 03 · Final dispositions — the scour, fully adjudicated

| Candidate (scout id) | Disposition | One-line reason · anchor |
|---|---|---|
| Cook-graph / recook explainer (O.1) | **→ D.0 — QUEUE-ELIGIBLE** | CROWN; greenfield outside TOPs; extends `handlers_tops/diagnostics.py` precedent to all contexts |
| Callback/expression runtime debugger (O.3) | **→ D.1 (staged in spec-D)** | CROWN; builds on `dispatcher.py` `traceback_str` substrate; second leg of the same track |
| Migration diagnostic (O.2) | **EXTENSION of spec-0.2** | The delta-probe *is* the machinery; H19→H21 is a repoint, not a new track |
| Bulk HDA param authoring / auto-UI (O.4/O.5) | **C-track extensions** | `HdaHandlerMixin` ships; consumes U.2/U.3 truth; lands after C.0 ratifies |
| MCP truth-contract provider (O.7) | **DONE** | `mcp_server.py` + `check_mcp_truth_contract` + D-H22-1 |
| Old→Copernicus COP translator (O.8) | **C-track (COP) — genuinely new capability on shipped surface** | `CopsHandlerMixin` exists; no old→new bridge does |
| COP↔MaterialX interop | **SHIPPED** | `cops_to_materialx` (audit, §00 #3) |
| AOV / render-var builder (O.10) | **EXTENSION** | `synapse_configure_render_passes` + `RenderHandlerMixin` ship |
| Sim-diagnostic (O.11) | **C-track (DOP) candidate** | DOP probeable; capability-truth axis |
| KineFX skeleton repair (O.12) | **DEAD** | `kinefx` = enforced drift term (§00 #2) |
| TOP/PDG authoring slice (O.13) | **Mostly shipped** | `handlers_tops/` cook + diagnostics + farm tools exist; `hou.pdg.*` runtime slice stays dead |
| Material-binding auditor | **EXTENSION of U.5 advisory** | `assignmaterial→material-source` advisory ships (U.5 note) |
| Shader scaffolder / node-equivalence / wrangle boilerplate / modeling recipes | **COMMODITY — fold in** | Filter 2; never queue standalone |
| Cross-renderer parity | **OUT — process boundary** | Redshift/Maya are other processes/undeclared domains |

**Net:** one new track (D), two of the scour's three "genuinely new" findings live inside it, everything else is extension, done, dead, or folded. The scour's real yield was **one cycle class**, not thirteen features — which is exactly what a depth-before-breadth system should extract from a breadth-shaped input.

---

## 04 · What this harness hands off

- **`spec-D-diagnostic-truth.md`** (companion artifact, written) — the frozen-spec-shaped evidence file: probe, catalog, review sweep, checks, goldens, the D.0 queue entry ready to paste, staged D.1.
- **Nothing else queues.** Extensions log against their mixins; C-track candidates wait for C.0's ratification; DONE/DEAD close out.
- **Your gate:** flipping `D.0` to `ratified:true` — the same human sanction U.5 received on 2026-07-03. Until then it's a proposal, and that's the correct resting state.

---

## Provenance
Fresh shallow clone this session, HEAD `d34f2f7`. Anchors re-verified live (not carried from the prior pass): `checks.py:324-345`, `authoring_domains.json`, `flywheel_queue.json` schema line, `mcp_tools_cops.py` tool count (audited to 21), spec-C structure + traps, `handlers_tops/diagnostics.py`, `dispatcher.py` traceback envelope. Read-only throughout; nothing pushed. Claims outside these anchors are labeled inference in context. F3: this file and its companion are written to be committed before any execution begins.
