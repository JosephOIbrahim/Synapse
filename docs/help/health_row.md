# The memory health row

`synapse_health` reports the write plane at `write_plane.store` (fed by
`server/write_plane.py::store_health()`). When a memory store is live, that row
names the five W1 operator fields: **requested backend · active backend ·
embedder id · embedding dim · row count** (under `store.backend_health`), each
carrying a ratified verdict of **SUCCESS**, **UNAVAILABLE**, or **BLOCKED**.

The row keeps its own `ok / degraded / unknown` word too — the ratified verdict
rides alongside it, so a Moneta request served by a jsonl fallback reads
**UNAVAILABLE** and is never shown as ok.
