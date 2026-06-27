# SYNAPSE × H22 — Native APEX MCP Provider Spec

**`SYNAPSE_H22_PROVIDER_APEX.md`**

> **Status:** DRAFT — design only (ARCHITECT). Wiring (FORGE) is gated on `SYNAPSE_H22_BOUNDARY.md`
> ratification + D-H22-4 verification against the shipped build.
> **Owner:** Joe Ibrahim · **Suggested repo path:** `docs/SYNAPSE_H22_PROVIDER_APEX.md`
> **Implements:** `SYNAPSE_H22_BOUNDARY.md` D-H22-1 / D-H22-2 / D-H22-4
> **Harness tasks:** scaffold `0.8`/`0.9` (Mode A, mock) → verify `1.7` (Mode B) → wire `2.7`/`2.8` (Mode B) → demo `3.3`
> **Compiled:** 2026-06-25

---

## 0 · Purpose
Make SYNAPSE *orchestrate* H22's native APEX MCP as one source among many — never compete with
it, never reimplement it. The provider seam is the concrete form of "the official MCP makes the
model fluent; SYNAPSE makes it accountable." Everything below exists to put the MCP's output
**inside the truth contract and the `agent.usd` ledger.**

---

## 1 · Provider abstraction (normalize on the envelope, not a gateway)
A provider is a thin adapter that exposes a uniform surface to SYNAPSE's orchestrator. The APEX
MCP becomes one registered provider alongside the model providers (Opus/Sonnet/Gemini/Nemotron).

- **Registry:** `server/providers/__init__.py` exposes `providers.get("apex_mcp")`. Registration is
  declarative; the orchestrator never special-cases the MCP.
- **Normalized on the native Anthropic-shaped envelope** — *not* a gateway like LiteLLM. Same
  decision as `SYNAPSE_MULTI_PROVIDER_HARNESS_v1.md`: one envelope shape preserves the truth contract.
- **Mock-first:** `science/mcp_mock.py` stands in for the MCP on H21 — same tool-list shape, benign
  responses — so `0.8`/`0.9` build and contract-test the seam before H22 exists. Drop day swaps the
  mock endpoint for the shipped one (verified by `1.7`); no design changes.

```
orchestrator → providers.get("apex_mcp").call_tool(name, args) → { envelope }
```

---

## 2 · Truth-contract wrapping
Every MCP tool call returns an **envelope** that records what was actually observed — a handler
cannot claim an outcome it didn't see, and that rule extends to provider surfaces.

Envelope (minimum):
- `observed` — the raw tool result as returned by the MCP (never synthesized).
- `claimed` — present only if the handler asserts something beyond `observed`; must equal `observed`
  or the truth contract is violated. (`check_mcp_truth_contract` asserts no overclaim.)
- `validator_verdict` — the MCP's own "is this valid APEX?" result, **carried as an input**, never
  restated by SYNAPSE as its own judgment (see §3).
- `source: "apex_mcp"`, `tool`, `args_digest`, `ts`.

---

## 3 · Validator verdict → provenance (not a Synapse claim)
The native MCP validates the APEX it generates. SYNAPSE does **not** reimplement APEX validation
and does **not** relabel that verdict as its own. Instead:

- The verdict rides in the envelope as `validator_verdict`.
- When an MCP-sourced action mutates the scene/stage, the `agent.usd` ledger entry records it as a
  provenance **input**: `customData:synapse:validator_verdict` (provenance, not authorship), alongside
  the usual `decision` + `reasoning` + `revert`.
- The distinction the Evaluator enforces (rubric 5): *theirs* answers "is this valid APEX?"; *the
  truth contract* answers "did the handler observe what it claims?" Two different questions; both recorded.

> Schema placement (`customData` vs typed USD schema) for `validator_verdict` is **RFC-only** with
> Michael Gold — do not unilaterally place it. Track under the Gold schema RFC.

---

## 4 · Scout federation (consume, don't rebuild — D-H22-2)
`synapse_scout` federates the APEX MCP as a knowledge source; it never owns an APEX-syntax corpus.

- `server/scout_sources.json` declares the APEX source with `"kind": "provider"` pointing at
  `apex_mcp`. The guardrail `scout_no_apex_corpus` fails the build if a local APEX corpus appears or
  the source kind isn't `provider`.
- Scout's own differentiators are untouched and remain authoritative: the `exists_in_runtime` flag
  (`dir()`-introspected against the live runtime) and cross-context breadth (SOP/LOP/COP/Karma/USD)
  that an APEX-only MCP will never cover. Every federated hit carries `source: "apex_mcp"` and
  `exists_in_runtime` (asserted by `check_scout_federates`).

---

## 5 · Shipped-surface probe (D-H22-4 — pre-release prose is not ground truth)
Before any wiring touches the real MCP, `science/mcp_surface_probe.py` enumerates the **installed**
H22 MCP's actual tool list and diffs it against the recorded surface:

- On H21 it points at the mock; the diff should be ~empty — that empty diff proves the probe works
  before the drop makes it real (same logic as `apex_probes.py` task `0.2`).
- On drop, `absent` and `renamed` endpoints must both be **0** before `2.7`/`2.8` proceed; confirmed-
  absent endpoints **auto-quarantine** without re-litigation. `check_mcp_surface_probe` gates this.

---

## 6 · Harness mapping
| Boundary directive | Scaffold (Mode A, mock) | Verify (Mode B) | Wire (Mode B) | Checks |
|---|---|---|---|---|
| D-H22-1 register provider | `0.8` | — | `2.7` | `mcp_registered`, `mcp_truth_contract`, `ledger` |
| D-H22-2 scout federates | `0.9` | — | `2.8` | `scout_federates`, `scout_no_apex_corpus` |
| D-H22-4 verify surface | (mock diff) | `1.7` | gates `2.7`/`2.8` | `mcp_surface_probe` |
| §3 verdict-as-provenance | `0.8` | — | `2.7` | `mcp_truth_contract`, `ledger` |
| demo with receipts | — | — | `3.3` | `mcp_registered`, `ledger` |

---

## 7 · Non-goals (enforced as guardrails)
- Not an APEX implementation — reuse the MCP's output, never regenerate APEX ourselves.
- No APEX-syntax corpus in scout — federate (`scout_no_apex_corpus`).
- No rigging-authoring drift — Synapse authors COP/LOP/SOP/Karma/USD (`no_rigging_drift`).
- No overclaiming an MCP result — observed ≥ claimed (`mcp_truth_contract`).

## 8 · Open gates
- Ratify `SYNAPSE_H22_BOUNDARY.md` (flip DRAFT → ratified) before FORGE.
- Gold RFC for `validator_verdict` schema placement (`customData` vs typed schema).
- D-H22-4 verification on the shipped H22 build before `2.7`/`2.8` execute.
