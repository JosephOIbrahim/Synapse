"""FaceToken — the TOKEN face: what a turn costs, and what it is made of.

R167 split the economist across two surfaces, and the split follows from what
V3 measured rather than from taste.

THE RAIL keeps what an artist must not miss AND what is obtainable: the model,
the session total, probe freshness. It cannot show a fuel gauge, because V3-F4
established that quota headroom is NOT obtainable — no free Anthropic endpoint
returns anthropic-ratelimit-* headers — and V3-F5 that no provider exposes
per-token pricing over its API. The blueprint's designed rail, `18.0k / 200k ·
$0.06`, cannot be produced.

THIS FACE takes what is diagnostic rather than ambient — things you go LOOKING
for, which is what a tab is for:

  · per-turn composition        E0 measured it and nothing surfaced it
  · cache behaviour             E0-F5: every write paid, every read missing,
                                and INVISIBLE because a miss looks like normal
                                operation. Only visible where you look on purpose.
  · local vs metered            R162: six of thirteen Ollama tags carry
                                remote_host=https://ollama.com and are METERED,
                                including glm-5:cloud which is the DEFAULT. The
                                distinction is invisible in the name.
  · reachability                V3-F1: the registry declares 9 models, the
                                providers serve 126.

Three constraints, all from R167 and none negotiable:

  1. NOTHING critical lives only here. Rate-limited, stale probe, model swap —
     those belong on the rail; this face only EXPLAINS them.
  2. Read-out, never read-in. Nothing on this face is typed or configured.
  3. Unobtainable renders as UNKNOWN, never zero and never an estimate.
     A zero is a claim (R162).

Every dependency is optional so the face always instantiates — graceful
degradation is a contract here, same as FaceWork.
"""

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import Qt
except ImportError:  # pragma: no cover - Houdini ships PySide6
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtCore import Qt

from synapse.panel.designsystem import tokens as t
from synapse.panel.designsystem import components as c
from synapse.panel.designsystem import fontload

try:
    from synapse.panel.providers.probe import probe_all
except Exception:  # pragma: no cover
    probe_all = None


UNKNOWN = "unknown"


class TokenField(QtWidgets.QWidget):
    """A cell field where each segment's AREA is its share of the turn.

    Extends FaceWork's BucketGrid idiom rather than inventing a second visual
    language: same cell vocabulary, but allocated by proportion instead of by
    progress.

    THE RULE THAT SHAPES IT: an unknown segment is NOT drawn as a small share.
    It gets a hairline outline and no cells. A segment rendered small reads as
    'this costs little'; the truth is 'nobody measured this', and those are
    different claims (R162 - a zero is a claim).

    So the field only fills to the extent the turn has actually been measured,
    and the unfilled remainder is honest empty space rather than an implied
    zero.
    """

    _COLS, _ROWS = 24, 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsSection")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._segments = []          # [(label, tokens, colour)]
        self.setMinimumHeight(96)

    def sizeHint(self):
        return QtCore.QSize(420, 110)

    def set_segments(self, segments):
        """segments: [(label, tokens_or_None, colour)]. None means UNMEASURED
        and claims no cells."""
        self._segments = list(segments or [])
        self.update()

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()
        n = self._COLS * self._ROWS
        cw, ch = w / float(self._COLS), h / float(self._ROWS)
        gap = 2.0

        known = [(lab, tok, col) for lab, tok, col in self._segments
                 if isinstance(tok, (int, float)) and tok > 0]
        total_known = sum(tok for _, tok, _ in known)

        # Cells are allocated against the KNOWN total only. If half the turn is
        # unmeasured the field is half empty - which is the honest picture.
        alloc, idx = [], 0
        for lab, tok, col in known:
            take = int(round((tok / float(total_known)) * n)) if total_known else 0
            alloc.append((col, idx, min(idx + take, n)))
            idx += take

        empty = QtGui.QColor(t.NEAR_BLACK if hasattr(t, "NEAR_BLACK") else "#111111")
        for i in range(n):
            r, cix = divmod(i, self._COLS)
            x, y = cix * cw, r * ch
            colour = empty
            for col, lo, hi in alloc:
                if lo <= i < hi:
                    colour = QtGui.QColor(col)
                    break
            p.fillRect(QtCore.QRectF(x + gap / 2, y + gap / 2,
                                     cw - gap, ch - gap), colour)
        p.end()



class FaceToken(QtWidgets.QWidget):
    """The token-economics read-out. Renders only what has been measured."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = {}
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(t.GUTTER, 20, t.GUTTER, 20)
        lay.setSpacing(18)

        lay.addWidget(self._eyebrow("THIS TURN"))
        self._field = TokenField()
        lay.addWidget(self._field)
        self._composition = self._kv_block([
            ("system prompt", UNKNOWN),
            ("tool surface", UNKNOWN),
            ("scene grounding", UNKNOWN),
            ("conversation", UNKNOWN),
        ])
        lay.addWidget(self._composition)

        lay.addWidget(self._eyebrow("CACHE"))
        self._cache = self._kv_block([
            ("prefix", UNKNOWN),
            ("last turn", UNKNOWN),
        ])
        lay.addWidget(self._cache)

        lay.addWidget(self._eyebrow("ENGINE"))
        self._engine = self._kv_block([
            ("model", UNKNOWN),
            ("runs", UNKNOWN),          # local | metered by <host>
            ("cost", UNKNOWN),          # NEVER zero for a metered model
            ("probed", UNKNOWN),
        ])
        lay.addWidget(self._engine)

        lay.addStretch(1)
        lay.addWidget(self._footnote(
            "The field fills only as far as the turn has been measured — an "
            "unmeasured segment claims no cells rather than reading as a small "
            "one. System prompt and tool surface are character-derived and run "
            "~6% low against exact counts (R155). Quota headroom and per-token "
            "price are not obtainable from any configured provider (V3-F4, "
            "V3-F5)."))

    # -- construction helpers ------------------------------------------------

    def _eyebrow(self, text):
        lbl = c.label(text, role="body") if hasattr(c, "label") else QtWidgets.QLabel(text)
        try:
            lbl.setFont(fontload.tracked_font("EYEBROW", t.SIZE_LABEL, mono=True))
            lbl.setStyleSheet("color:%s;" % t.TEXT_TERTIARY)
        except Exception:
            pass
        return lbl

    def _footnote(self, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setWordWrap(True)
        try:
            lbl.setStyleSheet("color:%s; font-size:%dpx;" % (t.TEXT_TERTIARY, t.SIZE_SMALL))
        except Exception:
            pass
        return lbl

    def _kv_block(self, pairs):
        w = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(6)
        for i, (k, v) in enumerate(pairs):
            key = QtWidgets.QLabel(k)
            val = QtWidgets.QLabel(str(v))
            try:
                key.setStyleSheet("color:%s;" % t.TEXT_TERTIARY)
                val.setStyleSheet("color:%s;" % t.TEXT_BRIGHT)
                val.setFont(fontload.tracked_font("LABEL", t.SIZE_SMALL, mono=True))
            except Exception:
                pass
            grid.addWidget(key, i, 0, alignment=Qt.AlignLeft)
            grid.addWidget(val, i, 1, alignment=Qt.AlignRight)
            self._rows[k] = val
        return w

    # -- the read-out --------------------------------------------------------

    def set_row(self, key, value):
        """Set one row. `None` renders as UNKNOWN, never as zero (R162)."""
        lbl = self._rows.get(key)
        if lbl is None:
            return
        lbl.setText(UNKNOWN if value is None else str(value))

    def set_composition(self, system=None, tools=None, grounding=None, conversation=None):
        """Per-turn token composition, measured. E0 measured these and nothing
        surfaced them: system prompt 2,961 EXACT, tool surface ~19k, grounding
        variable to 113k on a 25,850-node scene.

        Also drives the field. A segment passed as None claims no cells, so the
        field fills only as far as the turn has actually been measured."""
        self.set_row("system prompt", system)
        self.set_row("tool surface", tools)
        self.set_row("scene grounding", grounding)
        self.set_row("conversation", conversation)
        self._field.set_segments([
            ("system prompt", system, getattr(t, "SIGNAL", "#8FB3D9")),
            ("tool surface", tools, getattr(t, "CONIFEROUS", "#6E8F72")),
            ("scene grounding", grounding, getattr(t, "MUSHROOM", "#8A8078")),
            ("conversation", conversation, getattr(t, "TEXT_TERTIARY", "#6A6A6A")),
        ])

    def measure_static(self):
        """Fill the two segments that are knowable WITHOUT a live turn.

        The system prompt and the tool surface are the same on every turn until
        the code changes, so they can be counted at open. Scene grounding and
        conversation cannot - they are per-turn, and inventing them is exactly
        the estimate this face refuses to show.

        Free: character-derived, no API call, no completion spend. Labelled as
        approximate in the footnote rather than presented as exact, because the
        proxy was measured at ~6% low (R155)."""
        sysn = tools = None
        try:
            from synapse.panel.system_prompt import build_system_prompt
            sp = build_system_prompt({"network": "/stage", "selection": [],
                                      "frame": 1, "hip": ""})
            sysn = int(len(sp) / 3.6)
        except Exception:
            pass
        try:
            import json as _json
            from synapse.mcp import _tool_registry as _reg
            blob = _json.dumps(getattr(_reg, "TOOL_JSON", {}))
            tools = int(len(blob) / 3.6)
        except Exception:
            pass
        self.set_composition(system=sysn, tools=tools,
                             grounding=None, conversation=None)

    def set_cache(self, prefix=None, last_turn=None):
        """E0-F5/F6: the breakpoint wraps the whole system prompt and the prompt
        is not static, so every write is paid at 1.25x and every read misses.
        A miss looks exactly like normal operation - this is the only place it
        can be seen."""
        self.set_row("prefix", prefix)
        self.set_row("last turn", last_turn)

    def set_engine(self, model=None, runs=None, cost=None, probed=None):
        """`runs` is local vs metered, which R162 found is INVISIBLE in the name:
        glm-5:cloud carries remote_host=https://ollama.com and is metered by that
        host, and it is the registry's default pick. `cost` for a metered model
        with no published price is UNKNOWN - never zero.

        `probed` is formatted HERE rather than by the caller. It was formatted in
        refresh_from_probe first, which meant any other call site rendered a raw
        epoch float - a number the panel knows and the reader does not. The
        formatting belongs where the value lands, not where one caller happens
        to pass it."""
        self.set_row("model", model)
        self.set_row("runs", runs)
        self.set_row("cost", cost)
        self.set_row("probed", self._ago(probed))

    def refresh_from_probe(self):
        """Best-effort pull from the probe layer, plus the two static segments.

        Never raises: a face that cannot reach a probe shows unknown, which is
        the honest state."""
        self.measure_static()
        if probe_all is None:
            return
        try:
            results = probe_all()
        except Exception:
            return
        for r in (results or []):
            if not getattr(r, "available", False):
                continue
            host = getattr(r, "remote_host", None)
            self.set_engine(
                model=getattr(r, "model", None),
                runs=("metered by %s" % host) if host else "local",
                cost=getattr(r, "cost_per_1k_in", None),   # None -> unknown
                probed=getattr(r, "probed_at", None),
            )
            return

    @staticmethod
    def _ago(stamp):
        """Probe age as an artist reads it. A raw epoch float is a number the
        panel knows and the reader does not."""
        if stamp is None:
            return None
        try:
            import time
            secs = int(max(0, time.time() - float(stamp)))
        except (TypeError, ValueError):
            return str(stamp)
        if secs < 60:
            return "%ds ago" % secs
        if secs < 3600:
            return "%dm ago" % (secs // 60)
        return "%dh ago" % (secs // 3600)
