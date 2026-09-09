"""Process-lifetime admission and retention for interactive panel workers.

The shipped panel loader preserves host modules. UI generations share this
authority; it constructs no scene, store, provider or QWidget. Callbacks run outside
the lock, and only the exact reservation or completing worker can release it.
"""
from __future__ import annotations

import threading


class PanelWorkerRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._reservation = None
        self._worker = None

    def __bool__(self):
        with self._lock:
            return self._reservation is not None or self._worker is not None

    def __len__(self):
        return int(bool(self))

    def __contains__(self, worker):
        with self._lock:
            return self._worker is worker and worker is not None

    def reserve(self):
        """Reserve before UI setup can reenter; None means another task owns it."""
        with self._lock:
            if self._reservation is not None or self._worker is not None:
                return None
            self._reservation = object()
            return self._reservation

    def bind(self, reservation, worker):
        """Transfer the exact admission to a strong worker reference before start."""
        with self._lock:
            if (reservation is None or reservation is not self._reservation
                    or self._worker is not None or worker is None):
                raise RuntimeError("This panel task no longer owns its worker admission.")
            self._worker = worker
            self._reservation = None

    def release_reservation(self, reservation):
        """Release abandoned setup; never release an already bound worker."""
        with self._lock:
            if reservation is not None and reservation is self._reservation:
                self._reservation = None

    def release(self, worker):
        """Release only this worker once, after completion or a failed start."""
        with self._lock:
            if worker is None or worker is not self._worker:
                return False
            self._worker = None
            return True


active_workers = PanelWorkerRegistry()
