# Inspection child-category observation

Isolated release candidate. Current source-test and native qualification status
is recorded with the combined release evidence; this document is not a release
approval or a claim of model benefit.

Existing `category` remains the inspected node type's own category. The additive
`child_category` object reports `node.childTypeCategory()` independently in
selection rows and basic node metadata used by detail/input-graph inspection.
It contains exactly `status`, `name`, and `reason`:

- `available`: a nonblank runtime category name; `reason` is null.
- `none`: the API returned None; `name` is null and the reason says so.
- `unavailable`: missing/failing API or invalid name; `name` is null and a
  constant reason reports the observation failure. No exception text leaks.

A category fact does not prove a particular node type exists, grant mutation
permission, or guarantee an editable parent. There is no path/type inference,
automatic reparenting, node creation, geometry/stage read, or cook.
Callers retain the existing main-thread dispatch requirement.

The topology hash and pin eligibility retain their existing projection; this
advisory observation is not a creation capability or topology precondition.
Existing keys keep their meanings. Consumers rejecting unknown response fields
need separate compatibility qualification.

The preserved terminal-panel v002 trace shows the gap: inspection of a geometry
container reported its own Object category; the next request chose a different
parent. Later exact SOP facts did not prevent more wrong-parent attempts. This
supports making the categories explicit, but does not establish the observation
as the cause of failure or prove that the change improves model behavior.
No benchmark-specific node recipe or prompt is added.

Tests: `test_inspection_child_category.py`, the topology stability control in
`test_selection_snapshot.py`, and the exact additive dictionary in
`test_introspection.py`. The dedicated tests also cover eight unavailable/none
to available read transitions without rewriting an earlier view, and four
existing pin/wire consumer controls. These use fake nodes and do not qualify
Houdini recovery.

Historical H22.0.400 evidence for the same two product file hashes covered eight
read cases and sixteen old-field comparisons. It did not exercise this assembled
release, geometry, graphical Undo, native error recovery, or model behavior.
Those claims remain separate gates. See
[the combined release plan](moneta-rust-rc1-release-candidate.md).
