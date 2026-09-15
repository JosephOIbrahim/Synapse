# Model routing — milestone 4

Connect a model now offers **Chosen model** and **Prefer a checked local model**,
with a task need for conversation, Houdini tools or images. Automatic choice uses
fresh model-reported capabilities and also checks the actual tools and images in
each request. It explains the choice and keeps that model for the whole task.
Unknown abilities cannot qualify for automatic selection.

**Project rules** selects a local project file and offers Ask or Local only.
Temporary panel consent belongs to one task. Saved background permissions name
one exact service, model and endpoint, with an explicit sharing disclosure. Keys
are never written to the rules file. The path is selectable and wraps without
losing characters; the controls remain reachable in narrow and scaled windows.

SYNAPSE's panel, router, daemon, agent loop, CLI agent and planner check the same
rules immediately before their model requests. Changing project, revoking
permission or stopping a task prevents later sends. Queued work retains its
original project. Saving old cosmetic preferences cannot restore an old project
or its permission. Corrupt rules and ambiguous selectors refuse dispatch.

Local approval requires fresh positive weight metadata from a loopback Ollama
model. A local address alone is insufficient: relay/cloud tags stay remote or
unverified. Setup sends metadata requests only. Local provenance is checked again
before payload transmission; automatic follow-ups must still cover the tools and
images they actually contain. Owned model transports do not follow redirects,
use environment proxy clients or silently retry failed requests.

The token view separates the requested model from the service's reported model.
Reported usage is retained on failed/incomplete streams; missing counts stay
unknown. Process-local request receipts contain identity, destination, permission
result and usage, without prompt, image, tool content or keys.

## Qualification and use

The isolated `ux/routing-20260906` branch contains the cumulative first-session,
network, recipe and routing work. It has not replaced the artist's installation.
Exact source hashes, commands, counts and original failed probes are recorded in
`checks/routing/qualification.json` in the SYNAPSE_Refactor workspace and copied
to the local `harness/routing-20260906` evidence board after qualification.

The independent transport and scope reviews cover two installed SDK generations:
CPython 3.14.2 / Anthropic 1.4.0 / httpx2 2.12.0, and CPython 3.13.10 / Anthropic
0.96.0 / httpx 0.28.1. They exercise actual SDK parsing with fake transports and
synthetic credentials. Deliberately disabling permission, scope or capability
checks makes the regressions fail. Native Qt tests exercise the dialogs, exact
path copy/wrapping and control reachability at two text scales.

The full panel trial in Houdini 22.0.400 uses disposable preferences, project rules,
memory and an empty scene. A real `qwen3.5:4b` loopback conversation under Local
only returned LOCAL COFFEE without tools or scene changes. Its 24,586 input and
88 output tokens matched the request receipt and the panel; requested and reported
model IDs were both visible. Task scope, permission and session key were released
after completion. This qualifies the measured conversation, not model quality.

The first sandboxed host could not read Houdini's external `orjson` installation;
both M3 and M4 reproduced that environment failure. A fresh authorized host outside
the sandbox loaded the existing library and completed the same bridge protocol.
No product JSON fallback or installed dependency was modified. The first live
probe also referenced a nonexistent test-only settings attribute; the corrected
probe reads the actual settings API. Both original failures remain recorded.

## Limits

- Service-reported weights and capabilities do not prove the service's actual
  implementation, model quality, memory capacity, speed or privacy behavior.
- SYNAPSE rules control its own requests. External MCP clients use their own
  model permissions; this is not a workstation firewall. Recalled memory, tool
  results and images can leave through an explicitly permitted model request.
- In-process daemon children inherit cancellation. Exported CLI scopes are only
  project-origin snapshots: cancellation already present is retained; a later
  parent stop uses the existing team process-termination mechanism. Live tmux
  termination was not tested. Already transmitted requests may finish.
- The wider suite retains the ten prior failure names, including one incomplete
  baseline comparison. Production scenes, real cloud credentials/requests,
  sustained use and every native DPI configuration remain unqualified.
- A native UI run had one unreproduced settings-save refusal before its dialog
  assertion. The focused repeat and final full UI run passed; raw evidence is
  retained. A contended or inaccessible settings file refuses rather than
  changing project authority.

Next: observe real render/cache/simulation and connection events, then refine
the panel through actual use. Joe authorized continuing after each milestone.
