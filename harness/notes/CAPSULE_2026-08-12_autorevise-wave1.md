# CAPSULE 2026-08-12 — autorevise wave 1 (session close at M2 gate)

## Position
- Branch `feat/autorevise-harness` @ `00c5afa` (M1: harness built, 19 files).
- Master ahead 2, unpushed (mermaid palette) — push word pending.
- **M2-CRUX running detached**: runner pid 55232 → claude.exe 45680, Opus 4.8,
  relay profile, read-only in main tree. Started 21:01, bus post confirms.
- Receipt pending at `harness/notes/receipts/M2-CRUX.json`. Survives this
  session ending. COMMIT THE RECEIPT when it lands (lost-receipt prune lesson).
- Logs: `harness/autorevise/bus/_runs/M2-CRUX.{out,exit}.log` + `.pid`.
- Bus live: `harness/autorevise/bus/wave1/bus.jsonl` (1 post).

## Standing orders (ratified this session, apply always)
1. Chunk at gates; capsule per mile. 2. One writer per seam (MEM behind
W1-recovery; HSTRIP serializes behind H4 on token files). 3. BLOCKs close
before merge words. 4. Opus 4.8 on legs, deterministic code for mechanical
work. 5. UNKNOWN is the brand — GUI-required numbers stay UNKNOWN until
Joe's Houdini session measures them.

## Flags carried
- orchestrate.ps1 backup step pushed the branch STUB to origin during dry-run
  (designed behavior, backup ≠ Gate C; local is ahead of it).
- Done-pinned deps satisfy the dependency gate (observed; documented in
  make_control.py). CRUX-style unreceipted `ready` deps block correctly.
- DC blocking-wait anti-pattern re-confirmed: poll, never loop inside a call.

## Next session — enumerated, in order (each numbered act = one word)
1. Read `M2-CRUX.json` → triage: BLOCKs are the next mile, close before words.
   Commit receipt + this capsule's sibling artifacts.
2. Apply BASE in CTO session (orchestrate.ps1: per-leg `base` at worktree cut;
   model arg already live at :228/:357). Verify with -DryRun on the control.
3. On the word: append `harness/autorevise/waves/wave1.rows.json` legs →
   `harness/legs.json`; flip MEM held→ready only if worded.
4. Launch `harness/orchestrate.ps1` — one window owns the board.
5. M4: monitor via bus (`python harness/autorevise/bus.py read wave1` /
   `claims wave1`), receipts per leg, spawn_compile per receipt (print → word
   → --append). W1-CRUX gates the merge words.

## Paths card
harness/autorevise/{SPEC.md, mission_schema.py, compile_wave.py,
spawn_compile.py, bus.py, make_control.py, missions/, prompts/, waves/}
Control smoke: `python make_control.py wave1` then orchestrate `-DryRun
-Quiet -ManifestPath waves/wave1.control.json` (detached, kill after 1 cycle).
