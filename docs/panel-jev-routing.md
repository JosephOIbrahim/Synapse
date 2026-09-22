# Panel layout and JEV routing measurements

The native panel aligns the conversation invitation, composer, and actions on
one grid. Instructions and actions below the prompt share its left and right
edges; narrow layouts wrap into separate rows without overlapping. The model
picker groups Anthropic, Google, NVIDIA, Ollama and Custom in one searchable,
scrollable list. Rows separate readable names from exact model IDs and scale
with the host font. The saved next-task choice remains visible while filtering.
STOP sits directly below SEND at the right of the composer, shares its styling,
and keeps a compact 20 px height at normal scale with corresponding host scaling.
Stopping is cooperative: the panel stays busy until its worker ends. A stop
does not promise to interrupt a Houdini cook or undo scene changes.

The standalone TOKEN navigation tab has been removed. Provider-reported input
and output usage still feeds the per-task accounting and receipts. Removing the
tab does not disable that recording or substitute estimates for missing counts.

## Keep the chosen generation model

JEV is a separate assistance service. It is not an entry in the model chooser
and does not replace the selected provider or model. Routing measurement is
shadow only: those judgments never change the generator's prompt, history,
tools, or scene operations. Optional selected-network action ranking is a
separate feature: it orders actions when requested, and choosing an action
prepares an editable draft for the selected generator.

In **Connect models**, the **JEV assistance** group offers **Off**
(the default), **Measure routing**, and a separate **Rank selected-network
actions** preference. See [Selected network](selection-inspector-jev.md) for the
ranking workflow. Saving either preference does not grant
network permission. **JEV permissions…** opens the existing project rules for
the separate `typesafe/jev-latest` connection. The service also needs a
configured `TYPESAFE_API_KEY`. An explicit off value in `SYNAPSE_JEV` remains
a kill switch. Local-only project rules, revocation, and task cancellation
take precedence over the saved preference.

The fixed service destination is `https://api.typesafe.ai/v1/systemone`.
No SDK endpoint override, redirect, retry, or alternate-model fallback is used.
Transport uses the Python standard library; no TypeSafe SDK install is needed.

## What is shared

An approved routing request contains only the latest plain-text artist request
(at most 4,096 characters) and bounded routing context. Conversation history,
attachments, image data, and live scene reads are excluded. Oversized,
multimodal, and recognizable code or credential-bearing requests are skipped.
Text filtering cannot recognize every secret; the separate sharing permission
therefore explicitly covers the latest artist request.

The accepted task's project scope is carried into the background job. Permission
and cancellation are checked at the transport boundary and again before using
the answer. A grant for a generation model cannot authorize TypeSafe.

## Latency and evidence

Each accepted worker starts at most one shadow observation. The process permits
one transport at a time. A timed-out request keeps that capacity until its
underlying transport ends, including across module reloads. Shadow work is
never joined by Send, the first generated token, Stop, or terminal completion.
Missing credentials, denial, malformed answers, contention, and timeouts leave
the selected model's behavior intact.

Typed judgments classify work shape and context family. Their local JSONL
receipts include the task, generator, outcome, request hash, and elapsed time;
they do not store artist request text. The default directory is
`~/.synapse/jev/`, overridable with `SYNAPSE_JEV_LEDGER_DIR`. Worker telemetry
also records `worker_first_token_ms`, `worker_ms`, and per-tool durations.
The first-token measurement starts in the worker loop, not at the UI click.

This scaffold establishes measurement and permission boundaries. It does not
establish routing accuracy or an end-to-end speedup. Activating routing requires
a separately evaluated, labeled workload and evidence that useful work saved
exceeds the additional classification cost.

## Solaris connection reports

Assembly checks the actual source, target input, and source output immediately
after each new wire and again after wiring and layout finish. Dry-run records
remain plans rather than verified connections; existing nonzero output links
are preserved.

Textured materials report only verified authored values and shader connections
in `connected_maps`. Missing readers, unavailable parameters, incomplete normal
chains, or unsupported maps appear in `unapplied_maps`, with
`texture_status: partial`. Displacement remains unapplied by this tool.
`texture_files_checked: false` distinguishes graph authoring from asset loading
or rendered appearance. Scalar image readers use the measured H22.0.400
`default` signature token (the menu label is Float).

These changes do not deploy a panel, alter Houdini package paths, or update the
older authored LOP knowledge stamp. The review evidence separately identifies
the headless runtime and the source files tested.
