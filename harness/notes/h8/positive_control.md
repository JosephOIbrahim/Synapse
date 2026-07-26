# H8 — POSITIVE CONTROL RESULT

**Reported first, per the brief.** An audit that cannot detect known errors cannot be trusted on
unknown ones.

---

## Design

Twelve rulings were given to three independent adjudicators. **Four were known to have been wrong**
and corrected by later rulings. **Eight were decoys** believed sound. No agent was told which was
which, or that the set contained any known-wrong rulings at all, or what distribution to expect.

    probe set:  15, 48, 58, 64,  2, 14, 35, 50, 60, 71, 75, 77
    known-wrong: ─┴───┴───┴───┘   (R15, R48, R58, R64)
    decoys:                      └──── the remaining eight ────┘

Three lenses, deliberately different: `crucible` on evidence, `crucible` on logic/scope,
`h22-adjudicator` on consistency.

**Two acceptance criteria, not one:**

1. **Sensitivity** — all four known-wrong rulings independently flagged `SUPERSEDED_UNMARKED` or
   `SCOPE_ERROR` (or a higher-precedence verdict that subsumes them).
2. **Specificity** — the method must be able to return `SOUND`. A method that flags all twelve
   also "catches" all four and is worthless. This is Law 1 applied to the audit instrument:
   *state the condition under which this fails.*

---

## Result — PASS on both criteria

### Sensitivity: 4 of 4 caught, by all three independent lenses

`+` = further verdicts in `also_applies`.

| Ruling | Known failure | crucible-A | crucible-B | adjudicator |
|---|---|---|---|---|
| **R15** | named a harm, fixed only the mechanism (caught by R70) | `EVIDENCE_FAILS`+ | `EVIDENCE_FAILS` | `EVIDENCE_FAILS`+ |
| **R48** | closed the render half as not-implementable (refuted by R73) | `SUPERSEDED_UNMARKED` | `SUPERSEDED_UNMARKED` | `SUPERSEDED_UNMARKED` |
| **R58** | remedy was "cite the live probe" (replaced by R66) | `SUPERSEDED_UNMARKED`+ | `SUPERSEDED_UNMARKED` | `SUPERSEDED_UNMARKED` |
| **R64** | predicted `registered=True, in_use=False` (inverted by R74) | `SUPERSEDED_UNMARKED`+ | `EVIDENCE_FAILS`+ | `SUPERSEDED_UNMARKED` |

**12 of 12 lens-verdicts on the known-wrong four are non-SOUND.** Where a lens went past
`SUPERSEDED_UNMARKED` to `EVIDENCE_FAILS`, it carried `SUPERSEDED_UNMARKED` in `also_applies` — a
higher-precedence verdict on grounds no lens was given.

**The method found more than it was tested for.** On R15 all three lenses independently surfaced
that the ruling's stated premise — *"two of three already use `parent_path`"* — is **false against
the tree**. One lens proved it by git archaeology at the ruling's own commit
(`git show 764f926:…` — all three tools read `params.get("parent", "/stage")`, none used
`parent_path`), and the repo records the same refutation in-code at `component_builder.py:76-81`.
So R15 is not merely scope-limited as the control assumed; its factual premise was inverted, it was
caught on the day, and it never reached the ruling.

**The method found more than it was tested for.** On R15 both lenses independently surfaced
`SR1.json:112` drift D4, which records that R15's stated premise — *"two of three already use
`parent_path`"* — is **false against the tree**: only `scene_template` did. So R15 is not merely
scope-limited, as the control assumed; its factual premise was inverted, and that was recorded in
a receipt on the day and never reached the ruling.

### Specificity: the method returns SOUND, and does so unanimously

| Decoy | crucible-A | crucible-B | adjudicator | |
|---|---|---|---|---|
| R14 | `SOUND`+ | `SOUND` | `SOUND` | **unanimous clean** |
| R35 | `SOUND` | `SOUND` | `SOUND` | **unanimous clean** |
| R60 | `SOUND`+ | `SOUND` | `SOUND` | **unanimous clean** |
| R75 | `SOUND` | `SOUND` | `SOUND` | **unanimous clean** |
| R2 | `UNENFORCED` | `UNENFORCED` | `SOUND` | split |
| R71 | `EVIDENCE_FAILS`+ | `UNENFORCED` | `SOUND` | split |
| R77 | `UNENFORCED` | `UNENFORCED` | `SOUND` | split |
| R50 | `UNENFORCED` | `UNENFORCED` | `EVIDENCE_FAILS` | **unanimous flagged** |

No lens flagged everything; every lens returned `SOUND` for at least four decoys, and four decoys
came back clean on all three. **The instrument can report clean, so its non-clean reports carry
information.** Had the table been all-flagged, the control would have failed on criterion 2 and the
four true positives would have proved nothing.

### The control found a fifth known-wrong ruling nobody had flagged

**R50 was scored non-SOUND by all three lenses independently.** It was placed in the set as a
decoy. It is not one.

R50 reads *"**Ruled, adopted into the constitution:** `ABSENT` requires a positive control on the
same class."* The orchestrator verified directly:

    grep -n -i "positive control|same class|UNVERIFIABLE" harness/AGENT_CONSTITUTION.md
    → ZERO MATCHES
    git log --oneline -- harness/AGENT_CONSTITUTION.md
    → 6b41e1a  (v1, single commit, never amended)

The constitution's Article II ladder has six tiers and `UNVERIFIABLE` is not among them; Laws 1–7
do not state the rule. **R50 reports what was attempted, not what happened — Law 3, violated in the
act of adopting a law.** The rule did propagate, but only as prose copied into leg prompts, which
is instruction rather than structure — the precise distinction R61 rules against eleven rulings
later.

That the control surfaced a true positive it was never told about is the strongest available
evidence that it is measuring the document rather than reciting the answer key.

### Reader calibration (R50 applied to the audit itself)

Both lenses reported `found_a_real_mechanism: true` and quoted real enforcement at real
`file:line` — `harness/relay-settings.json:47`, `tests/test_solaris_tool_registration.py:523`,
`harness/verify/checks.py:1684`. The orchestrator independently confirmed five more (ground-truth
§A). An `enforcement: none` verdict in this audit is therefore a finding, not a failed search.

---

## What the control also exposed about the fleet

- **`h22-adjudicator` has no `Bash` tool.** It reported this itself rather than presenting
  git-sourced conclusions it could not have reached, and substituted Grep/Read across checkouts.
  That is Law 3 honoured by an agent unprompted, and it is why the sweep's git-archaeology work is
  assigned to `crucible`, which does hold Bash.
- **Enforcement must be branch-scoped.** The lenses disagreed on R64's enforcement
  (`mechanism` vs `landed_unpinned`) purely because the mechanism
  (`tests/test_moneta_substrate_truth.py`) exists **only on the unmerged `repair/h6-substrate-truth`
  branch**. A mechanism on an unmerged branch does not protect this tree. The full sweep therefore
  requires an explicit `UNMERGED:` prefix, and the distinction is carried into the final count.
- **The disagreements are the design working.** R2, R71 and R77 split between lenses. Those are
  exactly the rulings routed to the adversarial verification phase rather than averaged.

---

## Verdict

**The method detects known errors and can still return SOUND. It is fit to run on the other 66.**

Had either criterion failed, the correct action was to stop and repair the method before auditing
anything — and to say so. Neither failed.
