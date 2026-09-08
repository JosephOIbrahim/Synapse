# SYNAPSE Intent: Artist-Controlled Assistance

**Product direction recorded:** 8 September 2026

**Scope:** Predictive creation, Computer Use, and their combined operation within SYNAPSE.

The requirements in this document define intended behavior. They do not certify
that a capability has shipped or passed runtime qualification. Implementations
must preserve the execution rules in [CLAUDE.md](CLAUDE.md), the working rules in
[AGENTS.md](AGENTS.md), and applicable domain contracts. This document does not
silently amend those contracts or enable new permissions.

## 1. Purpose: protect the artist's attention

SYNAPSE exists to reduce the cognitive burden of working in Houdini while
preserving the artist's authorship and control. Routine construction, repetitive
adjustments, navigation, and preview management consume attention that an artist
could spend on hero assets, performance, composition, material character, and
other consequential creative decisions.

The intended benefit is more sustained attention for that work. Time saved is
valuable; the amount of supervision and correction required is equally important.
Completing more automated actions is not sufficient evidence of a better product.

The product metaphor is the simple cruise control of a **1995 Honda Accord**:
the artist chooses when to engage assistance, sets the operating scope, remains
responsible for the creative direction, and can take control back. Assistance
does not engage itself because it predicts that doing so would be useful.

**Core principle: the artist can engage help without giving up authorship.**

## 2. Two independent capabilities

**Predictive creation** anticipates useful next steps and proposes editable
networks or changes from the artist's goal, the observed scene, and applicable
constraints. It can cover a short continuation or a complete supported network.

**Computer Use** operates the permitted application interface to carry out a
task the artist has delegated. Examples include navigation, repeated control
adjustments, arranging views, and presenting results for review.

These capabilities MUST be independently selectable:

| Predictive | Computer Use | Intended behavior |
|---|---|---|
| Off | Off | The artist uses Houdini and SYNAPSE's existing explicit commands normally. Neither optional assistance capability runs automatically. |
| On | Off | SYNAPSE observes within the agreed scope and prepares suggestions. Applying a suggestion is an explicit artist command through an authorized construction route; it does not enable Computer Use. |
| Off | On | SYNAPSE carries out the artist's stated task through permitted operations. It does not start additional work based on an inferred next goal. |
| On | On | SYNAPSE may propose and execute next steps that satisfy the active delegation. A new goal or an expanded change boundary requires a new artist decision. |

Both optional capabilities MUST start disengaged in a new session. Preferences
may remember the artist's preferred mode, but a saved preference MUST NOT restore
an active delegation. Ordinary SYNAPSE functionality remains available when both
capabilities are off.

Selecting a capability does not grant unrestricted application access. Enabling
both does not expand permissions beyond the selected task.

## 3. Engagement and control contract

An engagement is a bounded agreement between the artist and SYNAPSE. One clear
interaction may select the capabilities, establish the task, and engage help.
The interface SHOULD avoid separate confirmations for each already-authorized
step. Existing operation and data-sharing permissions still apply.

Every engagement MUST record:

| Field | Required meaning |
|---|---|
| Identity | Engagement ID, project, scene/session identity, and responsible execution owner. |
| Goal | Requested outcome, creative constraints, and completion conditions. |
| Capabilities | Whether predictive assistance, Computer Use, or both are selected. |
| Change boundary | Permitted assets, nodes, parameters, files, and application surfaces; protected artist work. |
| Action scope | Permitted operation classes and the applicable existing authorization. |
| Starting state | Observed revision of affected scene state and dependencies, including unresolved facts. |
| Limits | Applicable observation, generation, repair, render, and resource budgets. |
| Handoff | Stop behavior, recovery options, and any separately authorized jobs allowed to continue independently. |

The host MUST validate this scope. A model-supplied ownership claim, scene
identity, permission, or confidence value cannot authorize an operation.

### Control lifecycle

| State | Required behavior |
|---|---|
| Disengaged | No automatic work from these capabilities. The artist retains normal explicit commands. |
| Engaged | Only the selected capabilities operate, within the current task and permissions. |
| Paused | No new steps are dispatched. The reason and any unfinished work are visible. |
| Stopping | New work is blocked; cancellation or completion of an in-flight operation is still being confirmed. |
| Completed | Required outcome checks pass, the result is available, and control has returned to the artist. An unmet or unknown required check prevents this state. |
| Failed | The task could not satisfy its completion conditions. Automated work has stopped, and partial results and recovery status are reported. |
| Unavailable | A required execution or observation capability cannot operate; the reason is reported. |

- **Engage:** requires a deliberate artist action tied to the task.
- **Take over or Stop:** immediately blocks further automated input and queued
  actions. SYNAPSE requests cancellation of interruptible work owned by the
  engagement and reports the actual remaining state.
- **Non-interruptible work:** remains visibly `Stopping` until its state is
  known. A timeout or a stop request alone is not proof that work has stopped.
- **Disable a capability:** removes it from the active scope and stops its
  pending work. Its in-flight operations follow the same cancellation and
  accounting rules as Stop. The other capability may continue only within its
  remaining, independently valid scope.
- **Resume:** requires a deliberate artist action and fresh validation of the
  affected scene. Restart, reconnection, scene replacement, and model suggestions
  MUST NOT silently resume an engagement.

**Stop and Undo are different operations.** Stopping assistance does not erase
completed work. Supported scene changes need tested undo behavior and an explicit
failure-recovery path. Undo grouping alone is not automatic rollback. External
files and submitted jobs require their own recorded cancellation or recovery
semantics.

Jobs may continue after a handoff only when the artist authorized them as
independent work. Their owner, progress, and cancellation controls MUST remain
accessible. Closing a view must not disguise an active engagement or running job.

## 4. Predictive creation from first principles

Prediction should reduce the construction work between a creative intention and
an editable result. The planner MUST distinguish observed facts, assumptions,
proposed actions, expected effects, and verified outcomes.

The intended planning sequence is:

1. **Observe the relevant scene.** Identify selected objects, existing networks,
   dependencies, artist edits, and the installed capabilities needed for the task.
2. **Express the desired outcome.** Record what should change, what should remain,
   and which choices belong to the artist.
3. **Reason from required outputs to inputs.** Select operations whose documented
   and observed behavior can satisfy those requirements. Resolve required data,
   attributes, ports, units, coordinate spaces, and dependencies.
4. **Produce a structured change proposal.** Name additions, edits, connections,
   preconditions, expected effects, and recovery actions.
5. **Validate and, when authorized, execute.** Recheck the affected state just
   before construction. Reject stale assumptions and unsupported operations.
6. **Check the result.** Read back the authored state and perform the domain's
   required output checks. Repairs remain inside the task and its limits.

Qualified recipes and building blocks can accelerate this sequence. A matching
recipe name or valid node type does not prove that the result meets the goal.
The planner must verify that each block's assumptions fit the scene.

Suggestions MUST explain their purpose at an artist-appropriate level, remain
editable, and be easy to dismiss. They MUST NOT modify the scene, launch expensive
cooks, or start renders merely to populate a suggestion. Any such work requires
an applicable task authorization and budget.

Prediction does not guarantee an image, deformation, or simulation outcome.
Structural validation, native execution results, and artist acceptance are
distinct forms of evidence and MUST be reported separately.

Preference memory, if introduced, must be inspectable and correctable. Accepting
a creative suggestion does not authorize future execution or expand data sharing.

## 5. Computer Use and execution ownership

Computer Use provides a temporary handoff of shared application controls. It
MUST operate only on the surfaces and actions permitted by the engagement and
yield when the artist takes control. Implementations must distinguish genuine
artist input from their own generated input.

SYNAPSE SHOULD choose the most dependable supported execution route for each
operation. Native Houdini construction can handle structured graph edits;
interface interaction can handle work that benefits from navigating and viewing
the application. The route used MUST be recorded. Switching routes MUST NOT
bypass an operation denial, scope boundary, or required permission.

There MUST be one owner of automated UI input at a time. Expected application
state must be checked before an action and its result observed afterward.
Unexpected focus changes, unresolved dialogs, stale targets, and ambiguous
outcomes pause the affected automation; repeated speculative clicks are not
recovery.

Computer Use must not compete with the artist for the mouse and keyboard.
Background previews or candidate preparation may continue separately only when
their ownership and resource use permit it. Work on a live scene remains
serialized through the supported host execution mechanism.

## 6. Architectural responsibilities

These responsibilities describe integration boundaries, not a requirement to
create new services, public tools, or storage systems.

| Responsibility | Contract |
|---|---|
| Artist interface | Shows capability selection, engagement scope, progress, Stop, and the next useful artist decision. |
| Scene observation | Supplies bounded, current facts with scene identity, dependency information, and explicit unknowns. |
| Predictive planner | Produces structured proposals and expected effects; grants no authority and claims no unmeasured success. |
| Engagement controller | Owns active scope, lifecycle, resource limits, input ownership, and dispatch eligibility. |
| Execution adapters | Perform authorized native or UI actions, observe results, and expose cancellation and recovery limits. |
| Outcome verification | Checks actual graph, geometry, material, render, or other domain results against the requested conditions. |
| Existing persistence owner | Retains task state, proposals, revisions, results, artist selections, and execution provenance without a competing registry. |

Panel code observes and presents state; it must not become a second construction
authority. Houdini API access stays within the host's main-thread execution
boundary. Model work, UI interaction, and native execution must not introduce
competing writers to scene or persistent state.

Each completed or interrupted operation MUST have a record connecting the
engagement and proposal to its actual changes, execution route, verification
results, and recovery status. Unsupported or unmeasured behavior remains
`UNAVAILABLE` or `UNKNOWN`, as appropriate.

Useful existing integration points include:

- [Scene grounding contract](docs/SCENE_GROUNDING_CONTRACT.md).
- [Graph proposal representation](python/synapse/cognitive/graph_proposal.py) and
  [proposal validation entry](python/synapse/cognitive/tools/propose_graph.py).
- [Solaris construction](python/synapse/server/handlers_solaris_graph.py) and
  [Copernicus handlers](python/synapse/server/handlers_cops.py).
- [Worker operation policy](python/synapse/panel/worker_policy.py).
- [Recipe contracts](python/synapse/recipes/contracts.py).

These references identify source responsibilities. They do not establish that
all current routes satisfy this intent or can be substituted for one another.
Each supported route needs its own qualification.

## 7. Artist experience and attention

The ordinary interface should answer four questions: **What help is engaged?
What is it doing? What can it change? How do I take control back?**

Suggestions SHOULD remain quiet and available without stealing focus or covering
the working view. Notifications should mark meaningful completion, failure, or a
decision that needs the artist. Progress details belong in an expandable view.

Artist edits are authoritative. Follow-up work MUST compare the current scene to
the recorded baseline and preserve changes outside the agreed boundary. An
artist's correction is not permission to replace the surrounding network.

Generated results should expose useful controls, understandable organization,
and provenance without requiring the artist to maintain an AI conversation to
keep editing them. The artist remains responsible for aesthetic selection.

## 8. Relationship to SYNAPSE's other work

| Workstream | Application of this intent |
|---|---|
| Solaris and Copernicus | Predict and construct editable material, texture, lighting, and scene changes while preserving existing artist work. This is the preferred first qualification area. |
| TOPs and rendering | Turn authorized candidates into bounded preview jobs, preserve their identities through comparison, and carry the artist's selection into a separately prepared final render. |
| APEX and creature workflows | Apply the same control model when domain authorization and capability qualification permit it; test anatomy, motion, deformation, and preservation separately. |
| Spatial worlds and splats | Ground proposed changes in the available editable and queryable scene representations; qualify spatial assumptions and provider compatibility. |

Parameter wedges and structural graph alternatives are different candidates.
Each must produce the actual scene variation it claims, with a stable identity
and verified outputs. Browsing or selecting a preview must not silently alter
the artist's working scene.

This intent does not declare a farm, universal rig authoring, or an external
world-provider integration operational. In particular, the existing
[Houdini domain boundary](docs/SYNAPSE_H22_BOUNDARY.md) remains in effect; expanding
it requires its own explicit decision and qualification.

## 9. Qualification and success criteria

Implementations MUST demonstrate the following behavior for every supported
capability combination and execution route:

| Case | Required evidence |
|---|---|
| Both capabilities off | Existing explicit workflows remain usable; no optional automatic activity begins. |
| Predictive only | Useful proposals are produced; scene changes require an explicit Apply or other authorized command. Computer Use remains inactive. |
| Computer Use only | The delegated task completes or reports its limit; no inferred follow-up task starts. |
| Combined operation | Predicted steps execute only inside the delegation; changes to goal, scope, or permission require a new decision. |
| Artist takeover or Stop | New dispatch/input ceases; in-flight work is accounted for; the system reports when control has actually returned. |
| Resume or recovery | Fresh scene validation precedes a deliberate resumption; restart/reconnect cannot silently reengage or duplicate prior work. |
| Artist edits during a task | Stale proposals are invalidated or revised, and unrelated edits remain intact. |
| Missing capability or failed action | The actual limit, partial result, and recovery options are visible; a fallback cannot bypass policy. |
| Creative comparison | Candidate identity and viewing conditions remain consistent; the chosen result can be reproduced in the final preparation. |

Behavioral tests need observed execution evidence on the supported Houdini build.
Mock or stock-Python tests can verify control logic, but cannot establish native
scene correctness, UI takeover, render quality, or practical artist benefit.

Evaluate matched artist tasks with assistance disengaged and with each relevant
mode engaged. Record:

- Time to an accepted, editable result, including inspection and repair.
- Active supervision time, interruptions, and manual corrections.
- Artist-reported cognitive workload and confidence in taking control back.
- Successful task completion and preservation of existing work.
- Measured dispatch-stop and actual-control-return latency, including failures.
- Compute and render resources consumed, alongside the creative outcome.

Include failed and abandoned attempts. Define task-specific acceptance thresholds
before qualification; publish measured results and remaining unknowns. Do not
claim a speedup or reduced cognitive load from action counts alone.

## 10. Product decision rule

Predictive creation and Computer Use advance SYNAPSE when they return useful
attention to the artist while keeping authorship, scope, and control clear.
Every feature proposal should explain which burden it removes, how the artist
engages and disengages it, what evidence proves its result, and how the artist
continues editing afterward.

**The intended outcome is an artist who can concentrate more attentively on the
work that matters, with assistance available on the artist's terms.**
