"""Bounded, read-only selection observations with captured-identity ownership.

No Qt or Houdini object is retained here. A daemon dispatches the cheap scan to
the host's main thread; late results cannot publish after refresh or close.
"""
from __future__ import annotations

from copy import deepcopy
import json
import re
import threading


DEFAULT_REQUEST = {"depth": 0, "include_parameters": False,
                   "include_geometry": False, "max_nodes": 200, "max_edges": 2000}


def inspection_request(snapshot):
    """Capture the exact observed target, refusing partial/unidentified scans."""
    if (not isinstance(snapshot, dict) or snapshot.get("schema") != "synapse-selection-v1"
            or snapshot.get("complete") is not True or snapshot.get("can_pin") is not True):
        raise ValueError("A complete, identified selection is needed. Refresh the inspection.")
    identities = snapshot.get("identities")
    scene = snapshot.get("scene", {})
    if (not isinstance(identities, list) or not identities
            or not isinstance(scene, dict)
            or any(not isinstance(scene.get(key), str) or not scene[key].strip()
                   for key in ("session_token", "hip_path"))
            or not isinstance(snapshot.get("topology_hash"), str)
            or re.fullmatch(r"[0-9a-f]{64}", snapshot["topology_hash"]) is None):
        raise ValueError("The capture has no verifiable node or scene identity.")
    rows = []
    for row in identities:
        if (not isinstance(row, dict) or not isinstance(row.get("path"), str)
                or not row["path"].startswith("/") or type(row.get("session_id")) is not int):
            raise ValueError("A captured node identity is unavailable.")
        rows.append({"path": row["path"], "session_id": row["session_id"]})
    if len({row["path"] for row in rows}) != len(rows):
        raise ValueError("The capture contains ambiguous node identities.")
    return dict(DEFAULT_REQUEST, node_paths=[row["path"] for row in rows],
                expected_identities=rows,
                expected_scene={"session_token": scene["session_token"], "hip_path": scene["hip_path"]},
                expected_topology_hash=snapshot["topology_hash"])


def _check_capture(snapshot, request):
    current = inspection_request(snapshot)
    for key in ("expected_identities", "expected_scene", "expected_topology_hash"):
        if current[key] != request[key]:
            raise ValueError("SELECTION_STALE: captured nodes, scene or wiring changed. Unpin or refresh the live inspection.")


def prepare_captured_prompt(action_id, snapshot):
    """Local facts only; this context is never an input to the JEV ranker."""
    from synapse.jev.selection_actions import prepare_prompt
    prompt = prepare_prompt(action_id)
    request = inspection_request(snapshot)
    facts = {"inspection_request": request,
             "observed_count": snapshot.get("observed_count"),
             "wires": snapshot.get("wires", {}), "warnings": snapshot.get("warnings", [])}
    return (prompt + "\n\nCaptured inspection context — not an edit sandbox. "
            "Do not substitute the current viewport selection. Re-inspect these exact identities "
            "with the scene and topology preconditions before relying on them. "
            "This pin does not constrain all editing tools; any proposed edit needs its own validation.\n"
            + json.dumps(facts, ensure_ascii=False, sort_keys=True, indent=2))


def scan_selection(request, cancelled):
    """Called only by the daemon. Queued cancelled reads become no-ops."""
    from synapse.server.main_thread import run_on_main
    from synapse.server.introspection import inspect_selection
    def read():
        if cancelled():
            raise ValueError("SELECTION_UNAVAILABLE: inspection was cancelled")
        return inspect_selection(**request)
    if cancelled():
        raise ValueError("SELECTION_UNAVAILABLE: inspection was cancelled")
    return run_on_main(read, timeout=3.0, record_stall=False, record_wait=False,
                       label="panel:inspect_selection")


def _launch(fn):
    threading.Thread(target=fn, name="synapse-selection-inspection", daemon=True).start()


class InspectionController:
    """One active read and one replaceable pending request per inspector.

    The view polls copies. Preparing a prompt is another captured read, never
    a generation request or a mutation. Closing does not wait for the host.
    """
    def __init__(self, *, scanner=scan_selection, launch=_launch):
        self._scanner, self._launch = scanner, launch
        self._lock = threading.RLock()
        self._revision, self._closed, self._running = 0, True, False
        self._pending = self._cancel = self._snapshot = self._pin = self._prepared = None
        self._status, self._error = "closed", ""

    def view(self):
        with self._lock:
            return {"revision": self._revision, "closed": self._closed,
                    "status": self._status, "error": self._error,
                    "pinned": self._pin is not None, "snapshot": deepcopy(self._snapshot)}

    def is_current(self, revision):
        with self._lock:
            return not self._closed and revision == self._revision

    def open(self):
        with self._lock:
            self._closed = False
        self.refresh()

    def close(self):
        with self._lock:
            self._closed = True
            self._revision += 1
            if self._cancel is not None:
                self._cancel.set()
            self._pending = self._prepared = None
            self._status = "closed"

    def refresh(self):
        with self._lock:
            request = deepcopy(self._pin) if self._pin is not None else dict(DEFAULT_REQUEST)
        self._submit(request)

    def pin(self):
        with self._lock:
            if self._status != "ready":
                raise ValueError("Wait for a complete inspection before pinning.")
            self._pin = inspection_request(self._snapshot)
            self._revision += 1

    def unpin(self):
        with self._lock:
            self._pin = None
        self.refresh()

    def prepare(self, action_id):
        from synapse.jev.selection_actions import prepare_prompt
        prepare_prompt(action_id)  # Unknown actions fail before any host read.
        with self._lock:
            if self._status != "ready":
                raise ValueError("Refresh a complete inspection before preparing a prompt.")
            request = inspection_request(self._snapshot)
        self._submit(request, action_id)

    def take_prepared(self):
        with self._lock:
            prompt, self._prepared = self._prepared, None
            return prompt

    def _submit(self, request, action_id=None):
        with self._lock:
            if self._closed:
                return
            self._revision += 1
            if self._cancel is not None:
                self._cancel.set()
            self._cancel = threading.Event()
            self._pending = (self._revision, deepcopy(request), action_id, self._cancel)
            self._prepared, self._error = None, ""
            self._status = "validating" if action_id else "loading"
            start = not self._running
            self._running = True
        if start:
            try:
                self._launch(self._drain)
            except Exception as exc:
                with self._lock:
                    self._running = False
                    self._pending = None
                    if not self._closed:
                        self._status = "unavailable"
                        self._error = "Inspection could not start: " + str(exc)

    def _drain(self):
        while True:
            with self._lock:
                job, self._pending = self._pending, None
                if job is None:
                    self._running = False
                    return
            revision, request, action_id, cancel = job
            if cancel.is_set():
                continue
            result, prompt, error = None, None, ""
            try:
                result = self._scanner(request, cancel.is_set)
                if isinstance(result, dict) and "success" in result:
                    if result.get("success") is not True:
                        raise ValueError(result.get("error") or "SELECTION_UNAVAILABLE: inspection failed")
                    result = result.get("data")
                if not isinstance(result, dict) or result.get("schema") != "synapse-selection-v1":
                    raise ValueError("SELECTION_UNAVAILABLE: the host returned no selection snapshot")
                if "expected_identities" in request:
                    _check_capture(result, request)
                if action_id:
                    prompt = prepare_captured_prompt(action_id, result)
            except Exception as exc:
                error = str(exc) or "Selection inspection is unavailable."
            with self._lock:
                if self._closed or revision != self._revision or cancel.is_set():
                    continue
                if error:
                    self._error = error
                    self._status = "stale" if "SELECTION_STALE:" in error else "unavailable"
                else:
                    self._snapshot = deepcopy(result)
                    self._prepared = prompt
                    self._status = "ready"
