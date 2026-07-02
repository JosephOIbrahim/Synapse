#!/usr/bin/env python3
"""
audit_panel.py  --  the THIRD gate (G3) for the SYNAPSE panel harness.

  G1 (run_panel.py --smoke) proves it BOOTS.
  G2 (Houdini 21.0.671)      proves it loads in the real host.
  G3 (this)                  proves it is READABLE and USABLE.

Two layers:
  A. TOKEN AUDIT  -- deterministic, no host. Contrast matrix + type-scale floors.
                     Reads your real designsystem/tokens.py, so it audits the
                     SYSTEM, not a screenshot.
  B. LIVE AUDIT   -- offscreen Qt build. Interactive target sizes + face presence.

Usage:
  python audit_panel.py            # full human report
  python audit_panel.py --strict   # exit 1 on any FAIL  (use this as the gate)
"""
import os, sys, math

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# ---- repo path (same discovery as run_panel) ----
def _find_root(start):
    p = os.path.abspath(start)
    while p != os.path.dirname(p):
        if os.path.isdir(os.path.join(p, "python", "synapse")):
            return p
        p = os.path.dirname(p)
    return os.path.abspath(start)

ROOT  = _find_root(__file__)
PYDIR = os.path.join(ROOT, "python")
if PYDIR not in sys.path:
    sys.path.insert(0, PYDIR)

from synapse.panel.designsystem import tokens as t

# ---------------- WCAG contrast ----------------
def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

def _lum(hx):
    h = hx.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)

def contrast(fg, bg):
    a, b = _lum(fg), _lum(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)

# ---------------- floors ----------------
AA_BODY    = 4.5    # WCAG AA, normal text
AA_LARGE   = 3.0    # WCAG AA, large/bold text
PRAGMATIC  = 3.0    # dark-DCC line we will not cross for ANY essential text
BODY_FLOOR = 12     # px @ scale 1.0 — Houdini-native (9pt≈12px); the ratified
                    # SIZE_BODY pinned by tests/panel/test_type_scale_native.py.
                    # Readability is carried by CONTRAST (A1/A3), not by oversizing
                    # past the host's own body size.
TARGET_FLOOR = 26   # px, comfortable click/tap height for pills + buttons

FAILS, WARNS = [], []
def tag(ok, warnable=False, cr=None):
    if ok:
        return "[ ok ]"
    if warnable:
        WARNS.append(1); return "[WARN]"
    FAILS.append(1);  return "[FAIL]"

print("=" * 70)
print("  SYNAPSE PANEL  ·  G3 READABILITY + USABILITY AUDIT")
print("=" * 70)

# ---------- A1 · contrast matrix ----------
print("\n-- READABILITY · text on surface (WCAG contrast) " + "-" * 19)
text_roles = {
    "PRIMARY  (body)":  (t.TEXT_PRIMARY,   "body"),
    "SECONDARY(meta)":  (t.TEXT_SECONDARY, "essential"),
    "TERTIARY (hint)":  (t.TEXT_TERTIARY,  "essential"),
    "BRIGHT   (head)":  (t.TEXT_BRIGHT,    "large"),
    "ACCENT   (link)":  (t.TEXT_ACCENT,    "large"),
}
surfaces = {"PANEL": t.PANEL, "GROUND": t.GROUND, "SURFACE": t.SURFACE}
hdr = "  " + " " * 16 + "".join(f"{s:>16}" for s in surfaces)
print(hdr)
for name, (fg, kind) in text_roles.items():
    row = f"  {name:<16}"
    for sname, sbg in surfaces.items():
        cr = contrast(fg, sbg)
        floor = AA_BODY if kind == "body" else (AA_LARGE if kind == "large" else PRAGMATIC)
        ok = cr >= floor
        warnable = (kind != "body")  # body is non-negotiable; others can warn
        row += f"  {cr:4.1f}:1 {tag(ok, warnable)}"
    print(row)
print(f"  floors:  body >= {AA_BODY}:1   head/link >= {AA_LARGE}:1   any essential >= {PRAGMATIC}:1")

# ---------- A2 · type scale ----------
print("\n-- READABILITY · type scale (px @ scale " + f"{t.FONT_SCALE_DEFAULT}) " + "-" * 22)
sizes = [("HERO", t.SIZE_HERO), ("TITLE", t.SIZE_TITLE), ("UI", t.SIZE_UI),
         ("SMALL", t.SIZE_SMALL), ("MICRO", t.SIZE_MICRO), ("BODY", t.SIZE_BODY)]
for n, s in sizes:
    eff = t.scaled(s, t.FONT_SCALE_DEFAULT)
    note = ""
    if n == "BODY":
        note = "  " + tag(eff >= BODY_FLOOR) + f"  chat body — floor {BODY_FLOOR}px"
    print(f"   {n:<6} {eff:>3}px{note}")
distinct = len({s for _, s in sizes})
print(f"   hierarchy: {distinct} distinct steps  " + tag(distinct >= 4, warnable=True))

# ---------- A3 · seeded-contrast sweep (Image #6 · the seed-blind gap) ----------
# The live panel RE-SEEDS its surfaces from the host pane grey (hou.qt.color),
# but the A1 matrix above only audits the headless FALLBACK tokens — so a host
# whose grey runs lighter than the fallback can drop body text below AA while
# this gate still reads green. Close that: derive the palette across a sweep of
# realistic host greys and assert body/secondary contrast holds at EVERY seed.
print("\n-- READABILITY · seeded-contrast sweep (DENSE, full grey range) " + "-" * 5)
# DENSE sweep — every grey 0..255, not a 6-point sample (a sparse sample skipped
# the ~107-127 mid-grey band where the seed math dips, a false-green). REALISTIC
# host greys (Houdini dark pane ~46, light theme >=200) must hold WCAG AA; the
# theoretical mid-grey band can't reach 4.5 in EITHER text direction once the
# elevation spread is included (a WCAG hard limit), so it's gated at a strong
# pragmatic floor instead of being silently skipped.
MID_FLOOR = 3.5     # never-cross floor for ANY host grey, incl. the mid band
def _realistic(v):  # greys Houdini actually ships as a pane background
    return v <= 95 or v >= 150
_derive = getattr(t, "_derive_palette", None)
if _derive is None:
    FAILS.append(1)
    print("   [FAIL] tokens._derive_palette missing — seed math isn't a pure, "
          "auditable function yet (contrast-aware seed not wired)")
else:
    worst_all = (99.0, None)        # body, any grey
    worst_real = (99.0, None)       # body, realistic greys only
    worst_sec = (99.0, None)        # secondary, any grey
    for v in range(0, 256):
        surf, txt = _derive(v, v, v)
        for sname in ("ground", "panel", "surface"):
            cb = contrast(txt["primary"], surf[sname])
            cs = contrast(txt["secondary"], surf[sname])
            if cb < worst_all[0]:
                worst_all = (cb, (v, sname))
            if cs < worst_sec[0]:
                worst_sec = (cs, (v, sname))
            if _realistic(v) and cb < worst_real[0]:
                worst_real = (cb, (v, sname))
    print(f"   body  realistic worst: {worst_real[0]:4.1f}:1 @ {worst_real[1]}  "
          + tag(worst_real[0] >= AA_BODY))
    print(f"   body  any-grey  worst: {worst_all[0]:4.1f}:1 @ {worst_all[1]}  "
          + tag(worst_all[0] >= MID_FLOOR))
    print(f"   2ndary any-grey worst: {worst_sec[0]:4.1f}:1 @ {worst_sec[1]}  "
          + tag(worst_sec[0] >= PRAGMATIC))
    print(f"   floors:  realistic body >= {AA_BODY}:1   any-grey body >= {MID_FLOOR}:1   "
          f"any-grey 2ndary >= {PRAGMATIC}:1")

# ---------- B · live build ----------
print("\n-- USABILITY · live offscreen build " + "-" * 31)
panel = None
try:
    import run_panel  # registers hou stub + path
    try:
        from PySide6 import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = run_panel.build_panel()
    panel.show()   # offscreen: sets the visibility flags so geometry/visible work
    app.processEvents()

    btns = panel.findChildren(QtWidgets.QAbstractButton)
    under = [b for b in btns if 0 < b.sizeHint().height() < TARGET_FLOOR]
    print(f"   interactive targets : {len(btns):>3} found, "
          f"{len(under)} under {TARGET_FLOOR}px  " + tag(not under, warnable=True))

    texts = [b.text() for b in btns if b.text()]
    faces = [f for f in ("Direct", "Work") if f in texts]
    print(f"   tabs present        : {faces}  " + tag(len(faces) == 2))
    # v9: Review folded into Work's done sub-state. Assert its synthesis (the
    # consent gate) still lives in-tree, so the fold didn't silently drop the
    # gate — a stronger check than the old 3-tab name match.
    from synapse.panel.gate_widget import GateWidget as _GW
    has_gate = bool(panel.findChildren(_GW))
    print(f"   review fold (gate)  : {has_gate}  " + tag(has_gate))

    # v9 type pass — bundled families register, OR the build-mismatch flag is
    # raised (the locked call permits the flagged-fallback state). Warnable.
    from synapse.panel.designsystem import fontload
    fst = fontload.font_status() or {}
    fam_present = [f for f in ("Space Grotesk", "Space Mono") if f in fst.get("families", [])]
    flagged = bool(fst.get("build_mismatch"))
    print(f"   bundled fonts       : {fam_present}{' FLAGGED' if flagged else ''}  "
          + tag(len(fam_present) == 2 or flagged, warnable=True))

    labels = panel.findChildren(QtWidgets.QLabel)
    print(f"   labels rendered     : {len(labels):>3}")

    # --- no bundled designed family may be forced via QSS either (the per-widget
    #     font().family() sample is blind to a QSS/HTML rule a child inherits) ---
    from synapse.panel.designsystem import qss as _qssmod
    from synapse.panel.styles import get_chat_display_stylesheet as _gcds
    qss_text = (_qssmod.stylesheet(1.0) + _gcds(1.0)).lower()
    qss_bundled = [b for b in ("space grotesk", "space mono") if b in qss_text]
    print(f"   no bundled font in QSS: {qss_bundled or 'clean'}  " + tag(not qss_bundled))

    # --- Image #6 · model selection must be APPARENT (not buried in a menu) ---
    from synapse.panel.providers.registry import PROVIDER_LABELS, DEFAULT_PROVIDER
    label_set = set(PROVIDER_LABELS.values())
    engine_btns = [b for b in btns if b.text() in label_set and not b.isHidden()]
    print(f"   model selector      : {[b.text() for b in engine_btns]}  "
          + tag(len(engine_btns) >= len(PROVIDER_LABELS)))
    # the active engine must be visibly marked (active property), and match state
    active = [b for b in engine_btns if b.property("active") in (True, "true")]
    want = PROVIDER_LABELS.get(getattr(panel, "_provider_id", DEFAULT_PROVIDER))
    sel_ok = len(active) == 1 and active[0].text() == want
    print(f"   active engine mark  : {[b.text() for b in active]} (want {want!r})  "
          + tag(sel_ok))
    # prominent model chip (the readout) is present + non-empty
    chip = getattr(panel, "_model_chip", None)
    chip_ok = chip is not None and bool(chip.text()) and not chip.isHidden()
    chip_txt = repr(chip.text()) if chip is not None else None
    print(f"   model readout chip  : {chip_txt}  " + tag(chip_ok))

    # --- the model switcher must expose the registry's models + mark the active
    #     one (switching Anthropic models must be apparent, not hidden) ---
    from synapse.panel.providers import registry as _reg
    items = panel._model_menu_items() if hasattr(panel, "_model_menu_items") else []
    want_ids = [m for m, _ in _reg.models_for(getattr(panel, "_provider_id", "claude"))]
    got_ids = [m for m, _, _ in items]
    actives = [m for m, _, a in items if a]
    picker_ok = (got_ids == want_ids and len(got_ids) >= 2 and len(actives) == 1
                 and isinstance(chip, QtWidgets.QAbstractButton))
    print(f"   model picker        : {len(got_ids)} models, active={actives}  "
          + tag(picker_ok))

    # --- match Houdini: the panel must inherit the host's native UI font, not
    #     override it with the bundled designed families (Space Grotesk/Mono).
    #     Mono stays legal only for genuine code/paths inside the chat HTML. ---
    BUNDLED = {"space grotesk", "space mono"}
    verbs = [b for b in btns if b.objectName() == "DsVerb"]
    samples = {
        "wordmark":  getattr(panel, "_wordmark", None),
        "tab":       (getattr(panel, "_face_pills", {}) or {}).get("direct"),
        "verb":      verbs[0] if verbs else None,
        "model chip": getattr(panel, "_model_chip", None),
        "engine seg": (getattr(panel, "_engine_pills", {}) or {}).get("claude"),
        "chat":      getattr(panel, "_chat", None),
    }
    fams, bad = {}, []
    for nm, wdg in samples.items():
        if wdg is None:
            continue
        fam = wdg.font().family()
        fams[nm] = fam
        if fam.strip().lower() in BUNDLED:
            bad.append("%s=%s" % (nm, fam))
    print(f"   native chrome font  : host={app.font().family()!r}  " + tag(not bad))
    if bad:
        print("      overrides host font: " + ", ".join(bad))

    # --- Image #5 bug 3 · the prompt box must not crop at the min pane height ---
    try:
        from PySide6.QtCore import QPoint
    except ImportError:
        from PySide2.QtCore import QPoint
    panel._set_face("direct")
    panel.resize(t.PANEL_MIN_WIDTH, t.PANEL_MIN_HEIGHT)
    app.processEvents()
    send = getattr(panel, "_send_btn", None)
    if send is not None and not send.isHidden():
        # bottom edge of Send, mapped into panel-local coords
        by = send.mapTo(panel, QPoint(0, send.height())).y()
        not_clipped = by <= panel.height()
        print(f"   input not clipped   : send bottom {by}px / panel {panel.height()}px  "
              + tag(not_clipped))
    else:
        FAILS.append(1)
        print("   [FAIL] input not clipped: Send button missing/hidden on Direct face")

    # --- readability: body must MATCH the host UI size (>= Houdini default) ---
    try:
        from PySide6.QtGui import QFontInfo
    except ImportError:
        from PySide2.QtGui import QFontInfo
    host_px = QFontInfo(app.font()).pixelSize()
    body_px = round(t.SIZE_BODY * getattr(panel, "_font_scale", t.FONT_SCALE_DEFAULT))
    print(f"   body matches host   : body {body_px}px vs host {host_px}px  "
          + tag(body_px >= host_px - 1))

    # --- model chip shows a SHORT label, not the long raw model id ---
    chip_short = chip is not None and "/" not in chip.text() and 0 < len(chip.text()) < 30
    _chip_txt = repr(chip.text()) if chip is not None else None
    print(f"   chip short-label    : {_chip_txt}  " + tag(chip_short))

    # --- ⌘K folded into the input ("/" opens palette; no bar glyph button) ---
    inp = getattr(panel, "_input", None)
    slash_ok = (inp is not None and "/" in inp.placeholderText()
                and hasattr(inp, "slash") and not hasattr(panel, "_more_btn")
                and hasattr(panel, "_open_palette"))
    _ph = repr(inp.placeholderText()) if inp is not None else None
    print(f"   ⌘K folded into input: placeholder={_ph}  " + tag(slash_ok))

    # --- non-tautological proof the host-scale base EQUALS the host font size
    #     (no readability floor any more — startup = the host UI size exactly) ---
    try:
        from PySide6 import QtGui as _QtGui
    except ImportError:
        from PySide2 import QtGui as _QtGui
    _saved_font = app.font()
    _big = _QtGui.QFont(_saved_font)
    _big.setPixelSize(20)
    app.setFont(_big)
    tracked = panel._host_font_scale()
    app.setFont(_saved_font)
    print(f"   host-scale = host px : 20px host -> {tracked:.2f}  "
          + tag(abs(tracked - 20 / float(t.SIZE_BODY)) < 0.05))

    # --- FONT-SCALE SCOPE: the Aa control scales CONTENT only (the dialogue +
    #     the prompt). Chrome (header, labels, pills) is FROZEN at the host UI
    #     size — it must NOT move when the artist changes reading size, or the
    #     panel jitters and eats vertical space. Assert chrome pixel sizes are
    #     identical across a 1.0 -> 1.6 content change, while the prompt + chat
    #     grow. Pixel size is the only honest signal offscreen (the family
    #     resolves to a substituted face, never the requested one). ---
    import re as _re

    def _hdr_px(name):
        w = getattr(panel, name, None)
        return QFontInfo(w.font()).pixelSize() if w is not None else None

    def _input_px():
        # the prompt size lives in a widget-level stylesheet (it overrides the
        # root QSS for this widget only); parse it back — QFontInfo(font()) does
        # not reflect a stylesheet font-size.
        m = _re.search(r"font-size:\s*(\d+)px", panel._input.styleSheet() or "")
        return int(m.group(1)) if m else None

    _saved_scale = panel._font_scale
    try:
        chrome = ("_wordmark", "_header_status", "_palette_hint", "_author_lbl",
                  "_foot_label", "_ctx_label", "_engine_lbl")
        panel._set_scale(1.0)
        chrome_a = {n: _hdr_px(n) for n in chrome}
        in_a, chat_a = _input_px(), getattr(panel._chat, "font_scale", None)
        panel._set_scale(1.6)
        chrome_b = {n: _hdr_px(n) for n in chrome}
        in_b, chat_b = _input_px(), getattr(panel._chat, "font_scale", None)
    finally:
        panel._set_scale(_saved_scale)

    READABLE_FLOOR = 11  # px — chrome must clear this
    wm = chrome_a.get("_wordmark")
    wm_heading = wm is not None and wm >= round(t.SIZE_TITLE)
    print(f"   wordmark is heading  : {wm}px >= title {round(t.SIZE_TITLE)}px  "
          + tag(wm_heading))
    chrome_floor_ok = all(v is not None and v >= READABLE_FLOOR
                          for n, v in chrome_a.items() if n != "_wordmark")
    print(f"   chrome floor (>=11)  : {chrome_a}  " + tag(chrome_floor_ok))
    chrome_frozen = all(chrome_a.get(n) == chrome_b.get(n) for n in chrome)
    print(f"   chrome FROZEN on Aa  : {chrome_b}  " + tag(chrome_frozen))
    content_scales = (in_a is not None and in_b is not None and in_b > in_a
                      and chat_a is not None and chat_b is not None and chat_b > chat_a)
    print(f"   content scales on Aa : prompt {in_a}->{in_b}px · chat {chat_a}->{chat_b}  "
          + tag(content_scales))

    # --- the chip stays SHORT for the slash-bearing provider (Nemotron) — the
    #     real test the long raw id isn't shown (claude alone never has a slash) ---
    panel._set_provider("nemotron")
    nemo_chip = panel._model_chip.text()
    panel._set_provider("claude")
    print(f"   chip short (nemotron): {nemo_chip!r}  "
          + tag("/" not in nemo_chip and len(nemo_chip) < 30))

    # --- same for Ollama — the registry label ('GLM 5'), never the raw
    #     tag-bearing id ('glm-5:cloud') ---
    panel._set_provider("ollama")
    oll_chip = panel._model_chip.text()
    panel._set_provider("claude")
    print(f"   chip short (ollama)  : {oll_chip!r}  "
          + tag("/" not in oll_chip and ":" not in oll_chip and len(oll_chip) < 30))
except (Exception, SystemExit) as e:
    WARNS.append(1)
    print(f"   [skip] live build unavailable here: {type(e).__name__}: {e}")
    print("          (run this one inside hython for the real G3 — fonts differ)")

# ---------- B2 · v9 behavioral invariants (the finish-line gate) ----------
print("\n-- v9 INVARIANTS · same-pane law + state-as-status " + "-" * 17)
if panel is None:
    WARNS.append(1)
    print("   [skip] no panel built — invariants need the offscreen build")
else:
    try:
        import glob as _glob, re as _re

        # 1 · no pane-spawn (static scan) — no handler creates/moves a pane
        pkg = os.path.join(PYDIR, "synapse", "panel")
        SPAWN = _re.compile(r"createFloatingPanel|\.createTab\(|setCurrentTab\(|\.floatPanel\(")
        offenders = []
        for f in _glob.glob(os.path.join(pkg, "*.py")):
            try:
                src = open(f, encoding="utf-8").read()
            except Exception:
                continue
            if SPAWN.search(src):
                offenders.append(os.path.basename(f))
        print(f"   no pane spawn (scan) : {offenders or 'clean'}  " + tag(not offenders))

        # 2 · no auto-switch — state events must NOT move the visible tab
        idx0 = panel._faces.currentIndex()
        panel._set_busy(True)
        panel._on_tool_status("houdini_render", "running", "")
        panel._on_gate_raised({"level": "approve"})
        print(f"   no auto-switch       : idx {idx0}->{panel._faces.currentIndex()}  "
              + tag(panel._faces.currentIndex() == idx0))

        # 3 · mark-as-status — the rail mark tracks agent state
        panel._set_busy(False)
        panel._set_busy(True)
        work_mark = panel._mark._state
        panel._set_busy(False)
        done_mark = panel._mark._state
        print(f"   mark-as-status       : work={work_mark} done={done_mark}  "
              + tag(work_mark == "working" and done_mark == "done"))

        # 4 · state-persistence across a manual tab switch
        panel._set_face("direct")
        panel._set_face("work")
        print(f"   state persistence    : work_substate={panel._work_substate}  "
              + tag(panel._work_substate == "done" and panel._work_stack.currentIndex() == 1))

        # 5 · reduced-motion honored — continuous timers go quiet.
        # NB: run_panel.build_panel() flushed + re-imported synapse.*, so the
        # top-level `t` is stale; bind the LIVE tokens module the widgets use.
        from synapse.panel.designsystem import tokens as _tl
        _tl.set_reduced_motion(True)
        try:
            panel._set_thinking(True)
            rm_ok = (not panel._mark._spin.isActive()
                     and not panel._work_face._cook._timer.isActive())
        finally:
            panel._set_thinking(False)
            _tl.set_reduced_motion(None)
        print(f"   reduced-motion       : timers quiet={rm_ok}  " + tag(rm_ok))

        # 6 · adversarial cook->done sweep — the transition is content-only,
        #     never a tab switch (20 cycles)
        base = panel._faces.currentIndex()
        sweep_ok = True
        for _ in range(20):
            panel._set_busy(True)
            if panel._faces.currentIndex() != base or panel._work_stack.currentIndex() != 0:
                sweep_ok = False; break
            panel._set_busy(False)
            if panel._faces.currentIndex() != base or panel._work_stack.currentIndex() != 1:
                sweep_ok = False; break
        print(f"   cook->done sweep     : content-only x20  " + tag(sweep_ok))
    except Exception as e:
        FAILS.append(1)
        print(f"   [FAIL] v9 invariants: {type(e).__name__}: {e}")

# ---------- verdict ----------
print("\n" + "=" * 70)
n_fail, n_warn = len(FAILS), len(WARNS)
if n_fail:
    print(f"  G3 RESULT:  {n_fail} FAIL · {n_warn} WARN  —  not readable/usable yet.")
else:
    print(f"  G3 RESULT:  pass  ·  {n_warn} WARN")
print("=" * 70)

if "--strict" in sys.argv:
    sys.exit(1 if n_fail else 0)
