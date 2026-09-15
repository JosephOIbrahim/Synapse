# Canvas second look - 2026-09-15

An adversarial second look at the three canvas artboards (`canvas/Main.dc.html`,
`canvas/Refined.dc.html`, `canvas/HostNative.dc.html`), checking them against the **as-built panel**
and against **what the crit room actually conceded** in `CRIT.md` / `MAP.json`.

Two kinds of finding are mixed below and they are NOT handled the same way:

- **Truth bug** - the canvas misrepresents the panel as it actually ships. Always worth fixing.
- **Scope bug** - the canvas shows a change the room did *not* concede, or one that is still
  ranked as Joe's ruling. Fixing these is a decision, not a correction.

> **Provenance.** Recovered from the reviewing agent's own transcript
> (`subagents/agent-acanvas-second-look-*.jsonl`) by the parent session. The agent was asked to write
> this file itself but hit its model usage limit before it could; nothing here was re-written or
> summarised by the parent. The published canvas was NOT updated - the live artifact carries Joe's
> own later edits, so any republish must read + extract the live page first and merge onto that.

---

Directory: `C:/Users/User/SYNAPSE/harness/design_review/2026-09-15/canvas/` (CRIT/MAP = parent dir)

**BLOCKER**

1. Main.dc.html:25 · Refined.dc.html:28 · HostNative.dc.html:22 — MarkDot drawn as a #555555 disc/ring. That is SLATE from the STATUS[disconnected] slot the room proved has no visible consumer (CRIT.md:89, :100 — "the lens's STATUS-colour-table-worn-by-the-MarkDot was wrong"). As built: one colour WARM #FF7759, open 300° arc at rest (CRIT.md:15, :47, :100), bucket 0 of the boot count. Fix (Main, Refined): `<svg width="16" height="16" viewBox="0 0 16 16"><path d="M8 1.5 A6.5 6.5 0 1 1 2.37 4.75" fill="none" stroke="#FF7759" stroke-width="1.5" stroke-linecap="round"></path></svg>`. HostNative may stay grey only with the J1 sticky (item 13).

2. Main.dc.html:44 · Refined.dc.html:46 · HostNative.dc.html:39 — context ribbon drawn empty. At boot it holds `_ctx_label ''` (stretch) + Pill "CHAT" active (TEXT_BRIGHT #DEDEDE, 2px SIGNAL #8FB3D9 underline) + Pill "TOKEN" (TEXT_TERTIARY #868686, transparent underline), Space Mono 11px 0.15em = 1.65px, padding 0 0 12px 0, radius 0 (MAP.json:572-581). CRIT.md:45 counts that underline in the boot SIGNAL family; ranked #7 recolours it, so Refined cannot show #7 either. Fix: ribbon div → `display:flex; align-items:flex-end; gap:16px;` with body `<div style="flex:1;"></div><div style="font-family:'Space Mono',monospace; font-size:11px; letter-spacing:1.65px; color:#DEDEDE; padding:0 0 12px 0; border-bottom:2px solid #8FB3D9;">CHAT</div><div style="font-family:'Space Mono',monospace; font-size:11px; letter-spacing:1.65px; color:#868686; padding:0 0 12px 0; border-bottom:2px solid transparent;">TOKEN</div>`. Refined: underline `#DEDEDE` (#7). HostNative: underline `#B98620` (CRIT.md:162).

**MAJOR**

3. Main.dc.html:19 — atmosphere gradient inverted and given a mid-stop. Token: `stop:0 #2E2E2E, stop:1 #262626` = light top, dark bottom (MAP.json:96, :503). Fix: `background: linear-gradient(180deg, #2E2E2E 0%, #262626 100%);`

4. Main.dc.html:56, :65, :69 — transcript mono set in Space Mono; as built `_MONO` = Consolas (`message_formatter.py:75`, CRIT.md:27; ranked #13 is the fix), so Refined's "one mono" is invisible on the canvas. Fix (Main only): `font-family: Consolas, 'Courier New', monospace;` on both speaker labels and the node chip.

5. Main.dc.html:50 (`padding: 12px 14px`) · Refined.dc.html:52 (`padding: 12px 15px`) — invented inset. As built the only inset is Qt document margin 4 → body x 50 (CRIT.md:35); Refined's own comment (:51) claims margin 0 → 46 but pads 15 → body at 62. Fix: Main `padding: 4px;` · Refined `padding: 0;` and revert Refined:53 `text-align: left` → `center` (#10 moves khint/footer only, CRIT.md:129).

6. Main.dc.html:55-61, :64-73 · Refined.dc.html:56-71 — speaker label sits outside the ruled cell. TYPE's round-2 self-correction: label is INSIDE the ruled body cell, label and body share x (`message_formatter.py:417-418`, CRIT.md:27; MAP.json:736 is the older reading). Fix: move each `● YOU` / `● SYNAPSE` div into the text column right of the 2px rule as its first child, `margin-bottom: 3px`, so the rule spans label + body.

7. Refined.dc.html:36 (also HostNative.dc.html:30) — "Bridge" at 700 / TEXT_PRIMARY #C5C5C5. No concession touches the rail verb's weight or colour: #14 changes the word only (CRIT.md:133); weight-hierarchy was conceded for the gate card's Approve/Reject (#2, #10) and tone=hot "at the verb's own weight" (#1). Fix: `font-weight: 400; color: #A0A0A0;` and delete "verbs told apart by weight (700), not hue" from the comment at :21.

8. Refined.dc.html:66 — "● SYNAPSE" at 700, comment "so type has a turn". That is the J3 supersession TYPE dropped from the crit — "Filed, not ruled" (CRIT.md:85, :197). Fix: remove `font-weight: 700` (and the span's `font-weight: 400`); comment → "J3's marks unchanged (ruled)".

9. Refined.dc.html:76 · canvas.json:10 — receipt tag moved 12 → 11px. The tag is the rhythm tag role 12/500 (`qss.py:422`; MAP.json:739 mislabels it "DsBadge" — the 10px DsBadge is not on this face). #1 retires 10s only; #19 moves the tag to 400|700 at 12 (CRIT.md:120, :138). Comment :74 also claims "verdict word first per C2a" — the markup (correctly) does not. Fix: `font-size: 12px; letter-spacing: 0.72px;` · canvas.json gate-c2: "Only the form moved: leaf 8/4, weight 700 (#12, #19)." · comment :74 → "tag leaf (8,4); weight 700; words unchanged (C2a/D3 rulings)".

10. Refined.dc.html:101-102 · HostNative.dc.html:76-77 — "Saved networks" / "Updates" are invented: USE flagged Recipes/Events (CRIT.md:59) but no ranked change, no concession, no replacement word exists in CRIT.md. Refined:22/:64 also drop "signed {model}" — a delete-list position (:65), not ranked (#14-#17 are the copy that rides). Fix: restore "Recipes" / "Events" in both; restore signed in Refined — and as built with a node chip it rides the chip, no standalone line (MAP.json:737), so Main.dc.html:69-70 should read `▪ /obj/geo1/box1 · signed claude-sonnet-4-6` and drop :70. Add sticky `{ "id": "copy-flagged", "x": 440, "y": 940, "w": 300, "text": "Events / Recipes / signed {model} — USE flagged as system-naming (CRIT.md:59, :65); no ranked change, no ruling. Shown as shipped." }`

11. Refined.dc.html:18 — comment says "Doctor loses its yellow … shown here as form (weight 700)"; markup (:38) correctly keeps #B98620 at 400. Fix comment: "Doctor keeps its yellow — B1-gated; 'Check' would ship yellow regardless (CRIT.md:86, :179)."

12. Crit.dc.html:75 — "Not decided here" omits two CRIT.md entries: A1/A2/A3/B2 the airy chain (CRIT.md:181) and D1 faces-stack 400px (CRIT.md:189). Fix: after B1 insert `<b>A1 / A2 / A3 / B2</b> the airy chain — #11's verb floor is derived, pending M1; A2's −13 stands until measured. ` and after D2 insert `<b>D1</b> faces-stack 400px — unassigned; #1 and #17 are D1-neutral iff page 0 drives. `

13. HostNative.dc.html:45-50 · canvas.json (no sticky) — the grey speaker rules and un-WARM mark ARE the J1/J3 supersession Direction B requires (CRIT.md:164 item 3, :195 `test_j3_speakers.py:157-160`); ruling-gated, no note. Fix: add `{ "id": "gate-j1j3", "x": 880, "y": -140, "w": 260, "text": "J1 / J3 — the grey speaker rules and the un-WARM mark in this sketch need a J1/J3 supersession (test_j3_speakers.py:157-160). Filed by no one, ruled by no one. Yours." }`

14. Main.dc.html:28, :32 vs :52-81 — one state the panel cannot be in: boot chrome ("Not connected", DsAuthor liveness=off #636363, mark disconnected) above a completed mutation, a CONIFEROUS reply and a "1 CHANGE" receipt. The bucket pin differs by state (≤3 boot / ≤4 connected, MAP.json:102). Fix, recommended: connected-after-one-turn — :32 `Ready` (STATUS connected, tokens.py:614), :28 `color: #6E8F72` (liveness=live), mark = ring + check WARM; canvas.json:3 title "As built — v5.71 tree, one turn in". Otherwise a true boot frame: delete :55-73 and :77-81.

**MINOR**

15. Main.dc.html:26 · Refined.dc.html:29 — wordmark tracking 2.24px is 0.16em at 14; live size is 15 → 2.4px (MAP.json:551, :560). Weight 600 renders as Qt Bold 700 (MAP.json:18). Fix: `letter-spacing: 2.4px;` (and `font-weight: 700` + add 700 to the fonts request if the board shows rendered weight).

16. Main.dc.html:24 · Refined.dc.html:27 · HostNative.dc.html:21 — mark→wordmark gap 5; as built it is stack gap 4 + WORDMARK_GAP 5 = 9, wordmark at x 55 (CRIT.md:35, MAP.json:551). Fix: row `gap: 4px;` + wordmark `margin-left: 5px;`.

17. Main.dc.html:22 — `margin-bottom: 8px` reproduces a QSS rule the room proved paints nothing (bare QWidget; seam 25 not 33, CRIT.md:80). Drop it, or say "token, not rendered" in the comment; Refined:25 then describes a no-op, not a change.

18. Main.dc.html:59, :69 — `line-height: 1.35` is not a token; as built there is none (native metrics + 1.0px leading, MAP.json:128). Fix: omit.

19. Refined.dc.html:87 — SEND at 700; as built `tracked_font('SEND', 11, weight=500)`, rendered weight is M7-pending, and #19 names status and tag only. Fix: `font-weight: 500;`.

20. Refined.dc.html:36, :38 — `margin: 0; min-height: 26px` applies #11, UNVERIFIED pending M1 and touching B2/A2 (CRIT.md:130, :181). Covered by the pending-m sticky; append "(#11 is applied on the Refined board — its rail height is derived)" to canvas.json:11.

21. Crit.dc.html:27 — "all priced at zero vertical cost"; #1 is CHAT 0 / Work +2–3 (CRIT.md:120, and the item's own text at :31). Fix: "— zero vertical cost on the CHAT face".

22. Crit.dc.html:58 — "five pins carried by hand"; CRIT.md:155 says two (≤3 bucket pin, gate pin); :195's five include two conditional on B1 option (2) / Direction B. Fix: "the bucket pin and the gate pin carried by hand".

23. Crit.dc.html:57 — "air from the ladder instead of hairlines"; CRIT.md:151 says ladder air at 0px; nothing replaces hairlines. Fix: "ladder air at zero vertical cost".

24. Crit.dc.html:75 · canvas.json:12 — "under the token's '26–36 safe'": 24 is below the band, i.e. outside it — that is why it is Joe's call (CRIT.md:191's "inside" is the ambiguous source). Fix: "24 sits below tokens.py:637's 26–36 safe band — outside it; Joe's call".

25. HostNative.dc.html:62 — composer border #B98620 at rest is the :focus state (CRIT.md:164 item 2); the sketch shows a focused field on a resting board. Fix: `border: 1px solid #363636;` and note "focus → #B98620". Also :55, :62, :64: Direction B says Houdini's 2px radii (CRIT.md:164 item 4) → `border-radius: 2px;`.

26. All four files :5 — `<script src="./support.js">` present and identical, but no `support.js` exists in the canvas directory (grep, 0 files). Confirm the viewer injects it or copy it in.

27. Main:10 · Refined:10 · Crit:10 — Google Fonts `<link>` is the only external reference (no images). Offline, Space Grotesk/Mono fall to Segoe UI and Main becomes visually the Host-native sketch. Prefer `@font-face` to `designsystem/fonts/*.ttf` if the viewer allows local files; otherwise note it in the Main title.

28. canvas.json:6 — Crit root declares no height; content at 640 wide estimates ~1,300px vs h 1180. If `"print": "flow"` does not auto-size, the room record (Crit.dc.html:78) clips. Fix: `"h": 1320` or verify flow.

29. Main.dc.html:102-105 — DsFooterLink is `padding 2px 0` + min-height 24 = 28 rendered (MAP.json:379-382); board has min-height 24 only. Fix: add `padding: 2px 0;`.

Holds as written: Refined "Bridge" not "Start bridge" (:36); Doctor yellow kept (:38); receipt words "1 CHANGE" / "← REVERT" unchanged (:76, :78); timestamps 11 (:57, :66); flat #2A2A2A ground (:23); SEND ink #111111 (:87); khint/footer/tag/composer text all at 46 (:94, :99, :75, :85); '/ commands' dropped (:86); empty state without "Ready." (:53). Main tokens verified correct: GUTTER 30, HAIR #303030, BORDER #363636, GROUND #1F1F1F, composer 64 / 16px 15px / r4, SEND #0F1F2B on #627A93 9px 15px 0.88px, timestamp 10px, DsVerb 11/1.65px/#A0A0A0/2px 0/8px margins, Doctor #B98620, 12px spacer, overflow 32, attach 52, tag 12/500/0.72px/6px 10px/999/margin-left 16, khint 0.33px. All four files well-formed (balanced, quoted, no emoji, no images); canvas.json artboard names and frames match; annotations well-formed.
