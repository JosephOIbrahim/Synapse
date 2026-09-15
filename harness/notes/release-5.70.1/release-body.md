Nothing that runs changed. What you read did.

If 5.70.0 works for you, 5.70.1 is optional: the panel, the tools and the installer
payload's code are identical apart from the version string. This release exists so the
first things an artist reads say the right thing in a form that can be scanned.

**README rewritten for scanning.** Same facts, one idea per block. Verified by three
independent critics before the build — every number, link and claim traced to its
producer; ADHD form per the project convention; nothing lost against the previous file.

**Setup guide links corrected.** `docs/getting-started/installation.md` had sent artists
to the 5.68.0 download and checksums — three releases behind.

**Harness state is in the tree.** Seven of the twelve harness boards, the reach and flow
agent definitions, the 2026-09-06 UX handoffs and the 2026-09-15 closeout, harness-review
and first-principles audit notes were untracked on one machine. They are committed now.

## Install

`SYNAPSE-5.70.1-Setup.exe` upgrades in place and preserves projects, memory,
credentials and custom files — that path is one of the 19 qualification checks.

- The installer is **unsigned**. Verify against `SHA256SUMS.txt`.
- Running from source? Pull `v5.70.1`. There is nothing new for a live Houdini
  session to load.

## What was measured

- Stock suite **8920 passed / 430 skipped / 0 failed** — identical to 5.70.0.
- Panel seat suite on Houdini 22.0.400 offscreen: **201 passed / 5 failed** — the same
  five known reds, **none new**.
- Installer unit checks **37 passed**.
- Installer qualification **19 of 19 PASS, exit 0**, against an isolated TestSetup that
  carries the same payload sha256 as the file published here.
- `git diff --stat v5.70.0 v5.70.1 -- python installer` shows one file: the version
  string in `python/synapse/__init__.py`.

`installer-verification.json` carries the full evidence, **including what was not run**.
CI on the tagged commit is recorded as `PENDING_AT_PUBLICATION` and will be amended in
place when it concludes.

## Still open

- Five panel seat tests remain red. Two are recorded design conflicts awaiting a
  ruling; three are named and undiagnosed.
- The suite's skip population is not stable — 21 tests are disabled by a symbol missing
  from an out-of-tree dependency, and no gate in this repository can see it.
- **Disclosed, not fixed:** a message typed while the bridge is down is queued without a
  visible signal and replayed when the bridge returns. Found by code reading in the
  2026-09-15 artist-surface review; not yet reproduced live. If **Connect** shows the
  bridge down, wait for it before sending.
- Code signing, a clean Windows machine and native wizard visual qualification remain
  separate checks.

Full notes: [`docs/releases/v5.70.1.md`](https://github.com/JosephOIbrahim/Synapse/blob/v5.70.1/docs/releases/v5.70.1.md)
