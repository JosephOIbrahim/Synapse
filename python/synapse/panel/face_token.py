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


UNKNOWN = "UNKNOWN"


class TokenField(QtWidgets.QWidget):
    """A Voronoi field where each segment's AREA is its share of the turn.

    Cells are real Voronoi regions, built by clipping the bounding rect with the
    perpendicular bisector between each seed and every other seed. No scipy, no
    dependency - at ~44 seeds the O(n^2) clip is trivial and it runs inside a
    paintEvent without complaint.

    THE HARD PART IS HONESTY, not the geometry. Voronoi cells have UNEQUAL
    areas, so allocating them by COUNT would misstate every proportion. Cells
    are assigned by CUMULATIVE AREA: walk them left-to-right and hand each
    segment cells until its measured share of the total area is met. Segments
    come out spatially coherent and areally correct.

    AND THE RULE THAT SHAPES IT: an unmeasured segment claims NO CELLS. Not a
    small region - none. A segment drawn small reads as "this costs little";
    the truth is "nobody measured this", and those are different claims (R162 -
    a zero is a claim). So the field fills only as far as the turn has actually
    been measured, and the remainder stays unfilled.

    Seeded deterministically from a fixed constant, so the pattern is stable
    across repaints - a field that reshuffles every paint reads as animation
    and this is a read-out.
    """

    # 18, and the number was MEASURED rather than chosen for looks.
    #
    # The reference uses very few, very large cells - 5 to 8 - and I tried 9.
    # At 9 seeds the field resolves to 12 cells and the system prompt, a real
    # 10.5% of the turn, receives ZERO of them. It vanishes.
    #
    # That is the exact inversion of this widget's rule. Unmeasured claims no
    # cells; a MEASURED segment must therefore never render as absent, or the
    # two states become indistinguishable and the field lies in the more
    # convincing direction.
    #
    #   seeds  9 -> 12 cells | share 0.000 vs 0.105 target | error 0.105
    #   seeds 18 -> 18 cells | share 0.104 vs 0.105 target | error 0.001
    #
    # 18 still reads as Cohere's large-cell language and is honest. That is
    # where the aesthetic and the constraint intersect.
    _SEEDS = 18
    _JITTER = 0.34          # 0 = regular lattice, 0.5 = fully scattered
    _INSET = 3.0            # gap between cells - the ground shows through
    _RADIUS = 10.0          # corner rounding

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsSection")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._segments = []          # [(label, tokens, colour)]
        self._cells = None           # cached [(polygon, area, cx)]
        self._cell_size = None
        self.setMinimumHeight(150)

    def sizeHint(self):
        return QtCore.QSize(420, 170)

    def set_segments(self, segments):
        """segments: [(label, tokens_or_None, colour)]. None means UNMEASURED
        and claims no area."""
        self._segments = list(segments or [])
        self.update()

    # -- geometry ------------------------------------------------------------

    def _seed_points(self, w, h):
        """A jittered lattice, with the ROW COUNT floored at 3.

        Pure lattice gives rectangles; pure random gives slivers. The jitter is
        what makes it read as organic while keeping the cells within an order of
        magnitude of each other.

        The floor matters at panel width. A docked panel is very wide and this
        field is short, so deriving both axes from the aspect ratio produced 11
        columns by 2 rows - cells stretched into a horizontal strip, nothing
        like the reference's equant tiles. Flooring rows at 3 and letting the
        column count follow keeps them chunky at any width.
        """
        import math
        rows = max(3, int(round(math.sqrt(self._SEEDS * h / float(max(w, 1))))))
        cols = max(2, int(round(self._SEEDS / float(rows))))
        cw, ch = w / float(cols), h / float(rows)
        pts, n = [], 0
        for r in range(rows):
            for c_ in range(cols):
                # Deterministic hash-jitter: same layout every repaint.
                n += 1
                jx = (((n * 1103515245 + 12345) >> 8) % 1000) / 1000.0 - 0.5
                jy = (((n * 1664525 + 1013904223) >> 8) % 1000) / 1000.0 - 0.5
                pts.append((
                    (c_ + 0.5 + jx * self._JITTER * 2) * cw,
                    (r + 0.5 + jy * self._JITTER * 2) * ch,
                ))
        return pts

    @staticmethod
    def _clip(poly, ax, ay, bx, by):
        """Clip a convex polygon to the half-plane closer to A than to B.

        The perpendicular bisector of AB; keep the side containing A. This is
        the whole Voronoi construction - a cell is the rect clipped against
        every other seed.
        """
        mx, my = (ax + bx) / 2.0, (ay + by) / 2.0
        dx, dy = bx - ax, by - ay          # normal, pointing away from A
        out = []
        n = len(poly)
        for i in range(n):
            px, py = poly[i]
            qx, qy = poly[(i + 1) % n]
            dp = (px - mx) * dx + (py - my) * dy
            dq = (qx - mx) * dx + (qy - my) * dy
            if dp <= 0:
                out.append((px, py))
            if (dp <= 0) != (dq <= 0):
                t_ = dp / (dp - dq) if (dp - dq) else 0.0
                out.append((px + (qx - px) * t_, py + (qy - py) * t_))
        return out

    @staticmethod
    def _area(poly):
        a = 0.0
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            a += x1 * y2 - x2 * y1
        return abs(a) / 2.0

    def _build_cells(self, w, h):
        """One Voronoi cell per seed, cached until the widget resizes."""
        if self._cells is not None and self._cell_size == (w, h):
            return self._cells
        pts = self._seed_points(w, h)
        rect = [(0, 0), (w, 0), (w, h), (0, h)]
        cells = []
        for i, (ax, ay) in enumerate(pts):
            poly = rect
            for j, (bx, by) in enumerate(pts):
                if i == j:
                    continue
                poly = self._clip(poly, ax, ay, bx, by)
                if len(poly) < 3:
                    break
            if len(poly) >= 3:
                cells.append((poly, self._area(poly), ax))
        cells.sort(key=lambda c: c[2])       # left-to-right: coherent regions
        self._cells, self._cell_size = cells, (w, h)
        return cells

    # -- paint ---------------------------------------------------------------

    @staticmethod
    def _rounded_path(poly, inset, radius):
        """A polygon, pulled in by `inset` and rounded at every vertex.

        This is what makes it read as Cohere rather than as a mesh. The
        reference's cells are heavily rounded and SEPARATED - the ground shows
        between them - so the field reads as a set of tiles rather than a
        subdivision. Sharp adjacent polygons read as a diagram; these read as
        objects.
        """
        n = len(poly)
        if n < 3:
            return None
        cx = sum(p[0] for p in poly) / float(n)
        cy = sum(p[1] for p in poly) / float(n)

        # Pull each vertex toward the centroid to open the gaps.
        pts = []
        for x, y in poly:
            dx, dy = cx - x, cy - y
            d = (dx * dx + dy * dy) ** 0.5 or 1.0
            k = min(inset / d, 0.45)
            pts.append((x + dx * k, y + dy * k))

        path = QtGui.QPainterPath()
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            ex, ey = x1 - x0, y1 - y0
            elen = (ex * ex + ey * ey) ** 0.5 or 1.0
            r = min(radius, elen / 2.0)
            ux, uy = ex / elen, ey / elen
            if i == 0:
                path.moveTo(x0 + ux * r, y0 + uy * r)
            else:
                path.quadTo(x0, y0, x0 + ux * r, y0 + uy * r)
            path.lineTo(x1 - ux * r, y1 - uy * r)
        path.closeSubpath()
        return path

    def paintEvent(self, _event):
        w, h = self.width(), self.height()
        if w < 8 or h < 8:
            return
        cells = self._build_cells(w, h)
        total_area = sum(a for _, a, _ in cells) or 1.0

        known = [(lab, tok, col) for lab, tok, col in self._segments
                 if isinstance(tok, (int, float)) and tok > 0]
        total_known = float(sum(tok for _, tok, _ in known)) or 1.0

        # Allocate by CUMULATIVE AREA, not by cell count - cells are unequal.
        targets, run = [], 0.0
        for lab, tok, col in known:
            run += (tok / total_known) * total_area
            targets.append((run, col))

        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        p.setPen(QtCore.Qt.PenStyle.NoPen)      # separation is the GAP, not a stroke
        empty = QtGui.QColor(t.GROUND)

        acc = 0.0
        for poly, area, _cx in cells:
            acc += area
            # FLAT FILL. My previous pass ramped luminance across the field for
            # "atmosphere" - the reference does no such thing. Every Cohere cell
            # is one solid colour, and the variation comes from the SHAPES and
            # the palette, not from a gradient. Removing it also removes the
            # only thing on this widget that varied for reasons unrelated to
            # data.
            colour = empty
            for limit, col in targets:
                if acc <= limit:
                    colour = QtGui.QColor(col)
                    break
            path = self._rounded_path(poly, self._INSET, self._RADIUS)
            if path is not None:
                p.fillPath(path, QtGui.QBrush(colour))
        p.end()



class FaceToken(QtWidgets.QWidget):
    """The token-economics read-out. Renders only what has been measured."""

    def __init__(self, parent=None, scale=1.0):
        super().__init__(parent)
        # THE HOST FONT SCALE, and this face was the only surface ignoring it.
        #
        # synapse_panel sets `self._chrome_scale = self._host_font_scale()` and
        # every other chrome font is built with `scale=` so it tracks the host
        # UI size. Not one of this face's tracked_font calls passed it, so its
        # values and footnote rendered at a literal 12px while the labels beside
        # them rendered at 12 x host scale. That is why the right-hand column
        # and the footnote read small no matter which SIZE_ token they used -
        # the token was never the problem, the missing scale was.
        self._scale = float(scale or 1.0)
        self._rows = {}

        # CROP AND SCROLL, LIKE A NATIVE HOUDINI PANEL.
        #
        # Without this the face compresses when the pane is short: the Voronoi
        # field holds its height, the rows collapse into it, and the labels
        # render ON TOP of the cells. Measured against Houdini's own parameter
        # panel - it does not compress anything. Content keeps its natural size
        # and the panel CROPS, with a scrollbar if you want the rest.
        #
        # So this widget is a scroll viewport and everything below is its
        # content. A read-out that becomes unreadable at small sizes is not a
        # read-out, and compressing is the failure mode that produces that.
        outer = QtWidgets.QVBoxLayout(self)
        self.setObjectName("DsTokenFace")
        self.setProperty("rhythm_role", "group")
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setObjectName("DsSection")
        self._scroll.viewport().setObjectName("DsSection")
        outer.addWidget(self._scroll)

        body = QtWidgets.QWidget()
        self._scroll.setWidget(body)
        lay = QtWidgets.QVBoxLayout(body)
        body.setObjectName("DsSection")
        body.setProperty("rhythm_role", "group")

        lay.addWidget(self._eyebrow("THIS TURN"))
        self._field = TokenField()
        # FIXED height, not minimum. Inside a scroll area a widget that can
        # stretch will, and the field would grow to eat the viewport on a tall
        # pane while the rows stayed bunched at the bottom. It is a read-out of
        # a fixed thing; it does not need more room when there is more room.
        self._field.setFixedHeight(self._px(150))
        self._field.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                                  QtWidgets.QSizePolicy.Policy.Fixed)
        lay.addWidget(self._field)
        # A legend, because a field whose colours nobody can decode is
        # decoration. Two entries only — the two segments that are actually
        # measurable without a live turn.
        lay.addWidget(self._legend([
            ("system prompt", t.SIGNAL),
            ("tool surface", t.CONIFEROUS),
        ]))
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

    def _px(self, token):
        """A size token in the host's terms. Every font on this face goes
        through here so none can drift out of step again."""
        return max(t.FONT_FLOOR_PX, t.scaled(token, self._scale))

    def _eyebrow(self, text):
        lbl = c.label(text, role="label", scale=self._scale)
        lbl.setObjectName("DsParmSection")
        lbl.setProperty("rhythm_role", "label")
        return lbl

    def _legend(self, entries):
        """Token-painted swatches; the existing labels remain the legend."""
        w = QtWidgets.QWidget()
        w.setObjectName("DsSection")
        w.setProperty("rhythm_role", "parm_row")
        row = QtWidgets.QHBoxLayout(w)
        for text, colour in entries:
            sw = QtWidgets.QLabel()
            d = self._px(t.SPACE_SM)
            sw.setFixedSize(d, d)
            pixmap = QtGui.QPixmap(d, d)
            pixmap.fill(QtGui.QColor(colour))
            sw.setPixmap(pixmap)
            lbl = c.label(text, role="caption", scale=self._scale)
            row.addWidget(sw)
            row.addWidget(lbl)
        row.addStretch(1)
        return w

    def _footnote(self, text):
        lbl = c.label(text, role="caption", scale=self._scale)
        lbl.setObjectName("DsTokenNote")
        lbl.setWordWrap(True)
        lbl.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        return lbl

    def _kv_block(self, pairs):
        # Reuse the existing grid: direct child ids give every pair the same
        # label/value columns without introducing wrapper widgets or controls.
        w = QtWidgets.QWidget()
        w.setObjectName("DsSection")
        w.setProperty("rhythm_role", "parm_row")
        grid = QtWidgets.QGridLayout(w)
        for i, (k, v) in enumerate(pairs):
            key = c.label(k, role="body", scale=self._scale)
            val = c.label(str(v), role="code", scale=self._scale)
            key.setObjectName("DsParmLabel")
            val.setObjectName("DsParmValue")
            key.setProperty("rhythm_role", "parm_row")
            val.setProperty("rhythm_role", "parm_row")
            val.setWordWrap(True)
            val.setTextFormat(Qt.PlainText)
            grid.addWidget(key, i, 0, alignment=Qt.AlignLeft)
            grid.addWidget(val, i, 1, alignment=Qt.AlignRight)
            self._rows[k] = val
        grid.setColumnStretch(2, 1)
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
            ("system prompt", system, t.SIGNAL),
            ("tool surface", tools, t.CONIFEROUS),
            ("scene grounding", grounding, t.MUSHROOM),
            ("conversation", conversation, t.TEXT_TERTIARY),
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
        to pass it.
        """
        self.set_row("model", model)
        self.set_row("runs", runs)
        self.set_row("cost", cost)
        self.set_row("probed", self._ago(probed))

        # Runs remains explicit text. Parameter values use the neutral role;
        # no late local stylesheet can leak a prior engine's accent.

    def refresh_from_probe(self):
        """Best-effort pull from the probe layer, plus the two static segments,
        plus the LAST task's real token spend (W5-PANEL item 3).

        Never raises: a face that cannot reach a probe — or a task — shows unknown,
        which is the honest state."""
        self.measure_static()
        if probe_all is not None:
            try:
                results = probe_all()
            except Exception:
                results = None
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
                break
        # Real per-task spend has the LAST word: the model that actually spent
        # (the selected engine) and the measured cache split override the probe's
        # advertised model. Runs regardless of whether a probe was reachable.
        self._refresh_usage()

    def _refresh_usage(self):
        """Feed the CACHE block and the ENGINE model from the LAST task's REAL
        per-task token usage (usage_sink).

        Every number here traces to ``provider.last_usage`` — an Anthropic API
        receipt captured by AnthropicProvider and folded across the task's tool
        loop by claude_worker. This is the wiring that turns the dead counter live.

        Honesty (R162): a field the API never reported is ``None`` and renders
        UNKNOWN via set_row, never zero. A task that never ran, or a non-Anthropic
        engine that reports no usage, leaves these rows UNKNOWN — the counter's
        honest resting state, not a fabricated number. A genuinely API-reported 0
        (a real cache miss) is a measured claim and shows as 0.

          cache_read     -> CACHE 'prefix'    (cached prefix reused this task)
          cache_creation -> CACHE 'last turn' (cache written this task, paid 1.25x)
          model          -> ENGINE 'model'    (the SELECTED model that did the spending)

        The four THIS-TURN composition rows (system/tools/grounding/conversation)
        are NOT fed here: the API reports totals plus the cache split, never the
        4-way input breakdown, so inventing it would be exactly the estimate this
        face refuses. They stay measure_static/UNKNOWN. Cost stays UNKNOWN too — no
        provider exposes per-token price (V3-F5)."""
        try:
            from synapse.panel.usage_sink import USAGE_SINK
            snap = USAGE_SINK.snapshot()
        except Exception:
            snap = None
        if not snap:
            return
        self.set_cache(prefix=snap.get("cache_read"),
                       last_turn=snap.get("cache_creation"))
        model = snap.get("model")
        if model:
            self.set_row("model", model)

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
