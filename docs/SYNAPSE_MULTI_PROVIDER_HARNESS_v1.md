# SYNAPSE_MULTI_PROVIDER_HARNESS_v1

> **Constitutional dispatch.** Commit before running (F3). This document governs the addition of a
> provider-abstraction layer to SYNAPSE's chat path. ARCHITECT designs, FORGE implements, CRUCIBLE
> attacks. The harness halts-and-surfaces at every D-gate and never defaults an owner decision.

---

## ORGANIZING TRUTH

**The model is the author. The provider is therefore a property of provenance — not a hardcoded assumption.**

Today the `anthropic` client is wired in as if it were the only possible author. This harness makes
"which engine authored this action" a *recorded fact* that happens to resolve to one of four models,
and makes the panel's author token carry that identity. The work is not "call more APIs." The work is
**preserve the truth contract and the agentic loop across four tool-calling dialects.**

---

## THE FOUR TARGETS

| Slot | Model | API string (SEED — confirm at Mile 0) | Surface | Tool support | Context |
|---|---|---|---|---|---|
| 1 | Claude Opus 4.8 | `claude-opus-4-8` | Anthropic SDK (native) | native blocks | large |
| 2 | Claude Sonnet 4.6 | `claude-sonnet-4-6` | Anthropic SDK (native) | native blocks | large |
| 3 | Gemini 3.5 | `gemini-3.5-flash` (GA) · Pro string **TBD/preview** | google-genai SDK | functionDeclarations | 1M |
| 4 | Nemotron 3 | **see D2** — `nemotron-3-ultra:cloud` (cloud) *or* local Nano | Ollama API | OpenAI-shaped `tool_calls` | 256K–1M |

**Verified facts feeding the seed (2026-06):**
- `gemini-3.5-flash` is GA and agentic-tuned (MCP Atlas 83.6%). `gemini-3.5-pro` may be **preview-only** — do not hardcode.
- Nemotron 3 Ultra is **550B MoE (55B active)** and on Ollama exists **only as `nemotron-3-ultra:cloud`**. It will **not** run on the 4090. Local Nemotron options are Nano-class (`nemotron-3-nano:4b` comfortable; `nemotron-3-nano:30b` ≈24GB, maxes the card).
- All four are tool/agent-tuned with large context. This de-risks the loop but does **not** waive fidelity measurement.

> **Model IDs live in config, never in business logic.** The registry is data. Adding/retiring a model
> must never touch dispatch code.

---

## OWNER DECISION GATES — the harness refuses to default these

**D1 · Abstraction strategy.** Build a thin **owned** provider layer vs adopt a gateway (LiteLLM).
→ *Harness assumes OWNED.* Rationale: inside-out embedded-Python + separate site-packages makes heavy
deps painful; truth contract + 110-tool loop demands inspectable tool translation; provenance needs
first-class model identity. Flip this and Leg 2 changes shape.

**D2 · Nemotron slot purpose.** This single choice resolves the contradiction in "local Ollama Ultra":
- **(P) Local / private / offline / $0** → `nemotron-3-nano:4b` (or `:30b` accepting the memory squeeze). Weaker tool fidelity — CRUCIBLE will quantify.
- **(A) Best open agentic engine, cost-saving vs Claude** → `nemotron-3-ultra:cloud`. Cloud, bills, data leaves the box.
- One adapter serves both; only the tag + auth differ.

**D3 · Mid-loop provider failure policy.** When a non-Claude provider fails or emits a malformed tool call mid-loop:
- **(halt)** halt-and-surface — *recommended, matches the truth contract and no-silent-fallback discipline*; or
- **(fallback)** auto-fallback to Claude — convenient, but muddies authorship/provenance unless logged and surfaced.
→ *Harness assumes HALT, with opt-in surfaced fallback.* Owner ratifies.

**D4 · Cost meter for non-billed paths.** Local Ollama = `$0` numeric vs a `local` label vs a `cloud` label for `:cloud`. Cosmetic but it's the panel's honesty signal. Owner picks the display contract.

---

## INVARIANTS — violating any is a CRUCIBLE failure, not a tradeoff

- **Invariant F (Floor).** The Claude/Anthropic path **never regresses.** Full existing suite (2,800+) green on Claude *before* any non-Claude adapter merges. New providers are gated on the floor — exactly as Track C is gated on Track H. If Leg 2 overruns, the floor still ships; the new providers slip.
- **Invariant Z (Zero-hou).** The provider layer is cognitive-layer. The abstraction and all `cognitive.tools.*` import **zero `hou`**. A `hou` import in this layer fails the build.
- **Invariant T (Truth).** Every provider is held to the same truth contract: *results never claim what was not observed.* A model that hallucinates a tool result is a defect, never a feature. Requires a cross-provider truth-conformance test (below).
- **Invariant P (Provenance).** Every action records its **authoring model identity**; the panel author token reflects it. **Display/telemetry layer only.** Writing model identity into USD `customData:synapse:signed_by` is **Michael-Gold-RFC-gated** — this harness does **not** touch the USD substrate. Multi-provider creates exactly the temptation to do so; resist it until Gold ratifies.
- **Invariant E (Envelope).** `AgentToolError` (frozen dataclass) is unchanged. All provider/transport errors normalize **into** it; nothing new is raised past the boundary.

---

## MILE 0 — RE-GROUNDING (V0-leads → live facts) · NO MUTATION

Everything below is a lead until re-grounded against the running build. Discovery, not edits.

1. **Find the real chat client.** Memory anchors to confirm (not assume): the Anthropic wrapping via
   raw SDK (`client.messages.create()`), `mcp_server.py` (where `synapse_scout` is wired), `auth.py`
   (the `SYNAPSE_ANTHROPIC_KEY` env path; `hou.secure` does **not** exist). Locate the actual module
   that builds requests, owns the tool-call loop, and meters cost. Name it in the ARCHITECT output.
2. **Phantom-API discipline on three new SDKs.** `dir()`-introspect the **installed** surfaces of
   `anthropic`, `google-genai`, and `ollama` — in **both** site-packages (graphical H21.0.671 **and**
   hython 21.0.631; they are separate). Record `exists_in_runtime` per symbol used. Trust the symbol
   table, not the docs.
3. **Confirm model IDs against live endpoints**, not prose:
   - Gemini: `list_models()` against the real key → resolve Flash vs Pro string actually available.
   - Ollama: `ollama.list()` / `GET /api/tags` (local) and confirm `nemotron-3-ultra:cloud` reachability + auth (cloud).
   - Anthropic: confirm `claude-opus-4-8`, `claude-sonnet-4-6` resolve.
4. **Inventory the tool surface.** Confirm the live tool count (~112) and serialize the **full schema
   payload size** — this is the load-bearing number for Leg 1's fidelity question.
5. **Capture the loop contract.** How tool results re-enter the request; where `hou.undos.group()`
   wraps mutation (≈37 sites); where provenance is recorded today.

**Mile 0 exit:** a re-grounded facts sheet + the named client module. No code changed.

---

## LEG 1 — ARCHITECT (design only, no mutation)

**Baton:** Mile 0 facts sheet. **Hand-off:** a design doc + the measured fidelity verdict. **No code merges in this leg.**

### 1A · The Provider protocol
Define a minimal `Provider` interface normalized on SYNAPSE's **native Anthropic-shaped envelope**
(messages + tool_use/tool_result + system). Surface, at minimum:
- `complete(messages, tools, system, stream) -> NormalizedResponse`
- normalized tool-call representation (name, id, args) and tool-result representation
- `model_identity` (for Invariant P)
- `cost(usage) -> Decimal | None` (None ⇒ non-billed; see D4)
- error normalization into `AgentToolError`

### 1B · Adapters (one per dialect)
- **Anthropic** — identity/near-identity; it is the home format.
- **Gemini** — Anthropic envelope ↔ `functionDeclarations` / `functionCall` / `functionResponse`; map `system` → `system_instruction`; handle `thinking_level` enum.
- **Ollama** — Anthropic envelope ↔ OpenAI-shaped `tools` / `tool_calls`; **same adapter for local and `:cloud`** (tag + auth differ only).

### 1C · THE SEARCH ITEM — tool-call fidelity at 110 tools (measure before committing)
*Unknown-direction finding. Measure first, in the spirit of C6. Predict signatures, then observe.*

- **H1 — full schema routes clean on all four.** Signature: valid tool_calls, correct names, no schema-size error, args type-faithful. → ship full schema, no router.
- **H2 — non-Claude routing degrades past N tools.** Signature: dropped/invented tool names, rising latency, schema-size rejections. → contingency: **tool subsetting / per-turn router** exposing only relevant tools.
- **H3 — translation lossiness.** Signature: tool fires but args are reshaped (enum coercion, nested-object flattening, dropped optional fields). → the dangerous one; this is a silent Invariant-T violation. Contingency: strict round-trip arg validation in each adapter.

Run a representative tool subset across all four providers headless (hython). **The verdict here decides
native-vs-compat per provider and whether a router is required — it is not decided in advance.**

### 1D · Provenance design
Thread `model_identity` through the existing provenance recording to the panel author token.
Display/telemetry only (Invariant P). Define the author-token string contract for the panel
(`SYNAPSE wordmark + author token` already exists in v9 — extend it, don't redesign it).

**Leg 1 exit (mile marker):** protocol signature frozen, adapter mapping tables written, **fidelity
verdict + router decision recorded**, provenance thread designed. Owner ratifies D1–D4 if not already.

---

## LEG 2 — FORGE (implement) · GATED ON THE FLOOR

**Baton:** ratified Leg 1 design. **Discipline:** atomic commits, race-safe push (fetch+rebase, max 3, halt on conflict). Anthropic path stays green the entire leg.

1. **Provider protocol + registry** (config-driven; model IDs as data).
2. **Anthropic adapter first** — wrap the *existing* path behind the protocol with **zero behavior
   change**. Prove Invariant F: full suite green, identical outputs. This adapter is the floor.
3. **Gemini + Ollama adapters** behind a **feature flag**, applying the three-step port discipline
   (implement → register → wire), router included only if Leg 1 demanded it.
4. **Cost tables** per provider; non-billed paths per D4. Local = no spend; `:cloud` + Gemini metered.
5. **Vendor deps** into both site-packages (`google-genai`, `ollama`). Silent fallback prohibited —
   a missing vendored dep fails loud, like the font-load contract.
6. **Provenance wiring** — author token reflects authoring model. **No USD `customData` writes.**

**Leg 2 exit:** all four selectable behind the flag; **Invariant F intact** (Claude suite green); adapters isolated; nothing merged that regresses the floor.

---

## LEG 3 — CRUCIBLE (adversarial testing · never weakens an assertion)

Fix-forward only (Commandment 7). Tests get harder, never softer.

1. **Tool-call fidelity suite** — representative tool subset × all four providers. Asserts correct
   name, id, and **type-faithful args** (directly kills H3). This is the spine of the leg.
2. **Truth-contract conformance (Invariant T)** — a scripted scenario where a provider is fed a
   context that tempts a fabricated tool result; assert SYNAPSE never reports an unobserved result,
   on every provider.
3. **Provenance correctness (Invariant P)** — author token matches the engine that actually authored,
   across switches; assert **no USD `customData` mutation** occurred.
4. **Failure injection (D3)** — provider down, malformed tool call, context overflow, auth failure.
   Assert halt-and-surface (or surfaced opt-in fallback). No silent degradation.
5. **Floor regression (Invariant F)** — full 2,800+ suite green on Claude. Non-negotiable merge gate.
6. **Envelope (Invariant E)** — every injected provider error arrives as `AgentToolError`, nothing else.

**Leg 3 exit:** every invariant has a green adversarial test; the floor is provably intact; the
fidelity verdict is now measured fact, not Leg 1 prediction.

---

## GATE DISCIPLINE

```
Mile 0  ──►  Leg 1 ARCHITECT  ──►  [D1–D4 ratified]  ──►  Leg 2 FORGE  ──►  Leg 3 CRUCIBLE  ──►  ship behind flag
                                                              │
                                              Invariant F (floor) gates every merge here
```

- Track-C-gated-on-Track-H rule: **non-Claude adapters cannot merge while the Claude floor is red.**
- If Leg 2 overruns, the **floor ships alone**; providers 3 & 4 slip. The floor never slips for them.
- Halt-and-surface before any irreversible step. D-gates are explicit and never defaulted.

---

## CAPSULE — to be filled at close of each leg

```
WHERE WE ARE   · <leg + mile marker, e.g. "Leg 2 FORGE, mile 2 of 3 — Gemini adapter green behind flag">
MILE MARKER    · <what is provably done; which invariants hold>
BLOCKERS       · <open D-gates; failing tests; vendoring/site-package issues>
NEXT ACTION    · <single next move>
```

---

## OUT OF SCOPE (explicit — do not let it balloon)

- USD substrate writes of model identity (`customData:synapse:signed_by`) — **Gold RFC zone.**
- Panel redesign — v9 is locked; extend the author token only.
- New tools, GEPA/FORGE, FTS5 sidecar — orthogonal; not this harness.
- Streaming UX polish beyond parity — fidelity and truth come first; pretty later.
