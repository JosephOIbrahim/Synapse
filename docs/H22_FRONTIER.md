# What would put SYNAPSE at the frontier of Houdini 22 AI assistants

**Written** 2026-07-27 · **Cross-referenced against** the local H22 help cache and the shipped node reference
**Method** every claim carries a producer. Where the source cannot answer, it says so.

---

## 0 · The question is not the one it appears to be

The instinctive framing is *"what AI capability do we add to get ahead."* That framing is wrong here, and the local sources say why.

**There is no AI floor in Houdini 22.** SYNAPSE's own scout established this by probing the running build: 22.0.368 registers no LLM, agent, assistant, copilot or MCP surface. SideFX publicly demonstrated an AI-assisted authoring surface and scoped it *out* of the shipped release.

So there is no incumbent to leapfrog. **The frontier is not defined by other assistants. It is defined by the distance between what Houdini 22 shipped and what an assistant understands about it.**

That distance is measurable, and it is the subject of this report.

---

## 1 · What Houdini 22 actually shipped

`news/22/index.json` lists **eighteen** areas of change:

```
APEX/KineFX/animation · Muscles and tissue · Hair, fur, feathers · Crowds
Solaris · Karma · PDG · Machine Learning · Houdini Engine
Copernicus · Modeling/geometry/terrains · Viewport/UI/scripting
Particles and MPM · Pyro and Simulation · RBD · Vellum
VEX/OpenCL/HOM · HQueue
```

**One of the eighteen has a dedicated 45 KB page in the browsing cache: Copernicus.**

That is a weak signal on its own — the cache holds only pages someone opened, so its contents reflect a reading history, not an editorial ranking. But the page itself is not weak evidence. It names, by node path, the nodes the release added.

---

## 2 · The measured gap

**Corrected 2026-07-27 after `I1` re-derived it.** The first version of this section said *"161
new Copernicus nodes"*. That figure was wrong twice, and both errors were mine:

- The page uses **two link forms** — `Node:/cop/x` and `Node:cop/x`. My pattern required the
  leading slash and silently dropped **10 node types**, including the whole `adjacency_*` family.
  **The true count of named paths is 171.**
- **Named and new are different counts.** Of the 171, only **98** appear in new-node sections;
  the other 73 appear solely under *"Copernicus improvements"* — changes to nodes that already
  existed.

```
Copernicus node paths NAMED in What's New   171
of those, named as NEW                       98
SYNAPSE grounded at the time of writing       3
```

**The conclusion survives and sharpens.** 3 of 171 is worse than 3 of 161, and 3 of 98 is worse
still. The direction was right; the arithmetic was mine, and it took a leg re-deriving rather than
trusting it to find that.

It is consistent with the figure measured independently a week earlier: **COP grounding at 6.2%**,
which was never *thin coverage of a known surface*. It was coverage of a surface that barely
existed when the corpus was written.

### And the gap is now closed on the documentation axis

`INGEST-01` built it. **693 entries, 12,696 parameters, 87.1% label-resolved against the live
runtime.** Of the 171 named nodes, **168 clear the quality floor; 3 need a runtime probe.**

```
cop    358 of 383 SideFX-shipped types    (384 installed, 1 third-party)
lop    169 of 210                          (219 installed, 9 third-party)
cop2   133 of 156                          (169 installed, 13 third-party)
33 known-thin — counted and named, not padded
88 live types ship with NO help page at all — documentation cannot ground them
```

**Denominators corrected 2026-07-27 (R136).** The earlier figures measured against the *installed*
catalogue, which includes third-party HDAs — SideFX Labs, MOPS. **SideFX help cannot document a
node SideFX did not ship**, so those types were unreachable by construction and their presence
understated coverage while overstating what a documentation ingest could ever close. `lop` is 219
installed, not the 218 quoted since H9.

### Wired, 2026-07-28

The corpus is no longer a measured artifact sitting beside the product. It is **loaded by
`knowledge_lookup`** — 603 live node types, VERIFIED-DOC, pinned to 22.0.368, each carrying its
summary, its documented parameters, and its build.

The gate `INGEST-01` required is applied **at build time**: only entries whose documented type
matched the running catalogue are written to `rag/corpus/h22_nodes.json`. One failed that test and
is absent. **A phantom is not filtered at read time — it was never stored.**

Two defects surfaced during the wiring, and both are recorded rather than quietly fixed. 51 type
names exist in more than one context — `blur`, `crop`, `chromakey` and `average` are in both `cop`
and `cop2` — and insertion order let the **legacy** context overwrite **Copernicus**, which is this
document's own H21 problem reappearing inside the H22 corpus. And placing the node match ahead of
keyword lookup broke 8 tests, because `merge`, `wrangle` and `solver` are all live node types: the
corpus must answer when a query **is** a node type, not when a sentence **contains** one.

**The answer to "does it know Copernicus?" is now yes, and it is one lookup to check.**

### Why this is the highest-value gap and not merely the largest

Three properties make it the frontier rather than just a backlog:

**It is what the release is about.** An assistant that cannot discuss the flagship feature of the version it runs on is not behind on a detail.

**It is unforgeable to verify.** A COP either exists in the running build or it does not. Unlike prose quality or "helpfulness," coverage here is checkable in a single probe, by us or by a studio.

**Nobody else has it either.** There is no incumbent assistant with Copernicus fluency, because there is no incumbent assistant.

---

## 3 · What the other local sources add

Each of these was read. Two of them narrow the problem; two of them widen it.

**`ml/train_solutions`** — *"Trainable solutions provide several specialized, domain-specific training pipelines."* Named: `mldeformer`, `ml_trainneuralcellularautomata`, reachable from the tab menu as ML *recipes*.

This is the shape of AI that H22 actually shipped: **task-specific trainable pipelines inside the node graph**, not an assistant. An assistant that can *drive* those pipelines — set up a training, wedge its parameters, read its outputs — is complementary to what SideFX built rather than competing with it. That is a strategically distinct position and it is currently unoccupied.

**`shade/glsl.json`** — *"Custom GLSL shaders aren't supported for Vulkan. Instead, use MaterialX."* A deprecation with a named replacement, in a file an assistant would reach for when asked about viewport shaders. Exactly the class of fact that a stale corpus gets wrong and that gets an artist stuck.

**`vex/contexts/cop2.json`** — 5 KB, five context functions. The *legacy* COP2 surface, and its smallness is the finding: the VEX vocabulary an assistant needs for images now lives in Copernicus, not here.

**`examples/nodes`** — 47 files, clustered on `blur`, `streak`, `composite`, `defocus`, `rotoshape`, `xform`. Legacy COP2 examples. **The worked examples an assistant would learn image work from describe the superseded system.**

**`solaris/glossary.json`** — 79 KB of vocabulary. The single densest definition of the language an assistant must speak to be credible in Solaris, and the one source here that is directly ingestible without interpretation.

---

## 4 · What would actually close it, in order

**Ingest the shipped reference, not the browsing cache.** The cache is a reading history — 104 HOM symbols, 25 COP pages, whatever someone happened to open. The install ships the complete set: `hom.zip` (967 entries, version-pinned by construction) and `nodes.zip` (5,034 pages, 90% LOP and 94% COP coverage against the live catalogues). **The frontier is not gated on new capability. It is gated on reading a 6 MB file that ships with the product.**

**Convert the corpus to H22.** The retrieval corpus is Houdini 21 documentation, accurately labelled. That is honest and it is a ceiling: an assistant reasoning from H21 prose about Copernicus is reasoning about a subsystem that did not exist. This is content work, not a relabelling pass — the H21 material is *true about H21* and rewriting its labels would falsify it.

**Report the two axes separately.** Symbols are H22 and verified against the running build; prose is H21. An assistant that knows *which of its own knowledge is current* is more useful than one that averages them into a single confident voice. This is already implemented and should be stated to users, not hidden.

**Drive the ML pipelines rather than compete with them.** `mldeformer` and the training recipes are the AI SideFX shipped. An assistant that sets one up, wedges it through PDG, and reads back the result occupies a position no one else is in.

---

## 5 · What this report does not establish

**The cache is a browsing history.** Sixteen of the eighteen what's-new pages are absent from it — which means nobody opened them, not that they hold nothing. The Copernicus emphasis in §1 is supported by the *content* of the page that is present, not by the absence of the others.

**161 is a floor, not a total.** It counts node paths named in one what's-new page. The live catalogue holds 384 Copernicus types plus 169 Cop2.

**No user has tested any of this.** Every statement about what an artist would find valuable is inference. SYNAPSE has zero production users, and the fastest way to make this report obsolete in the right direction is one artist on one show for one quarter.

---

## Producers

```
harness/notes/_h22_news.py            the what's-new structure
harness/notes/_h22_news2.py           the index and the Copernicus page
harness/notes/_h22_frontier_xref.py   161 vs 3, the measured gap
harness/notes/_h22_sources.py         glossary, ML, VEX cop2, GLSL, examples
harness/notes/forensic/S0_SCOUT.md    the proven absence of an AI surface in H22
```
