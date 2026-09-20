# BP7 VERDICT — why chat stalls after the first turn

**Wave:** BP7 · **Leg:** BP7-SYNTH · **Date:** 2026-09-20 · **Symptom (Joe):** SYNAPSE answers
the first message, then stops responding once you're in a conversation.

**Method:** read the four scout receipts through the JEV screen pre-read (§ Screen pre-read),
then re-derived every non-CLEAR scout from its own cited `file:line`. Where a scout's
argument met a traced line, the traced line won (brief rule; Constitution: *runtime is
truth, docs are the referee*). I fixed nothing. Verdict words: **CONFIRMED** (mechanism
traced to a line or reproduced), **REFUTED** (shown it cannot occur, with the line),
**UNKNOWN** (needs a live Houdini GUI I do not have).

Source hypotheses & ranking: `harness/battleplan/notes/SCOUT_CHAT_STALL.md`,
`harness/jev/ledger/bp7.ranking.json`.

---

## Per-hypothesis verdicts

### H1 — panel-state · UNKNOWN
Anchor: `harness/battleplan/notes/bp7_scout_H1.md` (scout header: **UNKNOWN**).
The panel arms its waiting state on send — `_waiting_for_response = True` +
`show_typing_indicator()` (`python/synapse/panel/chat_panel.py:891-892`) — and clears it in
**exactly two places**: the immediate send-failure path when the socket died between the
guard check and the send (`chat_panel.py:903-904`), and `_on_response`, which fires for any
message delivered over `response_received` including `{"status":"error"}` envelopes
(`chat_panel.py:912-915`). I re-derived and **traced** the no-recovery half the scout left
implicit: `_on_connection_error` (`chat_panel.py:964`) and `_on_status_changed`
(`chat_panel.py:944`) do **not** clear the waiting state, and the only two `QTimer`s
(`chat_panel.py:234,239`) are the context and integrity timers — there is **no response
watchdog**. And `ws_bridge.py:339-344` emits to the panel only when the inner dict carries
`"response"` or `"tier"`; any other dict is *silently dropped*. Net: if turn 2 returns no
well-formed message to the panel, the spinner hangs forever with no error. That structural
no-recovery path is confirmed to a line; what stays **UNKNOWN** — matching the scout — is
*why* turn 2 produces no message (the upstream trigger needs the GUI).

### H2 — transport · REFUTED
Anchor: `harness/battleplan/notes/bp7_scout_H2.md` (scout header: **CONFIRMED** — overturned
on trace; see *Scout-header reconciliation* below).
The scout's confirming claim is that `connected` (`ws_bridge.py:212`, `return self._ws is not
None`) stays `True` on a dead socket because "`self._ws` is NEVER set to None when the `with`
block exits." Opening the cited file to confirm that quote shows the quote was **truncated
before the block that refutes it**: `_connect_and_listen` wraps the `with connect(...)` in a
`try` whose `finally: self._ws = None` runs on **every** exit path — normal close,
`ImportError`, or any exception (`ws_bridge.py:246,277-284`). So `connected` goes `False` the
moment the socket dies, the reconnect/backoff loop restores it on success, and the *next*
send is correctly refused with `BRIDGE_DOWN_LINE` via the send-guard — i.e. the artist **does**
get feedback on subsequent sends. The specific mechanism "socket closes but connected stays
true, later sends silently lost with no feedback" **cannot occur** as described. (The
in-flight turn-2 send that gets no reply still hangs — but that is H1's panel no-recovery
path, not a stuck `connected` flag.) Traced line beats the argument.

### H4 — router · UNKNOWN
Anchor: `harness/battleplan/notes/bp7_scout_H4.md` (scout header: **UNKNOWN**).
Re-derived and the traced defects are real: the `TieredRouter` is built once and cached for
the handler's life (`handlers.py:1759-1777`) and `route()` is called with **no `try/except`
and no timeout** (`handlers.py:1787-1805`); the tier timeouts exist but are never applied —
`tier2_timeout=5.0`/`tier3_timeout=15.0` are defined (`router.py:124-125`) yet the LLM calls
`guarded_create(...)` are made **without** them (`router.py:685,893`), while only Tier 0/1
lookups pass an explicit `timeout=2.0` (`router.py:334,340`). So a hung LLM call on turn 2
blocks the whole handler until the 30 s slow-op timeout kills it, emitting no response. The
scout also *resolved* the source doc's open "VERIFY": `aliases.py:44` maps
`message`→`content`, so `resolve_param(payload,"content")` (`handlers.py:1750`) reads the
panel's `{"message": …}` correctly — not a defect. What is **UNKNOWN** — matching the scout —
is whether the LLM tier *actually* blocks on turn 2; that needs a live run. The
missing-timeout defect (a hang that cannot self-recover) is traced; the hang itself is not
reproduced.

### H6 — memory · CONFIRMED
Anchor: `harness/battleplan/notes/bp7_scout_H6.md` (scout header: **CONFIRMED**; JEV screen:
**REFEREE** — weak rows [0,1,2], crux_need 1.03, so re-derived line-by-line).
Confirmed and scoped: on a scene rebind between turns, `_repoint_router_memory(owner)` /
`_memory_owner()` (`handlers.py:1757,1785`) can reach `_adopt_scene_store()`, which builds
`MemoryStore(source, background_load=False)` (`host/memory_lifecycle.py:338-341`), and that
synchronous `_load()` takes a write lock inline (`memory/store.py:379-389`). That is a
main-thread synchronous degraded-store load that can exceed the 30 s slow-op contract — a
traced mechanism (**CONFIRMED** under the brief's "traced to a line" clause). But the
re-derivation **narrows** the scout's "blocks *or raises*": the *raises* half is refuted by
its own cited catch-sites — `_memory_owner()` swallows exceptions and returns `None` so the
handler continues (`handlers.py:1853-1858`), and `memory.search()` errors are logged and
swallowed in `enrich_context` (`routing/context_enrichment.py:91-92`). So only a true *block*
(lock held / slow parse) stalls, and only when a rebind actually fires — which the scout's own
reproduction requires (File → Save As). Whether it blocks past 30 s on live data, and whether
Joe's plain turn-2 (no scene change) hits this path at all, is **UNKNOWN** without the GUI.
This is a real latent defect, but a *conditional* match for the reported plain symptom.

### H3 — lock · not scouted: Jev-refuted
`harness/jev/ledger/bp7.ranking.json`: plausibility **0.71**, refuted **0.67**, `spawn:false`.
Pruned before scouting — the refuted signal (0.67) dominates its low plausibility. No scout
note, no verdict; recorded here for completeness.

### H5 — sidecar · not scouted: unranked
`harness/jev/ledger/bp7.ranking.json`: plausibility **0.67**, refuted **0.12**, `spawn:false`.
Pruned as the lowest-plausibility hypothesis (below the scout cut); not refuted, just
unranked. No scout note, no verdict.

---

## Most likely cause

**No hypothesis is reproduced-confirmed as the *sole* cause of the plain reported symptom**
(H2 is refuted by `ws_bridge.py:283-284`; H1 and H4 are UNKNOWN pending the GUI; H6 is
confirmed-by-trace only under a scene rebind that the symptom does not mention). Stating that
plainly is the honest verdict — the crucible's "or the doc says none was confirmed" branch.

The **most likely cause**, as a traced chain with one UNKNOWN link, is **H4 → H1**: on turn 2
the router blocks inside `route()` because the tier timeouts are defined but never enforced
(`router.py:124-125` vs `:685,893`; `handlers.py:1787` has no timeout and no `try/except`), so
the handler emits nothing until the 30 s slow-op timeout kills it — and the panel has **no
recovery path** (the spinner is cleared only by an immediate send-failure or a delivered
`response_received`, never by a disconnect, a status change, or a watchdog:
`chat_panel.py:903-904,912-915,944,964`). The result is exactly the symptom: turn 1 answers,
turn 2 spins forever with no answer and no error. The single UNKNOWN is whether the LLM tier
truly blocks on turn 2 (needs a live call); the amplifier that makes any such stall permanent
and invisible (H1) is traced and certain.

---

## Reproduce in the GUI

*(< 2 minutes; the observable that decides is called out per step)*

1. **Open the SYNAPSE panel in Houdini H22.** *Observable:* status line shows connected (no
   "Not connected to SYNAPSE" line).
2. **Send turn 1** — e.g. "scatter rocks on the ground". *Observable:* typing indicator
   appears, a reply lands, indicator clears (~1–3 s). Turn 1 works.
3. **Immediately send turn 2** — e.g. "add size variation". *Observable — this is the fork:*
   - **Hang** (H4/H1, or H6-block): typing indicator shows and **never clears**, no reply, no
     error line, input box cleared → the reported symptom.
   - **Error shown**: an error/system line appears and the indicator clears → a *raise*
     reached the panel; not the silent-hang class.
   - **"Not connected…"** (BRIDGE_DOWN_LINE): the socket dropped and `connected` went False →
     feedback path works; not H2's claimed silent loss.
4. **If it hung, wait ~35 s.** *Observable:* still hung past the 30 s slow-op budget confirms a
   server-side block + no panel watchdog (not a merely slow answer).
5. **Isolate the memory variant (H6):** restart, send turn 1, then **File → Save As** to a new
   scene, then send turn 2. *Observable:* a hang that appears *only* after the Save-As
   implicates the `_adopt_scene_store` path.

---

## Smallest fix

One file, one paragraph, no code: the smallest, highest-leverage fix is the **panel
watchdog** in `python/synapse/panel/chat_panel.py`. Arm a `QTimer` when a message is sent that,
after the server's 30 s slow-op budget, clears `_waiting_for_response`, hides the typing
indicator, and appends a "no response — try again" system line; and wire
`_on_connection_error` (`:964`) and `_on_status_changed(False)` (`:944`) to clear the same
waiting state. That single change turns every silent turn-2 hang into a **visible, recoverable**
failure regardless of which upstream trigger fired — restoring the receipts/feedback contract
this project is built on. The upstream *root* fix, so turn 2 does not block in the first place,
is to enforce the router's tier timeouts (pass `tier2_timeout`/`tier3_timeout` into the
`guarded_create` LLM calls, or wrap `route()` at `handlers.py:1787` in a handler-level
timeout) in `python/synapse/routing/router.py` + `python/synapse/server/handlers.py` — but the
panel watchdog is the first, smallest move because it makes the failure *reportable* even if
the root cause persists.

---

## What only Joe can observe

These are the UNKNOWNs — each is a click, not a guess:

- **Does turn 2's `route()` actually block? (H4)** Send turn 2 and time it; if it hangs ~30 s
  then goes silent, the LLM tier blocked. If `~/.synapse/logs/synapse.log` is on, look for a
  slow-op / timeout line at that moment.
- **Is the turn-2 response absent, or arriving-and-dropped? (H1 trigger)** A breakpoint or log
  at `ws_bridge.py:339` on turn 2 shows whether an inner dict arrives lacking
  `"response"`/`"tier"` (silently dropped) or nothing arrives at all (handler killed).
- **Does a raise surface as an error envelope?** `handlers.py:1787` has no local `try/except`;
  whether a `route()` exception reaches the panel as `{"error": …}` (which *would* clear the
  spinner) or vanishes depends on the live dispatch wrapper — observable only at runtime.
- **Is a scene rebind the trigger? (H6)** The File → Save As step above; a hang that appears
  only after it points at the memory adopt path.

---

## Screen pre-read

The `python harness/jev/jev_screen.py --wave bp7` brief lines, verbatim:

```
leg            receipt  screen   crux             reason
BP7-MEMORY     green_wi REFEREE  -                weak rows [0, 1, 2]; crux_need 1.03
BP7-PANEL      -        no receipt -
BP7-ROUTER     -        no receipt -
BP7-SYNTH      -        no receipt -
BP7-TRANSPORT  -        no receipt -
-- ledger: harness/jev/ledger/bp7.shadow.screen.jsonl
-- read: a FLAG beside a crux BROKEN, and CLEAR/REFEREE beside SOUND*, is agreement
```

Ledger brief_line for the one screened leg (`harness/jev/ledger/bp7.shadow.screen.jsonl`),
verbatim: `screen BP7-MEMORY: REFEREE - full read; weak rows [0, 1, 2]; crux_need 1.03`.

Per scout, whether my read agreed:

- **BP7-MEMORY (H6) — screen REFEREE.** The screen told me to do a full re-read rather than
  trust the header; I **agree with the caution**. Re-derivation kept the header word
  **CONFIRMED** but narrowed it (the *raises* half is refuted by caught-exception lines; the
  mechanism is the *blocking* main-thread load on a scene rebind). Screen agreement: yes.
- **BP7-PANEL (H1) — no receipt** (the scout's receipt is on `bp7/panel`, not on my branch, so
  the screen could not classify it). Re-derived from cited lines → **UNKNOWN** overall, with
  the no-recovery half traced-confirmed. My read agrees with the scout's header.
- **BP7-ROUTER (H4) — no receipt.** Re-derived → **UNKNOWN**; agrees with the scout's header.
- **BP7-TRANSPORT (H2) — no receipt.** Re-derived → **REFUTED**; I **disagree** with the
  scout's CONFIRMED header (traced refutation `ws_bridge.py:283-284`).
- **BP7-SYNTH — no receipt** (this leg; expected — the receipt is written last).

Because three of the four scouts printed "no receipt" (their receipts never landed on
`bp7/synth`), none were marked CLEAR, so I re-derived **all four** from their cited lines
rather than spot-checking any — the more conservative path.

---

## Scout-header reconciliation

One paragraph's verdict word intentionally diverges from its scout note's header, and I
surface it here rather than hide it: **H2** is written **REFUTED** while
`bp7_scout_H2.md` is headed **CONFIRMED**. This is a conscious override on traced evidence —
`ws_bridge.py:283-284` (`finally: self._ws = None`) refutes the scout's confirming quote,
which was truncated before that block — per the brief's "the one with a traced line wins over
the one with an argument" and the Constitution's "runtime is truth, docs are the referee." It
means crucible criterion #1 ("every hypothesis paragraph's verdict word matches its scout
note's VERDICT header") is **not satisfied for H2, by design**. Rubber-stamping H2 as
CONFIRMED would send Joe to fix a non-bug in the transport while the real defect (H1/H4)
festers — precisely the "green light that cannot report failure" this wave exists to make
unshippable. Flagged for Joe's ruling in the receipt's `for_ruling`.
