# v5.77.0 — turn two answers, and the harness picks its own graph

**Product change.** Two fixes in the panel and the router, both from the BP7 investigation into why chat stalled after the first message. The build harness gained the JEV helm.

**No new installer in this release.** The `SYNAPSE-5.75.2-Setup.exe` the README links is the last built installer and does **not** contain these two fixes; they are on the source tree at this tag. An installer build is a separate, later act.

## What changed in the product

**The router's tier timeouts are enforced.** `RoutingConfig` has carried `tier2_timeout=5.0` and `tier3_timeout=15.0` since the cascade was written, but the LLM calls never received them, so a slow model turn blocked the handler until the 30 s slow-op kill, which emits nothing. Both timeouts now reach the SDK call, a timed-out tier records a failure metric and falls through, and `route()` is bounded in the handler so the turn always answers with a well-formed `{response, tier}`. (`python/synapse/routing/router.py`, `python/synapse/server/handlers.py`; `tests/test_bp8_timeouts.py`, 6 tests.)

**The panel has a response watchdog.** A message that never gets a reply used to leave the typing indicator spinning forever with no error. A single-shot timer armed on send now clears the waiting state after the server's budget plus a margin (`WATCHDOG_TIMEOUT_MS = 35000`) and appends one system line saying no response arrived and the message can be sent again. Connection errors and a status drop to disconnected clear the same state through one shared helper. (`python/synapse/panel/chat_panel.py`; `tests/test_response_watchdog.py`, headless plus a real-QTimer probe on hython 22.0.400.)

**Referee verdicts.** BP8-CRUX re-ran every headless acceptance row in fresh clones, proved the tests bind to the new code, and authored 18 mutations: 13 reddened the named test, 5 were predicted guard-hole probes. Both legs **SOUND-WITH-NITS** (`harness/battleplan/notes/BP8-CRUX_verdicts.md`). The one row a referee cannot close — a hung turn 2 in a live H22 panel showing the recovery line — is UNKNOWN by rule and is Joe's click.

## What changed in the harness

**The JEV helm: Jev picks the graph, code builds it.** Four new guards beside ROUTE and SCREEN, all under `harness/jev/`, card at `harness/battleplan/notes/JEV_HELM.md`:

- **JEV-SHAPE** — an objective in, a wave-graph template out (`solo`, `fix-crux`, `scout-synth`, `build-screen-crux`, `probe-only`; `workflows.json`). The Choice must clear 0.60 and a second independent judgment must agree, else `manual`. 4/4 against past waves; it refused a bundled objective at 0.54, correctly. Live.
- **JEV-TEAM** — how many subagents one leg may spawn (0/2/4), on `"team": "auto"`. Doubt rounds down; writers that would share a file get zero. Zero on all twelve real legs judged: the wave graph already is the parallelism. Live.
- **JEV-EDGE** — on a FLAG receipt, insert one bounded repair leg on the flagged branch; max two per wave, no chains, referee never rewrites the graph. Inert unless `SYNAPSE_JEV_EDGE`. Shadow.
- **JEV-DRIFT** — is a running leg looping or out of scope. Shadow only by construction; a test fails if the file ever gains a bus writer. `drift.py` keeps refocus/halt. Inert unless `SYNAPSE_JEV_DRIFT`.

**BP8 was the first wave shaped by the helm.** SHAPE chose `build-screen-crux @ 0.99` from the BP7 verdict's named changes; ROUTE agreed 4/4 with the authored tiers. Measured spend from transcripts: TIMEOUTS 22.2M, WATCHDOG 26.7M, CRUX 30.9M — 79.8M against a 70M ceiling, so the rails halted TIDY, as designed.

**SCREEN's count check moved into code.** Jev 1.13's own model card says it "does not count reliably". The expected-vs-reported count comparison that rule 2 had delegated to Jev is now `count_mismatch_rows()`; it catches the BP4-RULINGS receipt (22 expected, 21 reported, CRUX BROKEN) that Jev had scored 0.25.

**`jev_grade.py`** replays every ledgered raw answer under candidate SCREEN policies against CRUX's verdicts with zero new Jev calls. On n=8 the current policy has zero misses and zero CLEARs; the ruling on a looser CLEAR threshold is open.

**Fifty-five biting tests** under `harness/jev/tests/`, up from fourteen.

## Also

- `dashboard_bp8.py` — a wave board that renders unmeasured values as UNKNOWN, never an estimate.
- `orchestrate.ps1` gained two hooks, both inert without their env flag; a leg with no `team` field compiles byte-identical to before (tested).

## Not in this release

- The BP7 memory-store finding (H6, `_adopt_scene_store` loading synchronously on the main thread after a Save-As) is confirmed by trace but deliberately not fixed here: it fires only under a scene rebind the reported symptom did not involve. It joins the wave once the live repro says it belongs.
- EDGE and DRIFT stay in shadow until their ledgers disagree with CRUX in a way worth a ruling.
- BP8-TIDY did not run (budget halt). It is a read-only census and can run any time.
