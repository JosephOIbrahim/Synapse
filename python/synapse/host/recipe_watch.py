"""Opt-in, one-shot scene-exit capture; host calls are injected and main-thread owned."""
from synapse.recipes.library import normalize_metadata
import logging
import uuid


class RecipeWatch:
    def __init__(self, host, notify):
        self.host = host
        self.notify = notify
        self._armed = None
        self._subscribed = False
        self._callback = self.event
        self.last_result = None
        self._closed = False

    @property
    def armed(self):
        return self._armed is not None

    def arm(self, name, tags, notes="", *, recipe_id=None):
        if self._closed:
            raise ValueError("Open Recipes again before keeping another selection.")
        metadata = normalize_metadata(name, tags, notes)
        identities = self.host.selection_identity()
        if not identities:
            raise ValueError("Select the Solaris nodes to keep first.")
        candidate = dict(metadata, recipe_id=recipe_id, identities=identities, arm_id=uuid.uuid4().hex,
                         source_scene=self.host.scene_path())
        if not self._subscribed:
            self.host.subscribe(self._callback)
            self._subscribed = True
        self._armed = candidate
        self._notice({"status": "watching", "message": f"Keeping {name} locally before the next scene change.",
                      "source_scene": candidate["source_scene"]})

    def disarm(self):
        self._armed = None
        self._notice({"status": "stopped", "message": "Stopped keeping this selection at scene changes."})

    def _notice(self, result):
        self.last_result = result
        try:
            self.host.record_notice(result)
        except Exception as exc:
            result["notice_saved"] = False
            result["message"] += f" Last-result record unavailable: {exc}"
            # A QObject may already be disappearing. Keep an observer outside
            # its widget tree, with a process-log fallback if the host is gone.
            try:
                self.host.report_notice_failure(result["message"])
            except Exception:
                logging.getLogger(__name__).error("%s", result["message"])
        try:
            self.notify(result)
        except Exception:
            pass  # a disappearing panel must not break Houdini's callback chain

    def event(self, event):
        if not self._closed and event in ("BeforeLoad", "BeforeClear"):
            self._capture(event)

    def _capture(self, reason):
        if self._armed is None:
            return
        # Disarm first: BeforeLoad → BeforeClear is one capture, including errors.
        candidate, self._armed = self._armed, None
        try:
            saved = self.host.save_identity(**candidate, reason=reason)
            result = {"status": "saved", "message": f"Saved {saved['name']} · version {saved['version']} locally.",
                      "recipe_id": saved["recipe_id"], "version": saved["version"],
                      "source_scene": saved.get("snapshot", {}).get("source_scene", candidate["source_scene"]),
                      "armed_source_scene": candidate["source_scene"]}
        except Exception as exc:
            result = {"status": "failed", "message": f"Could not keep {candidate['name']}: {exc}",
                      "source_scene": candidate["source_scene"]}
        self._notice(result)

    def close(self, *, notify=True):
        if self._closed:
            return
        self._closed = True
        if not notify:
            self.notify = lambda result: None
        self._capture("PanelClose")
        if self._subscribed:
            try:
                self.host.unsubscribe(self._callback)
            except Exception as exc:
                self._notice({"status": "failed", "message": f"Capture stopped; scene callback removal failed: {exc}"})
            finally:
                self._subscribed = False
                self.notify = lambda result: None
