# W5-WCRUX — Substrate Crucible Verdict Board

**Adversarial gate over the weak-domain substrate trio (W5-CATALOG · W5-PARMGATE · W5-MEASURES) before any merge word.**
Read-only leg. Every number below was **run live this session by the crucible** — none inherited from the builders' receipts.
Build: Houdini **22.0.400** (fresh hython, rc0) · Python 3.14.2 / pytest 8.4.2 (validation layer is pure-python; hou-tests skip).

**Verdict: `green_with_findings`.** The trio is faithful, independently re-verified, and adds no guardrail violation — but the combined full suite carries **one must-fix-before-merge defect** (F-ENVDOC) the CRUX caught that no single leg's slice did.

---

## 1 · Mandate table (binary, per leg)

| Leg | product_head exists | precedes receipt | receipt = leg's OWN closing commit | Verdict |
|---|---|---|---|---|
| **CATALOG** | `8682afef` ✅ | → `a26fb6ed` ✅ | HEAD `a26fb6ed` = receipt only, 82 ins ✅ | **PASS** |
| **PARMGATE** | `816826ca` ✅ | → `d7eb8c1b` ✅ | HEAD `d7eb8c1b` = receipt only, 89 ins ✅ | **PASS** |
| **MEASURES** | `a6db2286` ✅ | → `520a10d4` ✅ | HEAD `520a10d4` = receipt only, 96 ins ✅ | **PASS** |

All three receipts are their **own** closing commits — the W5H rule (no operator rescue) holds for the whole trio.

---

## 2 · Per-leg independent re-execution (predicate 1)

| Leg | isolated (own worktree) | composed (scratch tree) | independent audit |
|---|---|---|---|
| CATALOG | `test_node_catalog.py` **11/11** | — | **FP1**: 29 off-stride/never-audited nodes re-read in fresh hython → 0 mismatch |
| PARMGATE | `test_parm_gate.py` + routing **33/33** | — | gated_set reject/suggest + one-undo-group re-observed green |
| MEASURES | `test_measures_contracts.py` **24/24** | — | **FP2**: golden pair + tier-no-promote (below) |
| **COMPOSED** | — | all four slices **68/68** (=11+33+24) | no cross-leg interaction breaks a leg slice |

UNKNOWNs recorded, **not** laundered: live GUI one-Ctrl+Z reversal of a gated op (PARMGATE F5) and the live hython golden *cook* (MEASURES S2) are `gui_required` — untestable headless, held UNKNOWN.

---

### 2b · Keystone — the gate rejects a phantom against the REAL catalog (composed)

PARMGATE's whole thesis is that CATALOG makes the gate load-bearing — but on the parmgate branch **alone** the gate is degraded/permissive (no catalog data → `authority: none`), so its rejection power is **dormant** (its own R1). The combined tree is the first place both are present. Proven there:
- the reader resolves the **real** `opencl` COP row (81 parms; `kernelcode` present, `code` **absent** — the exact phantom the old RD hedge papered over);
- `gated_set` **rejects** the phantom `code` *before any mutation* — `ParmGateError`, top suggestion `kernelcode` — with `authority=catalog` (not permissive);
- `gated_set` **accepts** the real `kernelcode` (`authority=catalog`, `set=[kernelcode]`).

The substrate thesis (catalog ⇒ gate authoritative ⇒ phantom names caught+suggested) is demonstrated composed, not just unit-tested against a fixture.

## 3 · FP1 — catalog vs a fresh binary (target 2)

- **Static provenance PASS**: build-keyed `h22.0.400`, `total_probe_errors=0`, `dump_receipt.txt` present (the live hython dump stdout), blake2b on every category file.
- **Live re-sample PASS**: **29 different nodes** — off-stride Dop/Cop/Chop/Vop (disjoint from the builder's 20-stride) **plus 7 SOP types the builder audited zero of** — re-read in a fresh hython via the **canonical** `_type_record`, **0 mismatches**, full base-record equality.
- **A3 closed by fresh re-sample** (not inherited): 6 off-stride VOP wire signatures re-instantiated + 5 off-stride APEX callback signatures re-read in fresh hython → **0 mismatches** vs committed `Vop.json`/`apex_callbacks.json`. CATALOG's typed-port acceptance is re-derived from the binary, not trusted from its own test.
- **Method self-correction (recorded):** the first cut used raw `entriesWithoutFolders()`/`minNumInputs()` and produced *false* "mismatches" on multiparm-instance parms + VOP arity; switching to the canonical extraction showed **zero real drift**. (Do not pin your own error.)

## 4 · FP2 — measure-or-UNKNOWN + tier ladder (target 3)

- Healthy golden → **STABLE** (a real evaluated-window stable, not a laundered UNKNOWN). Exploding golden → **EXPLODING**, `signal=ke_growth`, `offending_frame=5`, anchored ("KE grew 1.0→60.0 ×60").
- **Tier ladder cannot promote without measurement**: every one of the 5 output kinds, given an unmeasured obs → `UNKNOWN` → rung `V0_membership` → tier `surfaced_unverified` (**never** foreground). A MEASURED result **does** reach `V1_output`/foreground; the two tiers differ; `exposure.highest_tier` resolved live, so the ladder genuinely **extends** the existing exposure system.

---

## 5 · Combined-state scratch-tree probe (predicate 3)

Base = `wcrux-base` @ `df8c9ef3` (the three legs' shared fork). Combined = `wcrux-scratch` @ `df8c9ef3` + the three legs staged (harness-provisioned; **verified faithful by me**).

| Check | Result |
|---|---|
| **Faithfulness** | 51 staged files = exact union (28+7+16); every file's git blob SHA == its leg branch — no tamper, nothing laundered, nothing dropped |
| **ingest_ledger R1** | `harness/ingest_ledger.json` **byte-identical** base↔combined (`3153db99…`) — staging the catalog did NOT write the served single-writer ledger |
| **Suite ratchet** | base **6445 pass / 1 fail** → combined **6523 pass / 2 fail** (+78 leg-test passes). **One NEW failure** (F-ENVDOC, below); the other is pre-existing F-VER (tag 5.51.0 > VERSION 5.50.0 at the fork) |
| **guardrail_violations** | **0 leg-introduced.** Phantom-clean ✅, version-single-source ✅, rigging-drift in-scope ✅, provenance = warn-only stub at fork (ok:None). One pre-existing hit (`memory/store.py` hardcoded path) is **not** a leg file — present identically at base |
| **Master drift** | master moved 268 files since the fork; the **only** overlap with any leg file is one markdown note (`CTO-RULING-measures-divergence`), whose blob differs from master → a benign doc-note merge reconcile, **no product-code conflict** |
| **Cleanup** | read-only probing left **zero** untracked/extra litter in either scratch worktree; harness stage intact |

---

## 6 · Findings

### F-ENVDOC — must-fix-before-merge (breaks the full suite → Safety Rule 7)
`python/synapse/validation/catalog.py` (**PARMGATE**) reads `SYNAPSE_PARM_CATALOG_ROOT` (`:43`) and `SYNAPSE_PARM_CATALOG_BUILD` (`:44`); neither is in the `### Environment Variables` table of `docs/studio/DEPLOYMENT.md`, so `test_m3_env_conformance::test_every_source_env_read_is_documented` **fails in-suite** (passes at base; DEPLOYMENT.md identical both sides → PARMGATE-attributable). PARMGATE's own slice never ran the *global* env-conformance test, so its receipt did not surface it.
**Fix (human-gated docs edit):** add two backticked rows to DEPLOYMENT.md's Environment Variables table before the trio merges.

### F-VER — not this trio (pre-existing)
`test_no_published_tag_outruns_the_canonical_version` fails at the `df8c9ef3` fork because published tag v5.51.0 outruns VERSION 5.50.0. Resolves when the legs rebase onto v5.51.0 master. No leg touches VERSION/tag/pyproject.

### F-SCOPE — MEASURES branch scope divergence (disclosed, not laundered)
The MEASURES branch carries a prior "unmeasured honesty audit" ride-along (`panel/health_infographic.py`, `dashboard.py`, `live_metrics.py`, `metrics.py` + tests) beyond the cook-verify charter — disclosed in its own receipt as F-PANEL for-ruling. The combined stage includes these; their tests pass in-suite; disposition is Joe/CTO's.

### F-TABLE — phantom guardrail ran against the H21.0.671 symbol table
With no live Houdini bound to scout, `check_phantom_clean`'s membership authority was the committed **21.0.671** table, not 22.0.400. It found **zero** phantoms, so "clean" holds regardless of table version (clean is clean) — but a stronger guarantee wants an H22 table regenerated on-host. Recorded, low.
