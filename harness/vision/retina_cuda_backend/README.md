# RETINA CUDA backend

Graph node **NR-VG-RETINA-CUDA-BACKEND**. Its spec is in `harness/next-release/proposals/vision-grow.amendment.PROPOSED.json`.

`retina/backend_cuda.py` runs one RETINA chain on an NVIDIA GPU through OpenCV's CUDA modules. It is the chain the owner ruled on 2026-11-07 (ruling R2, recorded in ADR-0002):

**absdiff → strict threshold → morphological open → morphological close**

That chain is the body of `retina.t1.change_mask`. The backend returns the same uint8 {0,1} mask. `retina.t1.change_mask` is unchanged and stays the CPU reference.

---

## Status

- **Off by default. Nothing calls it.** No production code imports the module. T1 itself has no production caller, and no worker launches T1 yet (ADR-0002, Context section 2). Until a worker exists, the only consumer is an offline parity harness.

- **Not ratified.** ADR-0002 is PROPOSED. The node's closure predicate stays red until the owner ratifies it. Merging is the owner's call.

- **The GPU tests run only on a CUDA device.** In CI and on CPU-only interpreters they skip. They run in the CUDA worker venv under the ruled build root `E:/OpenCV5.1_Prep` (ruling R3).

---

## Placement rules

These are hard rules.

- **Worker only.** The module runs in the out-of-process RETINA worker: CPython 3.12.10 with a CUDA build of cv2 (ruling R4). It never runs inside Houdini.

- **Unreachable from the in-host modules.** `retina/__init__.py`, `retina/t0.py`, `retina/events.py` and `retina/exr_header.py` load inside Houdini. None of them may import this module, statically or dynamically.

- **Never on the host payload.** The module must not join `RUNTIME_FILES` in `installer/build_payload.py`.

- **No `hou`.** The module imports no `hou`, and cv2 only inside functions. Importing the module needs neither cv2 nor numpy.

---

## The API

| Name | What it does |
|---|---|
| `OPERATIONS` | `("absdiff", "threshold", "morphology_open", "morphology_close")` |
| `cuda_status()` | Returns `(bool, reason)` and never raises. True only when cv2 imports, `cv2.cuda` exists and the device count is above 0 |
| `change_mask_cuda(...)` | Computes the mask on the device. Raises `CudaUnavailable(reason)` when CUDA cannot run the chain. Never falls back to the CPU |
| `change_mask_check(...)` | Returns `(mask, check)`. Unavailable gives `(None, check)` with `pass=None` and the reason: inconclusive, never a pass |
| `last_dispatch()` | Lists the operations the most recent call actually ran through `cv2.cuda` |
| `witness()` | Reports the cv2 in use, the device, the CUDA build lines and the loaded native DLLs |

`CudaUnavailable` is a `T1Unavailable`, which is T1's existing "could not run" signal.

Three things make the chain unavailable:

1. `cuda_status()` is False.
2. The cv2 build lacks a `cv2.cuda` function the chain calls.
3. A `cv2.cuda` call raises `cv2.error` part-way. The reason names the step.

---

## How parity is built in

1. **Luma on the host.** The backend calls `retina.t1._luma`, the same code the CPU path runs.

2. **A strict threshold at float32.** NumPy 2 compares a Python float threshold at float32. The device receives exactly that float32 value, so its strict `>` gives the same answer.

3. **A neutral border at every step.** The CPU morphology uses a constant border that holds each step's neutral value. On the device, each step pads by the radius with that value (1 for erode, 0 for dilate), filters, and crops back. The CUDA filters' own edge rule never reaches a pixel that is kept.

---

## What it does not do

- **SSIM stays on the CPU.** The CUDA filter has no float64 path (ADR-0002, Refused Site 3).
- **The scoped-delta check stays on the CPU.** That check confirms the change stayed inside the claimed target and the outside held still (ADR-0002, Refused Site 4).
- **No mode switch.** The off / cpu / gpu_required policy in the ADR's Decision needs a caller. None exists yet.
- **No performance claim.** Speed is UNKNOWN (ADR-0002, Consequence 8).

---

## Tests

All tests are in `tests/test_retina_backend_cuda.py`.

- **`test_unavailable_*`** tests are hermetic and run everywhere: CI with no cv2, a CPU-only dev interpreter, and the worker venv. They prove that an unavailable GPU operation becomes inconclusive with a reason.

- **The emulated-device tests** put real CPU cv2 behind a stand-in `cv2.cuda` whose filters use a deliberately wrong edge rule. They prove the padding, crop and step order. **They are not GPU evidence.**

- **`test_gpu_*`** tests compare against `retina.t1.change_mask` byte for byte. They skip unless a CUDA device is usable.

---

## The receipt

`make_receipt.py` writes `backend_receipt.json` into this folder. It uses the standard library only.

The receipt records:

- `operations`, read from the module source
- `unavailable_is_inconclusive_tests`, the `test_unavailable_*` node ids
- `qualification_receipt_sha256`, the sha256 of `harness/next-release/gpu_qualification.json`

The script refuses to run until that qualification file exists. `--check` compares the receipt with the tree instead of writing it.

The receipt is not committed with the code. The orchestrator runs the script after the qualification receipt is committed.

---

## Rollback

Revert the commit. Nothing imports the module, so nothing else changes.
