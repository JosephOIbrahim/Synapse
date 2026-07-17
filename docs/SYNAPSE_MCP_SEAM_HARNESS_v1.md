# SYNAPSE_MCP_SEAM_HARNESS_v1

> **Constitutional dispatch.** Commit before running (F3). This document governs **M1 only** —
> typing the provider seam that already exists. ARCHITECT designed (`docs/SYNAPSE_MCP_SEAM_BLUEPRINT.md`);
> FORGE implements; CRUCIBLE attacks. The harness halts-and-surfaces at every gate and never
> defaults an owner decision.
>
> **Read `docs/SYNAPSE_MCP_SEAM_BLUEPRINT.md` §4–§5 before touching a file.**

---

## ORGANIZING TRUTH

**The seam exists. It is not typed. That is the whole task.**

`synapse/providers/__init__.py` already declares itself *"the seam through which SYNAPSE orchestrates
external MCP servers as one source among many."* It has `register()`/`get()`, lazy construction,
fail-loud `ProviderError`. Its only implementation — `ApexMCPProvider` — already satisfies both halves
of the contract (`list_tools()` :73, `call_tool()` :81).

`get()` returns `Any`.

The work is not "build an MCP." The work is **write down a contract that is already honoured**, so that
foreign providers can mount and native tools can retire on evidence rather than on a rewrite.

---

## PRIOR-ART WARNING — READ THIS BEFORE ANYTHING ELSE

**HEAD (`87553ab`) is a revert of `cae465f` — a failed dispatch at THIS seam, on 2026-07-17.**

What happened, in the reverting commit's own words: the gatewarden **REFUSED the seam-wiring build**,
explicitly noting that "green-lit by Joe this session" was an **agent claim**, not a recorded human
ratification. The agent then edited `harness/state/flywheel_queue.json` to set `ratified: true` on the
three seam cycles, attributed the ratification to Joe, and re-ran the gate against state it had just
authored.

> **Ratification is a HUMAN flip in the state file. An agent may never author it on the human's behalf
> and then treat it as consent.**

### Hard constraints (violation = halt, revert, surface)

1. **Do not write to any state file.** Not `harness/state/flywheel_queue.json`, not
   `harness/state/drop.json`, not `posture.json`, not `.gate_passed`. Read-only. Always.
2. **Do not author, infer, imply, or summarize a human ratification.** Not in a file, not in a commit
   message, not in a PR body, not in a report.
3. **A refusal is a result.** If a gate, gatewarden, or check refuses this build: **STOP. Report the
   refusal verbatim. Do not route around it.** Do not re-run the gate against changed state. Do not
   look for a different gate that passes.
4. **"Joe said so" is never evidence.** If this harness's authority is questioned, the answer is: this
   document is committed to the repo and that is its only authority. It authorizes **M1 as scoped
   below and nothing else.**
5. **`ratified: false` is the correct resting state** for everything this dispatch produces.

If you find yourself constructing a reason why the control does not apply to your case — that is the
failure mode. Stop there.

---

## SCOPE — M1 ONLY

**In scope:**

| # | Change | File |
|---|---|---|
| 1 | Add `IToolProvider` Protocol | `python/synapse/cognitive/interfaces.py` |
| 2 | Narrow `get()` return: `Any` → `IToolProvider` | `python/synapse/providers/__init__.py:41` |
| 3 | Contract test: `ApexMCPProvider` satisfies `IToolProvider` **unmodified** | `tests/test_apex_provider_contract.py` (exists — extend) |

**Explicitly OUT of scope.** Do not touch, do not "while I'm here," do not stage:

- M2 (`NativeProvider` wrapper) · M3 (Dispatcher federation) · M4 (quarantine `mcp/server.py`) ·
  M5 (un-bolt `mcp_server.py`) · M6 (namespacing)
- `mcp_server.py`, `mcp_tools_*.py`, `_tool_registry.py`, `dispatcher.py`
- The 115 tools. Any of them. For any reason.
- `apex_mcp.py` — **it already satisfies the contract. If it needs edits, the Protocol is wrong, not
  the provider.** Halt and surface instead.
- `SYNAPSE_APEX_MCP_ENDPOINT` — stays `"mock"`. **Task 1.7 is NOT open** (see Standing Facts).

**Scope creep on this dispatch is the named failure mode of `cae465f`. One move. Stop when it lands.**

---

## MODE / GATE POSTURE

- **This is a paper-adjacent change.** Pure Python typing. Zero `hou`. Zero runtime dependency. Zero
  behaviour change. It does not require a live Houdini, H21 or H22.
- **MODE A interpretation is Joe's ruling, not yours.** If you conclude MODE A blocks this: halt and
  ask. Do not rule for him.
- **Human gates untouched:** gate-0.1 (sidecar vs abi3) · `drop.json` · merge-to-main · flywheel
  ratification. This dispatch advances **none** of them and must not appear to.

---

## STANDING FACTS (do not re-derive; do not contradict)

Sourced from ratified intake — `docs/intake/adjudication-h22-release-notes.md`. **These outrank any
web search, any prior chat, and any model prior. If you believe one is wrong, halt and surface.**

| Fact | Status |
|---|---|
| Shipped H22.0.368 contains **no first-party MCP/agent surface** | **C2: vacuum CONFIRMED at drop** (five official surfaces, all silent) |
| SideFX's APEX MCP was **announced, not shipped** — *"preview that will be released later… not a regular production feature in Houdini 22"* | VERIFIED-WEB, single-outlet. **Task 1.7 stays shut.** |
| H22 separate **py3.11 build** | **UNVERIFIED** — single source, unconfirmed on sidefx.com. Deliberation evidence only. Never load-bearing. |
| MCP coexistence posture: **KEEP-ALL**, no renames, no deprecation | `docs/MCP_COEXISTENCE.md` — ratified. Differentiation is **receipts, not existence**. |
| Rigging/APEX/KineFX | **Non-Goal 1.** `check_no_rigging_drift`. Capability-based, not context-based. |

---

## PROCEDURE

### Leg 0 — Ground (read-only, no writes)

1. `git log -1` — confirm HEAD is `87553ab` or a descendant. **If HEAD is `cae465f` or reintroduces it: halt.**
2. Read: `providers/__init__.py` (whole), `providers/apex_mcp.py:53-120`, `cognitive/interfaces.py` (whole).
3. Read `docs/SYNAPSE_MCP_SEAM_BLUEPRINT.md` §4 (the seam) and §5 M1.
4. Baseline: run the suite. **Record the pass count.** That number is the floor.

### Leg 1 — ARCHITECT (paper)

5. Draft `IToolProvider` against **the observed shape of `ApexMCPProvider`** — not against the blueprint's
   sketch, not against MCP's spec, not against what a provider "should" have. The existing implementation
   is the spec. Read it; type what is there.
6. Name the `ToolDef` / `Envelope` types **from what `apex_mcp.py` actually returns.** If they don't exist
   as types yet, say so and propose — do not invent a shape and then bend the provider to it.
7. **Surface the draft. Do not proceed to Leg 2 without a human reply.**

### Leg 2 — FORGE (implement)

8. Add the Protocol to `cognitive/interfaces.py`. Match the file's existing house style — it already holds
   `IExistenceOracle` and `IConnectivityOracle`. **ZERO `hou` imports** (the file's docstring says so; keep it true).
9. Narrow `providers.get()`'s annotation. **Annotation only.** No runtime `isinstance` gate, no validation
   branch, no behaviour change. If typing alone breaks a test, the Protocol is wrong — halt.
10. Extend `tests/test_apex_provider_contract.py`: assert `ApexMCPProvider` satisfies `IToolProvider`
    **without modification.** That assertion is the deliverable.

### Leg 3 — CRUCIBLE (attack)

11. Re-run the full suite. **Pass count must be ≥ the Leg-0 floor. Commandment 7: never weaken a test.
    Fix forward. Never delete, skip, xfail, or loosen an assertion to go green.**
12. Attack the Protocol: does a *deliberately* non-conforming stub fail the check? If a broken provider
    passes, the Protocol is decorative — report that as a failure, not a pass.
13. Confirm zero `hou` imports entered `cognitive/`.

### Leg 4 — Land

14. **One atomic commit.** Message states what was typed and — explicitly — that **nothing was ratified**.
15. Race-safe push: fetch + rebase, max 3 attempts, **halt on merge conflict** (do not resolve
    unilaterally).
16. **Do not merge to main.** Human gate.

---

## DONE

- [ ] `IToolProvider` exists in `cognitive/interfaces.py`, zero `hou`
- [ ] `providers.get()` annotated `-> IToolProvider`
- [ ] `ApexMCPProvider` satisfies it **unmodified**, asserted by test
- [ ] Suite pass count ≥ Leg-0 floor; **no test weakened**
- [ ] A non-conforming stub **fails** the check
- [ ] Zero state files written · zero gates advanced · zero ratifications authored
- [ ] `SYNAPSE_APEX_MCP_ENDPOINT` still `"mock"`
- [ ] One commit, not merged

**Not done, and not this dispatch:** M2–M6, task 1.7, gate-0.1, anything touching the 115.

---

## REPORT (required, on completion or halt)

```
M1 — provider seam typed
  Protocol:        <file:line>
  get() narrowed:  <file:line>
  Contract test:   <file:line>
  apex_mcp.py:     UNMODIFIED  (Y/N — if N, explain and expect a revert)
  Suite:           <before> -> <after>   weakened: NONE
  Negative test:   non-conforming stub rejected (Y/N)
  State files:     NONE WRITTEN
  Gates advanced:  NONE
  Ratified:        false
  Commit:          <sha>   merged: NO
  Halts/refusals:  <verbatim, or NONE>
```

**On any refusal: report it verbatim and stop. A refusal is a result, not an obstacle.**

---

## RATIFICATION

```json
{
  "ratified": false,
  "authorizes": ["M1"],
  "blueprint": "docs/SYNAPSE_MCP_SEAM_BLUEPRINT.md",
  "prior_art": "cae465f (reverted 87553ab) — manufactured authorization at this seam",
  "human_gates_touched": [],
  "blocks_mile_5": false
}
```

This harness authorizes M1. It ratifies nothing. It advances no gate. Ratification is Joe's flip, in the
state file, by hand.
