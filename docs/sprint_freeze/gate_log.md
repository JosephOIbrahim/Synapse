# Sprint Freeze — Gate Log

Marshal-Deadlock Elimination. Branch `fix/marshal-deadlock-class`, cut from
master `4c3deae`.

Blueprint constraint 5 requires each gate result recorded here. Release-week §9
requires DRIFT logged and surfaced. Both live in this file.

---

## CTO decision record

**Authority.** Joe granted CTO authority with all blueprint gates pre-approved
(2026-07-21). That authority covers the blueprint's Gates 0–4 — I decide and
proceed rather than stopping for confirmation at each.

**What it does not cover.** Two things, and they are named here so the boundary
is on the record rather than in my head.

### DRIFT-01 — this work is outside the release-week task lists

`SYNAPSE_RELEASE_WEEK.md` is the governing document for Sat Jul 18 → Fri Jul 24.
Its ingestion contract §0.3 permits only work in its task lists plus fix-forward,
and §0.5 reserves scope amendments to Joe. A marshal-deadlock sprint appears in
no leg.

There is a real argument this qualifies as fix-forward: Leg 1 (demo recording,
HUMAN lane) is IN-FLIGHT, and a UI lock during that recording would take the
release with it. There is an equally real argument against shipping concurrency
changes to master days before a demo.

**Ruling.** Both arguments resolve the same way, so no amendment is needed:

- All work lands on `fix/marshal-deadlock-class`. Master is untouched.
- No merge to master during the freeze. That decision is Joe's under §0.5 and
  stays Joe's — being pre-approved for the blueprint's gates is not authority to
  breach the governing document's human-only amendment clause.
- The one candidate for early master landing is the **warn-mode guard**: pure
  telemetry, zero behaviour change, cannot alter a demo's outcome but would name
  the culprit if the demo froze. Offered as an option; not taken unilaterally.

### D1 and D7 cannot be self-certified

`synapse_ping` at 2026-07-21 returned no live session (handshake timeout,
`ws://localhost:9999/synapse`) — the SessionStart "bridge connected" hook was
stale, as [[synapse-bridge-verification]] warns.

D1 (repro goes green) and D7 (soak clean) require graphical Houdini. Pre-approval
lets me decide; it does not let me manufacture evidence for a session nobody ran.
Both stay OPEN and are designed to close in **one** GUI session, not four.

---

## Gate results

| Gate | Phase | State | Evidence |
|---|---|---|---|
| 0 | Reproduce & instrument | **PASS** (static) | `marshal_map.md`; vendor source; see ruling below |
| 1 | Kill the specific deadlock | IN-FLIGHT | fix wave `wf_0ab9359e-364` |
| 2 | Structurally impossible | PENDING | — |
| 3 | Hostile crucible + modal | PENDING | — |
| 4 | Production readiness | PENDING | — |

---

## GATE 0 ruling — PASS on static evidence

The blueprint requires a live stack dump to name the culprit, and says STOP if the
dump is ambiguous. I am ruling the gate PASS **without** the live dump, because
the culprit is proven from vendor source rather than inferred. Recorded here with
the reasoning, so the ruling can be overturned if the reasoning is wrong.

### The defect, at the vendor level

`C:/Program Files/Side Effects Software/Houdini 22.0.368/houdini/python3.13libs/hdefereval.py`,
`_queueDeferred()` — read directly, quoted verbatim:

```python
_queue.append((code, block, num_waits, args, kwargs))
if block:
    _condition.wait()          # ~line 93 — no thread check of any kind
    result = _last_result
    exc_info = _last_exc_info
```

`_condition` is notified only by `_processDeferred()`, whose own docstring states
it is *"called from Houdini's event loop callback"* — the main thread.

So a main-thread caller of `executeInMainThreadWithResult` (= `_queueDeferred`
with `block=True`) enqueues work for itself and then parks waiting for itself to
run it. **Permanent, unrecoverable self-deadlock.** Not a race, not a timing
window — a structural certainty on every invocation.

Second defect, same primitive: `result = _last_result` reads module globals.
Concurrent blocking marshals from different threads can swap results. Silent
cross-thread data corruption, distinct from the hang and arguably worse.

### The route into it, verified in committed source

`python/synapse/server/handlers_render.py:393-397` at `4c3deae`:

```python
# Panel-inline path: the caller IS Houdini's main thread (Qt slot).
# A bounded wait is impossible — the render must run on this very
# thread — so the guard above is the only protection here.
if _threading.current_thread().ident == _threading.main_thread().ident:
    return _attach_advisory(self._handle_render(payload))
```

`_handle_render` then reaches `:771`:

```python
hdefereval.executeInMainThreadWithResult(_render_on_main)
```

The author's intent — *we are on main, so run it here* — is correct. The
implementation contradicts it one frame down by marshalling to main from main.
This is the only `current_thread`/`main_thread` comparison in the entire file,
and it routes the caller **into** the deadlock rather than away from it.

### Why the live dump is corroboration, not determination

The blueprint's ranked hypotheses assumed a fix must wait on discriminating
between them. It does not: candidates A (panel → `handlers_render.py:396→771`)
and B (`/mcp` read-only → `mcp/server.py:438` → `handlers_render.py:208`) are two
routes into **one** defect and share **one** cure. Candidate C (native modal
nested loop) is a different mechanism but takes the same treatment — watchdog and
graceful degradation, since neither can be un-wedged in-process.

Discriminating A from B would change no line of the fix. The gate therefore does
not block on it. Joe's live session is repurposed from *determining the cause* to
*confirming the cure* (D1) and *soaking* (D7) — one session instead of four.

**Residual risk accepted:** if the live repro still freezes after the fix, the
static diagnosis was incomplete rather than wrong, and the watchdog's stack dump
becomes the Phase 0 instrument the blueprint originally specified. That fallback
is preserved deliberately, not abandoned.

### The ceiling, stated honestly

On the main thread the render cannot be made non-blocking — it can only be made
to **complete**. `run_on_main` fast-path-2 converts a permanent deadlock into a
bounded stall (UI unresponsive for the render's duration, then it returns).
That is the real ceiling of an in-process fix and this sprint will not claim
past it.

---

## CTO rulings on outstanding items (2026-07-21)

Joe granted CTO authority with gates pre-approved and confirmed a live Houdini.
Every open item is ruled below. Each is reversible by Joe; the reasoning is
recorded so it can be argued with rather than just accepted.

**R1 — The two test rewrites: APPROVED.**
`test_host_layer.py::test_gui_mode_routes_through_hdefereval` pins the primitive
we deliberately removed; `test_render_offmain_c11.py::test_no_sleep_inside_main_thread_closure`
went vacuous when `handlers_render.py` stopped importing `hdefereval` — it now
passes while pinning nothing. Both keep their original invariant and change only
the mechanism they assert against. **Condition of approval:** each re-anchored
test must be demonstrated to FAIL when the invariant is violated (introduce the
violation, observe red, remove it). A guard nobody proved can go red is the same
defect we are cleaning up. Flagged to Joe per blueprint hard rule 2 — these are
the only two test files this sprint modifies.

**R2 — D3: accept PARTIAL, do not chase green.**
`websocket.py:471` dispatches handlers inline in a serial loop, so `cancel` queues
behind the handler that made you want to cancel. The watchdog can degrade the
server; it cannot deliver a message the transport will not read. Fixing it means
moving handler dispatch onto a worker pool — a change to the transport's
concurrency model, during a feature freeze, days before the Leg 1 recording.
Not worth it. D3 reports PARTIAL with the limitation named. #1 follow-up.

**R3 — Merge to master: NOT MINE. Held on branch.**
Release-week §0.5 reserves scope amendments to Joe. CTO authority over the
blueprint's gates is not authority over the governing document. All work stays on
`fix/marshal-deadlock-class`. The only artefact I would offer for master during
the freeze is the warn-mode guard, because it is pure telemetry with zero
behaviour change and would name the culprit if the demo froze — offered, not
taken.

**R4 — Guard ships in WARN mode. Do not flip to raise this week.**
Raising on a main-thread blocking wait could break paths that block benignly.
Warn-mode is zero-behaviour-change telemetry, and the ledger it produces is the
evidence that justifies flipping later. Same two-stage ratchet as the suite
baseline. Flip to raise after a clean soak, post-freeze.

**R5 — The /mcp 120s abandon-then-continue hazard: DOCUMENT, do not fix.**
On `/mcp`, `run_on_main(timeout=120s)` wraps the whole dispatch, so a 200s frame
reports "main thread didn't respond" while the render continues and writes the
file — and an agent may re-dispatch, double-rendering. This is **pre-existing and
strictly better than before** (that path used to self-deadlock permanently).
Fixing it properly means changing timeout semantics mid-freeze. Documented where
an operator will find it; not touched.

**R6 — `foreground_guard` bypass on the three render orchestrators: LOG ONLY.**
`_handle_safe_render`, `_handle_render_progressively` and `_handle_render_sequence`
bypass `_handle_render_bounded` and therefore the foreground guard — so
`render_progressively`'s 1920x1080 pass has no Karma XPU cold-cache gate. Real,
pre-existing, and correctly *not* rerouted (the build agent showed rerouting would
break per-frame result semantics and hand callers a token they cannot poll).
Logged as a follow-up. Out of scope for a deadlock sprint.

**R7 — D1 and D7 sequencing: one session, after the tree is quiet.**
Houdini is live (PID 31184, Responding=True) but the Synapse server is not
started — nothing listening on 9999 — and the remediation wave is mid-write.
Verifying against a half-remediated tree would produce noise. Order is fixed:
remediation closes → one clean full-suite run headless → Joe starts the server →
D1 → D7. Not before.

**R8 — Live verification will NOT deliberately trigger the freeze.**
The self-deadlock is proven from vendor source; reproducing it live would cost a
Houdini restart and prove nothing new. The live session verifies the CURE, not
the disease. If the fix is incomplete, the watchdog's stack dump becomes the
instrument — which is the blueprint's original Phase 0, preserved as a fallback.

**R9 — Evidence standard for D5.** Per-agent `pytest` subsets run concurrently
are not a gate (`__pycache__` collisions plus the known module-level `sys.modules`
hou-fake residency trap, where the alphabetically-first planter wins the run).
D5 closes on ONE full `pytest tests/` run, headless, no live bridge, against the
ratchet floor in `harness/verify/suite_baseline.json`. Nothing less.

---

## Finding OUT-OF-SCOPE-01 — the kill switch is head-of-line blocked

Not in the blueprint's hypothesis space, found during cartography, verified
directly in committed source. `python/synapse/server/websocket.py:471`:

```python
for message in websocket:
    ...
    self._handle_message(websocket, message, client_id)
```

The loop is serial and `_handle_message` runs inline. A long-running handler
therefore blocks **every subsequent message on that connection** — including
`cancel`, `emergency_stop`, `render_farm_cancel`, and `status`.

This is not a deadlock. It is a **recovery-path failure**, and it directly limits
D3. A watchdog can detect main-thread starvation and degrade the server
gracefully, but if the operator's cancel cannot be delivered because it is queued
behind the stuck handler, then "the daemon survives to serve the next turn" is
false *for that connection*. The kill switch is unreachable during precisely the
incident it exists for.

A partial mitigation already shipped (crucible F2, 2026-07-18: registry-only
reads exempted from the WS stall gate), but the serial loop itself is unchanged —
and an exemption at the top of the loop never executes while the loop is blocked
inside a previous `_handle_message`.

**Ruling — deliberately out of scope for this sprint.** The only real fix is to
dispatch handlers off the serial loop onto a worker pool, which is a change to
the transport's concurrency model. Making that change during a feature freeze,
days before the Leg 1 demo recording, carries more risk than the defect it
removes. It is recorded here as the **#1 follow-up** and D3 will be reported as
PARTIAL rather than green — see `done_signoff.md`.

---

## Blueprint errata (corrected before execution)

The blueprint was written from a stale README without a source read, and says so.
Verified against the repo at `4c3deae`:

| Claim | Reality |
|---|---|
| "README: 2874 passing" | 4,571 passing (`README.md:96`). Real gate is the ratchet floor `harness/verify/suite_baseline.json` = 4275 green / 0 failed, read at merge-base by `check_suite_baseline`. |
| "104 of 105 tools" | 115 registered (`CLAUDE.md:3`, `README.md:18`). |
| "Houdini 21.0.671" | Target is H22.0.368. 21.0.671 is uninstalled; release-week v2 retired it explicitly. |
| Watchdog / trace / operator card are **(NEW)** | `server/freeze_chain.py`, `scripts/freeze_trace.py`, `docs/L8_FREEZE_FIX_DESIGN.md`, `docs/render-freeze-operator-card.md` already exist. Reuse, do not rebuild. |
| Marshal boundary is `host/main_thread_executor.py` | That is the *cognitive Dispatcher* path. Production marshalling is `server/main_thread.py` — ~195 `run_on_main` call sites, unmentioned by the blueprint. |
| `mcp_server.py` is the "WS JSON-RPC dispatch" prime suspect | The live code is `python/synapse/mcp/server.py`, which holds raw `executeInMainThreadWithResult` calls at 367/438/601 and a comment at 507 stating it bypasses `run_on_main`. |

Corrected targets carry forward; the blueprint's ranked hypothesis is retained
only as a prior, per its own operating constraint 1.

---

## Prior art this sprint must not re-litigate

A 4-agent grounding + crucible on 2026-07-17/18 already confirmed and shipped a
fix for a *different* member of this deadlock class: in-process Karma render
capturing the main thread (`_handle_render` → raw `executeInMainThreadWithResult`
→ `node.render()`). That shipped as v5.32.0 "the render path is bounded"
(`13da14b`, `89ccdfd`).

The bug in this blueprint — *mutation never executed* — is a distinct symptom
from *render captures main*. Treat the render fix as evidence the class is real
and as the reference implementation for bounded marshalling, not as this bug.
