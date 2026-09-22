# Selected network

Open **Tools → Selected network…** to inspect the current Houdini selection. Refresh reads node identities, advertised ports, and exact connections. The default scan does not evaluate parameters, cook geometry, or read a USD stage. Internal wires, wires entering the selection, and wires leaving it are separate observations. Missing facts and scan limits are reported.

**Pin inspection** holds the captured nodes rather than following later viewport selections. Refresh and prompt preparation recheck their session identities, scene identity, and observed topology. Deleted or replaced nodes, changed connections, or a different scene invalidate the capture. Unpin to inspect the current selection again. The pin belongs to this inspector; it is not a universal editing sandbox.

Choose **Explain**, **Check wiring**, **Fix**, **Optimize**, or **Inspect materials** to prepare a draft with captured context. The inspector validates the capture first, then appends the draft to the existing composer. The artist reviews and sends it through the already selected model. Fix prepares a diagnosis and proposed repair; preparing a prompt never edits the scene or sends a model request.

The wire insertion preview uses an observed connection, an existing selected intermediate node, and explicit zero-based input/output ports. It preserves both original endpoint ports and displays the two proposed connections. Unknown ports, occupied intermediate inputs, incomplete scans, different networks, and cycles visible in the observed wiring refuse a proposal. Connections through dots or subnet indirect inputs require separate inspection. This preview cannot apply changes; external paths, operator semantics, and data-type compatibility still need validation before an edit.

## Optional JEV ranking

In **Connect models → JEV assistance**, enable **Rank selected-network actions** and save. This preference is separate from the existing **Measure routing** setting and defaults off. Configure `TYPESAFE_API_KEY` and the existing TypeSafe project permission. Saving a preference grants no external access.

In Selected network, describe the intent in plain language and choose **Suggest actions**. JEV orders the five existing action templates by relevance. The selected generator and its tools remain unchanged. All actions remain available in their default order while ranking is off, unavailable, denied, busy, malformed, stale, or cancelled.

Ranking uses five comparable [Score questions](https://docs.typesafe.ai/primitives/score.md) in one batch, following TypeSafe's [ranking guidance](https://docs.typesafe.ai/cookbooks/rerank_typesafe.md). Each question sees the same latest text request and public action descriptions. No selection snapshot, node identities, wire data, parameters, history, or attachments are supplied to JEV. Recognizable code, credentials, and filesystem or Houdini paths are skipped. Captured context is added locally only when preparing a draft for the selected generator.

The service is asynchronous, retains at most one request/result per inspector, shares a bounded transport slot, and discards stale results. It does not run while typing or join the Send path. Cached results are checked again against the current permission and request scope. Scores mean relevance, not correctness, permission, or confidence that a repair will work.

## Measurement and extension points

Input-free receipts record the question version, status, fixed action IDs and scores, and measured elapsed time. Synthetic response tests and the labeled fixture `tests/fixtures/jev_selection_actions_v1.json` cover ranking composition and failure handling. They do not establish real JEV accuracy or a latency improvement. Those require an explicitly authorized, representative live evaluation.

The catalog in `jev/selection_actions.py` connects existing Explain/Fix/Optimize functionality with focused wiring and material diagnosis. `jev/selection_suggestions.py` owns semantic ordering; `panel/selection_inspection.py` owns captured inspection state; `server/selection_snapshot.py` owns observed facts. Future material-binding comparisons or saved-network comparisons should supply real evidence through these inspection boundaries before adding a new judgment. A score must never replace identity, topology, permission, or execution checks.
