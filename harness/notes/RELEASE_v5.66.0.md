# v5.66.0 Preview — More creating, less setup

SYNAPSE's six UX milestones bring easier setup, more dependable Solaris networks and clearer feedback to daily work in Houdini. This is a **Preview/RC**, qualified through bounded checks in Houdini 22.0.400; it is not a production-stability claim.

## What's changed

- **Connect with more confidence.** Choose a service and model, check its reported metadata, and see the destination before using it. Replies support readable headings, lists and code. Activity shows observed progress, while usage distinguishes reported totals from unknown values.
- **Build and arrange networks predictably.** Repeated builds preserve arranged nodes and comments. Choose vertical or horizontal layout, review actual connections and ports, and explicitly request rearrangement when needed.
- **Keep useful networks locally.** Save selected Solaris sibling nodes as named, tagged versions containing a native Houdini clip and USD metadata. Review dependencies, then insert a copy into a separate subnet. An optional watch can capture the selected network when leaving the scene; it is not crash recovery. External assets remain references rather than being embedded.
- **Make model sharing an explicit choice.** Prefer a recently checked local model, or keep your chosen model. Project rules offer Ask and Local only. Permissions follow the original project and exact model connection, including queued work; revoked permissions block subsequent owned requests. Previously transmitted work may still finish.
- **Follow work in Events.** See local render and batch reports, connection changes, and supported Houdini jobs you explicitly watch. Events distinguishes finished, preview, failed and uncertain results. Desktop alerts are off by default; shared Quiet settings prevent suppressed events from replaying later.
- **Move through the panel with fewer interruptions.** Open Commands with the button, Ctrl+K or `/` in an empty prompt. Search, recover from empty results and return with Escape without losing the draft. Events and saved networks remain accessible during a running task. Controls wrap, and long replies and code remain readable and scrollable. New shelf openings select SYNAPSE during pane creation to avoid an inherited minimum-width problem; existing open wrappers are not repaired.

## Local storage and sharing

Saved networks and their USD metadata stay in the local recipe library; Events stays in the Houdini session. Those workflows do not require a model request. An approved remote model request can include conversation, scene context, recalled memory, tool output or images, as disclosed before sharing. Project rules govern SYNAPSE's own model requests; external clients and workstation network traffic have their own controls. A local service's reported weights provide locality evidence, not an independent privacy attestation.

## Preview qualification and limits

The final local candidate is `c3c336ebf3de429b433677fd47f95df2aa8a610c`. Its qualification is **PASS_WITH_LIMITS**: 186 relevant checks passed with six skipped, 28 independent native cases passed 197 assertions, and 12 full-host panel/shelf cases passed. The complete suite records **8,067 passed, ten inherited failures and 392 skipped**. Nine failing cases were reproduced on the unchanged baseline; one nested baseline comparison remains incomplete.

The release is built from that candidate with the coordinated 5.66.0 version update. The GitHub release identifies the final release commit and its successful exact-commit CI run. Local qualification limits remain applicable even when hosted CI passes.

The checks cover bounded native and panel workflows on Houdini 22.0.400. They do not establish sustained production reliability, arbitrary scene/HDA compatibility, cloud-provider billing behavior, long simulation completion, background cache execution, real Windows desktop-alert delivery or other Houdini builds. The shelf's docked startup/reuse passed live; its floating/fallback and installed-startup routes do not have a complete live deployment trial. Job notifications do not certify rendered pixels or output-file integrity. Generic SOP range completion is not a supported watch.

Four standing gates remain open for STABLE promotion: `mutation_fail_closed` (fail-closed dispatch), `hot_reload_gated` (development reload control), `installer_host_targeted` (explicit host targeting), and `ci_covers_shipping_surface` (Windows/native-dependency CI). The user approved publication of the disclosed **v5.66.0 Preview plan on 2026-09-07**, carrying all four requirements forward for this release. They remain open. This is a GitHub pre-release and does not replace the Latest stable designation. Workstation installation is outside this publication.
