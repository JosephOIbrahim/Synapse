# S0 — SCOUT

**Harness** FORENSIC-01 · **Leg** S0 · **Run** 2026-07-27
**Governed by** `harness/AGENT_CONSTITUTION.md` · **Brief** `harness/prompts/s0.md`
**Model** `claude-opus-5[1m]` · **Commit at run** `11f3a79`
**Standing** READ-ONLY. Zero recommendations. Zero prescriptive language — see §7 for the measured count.

---

## 0 · How to read this document, and where it is weak

### 0.1 Tiers

Per `SYNAPSE_FORENSIC.md` §1, every claim below carries one:

```
OBSERVED    read from a primary source, with a URL
REPORTED    a third party states it — who is named, marketing is marked as marketing
INFERRED    reasoned from OBSERVED facts — the reasoning is shown
ASSUMED     believed, unverified. LEGAL, and LABELLED.
```

### 0.2 The provenance seam in this leg, stated up front

**Two different read paths produced the evidence below, and they are not equally strong.**

| Path | What it is | Strength |
|---|---|---|
| `gh api` | Raw JSON from the GitHub REST API, returned unmodified | **Strongest.** No summarisation layer. A star count is the number GitHub returned. |
| `WebFetch` | Page fetched, converted to markdown, **then summarised by a small fast model** against my prompt | **Weaker.** Everything I quote from a web page passed through a summariser I did not read the raw input of. |

This matters and is not a formality. Every "reproduce this page" result below is one summarisation layer removed from the HTML. Where a claim is load-bearing I fetched **more than one independent page** and say so. Where I have a single-page read, the claim is marked accordingly.

**A specific consequence:** claims of the form *"page X does not mention Y"* are the weakest shape in this document, because a summariser omitting something is indistinguishable from the page not containing it. I have marked every absence claim and stated how many independent pages support it.

### 0.3 Absence of evidence

Where nothing was found, §5 says so by name. That list is a deliverable, not an apology — it tells S2 which of its own reasoning has no floor under it.

---

## 1 · Q1 — What does Houdini 22 ship natively?

### 1.1 Release timeline and build

| Claim | Tier | Source |
|---|---|---|
| Sneak peek 8 June 2026; launch event London (Curzon Soho) 17 June 2026; keynote broadcast 22 June 2026 | REPORTED | CG Channel + SideFX X post, via search — [cgchannel.com/2026/06/sneak-peek-houdini-22/](https://www.cgchannel.com/2026/06/sneak-peek-houdini-22/) |
| CG Channel's "SideFX just released Houdini 22" is dated **Thursday 16 July 2026**, by Jim Thacker | REPORTED | [cgchannel.com/2026/07/sidefx-just-released-houdini-22/](https://www.cgchannel.com/2026/07/sidefx-just-released-houdini-22/) |
| SideFX did not publicly confirm a download date; mid-July 2026 was inferred by third parties from prior release patterns | REPORTED | search result, same article cluster |

**No primary SideFX release-date announcement was located.** The date above is a trade-press posting date, not a vendor statement.

### 1.2 The platform floor — this is the hardest OBSERVED material in Q1

From `docs/houdini22.0/news/22/platforms.html` — [link](https://www.sidefx.com/docs/houdini22.0/news/22/platforms.html) — **OBSERVED**:

```
Python          3.13.10 primary   (3.11 available as a separate build)
Qt              6.8.3
PySide6         6.8.3             ("Dropped the Qt 5 builds")
VFX Platform    CY2026
gcc             14.2              (11.2 available as a separate build)
C++ API         C++20
Boost           1.88.0
OpenVDB         13.0
USD             26.05
Windows SDK     10.0.22621.0
```

Dropped: **Intel Mac (x86_64) builds**. Added: **Linux arm64 in Technical Preview** (no FBX support in that build).

Cross-checked against the VFX Reference Platform itself — [vfxplatform.com](https://vfxplatform.com/) — **OBSERVED**. Published by the **Visual Effects Society Technology Committee in partnership with the Academy Software Foundation**. Its own stated purpose: *"define a set of tool and library versions to establish a consistent build target for software providers,"* to *"minimise incompatibilities between different software packages"* and *"ease the support burden for integrated pipelines."*

| Component | CY2025 | CY2026 | CY2027 (draft) |
|---|---|---|---|
| Python | 3.11.x | **3.13.x** | 3.13.x |
| Qt / PyQt / PySide | 6.5.x | **6.8.x** | 6.8.x |
| gcc | 11.2.1 | **14.2** | 14.2 |
| C++ standard | C++17 | **C++20** | C++20 |
| NumPy | 1.26.x | **2.3.x** | 2.4.x |
| OpenVDB | 12.x | **13.x** | 14.x |
| OpenEXR | 3.3.x | **3.4.x** | 3.5.x |
| Boost | 1.85 | **1.88** | 1.91 |

**INFERRED** (from the two OBSERVED tables above): H22.0's stack matches CY2026 on every component both documents name. The CY2027 draft holds Python at 3.13.x, so the Python floor does not move again in the next platform year.

### 1.3 What shipped — the twenty documented sections

`docs/houdini22.0/news/22/index.html` lists exactly twenty feature sections — **OBSERVED**, [link](https://www.sidefx.com/docs/houdini22.0/news/22/index.html):

> APEX, KineFX, and animation · Muscles and tissue · Hair, fur, feathers · Crowds · Solaris · Karma · PDG · **Machine Learning** · Houdini Engine, APIs, and plug-ins · Copernicus · Modeling, geometry, and terrains · Viewport, user interface, and scripting · Particles and MPM · Pyro and Simulation · Rigid body dynamics · Vellum · VEX, OpenCL, and HOM scripting · HQueue · Licensing · Platforms

The marketing page `products/whats-new-in-h22/` uses a different, shorter taxonomy — **REPORTED** (this is marketing), [link](https://www.sidefx.com/products/whats-new-in-h22/):

> UI/UX · Gaussian Splats · Characters · CFX · Modeling · Lookdev · VFX · World Building

Trade press names the headline as *"a new 3D Gaussian Splatting toolset,"* changes to KineFX rigging, and Copernicus — **REPORTED**, CG Channel.

### 1.4 The Machine Learning section — the direct answer to "did the floor move under an AI tool?"

From `news/22/ml.html` — **OBSERVED**, [link](https://www.sidefx.com/docs/houdini22.0/news/22/ml.html):

**Shipped:**
- ML Train Regression now handles models exceeding 2GB
- ONNX Inference nodes: larger models, additional data types, scalar tensors, device selection, improved multi-threading, enhanced ONNX caching
- **Neural Layer to Depth (MoGe-2)** COP — depth, normal, position maps
- **Neural Layer to Mask (SAM2)** COP — segmentation via clicks / bounding boxes
- **Neural Cellular Automata Core** and **Decode** COPs
- ML Preprocess / Train GSplats
- ML Train Neural Cellular Automata
- ML Preprocess / Train Computer Vision (object detection, segmentation, keypoint tracking)
- ML Computer Vision Inference COP
- **Neural Terrain Generate SOP** — custom erosion inference models
- **Agent Add ML Deformer** — real-time crowd deformation from trained models

Model format is **ONNX**.

**Not present in this section:** LLM, natural-language, assistant, agent-in-the-LLM-sense, chat, MCP.

> **Note on the word "agent."** *Agent Add ML Deformer* uses "agent" in Houdini's crowd-system sense — a crowd agent primitive. It is not an autonomous software agent. Searching Houdini material for "agent" returns crowd tooling.

### 1.5 Native rig generation — named in the brief, so treated specifically

From `news/22/kinefx.html` — **OBSERVED**, [link](https://www.sidefx.com/docs/houdini22.0/news/22/kinefx.html):

**Automatic:**
- **APEX AutoRig Builder SOP** — interface redesigned for visual feedback; prebuilt rig templates (Mocap Biped, Biped); transfer full rigs onto a character with access to individual components
- Auto-orientation for joints
- Automatic creation and positioning of controls in the look-at rig component
- Improved rig inversion — *"more stable results when transferring skeleton animation to rig controls"*
- **Biped Setup SOP** — organises and groups a skeleton for biped work
- **Biped Retarget SOP** — *"transfers animation from one skeleton to another using full body IK"*
- Recipe: **APEX Retarget to Rig**
- Full body IK tool in the animate state

**Still manual, per the same page:**
- Fine-tuning rig components after template application
- Constraint setup and animation keyframing
- Control customisation through rig component parameters

Marketing frames the same material as *"a more automated biped character pipeline… new templates, guided workflows and retargeting tools reducing manual setup"* — **REPORTED**.

**Corroboration** — the Biped template is described elsewhere in SideFX docs as *"similar to the Electra test geometry, with twist joints, IK and FK finger control options, and setups for reverse foot, auto clavicle, and blendable IK/FK for the limbs."* — **REPORTED** (search-surfaced from `docs/houdini/character/kinefx/autorigbuilder.html`, not fetched directly).

### 1.6 Python / HOM surface

From `news/22/vex.html` — **OBSERVED**, [link](https://www.sidefx.com/docs/houdini22.0/news/22/vex.html). The API expansion is large. The load-bearing items:

**New classes** — `hou.ApexUniGraphDebugger`, `hou.Camera`, `hou.CameraPrim`, `hou.cameraProjection`, `hou.ChannelEditor`, `hou.channelGraphSelectionMode`, `hou.ChannelListPaneTab`, `hou.CompositorViewerEvent`, `hou.CopCable`, `hou.DetachedAttrib`, `hou.nodeConnectionDrawStyle`, `hou.OpenCLDevice`, `hou.openCLDeviceType`, `hou.UniNode`, `hou.UniNodeConnection`, `hou.UniStickyNote`, `hou.UniNodeType`, `hou.UniNodeTypeCategory`, `hou.ViewerHandleDragger2D`, `hou.ViewerStateDragger2D`.

**Removed** — and this is the part that breaks existing code:

```
hou.ChannelEditorPane                    (class removed; replaced by hou.ChannelEditor)
hou.ApexNode.copyNetworkBox()
hou.ApexNode.copyStickyNote()
hou.ApexNode.editableInputString()
hou.ApexNode.editableInputStrings()
hou.ApexNode.setEditableInputString()
hou.Node.copyNetworkBox()
hou.Node.copyStickyNote()
hou.Node.editableInputString()
hou.Node.editableInputStrings()
hou.Node.setEditableInputString()
```

**New COP-facing accessors** — `hou.CopNode.attrib()`, `.attribAtFrame()`, `.cable()`, `.cableAtFrame()`, `.pairedNode()`; `hou.Parm.evalAsCopCable()`, `.evalAsCopCableAtFrame()`. New pane types `hou.paneTabType.GenericGraphEditor` and `.UsdShadeEditor`. New `hou.hipFileEventType.BeforeQuit`.

No Python version change is stated on this page. (The version is on `platforms.html`, §1.2.)

### 1.7 Engine / APIs / plug-ins

From `news/22/engine.html` — **OBSERVED**, [link](https://www.sidefx.com/docs/houdini22.0/news/22/engine.html):

- HAPI: SOP camera support for inputs and outputs; ability to create **COP HDAs**; `int16`/`int32` conversion when extracting image data from COPs
- Unreal 5.7/5.8 (Win/Linux), 5.6 (macOS); Copernicus HDA support; PCG improvements; public API `InstantiatePreset`, `InstantiatePresetWithExistingWrapper`
- Unity 6.3, 6.5 · 3ds Max and Maya 2027
- glTF 2.0 importer/exporter with Draco, multi-animation clips, camera prims, `KHR_materials_emissive_strength`, `KHR_materials_transmission`
- FBX: animation export scaling removal, camera import

**Absence claim:** no MCP, no RPC, no external agent integration, no web server, no outside-of-Houdini session API on this page.

### 1.8 Viewport / UI / scripting

From `news/22/viewport.html` — **OBSERVED**, [link](https://www.sidefx.com/docs/houdini22.0/news/22/viewport.html):

- **OpenGL renderer removed in favour of Vulkan**
- GPU-accelerated surface subdivision; volumetric fog; OpenCL–Vulkan interop; improved GSplat rendering with shadows and a USD GSplat schema; XYZ gnomon
- New customisable UI skin with **Theme Editor**; redesigned Preferences window; Colour Editor with palette recipes and OKHSL; ramp preset gallery and Ramp Generator; per-instance/dynamic parameter slider ranges; cross-platform fullscreen (F11)
- Python: scripts for SOP/COP/APEX cameras; **Sprite Drawable** framework; Python states and handles gain multi-space COP support; *"Send UI Changes to Callback"*; improved undo support in Python handles

**Absence claim:** no AI/LLM capability, no webserver or remote-control feature documented on this page.

### 1.9 Solaris and Copernicus — the two domains SYNAPSE names

**Solaris** — `news/22/solaris.html`, **OBSERVED**, [link](https://www.sidefx.com/docs/houdini22.0/news/22/solaris.html):

New: Relocate LOP · Plane LOP (`UsdGeomPlane`) · Configure Guide Deform LOP · USD Create Component SOP · USD Create Proxy Geometry SOP · USD Parent Geometry SOP · Scatter Instances LOP (render-time instances via Hydra generative procedural) · PointInstancer LOP.

Renamed — **this is a compatibility surface, and renames break scripts silently**:

```
Layout LOP                   → Paint Instances LOP
Instancer LOP                → Copy to Points LOP
USD Character Import SOP     → UsdSkel Character Import SOP
USD Animation Import SOP     → UsdSkel Animation Import SOP
USD Skin Import SOP          → UsdSkel Skin Import SOP
SOP Character Import LOP     → SOP Import UsdSkel Character LOP
Bake Skinning LOP            → Bake UsdSkel Skinning LOP
```

Behavioural default change: *"The new `XformCommonAPI` convention stores transforms exploded and with pivots, instead of a 4 x 4 matrix."* All transform-capable nodes default to this; backward compatibility is preserved for imported scenes.

Beta: APEX Animate LOP · APEX SOP Rig Builder · Bake APEX Scene LOP · Configure APEX Rig LOP · SOP Import APEX Scene LOP.

**Copernicus** — `news/22/copernicus.html`, **OBSERVED**, [link](https://www.sidefx.com/docs/houdini22.0/news/22/copernicus.html): 60+ new COP nodes; HeightField COPs (terrain moves into COPs); 14 grunge-map generators; a five-node adjacency system for cross-seam processing; four time-based nodes (Time Blend / Loop / Pack / Shift); the ML COPs from §1.4; attribute wires with new **Signature** parameters; `op:` syntax with UDIM specification; Copernicus HDAs supported in Unreal.

### 1.10 Licensing changes in H22

From `news/22/licensing.html` — **OBSERVED**, [link](https://www.sidefx.com/docs/houdini22.0/news/22/licensing.html):

- SELinux officially supported
- Apprentice UX improvements; enhanced licence syncing; *"Improvements made to login-licensing while the server is having issues"*; better hserver init across platforms; browser support for login extended to *"Brave, Safari and others"*
- **A minimum `sesinetd` version of 21.0.679 or newer is required to serve Houdini 22 licences**

No tier restructuring is documented on this page.

### 1.11 What it costs

From `sidefx.com/products/compare/` — **OBSERVED**, [link](https://www.sidefx.com/products/compare/). Prices USD.

| Tier | Price | Hard restrictions |
|---|---|---|
| **Apprentice** | Free | Non-commercial. Render capped at 1920×1080. Watermarks on .jpg/.tif/.exr. 1 Karma/Mantra token. |
| **Indie** | **$299/yr** or **$449/2yr** | "Limited Commercial". **Max 3 licences per facility.** Watermarks. 2 tokens. Engine Indie free. |
| **Education** | **$95/yr** | Non-commercial. 10 tokens. Watermarks. |
| **Core** | **$1,995** perpetual node-locked · **$2,995** floating · **$1,475/yr** rental · **$1,095/yr** upgrade | Commercial. **Max 5 workstation licences per facility.** 5 Karma tokens; extra tokens $195. `.hdalc` assets only. |
| **FX** | **$4,495** perpetual node-locked · **$6,995** floating · **$3,505/yr** rental · **$2,740/yr** upgrade | Commercial. **Max 5 workstation licences per facility.** 5 Karma tokens. `.hdanc` assets; full DOP access. |
| **Engine** | **$525/yr** workstation · floating (GAL) from **$795/yr** (1 seat) | Commercial rentals only. Max 5 workstation per facility. |

Cross-check, **OBSERVED**, [Houdini Engine FAQ](https://www.sidefx.com/faq/houdini-engine-faq/): paid Engine *"will support all official Houdini Engine plugins, Hython, Custom game engines and allow for batch processing and .usd file creation."* Engine Indie is free but *"only compatible with Houdini Indie files and assets."*

The store page states Indie eligibility as *"for people making less than $100K USD per year"* and repeats the per-studio caps — **OBSERVED**, [sidefx.com/buy](https://www.sidefx.com/buy/). A third-party guide gives Indie as $299/yr, consistent with the primary source — **REPORTED**.

**The per-facility caps are an online-purchase ceiling, not an absolute one.** Above 5 seats the path is sales contact. Recorded here because it is a structural fact about how a studio of a given size acquires Houdini, and it appears on the primary page.

### 1.12 The licence mechanic that governs any headless Houdini process

**OBSERVED**, [Houdini Engine FAQ](https://www.sidefx.com/faq/houdini-engine-faq/): the paid Engine licence explicitly includes **hython** support and farm batch processing.

**REPORTED** (SideFX FAQ and forum material surfaced by search; the specific FAQ URL for the env-var question returned 404 on direct fetch):
- *"When hython is executed, it requests a Houdini-Engine license from the license server."*
- `HOUDINI_SCRIPT_LICENSE` set to `hbatch -R` in `houdini.env` attempts to check out a non-graphical (Engine) licence rather than an interactive FX or Core licence
- `HOUDINI_HYTHON_LIC_OPT` specifies that hython use only the Engine licence
- *"you only need engine licenses for machines that are running hython/hbatch, not for mantra"*; mantra licences are free
- Engine Indie gives free batch/plugin use on **up to 3 computers** without interactive licences

**INFERRED** from the above: any architecture that reaches Houdini by spawning an additional Houdini process carries a per-process licence cost, and the default checkout is not free. An architecture that runs inside an already-licensed interactive session does not add a checkout. This is a licence-arithmetic difference between integration shapes, not a feature difference.

### 1.13 What H22 does NOT ship — the absence claim, and its exact strength

**No LLM, no natural-language interface, no conversational assistant, no autonomous agent, and no MCP server ships in Houdini 22.**

Basis — **OBSERVED across eight independently fetched primary pages** (`ml.html`, `viewport.html`, `engine.html`, `vex.html`, `kinefx.html`, `solaris.html`, `copernicus.html`, `licensing.html`) **plus two SideFX marketing pages** (`whats-new-in-h22/`, `pipeline-ai/machine-learning-ai/`). None mentions any of those things. The Machine Learning section is entirely numeric/neural-network ML with ONNX as the model format.

**Strength of this claim.** It is the strongest absence claim this leg can make, and it is still an absence claim read through a summariser (§0.2). Ten independent pages agreeing is strong. It is not the same as having grepped the raw H22 documentation tree.

**A second, narrower absence, worth separating:** the *what's-new* pages do not document any new remote-control or webserver feature. That is not the same as Houdini having none. Houdini's built-in `hwebserver` exists and is in third-party use (§2.4) — it simply is not an H22 novelty. Conflating "absent from what's-new" with "absent from the product" is the error this note exists to prevent.

### 1.14 SideFX's own stated AI position

From `products/houdini/pipeline-ai/machine-learning-ai/` — **REPORTED, and this is marketing**, [link](https://www.sidefx.com/products/houdini/pipeline-ai/machine-learning-ai/):

- *"Artists and researchers can use Houdini to create large volumes of high-quality, labeled data for training models, including 3D geometry, simulations, and rendered imagery."*
- Emphasis on the **ONNX inference engine** — *"use models trained in PyTorch or TensorFlow in a common framework."*
- *"Synthetic data plays a critical role in accelerating AI development by enabling greater diversity, control, and scalability across datasets."*
- Positions Houdini to *"link outside AI models to the Houdini interface."*

No mention of LLMs, agents, assistants, natural-language control, or MCP on this page.

**INFERRED** from §1.4 + §1.14 together: SideFX's documented and marketed AI posture is *Houdini as data factory and inference host* — a producer of training data and a runner of ONNX models — rather than *Houdini as a target for a language model*.

### 1.15 One contested claim, recorded because it is contested

A SideFX forum thread contains the assertion that *"SideFX is already working on some kind of AI-Agent."* — **REPORTED, uncorroborated, and effectively ASSUMED.** It appears in community discussion. **No primary SideFX source for it was found.** See §5.1.

The same thread ([sidefx.com/forum/topic/103071](https://www.sidefx.com/forum/topic/103071/), started 4 Feb 2026) contains, **REPORTED**:
- User `toonafish` (4 Feb) proposes an "AI SOP" node taking natural-language prompts
- User `skrivantomas` (16 Feb) documents MCP implementations connecting Houdini to Claude, listing GitHub repositories
- User `IceBar0n` (30 Apr): *"Blender partnered with Anthropic"*, *"We need **built-in** functionality"*, *"Why isn't SideFX at the forefront?"*
- User `Numai` (29 Jun) disputes the Blender/Anthropic characterisation as overstated

The Blender/Anthropic claim is neither purely true nor purely false. §2.5 resolves it against primary sources.

---

## 2 · Q2 — What else exists in this space?

### 2.1 The measured landscape — strongest evidence in this document

`gh api` against the GitHub REST API, **2026-07-27**. **OBSERVED**, no summarisation layer. Producer: `gh api repos/<owner>/<repo>` and `gh api search/repositories?q=houdini+mcp+in:name,description&sort=stars`.

| Repo | ★ | Forks | Open issues | Created | Last push | Licence |
|---|---:|---:|---:|---|---|---|
| `Kazama-Suichiku/Houdini-Agent` | **326** | 47 | 2 | 2026-02-10 | 2026-07-12 | none |
| `capoomgit/houdini-mcp` | **273** | 40 | 7 | 2025-03-17 | 2026-06-11 | MIT |
| `healkeiser/fxhoudinimcp` | **138** | 22 | 0 | 2026-02-22 | **2026-07-27** | MIT |
| `HurtzDonutStudios/ai-forge-mcp` | 83 | — | — | — | 2026-04-09 | — |
| `capoom/houdini-mcp` | 59 | 5 | 3 | 2025-03-16 | 2025-03-31 | none |
| `oculairmedia/houdini-mcp` | 43 | 9 | 1 | 2025-12-18 | 2026-07-11 | none |
| `rendermagix/houdini2chat` | 22 | 2 | 0 | 2025-02-23 | 2025-03-03 | none |
| `loonghao/dcc-mcp` | 19 | — | — | — | 2026-07-19 | — |
| `orrzxz/Houdini21MCP` | 12 | — | — | — | 2026-02-04 | — |
| `eetumartola/houdini-mcp` | 11 | 3 | 0 | 2025-03-16 | 2025-03-17 | GPL-3.0 |
| `dcc-mcp/dcc-mcp-houdini` | 6 | — | — | — | 2026-07-27 | — |
| `maoweiming/houdini-mcp2.0` | 6 | 1 | 0 | 2025-03-21 | 2025-03-17 | GPL-3.0 |
| `lecopivo/another-houdini-mcp` | 5 | — | — | — | 2026-03-13 | — |
| `zxgvfx/houdini-mcp-tools` | 5 | — | — | — | 2025-07-07 | — |
| `chordee/houdini-tools` | 3 | — | — | — | 2026-06-27 | — |

Also surfaced but **404 on API lookup**: `atayilgun/Houdini-claudecode-mcp` (appeared in search results; repo not resolvable — renamed, deleted, or private).

**OBSERVED shape of this population:**
- **Nothing in it is large.** The largest is 326 stars. For comparison this is a hobby-scale open-source distribution, not a studio-tool distribution.
- **A visible dormancy split.** The 2025-era originals (`eetumartola` 11★, `capoom` 59★, `maoweiming` 6★, `rendermagix` 22★) have not been pushed since March 2025. The live set is `Houdini-Agent`, `fxhoudinimcp`, `capoomgit`, `oculairmedia`, `dcc-mcp`.
- **Licensing is inconsistent.** The two most-starred projects differ: `Houdini-Agent` (326★) carries **no licence**, `capoomgit` carries MIT. A repository with no licence is not open-source-licensed by default, which is a distribution constraint for any studio legal review.

### 2.2 The commercial products

| | **Houdini AI Assistant** | **NodeArchitect** |
|---|---|---|
| Author | Radu Cius (`raducius`), Chișinău | `jbishop02` / bishopvfx |
| Shape | **Native plugin** inside Houdini | **Native plugin** + **built-in MCP server** + web UI with streaming |
| Houdini versions | 20.0–21.0 stated in the announcement thread | v2.4.0 (19 Jul 2026) adds **Houdini 22** support |
| LLM | OpenAI, Anthropic Claude, DeepSeek; local via LM Studio / Ollama | Unspecified; login via GitHub Copilot and ChatGPT/Codex CLI mentioned |
| Pricing | Gumroad commercial — **price not obtained** (§5.10) | v1.0 free non-commercial; v2.0+ moving to paid *"at a small price in the future"*; early adopters grandfathered |
| Distribution | rart.gumroad.com | bishopvfx.gumroad.com |

**Tier: REPORTED throughout.** Both rows are vendor self-description from announcement threads and store pages. Neither has independent verification.

Houdini AI Assistant features, as claimed by its author — **REPORTED, marketing**: HDA Architect (AI-generated procedural networks), Scene Analyst, MaterialX shader generation, Solaris/Karma workflows, Pyro/FLIP/RBD support, Animation Maker (Windows only). Author's stated philosophy: *"AI not as a replacement for procedural thinking, but as a serious accelerator for it."* Author's own recommendation: *"GPT-5.5/5.4 for complex tasks; local models work for scene analysis only."*

NodeArchitect self-description — **REPORTED, marketing**: *"an AI agent and an MCP Server which actually understands your scene. You can select nodes and ask questions to get answers grounded in your real node graph."* v2.4.0 adds APEX/KineFX workflows, Solaris/Karma enhancements, and *"context-sensitive MCP tool discovery."*

**The engagement numbers are the honest part.** Houdini AI Assistant's SideFX thread ([topic/102263](https://www.sidefx.com/forum/topic/102263/)): announced **23 October 2025**, **5,919 views, 6 posts total**, updates 6 March and 7 June 2026 — and the thread *consists entirely of the developer's own posts*. **No user feedback, no complaints, no failure reports.** — **OBSERVED** (post/view counts are page furniture, not summariser inference; the "no replies" reading is REPORTED).

NodeArchitect's thread ([topic/103890](https://www.sidefx.com/forum/topic/103890/)): **no third-party replies at all.** Developer announcements only. — **REPORTED**.

The one substantive third-party reply found anywhere is on od|force ([topic/64621](https://forums.odforce.net/topic/64621-houdini-ai-assistant-%E2%80%94-analyze-debug-build-hdas/)), user **`Librarian`, 7 March 2026** — **REPORTED**. Sceptical, and specific about *why*: suggested focusing on AI texturing in COPs for stronger market appeal; **noted the existence of free GitHub alternatives with similar purpose**; questioned differentiation against the ComfyUI ecosystem. The developer replied that the goal is something *"native in Houdini"* rather than generic AI tooling.

### 2.3 The non-agent tool, recorded because its shape is different

**houdini2chat** — `rendermagix`, [GitHub](https://github.com/rendermagix/houdini2chat), also on Orbolt. **REPORTED**: an HDA with an *"Export 2 Chat"* button that serialises the scene to file(s), which the artist then pastes into any chat or code assistant. No live connection, no socket, no code execution in Houdini. Free. Self-described as *"early development stage (Proof of concept)… experimental and missing some features."* **OBSERVED**: 22★, last push 2025-03-03 — dormant for ~17 months.

Its `docs/Evaluation.md` is the only published evaluation artifact found for any Houdini AI tool — **REPORTED**, [link](https://github.com/rendermagix/houdini2chat/blob/main/docs/Evaluation.md). Method: three scenes of increasing difficulty, multiple models, qualitative scoring.

| Test | Scene | Models | Result as reported |
|---|---|---|---|
| 1 — Easy | xyzdist demo: 26 nodes, 5 sticky notes, 17 branches | Claude 3.7 Sonnet, Gemini 2.0 Flash | Both acceptable; Claude significantly superior |
| 2 — Medium | 8-Puzzle animation: 10 nodes, 1 branch | Claude 3.7 Sonnet, o3-mini-high, Grok 3.0 | **No model identified the animation logic initially.** o3-mini named the game; Claude required hints; Grok needed extended reasoning |
| 3 — Hard | Procedural burger: 88 nodes, 44 branches, 9 network boxes | Claude 3.7 Sonnet, o3-mini-high, Grok 3.0 | o3-mini 6/7 elements; Claude identified burger with minimal hints; **Grok identified only 3/7 after being told the answer** |

**No quantitative metrics** — no accuracy percentages, no token counts, no latency. Author's own document, so it is REPORTED and self-interested. Recorded because it is the only structured attempt at measuring scene comprehension found in the entire search, and because its Test 2 result — *no model identified the logic of a ten-node network* — is a negative finding a vendor had no incentive to publish.

### 2.4 The architectures in the wild

**`capoomgit/houdini-mcp` (273★)** — **REPORTED** from README, [link](https://github.com/capoomgit/houdini-mcp):
- Houdini-side Python plugin listening on **TCP localhost:9876**, plus an MCP bridge script speaking stdin/stdout to Claude
- JSON protocol over TCP
- **Executes arbitrary Python in Houdini's environment** — a full remote execution interface
- **No explicit security warnings in the README** regarding the TCP listener or the code execution
- Install path `~/houdini19.5/scripts/python/houdinimcp/`; `uv` for MCP deps; Claude Desktop config points at the bridge

**`healkeiser/fxhoudinimcp` (138★, pushed the day of this run)** — **REPORTED** from README, [link](https://github.com/healkeiser/fxhoudinimcp). This is architecturally the most elaborate found:
- **179 tools across 22 categories**, plus 8 resources and 6 workflow prompts. Categories: Graph Intelligence, Documentation, Scene Management, Node Operations, Parameters, Geometry (SOPs), LOPs/USD, DOPs, PDG/TOPs, COPs, HDAs, Animation, Rendering, VEX, Code Execution, Viewport/UI, Scene Context, Workflows, Materials, CHOPs, Cache, Takes
- **Uses Houdini's built-in `hwebserver`** on port **8100** (`FXHOUDINIMCP_PORT`). Its README states: *"Uses Houdini's built-in `hwebserver`. No custom socket servers, no rpyc."*
- Standalone FastMCP process forwards tool calls to Houdini over HTTP; async bridge; localhost by default
- Thread safety: *"Uses `hdefereval.executeInMainThreadWithResult()` to safely run `hou.*` calls on the main thread."*
- Security posture, stated plainly by its author: the bridge *"has no authentication, so only widen this on a network you trust"*; default binding is loopback `127.0.0.1`
- Requires **Houdini 20.5+**; integration verified on 20.5.278, 20.5.487, 20.5.613, 20.5.654, 21.0.440, and **22.0.368**
- Documented environment landmine: the Red Giant/Maxon Universe OpenFX plugin **crashes `hou` initialisation on Houdini 20.5.487 and later**, preventing `hython` from starting; workaround `HOUDINI_DISABLE_OPENFX_DEFAULT_PATH=1`

**`oculairmedia/houdini-mcp` (43★)** — **OBSERVED** from repo description: uses **hrpyc** for remote control.

**INFERRED** from the four architectures above: the space has settled on three integration shapes — (a) custom socket server inside Houdini, (b) Houdini's own `hwebserver`, (c) `hrpyc` — with a fourth, file-export-and-paste, occupied by houdini2chat. All of (a)–(c) put a listening port on the machine. Two of the three READMEs examined state no authentication or say nothing about security at all.

### 2.5 The adjacent floor moved, and Houdini is not on it

This is the single most consequential Q2 finding, and it resolves the contested forum claim in §1.15.

**Anthropic, "Claude for Creative Work", 28 April 2026** — **OBSERVED**, primary source, [anthropic.com/news/claude-for-creative-work](https://www.anthropic.com/news/claude-for-creative-work).

Official Claude connectors named in that announcement:

```
Ableton                      grounds Claude responses in product documentation
Adobe Creative Cloud         50+ tools incl. Photoshop, Premiere, Express
Affinity by Canva            automates production tasks
Autodesk Fusion              3D model creation and modification
Blender                      natural-language interface to the Python API
Resolume Arena / Wire        real-time control for live visual artists
SketchUp                     conversations into 3D modelling starting points
Splice                       royalty-free sample search
```

**SideFX Houdini is not named in that announcement.** — **OBSERVED** (absence claim, single primary page, §0.2 caveat applies).

The connectors are built on **MCP**, and the announcement states that *"because the connector is built on MCP, it is accessible to other LLMs in addition to Claude."*

Supporting facts — **REPORTED**, [CG Channel 2026-04](https://www.cgchannel.com/2026/04/ai-developer-anthropic-becomes-blenders-latest-corporate-patron/) and BlenderNation:
- Anthropic became a **Corporate Patron of the Blender Development Fund at €240,000/year**, described as equivalent to four full-time developers, directed at core development and the Python API
- **The Blender Lab built the MCP extension**, launched for **Blender 5.1, April 2026**. It enables users to *"analyze and debug entire Blender scenes, or build custom scripts to batch-apply changes to objects in a scene."*
- Community reaction was polarised, ranging from *"this is a smart move"* to *"I will never donate to you again"*
- Blender Foundation position: *"Corporate participation in the Development Fund does not imply alignment between Blender and the donor's mission, products, or strategy."* CEO Francesco Siddi said the donation enabled *"the Blender team to keep pursuing projects independently."*
- **By May 2026 the patronage was downgraded to a one-off donation**, ending the recurring annual commitment

**Resolution of the §1.15 dispute:** the forum poster who said *"Blender partnered with Anthropic"* was substantially right about the connector and the money; the poster who called it overstated was right that the recurring partnership did not survive first contact with the community. Both readings have primary-source support. Neither is evidence about SideFX.

### 2.6 Agentic pipelines reached the production-research literature this year

**DigiPro 2026** (ACM Digital Production Symposium, Los Angeles, 18 July 2026) — **REPORTED**, [3dvf coverage](https://3dvf.com/en/usd-ai-unreal-simulation-digipro-2026-puts-production-pipelines-in-the-spotlight/); proceedings DOI `10.1145/3819990` (ACM DL returned 403 on fetch, §5.9).

Nine talks. **Three are agentic AI in production pipelines:**

| Talk | Studio | Subject |
|---|---|---|
| **From Brief to Scene: Agentic AI for Asset Production** | **Ubisoft** | AI-driven scene assembly from creative briefs |
| **Smart Set Assembly: Learnings from Building an Agentic System for AI-Assisted Set Dressing** | not identified | AI agents for set dressing |
| **Automating the Handoff: From Hardcoded QC Scripts to a Multi-Agent Architecture for Layout-to-Animation Reviews** | not identified | Multi-agent QC automation |

The Ubisoft paper's authors, per search: Cyrus Rahgoshay, Nicolas Gaffiero, Patrick Sauvageau, Maxim Parisee, Jaeeun Cho, Alessandro Bernardi.

**One reported detail carries disproportionate weight** — the 3dvf coverage notes the Ubisoft system is *"primarily intended as a rapid prototyping tool rather"* than a production replacement. **REPORTED, and it is a partial sentence in a secondary source.** Marked as such, and flagged in §5.9 as needing the actual abstract.

The other six talks: KPop Demon Hunters facial rigging (Netflix); Kora physics-based fire (Wētā FX, *Avatar: Fire and Ash*); real-time feature animation (Dwarf Animation); Gaussian splatting for VFX reconstruction; Squid USD material authoring at scale; 2D/3D hybrid back-end pipeline.

---

## 3 · Q3 — What kills tool adoption in a VFX pipeline?

The brief asked for failure modes with mechanisms, not sentiment. Below, each entry names the mechanism and the evidence. **Ordering is by strength of evidence, not by my estimate of impact** — ranking impact is S2's job, not a scout's.

### 3.1 Content-security compliance — the only *contractual* blocker found

**MPA Content Security Best Practices, control OR-5.0 — "Organizational AI/ML Security Management."** Introduced in **v5.3 (2025)**. — **REPORTED**, via [cytrust.fr version-comparison](https://cytrust.fr/en/services/evolution-mpa-best-practices/) and search snippets of the CSBP document. *The MPA primary PDF was not read directly — see §5.12.*

Control version history as reported: v5.1 (2023) 64 controls → v5.2 (2023) 66 → **v5.3 (2025) 76** → v5.3.1 (2025) 82.

What OR-5.0 requires, as reported:
- Establish an *"Artificial Intelligence (AI) & Machine Learning (ML) policy aligned to overall Security Management program"*
- *"Identify and manage risks to include security controls associated with changes to datasets, applications, network infrastructure, and systems"*
- **"Ensure client approval for AI/ML application use"**
- *"Review data sources and its integrity before use"*
- *"Include AI/ML in Acceptable Use Policy"*, define *"appropriate usage for AI/ML datasets"*
- Training programme tailored to job responsibility

And in Additional Recommendations: **"Only use internally managed and sandboxed LLMs."**

**TPN** (Trusted Partner Network) is **wholly owned by the Motion Picture Association** and administers assessment against the CSBP — **REPORTED**, [ttpn.org](https://www.ttpn.org/2025/10/behind-the-scenes-of-security-how-tpn-keeps-hollywoods-content-safe-and-sound/). A vendor works through a questionnaire derived from the CSBP and attaches evidence: policies, configurations, diagrams, records. Third-party assessors report that *"virtually every major studio and streamer lists TPN Gold as a contractual requirement in 2025–2026 vendor agreements"* — **REPORTED, and the source is a compliance vendor selling assessments**, so it is interested. Assessment cadence reported as 2025: Blue + Gold, 2026: Blue, 2027: Blue + Gold.

**The compliance burden has already produced a community artifact.** The **Tool Disclosure List** — [github.com/sakerk/Tool-Disclosure-List](https://github.com/sakerk/Tool-Disclosure-List) — exists explicitly to satisfy this control. **REPORTED** from its README, which cites *"MPA/TPN+ Control OR-5.0 (Organizational Security – AI/ML Security Management)"* and NIST 800-171A-R3, and quotes the obligation: *"Maintain a Tool Disclosure List of all AI/ML tools in use, categorized by type, risk level, and approval status."*

Per-tool fields it records: name, official website, licence type (Commercial / Open-source / Hybrid), tool type, AI functionality category, **hosting model (Local / Hybrid / Cloud)**, **risk level (Low / Medium / High)**, output handling category, plain-English usage description.

Its five compliance buckets:

```
Standard Software Features    no approval required     LOW
Generative Content            APPROVAL REQUIRED        HIGH
Assisted, Artist-Controlled   no approval required     LOW
Internal Use / Non-Deliverable no approval required    LOW
Disclosure Required           producer decides         MEDIUM
```

**INFERRED** from the OR-5.0 text and the TDL taxonomy together: for a studio under a TPN-assessed contract, an AI tool is not adopted on technical merit alone. It acquires a hosting-model classification, a risk level, an approval status, and — where it touches deliverable content — a **client approval** requirement. A tool whose hosting model is *Cloud* sits against a control whose additional recommendation is *only internally managed and sandboxed LLMs*.

Corroborating the general shape, **REPORTED** from generic enterprise-security sources (weak, not VFX-specific): uploading unredacted client data to a commercial LLM is treated as an NDA and policy violation; *"Many enterprises now forbid any confidential material in ChatGPT unless absolutely controlled"*; vendor no-training promises are commonly judged insufficient because *"the logging and auditing controls often fall short of enterprise requirements."*

### 3.2 The tool hangs the host application

The strongest *mechanism-bearing* evidence found, because it is two independent reporters on two Houdini versions.

**`Kazama-Suichiku/Houdini-Agent` issue #9**, 26 May 2026, 3 comments — **OBSERVED** (raw issue body via `gh api`):

> "Houdini freezes (Not Responding) when launching `show_tool()` on Houdini 21.0.700 Windows"
> "PySide2 is being used (Houdini 21.0 bundled) — No window appears at all before freeze"

**Issue #12**, 9 June 2026 — a *different user*, *different Houdini version*:

> "I'm experiencing the same freeze on Houdini 20.5.700 on Windows. The Python Shell shows:
> `[AITab] init: _restore_all_sessions begin`
> `[AITab] init: _restore_all_sessions done`
> After that Houdini becomes unresponsive and **I have to force close it**. No window appears at all. **I tried deleting the cache and config folders but the issue persists.** Just wanted to flag that this is not limited to Houdini 21.0 — it also affects 20.5."

Note the shape: the failure is at **launch**, before any window, with no user error possible, and the obvious user-side remedy (clear cache/config) does not help. Both issues are now closed; #10 in the same repo is *"add startup breadcrumb logging for diagnosing `show_tool()` freezes"*, so the maintainer was debugging blind.

**Related, different mechanism, same class** — a third-party plugin breaking headless Houdini startup entirely. From `fxhoudinimcp`'s README, **REPORTED**: the Red Giant/Maxon Universe OpenFX plugin *crashes `hou` initialisation on Houdini 20.5.487 and later, preventing `hython` from starting*, requiring `HOUDINI_DISABLE_OPENFX_DEFAULT_PATH=1`. The tool did not cause this; it had to document a workaround for someone else's plugin in order to run at all.

### 3.3 Token cost per unit of work

**The only quantified datapoint found, and its source is vendor marketing that says so itself.**

MindStudio, 1 May 2026 — **REPORTED, vendor marketing, self-identified as promotional by my own read of it**, [link](https://www.mindstudio.ai/blog/claude-blender-mcp-60-percent-tokens-donut-test-results):

- Task: build the Blender Guru donut, via Blender MCP
- Plan: **5× Max ($200/month)**
- Consumed: **"60% of a 5x Max plan's session tokens"**
- Duration: **2 hours**
- Result: *"sprinkles clipping through the plate, a coffee cup clipping into the donut, wrong camera angles, and a magenta color wash"* — assessed by the author as *"better than nothing"* but *"worse than what a Blender beginner with a few hours of practice could produce"*

**This number is not trustworthy as a measurement.** It is a single unreproducible run published by a company selling a competing product. It is recorded because it is the only figure of its kind found anywhere (§5.6), and because the *direction* it points is independently corroborated:

**`capoomgit/houdini-mcp` issue #12** (closed) — **OBSERVED**, raw issue body. Titled *"Reduce token usage for large Houdini projects."* The maintainer's own fix list:

> - Remove base64 image encoding from render responses: renders now return a file path instead of encoding the full image (**~350KB+ saved per render, ~1.4MB for quad views**)
> - Replace `allSubChildren()` in `get_scene_info` with per-context node counts, **avoiding a full scene graph traversal on large projects**; now returns up to 20 nodes per context with count summaries instead of a flat 10-node list
> - Trim redundant fields (`label`, `raw_value`) from `get_node_info` parameter entries, **reducing parameter data by ~40%**

**INFERRED:** context cost is a first-order engineering concern in this space, not a footnote. The two mechanisms that drive it in a DCC are (a) images returned inline as base64 and (b) whole-scene-graph traversal on scenes large enough to matter.

### 3.4 The Python environment does not accept the tool

**`capoomgit/houdini-mcp` issue #9**, 5 October 2025, still **open** — **OBSERVED**, raw issue body:

> "I have tried several things Still not working… **I not very technical** Would really appreciate the help"

The diagnosis in the issue (pasted from an LLM by the reporter, so **REPORTED**, but the path it names is verifiable):

> `'C:/PROGRA~1/SIDEEF~1/HOUDIN~1.278/python311/lib/site-packages-forced'`
> "This **'forced' site-packages** directory takes precedence and breaks the normal import mechanism."

The mechanism: `hython` carries its own Python environment with a *forced* site-packages that takes precedence, so MCP packages installed into a venv are not importable. Options offered were: install into Houdini's Python directly with `hython.exe -m pip install`, or avoid `hython` entirely and reach Houdini over a socket from an outside process.

This composes with the platform pin (§1.2). **INFERRED** from §1.2 + §3.4: a tool's dependency set is constrained twice — once by the VFX Reference Platform year the host targets, and again by the host's own forced site-packages precedence. Neither constraint is visible to a developer testing outside the host.

The general form is corroborated by pipeline-survey material — **REPORTED**, Ynput: pipeline TDs report that *maintaining software variants and dependencies makes implementation outside of standard platforms extremely difficult*, which pushes studios away from adoption.

### 3.5 Licence arithmetic

Mechanism established in §1.12. **hython requests a Houdini Engine licence.** Engine is **$525/yr** per workstation, **$795/yr** floating for one seat (**OBSERVED**, §1.11). `HOUDINI_SCRIPT_LICENSE` and `HOUDINI_HYTHON_LIC_OPT` exist specifically to stop headless processes from consuming interactive FX/Core seats (**REPORTED**).

**INFERRED:** a tool architecture is not licence-neutral. Spawning Houdini processes has a per-process cost and a per-process configuration burden; running inside an already-licensed session does not. On Indie the ceiling is structural rather than financial — Engine Indie is free on up to 3 machines but is *"only compatible with Houdini Indie files and assets"* (**OBSERVED**), and Indie itself is capped at 3 licences per facility with watermarked output.

### 3.6 Single-client assumptions, failing silently

**`capoomgit/houdini-mcp` issue #14**, 26 April 2026, **open**, 0 comments — **OBSERVED**, raw issue body, quoted at length because the mechanism is fully worked:

> **Symptom** — "When a second MCP client tries to connect to Houdini while a first one already holds the socket, the second client either times out on `socket.connect()` or **hangs silently with no log line on either side**… this manifests as `port did not bind within 60s` errors **despite `lsof` clearly showing Houdini `LISTEN`-ing on 9876**."
>
> **Root cause** — `server.py` is hard-coded single-client:
> ```python
> self.socket.listen(1)                  # backlog of 1
> if not self.client and self.socket:    # accept only when no current client
>     self.client, address = self.socket.accept()
> ```
> "Once the first MCP client is accepted, `self.client` is set and the QTimer's accept guard skips all further accepts. A second incoming SYN sits in the kernel queue (size 1), gets dropped silently if a third comes in… **There's no log on Houdini side because the second connect never reaches the accept loop.**"
>
> "The bridge side compounds this — its `HoudiniConnection` caches the socket via `if self.sock is not None: return True`, so **once a session connects it holds the slot for the entire bridge lifetime.**"
>
> **Triggers** — "Reloading Claude Desktop while a previous bridge child is still attached… Running Claude Desktop + Claude Code concurrently against the same Houdini… Probing the port from outside the bridge (e.g. health checks, multi-agent / aggregator setups)."

The property that makes this an adoption problem rather than a bug: **the failure is silent on both sides while the port visibly listens.** A user's diagnosis of "it's running, so something else is wrong" is reinforced by the evidence available to them.

### 3.7 The suggestion and the action disagree

**`Kazama-Suichiku/Houdini-Agent` issue #39**, 24 July 2026, **open** — **OBSERVED**, raw issue body (Chinese original, translation mine):

> 添加 wrangle 功能判断不准确 — "Adding a wrangle: the function determination is inaccurate"
> "AI 提出可以使用 Volume Wrangle，但点击添加按钮后，添加的是普通 wrangle"
> — *The AI proposes using a Volume Wrangle, but after clicking the add button, what is added is an ordinary wrangle.*

Two screenshots attached. Filed three days before this run.

The mechanism is a divergence between what the model recommended and what the tool's own action button did. **INFERRED:** a class of failure where the artist cannot trust the affordance even when the reasoning is correct — the tool's text and the tool's mutation are two different systems, and only one of them is being read.

### 3.8 Platform gaps that stay open

**`capoomgit/houdini-mcp` issue #2**, 4 April 2025, **still open at time of this run**, 4 comments — **OBSERVED**:

> "Changed all the paths etc. but I get `ModuleNotFoundError: No module named 'houdinimcp'` when trying to start the tool in Houdini. Maybe there are different settings for Mac? **The Blender one works identically for both**"

Open for **~16 months**. The comparison the user reaches for is telling: the equivalent Blender integration is cross-platform and this one is not.

Compounding, **OBSERVED** (§1.2): H22 **dropped Intel Mac (x86_64) builds**, so macOS Houdini is Apple-silicon-only from H22 forward.

### 3.9 Cultural rejection, independent of whether the tool works

**REPORTED**, [Blender Artists thread, 28 April 2026, ~20 visible replies](https://blenderartists.org/t/from-blender-mcp-to-3d-agent-anthropic-partners-with-blender-claude-ai-connector-now-official/1639106):

> "fundamentally unethical, it's built on a lot of violence and has the express purpose of replicating human creativity" — with a call to ban generative AI outputs across Blender projects
>
> "finding the desire to continue making things in a world that will just scrape it, twist it and make a cheap knock-off mimic… has been very tough"

A **practical** objection from the same thread, distinct from the ethical ones: a developer reported their *Simply Loopy* addon was copied, processed through AI, resubmitted as a separate addon, and **received official Blender approval** — asking *"how can you trust anything on the official extensions platform if this is the case?"*

And one first-hand positive: *"I wrote 80% of my code and the 20% wrote by AI was pretty technical to a point it would have added extra weeks to figure this stuff out."*

The commercial consequence is measurable: **Anthropic's €240,000/yr Blender patronage was downgraded to a one-off donation within roughly a month**, following community reaction (§2.5). — **REPORTED**.

**Recorded without interpretation**: this axis is real, it is documented, and it operates independently of whether a tool functions.

### 3.10 Capability to integrate anything at all

**REPORTED** — Ynput / AYON, *The State of Animation & VFX Pipelines*, publisher **Ynput s.r.o.**, [ayon.app page](https://ayon.app/the-state-of-animation-vfx-pipelines) (the ynput.io URL 301-redirects here):

- *"Over a third of studios spend less than 5% of their budget on pipeline development"*
- **37% don't know their pipeline spend at all**
- *"only a small minority investing more than 10%"*
- *"Only 8% of studios feel highly prepared to tackle upcoming trends"*
- **78%** *"see the biggest challenge as balancing technical complexity and ease of use"*
- *"Over half of studios"* regularly use Maya
- Top obstacles, as summarised: **cost, lack of expertise, integration challenges**; *"justifying investment still tough and finding pipeline experts to implement new technology as rare as ever"*

**A version discrepancy I could not resolve.** The ayon.app page presents itself as **2026**. A separate search result describes *"the latest Pipeline Report, recently updated for 2025… based on survey responses from over 200 studios worldwide."* I could not determine from public pages whether the 2026 page carries new fieldwork or restates 2025 data, and the **full report is gated**. Sample size, recruitment method, and size distribution are all behind that gate (§5.2). **The percentages above are therefore REPORTED figures whose denominator I have not seen.**

### 3.11 HDA and version discipline on the farm

**REPORTED, and the sources are render-farm vendor blogs, which is weak** — [SuperRenders](https://superrendersfarm.com/article/houdini-cloud-render-farm-setup-guide-2026), [Artivoxa](https://www.artivoxa.com/building-reusable-hdas-houdini-digital-assets-for-your-studio-pipeline/):

- *"if a node in your network references a custom HDA version that isn't part of your submission, the scene won't cook"*
- *"a scene saved with HtoA 7.1 will not always load cleanly on a worker running HtoA 6.3"*
- Custom HDAs need embedding via Operator Type Manager → *Save to Embedded*, or copying into `$HIP/hda/` before submission

**No primary studio account of this failing on a real show was found** (§5.5). Recorded at its actual strength: vendor advice describing a known class, not an observed incident.

### 3.12 Even successful agentic systems are scoped away from final pixels

**REPORTED, partial-sentence source** (§2.6): the Ubisoft DigiPro 2026 agentic asset-production system is characterised as *"primarily intended as a rapid prototyping tool rather"* than a replacement.

Independently, **REPORTED, vendor marketing** — MindStudio on Claude + Blender MCP, [link](https://www.mindstudio.ai/blog/claude-blender-mcp-real-world-performance), 6 May 2026:

**Reported as working:** scene assembly from description; plausible-but-not-production materials; anything the Python API supports; iterative refinement without re-editing scripts.

**Reported as not working:**
- *"Trying to get Claude to model a human face, a realistic tree"* fails consistently
- Cannot manage *"edge loops, pole management, or subdivision-ready topology"*
- Node networks: *"anything beyond a few nodes tends to produce errors"*
- *"Creating a properly rigged character with weight painting"* — *"not realistic"*
- *"Claude's spatial understanding is imprecise. It'll place objects approximately where you describe"*
- *"not a replacement for a 3D artist"*

**When they report it is worth using:** *"The value isn't generating a scene from scratch but navigating and modifying a deeply nested node structure that would take significant manual effort to traverse. That's the kind of task where backend computer-to-computer communication has a real advantage over a human clicking through menus."*

And their stated cost/benefit: *"A skilled Blender artist who knows what they're doing probably doesn't need the MCP at all. A non-expert using it as a crutch will burn through tokens faster than they expect and still need to fix the output."*

Interested source. Recorded as REPORTED, in its own words, because it is the most specific public capability boundary found and it was published by a party with no incentive to flatter the category.

### 3.13 What was NOT found on Q3, and it is the most important gap in this leg

**Zero accounts were found of any Houdini AI or MCP tool being trialled at a studio and removed.** Not one. Every user-side account located is a solo developer, a hobbyist, a student (*"I hope to use it to complete my Houdini homework, please"* — Houdini-Agent #9), or a tool author.

The closest thing to a candid practitioner assessment found is a developer describing his own repository — **REPORTED**, [sidefx.com/forum/post/460855](https://www.sidefx.com/forum/post/460855/), user `impacthypothesis`, 1 May 2026 and 13 June 2026:

> "everything is well documented and project scope is well defined, still a work in progress but **i've found some things that aren't noted anywhere**."
> "**the highest value what i've got on the repo now is the bugs i found**, but if you get back to me in a while i will certainly have something more substantively functional."

And one second-hand line from search, source not verified directly: a developer describes usefulness as *"hit or miss"* while finding it useful *"for refactoring HDAs and tedious tasks."*

**INFERRED, and stated as the leg's central negative result:** the failure modes in §3.1–§3.12 are assembled from *adjacent* evidence — compliance controls, open bug trackers, a different DCC's ecosystem, survey aggregates, and vendor marketing. **The population of studios that have run a Houdini AI agent on real shots and stopped does not appear to exist yet in any published form.** Section 5 records this as the primary NOT-FOUND.

---

## 4 · Q4 — What is a mid-sized studio's actual constraint?

### 4.1 The named studios, with their own words

**REPORTED** — VFX Voice, *"What It Takes For Smaller VFX Studios To Survive – And Thrive"*, **6 January 2026**, [link](https://vfxvoice.com/what-it-takes-for-smaller-vfx-studios-to-survive-and-thrive/). VFX Voice is the Visual Effects Society's publication; these are interview quotes, attributed.

| Studio | Person | Quoted |
|---|---|---|
| **BUF** (Paris/Montreal) | Olivier Cauwet, VFX Supervisor | *"We wanted to have fewer artists, so now we're **around 140**, which allows us to preserve our philosophy."* · *"We are working on **proprietary software, so we're not using Nuke or Maya**. We have an R&D department which **releases software every three months**."* |
| **Wylie Co.** (Culver City) | Jake Maymudes, CEO & COO | *"In 2024, we **lost money for the first time in 10 years**, but this year we're making money."* · *"Specializing isn't a good business model… If you're a working group of artists capable of doing great work in a variety of different ways, that's what you should sell."* |
| **MARZ** (Toronto) | Jonathan Bronfman, CEO | *"Going out there right now as any run-of-the-mill visual effects provider, you're using the **same tech and pool of artists; there's no differentiation**."* · *"**We've placed ourselves in the arena of AI and machine learning. We have to, otherwise what's our competitive edge?**"* |
| **PFX** (Prague) | Lukas Keclik, Producer & Partner | *"We realized that the company wasn't small anymore, but not big enough… We didn't want to be a big corporate studio."* — expansion via acquisition, for geography and subsidy access |
| **Freefolk** (London) | Paul Wright, COO | *"You have to cast your net wider today than you might have needed to a long time ago… maintain the quality level that you would like to be able to deliver."* |
| **Haymaker VFX** (Gothenburg/LA) | Leslie Sorrentino, EP | *"Size does matter, and we have to grow exponentially."* |

The article names the structural condition directly: **the "midsize problem"** — *too small to compete with major studios owned by streamers, too large to maintain boutique agility.*

Also **REPORTED** from search aggregation, lower confidence: **RISE Visual Effects Studios** at approximately **240 permanent staff plus ~70 freelance artists**; BUF *"now operates around 140 artists, down from 300 employees."*

### 4.2 How many studios, and how big

**REPORTED, and the sources are market-research aggregators of unknown method** — figures conflict and are recorded as a range, not a number:

- *"Over 450 studios worldwide"* specialising in VFX production
- *"approximately 617 VFX studios globally with an estimated talent pool between 35,020 and 122,895 employees"*
- Range spans *"individuals to 10,000-strong VFX companies"*

**REPORTED, with a self-declared method** — Adrian Tsang, *"A Snapshot of 'Hollywood' VFX Studio Sizes"*, **10 December 2022**, [link](https://medium.com/@adriantsang/a-snapshot-of-hollywood-vfx-studio-sizes-eebfec1514cf). Method: IMDB credits from *Andor, Foundation, Stranger Things, Rings of Power, Black Panther 2, Mandalorian, Black Adam*, cross-referenced to LinkedIn company pages for self-reported employee counts.

- Sample total: **~40,000 employees**
- Author's own extrapolation: industry is *"3–5x larger"* than the sample → **120,000–200,000**; *"1000+ companies, and 100K+ employees"*
- Author's own stated caveats: underrepresents small/support/pre-production companies; limited credit visibility for smaller vendors; umbrella corporations (Disney, DNEG/ReDefine, Technicolor) hard to attribute

**Three-and-a-half years old, LinkedIn self-report as the measurement instrument, tentpole-only sample.** Recorded because it is the only size study found that publishes its method at all.

### 4.3 The licence ceiling is a structural fact about studio size

**OBSERVED**, §1.11. Restated here because it bears directly on Q4:

```
Indie      max 3 licences per facility · watermarked output · <$100K revenue
Core / FX  max 5 workstation licences per facility (online purchase)
Engine     max 5 workstation licences per facility · GAL floating from $795/yr
```

**INFERRED:** the online-purchase path tops out at 5 interactive Houdini seats. A studio above that is in a sales relationship with SideFX, which means it has a negotiated contract, a named account, and — by implication — someone whose job includes licence administration. The transition from "buy it on the website" to "call sales" happens between 5 and 6 Houdini seats.

**ASSUMED, labelled:** that this ceiling correlates with the presence of a pipeline function. I found no evidence connecting seat count to pipeline-team existence. It is a plausible reading and nothing more.

### 4.4 Small vs large, operationally

**REPORTED** — CG Spectrum, [link](https://www.cgspectrum.com/blog/small-vs-large-vfx-studios). Educational marketing; treated as such.

| | Large | Small |
|---|---|---|
| Roles | *"more specialized roles"*; risk of being *"pigeonholed"* | staff *"perform a wider variety of tasks"* |
| Pipeline | *"more complex pipeline and stricter procedures"*, dedicated pipeline TDs and developers | *"usually a little bit more nimble"*, *"fewer steps/processes"*, *"less stringent"* |
| Pressure | *"busier workdays and more overtime"*, *"more prominent clients"*, *"tighter deadlines"* | *"less demanding clients and/or fewer projects"* |

**No headcount ranges. No tool-selection process. No decision authority.** The article does not address who chooses tools at either size.

Corroborating only the pipeline-staffing direction, **REPORTED**: *"At larger film studios, the VFX pipeline is usually more complex but often runs smoother as there are more pipeline TDs and developers keeping it in check."*

### 4.5 What Q4 could not establish

Three of the four things the brief asked for under Q4 were **not found at any usable specificity**:

- **Pipeline-TD headcount** — no ratio, no absolute figure, at any studio size (§5.3)
- **How studios evaluate new tools** — no described process, no trial protocol, no criteria (§5.4)
- **Who decides** — no evidence on decision authority at any size (§5.4)

What *was* established: pipeline **budget** share (§3.10, gated denominator), named studio **headcounts** (§4.1, six studios), the **licence ceiling** (§4.3, primary source), and the **structural "midsize problem"** (§4.1).

**Stated plainly:** the brief's premise that *"a tool adopted by a 12-artist shop is a different product from one adopted by a 400-artist shop"* is not something this leg confirmed or refuted. It found the vocabulary for that distinction and no data underneath it.

---

## 5 · NOT FOUND

Questions that could not be answered from reachable sources. This section exists to tell S2 where its own reasoning has no floor.

**5.1 — Any primary SideFX statement about an official Houdini AI agent or assistant.** The claim *"SideFX is already working on some kind of AI-Agent"* appears in community discussion only. Ten SideFX pages were read (§1.13); none references such a project. **Absence of a public statement is not absence of a project.**

**5.2 — The Ynput/AYON survey methodology.** Sample size, recruitment, studio-size distribution, and pipeline-TD headcount are behind a gate. The public page states 2026; a search result describes a 2025 update with *"over 200 studios."* I could not determine which fieldwork the published percentages come from. **Every Ynput percentage in §3.10 has an unseen denominator.**

**5.3 — Pipeline-TD-per-artist ratio, at any studio size.** Searched directly. Nothing quantitative exists in reachable sources.

**5.4 — Who signs off on a new tool at a mid-size studio, and what the evaluation process is.** This is a named Q4 sub-question and it returned nothing. No trial protocol, no criteria, no decision authority, at any size.

**5.5 — Any first-hand account of a Houdini AI/MCP tool trialled at a studio and removed.** Zero, and this is the leg's headline gap (§3.13). The entire Q3 answer is built from adjacent evidence.

**5.6 — Any independent, non-vendor measurement of token cost per useful operation in a DCC agent.** The single figure found (§3.3) is competitor marketing describing one unreproducible run.

**5.7 — SideFX forum threads behind the login wall.** `sidefx.com/forum/topic/31201` ("Batch render licensing – potential dealbreaker?") returned a login page. Older forum history is therefore not reachable by this method, which biases every forum finding in this document toward **recent, publicly visible threads**.

**5.8 — `code.blender.org` VFX Reference Platform post.** HTTP 403. The vendor-side cost argument for platform conformance was not read.

**5.9 — DigiPro 2026 abstracts.** ACM DL returned 403 on both the proceedings page and the front-matter PDF. §2.6 rests on trade coverage and search snippets. **The Ubisoft "rapid prototyping tool rather" quote is a truncated fragment from a secondary source and has not been verified against the paper.**

**5.10 — The price of Houdini AI Assistant.** The Gumroad product page returned only a title with no body content.

**5.11 — Whether any commercial Houdini AI tool has paying *studio* customers**, as distinct from individual buyers. No evidence either way. Neither product's thread contains a customer of any kind.

**5.12 — MPA CSBP v5.3 / v5.3.1 primary document.** OR-5.0 was read through a third-party compliance consultancy's version comparison and search snippets, **not the MPA document itself**. The control's existence, its version of introduction, and its quoted text are all one source-hop from primary. Given that §3.1 is the strongest *contractual* finding in this leg, this is the gap most worth closing.

**5.13 — H22 adoption rate.** Nothing on whether studios have moved off H20.5/H21 onto H22, at what pace, or at all. H22's public release is ~11 days old at the time of this run.

**5.14 — SideFX's own AI roadmap or policy statement.** The closest primary artifact is a product page about ONNX and synthetic data (§1.14). Two SideFX conference talks exist — *"The Future of AI in Houdini | Panel Discussion"* and *"Leveraging generative AI for 3D content generation"* — **neither was watched or transcribed**, and a panel discussion is not a policy statement in any case.

**5.15 — The `atayilgun/Houdini-claudecode-mcp` repository.** Appeared in search results, 404 on API lookup. Renamed, deleted, or made private between indexing and this run.

---

## 6 · Drift

**6.1 — S0 was dispatched into a directory that is not a git worktree.**

The stated working directory `C:\Users\User\SYNAPSE\.claude\worktrees\s0-forensic` contains only `.claude/` (a `settings.local.json` enabling MCP servers, and an `.orch_launched` marker stamped `2026-07-27T14:41:29`). `git worktree list` does not include it; the six registered worktrees are `h1-schemas-b`, `ledger-moneta-seam`, `p1-panel-redesign`, `q2-baseline`, `s2-forensic`, `v0-m2-reconcile`. `git status` from inside it reports against the main repo at `feat/repair-heats-01`.

Constitution Article V: *"Every parallel agent gets its own git worktree."* S0 did not get one. **Note that `s2-forensic` exists** — so the intent was present and the S0 creation did not happen or did not persist.

Consequence: writing to a relative `harness/notes/` from that directory would have created an orphan tree outside the repo. **Both oracle artifacts were written to the real tree** at `C:\Users\User\SYNAPSE\harness\notes\`.

**6.2 — `harness/readonly-settings.json` would have made this leg impossible.**

The read-only profile allows exactly two WebFetch domains:

```
"WebFetch(domain:www.sidefx.com)",
"WebFetch(domain:sidefx.com)",
```

and does not allow `Bash(gh:*)`.

Q1 is answerable within that fence. **Q2, Q3 and Q4 are not.** This leg's evidence came from `github.com` (the whole of §2.1, via `gh api` — the strongest evidence in the document), `anthropic.com`, `vfxplatform.com`, `ayon.app`, `vfxvoice.com`, `cgchannel.com`, `ttpn.org`, `cytrust.fr`, `mindstudio.ai`, `medium.com`, `blenderartists.org`, `3dvf.com`, `forums.odforce.net`, and `cgspectrum.com`.

The brief's own framing is that the market *"is the only input that requires looking outside."* The fence for a read-only leg permits looking outside to exactly one place — the vendor.

**A leg run behind that profile would have returned a confident, well-sourced, SideFX-only picture and reported green.** It would not have failed; it would have answered a narrower question than the one asked, which is the failure shape R80 names. This is a `for_ruling` item, not something S0 decides.

**6.3 — The fence this run was actually behind.**

Not `readonly-settings.json`. This leg ran in the interactive session under the project `.claude/settings.json`, evidenced by the calls that succeeded (`gh api`, non-SideFX `WebFetch`) which that profile denies. Recorded honestly per R25 rather than claiming a profile that was not applied.

---

## 7 · Standing

Never pushed, never merged, never tagged. Nothing outside `harness/notes/**` was written. No SYNAPSE source file was read — the codebase is S1's leg, and the market picture in this document was assembled without reference to what SYNAPSE happens to contain.

Zero recommendations.

**The prescriptive-language check, measured rather than asserted.** Producer: `grep -o -i "should" harness/notes/forensic/S0_SCOUT.md | wc -l`.

The oracle asks for zero uses of the prescriptive verb. Run against an earlier draft, the grep returned **3**: two were this document's own compliance statements *mentioning* the word, and one is inside a verbatim quotation. The closing statement asserted the word "does not appear in this document" while itself containing it — a claim that was false at the moment it was written, and false *because* of how it was written.

Both self-referential uses are now removed. **One occurrence remains, at §4.1**, inside an attributed verbatim quotation from Jake Maymudes of Wylie Co. It is left intact: editing a source quotation to satisfy a lint would be falsifying evidence, which is a worse defect than the one it fixes.

**Final state — authored prescriptive uses: 0.** The grep now returns **2**, and both are accounted for:

1. **§4.1** — inside the attributed Wylie Co. quotation.
2. **This section** — inside the producer command string above. Law 2 requires a number to name the producer that emits it, and this producer necessarily contains the token it counts.

There is no phrasing of a self-measuring check that drives its own count to zero. The count is 2, the reason each occurrence exists is written down, and neither is this document prescribing anything.
