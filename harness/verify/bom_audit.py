"""BOM audit across every JSON this project writes or reads.

A UTF-8 BOM (EF BB BF) breaks Houdini's package parser silently - the package
does not load, no error appears, and the panel simply never registers. It cost a
live panel on 2026-07-27 and it was self-inflicted: PowerShell's
`Set-Content -Encoding utf8` writes a BOM on Windows PowerShell 5.1.

R26 already caught this exact mistake on relay-settings.json two days earlier.

The first version of this audit was worthless: it used relative paths from a
shell whose CWD was elsewhere, every read threw, and the null comparison
evaluated false so every file reported CLEAN. A check that reports clean when it
cannot read the file is the defect this repository keeps finding. Absolute paths
and an explicit existence assert now.
"""
import os, sys, json

ROOT = r"C:\Users\User\SYNAPSE"
DEPLOYED = r"C:\Users\User\OneDrive\Documents\houdini22.0\packages"

targets = [
    os.path.join(ROOT, "VERSION"),          # R107: carried a BOM from the v5.35.0 release
    os.path.join(ROOT, "packages", "synapse.json"),
    os.path.join(ROOT, "harness", "legs.json"),
    os.path.join(ROOT, "harness", "relay-settings.json"),
    os.path.join(ROOT, "harness", "readonly-settings.json"),
    os.path.join(ROOT, "harness", "agent-settings.json"),
    os.path.join(ROOT, "harness", "verify", "suite_baseline.json"),
    os.path.join(ROOT, "drop.json"),
    os.path.join(DEPLOYED, "synapse.json"),
]

BOM = b"\xef\xbb\xbf"
bad, missing, clean = [], [], []

for p in targets:
    if not os.path.exists(p):
        missing.append(p)
        continue
    with open(p, "rb") as f:
        head = f.read(3)
    (bad if head == BOM else clean).append(p)

def short(p):
    return p.replace(ROOT + os.sep, "").replace(DEPLOYED, "<deployed>")

print("BOM AUDIT")
print("=" * 60)
for p in bad:
    print("  *** BOM ***", short(p))
for p in clean:
    print("  clean      ", short(p))
for p in missing:
    print("  MISSING    ", short(p), "  <- could not be checked, NOT clean")

print()
print("bad: %d   clean: %d   unreadable: %d" % (len(bad), len(clean), len(missing)))

# A missing file is NOT a pass. That distinction is the whole point.
sys.exit(1 if (bad or missing) else 0)
