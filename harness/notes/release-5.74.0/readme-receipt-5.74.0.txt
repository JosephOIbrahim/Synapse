  mermaid blocks: 3
  1. flowchart LR  7 nodes   styled 7/7   fill=#333333 ink=#FFFFFF
  2. flowchart TB  9 nodes   styled 9/9   fill=#333333 ink=#FFFFFF
  3. flowchart TB  5 nodes   styled 5/5   fill=#333333 ink=#FFFFFF
     21 nodes across 3 block(s), all resolved by source

  ASSERTED vs ACTUAL   (these gate - a mismatch fails this receipt)
    version            VERSION=5.74.0
      release-tagged   v5.74.0
      not release-tagged (not checked, historical): 22.0.400, 5.43.0
    tool count         README says 137   len(TOOL_DEFS) = 137   True

  NEGATIVE CONTROLS    (a resolver that cannot fail is not evidence)
    unstyled block        reported as failing: yes
    white-on-white block  reported as failing: yes

RESULT: PASS - source declares dark-grey fill and white ink on every node,
        version strings and the tool count match their producers.
        NOT PROVEN: that GitHub renders those colours. No renderer was invoked.
C:\Users\User\SYNAPSE\harness\notes\readme_check.py:226: RuntimeWarning: SYNAPSE vendored-SDK ABI mismatch: the bundled native wheels under C:\Users\User\SYNAPSE\python\synapse\_vendor ship cp311 + cp313 win_amd64 binaries, but this interpreter is Python 3.14.2 on Windows (no matching ABI). The vendor tree is INACTIVE on this Python, so SYNAPSE will rely on a real pip-installed pydantic/anthropic. If those are absent, the brain (agent loop) will fail later with a cryptic deep ImportError. Remediate by re-vendoring for this Python (see python/synapse/_vendor/README.md) or by using the out-of-process sidecar (see harness/notes/gate-0.1-sidecar-vs-abi3.md). Query synapse._VENDOR_ABI_RISK to detect this in diagnostics.
  from synapse.mcp._tool_registry import TOOL_DEFS  # noqa: PLC0415
