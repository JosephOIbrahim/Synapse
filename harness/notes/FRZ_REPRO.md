# FRZ — attributed freeze repro protocol

**Leg:** FRZ (freeze attribution) · **branch** `finish/freeze-attribution` · **base** `1f18ab46`
**Status of this document:** protocol only. **Nothing in it has been executed.**

> **Not observed.** Every number this protocol can produce requires a human at the
> Houdini GUI. This leg ran headless: it built the instrument, proved the instrument
> records and reports in a plain-Python harness, and wrote these steps. It did **not**
> reproduce the freeze and does not claim to have. Any statement below in the future
> tense is a prediction, not a result.

---

## What this measures

When you send a prompt from the SYNAPSE panel, Houdini's node-interaction surface
freezes for a tight 5–6 second band and then recovers. This protocol answers one
question: **which layer held the main thread.**

It answers it by elimination, on a ladder. Before this leg, the ladder had a hole —
the Qt slots that render a reply had zero timing, so "the cost is somewhere in the
panel" was as precise as anyone could get. Rung 5 is new.

| Rung | Layer | Reading it high means |
|---|---|---|
| 1 | worker→main wake latency (`dispatch_wait`) | main was **already** busy with something else |
| 2 | `run_on_main` fast path 2 — inline `fn()` on main | a payload ran inline on the GUI thread |
| 3 | deferred payload **hold** on main (OCC) | a marshalled tool payload occupied main — `slowest_label` names it |
| 4 | panel inline **tool** dispatch (Qt slot) | the full inline tool dispatch |
| 5 | **result path** — `send` / `stream` / `finalize` / `append` / `review` | rendering the reply held the GUI thread |

**The first rung showing a hold in the band is the attribution.**

---

## Before you start

1. Houdini **22.0.368** running, with the SYNAPSE panel open (the Python Panel
   registered by `houdini/python_panels/synapse_panel.pypanel`).
2. This branch's `python/` on the session's path — the rung-5 instrument does not
   exist on `master`.
3. A conversation with **some history in it**. Rung 5's costs scale with document
   size and conversation length; a cold first prompt is the *least* likely to
   reproduce. If you can, reproduce on a session that has already been used.

No env var is required. The guard defaults to `warn`, which is the mode this
protocol assumes. Do not set `SYNAPSE_MARSHAL_GUARD=off` — that silences the log
lines, though the counters still record.

---

## The one command

In Houdini's **Python Shell**:

```python
exec(open(r'C:\Users\User\SYNAPSE\scripts\frz_probe.py').read())
```

**Run that exact line twice.**

- **First run — ARMS.** Zeroes every main-thread histogram and stamps a marker.
  It prints `[frz] ARMED` and lists what it zeroed.
- **Then send ONE prompt in the panel** and let the freeze happen. Don't touch
  anything else — every extra interaction adds samples that muddy attribution.
- **Second run — REPORTS.** Prints the attribution ladder and writes it to
  `<SYNAPSE_ROOT>/.synapse/frz_report.txt`, `fsync`'d so it survives a force-kill.
  It then disarms, so running the line a third time starts a fresh window.

**Why twice instead of a timer.** A `QTimer` auto-report would post work to the very
event loop under investigation. Arm/report adds nothing to the main thread while the
freeze is happening.

---

## What you'll see

A table. The `<<<` marks any rung over 1000 ms:

```
  rung        layer                                            max_ms   count
  ----------------------------------------------------------------------------
  1           worker->main WAKE latency (dispatch_wait)           0.0       0
  2           run_on_main fast path 2: inline fn() on main        0.0       0
  3           deferred payload HOLD on main (OCC)                 0.0       0
  4           panel inline TOOL dispatch (Qt slot)                0.0       0
  5.send      result path: send                                   0.0       0
  5.stream    result path: stream                                 0.0       0
  5.finalize  result path: finalize                            5840.0       1  <<<
  5.append    result path: append                              5610.0       1  <<<
  5.review    result path: review                                 0.0       0
```

*(That sample is **synthetic** — produced by injecting two fake durations to prove
the report renders and attributes. It is not a measurement of the real freeze.)*

Then a `GUARD:` line (mode, budget, violation and overrun counts) and, if anything
crossed the 5 s inline budget, the ledger entries naming the phase.

---

## Reading the result

**If exactly one rung is hot** — that is the attribution. Record the rung, the
`max_ms`, and the payload/document sizes printed beside it.

**If rung 5 is hot** — the leading hypothesis is confirmed and you now have the
scaling law: compare `doc_chars_at_max_ms` across two runs at different conversation
lengths. If duration tracks document size, the cost is Qt rich-text re-layout, and
the fix is architectural (bounded document, incremental append), not a timeout.

**If rung 3 is hot** — a tool payload is the cost, and `slowest_label` names the
tool. That contradicts the current reading of the evidence and is worth escalating.

**If NOTHING is over 1000 ms and you still saw the freeze** — that is a **result,
not a failed run.** It means the cost is outside all Python instrumentation: native
Qt layout, a Houdini cook, or a C-level call. Report that plainly. Do not re-run
until a number appears — the honest negative is the finding, and this leg's constant
hunt already predicts it is a live possibility.

---

## Two things to check while you are at the GUI

Both are main-thread work this leg found but did **not** instrument, because both
sit outside the result path the brief scoped:

1. **`agent_health.py:71`** — `_find_bridge_instance` caches only a *positive*
   lookup. While no bridge exists, a 4-second `QTimer` walks the **entire Python
   heap** (`gc.get_objects()`) on the main thread, forever. Heap size is roughly
   constant within a session, so its duration is roughly constant too — which is
   the one mechanism found that would produce a **tight band without any timeout
   being involved.** Check whether the panel feels sticky *without* sending a
   prompt. If it does, this is a stronger suspect than anything on the result path.

2. **`synapse_panel.py:2342`** — the 2-second context timer reads `hou.frame()`,
   `hou.selectedNodes()`, `hou.hipFile.basename()` **inline on the main thread**,
   unmarshalled — while `ws_bridge.gather_context_off_main` exists specifically to
   do that read off-main and the live panel does not use it.

---

## If the probe reports nothing usable

| Symptom | Meaning | Do this |
|---|---|---|
| `[frz] zeroed: NOTHING` | `synapse` is not importable in this session | Confirm the panel is open and this branch is on the path. The probe deliberately refuses to produce a report it cannot ground. |
| `WARNING: synapse.panel.tool_executor unavailable` | Qt not importable — expected **outside** Houdini, wrong **inside** it | Inside Houdini this means the panel failed to load. Rung 4 will read zero and must not be trusted. |
| Report shows `count 0` everywhere | The window captured no turn | You likely ran the line twice without sending a prompt between. Run again and send a prompt in between. |
| Second run arms instead of reporting | The state file was removed | Re-arm, send a prompt, report. |

---

## Related, deliberately not merged into this protocol

`scripts/freeze_trace.py` is the older, complementary tracer: it wraps the
**tool-execution** path with ENTER/EXIT logging, so a *hard* freeze (one that never
recovers) is located by the last `ENTER` with no matching `EXIT`. Use that one when
Houdini never comes back. Use `frz_probe.py` — this one — when it freezes and then
**recovers**, which is the 5–6 s band case, because a recovered freeze leaves
durations in histograms rather than a truncated log.
