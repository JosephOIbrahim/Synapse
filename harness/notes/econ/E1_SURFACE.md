# E1 — Tool Surface Census

**Leg** `E1` · **Harness** `ECON-01` · **Date** 2026-07-28 · **Mode** READ-ONLY
**Governed by** `harness/AGENT_CONSTITUTION.md` · `harness/SYNAPSE_ECONOMIST.md`
**Ran parallel to E0 on a disjoint question.** E0 asks what a turn *costs*. E1 asks what the
surface *is*. Nothing here depends on E0's answer, and nothing here settles it.

**Producers** — every number below traces to one of these (Law 2):

| Producer | Emits |
|---|---|
| `harness/notes/econ/econ_surface_census.py` | `E1_surface_census.json` — per tool, per component |
| `harness/notes/econ/econ_schema_dupes.py` | `E1_schema_dupes.json` — repetition and what it is worth |
| `harness/notes/econ/econ_floor.py` | `E1_floor.json` — the 2,000 reachability question |
| `harness/notes/econ/econ_call_evidence.py` | `E1_call_evidence.json` — dead surface |
| `harness/notes/econ/econ_controls.py` | `E1_controls.json` — mutation controls for all of the above |

---

## 0 · The four findings that change the programme

**1. The governing number is stale, and the brief mixes two vintages.**
17,310 was measured at **115** tools. The registry now holds **120**. The live surface is
**18,962**. The brief's "17,310 across 120 tools" is two different measurements joined.

**2. Descriptions are not where the mass is — and they are the only risky cut.**
Schema is **56.8%** of the surface. Auto-generated `annotations` are **21.0%**. All tool
descriptions together are **18.1%**. The component the brief correctly identifies as
correctness-critical is the *smallest* of the three.

**3. There is no Pareto concentration. This is a sweep, not a targeted edit.**
It takes **37 of 120 tools to reach 50%** of the mass and **78 of 120 to reach 80%**. The
brief's "20 of 120 carry half" hypothesis is refuted: the heaviest 20 carry **33.7%**.

**4. 2,000 is not reachable at 120 tools, and this is now measured rather than argued.**
The cheapest **legal** `tools/list` for 120 tools — every description empty, every schema
empty, nothing but names — is **2,919 tokens**. That is **919 over the ceiling before a
single word is written**. The ceiling is a statement about tool *count*, not tool *size*.

---

## 1 · Calibration — why these numbers can be trusted (R60)

A reader that cannot reproduce the published number from the published input is not
measuring the same thing. So `econ_surface_census.py` reconstructs the registry **as
committed at T.0's own commit** (`d92bb4b`), runs the identical decomposition over it, and
requires the published result:

```
G1 historical   115 tools expected → 115 measured      MATCH
                17,310 tokens expected → 17,310 measured  MATCH
G2 fragment     all 120 wire objects rebuild byte-for-byte
                from exactly four decomposed fragments    MATCH
```

**G1 passed exactly.** The decomposition below therefore splits the same quantity T.0
published, not a near neighbour of it.

### Mutation controls — 8 of 8 flip (R133, Law 1)

Each control runs the **real producer end to end** against a deliberately mutated registry,
never a re-implementation. A control that could not fail is reported as a failure of the
control.

| # | Reader | Mutation applied | Verdict flips |
|---|---|---|---|
| C1 | census G1 | 3 words added to one historical description | 17,310 → 17,313, gate red, exit 2 |
| C2 | census G2 | a fifth key added to one tool object | rebuild-exact → false |
| C3 | census totals | one tool appended with a pre-computed description cost | delta matches prediction **exactly** |
| C4a | dupes counting | one property copied into one more tool | repeat +1, saving +1 fragment exactly |
| C4b | dupes **negative** | every property name and description made unique | 1,265 → **0** |
| C5 | floor verdict | ceiling file raised to 99,999 | unreachable → reachable |
| C6 | floor scaling | registry halved to 60 tools | 2,919 → 1,490, over → under |
| C7 | floor ladder | — | each floor strictly cheaper than the one above |

**C4b is the one that matters most.** It is the paired negative control whose absence Law 1
names as the defect in `probe_phase3_layout`. It failed on first authoring — my uniquifier
renamed only top-level properties, nested bodies stayed identical, and the reader kept
correctly reporting duplication. **The control was wrong, not the reader.** Fixed, re-run,
flips clean.

---

## 2 · The drift: 17,310 is no longer the number

| | T.0 (2026-07-23) | E1 (2026-07-28) | Δ |
|---|---:|---:|---:|
| tools | 115 | **120** | +5 |
| mcp_http tokens | 17,310 | **18,962** | **+1,652** |
| registry bytes (LF) | 82,664 | 93,690 | +11,026 |

**Cause, named:** two commits, both the S1/SR1 Solaris repair.

```
97b879d  fix(solaris): M1+M2 one tree - relocate + register 4 of 5, collect tests
9187f38  feat(solaris): M5 register import_megascans - F9+F3 live-proven
```

The five tools S1 found *registered, tested and unreachable* were made genuinely reachable.
They cost **1,657 tokens**:

`synapse_solaris_component_builder` 450 · `synapse_solaris_import_megascans` 409 ·
`synapse_solaris_scene_template` 342 · `synapse_solaris_create_variants` 272 ·
`synapse_solaris_set_purpose` 184

**This is a real cost incurred for a real repair.** Naming it is not an argument against it.

### A defect in T.0's staleness detector, found while checking this

`token_baseline.json` records `registry_blake2b` over **working-tree bytes**. On a
`core.autocrlf=true` checkout those are CRLF. The recorded digest `c0cd3db1…` matches the
`d92bb4b` blob **only when checked out CRLF**; this LF checkout of the identical commit
hashes `047a5ace…`.

**The field is checkout-dependent and can raise a false alarm across machines.** It cannot
produce a false *OK*, so nothing downstream is wrong — but it is not the drift detector it
looks like. E1's producers digest LF-normalised content and report both.
**The drift above is established by tool count and by the two named commits, never by the digest.**

---

## 3 · Where the mass actually sits

Measured as literal wire fragments — the bytes that ship — through
`jsonrpc_result(1, {"tools": get_tools()})`, serialised by `orjson.dumps(OPT_SORT_KEYS)`
exactly as `protocol._dumps` does.

| Component | Wire tokens | Share | Compressibility |
|---|---:|---:|---|
| **`inputSchema`** | **10,778** | **56.8%** | safe — changes how arguments are stated, never whether a tool is reached |
| **`annotations`** | **3,987** | **21.0%** | **free — 100% derived, no mechanism needed** |
| **`description`** | **3,432** | **18.1%** | **risky — the only component where cutting changes when a tool is called** |
| `name` | 981 | 5.2% | untouchable — renaming breaks every caller |
| structural | −114 | −0.6% | BPE merges across fragment seams |

**The headline of this table: auto-generated metadata (21.0%) costs more than every tool
description in the product combined (18.1%).**

### The fourth component the brief did not name

The brief specifies three cost centres. **The `mcp_http` wire carries four.** Every tool
ships an `annotations` block:

```json
"annotations":{"title":"Create Material","readOnlyHint":false,
               "destructiveHint":true,"idempotentHint":false,"openWorldHint":false}
```

Every byte is recomputable from the tool name and three booleans already in `TOOL_DEFS`
(`_tool_registry.py:1543-1552`). It is **derivation, not duplication** — removing it needs
no dictionary, no `$ref`, and no client support.

**It is already removed in production on the other transport.** `annotations` are optional
in the MCP `Tool` object, and `mcp_stdio` ships without them — which is the bulk of why T.0
measured stdio 3,409 tokens under http. Dropping them costs **zero capability** and is
verified by measurement, not argued: `F1` below.

### Reconciliation, stated rather than smoothed

```
surface                       18,962   exact
sum of 120 tool objects       19,064   independently tokenised
concatenation effect            −116   adjacent objects share BPE merges across '},{'
jsonrpc framing                  +14
```

Per-tool totals are therefore **~1 token pessimistic each**; the surface total is exact.
Both are reported. Neither is estimated.

### Distribution — shape, not just totals

| | min | median | mean | p90 | max |
|---|---:|---:|---:|---:|---:|
| description (content) | 6 | **18** | 26.6 | 56 | 89 |
| schema (content) | 12 | **65** | 86.8 | 182 | 401 |
| total per tool | 61 | 133 | 158.9 | 272 | 495 |

**Descriptions are already terse.** Median 18 tokens; not one exceeds 89. There is no
bloated-prose problem to solve here — 65 of 120 tools describe themselves in under 20
tokens. Schema is **3.3× description mass** at the median and **4.5×** at the maximum.

Description length histogram:

| tokens | tools | total | e.g. |
|---|---:|---:|---|
| 0–10 | 16 | 123 | `cops_stamp_scatter` |
| 10–20 | **49** | 693 | `cops_pixel_sort` |
| 20–40 | 25 | 685 | `houdini_query_prims` |
| 40–80 | 27 | 1,432 | `houdini_create_material` |
| 80–160 | 3 | 259 | `synapse_solaris_assemble_chain` |
| 160+ | **0** | 0 | — |

### Families

| family | tools | tokens | share | mean/tool |
|---|---:|---:|---:|---:|
| `houdini_*` | 40 | 6,874 | 36.3% | 171.8 |
| `synapse_*` | 42 | 6,513 | 34.4% | 155.1 |
| `cops_*` | 21 | 3,111 | 16.4% | 148.1 |
| `tops_*` | 17 | 2,566 | 13.5% | 150.9 |

Mean cost per tool is strikingly flat across families (148–172). **No family is the problem;
the count is.**

---

## 4 · The Pareto curve — there isn't one

| coverage | tools needed | share of tools |
|---|---:|---:|
| 50% of mass | **37** | 30.8% |
| 80% of mass | **78** | 65.0% |
| 90% of mass | 96 | 80.0% |

| top-N | tokens | share |
|---|---:|---:|
| 5 | 2,186 | 11.5% |
| 10 | 3,852 | 20.2% |
| **20** | **6,420** | **33.7%** |
| 30 | 8,392 | 44.0% |
| 50 | 11,716 | 61.5% |

**The brief's decision hypothesis is refuted.** "If 20 of 120 tools carry half the mass, the
reduction is a targeted edit rather than a sweep" — they carry a third. The heaviest tool
(`houdini_create_material`, 495) is only 8.1× the lightest (`synapse_router_stats`, 61),
and the distribution between them is smooth.

**Consequence for E2:** there is no small edit. Deleting the 20 heaviest tools outright
leaves 12,542 tokens, still 6.3× the ceiling. **Any programme that keeps a flat catalog of
120 tools is a sweep across all 120, and it still will not reach 2,000** (§6).

---

## 5 · Duplication — real, and smaller than hoped, for a findable reason

461 property instances across 120 tools, costing 9,649 tokens (93% of all schema mass).
Property *descriptions* alone are **3,998 tokens — more than all 120 tool descriptions
combined (3,192)**.

### Verbatim repetition

| kind | distinct repeated | ceiling saving | realistic with `$defs`/`$ref` |
|---|---:|---:|---:|
| property fragments | 38 | 1,265 | 232 |
| property descriptions | 38 | 761 | 52 |
| enum bodies | 1 | 15 | 0 |

Top repeats by ceiling value:

| repeats | property | tokens | ceiling | fragment |
|---:|---|---:|---:|---|
| 10 | `node` | 18 | 162 | `"node":{"description":"LOP node to wire after (optional)","type":"string"}` |
| 10 | `parent` | 14 | 126 | `"parent":{"description":"COP network path","type":"string"}` |
| 3 | `set_display` | 48 | 96 | long display-flag prose |
| 7 | `node` | 13 | 78 | `"node":{"description":"TOP node path","type":"string"}` |
| 4 | `node` | 21 | 63 | `"node":{"description":"LOP node path. If omitted, uses current selection.","type":"string"}` |
| 6 | `name` | 11 | 55 | `"name":{"description":"Node name","type":"string"}` |

**The brief expected "the same `node_path` description written 60 times."** The most-repeated
fragment appears **10** times. Free reduction from verbatim dedup is **1,265 tokens
(6.7%)** at ceiling, and only **232** through a real `$ref`.

### Why it underperforms — and the bigger, non-free lever underneath

The property name `node` appears in **40 tools under 17 distinct bodies**. `name` appears in
23 tools under 16 bodies. **Nothing can dedup what was never written identically.**

| property | tools | distinct bodies | normalise-then-dedup ceiling | information discarded |
|---|---:|---:|---:|---:|
| `node` | 40 | **17** | 637 | 15 |
| `parent` | 21 | 7 | 337 | 7 |
| `name` | 23 | 16 | 305 | 10 |
| `prim_path` | 11 | 8 | 163 | 5 |
| `resolution` | 7 | 6 | 160 | 26 |

| approach | tokens |
|---|---:|
| normalise wording only, no dedup | 927 |
| normalise **then** dedup — ceiling | **4,006** |
| normalise then dedup — realistic `$ref` | 1,411 |

**Normalisation is not free, and this report will not present it as free.** Collapsing
"LOP node path", "TOP node path" and "COP node path" onto one string deletes the context
that tells the model which network the argument belongs to. `information_discarded` per row
is the size of what is thrown away — **that is the number to argue over, not the saving.**

### The honest summary of "free reduction"

| lever | tokens | capability lost | mechanism needed |
|---|---:|---|---|
| **drop `annotations`** | **3,987** | **none** | **none — already shipping on stdio** |
| verbatim fragment dedup | 1,265 ceiling / 232 real | none | `$defs` + `$ref` — **support UNVERIFIED** |
| normalise then dedup | 4,006 ceiling / 1,411 real | **real** — per-network context | `$ref` + wording ruling |

**Open probe, named rather than assumed:** `$ref` inside a tool `input_schema` is not
uniformly supported by MCP clients or by the Anthropic tool API. Every `$ref` figure above
is contingent on a probe nobody has run. **`annotations` removal is contingent on nothing.**

---

## 6 · Is 2,000 reachable at 120 tools? — **No.**

Each floor is a **real payload built and measured**, not an estimate. Ceiling is 2,000 from
`harness/verify/token_ceiling.json` (CTO ruling 2026-07-23, down-only, not self-writable).

| floor | what remains | tokens | ×ceiling | fits |
|---|---|---:|---:|---|
| **F0** | as shipped | 18,962 | 9.5× | no |
| **F1** | annotations dropped (the stdio shape) | 15,095 | 7.5× | no |
| **F2** | + every per-argument description removed | 9,935 | 5.0× | no |
| **F3** | + schemas emptied; tool descriptions kept | 6,117 | 3.1× | no |
| **F4** | **names only — empty description, empty schema** | **2,919** | **1.46×** | **no** |
| F5 | bare name array (*not* a legal tools/list) | 742 | 0.37× | — |

### The verdict

> **2,000 is NOT reachable as a flat catalog at 120 tools.** The cheapest *legal*
> `tools/list` for 120 tools — every description empty, every schema empty, nothing but
> names — costs **2,919 tokens**, which is **919 over the ceiling before a single word of
> description is written**. At that floor shape only **81** tools fit under 2,000; at the
> current average tool shape only **13** do. The ceiling is therefore a statement about
> tool **count**, not tool **size**, and no description- or schema-editing programme can
> satisfy it while all 120 definitions stay in context.

Scaling, measured not divided (BPE is not linear):

| tools | F4 tokens |
|---:|---:|
| 20 | 497 |
| 60 | 1,490 |
| **80** | **1,958** ← last rung under 2,000 |
| 100 | 2,447 |
| 120 | 2,919 |

### The ceiling is satisfiable — by the shape it was actually calibrated for

`token_ceiling.json`'s own rationale names three verbs. Built realistically — full routing
hints in `tool_search`, family map included — they measure **332 tokens, with 1,668 to
spare**.

**So the ceiling is not wrong. It was never a budget for a flat catalog.** Reading it as
"make 120 definitions smaller" is a category error; it is a budget for a *lookup*. That
distinction is the whole of T.1, and it is now measured rather than assumed.

**This is not a recommendation.** Which programme is right is E2's call and needs E0's cache
answer first: if the surface is cache-read at 0.1×, 18,962 is ~1,896 effective and the
ceiling is already met without touching anything. **E1 measures; it does not choose.**

---

## 7 · Dead surface — 0 structurally dead, 34 with no runtime evidence

### The S1 condition is closed

`SynapseHandler()` builds standalone — no Houdini needed — so its registry is ground truth.
**All 120 registered tools resolve to a live handler.** 132 command types registered, zero
orphans. The five tools S1 found unreachable are the five added in §2.

**Nothing is structurally dead. That failure mode is fixed, not merely absent.**

### Two runtime sources with complementary blind spots

| source | records | keyed by | blind to |
|---|---:|---|---|
| `~/.synapse/audit/*.jsonl` | 58,663 lines, 85 files, 2,063 sessions, Feb 6 – Jul 28 | `operation` = command_type | **all read-only commands** |
| SessionJournal `journal.log` | 1,705 tool records (production) | **MCP tool name** | date — timestamps are `%H:%M:%S` only |

### The validity constraint that reverses a naive reading

`handlers.py:488` → `_mutating = cmd_type not in _READ_ONLY_COMMANDS`
`handlers.py:531` → `if _mutating: self._submit_logs(...)`

**The audit trail cannot record a read-only call.** For 32 tools, "never called" was a check
that could never have returned "called" — the exact Law 1 decoration.

**The worked example that proves it:** `synapse_ping` shows zero audit calls. It runs on
every session start. Its command type is in `_READ_ONLY_COMMANDS`, so no call it will ever
receive can be recorded.

**The coverage model is complete, not a hypothesis.** The tools whose annotations say
`readOnlyHint: true` but whose command_type is *absent* from `_READ_ONLY_COMMANDS` are
**exactly** the read-only-hinted tools that carry audit evidence — 7 of 7, zero residual:

`cops_temporal_analysis` · `houdini_hda_list` · `houdini_query_prims` ·
`synapse_memory_query` · `synapse_memory_status` · `synapse_propose_graph` ·
`synapse_render_farm_status`

> **Secondary finding for the ledger:** those 7 tools advertise `readOnlyHint: true` to MCP
> clients while the server treats them as **mutating** — for the C5 mutation lock, the live
> integrity envelope, and the audit write. That is an annotation/implementation
> disagreement on a safety-relevant flag. It is not E1's to fix.

The journal closes the gap: it records tool **names** with no mutation gate, so read-only
calls are visible there.

### Contamination, fingerprinted rather than assumed

This repo has been burned exactly here — `RSI_SURFACE_AUDIT.md` found 4,795 "epoch closed"
lines that read as production and were all pytest.

- **581 of 2,063 audit sessions (28.2%) flagged TEST-SUSPECT** — they contain operations
  that are not registered tools (`c5_hold`, `c5_mutate`, `c5_quick`, `fake_mutate`, `test`).
  `gate_proposal`/`gate_decision` are allowlisted after inspection: they are the real
  HumanGate lifecycle, and flagging them was mis-marking every consent-gated production
  session as a test.
- **Journal provenance is decidable from the path.** `_resolve_log_dir():110` falls back to
  `<tempdir>/synapse_journal` when `hou` is unimportable — which is precisely the path
  pytest takes. That copy (407 records, contains `fake_tool`) is excluded.
- **One near-miss worth recording.** The first provenance rule downgraded the *production*
  journal to "test" because it contained one unrecognised name: `hrudini_create_noe` — a
  fat-fingered `houdini_create_node`, **1 record in 1,705 (0.06%)**. That would have
  discarded 1,705 real dispatches over a typo and manufactured dead surface out of a
  spelling mistake. The rule now downgrades only on an explicit test-marker name or when
  unrecognised names exceed 5% of a file.

### Result

| classification | tools | tokens | share of surface |
|---|---:|---:|---:|
| CALLED (audit or production journal) | 84 | 13,580 | 71.6% |
| CALLED — test sessions only | 2 | 309 | 1.6% |
| **NO RUNTIME EVIDENCE (auditable, nothing anywhere)** | **21** | **3,755** | **19.8%** |
| no evidence, and audit-blind (journal-only absence) | 13 | 1,420 | 7.5% |
| **structurally dead** | **0** | **0** | — |

**34 tools — 28% of the registry — carry 5,175 tokens (27.3% of the surface) with no
recorded invocation of any kind.**

The 21 with the strongest claim (auditable, so absence *is* measured absence):

| tool | tokens | | tool | tokens |
|---|---:|---|---|---:|
| `houdini_set_usd_primvar` | 356 | | `tops_configure_scheduler` | 157 |
| `tops_multi_shot` | 351 | | `tops_cook_node` | 142 |
| `tops_render_sequence` | 294 | | `tops_setup_wedge` | 138 |
| `houdini_hda_create` | 270 | | `tops_cook_and_validate` | 135 |
| `houdini_shot_render_ready` | 255 | | `tops_batch_cook` | 133 |
| `synapse_autonomous_render` | 236 | | `houdini_set_keyframe` | 120 |
| `tops_monitor_stream` | 186 | | `houdini_wedge` | 114 |
| `houdini_set_usd_attribute` | 172 | | `synapse_evolve_memory` | 107 |
| `houdini_set_payload_loadstate` | 168 | | `synapse_sleep_pass` | 105 |
| `houdini_modify_usd_prim` | 161 | | `tops_cancel_cook` | 83 |
| | | | `houdini_redo` | 72 |

The 13 whose absence rests on the journal alone (weaker — treat as unmeasured, not dead):

`tops_query_items` 159 · `tops_get_work_items` 151 · `tops_diagnose` 128 ·
`synapse_validate_frame` 122 · `tops_get_dependency_graph` 115 · `cops_analyze_render` 113 ·
`tops_pipeline_status` 112 · `houdini_capture_viewport` 108 · `synapse_live_metrics` 97 ·
`tops_get_cook_stats` 93 · `cops_read_layer_info` 90 · `synapse_search` 71 ·
`synapse_router_stats` 61

### The finding inside the finding: TOPS is unexercised

| family | tools | no evidence | share | dead tokens | family tokens |
|---|---:|---:|---:|---:|---:|
| **`tops_*`** | 17 | **15** | **88%** | **2,377** | 2,566 |
| `houdini_*` | 40 | 10 | 25% | 1,796 | 6,874 |
| `synapse_*` | 42 | 7 | 17% | 799 | 6,513 |
| `cops_*` | 21 | 2 | 10% | 203 | 3,111 |

**92.6% of the entire TOPS family's token mass has no recorded invocation.** Only
`tops_dirty_node` and `tops_generate_items` show any trace. This is the single most
concentrated block of unexercised surface in the product and the most obvious candidate for
E2 — **as a product question about whether PDG orchestration is a shipped capability or an
aspiration, not as a token optimisation.**

### The limit on all of §7, stated plainly

**This is one developer machine.** Absence means "never called on this host across the audit
span", which is evidence, not proof, that no user calls the tool. It cannot see other
installs. **Law 4 applies without exception: census output is a hypothesis, and classifying
is not deleting.**

---

## 8 · What E1 did not do

Not one tool was edited. No reduction is proposed — that is E2's, and E2 needs E0's cache
answer first, because if the surface is cache-read at 0.1× then 18,962 is ~1,896 effective
and the entire reduction programme demotes to a header change.

**The one thing E1 will say about direction, because it is measured and not a preference:**
if a flat catalog is retained, the ceiling is unreachable at any tool count above 81 — and
that is a product decision about how many tools SYNAPSE ships, not an optimisation.

---

## 9 · For ruling

1. **The governing number needs re-basing.** `token_baseline.json` says 17,310/115; live is
   18,962/120. Re-run `scripts/token_baseline.py` and re-quote, or freeze 17,310 as a dated
   historical baseline. It should not keep circulating undated.
2. **`registry_blake2b` is checkout-dependent** (CRLF). Normalise to LF before hashing, or
   drop the field — it cannot do the job its name implies.
3. **7 tools declare `readOnlyHint: true` but are treated as mutating** by the C5 lock, the
   integrity envelope and the audit write. Which side is wrong is a safety call, not E1's.
4. **`$ref` support in MCP `input_schema` is unverified** and gates ~1,400–4,000 tokens of
   claimed saving. Needs a probe before any figure depending on it is banked.
5. **TOPS: 15 of 17 tools, 92.6% of family mass, no recorded invocation.** Product question.
6. **The audit trail cannot see read-only calls.** If tool-usage telemetry is wanted as a
   standing instrument, that gate is the thing to change — otherwise a third of the surface
   stays permanently unmeasurable.

---

## Appendix A · Per-tool table, sorted by total cost

Content-token counts per component (the string values); **total** is the exact wire cost of
that tool's serialised object. `share` is the running cumulative share of the 18,962-token
surface — read it as the Pareto curve.

Evidence column: blank = called · `~` = test sessions only · **DEAD?** = no runtime evidence
(auditable) · `unmeas.` = audit-blind, absent from journal.

| # | tool | desc | schema | annot | name | **total** | share | evidence |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | `houdini_create_material` | 50 | 401 | 30 | 5 | **495** | 2.6% |  |
| 2 | `synapse_solaris_build_graph` | 64 | 364 | 32 | 7 | **476** | 5.1% |  |
| 3 | `synapse_solaris_component_builder` | 56 | 346 | 32 | 7 | **450** | 7.5% |  |
| 4 | `synapse_solaris_import_megascans` | 44 | 312 | 34 | 10 | **409** | 9.7% |  |
| 5 | `houdini_set_usd_primvar` | 54 | 252 | 33 | 8 | **356** | 11.5% | **DEAD?** |
| 6 | `tops_multi_shot` | 57 | 249 | 32 | 4 | **351** | 13.4% | **DEAD?** |
| 7 | `synapse_solaris_assemble_chain` | 87 | 208 | 33 | 8 | **345** | 15.2% |  |
| 8 | `synapse_solaris_scene_template` | 83 | 211 | 32 | 7 | **342** | 17.0% |  |
| 9 | `houdini_hda_package` | 34 | 240 | 31 | 6 | **320** | 18.7% |  |
| 10 | `houdini_create_textured_material` | 53 | 207 | 32 | 7 | **308** | 20.3% |  |
| 11 | `tops_render_sequence` | 55 | 194 | 32 | 4 | **294** | 21.9% | **DEAD?** |
| 12 | `houdini_manage_collection` | 49 | 179 | 30 | 5 | **272** | 23.3% |  |
| 13 | `synapse_solaris_create_variants` | 46 | 176 | 33 | 8 | **272** | 24.7% |  |
| 14 | `houdini_hda_create` | 42 | 182 | 31 | 6 | **270** | 26.2% | **DEAD?** |
| 15 | `houdini_reference_usd` | 51 | 163 | 31 | 6 | **260** | 27.5% |  |
| 16 | `houdini_shot_render_ready` | 56 | 153 | 31 | 6 | **255** | 28.9% | **DEAD?** |
| 17 | `houdini_network_explain` | 47 | 151 | 30 | 6 | **243** | 30.2% |  |
| 18 | `houdini_query_prims` | 29 | 164 | 31 | 6 | **239** | 31.4% |  |
| 19 | `synapse_autonomous_render` | 35 | 156 | 31 | 5 | **236** | 32.7% | **DEAD?** |
| 20 | `houdini_manage_variant_set` | 48 | 133 | 31 | 6 | **227** | 33.9% |  |
| 21 | `cops_reaction_diffusion` | 23 | 153 | 33 | 5 | **224** | 35.0% |  |
| 22 | `houdini_configure_light_linking` | 59 | 107 | 32 | 7 | **215** | 36.2% |  |
| 23 | `houdini_hda_promote_parm` | 27 | 119 | 33 | 8 | **196** | 37.2% |  |
| 24 | `synapse_render_sequence` | 31 | 121 | 30 | 4 | **195** | 38.2% |  |
| 25 | `cops_growth_propagation` | 17 | 130 | 33 | 5 | **194** | 39.3% |  |
| 26 | `synapse_configure_render_passes` | 57 | 89 | 32 | 6 | **193** | 40.3% |  |
| 27 | `synapse_write_report` | 78 | 70 | 30 | 4 | **191** | 41.3% |  |
| 28 | `cops_pixel_sort` | 16 | 128 | 32 | 4 | **190** | 42.3% |  |
| 29 | `houdini_create_point_instancer` | 40 | 100 | 32 | 7 | **188** | 43.3% |  |
| 30 | `tops_monitor_stream` | 63 | 78 | 32 | 4 | **186** | 44.3% | **DEAD?** |
| 31 | `synapse_solaris_set_purpose` | 44 | 91 | 32 | 8 | **184** | 45.2% |  |
| 32 | `cops_procedural_texture` | 19 | 113 | 34 | 6 | **181** | 46.2% |  |
| 33 | `cops_stamp_scatter` | 9 | 125 | 32 | 5 | **180** | 47.1% |  |
| 34 | `houdini_hda_set_help` | 29 | 103 | 32 | 7 | **180** | 48.1% |  |
| 35 | `synapse_propose_graph` | 89 | 41 | 31 | 5 | **175** | 49.0% |  |
| 36 | `cops_wetmap` | 16 | 111 | 32 | 5 | **173** | 49.9% |  |
| 37 | `houdini_set_usd_attribute` | 8 | 116 | 32 | 7 | **172** | 50.8% | **DEAD?** |
| 38 | `cops_stylize` | 17 | 106 | 33 | 5 | **170** | 51.7% |  |
| 39 | `synapse_render_progressively` | 39 | 85 | 31 | 5 | **169** | 52.6% | ~ |
| 40 | `cops_bake_textures` | 20 | 100 | 33 | 6 | **168** | 53.5% |  |
| 41 | `houdini_set_payload_loadstate` | 36 | 84 | 32 | 7 | **168** | 54.4% | **DEAD?** |
| 42 | `houdini_create_usd_prim` | 8 | 110 | 32 | 7 | **166** | 55.3% |  |
| 43 | `houdini_modify_usd_prim` | 17 | 96 | 32 | 7 | **161** | 56.1% | **DEAD?** |
| 44 | `synapse_inspect_node` | 21 | 94 | 30 | 5 | **159** | 56.9% |  |
| 45 | `tops_query_items` | 26 | 87 | 32 | 4 | **159** | 57.8% | unmeas. |
| 46 | `tops_configure_scheduler` | 28 | 84 | 32 | 4 | **157** | 58.6% | **DEAD?** |
| 47 | `synapse_safe_render` | 34 | 76 | 30 | 4 | **153** | 59.4% |  |
| 48 | `cops_composite_aovs` | 15 | 87 | 34 | 7 | **152** | 60.2% |  |
| 49 | `tops_get_work_items` | 12 | 92 | 33 | 5 | **151** | 61.0% | unmeas. |
| 50 | `cops_to_materialx` | 16 | 83 | 33 | 5 | **146** | 61.8% |  |
| 51 | `synapse_instantiate_graph` | 66 | 33 | 30 | 5 | **144** | 62.5% |  |
| 52 | `houdini_render` | 35 | 65 | 29 | 4 | **142** | 63.3% |  |
| 53 | `houdini_set_parm` | 52 | 46 | 30 | 5 | **142** | 64.0% |  |
| 54 | `tops_cook_node` | 14 | 82 | 32 | 5 | **142** | 64.8% | **DEAD?** |
| 55 | `synapse_validate_ordering` | 41 | 55 | 30 | 5 | **140** | 65.5% | ~ |
| 56 | `cops_create_copnet` | 25 | 64 | 33 | 6 | **138** | 66.3% |  |
| 57 | `tops_setup_wedge` | 12 | 79 | 33 | 5 | **138** | 67.0% | **DEAD?** |
| 58 | `houdini_connect_nodes` | 12 | 80 | 30 | 5 | **136** | 67.7% |  |
| 59 | `tops_cook_and_validate` | 22 | 65 | 33 | 6 | **135** | 68.4% | **DEAD?** |
| 60 | `synapse_doctor` | 62 | 30 | 29 | 4 | **134** | 69.1% |  |
| 61 | `cops_batch_cook` | 8 | 79 | 32 | 5 | **133** | 69.8% |  |
| 62 | `tops_batch_cook` | 15 | 72 | 32 | 5 | **133** | 70.5% | **DEAD?** |
| 63 | `cops_create_solver` | 12 | 73 | 32 | 4 | **130** | 71.2% |  |
| 64 | `houdini_execute_python` | 26 | 59 | 30 | 5 | **129** | 71.9% |  |
| 65 | `tops_diagnose` | 22 | 59 | 33 | 5 | **128** | 72.6% | unmeas. |
| 66 | `cops_slap_comp` | 11 | 69 | 33 | 5 | **127** | 73.2% |  |
| 67 | `houdini_create_node` | 17 | 66 | 30 | 5 | **127** | 73.9% |  |
| 68 | `cops_create_network` | 13 | 68 | 32 | 4 | **126** | 74.6% |  |
| 69 | `synapse_inspect_scene` | 17 | 65 | 30 | 5 | **126** | 75.2% |  |
| 70 | `cops_connect` | 6 | 76 | 31 | 3 | **125** | 75.9% |  |
| 71 | `cops_temporal_analysis` | 13 | 64 | 33 | 5 | **124** | 76.5% |  |
| 72 | `synapse_validate_frame` | 18 | 61 | 30 | 4 | **122** | 77.2% | unmeas. |
| 73 | `cops_set_opencl` | 17 | 57 | 33 | 5 | **121** | 77.8% |  |
| 74 | `houdini_set_keyframe` | 13 | 61 | 31 | 6 | **120** | 78.5% | **DEAD?** |
| 75 | `synapse_batch` | 12 | 66 | 29 | 3 | **119** | 79.1% |  |
| 76 | `houdini_execute_vex` | 12 | 60 | 31 | 6 | **118** | 79.7% |  |
| 77 | `houdini_get_usd_attribute` | 12 | 57 | 32 | 7 | **117** | 80.3% |  |
| 78 | `tops_get_dependency_graph` | 20 | 48 | 33 | 5 | **115** | 80.9% | unmeas. |
| 79 | `houdini_wedge` | 12 | 58 | 30 | 5 | **114** | 81.5% | **DEAD?** |
| 80 | `cops_analyze_render` | 18 | 48 | 33 | 5 | **113** | 82.1% | unmeas. |
| 81 | `houdini_assign_material` | 8 | 61 | 30 | 5 | **113** | 82.7% |  |
| 82 | `synapse_memory_write` | 10 | 60 | 30 | 4 | **113** | 83.3% |  |
| 83 | `tops_pipeline_status` | 20 | 47 | 32 | 4 | **112** | 83.9% | unmeas. |
| 84 | `synapse_add_memory` | 8 | 60 | 30 | 4 | **111** | 84.5% |  |
| 85 | `houdini_capture_viewport` | 10 | 52 | 31 | 6 | **108** | 85.1% | unmeas. |
| 86 | `synapse_evolve_memory` | 6 | 56 | 31 | 5 | **107** | 85.6% | **DEAD?** |
| 87 | `cops_create_node` | 9 | 52 | 32 | 4 | **106** | 86.2% |  |
| 88 | `synapse_render_farm_cancel` | 48 | 12 | 31 | 6 | **106** | 86.8% |  |
| 89 | `synapse_sleep_pass` | 50 | 12 | 30 | 4 | **105** | 87.3% | **DEAD?** |
| 90 | `synapse_decide` | 9 | 52 | 30 | 4 | **104** | 87.9% |  |
| 91 | `tops_dirty_node` | 15 | 43 | 32 | 4 | **103** | 88.4% |  |
| 92 | `synapse_project_setup` | 29 | 28 | 30 | 4 | **100** | 88.9% |  |
| 93 | `houdini_read_material` | 13 | 41 | 30 | 5 | **98** | 89.4% |  |
| 94 | `synapse_live_metrics` | 24 | 30 | 30 | 4 | **97** | 90.0% | unmeas. |
| 95 | `houdini_render_settings` | 14 | 38 | 30 | 5 | **96** | 90.5% |  |
| 96 | `synapse_memory_query` | 6 | 44 | 30 | 4 | **93** | 91.0% |  |
| 97 | `tops_get_cook_stats` | 19 | 26 | 33 | 6 | **93** | 91.4% | unmeas. |
| 98 | `houdini_get_parm` | 11 | 36 | 30 | 5 | **91** | 91.9% |  |
| 99 | `cops_read_layer_info` | 18 | 25 | 33 | 5 | **90** | 92.4% | unmeas. |
| 100 | `houdini_hda_list` | 29 | 12 | 31 | 6 | **87** | 92.9% |  |
| 101 | `synapse_inspect_selection` | 14 | 28 | 30 | 5 | **86** | 93.3% |  |
| 102 | `tops_generate_items` | 17 | 24 | 32 | 4 | **86** | 93.8% |  |
| 103 | `synapse_knowledge_lookup` | 16 | 24 | 30 | 5 | **84** | 94.2% |  |
| 104 | `houdini_delete_node` | 11 | 28 | 30 | 5 | **83** | 94.6% |  |
| 105 | `tops_cancel_cook` | 11 | 26 | 32 | 5 | **83** | 95.1% | **DEAD?** |
| 106 | `houdini_stage_info` | 10 | 25 | 30 | 5 | **79** | 95.5% |  |
| 107 | `houdini_scene_info` | 21 | 12 | 30 | 5 | **77** | 95.9% |  |
| 108 | `synapse_recall` | 11 | 24 | 30 | 3 | **77** | 96.3% |  |
| 109 | `synapse_render_farm_status` | 18 | 12 | 31 | 6 | **76** | 96.7% |  |
| 110 | `houdini_redo` | 16 | 12 | 30 | 5 | **72** | 97.1% | **DEAD?** |
| 111 | `synapse_search` | 7 | 23 | 29 | 3 | **71** | 97.5% | unmeas. |
| 112 | `synapse_list_recipes` | 13 | 12 | 30 | 5 | **69** | 97.8% |  |
| 113 | `synapse_memory_status` | 14 | 12 | 30 | 4 | **69** | 98.2% |  |
| 114 | `houdini_undo` | 14 | 12 | 29 | 4 | **68** | 98.5% |  |
| 115 | `houdini_get_selection` | 10 | 12 | 30 | 5 | **66** | 98.9% |  |
| 116 | `synapse_ping` | 13 | 12 | 29 | 3 | **66** | 99.2% |  |
| 117 | `synapse_metrics` | 9 | 12 | 29 | 3 | **62** | 99.6% |  |
| 118 | `synapse_context` | 8 | 12 | 29 | 3 | **61** | 99.9% |  |
| 119 | `synapse_health` | 8 | 12 | 29 | 3 | **61** | 100.2% |  |
| 120 | `synapse_router_stats` | 6 | 12 | 30 | 4 | **61** | 100.5% | unmeas. |

