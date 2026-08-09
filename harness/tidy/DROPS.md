# TIDY — Drop Proposals

> Proposals only. **Nothing here is deleted by the harness.** Each entry is a
> recommendation with rationale and risk. The human approves each drop before
> any `rm` / `git branch -D` runs. See `harness/tidy/SPEC.md` (DROP disposition).
>
> Generated: 2026-08-07 · Dispatch agent: propose-drops

---

## TIDY-09 — `$null` (repo root)

**Path:** `C:/Users/User/SYNAPSE/$null`

**What it is:** A UTF-16 LE, CRLF text file (2054 bytes, dated Aug 4). A
PowerShell redirect artifact — a `2>$null` redirect landed on a literal file
named `$null` instead of discarding stderr. `git status` shows it untracked
(`?? $null`).

**Content confirmed:** It is a captured PowerShell `NativeCommandError` /
`RuntimeWarning` block. The signal inside is a real SYNAPSE vendored-SDK ABI
mismatch warning (bundled `_vendor` wheels ship cp311+cp313 win_amd64, but the
interpreter is Python 3.14.2 → vendor tree INACTIVE). **This signal is real
and is preserved elsewhere in the repo** — the ABI-mismatch / `_VENDOR_ABI_RISK`
topic is referenced in `harness/notes/CTO_RULINGS_01.md`,
`harness/notes/CTO_RELAY_01_RULING.md`, `harness/notes/POSITIONING_CLAIM_AUDIT.md`,
and `harness/notes/receipts/C0.json`. It is not lost by dropping this file.

**Why safe to delete:** It is a junk redirect artifact, not authored work. The
only substantive content (the ABI-mismatch warning) is preserved in the repo's
notes. No code, no harness state, no documentation depends on this file.

**Risk:** None to the tree. The ABI-mismatch signal survives in the notes files
above. (Note: the classifier's "TIDY-45" tracking item does not exist in the
tree — the signal lives in the notes, not a dedicated item.)

**Disposition:** DROP (proposed). Action: `rm '$null'` — human-approved only.

---

## TIDY-10 — `harness/rope/OPERATOR_CARD.md.bak`

**Path:** `C:/Users/User/SYNAPSE/harness/rope/OPERATOR_CARD.md.bak`

**What it is:** A `.bak` backup of the ROPE harness Operator Card (5298 bytes,
dated Aug 3). `git status` shows it untracked (`?? harness/rope/OPERATOR_CARD.md.bak`).

**Content confirmed:** Head matches the live `harness/rope/OPERATOR_CARD.md`
(which is tracked, dated Aug 5). The `.bak` is the **superseded** Aug 3 version;
the live card is newer. No `.bak` file is tracked anywhere in the repo — this is
untracked junk.

**Why safe to delete:** The live `OPERATOR_CARD.md` is tracked and newer. The
`.bak` is a stale backup of an already-tracked file. Nothing references it.

**Risk:** None. The current card is preserved in git; the backup adds nothing.

**Disposition:** DROP (proposed). Action: `rm harness/rope/OPERATOR_CARD.md.bak`
— human-approved only.

---

## TIDY-11 — branch `archive/retina-m2-orphan`

**Path:** git ref `refs/heads/archive/retina-m2-orphan` (HEAD `f3be38c3`)

**What it is:** A branch named `orphan` under `archive/`. Memory
(`retina-v0-verdict`, 2026-07-27) records that the RETINA M2 archive branch was
**rejected as a merge candidate** — `merge-tree` is clean *and a no-op*, and its
`retina/t0.py` is the PRE-crucible-fix version, so taking that side would revert
a shipped showstopper fix. M2 itself shipped as v5.29.0.

**⚠ Two corrections to the classifier's premise — this is why it is BLOCKED, not a clean drop:**

1. **It is NOT local-only.** It has a remote tracking ref:
   `refs/remotes/origin/archive/retina-m2-orphan` (same commit `f3be38c3`).
   Deleting the local branch alone would leave the remote ref; deleting both is
   a remote mutation that the safety model does not authorize.
2. **Memory explicitly says the ref was KEPT, not deleted.** The verdict states:
   *"Ref kept + classified, not deleted (Law 4)."* The branch was deliberately
   retained as a classified archive ref. Deleting it contradicts the recorded
   decision.

**Why it is NOT safe to auto-delete:** `git branch -D` is irreversible (no
reflog recovery for a force-delete of a non-merged branch). The branch is not an
ancestor of `master` and is not merged. It is a rejected-but-kept archive ref,
not garbage.

**Risk of deleting:** Loses the classified archive ref that memory says was
deliberately kept; diverges from the recorded RETINA V0 verdict; the remote
ref remains unless separately handled.

**Disposition:** **BLOCKED** (proposed drop, but NOT recommended). If the human
still wants it gone, the correct sequence is: (1) confirm the remote ref is
also intended for removal, (2) `git branch -D archive/retina-m2-orphan` locally,
(3) `git push origin --delete archive/retina-m2-orphan` — all human-executed.
Recommendation: **keep the ref** per the recorded verdict.

---

## Gate summary

| Item | Disposition | Gate |
|---|---|---|
| TIDY-09 `$null` | DROP | Human approves `rm '$null'` |
| TIDY-10 `OPERATOR_CARD.md.bak` | DROP | Human approves `rm harness/rope/OPERATOR_CARD.md.bak` |
| TIDY-11 `archive/retina-m2-orphan` | BLOCKED (keep) | Human decides; not recommended to delete |
