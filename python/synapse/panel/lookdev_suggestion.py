"""One requested suggestion and an editable draft; no automatic submission."""
from __future__ import annotations

import weakref


def suggestion_view(result):
    """Validate the returned evidence before exposing a usable draft."""
    from synapse.memory.experience import validate_environment, validate_experience
    empty = {"status": "UNAVAILABLE", "body": "Saved lookdev assistance is unavailable.", "draft": ""}
    if not isinstance(result, dict):
        return empty
    status = result.get("status")
    if status != "HIT":
        if status == "NO_MATCH" and result.get("complete") is True:
            return dict(empty, status="NO_MATCH", body="No compatible saved lookdev setup was found for this environment.")
        reason = result.get("reason")
        return dict(empty, body=reason if isinstance(reason, str) and reason else empty["body"])
    try:
        record = validate_experience(result["experience"])
        environment = validate_environment(result["environment"])
        if (result.get("complete") is not True or result.get("record_id") != record["record_id"]
                or environment != record["environment"]):
            return empty
        parameters = record["procedure"]["parameters"]
        rgb = ", ".join(str(value) for value in parameters["base_color"])
        settings = ("Base color RGB: " + rgb + "\nNoise: " + parameters["noise_type"]
                    + "\nFrequency: " + str(parameters["frequency"])
                    + "\nOctaves: " + str(parameters["octaves"]))
        limits = "Configuration and USD were checked. Texture pixels and rendered appearance were not checked."
        body = record["procedure"]["summary"] + "\n\n" + settings + "\n\n" + limits
        # Only validated settings enter the prompt. Free-form historical
        # summaries, node paths and any claimed execution instructions do not.
        draft = ("Create a new Copernicus lookdev setup using the copernicus_lookdev builder.\n"
                 + settings + "\nLayout: " + record["procedure"]["layout"]
                 + "\nUse a fresh name and an editable Solaris network, preserving existing work.\n" + limits)
        return {"status": "HIT", "body": body, "draft": draft}
    except (KeyError, ValueError, TypeError, AttributeError):
        return empty


class SuggestionState:
    """Pure request ordering; an old reply can never restore a dismissed hit."""

    def __init__(self):
        self.generation = 0
        self.result = None

    def begin(self):
        self.generation += 1
        self.result = None
        return self.generation

    def accept(self, generation, result):
        if generation != self.generation:
            return False
        self.result = result
        return True

    def view(self):
        return suggestion_view(self.result)


try:
    from PySide6 import QtCore, QtWidgets
except ImportError:
    try:
        from PySide2 import QtCore, QtWidgets
    except ImportError:
        QtCore = QtWidgets = None


# QThreads outlive a dismissed/deleted panel until their bounded host wait ends.
# This set owns no store, panel or scene object. Finished threads release it.
_LOOKUPS = set()


if QtWidgets is not None:
    from .designsystem import components as c, rhythm, tokens as t

    class _Lookup(QtCore.QThread):
        ready = QtCore.Signal(int, object)

        def __init__(self, session, generation, token):
            super().__init__(None)
            self.session, self.generation, self.token = session, generation, token

        def run(self):
            result = self.session.lookup(self.token, requested=True)
            self.ready.emit(self.generation, result)

    class LookdevSuggestionCard(c.Card):
        draft_ready = QtCore.Signal(str)
        scene_changed = QtCore.Signal()

        def __init__(self, parent=None):
            super().__init__(parent=parent)
            from synapse.host.lookdev_suggestion import LookdevSuggestionSession
            reference = weakref.ref(self)
            def changed():
                card = reference()
                if card is not None:
                    try:
                        card.scene_changed.emit()
                    except RuntimeError:
                        pass  # the Qt receiver has already been deleted
            self.session = LookdevSuggestionSession(changed)
            session = self.session
            self.destroyed.connect(lambda *_: session.close())
            self.state = SuggestionState()
            self._worker = None
            self._closed = False
            self.setProperty("rhythm_role", "band")
            layout = QtWidgets.QVBoxLayout(self)
            header = c.label("saved lookdev suggestion")
            header.setObjectName("DsCardHeader")
            header.setProperty("rhythm_role", "label")
            self.body = QtWidgets.QTextBrowser()
            self.body.setObjectName("DsCardBody")
            self.body.setProperty("role", "lookdev_suggestion")
            self.body.setReadOnly(True)
            self.body.setOpenExternalLinks(False)
            self.body.setMaximumHeight(t.SPACE_32 * 6)
            self.body.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
            footer = QtWidgets.QWidget()
            footer.setObjectName("DsCardFooter")
            footer.setProperty("role", "lookdev_suggestion")
            footer.setProperty("rhythm_role", "stack")
            row = QtWidgets.QGridLayout(footer)
            self.use = c.Button("Use in prompt", variant="ghost")
            self.use.setToolTip("Add editable starting settings to your prompt. Nothing is sent or built.")
            self.retry = c.Button("Ask again", variant="ghost")
            self.dismiss = c.Button("Dismiss", variant="ghost")
            self.use.clicked.connect(self._prepare)
            self.retry.clicked.connect(self.request)
            self.dismiss.clicked.connect(self.disengage)
            self.scene_changed.connect(self._invalidate_scene)
            row.addWidget(self.use, 0, 0, 1, 2)
            row.addWidget(self.retry, 1, 0)
            row.addWidget(self.dismiss, 1, 1)
            for band in (header, self.body, footer):
                layout.addWidget(band)
            self.use.setEnabled(False)
            rhythm.apply(self)
            self.hide()

        def request(self):
            if self._closed:
                return
            self.show()
            generation = self.state.begin()
            self.use.setEnabled(False)
            if self._worker is not None and self._worker.isRunning():
                self.body.setPlainText("The previous lookup is finishing. Ask again in a moment.")
                return
            try:
                token = self.session.begin_request()
            except Exception as exc:
                self.body.setPlainText("Saved lookdev assistance could not start: " + str(exc))
                self.retry.setEnabled(True)
                return
            self.body.setPlainText("Looking for a compatible saved lookdev setup…")
            self.retry.setEnabled(False)
            worker = _Lookup(self.session, generation, token)
            self._worker = worker
            _LOOKUPS.add(worker)
            worker.ready.connect(self._ready)
            worker.finished.connect(self._finished)
            worker.finished.connect(lambda call=worker: _LOOKUPS.discard(call))
            worker.start()

        @QtCore.Slot(int, object)
        def _ready(self, generation, result):
            if not isinstance(result, dict):
                result = {"status": "UNAVAILABLE", "reason": "Saved lookdev returned an unreadable result."}
            if self._closed or not self.state.accept(generation, result):
                return
            if not self.session.is_current(result.get("request_token")):
                self.state.result = None
                self.body.setPlainText(result.get("reason") or "The scene changed. Ask for a fresh suggestion.")
                self.use.setEnabled(False)
                return
            view = self.state.view()
            self.body.setPlainText(view["body"])
            self.use.setEnabled(bool(view["draft"]))

        @QtCore.Slot()
        def _finished(self):
            if not self._closed and self.sender() is self._worker:
                self.retry.setEnabled(True)

        def _prepare(self):
            result = self.state.result or {}
            if self._closed or not self.session.is_current(result.get("request_token")):
                self._invalidate_scene()
                return
            draft = self.state.view()["draft"]
            if draft:
                self.draft_ready.emit(draft)
                self.disengage()

        @QtCore.Slot()
        def _invalidate_scene(self):
            if self._closed:
                return
            self.state.begin()
            self.use.setEnabled(False)
            self.body.setPlainText("The scene changed. Ask for a fresh saved lookdev suggestion.")

        def disengage(self):
            self.state.begin()
            self.session.cancel()
            self.use.setEnabled(False)
            self.hide()

        def shutdown(self):
            self._closed = True
            self.state.begin()
            self.session.close()
else:
    class LookdevSuggestionCard:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("Saved lookdev suggestions require PySide6 or PySide2")
