# v5.79.0 -- one Commands list, and six dead gates

**Product change.** {{PRODUCT_DIFF}} (`python scripts/product_surface.py --diff v5.78.0 HEAD`).

**No new installer in this release.** The `SYNAPSE-5.75.2-Setup.exe` the README links is the last built installer and does **not** carry these changes. An installer build is a separate, later act.

## What you will notice

**The Commands list has one name and one order.** The overflow action said "Palette", the tooltip said something else, and the rows arrived in whatever order the alphabet produced. It is now called Commands everywhere, and each row carries a group, a head and an order, so the list is sorted by a decision rather than by spelling. Adding a band means giving its rows a group, not re-sorting the list. (`python/synapse/panel/tool_palette.py`, `command_palette.py`, `synapse_panel.py`.)

**The first thing you click cannot dead-end.** Type `/` into an empty composer on an empty scene and the top of the list used to be a registry row whose only honest answer was "nothing is selected". The first eight rows now each lead somewhere: four open a local view without reaching a model, one restores the last session and answers plainly when there is none, and three send a prompt that states its own empty-selection fallback. A probe walks all eight and names the row that dead-ends. (`python/synapse/panel/scripts/probe_first_click.py`.)

**One registry, not two lists that disagreed.** The five commands the panel answers itself are now a single frozen set with a field on every entry, so the list and the handler can no longer drift apart. One row was found missing along the way: the panel has intercepted `/restore-session` since W7-SESSCOPE and the list had never said so. The brief said 20 rows needed a decision; the real number was 21.

**The panel scales with the host, all of it.** Roughly 25 sizes inside the SWEEP_A block were frozen pixels, including the status dots and chevrons, so at a 2.25 host scale the text around them grew and they did not. Every builder now takes the scale and floors it the same way. Nothing moves at 1.0; at 2.25 the chat rules go 12px to 27px, measured.

## What you will not notice

**Five letter-spacing declarations are gone and five arithmetic `700`s are named weights.** Cosmetic in effect, load-bearing for the audit: the type ramp is now one thing rather than a ramp plus a scatter of literals.

**A comment was the bug.** The strict audit's "no bundled font in QSS" row was caused by a code comment naming the bundled face, because comments ship inside the generated stylesheet string. The comment now describes the face instead of naming it.

**The font floor tells the truth about itself.** A provenance string in the design tokens said "nothing in the panel scales to the host". The panel seeds its chrome scale from the host font at `synapse_panel.py:552`, so that sentence had been false for some time. It now says what is measured.

## What changed in the build harness

**Four gates were handed to the legs, and not one of them could pass.** Every panel leg was handed acceptance lines that could not pass on any branch, master included:

- `audit_panel.py --strict exits 0` -- impossible since 2026-09-15, because the audit read a token that had been deleted and crashed on its first table, taking two real FAIL rows down with it.
- `hytest tests/panel/test_bc_wave.py exits 0` -- impossible too: master itself is 2 failed, 11 passed there.
- Worse than dead, **both lied from a worktree.** `HOUDINI_PACKAGE_DIR` points Houdini at the main checkout and beats `PYTHONPATH`, so hython imported `synapse` from `C:\Users\User\SYNAPSE` whatever branch was checked out. A gate printing green for code the branch did not contain.
- One seat test needs an Anthropic key from a gitignored `.env` that no worktree has, so every worktree also saw a phantom third failure.

`harness/notes/bp9/panel_gate.py` replaces all four. It forces the interpreter onto the tree under test and **prints where it imported from**, supplies the key in memory without ever writing it into a worktree, and ratchets the audit and the seat suite against committed baselines instead of demanding a green that does not exist. Both baselines are in the repo; a row may only be deleted by the commit that fixes it.

**A fifth dead gate, found by rehearsing.** Running the composed gate on a trial integration before the graph finished caught `panel_gate.py` matching only `G3 RESULT: <n> FAIL` -- the audit prints `G3 RESULT: pass` when nothing fails, so a fully green audit parsed as a crash. A gate that cannot recognise success is as dead as one that cannot pass.

**And a sixth: the instrument that replaced the other five was lying the same way.** The composed gate's three hython probe rows never set `HOUDINI_PACKAGE_DIR`, so every one of them imported the panel from the main checkout and reported on code the integration does not contain. Two of those rows had been reading PASS. `panel_gate.py`, two rows above in the same script, was proving its own tree correctly the whole time.

It surfaced by accident: a probe called a helper that exists on the branch and not on master, and the resulting attribute error gave it away. Without that accident this release would have been cut on three green rows measured against the wrong tree.

The rule that came out of it is now a gate row of its own, placed first: print the path the interpreter actually imported from, and fail unless it is the tree under test. Every later row is void unless that one is green. A convention inside one helper was not enough, because the next row added did not copy it.

**A read-only probe was eating the artist's parked session.** The first-click probe's own docstring claimed READ-ONLY. Its adversarial verifier disproved that half and proved it: `SYNAPSE_PANEL_SETTINGS` isolates the panel's settings only, while the conversation store resolves from the HIP directory, so merely constructing the panel parked the live conversation and destroyed whatever was already parked there. Seeded with a live conversation and an older parked one, the probe left the live slot empty and the older one gone. Repaired, both survive byte-intact. Pinned by a test that needs neither Qt nor hython.

**Every verifier said no, and every verifier was right.** Three legs came back SOUND-WITH-NITS with `merge_ready` false, each writing in its notes that the leg itself was clean and the red was pre-existing -- one of them reproduced master's identical failures in an independent worktree to prove it. The composed gate now waives exactly the two proven-dead predicates, mechanically; anything else a verifier failed still refuses the leaf.

**The composed gate found five reds no leg could see.** Each leg runs only the tests its own acceptance names, so a leg cannot catch what it breaks elsewhere. Every leg was green alone. Running the whole suite over the merged tree, three times, caught all of these:

- The new first-click probe emitted `print()` eleven times, which a pin forbids anywhere under the package. The convention already existed one directory over, where a sibling probe writes through a helper on stdout. The probe now does the same, so the pin stays intact rather than being widened.
- Moving the slash telling into the composer changed a constructor that a *second* pin holds verbatim. The leg amended the first pin and missed this one. Declared through the mechanism that file already provides, with the entry generated from the real sources rather than hand-typed. The change is not optional: the audit check that leg cleared requires the telling to ride there.
- The transcript measure overshot its own 66-character constant. Sizing the column with Qt's average character width averages the whole glyph set, including capitals and symbols prose barely uses; once the type scale moved the metrics, a 630 pixel column rendered 75.2 characters per line, outside the very band the constant exists to hold. It now measures a prose sample, so the ruled 66 stays ruled rather than being quietly retuned.
- That probe also added two rhythm owners, under a ratchet whose own policy says ceilings may only decrease. Tagging spends the residual and raising the cap is the one move the policy forbids, so the probe now applies its stylesheet and margins through the design system, which is where that ownership is supposed to live.
- A third rhythm pin, in a file no leg touched, still named the shared keys the transcript had stopped borrowing. Amended by declaration at three sites.

Every one was proven by deliberate break, and every file restored byte-identical.

## Two rulings need your word

Both are the same shape, and it is the shape I want: a leg measured the instruction against the code before applying it, found applying it literally would do harm, shipped the honest half, and said so. Neither is a leg falling short.

**R3-B asked for the quiet voice in caps, and the leg refused with evidence.** R3-B reads "quiet = caps + tracking in sans 500 at body size". Measured against the code, the caption role is handed whole sentences at about twenty call sites, including consent copy in the connection dialog and the project-rules explanation. Upper-casing a paragraph is the opposite of the readability the leg exists for.

So the mechanism ships wired and tested and the set ships empty, saying so in the code. It is unblocked either by splitting the caption role into a metadata chip and explanatory prose, or by your ruling. Adding one word to the set is then the whole change.

**The measurement band cannot hold at the narrowest dock.** The brief asked for four characters-per-line corners all inside 45 to 75. At a 340 pixel dock the transcript column is the dock, and the probe measures 7.7 pixels per character, so 45 characters would need 346 pixels. More than the dock is wide, and 572 pixels at the larger text size.

The probe ships sound: it measures rendered text lines, reds at 90, and reports both narrow corners as pane-limited by name instead of pretending they pass. The two wide corners already sit inside the band. What needs your word is the band itself: floor it by dock width, drop the lower bound for a pane-limited column, or change the panel rather than the band. All three are written up in the rulings file.

## Rulings that shaped this release

Recorded in `harness/notes/bp9/RULINGS.md`. Joe ruled that airy is a specification rather than a binding constraint, and that the Doctor button's yellow goes, both ingested into `harness/state/resolved.json` against the roster and its hash. At cut time he pre-approved the merge and BP10's presence on master.

## Not in this release

{{NOT_LANDED}}

**The other palette still ships dead-end literals.** `CommandPaletteWidget` sends `entry.command` verbatim, and its apex and vex entries carry `/apex build <name>` and `/vex help <fn>` with no panel handler -- the same dead-end class the Commands list just lost. Out of the brief's scope, logged rather than hidden.

**BP10's harvest wave is only part-way in.** Its scaffold landed on master during this cut: the vendored `fxhoudinimcp` guide tree (MIT, LICENSE and NOTICE hashes retained), three shadow-first Jev guard stubs, an ADR, and CI wiring for `harness/jev/tests`. Its bench, corpus, guides and crux legs are **not** in this release. The scaffold's own receipt is green and its 55 tests pass, but it had never run CI before this tag.
