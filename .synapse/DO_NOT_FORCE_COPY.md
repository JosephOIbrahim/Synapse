# ⛔ DO NOT `Copy-Item -Force` INTO `.synapse/`

**This folder holds LIVE, IRREPLACEABLE DATA — not just harness code.**

A `-Force` copy (or any bulk overwrite) into `.synapse/` will silently clobber same-named
files and can destroy work that has **no git history** (`.synapse/` is gitignored — see
`.gitignore`). This already happened once: **2026-06-22**, when a third-party
`synapse-harness.zip` was `Copy-Item -Force`'d in over the top, replacing the harness
**code** files (`harness.py`, `memory.py`, `verify.py`, `config.yaml`, `ip_fence.yaml`) with
the zip's versions.

**That time, nothing was provably lost.** A forensic check (`__pycache__` source-mtime decode,
cross-repo import grep, `git reflog`/`log`/`stash`) found: the data folders share no filename
with the zip, so the copy could not touch them (and didn't — files intact, pre-incident
dates); and no surviving evidence shows the overwritten code differed from the zip. **But it
was unrecoverable *in principle*** — `.synapse/` had no safety net (no shadow copies, not under
OneDrive, never git-tracked). We got lucky on *what* got hit. Next time it could be data, with
no way back. That is why this rule exists.

## What lives here that you cannot get back
- `corpus/`, `scout_corpus/` — retrieval corpora
- `science/` — probe results / harness scaffold
- `provenance/` — 5,000+ `op-*.json` operation records
- `ledger/` — `agent.usd` + Confirmation/DeadEnd/DocConformance entries
- `*_suite.log`, `_vfx_probe_digest.md`, `*_probe*.log` — accumulated run logs

The harness *code* (`harness.py`, `scout.py`, `verify.py`, `memory.py`, `config.yaml`,
`ip_fence.yaml`, `phantom_fence.yaml`, `hooks/`, `contracts/`, `tests/`) **is force-tracked
in git** (`git add -f`), so it has history. The **data above does not** — protect it.

## The rule
1. **Never** `Copy-Item -Force`, `robocopy /MIR`, or `Expand-Archive -Force` *into* `.synapse/`.
2. Stage any third-party drop (e.g. a new harness zip) in a **sibling directory**
   (`_unzip/`, `_incoming/`, …), then **merge file-by-file** — diff each file against the
   live one before replacing it.
3. If a vendor README literally says `copy .synapse <repo>\.synapse` (the ANVIL harness
   README does), **do not run it as-is** on an existing `.synapse/`. Merge instead.

## Safety net
Versioned backups run via the **`SYNAPSE-Backup`** scheduled task (daily + at logon):
dated git bundle + full-tree snapshot incl. `.synapse/` → `D:\Backups\SYNAPSE\`, mirrored
off-site to `OneDrive\Backups\SYNAPSE\`, last 30 kept. To restore the gitignored data after
an accident, pull `synapse-data_<timestamp>.zip` from either location. Backups reduce the
blast radius — they are **not** a license to `-Force`.
