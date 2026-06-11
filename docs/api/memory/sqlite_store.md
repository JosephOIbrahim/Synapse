# synapse.memory.sqlite_store

SQLite-backed memory store -- drop-in replacement for MemoryStore.

NOT wired to the live selector: `SynapseMemory._make_store` recognizes only
`jsonl | moneta | shadow` and warns on anything else. The `sqlite` value is
honored only by the `create_memory_store` factory below, which has no
production callers (tests/dev only).

::: synapse.memory.sqlite_store.SQLiteMemoryStore

::: synapse.memory.sqlite_store.create_memory_store
