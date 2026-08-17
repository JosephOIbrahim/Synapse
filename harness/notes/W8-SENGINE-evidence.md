# W8-SENGINE — engine scout evidence (B3-ENGINE)

Read-only recon on branch `wave8/sengine`. Every claim is first-hand from my own
read of the tree at base `327f52fd`; the multi-agent recon corroborated and its
adversarial pass CONFIRMED every finding (0 refutations). Anchors are repo-relative.

The "five backends" = `PROVIDER_IDS = ("claude","gemini","nemotron","ollama","custom")`
(`python/synapse/panel/providers/registry.py:109`). Ollama + Custom subclass
Nemotron and inherit its transport verbatim.

---

## Axis 1 — Five-backend resilience (timeout / retry / failover / error)

Per-backend, observed from the actual `stream()` HTTP call:

| Backend | HTTP timeout (wired) | Retry | Failover | In-stream error → loud? |
|---|---|---|---|---|
| claude (anthropic) | 60s — `anthropic_provider.py:28`, HTTPSConnection `:192` | none | none | YES — `error` event → RuntimeError `:379-381` |
| gemini | 60s — `gemini_provider.py:28`, `:83` | none | none | **NO** — parser `:127-172` has no error branch; `stop_reason` hardcoded `:183` |
| nemotron | 120s — `nemotron_provider.py:40`, `:291`/`:294` | none | none | **NO** — parser `:333-367` no error branch; unclosed `<think>` → warning only `:375-378` |
| ollama | 120s (inherits Nemotron `stream`) — `ollama_provider.py:56,62` | none | none | **NO** (inherited) |
| custom | 120s (inherits Nemotron `stream`) — `custom_provider.py:28,43` | none | none | **NO** (inherited) |

- **No no-timeout hang class**: every backend passes a socket timeout to its
  connection. P0-for-hang does NOT exist. (Verified; recorded as a confirmed
  non-issue, not UNKNOWN.)
- **Zero retry** on any backend — a 429 / 5xx / transport blip fails the turn on
  the first attempt; no `Retry-After` honoring. Uniform (`nemotron_provider.py:299`
  single `conn.request`; same shape in all five). **P1.**
- **No cross-backend failover** — the worker binds exactly one provider at
  construction (`claude_worker.py:136`) and never substitutes another. A provider
  `RuntimeError` unwinds to `run()` → `stream_error.emit` (`claude_worker.py:173-175`).
  This is deliberate (base.py D3, "no silent fallback"). INFO/by-design.
- **Error-surface asymmetry (P1)**: only Anthropic converts a *mid-stream* server
  error into a loud RuntimeError. Gemini + the 3 OpenAI-shape backends drop a
  mid-stream error (skipped as non-JSON `logger.debug`, or ignored) and end the
  turn as `end_turn` with partial/empty content — nothing surfaced. Breaks D3's
  loud-surface discipline for 4 of 5 backends.

## Axis 2 — Routing + offline

- **Selection is EXPLICIT, not cost/capability routing.** A turn uses the provider
  the user picked (engine pill) → `build_provider(provider_id, model)`
  (`registry.py:193`); hardcoded default `claude` (`registry.py:106`). Unknown id →
  loud fallback to the Claude floor (`registry.py:224`).
- **No automatic router is wired.** `tier_candidates_for` (FRONTIER/BALANCED/FAST
  capability classifier, hard-gates on tool-capability) exists at
  `probe.py:339` but has **zero non-test consumers** (grep). Cost is display-only:
  `probe.py:269` — "Cost never appears here. A price cannot make anything green."
  `catalog.py` = discovery cache + price display, read by `settings.py:219` and
  `face_token.py`; `probe_all` colors the author-token rail (`face_token.py:51`).
  The capability-routing infrastructure is **latent**.
- **Fully offline**: every cloud backend's connection fails → RuntimeError →
  `stream_error`; no failover, no retry. Ollama is the only local-capable backend,
  but its default row `glm-5:cloud` is a **cloud** tag metered by ollama.com
  (`registry.py:88-96`), so the default "local" pick also fails offline. A
  genuinely-local Ollama tag works only if the daemon runs and the user picked it.

## Axis 3 — NL-to-node injection defense

Path: `claude_worker.run()` → `provider.stream()` → `tool_use` blocks →
`_execute_tool_block` (`claude_worker.py:275`) → `try_mcp_tool_call`
(`tool_executor.py:666`, MCP first) or off-main `ToolExecutor._dispatch`
(`tool_executor.py:442`) → handlers → `hou` node creation.

- **Sanitize-SQ provides ZERO coverage and is mislabeled.** `sanitize_sq`
  (`harness/autorevise/quote_safe.py:29`) doubles the apostrophe for a PowerShell
  single-quoted literal — a harness shell-quoter. Whole-repo grep: every call site
  is under `harness/**` (orchestrate.ps1, quote-safe.ps1, tests); **zero** under
  `python/synapse/**`. `PROGRAM.md:23` lists "Sanitize-SQ shipped (W6)" as the
  engine's NL-to-node injection defense — a **category error**. **P1.**
- **A real allow-list gate EXISTS but is OFF on the artist path (top finding).**
  `worker_policy.is_tool_allowed_for_worker` denies review/approve/critical ops
  (execute_python/execute_vex/delete/render) and fails closed on unknown tools —
  but it is guarded by `if self._enforce_worker_policy:` (`claude_worker.py:292`),
  and the interactive panel constructs the worker with
  `enforce_worker_policy=False` (`synapse_panel.py:2289`). Default is `True`
  (`claude_worker.py:104`, autonomous/headless), but the chat path skips it. The
  panel bridge also nullifies consent (auto-approve `True`, `HumanGate _gate=None`).
  Net: on the path users actually chat through, `execute_python` etc. dispatch
  ungated. The gate that would stop injection ships built-but-off. **P1 as-shipped
  single-user; P0 for any networked/multi-user deployment.**
- **Terminus = arbitrary code, no argument sanitization.** `_handle_execute_python`
  compiles + `exec()`s the LLM `content` with `{"hou": hou, "__builtins__":
  __builtins__}` — full builtins, no import filter (`handlers.py:1262,1272`; mirror
  `api_adapter.py:367,471`). `_handle_execute_vex` lint is advisory-only, never
  blocks (`handlers.py:1385`). Undo-wrap + 30s timeout protect scene state, not the
  injection surface.
- **Other verbatim seams**: `create_node` passes the LLM `name` to
  `createNode(node_type, name)` with existence-check only — the repo `_safe_node_name`
  sanitizer is not applied (`handlers_node.py:68`). `set_parm` validates only
  NaN/Inf, then passes path/name/value verbatim. **P2.**
- The only structural control on the dispatch seam itself is the tool-NAME registry
  (unknown tool → rejected, `tool_executor.py:510`) — a name allow-list, not an
  argument check.

## Axis 4 — Key handling (location class only; values never echoed)

- claude: `hou.secure` cred store (`synapse_anthropic`; inert on H21/H22 —
  `hou.secure` absent, forward-compat only) OR `ANTHROPIC_API_KEY` env OR
  `<repo>/.env` **plaintext** (`set_anthropic_key.bat` appends it; `.env` gitignored
  — `.gitignore:90-92`). `host/auth.py`.
- gemini: `GEMINI_API_KEY` / `GOOGLE_API_KEY` env (`gemini_provider.py:44-49`).
- nemotron: `NVIDIA_API_KEY` env (`nemotron_provider.py:238`), Bearer.
- ollama: `OLLAMA_API_KEY` env or none (`ollama_provider.py:80-83`).
- custom: a user-named env var; only the NAME (`key_env`) lives in
  `panel_settings.json` (`settings.py:129`), never the value (`custom_provider.py:71`).
- **No key value is ever logged** — `host/auth.py` docstring: "No logging is emitted
  on fallback"; only the label/absence is debug-logged (`:146,:152`).
- Each key egresses only to its provider host; nemotron/ollama/custom base URLs are
  env/config-settable (`NVIDIA_BASE_URL`/`OLLAMA_HOST`/custom `base_url`), so the
  Bearer key follows the configured host with no vendor-host pin. **P2.**
