# RETINA Blueprint Reconciliation — 2026-07-16

**Artifact:** `docs/SYNAPSE_RETINA_BLUEPRINT.md` v1.0, received 2026-07-16 evening, committed verbatim per its own F3 rule.
**Protocol:** the v5.24 precedent — a blueprint is reconciled against the repo **before** execution; anything authored above the code is corrected here, not silently in the blueprint. Per the blueprint's own §12 rule, this record and the future perception truth catalog outrank any INFERENCE line in the blueprint.
**Administrator note:** unlike the v5.24 drop-harness blueprint (which re-specified shipped work) and the pasted "SideFX memo" (which was refuted), this document reconciles **clean**: it is internally consistent with the v5.26.0 repo state, self-labels its inferences, and its single stale line is an INFERENCE it explicitly asked to have closed.

---

## 1 · Truth-appendix closures (what today's evidence already settles)

| Blueprint §12 line | Label there | Closure | Evidence |
|---|---|---|---|
| `opencv-python(-headless)` 5.0.0.93 abi3 win_amd64 on PyPI, 2026-07-02 | VERIFIED | **RE-VERIFIED LIVE this administration** — exact filename `opencv_python_headless-5.0.0.93-cp37-abi3-win_amd64.whl` (43.8 MB), released Jul 2 2026, abi3 not per-version tags. | PyPI files page, fetched 2026-07-16 evening |
| SYNAPSE host build = H22 **py3.11** (`_vendor` remains CP311) | INFERENCE — "close in drop record" | **CLOSED — CORRECTED.** The H22 host Python is **3.13.10** (`harness/state/drop.json`, captured live inside 22.0.368 on drop day), and `_vendor` is **dual-ABI cp311 + cp313** since the drop-day re-vendor (commit `38b33b6`; `_VENDOR_PYS = {(3,11),(3,13)}`). **Impact on the blueprint: none-to-positive** — the derived move (P5: worker in its own venv on the abi3 wheel) is unaffected; the abi3 wheel spans both ABIs regardless. The §1 sentence "H22's dual Python builds" remains true (SideFX ships a separate 3.11 build), but SYNAPSE's *installed* host is the 3.13.10 build. | `harness/state/drop.json` · `docs/reviews/h22-abi-verdict.md` |
| `Usd.GetVersion()` python symbol | INFERENCE — "runtime check" | **CLOSED — VERIFIED-LIVE.** Called live during the CTO-01 probe: `Usd.GetVersion()` → `(0, 26, 5)` on the running 22.0.368. | `docs/reviews/h22-live-reconfirm-2026-07-16.md` (CTO-01 section) |
| H22 = 22.0.368; USD 26.05; Python 3.13.10 default; Qt5 dropped | VERIFIED (launch coverage) | **CONFIRMED against the installed build** — with the notation fix: USD is **0.26.5** (`drop.json`), matching the blueprint's "26.05" intent. Qt/PySide 6.8.3 confirmed (qt-smoke artifact). | `harness/state/drop.json` · `docs/reviews/h22-qt-smoke.md` |
| SYNAPSE v5.26.0 live-verified; 4,387/0 | VERIFIED | **CONFIRMED** — and already advanced: master sits at 4,387 passed / 0 failed / 97 skipped post-W.4/U.1-fold merges. | this session's post-merge suite runs |

## 2 · Risk-register corrections (facts that *improve* the register)

- **"H21 uninstalled at v5.25.0" is half-stale:** H21.0.**671** (the catalog-stamped build) is uninstalled, but **H21.0.773 is installed on this machine** and was used *today* as the U.1-fold crucible's second-major live verification. The register's mitigation option ("keep one H21 instance for release gates") is **already satisfied** — with the known caveat, on record from that crucible, that the frozen 21.0.671 catalogs serve same-major-stale truth to a .773 host (accepted; the granularity note lives in `U.1b-H22-resolver-hardening`).
- **Zero-cv2 baseline confirmed pre-existing:** grep across `python/synapse/` finds no `cv2` import anywhere today — the M0 pin starts from a clean floor, not a cleanup.

## 3 · Repo-reality checks on §3/§6 references (all real)

| Blueprint reference | Repo reality |
|---|---|
| "perception channel, Phases A/B" | Real: `python/synapse/host/tops_bridge.py` (Phase A) + `scene_load_bridge.py` (Phase B) |
| "BL-007 class" (T0's target) | Real, documented: `docs/reviews/h22-cto-roadmap-2026-07-16.md` (N-8 pins) + wave-2 doc-intel; the synthesized-default path in `handlers_render.py` |
| zero-`hou` cognitive-boundary lint (the pin's pattern) | Real: `tests/test_cognitive_boundary.py` — the M0 pin mirrors it structurally |
| customData RFC gate (M. Gold) | Real, standing: `docs/RFC_agent_usd_ledger.md` gate registry — verdict-USD writes correctly stay off RETINA's critical path |
| major-aware host-hook pattern (P5) | Real as of today: the U.1-H22 fold shipped exactly this pattern for the connectivity catalog (`wiring.py::_pkg_catalog_path`) |

## 4 · Sequencing findings (the one genuine conflict surface)

1. **The render port wave vs. M1 host hooks.** The manifest writer + `.done` sentinel (M1) touch the render-submit path — the same surface the queued `render` port sub-wave will golden-pin. **Ruling required at M1 dispatch, not now:** either M1's hooks land *before* the render wave captures parity goldens (fix-before-freeze, the roadmap's own rule), or the render wave goes first and M1 rides a ratified post-wave cycle with golden updates in-cycle. Recorded on the RETINA.M1 queue entry; the gatewarden enforces whichever order is ruled.
2. **M4 is explicitly paired with the Copernicus expansion** (C.3/C.4/C.10, ratified + spec'd at `docs/SYNAPSE_COPERNICUS_EXPANSION.md`). The expansion's serialized builds (C.4→C.3→C.10) are queued ahead of M4; the pairing is natural — C.10's terrain COP recipes and M4's agent-authored QC COP nets share the `cops_create_node`/recipe surface, and the neural-preflight honesty rule is shared verbatim.
3. **No file-ownership conflicts with anything in flight** — nothing currently building touches the render-submit path or a `retina/` tree.

## 5 · Cross-reference passes

Two read-only agent passes (HDK × blueprint; HAPI × blueprint) were dispatched at administration time — targets: aiming the M1 probe at any HDK-named Karma object-ID/cryptomatte truth; the husk/ROP hook surface; EXR channel-layout facts for T0/T1; and HAPI's versioned image-extraction API as the existence proof behind §10 asks #2/#3. **Their sections append below when they land.** Per the blueprint's own rule, anything they surface is probe-*aiming* only — nothing is coded against until the M1 catalog verifies it live.

## 6 · Administration verdict

**RECONCILED — CLEAN, with one INFERENCE corrected (host Python / vendor ABI) and two INFERENCE lines closed for free by today's live evidence.** M0 proceeds: this record + the blueprint + the zero-cv2 pin commit together. The six miles enter the flywheel queue as gated cycles (M1 next; M2–M5 sequenced). The blueprint governs; this record and the M1 catalog outrank its INFERENCE column.

---

## HAPI cross-reference (agent pass, 2026-07-16)

**Executive summary.** HAPI's relevance to RETINA is exactly one strategic footnote — but it is a *good* footnote: Houdini Engine already ships a semver'd, documented, changelog-tracked image-readback contract (`HAPI_RenderCOPToImage` → `HAPI_ExtractImageToMemory`, Engine 8.0→9.0), which is direct evidence that SideFX knows how to ship precisely what §10 asks #2 and #3 request — the asks can now cite SideFX's own precedent instead of arguing from first principles. As an actual runtime for RETINA, HAPI is disqualified twice over: structurally (an Engine session consumes a commercial license seat and re-couples the worker to a full Houdini core process, violating P5, while `ExtractImageToMemory` over Thrift IPC moves pixels across a wire, violating P4) and by capability (HAPI has **no Karma/ROP final-frame readback at all** — its image extraction covers material textures and COP nodes only, and its named format contract is LDR-skewed with no EXR constant). Nothing found changes a blueprint decision; three sections gain annotations, and the prior memo's "HAPI has no changelog" characterization gains one narrow correction that incidentally *strengthens* that memo's fabrication verdicts.

### (a) The versioned-readback existence proof — VERIFIED-WEB

**The contract exists and is semver'd.** The Engine 9.0 doc set (generated 2026-07-16, i.e. version-current for H22) documents a complete render→inspect→extract image pipeline:

- **Render step:** `HAPI_RenderTextureToImage()` (material textures), `HAPI_RenderCOPToImage()` (COP2 *and* Copernicus nodes, first output), `HAPI_RenderCOPOutputToImage()` (selectable output). Source: `hengine/_h_a_p_i__materials.html` — "Rendering to Image" / "Extracting Images."
- **Inspect/configure step:** `HAPI_GetImageInfo()` / `HAPI_SetImageInfo()` on a `HAPI_ImageInfo` struct; resolution, data format, interleaving, and packing are mutable pre-extraction.
- **Extract step:** `HAPI_ExtractImageToFile()` and `HAPI_ExtractImageToMemory()` + `HAPI_GetImageMemoryBuffer()`; re-extractable "as many times as you wish."
- **Planes/AOVs:** `HAPI_GetImagePlaneCount()` / `HAPI_GetImagePlanes()`; extraction by plane name ("C", "A", custom normal/bump/tangent; "C N" multi-plane — multi-plane files documented only for Houdini `.pic`).
- **Formats:** named constants are `RAW` (in-memory only), `PNG`, `JPEG`, `BMP`, `TIFF`, `TGA`, plus `.pic`. **No EXR constant exists**; `HAPI_DEFAULT_IMAGE_FORMAT_NAME` = PNG (`_h_a_p_i___common_8h.html`). Runtime enumeration via `HAPI_GetSupportedImageFileFormats()` may surface EXR from Houdini's IMG library, but the *documented* contract does not promise it. HDR data is reachable: `HAPI_ImageDataFormat` includes `HAPI_IMAGE_DATA_FLOAT16` / `FLOAT32` (default `INT8`); `HAPI_ImagePacking` covers SINGLE/DUAL/RGB/BGR/RGBA/ABGR — float readback exists via the RAW in-memory path.
- **The semver:** `HAPI_Version.h` pins `HAPI_VERSION_HOUDINI_ENGINE_MAJOR=9 / MINOR=0 / API=0` against `HAPI_VERSION_HOUDINI 22.0.382`, runtime-checkable without a session (`HAPI_GetEnvInt`). Documented compatibility rules: MAJOR "must match" per Houdini major; MINOR bumped on ABI breaks and "must match"; API/patch bumped per additive change — "a Houdini Engine plugin is compatible with Houdini versions that have the same or a higher HAPI_VERSION_HOUDINI_ENGINE_API number."

**What this proves for §10.** SideFX demonstrably ships, versions, and changelogs a programmatic image-readback contract on the Engine surface — with stated cross-version compatibility semantics. Asks #2 (hook stability) and #3 (blessed readback) are therefore not asking SideFX to invent a discipline; they are asking for the **HOM/Karma-surface equivalent of a contract Engine customers already get.** Sharpened pitch line for §10: *"Engine 8.0 added `HAPI_RenderCOPToImage`; 9.0 extended it. We're asking for the same contract where SYNAPSE lives — in-process HOM."*

**Honest scope limit (do not over-claim):** the contract is texture/COP-scoped. There is **no documented HAPI path that renders a ROP/Karma frame and reads back the beauty + AOVs** — no EXR named format, no render-product readback, no renderer named anywhere on the materials page. HAPI is an existence proof for the *discipline*, not for the *surface RETINA needs*.

### (b) Could a HAPI session serve RETINA? — honest answer: no, twice over

**(i) As a CRUCIBLE render oracle — INFERENCE (grounded in VERIFIED-WEB licensing/session facts): rejected.**
- **Licensing:** an Engine session acquires, in fallback order, "Houdini Engine → Houdini Core → Houdini FX → Houdini Engine Indie → Houdini Indie"; non-commercial licenses "explicitly unsupported" (`_h_a_p_i__licensing.html`). A CRUCIBLE oracle would consume a commercial seat per test session — on this Indie setup it would contend with the interactive seat.
- **Process weight:** out-of-process HARS "links directly to libHAPI and to core Houdini libraries and their dependencies" and "currently only supports a single client connection" (`_h_a_p_i__sessions.html`) — a full headless Houdini, not a light oracle.
- **Independence failure (the decisive one):** P6's oracle rule is that the same metric computed two *independent* ways must agree within ε. A HAPI-rendered COP result **is Houdini's own image library output** — using it to cross-check a COP QC net is circular. OpenCV remains the only genuinely independent oracle. HAPI adds cost without adding independence.

**(ii) As the worker's scene-truth reader — INFERENCE: rejected, direct P5/P4 violation.**
- P5 requires the worker hou-free and host-ABI-independent. In-process HAPI links `libHAPI` into the worker (ABI coupling per Houdini major — the exact re-grounding burden P5 exists to avoid); out-of-process still tethers the worker to a licensed HARS process lifecycle. Either way the worker stops being "own venv, testable without Houdini running" (§3's synthetic-manifest property dies).
- P4 requires pixels stay put. `HAPI_ExtractImageToMemory` over a Thrift socket/pipe/shared-memory session is pixels crossing a wire by construction — the architecture the blueprint's disk-outbox design deliberately replaces.
- The manifest already solves scene truth the P2 way: host exports camera + prim truth once, worker judges. HAPI would replace a JSON file with a licensed IPC dependency to obtain the same facts.

**Verdict: HAPI is not a road for RETINA — it is a precedent for §10.**

### (c) Eventing — NULL (marginal, and it flatters the existing design)

HAPI's completion model is **polling, exclusively**: `HAPI_GetStatus` / `HAPI_GetStatusString` for cook state, `HAPI_GetPDGEvents` + `HAPI_GetPDGState` for PDG ("completion is signaled through `HAPI_PDG_EVENT_COOK_COMPLETE`, discoverable only by polling the event queue"; no callback registration exists anywhere in the API — `_h_a_p_i__p_d_g.html`). The blueprint's §11 says "Not polling"; SideFX's only supported programmatic completion surface is poll-based. Nothing here overlaps or improves the `.done` sentinel design — it confirms an event-shaped completion signal has to be self-authored (ROP post-render script), because SideFX doesn't ship one on any surface. H22/Engine 9.0 additionally *deprecated* the two cook-progress counters — the surface is thinning, not growing toward events.

### (d) H22-new in HAPI (Engine 9.0) touching images/rendering — VERIFIED-WEB

From "What's New in HAPI" (`hengine/_h_a_p_i__migration.html` — the changelog the artist-facing page lacks):

| Item | RETINA relevance |
|---|---|
| `HAPI_CreateCOPImage()` gains a `new_node_id` output arg (9.0) | The COP image surface is under active development in H22 — supports the "Copernicus readback is a live, evolving contract" framing for ask #3 |
| SOP camera support: `HAPI_CameraInfo`, `HAPI_GetCameraInfo()`, `HAPI_GetCameraTransform()`, `HAPI_PARTTYPE_CAMERA` (9.0) | SideFX now treats *camera truth readback* as versioned API on the Engine surface — mild precedent for the manifest's camera-4×4 export being reasonable to bless |
| Engine 8.0 (H21) introduced Copernicus into HAPI (`HAPI_CreateCOPImage`, `HAPI_RenderCOPOutputToImage`, `HAPI_NODETYPE_LOP`) | Dating for the precedent claim in (a) |
| 13 legacy PDG work-item methods removed; cook-count functions deprecated (9.0) | Null for RETINA |

**Bonus cross-check on the prior memo:** the HAPI 9.0 changelog contains **none** of the pasted memo's four outstanding items (CORE-MATH, Vulkan-OpenCL interop, `walkonsurface`, `curveanimate`) — a **fourth** independent official surface returning null, further hardening the memo appendix's "trending almost-certainly-fabricated" posture. One narrow correction applied to that appendix's §(e): "HAPI has no changelog" is true of the artist-facing `docs/houdini/hapi/` page it fetched; the `hengine` doc set does carry a per-major changelog at `_h_a_p_i__migration.html`.

### Decision impact

| Blueprint section | Impact | Change or annotate? |
|---|---|---|
| §10 asks #2/#3 | Cite Engine's semver'd readback contract as SideFX's own precedent | **Annotate — strengthens, changes nothing** |
| §3 architecture (P4/P5) | HAPI evaluated and rejected as worker/oracle path (licensing, IPC pixel movement, ABI coupling, oracle circularity, no Karma readback) | **Annotate — confirms the design** |
| §11 "Not polling" | SideFX's only programmatic completion surface is poll-based; the `.done` sentinel remains the right shape | **Annotate — confirms** |
| §8 risk register | No new risk; no HAPI line item warranted | **No change** |

*Doc-set note: the hengine docs stamp `HAPI_VERSION_HOUDINI 22.0.382` vs the installed 22.0.368 — version-current, generated 2026-07-16. Sources: `hengine/` index, `_h_a_p_i__materials.html`, `_h_a_p_i__licensing.html`, `_h_a_p_i__sessions.html`, `_h_a_p_i_8h.html`, `_h_a_p_i___version_8h.html`, `_h_a_p_i___common_8h.html`, `_h_a_p_i__migration.html`, `_h_a_p_i__p_d_g.html`, `_h_a_p_i__fundamentals.html`, plus the artist-facing `docs/houdini/hapi/`.*

---

## HDK cross-reference (agent pass, 2026-07-16)

**Executive summary:** The HDK does **not** name Karma's object-ID render var anywhere (a genuine NULL — the ID-AOV spelling stays INFERENCE and M1's probe list below is now aimed), but it *does* document the cryptomatte pass-through mechanism (`UT_HUSDExtraAOVResource`, verbatim: "HUSD Interface for passing Cryptomatte AOV information through Hydra") and a surprisingly rich, documented husk callback surface (verbose-callback Python hooks, snapshot checkpointing, per-frame script flags) that directly evidences §10 ask #2. The sharpest de-risk of the pass is a documented timing trap: the usdrender ROP's Post-Frame/Post-Render scripts fire at USD-*generation* time, explicitly **not** when husk has finished pixels — the blueprint's §3 `.done` sentinel must ride `husk --postframe-script` (documented: "after each frame is rendered"), not the ROP param. The HDK changelog still has no H22 entry (re-checked verbatim today), and the HDK has zero Copernicus surface at all — which strengthens, not weakens, §10 ask #3.

### (a) Karma ID-AOV truth — §5 flagship / §12 INFERENCE row / M1 probe target

| Finding | Tier | Evidence |
|---|---|---|
| The HDK never names an object-ID render var. `HUSD_RenderTokens` (the only render-token namespace in the HDK) contains exactly: `productName, productType, dataType, aspectRatioConformPolicy, dataWindowNDC, disableMotionBlur, pixelAspectRatio, resolution, raster, color, cameraDepth` — no id, no prim/instance/element id, no crypto token. | **NULL (closes the "is it in the HDK?" question)** | `hdk/namespace_h_u_s_d___render_tokens.html` |
| BRAY (Karma's engine library) **is** in the HDK, but as bare class reference only — no guide page, no named AOVs. `BRAY::AOVBufferPtr` is fully generic (`getName/getVariable/getFormat/getPacking/...` + `getMetadata()`). The Rendering TOC has procedural docs for **Mantra only** — Karma has no authoring guide in the HDK at all. | VERIFIED-WEB | `hdk/namespace_b_r_a_y.html` · `hdk/class_b_r_a_y_1_1_a_o_v_buffer_ptr.html` · `hdk/_h_d_k__render_output.html` |
| The cryptomatte **mechanism** is HDK-documented: "a single Cryptomatte layer may require four image planes... it's more convenient to declare just one `RenderVar`" — carried by returning a `UT_HUSDExtraAOVResource` from `HdRenderBuffer::GetResource`; members `myNames`, `myFormats`, `myMetadata` ("Dictionary of extra metadata for the AOV") — **the manifest travels as per-AOV string→string metadata written into the image.** Exact manifest key spellings NOT given. | VERIFIED-WEB (mechanism) / NULL (key spellings) | `hdk/_h_d_k__u_s_d_hydra.html` (Husk: Extra Channels) · `hdk/struct_u_t___h_u_s_d_extra_a_o_v_resource.html` |
| Supplemental (user docs, labeled as such): crypto declared on the Karma ROP AOV dropdown as **"Cryptomatte Object Name"** / **"Cryptomatte Material Name"** (custom string primvars via "Source Name"), and *"Cryptomatte is supported by Karma CPU and Karma XPU"* — the CPU/XPU parity the blueprint needs, stated verbatim for crypto (not yet for an integer ID var). | VERIFIED-WEB (user docs) | `houdini/solaris/cryptomatte.html` · `houdini/render/cryptomatte.html` |
| Hydra's standard AOV identifiers (`primId`/`instanceId`/`elementId`, HdAovTokens) are the likeliest integer-ID candidates given the delegate contract the HDK documents (`orderedVars` with `sourceType/sourceName/dataType/HdFormat`) — but **no fetched page confirms Karma honors them.** | INFERENCE — M1 probe #1 decides | derived from `hdk/_h_d_k__u_s_d_hydra.html` (Delegate Render Products) |

**Net for §5/§12:** the integer object-ID render-var name remains INFERENCE, exactly as the blueprint's own rule requires — but the probe is aimed, and crypto-as-fallback is upgraded: mechanism + CPU/XPU parity + declaration surface all documented.

### (b) Husk/ROP hook surface — §6 EXPLORE / §10 ask #2 / §3 `.done` sentinel — **DESIGN-AFFECTING**

| Finding | Tier | Evidence |
|---|---|---|
| The HDK documents a real husk↔delegate contract: `batchCommandLine` in the `HdRenderSettingsMap`; unhandled render products handed to the delegate; SIGUSR1-triggered snapshots as a `"husk:snapshot"` render setting; `huskErrorStatus` critical-error stat; and a **Python verbose-callback surface** — `husk.verbose_callback` / `husk.verbose_interval` in `UsdRenderers.json`, invoked with mode ∈ {"start","active","end","snapshot","info"} plus "husk render stats in JSON form." | **VERIFIED-WEB** | `hdk/_h_d_k__u_s_d_hydra.html` (Integration with husk · Critical Delegate Errors · Render Delegate Configuration) |
| Caution: the HDK section "Render delegate event scripts" is **viewport delegate switching** (`activate(pane)`/`deactivate(pane)`, receives `hou.SceneViewer`) — GUI-only, never the farm path. | VERIFIED-WEB (scope-correcting) | same page |
| ROP pre/post-render script params are NOT HDK-documented (SOHO has no lifecycle-hook content); they live in node user docs. | NULL (HDK) | `hdk/_h_d_k__s_o_h_o.html` |
| **THE TIMING TRAP (user doc, verbatim):** usdrender ROP Post-Frame — *"This command is run after each USD is generated. Although the USD may have been generated, this does not necessarily mean that `husk` has finished rendering the image when this command is run."* Post-Render carries the same caveat. **The §3 `.done` sentinel as drafted would fire before pixels exist on the husk path.** | VERIFIED-WEB — **design-affecting** | `houdini/nodes/out/usdrender.html` (Scripts tab) |
| The correct sentinel surface is husk's own flags: `--postframe-script` (*"after each frame is rendered"*), `--postrender-script`, `--prerender-script`, `--preframe-script` (documented `SkipFrame` exception), `--presnapshot-script`/`--postsnapshot-script`, `--verbose-callback` + `--verbose-callback-interval`, `--snapshot ‹sec›`/`--snapshot-path`/`--snapshot-suffix`/`--snapshot-save-mode`. | VERIFIED-WEB (user docs) | `houdini/ref/utils/husk.html` |
| Windows note: SIGUSR1 does not exist on Windows — interval `--snapshot ‹sec›` is the portable form; signal-triggered checkpointing needs a live probe on this platform. | INFERENCE (platform gap) — M1 probe #4 | HDK huskCheckpoint + platform knowledge |

**Net for §10 ask #2:** the ask gains evidence teeth — husk scripts, the verbose callback, and the checkpoint contract all exist and are documented today; the ask is precisely to treat them as versioned, stable-across-majors surface.

### (c) EXR/IMG layer facts for T0/T1 — beyond what W.1b banked

| Finding | Tier | Evidence |
|---|---|---|
| **husk writes multi-part OpenEXR** (at minimum, supports it as the metadata-rich path): typed metadata as `<type> OpenEXR:<key>` (bool/int/float/string/matrices/timecode/keycode; example `mat4f OpenEXR:worldToCamera`). **T0 header checks must be multi-part-aware.** | VERIFIED-WEB | `hdk/_h_d_k__u_s_d_hydra.html` (Husk: Image Metadata) |
| **Manifest-into-EXR is free:** *"husk will process all the attributes on the render product. It looks for settings that begin with `driver:parameters:` and will pass that data down to the image as a piece of metadata."* The manifest writer can stamp the expectation-contract fingerprint **inside the EXR itself** — the receipt travels with the artifact. Design gift for T0; not in the blueprint today. | VERIFIED-WEB | same section |
| Per-AOV pixel format is **data-driven**: delegate products arrive as `orderedVars` each carrying `sourceType, sourceName, dataType, HdFormat`. **T1 ingest reads channel types from the header, never assumes half-float.** Karma's *defaults* per AOV are undocumented in everything fetched. | VERIFIED-WEB (contract) / INFERENCE (defaults) — M1 probe #2 | same page |
| Bottom-left origin corroborated at the IMG layer — independent confirmation of the W.1b banking. | VERIFIED-WEB | `hdk/_h_d_k__image.html` |
| EXR channel-naming convention (`AOVname.r` vs nested layers) — nowhere in the fetched HDK pages. | NULL — T0 probe reads a live header | index + `_h_d_k__image.html` + Hydra page all silent |
| Deep support: the HDK's only deep documentation is Mantra-era `.dsm` — zero Karma/husk/deep-EXR mention. Do not design T0 against deep until probed. | NULL (HDK) | `hdk/_h_d_k__image_d_s_m.html` |
| The HDK has **no Copernicus/COP surface at all** — no COP, IMX, or Copernicus entry in the full TOC or namespaces; the memo-pass's PXL_Common.h/IMX_Buffer.h header grounding remains the only HDK-adjacent anchor for buffer↔numpy. | NULL — **strengthens §10 ask #3** (a blessed readback path genuinely doesn't exist in public docs today) | `hdk/index.html` · `hdk/pages.html` · `hdk/namespaces.html` |

### (d) Changelog re-check — one fetch, verbatim

**No H22 entry has appeared.** Newest heading remains "Major Changes in Houdini 21.0"; eighteen entries, zero mention of "22" anywhere. Unchanged from the intake memo's §(e) finding this afternoon. — VERIFIED-WEB · `hdk/_h_d_k__changes.html`

### Probe targets handed to M1

1. **ID-var enumeration (the flagship question):** enumerate the Karma ROP / `rendervar` LOP AOV menus on live 22.0.368; probe sourceName candidates in order — HdAovTokens `primId`/`instanceId`/`elementId`, bare `id`, then the documented crypto pair. CPU **and** XPU.
2. **Header ground truth:** render one frame through SYNAPSE's actual path; dump the EXR header — multi-part vs single, channel naming, per-AOV pixel types, and (crypto enabled) the actual manifest metadata keys.
3. **Sentinel timing:** measure usdrender ROP Post-Render fire-time vs product mtime (docs predict early fire) → verify `husk --postframe-script` reachability from SYNAPSE's render invocation. **This decides the §3 `.done` design.**
4. **Windows checkpoint reality:** SIGUSR1 absent on Windows — probe `--snapshot ‹sec›` interval behavior.
5. **`driver:parameters:` round-trip:** author a custom attr on the render product; confirm it lands as EXR metadata — the manifest-in-EXR receipt upgrade.
6. **verbose-callback smoke:** wire a minimal `--verbose-callback` script; confirm "end" mode fires with JSON stats — candidate second sentinel channel, filesystem-independent.

### Blueprint mapping

- **§3 host hooks** — the `.done`-via-ROP-postrender line carries the (b) timing correction; the sentinel moves to husk flags or verbose-callback (M1 probes #3/#6 decide).
- **§5/§12** — ID-AOV stays INFERENCE (HDK NULL confirmed), probe aimed; crypto fallback upgraded (mechanism + CPU/XPU parity documented).
- **§10 asks** — #1 gains its sharpest form ("`HUSD_RenderTokens` has `color` and `cameraDepth` but no `id` — that's the missing token"); #2 gains today's documented-surface inventory; #3 gains the strongest evidence of the three (the HDK contains no Copernicus surface whatsoever).
- **T0/T1 design facts** — multi-part-aware header checks; format-from-header ingest; bottom-left corroborated; deep out-of-scope until probed; manifest-in-EXR as a free upgrade.
