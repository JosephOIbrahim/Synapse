# v5.74.0 - how it was cut

No merge train. The working tree carried the whole release: the README rebuild, the receipt that
guards it, and the memory-seam test file. The standard ritual on top.

## The cut started by finishing the previous one

v5.73.0 was published, marked Latest, and carried **zero assets**. The README download button on
the public repository returned 404. All four assets existed on the build machine, qualified
19/19, and had done since the night before. What never ran was the whole release tail: the last
invocation in that cut's log is `['build', 'qual', 'suites', 'compose']`, and `commit`, `tag`,
`push`, `publish` and `verify` have no line in it. Every invocation logs its step list before it
runs anything, so the absence IS the record rather than an inference. Four of those five were
done by hand the next day. Publish was done by nobody, and nothing noticed.

Before uploading them, three provenance fields were corrected (`repair_assets.py` in the v5.73.0
notes directory):

- `source_revision` and `ci.headSha` named `85c8fe29`, the pre-bump commit. The composer stamps
  those from `HEAD` at compose time, and that cut never ran its `tag` step - which is where the
  second compose pass lives. The known lesson, hit anyway, because the step that carries the fix
  is the one that was skipped.
- `product_change_since_v5.70.0` named three different baselines at once: the key said v5.70.0,
  the `check` string said v5.70.0, and the command actually run said v5.70.1. The real
  predecessor was v5.72.0.
- That block's note claimed "only python/synapse/__init__.py, the version string" while its own
  `result` field listed 56 files. A note contradicted by the data printed beside it.

The correction rests on evidence, not on assertion: `repair_assets.py` re-proves, before it will
write anything, that every non-`_vendor` file under `python/synapse/` in the shipped payload is
byte-identical to the same file at the tag. 415 files, 0 differences. `_vendor/` is excluded
because the builder vendors it at build time; `RELEASE_CARD.md` lists it as not a surface.

Then: upload, all four assets 200, and the served installer re-downloaded and hashed against the
qualified hash - `c86c97d0...`, match.

## What this cut has that the last one did not

1. **The composer's baselines are derived from one `PREV`,** so the key, the `check` string and
   the command cannot name three different releases again.
2. **The product-delta note is computed from the diff** instead of asserted over it. If the delta
   is the version string alone, the note says so; if it is not, the note lists what changed. It
   can no longer contradict its own result.
3. **The seat baseline is the six reds v5.73.0 measured,** not the five its composer listed. That
   one-short list is why the v5.73.0 report carried `PASS_WITH_NEW_SEAT_RED` over a red that had
   been present all along. The release note beside it said six. The note was right.
4. **The README receipt's verdict is parsed from its log,** not retyped. The first draft of the
   public note carried the node count as a literal - measured once, then maintained by hand,
   which is the failure Law 2 names.
5. **The render stopped being an UNKNOWN.** Every previous cut shipped the diagram colours as
   declared-but-unrendered, because the receipt invokes no browser and nothing else did either.
   This cut rendered all three blocks in a real browser on both themes and read the computed
   fill and ink back off the painted SVG. The probe POSTs its own result to a local server that
   writes the JSON (`render_probe_server.py` to `render-probe-5.74.0.json`), so the chain is
   browser to POST to file to composer, with no hand in it.

   That was not fastidiousness. Two bugs turned up in the probe itself before it produced a
   single number, which is the usual rate for instrument code. Its first run reported a FALSE
   MISMATCH, because it counted a zero-size placeholder rect that mermaid emits per node and
   that paints nothing - read off a screen, that becomes a defect report about a defect that
   does not exist. And before that, a generator bug: a newline escape inside a JS string
   literal was interpreted by PYTHON as a real newline, which is a JavaScript syntax error
   that killed the entire script block. The page sat on "running..." and reported nothing.
   A silent instrument reads exactly like a slow one.

6. **The stock-suite gate was wider than the thing it meant to catch.** Every cut through
   v5.73.0 gated on `if "failed" in stock` - a substring test against pytest's summary line.
   v5.74.0 is the first release to ship xfails, and `"xfailed"` CONTAINS `"failed"`, so that
   gate would have stopped this cut on its own five EXPECTED xfails and called them failures.
   It survived four releases because no input had ever exercised the overlap.

   The fix that outlives the bug is not the regex. It is that `gates` is now a separate step
   from `suites`: judgement is cheap and was wrong, measurement is expensive and was right, and
   re-judging must not mean re-running a seven-minute suite - or the pressure is always to skip
   the gate rather than pay for the suite again. The bug was caught while the suites were
   mid-flight, with the running process already holding the broken copy in memory, which is
   exactly the situation that separation was needed for.

7. **Two more gates were the wrong width, and a standing marshal found both.** An agent
   running outside the cut, whose only job is to check effects rather than intentions, swept
   for the shape the xfail bug has: a test wider or narrower than the thing it means to catch.

   **Wide, and vacuous:** the claim gate compared `git diff PREV HEAD -- python installer`.
   compose runs BEFORE the release commit, and the `v5.73.0` tag sits *on* HEAD — it was
   created at the asset-repair commit that followed the release commit, so `git log
   v5.73.0..HEAD` is empty. The gate was asking what changed between the tag and the tag,
   getting nothing, finding nothing unexpected in nothing, and logging that it had verified
   the documentation-only claim. It had abstained. Printing PASS for an abstention is the
   more dangerous of the two failures, because a red gate gets read and a green one does not.
   Fixed by dropping the second ref — PREV against the working tree is the question actually
   being asked, and it stays correct on the post-tag pass where the tree is clean — plus a
   hard refusal on an empty delta, since every release bumps the version string.

   **Narrow:** the seat gate was `if nfail != SEAT_KNOWN_REDS` — a count. Fix one known red,
   acquire one genuine new one, and the total is unchanged: the gate passes and the regression
   ships. The composer computed the identity difference all along but only *recorded* it; it
   never raised. Nothing between the measurement and the tag was checking identity. The
   baseline is now a list of six test ids with the count DERIVED from it, and the gate stops
   on a red that is not in the list, on a baseline red that has started passing, and on a
   summary that disagrees with its own FAILED lines. Proven against a synthetic swap that a
   count-only gate accepts.

## Measured

- Stock suite: 9588 passed, 433 skipped, 5 xfailed, 625 warnings in 456.85s (0:07:36)
- Seat suite (hython 22.0.400, `SYNAPSE_HYTHON` pinned, alone): 6 failed, 201 passed, 43 warnings in 72.68s (0:01:12)
- Installer unit checks: 37 passed, 1 warning in 7.76s
- Installer qualification: 19 of 19 PASS, exit 0
- README receipt (source resolution): PASS - 21 nodes across 3 block(s), all resolved by source; both negative controls rejected
- Diagram render (real browser, both themes): PASS - 6/6 renders parsed, 0 error boxes, 42/42 node observations at rgb(51, 51, 51) with rgb(255, 255, 255) ink (mermaid 11.4.1 (cdn.jsdelivr.net), dark + default themes)
- Payload vs source: MATCH - 415 non-_vendor files under python/synapse/ byte-identical to the source, read out of payload.zip itself; installer/ has 0 members in the payload, so it has no subject to match
- Payload: `9efc739d2e12e6e53ff634141373a1ed199e638673759c3405c7eaca344b0ad4` (`5.74.0-3d3146d2d5efeadc`), built at `236fd2e546e3`
- Setup: `383e74b78b33200fe752e92928652e008a282bfb06fbe17423862863ee7944eb`
- CI on the tagged commit: PENDING_AT_PUBLICATION

The seat suite and the stock suite share a log file and must not run at the same time; they ran
alone, in that order.

## The count that matters

The two defects this cut fixed in its own tooling were both **silent-success** defects: a field
that named the wrong baseline and a list that was one member short. Neither raised. Neither
failed a gate. Both produced a report that read as evidence.

The v5.73.0 assets sat qualified on disk for a day while the public download 404'd, and nothing
in the ritual noticed - because every gate the ritual owns had already passed. The gap was
between the last gate and the reader. That is the shape worth watching: not a check that fails,
but a step with no check after it.
