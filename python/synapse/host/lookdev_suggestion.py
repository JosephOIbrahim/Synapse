"""Private, artist-requested lookdev recall. No public tool or memory owner.

The panel owns this observation session; workers carry only its request token.
Every Houdini call and access to the existing memory owner happens on main.
"""
from __future__ import annotations

import logging
from pathlib import Path
import sys
import threading
import uuid
import weakref

_LOG = logging.getLogger(__name__)


def _unavailable(reason):
    return {"status": "UNAVAILABLE", "reason": reason}


def _on_main(fn):
    from synapse.server.main_thread import run_on_main
    return run_on_main(fn, timeout=5.0, label="lookdev:requested_recall")


class LookdevSuggestionSession:
    """An opt-in scene observer, never a store constructor or executor."""

    def __init__(self, on_change=None):
        self._lock = threading.RLock()
        self._generation = uuid.uuid4().hex
        self._closed = False
        self._callback = None
        self._on_change = on_change
        self._owner_identity = None

    def token(self):
        with self._lock:
            return None if self._closed else self._generation

    def is_current(self, token):
        with self._lock:
            if self._closed or token is None or token != self._generation:
                return False
            if self._owner_identity is not None:
                # Like the panel health strip: identity-only peek, no owner
                # construction, storage I/O, embedding, or handle acquisition.
                module = sys.modules.get("synapse.memory.store")
                current = getattr(module, "_global_synapse", None)
                identity = (id(current), id(getattr(current, "store", None)))
                if identity != self._owner_identity:
                    return False
            return True

    def _scene_changed(self):
        with self._lock:
            if self._closed:
                return
            self._generation = uuid.uuid4().hex
        if self._on_change is not None:
            self._on_change()

    def _install_callback(self, hou):
        if self._callback is not None:
            return
        reference = weakref.ref(self)
        def changed(event):
            owner = reference()
            name = str(event).rsplit(".", 1)[-1]
            if owner is not None and name in {"BeforeClear", "BeforeLoad", "BeforeQuit", "AfterSave"}:
                owner._scene_changed()
        hou.hipFile.addEventCallback(changed)
        try:
            if changed not in hou.hipFile.eventCallbacks():
                raise RuntimeError("Scene-change observation could not be established")
        except Exception:
            hou.hipFile.removeEventCallback(changed)
            raise
        self._callback = changed

    def begin_request(self):
        """Bind scene changes before the panel queues its memory lookup.

        Only observer registration runs here; no memory, files or model work.
        From the panel this is a short main-thread operation through the
        established dispatcher, so a load between click and lookup is visible.
        """
        def arm():
            if threading.get_ident() != threading.main_thread().ident:
                raise RuntimeError("Scene observation requires the Houdini main thread")
            with self._lock:
                if self._closed:
                    raise RuntimeError("This suggestion session has closed")
                import hou
                self._generation = uuid.uuid4().hex
                self._owner_identity = None
                self._install_callback(hou)
                return self._generation
        return _on_main(arm)

    def lookup(self, token=None, *, requested=False):
        if requested is not True or not self.is_current(token):
            return _unavailable("Saved lookdev assistance requires a current artist request")
        try:
            return _on_main(lambda: self._lookup_on_main(token))
        except Exception as exc:
            return _unavailable("Saved lookdev lookup could not finish: " + str(exc))

    def _lookup_on_main(self, token):
        if threading.get_ident() != threading.main_thread().ident:
            raise RuntimeError("Saved lookdev recall requires the Houdini main thread")
        with self._lock:
            if not self.is_current(token):
                return _unavailable("This suggestion request has ended")
            if self._callback is None:
                return _unavailable("Scene observation must begin before requesting a suggestion")
            import hou
            from synapse.memory import store as memory_store
            from synapse.memory.moneta_store import MonetaBackedStore

            # Never wait on a worker constructing an owner: that worker may
            # itself be waiting for main-thread project resolution.
            if not memory_store._GLOBAL_LOCK.acquire(blocking=False):
                return _unavailable("Project memory is busy. Ask again when it is ready.")
            try:
                owner = memory_store._global_synapse
                if owner is None:
                    return _unavailable("Project memory is not ready for saved suggestions")
                backend = owner.store
                if not isinstance(backend, MonetaBackedStore):
                    return _unavailable("Saved lookdev suggestions require the existing Moneta project memory")
                if not backend._lock.acquire(blocking=False):
                    return _unavailable("Project memory is busy. Ask again when it is ready.")
                try:
                    return self._recall_owned(hou, owner, backend, token)
                finally:
                    backend._lock.release()
            finally:
                memory_store._GLOBAL_LOCK.release()

    def _recall_owned(self, hou, owner, backend, token):
        """Called only under the main-thread session/owner/backend locks."""
        from husd import quickmaterials
        from synapse.memory.experience import ExperienceMemory, TASK, capture_environment
        observed = owner._resolve_project_path(None).resolve()
        base = observed.parent if observed.is_file() else observed
        if (base / ".synapse").resolve() != Path(owner.storage_dir).resolve():
            return _unavailable("Project memory belongs to a different scene location")
        environment = capture_environment(
            hou.applicationVersionString(),
            hou.expandString(quickmaterials.theQuickMaterialBaseFilePath))
        result = ExperienceMemory(backend, enabled=True).recall(TASK, environment, requested=True)
        if not self.is_current(token) or owner.store is not backend:
            return _unavailable("The scene changed during this suggestion request")
        result["request_token"] = token
        self._owner_identity = (id(owner), id(backend))
        result["environment"] = environment
        result["scene_file"] = hou.hipFile.path()
        return result

    def cancel(self):
        with self._lock:
            self._generation = uuid.uuid4().hex
            self._owner_identity = None
            if self._callback is None:
                return
        try:
            _on_main(self._detach_on_main)
        except Exception as exc:
            # The token is already invalid even when the host cannot detach.
            _LOG.warning("Saved-lookdev observer detach did not finish: %s", exc)

    def _detach_on_main(self):
        if threading.get_ident() != threading.main_thread().ident:
            raise RuntimeError("Scene observer cleanup requires the Houdini main thread")
        with self._lock:
            callback = self._callback
            if callback is not None:
                import hou
                hou.hipFile.removeEventCallback(callback)
                self._callback = None

    def close(self):
        with self._lock:
            self._closed = True
        self.cancel()
