# Picking this up next time

*Written 2026-07-28, end of a long session. Read this first — it is the state of things, not a summary of what was done.*

---

## Where everything stands

```
master        in sync, nothing unpushed
release       v5.39.0
suite         5,279 passed · 0 failed
board         all legs done, nothing running, nothing held
rulings       182
```

**Nothing is running and nothing is at risk.** The orchestrator is stopped deliberately — start it only when you actually want to dispatch a leg.

---

## The one number that governs the next session

**The weekly usage limit was at ~92% when this session ended.**

R168 measured where it went: **session length, not context size.** A conversation re-sends everything said so far on every turn, so cost is quadratic in turn count. One leg, one long unattended session, 45–130 minutes — that is the most expensive shape available, and eleven of them ran in a day.

**Until the limit resets:** work in-conversation, which costs a fraction of a leg. When legs resume, make them **shorter, not fewer** — halving a session's length quarters its cost.

---

## Three things that are yours, not mine

**`shared/bridge.py:2288`** — the emergency halt walks `/obj` only and misses TOP networks entirely. Probed against a real cook: returned `ALL_OPERATIONS_HALTED` in 0.0s with the cook still running three seconds later. The file is deny-listed, and a safety control is not somewhere to guess.

**T.1 is a product decision, not an optimisation.** The 2,000-token ceiling is about tool **count**, not tool **size** — 120 tool *names alone* measure 2,919 tokens. The choices are: migrate to the deferred surface (three verbs at 332 tokens, everything else behind `tool_search`), ship fewer MCP tools, or raise the ceiling and say why.

**Seven MCP tools disagree with the server** about being read-only. `harness/verify/readonly_hint_agreement.py` ships and gates. A shallow read found no mutation in six of them, which suggests the *server* is wrong and not the annotations — the reverse of what R150 said. **Do not reclassify on a grep:** adding a command to `_READ_ONLY_COMMANDS` makes it execute with zero floor provenance.

---

## What is genuinely close

**OpenCV in the sidecar.** Vision now says *what* changed; it does not say *by how much*. Changed-pixel counts, bounding boxes, thresholds — `cv2` is absent in hython and present in system Python, which is exactly why RETINA was specified as a host-ABI-independent worker. That is the verification half.

**Confirm V1-F10 on a real scene.** Renders measured deterministic — pixel-identical across separate husk processes, zero sampling noise — and the whole vision-diff approach rests on it. Its own scope limit reads *one frame, one trivial scene, one machine.* Treat it as a strong prior until a real scene agrees.

**The WORK/TOKEN split is designed and half-built.** The TOKEN face ships; R167 has the rail's side of it, which stays small because V3 established quota headroom and per-token price are not obtainable from any provider.

---

## Habits worth keeping, learned the hard way

**"When did this start?"** is the first question, before any instrument. An hour went into investigating a marshal, a WebSocket topology and Houdini's threading model — all of which predate the symptom by months — because that question was never asked. It is free and it bounds everything after it.

**Sample the failure, not the operation.** One sample measured seven cores and concluded "burning." A second, taken *during the freeze*, measured zero cores with every thread waiting. Both were correct. A long operation has phases, and a phase is not a theory.

**Check the whole seam, not the unit.** Twice in one day a mechanism was built, unit-tested, passed — and wired to one of two call sites. The lock had a release nothing called. The vision attach sat on the branch its tool did not take. **Built and connected to nothing, with the connection half made, is harder to see than not making it at all.**

**A note in a tool result is a request, not enforcement.** A refusal the model can absorb will be absorbed. If the artist needs to know something, it belongs on a surface the model does not author.

---

## Where to look

```
harness/notes/CTO_RULINGS_01.md    182 rulings, including the reversals
docs/HOW_WE_KNOW.md                the method, with its own failures in it
docs/H22_FRONTIER.md               the corpus, and three numbers a leg corrected
python harness/status.py           the board, and both stranded-work checks
```

**The rulings file is the real record.** Roughly fifteen of the 182 correct earlier ones — that is what makes the rest usable.

---

## And the thing that has not moved

**SYNAPSE still has no users.** Every judgement about what an artist would find valuable is inference. The verification method is mature and aimed entirely inward; it found ten of its author's own errors in a single day and cannot tell you whether any of this is worth having.

**One artist, one task, one week, with a pre-agreed abort condition.** S3 specified it. Nothing has run it. That is the highest-value thing on this list and it is not a code change.
