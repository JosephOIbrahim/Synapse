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

4. **A fresh folder per take, outside the repo.** Make a new empty folder, for example `C:\SynapseDemo\take1\`, and copy `demo/synapse_demo.hip` into it. Never open the hip inside the repo.

   **Every hip in the same folder shares one memory store,** and so does every hip under the same `JOB`. A rehearsal deposit will show up during the show unless the show hip sits in its own new folder. Rehearse in a different folder from the show.

5. **JOB.** `JOB` is unset, or set to this take's folder. Check it in the Python shell: `hou.getenv("JOB")`. If it names a folder **above** the take folder (`C:\`, `C:\Users\User`), set `JOB` to the take folder. Memory goes to `$JOB/.synapse` when `JOB` contains the hip, otherwise to `.synapse` next to the hip (seam-guard, live hython on master `ed01db41`).

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
- No contractions. "What's" leaves a stray *s* that kills the match.

**Every recall says `scope=project`.** The default scope (`all`) adds a reference-docs article and reports a hit even when nothing was remembered (`python/synapse/server/handlers_memory.py`). That is not changing today.

**Two recall lines.** Track B is the primary line when the seat includes the recall fix. Track A is the fallback: it matches on the code as it is today.

On today's code, natural rewordings mostly miss: 5 of 65 measured questions hit (recall-eval, `memory/eval/results/baseline-d4a95d0c/`). Say the fallback line exactly as written. Never improvise a recall question on camera.

### Steps

1. **Deposit.** Type in the panel chat:

   > **Remember this for the project: Hero sphere look: warm coral shader with roughness 0.35, copper torus beside it on a charcoal plinth. The client approved the warm palette at the Tuesday review.**

   This is the deposit recall-eval measured. Keep its wording.

2. **Check the tool call.** The panel shows a `synapse_decide` call. Confirm it reads **`scope: project`** and the result says **`recorded: true`**. Note the **`id`** in the result: that is the record id for the take sheet. Check that **`storage_dir`** reads `<take folder>\.synapse`.

   If the scope reads `scene`, stop and redo the take. A scene-scoped decision is the wrong demo.

3. **Save.** File > Save.

4. **Close.** File > New. Do not save the empty scene. Don't recall here: the empty scene has its own empty store, so recall returns `found: false`. That is expected.

5. **Reopen.** File > Open the same hip from the take folder.

   The panel should open on this scene's own conversation (the PUX-01 fix).

   **Fallback:** if the panel opens on another scene's chat, clear it before recalling.

6. **Recall.** Type in the panel chat:

   - **Primary (Track B, only if the seat includes recall fix `a71eca94`):** **Use project scope. What did we decide about the hero sphere?**

     Measured at `a71eca94` (branch `mem/recall-20261007`): returns the look deposit first on both memory backends, with and without save, close and reopen, in a 12-decision store. It misses on today's code. The fix widens recall but does not understand synonyms: natural questions hit 0.68 to 0.72 of the time on questions it was not tuned on (recall-eval). Synonyms like "how shiny" or "f-stop" still miss. Read the line as written. Keep it on the deposit's own nouns: a question with a word in no record returns nothing, and a later deposit sharing a word (like "light fog") can outrank a looser question.
   - **Fallback (Track A):** **Use project scope. What was the look decision?**

   The fallback hit on today's code on both memory backends, with and without a reopen. Only *look* has to survive in the stored decision; *decision* is always there, because every deposit is stored as "**Decision:** ...".

7. **Check the tool call.** The panel shows a `synapse_recall` call. Confirm it reads **`scope: project`**, and that its `query` holds only words from the stored decision. The model writes the query, not you; an extra word like *memory* or *search* in it is enough to miss.

**One decision per topic in the store.** A fresh folder per take (pre-flight step 4) keeps the store to the one deposit, so nothing older can compete with it.

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
