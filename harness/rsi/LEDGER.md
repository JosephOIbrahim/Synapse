# LEDGER — the RSI closure harness

*Append-only skill ledger. Recipes that survived verification, with when-to-use / when-not. A recipe enters
only after it has actually been run and produced a result.*

---

## The honesty rung — prove a signal can represent failure before closing a loop

- **goal:** stop an RSI loop from compounding on a reward signal that cannot represent failure
- **approach:** insert `L1 HONEST` **below** reachability in the ladder. To prove it, find a run where the
  signal is *not* the success value. To refute it, find a constant, a hardcoded literal, a default never
  overridden, or a failure path that does not record at all.
- **verifier result:** at frame, three of nine registered loops fail `L1` (`A1`, `F`, `E`). All three would
  have been wired by the prior harness's "find the dormant half" thesis.
- **when-to-use:** any self-tuning, self-promoting, or self-evolving mechanism before its apply half is wired
- **when-not:** a loop that is purely observational with no actuator — there, honesty is a reporting-quality
  issue, not a safety gate

---

## Make the predicate read the code, not a status field

- **goal:** stop the bar from needing a human edit to tell the truth
- **approach:** `P4` greps `router.py` for `_record_metric` call sites and parses their argument lists with
  paren balancing, rather than reading a `signal_honest: true` field. It then **cross-checks the code against
  the registry** and fails in *both* directions: registry claims honest while code is constant (a lie), and
  code now carries an outcome while registry still says unproven (staleness).
- **verifier result:** independently re-derived exactly the eight call sites the July audit named —
  `router.py` :285, :448, :515, :554, :584, :706, :742, :819 — without sharing a source with the audit. Two
  independent derivations agreeing is stronger evidence than either alone.
- **when-to-use:** any predicate whose ground truth is a greppable code property
- **when-not:** properties needing runtime state (reachability, restart-durability). Those need probes, and a
  grep-based proxy for them would be a false green.

---

## Let the verifier find the registry's own gaps

- **goal:** stop a registry from silently drifting behind the code it describes
- **approach:** `P1` sweeps `python/` and `shared/` for RSI-shaped surfaces by filename pattern **and**
  content pattern, then subtracts everything any registry entry claims. The remainder is drift.
- **verifier result:** on its first run it failed, naming three unregistered surfaces —
  `shared/conductor_advisor.py` (the read side of the §16 loop), `shared/constants.py`
  (`FAST_PATH_PROMOTION_THRESHOLD`, `CONSTANTS_HASH`), and `shared/evolution.py` (`LosslessEvolution`,
  distinct from `python/synapse/memory/evolution.py`). All three were genuine and were registered. The
  predicate found a real gap on run one.
- **when-to-use:** any registry/catalog that claims to be complete over a code surface
- **when-not:** where the sweep's false-positive rate would exceed the drift it catches — then narrow the
  patterns rather than deleting the predicate

---

## Discover harnesses; never list them

- **goal:** a status board that cannot describe a world that stopped existing
- **approach:** `harness/progress.py` treats *any* `harness/<name>/verify.py` as a harness and shells it with
  `--json`. No harness list exists anywhere in the tool. Verifiers run concurrently; unreadable or
  non-conforming ones render `?` with the reason, never a score.
- **verifier result:** built and run against CLEAR before this harness existed; CLEAR reported **5/8 clear,
  3 open**, matching CLEAR's own logged last run (`5 PASS / 3 FAIL`) — an independent cross-check. This
  harness then appeared on the board with no edit to the tool.
- **when-to-use:** any multi-instance status surface in this repo
- **when-not:** never, per R140. If a board needs to know instance names, the design is wrong.
