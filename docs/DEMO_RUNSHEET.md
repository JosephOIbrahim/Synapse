# Demo runsheet

Four chapters. This page is for the person at the rig.

The **memory chapter** is written out in full. The other three are stubs: they list what is already known about them and nothing more. Their prompts get written when someone rehearses them.

The old script in `docs/archive/DEMO_SCRIPT.md` is stale. It was written for an earlier Houdini build and an earlier tool set. Do not read from it on camera.

---

## Pre-flight

Do these in order, before the recording starts. One take = one pass through this list.

1. **Seat build: fast-forward, then restart once, off camera.** After the memory fix passes, fast-forward the seat to master. Then quit and restart Houdini once, before rehearsal. A running panel keeps the code it loaded. Read the commit and the `VERSION` file off the seat and write them on the take sheet.

2. **Worker tool mode.** `SYNAPSE_WORKER_TOOL_MODE` and `SYNAPSE_WORKER_TOOL_PROFILE` are both unset, or both `standard`. The `demo`, `strict` and `proposal` modes refuse `synapse_decide` (`python/synapse/panel/worker_policy.py`), so the deposit would never happen.

3. **OCIO.** `OCIO` points at the color config. See `demo/README.md`.

4. **A fresh hip, outside the repo.** Make a new empty folder for this take, for example `C:\SynapseDemo\take1\`. Copy `demo/synapse_demo.hip` into it. Never open the copy inside the repo: opening it in place writes `demo/.synapse/` into the source tree.

5. **JOB.** `JOB` is unset, or set to this take's folder. Memory is stored under the Houdini project (`JOB`) when that contains the scene, otherwise next to the scene (`docs/demo-repairs.md`). A `JOB` left over from another take would carry that take's memory into this one.

6. **Conversation cleared.** Open the fresh copy, open the panel, clear the conversation. The panel keeps one previous session and may open on a "parked" notice. The first frame on camera should be an empty chat.

7. **Model locked.** Pick the model in the panel and do not change it during the take.

8. **No accessibility or recording hooks attached to Houdini.** The September demo had a Houdini exit inside Qt WebEngine / accessibility processing. Present with nothing hooked in. Rehearse once on the real recording setup, with the real capture software, before the take that counts.

---

## Chapter 1 — Memory round trip

**What it shows:** SYNAPSE remembers a project decision after the scene is closed and opened again.

**How recall matches on today's code (Track A, read this once).** Recall needs every meaningful word of the question to appear, spelled exactly, in the stored decision. Question words like *what, was, our, the, about, for, remember, recall* are ignored (`python/synapse/memory/store.py`, the recall matcher). Everything else must match letter for letter.

That means:

- *decide* is **not** ignored, and the stored text says *Decision*. So "What did we **decide**…" misses. Say "What was our **decision**…" or leave the verb out.
- *project* is **not** ignored. "Use project scope" is an instruction to the model, not part of the question. If the model puts *project* into the recall `query`, it misses.
- *light* and *lights* are different words. Use exactly the same nouns in the deposit and the recall.

**Every recall says `scope=project`.** The default scope (`all`) adds a reference-docs article and reports a hit even when nothing was remembered (`python/synapse/server/handlers_memory.py`). That is not changing today.

**Two recall lines.** Track B is the primary line once it is measured on the build the seat runs. Track A is the fallback: it matches on the code as it is today.

### Steps

1. **Deposit.** Type in the panel chat:

   > **Remember this for the project: the hero lens is 35mm because the set is tight.**

2. **Check the tool call.** The panel shows a `synapse_decide` call. Confirm it reads **`scope: project`** and the result says **`recorded: true`**. Note the **`id`** in the result: that is the record id for the take sheet.

   If the scope reads `scene`, stop and redo the take. A scene-scoped decision is the wrong demo.

3. **Save.** File > Save.

4. **Close.** File > New. Do not save the empty scene.

5. **Reopen.** File > Open the same hip from the take folder.

   Reopening a scene can replace the panel conversation and show a "parked" notice. That is known (PUX-01) and not part of the demo. Clear it if it appears.

6. **Recall.** Type in the panel chat:

   - **Primary (Track B):** *pending recall-eval's measurement on the forge branch.*
   - **Fallback (Track A):** **Use project scope. What was our hero lens?**

7. **Check the tool call.** The panel shows a `synapse_recall` call. Confirm it reads **`scope: project`**, and that its `query` holds only words from the stored decision. The model writes the query, not you; an extra word like *memory* or *search* in it is enough to miss.

### What success looks like

- The recall result says **`found: true`**.
- The first match's **`id`** is the same id you noted in step 2.
- No match in the result says `source: knowledge`.
- The recall card shows **HIT** and the decision text.

### When it breaks

- **NO HIT on the primary line.** Use the fallback line. If that misses too, the model reworded the decision: open the `synapse_decide` result, read the stored decision, and ask again with only nouns that appear in it.
- **Recall ran with `scope: all`.** The take does not count. Ask again, starting with "Use project scope."
- **The deposit was refused.** Check pre-flight step 2: the worker tool mode.

---

## Chapter 2 — Solaris build from prompts (stub)

Not written yet. Prompts to be written during rehearsal on the seat build.

---

## Chapter 3 — Network layout and TOPs monitor (stub)

Not written yet.

Known: network layout uses `houdini_layout_network`. It moves, colors, comments and boxes existing nodes; names, parameters, connections and flags stay as they were. It needs Undo enabled (`docs/demo-repairs.md`).

---

## Chapter 4 — Panel and safety story (stub)

Not written yet.

Known: render goes through the **Render** button or **`/render`**. Never ask for a render in chat.

---

## Take sheet

For each take, record: take number, seat commit, the deposit's record id, the recall result (`found`, first match `id`, any `source: knowledge` entry), and the footage path.
