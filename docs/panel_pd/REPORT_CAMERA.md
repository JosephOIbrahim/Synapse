# PD-CAMERA report — 2026-09-04

**BLOCKED: Git delivery, strict raw-zero acceptance and composed docking.**
T1–T6 implementation is present on `pd/panel-camera`, starting at `ce04dcb0`.
HEAD is unchanged because all staging/commit attempts failed. This is not a
green receipt, merge request, or GUI sign-off.

## Final acceptance ledger

| Deliverable / criterion | Verdict and producer |
|---|---|
| T1 profile row pills, SIGNAL active, no local 28 gap | PASS: `python/synapse/panel/synapse_panel.py:984`. Existing active underline is SIGNAL, text remains bright; no new accent fill. |
| T2 label verbs / group divider / role gap | PASS: `synapse_panel.py:1806`; `_verb` label role, Direct uses existing `c.divider()` after the group. |
| T3 token leading / turn headers / role message gaps | PASS real Qt: `chat_display.py:173,456,630`; explicit grouping/header metadata through sync and queued inserts; density changes preserve history. |
| T4 recall card / existing result / status truth | PASS adapter + real Qt: `recall_card.py:11,52,107`; panel wiring `synapse_panel.py:1586,2005`; 40px header/footer, literal deposit, Copy left/status right, HOT_SOFT only BLOCKED. |
| T5 parameter columns / UNKNOWN text | PASS real Qt: `face_token.py:430,454`; existing grids, direct child DsParmLabel/Value, 128/64 columns. UNKNOWN never becomes zero; measured 0 stays 0. |
| T6 one header row / label controls / ? opens docs | IMPLEMENTED: `synapse_panel.py:613,930`; same help callback, unchanged shelf. Narrow-header visual nits remain. |
| CAMERA census 0 / 0 / 0 | **FAIL strict raw count**: actual **2 spacing / 1 sheet / 0 hex**, all three residual sites have specific exemption comments. No untagged or grid-spacing CAMERA sites. |
| Before/after PNGs per profile | CAPTURED, commit BLOCKED: twelve genuine PNGs under `design/rhythm_pd/{before,after}/{curious,expert,ml}/{panel_direct,panel_token}.png`. Before source untouched at ce04dcb0. |
| Docking at 380px | **FAIL composed width**: final real minima airy **466x393**, standard **466x357**, tight **466x351**. Height demand fixed; untouched health_strip keeps the rail wider than 380. Owned mode/verb/TOKEN/card widths pass. |
| Inherited docking suite | **Qt NOT_RUN**, stock result 1 passed / 87 skipped; interpreter limitation below. Skips do not certify docking. |
| Expert pin / density rule | PASS, 2 / 16 respectively, targeted + full runs. No QSS/token/fontload changes. |
| Guard green / lowered residual | PASS guard + CAMERA-local ratchet; shared ceiling update deferred to its owner. Whole-panel primary count 348→296; grid 4→2. |
| Lifecycle / completion refresh / shelf untouched | PASS protected-source comparisons and diff proof below. |
| Full suite once / baseline floor | RUN: **6985 passed / 11 failed / 314 skipped**. Raw pass floor met; suite not green. Same eleven failures as inherited LEVER. |
| GUI H22.0.400 | **NOT_RUN, Joe's red gate**. Offscreen grabs are a diff instrument. |
| Required milestone commits | **BLOCKED**: Permission denied creating this worktree's index.lock. |

Panel source names below are relative to `python/synapse/panel/`.

## Final implementation choices and ownership limits

The contract's STATUS/REPORT workflow replaces a separate bus. No board or
other leg was edited. The actual visual shelf/header owner is synapse_panel;
the external `houdini/scripts/python/synapse_shelf.py` is untouched.

Only RecallCard is a new component. TOKEN reuses existing grid widgets, without
wrapper widgets or invented controls. Existing CHAT/TOKEN navigation now shares
the context row; the three profile pills occupy one row. This removes the
second tall tab row while preserving the manifests and all existing controls.
Expert's pin is a structural manifest claim, not pixel equivalence.

All removed layout gaps are replaced by roles on their owners. Nested anonymous
layouts inherit the owner's spacing; actual Qt verifies the header row. The
compositor is untouched. `_recompose` adds only a document rhythm refresh,
because QTextDocument spans are outside the QWidget walker. Existing
`CHAT_LEADING_PT` / `chat_leading_px()` supplies leading; typography and gaps
use the existing design tokens. Aa updates existing prompt text and subsequent
streamed characters independently of chrome. No font family or token was added.

Recall is display-only. Real producer: `server/handlers_memory.py:175` through
`session/tracker.py:596,617`, with `found/matches` and prose in `matches[].content`.
The adapter also accepts the brief's STATUS/payload shape. Explicit failure
outranks stale hit data; absent/malformed booleans remain UNKNOWN. A reported
hit with no body is HIT + UNKNOWN body. Only nonempty matching tool-use IDs
for `synapse_recall` associate existing conversation results. Request-only
tool_status events are never used as results. No query, store or worker added.

Strict ownership won over three impossible-to-hide raw-zero conflicts:

- The root installs the single `qss.stylesheet()`; no designsystem installer
  exists. Removing it removes the theme. It remains explicitly counted.
- The card's zero margins and inter-band spacing need two fixed-seam calls.
  The v2 spec explicitly separates fixed bands from the card collection role;
  every supplied role has a positive gap. These reason-tagged calls remain counted.
- LEVER's shared RESIDUAL.json is outside CAMERA's write set. A CAMERA test
  guards its exact residual. The orchestrator can lower the shared ceiling to
  **296 primary / 2 grid** before integration. This is not a silent waiver.

## Final census

Producer: unchanged `harness/notes/panel_rhythm_census.py:census`, invoked on
`python/synapse/panel`; measurement_complete=True, no errors. The CAMERA test
calls this same producer. No census artifact owned by CENSUS was overwritten.

| File | Before spacing / sheet / hex | After | Grid before→after |
|---|---|---|---|
| synapse_panel.py | 23 / 6 / 0 | 0 / 1 / 0 | 0→0 |
| face_token.py | 7 / 8 / 9 | 0 / 0 / 0 | 2→0 |
| chat_display.py | 0 / 2 / 0 | 0 / 0 / 0 | 0→0 |
| token_readout.py | 0 / 0 / 0 | unchanged | 0→0 |
| recall_card.py | absent | 2 / 0 / 0 | absent→0 |
| CAMERA | 30 / 16 / 9 | **2 / 1 / 0** | 2→0 |
| Whole panel | 107 / 106 / 135 | **79 / 91 / 126** | 4→2 |

Primary reduction **52** (348→296). TOKEN fallback colors now directly use
their existing named tokens: GROUND, SIGNAL, CONIFEROUS, MUSHROOM,
TEXT_TERTIARY. No new palette entry or color inference.

## Final validation and interpreter evidence

All Qt commands used QT_QPA_PLATFORM=offscreen, SYNAPSE_REDUCED_MOTION=1 and
PYTHONDONTWRITEBYTECODE=1. Stock Python has no PySide. Although PATH hython is
unbound and SYNAPSE_HYTHON initially unset, the shim found installed .400 and
actual offscreen Qt construction/grabs succeeded. Its pytest import is only
a namespace: `hython -m pytest` fails with `No module named pytest.__main__`,
and `pytest.mark` is absent. `hython -I` cannot find encodings. No dependency or
interpreter was installed/modified. CAMERA's stock-pytest wrapper explicitly
invokes its standalone Qt probe through SYNAPSE_HYTHON without -I on hython.
The inherited runner was not edited or falsely certified.

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:SYNAPSE_REDUCED_MOTION='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:SYNAPSE_HYTHON='C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe'
python -m pytest tests/test_panel_camera_rhythm.py tests/test_panel_camera_rhythm_qt.py tests/test_panel_rhythm_owner.py tests/test_rope_expert_pin.py tests/test_bp2_paneldesign_density.py tests/test_bp2_paneltruth_density_repolish.py tests/test_bp2_paneltruth_token_refresh.py tests/test_token_tab_usage.py tests/panel/test_chat_leading.py -q -p no:cacheprovider --tb=short
python -m pytest tests/test_panel_rhythm_docking.py -q -p no:cacheprovider --tb=short
```

Expanded targeted run: **119 passed, 9 skipped**. CAMERA: **41 pure checks and
3 real Qt probes pass**. Nine skips are older Qt tests inside stock Python,
not CAMERA's subprocess probes. Inherited docking: **1 passed, 87 skipped**.
After the final navigation move each standalone probe was rerun directly:
`& $env:SYNAPSE_HYTHON tests/test_panel_camera_rhythm_qt.py airy` (and standard,
tight). All exited 0 and emitted the final composed measurements above, with
scope explicitly limited to owned-component assertions.

| Deliberate mutation, restored byte-for-byte | Red control |
|---|---|
| recall_card: `if type(hit) is not bool:` → `if False:` | `test_recall_status_requires_measured_boolean`: **4 failed / 6 passed**, exit 1 |
| chat_display: `lead = t.chat_leading_px()` → `lead = 0` | Standalone airy Qt probe: lineHeight assertion failed, exit 1 |
| face_token: parm_row → group in existing grids/legend | Standalone standard Qt probe: value-parent role assertion failed, exit 1 |

Independent review reproduced and then verified fixes for malformed recall IDs,
malformed text blocks, lost error reasons, and grouped-header classification.
It found no additional blocker in those fixes; it did not run Qt or certify
composed docking. The Qt probes also cover neutral→BLOCKED→neutral repaint,
40px bands, long literal body text, UNKNOWN vs real zero, grouped body beginning
YOUR, header font, repeated profile changes, existing prompt font and the next
stream's character font. The initial leading test accidentally selected an
empty timestamp separator: it now selects the first nonempty reply and asserts
validity, without weakening the expected leading value. Real recompose-gap and
subsequent-stream font defects then went red and were fixed.

Full suite ran **once**, before the final review/layout fixes:

```powershell
$env:TEMP=Join-Path (Get-Location) '.tmp_camera'
$env:TMP=$env:TEMP
$env:TMPDIR=$env:TEMP
python -m pytest tests -q -p no:cacheprovider --basetemp .tmp_camera/full
```

Output: **11 failed, 6985 passed, 314 skipped, 84 warnings in 202.65s**.
Local log `.tmp_camera/full.txt`. Versus BASELINE.md: **+44 passes, +10 failures,
+122 skips**. Versus LEVER: +40 passes, same 11 failures, +3 Qt skips. It collected
the then-current 40 pure CAMERA tests; the extra malformed-input test and final
fixes were covered by later targeted runs. This is not a second full run.

Failure identities match REPORT_LEVER: backfill backup; M2 compose_parms_keep_tokens;
six orchestrate_close_gate cases; two orchestrate_liveness cases; ACL-denied
write-plane probe. No out-of-scope repair or weakened inherited assertion.
Their root causes and baseline-environment equivalence remain unverified.

## Protected-source and diff proof

Tests compare full method source against ce04dcb0 for `_on_done`,
`_refresh_token_surfaces`, `_show_token_face`, `_build_token_face`, `_start_worker`,
`_on_token`, `_on_error`, `_on_stop`, `_set_busy`, `closeEvent`, `showEvent`,
`_update_context`, `_update_health`. Constructors differ only by the root-sheet
exemption comment. FaceToken refresh_from_probe, _refresh_usage and measure_static
are byte-identical after newline normalization. No timer line changed.

`git diff ce04dcb0 -- python/synapse/panel/token_readout.py python/synapse/panel/claude_worker.py python/synapse/panel/designsystem/fontload.py python/synapse/panel/designsystem/tokens.py houdini/scripts/python/synapse_shelf.py`
emits no diff. The worker and shelf paths are untouched. Zero-context
synapse_panel diff hunk headers are appended below; no completion/timer hunk.

## GUI nits and handoff limits

- **Width 466px remains:** the rail includes untouched health_strip, already
  measured wider than 380 before LEVER. This is a documented ownership exemption,
  not an altered docking assertion. Other failing alternate widgets belong to
  sweeps or are unassigned and were left alone.
- At 380px the header's retained state/author/connection text can truncate.
  The one-row requirement, retained control set and host floor need Joe's eyes.
  PNGs expose it; it is not signed. The TOKEN light-background fallback found
  in the first after capture was fixed using the existing DsSection selector.
- Raw-zero remains blocked by three explicitly counted design-system/seam calls.
  Their owner/API location or acceptance needs resolution by the orchestrator.
- Host font provenance, full inherited Qt suite, live backend/result delivery,
  independent CRUX and GUI sign-off remain unverified. Fixtures prove display
  behavior, not live backend availability.

## Delivery receipt

Intended staging set: four production modules (synapse_panel, face_token,
chat_display, recall_card), two CAMERA test files, this REPORT, STATUS_CAMERA,
and twelve named PNGs. token_readout is already clean and unchanged. No other
tracked file was edited. Do not stage `.tmp_camera/` or generated PNG sidecar
JSONs. Before/after provenance and the capture recipe follow in the appendix.

Milestone staging/commit attempts failed with:

```text
fatal: Unable to create 'C:/Users/User/SYNAPSE/.git/worktrees/pd-panel-camera/index.lock': Permission denied
```

This is a filesystem denial, not an automatic approval-review rejection. No
ACL change, alternate index, permission bypass or out-of-worktree write was
attempted. Attempted subjects use `pd(camera):`; every commit command includes
`Co-Authored-By: Codex (gpt-6-astra) <noreply@openai.com>`. No CAMERA commit exists.
No merge, push, branch switch, release act or live Houdini GUI action occurred.

Receipt: `leg=panel_pd:CAMERA:BUILD`; `verdict=BLOCKED`; touched/commands/artifacts
above; `proved_it_bites` is the mutation table;
`could_not_verify=[Git delivery, strict raw-zero, composed docking, full inherited
Qt suite, live recall/backend availability, host-font provenance, Joe GUI sign-off,
independent CRUX, exact PID-to-worktree attribution, baseline-environment equivalence,
inherited failure root causes]`; `needs_human=[]` for gated repository acts.

## Appendix: initial planning and untouched-tree capture (historical)

## Grounding and implementation decisions

- The contract's ownership table is the write boundary. The real header/ribbon
  owner is `synapse_panel.py`; the external shelf launcher stays untouched.
- Use existing role QSS and `rhythm.apply` for layouts. Reuse existing widgets
  and layouts; the only new component is `recall_card.py`.
- Keep the existing `CHAT_LEADING_PT` / `chat_leading_px()` rule for replies;
  express document turn spacing through role gaps and token typography.
- Display actual recall results, including the existing `found/matches` server
  shape, without initiating recall or reading a store. Missing/malformed
  evidence remains UNKNOWN; explicit failure wins over stale hit data.
- Preserve lifecycle/timer methods and token completion refresh byte for byte.
- The root QSS installation is a census-counted call but is the single design
  system sheet, not a local style. A fixed card band seam also requires zero
  layout spacing, which no supplied role represents. Keep honest documented
  exemptions if these cannot be eliminated inside the write set. Do not hide
  calls from the census or edit LEVER-owned appliers.
- The residual ceiling belongs to LEVER/orchestrator; report the reduction and
  add a CAMERA-specific ratchet within the authorized test filename pattern.

## Untouched-tree screenshot milestone

`git status --short` was empty before capture. `hython ... --help` on PATH failed
because the command was unbound and `SYNAPSE_HYTHON` was unset. However,
`.synapse/hytest.py:find_hython()` found the installed H22.0.400 executable
(`C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe`).
Its `panel_shot.py --help` completed successfully. Stock Python has neither
PySide6 nor PySide2; offscreen hython is available in this session.

Before images were captured from untouched `ce04dcb0` with the original
`harness/notes/panel_shot.py` imported as a module. Its VIEWS list was narrowed
in memory to direct/TOKEN at 380x760 and each builder recomposed Curious,
Expert, or ML before grabbing. Six images, all six reported `ok`, under
`design/rhythm_pd/before/{curious,expert,ml}/`. This is an actual QWidget grab,
not fabricated content. The harness also writes its provenance manifests.
The original constructor attempted its usual external logging; the sandbox
denied `.synapse/logs/synapse.log`. No logging configuration or permission was
changed. GUI sign-off remains Joe's gate, not an offscreen claim.

Ownership sweep: `git worktree list` showed one CAMERA checkout; no previous
CAMERA STATUS existed. Process IDs were inspected; multiple other wave agents
exist, but no second CAMERA conductor was identified. Precise PID-to-worktree
attribution remains unverified.

## Capture recipe and final audit

Run the following on hython stdin after setting the headless environment shown
above. Before used the untouched ce04dcb0 tree and `before` output directory;
after uses the final working tree. The harness itself is unchanged.

```python
import importlib.util, logging, sys
logging.disable(logging.CRITICAL)
spec = importlib.util.spec_from_file_location('shot', 'harness/notes/panel_shot.py')
shot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shot)
for profile in ('curious', 'expert', 'ml'):
    def build(face, profile=profile):
        panel = shot._panel(face)
        panel._layout_profile = profile
        panel._mark_profile_pill(profile)
        panel._recompose(profile)
        return panel
    shot.VIEWS = [('panel_direct', lambda: build('direct'), (380, 760)),
                  ('panel_token', lambda: build('token'), (380, 760))]
    sys.argv = ['panel_shot.py', '--out', 'design/rhythm_pd/after/' + profile]
    assert shot.main() == 0
```

Final-source recheck, after the navigation move and last screenshot refresh:
`python -m pytest tests/test_panel_camera_rhythm.py tests/test_panel_rhythm_owner.py tests/test_rope_expert_pin.py tests/test_bp2_paneldesign_density.py -q -p no:cacheprovider --tb=short`
returned **83 passed**. The three standalone real Qt density probes also passed
after that move. The refreshed TOKEN image was visually inspected to verify
the light-background fallback was gone. GUI approval remains unclaimed.

## Actual zero-context panel diff

Producer: `git diff ce04dcb0 --unified=0 -- python/synapse/panel/synapse_panel.py`.

```diff
diff --git a/python/synapse/panel/synapse_panel.py b/python/synapse/panel/synapse_panel.py
index 5a946678..a6b99a29 100644
--- a/python/synapse/panel/synapse_panel.py
+++ b/python/synapse/panel/synapse_panel.py
@@ -333 +333 @@ class SynapsePanel(QtWidgets.QWidget):
-        self.setStyleSheet(qss.stylesheet(self._chrome_scale))
+        self.setStyleSheet(qss.stylesheet(self._chrome_scale))  # rhythm-exempt: installs the sole designsystem sheet at the root; no local style
@@ -478,0 +479 @@ class SynapsePanel(QtWidgets.QWidget):
+        w.setProperty("rhythm_role", "group")
@@ -484,2 +485 @@ class SynapsePanel(QtWidgets.QWidget):
-        root.setContentsMargins(0, 0, 0, 0)
-        root.setSpacing(0)
+        self.setProperty("rhythm_role", "group")
@@ -599,0 +600,5 @@ class SynapsePanel(QtWidgets.QWidget):
+        # QTextDocument spans are outside the QWidget role walker. Reapply
+        # their group gaps after the same cached-widget recomposition.
+        chat = getattr(self, "_chat", None)
+        if chat is not None and hasattr(chat, "_apply_turn_rhythm"):
+            chat._apply_turn_rhythm()
@@ -611,3 +616,2 @@ class SynapsePanel(QtWidgets.QWidget):
-        One strip replacing the old header AND footer: the mark-as-status +
-        wordmark + state phrase on top; connection, an activity meter, and Stop
-        beneath. Termination and live state never scroll away.
+        One row of existing identity/actions, with the persistent health strip
+        beneath it. Termination and live state never scroll away.
@@ -621,5 +625 @@ class SynapsePanel(QtWidgets.QWidget):
-        # Comp row-1 padding: 16 / GUTTER / 14 (the confident header air).
-        col.setContentsMargins(t.GUTTER, 16, t.GUTTER, 14)
-        col.setSpacing(t.SPACE_SM)
-
-        # line 1 — identity + selection + state (comp order):
+        # The owning widget's role supplies margins and inherited row gaps.
@@ -628 +627,0 @@ class SynapsePanel(QtWidgets.QWidget):
-        top.setSpacing(t.SPACE_SM)
@@ -655 +654 @@ class SynapsePanel(QtWidgets.QWidget):
-        word.setStyleSheet("color:%s;" % t.TEXT_BRIGHT)
+        word.setProperty("role", "title")
@@ -660 +659 @@ class SynapsePanel(QtWidgets.QWidget):
-        self._header_status.setStyleSheet("color:%s;" % t.TEXT_SECONDARY)
+        self._header_status.setProperty("role", "label")
@@ -703 +701,0 @@ class SynapsePanel(QtWidgets.QWidget):
-        top.addSpacing(t.SPACE_XS)        # a beat between the mark and the wordmark
@@ -711 +708,0 @@ class SynapsePanel(QtWidgets.QWidget):
-        col.addLayout(top)
@@ -713,4 +710,2 @@ class SynapsePanel(QtWidgets.QWidget):
-        # line 2 — connection · corpus · activity strip (kept-for-now: not in
-        # the comp, not ratified out — retiring it is a future owner call).
-        bot = QtWidgets.QHBoxLayout()
-        bot.setSpacing(t.SPACE_SM)
+        # Existing connection/corpus controls join the same header row.
+        bot = top  # one header row; the persistent health strip remains below
@@ -719 +714 @@ class SynapsePanel(QtWidgets.QWidget):
-        self._foot_label.setStyleSheet("color:%s;" % t.TEXT_TERTIARY)
+        self._foot_label.setProperty("role", "caption")
@@ -727 +722,2 @@ class SynapsePanel(QtWidgets.QWidget):
-        self._help_btn = c.Button("Help", variant="primary")
+        self._help_btn = c.Button("?", variant="ghost")
+        self._help_btn.setAccessibleName("Open documentation")
@@ -756 +751,0 @@ class SynapsePanel(QtWidgets.QWidget):
-        bot.addSpacing(t.SPACE_MD)
@@ -770,0 +766,8 @@ class SynapsePanel(QtWidgets.QWidget):
+        w.setProperty("rhythm_role", "parm_row")
+        for control in (self._connect_btn, self._corpus_btn, self._help_btn, overflow):
+            control.setObjectName("DsVerb")
+            control.setProperty("rhythm_role", "label")
+        overflow.setFixedWidth(t.SPACE_LG)
+        for label in (self._header_status, self._foot_label, self._meter_lbl,
+                      self._palette_hint, self._author_lbl):
+            label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
@@ -933,3 +936 @@ class SynapsePanel(QtWidgets.QWidget):
-        # L5-17: left inset = t.GUTTER, the same token the tab row applies, so
-        # the .hip filename's first glyph sits on the same vertical as CHAT.
-        lay.setContentsMargins(t.GUTTER, t.SPACE_SM, t.SPACE_MD, t.SPACE_SM)
+        # The section role owns the ribbon's spacing.
@@ -937,2 +938,4 @@ class SynapsePanel(QtWidgets.QWidget):
-        lay.addWidget(self._ctx_label)
-        lay.addStretch(1)
+        self._ctx_label.setObjectName("DsContextLabel")
+        self._ctx_label.setProperty("rhythm_role", "label")
+        self._ctx_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
+        lay.addWidget(self._ctx_label, 1)
@@ -994,2 +997 @@ class SynapsePanel(QtWidgets.QWidget):
-        lay.setContentsMargins(t.GUTTER, 24, t.GUTTER, 0)
-        lay.setSpacing(28)
+        navigation = self._build_context_ribbon().layout()
@@ -1002 +1004 @@ class SynapsePanel(QtWidgets.QWidget):
-        lay.addWidget(pill)
+        navigation.addWidget(pill)
@@ -1015,3 +1017 @@ class SynapsePanel(QtWidgets.QWidget):
-        lay.addWidget(tok)
-
-        lay.addStretch(1)
+        navigation.addWidget(tok)
@@ -1029,0 +1030 @@ class SynapsePanel(QtWidgets.QWidget):
+            p.setProperty("rhythm_role", "row")
@@ -1104,2 +1104,0 @@ class SynapsePanel(QtWidgets.QWidget):
-        col.setContentsMargins(t.GUTTER, 24, t.GUTTER, 24)
-        col.setSpacing(0)
@@ -1106,0 +1106,4 @@ class SynapsePanel(QtWidgets.QWidget):
+        from synapse.panel.recall_card import RecallCard
+        self._recall_card = RecallCard()
+        self._recall_card.hide()
+        col.addWidget(self._recall_card)
@@ -1107,0 +1111 @@ class SynapsePanel(QtWidgets.QWidget):
+        col.addWidget(c.divider())
@@ -1124,2 +1127,0 @@ class SynapsePanel(QtWidgets.QWidget):
-        col.setContentsMargins(0, 0, 0, 0)
-        col.setSpacing(0)
@@ -1136 +1137,0 @@ class SynapsePanel(QtWidgets.QWidget):
-            _l.setContentsMargins(t.SPACE_MD, t.SPACE_SM, t.SPACE_MD, t.SPACE_SM)
@@ -1168 +1168,0 @@ class SynapsePanel(QtWidgets.QWidget):
-        col.setContentsMargins(t.SPACE_MD, t.SPACE_SM, t.SPACE_MD, t.SPACE_SM)
@@ -1593,0 +1594,4 @@ class SynapsePanel(QtWidgets.QWidget):
+        from synapse.panel.recall_card import latest_recall_result
+        result = latest_recall_result(getattr(self, "_messages", ()))
+        if result is not None:
+            self._display_recall_result(result)
@@ -1698,2 +1701,0 @@ class SynapsePanel(QtWidgets.QWidget):
-        lay.setContentsMargins(t.SPACE_MD, t.SPACE_MD, t.SPACE_MD, t.SPACE_MD)
-        lay.setSpacing(t.SPACE_SM)
@@ -1711 +1712,0 @@ class SynapsePanel(QtWidgets.QWidget):
-        row.setSpacing(t.SPACE_SM)
@@ -1792,0 +1794 @@ class SynapsePanel(QtWidgets.QWidget):
+        btn.setProperty("rhythm_role", "label")
@@ -1807,7 +1809 @@ class SynapsePanel(QtWidgets.QWidget):
-        # face carries GUTTER/24; L5-17: top steps SPACE_SM→SPACE_MD (next rung
-        # on the tokens scale) — air between the verbs and the rule above them.
-        lay.setContentsMargins(0, t.SPACE_MD, 0, t.SPACE_SM)
-        # L5-21: inter-verb gap steps SPACE_MD→SPACE_LG (one rung = the ladder's
-        # double) so EXPLAIN / FIX / OPTIMIZE / BUILD HDA read as four controls,
-        # not one phrase.
-        lay.setSpacing(t.SPACE_LG)
+        # The group role owns inter-verb gaps; DsVerb remains the text action.
@@ -1832,2 +1827,0 @@ class SynapsePanel(QtWidgets.QWidget):
-        col.setContentsMargins(0, 0, 0, 0)   # the Direct face carries the GUTTER/24
-        col.setSpacing(t.SPACE_XS)
@@ -1835,4 +1829,2 @@ class SynapsePanel(QtWidgets.QWidget):
-        # The prompt scales with the Aa content scale via a widget-level sheet
-        # (overrides the root QSS font-size for this widget only); chrome stays put.
-        self._input.setStyleSheet("QTextEdit#DsInput { font-size: %dpx; }"
-                                  % t.scaled(t.SIZE_UI, self._font_scale))
+        # Aa scales document text; the inherited root sheet owns the chrome.
+        self._set_prompt_font(self._input, self._font_scale)
@@ -1845,3 +1837 @@ class SynapsePanel(QtWidgets.QWidget):
-        row.setSpacing(t.SPACE_SM)
-        # Image-attach: a drawn image glyph, NOT an emoji (the bundled mono font
-        # has no pictographs → a paperclip codepoint renders as an unreadable tofu box).
+        # Image attachment uses the existing drawn glyph.
@@ -2014,0 +2005,6 @@ class SynapsePanel(QtWidgets.QWidget):
+    def _display_recall_result(self, result):
+        card = getattr(self, "_recall_card", None)
+        if card is not None:
+            card.set_result(result)
+            card.show()
+
@@ -2015,0 +2012,2 @@ class SynapsePanel(QtWidgets.QWidget):
+        if tool_name == "synapse_recall":
+            self._display_recall_result(result)
@@ -2077,3 +2075,2 @@ class SynapsePanel(QtWidgets.QWidget):
-        prompt input. The prompt uses a widget-level stylesheet — a widget's own
-        sheet overrides the inherited root QSS font-size for that widget only, so
-        the chrome around it stays put. Defensive: safe before either is built."""
+        prompt input. Document fonts keep content scaling independent of the
+        root chrome stylesheet. Defensive: safe before either is built."""
@@ -2090,2 +2087 @@ class SynapsePanel(QtWidgets.QWidget):
-                inp.setStyleSheet("QTextEdit#DsInput { font-size: %dpx; }"
-                                  % t.scaled(t.SIZE_UI, sc))
+                self._set_prompt_font(inp, sc)
@@ -2094,0 +2091,14 @@ class SynapsePanel(QtWidgets.QWidget):
+    @staticmethod
+    def _set_prompt_font(inp, scale):
+        font = QtGui.QFont(inp.font())
+        font.setPixelSize(max(t.FONT_FLOOR_PX, t.scaled(t.SIZE_UI, scale)))
+        inp.document().setDefaultFont(font)
+        selection = inp.textCursor()
+        content = QtGui.QTextCursor(inp.document())
+        content.select(QtGui.QTextCursor.Document)
+        fmt = QtGui.QTextCharFormat()
+        fmt.setFont(font)
+        content.mergeCharFormat(fmt)
+        inp.setTextCursor(selection)
+        inp.setCurrentFont(font)
+
```

## PNG integrity inventory

| Image | Bytes | Pixels | SHA-256 |
|---|---:|---|---|
| design/rhythm_pd/before/curious/panel_direct.png | 21681 | 380x760 | 09ad16d670d414be3393a0b8d371a48cc452828addaf4e73c06d26b37eac8cb1 |
| design/rhythm_pd/before/curious/panel_token.png | 29973 | 380x760 | 8e6fa7c24320c2a47814108b69452d6f47803b907dce413f447e87c3f20756ee |
| design/rhythm_pd/before/expert/panel_direct.png | 21496 | 380x760 | fdaceb35a068e4bb2ee980d44e798fe4a353dd13952679b4fa9e9e9e6bb5595e |
| design/rhythm_pd/before/expert/panel_token.png | 29734 | 380x760 | 909161d8763ad78b82cd5a5a18e3877af88de84f2fc52c765cecc3fb6c917475 |
| design/rhythm_pd/before/ml/panel_direct.png | 21388 | 380x760 | 81def6cef918531dad4fe81626c0c310e1e58e81a6d8a8a0de1abd610751f278 |
| design/rhythm_pd/before/ml/panel_token.png | 29699 | 380x760 | 0ad455ead5a326e920b21052195039da5e8521ec15e0d5fdfbe1dd2ca81a75b7 |
| design/rhythm_pd/after/curious/panel_direct.png | 20561 | 380x760 | 5b534ccf63eb6bbf09bc0bc269a03f3bfa39e5bb074ca1049fd07ce5569f2804 |
| design/rhythm_pd/after/curious/panel_token.png | 28397 | 380x760 | 95c07ed803f67a2ac092454d44f7c4fc605bf0f44661be015934eb2c80184494 |
| design/rhythm_pd/after/expert/panel_direct.png | 20474 | 380x760 | 154a2f0639f87389d2eba36f23073dfc8222d8c061178db066b9f09146938be0 |
| design/rhythm_pd/after/expert/panel_token.png | 27358 | 380x760 | cbc701b290518674f47630f30fa2a6245f91454b55a21f3841e1677573361cf9 |
| design/rhythm_pd/after/ml/panel_direct.png | 20440 | 380x760 | 13f4f4f7d07b9b6b80c556fd5ba4a2e75d12b5ba38e1df798122983d44d55810 |
| design/rhythm_pd/after/ml/panel_token.png | 28376 | 380x760 | 5df90a266c6ebcbf996a84252266c32a1412eb05560570abb0bdee35df3da94b |
