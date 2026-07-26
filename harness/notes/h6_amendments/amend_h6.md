
=== AMENDED 2026-07-26 — READ THIS BEFORE LINE 24 ===

Line 24 predicted registered=True, in_use=False and said CONFIRM THAT — do not assume it.
Confirmation came back NEGATIVE on both interpreters. The brief was right to hedge; the
prediction was wrong.

  registered = FALSE on both. Nothing in packages/synapse.json or in Moneta ever sets
               PXR_PLUGINPATH_NAME, `import moneta` does not self-register, and the wheel
               ships no schema/ at all (packages = ["src/moneta"]). Registration is
               reachable only by setting the variable by hand.

  in_use     = TRUE in Moneta's own authoring path — usd_target.py:318 sets
               prim_spec.typeName = "MonetaMemory" unconditionally, and has since f7b6253
               (2026-04-27). But FALSE for SYNAPSE, which builds MonetaConfig without
               use_real_usd (moneta_store.py:215-227), so the handle runs the pxr-free
               MockUsdTarget and authors no USD at all. Zero cortex_*.usda exist on this
               machine; the one real snapshot has 39 rows, every usd_link None.

So line 22's citation IS stale — DEEP_THINK_BRIEF_codeless_schema.md:15 is a
pre-implementation design doc, committed the same day as the migration it proposes and never
updated. Line 24 named that as a finding condition; it fired.

The cell that looks like success on this build is the INVERSE of line 35's: it is
`!registered && in_use` — a typeName on disk that the runtime cannot resolve. Sdf authoring
is schema-blind, so GetTypeName() returns "MonetaMemory" with or without a registered
schema. IsA(Usd.Typed) is the discriminating signal; a check asserting only typeName
measures authoring and never registration.

Line 33's premise was also broken: store.py:817's `except ImportError` was dead code, because
moneta_store.py:207 raises RuntimeError when Moneta is absent — so the arm that did fire
logged "installed but failed to initialize ... not a missing dependency", the exact inverse
of the truth. Closed in 1fbbcd8.

Full evidence: harness/notes/receipts/H6.json, the R64 amendment in
harness/notes/CTO_RULINGS_01.md, and .claude/remediation_ticket.md.
