"""Artist render facade. Scene inspection is the only host HOM boundary.

The local journal is a farm authority, never a panel-owned memory store.
Frozen-scene export and rendering belong to the detached native backend.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from synapse.core.farm_contract import FARM_CONTROL_COMMANDS, FARM_READ_COMMANDS
_services = {}
_services_lock = threading.Lock()


def _require_local_deployment():
    if os.environ.get("SYNAPSE_DEPLOY_MODE", "local").strip().lower() != "local":
        raise ValueError("This render profile is available in local deployment only. Studio user identity and job ownership are not qualified yet.")


def farm_home() -> Path:
    override = os.environ.get("SYNAPSE_RENDER_HOME")
    if override:
        root = Path(override).expanduser()
        if not root.is_absolute():
            raise ValueError("SYNAPSE_RENDER_HOME must be an absolute local directory.")
        return root
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / ".local" / "share") / "SYNAPSE" / "render_jobs"


def _backend():
    from synapse.farm.backend import NativeTopsBackend
    return NativeTopsBackend()


def _service(*, create=True):
    root = farm_home().resolve()
    key = os.path.normcase(str(root))
    with _services_lock:
        if key in _services:
            return _services[key]
        if not create and not (root / "farm.sqlite3").is_file():
            return None
        from synapse.farm.service import FarmService
        service = FarmService(root, _backend())
        _services[key] = service
        return service


def _inspect_saved_source():
    """Cheap main-thread reads; never evaluate a Solaris stage or cook a node."""
    try:
        import hou
    except ImportError:
        return {"status": "needs_attention", "source_hip": "", "source_node": "",
                "source_nodes": [], "frames": [1, 1, 1], "unsaved": False,
                "note": "Open Houdini and save the scene to choose its Solaris output."}
    from .main_thread import run_on_main

    def inspect():
        path = hou.hipFile.path()
        unsaved = bool(hou.hipFile.hasUnsavedChanges())
        candidates = []
        for node in hou.selectedNodes():
            if node.type().category() == hou.lopNodeTypeCategory():
                candidates.append(node)
        stage = hou.node("/stage")
        display = stage.displayNode() if stage is not None else None
        if display is not None and all(n.path() != display.path() for n in candidates):
            candidates.append(display)
        start, end = hou.playbar.frameRange()
        saved = bool(path and Path(path).is_file())
        note = ("Save the scene before preparing this render." if unsaved or not saved
                else "Choose a Solaris output to prepare." if not candidates
                else "Ready to prepare a separate copy of the saved scene.")
        return {"status": "ready" if saved and not unsaved and candidates else "needs_attention",
                "source_hip": path if saved else "", "unsaved": unsaved,
                "source_node": candidates[0].path() if candidates else "",
                "source_nodes": [{"path": n.path(), "label": n.path()} for n in candidates],
                "frames": [int(start), int(end), 1], "note": note}
    return run_on_main(inspect, timeout=5.0, label="farm_inspect")


class FarmHandlerMixin:
    def _handle_farm_inspect(self, payload):
        return _inspect_saved_source()

    def _handle_farm_capabilities(self, payload):
        result = _backend().capabilities()
        try:
            _require_local_deployment()
        except ValueError as exc:
            for profile in result.get("profiles", []):
                profile.update(available=False, reason=str(exc))
        return result

    def _handle_farm_prepare(self, payload):
        _require_local_deployment()
        source = payload.get("source_hip", "")
        inspection = _inspect_saved_source()
        active = inspection.get("source_hip", "")
        same_source = False
        if active and source:
            try:
                same_source = os.path.samefile(source, active)
            except OSError:
                same_source = os.path.normcase(str(Path(source).resolve())) == os.path.normcase(str(Path(active).resolve()))
        if same_source:
            if inspection.get("unsaved"):
                raise ValueError("Save the scene first so the prepared render includes your changes.")
        return _service().prepare(dict(payload))

    def _handle_farm_submit(self, payload):
        _require_local_deployment()
        return _service().submit(payload.get("request_id", ""), payload.get("digest", ""))

    def _handle_farm_jobs(self, payload):
        _require_local_deployment()
        service = _service(create=False)
        return {"jobs": service.list_jobs(limit=payload.get("limit", 20)) if service else []}

    def _handle_farm_job(self, payload):
        _require_local_deployment()
        service = _service(create=False)
        if service is None:
            raise ValueError("No render history exists here yet. Prepare a render first.")
        return service.refresh(payload.get("request_id", ""))

    def _handle_farm_cancel(self, payload):
        _require_local_deployment()
        service = _service(create=False)
        if service is None:
            raise ValueError("No render history exists here. No cancellation was sent.")
        return service.cancel(payload.get("request_id", ""))
