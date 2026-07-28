# V2 — The verdict schema + the voice contract

**Leg** `V2` · **Harness** `ECON-01` · **Run** 2026-07-28 · Blueprint Mile 3
**Governed by** `harness/AGENT_CONSTITUTION.md` · **Brief** `harness/prompts/v2.md`
**Producers** `v2_prompt_delta.py` · `v2_mutation_test.py` (+ `v2_mutation_plugin.py`)
**Product** `python/synapse/panel/verdict.py` · `voice_contract.py` · `decision_log.py`

---

## The one-paragraph answer

**The contract is built and enforced. The brief's cost argument for it is
refuted, and the reason is the brief substituting the same two units E0 spent a
whole leg separating.** The typed object refuses to be constructed without an
author, refuses model-free prose in any field but one, refuses to let the model
author its own credit line, and cannot tell an unmeasured token count from a
zero. The voice contract is ten rules, every one demonstrated firing, every one
mutation-tested against a shipped module rather than a stub.

**Two passes found what the leg could not see about itself, and both are the
reason to run them.** The mutation harness reported **all ten voice rules
unpinnable** on its first run — `validate` had snapshotted its rule table at
import, so nothing a mutation changed was ever read. The adversarial pass then
found a **blocker in the gate itself**: acceptance was never recorded, so after
the canonical reject → rewrite → accept loop, `resolve()` handed back the string
the gate had just **rejected** — and the invariant-8 arm that should have caught
it was blind by fixture. Both are fixed, both are now pinned by a mutation, and
both are kept in the record.

Invariant 8 holds across three tiers on actual bytes. But the measured
before/after says this contract **does not shrink the thing that cannot be
cached**: it removes **688** exact tokens of register instruction from the system
prompt and adds **1,046** (928 lean) of JSON Schema to the tool block — a **net
cost of 240–358 preload tokens**, and a **derived saving of ~755 BTE per API
call** because the tokens moved from a span that is rewritten every turn into one
that is read. Cost and price move in opposite directions, which is E0's central
correction applied to the leg that cited it.

---

## What was built

| | file | what it is |
|---|---|---|
| the object | `python/synapse/panel/verdict.py` | seven frozen dataclasses, a JSON-Schema wire form, and a pure row projection |
| the register | `python/synapse/panel/voice_contract.py` | ten rules, a reject-and-re-ask gate, a templated floor |
| the reconciliation | `python/synapse/panel/decision_log.py` | additive adapter — P1's quoted rows enter the typed field with their provenance intact |

**Nothing renders in the panel.** T.4's freeze holds until V3 also lands. No
call site in `synapse_panel.py` or `face_review.py` was touched.

### Enforced, not documented

1. **`by` is never null.** It is the first field with no default, so `Verdict()`
   is a `TypeError` from the language before any of this code runs; `by=None`
   raises; a dict raises. *A verdict with no author does not render because it
   cannot be constructed.*
2. **Invariant 1 is a provenance ladder, not an honour system.** `MODEL_FREE` is
   refused on every field that could carry it, so exactly one field renders a
   string the model wrote freely. `model_free_fields()` reads the answer back off
   a built object, so the invariant is checkable from outside as well.
3. **Unmeasured is not zero.** `None` means nobody looked; `0` means somebody
   looked and saw none; `bool` is refused because `True` is an `int` in Python
   and would silently become a count of 1. E0-F12 says no usage reader is closed,
   so today every real verdict carries `None` — and the render proves the two
   are distinguishable.

### The ladder, and why it exists

Invariant 1 as written — *"the panel renders NO string the model wrote, except
`verdict`"* — is contradicted by work merged the same morning. `decision_log`
**quotes** a sentence the model wrote and renders it. Rather than weaken either,
the contract names four provenances and enforces that only one of them may reach
a second field:

    MODEL_FREE    unconstrained prose.  ONE field: `verdict`.  Refused elsewhere.
    MODEL_QUOTED  a sentence the model wrote, SELECTED verbatim (decision_log)
    TOOL          derived from a tool's name/input/result (_turn_evidence)
    SYSTEM        composed by the panel or router from its own state

Both existing credit producers now land in the same typed field with their source
recorded. Neither was replaced. **See V2-F6 — whether `MODEL_QUOTED` satisfies
invariant 1 is a ruling, not a decision this leg may take.**

---

## The oracle, line by line

| the brief asked for | verdict | evidence |
|---|---|---|
| the verdict object as a typed contract, `by` non-nullable **ENFORCED** | **MET** | `test_verdict_without_by_is_a_type_error` + 3 siblings; mutations `none_by`, `anonymous_by` both caught |
| the voice contract as a VALIDATOR that can fail, **demonstrated failing** (R127) | **MET — with a measured hole, see V2-F9** | 10/10 rules fire on their own violation and stay silent on a conforming one; `test_every_rule_is_demonstrated_firing` pins the coverage to the rule set. On an adversarial corpus the rules score **0% false positives and 100% false negatives** |
| the templated fallback, demonstrated firing after three rejections | **MET — after repair** | fires on the 3rd and not the 2nd; a model that recovers on the 3rd keeps its words *and the gate now records that it did* (V2-F10); degrades rather than smuggling a rejected hedge; empty when nothing structured exists |
| the invariant-8 suite: same input, ≥2 tiers, byte-identical rendered output | **MET — after repair** | 3 tiers, bytes not strings, an anti-vacuity control, a demonstrated red, and a mask-footprint control the first draft lacked (V2-F17) |
| a MEASURED before/after on the system prompt via `count_tokens` | **MET — and it refutes the premise** | calibration PASS against R155's 2,961; net **cost**, not saving. See below |
| NOTHING rendered in the panel yet | **HELD** | no panel call site touched |

---

## The measurement, and what it refutes

Producer `v2_prompt_delta.py` → `V2_prompt_delta.json`. Every figure is
`count_tokens` — **exact, free, unbilled** (R155 ruling 3). 13 calls, no
completions.

**Calibration first (R60).** The reader reproduces R155's committed exact figure
for the `/stage` system prompt — **2,961 tokens, measured 2,961** — before it
publishes anything new. A reader that cannot reproduce a known number has not
earned the right to report an unknown one.

### What comes OUT

| network | before | after | removed | share |
|---|---|---|---|---|
| `/stage` | 2,961 | 2,273 | **688** | 23.2% |
| `/obj` | 1,537 | 849 | **688** | 44.8% |
| `/out` | 1,394 | 706 | **688** | 49.4% |

`TONE.md` — the Synapse Voice Guide — is **688 exact tokens**, every turn. That is
the register instruction the structured contract makes unnecessary.

> The "after" prompt is a **counterfactual** built by string surgery on the real
> output of `build_system_prompt`, verified by reconstruction. `TONE.md` was not
> modified and `system_prompt.py` was not touched — neither is this leg's to
> change. The measurement says what is *available*, not what has been taken.

### What goes IN

    as shipped   1,046 tokens  =  981 structure  +  65 rule prose
    lean           928 tokens     (drops maxLength/minimum/pattern/additionalProperties,
                                   all of which verdict.py enforces at construction anyway)

**The intuition was wrong and the measurement said so.** The added cost is not
relocated register instruction — the rules are 65 tokens. It is JSON Schema
structure, and **a schema for a six-field object costs 1.52× the entire prose
voice guide it replaces** (1.35× lean).

> Both figures are **post-repair**. Taking `by` off the wire (V2-F13) removed 138
> tokens as a side effect of closing an invariant-1 hole — the schema was 1,184
> when it asked the model to author its own credit line.

### The net

| | `/stage` | `/obj` | `/out` |
|---|---|---|---|
| net, as shipped | **−358** | −358 | −358 |
| net, lean | **−240** | −240 | −240 |

**Negative is a cost.** The brief's claim — *"it shrinks the thing that cannot be
cached"* — is **REFUTED on preload tokens.**

### But price moves the other way

`cache_control` sits on the **last tool** (`anthropic_provider.py:64`), so a
schema appended to the tools array lands inside the cached prefix. The tone guide
sat in the system span, which E0-F5/F6 showed is rewritten every turn — a
perpetual cache **write** that is never read back.

    before   688 x 1.25 (write, never read)     =   860 BTE / call
    after  1,046 x 0.10 (read, after 1 write)   =   105 BTE / call
    steady state                                =  +755 BTE / call saved
    break-even                                  =  2 calls

**VERIFIED-DERIVED**, and it rests on three inputs neither this leg nor E0
verified: E0's limit A1 (the 1.25×/0.1× multipliers were never re-checked against
current pricing), E0-F12 (no usage reader is closed, so cache warmth is inferred
from code and never observed), and the assumption that the system span is a
**perpetual write** in every session, not only the navigating one.

> That third input was challenged in review and **held on E0's own artifact**:
> `E0_segments.json:q4_stability_by_session.stationary.system_whole.stable_across_3_turns`
> is `false` — three distinct hashes across three stationary turns. The span is
> rewritten even when the artist does not navigate, so the write rate applies to
> both sessions. It is named here because if it were wrong the sign would flip,
> and a load-bearing assumption belongs on the face of the figure.

`break_even_calls` is now the closed form solved for the smallest whole `n`, and
returns `None` rather than a number when the per-call saving is non-positive. The
first draft floor-divided the one-time write by the per-call saving and added 1,
which lands on 2 for these inputs by coincidence rather than by arithmetic
(V2-F16).

> **This is E0's correction applied to the leg that cited E0.** Preload tokens
> and price are different quantities. This contract is a **cost** on the first
> and a **probable saving** on the second, and which governs is E2's call — it
> cannot be settled until the usage reader is closed, which was already E0's
> prerequisite 4.

### And what it does NOT fix

Removing the tone guide does **not** make the cached span static. `/stage → /obj`
still swings **1,424 tokens** and `/stage → /out` swings **1,567**, because
`_solaris_context_block` swaps the guidance literal on navigation (E0-F6). Both
figures cross-check against the independently measured whole-prompt counts
(2,961 − 1,537 = 1,424; 2,961 − 1,394 = 1,567). The contract addresses the
register half of the non-staticness. **The larger half is untouched — it is more
than twice the size of the half this leg can reach — and must not be reported as
fixed.**

---

## Reader calibration (R60) and mutation-tested controls (R133)

| id | what | verdict |
|---|---|---|
| CAL-1 | token reader reproduces R155's committed `/stage` figure bit-exactly | **PASS** — 2,961 = 2,961 |
| CAL-2 | counterfactual surgery is reconstructible (removed span == tone + join) | PASS |
| CAL-3 | the loaded tone guide is the committed `TONE.md`, not a cached stale copy | PASS |
| CAL-4 | every voice rule fires on its own violation | PASS ×10 |
| CAL-5 | no voice rule fires on a conforming verdict | PASS ×10 |
| CAL-6 | the firing-case set equals the rule set (no rule ships undemonstrated) | PASS |
| CAL-7 | invariant-8's masked row is masking something real | PASS — 3 distinct BY values |
| CAL-8 | invariant-8 detects a renderer that does branch on tier | PASS — goes red |

**29 mutations, 29 caught, 0 survivors, 0 invalid** (`V2_mutation.json`). Each
removes one piece of enforcement from a **shipped** module — not a stub — and the
control file that should notice it must go red.

Three corrections to the harness itself came out of the adversarial pass:

- **A non-zero exit is no longer read as "caught."** pytest exits non-zero for a
  collection error or a plugin that raised, so a crashed run was scoring as a
  successful detection. A mutation now counts only when a test actually FAILED,
  and a `broken` outcome is reported as `INVALID`, never as a pass.
- **Two mutations were over-broad and attributed to nothing.** `bool_is_a_count`
  rebuilt `By.__post_init__` on the false premise that it closed over `_count` —
  it resolves through globals at call time — and in doing so also deleted the
  model-required, tier-required and tier-shape checks. `name_may_be_a_sentence`
  silently deleted "chose is required" the same way. Both are now single-guard.
- **Seven mutations were added**, one per defect the adversarial pass found, so
  each repair is pinned by something that goes red if it is undone.

> **The first run found ten survivors and that is the leg's most useful hour.**
> All ten voice-rule mutations left the suite green, because `validate` took
> `rules=VOICE_RULES` as a **default argument** and snapshotted the table at
> import. Nothing a mutation changed was ever read. The controls were pinning a
> table nobody consulted — R127's defect wearing ten masks, exactly the shape
> R131 made a standard. Fixed in the product (call-time resolution), not in the
> harness.

---

## The adversarial pass

Article IV: the crucible never built the thing it attacks. Six hostile lenses
(oracle conformance · Law-1 vacuity · contract soundness · the voice rules as a
product · the numbers · constitution and standing rules) were run read-only
against the committed leg, and **every finding was then handed to an independent
verifier instructed to REFUTE it** and to default to refuted unless it could
reproduce the wrong output itself.

**36 verdicts: 27 upheld, 9 refuted.** The refutations mattered as much as the
upholds — one of them defended the price figure by reading E0's own artifact
(above), and one showed that a proposed "inert control" was byte-identical to the
shipped product.

**It found a blocker this leg had missed, and the blocker was in the one thing
the leg exists to guarantee.**

> `VoiceGate.submit` returned an ACCEPTED outcome without recording it, so
> `resolve()` fell through to the object's ORIGINAL free field. The canonical
> loop — reject → the model rewrites → the gate accepts — **rendered the string
> the gate had just REJECTED, violations intact.** Four independent verifiers
> reproduced it.
>
> The invariant-8 arm that should have caught it was blind **by fixture**: the
> test built its gate around a verdict already carrying the good sentence and
> then submitted that same sentence, so "returns the accepted text" and "returns
> the pre-gate text" were equal by construction. Law 1, in my own suite, in the
> exact shape the constitution names — a check that could not fail for the defect
> it was written to catch.

Every upheld finding is repaired below and pinned by a new mutation. The fixture
now carries prose the gate must reject, so the test can tell the two apart.

---

## Findings

**V2-F1 · the ten controls that pinned nothing.** `validate`'s default-bound rule
table meant `VOICE_RULES` was un-overridable and un-mutatable. Two authorities on
one table — the shape `panel/tokens.py` was repaired for. VERIFIED-RUNTIME, first
mutation run. **Fixed** at `voice_contract.py:validate`.

**V2-F2 · there is no tier vocabulary and this leg must not invent one.**
`by.tier` is shape-checked (lowercase identifier), not vocabulary-checked.
`RoutingTier` (`routing/router.py:68`) is the **cascade** tier — cache/recipe/
instant/fast/standard/deep — a different axis from the model tier this schema
carries. V3 owns the manifest and runs concurrently; a closed set invented here
would reject V3's names on the day it lands. `By.validate_tier(vocabulary)` is the
opt-in hook. **for_ruling.**

**V2-F3 · the schema's `checks` cannot say "inconclusive".** Two states, per the
blueprint. `face_review.py` renders five, and RETINA's receipt is tri-state with a
**ratified** honesty rule that an inconclusive check must not render as a pass
(`face_review.py:56-64`). `check_from_tristate` maps `None → fail` — lossy in the
safe direction, and named rather than hidden. **for_ruling.**

**V2-F4 · `cost` is carried and not drawn.** The panel's metering rule is TOKENS
ONLY, never $ (`synapse_panel.py:468-471`), and no usage reader is closed
(E0-F12), so a cost row today would be a currency figure with no producer. The
field stays on the object. **for_ruling.**

**V2-F5 · the typed schema has no slot for `classified`.** `decision_log` rule 3
deliberately keeps an unregistered tool's row **loud**; the verdict schema cannot
carry that warning. The adapter therefore **refuses** to convert an unclassified
row unless the caller opts in, rather than converting and forgetting.
**for_ruling.**

**V2-F6 · invariant 1 as written is contradicted by merged work.** `decision_log`
quotes a model sentence and renders it. The ladder makes the distinction
enforceable, but whether `MODEL_QUOTED` **satisfies** invariant 1 or **violates**
it is a value judgement between defensible options. **for_ruling.**

**V2-F7 · the brief's cost premise is refuted.** Net **+332 to +496 preload
tokens**, not a reduction. The voice case for this leg stands entirely on its own
merits — tier rotation without voice B is a re-onboarding event — and does not
need the cache argument. VERIFIED-RUNTIME (`count_tokens`, calibrated).

**V2-F9 · the rules are lexical, and the register failures that matter are not.**
Producer `v2_voice_probe.py` → `V2_voice_probe.json`, an 18-verdict labelled
corpus:

    good corpus  8 of 8 accepted     false-positive rate  0%
    bad corpus   0 of 10 caught      false-negative rate  100%

**Zero false positives is the result that matters most** — the rules never reject
good VFX register, including decimals, node paths, units (mm, K, fps),
semicolons and `e.g.`, so they never burn a re-ask on a verdict that was already
right. But every one of ten adversarial verdicts got through, including
`"Everything went fine with Dark_Glass"`, `"All good on /stage/matlib"` and the
bare token `"Dark_Glass"`.

The shape of the gap: the rules catch **banned words, sentence breaks, length and
markup**. They do not catch a sentence that is grammatical, specific-*looking*
and empty. `names_change` is satisfied because the token is present, not because
the sentence is about it.

**This is not closed here, and that is deliberate.** The brief enumerates the
rules — one sentence, outcome first, names the change, no preamble, no hedging,
no restating the request, a ceiling — and all seven are implemented and
demonstrated. Rules beyond that list, tuned against ten verdicts I wrote myself,
would be over-fitted to a sample of one author and would then be cited as
coverage. The corpus is committed so a later rule has a regression target: it
must move 100% down, and moving it is how anyone will know it worked.
**for_ruling.**

> **What this costs the product, stated plainly.** The brief's *"a weak model
> must not be able to produce a weak panel"* holds for the **structure** —
> everything except `verdict` is panel-composed and byte-identical across tiers —
> and for prose that trips a lexical rule. It does **not** yet hold for a weak
> sentence that is merely empty. The floor never fires, because nothing failed.

### Found by the adversarial pass, repaired here

**V2-F10 · the gate did not record its own acceptances. BLOCKER, fixed.**
`submit`'s accept path returned a `GateOutcome` without setting `_final`, so
`resolve()` returned the pre-gate free field — the rejected draft. `submit` now
latches acceptance exactly as it latches the floor; `resolve()` **raises** rather
than answering before anything is settled; and `settled` (a verdict is final) is
now a different question from `exhausted` (the floor fired), because conflating
them is what let the accept path escape. Pinned by `unlatched_accept`.

**V2-F11 · `names_change` refused a name written inside its own path. Fixed.**
The lookbehind excluded `/`, so `dome_light` in `/lights/dome_light` did not
match — the rule rejecting the most specific form of exactly what it asks for.
Pinned by `path_name_refused`, with a companion test that `dome_lighting` still
does not count as `dome_light`.

**V2-F12 · the seam crashed on its commonest input. Fixed.** `decision_log._trim`
appended its ellipsis AFTER cutting to the limit, returning `limit+1` for any
string with no space in its first `limit` characters — i.e. every node path, which
is exactly what `_CHOICE_KEYS` selects. The typed field then raised, and
`to_verdict_decisions` took the whole cycle down with it. `_trim` now reserves the
ellipsis's own column, and a rejected row is dropped and **counted** in
`rejected_conversions()` rather than costing every other decision in the cycle.
Pinned by `trim_overflow` and a `_trim` property test over four limits.

**V2-F13 · the wire form made the model author its own credit line. Fixed.**
`json_schema()` required `by` — the model's own model id, tier, **96 characters of
free-text `reason`**, and its own token counts, all of which render. A second free
field arriving through the one door invariant 1 exists to watch, and a tool
description that said *"you write only `verdict`"* contradicting the schema inside
one function. `by` is SYSTEM data: the panel knows which provider it called.
Removing it also cut **138 tokens**. Pinned by `author_on_the_wire` plus a
per-field test that no single `By` field can creep back.

**V2-F14 · the schema blessed payloads the constructor rejected. Fixed.** `paths`
was an unconstrained string array while the constructor enforced absolute-and-96.
That gap is where an agent emits something valid and the panel explodes on it.
Pinned by `unconstrained_wire_paths`.

**V2-F15 · a fractional token count constructed and rendered as a whole one.**
`tokens_in=1.9` passed and drew as `1` through `%d` — a wrong figure becoming a
plausible one on the way to the screen. Token fields now refuse floats; `cost`
stays fractional because money is. Pinned by `fractional_tokens`.

**V2-F16 · `break_even_calls` was not the arithmetic it claimed.** Floor-divided
one-time write over per-call saving, plus one — right answer, wrong method, and
it would have reported a break-even for a regime that never breaks even. Now the
closed form, returning `None` when the per-call saving is non-positive.

**V2-F17 · two of my own controls could not fail for the defect they named.**
`register_signature` could be replaced with one masking EVERY value — collapsing
invariant 8 to "the row keys match" — and the suite stayed green, because one
control read the unmasked `render_rows` and the other re-implemented the masking
locally instead of calling the product function. And
`test_the_schema_carries_one_ceiling_not_two` compared two reads of the same
variable, so a hardcoded literal left it green. Both rewritten to call the product
and to MOVE the constant. Pinned by `over_masked_signature`.

---

**V2-F8 · `synapse_economist_blueprint.md` is not in the tree.** The brief cites
§3.1/§3.2/§04/§P7 and invariants numbered 1/6/8; `harness/SYNAPSE_ECONOMIST.md`
§3 restates six invariants under a **different numbering** (blueprint 6 = harness
4, blueprint 8 = harness 6, blueprint 1 absent entirely). The load-bearing content
was inlined in the brief, so this is drift, not a blocker — but no leg after this
one should cite a blueprint section number as if it could be looked up. **drift.**

---

## Drift

**D1 · two figures in the first committed draft of this document had no
producer.** `/stage → /out` was published as **1,712** where the artifact says
**1,567**, and the schema-to-tone ratio as **1.6×** where it is **1.72×** (1.48×
lean). Both were written from recall of E0's proxy figures rather than read off
`V2_prompt_delta.json` — **Law 5 in the document that cites Law 2**, and R127's
exact shape: a number whose producer I wrote and did not read back. Caught by
cross-checking every figure against its artifact before the receipt; corrected at
the commit following `a8a773d`. The correction is here rather than silent because
the silent version is the defect.

---

## Limits

- **Nothing is wired.** No panel call site imports either module. The contract is
  enforced on construction and nothing in the product constructs one yet — this
  leg proves the shape, V3 + the panel unfreeze prove the flow.
- **No model in the loop.** The voice rules were demonstrated against
  hand-written tier-characteristic prose, not against live Haiku/Opus output.
  `TIER_PROSE` in the invariant-8 suite and both corpora in `v2_voice_probe.py`
  are **fixtures, not samples** — written by one author, which is exactly why
  V2-F9 is reported rather than patched.
- **The false-negative rate is 100% on the measured corpus** (V2-F9). The rules
  are lexical; empty-but-grammatical register passes.
- **`names_change` is lexical.** A verdict that names the change in a synonym is
  rejected. That is deliberate (a synonym is not a name the artist can search
  for) and it is a false-positive axis nobody has measured on real output — the
  8-verdict good corpus found none, which is a floor, not a clearance.
- **The price figure is DERIVED** on two inputs neither leg verified (above).
- **`no_request_echo`'s 0.6 ratio has no producer.** It is a chosen threshold, not
  a measured one, and it is the one rule whose constant was not calibrated
  against data.
- The counterfactual measures removing `TONE.md` **entirely**. If any part of the
  tone guide governs behaviour the schema does not cover, the real available
  saving is smaller than 688.
- Suite evidence is the **system Python 3.14.2 gate**, not the shipping hython
  runner; the vendored tree is INACTIVE on this interpreter.
