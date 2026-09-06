# SYNAPSE first-session milestone

The approved first milestone makes it easier to connect a model, understand
where a panel task is going, read its reply, and find commands. The source is on
`ux/first-session-20260906`, based on `b1ec9a8d`. This build has not been loaded
into the existing Houdini session.

## What the artist gets

- **Connect models:** choose a service and model, enter a masked session key,
  and check the service without sending a scene or prompt. A successful check
  means the service answered and listed that model; generation is still untested.
- **Clear destination:** Local, Cloud, Cloud relay, Remote, or Unverified, with
  the full requested model and endpoint available. Local Ollama evidence is
  explicitly a recent report from that service, not an independent attestation.
- **Permission before sharing:** remote or unverified panel tasks disclose the
  prompt, conversation, scene context, recalled memory, tool results, and images
  they may send. Keep editing preserves the draft and current view. The approved
  endpoint, credential, and requested model stay bound to that task.
- **Readable replies and activity:** headings, lists, code, and safe links;
  observed progress such as waiting for a response or running a named tool.
  Interrupted or failed replies retain the task's model signature.
- **Commands in view:** the Commands button opens the existing palette, with
  the same actions as `/`. Opening or dismissing it preserves the draft.
- **Honest usage:** provider-reported token usage remains the source of counts.
  A model name alone no longer establishes Local or a zero cost. Unknown values
  remain unknown. Two panel tasks cannot overlap the existing shared usage sink.

Entered keys are retained only for this panel session. Closing it clears them;
a task already running may finish with its captured key. Existing configured
environment keys continue to work. Changing a custom address does not carry
the previous service's environment-key binding to the new address.

## Evidence and remaining qualification

The receipt for this build records the focused tests, the complete suite,
independent review, reproduced baseline failures, and the exact limitations.
The standalone `harness/check_first_session_qt.py` runs the actual Qt widgets
with Houdini 22.0.400's plain Python interpreter. It exercises asynchronous
setup, stale results, key lifetime, rendering, safe links, drafts, palette,
worker completion/cancellation, and panel widths of 360, 480, and 720 pixels.
It blocks network calls and supplies simulated replies. Its previews are UI
evidence, not screenshots of a live model or a modified Houdini scene.

No model generation, billing, network creation, USD memory operation, or live
Houdini performance result is claimed by those isolated checks. The broader
suite is reported separately rather than represented as green by the focused
checks. Windows permission and shared-memory failures need their own follow-up.

## First use session

After specific authorization for a separate disposable Houdini test session:

1. Load this reviewed source and confirm its actual imported path.
2. Connect the intended service and verify its listed model and displayed
   destination. Try an invalid selection, then recover in the same dialog.
3. Submit one small explanation task. Compare the displayed task identity and
   actual usage with the provider response. For a remote task, decline once and
   confirm the prompt survives before accepting.
4. Open and dismiss Commands, then read a reply with a list and code block.
   Stop one task and try the next task. Confirm no draft loss or misattribution.
5. Spend a short session creating normally and record interruptions, unclear
   wording, and extra steps. Use those observations to choose the next edit.

The present live scene is not a test fixture. Repository AGENTS.md Law 7 gates
“Anything touching the live Houdini GUI” on the human's word for that act.

## Next milestones

1. Consistent Solaris network construction and dependable vertical/horizontal
   organization, verified by the resulting network.
2. Reusable recipes with tags, versions, dependencies, and capture when leaving
   a shot or scene.
3. Production-aware local/cloud routing and project-wide sharing enforcement,
   including independently configured MCP clients and background services.
4. Useful render, simulation, cache, and connection notifications.
5. Further panel refinement driven by actual use.

The current panel permission covers panel tasks. It is not a universal firewall
for other clients or services. The saved memory store stays on the workstation;
recalled contents can be included in an approved remote task.
