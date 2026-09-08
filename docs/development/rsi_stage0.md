# RSI Stage 0: checked experience on request

Stage 0 is a development scaffold for one fixed `copernicus_lookdev` workflow
on Houdini 22.0.400, built on the v5.67.1 runtime. It preserves a checked
procedure and returns it when explicitly requested in a matching environment.
This is the first piece of the artist-controlled assistance described in
[INTENT.md](../../INTENT.md).

The developer supplies the first working procedure. There is no model training,
generated repair, automatic execution, panel registration, or Computer Use in
this stage. Its qualification level is **development scaffold verified**;
artist-panel integration remains a separate milestone.

## What the artist will control

Assistance defaults to disabled. A future host integration must enable it only
within the artist's chosen scope and request recall only when they ask for help.
The result explains what was checked and what remains unknown. The artist can
inspect it, dismiss it, or choose to use the procedure through the existing
ordinary build route with a fresh destination and authorization.

A recalled procedure contains settings and a reference to the existing builder.
Historical node paths stay in the evidence; they are never replay instructions.
The adapter has no scene execution method. A stored success grants no authority
over the current scene, and a later improvement cannot silently replace a
network the artist already accepted.

## Record, restart, recall

Use an **isolated development project directory**, with no other process owning
its memory store. The standalone command owns one existing `MonetaBackedStore`
facade for its lifetime. It does not change the selected backend or migrate
existing project memory.

First retain a real report from
[`probe_rsi_stage0.py`](../../scripts/live_probes/probe_rsi_stage0.py). Run that
probe in a fresh headless Houdini 22.0.400 subprocess with isolated preferences,
temporary files, SYNAPSE logs/ledger, and an enforced timeout. The qualification
run used a 120-second subprocess timeout. The probe rejects GUI use, a nonempty
Solaris network, an unsupported build, or execution outside the main thread.
It uses the existing lookdev handler and writes a new report with `--output`.
Keep the launch command, process log, and return code beside that report.

The report is a trusted **developer import**, not an arbitrary model response.
The normalized stored experience's digests detect later content changes. They
cannot authenticate a fabricated report, or one altered before import, as a real
Houdini execution. Never expose this import as a generic agent tool.

From the repository root, substitute your existing development directory and
retained report path in these PowerShell commands:

```powershell
$env:SYNAPSE_MEMORY_BACKEND = 'moneta'
python scripts/rsi_stage0.py --enable --project-dir 'C:/dev/rsi-demo' record --native-report 'C:/dev/rsi-evidence/native-report.json' --summary 'Fixed Solaris and Copernicus lookdev setup'
python scripts/rsi_stage0.py --enable --project-dir 'C:/dev/rsi-demo' recall --environment 'C:/dev/rsi-evidence/native-report.json'
```

Each command starts a separate process. Expect `STORED`, then `HIT`; repeating
the identical import returns `DUPLICATE`. Omitting `--enable` opens neither the
input files nor the store. The command returns exit code 2 for unavailable or
ineligible operations, including a missing Moneta installation.

Using the same report for recall proves a matching-environment roundtrip. For
a different target session, supply newly observed environment facts instead.
`--environment` accepts those facts directly or a native report containing them;
the CLI does not inspect a running Houdini session. Compatibility requires exact
Houdini build, SYNAPSE version, producer/checker identity, relevant builder source
hashes, and fixed dependency hash. Documentation-only changes do not invalidate
the builder identity.

## Storage and result contract

The adapter in [`experience.py`](../../python/synapse/memory/experience.py)
accepts an already owned store or a host owner exposing `.store`. Host callers
must inject that existing owner on the established host path. Panels and workers
must not construct another owner for the same storage URI.

| Result | Meaning |
| --- | --- |
| `STORED` | The primary store acknowledged a synchronous snapshot of this record. |
| `DUPLICATE` | The identical source outcome was already present and checkpointed again. |
| `HIT` | Complete lookup found a compatible checked procedure. |
| `NO_MATCH` | Complete lookup found no compatible checked procedure. |
| `INELIGIBLE` | Invalid evidence or conflicting content for an existing source identity. |
| `UNAVAILABLE` | Disabled, unsupported, incomplete, or failed operation; the reason is included. |

Records are capped at 16 KiB. Lookup uses exact namespace and compatibility
checks, with a maximum of 20 namespace candidates. It enumerates the existing
store; this cap is not a large-store latency guarantee. Overflow or malformed
stored data returns `UNAVAILABLE`, never a false complete miss. Generic AI memory
cannot qualify as checked experience. Multiple matches choose the newest
canonical UTC timestamp, then stable record identity.

Recording may use the store's existing local embedder. Recall performs no
embedding, semantic search, model call, or scene operation. The strict standalone
factory refuses incompatible vector dimensions, unknown snapshot formats,
malformed snapshots, pending WAL data, and quarantined snapshots before opening
the owner. It does not reconcile or repair them. A compatible owner's normal
close still checkpoints storage; the complete CLI lifecycle is not a promise
of zero filesystem writes.

A failed snapshot may leave an unacknowledged row in memory. Retry the same
source ID and identical content; do not repeat the Houdini build to repair
memory. A partial backend deposit makes checked operations unavailable until
the owner is reopened and its state can be checked. Existing JSONL/USD mirrors
remain secondary; the primary snapshot acknowledgment defines `STORED`.

## Evidence and next boundary

The native rehearsal checked scene configuration and USD associations, including
material binding, UVs, texture sources, camera, and render settings. **Texture
pixels were not measured, and rendered appearance was not checked.** A matched
procedure retains those limits in its explanation.

Qualification used a real Houdini 22.0.400 producer, followed by record and exact
recall in separate Python 3.14 development processes, including an abrupt exit
without cleanup. The memory consumer has not been qualified inside Houdini's
Python 3.13 host or the deployed artist panel. The Python 3.14 checks emit the
existing vendored SDK ABI warning and use installed development dependencies.

Focused regression command:

```powershell
python -m pytest tests/test_rsi_stage0.py tests/test_moneta_store.py tests/test_moneta_crucible.py tests/test_moneta_substrate_truth.py tests/test_w3_kind_routing.py tests/test_memory_handle_law.py tests/test_solaris_lookdev.py -q -o addopts=
```

The next boundary is a small, separately qualified host integration: observe
the current environment on the Houdini main thread, inject the existing owner,
and display one suggestion on explicit request. Automatic improvement of
recipes can build on these retained outcomes later, with separate tests and
promotion decisions before any artist sees a changed suggestion.
