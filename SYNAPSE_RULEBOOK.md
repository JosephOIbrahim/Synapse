# SYNAPSE_RULEBOOK — Governing Blueprint

> **F3 notice.** This document governs execution. Commit it to `master` at repo root **before** any mile below runs. Pasting it ephemerally into a session contradicts the harness's own provenance thesis.
>
> **Status:** DRAFT → ratified on Joe's commit. **Blueprint version:** 0.1.0
> **Roles:** ARCHITECT authored this document (design only, no mutation). FORGE implements per mile. CRUCIBLE writes hostile suites and never the implementation. Commandment 7 holds: tests are never weakened; fix forward.
> **Provenance baseline:** repo `master` as publicly verified 2026-07-17 (README @ Sprint 3 Mile 4 closed, 1 tool through Dispatcher, 104 on WS path, 6 knowledge tools exempt). If local HEAD is ahead, FORGE re-verifies counts at Mile 0 and corrects this header in the same commit.
>
> **[CORRECTED · Mile 0 · 2026-07-17 · FORGE]** Local HEAD **is** ahead of the public mirror (by docs-only commits). Release tag **`v5.28.0`** (`72de5f1`); at HEAD the registry carries **115 registered tools** — verified `len(synapse.mcp._tool_registry.TOOL_DEFS) == 115` (`python/synapse/mcp/_tool_registry.py`), pinned by the `documented == actual` assert in `tests/test_phase0c_doc1_toolcount.py:42` (counter helper at :24-25), banner at `CLAUDE.md:3`, `pyproject.toml:8`. The `1 Dispatcher + 104 WS + 6 knowledge = 111` figures above are the **stale v5.5.0-era public-mirror snapshot** that this blueprint's own §G9 flags as public-mirror drift; the Dispatcher/WS/knowledge split is **not** re-derived at HEAD (not load-bearing for Mile 0) — the +4 tool delta since the snapshot is INFERENCE pending a later mile.

---

## 0 · What the Rulebook is

One sentence: **the Rulebook is SYNAPSE's Core Specification — the versioned, machine-readable contract that agents build against and CI enforces — harvested from the live runtime because SideFX publishes none.**

The nanousd-labs method (AOUSD spec as contract → agents generate → spec-derived tests validate) proved that agents grind mechanical work reliably *when the contract is formalized first*. SYNAPSE already runs the discipline — phantom API gate, U.1 catalog, F3, CRUCIBLE, flywheel — but the contract knowledge is scattered across audits, protocols, commit messages, and test suites. The Rulebook unifies it into one indexed, enforced structure.

**The defining property — enforcement coupling.** A rule in `docs/` is prose; it drifts. A rule in the Rulebook is law: if its status is `ratified` and it has no green test binding, **CI fails**. If a quarantined phantom symbol appears anywhere in source, **CI fails**. If a harvested surface file is hand-edited, **CI fails**. Everything else about this document serves that property.

---

## 1 · First principles

**P1 — The runtime is the spec.** Documentation lies (`hou.pdg.*`), training priors lie (`pdg.PyEventCallback`), and only `dir()` against the live build tells the truth. Every normative statement carries provenance: how verified, which build, which interpreter, when. The truth contract applies to the Rulebook itself.

**P2 — Contracts precede code.** The Rulebook section for a context (SOP, DOP, CHOP, VOP) must exist and be ratified before FORGE ports tools in that context. This is F3 generalized, and it is G9's pre-flight gate (validation precedes mutation) given a permanent home.

**P3 — Every rule is testable or it isn't a rule.** Rules without tests are documentation. Tests without rules are folklore. The manifest binds them, and the binding is CI-checked.

**P4 — Goldens are evidence; contracts are law.** The 104 working WS tools exhibit production behavior *today* — that observed behavior is the spec for each tool's port. But where a golden captures a bug, the contract declares the deviation and the intended behavior wins. Evidence informs; law decides.

**P5 — Durable per build, elastic across builds.** Each Houdini build gets a frozen surface snapshot. When H22 lands, harvest again and **the diff is the migration worklist** — the G2 gate stops being an unknown and becomes a generated report.

**P6 — Human gates stay human.** Harvest is automated. Ratification is Joe. The Michael Gold RFC gate on USD `customData` / typed schema is encoded as a status, not a suggestion. The three existing human gates (Gate 0.1, `drop.json`, merge to main) are untouched and unautomated.

---

## 2 · The artifact

Root-level `rulebook/` — it is a **build input**, not documentation, and sits parallel to `python/`, `tests/`, `docs/`. Existing evidence (spike audits, U.1, crucible protocol) **stays where it lives**; the Rulebook indexes it. No file moves. Conformance tests live in `tests/rulebook/` so the existing pytest runner collects them with zero config change.

```
rulebook/
├── RULEBOOK.md                  # constitution — how to read, cite, and amend (Mile 0)
├── VERSION                      # rulebook semver, independent of code VERSION
├── manifest.json                # the machine index — sections, rules, statuses, test bindings, provenance
├── surfaces/                    # HARVESTED — regenerable, never hand-edited
│   └── h21.0.671/
│       ├── _meta.json           # build string, interpreter, harvester version, timestamp, checksums
│       ├── hou_root.json        # dir(hou) + inspectable signatures — graphical AND hython captured separately
│       ├── sop.json  dop.json  chop.json  vop.json  lop.json  cop.json
│       ├── pdg.json             # standalone pdg.* surface (hou.pdg is a phantom — PH-001)
│       └── connectivity.json    # U.1 registered by reference (locate existing artifact; do not fork)
├── phantoms.json                # quarantine registry — confirmed-absent symbols + evidence anchors
├── failures/                    # failure-class registry — SF-N numbering preserved
│   └── SF-8-split-scope.md
├── contracts/                   # NORMATIVE — human-ratified law
│   ├── boundary.md  threading.md  undo.md  transport.md  auth.md  scope.md
│   ├── usd_customdata.md        # status: rfc-gated (Michael Gold)
│   └── tools/
│       ├── _TEMPLATE.md         # Appendix A
│       └── <tool_name>.md       # one per ported tool — the answer keys
├── goldens/                     # captured WS-tool behavior — JSON envelopes (§6)
└── fixtures/                    # programmatic scene builders — deterministic, no binary .hip

scripts/rulebook_harvest.py      # in-process surface harvester (Mile 1)
scripts/rulebook_diff.py         # surface differ — the future G2 instrument (Mile 1)
tests/rulebook/                  # meta-tests + conformance + golden replay (Miles 0–4)
```

---

## 3 · Rule anatomy

**IDs.** `RB-<DOM>-NNN` for rules (`RB-THR-001`), `PH-NNN` for phantoms, `SF-N` preserved for failure classes, `g-<context>-<tool>-NNN` for goldens. IDs are permanent; superseded rules keep their ID with status flipped.

**Statuses.** `draft` (advisory — FORGE may read, must not rely) · `ratified` (binding — CI-enforced) · `rfc-gated` (blocks all dependent work until the named RFC lands; no test binding required to hold the gate) · `superseded` (kept for citation; replacement named).

**Provenance kinds.** `empirical` (live `dir()` / observed behavior, build-stamped) · `audit` (existing spike audit, cited in place) · `repo` (enforced by existing code/test, cited by path) · `golden` (captured envelope).

**Manifest schema** (validated by meta-test at Mile 0):

```json
{
  "rulebook_version": "0.1.0",
  "runtime_baseline": {
    "houdini_graphical": "21.0.671",
    "hython": "21.0.631",
    "python": "3.11",
    "platform": "win_amd64"
  },
  "contracts_checksum": "<sha256 of contracts/ tree — recomputed by meta-test>",
  "sections": [
    {
      "id": "RB-THR",
      "path": "contracts/threading.md",
      "status": "ratified",
      "ratified_by": "joe",
      "ratified_on": "YYYY-MM-DD",
      "rules": [
        {
          "id": "RB-THR-001",
          "summary": "hou.hipFile event handlers run on MainThread; call hou.* directly, never hdefereval main→main",
          "tests": ["tests/rulebook/test_threading_bindings.py::test_hipfile_events_main_thread"],
          "provenance": {
            "kind": "audit",
            "source": "docs/sprint3/spike_3_2_scene_load_audit.md",
            "verified_build": "21.0.671"
          }
        }
      ]
    }
  ]
}
```

---

## 4 · Discipline — the enforcement layer

Five meta-tests, written at **Mile 0**, green forever after:

1. **Schema** — `manifest.json` validates; statuses from the enum; every section path exists.
2. **Binding** — every `ratified` rule lists ≥1 test node ID that pytest actually collects and passes. A ratified rule with a missing or red binding fails the suite by name.
3. **Surface integrity** — every file under `surfaces/` carries `generated_by` + checksum in `_meta.json`; recomputed checksum must match. Hand-edits die in CI.
4. **Amendment lock** — recomputed `contracts/` tree hash must equal `contracts_checksum`. Any contract edit forces a deliberate manifest bump + rehash in the same commit. No silent law changes.
5. **Phantom lint** — grep-scan of `python/synapse/` (excluding `_vendor/`) for every symbol in `phantoms.json`. Any reference to a quarantined symbol fails CI. Same mechanism as `tests/test_cognitive_boundary.py`, pointed at the quarantine list. This moves the phantom gate out of human memory and into the build.

**Amendment protocol.** Surfaces: regenerate via harvester only, PR shows the diff. Contracts: `draft` → `ratified` is a Joe action recorded in the manifest (`ratified_by`, `ratified_on`). Phantom re-litigation is forbidden absent new empirical evidence from a **newer build** — encode as `RB-META-001`. `rfc-gated` flips only when the RFC reference lands in the contract file.

**RFC gate, operationalized.** `contracts/usd_customdata.md` opens `rfc-gated`, naming Michael Gold and scope (`customData:synapse:*` writes, typed USD attribute schema). Add a draft lint (advisory until ratified): new `customData` write sites outside an allowlist must cite an RFC ID or fail. FORGE structurally cannot ratify around the gate.

---

## 5 · Execution plan — six miles

MODE A note: Miles 0–2 are introspection + new files + tests — Phase-0 compatible. Mile 3 drives tools inside **synthetic throwaway scenes only** — never user files. Mile 4 mutates product code under G1, which is ranked sprint work on pinned H21 and is **not** `drop.json`-gated. Mile 5 is horizon; it runs when H22 exists and only after the H21 baseline is clean.

| Mile | Name | Role | Runtime needed |
|---|---|---|---|
| 0 | Charter | FORGE (from this doc) | none |
| 1 | Harvester + differ | FORGE | hython headless; one 2-min Joe run in graphical |
| 2 | Backfill the law | FORGE builds, **Joe ratifies** | none |
| 3 | Golden capture + keystone | FORGE | hython bulk; GUI queue for UI-bound tools |
| 4 | Pilot port slice (G1) | ARCHITECT→FORGE→CRUCIBLE per tool | mixed |
| 5 | H22 diff (horizon) | scripted | H22, post-`drop.json` |

**Mile 0 — Charter.** Create the `rulebook/` skeleton, `RULEBOOK.md` constitution (condensed from §§1–4 here), `manifest.json` (empty-but-valid), `tests/rulebook/test_rulebook_meta.py` implementing all five meta-tests, and the CLAUDE.md stanza (Appendix B). Re-verify the tool counts in this doc's header against local HEAD; correct if stale.
**Done when:** full suite green including meta-tests (trivially, on an empty ratified set); one commit; the discipline exists before any content does.

**Mile 1 — Harvester + differ.** `scripts/rulebook_harvest.py`: runs in-process, **read-only introspection, zero scene mutation, zero network**. Walks `dir(hou)` with `inspect` signatures where inspectable; enumerates node type categories per context (SOP/DOP/CHOP/VOP/LOP/COP) via `hou.nodeTypeCategories()`; captures standalone `pdg.*`. Two capture modes — graphical 21.0.671 and hython 21.0.631 — stored as separate keys, because the site-packages split is real and the divergence (e.g., `hou.ui`) is itself contract data. Output: sorted, stable-ordered JSON for clean diffs. `scripts/rulebook_diff.py`: structural diff of two surface trees → markdown report (added / removed / signature-changed). Locate the U.1 artifact and register it in the manifest by reference with its existing ratification provenance — **do not duplicate it**.
**Done when:** `surfaces/h21.0.671/` populated from both interpreters, meta-test 3 green, differ produces an empty report against itself, Joe has eyeballed one context file. The hython run is Claude Code–drivable; the graphical run is one line Joe pastes into the Python Shell.

**Mile 2 — Backfill the law.** Convert existing verified knowledge into contract files with bindings (full inventory: Appendix C). Where a binding test already exists (`tests/test_cognitive_boundary.py` → `RB-BND-001`; `check_no_rigging_drift` → `RB-SCOPE-001`), bind it. Where none exists, write the conformance test or leave the rule `draft`. Populate `phantoms.json` (activating the phantom lint) and `failures/` (SF-8 et al., cross-referencing the bun `.env` injection hazard under auth). **Fold in the known public-README defect:** install §3 currently instructs `setx ANTHROPIC_API_KEY` — rewrite to the `SYNAPSE_ANTHROPIC_KEY` resolver path in the same commit that ratifies `contracts/auth.md`, so the public doc and the law land together.
**Done when:** Joe ratifies the batch (statuses flip, manifest records it), phantom lint is live in CI, and the suite is green.

**Mile 3 — Golden capture + keystone.** Build the capture harness: drive existing WS-path tools inside synthetic scenes from `rulebook/fixtures/` (programmatic builders, deterministic seeds — reproducible and diffable, no binary `.hip` where avoidable), record request/response envelopes (§6) to `rulebook/goldens/`. Bulk-capture every hython-reachable tool; queue GUI-dependent tools for a Joe session with an exact checklist.
**Keystone:** `synapse_inspect_stage` is the only tool living on **both** paths today. Capture its goldens through the WS path *and* the Dispatcher path; assert equivalence in `tests/rulebook/test_keystone_equivalence.py`. That one green test proves the entire method end-to-end before scaling it 104×.
**Done when:** keystone green, bulk capture landed with provenance stamps, GUI-capture queue written.

**Mile 4 — Pilot port slice.** Default lane: **SOP family, 5–10 tools** (Joe may swap the lane in this doc before Mile 4 starts; that edit is expected, not scope drift). Per tool, in order: golden exists → contract from `_TEMPLATE` (schema, behavioral rules, edge semantics, hostile cases, declared deviations) → **Joe ratifies** → FORGE ports per the existing three-step pattern (pure function under `synapse.cognitive.tools.<name>`, schema dict, adapter swap to `dispatcher.execute`) → golden replay green through the Dispatcher (modulo declared deviations) → CRUCIBLE hostile suite from the contract's hostile section → phase gate. Instrument the slice: tokens and wall-time per tool logged to a flat file — **this seeds the G6 benchmark harness for free.**
**Done when:** slice green end-to-end, per-tool cost numbers exist, and the pattern is measured. The remaining ~95 tools become flywheel grind under a proven, priced pattern — not a mile, a metronome.

**Mile 5 — H22 diff (horizon, do not start).** On H22 + `drop.json`: harvest `surfaces/h22.x.y/`, run the differ against `h21.0.671/`, and the report **is** the G2 migration worklist — every removed symbol, changed signature, and new phantom, generated instead of discovered. One paragraph now; one command later.

---

## 6 · Golden envelope + deviation protocol

```json
{
  "golden_id": "g-sop-<tool>-001",
  "tool": "<registry name>",
  "transport": "ws | dispatcher",
  "fixture": "rulebook/fixtures/sop_basic_grid.py::build",
  "request": { },
  "response": { },
  "build": "21.0.671",
  "interpreter": "hython | graphical",
  "captured": "YYYY-MM-DD",
  "commit": "<sha at capture>",
  "status": "evidence | superseded",
  "notes": ""
}
```

Goldens carry the commit they were captured at; if legacy behavior changes before a port lands, re-capture — never hand-edit an envelope. When a golden captures a bug, the tool's contract declares it: `deviation: g-sop-x-003 exhibits <observed>; intended <behavior>; port implements intended; golden marked superseded`. Replay tests honor declared deviations and nothing else. **Evidence informs; law decides.**

---

## 7 · Constraints and non-goals

- **No nanousd dependency.** The method is adopted; the runtime is not. Houdini's own pxr build remains the sole composition authority. (One optional, zero-risk sibling task: ingest the public AOUSD USD Core Spec as a `synapse_scout` corpus — retrieval only, no runtime coupling.)
- **No file migration.** Existing audits, U.1, and protocols are cited in place. The Rulebook is an index and an enforcer, not a reorganization.
- **No wiki drift.** If it doesn't gate, it doesn't belong. Prose that can't bind to a test goes to `docs/`, not `rulebook/`.
- **No rigging.** `RB-SCOPE-001` binds the existing drift check; KineFX-touching candidates are structurally dead. VOP is graph plumbing only, never shader authoring.
- **Never weaken tests.** Commandment 7 applies to conformance and goldens alike — a red golden means fix the port or declare the deviation in law, never edit the evidence.
- **Human gates unautomated.** Ratification, Gate 0.1, `drop.json`, merge to main, and the Michael Gold RFC remain human acts.

---

## 8 · Payoffs ledger

| Gap | What the Rulebook does to it |
|---|---|
| **G1** (port debt) | Converts 104 ports from rewrite-and-hope into golden-gated regeneration — mechanical FORGE grind at a measured per-tool cost |
| **G2** (H22 re-grounding) | The gate becomes `rulebook_diff h21.0.671 h22.x` — a generated worklist, not an investigation |
| **G6** (benchmarks) | Mile 4 instrumentation produces the first real tokens-per-task numbers as a side effect |
| **G9** (pre-flight gate) | Validation-precedes-mutation gets a permanent, CI-enforced home |
| Phantom discipline | Leaves human memory, enters the build (phantom lint) |
| Positioning | "Spec-grounded agent development" is now industry-legible — NVIDIA published the pattern; SYNAPSE ships it against a live runtime, which is the harder problem |

---

## Appendix A — `contracts/tools/_TEMPLATE.md`

```markdown
# RB-TOOL-<name>

status: draft | ratified          ratified_by: —          ratified_on: —
context: SOP | DOP | CHOP | VOP | LOP | COP | PDG | none
legacy_transport: ws              goldens: g-<...>-001..N

## Schema
<description + JSON Schema — verbatim what registers with the Dispatcher>

## Behavior
<numbered normative statements; each cites a golden, a surface entry, or an audit>

## Edge semantics
<empty inputs, missing nodes, locked parms, error envelope shape — each testable>

## Deviations
<golden_id → observed vs. intended; empty if none>

## Hostile cases (CRUCIBLE owns)
<minimum set the hostile suite must cover; CRUCIBLE may add, never remove>

## Bindings
<test node IDs — replay + conformance + hostile>
```

## Appendix B — CLAUDE.md stanza (verbatim, added at Mile 0)

```markdown
## Rulebook discipline
- `rulebook/` is law. Before touching any `hou.*` surface, check `surfaces/<build>/` and `phantoms.json`.
- `ratified` rules bind; `draft` advises; `rfc-gated` blocks until the named RFC lands.
- Never hand-edit `surfaces/` — regenerate via `scripts/rulebook_harvest.py`.
- Every port: golden first, contract ratified, then code. Goldens are evidence; contracts are law.
- Never reference a quarantined symbol; the phantom lint fails CI.
```

## Appendix C — Mile 2 backfill inventory

| Rule | Source of truth | Binding |
|---|---|---|
| RB-BND-001 · cognitive layer: zero `hou` imports | repo — lint-enforced | `tests/test_cognitive_boundary.py` (exists) |
| RB-THR-001 · hipFile events fire MainThread → direct calls, no main→main hdefereval | audit — spike_3_2 | new conformance test |
| RB-THR-002 · PDG handlers read `pdg.*` only, no `hou.*` (off-main threads) | audit — spike_3_0 / 3_1 | bind existing tops_bridge hostile tests |
| RB-THR-003 · `submit_turn` returns `TurnHandle` immediately; blocking variant for headless | repo — Spike 2.4 | bind existing TurnHandle suite |
| RB-UND-001 · mutating dispatches wrap `hou.undos.group()`; LosslessExecutionBridge never on live transport | repo — 37 call sites | new grep/conformance test |
| RB-TRN-001 · WS `execute_python` is single-line only; sequential calls for multi-line | empirical — known failure | new conformance test |
| RB-AUTH-001 · resolver honors `SYNAPSE_ANTHROPIC_KEY`; `ANTHROPIC_API_KEY` never set permanently; `OCIO`/`WS_PORT` preserved | repo + guardrail | new test + README §3 rewrite same commit |
| RB-EXE-001 · split-scope templates re-publish helpers into exec globals | failure class SF-8 | bind existing regression |
| RB-SCOPE-001 · no KineFX/rigging; VOP plumbing only | repo — drift check | `check_no_rigging_drift` (exists) |
| RB-USD-001 · `customData:synapse:*` writes RFC-gated (Michael Gold) | governance | rfc-gated; draft customData lint |
| PH-001..N · `hou.pdg.*`, `hou.secure`, `hou.lopNetworks()`, `hou.updateGraphTick()`, `pdg.PyEventCallback` | empirical — quarantine | phantom lint (Mile 0) |

---

*The spec is durable. The agents are elastic. The runtime is the truth.*
