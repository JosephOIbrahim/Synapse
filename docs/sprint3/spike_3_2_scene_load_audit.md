# Spike 3.2 — Scene-Load API Audit (Empirical)

> **Authority:** ARCHITECT scaffold (this doc) + Joe (operator, live
> Houdini). The script ``spike_3_2_scene_load_audit_script.py`` runs
> inside graphical Houdini 21.0.671; this doc is the receiving vessel
> for its output. Spike 3.2's auto-warm scaffold cannot be designed
> until § 3 (thread-context probe) is filled in.
>
> **Status:** AUDIT LANDED — § 3 thread-context resolved on
> MainThread. Spike 3.2 design opens.
>
> **Sprint position:** Spike 3.1 (TopsEventBridge scaffold + hostile
> suite) shipped at commits ``89da296`` (scaffold) and ``bb2713b``
> (hostile suite). Spike 3.2 (auto-warm on scene load) opens once this
> audit lands. Anchors: ``CONTINUATION_INSIDE_OUT_TOPS.md`` § Hard API
> verification gate; Sprint 3 hard invariant #6.

---

## 0. Header

| Field | Value |
|---|---|
| Audit run | 2026-04-26T13:01:08 |
| Houdini build | 21.0.671 |
| Python version | 3.11.7 |
| Operator | Joe Ibrahim |
| Script run | ``docs/sprint3/spike_3_2_scene_load_audit_script.py`` |
| Full report file | ``C:\Users\User\spike_3_2_scene_load_audit_20260426-130108.txt`` |
| Audit summary | 6 surfaces resolved · 0 missing · 0 errors · 4 events captured |
| Probe finalization | afterload_captured |
| Events captured | 4 |

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

### 1.1 hou.hipFile.addEventCallback (function surface)

**Resolved path:** ``hou.hipFile.addEventCallback``

**STATUS:** RESOLVED
**Type:** ``method``
**Repr:** ``<bound method addEventCallback of <module 'hou.hipFile'>>``

**Signature:** ``(callback)``

**__doc__:**
```
<no doc>
```

**dir() — 1 attributes:**
```
  __call__(*args, **kwargs)  -> method-wrapper
```

### 1.2 Return-value probe (live call)

Subscribe a noop callback, capture the return value, immediately unsubscribe. No event fires; pure API contract probe.

```
  return value (repr):  None
  return value (type):  NoneType
  remove result:        ok
```

**Implication for Spike 3.2:** if return value is ``None`` (expected, per Spike 3.0 § 3.1), the auto-warm scaffold MUST store the bound callback function reference itself (not a returned handle) and pass that same function reference to ``hou.hipFile.removeEventCallback`` at teardown.

---

## 2. hou.hipFileEventType enum members

> Receiving vessel for the script's § 2 output. Paste the raw
> ``### 2.1 …`` block from the report file directly below this line.

### 2.1 hou.hipFileEventType (full member dump with values)

**Resolved path:** ``hou.hipFileEventType``

**STATUS:** RESOLVED
**Type:** ``type``

**Members (public, value-bearing):**
```
  AfterClear = hipFileEventType.AfterClear
  AfterLoad = hipFileEventType.AfterLoad
  AfterMerge = hipFileEventType.AfterMerge
  AfterSave = hipFileEventType.AfterSave
  BeforeClear = hipFileEventType.BeforeClear
  BeforeLoad = hipFileEventType.BeforeLoad
  BeforeMerge = hipFileEventType.BeforeMerge
  BeforeSave = hipFileEventType.BeforeSave
  thisown = <property object at 0x000000007F82D0D0>
```

**__doc__:**
```
hou.hipFileEventType

Enumeration of the hip file event types that can be handled by callback
functions.

See hou.hipFile.addEventCallback.

VALUES


    BeforeClear
        This event is triggered immediately before the current .hip file
        is cleared. For example, when selecting File -> New in the main
        menu bar.

    AfterClear
        This event is triggered immediately after the current .hip file
        is cleared. For example, when selecting File -> New in the main
        men...[truncated]
```

---

## 3. Thread-context probe results — LOAD-BEARING

> Receiving vessel for the script's § 3 output. **This section gates
> Spike 3.2 design.** Until thread context is empirically known, the
> auto-warm scaffold cannot decide between direct ``hou.*`` calls vs
> ``hdefereval`` marshaling — and that decision is structural, not
> cosmetic.

**Finalization reason:** ``event_captured``
**Events captured:** 4
**Unsubscribe result:** ``ok``
**Timeout fired:** ``False``
**Timeout window:** ``300s``

**Captured event sequence (4 events):**

#### Event 1
```
  thread_name            : MainThread
  thread_id              : 35700
  is_main_thread         : True
  event_type_repr        : hipFileEventType.BeforeLoad
  event_type_str         : hipFileEventType.BeforeLoad
  event_type_typename    : EnumValue
  fired_at               : 2026-04-26T13:02:23
```

#### Event 2
```
  thread_name            : MainThread
  thread_id              : 35700
  is_main_thread         : True
  event_type_repr        : hipFileEventType.BeforeClear
  event_type_str         : hipFileEventType.BeforeClear
  event_type_typename    : EnumValue
  fired_at               : 2026-04-26T13:02:23
```

#### Event 3
```
  thread_name            : MainThread
  thread_id              : 35700
  is_main_thread         : True
  event_type_repr        : hipFileEventType.AfterClear
  event_type_str         : hipFileEventType.AfterClear
  event_type_typename    : EnumValue
  fired_at               : 2026-04-26T13:02:23
```

#### Event 4
```
  thread_name            : MainThread
  thread_id              : 35700
  is_main_thread         : True
  event_type_repr        : hipFileEventType.AfterLoad
  event_type_str         : hipFileEventType.AfterLoad
  event_type_typename    : EnumValue
  fired_at               : 2026-04-26T13:02:25
```

**Headline finding for Spike 3.2 scaffold:**

- AfterLoad fired on thread ``MainThread`` (``is_main_thread=True``)
- **Main thread confirmed.** Spike 3.2 auto-warm callback can call ``hou.*`` directly. No ``hdefereval`` marshaling required for the scene-load reaction path.

### 3.1 Thread-context implication

All four hipFile events fire on ``MainThread`` with
``is_main_thread=True`` (thread_id 35700, consistent across all four
captures). Phase B's auto-warm callback runs on the main thread by
definition — **no ``hdefereval`` marshaling required** for ``hou.*``
calls inside the scene-load handler. This is the **opposite** shape
from PDG events (which fire on a cook-thread per the Sprint 3 hooks
reference), and it collapses Phase B's design to a direct callback
without the deferred-dispatch ceremony that ``shared/bridge.py``
applies to PDG cook events.

| Question | Answer | Evidence |
|---|---|---|
| Did AfterLoad fire? | yes | event 4 of § 3 capture sequence (fired_at 2026-04-26T13:02:25) |
| Thread name | MainThread | every event in § 3 |
| ``is_main_thread`` | True | every event in § 3 |
| Other events captured before AfterLoad | BeforeLoad → BeforeClear → AfterClear (events 1–3) | § 3 sequence |
| Unsubscribe result | ok | § 3 unsubscribe field |

### 3.2 Event-sequence implication

A fresh File → Open emits **BeforeLoad → BeforeClear → AfterClear →
AfterLoad** in sequence. Auto-warm must trigger on ``AfterLoad``
specifically (not ``AfterClear``) to avoid warming against the
transient empty-scene state mid-load: between ``AfterClear`` and
``AfterLoad`` the stage holds no nodes, so any TOP-network walk
would return zero topnets and warm nothing useful. Filter the event
handler to ``hou.hipFileEventType.AfterLoad`` and ignore the other
three. Note the timing gap in the capture: events 1–3 land at
``13:02:23``, AfterLoad at ``13:02:25`` — the two-second window is
where the load actually happens.

---

## 4. Callback identity / removal behavior

> Receiving vessel for the script's § 4 output. Paste the raw
> ``Sequence of operations + outcomes`` block and the interpretation
> key directly below this line.

Test: subscribe the same callback function reference twice, then attempt removal twice. The outcome reveals whether ``addEventCallback`` de-duplicates by identity (idempotent), treats each subscription as a distinct registration (FIFO removal), or rejects double-add outright.

**Sequence of operations + outcomes:**
```
  first_add                 : ok
  second_add_same_fn        : ok
  first_remove              : ok
  second_remove             : ok
```

**Interpretation key:**
- If ``second_add_same_fn`` raised → API **rejects** double-add. Spike 3.2 must check before subscribing (e.g. ``if not self._registered: hou.hipFile.addEventCallback(...)``).
- If ``second_add_same_fn`` ok AND ``second_remove`` raised → API **de-duplicates** by callback identity. Idempotent subscription is safe.
- If ``second_add_same_fn`` ok AND ``second_remove`` ok → API treats double-add as **two distinct registrations** (FIFO-style removal). Spike 3.2 must guard against double-subscription with an explicit bool flag or single-registration discipline.

### 4.1 Callback identity behavior

Captured outcome:

```
  first_add                 : ok
  second_add_same_fn        : ok
  first_remove              : ok
  second_remove             : ok
```

``second_add_same_fn`` ok AND ``second_remove`` ok → API treats
double-add as **two distinct registrations** (FIFO-style removal).
Spike 3.2 must guard against double-subscription with an explicit
bool flag or single-registration discipline.

**Phase B implication:** follow Spike 3.1's cleanup contract pattern —
store the bound function reference on the bridge, pass that same
reference to ``hou.hipFile.removeEventCallback`` at teardown. Removal
is **identity-based, not handle-based** (consistent with Spike 3.0
§ 3.1 and § 1.2 above, where ``addEventCallback`` returns ``None``).
Add a ``_scene_load_subscribed: bool`` guard on the bridge so
``warm_on_scene_load()`` is idempotent at the call site even though
the underlying API would happily double-register.

---

## 5. Aux surface (hipFile module, path, removeEventCallback, version)

> Receiving vessel for the script's § 5 output. Paste the raw
> ``### 5.1 …`` through ``### 5.4.1 …`` blocks from the report file
> directly below this line.

### 5.1 hou.hipFile (module / namespace surface)

**Resolved path:** ``hou.hipFile``

**STATUS:** RESOLVED
**Type:** ``hipFile``
**Repr:** ``<module 'hou.hipFile'>``

**__doc__:**
```
hou.hipFile

Functions for working with the current scene (.hip) file.


NOTE
    Houdini inherits the current directory (sometimes called the current
    working directory) from the environment where you run it. Some
    functions return or accept paths relative to the current directory.
    You can check Houdini's current directory by calling os.getcwd(),
    and change it by calling os.chdir.
```

**dir() — 27 attributes:**
```
  addEventCallback(callback)  -> method
  basename() -> 'std::string'  -> method
  clear(suppress_save_prompt: 'bool' = False) -> 'bool'  -> method
  clearEventCallbacks() -> 'void'  -> function
  collisionNodesIfMerged(*args, **kwargs) -> 'std::vector< HOM_ElemPtr< HOM_Node >,std::allocator< HOM_ElemPtr< HOM_Node > > >'  -> method
  eventCallbacks()  -> method
  groupColorTable() -> 'std::map< std::string,HOM_Color,std::less< std::string >,std::allocator< std::pair< std::string const,HOM_Color > > >'  -> method
  hasUnsavedChanges() -> 'bool'  -> method
  importFBX(*args, **kwargs) -> 'std::pair< HOM_ElemPtr< HOM_Node >,std::string >'  -> method
  isLoadingHipFile() -> 'bool'  -> method
  isNewFile() -> 'bool'  -> method
  isShuttingDown() -> 'bool'  -> method
  load(file_name: 'char const *', suppress_save_prompt: 'bool' = False, ignore_load_warnings: 'bool' = False) -> 'void'  -> method
  merge(*args, **kwargs) -> 'void'  -> method
  name() -> 'std::string'  -> method
  path() -> 'std::string'  -> method
  removeEventCallback(callback)  -> method
  save(file_name: 'char const *' = None, save_to_recent_files: 'bool' = True) -> 'void'  -> method
  saveAndBackup() -> 'std::string'  -> method
  saveAndIncrementFileName() -> 'void'  -> method
  saveAsBackup() -> 'std::string'  -> method
  saveMode() -> 'HOM_EnumValue &'  -> method
  setGroupColorTable(color_table: 'std::map< std::string,HOM_Color,std::less< std::string >,std::allocator< std::pair< std::string const,HOM_Color > > > const &') -> 'void'  -> method
  setName(file_name: 'char const *') -> 'void'  -> method
  setSaveMode(savemode: 'EnumValue') -> 'void'  -> method
  this = <Swig Object of type 'HOM_hipFile *' at 0x00000000E50DF240>  -> SwigPyObject
  thisown = False  -> bool
```

### 5.2 hou.hipFile.path (current scene path probe)

**Resolved path:** ``hou.hipFile.path``

**STATUS:** RESOLVED
**Type:** ``method``
**Repr:** ``<bound method hipFile.path of <module 'hou.hipFile'>>``

**Signature:** ``() -> 'std::string'``

**__doc__:**
```
path() -> str

    Return the absolute file path of the current scene file. Remember
    that a file may not exist at this path if the current scene hasn't
    been saved yet.
```

**dir() — 1 attributes:**
```
  __call__(*args, **kwargs)  -> method-wrapper
```

### 5.2.1 hou.hipFile.path() — live call result

```
  hou.hipFile.path() = 'C:/Users/User/untitled.hip'
```

### 5.3 hou.hipFile.removeEventCallback

**Resolved path:** ``hou.hipFile.removeEventCallback``

**STATUS:** RESOLVED
**Type:** ``method``
**Repr:** ``<bound method removeEventCallback of <module 'hou.hipFile'>>``

**Signature:** ``(callback)``

**__doc__:**
```
<no doc>
```

**dir() — 1 attributes:**
```
  __call__(*args, **kwargs)  -> method-wrapper
```

### 5.4 hou.applicationVersionString

**Resolved path:** ``hou.applicationVersionString``

**STATUS:** RESOLVED
**Type:** ``builtin_function_or_method``
**Repr:** ``<built-in function applicationVersionString>``

**Signature:** ``<no signature: builtin_function_or_method>``

**__doc__:**
```
hou.applicationVersionString

Returns the application's version number as a string.

USAGE
  applicationVersionString() -> string

The format of the string is 'major_version.minor_version.build_version'.
If this method is executed in python, then it returns the hou module's
version number.

RELATED

  * hou.applicationCompilationDate

  * hou.applicationName

  * hou.applicationVersion

  * hou.applicationPlatformInfo

  * hou.licenseCategory

  * hou.isApprentice
```

**dir() — 1 attributes:**
```
  __call__(*args, **kwargs)  -> method-wrapper
```

### 5.4.1 hou.applicationVersionString() — live call result

```
  hou.applicationVersionString() = '21.0.671'
```

---

## 6. Anomalies / surprises / gotchas

> Operator fills. Anything that diverged from the watchlist; anything
> that surprised you; any signature/repr/value that contradicts what
> Spike 3.0's audit recorded; any silent failure or misleading return
> value. If nothing surprised you, write "none — surfaces matched
> watchlist exactly."

None — surfaces matched watchlist exactly. All 6 surfaces resolved,
0 missing, 0 errors during audit. The pre-audit hypothesis (anchored
in the ``shared/bridge.py:600+`` PDG hooks pattern) that hipFile
callbacks would need ``hdefereval`` marshaling is **empirically
refuted** — events already fire on the main thread. PDG's
cook-thread shape does not generalize to hipFile events; each event
source must be probed independently.

---

## 7. Implications for Spike 3.2 design

> Synthesis section. Pulls answers from § 1–§ 6 into actionable design
> constraints for the auto-warm scaffold. Mirrors the shape of Spike 3.0
> § 4 ("Implications for Spike 3.1 TopsEventBridge design").

### 7.1 Threading model (LOAD-BEARING — from § 3)

AfterLoad fires on ``MainThread`` with ``is_main_thread=True``
(thread_id 35700). All four hipFile events fire on the same main
thread. Phase B's auto-warm callback therefore needs **no
``hdefereval`` marshaling** for ``hou.*`` calls inside the scene-load
handler — node-tree walks, ``hou.LopNetwork`` discovery, and
``TopsEventBridge.warm()`` invocations all run synchronously on the
main thread by definition. This is the inverse of the PDG
cook-thread pattern in ``shared/bridge.py``; the bridge sketch's
hypothesis that hipFile callbacks would need the same deferred
dispatch is empirically refuted (§ 6).

### 7.2 Callback registration shape (from § 1 + § 4)

- **Return-value contract:** ``hou.hipFile.addEventCallback`` returns
  ``None`` (verified live in § 1.2). No removable handle exists; the
  bound callback function reference itself is the identity used for
  teardown.
- **Subscription idempotency:** double-add registers twice (§ 4.1
  outcome — both ``second_add_same_fn`` and ``second_remove`` ok).
  Phase B guards with a ``_scene_load_subscribed: bool`` flag on the
  ``TopsEventBridge`` instance before calling ``addEventCallback``.
- **Cleanup contract:** store the bound callback function reference
  on the bridge instance; at teardown, pass that exact reference to
  ``hou.hipFile.removeEventCallback``. Identity-based, not
  handle-based. This mirrors **Spike 3.1's cleanup contract pattern**
  for PDG event handlers — same shape, same discipline, different
  event source.

### 7.3 Event filter — AfterLoad only (from § 2 + § 3.2)

Hard-code the filter against ``hou.hipFileEventType.AfterLoad``. The
audit captured the full enum (``BeforeClear``, ``AfterClear``,
``BeforeMerge``, ``AfterMerge``, ``BeforeSave``, ``AfterSave``,
``BeforeLoad``, ``AfterLoad``) and the live File → Open sequence
``BeforeLoad → BeforeClear → AfterClear → AfterLoad``. **AfterLoad
is the trigger, not AfterClear.** Between ``AfterClear`` and
``AfterLoad`` the stage is empty; warming on ``AfterClear`` would
walk a node tree with zero topnets and accomplish nothing. The
handler must inspect the event-type argument, branch on
``AfterLoad``, and ignore the other three.

### 7.4 Auto-warm trigger contract

On ``AfterLoad`` (only), the scene-load handler walks for TOP
networks from the root and invokes ``TopsEventBridge.warm()`` per
topnet found. Pseudocode shape:

```python
def _on_hipfile_event(event_type):
    if event_type != hou.hipFileEventType.AfterLoad:
        return
    for topnet in _find_top_networks(hou.node("/")):
        self.warm(topnet)
```

No ``hdefereval`` (§ 7.1). No deferred dispatch. The single
``_scene_load_subscribed`` bool flag (§ 7.2) is the only ceremony.
Per-topnet ``warm()`` calls inherit Spike 3.1's already-verified
contract.

### 7.5 Scaffold-blocking issues

None. All 6 surfaces resolved, all four anchors of the audit
(return-value, enum members, thread context, identity behavior)
returned clean data. **Spike 3.2 design opens.**

---

## 8. Sign-off

Spike 3.2 audit closes when **all** of the following are true:

- [x] § 0 header table filled in (timestamp, build, summary,
      finalization reason, events captured)
- [x] § 1, § 2, § 4, § 5 contain real audit output (no
      ``_<paste here>_`` placeholders remain)
- [x] § 3 thread-context probe results pasted **AND** § 3.1
      thread-context implication populated **AND** § 3.2
      event-sequence implication stated explicitly
- [x] § 4.1 callback identity behavior + Phase B subscription
      pattern stated explicitly
- [x] § 6 anomalies recorded ("none — surfaces matched watchlist
      exactly", with PDG-hypothesis refutation noted)
- [x] § 7 implications complete: threading model, callback
      registration shape, AfterLoad-only filter, auto-warm trigger
      contract — Spike 3.2 ARCHITECT pass can write a design against
      verified surfaces

All six boxes checked: **Spike 3.2 design opens.**
