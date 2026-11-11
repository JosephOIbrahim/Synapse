# NR-QC-TIMING

Times the three legs of the render-QC scan on real frames, on the CPU.

The rule is frozen (revision 2). The harness only measures and applies it.

---

## What it measures

**R** reads a frame. **S** is the firefly scan. **W** writes the mask PNG.

**T** is R + S + W. **Floor** is R + W + S_rest, the best a GPU could reach.

The scan is split by call site, with timers around `cv2` calls. No product file is edited.

- **S_dense**: the calls at lines 292, 313, 314, 352, 542 and 549.
- **S_rest**: everything else in the scan, including the per-blob dilate at 373.
- **W**: the `cv2.imwrite` call at 458.

Five branches come out of that. `decide.py` holds them.

---

## The pieces

| File | Job |
|---|---|
| `decide.py` | The branches, the voting units, the verdict. Stdlib only. |
| `stage.py` | Copies the named frames, checks hashes and headers. |
| `run_timing.py` | The dry pass, then the timed passes, in one process. |
| `make_receipt.py` | Builds `timing_receipt.json` from a run. |
| `test_qc_timing_harness.py` | Tests for all of the above. |

The closure predicate lives in `harness/next-release/proposals/predicates/test_nr_qc_timing.py`.

It stays red until the receipt is committed.

---

## How to run it

Use the R4 venv with `-B`. Set `PYTHONPATH` to the release tree and nothing else.

**1. Stage.**

`<R4_PYTHON> -B harness/vision/qc_timing/stage.py --rule <RULE_R2> --stage-root <STAGE_ROOT> --manifest <STAGE_MANIFEST> --summary <STAGE_SUMMARY>`

It refuses a rule file that is not revision 2. It skips any source with a placeholder bit and never opens it. Exit 0 means 124 distinct files, all verified.

**2. Time.**

`<R4_PYTHON> -B harness/vision/qc_timing/run_timing.py --manifest <STAGE_MANIFEST> --out <RUN_DIR>`

Close Houdini, husk, hython and pytest first. The run checks the machine before and after every pass and voids a pass that fails.

Exit codes:

- `0` done
- `2` the machine never went quiet
- `3` the dry pass raised
- `4` a startup assert failed, before any pass

`--resume` continues from `raw.jsonl`.

**3. Receipt.**

`<R4_PYTHON> -B harness/vision/qc_timing/make_receipt.py --run <RUN_DIR> --staging-summary <STAGE_SUMMARY> --harness-commit <HARNESS_COMMIT>`

Pass `--host-marker <text>` for anything that must not appear in the receipt. A leak stops the write with exit 2.

---

## Rehearse on synthetic frames

`run_timing.py --smoke --smoke-frames <a.exr> <b.exr> <c.exr> --out <RUN_DIR>`

The same code path, with the machine checks report-only. The receipt says `mode: "smoke"`, and the predicate refuses it.

---

## What the receipt says

Per frame: the medians and spread of R, S, S_dense, S_rest and W, and every raw pass.

Per voting unit: the values, the branch, and the verdict (`branch k`, `split` or `no verdict`).

It also carries the statements the rule asks for:

- char-3 against char-4 on frames 0001-0009
- char-10 against char-3
- T against header render time, context only
- R is a part-0 read on the multi-part entries
- char-12 and char-13 never vote

The numbers live in the receipt, not here.

---

## Known limits

**Clean content only.** A NO covers clean frames at these sizes.

**A YES is a trial, not proof.** Transfer and GPU start-up are not measured.

**The wrappers add overhead.** It is recorded per pass and lands in S_rest, which leans against a GPU push.

**An exception after the dry pass** is recorded on its pass and the run continues. That frame then does not reach a result.
