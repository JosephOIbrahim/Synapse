# Spike 3.2 — Scene-Load API Audit (Empirical)

> **Authority:** ARCHITECT scaffold (this doc) + Joe (operator, live
> Houdini). The script ``spike_3_2_scene_load_audit_script.py`` runs
> inside graphical Houdini 21.0.671; this doc is the receiving vessel
> for its output. Spike 3.2's auto-warm scaffold cannot be designed
> until § 3 (thread-context probe) is filled in.
>
> **Status:** PRE-STAGE — script drafted, audit not yet run. § 3 is
> LOAD-BEARING and gates the Spike 3.2 design pass.
>
> **Sprint position:** Spike 3.1 (TopsEventBridge scaffold + hostile
> suite) shipped at commits ``89da296`` (scaffold) and ``bb2713b``
> (hostile suite). Spike 3.2 (auto-warm on scene load) opens once this
> audit lands. Anchors: ``CONTINUATION_INSIDE_OUT_TOPS.md`` § Hard API
> verification gate; Sprint 3 hard invariant #6.

---

## 0. Header (operator fills after audit run)

| Field | Value |
|---|---|
| Audit run | _<TIMESTAMP — printed by script header>_ |
| Houdini build | 21.0.671 _(verify with ``hou.applicationVersionString()``)_ |
| Python version | _<operator fills — printed by script header>_ |
| Operator | Joe Ibrahim |
| Script run | ``docs/sprint3/spike_3_2_scene_load_audit_script.py`` |
| Full report file | _<operator fills — script prints exact path>_ |
| Audit summary | _<operator fills — N resolved · M missing · E errors>_ |
| Probe finalization | _<operator fills — `event_captured` / `timeout` / `manual_abort`>_ |
| Events captured | _<operator fills — count printed in second summary>_ |

### Why this audit exists

Houdini 21.0.671 has known divergences from prior versions and from
external-LLM training data. Spike 3.0's PDG audit pinned six wrong
references in the early bridge sketch — every ``hou.pdg.*`` path missing,
``hou.hipFile.addEventCallback`` returning ``None`` (not a removable
handle), ``pdg.PyEventCallback`` being the wrong name. Each of those
would have crashed first contact with Houdini if Spike 3.1 had coded
against the sketch verbatim.

Sprint 3 hard invariant #6:

> *Hard API verification before any Houdini call: ``dir()``
> introspection in live Houdini 21.0.671 first, blueprint code second.*

Spike 3.2's auto-warm scaffold needs the scene-load surface verified
before any code lands. Five questions, one of them load-bearing:

1. **§ 1.** What does ``hou.hipFile.addEventCallback`` actually return
   when you call it? Spike 3.0 § 3.1 already refuted the
   "removable handle" hypothesis on dir() inspection alone; this audit
   re-confirms by **calling** the function and recording the runtime
   return value in the scene-load scenario specifically.

2. **§ 2.** Which ``hou.hipFileEventType`` member fires during a fresh
   File → Open? Spike 3.0 § 2.9 confirmed ``AfterLoad`` exists. This
   audit enumerates the full member set with integer values so Spike 3.2
   can hard-code constants the same way ``tops_bridge.py:78–90`` does
   (``_EVT_COOK_COMPLETE = 14`` etc.).

3. **§ 3 — LOAD-BEARING.** What thread does the AfterLoad callback
   fire on? Never previously verified. If main thread → auto-warm
   scaffold can call ``hou.*`` directly. If worker thread → every
   reaction must marshal through ``hdefereval``. The bridge design
   changes either way; only one path is right and it is empirical.

4. **§ 4.** Does ``addEventCallback(fn) + addEventCallback(fn)`` register
   once or twice? Determines whether Spike 3.2 must guard against
   double-subscription with an explicit bool flag or whether the API
   self-deduplicates by callback identity.

5. **§ 5.** Aux surfaces — ``hou.hipFile.path()``,
   ``hou.applicationVersionString()``, ``hou.hipFile.removeEventCallback``,
   the ``hou.hipFile`` namespace — captured for context completeness so
   the design pass has every surface verified up front.

---

## 1. hou.hipFile.addEventCallback surface

> Receiving vessel for the script's § 1 output. Paste the raw
> ``### 1.1 …`` and ``### 1.2 …`` blocks from the report file directly
> below this line. Annotations belong in § 6 / § 7.

_<paste § 1 here>_

---

## 2. hou.hipFileEventType enum members

> Receiving vessel for the script's § 2 output. Paste the raw
> ``### 2.1 …`` block from the report file directly below this line.

_<paste § 2 here>_

---

## 3. Thread-context probe results — LOAD-BEARING

> Receiving vessel for the script's § 3 output. **This section gates
> Spike 3.2 design.** Until thread context is empirically known, the
> auto-warm scaffold cannot decide between direct ``hou.*`` calls vs
> ``hdefereval`` marshaling — and that decision is structural, not
> cosmetic.

_<paste § 3 here>_

### 3.1 Implication summary (operator fills after paste)

| Question | Answer | Evidence |
|---|---|---|
| Did AfterLoad fire? | _<yes / no / timeout>_ | _<event N from § 3 capture sequence>_ |
| Thread name | _<MainThread / worker-N / …>_ | _<info from event>_ |
| ``is_main_thread`` | _<True / False>_ | _<info from event>_ |
| Other events captured before AfterLoad | _<list or "none">_ | _<§ 3 sequence>_ |
| Unsubscribe result | _<ok / error>_ | _<§ 3 unsubscribe field>_ |

### 3.2 Spike 3.2 scaffold decision

_<operator fills — pick one and explain in one sentence:_
_— "Main thread confirmed → scaffold calls hou.\* directly, no marshaling"_
_— "Worker thread → scaffold marshals every hou.\* call through hdefereval"_
_— "AfterLoad never fired → re-run audit before opening Spike 3.2 design">_

---

## 4. Callback identity / removal behavior

> Receiving vessel for the script's § 4 output. Paste the raw
> ``Sequence of operations + outcomes`` block and the interpretation
> key directly below this line.

_<paste § 4 here>_

### 4.1 Spike 3.2 subscription pattern (operator fills)

_<operator fills — pick the one matching § 4 outcome and explain:_
_— "Idempotent (de-duped) → safe to call addEventCallback repeatedly"_
_— "Distinct registrations → guard with bool flag in_
_TopsEventBridge.warm\_on\_scene\_load() before subscribing"_
_— "Rejects double-add → check before subscribing">_

---

## 5. Aux surface (hipFile module, path, removeEventCallback, version)

> Receiving vessel for the script's § 5 output. Paste the raw
> ``### 5.1 …`` through ``### 5.4.1 …`` blocks from the report file
> directly below this line.

_<paste § 5 here>_

---

## 6. Anomalies / surprises / gotchas

> Operator fills. Anything that diverged from the watchlist; anything
> that surprised you; any signature/repr/value that contradicts what
> Spike 3.0's audit recorded; any silent failure or misleading return
> value. If nothing surprised you, write "none — surfaces matched
> watchlist exactly."

_<operator fills>_

---

## 7. Implications for Spike 3.2 design

> Synthesis section. Pulls answers from § 1–§ 6 into actionable design
> constraints for the auto-warm scaffold. Mirrors the shape of Spike 3.0
> § 4 ("Implications for Spike 3.1 TopsEventBridge design").

### 7.1 Threading model (LOAD-BEARING — from § 3)

_<operator fills:_
_— Which thread does AfterLoad fire on?_
_— Does Spike 3.2 need ``hdefereval`` marshaling?_
_— What in the bridge sketch needs to change?>_

### 7.2 Callback registration shape (from § 1 + § 4)

_<operator fills:_
_— Return-value contract (None expected per Spike 3.0 § 3.1 — verify here)._
_— Subscription idempotency: which guard pattern does Spike 3.2 need?_
_— Storage shape: store the bound callback function reference (not a_
_handle) so removeEventCallback can match by identity at teardown.>_

### 7.3 Event filter constants (from § 2)

_<operator fills:_
_— Which integer values to hard-code in the auto-warm scaffold,_
_following the ``tops_bridge.py:78-90`` pattern (e.g._
_``_EVT_AFTER_LOAD = N``)._
_— Whether the BeforeLoad → AfterLoad sequence is interesting or only_
_AfterLoad matters.>_

### 7.4 Scaffold-blocking issues (if any)

_<operator fills:_
_— Anything in § 1–§ 6 that prevents Spike 3.2 design from opening._
_— "None" is a valid answer if all surfaces resolved cleanly.>_

---

## 8. Sign-off

Spike 3.2 audit closes when **all** of the following are true:

- [ ] § 0 header table filled in (timestamp, build, summary,
      finalization reason, events captured)
- [ ] § 1, § 2, § 4, § 5 contain real audit output (no
      ``_<paste here>_`` placeholders remain)
- [ ] § 3 thread-context probe results pasted **AND** § 3.1
      implication summary populated **AND** § 3.2 scaffold decision
      stated explicitly
- [ ] § 4.1 subscription pattern decision stated explicitly
- [ ] § 6 anomalies recorded (or "none — surfaces matched watchlist
      exactly" stated explicitly)
- [ ] § 7 implications complete enough that Spike 3.2's ARCHITECT pass
      can write a design against verified surfaces

When all six boxes checked: **Spike 3.2 design opens.**
