# v5.66.1 — Approve once, keep creating

SYNAPSE can now remember an explicitly approved model connection for the current Houdini session. Choose **Allow for this session** to continue with follow-up panel prompts without repeating the sharing dialog each turn.

## What changed

- **A clear choice of permission lifetime.** The dialog offers **Allow this task**, **Allow for this session**, and **Keep editing**. Cancel, Escape and closing the dialog preserve the draft and attachments.
- **Approval survives panel reopening.** Session permission applies to the exact provider, model, endpoint and credential under the selected project rules. It remains in process memory until Houdini exits. It is never written to preferences, project rules or conversation history.
- **Visible revocation.** Use **Session · Revoke** beneath the prompt, or **More → Revoke session model permissions**. Revocation updates open panels, including panels opened before a reload, and blocks subsequent requests using that session approval. Requests already transmitted may finish.
- **Fresh boundaries for every task.** Each submitted task still gets its own permission scope. Completing or stopping a task retires that task's permission while preserving the explicitly selected session approval. Changed project rules invalidate session approval; another model connection or credential requires its own permission.
- **Readable controls at larger text sizes.** The session control uses the shared panel styling and fits the tested 360- and 560-pixel widths at text scales 1.0 and 2.25.

## Sharing and local storage

An approved model request can include prompts, conversation, scene context, recalled memory, tool results and tool-supplied images. Saved memory remains local; recalled contents may be sent as disclosed in the dialog. Session permission does not authorize background SDK requests or child-process handoffs. Local-only project rules still apply, saved background permissions remain separate, and worker tool permissions are unchanged. Here, project means the selected model-rules file; changing HIP files alone does not select different rules.

After updating, finish any current task and reopen the SYNAPSE panel to load the fix. Existing repository-based Houdini packages continue to use their configured source location.

## Verification and limits

The feature checkpoint is `443e5bf5851bd5d2c5c73f9f8f9214c5605b65bc`:

- **336 focused checks passed**, including session permission, transports, routing, panel behavior and agent tests.
- **24 native Qt cases passed** using Houdini 22.0.400's Python 3.13.10 and Qt 6.8.3 in isolated offscreen controls. These execute the actual panel methods and controls; they are not 24 full-host or live-model workflows.
- **16 independent composition checks passed**, including full module eviction/reimport and revocation across panel generations.
- Deliberate regressions in session reuse, revocation and old-generation display were detected by the corresponding checks.
- The wider local suite recorded **8,025 passed, ten previously recorded failing names and 391 skipped**. All ten failing names match the preceding qualification; nine had been reproduced on the earlier unchanged baseline, while one baseline comparison remains incomplete. Footer-only refinement overlapped that wider run; the final focused and native checks cover the final source.

This is a bounded panel-permission qualification. It does not establish full installed-startup behavior, arbitrary scene compatibility, actual provider generation or billing, or sustained production reliability. The active artist scene was not used for these tests. Successful hosted CI does not remove the recorded local failures or native/runtime limits.

The four standing requirements from the prior release remain open: `mutation_fail_closed`, `hot_reload_gated`, `installer_host_targeted`, and `ci_covers_shipping_surface`. Publishing this patch as **Latest** does not claim that those requirements are satisfied.
