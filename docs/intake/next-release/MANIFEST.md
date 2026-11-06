# Next-release intake — source manifest

One external artifact, adjudicated under the repo's intake protocol. The file is
kept verbatim; nothing in it has been edited.

| Field | Value |
|---|---|
| Source | `SYNAPSE_Next_Release_Engineering_Blueprint.md` |
| Copy | `docs/intake/src/synapse_next_release_blueprint.md` |
| Bytes | 59,424 |
| Lines | 418 |
| SHA-256 | `167ca678f620e6a078cf23958851dd5c708edd0c0f02bc89d6f0fcb5628a448c` |
| Stated revision | 1.1 — five-round reviewed draft |
| Stated baseline | `eefa8a11ada9381f8015fd1ceaf85bb0bc85d31e` |
| Received | 2026-11-06 |

## Anchor verification (run against this checkout at `eefa8a11`)

Every repository reference the blueprint makes was checked. A "missing" row is a
correction to the document, not a defect in the repo.

| Anchor | Claim | Result |
|---|---|---|
| `eefa8a11` | baseline commit | present; it is `master` |
| CI run `42301796914` | six jobs passed | present; conclusion success |
| `retina/t0.py`, `retina/events.py`, `retina/ingest.py`, `retina/qc_profiles.toml` | RETINA surfaces | present |
| `python/synapse/server/parm_authored.py` | G25 authored writes | present |
| `python/synapse/autonomy/{driver,planner,evaluator}.py` | G101 surfaces | present |
| `python/synapse/server/render_notify.py` | farm report | present |
| `installer/build_payload.py`, `installer/toolchain.lock.json` | distribution | present |
| `python/synapse/loop/coordinator.py` | publication pattern | present |
| `docs/SYNAPSE_RETINA_BLUEPRINT.md` | boundary design | present |
| PR #112 / PR #116 | OpenCV plan / SL0 draft | both OPEN |
| `docs/tickets/ANTHROPIC_SDK_2X_MIGRATION.md` | SDK migration | **missing at this SHA** — the blueprint's S12 link does not resolve in this tree; treat that reference as stale |

## What this manifest does not claim

The blueprint's upstream claims (OpenCV 5.1 release contents, NVIDIA licence
terms) were checked separately and are recorded in
`docs/reviews/next-release-licensing-2026-11-06.md`. Nothing here proves GPU
execution, a native build, or installed behaviour.
