# Networks that stay readable

Milestone 2 of the UX roadmap approved by Joe, resumed with "go ahead with
tasks that are waiting" on 2026-09-06. Build and test locally in the isolated
`ux/networks-20260906` worktree. The original Houdini scene stays intact.

## Outcome

A repeated build preserves an already arranged network. New graphs use a
deterministic vertical layout; the artist can request horizontal layout and
explicitly reorganize the reused nodes named in that graph. Wiring reports
describe actual input and output ports. Invalid or conflicting specifications
are rejected before they can quietly replace a requested wire.

## Chosen approach and alternatives

Extend the existing graph/chain handlers and shared layout helpers. This keeps
one construction path and the existing tool names. A separate layout subsystem
would duplicate graph ownership; a prompt-only change would leave the concrete
repeat-build defects in place. The prompt will direct the model to these tools
and stop recommending parent-wide layout calls.

## Implementation contract

- `handler_helpers.py`: accept vertical/horizontal orientation in shared layout
  helpers, keep existing defaults, and make section safety follow the flow axis.
  Match a section namespace exactly, including only numeric auto-suffixes.
- `solaris_graph_plan.py`: resolve actual node paths before deduplication; reserve
  explicit destination ports before implicit appends. Preview and execution use
  this same live plan. Preserve a protected node's occupied source and output.
  Readback failure cannot claim verification. Ground display flags on live LOP
  instances and distinguish requested display/layout from observed/applied state.
- `handlers_solaris_graph.py`: validate node specifications, nonnegative integer
  ports, repeated node names and duplicate destination slots before mutation.
  Compare the full source-node/output-port connection when reusing or appending.
  Read back requested connections and parameter failures. Preserve reused node
  positions by default; `relayout: true` explicitly includes them. Artist-owned
  `existing` references remain fixed. Report moved nodes and actual display state.
- `handlers_solaris_assemble.py`: accept the same orientation, keep its anchor
  fixed, reject duplicate target paths/self-anchors, and report the chosen layout.
- `_tool_registry.py`: expose orientation and relayout plus existing-node
  references; mirror runtime port validation without removing any registered tool.
- `panel/system_prompt.py`: prefer the shared builder and preserve artist layout.
- Catalogs: refresh the connectivity and LOP catalogs from 22.0.400, preserving
  the previous build's historical artifacts.
  Connectivity instances use exact type names and record the measured ordered
  input boundary. Some unordered LOPs have a dedicated input; its empty slot is
  valid, while gaps among the unordered ports would be compacted by Houdini.

## Checks and completion

Entry gates: connectivity and LOP catalogs are current, and phantom check uses
the 22.0.400 symbol table. The initial catalogs failed freshness; both were
regenerated on the installed build. The unchanged focused baseline has 219 passes.

Regressions must fail before the fix. Check build A → build B → rebuild A,
vertical → horizontal → repeat, merge input order, exact output ports, duplicate
slots, invalid parameters, similarly prefixed section names, existing references,
and assembly duplicates. Run the required independent composition review,
targeted checks, live probe battery, and full suite; report every failure and
baseline limitation. Qualify the visible result in a disposable Houdini session.

Finish when the scoped changes are reviewed, their results and limitations are
recorded, the local checkpoint and dashboard are updated, and Joe has a network
example to try. Stop for use feedback before recipes. This is not permission to
merge, publish, change VERSION, deploy over the original session, or install a
substrate. Rendering, USD memory semantics, recipes, routing, notifications, and
the rest of the panel refinement remain later milestones.

Test contract correction: build A → B → rebuild A preserves positions but changes
the display from B to A, so that call reports `updated`; one further A rebuild must
report `unchanged`. The old prompt assertion requiring parent-wide layout is
replaced with preservation/scoped-layout assertions because it contradicted this
milestone's accepted behavior. These corrections preserve stronger scene checks.
The full suite also exposed three test pins still naming 22.0.368. They now
name the independently probed 22.0.400 artifact and version; byte equality and
checksum recomputation remain required. The prior artifact is preserved.
