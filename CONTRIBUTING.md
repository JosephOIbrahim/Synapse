# Contributing to SYNAPSE

Welcome — genuinely glad you're here. SYNAPSE is an AI copilot that runs **in-process inside Houdini**: the panel and the agent brain live in Houdini's own embedded Python, so a chat turn becomes **real nodes in your live scene**. That "inside-out" design is the whole point — and it's also what makes contributing fun.

You don't need to be a Houdini expert to help. A big chunk of this codebase is plain Python you can run on a laptop with nothing installed but `pytest`. Start there (see [Easiest entry point](#-easiest-entry-point)).

---

## ✦ The ethos (read this once)

Three commitments shape almost every design call. Hold them and your PR will feel native:

- **Provenance / receipts.** Every scene mutation leaves a record of who did what. We don't do invisible side effects.
- **Undo-safe by default.** Everything the agent does is an ordinary Houdini action wrapped in an undo group — **Ctrl+Z undoes it.** New mutations must keep that property; never reach around it.
- **The truth contract.** *A result may not claim an outcome the handler did not observe.* If a tool says it set a parameter, the handler must have actually read it back. No optimistic "probably worked" reporting — that's the bug class we exist to kill.

When in doubt, prefer the honest, smaller, reversible change.

---

## ✦ Easiest entry point

> **`python/synapse/cognitive/` is pure Python with ZERO `hou` imports** — and that rule is **lint-enforced**, not just convention.

If you don't own Houdini (or just want a fast inner loop), this is your front door. The cognitive layer — routing, the dispatcher, scout, the reasoning tools — is host-agnostic by construction. Anything that genuinely needs Houdini lives in `synapse.host.*` and gets injected across the dispatcher boundary as a callable.

The boundary is a real test, run on every CI invocation and locally:

- [`tests/test_cognitive_boundary.py`](tests/test_cognitive_boundary.py) — `test_cognitive_layer_has_no_hou_imports` walks every `*.py` under `python/synapse/cognitive/` and **fails pytest loud at collection time** if it finds an `import hou` or `from hou ...` anywhere in the tree.

So: write cognitive-layer code, run its tests with plain `pytest`, and you'll never need a Houdini license to know it works. If you find yourself wanting `hou` in cognitive code — **you don't.** Move the Houdini bit to `synapse.host.*` and inject it (see `Dispatcher(main_thread_executor=...)`).

---

## ✦ Dev setup

Editable install with the test + transport extras:

```bash
pip install -e ".[dev,websocket,mcp]"
```

Run the suite — **the full suite is the gate**:

```bash
python -m pytest tests/
```

That's ~3,796 tests and counting. They run host-free (no Houdini needed) — the suite plants lightweight fakes for `hou` where a module touches it.

**About the Moneta memory backend.** SYNAPSE works **standalone out of the box** with a plain JSONL memory store — that's the live default, nothing to configure. [Moneta](https://github.com/JosephOIbrahim/Moneta) is an **optional** private encrypted memory substrate: it's **built but default-off**. You flip it on with an env var, selected in `python/synapse/memory/store.py`:

```bash
SYNAPSE_MEMORY_BACKEND=jsonl     # default — what you get with no env var
SYNAPSE_MEMORY_BACKEND=moneta    # route through Moneta (falls back to jsonl + warning if unavailable)
SYNAPSE_MEMORY_BACKEND=shadow    # jsonl primary + Moneta shadow dual-write
```

You don't need Moneta to contribute. Its ~70 tests `skipif` it isn't importable, so **they skip cleanly and CI stays green** when the backend isn't present. CI only checks it out when the `MONETA_DEPLOY_KEY` secret is configured. Details: [`docs/MONETA_FOLLOWUPS.md`](docs/MONETA_FOLLOWUPS.md).

*Want the full artist + developer install walkthrough?* See [`docs/getting-started/installation.md`](docs/getting-started/installation.md).

---

## ✦ What needs Houdini, what doesn't

You can do most development with **zero Houdini installed**:

| Houdini-free (just `pytest`) | Needs Houdini |
|---|---|
| `python/synapse/cognitive/` — routing, dispatcher, scout, reasoning | `python/synapse/panel/` — the docked UI (PySide) |
| Most of `python/synapse/core/` and `memory/` | `python/synapse/server/` + the command handlers (`hou.*` calls) |
| `shared/` — bridge, evolution, router (run in standalone mode) | Anything verifying real node creation in a live scene |

When a change *does* touch the live path, verify it in Houdini and say so in the PR. When it doesn't, the test suite is sufficient proof.

---

## ✦ PR flow

1. **Branch off `master`.** One focused change per branch.
2. **Atomic commits** — each commit builds and tells one story. Touch only what the change needs; don't drive-by-refactor adjacent code.
3. **Keep CI green.** The pipeline runs the full `python -m pytest tests/` on **Python 3.11 and 3.14** (Linux + macOS). Both must pass before merge.
4. **Expect an automated CodeRabbit review** on your PR — read its comments and address or reply to them; it's a second pair of eyes, not a gate to fight.
5. Open the PR against `master` with a clear description of *what* and *why*. If you verified anything in a live Houdini session, note exactly what you saw.

---

## ✦ License

SYNAPSE is **MIT** — see [`LICENSE`](LICENSE). Note that MIT covers **copyright, not patents**: SYNAPSE also documents **patent-pending methods** in a separate [`PATENTS`](PATENTS) notice. By contributing, you're contributing under the MIT terms; read both files if that distinction matters to you.

---

Thanks for helping make SYNAPSE better. Small, honest, reversible — that's the whole game.
