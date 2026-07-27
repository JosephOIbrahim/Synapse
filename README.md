# SYNAPSE

**An AI agent that runs inside Houdini — not beside it.**

SYNAPSE lives in Houdini's own Python interpreter and calls `hou.*` directly. No external bridge, no RPC hop, no second copy of the scene.

> Houdini 22.0.368 · Python 3.13 · USD 0.26.5 · PySide6

---

## What it does

**Builds networks.** Ask for a Solaris scene, a material graph, a COP chain — it wires the nodes and tells you what it chose.

**Explains itself.** Every mutation records what it did and why.

**Stays on the main thread.** All `hou.*` calls marshal to Houdini's main thread. No cross-thread scene access.

**Groups its undo.** One Ctrl+Z reverses a whole operation. See *Undo, precisely* — the claim is narrower than it sounds.

---

## Install

Three steps. The third is the one people miss.

**1 — Clone**

```
git clone https://github.com/JosephOIbrahim/Synapse.git
```

**2 — Package file**

At `Documents/houdini22.0/packages/synapse.json`:

```json
{
    "name": "synapse",
    "enable": true,
    "env": [
        { "var": "SYNAPSE_ROOT", "value": "C:/path/to/Synapse" },
        {
            "var": "PYTHONPATH",
            "value": ["$SYNAPSE_ROOT/python", "$SYNAPSE_ROOT"],
            "method": "prepend"
        }
    ],
    "hpath": "$SYNAPSE_ROOT/houdini"
}
```

**3 — Verify**

```
python scripts/install_synapse_package.py --verify
```

Read-only. Prints pass/fail per requirement.

### Two things that bite

**`PYTHONPATH` needs both entries.** `shared/` lives at the repo root, not under `python/`. Omit the root and the handler fails to import — and it surfaces as a misleading *"hou not responding"* in the panel.

**`hpath`, not `path`.** On H22 the keyword is `hpath`. SideFX use it exclusively in their own shipped packages — six occurrences, zero of `path`. The deprecated `path` still works, which is why nobody notices.

Without either, `import synapse` succeeds, the version prints, and **the panel never appears.** No error. Just absence.

---

## Undo, precisely

This used to say *"every mutation is reversible."* That was overstated.

`hou.undos.group()` **groups** undo entries so one Ctrl+Z reverses a whole operation.

It does **not** roll back when something raises. On the exception path a partial network survives in your scene and you undo it deliberately.

**Wrapping is not reversing.** Both are useful. Only one was being claimed.

---

## The two paths

**`/mcp` — audited.** Undo-wrapped, main-thread-marshalled, consent-gated, scene-hashed.

**`/synapse` — live WebSocket.** RBAC-gated and main-thread-marshalled, but calls handlers directly. Undo-wrapping is partial.

Connect on `ws://localhost:9999/synapse` — the path matters, a bare `host:port` returns HTTP 400.

---

## Two test numbers, and they mean different things

| | interpreter | result |
|---|---|---|
| **Gate** | system Python 3.14 | 4,940 passed · 0 failed |
| **Shipping** | `hython3.13` — what Houdini runs | 4,048 passed · 110 failed · 771 errors |

The gate number runs with the vendored SDK **inactive**. The shipping number runs with it **active**. They share almost no dependency surface, so neither substitutes for the other.

**Most of that gap is environment, not code.** Supplying six missing packages closes 88% of the failures and 98% of the errors:

```
websockets  mcp  pytest-asyncio  orjson  xxhash  filelock
```

Those are shipping dependencies that are not shipped.

---

## Known limitations

Read this here rather than discover it mid-shot.

**A render can be stopped, but not from `RopNode`.** `hou.RopNode` has no cancel method. `rkill` works and SYNAPSE does not yet use it. `hou.ActiveRender` — the documented HOM replacement — is `#status: ni` and absent at runtime.

**The PDG rollback has never executed.** `bridge.py:1718` passes `remove_files=` to `dirtyAllTasks`; the real keyword is `remove_outputs`. It raises `TypeError` every time and the failure is recorded, not rolled back.

**41 node types SYNAPSE uses are deprecated.** 39 of them are deprecated in the docs while the runtime says nothing, so a probe alone cannot see them. `karmarenderproperties` and `karma` are emitted 123 and 31 times.

**Emergency halt is not surfaced in the panel.** The mechanism exists; there is no always-visible artist-reachable control yet.

**Node grounding is thin.** 18.3% of LOP types and 6.2% of Copernicus types carry semantic grounding. The shipped reference documents 37.9% of LOP parameters, which is the realistic ceiling from documentation alone.

---

## Verifying any of this

```
python harness/heats_status.py                    # leg board
powershell harness/supply_shipping_deps.ps1       # the six missing packages
powershell harness/run_suite_shipping_python.ps1  # shipping suite
```

Live catalogues in `harness/notes/`: 218 LOP types, 384 Copernicus + 169 Cop2, integrity-hashed, zero probe errors.

**House rule:** no number enters a document without a producer path beside it.

---

## Licence

MIT. Patent applications pending on the USD cognitive-state substrate, digital injection, and predictive lighting.
