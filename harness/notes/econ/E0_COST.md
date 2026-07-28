# E0 — Cache + cost truth

**Leg** `E0` · **Harness** `ECON-01` · **Run** 2026-07-28 · **READ-ONLY**
**Governed by** `harness/AGENT_CONSTITUTION.md` · **Brief** `harness/prompts/e0.md`
**Producers** `econ_segments.py` · `econ_effective.py` · `econ_cachetrace.py` · `econ_gaps.py`

> **REVISION 2.** An adversarial pass against revision 1 upheld three showstoppers, and two of
> them **inverted the verdict**. Revision 1 concluded caching had already done T.1's work on the
> panel; it had not, and the reason was a unit error in revision 1's own arithmetic. Everything
> superseded is listed in the receipt's drift log (D6–D8) so the change is auditable rather than
> silent.

---

## The one-paragraph answer

**T.1 and prompt caching are not alternatives. They optimise different quantities, and the
brief's "opposite engineering programmes" framing is itself the error.** T.1 reduces
**context-window occupancy** (preload tokens). Caching reduces **price** (billed-token-
equivalents). A cache read cannot put anything under a preload-token ceiling — the tokens still
occupy the window — and a tool-surface reduction cannot make a cached token cheaper. Measured on
the live tree: the panel tool surface is **19,711 tokens = 9.86× the 2,000 ceiling**, and
**caching changes that number not at all**, while cutting its price by 90% per cache-read call.
Across **12 measured regimes** (2 sessions × 3 tool-loop depths × warm/cold), **every single
cheapest configuration contains T.1's reduction**, and caching-without-reduction **never wins
once**. So T.1 is necessary. It is also not sufficient, and it is not where the money is on
large scenes, where scene grounding is **91.5%** of an API call.

---

## Q1 — Is the tool surface actually 17,310 tokens?

### The API is still blocked. The figure remains a PROXY.

`harness/notes/_credit_probe.py`, run 2026-07-28:

```
count_tokens: HTTP 400  "Your credit balance is too low to access the Anthropic API"
request_id: req_011CdUVD9PusSuzZDatVCkfN
```

**C1-F2 stands.** The key authenticates (a bad key returns 401; this returns 400).

**No offline exact count exists either.** Vendored `anthropic` is **0.96.0**
(`_vendor/anthropic/_version.py:4`), pip's is **0.75.0** — both far past 0.39, the last release
shipping a local tokenizer. `tokenizers` 0.22.2 and `transformers` 4.57.3 import fine, but
Anthropic has never published a Claude 3+ tokenizer to load into them.

> Every token figure here is a declared proxy — `tiktoken/cl100k_base`, with `o200k_base`
> reported beside it. Bytes and chars are exact.

### And the inherited number is STALE.

| | committed T.0 (2026-07-23) | live tree (2026-07-28) | drift |
|---|---|---|---|
| registry `blake2b` | `c0cd3db16c29…` | `d6c79a415f13…` | **differs** |
| `mcp_http` tools / tokens | 115 / **17,310** | **120 / 18,962** | +5 / **+1,652** |
| `panel` tools / tokens (T.0 method) | 121 / 14,380 | **126 / 15,901** | +5 / +1,521 |
| `panel_worker` tokens | 10,264 | **10,264** | **0** |

Producer: `econ_segments.py` → `E0_segments.json:q1_tool_surface`. **CAL-6 = FAIL**, which is a
finding about the inherited number, not the meter — see CAL-7 below.

### The measurement band

The same 126 tools measure **15,901** or **19,711** cl100k tokens — **24% apart** — because
`token_baseline.py:96` measures the compact form while `anthropic_provider.py:120` emits
`json.dumps(body)` at default separators with `ensure_ascii=True`. Neither is the billed number:
**Anthropic re-renders tool definitions canonically**, so client whitespace never survives. The
MCP figure carries a second dependency — `mcp/protocol.py:15-24` uses `orjson` when importable
and `json.dumps(sort_keys=True)` otherwise, so **the same surface measures differently on two
machines**.

---

## Q2 — Is anything cached today?

**Yes — on exactly one path, and it is the correct one.** Not "absent".

```
python/synapse/panel/providers/anthropic_provider.py:64   cache_control on the LAST tool
python/synapse/panel/providers/anthropic_provider.py:69   cache_control on the system prompt
python/synapse/panel/providers/anthropic_provider.py:109  _with_prompt_cache() CALLED in stream()
```

Those are the only two occurrences **in 835 non-vendor `.py` files** — the producer's exact
search space (`econ_cachetrace.py:43-46`; tree-wide across all file types the string also
appears in five docs/notes and this brief, none of them code). Of **18 files containing
request-construction sites, 1 is cache-aware.**

### Reachability — it runs

```
synapse_panel.py:1684 _on_submit → :1690 _send → :1738 _start_worker
  → :1758 ClaudeWorker(provider=_make_provider())
  → claude_worker.py:157 provider.stream(...)
  → anthropic_provider.py:109 _with_prompt_cache(tools, system)
```

`registry.py:161,189,193` makes `AnthropicProvider` the `claude` provider *and* the fallback for
any unknown id. `claude_worker.py` retains no inline SSE or `http.client` construction.
**Placement is correct**: prefix order is `tools → system → messages`, so a hit covers both.

### The paths that do NOT cache

`cognitive/agent_loop.py:287` · `routing/router.py:646,794,853` · `agent/synapse_agent.py:186` ·
`host/daemon.py:502` · all four non-Claude providers. **Absent** in every case.

### The MCP path — a structural asymmetry, stated more carefully than in revision 1

`mcp/server.py:394` returns `tools.get_tools()` as a JSON-RPC response; `mcp_server.py:910`
builds `mcp.types.Tool(...)` over a stdio↔WebSocket bridge. Neither holds an Anthropic client.

> **SYNAPSE cannot set `cache_control` on the MCP path** — it is the server, and the external
> client builds the model request.
>
> **But "SYNAPSE cannot cache it" is not "it is uncached."** The external client (Claude Code /
> Desktop) may well cache the tool block itself. SYNAPSE cannot observe it either way. Revision 1
> scored that unknown as *absent* while scoring the panel's measured-present as a reason to
> discount T.1 — an asymmetry that manufactured its recommendation. **Unknown is recorded as
> unknown here.**

### A "live-verified" doc claim the code cannot produce

`docs/LATENCY_SOLARIS_REVIEW.md:6` asserts *"Live-verified (cache_creation 5052 → cache_read
5052)"*. The token `5052` appears **exactly once in the tree — that line.** No producer, no
receipt, no test, no log. Stronger: `anthropic_provider.py:206` has **no `message_start` branch**
— where `cache_read_input_tokens` arrives — and `:284` reads only `delta.stop_reason`, discarding
the usage object. `_note_usage` (`synapse_panel.py:556`) has **zero callers**.

*(The same file contradicts itself at `:208` — "caching is OFF". That resolves in favour of `:6`
on the on/off question; the code commit is a git ancestor of the doc commit. The parenthetical
figure does not survive.)*

---

## Q3 — What is the per-turn cost, broken down?

### Two corrections to the brief's segment model

1. **Grounding is not a top-level segment.** The system prompt carries only a 31–86 token flat
   block (`system_prompt.py:255-277`). All node/parm/geometry grounding enters as `tool_result`
   blocks **inside the conversation history** (`claude_worker.py:263-269`) — so grounding is
   *resident and permanent*, re-sent on every later call, not transient.
2. **A "turn" is not an API call.** `claude_worker.py:153` makes up to
   **`_MAX_TOOL_ITERATIONS = 25`** full requests per user turn, each carrying the entire tools
   array and the frozen system string (`:85`). Any tool-using turn is k ≥ 2.

The four segments below are therefore **disjoint** — `conversation_chat` excludes grounding, so
the shares are a real partition. *(Revision 1's rows overlapped and its shares were not.)*

### Which tool surface the panel actually sends — verified, because it decides everything

`claude_worker.py:90-91` defaults to the **93-tool** worker subset. **The interactive panel does
not use that default:** `synapse_panel.py:1753` passes `get_anthropic_tools()` explicitly — **126
tools / 19,711 wire tokens**, the surface priced throughout. *(Degraded path: `:56-58` sets the
symbol to `None` on import failure, silently shipping the 93-tool subset — a 35% smaller surface
reached by an import failure rather than a decision.)*

### The ranking — per API call, turn 3, k=2, grounding resident

**Small scene** (C1 rung `L1_color_falloff`, 13 nodes):

| segment | tokens | share |
|---|---|---|
| **tool definitions** | **19,711** | **82.8%** |
| system prompt | 2,669 | 11.2% |
| scene grounding (resident) | 998 | 4.2% |
| conversation chat | 423 | 1.8% |

**Large scene** (C1 rung `L6_karma_user_guide`, 25,850 nodes):

| segment | tokens | share |
|---|---|---|
| **scene grounding (resident)** | **245,544** | **91.5%** |
| tool definitions | 19,711 | 7.3% |
| system prompt | 2,669 | 1.0% |
| conversation chat | 423 | 0.2% |

**The ranking inverts with scene size, and that is the finding.** Grounding figures are C1's
**`tokens_model_visible`** column — what the model is charged after the double JSON encode
(C1-F8). *(Revision 1 silently took C1's smaller `tokens` column, understating grounding inside
the very argument that grounding dominates.)*

### Inside the system prompt

Producer: `econ_segments.py:system_prompt_anatomy` → `E0_segments.json:system_prompt_anatomy`.
*(Revision 1 quoted these from a subagent's prose with no producer, and two of them did not
reproduce.)*

| part | chars | tok |
|---|---|---|
| `_SOLARIS_CONTEXT_GUIDANCE` | 5,779 | 1,369 |
| `TONE.md` | 2,754 | 641 |
| `_TOOL_GUIDANCE` | 2,036 | 454 |
| `_IDENTITY` | 678 | 165 |
| `_OBJ_CONTEXT_GUIDANCE` | 567 | 118 |

Composed: `/stage` **2,660** · `/obj` **1,409** · `/out` = `/img` = `/mat` **1,290**.

---

## Q4 — What is the cache-stability profile?

> **ORACLE MISS, stated plainly.** The brief asks for stability across **at least 3 real turns**.
> **No real turns exist and none are recoverable.** The audit log at `~/.synapse/audit/`
> *does* decrypt (`~/.synapse/encryption.key`, 58,676 entries at time of run, 2026-02-06 → 2026-07-28) — revision
> 1 wrongly reported it as opaque — but `carries_message_payloads` is **False**: no `messages`,
> `system`, or `input_tokens` key exists in any entry. The only conversation persistence in the
> code is `save_shot.py:277,295,301-308`, a lossy 10-item markdown summary, not a transcript.
>
> Q4 is therefore answered by **driving the shipped request-construction code across two 3-turn
> sessions**. That is VERIFIED-RUNTIME on *construction*, labelled reconstructed (A5). **The
> oracle line is not met**, and naming the assumption is not the same as meeting it.

**Two sessions, not one** — one would have been a rigged control. *Stationary* holds the network
fixed; *navigating* moves `/stage → /obj → /stage`, which is ordinary lookdev.

| segment | stationary | **navigating** | why |
|---|---|---|---|
| **tool definitions** | ✅ stable | ✅ **stable** | immutable tuple, deterministic order (CAL-5) |
| system prompt (whole) | ❌ changes | ❌ changes | rebuilt per turn from live scene state |
| ├ static remainder | ✅ stable | ❌ **CHANGES** | the guidance literal itself swaps |
| └ scene-context block | ❌ changes | ❌ changes | selection / frame / network / hip |
| conversation history | ❌ grows | ❌ grows | append-only, nothing compacts |
| └ **history prefix** | ✅ byte-identical | ✅ byte-identical | mutation control PASS |

**Within a turn**, by contrast, tools and system are **frozen** (`claude_worker.py:85,157`) — so
iterations 2..k are byte-identical by construction. That is assumption **A7**, and it is what
makes caching pay.

### Measured single-field cache-bust deltas

| change | Δ chars | Δ tok | byte-identical? |
|---|---|---|---|
| network `/stage → /out` (also `/img`, `/mat`) | **−5,783** | −1,370 | no |
| network `/stage → /obj` | −5,214 | −1,251 | no |
| selection `[] → [one]` | +11 | +3 | no |
| frame `1 → 2` | 0 | 0 | **no** |
| hip rename | 0 | 0 | **no** |

> **The biggest single-field hazard is `/stage → /out`, not `/stage → /obj`.** Revision 1 named
> the wrong one and quoted it without a producer.

---

## Q5 — What would the ceiling be if caching were on?

### The question contains a unit error, and correcting it is the answer

`harness/verify/token_ceiling.json` declares **`max_preload_tokens: 2000`** — a budget on
**context-window occupancy**, listing `panel` among its measured surfaces. The brief (and
revision 1 of this document) compared a *cost* figure against it:

```
uncached        17,310 per turn      8.6x over ceiling
cached (read)   ~1,731 effective     UNDER the ceiling      <- unit substitution
```

**A cache read changes what a token costs. It does not remove the token from the window.**

| quantity | what it is | uncached | cached |
|---|---|---|---|
| **preload tokens** | window occupancy — what the ceiling budgets | 19,711 = **9.86×** | **19,711 = 9.86×** |
| **cost (BTE)** | price per API call | 19,711 | **1,971 (−90%)** |

> **Caching does nothing whatsoever for the ceiling.** On preload tokens, **T.1 is the only
> lever that exists.** That is the single most important correction in this revision.

### TTL — measured, not asserted

Revision 1 claimed *"VFX think-time between turns routinely exceeds 5 minutes"* with **no
producer**, and rested "the strongest argument for T.1" on it. The measurement was available.
`econ_gaps.py` decrypts the audit log (aggregate timing only — no content read into the artifact). **58,676 entries** at time of run; the log is append-only and live, so the count grows between runs:

| burst threshold | gaps | median | **% exceeding the 300s TTL** |
|---|---|---|---|
| 10s | 4,204 | 26s | **17.2%** |
| 30s | 1,965 | 147s | **36.8%** |
| 60s | 1,499 | 273s | **48.3%** |
| 120s | 1,075 | 572s | **67.3%** |

**At a 30s threshold, 63% of gaps fall *inside* the TTL.** The assertion is not supported. *(Bias:
these are tool-op bursts, not chat turns, and an artist can think without firing an operation —
so this is a lower bound on how often the cache is cold.)*

### The decision table — BTE per user turn, turn 3, small scene

| scenario | stat k=1 WARM | stat k=2 WARM | stat k=2 COLD | nav k=2 WARM |
|---|---|---|---|---|
| **S1** as shipped | 6,727 | 12,881 | 35,549 | 12,881 |
| **S2** no caching *(T.1's premise)* | 23,800 | 50,095 | 50,095 | 50,095 |
| **S3** T.1 alone | 6,089 | 14,673 | 14,673 | 14,673 |
| **S4** T.1 + caching | 4,956 | 9,339 | **11,639** | **9,339** |
| **S5** caching + volatile moved | 3,695 | 9,885 | 35,575 | 12,907 |
| **S6** T.1 + caching + volatile moved | **1,924** | **6,343** | 11,665 | 9,365 |

**Across all 12 regimes** (2 sessions × k ∈ {1,2,5} × warm/cold):

- **S4 wins 6 · S6 wins 4 · S3 wins 2 · S5 wins 0.**
- **Every cheapest configuration contains T.1's reduction.**
- **Caching without reduction never wins once.**

*(Revision 1 reported S5 as the largest available win. It compared S5 — granted caching —
against S3 — denied it — and omitted S6 entirely. Nobody would ship T.1 and switch caching off.)*

### Large scenes

Grounding is **91.5%** of an API call, and the spread across all scenarios is **30.4×**
(246,470 → 7,480,330 BTE). *(Revision 1 claimed "every scenario lands within 3% of ~119k" —
falsified by its own table.)* The surviving claim is the **ranking**, not a narrow band: on large
scenes neither programme touches the dominant term, because **grounding is the one segment that
cannot be cached** — it changes every turn by construction.

---

## Verdict on T.1

**T.1 is necessary, insufficient, and mis-framed — but it is not optional and it is not
second-best.**

| the claim | verdict |
|---|---|
| "the tool surface runs 8.6× over its ceiling" | **stale, and understated.** Live it is **9.86×** on the panel, 9.48× on MCP. |
| "you cannot be a credible token economist while your tool surface runs over" | **stands, and strengthens.** Caching does not reduce preload tokens at all. |
| "cut 17,310 → 2,000" is the right first mile | **yes on preload tokens, and it is in every winning configuration.** But it must ship *with* caching, not instead of it. |
| caching and reduction are "opposite engineering programmes" | **false.** They optimise different quantities. The measured best is always **both**. |

**This is not V1-refuting-the-scoped-delta.** The brief invited "T.1 is unnecessary" as the most
valuable possible result. The measured answer is the opposite: **T.1 survives, the case for it is
stronger than the brief's own arithmetic made it, and the thing that needed refuting was the
either/or framing.**

### What E2 should decide

1. **Ship both.** Every cheapest row in all 12 regimes contains T.1's reduction (S4 ×6, S6 ×4,
   S3 ×2); S5 (caching alone) never wins. Sequencing is a scheduling question, not a choice between them.
2. **Make the cached system span genuinely static.** Moving the scene-context block out is not
   sufficient alone — the measured *navigating* session shows the guidance literal swapping
   inside the span (`/stage → /out` is a −5,783-char change). The span is stable only if the
   scene block **and** the guidance selection both sit after the breakpoint.
3. **Grounding is the large-scene problem and it is a reduction problem, not a caching one**
   (91.5% of an API call, uncacheable by construction). It outranks the tool surface wherever
   scenes are big.
4. **Close the usage reader** (C1-F12): no cache claim is verifiable until `message_start` is
   parsed. Prerequisite for E3.
5. **Re-baseline `token_baseline.json`** — CAL-6 fails; the gate grades a registry that no
   longer exists.
6. **Consider the 1-hour TTL** only with pricing in hand — it is a 2.0× write multiplier, so it
   could make the cold case worse.

---

## Reader calibration (R60) and mutation-tested controls (R133)

| id | what | verdict |
|---|---|---|
| CAL-1 | tokenizer determinism | PASS |
| CAL-2 | segment additivity (parts vs whole) | PASS |
| CAL-3 | reader registers a removed tool | PASS *(dropped a tool)* |
| CAL-4 | byte-stability detector *(the Q4 instrument)* | PASS *(one-space edit seen; identical rebuild does not fire)* |
| CAL-5 | tool **order** stable across calls | PASS *(reversal detected)* |
| **CAL-6** | inherited T.0 baseline still describes this tree | **FAIL** — *the finding, not a reader fault* |
| **CAL-7** | **reader reproduces T.0's committed figure bit-exactly** | **PASS** |
| CAL-8 | system-prompt segmenter cuts at the real seam | PASS *(two contexts)* |
| CTL-1..4 | cache scanner: detects sites, detects breakpoints, no false positives, reports uncached as uncached | PASS |
| CTL-G1..G3 | gap reader: sees an over-TTL gap, does not manufacture gaps, threshold sweep moves the answer | PASS |
| — | history-prefix test | PASS *(corrupted an earlier message)* |

**CAL-7 is load-bearing.** On `panel_worker` — the one surface whose content has not drifted —
this reader returns T.0's committed figures *to the byte*: 93 tools, 46,319 bytes, 46,317 chars,
**10,264 tokens**. That licenses the central Q1 inference: **`mcp_http` and `panel` moved because
the tree moved, not because the meter moved.**

---

## Limits

- **No model in the loop, no exact tokenizer, no billed usage.** Declared proxy throughout.
- **Q4's oracle is NOT met**: no real turns exist; reconstructed from shipped code (A5).
- **A1's price multipliers were not re-verified** against current Anthropic pricing.
- **A6 and A7 were not observed live** — both load-bearing, both code-verified only.
- The TTL figure is an **op-burst proxy**, not chat turns, and is a lower bound on cold-ness.
- Grounding figures inherit every C1 limit — proxy tokenizer, one machine, one build, one day.
- **k is modelled at 1, 2 and 5**; the shipped cap is 25 and no real distribution of k exists.
- `econ_cachetrace.py` is line-oriented: docstring mentions count as sites (matched text and a
  `looks_like_prose` flag are emitted per hit), and its patterns cannot detect a provider that
  builds its endpoint from a settings-supplied `base_url` — **an untested false-negative axis**.
- **Instrument drift in C1:** its flat-control arm builds selections with `n.name()` while the
  panel uses `n.path()` (`c1_token_bench.py:349` vs `synapse_panel.py:1727`).
- **C1-F11's anchor is stale** — the block is at `system_prompt.py:255-277`, not `:224`.
