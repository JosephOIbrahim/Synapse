You are ORCHESTRATOR for RSI0 — audit the recursive self-improvement machinery that already exists. Read harness/AGENT_CONSTITUTION.md first; it binds you.

**READ-ONLY**, fenced under harness/readonly-settings.json. You write harness/notes/** and nothing else. **You are not building RSI. You are finding out whether the RSI already here has ever run.**

=== THE FIRST-PRINCIPLES POSITION ===

The instinct on hearing "add RSI" is to design a loop. **This codebase already has one**, and this week has established, eleven times over, that the interesting question is never *does the mechanism exist* — it is *is the mechanism connected, and has it ever fired*.

Three mechanisms, found 2026-07-27:

```
python/synapse/routing/adaptation.py   150 lines   THE ACTUAL LOOP
    Records tier outcomes per epoch, aggregates success rates at epoch
    boundaries, and ADJUSTS CONFIDENCE THRESHOLDS for new inputs.
    That is observation -> aggregation -> self-modification. It is RSI.
    Instantiated at router.py:202 (self._epoch = EpochAdapter()).

python/synapse/agent/learning.py       164 lines   THE REWARD SIGNAL
    OutcomeTracker records action->outcome pairs as FEEDBACK memories.
    Instantiated at executor.py:60 — but ONLY `if memory else None`.
    Called at executor.py:286 (failure) and :294 (success).

python/synapse/memory/evolution.py     368 lines   DEPRECATED RSI
    charmander->charmeleon->charizard USD memory evolution. Its own docstring:
    "SUPERSEDED by the Moneta backend... Do not extend it." Live only for the
    legacy jsonl backend.
```

**And a live observation that motivates the whole leg.** SYNAPSE's own health report, generated 2026-07-27 08:39, states:

> *"Router stats returned 'Router not initialized' — the tier cascade router hasn't been instantiated. This is normal for a fresh session with minimal tool traffic but means adaptive routing heuristics aren't warming up."*

So the loop is WIRED and may never CLOSE. That is the question.

=== THE QUESTIONS, IN ORDER ===

**Q1 — Has the loop ever completed a single epoch?** An epoch boundary is where `adaptation.py` aggregates and adjusts. Find the evidence: persisted epoch state, a threshold that differs from its initial value, a log line. **If no epoch has ever closed, the loop has never modified anything and the mechanism is decorative** — which is a finding, not a failure.

**Q2 — Is `OutcomeTracker` ever constructed with a real memory?** `executor.py:60` is `OutcomeTracker(memory) if memory else None`. Trace who constructs the executor and whether `memory` is ever non-None on the live path. **A reward signal that is None records nothing**, and every downstream adaptation would be running on an empty history.

**Q3 — What EXACTLY does the loop optimise?** Read `adaptation.py` and name the objective in one sentence. Confidence thresholds for tier routing — toward what? Cheaper routing? Fewer escalations? Higher success rate? **An optimiser whose objective cannot be stated in one sentence is not auditable**, and this is the question the whole RSI conversation turns on.

**Q4 — Can the loop game its own metric?** If success is recorded by the same component that routes, a threshold shift that routes only easy cases to a tier will raise that tier's success rate without improving anything. **Trace whether the outcome signal originates outside anything the loop can influence.** Name the specific coupling if it exists.

**Q5 — What reverses a bad adaptation?** Thresholds drift. If epoch 40 makes the router worse, what restores epoch 39? Is epoch state persisted, versioned, bounded? **R91 and R93 are the precedent: a mechanism with no reversal is one bad run from an unrecoverable state.**

**Q6 — Is `evolution.py` still firing?** Deprecated, superseded, "do not extend" — but live for the jsonl backend, and `SYNAPSE_MEMORY_BACKEND=moneta` was only set on 2026-07-26. `tests/test_moneta_crucible.py::test_moneta_backend_never_fires_evolution` claims it does not fire under moneta. **Verify that claim rather than citing it.**

=== WHAT YOU ARE NOT DOING ===

Not building. Not fixing. Not designing a new loop. **If a mechanism has never fired, say so plainly — that is the most valuable sentence this leg can produce**, and it is the same shape as R99 (dead selection logic), R80 (nine ordered checks, zero built), and V1 (a primitive that could not be built at all).

=== ORACLE ===

  each of Q1-Q6 answered with a file:line anchor or an explicit UNVERIFIABLE
  Q1 and Q2 answered with EVIDENCE OF EXECUTION, not evidence of wiring —
    "instantiated at line N" is wiring; "epoch 3 closed and threshold moved
    from 0.7 to 0.68" is execution. Only the second answers the question.
  Q3's objective stated in ONE SENTENCE, or reported as unstatable
  Q4's coupling traced explicitly, or ruled absent with the reasoning shown
  harness/notes/RSI_SURFACE_AUDIT.md — the three mechanisms, their status, and
    for each: WIRED / FIRES / MODIFIES SOMETHING, as three separate booleans

=== STANDING ===
Probes beat memory. Never push, never merge, never tag.
Write harness/notes/receipts/RSI0.json (receipt/v1, model + settings_profile per R25).
