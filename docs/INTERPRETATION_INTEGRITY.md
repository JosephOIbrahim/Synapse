# Interpretation Integrity — closing the "I asked for one, I got four" gap

**Status:** spec, not yet built. Written 2026-08-03 from a live seat observation.
**Audience:** Claude Code, working in `C:\Users\User\SYNAPSE`, branch `rope/gate-a`.
**Origin:** Joe typed *"create an areA LIGHT IN SOLARIS"* in the Curious profile
against Nemotron Nano 30B. Three `AreaLight` prims appeared on the stage. The
panel reported success.

---

## The principle

An agent that says "done" when it did something other than what was asked is
worse than one that crashes. A crash gets reported. Silent over-delivery gets
cleaned up by hand, and the artist quietly stops trusting the tool.

This document is not about making the model smarter. It is about **shrinking
the model's jurisdiction** and **making its claims checkable**.

Ordered cheapest-first. Each layer is independently shippable.

---

## Layer 0 — The verb rail is not the culprit (RESOLVED 2026-08-04)

**Observation.** The chat showed two instructions in one turn:

```
create an areA LIGHT IN SOLARIS
Explain what the selected nodes do and how they connect.
```

**The suspicion was silent concatenation** — that the EXPLAIN verb's prompt
was appended to Joe's typed text before send. Traced 2026-08-04 in
`python/synapse/panel/synapse_panel.py`. That is not what happens.

`_build_act()` binds each verb to its own prompt and nothing else:

```python
for label_text, prompt in _QUICK_ACTIONS:
    lay.addWidget(self._verb(
        label_text.upper(), lambda _=False, p=prompt: self._send(p)))
```

`_send()` never reads the composer. **A verb fires standalone, by
construction.** The contract this document asked you to decide is already
decided in code.

### The compound instruction is real; the route is different

`_send()` appends to a running list:

```python
self._messages.append({"role": "user", "content": text})
```

and `_start_worker()` hands **the whole list** to the provider every turn:

```python
self._worker = ClaudeWorker(self._messages, system_prompt=system, ...)
```

Submit a typed prompt, then click a verb before that turn completes, and two
consecutive `user` messages sit in the list with no assistant turn between
them. Both go up in a single request.

**The question this section asked — one message containing both instructions,
or two messages? — answers: two messages, one request.** Not concatenation.
The same compound input, on a 30B model.

### What that changes

The standalone-versus-decorates contract is moot. The seam is the **turn
boundary**, not the verb rail:

1. While a turn is in flight, submission is gated — the composer's submit and
   the verb rail both refuse, or queue. The gate is panel-side, so it holds
   regardless of provider or model.
2. The panel says so visibly. A dead control with no explanation is its own
   trust problem.
3. Confirm against `C:\Users\User\.synapse\logs\synapse.log` that the 08-03
   incident actually took this path. The mechanism is proven to exist; the
   incident is not yet proven to be an instance of it. **Do not record this as
   the cause until the log says so** — a plausible mechanism standing in for
   an observed one is precisely the failure this document exists to stop.

**Cost:** hours for the gate, minutes for the log check. **Do the log check
first** — it is the difference between a fix and a guess.

---

## Layer 1 — Promote deterministic operations out of the agent tier

**The insight.** The routing cascade already exists:
`Cache → Recipe → Regex → RAG → Haiku → Agent`.

"Create an area light in Solaris" is not an open-ended request. It is a
**recipe**: a parameterized operation with exactly one correct outcome. It
should never have reached the Agent tier.

**Every request promoted out of the Agent tier converts a class of
misinterpretation from statistically-unlikely to structurally-impossible.**

**Work:**
1. Audit which requests currently fall through to Agent. Instrument the
   cascade to log the tier that served each turn.
2. Write recipes for the obvious deterministic set. Starting list, from the
   VFX operations most likely in a first session:
   - create light (area / point / distant / dome), N defaulting to **one**
   - create camera
   - create a primitive (sphere / grid / box / tube)
   - scatter points on selected geometry
   - copy-to-points / instance
   - assign material to selection
   - set display / render flag
3. Recipes must be **arity-explicit**: the count is a parameter with a default
   of 1, never inferred from prose.

**Cost:** days, incremental. Each recipe is independently shippable and each
one permanently removes a failure mode.

---

## Layer 2 — The agent verifies its own claim before reporting done

**The insight, from RETINA's own philosophy applied to scene ops instead of
renders:** a confirmation that isn't backed by observation is a claim.

The mismatch in this incident was **mechanically detectable with no model
involvement**: the request implied one light; the stage gained three prims.

**Work:**
1. Snapshot relevant scene state before a mutating turn — prim/node counts by
   type, under the affected parent path.
2. Snapshot after.
3. Diff, and compare against the operation's declared intent (which Layer 1's
   recipes make explicit — a recipe knows it should create exactly N).
4. On mismatch, the panel **reports the discrepancy rather than success**:

   > Created 3 AreaLight prims — the request implied 1. Keep or revert?

5. Wire that revert to the existing undo/rollback path.

**Honesty discipline, inherited from `retina_manifest.py`:** where intent
cannot be honestly derived (a genuinely open-ended agent turn), the check
reports **inconclusive** — never a false pass, never a fabricated expectation.

**Cost:** week-ish. This is the layer that makes Synapse's confirmations mean
something, and it is the natural sibling of RETINA M2.

---

## Layer 3 — User feedback, correctly scoped

**Feedback is not training data.** Fine-tuning is the wrong economics and it
welds Synapse to one model.

**Feedback is a recipe backlog.** Its job is to tell you *which requests fell
through to the Agent tier and went wrong*. A thumbs-down on "create an area
light" is not a training signal — it is a work item saying *this should have
been a recipe and wasn't.*

**Work:**
1. Per-turn thumbs up/down in the chat surface.
2. Capture with it, automatically: the routing tier that served the turn, the
   tool calls made, the scene diff (Layer 2), the model id, and the prompt.
3. Local-first. This is a single-user localhost tool; **do not ship telemetry
   without explicit opt-in**, and do not let this contradict the privacy
   posture stated in the README and SECURITY.md.
4. Report: "requests that reached Agent and were marked wrong, grouped by
   similarity" — read that list, write those recipes, repeat.

**Cost:** days for capture, ongoing for the loop.

---

## Layer 4 — Model-appropriate prompting

Small local models need shorter, more literal, one-instruction-per-turn input.
Frontier models tolerate compound requests. Synapse already knows which model
is active.

**Work:** let the system prompt overlay vary by model class, not only by
profile. A 30B local model gets a terser, more constrained instruction frame
than a frontier model does. The `system_prompt_overlay` mechanism in
`python/synapse/panel/manifests/curious.py` is the existing seam.

**Also:** document the difference for beta testers. Most will start on Ollama,
and "be literal and specific with local models" is honest guidance, not an
apology.

**Cost:** hours to days.

---

## Layer 5 — Profiles must be mechanism, not prompt text

**Observed 2026-08-03, same session.** Curious, Expert and ML rendered
identically at the seat. Two separate causes, and the second is the important
one.

### 5a — The rendering bug (FIXED, verify at the seat)

`compositor.compose()` set the `density` dynamic property on the panel root and
repolished **only the root**. Qt does not cascade a property change to
children, so every `#DsRoot[density=...] <child>` rule matched on paper and
never repainted. Airy buttons specify `16px 24px` padding against tight's
`4px 8px` — a large difference that rendered as nothing.

Fixed by repolishing the whole subtree (`_repolish_tree`). Commit `4484c747`.
**Still needs seat confirmation.**

**The general lesson, worth a guard:** any panel-wide dynamic property needs a
tree-wide repolish. If another such property is ever added, this bug returns.

### 5b — The architectural problem (NOT FIXED)

Even with rendering repaired, the profiles' *behavioural* difference is
implemented as **prompt text**: `system_prompt_overlay` in
`python/synapse/panel/manifests/curious.py` asks the model to narrate
decisions, translate errors, and define jargon on first use.

That is a request, not a mechanism. The four-lights incident is the proof of
what requests are worth — the model was asked for one light and produced three.
On a 30B local model, compliance with a narration instruction is not reliable
either, so **Curious's promise is only as good as the model's mood.**

`docs/PROFILES.md` documents a hand-me-the-pen gradient —
`build-while-you-watch → build-with-pauses → explain-then-you-try` — that
exists nowhere in code.

**Make the pace structural. Capability stays identical in all three profiles
(the L5 invariant); what varies is who confirms, and when.**

- **Curious** — the panel intercepts before tool execution:
  *"About to create 1 AreaLight at /lights. Proceed?"* The pause is the harness
  holding the call, not the model choosing to mention it. That is
  build-with-pauses as a guarantee.
- **Expert** — no interception. Same tools, no gate.
- **ML** — shows the cost of the turn before spending it: tokens and dollars
  from the provider's own numbers, never an estimate (the `face_token.py`
  contract already states this discipline).

**Note the convergence:** Curious's pre-execution pause is Layer 2's scene-diff
check surfaced *before* execution instead of after. Same machinery, two
placements. Build them together.

**Where to work:** the tool-dispatch path between `claude_worker` and the
in-process `hou` call — `bridge_adapter.py`, `_tool_registry.py`, `handlers.py`.
The gate must be panel-side, so it holds regardless of provider or model.

**Cost:** week-ish, and it is the same week as Layer 2.

**Until it exists, do not demo profile switching as a capability difference.**
Demo it as pacing — same prompt, Curious's narrated reply beside Expert's terse
one — which is true today.

---

## Layer 6 — Unmeasured is not zero (worked example: `synapse_doctor`)

**Observed 2026-08-03, 8:18 PM, live seat.** `synapse_doctor` reported:

```
Integrity check failed: fidelity=0.0
```

The agent (Kimi K3, via Ollama) did the right thing unprompted: it distrusted
the red line, cross-checked seven planes independently, and found every one of
them healthy — bridge ping (protocol 4.0.0), health with
`houdini_available: true`, both write planes, a live scene query returning 10
nodes, 341 memory entries, scene info intact. It then named the likely cause:

> `synapse_live_metrics` returned **not-running**. If that aggregator feeds the
> fidelity computation, the zero is a zero-sample read, not a broken bridge.

That hypothesis is almost certainly correct.

### Why this is the same bug as the rest of this document

The repository already states the correct rule, in
`python/synapse/panel/face_token.py`:

> *Unobtainable renders as UNKNOWN, never zero and never an estimate.*

The TOKEN face obeys it. **The doctor's fidelity probe does not.** It has no
samples, and it renders that as `0.0` — a number that reads as *total
integrity failure* rather than *no data*.

This is the identical failure shape as the four lights and the profile
overlays: **a claim asserted where nothing was actually observed.** Here it is
inverted — a false negative instead of a false positive — which makes it no
less damaging.

### Why it matters more than it looks

`synapse_doctor` is the first thing the documentation tells a new artist to
run. It is named in the README and in `docs/help/index.html` under *When
something goes wrong*. **A healthy install that opens with a red integrity
failure is the first impression every beta tester gets.** They will either
report a bug that isn't one, or conclude the tool is broken and stop.

### The fix

1. The fidelity probe must distinguish **failed** from **unmeasured**. Zero
   samples returns `UNKNOWN` / `inconclusive`, never `0.0`.
2. The doctor's summary must not render `UNKNOWN` as a failure. Suggested
   surface: `fidelity: unknown — metrics aggregator not running`, with the
   remedy inline.
3. Audit every other probe in the doctor for the same shape: any check that can
   return a numeric score must be able to say *I could not measure this*.
4. `retina_manifest.py`'s `honesty` block is the pattern already in the
   codebase — fields the host cannot cheaply and truthfully derive are recorded
   `inconclusive`, never faked. Reuse that vocabulary rather than inventing a
   second one.

**Immediate, before any invite goes out:** start the metrics aggregator, re-run
`synapse_doctor`, and confirm fidelity scores clean. That verifies the
hypothesis and clears the first-impression problem for the beta.

**Cost:** hours. **Priority: high** — it is small, and it sits on the first
command every new user runs.

---

## Tonight, before the announcement

One line, in `Known limitations` in the README:

> The agent may create more nodes than you asked for. Check the network before
> continuing; undo is scene-level.

This costs nothing and it is the difference between a tester who was warned and
a tester who was surprised. Surprised testers stop reporting bugs.

---

## Sequence

| | Layer | Cost | Why here |
|---|---|---|---|
| 1 | **Layer 0** — turn-boundary gate | hours | Verb rail cleared; seam moved |
| 2 | **README line** | minutes | Ships with the announcement |
| 2b | **Layer 6** — doctor honesty | hours | First command every tester runs |
| 3 | **Layer 1** — recipes | days, incremental | Structural, permanent |
| 4 | **Layer 2** — scene-diff verification | week | Makes "done" mean something |
| 5 | **Layer 5b** — profiles as mechanism | week (with Layer 2) | Makes the L5 claim true |
| 6 | **Layer 4** — model-aware prompting | hours–days | Cheap, helps every local user |
| 7 | **Layer 3** — feedback loop | days + ongoing | Feeds Layer 1 forever |

**This week:** the Layer 0 log check and turn gate, the README line, Layer 6, seat-verify the 5a fix, and
the first three or four recipes.

**Before the first beta invite:** start the metrics aggregator and confirm
`synapse_doctor` runs clean. A red doctor on a healthy install is the worst
possible first impression.
**Next:** Layers 2 and 5b together — a pre-execution gate and a post-execution
diff are one piece of machinery — alongside RETINA M2, which is the same idea
again in the render domain.

---

## The measure

Synapse is measured by what the artist can do without it. An agent that
over-delivers silently teaches the artist to distrust their own scene, which is
the opposite of the axiom. Every layer above exists to make Synapse's
confirmations worth believing — and none of them require a smarter model.
