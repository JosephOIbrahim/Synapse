# BP1 G4 FALSE FAIL — correction of record (2026-08-31, GUI main-thread autopsy)

**Finding:** The GUI-half G4 RECALL verdict `fail` / `bucket=recall` in
`harness/battleplan/runs/2026-08-31/silent_recall_gui.json` is a **probe-side
false negative**, not a product recall failure. The deposit→recall round trip
is healthy in the GUI on the main thread.

## Evidence (rawdump autopsy, probe_recall_rawdump.py, build 22.0.400 ui=True)

- Deposit envelope: SUCCESS, `payload.deposited.claim_id = BP1-RAWDUMP-known-323a917e`.
- Raw fetch returned exactly one row — and that row IS the deposit:
  `payload.summary = "settlement HIT for BP1-RAWDUMP-known-323a917e"`,
  `created_at` = run time, fresh temp store.
- `query_and_filter` returned the same row: count=1, dropped all zero.
- USD referee: `cortex_root.usda` contains prim `mem_39630f6b4764` whose
  payload string embeds the claim_id. Deposit → USD authoring → raw fetch →
  filter → return: all green.
- Preserved store: `harness/battleplan/runs/2026-08-31/rawdump_store_swjv252n/`.

## The defect (probe, not product)

`probe_silent_recall.py` gate4 predicate (both `known_in_raw` and
`known_recalled`):

    (r.get("payload") or {}).get("claim_id") == known

Actual row contract: there is no `payload.claim_id`. The settlement fields are
JSON-serialized inside `payload.content` (a string). The predicate is
false-negative **forever** on this shape.

## Corrected predicate (for the post-merge probe fix)

    def _claim_id_of(row):
        p = row.get("payload") or {}
        cid = p.get("claim_id")           # forward-compat if shape flattens
        if cid:
            return cid
        try:
            return json.loads(p.get("content") or "{}").get("claim_id")
        except Exception:
            return None

## Direction of the error — why this is not a merge blocker

The defect fails **safe**: a pessimistic instrument that misses true passes,
not a green light that cannot report failure. The inverse class is the one
this wave exists to kill; this is its benign mirror.

## What stands, what changes

- STANDS: hython half `bucket=env` (G1 fired first; G4 predicate never reached).
  TRIAGE receipts and LAUNCH_PATH_FIX.md unaffected.
- STANDS: `silent_recall_gui.json` as an immutable receipt of what the probe
  measured. It is SUPERSEDED in interpretation by this note + preserved store.
- CHANGES: GUI-half Gate 0 reading — env/plugin/layer/recall all healthy on
  the main thread. Off-main access is BLOCKED-with-reason by host law (correct).
- OPEN: cross-session recall (close → reopen → remember) — the demo-round-trip
  contract (red, GUI, pending ratification) is the instrument for it.
- DISPOSITION: probe predicate fix rides post-merge (Joe's word on placement).
  Not touching the bp1/triage leg or the bus while CRUX reviews.
