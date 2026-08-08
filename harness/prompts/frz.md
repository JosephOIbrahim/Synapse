You are ORCHESTRATOR for FRZ - attribute the UI freeze during node
operations. Read harness/AGENT_CONSTITUTION.md first; it binds you.

=== AUTHORITY - READ BEFORE ANYTHING ===
docs/MAIN_THREAD_FREEZE.md end to end. It is the settled record; do NOT
re-derive its findings: guard_mode confirmed 'warn' (08-04 diagnostic,
muted-instrument hypothesis ELIMINATED); the ~6s is NOT spent inside any
instrumented main-thread payload; 13 call sites of
marshal_guard.note_main_thread_inline_overrun have never logged a line;
the 5-6s tight band reads as a constant, not a computation; leading
candidate is Qt-side panel work (large result serialisation/rendering).
This is a task queue with deterministic answers - work it in order.

=== THE WORK ===
1. Execute the freeze doc's open queue items, in its order, evidence per
   item. Attribution first - this leg fixes nothing.
2. Instrument the Qt result path: timing + payload-size logging around
   result serialisation -> widget population, following the existing
   marshal_guard conventions (warn-mode, zero behavior change).
3. Constant hunt: search the result/render/transport path for any fixed
   5-6 second value (timeouts, waits, retries). The band tightness says
   constant; find it or rule it out with the list of candidates checked.
4. Deliver harness/notes/FRZ_REPRO.md: exact steps + one command for the
   human to run inside live Houdini that captures an attributed trace of
   the freeze. Live-panel measurement is human-at-GUI - never claim a
   reproduction you did not observe.

=== WHAT YOU MAY NOT DO ===
No fixes to the freeze itself. No changes to main_thread.run_on_main
semantics. No guard removal or quieting. Instrumentation only, reversible,
convention-matched.

=== RECEIPT harness/notes/receipts/FRZ.json ===
{ "queue_items_closed": [{"item": "", "evidence": ""}],
  "instrumented_at": ["file:line"], "constants_checked": ["file:line: value"],
  "constant_found": "file:line or NONE-of-listed",
  "repro_protocol": "harness/notes/FRZ_REPRO.md", "open": [] }
