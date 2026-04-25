# Spike 3.0 — PDG API Audit (Empirical)

> **Authority:** ARCHITECT scaffold (this doc) + Joe (operator, live
> Houdini). The script ``spike_3_0_pdg_audit_script.py`` runs inside
> graphical Houdini 21.0.671; this doc is the receiving vessel for
> its output. Spike 3.0 closes when Joe runs the script and pastes
> findings into §2–§4 below.
>
> **Status:** Pre-execution. Script written; audit not yet run.
>
> **Sprint position:** Spike 3.0 is BLOCKING — Spike 3.1
> (TopsEventBridge) does not open until §4 is filled in. Anchors:
> ``CONTINUATION_INSIDE_OUT_TOPS.md`` § Hard API verification gate;
> Sprint 3 hard invariant #6.

---

## 0. Audit metadata

| Field | Value |
|---|---|
| Audit run | _Joe fills in: 2026-MM-DD HH:MM (UTC)_ |
| Houdini build | _Joe confirms: 21.0.671_ |
| Python version | _from script banner — should be 3.11.x_ |
| Operator | Joe Ibrahim |
| Script run | ``docs/sprint3/spike_3_0_pdg_audit_script.py`` |
| Full report file | _file path printed at end of script — paste here_ |

---

## 1. Why this audit exists

Houdini 21.0.671 has known divergences from prior versions and from
external-LLM training data. The codebase has already pinned three:
``componentbuilder`` is not a native HDA, ``hou.secure`` is absent
(env-var fallback documented in ``spike_2_4_design.md`` §8), and
light nodes use ``xn__`` parameter prefix encoding.

The PDG / TOPs surface has its own divergences. ``shared/bridge.py:568``
records one:

> *H21 moved PDG events from ``hou.pdgEventType`` to the standalone
> ``pdg`` module. Cook events use ``pdg.GraphContext.addEventHandler``
> with ``pdg.PyEventHandler`` instead of ``hou TopNode.addEventCallback``
> (which handles ``hou.nodeEventType``).*

The early ``TopsEventBridge`` sketch in
``CONTINUATION_INSIDE_OUT_TOPS.md`` (lines ~186–280) reaches for
``hou.pdg.scheduler``, ``hou.pdg.workItem``, and
``hou.pdg.GraphContext``. The R8 implementation in ``bridge.py``
reaches for **standalone ``pdg``** instead. Until this audit
resolves which surface is real for what, Spike 3.1 cannot land code
that survives first contact with Houdini.

Sprint 3 hard invariant #6:

> *Hard API verification before any Houdini call: ``dir()``
> introspection in live Houdini 21.0.671 first, blueprint code
> second.*

---

## 2. Resolved surfaces

For each section: paste the corresponding block from the audit
report file directly under the fence. Don't edit; raw output **is**
the audit. Annotations belong in §3.

### 2.1 hou.pdg surface
```
[paste output here]
```

### 2.2 Standalone `pdg` module surface
```
[paste output here]
```

### 2.3 Scheduler surfaces — `hou.pdg.scheduler`, `pdg.Scheduler`, `pdg.SchedulerType`
```
[paste output here — all three blocks from §2 of the report]
```

### 2.4 WorkItem surfaces — `hou.pdg.workItem`, `pdg.WorkItem`
```
[paste output here]
```

### 2.5 Event subscription API
Captures: ``pdg.PyEventHandler``, ``pdg.EventType`` (enum members),
``pdg.EventHandler``, ``pdg.PyEventCallback``.

```
[paste output here — all four blocks from §4 of the report]
```

### 2.6 Callback registration shape
Captures: ``pdg.GraphContext``, ``hou.pdg.GraphContext``,
``hou.topNodeTypeCategory``.

```
[paste output here]
```

### 2.7 Cook lifecycle event types
Cross-reference §2.5 ``pdg.EventType`` plus ``hou.nodeEventType``
(node-level parallel) and ``hou.pdgEventType`` (legacy — confirm
absent).

```
[paste output here]
```

### 2.8 Auxiliary surfaces
``hou.topNodeTypeCategory``, ``hou.hipFile``, ``hou.hipFileEventType``,
``hou.hipFile.addEventCallback`` probe.

```
[paste output here]
```

---

## 3. Anomalies / surprises / gotchas

> Joe fills after running the audit. The watchlist below seeds the
> things to LOOK FOR — confirm or refute each against captured output.

| Hypothesis | Confirmed? | Spike 3.1 impact if true |
|---|---|---|
| ``hou.pdg`` is thin/empty — real PDG surface lives under standalone ``pdg`` | _y/n_ | Bridge sketch must rename every ``hou.pdg.*`` reference. |
| ``hou.pdg.GraphContext`` does not resolve — must reach via ``top_node.getPDGGraphContext()`` (R8 pattern, ``bridge.py:616``) | _y/n_ | Bridge sketch's class-import path is wrong; instance-method path is correct. |
| ``hou.pdgEventType`` does not exist — superseded by ``pdg.EventType`` | _y/n_ | Confirms ``bridge.py:568`` doc string empirically. |
| ``event.workItem.attribValue("frame")`` — ``attribValue`` is the right method name | _y/n_ | Sketch's frame-read works as written. |
| ``event.workItem.expectedResultData`` is iterable, each element has ``.path`` | _y/n_ | Sketch's outputs-read works as written. |
| ``event.workItem.cookDuration`` exists; unit is seconds (sketch multiplies by 1000) | _y/n_ | Sketch's duration calc works as written. |
| ``hou.hipFile.addEventCallback`` returns a removable handle | _y/n_ | Sketch's cleanup (``self._scene_callback_handle = ...``) works. |
| ``hou.hipFileEventType.AfterLoad`` spelled exactly that way | _y/n_ | Sketch's ``_on_hip_event`` switch works. |
| ``hou.topNodeTypeCategory`` is callable (returns category) vs already-a-category attribute | _y/n_ | Sketch calls it as ``hou.topNodeTypeCategory()`` — wrong shape if it's an attribute. |

**New findings** (anything not in the watchlist):

| Finding | Severity | Spike 3.1 impact |
|---|---|---|
| | _info / warn / blocking_ | |

---

## 4. Implications for Spike 3.1 TopsEventBridge design

> Joe fills after audit. Each row names a specific change to the
> bridge sketch in ``CONTINUATION_INSIDE_OUT_TOPS.md`` (lines ~186–280).

### 4.1 Required imports & call shapes

| Sketch reference | Verified shape | Action |
|---|---|---|
| ``hou.pdg.scheduler`` | _e.g. ``import pdg; pdg.Scheduler``_ | _e.g. rename + add ``import pdg``_ |
| ``graph_context.addEventHandler(handler)`` | _Joe pastes signature_ | _e.g. pin to 2-arg ``addEventHandler(handler, EventType)`` per ``bridge.py:637``_ |
| | | |

### 4.2 Event payload contract

The sketch's ``_on_workitem_complete`` reads four fields. Each must
trace to a real attribute:

| Field read | Verified attribute | Type | Notes |
|---|---|---|---|
| ``event.workItem`` | | | |
| ``.node.path()`` | | | |
| ``.attribValue("frame")`` | | | |
| ``.expectedResultData`` (+ ``f.path`` per element) | | | |
| ``.cookDuration`` | | seconds (sketch ×1000) | |

### 4.3 Cleanup contract

| Sketch behaviour | Verified shape | Action |
|---|---|---|
| ``hou.hipFile.removeEventCallback(handle)`` | | |
| ``graph_context.removeEventHandler(handler)`` | _bridge.py:664 already uses_ | _confirm via audit_ |

### 4.4 Open questions for orchestrator / next ARCHITECT pass

1.
2.

---

## 5. Sign-off

Spike 3.0 closes when **all** of the following are true:

- [ ] §0 metadata filled in
- [ ] §2.1–§2.8 all contain real audit output (no
      ``[paste output here]`` placeholders remain)
- [ ] §3 watchlist confirmed/refuted row-by-row, plus any new
      findings recorded
- [ ] §4 implications complete enough that Spike 3.1's ARCHITECT
      pass can write a design against verified surfaces
- [ ] No surfaces flagged "blocking" remain unresolved (or if any
      are, an open question is logged in §4.4)

Once all five boxes are checked, Spike 3.1 design opens.

*End of audit document. Script: ``spike_3_0_pdg_audit_script.py``.*
