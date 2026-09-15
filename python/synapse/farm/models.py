"""Versioned, bounded render plans. No host, model, UI or network access."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

SCHEMA_VERSION = 1
MAX_FRAMES = 4096
MIN_FRAME = -1_000_000
MAX_FRAME = 1_000_000
MAX_DIMENSION = 16384
MAX_SAMPLES = 65536
MAX_LIST_JOBS = 200
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z", re.ASCII)
_RANGE = re.compile(r"(-?\d+)(?:-(-?\d+)(?:[xX](\d+))?)?\Z", re.ASCII)
_RESERVED = {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)],
             *[f"LPT{i}" for i in range(1, 10)]}


class FarmError(ValueError):
    """Display-safe contract refusal, suitable for a transport error envelope."""

    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


def get_constants() -> dict:
    return {"schema_version": SCHEMA_VERSION, "max_frames": MAX_FRAMES,
            "min_frame": MIN_FRAME, "max_frame": MAX_FRAME,
            "max_dimension": MAX_DIMENSION, "max_samples": MAX_SAMPLES,
            "max_list_jobs": MAX_LIST_JOBS}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def payload_digest(value: dict) -> str:
    """Hash all canonical scope fields, excluding the digest itself."""
    return hashlib.sha256(canonical_json({k: v for k, v in value.items()
                                         if k != "digest"}).encode("utf-8")).hexdigest()


def validate_request_id(value: Any) -> str:
    if type(value) is not str or not _ID.fullmatch(value) or value.upper() in _RESERVED:
        raise FarmError("invalid_request_id", "Use a UUID or 1–64 letters, digits, underscores and hyphens for the request ID.")
    return value


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise FarmError("invalid_plan", f"{name} must be an integer between {minimum} and {maximum}.")
    return value


def parse_frames(value: Any) -> list[int]:
    """Return the sorted unique frame set; never expand an unbounded range."""
    frames: set[int] = set()
    if type(value) is list:
        if not value or len(value) > MAX_FRAMES:
            raise FarmError("invalid_frames", f"Choose between 1 and {MAX_FRAMES} frames.")
        for frame in value:
            frames.add(_integer(frame, "Frame", MIN_FRAME, MAX_FRAME))
    elif type(value) is str and 0 < len(value) <= 32768:
        parts = value.split(",")
        if len(parts) > MAX_FRAMES:
            raise FarmError("invalid_frames", "The frame selection is too large.")
        for part in parts:
            match = _RANGE.fullmatch(part.strip())
            if match is None:
                raise FarmError("invalid_frames", "Use frames such as 1001-1012x2,1040 or an integer list.")
            if any(len(group.lstrip("-")) > 7 for group in match.groups() if group):
                raise FarmError("invalid_frames", "A frame or step is outside the supported bounds.")
            start = _integer(int(match[1]), "Frame", MIN_FRAME, MAX_FRAME)
            end = _integer(int(match[2]), "Frame", MIN_FRAME, MAX_FRAME) if match[2] else start
            step = int(match[3]) if match[3] else 1
            if end < start or not 1 <= step <= (MAX_FRAME - MIN_FRAME + 1):
                raise FarmError("invalid_frames", "Frame ranges must increase and their step must be positive.")
            selected = range(start, end + 1, step)
            if len(selected) > MAX_FRAMES:
                raise FarmError("invalid_frames", f"Choose at most {MAX_FRAMES} frames.")
            frames.update(selected)
            if len(frames) > MAX_FRAMES:
                raise FarmError("invalid_frames", f"Choose at most {MAX_FRAMES} frames.")
    else:
        raise FarmError("invalid_frames", "Provide a frame range or a nonempty list of integer frames.")
    if not frames:
        raise FarmError("invalid_frames", "Select at least one frame.")
    return sorted(frames)


def absolute_path(value: Any, name: str) -> Path:
    if type(value) is not str or not value or len(value) > 4096 or any(ord(c) < 32 for c in value):
        raise FarmError("invalid_path", f"{name} must be an absolute filesystem path.")
    path = Path(value)
    if not path.is_absolute():
        raise FarmError("invalid_path", f"{name} must be an absolute filesystem path.")
    try:
        return path.resolve()
    except (OSError, ValueError) as exc:
        raise FarmError("invalid_path", f"{name} could not be resolved.") from exc


def file_identity(path: Path) -> dict:
    """Hash stable regular bytes; a changed/replaced/empty file cannot qualify."""
    if path.is_symlink() or not path.is_file():
        raise FarmError("invalid_file", "A required regular file is missing or is a symbolic link.")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
            after = os.fstat(stream.fileno())
        current = path.stat()
    except OSError as exc:
        raise FarmError("invalid_file", "A required file could not be read.") from exc
    identity = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
    if not after.st_size or identity(before) != identity(after) or identity(after) != identity(current):
        raise FarmError("changing_file", "A required file is empty or changed during verification.")
    return {"sha256": digest.hexdigest(), "size": after.st_size, "mtime_ns": after.st_mtime_ns}


def canonical_plan(payload: dict) -> dict:
    if type(payload) is not dict:
        raise FarmError("invalid_plan", "A render plan must be an object.")
    allowed = {"request_id", "source_hip", "source_node", "frames", "output_root",
               "profile_id", "width", "height", "samples"}
    if set(payload) - allowed:
        raise FarmError("invalid_plan", "The render plan contains unsupported fields.")
    request_id = validate_request_id(payload.get("request_id"))
    raw_source = payload.get("source_hip")
    source = absolute_path(raw_source, "Saved scene")
    if Path(raw_source).is_symlink() or source.suffix.lower() not in {".hip", ".hiplc", ".hipnc"}:
        raise FarmError("invalid_source", "Choose an existing saved HIP, HIPLC or HIPNC scene.")
    try:
        identity = file_identity(source)
    except FarmError as exc:
        raise FarmError("invalid_source", "The saved Houdini scene is missing, empty or changing. Save it before preparing.") from exc
    source_node = payload.get("source_node")
    if (type(source_node) is not str or len(source_node) > 1024 or not source_node.startswith("/")
            or source_node == "/" or "\\" in source_node or any(c.isspace() for c in source_node)
            or any(part in {"", ".", ".."} for part in source_node[1:].split("/"))):
        raise FarmError("invalid_source", "Choose an absolute Houdini LOP path, such as /stage/OUT.")
    profile = payload.get("profile_id", "local")
    if type(profile) is not str or not _ID.fullmatch(profile):
        raise FarmError("invalid_profile", "Choose a named render profile.")
    plan = {"schema_version": SCHEMA_VERSION, "request_id": request_id,
            "source_hip": str(source), "source_node": source_node,
            "source_sha256": identity["sha256"], "frames": parse_frames(payload.get("frames")),
            "output_root": str(absolute_path(payload.get("output_root"), "Output folder")),
            "profile_id": profile,
            "width": _integer(payload.get("width", 256), "Width", 1, MAX_DIMENSION),
            "height": _integer(payload.get("height", 256), "Height", 1, MAX_DIMENSION),
            "samples": _integer(payload.get("samples", 8), "Samples", 1, MAX_SAMPLES)}
    plan["digest"] = payload_digest(plan)
    return plan
