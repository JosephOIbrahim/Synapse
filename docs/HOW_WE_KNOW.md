# How we know

**Most of what this project found was wrong with its own instruments, not its code.**

That sentence is the method, the finding, and the reason this document exists.

---

## The finding

Six days of auditing SYNAPSE produced a different result than expected. The code was mostly less broken than the things measuring it.

**Five Solaris tools** passed a test suite that asserted against a mock. They were unreachable — no code path could invoke them — and every test was green.

**A coverage metric** read 100%. It was 100% by construction: it counted what it had already decided to count.

**A ratchet floor** sat 599 tests stale, so the guard against regression had been passing anything for months.

**The shipping test number could not be measured at all.** The runner carried `--ignore` flags for exactly the three files that failed to collect. The instrument was built not to see the fault.

**A knowledge corpus** was five years old and nobody knew, because the code that selected it read a variable nothing ever set.

None of those were product bugs. Every one was **an instrument reporting healthy while measuring nothing.**

---

## The method

Work is dispatched as **legs**. A leg has a written brief, an explicit oracle, and a fence.

**The brief states what is already known** so the leg does not re-derive it, and **what is out of scope** so it does not wander. Briefs are files in the repository, not instructions in a chat — a leg whose brief exists only in prose does not exist.

**The oracle is what must be true when it finishes.** Not "make it better" — a list of checkable conditions.

**The fence is structural.** A read-only leg runs under a permission profile that cannot write product code. Early on, "read-only" was an instruction in the brief; six violations were observed. It is now a deny list.

Every leg writes a **receipt**: what it did, what it found, what it could not establish, and what needs a human decision. A finding without a `file:line` anchor is not a finding.

---

## The rules that came out of it

These were not designed. Each one exists because something broke.

**A check must be able to fail.** Demonstrate it failing before trusting it to pass. A check written after the defect is fixed has never seen the thing it guards against.

**No number without a producer path.** A figure with no command that reproduces it is a recollection. This rule has been broken by the author three times and caught by others each time.

**`ABSENT` requires a positive control on the same class.** Not finding something proves you looked in one place. One probe reported five symbols absent; all five were the probe asking the wrong class.

**A health check must call the same function the product calls.** A check on a neighbouring value reports green about something nobody uses.

**Probes beat memory; observed beats documented beats assumed.** Every `hou.*` symbol is confirmed against the running build before code is written against it.

**A control only rules out what it actually exercises.** A fast health-check response was read as proving the marshal worked. The health check does not use the marshal.

---

## What it caught in the author

This is the part that makes the rest credible.

The rulings document records **125 decisions**. Roughly a dozen correct earlier decisions by the same author. Several were caught not by re-reading, but by an agent, a control, or a direct question.

**A ruling built on a design brief** that described intent at the time of writing. The brief had aged into a claim about the present with nobody editing it. The prediction it produced was inverted.

**A vendor ask, nearly sent**, claiming an API did not exist. A full sweep of the vendor's own shipped reference found a command that does exactly what the ask said was impossible.

**A migration leg, dispatched and killed before it wrote anything.** It would have relabelled 108 accurate documentation references as stale — making a corpus lie about its own provenance. The labels were right; the reading of them was wrong.

**An audit of the rulings themselves**, run by an agent given four known-wrong decisions without being told which. It caught all four, found two more nobody planted, and returned **28% sound, 40% unenforced.** Forty percent of a document arguing that structure beats intention was intention.

---

## The evidence

Verifiable in the repository, not asserted here.

**A self-improvement loop that had never run.** The routing package was absent from the live process's `sys.modules`. Its reward signal was a hardcoded constant. Its output was read by nothing. **And 4,357 "Epoch complete" lines sat in the operator's log directory** — every one written by unit tests. Anyone reading the log would have concluded it worked.

**A competitor claim, refuted by probe.** The positioning document asserted that Houdini 22 ships an AI assistant. A scout established that 22.0.368 registers no LLM, agent, assistant or MCP surface at all. The claim came from trade coverage the vendor's own pages do not support.

**A central marketing claim, refuted by measurement.** "Cost stays flat, even on huge scenes" was measured across a 13 → 25,850 node ladder: **443 → 113,411 tokens.** Not flat. The advantage is real but it comes from reading less, not encoding better — and the honest replacement claim states the coverage tradeoff alongside it.

**A crash on the vendor's own scene.** A shipped tool segfaulted the interpreter on `karma_user_guide.hip`, the largest scene SideFX ships. Found by a benchmark that was measuring something else, fixed, and verified on the same file.

---

## What this does not claim

It does not claim SYNAPSE is correct. The README lists what does not work, and that list is long and specific.

It does not claim the method is complete. Two formatting defects shipped this week that no headless test could reach — both were found in ten minutes of using the product, and both lived in *where the eye lands* rather than in what a function returns.

**Verified and rehearsed are different words.** You need both.

---

## Why a studio should care

Every tool vendor says their software works.

**This one can show you what it got wrong, when, and how it found out** — with a ruling number, a receipt, and a command you can run yourself.

The list of known limitations in the README is not an apology. It is the output of the same process that produced everything else, and it is the part you should read first.
