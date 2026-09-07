"""Carry an accepted project's scope across an owned process queue, never consent."""
import base64
import json
from pathlib import Path

from synapse.model_access import ModelAccessDenied, RequestScope, request_scope, _unique_object


def accepted_child_scope():
    """A queued child retains its parent's project and cancellation condition."""
    with request_scope() as parent:
        def parent_stopped():
            return not parent.active or (callable(parent.cancelled) and parent.cancelled())
        return RequestScope(parent.path, parent.revision, parent.generation,
                            active=not parent_stopped(), cancelled=parent_stopped)


def export_scope():
    with request_scope() as scope:
        data = {"version": 1, "path": str(scope.path), "revision": scope.revision,
                "generation": scope.generation,
                "active": scope.active and not (callable(scope.cancelled) and scope.cancelled()),
                "task_id": scope.task_id}
    return base64.urlsafe_b64encode(json.dumps(data, sort_keys=True).encode("utf-8")).decode("ascii")


def import_scope(token):
    if token is None:
        return None
    try:
        if not isinstance(token, str) or len(token) > 16384:
            raise ValueError("Invalid scope")
        data = json.loads(base64.b64decode(token, altchars=b"-_", validate=True), object_pairs_hook=_unique_object)
        if not isinstance(data, dict) or set(data) != {"version", "path", "revision", "generation", "active", "task_id"}:
            raise ValueError("Invalid scope")
        if type(data["version"]) is not int or data["version"] != 1 or type(data["active"]) is not bool:
            raise ValueError("Invalid scope")
        for key in ("path", "revision", "generation", "task_id"):
            if not isinstance(data[key], str) or len(data[key]) > (4096 if key == "path" else 512):
                raise ValueError("Invalid scope")
        if not Path(data["path"]).is_absolute():
            raise ValueError("Invalid scope")
        return RequestScope(Path(data["path"]).resolve(), data["revision"], data["generation"],
                            active=data["active"], task_id=data["task_id"])
    except (ValueError, TypeError, OSError):
        raise ModelAccessDenied("The queued task's project rules are unavailable. Start a new task from the selected project.") from None
