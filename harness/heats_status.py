"""RETIRED 2026-07-28 - use harness/status.py instead.

R140. This tool had the seven REPAIR-HEATS legs baked into its print statements.
It went on rendering that board for 23 legs and 115 rulings after they stopped
existing - reporting "6/7 receipts", "24 ruling", "F2 running", and the literal
line "Q2 shipping number decides heat scope", while thirty legs were on the
manifest and E0/E1 were live.

It read REAL receipts into a layout that no longer described anything. It never
errored and never looked stale. That is this project's own central finding,
occurring in the tool built to report on it.

Retired rather than deleted, and it EXITS NONZERO: a tool that lies quietly is
worse than one that stops. The original source is in git history at 8425378.

harness/status.py reads legs.json, so the board follows the manifest with no
edit to the tool.
"""
import sys

print(__doc__)
print("  RETIRED. Run instead:")
print()
print("      python harness/status.py")
print()
sys.exit(2)
