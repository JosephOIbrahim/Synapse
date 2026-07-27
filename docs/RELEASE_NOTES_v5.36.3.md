# v5.36.3 — known limitations now include the MCP `inspect_scene` hang

*Docs and rulings only.* `v5.36.2` shipped before R125 landed, so master carried a limitations list missing an entry.

---

## The entry

**`synapse_inspect_scene` does not return over the external MCP surface.** It hangs to the idle timeout.

It states what was actually established rather than what was first suspected. **Two proposed mechanisms were both refuted by measurement:**

- `_node_issues` calling `node.errors()` — **0.00s** over 12 real LOP nodes. Free.
- `inspect_scene` itself — returns in **0.08s** for a 5,764-node scene when called directly.

The fault is in the main-thread marshal under MCP, not in introspection. **The panel's WebSocket path is unaffected** and is demonstrated working on that same scene.

---

## Also in this patch

**There is no AI floor in Houdini 22.** 22.0.368 registers no LLM, agent, assistant or MCP surface — a **proven absence**, not an assumption. This refutes the positioning document's opening premise, and it strengthens the position: the slot is empty rather than commoditised.

**The routing self-improvement loop has never run.** The package is absent from the live process's `sys.modules`, its reward signal is a hardcoded constant, and its output is read by nothing — while **4,357 "Epoch complete" lines** sit in the operator's log directory, every one written by unit tests.

**A control only rules out what it actually exercises.** A fast health-check response was read as proving the marshal worked. The health check does not use the marshal.

---

## Verifying any of this

```
python harness/verify/version_agreement.py
python harness/verify/bom_audit.py
python harness/notes/_inspect_scene_probe.py    # under hython
```

**House rule:** no number enters a document without a producer path beside it.
