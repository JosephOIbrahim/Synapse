# G9 — PRE-FLIGHT ADMISSION GATE (P7 made operational)

**`docs/PREFLIGHT_GATE.md`** · Repo: `C:\Users\User\SYNAPSE` · Grounded against HEAD `314acd6` / H21.0.671.
Module paths (`host/`, `server/`, `core/`, `mcp/`, `routing/`, `cognitive/`) are `python/synapse/`-relative — e.g. `host/graph_builder.py` = `python/synapse/host/graph_builder.py` (a *separate* repo-root `host/` holds the live-probe scripts); harness/docs paths are repo-root-relative. Every path, count, and symbol below was verified by this dispatch's own
Read/Grep/Bash; anything not locally verifiable is tagged `[UNVERIFIED — …]` or `V0` inline.

**Status: PROPOSAL — design spec (MODE A paper).**
**Governing gate:** *G9 design review* — per the blueprint gate registry (`docs/H22_AGENT_HARNESS.md:59`),
this file **merged to main IS the gate**; merging it opens the **G9 MODE B build**.
**Relay leg:** Leg 0 paper artifact (MODE A). The G9 *build* runs MODE B (post-`drop.json`); its
Pass-2 COP branch additionally blocks on the drop-week **step-5 COP re-audit** artifact
(`.claude/workflows/h22-drop-week.js:61`, whose own text reads *"G9's COP conformity pass blocks on
this output"*).

---

## OPEN DECISIONS (human-only rulings — the rest of the spec is complete without them)

The design below is executable as written. These five points are policy/naming calls the harness
must not invent; each carries the recommended default the build will assume **if the human says
nothing**, so no deliverable is blocked on a ruling.

1. **The COP-re-audit dependency's canonical name.** The brief names it *"the G2 COP re-audit."*
   I could not verify a gate literally named `G2` for COPs: the blueprint's `G1–G9` are *gaps*, and
   `G2` in the harness playbook (`docs/H22_AGENT_HARNESS.md:111`) is a **golden task** (the Leg-0
   spec deliverable), not a COP gate. The concrete artifact that G9's COP pass depends on is
   **drop-week runbook step 5** (`.claude/workflows/h22-drop-week.js:61`), which emits per-tool
   `PASS/CHANGED/GONE` for the Copernicus surface. *Recommended default:* treat "the COP re-audit"
   as **that step-5 artifact**; keep the `G2` label only if the human confirms an out-of-band mapping.

2. **Which transport/build path G9 sits on.** The shipped graph-synthesis build path is the **live
   `/synapse` host command handlers** `_handle_propose_graph` / `_handle_instantiate_graph`
   (`server/handlers_graph_synth.py`), which marshal onto Houdini's main thread (`run_on_main`) and
   drive `GraphBuilder` — whose OWN `hou.undos.group` wraps the whole build and rolls back to **zero
   net mutation** on any build exception (`host/graph_builder.py:131`, `:165-188`). That is a *complete*
   undo transaction, distinct from the partial-undo `handlers_node.py` create/set-parm handlers
   CLAUDE.md §1.2 flags. So G9 does **not** need `shared/bridge.py` for reversibility — it layers on
   this shipped path. The open question is whether G9 must *also* cover the `/mcp` and autonomous
   dispatch surfaces (S.1/S.2 territory, `harness/notes/spec-S-studio-readiness.md`). *Recommended
   default:* **reuse the shipped live host-handler build path as-is** (its undo + rollback-to-zero is
   complete for graph synthesis); transport-agnostic admission across `/mcp`/autonomous paths is a
   follow-on gated behind S.1's single-source policy table.

3. **Colorspace enforcement when the show is silent.** `show_config.color.{ocio,display,view}`
   default to `""` — a documented "use `$OCIO`/Houdini defaults" sentinel (`core/show_config.py:73`),
   and the keys are labelled *forward keys* (declared, enforcement-wiring `[UNVERIFIED — no COP OCIO
   read surface exists today; see §Ground truth]`). *Recommended default:* Pass 2 enforces a working
   space **only when the show config explicitly declares one**; an unset policy is deferred to Houdini,
   never a gate-injected ACEScg conversion the show never asked for.

4. **The repair-vs-refuse boundary for context failures.** Pass 1 *refuses* (structural = not
   admissible). Pass 2 *repairs* by injection (context = conformable). Which conformity failures are
   injection-repairable vs. refusal-worthy is a small policy table. *Recommended default:* resolution
   divergence → repairable (inject resize); undeclared/absent colorspace → advisory; a COP whose type
   the step-5 re-audit marks `GONE` → **refuse** (the graph names a tool that no longer exists).

5. **Whether a strictly `hou`-free refusal is required — and, if so, which existence oracle.** The
   shipped validator is grounded by the **hou-backed oracle pair** `HouExistenceOracle` +
   `ConnectivityOracle` (`host/existence_adapter.py`, `host/graph_oracle.py`), injected by
   `graph_synth_runtime._build_validator` (`:53-62`); both `import hou` at construction and answer
   existence/arity via `hou.nodeType(...)` / `parmTemplateGroup().find(...)` — **read-only,
   non-mutating**. If G9 reuses this pair (the recommended reuse), then on a REFUSED proposal **hou
   READS execute** (type/param lookups) but **zero hou mutations** — hence DoD-1 is stated as *zero
   hou mutations*, not *zero hou calls*. A strictly `hou`-free refusal (e.g. to refuse in a
   headless/no-hou context) would need a **pure** existence oracle. The naive "scout symbol table"
   backing is **refuted by shipped evidence**: `existence_adapter.py` (§2.6) documents that scout's
   doc-presence wrapper false-negatives real node types (a bare `box` is not a dotted `hou.*`
   symbol), so scout cannot authoritatively answer node-type existence. The viable hou-free backing
   is the connectivity catalog's **282 `Category/type_name` keys** (probe-verified membership) — but
   that covers only catalogued types (partial). *Recommended default:* **reuse the shipped hou-backed
   pair** (read-only existence, zero mutations), DoD-1 = zero hou mutations; build a pure
   catalog-membership existence oracle only if the human requires a hou-free refusal.

---

## Definition of Done

The G9 gate is DONE when a proposed graph IR cannot reach a single `hou` mutation without passing
structural admission, and when every context repair it performs is one atomic, provenance-tagged,
reversible transaction. Concretely, the built gate satisfies all of:

- **DoD-1 — typed structural refusal.** A `GraphProposal` carrying a hallucinated `node_type` is
  REFUSED with a typed refusal that names the failing rule (`P1`) and the houdini stamp; **zero `hou`
  mutations execute**. (The validator *engine* imports zero `hou`; its existence/arity checks read
  via the hou-backed oracles — read-only, non-mutating — and a refusal never reaches `GraphBuilder`'s
  undo group, so no node is ever created. A strictly `hou`-free refusal is OPEN DECISION 5.)
- **DoD-2 — arity/wire legality from the catalog.** A proposal wiring into an input index `≥` the
  probe-verified `max_inputs`, or naming a target-slot label the type does not carry, is REFUSED
  naming rule `P3a`/`P3e` with the arity/labels quoted from `verified_connectivity_21.0.671.json`.
- **DoD-3 — fail-closed on catalog loss.** A missing/corrupt/schema-mismatched/checksum-failed
  connectivity catalog makes the gate **REFUSE**, not silently fall back to the weaker oracle-only
  check. (This is the one deliberate divergence from the shipped validator's non-strict posture.)
- **DoD-4 — Pass 2 runs only on an admitted IR.** Context conformity never touches an IR that failed
  Pass 1. When a fix node IS injected it is appended to the admitted proposal so it builds **inside
  the same `hou.undos.group`** as the rest of the graph (`GraphBuilder`, `graph_builder.py:131`) and
  carries a `gate-injected` provenance tag on the build receipt.
- **DoD-5 — COP pass is advisory until the re-audit.** Until the H22 COP re-audit artifact (OPEN
  DECISION 1) exists, Pass 2's COP branch **flags divergence and injects nothing** — it must never
  auto-mutate against a `V0` Copernicus symbol.
- **DoD-6 — one transaction, rollback to zero net mutation.** Build runs through the shipped
  `graph_synth_runtime.instantiate` → `GraphBuilder` path (`host/graph_builder.py`): it re-validates
  the proposal **unconditionally** against the current live scene first (`:112-120`) — INVALID ⇒
  **HALTED**, zero mutation, the undo group never entered; otherwise the whole build
  (create → set-parms → connect) runs inside **one** `hou.undos.group` (`:131`), and any build
  exception destroys the created NEW nodes so the group nets to **zero mutation** ⇒ **FAILED**
  (`:165-188`). Every parm and connection is read back (truth contract) and the result reports only
  observed state — **no partial graph is ever left in the scene**. *There is no
  `IntegrityBlock`/`fidelity`/`composition_valid` on this path* (`graph_builder.py` references none —
  grep: 0 hits); rollback is exception-driven, not a post-verify fidelity gate.
- **DoD-7 — no unprobed symbol asserted.** Every header/resolution/colorspace read on the Pass-2 path
  (`hou.imageResolution`, COP `xRes()/yRes()`, any OCIO read) is tagged `V0` and routed to runbook
  step 9; **none is emitted into code before its V1 verdict**.
- **DoD-8 — reuse, not fork.** Pass 1 delegates to `GraphValidator` — a test pins that the gate calls
  the shipped validator and re-implements no structural rule. If a rule needs to change, it changes in
  `graph_validator.py`, not in a G9 copy.

---

## Ground truth (verified this dispatch — do not re-litigate)

The shipped structural rulebook already exists and already checks exactly what Pass 1 needs. G9 is
**pointing it backward** (running it as an admission gate before mutation), not building a validator.

- **The rulebook is `python/synapse/cognitive/graph_validator.py` (533 lines), NOT `python/synapse/routing/`.**
  A grounding correction to the brief: `python/synapse/routing/` is the tiered **IR producer** —
  `parser.py` (Tier-0 regex → `SynapseCommand`) and `planner.py` (`WorkflowPlanner` composite intents
  → `list[SynapseCommand]`); it emits command/plan streams and does **no** catalog/arity checking.
  The structural **validator** that does Pass-1's job lives in `cognitive/`. Both are reused (see the
  Reuse Map); the design is honest about where each lives.
- **`GraphValidator.validate(GraphProposal) → ValidationReport`** runs, in order:
  `_phase1_symbols` (`:93`, NEW-node `node_type` existence via `IExistenceOracle`) · `_phase2_parameters`
  (`:112`, parameter-name existence) · `_phase3_connections` (`:162`: **3a** arity, **3b** typed
  type-compat, **3c** slot-label advisory, **3d** occupied-input HALT, **3e** catalog slot semantics)
  · `_catalog_slot_check` (`:244`, the U.1 probe-verified `max_inputs`/`input_labels` check) ·
  `_phase4_structural` (`:401`: DAG acyclicity, friendly-name collision, `node_category ↔ network_type`)
  · `_phase5_context` (`:481`: parent resolves, every EXISTING `scene_path` resolves, name collision)
  · `_lop_ordering_check` (`:297`, SOLARIS-only: known-absent LOP type = HARD ERROR, ordering = advisory).
  It imports **zero `hou`**; live phases go through the `IConnectivityOracle`/`IExistenceOracle`
  Protocols (`interfaces.py`, 27 lines).
- **The IR is `GraphProposal` (`graph_proposal.py`, 84 lines).** Fields: `proposal_id`, `network_type`
  (`"SOP"|"SOLARIS"|"DOP"|"COP"|"VOP"|"MAT"`), `parent_path`, `nodes[ProposedNode]`, `edges[ProposedEdge]`,
  `natural_language_intent`, `model_id`, `merge_strategy`, `houdini_version_stamp`, `scout_snapshot_id`,
  `scene_fingerprint`. Module docstring, verified: *"Construction mutates nothing."* This is the pre-mutation
  object G9 admits. `ValidationReport{status, proposal_id, errors[], advisories[]}` and `ValidationIssue{where,
  message}` are the refusal shape — already typed, already collect-all-errors.
- **The catalog is `harness/notes/verified_connectivity_21.0.671.json`** — `schema`-versioned,
  blake2b-checksummed, **282 entries** keyed `Category/type_name`, each `{category, input_labels,
  instantiated, max_inputs, min_inputs, output_count, output_labels, sources, type_name, note}`.
  Category counts: `Sop 119, Lop 36, Cop2 23, Dop 22, Cop 19, Top 16, Chop 11, Object 10, Driver 9,
  Vop 9, Shop 4, VopNet 2, Data 1, TopNet 1`. The name is **major-pinned** — H22 requires a re-probe
  (see Non-goals / V0 ledger).
- **The loader is `core/wiring.py:load_connectivity_catalog(path=None, *, strict=True)`.** `strict=True`
  **raises `WiringError`** on missing/unreadable/schema-mismatch/checksum-mismatch (docstring, verified:
  *"the wire-time posture: a mutation must not proceed on a missing/corrupt catalog"*); `strict=False`
  returns `None` (validator posture — the additive check skips). `resolve_catalog_entry(catalog,
  category, type_name)` (`:96`) accepts exact/version-elided/bare spellings; ambiguous bare-name → `None`
  (*"no check beats a wrong check"*). `GraphValidator` currently loads it **non-strict** (`:59`).
- **The project-context source is `core/show_config.py`.** `get_show_config(hip_dir=None)` → `ShowConfig`;
  `DEFAULTS` (`:53`) carries `resolution.{render:[1920,1080], preview:[1280,720], capture:[800,600]}`
  and `color.{ocio:"", display:"", view:""}`. The `color.*` keys are labelled *forward keys* — `""` means
  "use `$OCIO`/Houdini defaults" (`:73`). This is the authoritative resolution/colorspace policy Pass 2
  conforms against. **`[UNVERIFIED — the enforcement wiring for `color.*` in COPs: I found no OCIO/ACEScg
  read or set surface in `server/handlers_cops.py` (grep: 0 hits). Color conformity is therefore a
  net-new Pass-2 surface, not a reuse.]`**
- **The COP resolution read today is `xRes()/yRes()`.** `handlers_cops.py:_handle_cops_read_layer_info`
  (`:397`) reads `[node.xRes(), node.yRes()]` (`:427`) with a `resx/resy` parm fallback. Those are
  H21 COP2 node methods; on H22 Copernicus they are **`V0`** (probe at step 9).
- **The shipped propose→park→build admission pipeline already enforces the core DoD invariant.** An
  IR cannot reach a `hou` mutation without passing structural admission, **today** — G9 is added on
  top of this, not building it:
  - **Propose (validate + park-only-if-VALID).** `cognitive/tools/propose_graph.py:synapse_propose_graph`
    builds a `GraphProposal` from a dict, calls `GraphValidator.validate`, and parks it **only when
    `status is VALID`** via `_STORE.put(p)` (`:90-91`) — INVALID proposals are never stored. It
    imports **zero `hou`** and returns the refusal envelope `{status, proposal_id, errors[],
    advisories[]}` (`:92-97`).
  - **Store.** `host/proposal_store.py:ProposalStore` — in-memory, TTL + size-capped; unknown id ⇒
    nothing to build.
  - **Runtime seam.** `host/graph_synth_runtime.py` holds the **single shared `ProposalStore`** both
    halves co-own (the critical invariant), `wire_propose()` configures the propose tool with the
    hou-backed validator + that store, and `instantiate(proposal_id)` drives a `GraphBuilder` bound
    to the SAME store.
  - **Build (TOCTOU re-validate → atomic build).** `host/graph_builder.py:GraphBuilder.instantiate`
    re-validates **unconditionally** before mutating (`:112-120`) — the working TOCTOU guard; a
    proposal that passed propose but whose scene changed HALTS with zero mutation.
  - **Wiring + tests.** Registered live as host command handlers (`server/handlers.py:293` mixin,
    `:708-709` `reg.register`; `mcp/_tool_registry.py:1117/1129`; lazily wired at `host/daemon.py:406`)
    and pinned by `tests/test_graph_proposal_mile1.py`, `tests/test_graph_builder_mile3.py`,
    `tests/test_graph_synth_wiring.py`.

  G9's genuine net-new is **layered on top**: the fail-closed (`strict=True`) catalog posture,
  `rule_id` tagging, Pass-2 context conformity, and the routing→proposal adapter. It does **not**
  rebuild propose / park / build.
- **The transaction mechanism is `host/graph_builder.py` — NOT `shared/bridge.py`.**
  `GraphBuilder.instantiate` opens **one** `hou.undos.group(undo_label)` (`:131`) wrapping
  create → set-parms → connect; a mid-build exception destroys the created NEW nodes (EXISTING
  untouched) so the group nets to **zero mutation** and returns `FAILED` (`:165-188`); success reads
  back every parm + connection (truth contract) and returns `BUILT` with a best-effort agent.usd
  provenance receipt (`:190-191`, `graph_synth_runtime._agent_usd_provenance`). `graph_builder.py`
  references **neither `bridge` nor `IntegrityBlock` nor `fidelity`** (grep: 0 hits) — Pass 3 reuses
  THIS. Standing up a second, bridge-wrapped builder for the same IR is the exact "a second copy is a
  bug" this spec forbids. **Live-path note:** this build runs on the live `/synapse` host handler with
  a *complete* undo group — it is NOT one of the partial-undo `handlers_node.py` handlers CLAUDE.md
  §1.2 flags (OPEN DECISION 2).
- **The Pass-1 grounding is the hou-backed oracle pair, not scout.**
  `graph_synth_runtime._build_validator` (`:53-62`) constructs
  `GraphValidator(HouExistenceOracle(), ConnectivityOracle())`; `HouExistenceOracle`
  (`host/existence_adapter.py`) and `ConnectivityOracle` (`host/graph_oracle.py`) both `import hou`
  at construction and answer existence/arity via `hou.nodeType(...)` / `parmTemplateGroup().find(...)`
  / `inputConnections()` — read-only. `interfaces.py:IExistenceOracle`'s docstring still says
  *"scout-backed"*, but the shipped implementation **pivoted to hou-backed** because scout
  false-negatives real node types (`existence_adapter.py` §2.6). So Pass-1 existence runs `hou`
  READS (OPEN DECISION 5).
- **`hou.imageResolution`** appears in the H21.0.671 headless symbol table
  (`cognitive/tools/data/h21_symbol_table.json`) as `hou.imageResolution` and `hou.IPRViewer.imageResolution`.
  **That is an existence hint only.** Its semantics (reads an image file's header → returns resolution/
  colorspace) and its H22 presence are unprobed → **`V0`, route to runbook step 9**, never asserted.

---

## The design

### Input — the proposed graph IR, before any `hou` mutation

G9 admits a **`GraphProposal`** (the declarative, mutation-free skeleton). Two producers feed it:

1. **The model emits a `GraphProposal` directly** — the intended path; the shipped
   `synapse_propose_graph` tool already accepts this dict, validates it, and parks it if VALID. The
   object is already the IR.
2. **A routing/-produced plan is lifted into a `GraphProposal`** — a thin `routing → proposal` adapter
   (net-new, §Reuse Map). *Constraint, stated honestly:* `planner.py` today emits `execute_python`
   steps whose node creation is embedded Python (e.g. `parent.createNode('vellumconstraints', …)`,
   `planner.py:279`). Those blobs are **opaque to a structural validator** — G9 cannot see typed
   nodes/edges inside a code string. So **G9 admits declarative graphs, not code blobs.** An
   `execute_python`-carrying step is the CRITICAL arbitrary-code path (CLAUDE.md §1.2) and is **out of
   G9's structural scope** — flagged, not structurally admitted (Non-goals). The adapter's job is to
   lift the *declarative* subset of a plan into typed `ProposedNode`/`ProposedEdge`; what stays as code
   stays gated by consent, not by G9.

### Pass 1 — structural admission (reuse the shipped propose gate; fail-closed)

The shipped `propose_graph.synapse_propose_graph` **already** runs `GraphValidator.validate(proposal)`
and parks the IR **only if VALID** (`propose_graph.py:90-91`) — that validate→refuse→park-only-if-VALID
pipeline IS Pass 1's admission decision, and G9 reuses it wholesale (no rule re-implemented). G9's
net-new on top is just the fail-closed catalog posture and a machine `rule_id` per issue (below).
The mapping to the brief's three admission criteria:

| Brief criterion | Shipped rule | Backing data |
|---|---|---|
| **type exists** | `_phase1_symbols` (`:93`) via `IExistenceOracle.node_type_exists` | **`HouExistenceOracle`** (`hou.nodeType`, read-only) — the shipped grounding (`_build_validator:53-62`); catalog membership (282 keys) is the hou-free alternative under OPEN DECISION 5. *Not* the scout symbol table (refuted for node types, `existence_adapter.py` §2.6). |
| **wire catalog-legal** | `_phase3_connections` 3b/3c + `_catalog_slot_check` 3e (`:244`) | `input_labels`/`output_labels` from the catalog |
| **arity** | 3a (`:183`) + 3e `max_inputs` (`:257`) | `min_inputs`/`max_inputs`/`output_count` from the catalog |

Plus the structural invariants that make an admission real: DAG acyclicity, `node_category ↔
network_type` consistency, parent/`scene_path` resolution, occupied-input HALT (`_phase3` 3d fails
**safe** to OCCUPIED, never to a pass — `:152`). All errors are collected in one pass so the refusal
names **every** fault, not just the first.

**The one gate adaptation — fail-closed catalog posture.** The shipped validator loads the catalog
`strict=False` (`:59`): no catalog → the additive P3e check silently skips, oracle checks still run.
That is correct for a *validator* but wrong for an *admission gate*: a gate that quietly weakens itself
when its evidence is missing is not a gate. G9 therefore loads with **`strict=True`** (`wiring.py:56`),
and a `WiringError` (missing/corrupt/schema/checksum) is a **REFUSAL**, satisfying DoD-3. The catalog
is major-pinned; on H22 a stale/absent catalog fails closed until the re-probe lands.

**Typed refusal, no mutation.** The validator engine imports zero `hou` (its oracle reads are
read-only — OPEN DECISION 5), and a Pass-1 failure means the gate simply does not park/proceed to the
builder, so **no mutation is possible by construction**. The refusal envelope already ships — propose
returns `{status, proposal_id, errors[], advisories[]}` (`propose_graph.py:92-97`) — so the build
adds one thin field per `ValidationIssue`: a machine **`rule_id`** (`P1`/`P2`/`P3a`/`P3b`/`P3d`/`P3e`/`P4`/`P5`),
so a caller can branch on the failing rule without parsing prose. The houdini stamp already travels
in every message (`_stamp`, `:87`) — a stale-runtime refusal is auditable from its text alone.

### Pass 2 — context conformity, COP-first (repair by injection, gate-provenance)

Pass 2 runs **only on a Pass-1-admitted IR**. It reads project policy from `get_show_config()` and
conforms the graph to it. **COP-first** because Copernicus is the H22 migration hotspot — the drop-week
step-5 re-audit exists precisely because the SOPs→COPs heightfield migration churns this surface, and
colour/resolution drift there is silent and expensive.

Two conformity classes:

- **Resolution policy.** A COP output whose resolution diverges from the show's declared policy
  (`resolution.{render|preview|capture}`) → inject a resize/scale fix node (or set the res parms) by
  **appending it to the admitted proposal before instantiate**, so it builds inside `GraphBuilder`'s
  single `hou.undos.group` (`graph_builder.py:131`), tagged `gate-injected` in the build provenance
  receipt (`ProposedNode` carries no such field today — the tag rides the receipt, net-new).
- **Colorspace policy (OCIO/ACEScg).** *Only when the show config declares a non-empty working space*
  (OPEN DECISION 3): a COP read/write whose colorspace diverges → inject an OCIO/colorspace convert
  node, same undo block, same `gate-injected` tag. When `color.*` is the empty default, Pass 2 defers
  to `$OCIO`/Houdini and injects nothing.

**Two hard honesty rails on Pass 2 (both required for DoD-5/DoD-7):**

1. **The COP branch BLOCKS on the H22 COP re-audit.** Until the step-5 artifact (OPEN DECISION 1)
   reports per-tool `PASS/CHANGED/GONE`, Pass 2's COP branch runs **advisory-only**: it flags
   divergence and **injects nothing**. It must not auto-mutate against a tool surface whose H22 shape
   is unverified. A COP the re-audit marks `GONE` becomes a Pass-1 refusal input, not a Pass-2 repair.
2. **Every read symbol on this path is `V0`.** Reading a COP's actual resolution today uses
   `xRes()/yRes()` (`handlers_cops.py:427`, H21 COP2); reading an image header is the unprobed
   `hou.imageResolution`; the OCIO read surface **does not exist yet** in COPs (grep: 0 hits). None of
   these is asserted as working in this spec or emitted into code before its runbook step-9 V1 verdict
   (V0 ledger below).

**Provenance.** Gate-injected nodes are tagged `gate-injected` so the ledger/`agent.usd` records that
the *gate*, not the artist, authored them (the harness's differentiator is the receipts — `harness/CLAUDE.md`).
They are part of the same atomic transaction as the admitted build.

### Pass 3 / commit — the shipped `GraphBuilder`: one undo group, TOCTOU re-validate, rollback-to-zero

The admitted IR (+ any Pass-2 fix nodes, appended as `ProposedNode`/`ProposedEdge`) is built through
the shipped **`graph_synth_runtime.instantiate(proposal_id)` → `GraphBuilder`** path — **G9 builds no
transaction machinery of its own** (and must not stand up a second undo-wrapped builder for the same
IR):

```
admitted IR parked in the shared ProposalStore
  └── graph_synth_runtime.instantiate(proposal_id)      # host/graph_synth_runtime.py:163
        └── GraphBuilder.instantiate(proposal_id)        # host/graph_builder.py:94
              ├── re-validate UNCONDITIONALLY vs current scene   # :112-120
              │     INVALID → HALTED (zero mutation, undo group never entered)
              └── with hou.undos.group(undo_label):      # :131 — one group, whole graph
                    create NEW (topo order) → set parms → connect edges
                    exception → destroy created NEW nodes → FAILED (zero net mutation)   # :165-188
              → read back every parm + connection (truth contract) → BUILT
              → best-effort agent.usd provenance receipt  # :190-191
```

There is **no `IntegrityBlock`/`fidelity`/`composition_valid`** on this path — rollback is
**exception-driven** (a TOCTOU-changed `createNode`, an incompatible `setInput`), not a post-verify
fidelity gate, and the readback is a *truth contract* (reports observed state), not a rollback
trigger. The three terminal states — `HALTED` (nothing created), `FAILED` (rolled back to zero),
`BUILT` (clean, read-back) — mean **no partial graph ever survives** (DoD-6). This path runs on the
live `/synapse` host handler with a *complete* undo group (distinct from the partial-undo
`handlers_node.py` handlers CLAUDE.md §1.2 flags — OPEN DECISION 2).

### Reuse Map (the design in one table)

| G9 stage | Reused, shipped (do not rebuild) | Net-new (thin) |
|---|---|---|
| IR shape | `graph_proposal.GraphProposal` / `ProposedNode` / `ProposedEdge` (84 lines) | `routing → proposal` adapter (declarative subset only) |
| Pass 1 engine | `propose_graph.synapse_propose_graph` (validate → park-only-if-VALID) + `graph_validator.GraphValidator` P1/P3/P4/P5 + the hou-backed `HouExistenceOracle`/`ConnectivityOracle` pair + `wiring.load_connectivity_catalog` + `verified_connectivity_21.0.671.json` (282 entries) | fail-closed (`strict=True`) catalog posture; per-issue `rule_id` tag |
| Pass 2 policy | `show_config.get_show_config` (`resolution.*`, `color.*`) | COP conformity rules; resolution/OCIO fix-node injectors; `gate-injected` provenance |
| Pass 3 transaction | `graph_synth_runtime.instantiate` → `host/graph_builder.GraphBuilder` (one `hou.undos.group`, TOCTOU re-validate, rollback-to-zero) + `ProposalStore` | append Pass-2 fix nodes to the proposal before instantiate; **no** new transaction machinery |

---

## DoD-per-deliverable

Each deliverable is a build-time artifact of the G9 MODE B build; this spec is done when the table
below is the agreed contract. "Reuse" rows re-implement nothing.

| # | Deliverable | Reuse / new | DoD (acceptance) |
|---|---|---|---|
| D-A | `routing → GraphProposal` adapter | new (thin) | Lifts a plan's **declarative** node/edge subset into `ProposedNode`/`ProposedEdge`; an `execute_python`-carrying step is passed through **flagged, not structurally admitted**. Round-trips a known plan to a valid proposal. |
| D-B | G9 Pass-1 over the shipped propose gate | reuse `propose_graph` + fail-closed posture | DoD-1, DoD-2, DoD-8. The validate→park-only-if-VALID pipeline (`propose_graph.py:90-91`) already ships; G9 adds a `strict=True` catalog load (DoD-3, via the `connectivity_catalog=` inject seam on `GraphValidator.__init__`) and `rule_id` tagging; a test pins that no structural rule is forked. |
| D-C | Typed refusal envelope | reuse propose's `{status, proposal_id, errors[], advisories[]}` + `rule_id` | The envelope already ships (`propose_graph.py:92-97`); net-new is the per-issue `rule_id`. Refusal names the failing rule + houdini stamp; **zero `hou` mutations** on a refused proposal (existence reads are read-only — OPEN DECISION 5). |
| D-D | Pass-2 context conformity (resolution) | new, over `show_config` | Divergence from `resolution.*` flags; a repair injects a resize node with `gate-injected` provenance inside the build's undo group (DoD-4). |
| D-E | Pass-2 COP conformity (colorspace) | new, gated | Advisory-only until the step-5 re-audit exists (DoD-5); enforces a working space only when the show declares one (OPEN DECISION 3); every read symbol `V0` (DoD-7). |
| D-F | Pass-3 transaction binding | reuse `graph_synth_runtime.instantiate` / `GraphBuilder` | Admitted IR (+ Pass-2 fix nodes) builds in `GraphBuilder`'s **one** `hou.undos.group`; unconditional TOCTOU re-validate → HALTED; build exception → rollback-to-zero → FAILED; truth-contract readback → BUILT. No `IntegrityBlock` on this path — no partial graph (DoD-6). |
| D-G | Tests (`tests/test_preflight_gate.py`, style of `tests/` graph-validator suites) | new | Pin DoD-1..DoD-8 with synthetic proposals + a mock oracle; assert the reuse-not-fork call path; **no render in any test** (Indie-husk-noop binding trap, inherited). |
| D-H | V0 → V1 promotion note | new (doc) | Records that `hou.imageResolution`, COP `xRes()/yRes()`, and the COP OCIO read/set surface are promoted to code **only** after their runbook step-9 verdicts. |

---

## Non-goals (explicit)

- **Not a rewrite** of the shipped propose→park→build pipeline (`propose_graph.py`,
  `proposal_store.py`, `graph_synth_runtime.py`, `graph_builder.py`, `handlers_graph_synth.py`) or of
  `graph_validator.py`, `graph_proposal.py`, `interfaces.py`, or `routing/`. G9 layers strict posture
  + `rule_id` + Pass-2 conformity + the routing adapter ON TOP; a structural rule that must change,
  changes in the shipped validator — G9 owns no fork.
- **Does not route graph synthesis through `shared/bridge.py`, and stands up no second builder.** The
  transaction machinery is the shipped `GraphBuilder`; a bridge-wrapped duplicate of the same IR is
  the "second copy is a bug" this spec forbids.
- **Does not gate the `execute_python` arbitrary-code path.** That is CRITICAL consent (CLAUDE.md
  §1.2), not structural admission. G9 admits declarative graphs; opaque code blobs are flagged and
  left to the consent gate.
- **Does not author the single-source policy layer.** That is S.1 (`spec-S`). G9 *consumes* policy
  (`show_config`, the catalog); it does not define capability/gate/RBAC tables.
- **Does not enforce a colorspace the show never declared** (OPEN DECISION 3, recommended default).
- **Does not probe H22 symbols itself.** It consumes the drop-week step-5 (COP) and step-9 (symbol)
  verdicts. A doc is never promoted to a probe (blueprint §8 failure-mode rule).
- **Does not change the live-path RBAC/consent posture** (S.2/S.3). On the live path G9 inherits the
  partial-undo gap until S.1 lands (OPEN DECISION 2).
- **No render in any G9 check.** Inherits the binding trap: Indie husk no-ops headless, so no gate
  check may depend on a render.
- **Does not re-probe or edit the connectivity catalog.** The catalog is major-pinned; G9 reads it and
  fails closed on drift — the re-probe is a separate host-layer deliverable.

---

## Style & traps (binding on the build)

- Pass 1 is **pure** — if a mutation is possible before Pass 1 returns VALID, the design is violated.
- **Fail closed, never silent.** Missing catalog, absent step-5 re-audit, `V0` read symbol → refuse or
  stay advisory; never downgrade to a weaker-but-passing check.
- **Reuse is the deliverable.** A second copy of any structural rule is a bug; the test that pins the
  reuse call-path is not optional.
- **Provenance or it didn't happen** (`harness/CLAUDE.md`). Every gate-injected node carries
  `gate-injected` + lands in the ledger; an injection with no receipt is incomplete.
- **Probe truth > pinned constants.** Where the step-9 probe reports drift on `hou.imageResolution` /
  COP resolution reads, use the live-introspected op — never hardcode an H21-era constant the probe
  flagged.
- Match the shipped validator's collect-all-errors ethos: refusals enumerate every fault at once.

---

## V0 symbol ledger (probe at runbook step 9 — never asserted here as working)

| Symbol | Where G9 would use it | Status | Verify by |
|---|---|---|---|
| `hou.imageResolution` | Pass 2, image-header resolution/colorspace read | **V0** — present in the H21.0.671 headless symbol table as a name; semantics + H22 presence unprobed | drop-week step 9 (`h22-drop-week.js:91`) |
| `hou.CopNode.xRes()` / `.yRes()` | Pass 2, live COP resolution read | **V0** — H21 COP2 methods (`handlers_cops.py:427`); H22 Copernicus shape unverified | drop-week step 5 (COP re-audit) + step 9 |
| COP OCIO / colorspace read + set | Pass 2, colorspace conformity + fix injection | **`[UNVERIFIED — no such surface exists in `handlers_cops.py` today (grep: 0 hits); net-new]`** | step 5 re-audit + a host probe before code |
| `show_config.color.*` enforcement | Pass 2, colorspace policy source | declared *forward keys*; **`[UNVERIFIED — enforcement wiring]`** | read `core/show_config.py` consumers at build time |

*Provenance tiers (blueprint): `V0` = unprobed claim, probe scheduled; `V1` = confirmed against live
runtime. No `V0` symbol enters G9 code before its `V1` verdict.*
