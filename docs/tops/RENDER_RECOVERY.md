# Local render recovery contract

This repair applies to the unpublished TOPs/render branch based on `be7cb4fe`.
It changes recovery behavior without granting another preparation or submission.

## Cancellation delivery and acknowledgement

`cancellation_requested` is a permanent output-acceptance fence. The separate
`cancellation_delivery_pending` flag records whether the backend has acknowledged
delivery of the stop message. An I/O failure, host crash, or lost acknowledgement
leaves delivery pending. Refresh retries that same idempotent stop message;
explicit Cancel may also redeliver it. Neither operation retries a render.

The native backend acknowledges delivery only after its request marker is written.
That marker binds the existing request ID and reviewed plan digest. When an
operation is known, its marker also binds the existing native token. A crash after
writing either marker is safe to retry. Delivery alone remains `cancel_requested`;
`cancelled` requires confirmation that the active operation stopped.

There is one additional positive acknowledgement: the unique admitted prepare or
submit caller can durably report that it skipped its backend invocation because
Stop arrived first. No later status query infers this from missing process files.
If that caller dies before acknowledging its decision and execution cannot be
established, cancellation stays uncertain. Nothing is automatically relaunched.

## Rechecking accepted images

Refresh of a previously complete request hashes its original accepted outputs.
A stable hash or size mismatch, an empty/non-regular output, or a missing image
whose parent remains accessible becomes `failed` with `output_changed`. This is
terminal even if another file later appears at that path.

An unreadable or unstable byte read, or an unavailable output directory, becomes
`status_unavailable` with `output_unavailable` and `output_recheck_pending: true`.
Public outputs are empty and unverified. The original decoder receipt, hashes,
frame set, plan digest, backend identity and metadata remain in the private journal.
Refresh checks those original bytes again without invoking any backend method.
The same bytes can return to `complete`; no new render or replacement receipt is
accepted. Concurrent cancellation still fences the result.

The Render view accepts these transitions only for the same plan, output folder,
backend identity and native operation token at an appropriate journal revision.
While checking is unavailable, it hides Open outputs and does not claim a render
is still running. A view that observed the earlier completed receipt also requires
recovered hashes, frame evidence and output paths to match that receipt.

## Reviewed sample budget

USD localization clears authored value opinions for both Karma sample attributes
before setting the reviewed constant sample count. Remaining effective time samples
are rejected before sealing the package. Setting only a default was insufficient:
authored frame values could otherwise retain the source scene's larger budget.

## Compatibility and qualification

The SQLite table schema is unchanged. New record fields are additive. An old
cancel-requested record without a delivery flag is treated as pending delivery.
Its permanent stop fence and submission-attempt flag remain intact. Existing old
`failed/output_changed` records are not reclassified automatically: the former
record format did not distinguish unreadable images from confirmed changes.

Backends that return cancellation without the optional exact-boolean
`cancellation_delivered: true` continue to have their cancel method retried until
they confirm cancellation. Backend cancel implementations must be idempotent.
Existing public state names and method signatures are unchanged.

Regression tests use disposable journal/files, simulated process identities,
failure injection, and real OpenUSD on synthetic stages. The repair qualification
does not exercise Houdini's native exporter, a Karma render, the live artist GUI,
actual shared storage, or real process termination. Prior bounded native evidence
is described in `ARTIST_RENDER_IMPLEMENTATION.md`; these changes still need native
qualification before a production renderer release.

Focused command (stock Python with pytest; OpenUSD cases skip when pxr is absent):

```text
python -B -m pytest tests/test_farm_core.py tests/test_farm_backend.py tests/test_farm_recovery.py tests/test_farm_usd_settings.py tests/test_render_workspace.py -k "not owned_process_tree_termination" -p no:cacheprovider
```
