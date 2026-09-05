# AUTHORITY integration patch notes

2026-09-04. These are unapplied integration changes; the AUTHORITY write set
does not include their target files. No live panel/render qualification is claimed.

## Handler registration

In `python/synapse/server/handlers.py`, add the import:

```python
from .handlers_recipe import RecipeHandlerMixin
```

Append `RecipeHandlerMixin` to `SynapseHandler`'s base classes. In
`SynapseHandler._register_handlers`, immediately after `reg = self._registry`:

```python
reg.register("run_recipe", self._handle_run_recipe)
```

Change the existing no-argument constructor signature to accept host adapters,
and add this initialization before `_register_handlers()`:

```python
def __init__(self, *, recipe_executor=None, recipe_scope_provider=None):
    # ... existing initialization remains ...
    self.configure_recipe_authority(
        executor=recipe_executor,
        scope_provider=recipe_scope_provider,
    )
    self._register_handlers()
```

`None` adapters deliberately leave writes UNAVAILABLE. Configure once when the
server constructs the handler; do not configure on a tool call. The BLOCKS
`load_recipe_spec(recipe_id)` loader is discovered when present. An alternate
loader can be injected through the existing `SpecLoader` callable argument.

The LIFECYCLE adapter must implement exactly:

```python
def wrapped_permission(self, action: ActionSpec) -> PermissionCategory: ...
def execute(self, operation: PreparedOperation) -> dict: ...
```

`PreparedOperation` contains `request`, `spec`, `action`, `permission` and a
tuple of `TypedBinding(node_id, parm_name, value)`. Resolve node IDs only through
the owned instance. Re-read revision, conflicts and dependencies under the
host's exclusive ownership before mutation. `execute` returns the actual
receipt/outcome, including a `status`; it is not an approval callback.

## Canonical tool registry

In `python/synapse/mcp/_tool_registry.py`, add pure imports:

```python
from synapse.recipes.contracts import RUN_RECIPE_TOOL_NAME
from synapse.recipes.authority import RUN_RECIPE_INPUT_SCHEMA
```

Add this exact tuple inside `TOOL_DEFS`, before the derived tables are built:

```python
(RUN_RECIPE_TOOL_NAME, "run_recipe", _identity,
 "Propose one declared Solaris recipe action. Render requires trusted human approval.",
 RUN_RECIPE_INPUT_SCHEMA, False, False, False),
```

The final `False` avoids promising durable/cross-session idempotence through a
registry hint. The handler does deduplicate request IDs during its lifetime.
Both transports consume the registry; no parallel hand registration in
`mcp_server.py` is needed. Do not classify `run_recipe` as an inform-level generic
writer in `bridge_adapter`: only demo's explicit proposal exception permits it.

## Advertisement and captured worker profile

In `python/synapse/panel/tool_bridge.py`, extend the local import in
`get_anthropic_tools_for_worker` and add the demo branch before cache lookup:

```python
from synapse.panel.worker_policy import (
    demo_tool_definitions, is_tool_allowed_for_worker, resolve_mode,
)
mode = resolve_mode()
if mode == "demo":
    return demo_tool_definitions()
```

This exposes registered reads plus the proposal, without modifying the legacy
full-tool cache. Once the registry tuple is installed the existing filter also
recognizes the recipe tool, but the explicit provider is the tested demo offer.

In `ClaudeWorker.__init__`, capture the host profile (import `resolve_mode`):

```python
self._worker_policy_profile = "demo" if resolve_mode() == "demo" else None
```

Replace the existing final-dispatch policy call in `_execute_tool_block` with:

```python
allowed, reason = is_tool_allowed_for_worker(
    tool_name, profile=self._worker_policy_profile,
)
```

Keep `_start_worker`'s `enforce_worker_policy=True`. A later environment change
cannot override a captured demo profile: disagreements resolve to strict. The
optional `SYNAPSE_WORKER_TOOL_PROFILE` environment constraint uses the four mode
names too; unknown, empty or conflicting selections resolve to strict.

## Exact phrase and turn boundary

Before starting the demo worker or proposing any operation, the trusted panel
entry path must call `match_phrase` on the **original entire user text**:

```python
from synapse.recipes.phrases import match_phrase
from synapse.recipes.contracts import Refusal

request = match_phrase(
    original_user_text, spec, request_id=request_id,
    instance_id=instance_id, expected_revision=expected_revision,
)
if isinstance(request, Refusal):
    # Surface request.reason + request.supported_alternative; stop this turn.
    return request
payload = {
    "recipe_id": request.recipe_id,
    "action_id": request.action_id,
    "instance_id": request.instance_id,
    "slots": dict(request.slots),
    "expected_revision": request.expected_revision,
    "request_id": request.request_id,
}
```

The panel supplies the actual text, instance and revision; the model cannot
discard clauses before this gate. The integration must wire its existing
refusal display and transport to these values. Their UI APIs are not invented
here. Validated slots are a read-only mapping; the explicit conversion above is
intentional (dataclasses.asdict cannot deepcopy a mapping proxy).

At each **new trusted user turn**, create one budget and share it with the host
handler and any other writer path in that turn:

```python
from synapse.recipes.authority import MutationBudget

turn_budget = MutationBudget()
handler.begin_recipe_turn(turn_budget)
```

Never reset the budget on a tool call, transport retry or new model-generated
request ID. Recipe proposals reserve their terminal action inside the handler;
do not spend it twice in the worker. Any other mutating dispatch in that turn
must call `turn_budget.consume()` and stop on its Refusal. Read calls use
`consume(mutating=False)`. All four recipe actions seal the turn, including an
approval proposal or a failed/uncertain executor call. If worker and host are
separate processes, the integrator needs a trusted turn-ownership adapter;
model-supplied turn IDs are not authority. This lifecycle wiring is NOT_RUN.

## Approval path

`ScopeProvider(request, spec)` returns a validated `ApprovalScope` with exact
instance, revision, engine, `(width, height)`, samples and host-selected output.
The proposal response's `binding` is **unapproved scope data**. It deliberately
has no invented `approved_by`/`approved_at`. Missing provider yields
`awaiting_approval` with `binding=None` and a reason; nothing starts.

After the existing trusted confirmation/native UI approves the displayed
scope, its host callback (never the MCP payload) calls:

```python
binding = bind_approval(scope, approved_by=trusted_human_identity)
```

Inside LIFECYCLE's exclusive start window, immediately before the bounded
render starts, re-observe and call:

```python
refusal = require_approval(binding, live_scope)
if refusal is not None:
    return refusal
# Start the bounded job here, while the same scope ownership is held.
```

Import `bind_approval` and `require_approval` from `synapse.recipes.authority`.
The stricter CRITICAL category must retain its existing critical gate. Do not
approve by fabricating an `approved_by` string; a binding is not authentication.
There is deliberately no model-accessible approve/resume tool. The UI/job
adapter owns transitioning pending proposals and durable job deduplication.

## SPEC presentation adapter

AUTHORITY reads `presentation.named_colors` as a name-to-color3 table and
`presentation.demo_slots[action_id]` as typed phrase defaults. For example,
the SPEC author supplies the color constants and bounded render defaults;
AUTHORITY does not invent them. Missing defaults fail slot validation. Every
slot in the frozen seam is required because it has no optional/default field.

## Required integration qualification

Rerun T4 through the actual original-text panel entry, T5 through its live final
dispatch, and T6 through the trusted UI + bounded job start. Also test turn reset,
lost-response replay, host restart dedup and post-approval scope changes. Pure
tests here do not promote G0/G2 or qualify the pending golden scene.
