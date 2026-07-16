# Adjudication Appendix — H22 Release Notes / Launch Materials

**Artifact:** Houdini 22.0 launch surface, fetched live 2026-07-16 — SideFX What's New page (`sidefx.com/products/whats-new-in-h22/`), official docs What's New index + subpages (`sidefx.com/docs/houdini/news/22/{index,kinefx,ml,vex}.html`), CG Channel release article (2026-07-16), 80.lv release article, DIGITAL PRODUCTION keynote article (2026-06-23) + release-day retrospective (2026-07-16).
**Runbook context:** §9 step 7 (release-notes scan), Leg 2, `drop.json` = H22.0.368 / py 3.13.10 / USD 0.26.5 / PySide 6.8.3 (written 2026-07-15).
**Protocol:** blueprint §10. This appendix revises nothing; escalations return to the human + CTO.

---

## (a) First-party MCP/agent surface — C2 CLOSED

| # | Claim | Tier | Verdict |
|---|---|---|---|
| 1 | H22 is released: 2026-07-15, build 22.0.368 | VERIFIED-WEB (80.lv "officially released… July 15"; CG Channel 7/16) **+ VERIFIED-RUNTIME** (`harness/state/drop.json`, versions captured live inside H22.0.368) | **CORRECT — C1 closes as launched.** The release-notes fetch C1 demanded now exists. "Was announced" upgrades to "has shipped," proven both ways. |
| 2 | The **shipped** H22.0 release contains **no first-party MCP/agent surface** | VERIFIED-WEB — five independent surfaces all silent: official What's New page (zero MCP/AI-agent mentions), docs news **index**, docs **kinefx.html**, **ml.html**, **vex.html** (each explicitly checked: absent); CG Channel + 80.lv release articles also silent | **C2 verdict: vacuum CONFIRMED at drop.** ADOPT into G4 as designed ("C2 closes at runbook step 7"). |
| 3 | SideFX **announced** a first-party **"APEX Script Comfort Package"**: VS Code extension (autocomplete), in-Houdini Python panel, an **MCP server** over a curated syntax/snippet library, local-LLM natural-language **rig generation** — shipped status: **"preview that will be released later… not a regular production feature in Houdini 22"** | VERIFIED-WEB, **single-outlet** (DIGITAL PRODUCTION 6/23 keynote + 7/16 retrospective, quoting SideFX's own character overview). Absent from all official H22.0 docs — consistent with "deferred preview" | **ADAPT → G4.** C1 discipline applied: "provides an MCP server" reads as **"was announced."** The vacuum holds for the shipped build but is now **dated and scoped**: first-party MCP arrives later, **inside the rigging lane**. **ESCALATE: possible version bump** — C2's text ("no public evidence of a first-party MCP/agent surface") now needs a rider; human + CTO decide rider vs. closure-as-designed. |

**Posture consequence (G4, no re-litigation needed):** the announced package validates MCP-as-channel and lands in the lane SYNAPSE conceded (Non-Goal 1). Their MCP = curated rig-script snippets ("token-efficient" marketing); SYNAPSE = stateful scene agency. The four differentiation columns (in-process perception events · undo-wrapped mutation · provenance · substrate memory) remain unoccupied by anything announced. D-H22-1 deck: position **complementary to**, never competing with, the APEX MCP.

## (b) KineFX/APEX scope — BOUNDARY-PRESSURE EVENT (logged, rejected)

| # | Claim | Tier | Verdict |
|---|---|---|---|
| 4 | H22 character scope is the headline: ~60 named rig components/SOPs/tools (Autorig Builder templates, Biped Setup/Retarget, Set Driven Keys, Character Picker, nested Motion Mixer clips, FBIK, ragdoll forces, rig inversion, APEX Graph Debugger, muscles/hair/crowds) | VERIFIED-WEB (docs kinefx.html, itemized) | **REJECT for scope — Non-Goal 1**, no re-litigation. Recorded for G2 awareness only. |
| 5 | **Rigging LOPs toolset (Beta)** — rig/animate characters in the USD stage context, Hydra scene-index plugin | VERIFIED-WEB (docs kinefx.html) | **REJECT for scope.** New vector: rigging now enters SYNAPSE's own `lop` authoring domain. The drift term is **capability-based, not context-based** — a rig-authoring op in LOPs is still rigging. |

**Pressure grew — one event, three vectors:** (1) headline-scale rigging surface; (2) first-party MCP announced *in* the rigging lane (natural-language rig generation — expect "SYNAPSE should bridge/compete" pulls); (3) rigging entering the LOP context (Beta). **Drift term re-affirmed in checks vocabulary [verified by local read this dispatch]:** `harness/verify/checks.py::check_no_rigging_drift` + `python/synapse/server/authoring_domains.json` (`{"domains": ["cop","lop","sop","karma","usd"]}`; drift terms apex/rig/rigging/kinefx/muscle/cfx = deterministic guardrail failure). SideFX occupying the lane first-party makes the concession *more* correct: the vendor's floor is now the vendor's product. The answer stays no, including proxy variants.

## (c) G1–G9 impacts

| # | Claim | Tier | Verdict → gap |
|---|---|---|---|
| 6 | Terrain and oceans **move into Copernicus**; new grunge/baking/texture-synthesis tools, 2D ripple solver, experimental 3D texture painting | VERIFIED-WEB (official What's New + CG Channel) | **ADOPT → G2** (step-5 COP audit churn confirmed) **+ G9** (COP conformity rulebook changes under it, as the blueprint predicted). |
| 7 | **OpenGL renderer removed** (Vulkan-only, GPU subdivision); **Qt5 builds dropped**; macOS Apple-Silicon-only | VERIFIED-WEB (search synthesis + DP retrospective) | **ADOPT → G2** (step-6 Qt smoke stakes; PySide 6.8.3 per drop.json [VERIFIED-RUNTIME]). |
| 8 | Python **3.13.10** primary (≠ cp311); a separate **3.11 build** reportedly available | 3.13.10: VERIFIED-WEB + VERIFIED-RUNTIME (drop.json match). 3.11 build: **UNVERIFIED** (single source, not confirmed on sidefx.com) | **ADOPT → gate-0.1** (already re-opened by drop.json; sidecar remains ruled default). The 3.11 build is deliberation *evidence only* — verify on sidefx.com/download before it influences anything; decision is human. |
| 9 | ML/splat TOP surface is real: **ML Train GSplats TOP**, ML Preprocess GSplats TOP, ML Train NCA/Computer Vision TOPs, ONNX SOP/COP extensions, Neural Terrain Generate SOP, Neural Layer to Depth (MoGe-2) / Mask (SAM2) COPs | VERIFIED-WEB (docs ml.html) — **docs = intent; node-type names are V0** until probed | **ADAPT → G8** (splat candidate stays `ratified:false`, orchestrate-never-author) **+ route all node names to runbook step-9 probe list.** Whitepaper's `top::gaussian_splat_train` confirmed phantom-shaped — real docs use different naming. |
| 10 | HOM deltas: `hou.ChannelEditorPane` **removed** (→ `hou.ChannelEditor`); several `hou.ApexNode`/`hou.Node` methods removed; new classes `hou.CopCable`, `hou.DetachedAttrib`, `hou.Camera`/`hou.CameraPrim`, `hou.OpenCLDevice`, `hou.UniNode*` | VERIFIED-WEB (docs vex.html) — **all symbols V0 until introspected** (P1) | **ADOPT → G2 / step-9 + doc-scout probe queue.** Nothing here enters code or specs as fact without a live probe against 22.0.368. |
| 11 | The announced APEX MCP markets itself as **"token-efficient"** | VERIFIED-WEB (DP, single outlet) | **ADAPT → G6.** Token-efficiency claims are now first-party-adjacent marketing; measured numbers (latency/token/Shot-010 tracks) gain urgency. |
| 12 | Solaris: new layout/world-building/set-dressing tools; Karma "smaller update" | VERIFIED-WEB (official What's New + CG Channel) | **ADOPT → G2/G8 intake** (tool names V0, enter via re-sweep only). |

**No change:** G1 (port priority unchanged — if anything reinforced by claim 11), G3 (nothing on background/perception in any launch material — event-push moat intact), G5, G7.

## Step-9 probe routing (nothing below is fact yet)

`ML Train GSplats` / `ML Preprocess GSplats` / `ML Train Neural Cellular Automata` / `ML Train Computer Vision` TOP internal names · `Neural Terrain Generate` SOP · ONNX COP/SOP deltas · `hou.CopCable` · `hou.DetachedAttrib` · `hou.Camera` / `hou.CameraPrim` · `hou.OpenCLDevice` · `hou.UniNode*` · `hou.ChannelEditor` (and confirm `hou.ChannelEditorPane` absence) · removed `hou.ApexNode` methods.

## Residuals + self-attack notes

- Claim 3 rests on one outlet (two DP articles quoting SideFX's own overview). Treat "Comfort Package" naming and exact contents as soft until a SideFX-authored page exists; the *deferral* is the load-bearing part and is corroborated by five silent official surfaces.
- WebFetch summarization could miss an in-page mention; mitigated by five independent official surfaces + two independent outlets, all consistent. The SideFX changelog/journal for 22.0.368 was not fetched (login/dynamic) — cheap follow-up if anyone doubts the vacuum.
- Claim 8's "separate 3.11 build" is deliberately quarantined at UNVERIFIED — do not let it soften the sidecar posture.

## Verdict counts

ADOPT 6 · ADAPT 3 · REJECT 2 · CORRECT 1 (12 load-bearing claims) · boundary-pressure events: 1 (three vectors) · escalations: 1 (C2 rider → possible version bump, human + CTO).

**Sources:** [SideFX What's New in H22](https://www.sidefx.com/products/whats-new-in-h22/) · [H22 docs news index](https://www.sidefx.com/docs/houdini/news/22/index.html) · [kinefx.html](https://www.sidefx.com/docs/houdini/news/22/kinefx.html) · [ml.html](https://www.sidefx.com/docs/houdini/news/22/ml.html) · [vex.html](https://www.sidefx.com/docs/houdini/news/22/vex.html) · [CG Channel release](https://www.cgchannel.com/2026/07/sidefx-just-released-houdini-22/) · [80.lv release](https://80.lv/articles/houdini-22-is-out-now-bringing-native-gaussian-splats-new-ui-and-more) · [DIGITAL PRODUCTION keynote](https://digitalproduction.com/2026/06/23/here-comes-houdini-22/) · [DIGITAL PRODUCTION retrospective](https://digitalproduction.com/2026/07/16/houdini-22-how-right-were-we/)
