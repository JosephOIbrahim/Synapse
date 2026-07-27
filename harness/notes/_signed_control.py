"""Control for the signed-credit fix.

Before: the authorship suffix attached to the FIRST node chip, which on a
structured answer fell inside a markdown table cell and rendered as
`/stage/lights - signed GLM 5.2` mid-table. Observed live on a 2,727-node
explain of karma_user_guide.hip.

After: chips never take it; the standalone note renders once, at the foot.

Both directions are asserted - the credit must appear exactly once, and it must
not appear inside the table.
"""
import sys
sys.path.insert(0, 'python')

from synapse.panel.message_formatter import format_synapse_message

md = "\n".join([
    "| Subnet | What it demonstrates |",
    "|---|---|",
    "| /stage/lights | every light type |",
    "| /stage/noise | noise diagnosis |",
])

html = format_synapse_message(md, grouped=False, signed="GLM 5.2")

count = html.count("signed GLM 5.2")
print("credit count            :", count, "  (must be exactly 1)")

# where does it sit? split on the last closing div of the body
foot = html[-300:]
print("credit at the FOOT      :", "signed GLM 5.2" in foot)

body = html[:-300]
print("credit inline in body   :", "signed GLM 5.2" in body, "  (must be False)")

ok = count == 1 and "signed GLM 5.2" in foot and "signed GLM 5.2" not in body
print()
print("RESULT:", "PASS" if ok else "FAIL")

# Negative control: with no signature, nothing renders.
h2 = format_synapse_message(md, grouped=False, signed=None)
print("no-signature control    :", "signed" not in h2, "  (must be True)")

sys.exit(0 if ok else 1)
