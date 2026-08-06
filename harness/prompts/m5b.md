You are ORCHESTRATOR for M5b — closing the four M5 rulings. Read harness/AGENT_CONSTITUTION.md first; it binds you. Then read harness/notes/receipts/M5.json in full — especially findings[] and for_ruling[] — and the resume_token at its end.

**WRITES CODE.** M5 shipped green and is committed at 87927076 on blocks/m5-reconciler. This leg closes the four escalations.

=== FIRST ACTION — VERIFY YOUR BASE ===

This leg was dispatched once on the WRONG base (2026-08-06, orchestrator manifest base feat/repair-heats-01) and was stopped by hand. The worktree branch blocks/m5b-rulings has since been reset onto 87927076. The orchestrator uses one manifest-level base and does NOT honour a per-leg base field, so verify before anything else:

    git log --oneline -1
    git merge-base --is-ancestor 87927076 HEAD ; echo $?

If 87927076 is NOT an ancestor of HEAD, or python/synapse/blocks/runtime.py does not exist, STOP. Do not write a line and do not attempt a fix — report it in the receipt under drift[] and halt. A "clean" run on that base would silently reimplement M5 from scratch, which is worse than no run at all.

=== HONOUR THE RESUME TOKEN ===

Do NOT re-probe: NetworkBox surface, display exclusivity, undo-in-hython, parm read-back, node type versioning, box USD-neutrality. All six are VERIFIED-RUNTIME on 22.0.368 in harness/notes/_m5_*.py. Do NOT re-derive the $HIP dependence (M5-F1). Do NOT re-run the merge-base suite baseline — the 9 pre-existing failures are enumerated in the receipt with their producer.

=== THE RULINGS (Joe, 2026-08-06 — closed, not open) ===

**R-M5-1 -> c3 canonicalizer.** Strip $HIP-derived output paths from the canonical text. Rationale, so you extend it correctly rather than literally: $HIP is ENVIRONMENT, not scene content — the same category as the session node IDs c2 strips and the anon: handles c1 stripped. This is the third instance of that class. Write the rule to that principle, not to the single karmarendersettings symptom: any authored path that resolves through a Houdini environment variable ($HIP, $HIPNAME, $JOB, $OS, $TEMP) is session-local, and a stage differing ONLY in such a path is the same stage.

  - CANONICALIZER_VERSION becomes "c3". Extend _C1_RULES with the new rule name.
  - synapse.blocks.canonical stays the single source; autoresearch imports it.
  - RE-BASELINE fixtures/solaris.basic.json: cut the new sha256 under c3 via
    the invariant harness, update baseline.sha256 + baseline.canonicalizer,
    and record the prior 8bb05761/c2 pair in a superseded_baselines[] entry
    with the reason. Do not silently overwrite history.
  - PROVE the fix: the c3 hash must be IDENTICAL when the fixture is built
    from the main working tree AND from this worktree (different $HIP). That
    cross-cwd equality is a new invariant — see F-6 below. If it does not
    hold, the rule is wrong; report rather than widen the filter until green.

**R-M5-2 -> keep exactly what shipped.** Honour the fixture's declared display node, report the transfer by name, F-4 / F-4b stay split. No code change. Ratify it: add a comment at the display branch in runtime.py naming R-M5-2 and why never-take and only-on-first-create were rejected (both leave the declared display permanently unsatisfiable when an outsider holds the flag — residual_ops=1 forever, idempotence broken).

**R-M5-3 -> OVERRIDE what shipped. Eject, do not delete.** A node the artist dragged INTO the box that the fixture does not declare must be REMOVED FROM THE BOX and LEFT ALIVE in /stage. Rationale: box membership was established by the artist's drag, not by the fixture's declaration — the reconciler must not destroy what it never created. The asymmetry decides it: a wrong delete is recoverable only by Ctrl+Z, a wrong eject by one drag.

  - remove_fixture is UNCHANGED — it still deletes members. That is an
    explicit "remove this fixture" instruction and is a different act.
  - Report ejections in result['ejected'] with per_node reason
    'not declared by the fixture - ejected, not deleted'.
  - The verdict line must account for ejections when any occurred.
  - Replace tests/test_blocks_reconciler.py::test_stray_inside_the_box_is_deleted
    with a test asserting the stray SURVIVES and is no longer a member. This is
    a ruled behaviour change, not a weakened test — Law 6 still applies: the
    total test count must strictly increase across this leg.

**R-M5-4 -> regenerate the h22 symbol table for 22.0.368, and gate it at load.** Regenerate python/synapse/cognitive/tools/data/h22_symbol_table.json by introspection on the installed 22.0.368 host. Add a load-time build check in the consumer: if the table's houdini_version does not match the running build, WARN with both versions rather than silently trusting it. A phantom-API gate whose authority is a different point release can pass a symbol that does not exist on this machine.

  - If regeneration is not possible in this environment, ship the load-time
    check alone and report exactly why in the receipt. Do not fabricate a table.

=== CRUCIBLE INVARIANTS ===

Re-run the full M5 set, unchanged in intent, against the NEW c3 baseline:

  C-1..C-5  the five negative controls FIRST (Law 1 — an instrument that has
            not been shown to disagree is not evidence)
  F-1       apply on clean -> new c3 baseline, byte-exact
  F-2       apply -> remove -> apply -> same hash
  F-3       apply on applied -> ops == 0, hash unchanged
  F-4       artist node outside box keeps every AUTHORED property
  F-4b      display transfer reported by name, not silent

Plus two NEW invariants this leg must add:

  F-6  CROSS-CWD EQUALITY. Build the fixture with two different $HIP values
       (main working tree and this worktree) and assert an IDENTICAL c3 hash.
       This is the invariant that proves R-M5-1 actually closed. Pair it with
       a negative control (C-6) showing the comparison CAN fail — e.g. the
       same two builds under c2 must differ, which is exactly M5-F1.

  F-7  EJECTION SAFETY. Artist node dragged into the box, not declared by the
       fixture. After apply: the node is ALIVE in /stage, every authored
       property unchanged, no longer a box member, and reported in
       result['ejected']. Pair with a control proving the assertion can fail.

Commandment 7 stands: a failing invariant is fixed in the implementation,
never weakened in the test.

=== SEAM DRIFTS — RECORD, DO NOT FIX ===

M5 recorded SD-1 (four Dispatcher singletons, not one), SD-2 (every dispatcher
is_testing=True; main-thread safety is downstream in the WS handler), SD-3
(M5 deliberately does not inline the Houdini-side implementation). These are
architecture findings, not M5b's scope. Do not repair them. If you touch that
seam, keep the existing posture and say so.

=== WHAT YOU ARE NOT DOING ===

Not M6 (no phrase table, no alias routing — tools still take a fixture NAME).
Not panel UI. Not USD customData (RFC-gated with Michael Gold). No new
fixtures. No merge, no push — Gate C is human.

**If hou surprises you, probe with dir() before coding against it.**

=== ORACLE ===

  C-1..C-6 controls green BEFORE the F-* set
  F-1..F-7 green in headless hython on 22.0.368
  the c3 re-baseline recorded in the fixture with superseded_baselines[]
  cross-cwd equality demonstrated in both directions (c3 same, c2 differs)
  plain-python suite green; total test count strictly increased
  receipt M5b.json: rulings closed, the new baseline and how it was cut,
    invariant results, symbol-table outcome, and the one verdict line

=== STANDING ===

M5's engine is proven and pushed. This leg makes its oracle portable and its
delete behaviour safe. Ship over perfect — closing the four rulings honestly
beats adding anything nobody asked for.
