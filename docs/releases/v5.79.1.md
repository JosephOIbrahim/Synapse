# v5.79.1 -- the transcript stopped shouting

**Product change.** 8 files, +99/-20, all of it panel code (`python scripts/product_surface.py --diff v5.79.0 HEAD`).

**No new installer in this release.** The `SYNAPSE-5.75.2-Setup.exe` the README links is the last built installer and does **not** carry these changes.

## What went wrong in v5.79.0

The chat transcript rendered **every message in capitals at a semi-bold weight**. Not a styling choice, a defect: the speaker-label pass selected the whole text block and merged its label font across it, and the speaker label, the timestamp and the message body all live in one block. Measured on the shipped build, six of six text fragments came back uppercase.

Joe found it in the live panel: *"the chat text in SYNAPSE is all caps and tightly spaced. That makes it hard for neurodivergent users to read."*

**No test had ever asserted what a chat message looks like once rendered.** That absence is the whole reason it shipped. The HTML the formatter produced was correct; the defect lived in a Qt format merge downstream of it, where nothing was looking.

## What changed

**Sentence case.** The format now reaches the speaker-label run only, which is all it was ever for, and the uppercase transform is gone. This also settles the question the type leg escalated rather than guess at: the "quiet voice takes caps" rule was written for tiny chips, and a transcript is not a chip.

**Un-bolded.** The same scoping fix. With the merge confined to the label, body text keeps the formatter's regular weight instead of inheriting the label's 500.

**Line spacing doubled, onto the accessibility minimum.** The added leading goes from 0.75pt to 1.5pt. Measured at a 12px body: the line-to-line step was 17.00px, a ratio of 1.42 times the font size, **under** the 1.5 that WCAG 1.4.12 asks of body text. It is 18px and exactly 1.50 now. The doubling and the standard turned out to be the same number.

**Space between turns doubled**, 24px to 48px, and between messages from one speaker, 8px to 16px, both still on the spacing grid. Only the transcript's own rhythm keys moved, so cards, parameter rows and the rail did not move with the chat.

**The reading column is 10% wider**, 462px to 511px at a wide dock.

**Stray `**` markers are gone.** `**/stage/lookdev**` printed literal asterisks because the node path between the markers is parsed into a chip first, so neither `**` ever met its partner. The stranded markers are removed rather than promoted to bold: the chip's own colour already carries the emphasis, and the ask was to un-bold.

**The model is told to write readably.** Sentence case, no em dashes, short paragraphs, a list when naming more than two things. The chat text is written by the model, so that is where the instruction has to live.

## The band moved, and the caps fix is why it mattered

The reading column had been calibrated against **capitals**, which are wider, so it under-filled. In sentence case the same measurement reads very differently:

| dock | before | after |
|---|---|---|
| 340px, small text | 44.4 cpl, unreachable | **53.7 cpl, in band** |
| 340px, large text | 26.9 cpl, unreachable | 33.7 cpl, still unreachable |
| 1100px, small text | 59.2 cpl | 84.2 cpl |
| 1100px, large text | 60.5 cpl | 84.2 cpl |

The narrow dock, which the brief's 45-character floor could never reach, now sits inside the band. The wide dock went the other way, because the 10% widening and the narrower glyphs compound. Ruled: the band's ceiling moves from 75 to 85, and the hard red stays at 90. The one corner still out of band is arithmetic, not a defect, and the probe reports it as pane-limited by name rather than pretending.

## Two bugs introduced while fixing this, both caught before shipping

- A lazy import added to the design system ran while the panel's websocket thread held the import lock, and the seat suite died with a Windows access violation. The module it wanted imports only tokens, so there was no cycle to avoid; it is a module-level import now.
- The new line-height test read Qt's text layout and segfaulted once other tests had walked the document. It computes from the block format and font metrics instead: same number, no crash.

Both are named here because a release that hides the mistakes made inside it is not worth more than one that never made them.

## Pinned

`tests/panel/test_transcript_readability.py` asserts the **rendered document**, not the source, because that is where the defect lived: body never uppercase, body never heavier than regular, the label still gets its own weight, line height at or above 1.5, and the gaps doubled while the shared keys held. Four of the five go red under a deliberate break of the three changes, with the files restored byte-identical.

The two leading pins in `tests/panel/test_chat_leading.py` are amended by declaration, carrying the measurement and the reason rather than a new number alone.
