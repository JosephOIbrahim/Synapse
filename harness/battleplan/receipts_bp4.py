# receipts_bp4.py - read every BP4 leg receipt straight from its branch (no checkout) and print a one-line
# summary per leg: status, product head, acceptance verdict counts, ruling items, findings. Read-only.
# Run: python harness/battleplan/receipts_bp4.py            (also used at close for the merge ledger)
import json, subprocess, sys
from collections import Counter

LEGS = ["INTAKE", "RULINGS", "B7FIX", "SPATIAL", "PANELFONT", "USDKNOW", "CRUX", "TIDY"]
REPO = r"C:\Users\User\SYNAPSE"

def show(ref):
    try:
        return subprocess.check_output(["git", "-C", REPO, "show", ref], stderr=subprocess.DEVNULL).decode("utf-8-sig")
    except subprocess.CalledProcessError:
        return ""

for leg in LEGS:
    raw = show(f"bp4/{leg.lower()}:harness/notes/receipts/BP4-{leg}.json")
    if not raw:
        print(f"BP4-{leg:<10} no receipt on bp4/{leg.lower()}")
        continue
    try:
        r = json.loads(raw)
    except Exception as e:
        print(f"BP4-{leg:<10} receipt present but not JSON: {e}")
        continue
    acc = Counter((a.get("verdict") or "?") for a in r.get("acceptance", []))
    head = (r.get("head_sha") or r.get("product_head") or "?")[:8]
    print(f"BP4-{leg:<10} {r.get('status','?'):<22} head {head}  acceptance {dict(acc)}  "
          f"ruling {len(r.get('for_ruling', []))}  findings {len(r.get('findings', []))}")
    if "--full" in sys.argv:
        for f in r.get("findings", []):
            print(f"    - {str(f.get('claim', f))[:220]}")
