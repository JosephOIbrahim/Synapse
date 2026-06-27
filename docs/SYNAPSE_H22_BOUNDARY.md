# SYNAPSE × Houdini 22 — The Boundary

**`SYNAPSE_H22_BOUNDARY.md`**

> **Status:** DRAFT — awaiting human ratification (flip DRAFT → **ratified** to unlock FORGE wiring of `2.7`/`2.8`).
> **Owner:** Joe Ibrahim
> **Implemented by:** [`SYNAPSE_H22_PROVIDER_APEX.md`](SYNAPSE_H22_PROVIDER_APEX.md) (D-H22-1 / D-H22-2 / D-H22-4)
> **Enforced by:** `harness/verify/checks.py` guardrails + the `guardrails` block in `harness/tasks.json`
> **Context:** H22 drop ETA mid-July 2026 (~3 weeks out) · grounded against SYNAPSE on Houdini 21.0.671
> **Compiled:** 2026-06-27

---

## 1 · Why this doc exists

Houdini 22 ships a **native APEX MCP** — SideFX's own Model Context Protocol server that makes an
LLM fluent in APEX (the rigging/graph authoring language). That is the first time a first-party
Houdini surface overlaps SYNAPSE's territory, and it forces one existential question:

> When the vendor ships a tool that generates APEX better than we ever could, what is SYNAPSE *for*?

Answer it wrong — by racing the MCP on APEX fluency — and SYNAPSE becomes a worse copy of a
first-party tool. Answer it right and the MCP becomes **an input that makes SYNAPSE stronger**.
This document draws that line once, names the decisions it implies (D-H22-1…4), and the non-goals
that protect it. Every guardrail in the harness exists to keep a future change — ours or a
Generator round's — from quietly crossing it.

---

## 2 · The thesis

> **The native APEX MCP makes the model *fluent*. SYNAPSE makes it *accountable*.**
> **Orchestrate it as one source among many. Never compete with it, never reimplement it.**

Fluency is a commodity the moment the vendor ships it. Accountability is not, and it is exactly
what an LLM acting on a live scene lacks: a record of *who decided what, what was actually
observed, and how to undo it*. SYNAPSE's moat is three things the APEX MCP structurally cannot
provide alone:

1. **Receipts** — every mutation is undo-wrapped and written to `agent.usd` with `decision` +
   `reasoning` + `revert`. *No ledger entry ⇒ it didn't happen.*
2. **Cross-context breadth** — SYNAPSE authors across COP / LOP / SOP / Karma / USD. An APEX-only
   MCP is a single domain; SYNAPSE is the orchestrator that spans them.
3. **Runtime truth** — `synapse_scout`'s `exists_in_runtime` flag is decided by a `dir()`
   introspection of the *live* build, not by a corpus. It is the front-line defense against
   phantom APIs — and it stays authoritative even over the MCP's own claims.

The MCP plugs into #1–#3; it does not replace them.

---

## 3 · The two roles

### 3.1 The native APEX MCP — a first-party source SYNAPSE consumes
A registered **provider**, peer to the model providers (Opus / Sonnet / Gemini / Nemotron). It
answers "what is valid APEX?" with first-party authority. SYNAPSE calls it, never special-cases
it, and never relabels its output as SYNAPSE's own work.

### 3.2 SYNAPSE — the orchestrator of record
The layer that decides *which* source to call, wraps every result in the truth contract, lands the
consequential ones in `agent.usd`, and keeps the whole action reversible. SYNAPSE is where the
receipts live. That is the product.

---

## 4 · D-H22-1 — Register the MCP as a truth-contract-wrapped provider

**Decision.** The APEX MCP is registered as a first-class provider (`providers.get("apex_mcp")`),
and every tool call returns a **truth-contract envelope** — normalized on the native
Anthropic-shaped envelope, *not* a gateway.

The envelope records what was actually observed:

| field | meaning |
|---|---|
| `observed` | the raw tool result as returned by the MCP — never synthesized |
| `claimed` | present only if the handler asserts beyond `observed`; **must equal `observed`** or the contract is violated |
| `validator_verdict` | the MCP's own "is this valid APEX?" result — carried as a provenance **input**, never restated as a SYNAPSE judgment (see below) |
| `source` / `tool` / `args_digest` / `ts` | provenance metadata |

**The two-question rule.** *Theirs* answers "is this valid APEX?"; *the truth contract* answers
"did the handler observe what it claims?" Two different questions. SYNAPSE records both and conflates
neither — the MCP's verdict rides into `agent.usd` as `synapse:validator_verdict` (provenance, not
authorship), alongside `decision` + `reasoning` + `revert`.

**Why.** This is the concrete form of "fluent vs accountable." It puts the MCP's output *inside*
the contract and the ledger without SYNAPSE pretending to have authored or validated it.

**Verified by.** `check_mcp_registered`, `check_mcp_truth_contract`, `check_ledger` · tasks
scaffold `0.8` (mock) → wire `2.7` (shipped).

---

## 5 · D-H22-2 — Scout federates the MCP; SYNAPSE owns no APEX corpus

**Decision.** `synapse_scout` federates the APEX MCP as a knowledge source. `server/scout_sources.json`
declares the APEX source with `"kind": "provider"` pointing at `apex_mcp`. SYNAPSE builds and
maintains **no local APEX-syntax corpus** that competes with the first-party source.

**Why.** A corpus we maintain would be perpetually one drop behind the vendor's ground truth — the
exact staleness `exists_in_runtime` was built to kill. Federate the authority; don't fork it. Scout's
own differentiators stay intact and authoritative: `exists_in_runtime` (`dir()`-introspected against
the live runtime) and the cross-context breadth (SOP/LOP/COP/Karma/USD) an APEX-only MCP will never
cover. Every federated hit carries `source: "apex_mcp"` and an `exists_in_runtime` flag.

**Verified by.** `check_scout_federates` (source-tagged + `exists_in_runtime` present),
`check_scout_no_apex_corpus` (standing guardrail) · tasks scaffold `0.9` → wire `2.8`.

---

## 6 · D-H22-3 — Authoring center of gravity stays off rigging/APEX

**Decision.** SYNAPSE's authoring domain is **COP / LOP / SOP / Karma / USD**. Rigging and APEX
authoring are the native MCP's floor, not SYNAPSE's. The clean signal is a declared
authoring-domain allowlist (`server/authoring_domains.json`); drift terms (`apex`, `rig`, `rigging`,
`kinefx`, `muscle`, `cfx`) entering it is a deterministic failure.

**Why.** The fastest way to become a worse copy of the MCP is to slowly grow rigging features
"because we can." This decision makes that drift *visible and blocked* rather than discovered three
sprints later. SYNAPSE orchestrates a rig the MCP authored; it does not author the rig.

**Verified by.** `check_no_rigging_drift` (standing guardrail).

---

## 7 · D-H22-4 — Probe the shipped surface; pinned prose is not ground truth

**Decision.** Before any wiring touches the real MCP, `science/mcp_surface_probe.py` enumerates the
**installed** H22 MCP's actual tool list and diffs it against the recorded surface. `absent` and
`renamed` endpoints must both be **0** before `2.7`/`2.8` proceed; confirmed-absent endpoints
**auto-quarantine** without re-litigation.

**Why.** Pre-release documentation is a promise, not an interface. This is the same discipline that
governs `hou.*`/`pdg.*`/`pxr.*` — the `dir()`-is-a-hard-gate rule — aimed at the MCP's tool surface
instead of the Python runtime. On H21 the probe points at the mock; an empty diff there proves the
probe works *before* the drop makes it real.

**Verified by.** `check_mcp_surface_probe` · task `1.7` (gates `2.7`/`2.8`).

---

## 8 · Non-goals — the moat (standing guardrails)

These are the behaviors that erode the boundary. They run on **every** harness task, in addition to
that task's own `verify` list, so no single Generator round can silently cross the line. A guardrail
returning `ok:false` is a **deterministic FAIL** (the harness writes a repair ticket and loops
*before* the adversarial Evaluator is invoked); `ok:null` means "not yet wired" and only **warns**.

| Non-goal | Stated | Enforced by |
|---|---|---|
| **Not an APEX implementation** | Reuse the MCP's output; never regenerate APEX ourselves. | (stance; D-H22-1/2 make it structural) |
| **No APEX corpus in scout** | Federate the first-party source; never fork it into a local corpus. | `scout_no_apex_corpus` *(guardrail)* |
| **No rigging-authoring drift** | Author COP/LOP/SOP/Karma/USD; rigging is the MCP's floor. | `no_rigging_drift` *(guardrail)* |
| **No mutation that bypasses the ledger** | Every scene/stage mutation routes through provenance and lands in `agent.usd`. | `provenance_not_bypassed` *(guardrail)* |
| **No overclaiming an MCP result** | `observed ≥ claimed`; the MCP's verdict is an input, never a SYNAPSE claim. | `check_mcp_truth_contract` *(per D-H22-1 call)* |

If any of these flips false, the moat is leaking. Treat it as a release blocker, not a style note.

---

## 9 · How the harness holds the line

The boundary is not a memo; it is wired into the gate that grinds H22 prep. `run.ts` runs each
task's `verify` checks **and** the cross-cutting `guardrails` set on every sprint, short-circuiting
to a repair ticket on any guardrail violation before the Evaluator ever sees the work.

| Directive | Scaffold (Mode A, mock) | Verify (Mode B) | Wire (Mode B) | Checks |
|---|---|---|---|---|
| D-H22-1 register provider | `0.8` | — | `2.7` | `mcp_registered`, `mcp_truth_contract`, `ledger` |
| D-H22-2 scout federates | `0.9` | — | `2.8` | `scout_federates`, `scout_no_apex_corpus` |
| D-H22-3 no rigging drift | (standing) | (standing) | (standing) | `no_rigging_drift` |
| D-H22-4 verify surface | (mock diff) | `1.7` | gates `2.7`/`2.8` | `mcp_surface_probe` |
| Provenance integrity | (standing) | (standing) | (standing) | `provenance_not_bypassed` |
| Demo with receipts | — | — | `3.3` | `mcp_registered`, `ledger` |

The boundary checks ship as honest scaffolds: until ADAPTed against the real seams
(`server/providers/apex_mcp.py`, `server/scout_sources.json`, `server/authoring_domains.json`),
they return `ok:null` and warn — they never fake a pass.

---

## 10 · Staging & ratification

- **Mode A (now, on H21):** scaffold and contract-test the provider seam against the mock
  (`science/mcp_mock.py`) — tasks `0.8`/`0.9`. This proves the abstraction before H22 exists.
- **Mode B (drop day, mid-July):** verify the shipped surface (`1.7`), then swap the mock for the
  real MCP and wire (`2.7`/`2.8`). No design changes — only the endpoint moves.

**Open gates (human-owned):**
1. **Ratify this document** (DRAFT → ratified) before FORGE wires `2.7`/`2.8`.
2. **Gold RFC** for `validator_verdict` schema placement in `agent.usd` (`customData` vs a typed USD
   schema) — do not unilaterally place it.
3. **D-H22-4 verification** against the shipped H22 build before `2.7`/`2.8` execute.

> Ratification is the human gate the harness will not cross. Until this flips to **ratified**, the
> boundary is the intended direction; after, it is the enforced contract.
