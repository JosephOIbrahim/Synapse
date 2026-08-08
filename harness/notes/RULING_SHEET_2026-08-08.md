# RULING SHEET - 2026-08-08 - circle letters, run three blocks

Five minutes. Full text lives in harness/NEXT_SESSION.md + harness/tidy/GATES.md.
Nothing below decides for you; letters map 1:1 to the handoff's own options.

## RULINGS

    R-CI0-1  moneta first-deposit force-save (THE ONE)
             [ ] A - keep shipped: first deposit always fsyncs
             [ ] B - monotonic init: docstring true, lone deposit +kill-9 <30s lost
    R-CI0-2  synapse_evolve_memory      [ ] keep CI0 reroute   [ ] deprecate
    R-CI0-3  3 zero-elapsed Win tests   [ ] LEAVE -> retires CLOCK   [ ] FIX -> arms CLOCK
    R-CI0-4  2 stale evolution lines    [ ] direct it -> arms DOCS   [ ] do it yourself
    R-CI0-5  statusline worktree fix    [ ] fix -> arms STAT         [ ] leave
    M6       phrase table design        [ ] exact-match only         [ ] aliases
             -> also check the slot inside harness/prompts/m6.md

## TIDY (detail: harness/tidy/GATES.md)

    [ ] commits 1-5   [ ] drop $null + .bak   [ ] legs M5/M5b flip
        + same flip for RES and H3a: orchestrator board 08-06 19:41 shows
        both done; manifest rows never updated. Data fix, not a ruling.
    [ ] gitignore models/ + shot_layers/      [ ] worktree prunes 22/23
    NOTE (observed 08-08): yesterday's git-add staging no longer shows in
    status. Re-stage per tidy/COMMITS.md before committing.

## BLOCK 1 - flip states in harness/legs.json per rulings above

    STAT / DOCS / CLOCK:  held -> ready  (or retire CLOCK on LEAVE)
    M6: flip only after Block 2 AND the brief slot is filled.
    Pair discipline: orchestrator dispatches EVERY ready leg - hold GUARD
    if you want strict pairs (burn order is on AM_BATTLE_PLAN.md).

## BLOCK 2 - Gate C (yours alone)

    $env:SYNAPSE_GATE_C=1
    git merge ci/ci0-honest-green
    git checkout master

## BLOCK 3 - launch, REAL terminal only (DC-headless stalls, verified)

    claude --model claude-opus-4-8 --permission-mode acceptEdits
        # in-session: read harness/prompts/base.md, execute end to end
        # (BASE + STAT need this seat - relay-settings denies harness/ edits)
    powershell -File harness\orchestrate.ps1
        # dispatches ready legs; meters: python harness/progress.py --watch
