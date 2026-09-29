# Release preparation: v5.85.2

Publish one commit on top of v5.85.1 (`0df2da2b`). Joe's word: "go"
(2026-09-29), after the seat offered the release.

| Commit | What it does |
|---|---|
| `ce825a26` | The composition anchor reads H22's authored list ops from the prim stack, a LOP target anchors on itself, and tool results encode `hou.Ramp`; `tests/test_h22_composition_and_ramp.py` |

## Evidence

- **The bugs.** On 2026-09-28 the panel and Claude Code both had
  `houdini_set_parm engine=xpu` on `/stage/lookdev_xpu/preview_settings` refused as
  "USD Composition violation" on its internal `pythonscript1`. The bridge log read
  "FAILED-CLOSED ... 'References' object has no attribute
  'GetAddedOrExplicitItems'". `houdini_network_explain` and `synapse_inspect_node`
  failed with "Type is not JSON serializable: Ramp".
- **API probe.** In hython 22.0.400, `Usd.References` and `Usd.Payloads` lack
  `GetAddedOrExplicitItems`, and `SdfPrimSpec.referenceList` and `.payloadList`
  have it.
- **Real pxr.** A hython probe built a stage with an internal reference and a stock
  `karmarendersettings` LOP. The anchor passed, the blast radius was the LOP itself,
  and a self-reference and a missing file were still refused. A real `hou.Ramp`
  encoded.
- **Live.** After Joe restarted Houdini on 2026-09-29, Claude Code ran headless
  (model `claude-sonnet-5-5`, synapse tools only: 39 reads plus `houdini_set_parm`)
  and wrote engine and picture on `preview_settings`. It wrote the values the scene
  already held, so the scene did not change, and each write still ran the anchors.
  Both returned `composition: true`, `anchors_hold: true` and fidelity 1.0. The
  parameter pane showed `XPU Parameters` and `$HIP/render/$HIPNAME.$OS.$F4.exr`.
  `houdini_network_explain` on `/stage/lookdev_xpu` returned 13 nodes with the
  31-key `tonemapcurve` ramp, and `synapse_inspect_node` on `preview_settings`
  returned the ramp.
- **Mutation.** Six of the nine new tests fail on the old code. The other three pin
  fail-closed behavior that the fix keeps.
- **Tests.** The `tests/` suite passed on Windows with Python 3.14: 10,111 passed,
  457 skipped, 0 failed.
- **Found, not fixed (BP12 items 15 and 16).** Reads return evaluated values only,
  so Claude Code reported the picture write as failed while the pane showed it set.
  The scene hash moved between two back-to-back writes with only reads between them.

This record does not claim that the later CI, push or publication steps have
completed. They are checked after publication.
