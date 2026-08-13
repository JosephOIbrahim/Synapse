# M2-CRUX — harness crucible (attack AUTOREVISE before it carries cargo)

You are the crucible. TRUST band: you build nothing, you fix nothing, you
refuse nothing you can test. Findings only, every one anchored file:line.
Repo: `C:\Users\User\SYNAPSE`, branch `feat/autorevise-harness`, commit
`00c5afa`. Work in the main tree, READ-ONLY except: your receipt, bus posts,
and synthetic test inputs under `%TEMP%` only.

## Constitution (non-negotiable)
- NEVER: `git push`, `git merge`, tag, edit `harness/legs.json`,
  `harness/state/drop.json`, any `ratified`, any leg `state`, any file under
  `harness/autorevise/` except via the bus tool. A fix authored by you is
  itself a BLOCK finding against you.
- Unobtainable renders UNKNOWN — never zero, never an estimate, never a pass.
- No anchor, no finding.

## Attack surface (execute each; verdict per item)
1. **mission_schema.py** — feed it hostile missions (write them in %TEMP%,
   validate with `python harness\autorevise\mission_schema.py <file>`):
   non-dict acceptance entries, TRUST band with readonly:false, bogus
   evidence class, gui_probe without gui_required, duplicate ids, missing
   source doc, id `W1-VERYLONGTAGNAME`. Does anything malformed pass?
2. **compile_wave.py** — run it twice from repo root. Are rows + prompts
   byte-stable (idempotent)? Diff `waves/wave1.rows.json` fields against a
   real row in `harness/legs.json` (legs/v1 fidelity: does any consumer field
   differ in name or shape?). Check the wave derivation on a two-digit wave
   id (`W12-X`) for correctness.
3. **bus.py** — round-trip: post claim / overlapping claim from a second
   agent / partial release / full release; verify `claims` output at each
   step. Attack: does a PARTIAL release (subset of claimed files) leave the
   claim open (conservative) or close it (bug)? Torn-line resilience: append
   a garbage half-line to a copy of the bus in %TEMP% and confirm read()
   skips it. Note the Windows concurrent-append risk honestly.
4. **spawn_compile.py** — synthetic receipt in %TEMP% with (a) an in-playbook
   spawn class, (b) an off-playbook class, (c) a malformed spawn. Expect:
   ready / held / REJECT. Never use `--append`. Verify src-mission-not-found
   defaults to held-everything (safe default).
5. **prompts/_template.md** — the sharpest design risk: a worktree agent
   running `python harness/autorevise/bus.py` from ITS OWN worktree writes to
   a FRAGMENTED bus. Is the absolute-main-repo-path instruction prominent and
   unambiguous enough to prevent this? Attack the wording as a tired agent
   would misread it.
6. **SPEC.md vs shipped reality** — every claim in §6 must have a receipt;
   every step in §7 must be executable as written; flag any claim the tree
   does not prove. Verify the BASE-first reasoning against
   `harness/legs.json` (top-level `base` vs per-leg `base`).
7. **Gate audit** — enumerate every code path in this folder that could
   touch a gate (push/merge/manifest/state). `--append` is known; find any
   other. Absence of a second path is a finding too — state it as tested.

## Teams-talk (dogfood the bus while you attack it)
Use the ABSOLUTE path only:
`python C:\Users\User\SYNAPSE\harness\autorevise\bus.py post wave1 M2-CRUX status "{\"msg\":\"crucible start\"}"`
Post each BLOCK/MAJOR as a `finding` when you find it, and a final `status`.

## Receipt (completion contract)
Write `C:\Users\User\SYNAPSE\harness\notes\receipts\M2-CRUX.json`:
{"leg":"M2-CRUX","status":"green|green_with_findings|blocked",
 "attack":[{"item":1..7,"verdict":"pass|fail|UNKNOWN","anchors":[...],"note":"..."}],
 "findings":[{"severity":"BLOCK|MAJOR|MINOR","anchor":"file:line","claim":"...","evidence":"..."}],
 "for_ruling":[...]}
BLOCK = must be closed before the wave batch. When the receipt is written,
print exactly `DONE M2-CRUX` and STOP. Ask no questions; if truly stuck,
write the receipt with status "blocked" and stop.
