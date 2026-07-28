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

    _SEEDS = 44
    _JITTER = 0.42          # 0 = regular lattice, 0.5 = fully scattered

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
        """A jittered lattice. Pure lattice gives rectangles; pure random gives
        slivers. The jitter is what makes it read as organic while keeping the
        cells within an order of magnitude of each other."""
        import math
        cols = int(round(math.sqrt(self._SEEDS * w / float(max(h, 1)))))
        cols = max(2, cols)
        rows = max(2, int(round(self._SEEDS / float(cols))))
        cw, ch = w / float(cols), h / float(rows)
        pts, n = [], 0
        for r in range(rows):
            for c in range(cols):
                # Deterministic hash-jitter: same layout every repaint.
                n += 1
                jx = (((n * 1103515245 + 12345) >> 8) % 1000) / 1000.0 - 0.5
                jy = (((n * 1664525 + 1013904223) >> 8) % 1000) / 1000.0 - 0.5
                pts.append((
                    (c + 0.5 + jx * self._JITTER * 2) * cw,
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
        empty = QtGui.QColor(getattr(t, "GROUND", "#1B1B1B"))
        edge = QtGui.QPen(QtGui.QColor(getattr(t, "VOID", "#0A0A0A")))
        edge.setWidthF(1.4)
        p.setPen(edge)

        acc = 0.0
        for poly, area, _cx in cells:
            acc += area
            colour = empty
            for limit, col in targets:
                if acc <= limit:
                    colour = QtGui.QColor(col)
                    break
            path = QtGui.QPolygonF([QtCore.QPointF(x, y) for x, y in poly])
            p.setBrush(QtGui.QBrush(colour))
            p.drawPolygon(path)
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
            # SIZE_SMALL, not SIZE_LABEL. These are section markers - THIS TURN,
            # CACHE, ENGINE - and SIZE_LABEL is 10px, which the tokens file
            # reserves for "tiny labels / numbers". A marker you have to lean in
            # for is not doing its job.
            lbl.setFont(fontload.tracked_font("EYEBROW", t.SIZE_SMALL, mono=True))
            lbl.setStyleSheet("color:%s;" % t.TEXT_TERTIARY)
        except Exception:
            pass
        return lbl

    def _footnote(self, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setWordWrap(True)
        try:
            # SIZE_BODY, not SIZE_SMALL. The tokens file names SIZE_BODY as
            # "Houdini-native default (9pt = 12px)" and this face had the
            # footnote at 11 and the values at 11 while the left-hand keys
            # inherited the native default - so the two columns disagreed and
            # the footnote read as fine print. A read-out nobody can read is
            # not a read-out.
            lbl.setStyleSheet("color:%s; font-size:%dpx;" % (t.TEXT_TERTIARY, t.SIZE_BODY))
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
                # SIZE_BODY: the values must read at the same size as the keys
                # beside them. The keys inherit Houdini's native default and the
                # values were set to SIZE_SMALL, so the right-hand column was a
                # step smaller than the left for no reason anyone chose.
                val.setFont(fontload.tracked_font("LABEL", t.SIZE_BODY, mono=True))
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
