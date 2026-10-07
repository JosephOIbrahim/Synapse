# OpenCV in SYNAPSE: render QC first

**Status:** plan only. Building starts after the 2026-10-07 work in flight is finished: the demo merge set, improvement loops 1 to 3, and the code-block Copy button.

**Why this exists:** Joe asked the panel how to bring OpenCV into SYNAPSE so Claude Code could build it. The answer it gave (model `ollama/kimi-k3:cloud`) had the right shape but two wrong facts. This plan keeps the shape, corrects the facts and fixes the order.

---

## What is true today

| Fact | Evidence |
|---|---|
| **OpenCV 5 is released.** OpenCV 5.0.0 shipped on 2026-06-06; `opencv-python` 5.0.0.93 is on PyPI and supports Python 3.6 to 3.14. | [OpenCV 5.0.0 release](https://github.com/opencv/opencv/releases/tag/5.0.0), [PyPI](https://pypi.org/project/opencv-python/5.0.0.93/) |
| **A Windows `cp313` wheel for 5.0.0.93 is not yet confirmed.** Search results only showed Linux wheels. | Phase 0 checks it with `pip download --only-binary=:all:` |
| **Houdini 22.0.400 runs Python 3.13.10.** It already ships numpy 2.3.2, OpenImageIO 2.5.18 (reads EXR natively), imageio 2.6.1 and PIL 12.1.0. **It does not ship `cv2`.** | Isolated hython probe, 2026-10-07 |
| **Heavy work on Houdini's main thread freezes the GUI.** Live handlers run there through `run_on_main`. | The project's known freeze class |
| **SYNAPSE already checks frames.** `synapse_validate_frame` reports black frames and clipping. | Tool registry |
| **Ports in use:** 9999 (the live bridge, with failover) and 8008 (the API adapter). | `mcp_server.py:152`, `server/api_adapter.py:485` |

**What the panel answer got wrong:**
- It said OpenCV 5 is not shipped. It shipped in June.
- It targeted Houdini 21. The seat runs 22.0.400.
- It suggested the imageio OpenEXR plugin. Houdini already ships OpenImageIO, which reads EXR.

---

## Decisions

Jev (TypeSafe) made the calls from the facts above. Its ledger is in the run folder, not in the repo.

| Question | Answer | Confidence | Status |
|---|---|---|---|
| **First tool set** | Render QC on frames on disk | 0.99 | Decided |
| **Pin OpenCV 5.x** (4.x only if no Windows cp313 wheel exists) | Yes | 0.67 | Decided |
| **Where OpenCV runs** | A separate local process (0.58), over cv2 on a worker thread inside Houdini (0.41) | under 0.6 | **Joe's call, after Phase 0's numbers** |

---

## Scope of the first build

Two tools. Each takes a frame path and returns small JSON. Pixels never travel across the bridge.

**`synapse_cv_exposure(image_path)`**
Returns mean and median luminance, black and clipped percentages, a suggested exposure offset in stops, and the path of a written histogram image.

**`synapse_cv_fireflies(image_path, threshold_sigma=6.0)`**
Returns the firefly count, the worst pixel's position and the path of a written mask.

**Image reading lives in one place.** OpenImageIO reads EXR as linear float32 RGB, and channel order is fixed there. Conversion to OpenCV's types happens in that one module and is tested on its own.

**Not in this build:**
- gobo masks
- feature matching
- edge images
- anything live in the viewport

They come after render QC proves out.

---

## Phases

1. **Phase 0, spike, about 1 hour.**
   - Confirm the Windows cp313 wheel for `opencv-python` 5.0.0.93 and that it imports next to numpy 2.3.
   - Measure both options on a 4K EXR: a separate process (start-up time, round trip) and cv2 on a worker thread in hython (import time, peak memory, whether the GUI stays responsive).
   - Joe picks where OpenCV runs.
2. **Phase 1, the analysis module.**
   - Pure functions under `python/synapse/cv/`.
   - Tested on generated EXRs: a flat grey frame, a clipped frame, and a frame with planted fireflies at known positions.
   - No Houdini needed.
3. **Phase 2, the tools.**
   - Register the two tools in the MCP registry and the live handler table.
   - Generate the tool count in docs from the registry; never type it by hand.
   - A missing OpenCV install reports a clear error, never a fake success.
4. **Phase 3, the panel.**
   - A frame with clipping or fireflies reads as a **warn** row. The warn state is in the demo merge set.
   - The agent names the numbers.
5. **Phase 4, live check.**
   - Run both tools in hython 22.0.400 on a real Karma frame from the render workspace.
   - Isolate the run: no packages, scratch preferences, nothing loaded from the seat checkout.

---

## Rules for the build

- **Nothing writes into Houdini's own `site-packages`.**
- **No image analysis on Houdini's main thread.**
- **Every new test fails on the code before it.** No existing test is edited.
- **Merging is Joe's call.**
