# TRIAGE FARM discovery and migration

8 September 2026. Static source review; no panel, HIP or render code was executed. This records the existing prototype and the proposed integration. It does not enable another render profile.

## Where it lives

The installed entry is [tops_farm.pypanel](C:/Users/User/OneDrive/Documents/houdini22.0/python_panels/tops_farm.pypanel:8), with interface name `tops_farm` and label **Triage Farm**. Its loader uses `TRIAGE_FARM_ROOT`, defaulting to `G:/KARMA_TRIAGE_FARM`, then imports `panel/tops_farm_panel.py`. No process, user or machine override was observed during this inspection.

The actual implementation is [G:/KARMA_TRIAGE_FARM](G:/KARMA_TRIAGE_FARM/README.md). Its saved graph is [out/triage_farm.hip](G:/KARMA_TRIAGE_FARM/out/triage_farm.hip). This separate project explains why the prototype was absent from the tracked SYNAPSE source reviewed on 7 September.

## What it does today

The prototype describes a single-workstation Karma XPU workflow: make cheap variations, measure image properties, show a contact sheet, then let the artist choose which looks deserve a better render. Its documented build is Houdini 22.0.368. The new SYNAPSE preview was qualified separately on 22.0.400.

Its builder creates:

`wedge_params → proxy_render → score → wait_all → rank_sheet`

The panel chooses an existing TOP network/node, changes the wedge count, starts or cancels a cook, shows work-item states and opens shared output paths. Defaults are 50 wedges, frame 1001, one GPU scheduler slot and a created CPU scheduler with 16 slots. The supplied `out` directory contains the probe, parameter map, findings and HIP; no rendered images, score log or contact sheet was present there. The July brief explicitly calls the graph a skeleton with shot-specific setup remaining. That is not evidence that an actual look-comparison render has passed.

Sources: [project brief](G:/KARMA_TRIAGE_FARM/h22/CLAUDE.md:7), [builder defaults](G:/KARMA_TRIAGE_FARM/h22/build_farm2.py:53), [panel actions](G:/KARMA_TRIAGE_FARM/panel/tops_farm_panel.py:324).

## Integration decision

Use one SYNAPSE render service and one artist workflow. Preserve the existing project as a reference while its useful look-comparison features move into that service.

| Existing part | Treatment |
| --- | --- |
| Cheap look variations and contact-sheet review | Add an optional **Compare looks** path inside Render. |
| Technical image measurements | Reuse selected algorithms after validation, as descriptive flags; keep creative selection with the artist. |
| TOP graph and parameter probes | Use as migration references, then verify the needed APIs on the current qualified build. |
| Direct cook/dirty/cancel controls | Route future artist actions through the durable prepared-request and execution service. |
| Shared CSV/output folder | Replace with per-request, per-variation artifacts and one deterministic aggregation step. |
| Vendored design system and separate launcher | Use SYNAPSE's current design system and a shared render view. Preserve the existing panel entry during migration. |

The old Python Panel entry can eventually open the shared view. First separate an embeddable render widget from the existing modeless dialog and test both hosts; merely returning the current dialog from a Python Panel callback would be an unverified integration.

Extract reusable image functions into an import-safe component. The three legacy command-line scripts call `main()` unconditionally, so importing them directly can parse arguments, build a graph or launch work. [Proxy entry](G:/KARMA_TRIAGE_FARM/farm/render_proxy.py:116), [scorer entry](G:/KARMA_TRIAGE_FARM/farm/score_frame.py:184), [builder entry](G:/KARMA_TRIAGE_FARM/h22/build_farm2.py:254).

## Gaps to close before enabling Compare looks

**Apply every variation to the rendered scene.** The current generated render payload reads `usdpath`; other wedge values travel as `--attrs` log text. The wrapper does not apply those values to USD. A new recipe must create and seal the scene changes for each variation, then prove that a controlled parameter change alters the intended scene property and image. Several distinct, already-authored USD inputs could be used by the old code, but arbitrary wedge attributes alone do not create different looks. [Render payload](G:/KARMA_TRIAGE_FARM/h22/build_farm2.py:125), [wrapper](G:/KARMA_TRIAGE_FARM/farm/render_proxy.py:59).

**Use the durable execution boundary.** The old panel cooks the artist's selected graph directly and derives completion from work-item states, including cached items. Its Cancel action uses whichever node is currently selected. The new request service should own the frozen scene, exact variation/frame identities, admission, process lifetime and cancellation. A non-blocking panel cook alone does not qualify that detached lifetime. [Cook/cancel](G:/KARMA_TRIAGE_FARM/panel/tops_farm_panel.py:324), [completion calculation](G:/KARMA_TRIAGE_FARM/panel/tops_farm_panel.py:407).

**Make outputs belong to one request.** The prototype uses common names such as `w000.1001.exr`, `scores.csv` and `contact_sheet.png`. A recook or another graph can reuse those names. Keep a sealed manifest of expected variant/frame outputs, write one score record per image, and aggregate exactly that manifest. The new service's existing decoder and current-byte checks remain the completion authority. [Shared output paths](G:/KARMA_TRIAGE_FARM/h22/build_farm2.py:142), [CSV and sheet](G:/KARMA_TRIAGE_FARM/farm/score_frame.py:115).

**Verify the sheet as an artifact.** The rank payload ignores the subprocess return code and registers the sheet path regardless. The sheet writer ignores the Boolean result of `cv2.imwrite`. Require successful execution, a fresh decodable sheet and exact manifest membership; a sheet from an earlier run cannot complete the current request. [Rank payload](G:/KARMA_TRIAGE_FARM/h22/build_farm2.py:167), [sheet write](G:/KARMA_TRIAGE_FARM/farm/score_frame.py:160).

Treat image review as a separate stage after verified rendering. If scoring or sheet creation fails, preserve the completed render and show **Review unavailable** with a retry action.

**Make the comparison match the artist's view.** The current EXR loader applies fixed tonal compression and a 1/2.2 power before computing scores and drawing thumbnails. It does not use the shot's OCIO/view configuration. Qualify a consistent display transform for the comparison grid and record it with the request. Validate technical flags against intentional dark, soft or stylized looks before using them to hide images. [Display conversion](G:/KARMA_TRIAGE_FARM/farm/score_frame.py:26).

**Qualify XPU and resource admission separately.** The old wrapper defaults to a 22.0.368 husk path and 12 CPU threads. The generated TOP scripts call blocking subprocesses, while the builder does not explicitly set the Python TOP execution mode or bind the score/rank nodes to its CPU scheduler. Recheck those settings and enforce a shared GPU/resource budget across requests. Neither the old one-slot graph nor the new per-job CPU limits establish a machine-wide queue. [Wrapper defaults](G:/KARMA_TRIAGE_FARM/farm/render_proxy.py:19), [scheduler construction](G:/KARMA_TRIAGE_FARM/h22/build_farm2.py:201).

## Artist flow and acceptance

Start with **Render** as the ordinary path. **Compare looks** opens only when the artist wants alternatives: choose the property to vary, a small explicit set of values, a preview frame and a budget. Prepare shows the exact number of images and the settings. Render produces a clear thumbnail grid. Optional technical flags explain measurable issues without presenting a quality score as an aesthetic verdict. Selecting thumbnails creates a new reviewed request for higher-quality output.

The first acceptance fixture should contain four distinguishable variants of one scene and one frame. Prove that each manifest entry drives a different authored scene value, all four images decode, the sheet contains exactly those four current images, selection preserves variant identity, and cancellation/restart cannot mix attempts. Keep render-farm setup separate from that creative flow.

No legacy panel or project files were changed or removed during discovery. The existing implementation remains independently available. Actual XPU execution, loading the legacy HIP, multi-machine HQueue operation and replacement of the installed panel are still unqualified.
