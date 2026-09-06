# SYNAPSE first-session milestone

The approved first milestone makes it easier to connect a model, understand
where a panel task is going, read its reply, and find commands. The source is on
`ux/first-session-20260906`, based on `b1ec9a8d`. This build has not been loaded
into the existing Houdini session.

The first-session flow was qualified on 2026-09-06 in a separate interactive
Houdini 22.0.400 process using `ollama/qwen3.5:4b`. The running artist session
was kept intact. The test panel remains available for hands-on feedback.

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

## Live qualification

Joe authorized Houdini testing on 2026-09-06. The disposable trial confirmed
its imported source paths and isolated preferences, home, settings, and scene.
Computer Use exercised the composer, visible Commands, chat, and Token view;
bounded scripts also exercised the actual Qt setup, Stop, and disclosure
controls through the authenticated bridge on the trial process only.

Verified outcomes:

- Missing-model recovery and Local versus Cloud relay classification from
  actual Ollama metadata; no cloud generation was requested.
- A real local reply with bullets, a code block, and the exact model signature.
- Provider-reported usage equals the actual Token widgets. The final two turns
  reported 24,429/51 and 24,462/48 input/output tokens respectively.
- Commands opens and dismisses with the draft intact.
- Stop releases the task and preserves the next draft. An interrupted response
  with no reported usage displays UNKNOWN. Subsequent local tasks complete.
- A completed answer is present exactly once in the next request. The model
  answered `Soft key`, then correctly answered `SOFT KEY` to a follow-up.
- Naturally expired locality evidence becomes Unverified. Choosing Keep editing
  in the real disclosure starts no worker and preserves draft, history, and usage.

The trial exposed and corrected three defects: undersized setup labels at the
host's 2.25 display scale; a Qt callback whose connection receiver could be
collected before cleanup, causing a native crash; and missing completed answers
in conversation history. Each has a failing regression before correction and
passing checks afterward, plus independent review. Crash evidence is preserved.
The crash correction completed real subsequent replies in a fresh host. Only
the idle worker module was later reloaded for the history correction; the host,
panel, and store were retained.

Evidence lives in the accompanying workspace's `checks/houdini-trial`, with
`connection-checks.json`, `commands-check.json`, `stop-check.json`,
`history-check-final.json`, `decline-check.json`, and `final-live-state.json`.
The earlier polling observer missed one immediate task boundary; its mixed
comparison is not qualification evidence. The final history check captures
each provider's usage and matching widgets before sending the next request.

The focused correction suite has 127 passes and 19 skips. A wider worker suite
has 185 passes, six skips, and one failure reproduced on the unchanged baseline
(missing `hdefereval` in the standalone interpreter). The earlier full suite
still has ten recorded failures; it is not represented as green. Nine were
reproduced at baseline and the tenth baseline case remains partially characterized.

This qualifies the bounded first-session flow, not production network building,
rendering, simulation, USD memory writes, external-client sharing enforcement,
cloud billing, or sustained production stability. Local classification remains
recent service-reported evidence. Artist feedback is the next step before the
next product milestone.

## First hands-on review

Use the separate trial panel for a short session and record interruptions,
unclear wording, and extra steps. In particular, revisit the large context cost
of small requests, rechecking locality every three minutes, and the density of
the Token view. These observations guide the next changes. The original live
scene is not a test fixture, and this build has not been deployed over it.

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
