# Release preparation: v5.94.2

Publish one change on top of v5.94.1 (tag `v5.94.1` on `c9aec9d6`): the page the panel's Help opens. Joe's words,
2026-10-05, in order: after the v5.94.1 release and the houseclean, "The help docs severely need updating on
synapse to work with the current system. Using adhd friendly formatting and pentagram design studio style
aesthetic in the same vein as the synapse panel."; on the first preview, "20% more space and adhd friendlty"; on
the second preview, sent at 1:14pm, "looks good"; then "can you commit, git push, git release".

| File | What changed |
|---|---|
| `docs/help/index.html` | Rewritten from the panel's source. 42,485 bytes, blob `9c10ef72`. The page it replaces was 12,586 bytes and carried the banner v5.42.0. |

Everything else in the commit is version strings and documents.

## Evidence

- **The old page.** `git log -1 -- docs/help/index.html` on `c9aec9d6`: `19671554`, 2026-08-03, "docs: help doc
  restructured SideFX-style". Its only version string is v5.42.0. It contains none of: Doctor, Connect models,
  Updates, Saved networks, Identify, Spatial, Render, REVERT, World Labs, Emergency, Ollama.
- **Where the page was written, and how it came across.** It was written and checked in Claude's cloud workspace,
  against a clone of the public repository at `c9aec9d6`, because the browser tooling is there. It came to this
  machine as base64 of gzip, 215 lines in five writes, and `.token-saver/help-20261005/unpack.py` wrote
  `index.html` only after the sha256 matched (`531e20d1...`). The staged blob is `9c10ef72...`, the id
  `git hash-object` gave in the workspace, so the committed bytes are the checked bytes.
- **Names.** `help_receipt.py` in the workspace: 96 names taken from the page's `<b>`, `.says`, `<dt>`, map links
  and `<code>`; 91 are quoted string literals in `python/synapse/panel/**/*.py`; "Synapse" and "New Pane Tab ->
  Synapse" were found in the README; "Model name", "Status line" and the lightning glyph are map labels; missing,
  none. The panel source is the same on this branch as on `c9aec9d6`. `houdini/toolbar/synapse.shelf` labels the
  shelf and its first tool "Synapse".
- **Facts read in the source for the second pass.** `_author_display_label` returns "Choose a model" when no
  model is chosen. `_fit_panel_chrome` hides the Doctor button when the status row does not fit, and
  `_build_overflow_menu` then adds Doctor, and Saved networks and Updates in a narrow dock. The overflow menu has
  three separators, so four groups. `health_strip.build_cells` gives four cells: connection, memory, project,
  job. `handlers_render._handle_emergency_halt` sweeps `/tasks`, `/obj`, `/stage` and `/out`.
- **Behaviour.** Chromium 141.0.7390.37, headless, puppeteer, on the committed bytes: 17 of 17 checks pass
  (`interact2.js`). The check for find-in-page dispatches `beforematch` itself; no real find was driven.
- **Layout.** `layout_check.js` at 1360, 1153, 1152, 900, 760 and 420 pixels: no sideways scroll, no clipped map
  label, nothing past the right edge. 57 side-by-side rows, 0 with the name and the first answer line on
  different baselines. Print media: all five sections display.
- **Links.** `linkcheck_help.py` on the release tree: 12 links, 9 file-backed, 0 bad; the four headings exist.
- **Space, measured.** At 1360 pixels wide the first preview's words take 17% more height in the second layout
  (14,591 to 17,063 pixels). With the text pass the page is 19,225 pixels, and 2,735 words against 2,638.
- **The suite.** The CI command on the release branch's working tree, on top of `c9aec9d6`: Windows, Python
  3.14.2, home folder on scratch, no `SYNAPSE_*` variables (`.token-saver/help-20261005/full.log`). 10,923
  passed, 430 skipped, 186 deselected, 5 xfailed, 0 failed, in 8 minutes 29 seconds. Those are the counts of
  v5.94.1's run on `377e5cca`. The run came before the notes were final and before this note and the Jev ledger
  row existed. With those in place, the README receipt, version conformance and tool-count tests and
  `harness/jev/tests` were run again on 3.14 and passed.
- **Python 3.11.** 3.11.15 on the same tree, before and after those files were added: the eight files of
  `py311.ps1` (README receipt, version conformance, tool count, egress docs and four that v5.94.1 touched), 124
  passed, 40 skipped; CI step 2, `harness/jev/tests`, 88 passed; CI step 3, 14 passed and 27 skipped without the
  engine, and 41 passed with it on the path.

## Decisions

- **Released on Joe's word, before the pin.** The plan this morning kept master on v5.94.1 until his run-through
  and the pin. His instruction replaces that. The run-through and the pin are now on v5.94.2, after a relaunch.
  The running code differs from v5.94.1 by the two version strings in `python/synapse/__init__.py`.
- **v5.94.2, a patch.** One document and version strings.
- **The help page only.** `houseclean/20261005` stays unmerged until after the take, as Jev read it this morning.
  It was cut from `c9aec9d6`, so it no longer fast-forwards onto master; it needs a rebase first.
- **The README's recipe pointer stays on v5.94.1.** The sentence under the verified-recipe section says the
  release notes list what was seen in Houdini, and those are v5.94.1's. The README receipt requires three
  current-release pointers to name VERSION, and that pointer is not one of them.
- **The four older help pages are left.** Correcting or removing them is Joe's call.
- **No test for the page.** A test that reads the panel source is a code change, and it waits for after the take.
- **Not opened in Houdini.** Claude does not take the screen while Joe is at the machine. His run-through covers
  it with one click on Help.
- **JEV.** For the notes, 29 claims were checked in one request
  (`harness/jev/ledger/v5.94.2.release.notes.jsonl`): 21 came back supported and 8 partial, none unsupported.
  Each partial went to a direct read. Reworded after the request: "eleven symptoms" became "eleven situations";
  the font and network sentence was split, so "no network request" stands as a measurement; the name check now
  gives its counts by kind of markup, says two matches are through a format string and lists what it left out;
  the font fallback names the stylesheet's next choices instead of "a system font"; the name-check limit no
  longer says a renamed control fails no test, only that nothing reads the page; "the panel does not open them"
  became "the panel's source refers to none of them"; and the Setup sentence now rests on the v5.86.0 tree
  holding the same older page (blob `6da91e8d` at both tags). Left as written after the read: the Emergency halt
  bullet (partial at 0.49), whose three facts are each in the source. The weakest supported claim was the old
  page's date and banner (0.47): `git log` gives 2026-08-03, and the file's only version string is v5.42.0. One
  claim was added to the check before the request: all five doors in the bar were clicked, where the first run
  of the browser checks had clicked two.

## Not in this release

- **The page opened from the panel in Houdini.**
- **A test that keeps the page's names honest,** and the page as a `sync_version.py` surface.
- **The four older pages in `docs/help/`.**
- **Two tooltips:** the hidden help button's, and Emergency halt's.
- **The houseclean branch.**
- **Joe's own run-through, and the pin.** After this release.
- **A Windows Setup.**
