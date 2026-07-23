# spec-T — Tool Surface & Token Truth

**Track:** T · **Mode:** A · **Authored:** 2026-07-23 · **Status:** contract

The one-line thesis: **SYNAPSE optimized for surface area in the year surface
area became a tax.** The routing cascade is frugal per call. Nothing measures
what is spent *before the artist types anything*. T measures it, then collapses
it, without losing a single tool.

---

## 1 · The finding (VERIFIED-WEB, 2026-07-23)

Ecosystem convergence on progressive tool disclosure, all published between
Nov 2025 and May 2026:

| Source | Claim |
|---|---|
| Anthropic, Tool Search Tool | ~85% token reduction; GA February 2026 |
| Anthropic, code execution with MCP | 150,000 → 2,000 tokens on one reference task |
| Cloudflare, Code Mode (2026-02-20) | 2,500+ endpoints behind 2 tools, ~1,000 tokens |
| Speakeasy | search/describe/execute; up to 160x reduction |
| Field measurement | flat catalogs consume up to 72% of context before work; tool-selection accuracy drops ~3x under bloat |
| Claude Code v2.1.7+ | auto-triggers MCP Tool Search past 10% of context |

SYNAPSE ships 115 registry tools across three surfaces. The competitive field
ships more (`fxhoudinimcp` 179). **Tool count is now an anti-signal.**

**UNVERIFIED until T.0:** SYNAPSE's own preload cost. Every number above is
someone else's measurement. The frugality claim in `pyproject.toml` is
architecturally reasoned and numerically unproven. T.0 exists to make it a fact
or kill it.

---

## 2 · Task contracts

### T.0 — token baseline probe (read-only, arming)

Serialize tool definitions exactly as each surface puts them on the wire and
count them. Three surfaces: `mcp_server.py` (stdio), `python/synapse/mcp/`
(Streamable HTTP), panel path.

Deposit: `harness/notes/token_baseline.json`, schema `token_baseline/v1`,
blake2b over the `stats` block, digest of `_tool_registry.py` source.
Shape copied verbatim from `knowledge_baseline.json` (K.0).

**T.0 does not gate on the number.** Same posture as `check_rewire_assessed`:
the check confirms the artifact exists and is sound, and surfaces
`preload_tokens_total`. The number is a finding, not a verdict.

**T.0's number re-ranks T.1–T.3.** Precedent: C.0's catalog re-ranks C.1–C.6;
the 1.4 probe re-ranks V.5–V.7. If preload is small, T.1 demotes and that is
the probe working, not failing.

### T.1 — deferred tool surface

Three tools in context: `tool_search`, `tool_describe`, `tool_execute`. The
115-entry registry moves off-context behind a lookup. **No rewrite of
`_tool_registry.py`** — a search layer in front of it.

Two gates, and the second one is the important one:

- `tool_surface_deferred` — preloaded definition budget ≤ the committed floor
  in `harness/verify/token_ceiling.json`. That file is peer to
  `suite_baseline.json` and lives in the agent deny-list: a sprint may not
  raise its own ceiling.
- `tool_surface_parity` — **every tool reachable through the flat registry
  remains reachable through search→execute.** Reach count strictly increases
  or holds. This is Commandment 7 in a different coat. Token reduction that
  loses a tool is a regression that happens to look like a win, and it is the
  single most likely way this track fails quietly.

### T.2 — code mode

Agent writes code against a typed in-process API instead of calling N tools.

**RULED 2026-07-23 (CTO ruling, human-sanctioned): SHARED DISPATCH PATH.**
Code-mode execution traverses the same undo group, consent gate, ledger write
and RBAC boundary as tool dispatch. No parallel path. Rationale, on the gate-0.1
pattern: the shared path costs milliseconds against a ~2s Houdini cook floor, so
cost does not discriminate the arms; a parallel path degenerates into
`execute_python` with better ergonomics, splits the safety story, and forfeits
the one property a bridged competitor cannot replicate. There is no arm where
the second path is correct.

Per the R.4 precedent — a gate that has been ruled and committed is no longer a
gate. `run.ts` does not decide architecture; it executes a ruling that predates
the run. **T.2 is loop-executable.** The property, not the mechanism, is gated:
`code_mode_undo_wrapped`.

### T.3 — agent outcome evals

4,275 green tests prove the *code* works. Nothing proves the *agent* produces
correct Houdini outcomes. Orthogonal axes; only one is covered.

`cognitive/graph_validator.py` already scores proposed node-graphs against
probe-verified truth. T.3 promotes it: freeze a scored eval set, commit a
pass-floor, ratchet it. Extends S.5's `eval_backbone` rather than duplicating it.

### T.4 — panel (deferred out of track)

**RULED 2026-07-23: FREEZE, DO NOT DECIDE.** `panel/` (23,365 lines, 71 files —
the largest first-party package, larger than `server/`) takes no new feature
surface during T. Bugfix only.

Product-vs-reference is *not* ruled, deliberately: T.1 and T.2 change what the
panel is. When the tool surface collapses to three verbs and code mode lands,
the panel stops being a tool launcher and becomes a review-and-consent surface.
Ruling now would rule on a shape that is about to change. Re-enters as a
bounded-decision task blocked on `T.1 + T.2` merged to main.

---

## 3 · Acceptance

The track is done when all four hold simultaneously:

1. `token_baseline.json` exists, sound, and its number is quotable in public.
2. Preload ≤ ceiling, **and** parity reach has not dropped.
3. A code-mode mutation appears in `agent.usd` and reverts clean.
4. Full `pytest tests/` has not regressed against `suite_baseline.json`.

---

## 4 · Anti-runaway anchors

- **Parity before economy.** `tool_surface_parity` joins the standing
  guardrails **only after T.1 lands and the check itself exists and can return
  `ok:null`.** Do NOT add it to `tasks.json` guardrails early: `run_one()`
  returns `{"ok": False, "detail": "no check implemented - ADAPT"}` for any name
  absent from `DISPATCH`, and a guardrail with `ok:false` short-circuits EVERY
  sprint in the repo before the Evaluator. The `ok:null` -> WARN path is for a
  check that exists and detects "not wired yet" — it is not free for an
  unimplemented verb. Sequence: T.1 authors `check_tool_surface_parity` with an
  explicit `ok:null` branch for the pre-deferred surface, T.1 banks, THEN the
  guardrail list grows.
- **The ceiling is not self-writable.** `token_ceiling.json` goes in the
  `agent-settings.json` deny-list beside `suite_baseline.json`.
- **Checks are loop-authored, contract is not.** `harness/verify/**` is
  allow-listed (S.5 precedent). This spec is the contract; the sprint writes
  the check functions and registers them in `DISPATCH`. An honest first-round
  FAIL of `no check implemented — ADAPT` is expected, not a bug (V.5 precedent).
- **Merge to main stays human.** Unchanged. The only stop left in the track.

## 5 · Non-goals

- No new transport. T rides the existing dispatch spine.
- No touching the routing cascade. Its value under 2026 inference economics is
  a live question and an explicitly separate one; measuring it is not T's job.
- No rigging, no APEX corpus, no ledger bypass, no phantom `hou.*`. The five
  standing guardrails apply every sprint, as always.

## 6 · Deposit

`harness/notes/token_baseline.json` — the number. It is the artifact that turns
*"115 tools"* into a sentence worth saying out loud.
