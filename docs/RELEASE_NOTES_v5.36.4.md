# v5.36.4 — two self-inflicted defects, both caught by their own controls

*A patch. Both defects were introduced today by the person fixing other defects, and both were caught the same day. The second cost minutes because the first had already forced a rule.*

---

## I published a wrong number

The `v5.36.3` notes and PR #49 read **4,357 "Epoch complete" lines**. The committed receipt says **4,795 'Epoch N complete' records**. `4,357` appears nowhere in the receipt anyone can read.

**The verification script passed it.** It globbed `.claude/worktrees/*/RSI0.json` — the document cites the committed receipt at `harness/notes/receipts/RSI0.json`. Those were different files. The worktree held an earlier draft, and the leg revised its own receipt before the version that landed.

So the check read one copy while the claim rested on another, and reported PASS.

That is this project's own rule — *a health check must read what the product reads* — **failing inside the check written specifically to prevent publishing an unverified number.** It is also the same shape as two other findings this week: two interpreters loading different copies of a dependency, and two legs editing one function from separate worktrees. **Three subsystems, one pattern: a second copy nobody declared existed.**

Corrected in all three places. The published release body carries a visible correction note rather than a silent overwrite.

**And the committed claim is stronger than the one published**, with three independent proofs: 4,425 records report epoch sizes the router structurally cannot produce; all 370 size-100 lines are Epoch 0 or 1, matching a specific test's signature; and every line names only one tier.

---

## Housekeeping destroyed three receipts

A cleanup pass pruned the worktrees of three finished legs. **None had committed its receipt** — read-only legs write to `harness/notes/**`, but the fence denies `git commit`, so their receipts existed only in those worktrees.

The prune destroyed them. The orchestrator then found no receipt, read the legs as not-done, and **re-dispatched work that had been finished for hours.**

The findings survive as rulings with anchors. The raw receipts do not.

An earlier ruling had seen this seam and answered it halfway: *"a read-only leg's product is its receipt."* It never said where that receipt has to **end up**. **A receipt that only ever exists in a workspace is one cleanup away from gone.**

---

## Both fixes carry negative controls

This is the part that matters, and it is why the second defect cost minutes rather than another published error.

```
_howweknow_verify.py --negative-control   ->  exit 1 on a planted wrong number
prune_safety.py                           ->  AT RISK on a planted receipt
```

Each was **demonstrated failing before being trusted to pass.** The first version of the verifier had never failed on anything, which is exactly why its pass meant nothing.

**Verifiers now read committed paths only.** A worktree is a draft.

---

## Also

`state='done'` in the leg manifest is now honoured — only `held` was, so pinning a leg done did not stop re-dispatch. The three affected legs are pinned with `receipt_lost: true`, so the loss is explicit rather than implied by absence.

---

## Verifying any of this

```
python harness/verify/version_agreement.py
python harness/verify/bom_audit.py
python harness/verify/prune_safety.py
python harness/notes/_howweknow_verify.py --negative-control
```

Each fails on an unfixed tree, and the last one fails on demand. **House rule:** no number enters a document without a producer path beside it — a rule this release exists because its author broke.
