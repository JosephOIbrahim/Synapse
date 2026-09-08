# RSI Stage 0: checked experience on request

Stage 0 is a development scaffold for one fixed `copernicus_lookdev` workflow
on Houdini 22.0.400, built on the v5.67.1 runtime. It preserves a checked
procedure and returns it when explicitly requested in a matching environment.
This is the first piece of the artist-controlled assistance described in
[INTENT.md](../../INTENT.md).

The developer supplies the first working procedure. The scaffold now includes
an artist-requested panel entry that recalls it and prepares an editable prompt.
There is no model training, generated repair, automatic recording, automatic
execution, or Computer Use in this stage. Its qualification level is
**development scaffold and offscreen panel integration verified**. Deployment
and interaction in the live artist panel remain unverified.

## What the artist controls

The suggestion card starts hidden and performs no lookup at panel startup.
Open **Saved lookdev suggestion…** in the panel's overflow menu, or choose
`/lookdev-suggestion` from the command palette. Each request asks for one
compatible saved procedure; it needs no connected model.

The card shows the settings and verification limits. **Use in prompt** appends
validated starting settings to the existing composer text, then hides the card.
The artist can edit that text and send it through SYNAPSE's ordinary build route
when ready. Preparing the prompt does not submit it or change the scene.
**Ask again** requests another lookup; **Dismiss** ends this assistance.

The host must already have an initialized Moneta owner for the current project,
containing a developer-imported Stage 0 record. Missing memory, a busy store, an
unsupported backend, or a changed environment produces an explanation with no
usable draft. The panel does not install Moneta, create or switch memory owners,
or populate a suggestion library automatically.

A recalled procedure contains settings and a reference to the existing builder.
Historical node paths stay in the evidence; they are never replay instructions.
The adapter has no scene execution method. A stored success grants no authority
over the current scene, and a later improvement cannot silently replace a
network the artist already accepted.

## Private host integration

[`host/lookdev_suggestion.py`](../../python/synapse/host/lookdev_suggestion.py)
arms a scene observer on the Houdini main thread before queuing the request.
It uses the existing project owner, confirms its location against the current
scene, observes the installed environment, and performs the exact recall on
main. The owner and backend locks are acquired without waiting; contention
returns `UNAVAILABLE`. Workers carry an observation session, never a memory
handle. This adds no public MCP tool or argument.

[`panel/lookdev_suggestion.py`](../../python/synapse/panel/lookdev_suggestion.py)
rejects replies from an older request and validates the returned record again
before offering a draft. Loading or clearing a scene, including reloading the
same file, invalidates the request. Saving the scene, replacing its memory
owner/backend, dismissing the card, or closing the panel also prevents reuse
of an old result. Ordinary profile recomposition retains the existing card and
draft. A running lookup can finish after dismissal without reopening the card.

The five-second dispatch timeout bounds a worker's wait. It cannot interrupt
work already running on main. Environment hashing and exact store enumeration
still need measurement on large production projects; this scaffold makes no
frame-time or hard cancellation guarantee.

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
without cleanup. The private host consumer also recalled that retained native
record inside Houdini 22.0.400 / Python 3.13.10 and after a fresh native-process
restart. Native recall performed no embedding and did not alter scene nodes;
reloading the same HIP file invalidated its previous request token.

The native memory run supplied an existing Moneta source checkout through
`MONETA_SRC` in isolated subprocesses. It did not install or configure Moneta in
the artist's environment. Without that source, the isolated native environment
reported Moneta unavailable. The Python 3.14 tests use a separately installed
development copy and emit the existing vendored SDK ABI warning.

Real Qt 6.8.3 offscreen checks cover the card, queued replies, dismissal,
destruction while work is pending, prompt preservation, menu/slash routing,
and full panel composition/profile changes. Full composition uses a controlled
host result with unrelated background polling disabled; native memory and scene
callbacks were qualified separately. A 340-pixel composed panel has readable
text and unclipped action labels. These checks do not qualify the live GUI
event loop, physical artist interaction, or a subsequent model-directed build.

Focused regression command:

```powershell
python -m pytest tests/test_rsi_stage0_panel.py tests/test_rsi_stage0.py tests/test_panel_finesse.py tests/test_moneta_store.py tests/test_moneta_crucible.py tests/test_moneta_substrate_truth.py tests/test_w3_kind_routing.py tests/test_memory_handle_law.py tests/test_solaris_lookdev.py -q -o addopts=
```

The next boundary is deployment and artist acceptance of this single requested
suggestion. Automatic improvement of recipes can build on these retained
outcomes later, with separate tests and promotion decisions before any artist
sees a changed suggestion.
