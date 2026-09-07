# Model routing — milestone 4

Joe approved continuing the ordered UX roadmap. This milestone makes model choice
fit production sharing constraints and extends enforcement to SYNAPSE-owned model
requests outside the panel. It preserves the exact active model and real usage.
No production policy or cloud credentials are changed during implementation.

## Chosen approach

A shared request policy and explicit, measured candidate selection. UI-only labels
leave background egress uncovered; an autonomous benchmark/ranking system adds
model spend and opaque quality claims. This milestone uses the existing connection
checks, exact user preferences and reported capabilities. It never equates model
file size or metadata latency with quality, performance or GPU suitability.

## Production rules

One pure `synapse.model_access` owner reads local JSON policy. Missing policy means
ask before remote work; unreadable or malformed policy refuses model dispatch.
Modes are **Local only** and **Ask before remote tasks**. Exact provider, endpoint
and requested model identities define a saved background permission. A panel
permission is task-bound and is not silently a background permission. Tightening
the rules, changing policy scope or releasing a task invalidates its permission.
Capture canonical policy path, policy revision and scope-selection generation
when a task is accepted or queued, not only at eventual dispatch. Carry that
binding through daemon queues, router asynchronous work and tool follow-ups.
An A → B → A project switch must not revive an older permission. A mismatch is
terminal for that task; it cannot borrow the new project's saved grants.

Project rules is reachable from Connect a model. It shows the current policy
location and can choose a project folder for `.synapse/model_access.json`; the
default is explicitly labeled as this SYNAPSE installation. A deployment override
can select the policy file. A saved background permission requires an explicit
control explaining that prompts, scene/memory/tool content and images can leave
this workstation. Keys never enter the policy. Loading a project policy cannot
silently turn an unreadable file into permission.

Enforce immediately before provider transport and before each direct SDK request,
including retries. Freeze each task's actual endpoint and credentials; reject
unknown providers without a Claude fallback. SDK clients capture the effective
base URL and disable redirects. Non-panel background calls without matching local
policy permission return a clear unavailable/blocked result before transmission.
SYNAPSE cannot govern an independent external MCP client's own model connection;
the UI states that boundary.

Ollama locality requires a loopback endpoint and fresh positive weight metadata.
Cloud tags and remote metadata remain remote even on localhost. Recheck local
evidence on the worker thread before payload transmission; stale or changed
identity cannot inherit a local permission. Catalog discovery must apply the same
locality rule and cannot reuse a different endpoint's cache as a current result.

## Choice and visibility

Keep **Chosen model** as the default. Add **Prefer a checked local model** and a
task need: conversation, Houdini tools, or images. Automatic choice uses fresh,
endpoint-bound checks that report the required capability. Unknown capability
does not qualify for automatic choice. The artist's selected model breaks ties;
remaining ties are deterministic. A suitable remote candidate still follows the
sharing rule. No candidate means a helpful connection-check action, not a fallback
to an unverified model. Selection changes take effect on the next task.
The effective capability requirement is the union of the selected need and the
actual request: advertised tools require `tools`; image content anywhere in
history or tool results requires `vision`. A conversation label cannot bypass
these requirements while the payload still contains tools. Recheck the union
before every follow-up; newly required but unreported capabilities stop the task
with an actionable explanation, without switching models mid-task.

Ollama's metadata-only `/api/show` augments a successful list check with reported
capabilities and context information. Failure retains a truthful partial check.
The UI labels listed/untested state and unknown capability. No benchmark or scene
is sent during setup. A route explanation names the selected identity, service,
location and reason. Returned model IDs are recorded separately from requested
IDs; aliases are never falsely presented as verified actual execution identity.
Usage remains API-reported; absent token counts stay unknown.

## Files and implementation order

1. `model_access.py`: policy parsing, exact grants, request checks and SDK helper;
   `tests/test_model_access.py`: deny, grant, revoke, malformed, scope and retry tests.
2. `panel/connections.py`, provider adapters/registry and existing catalog/probe:
   bind checked facts and guard transport; metadata and returned model identity.
3. Direct SDK/HTTP producers identified by `checks/routing/dispatch-map.md`:
   shared checks at every owned dispatch, preserving honest error results.
4. `panel/model_routing.py`, settings, connection/project dialogs and panel:
   candidate selection, visible reason and project rules; existing shared QSS owns
   styling. No new memory store or Houdini worker-thread access.
5. Usage/readout additions, focused and composed tests, independent review,
   isolated Qt/Houdini trial, checkpoint and dashboard report.

## Acceptance and falsification

An instrumented transport must observe zero payload requests for unapproved cloud,
local-only remote/relay, malformed policy, endpoint/model substitution, revoked
grant, stale local metadata and hidden fallback. Test a two-call tool sequence,
policy tightening between calls, background router escalation, and endpoint changes
after selection. Mutating the boundary check must make these tests fail.
Include queued project A content dispatched after switching to B, then back to A;
neither B's saved grants nor reselecting A may revive the original task.

Eligible local selection, explicitly permitted remote tasks and saved background
permissions must actually reach a controlled local fixture, with exact request and
reported model IDs plus real fixture token receipts. GUI checks preserve drafts
on refusal, show the routing reason and obey narrow/scaled layouts. Use a real
local model only in the isolated Houdini test with synthetic content. No private
production/cloud request is needed for qualification. Preserve existing broader
test failures separately; no green claim for unrun production cases.

Limits: endpoint-reported locality and capabilities are evidence from that service,
not proof of its implementation. Model quality, hardware throughput, full network
isolation and external clients' behavior are not established by this milestone.

## Review corrections

Only local UI/owner code can issue an in-memory task grant; model/tool JSON cannot
grant access. Bind it to one task, exact connection and captured scope. Stop,
close/destruction, completion and startup failure revoke it immediately for future
attempts. Keep credentials alive until the worker finishes an already-sent request.
An environment policy override takes precedence over the project selector and the
installation default. A corrupt selector refuses dispatch; it cannot fall back to
a more permissive installation policy. Every explicit project switch writes a new
selection generation, including switching back to a previously used project.

Use a plain `httpx.Client(trust_env=False, follow_redirects=False)` with a guarded
request hook and `max_retries=0` on the SDK. Do not use Anthropic's default HTTPX
subclass, which can construct environment proxy mounts. Supplied SDK clients must
meet the same controlled transport contract or be refused. Capture and validate
the actual URL/model at the physical send, and reject remote HTTP credentials.
Tests include proxy recorder, 307/308, 5xx without a hidden second send, endpoint
mutation and supplied-client refusal. Record the actual tested SDK version.

Reported vision capability takes precedence over `vision_attach`'s historical
model-name hints. Automatic routing cannot use hints as evidence. Preserve images
in the adapter's actual payload when supported; otherwise refuse visibly instead
of claiming the model saw them. A history/tool-result image is part of the effective
capability union on every request.

API grounding: Ollama's metadata-only `/api/show` and its `capabilities` and
`model_info` fields were checked in the official documentation on 2026-09-06:
https://docs.ollama.com/api-reference/show-model-details . Runtime checks remain
the evidence for a particular installed model.
