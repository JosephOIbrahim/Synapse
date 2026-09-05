# CTO REVIEW LOOP — operator's card

One crank = one honest review of master with a backlog the next crank checks itself.

---

## RUN

```
Agent: cto-orchestrator
```

or, direct:

```
Workflow name=cto-review
args {"date":"YYYY-MM-DD","head":"<sha>","range":"<last-tag>..<sha>","autonomy":"amber"}
```

---

## READ

```
harness/cto/runs/<date>/report.json      full verdicts + raw lanes
harness/cto/BACKLOG.json                 open items, each with a closure predicate
harness/cto/LEDGER.md                    one line per run
```

---

## FLIP (Joe's word only)

```
harness/cto/STATE.json  autonomy   red | amber | green
                        spec_status DRAFT -> RATIFIED
```

`green` + `"apply":true` lets the loop land gate=auto items in worktrees. It never merges.

---

## BREAKS

Bridge down → lanes report 'claimed' and 'shipped' only, never 'live'. Fine.
A lane returns nothing → report says coverage partial; re-run with `"lanes":["DESIGN"]`.
Predicate 'unknown' → the command is missing on this machine; item stays open.
