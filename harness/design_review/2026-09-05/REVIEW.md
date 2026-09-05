# SYNAPSE panel design review — synthesis to the CTO

**Date** 2026-09-05 · **Master** 74dc0219 (Panel PD wave landed) · **Reference practice** Pentagram / Michael Bierut
**Method** five lenses (IDEA, TYPE, SYSTEM, SUBTRACT, USE), two rounds, 139 bus posts, hython 22.0.400 offscreen at 340×760 in all three profiles, plus the landed screenshots under `design/rhythm_pd/after_r3/`. Every number below has a producer file in this directory or a `path:line` in the tree.

---

## Verdict

**HOLD as the design reference until the four blockers close.**

The idea is sound and measurably held. The style has started substituting for it at four seams. At the panel's own preferred width (340, `tokens.py:623`) in every density, the panel clips its verbs, cannot say its state, promises a docking width it never offers the host, and speaks another colour grammar at the one moment the artist decides to trust it.

The restraint half is real: 0.82–0.84% chromatic pixels, three hue buckets, one warm mark, a wordmark that never elides. That is the floor. Nothing below touches it.

---

## The one point of view

A conversation with a capable studio partner, docked at 340 in a dark host.

One voice for words (Space Grotesk) and one for data (Space Mono). One accent, and it means *the artist's next action*. One sentence of state that never gives way — exactly as the wordmark never gives way. Nothing on screen the artist cannot read at the width the panel asks for.

Everything that is not the conversation, its state, its verbs, or its consent is chrome. Chrome earns its place at 340 or leaves.

Sources: `docs/design/SYNAPSE_PANEL_REDESIGN.md:43` (the sentence), `:59` (CONVERSE dominant); `python/synapse/panel/designsystem/tokens.py:357-363` (mono is for code); `docs/PANEL_BATTLEPLAN_PD.md:185` (accent: SIGNAL family only, no other colour points); `python/synapse/panel/synapse_panel.py:706-712` (the never-elide floor).

---

## Gates and the predicate preamble

- **auto** — doc/test-only.
- **crux** — code inside `python/synapse/panel/designsystem/`.
- **joe** — anything that changes what the artist sees.

Every closure predicate below runs from the repo root in Git Bash after this preamble:

```bash
HY="C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe"
DR=harness/design_review/2026-09-05
probe() { for p in curious expert ml; do for s in census_subtract use_probe measure_regions; do
  SYNAPSE_PANEL_SETTINGS=$DR/settings_$p.json QT_QPA_PLATFORM=offscreen "$HY" $DR/$s.py $p >/dev/null 2>&1; done; done; }
export PYTHONIOENCODING=utf-8
```

`probe` re-measures all three profiles (~60s). Predicates print `PASS` or the offending rows.

---

## Findings, ranked

### Blockers

**F1 · The type-set verb rail is cut mid-word at 340 in three of three profiles** — IDEA-04 · T2 · S3 · USE-01 — gate **joe**

Evidence. Natural rail width 333 / 301 / 285 (airy / standard / tight, group gaps 24 / 16 / 12) against the 280 interior (340 − 2×GUTTER 30). Rendered width / hint: expert OPTIMIZE 59/65, BUILD HDA 58/73; curious EXPLAIN 48/57, OPTIMIZE 47/65, BUILD HDA 48/73; ml BUILD HDA 68/73 (`census_*.json` verbs, `use_*.json` verb_rail.natural, `verb_tracking.json`). Visible as ')PTIMIZE' 'UILD HD.' / 'XPLAIN' 'PTIMIZ' 'ILD HI' in `design/rhythm_pd/after_r3/{expert,curious,ml}/panel_direct_chat.png`. Same clip in `before/`. Construction `synapse_panel.py:1901-1916`; the wordmark's floor at `:712` was never given to the verbs.

Where lenses disagreed, and which evidence wins. TYPE said tracking is the cause (LABEL 0.15em = 301; DATA 0.03 = 278 fits; sans 12 sentence-case = 248). USE and SUBTRACT showed those fits assume the standard gap of 16; at airy (gap 24, `use_curious.json`) 0em mono = 304 and sans 12 = 280 with zero slack. **The airy measurement wins:** the count is the first problem, tracking the second. IDEA wants a rail with fewer words (the rail is the one type-set action surface below the wordmark, `qss.py:159-165`); USE/SUBTRACT want the rail retired (palette twins at `command_palette.py:86-96`, Aa duplicates overflow `:2040-2041`). Both are honest; that choice is Joe's (Direction A vs Direction B). B11 (collapse to icons below ~360, `docking-minimums.yaml:43`) is retired as an option: it trades the voice for a row the palette already is.

Fix. Conformance now: verbs never elide (the `setMinimumWidth(sizeHint)` rule at `:712`). Decision: three sans verbs on a rail, or no rail.

Closure predicate.
```bash
probe; python -c "import json,glob;bad=[(f,v['text'],v['w'],v['hint_w']) for f in glob.glob('$DR/census_*.json') for v in json.load(open(f,encoding='utf-8'))['verbs'] if v['w']<v['hint_w']];print('PASS' if not bad else bad)"
```
(Also passes vacuously if the rail is retired: `verbs` is then empty.)

---

**F2 · At 340 the panel cannot say what it is doing, and its two truths at boot are both invisible** — USE-02 · S1 · S2 · SYS-8 · IDEA-07 (fold) — gate **joe**

Evidence. `_header_status`, `_meter_lbl`, `_palette_hint`, `_author_lbl`, `_foot_label` all render w=0 in airy, standard and tight (hints 66/7/67/81/83 = 304 px painted at 0; `use_*.json` rail_labels, `census_*.json` rail_labels). Cause: `QSizePolicy.Ignored` at `synapse_panel.py:833-835`; 0 hits for `breakpoint|reappear` in tokens.py, synapse_panel.py, PANEL_RHYTHM_SPEC.md, PANEL_REGION_MAP.md. Boot: header 'Standing by' AND foot 'Not connected' at once (`use_*.json` boot_truth; `:768-769`, `:2580`; `_update_context :2652-2670` only ever moves the foot toward 'Houdini'). Health strip 280×16 of four 0-width 'unknown' cells (`:846-853`). With a gate up, 'Result ready' is also 0px (`use_review_expert.json`). `DsRailMeter` constructed `:799-800`, never shown `:820`.

Fix. One state string from `STATUS` (`tokens.py:601-608`; disconnected wins over idle) with the wordmark's hard minimum. Author token, Ctrl+K and the health strip move to the overflow where the Engine submenu already lives (`:2032`). Delete the five Ignored labels and DsRailMeter. Rail 84 → 52 in every profile; not one visible pixel is lost.

Closure predicate.
```bash
probe; python -c "
import json
ok=True
for p in ('curious','expert','ml'):
    u=json.load(open('$DR/use_%s.json'%p,encoding='utf-8')); rl=u['rail_labels']
    shown=[k for k,v in rl.items() if v['geo'][2]>0]
    hidden=[k for k,v in rl.items() if v['geo'][2]==0 and v['hint_w']>0]
    full=[k for k in shown if rl[k]['geo'][2]>=rl[k]['hint_w']]
    bt=u['boot_truth']; contradict=('Standing by' in bt['header'] and 'Not connected' in bt['foot'])
    good=(len(full)>=1 and not hidden and not contradict)
    ok&=good; print(p,'shown',shown,'hidden',hidden,'boot',bt,'OK' if good else 'FAIL')
print('PASS' if ok else 'FAIL')"
```

---

**F3 · Docking is a patch: 280 promised, 393/361/345 measured, 400/380/380 written in YAML prose and read back by regex** — SYS-6 — gate **joe** (the decision) · **crux** (the token)

Evidence. `tokens.py:622` `PANEL_MIN_WIDTH = 280`; `probe_*.json` `panel_minimumSizeHint` [393,353] / [361,337] / [345,329] (reproduced by `use_*.json` min_hint). `.synapse/contracts/docking-minimums.yaml:42-45` carries the per-density bound as a feature-description string; `tests/test_panel_rhythm_docking.py:85-86` recovers it with `re.findall(r"<= (\d+)px wide at (airy|standard|tight)")`. The only collapse rule on file is prose ('verb rail to icons below ~360px … next design wave').

Fix. Decide what gives way at 340 and write it where the next designer looks: per-density floors beside `PANEL_MIN_WIDTH`, one `DOCK_COLLAPSE_PX`, a written reappear rule for anything that hides. Either 280 becomes true or it is deleted. The test reads tokens, not prose.

Closure predicate.
```bash
python -c "
import re,sys; sys.path.insert(0,'python')
from synapse.panel.designsystem import tokens as t
src=open('tests/test_panel_rhythm_docking.py',encoding='utf-8').read()
have=hasattr(t,'DOCK_COLLAPSE_PX') and hasattr(t,'PANEL_MIN_WIDTH_BY_DENSITY')
print('PASS' if have and 'px wide at (airy|standard|tight)' not in src else 'FAIL: tokens has DOCK_COLLAPSE_PX=%s PANEL_MIN_WIDTH_BY_DENSITY=%s; test still regex-parses YAML=%s'%(hasattr(t,'DOCK_COLLAPSE_PX'),hasattr(t,'PANEL_MIN_WIDTH_BY_DENSITY'),'px wide at (airy|standard|tight)' in src))"
```
(Token names are proposals; rename in the predicate if Joe names them differently.)

---

**F4 · The consent card speaks another colour grammar, and at REVIEW level offers no verb** — IDEA-06 · USE-04 · SYS-10 · USE-08 (targets) — gate **joe**

Evidence. `design/rhythm_pd/after_r3/expert/gate_widget.png` 5562 chromatic px = 3.15% across 12 hue buckets vs chat 2181 / 0.84% / 3 buckets and review face 646 / 0.37% / 3 (Pillow, chroma > 24, 15° buckets). Mechanism — SYSTEM's trace wins over IDEA's round-1 attribution: hues are read directly from `GATE_LEVELS` (`tokens.py:611-616`) at `gate_widget.py:28-31` and GROW/ERROR at `:327, :353`; `styles.py:714-790` has 0 consumers and is a dead second stylesheet source. Buttons only for `approve`/`critical` (`gate_widget.py:204`); `_on_gate_raised` surfaces Work for any non-inform level (`synapse_panel.py:2007-2021`); a REVIEW card measures 280×19 with `buttons: []` (`use_review_expert.json`); Reject 62×23, Approve 68×23, fold toggle 280×23. `face_review.py:328-335` proves consent verbs already exist in the muted set (ACCEPT tone ok, COMMIT tone hot).

Fix. GateWidget takes the panel's own vocabulary: DsCard bands, DsVerb tone verbs, rhythm tag badges. Every auto-surfaced card carries a verb (REVIEW: reject — CLAUDE.md §1.2 'continues unless rejected' owes the control). Approve is the one accented thing on the card. All consent targets at the 36px verb height. The hue map for four levels inside the muted set is proposed to Joe with WCAG numbers, not invented. Direction C sketches the inline form.

Closure predicate.
```bash
SYNAPSE_PANEL_SETTINGS=$DR/settings_expert.json QT_QPA_PLATFORM=offscreen "$HY" $DR/use_probe_review.py expert >/dev/null 2>&1; python -c "
import json; u=json.load(open('$DR/use_review_expert.json',encoding='utf-8'))
rc=u['review_card']; ft=u['fold_toggle']
btns=rc.get('buttons',[]); ok=len(btns)>=1 and ft['geo'][3]>=36
print('PASS' if ok else 'FAIL: review buttons=%s fold_h=%s'%(btns,ft['geo'][3]))"; python -c "
from PIL import Image; import colorsys
im=Image.open('design/rhythm_pd/after_r3/expert/gate_widget.png').convert('RGB'); b=set()
for r,g,bl in im.getdata():
    if max(r,g,bl)-min(r,g,bl)>24: b.add(int(colorsys.rgb_to_hsv(r/255,g/255,bl/255)[0]*360)//15)
print('PASS' if len(b)<=3 else 'FAIL: %d hue buckets'%len(b))"
```
(The PNG half requires the after_r3 shot to be regenerated by `harness/notes/panel_shot.py` after the change.)

---

### Majors

**F5 · The profile row is a density switch wearing a persona name; it costs the conversation its majority and brings a second selector vocabulary** — IDEA-01 · IDEA-03 · S5 · USE-06 · SYS-3 · SYS-4 · SYS-5 · T7 — gate **joe** (row) · **crux** (RADIUS_ROUND)

Evidence. Chat 282/338/366 px = 37/44/48% of 760 (`regions_*.json` chat.h); chrome before the first word 193/177/169. DsTabRow (47px) holds only CURIOUS/EXPERT/ML; `compositor.py:252-268` walks identical builders for all three. CHAT/TOKEN are underline tabs 11px/115%/400; profile chips are filled squares 12px/106%/500/AllUppercase via three appliers (`synapse_panel.py:1099-1100` dead; `qss.py:388-392`; `rhythm.py:55-71`). Mechanism — SYSTEM/TYPE win over IDEA's round-1 sentence: `#DsRoot [rhythm_role="tag"]` (1,1,0) outranks `QPushButton#DsPill` (1,0,1), so `RADIUS_ROUND` 999 is applied and Qt 6.8.3 drops any radius over half the box (`probe_radius.json`: 999/100 corner = fill, 14/8 corner = host; boundary at 14.5 on a 29px chip). Curious clips its own selected name 'URIOUS'. The HDA form the shipped BUILD HDA verb opens *does* receive density (SYSTEM's entry-point trace, SYS-9 downgraded).

Fix. Fold the row into the overflow. A CHAT pill whose only sibling is TOKEN is a label, so one TOKEN underline tab at the ribbon edge. +47px: expert 338 → 385 = 51%. Retire `RADIUS_ROUND` or define it as half the target box (`RADIUS_PILL` 14 for a 29px chip). The three-applier fight dissolves by removal.

Closure predicate.
```bash
probe; python -c "
import json,sys; sys.path.insert(0,'python')
from synapse.panel.designsystem import tokens as t
ok=all(json.load(open('$DR/regions_%s.json'%p,encoding='utf-8'))['chat']['h']/760>=0.5 for p in ('curious','expert','ml'))
rr=getattr(t,'RADIUS_ROUND',None); ok&=(rr is None or rr<=14)
print('PASS' if ok else 'FAIL: chat share %s RADIUS_ROUND=%s'%([json.load(open('$DR/regions_%s.json'%p,encoding='utf-8'))['chat']['h'] for p in ('curious','expert','ml')],rr))"
```

---

**F6 · Two-thirds of the voice is typewriter against the system's own doctrine; four primary buttons are repainted as verbs** — T3 · IDEA-05 — gate **joe**

Evidence. `type_census_expert_340.json` summary.family_hist: Space Mono 85, Space Grotesk 34, host face 8 (all text widgets; 61/26/8 among the visible). `tokens.py:357-363`: 'Mono is for CODE, sans is for everything else … reads like a terminal emulator'. Connect/Corpus built `c.Button(variant='primary')` at `synapse_panel.py:783, 792`, then re-objectNamed `DsVerb` + tracked_font at `:828-831`; Help `:778` and overflow `:745` likewise; `tokens.py:239` still documents SIGNAL_DEEP as 'Connect / Corpus / SEND'.

Fix. Space Grotesk for anything read as words (verbs, Connect, pills, captions, khint); Space Mono for ids, paths, counts, code and the eyebrow. Build rail controls with `_verb()` (`:1883`) once and delete the re-name loop; update `tokens.py:239`. This one move also resolves F1 at standard and most of F7.

Closure predicate.
```bash
SYNAPSE_PANEL_SETTINGS=$DR/settings_expert.json QT_QPA_PLATFORM=offscreen "$HY" $DR/type_census.py expert 340 >/dev/null 2>&1; python -c "
import json; h=json.load(open('$DR/type_census_expert_340.json',encoding='utf-8'))['summary']['family_hist']
print('PASS' if h.get('Space Grotesk',0)>h.get('Space Mono',0) else 'FAIL: %s'%h)"; python - <<'EOF'
import re; s=open('python/synapse/panel/synapse_panel.py',encoding='utf-8').read()
n=len(re.findall(r'setObjectName\(\s*["\']DsVerb["\']\s*\)', s)); print('PASS' if n==0 else 'FAIL: %d DsVerb re-name sites'%n)
EOF
```

---

**F7 · Ten tracking values through four mechanisms; the token doctrine's reason is false on this host** — T4 · SYS-13 · SYS-11 — gate **crux**

Evidence. spacing_hist 100/115/106/108/116/103/122/112% plus abs 0.5/1.0px (`type_census_expert_340.json`). Mechanisms: QFont percent (`fontload.py:181`), QFont abs (`components.py:47`), QSS `letter-spacing` (`qss.py:533,537,560,584,587`), HTML (`message_formatter.py:302`). `tokens.py:378` 'Qt QSS has no letter-spacing' — `probe_qss_letterspacing.json`: 63 → 108px, and QSS silently overrides a QFont percentage and flips the spacing type. BRAND and BODY have 0 consumers.

Fix. Three values, one owner: `TRACKING_EM = {WORDMARK 0.16, EYEBROW ~0.10, DATA 0.03}`; QFont owns tracking; delete the five QSS sites (all in SWEEP_A blocks that ship nothing) and the TYPE_ROLES absolute-px column; correct the sentence at `tokens.py:378`.

Closure predicate.
```bash
python -c "
import sys,re; sys.path.insert(0,'python')
from synapse.panel.designsystem import tokens as t
q=open('python/synapse/panel/designsystem/qss.py',encoding='utf-8').read()
n=len(re.findall(r'letter-spacing', q)); k=sorted(t.TRACKING_EM)
print('PASS' if n==0 and len(k)<=3 else 'FAIL: qss letter-spacing sites=%d TRACKING_EM=%s'%(n,k))"
```

---

**F8 · SEMIBOLD is a name without a face; the same token draws 500 or 700 by code path** — T5 — gate **crux**

Evidence. Bundled Space Grotesk registers Light/Regular/Medium/Bold (`type_census_*.json` styles_registered). `WEIGHT_SEMIBOLD = 600` (`tokens.py:354`) → `setBold` at `components.py:45` / `fontload.py:176-177` = 700; QSS `font-weight: 600` = Medium. `qss.py` writes 700 as `WEIGHT_SEMIBOLD + WEIGHT_MEDIUM - WEIGHT_REGULAR` eleven times (`:533, :543, :544, :560, :587, :630, :633, :642, :653, :666, :676`). weight_hist 400×71, 500×17, 700×5, 600×2.

Fix. Name what the bundle has: REGULAR 400, MEDIUM 500, BOLD 700. Replace SEMIBOLD site by site with the weight that already renders; delete the arithmetic. Keep near-zero bolding.

Closure predicate.
```bash
python -c "
import re,glob; n=0
for f in glob.glob('python/synapse/panel/designsystem/*.py'): n+=len(re.findall(r'WEIGHT_SEMIBOLD', open(f,encoding='utf-8').read()))
print('PASS' if n==0 else 'FAIL: %d WEIGHT_SEMIBOLD references in designsystem/'%n)"
```

---

**F9 · The ladder on paper is not the ladder on screen; four floors; six 10px widgets the audit never sees** — T1 · T8 · USE-07 · S11 — gate **joe** (floor) · **auto** (audit walk)

Evidence. `TYPE_ROLES` 19/15/12/11 (+10); rendered px_hist 11×73, 12×43, 10×6, 14×4, 15×1 — no 19 anywhere; 14 and 21 are literals (`synapse_panel.py:704`, `face_review.py:227`); `health_infographic.py:113` paints 11px via QPainter outside TYPE_ROLES. `scaled()` min 8 (`tokens.py:655-657`), `FONT_FLOOR_PX = 10` 'provenance UNKNOWN' (`:337-345`), `READABLE_FLOOR = 11` on a 7-name tuple (`audit_panel.py:377`), `BODY_FLOOR = 12`. khint is DATA 10px mono TERTIARY 3.9:1 (`synapse_panel.py:1952-1954`), outside the tuple; five more 10px widgets likewise. G3 'chrome floor ≥ 11 [ok]' is true of its list, false of the panel. Zero-consumer tokens (SIZE_HERO, BRAND, BODY, LABEL_SM, DISPLAY) are each test-pinned (`tests/panel/test_type_scale_native.py:24`, `tests/test_panel_faces.py:394-446`), so retirement is Joe's edit.

Fix. One floor (11 until the GUI probe lands), consumed by `scaled()`, every `tracked_font` and the audit; the audit walks visible text widgets, not a tuple. Promote 14/21 into the ladder or retire them. Put the zero-consumer tokens on the no-list.

Closure predicate.
```bash
SYNAPSE_PANEL_SETTINGS=$DR/settings_expert.json QT_QPA_PLATFORM=offscreen "$HY" $DR/type_census.py expert 340 >/dev/null 2>&1; python -c "
import json,sys; sys.path.insert(0,'python')
from synapse.panel.designsystem import tokens as t
h=json.load(open('$DR/type_census_expert_340.json',encoding='utf-8'))['summary']['px_hist']
mn=min(int(k) for k in h); print('PASS' if mn>=11 and t.FONT_FLOOR_PX>=11 else 'FAIL: min rendered px=%d FONT_FLOOR_PX=%d'%(mn,t.FONT_FLOOR_PX))"
```

---

**F10 · The composer's biggest glyph is its least-used control, and it says '/' three times** — IDEA-08 · USE-05 · S8 · S4 — gate **joe**

Evidence. attach 52×54 = 2808px² (`setIconSize(36,36)`, `setFixedWidth(52)`, `synapse_panel.py:1931-1935`, on a 24 icon grid `tokens.py:544`) vs SEND 60×32 = 1920px²; input 212 of 280 (`use_expert.json` composer). Placeholder 'Ask SYNAPSE…    ·    / for commands' (`:126`) wraps in all three shots; khint repeats '/ commands' at 10px (`:1952`); the Ctrl+K chip is a third telling at 0 width (`:745`). SEND carries 79–87% of all accent pixels on the panel.

Fix. Attach as a 24px ghost glyph inside the well; SEND the single raised element; placeholder 'Ask SYNAPSE…'; one legend (khint at caption 11 SECONDARY, or delete it and put Shift+Enter in the tooltip). ~28% more input width.

Closure predicate.
```bash
probe; python -c "
import json; u=json.load(open('$DR/use_expert.json',encoding='utf-8'))['composer']
a=u['attach']; s=u['send']; legend=(u['placeholder'].count('/')+u['khint']['text'].count('/')) if u.get('khint') else u['placeholder'].count('/')
ok=a[2]*a[3]<s[2]*s[3] and u['attach_icon'][0]<=24 and legend<=1 and u['input'][2]>=240
print('PASS' if ok else 'FAIL: attach %s icon %s send %s input %s slash-tellings %d'%(a,u['attach_icon'],s,u['input'],legend))"
```

---

**F11 · Undo after a quiet turn has no control on the CHAT surface** — USE-03 · IDEA [118] · S [114] — gate **joe**

Evidence. REVERT only at `face_review.py:328-329` (`_on_revert` `synapse_panel.py:1754-1762`). The only `_set_face("work")` is `:2021`, gated `level != inform`; INFORM ops (create_node, set_parameter, connect_nodes — CLAUDE.md §1.2) never raise a gate; `chat_display.py` has no per-tool receipt; `use_expert.json` revert_visible_on_chat = [False]. 'Every action reversible and recorded' is the product's stated differentiator.

Fix. A per-turn revert in the transcript footer for turns whose `_turn_tools` include a mutator (the data exists at `:1657-1672`), or the MarkDot done-state as a click target into Work. One signal, one destination.

Closure predicate.
```bash
probe; python -c "
import json; ok=all(any(json.load(open('$DR/use_%s.json'%p,encoding='utf-8'))['revert_visible_on_chat']) for p in ('curious','expert','ml'))
print('PASS' if ok else 'FAIL: no artist-clickable revert on the CHAT surface')"
```
(`use_probe.py` must be extended to drive one INFORM-only turn before reading `revert_visible_on_chat`; today it reads the boot state.)

---

**F12 · Nine rhythm roles resolve to two gap sizes; row is dead; parm_row is a column-width hook; three things are named 'label'** — SYS-1 · SYS-2 · T12 — gate **crux**

Evidence. `rhythm.py:26-36`: shell=group=card 24/16/12, stack=parm_row 6/4/3, band 0 (`probe_*.json` applied_gaps_by_role). `rhythm_role="row"` has 0 set-sites; `qss.py:374-387` still ships its 44px box. 22 of 24 parm_row stamps sit on layout-less QLabels; their only effect is `qss.py:424-431` SPACE_32×4 / ×2. `TYPE_ROLES['label']`, `TRACKING_EM['LABEL']`, `rhythm_role='label'` are three different things (RULING-4d defers the rename, `PANEL_RHYTHM_SPEC.md:167-172`).

Fix. Fewer roles that mean more (shell, group, stack, band, eyebrow, tag); card aliases group or gets its own margin; delete the row block; parm columns become named dimension tokens. The collapse is a Design Director call; the code is designsystem/.

Closure predicate.
```bash
python -c "
import sys,re; sys.path.insert(0,'python')
from synapse.panel.designsystem import rhythm
g=rhythm.ROLE_GAPS if hasattr(rhythm,'ROLE_GAPS') else {}
q=open('python/synapse/panel/designsystem/qss.py',encoding='utf-8').read()
dead='rhythm_role=\"row\"' in q
print('PASS' if not dead and len(set(g.values()))==len(g) else 'FAIL: row block shipped=%s gaps=%s'%(dead,g))"
```

---

**F13 · A second pypanel entry point is dead but not gone, and the sheet carries type for surfaces that do not ship** — SYS-12 · T11 · SYS-9 — gate **crux**

Evidence. `packages/synapse.json` hpath → `houdini/python_panels/synapse_panel.pypanel:45`; `python/synapse/panel/synapse_chat.pypanel:35-41` launches `chat_panel.SynapseChatPanel` (no compositor) off hpath. `qss.py:459-461` admits SWEEP_A ships nothing, yet `:530-782` ships pt units in a px system, 18/14px derived sizes, 10px on a primary button. `after_r3` manifests still render hda_* and context_bar; three lenses reviewed them as shipped. `tests/test_panel_alt_entry_unshipped.py` already pins reachability.

Fix. Delete the alternate entry and the SWEEP_A blocks with their modules, or mark them unshipped so census and screenshot manifests skip them. Make `rhythm.apply` require a density (SYS-9).

Closure predicate.
```bash
python -c "
import os,re; q=open('python/synapse/panel/designsystem/qss.py',encoding='utf-8').read()
alt=os.path.exists('python/synapse/panel/synapse_chat.pypanel'); n=len(re.findall(r'HdaGenerateBtn|StageLabel', q))
print('PASS' if not alt and n==0 else 'FAIL: alt pypanel=%s sweep_a type rules=%d'%(alt,n))" && "C:/Program Files/Side Effects Software/Houdini 22.0.400/python313/python.exe" -m pytest tests/test_panel_alt_entry_unshipped.py -q -p no:cacheprovider
```

---

**F14 · The idle panel says 'nothing yet' eight ways; the Work face shows five at once** — IDEA-07 · T [87] · S [104] — gate **joe**

Evidence. 'Standing by' (`synapse_panel.py:714`; `face_work.py:196`), 'Not connected' (`:769`), 'no scene context' (`:1002`), 'Ready. What are we building?' (`:1024`), 'waiting for work' (`face_work.py:215`), 'no steps yet' (`:333`), 'Awaiting telemetry…' (`health_infographic.py:113`), 'no operations tracked yet' (`integrity_readout.py:63`). `after_r3/expert/panel_work.png`: five on one face.

Fix. One idle line per face. The chat face already has the right one. Empty sub-sections render as absence.

Closure predicate.
```bash
python -c "
import re,glob; idle=['Standing by','waiting for work','no steps yet','Awaiting telemetry','no operations tracked yet','no scene context']
n=sum(len(re.findall(s, open(f,encoding='utf-8').read())) for f in glob.glob('python/synapse/panel/**/*.py',recursive=True) for s in idle)
print('PASS' if n<=3 else 'FAIL: %d idle-string sites (target: one per face)'%n)"
```

---

### Minors

**F15 · The written idea exists in two versions; reviewers read the older one first** — IDEA-02 (downgraded from major) · IDEA-11 — gate **auto**

Evidence. `REDESIGN.md:45-46` names cyan #00D4FF, DM Sans/JetBrains, a four-hue status grammar and 'SIGNAL for intelligence/connectivity'; shipped truth is `tokens.py:29` #8FB3D9, Space Grotesk/Mono, and `BATTLEPLAN_PD.md:185`. On screen the accent consistently means the next action (2181 chromatic px; SEND 1714–1908; 0 on the connection ring). IDEA downgraded its own finding once it saw the doc-vs-doc split; the panel conforms to the live doctrine.

Fix. One line at the top of REDESIGN.md §3 marking it superseded by tokens.py + BATTLEPLAN §4; one sentence at `tokens.py:29` stating what SIGNAL means.

Closure predicate.
```bash
python -c "
s=open('docs/design/SYNAPSE_PANEL_REDESIGN.md',encoding='utf-8').read(); stale=('00D4FF' in s and 'superseded' not in s.lower())
print('PASS' if not stale else 'FAIL: REDESIGN.md sec3 still carries #00D4FF without a superseded marker')"
```

**F16 · Four vocabularies for 'this is where a band ends'; the grid has no hairline rung** — IDEA-09 · SYS-7 — gate **crux**

Evidence. HAIR rule (`qss.py:39, :338`), BORDER rule (`:119`; `components.py:333`; `:410`), the '· · ·' grip, and a bare tone step at y=185. Six off-ladder `setSpacing(1|2)` literals (`face_review.py:271,299`; `integrity_readout.py:82`; `face_work.py:226`; `chat_panel.py:425`; `recall_card.py:115`) behind exemptions reading 'no role expresses 1px'; `rhythm.apply` walks widgets so a bare QLayout can never carry a role.

Fix. HAIR for chrome boundaries (`tokens.py:137-141`); drop the divider between verbs and composer; add a seam rung (0–1px); keep the grip.

Closure predicate.
```bash
python -c "
import re,glob; hits=[]
for f in glob.glob('python/synapse/panel/**/*.py',recursive=True):
    for i,l in enumerate(open(f,encoding='utf-8'),1):
        if re.search(r'setSpacing\(\s*[12]\s*\)', l): hits.append('%s:%d'%(f,i))
print('PASS' if not hits else hits)"
```
(Passes when a seam rung exists and the six sites use it; `harness/notes/panel_rhythm_census.py --json/--md` regenerates the census for the exemption count.)

**F17 · A third family leaks in: eight widgets carry no family at all** — T10 — gate **joe**

Evidence. family_hist host face = 8 (ChatDisplay widget font, DsInput, HDA QTextEdit/QComboBox/QCheckBox, DsButton Generate HDA / Main menu). `chat_display.py:157-162` fonts the document, not the widget; `qss.py:21` 'No font-family'. Offscreen Courier; in Houdini the host sans.

Fix. Apply `fontload.apply_family` on the eight at construction, or declare body = host face in TYPE_ROLES. One decision either way.

Closure predicate.
```bash
SYNAPSE_PANEL_SETTINGS=$DR/settings_expert.json QT_QPA_PLATFORM=offscreen "$HY" $DR/type_census.py expert 340 >/dev/null 2>&1; python -c "
import json; h=json.load(open('$DR/type_census_expert_340.json',encoding='utf-8'))['summary']['family_hist']
other={k:v for k,v in h.items() if k not in ('Space Mono','Space Grotesk')}
print('PASS' if not other else 'FAIL: %s'%other)"
```

**F18 · Small click targets on the rail and verb row** — USE-08 · S6 · S7 — gate **joe**

Evidence. '?' 9×36 (hint 9), Aa 17×36, overflow 24×36, FIX 25×36 in all three profiles (`use_*.json` small_targets); G3 measures sizeHint height only (`audit_panel.py:181`). Corpus tooltip cites the H21 corpus on an H22.0.400 host (`synapse_panel.py:791-796`).

Fix. Fold ? and Aa into the overflow; Corpus folds into Connect ('connect, then ground the corpus' `:810`); surviving verbs get a 32px minimum width.

Closure predicate.
```bash
probe; python -c "
import json; bad={p:json.load(open('$DR/use_%s.json'%p,encoding='utf-8'))['small_targets'] for p in ('curious','expert','ml')}
print('PASS' if not any(bad.values()) else bad)"
```

---

### Praise (one line each, earned)

- **P1** The restraint half of the idea is real: 2175 / 2181 / 2121 chromatic px of 258,400 (0.82–0.84%), three hue buckets, identical in all three profiles — reproduced by five lenses.
- **P2** The wordmark never gives way: w = hint = min = 69 at 340 in every density and at 280 (`synapse_panel.py:706-712`); Space Grotesk 700, 14px, 116%.
- **P3** One property drives one grid through one sheet: 0 raw hex outside designsystem/, every role gap steps exactly round(base × 1.5/1.0/0.75), the Aa ladder moves chat and leaves chrome alone.
- **P4** The subtraction doctrine is already in the file: Stop is state-gated (`:737-738`), the rail meter was retired as 'a fourth signal for one state' (`:815-820`), verbs are type not pills (`:1883`).
- **P5** Contrast holds in a dark host: PRIMARY 8.3 / 9.5 / 7.0:1, seeded worst 5.3:1 at grey 95 (G3 pass).

---

## Rulings for the CTO

1. **Verb rail (F1).** The airy measurement (333 at 24px gaps) wins the fix argument: no mono tracking fits five words; count first, tracking second. Conformance (never-elide) now; count-vs-retire is Joe's, sketched as Direction A vs B. B11 icon collapse is retired.
2. **IDEA-06 mechanism.** SYSTEM's trace wins: gate hues come from `GATE_LEVELS` via `gate_widget.py`, not `styles.py:714-790` (0 consumers). Retire styles.py's gate sheets as dead code regardless.
3. **IDEA-03 mechanism.** SYSTEM/TYPE win: the tag rule outranks `#DsPill`; `RADIUS_ROUND` 999 is applied and dropped by Qt. Editing `qss.py:123` would change nothing.
4. **T2 'tracking is the cause'.** USE/SUBTRACT win at airy; TYPE is right at standard. S3's '+41 clears expert' was airy arithmetic; the corrected figure is +33 at expert, +41 at curious (still −12).
5. **SYS-9.** SYSTEM's own entry-point trace wins over USE's corroboration: the shipped BUILD HDA form lives inside the composed root and receives density. Downgraded to minor and folded into F13.
6. **IDEA-02.** Downgraded to minor: `BATTLEPLAN_PD.md:185` is the live accent doctrine and the panel conforms to it; `REDESIGN.md` §3 is stale (F15, auto).
7. **Tracking owner.** QFont, not QSS: the probe shows QSS silently overrides a QFont percentage. Delete the five QSS sites (SYSTEM answer to TYPE [75]).
8. **Zero-consumer tokens.** On the no-list, not deleted here: each is test-pinned; retirement is a human test edit (S11).
9. **Audit honesty (F9).** G3's chrome-floor line is true of a 7-name tuple and false of the panel; the audit must walk widgets. Auto-gated, no threshold is weakened.
10. **Directions are options.** A (three sans verbs), B (no rail), C (consent + undo inline) are sketches for Joe; C composes with either A or B.

---

## GUI gate — what offscreen cannot verify

- Host UI font and `chrome_scale` (offscreen reads none): F17's eight host-face widgets resolve differently inside Houdini.
- The real dock at 340 in a pane beside the network editor: whether the host ever offers 280, and how the pane behaves at the 393/361/345 hints (F3).
- `FONT_FLOOR_PX` host default (F9): the floor is provisional at 11 until measured on the live host font.
- Gate card auto-surface in a live session (F4): `use_probe_review.py` drives `_add_proposal_card` synthetically.
- Tooltips and hover for anything folded into the overflow or StatusDot (F2, F18).
- Corpus tooltip text on H22 (`synapse_panel.py:791-796`).
- Colour on the artist's actual monitor: chroma counts are file-space measurements of offscreen PNGs.

---

## Files written (all under `harness/design_review/2026-09-05/`)

- `Findings.dc.html` — the review artboard (880×1100).
- `DirectionA.dc.html`, `DirectionB.dc.html`, `DirectionC.dc.html` — low-fi option sketches (720×800, black/white + SIGNAL).
- `canvas.json` — Findings added to row 1 right of Regions (x=3840); Directions as row 3 (y=1740).
- `REVIEW.md` — this file.
- `bus.jsonl` — five SYNTHESIS posts appended (round 2).

Nothing outside this directory was written. No product code, tests, or `.git` were touched.
