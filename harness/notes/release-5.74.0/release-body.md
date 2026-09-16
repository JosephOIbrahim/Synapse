Documentation and tests only. The product is unchanged: the single file that differs under
`python/` since v5.73.0 is the version string. The tool registry holds 137.

## What a reader gets

- **The three README diagrams read on either GitHub theme.** They were drawn with unstyled
  nodes, which inherit the host theme - so the ink and the fill were whatever the visitor's
  GitHub happened to be set to, and on one of the two settings they were hard to read. Each
  node now declares a dark grey fill, white text, and a grey outline that keeps the shape
  visible against a dark page. These are the three pictures carrying the parts of SYNAPSE
  that are easiest to get wrong: what one Ctrl+Z takes back, what the three stop controls
  each reach, and why the audited path and the live path are drawn apart.
- **The README is rebuilt to this project's own ADHD convention.** Short blocks, one idea
  each, bold only where it anchors. Nothing was removed to make it shorter - the length moved
  into whitespace. `CLAUDE.md` has required this of the README for some time; the file had
  drifted into prose walls anyway.

## For the repository

**The page now has a receipt, and the receipt can fail.**

`harness/notes/readme_check.py` checks, in one command, that every diagram node resolves to
the declared fill and ink, that every release-tagged version string on the page matches
`VERSION`, and that the tool count matches the module the page itself names as its producer -
read by importing that module, because importing it *is* reading the producer.

The previous version of that script had exactly one failure channel, and none of its numbers
were on it. Its exit code came from a quote-and-bracket balance check on each diagram - an
unbalanced block did exit 1 - and nothing else reached it. Everything under its "ASSERTED vs
ACTUAL" heading printed and stopped there: the version string was never compared against
anything, and a count was checked against a literal baked into the script that the README does
not claim. So the half that looked like verification could not fail, which is worse than a
check that fails loudly, because it spends trust a real one would have earned.

So the receipt carries two negative controls - a diagram with no styling at all, and one
styled white-on-white - and it fails if the resolver calls either of them good. An instrument
that has not been shown to disagree is not evidence.

**What the receipt does not prove is stated on the receipt itself.** It resolves the *source*.
It invokes no browser, so on its own it cannot prove anything about how the diagrams actually
paint. Two styling limits are stated rather than omitted: `classDef` styles nodes, so edge
lines and edge labels deliberately inherit the host theme (pinning them white would make them
invisible on a light background), and the two subgraph containers are deliberately left
unstyled so their titles stay legible either way.

**So the render was measured separately, before this was tagged.** All three diagrams were
rendered in a real browser, in both the dark and the light theme, with every node's computed
fill and text colour read back off the painted SVG. The result is in the table below. The
subgraph containers came back carrying the host theme in both — which is the deliberate choice
above, confirmed rather than assumed.

That probe records itself: the page POSTs its own measurement to a small local server that
writes the JSON, so no number passes through anyone's hands on the way to this page. It earned
that design immediately — its first run reported a false mismatch, because it counted a
zero-size placeholder rect that mermaid emits per node and that paints nothing. A person
reading that off a screen would have written down a defect that does not exist.

**Eight tests now guard the memory seam** (`tests/test_memory_seam_defects.py`). They come from
a review whose every "fails today" verdict was a *prediction* - the review ran no tests, by its
own account: pytest was forbidden on every leg and no live bridge was present. It did run static
`grep` and `git` checks and quotes their output. A probe
pass then executed seven of them and refuted two. This file is the survivors, converted from
prose into claims that execute:

- **Four are strict xfails.** They fail at HEAD today, and they turn the suite red the moment
  someone fixes the underlying defect without deleting the marker. That is the point: a defect
  that can be fixed silently is a defect that will regress. Each was run and observed failing
  before it was committed.
- **One is a thread race**, marked non-strict, because a probabilistic test cannot honestly be
  made strict.
- **Three are permanent green guards.** They pin facts that are true today and that two
  independent agents disagreed about - the gate-policy truth table including its documented
  empty-set vacuity, that `fetch_raw_memories` is an exact set intersection with no distance
  path, and that the distance threshold is emitted but never compared. These are the reason the
  file still earns its place after every defect above is fixed.

**Pinned is not fixed.** None of the four defects is repaired in this release.

## Verification scope

Measured on this build, alone, in this order.

| Check | Result |
|---|---|
| Installer qualification | 19 of 19 PASS, exit 0 |
| Stock suite (Windows, Python 3.14) | 9588 passed, 433 skipped, 5 xfailed, 625 warnings in 456.85s (0:07:36) |
| Panel seat suite (Houdini 22.0.400, offscreen Qt) | 6 failed, 201 passed, 43 warnings in 72.68s (0:01:12) |
| Installer unit checks | 37 passed, 1 warning in 7.76s |
| README receipt (source resolution) | PASS - 21 nodes across 3 block(s), all resolved by source; both negative controls rejected |
| Diagram render (real browser, dark and light) | PASS - 6/6 renders parsed, 0 error boxes, 42/42 node observations at rgb(51, 51, 51) with rgb(255, 255, 255) ink (mermaid 11.4.1 (cdn.jsdelivr.net), dark + default themes) |
| Installer payload vs the source it was built from | MATCH - 415 non-_vendor files under python/synapse/ byte-identical to the source, read out of payload.zip itself; installer/ has 0 members in the payload, so it has no subject to match |

The stock summary reports no failure *count* - no `N failed`, no errors. It does contain the
token `5 xfailed`, and that token contains the letters `failed`: saying the summary "carries no
failed" would repeat the exact bug described below. The five xfails are the memory-seam tests
above, and xfail is the marker doing its job.

Payload `9efc739d2e12e6e53ff634141373a1ed199e638673759c3405c7eaca344b0ad4`, built from the bumped working tree at `236fd2e546e3`. The
TestSetup that was qualified carries the same payload hash as the published Setup, which is
what binds the qualification to the file you download.

## Update

`SYNAPSE-5.74.0-Setup.exe` upgrades in place and preserves projects, memory, credentials and
custom files - that path is one of the qualification checks.

- The installer is **unsigned**; verify it against `SHA256SUMS.txt`.
- **There is no reason to update for this release if 5.73.0 is working for you.** Nothing that
  runs changed. It is offered so the version on disk matches the page.
- Running from source? Pull `v5.74.0`. A live Houdini session holds the modules it already
  loaded until the panel is reloaded or Houdini restarts.

## Still unfinished

- **The diagram colours are proven rendered by mermaid, not by GitHub's mermaid.** The
  browser probe above settles that the declared `classDef` survives into the painted SVG on
  both themes. It does not settle GitHub, which pins its own mermaid version and its own theme
  and renders server-side. If GitHub changes how it handles `classDef`, both the receipt and
  the probe will still pass and neither will have caught it. The honest state is: proven in a
  browser, unproven on the one page that matters.
- **Four memory-seam defects are pinned, not fixed** - the recall receipt cannot distinguish a
  checked memory from an unchecked one, a bare string is exploded into a token set on two
  ungated paths, and a repeated settlement deposit does not carry a stable id. Two of these
  self-qualify as latent hazards rather than live production failures, and the tests say so
  where the probe said so.
- **The v5.73.0 release shipped with no assets attached** and its download link returned 404
  until this cut. The four assets existed, qualified 19/19, on the build machine since the night
  before. What never ran was the whole release tail: that cut's last invocation was
  `['build', 'qual', 'suites', 'compose']`, so `commit`, `tag`, `push`, `publish` and `verify`
  have no line in its log. Four of those five were done by hand the next day; the fifth,
  publish, was done by nobody. They are attached now, and their provenance was corrected first: three fields
  named the pre-bump commit, and a fourth carried a baseline copied forward from v5.70.0 with a
  note its own result contradicted. The gap is recorded in
  `harness/notes/release-5.73.0/repair_assets.py`, which re-proves the payload matches the tag
  before it will write anything.
- **Three published releases claim a seat regression that did not happen, and this release
  does not rewrite them.** The panel seat suite gained a genuine sixth red at v5.71.0
  (`test_doctor_button.py::test_transport_discovers_only_the_running_owner_and_tracks_reconnection`).
  The composer's list of known reds was never raised from five to six, and it computes
  "new" as *measured minus known* — so the same test was re-reported as a new regression at
  **v5.72.0** (one release old) and again at **v5.73.0** (two releases old). All three assets
  carry `status: PASS_WITH_NEW_SEAT_RED` and `installed_houdini.status: NEW_RED` over it, and
  all three say "the other three are named and undiagnosed" when the count is four. A red
  that is new in three consecutive releases is by construction not new.

  The error over-claims a regression rather than hiding one, which is the better direction to
  fail in, but it is still a published artifact that is wrong about its own product. The list
  is corrected to six here, so v5.74.0 does not repeat it. The published assets are left as
  they were found: they are the record of what those releases actually said, and this note is
  the correction. Verified by fetching each asset from its public URL, not from a local copy.
- The three readability findings from v5.73.0 are unchanged: two named greys are nearly one
  grey, the panel renders far smaller than its host, and the transcript reads 28.6 characters
  per line. All three await a design ruling.
- Six panel seat tests remain red; none is new — and this time that is checked against a
  baseline of six rather than five.

Full notes: [`docs/releases/v5.74.0.md`](https://github.com/JosephOIbrahim/Synapse/blob/v5.74.0/docs/releases/v5.74.0.md)
