# Panel model permission for a Houdini session

The artist reports that approving each chat turn interrupts creation. They explicitly selected session approval over permission saved across restarts on 2026-09-07.

Add **Allow for this session** beside **Allow this task** and **Keep editing** in the model-sharing dialog. Preserve the current disclosure of prompts, conversation, scene context, recalled memory, tool results and images. Session permission covers future explicitly submitted panel tasks using this exact provider, model, endpoint and credential with the selected project rules. It ends when Houdini exits. Project means the selected rules file; changing HIP files alone is not a project-rule change.

Keep the existing task option for one-off work. The rejected alternative is persisting consent across restarts; this change writes no session permissions to preferences, project rules or conversations.

The shared `model_access` authority owns ephemeral session approvals. Each send still captures its own request scope and receives its own task grant. A revocable session parent binds the canonical rules path, revision, selection generation, exact connection and credential digest. Revocation is checked again at the existing final transport check. Completion and Stop revoke the task child only. Revoking session permissions blocks later requests, including pending tool follow-ups, but cannot recall a request already transmitted.

Ordinary panel reopening evicts the `synapse.*` modules. A single versioned, process-owned memory anchor therefore retains the parent map across module generations. It stores primitive identities and credential digests, never credentials, prompts, providers or task scopes. Old and newly opened panels share revocation. An incompatible anchor or changed process ID fails closed; it cannot inherit permissions into another process.

Local-only rules and invalid rules/selectors continue to deny. Project selection A→B→A cannot revive approval. A scope captured before a project switch cannot be authorized by approving the new project. Session permission is consumed only by explicit panel task creation, never by ambient SDK/background calls or process handoffs. Worker tool permissions remain unchanged.

Show **Session · Revoke** by the connection control while the displayed connection has session permission. Its tooltip names the approved connection and lifetime. The compact wording keeps the control readable at larger text sizes in a narrow panel. Also provide **Revoke session model permissions** in More so an artist can revoke approvals even after changing the selected model. Revocation covers session permissions in all panels in the current Houdini process. Refresh other open panels after approval/revocation.

## Implementation and verification

1. `python/synapse/model_access.py`: ephemeral parent authority and fresh child issuance, exact matching, revocation, stale-policy invalidation. Focused tests in `tests/test_model_session_access.py`.
2. `python/synapse/panel/synapse_panel.py`: explicit dialog option, reuse at the routed-connection approval seam, visible status and revoke controls. No edits to release version, installed preferences, worker policy or live scene.
3. `tests/test_panel_session_consent.py`: independently authored actual-method sequence tests. An isolated native Qt harness checks real buttons, cancellation, project switching during the modal, multiple panels and repeated submits without network requests.
4. Run the existing model-access, transport, background, routing and first-session tests; then the required wider suite with known inherited failures reported honestly. Verify new tests fail under a deliberate isolated mutation. Independently review the final diff and retain commands, output and limitations.

Stop when the change is implemented, focused and native checks pass, independent review finds no unresolved defects, and the result is recorded for review/integration. Local installation and any new public release must be reported as separate states; this feature is not part of the already published v5.66.0 tag.
