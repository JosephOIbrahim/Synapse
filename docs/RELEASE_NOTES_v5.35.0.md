# v5.35.0 — the instruments were the defect

*Two days of auditing this codebase produced a different finding than expected: the code was mostly less broken than the things measuring it. Five Solaris tools passed a test suite that asserted against a mock. A coverage metric read 100% by construction. A ratchet floor sat 599 tests stale. The shipping test number could not be measured at all, because the runner carried `--ignore` flags for exactly the three files that failed to collect. **None of those were product bugs.** Every one was an instrument reporting healthy while measuring nothing. This release is what came out of fixing the instruments, then re-reading everything they had ever told us.*

---

## The headline numbers

| | before | after |
|---|---|---|
| Gate suite | 4,873 | **4,940** passed · 0 failed |
| Shipping suite | *unmeasurable* | **4,048** passed · 110 failed · 771 errors |
| Ratchet floor | 4,275 *(599 stale)* | tuple, both interpreters, with producers |
| Deprecated types in use | *unknown* | **41** — 39 invisible to runtime probes |
| Copernicus types | *never counted* | **384**, integrity-hashed |

---

## What changed for you

**A render can be stopped.** `rkill` works, and v5.34.0's notes were wrong to imply otherwise. `hou.RopNode` has no cancel method — that part holds — but the broader claim that *Houdini exposes no way to cancel a render* was refuted by a full sweep of the shipped reference. Corrected here, and the correction is the reason to read this section.

**Consent gates no longer announce decisions that never landed.** `_on_approve` and `_on_reject` caught every exception from `gate.decide()`, logged it, then marked the card decided and emitted the announcement anyway. The artist saw APPROVED, the chat said APPROVED, the gate recorded nothing. The reject path was worse — a reject that never reached the gate had blocked nothing.

**The panel test suite runs again.** One test file planted `sys.modules["PySide6"]` stubs at module scope, and because pytest imports every module at collection, the fake Qt was resident before any panel test ran. The suite took a Windows access violation. The real fix was subtler than it looked: restore the original module *objects*, not a re-import — those look identical and are not.

**Moneta is on.** `SYNAPSE_MEMORY_BACKEND=moneta`. It was never off by a flag; the flag was simply never set, and the design always intended this — `evolution.py` anticipates code being deleted *"when `SYNAPSE_MEMORY_BACKEND` defaults to moneta."*

---

## Gate 0.1 closes

Open since drop week. Task number one in the ledger, and the longest-open item in it.

The question was sidecar versus abi3 for the vendored `cp311`/`cp313` seam, blocked on a segfault under `hython3.13` that looked like an ABI problem.

It was not. The crashing frame is `QApplication::font()`, with **zero frames under `python/synapse/_vendor`** anywhere in the traceback and `_VENDOR_ABI_RISK` reporting `False`. Isolation with controls on both sides:

```
tests/panel/ alone                      27 passed, no crash
tests/panel/ + tests/test_hda_panel.py  ACCESS VIOLATION
```

**The vendored path stands. No sidecar is required on ABI grounds.**

---

## Two test numbers, and why there must be two

The gate suite runs on system Python with the vendored SDK **inactive**. The shipping suite runs on `hython3.13` with it **active**. They share almost no dependency surface, so a green number on one says very little about the other.

The shipping number had never been measured. The runner carried:

```
--ignore=tests/test_load.py
--ignore=tests/test_passthrough_hygiene.py
--ignore=tests/test_port_wave_scene1.py
```

— exactly the three files that fail to collect on that interpreter. **The instrument was built not to see the fault.** `--ignore` is now banned in any measurement runner; `--continue-on-collection-errors` records the error and proceeds.

**88% of the shipping gap is environment.** Supplying six packages closes 728 failures:

```
websockets  mcp  pytest-asyncio  orjson  xxhash  filelock
```

Those are shipping dependencies that are not shipped. Demonstrated by intervention, not argued.

---

## Deprecation is invisible to introspection

`dir()` tells you a symbol exists. It cannot tell you the symbol is deprecated.

A cross-reference of every `hou.*` symbol and node type SYNAPSE touches, against the reference that ships with the build, found **41 deprecated types in use — and 39 of them are deprecated in the documentation while the runtime says nothing.** `karmarenderproperties` has a 56,325-character help page that never mentions it; SYNAPSE emits it 123 times.

**A phantom API fails loudly on first call. A deprecated one works perfectly until the release that removes it.**

The reverse case exists too: `hou.ActiveRender` documents `kill()`, `suspend()` and `resume()`, is marked `#status: ni`, and is absent at runtime. Documentation describing an API that does not exist.

---

## Known limitations

**The PDG rollback has never executed.** `bridge.py:1718` passes `remove_files=` to `dirtyAllTasks`; the signature takes `remove_outputs`. It raises `TypeError` on every invocation and the failure is *recorded*, not rolled back. The method is additionally deprecated in favour of `dirtyAllWorkItems`.

**Emergency halt is not surfaced in the panel.** The mechanism exists; there is no always-visible artist-reachable control. Stop aborts the agent loop cooperatively and is honest about it, but does not cancel a running render.

> **Superseded 2026-07-28 (H3b).** Emergency halt is now surfaced in the panel's `⋯` overflow as a control distinct from Stop, and the running render is now stoppable via `render_stop` (`rkill`). Two corrections that came with it: the shipped `trigger_emergency_halt` walks `/obj` only and does **not** stop a cook under `/tasks` (measured), and it does not stop renders at all — the halt handler now sweeps scene-wide and reports what it did *not* cover rather than implying a wider guarantee.

**Node grounding is thin.** 18.3% of LOP types and 6.2% of Copernicus types carry semantic grounding. The shipped reference documents 37.9% of LOP parameters — the realistic ceiling from documentation alone, and well below what type-level coverage of 83% would suggest.

**Six shipping dependencies are not vendored.** Listed above. A fresh install on Houdini's Python will not have them.

**41% of panel affordances were found ORPHAN or SILENT.** Removal and repair are scoped, not done.

---

## Under the hood

**Gate C is enforced by capability.** Deny rules match a command *form* — `git -C <path> push` walks straight past `Bash(git push:*)`. A `pre-push` hook does not care how git was invoked. Pushing master now requires `SYNAPSE_GATE_C=1`, deliberately, for that one command.

**The repository now complies with its own `.gitattributes`.** `text=auto eol=lf` landed months ago; the renormalization commit was never run, so every blob carried CRLF under a policy demanding LF. It broke merges and buried real diffs under tens of thousands of lines of noise.

**The ruling record is public.** Rulings carry anchors, and the document contains twelve corrections to earlier rulings in the same document — including six that were wrong on evidence, found by an independent audit given a blind control that passed both its sensitivity and specificity halves.

---

## Verifying any of this

```
python harness/heats_status.py
powershell harness/supply_shipping_deps.ps1
powershell harness/run_suite_shipping_python.ps1
```

**House rule:** no number enters a document without a producer path beside it. This release also records three places where that rule was broken by its own author.
