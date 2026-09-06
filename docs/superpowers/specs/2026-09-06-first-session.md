# First session: connect, understand, and control

Status: implementation design for the roadmap approved by Joe on 2026-09-06.
Base: b1ec9a8d58836ebf401ad66f520e1d3cd15d9116, Houdini 22.0.400.

## Outcome

A new artist can connect an available model from the panel, identify the actual
model and execution location, understand what remote use shares, read formatted
responses and truthful activity, and discover commands without knowing `/`.
Preserve the existing palette and panel design. Implement and verify in an
isolated worktree. Do not replace the artist's running Houdini installation.

## Product contract

1. A visible Connect models entry opens guided setup for the supported engines.
   Installed Ollama models are discovered with bounded metadata-only requests
   off the UI thread. Cloud services accept a masked credential directly;
   environment-variable configuration remains an advanced/legacy option.
   A failed test never replaces a working selection or reports Connected.
2. Credentials entered here stay in process for this panel session unless an
   existing approved secure credential store is used. Never write plaintext keys
   to settings, history, tests, logs, reports, URLs, or model payloads. State the
   session-only lifetime in the UI so restart behavior is understandable.
   Cancelled entries are discarded; panel close clears panel-held keys. An
   already running worker may finish with its captured key, then releases it.
   A reopened panel does not inherit session keys. No memory-zeroization claim.
3. Actual provider, complete model identity, endpoint location evidence, and
   reported token totals remain inspectable. A model selected during an active
   task applies next; the in-flight task and its answer retain the original
   identity. An unknown provider or construction error cannot fall back to a
   different cloud engine on the panel path.
4. A local endpoint is not proof of local inference. Ollama model metadata can
   identify a cloud relay; custom loopback endpoints remain unverified without
   affirmative deployment evidence. Unavailable/stale evidence is labeled
   unverified. Never label unknown location Local or unknown usage zero.
5. Before a panel turn sends project context to a remote or unverified model,
   the artist receives a concise disclosure of destination and data classes:
   prompt, conversation, scene context, tool/memory results, and any images
   supplied by tools. Approval is
   scoped to the exact provider/model/endpoint and current panel task. Declining
   preserves the draft and does not start the worker. The check is outside model
   instructions; the model cannot approve its own outbound request. No durable
   universal `local-only` assurance is advertised: independently configured MCP
   clients and host background lanes remain explicitly outside this panel-turn
   permission. Comprehensive project-wide egress control stays a tracked item.
   Freeze the transport endpoint and credential with the requested model for
   every continuation; environment changes cannot redirect an approved task.
   Provider-reported identity is distinct from the requested model identifier.
6. A supported message subset renders headings, emphasis, lists, fenced code,
   inline code, and safe links as readable Qt-compatible HTML. Preserve existing
   node links and trusted tool-produced HTML. Treat model prose as text, escape
   HTML, reject active/unsafe link schemes, and preserve code literally. Retain
   existing speaker colors, asynchronous formatting, and stream behavior.
7. Activity describes actual stages (connecting, waiting for response, running a
   tool, checking a result), distinct from final answers. Provider-internal
   reasoning is not fabricated or exposed by bypassing existing filters.
8. A visible Commands button and `/` on an empty input open the same palette.
   Opening/dismissing the palette preserves drafts. Selecting an entry remains
   on the established dispatch path; unknown commands are not invented.

## Architecture and file ownership

- `panel/connections.py` (new, no Qt/hou): immutable connection facts, endpoint
  classification, safe metadata discovery, in-memory credentials, friendly test
  outcomes. Reuse provider definitions and transport conventions.
- `panel/connection_dialog.py` (new): guided selection, masked key entry,
  asynchronous discovery/test, exact selection payload. Never import hou.
- `panel/synapse_panel.py`: wire Connect models/Commands, task-bound identity,
  local/remote disclosure before a task, safe worker construction, and readable
  status. Keep all existing source architecture and layout tokens.
- `panel/claude_worker.py`: retain immutable per-task model identity and existing
  usage accounting; no silent fallback introduced. UI authorization is explicit
  and is not inferred from model output.
- `panel/message_formatter.py` and `panel/face_work.py`: formatting and actual
  activity labels. Rich text compatibility remains Qt-tested.
- `panel/face_token.py`, `panel/providers/model_facts.py`, and egress documentation:
  remove tag-only Local/$0 claims and use the same bounded location evidence.
  Metadata checks prove reachability and a listed model, not successful generation.
  Obsolete asynchronous results cannot select a model. Evidence expires after
  three minutes; missing metadata and custom loopback inference remain unverified.
- Focused tests cover renderer inputs, privacy/location classification,
  connection failures, asynchronous UI flow, decline-without-send, provider
  changes during a turn, token attribution, and palette draft preservation.

## Validation

First run existing model/settings/formatter/usage tests in an isolated temporary
directory to establish baseline. Add meaningful regression cases and demonstrate
they fail on the old behavior. Run the affected suite and the repository's
required broader suite, reporting environmental exclusions and inherited failures
separately. Use an offscreen Qt harness if available; never treat skipped GUI
tests as visual verification. Independent review checks the complete diff.

Live qualification is a separate, final step: load the reviewed code into a
disposable panel/session or deploy with the artist's specific authorization.
Do not reload or mutate the current live scene as part of isolated development.

## Remaining roadmap (preserved scope)

After this first-session delivery and use review: consistent Solaris builders and
vertical/horizontal layout; saved network recipes with tags, dependencies and
shot recovery; project-wide sharing enforcement including external-client
boundaries; capability/resource-aware model routing; job notifications; complete
panel refinement. Existing infrastructure is reused and qualified, not assumed
live merely because a module exists.

## Success evidence and limits

The implementation receipt names exact files, test commands/results, reviewer
findings resolved, and remaining live checks. No measured latency, cloud locality,
universal privacy guarantee, or production readiness is inferred from a mock,
configuration label, code comment, or successful localhost ping.
