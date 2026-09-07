"""Accept image-decoder evidence only when every expected file still matches."""

from __future__ import annotations

from pathlib import Path
import os
import re

from .models import FarmError, file_identity


def verify_completion(plan: dict, job_dir: Path, result: dict) -> list[dict]:
    """Backend owns full image decoding. This boundary checks its complete receipt.

    A decoder must explicitly certify every frame and its dimensions. We bind
    that evidence to the stable bytes currently in the owned output directory.
    Merely listing existing files or receiving a successful process exit fails.
    """
    expected = plan["frames"]
    evidence = result.get("verification")
    verified = result.get("verified_frames")
    def exact(values):
        return (type(values) is list and all(type(f) is int for f in values)
                and len(values) == len(expected) and sorted(values) == expected)
    if (type(evidence) is not dict or evidence.get("verified") is not True
            or not exact(evidence.get("frames")) or not exact(verified)):
        raise FarmError("verification_failed", "Complete output verification for the requested frame set is missing.")
    outputs = result.get("outputs")
    if type(outputs) is not list or len(outputs) != len(expected):
        raise FarmError("verification_failed", "The verified output set does not match the requested frames.")
    owned = job_dir.resolve()
    seen_frames, seen_paths, accepted = set(), set(), []
    for output in outputs:
        if type(output) is not dict or output.get("verified") is not True:
            raise FarmError("verification_failed", "An output has no successful image verification receipt.")
        frame, name = output.get("frame"), output.get("path")
        if type(frame) is not int or frame not in expected or frame in seen_frames or type(name) is not str:
            raise FarmError("verification_failed", "An output frame is missing, duplicated or unexpected.")
        path = Path(name)
        if not path.is_absolute() or path.is_symlink() or not path.resolve().is_relative_to(owned):
            raise FarmError("verification_failed", "A verified image is outside this render request's output folder.")
        resolved = str(path.resolve())
        if os.path.normcase(resolved) in seen_paths:
            raise FarmError("verification_failed", "More than one frame points to the same output image.")
        if (type(output.get("width")) is not int or type(output.get("height")) is not int
                or (output["width"], output["height"]) != (plan["width"], plan["height"])):
            raise FarmError("verification_failed", "An output resolution differs from the reviewed plan.")
        digest = output.get("sha256")
        if (type(digest) is not str or re.fullmatch(r"[a-f0-9]{64}", digest) is None
                or type(output.get("size")) is not int or output["size"] <= 0):
            raise FarmError("verification_failed", "An output receipt has no valid file identity.")
        try:
            identity = file_identity(path)
        except FarmError as exc:
            raise FarmError("verification_failed", "A verified output is missing, empty or changing.") from exc
        if (identity["sha256"], identity["size"]) != (digest, output["size"]):
            raise FarmError("verification_failed", "An image changed after the backend verified it.")
        seen_frames.add(frame)
        seen_paths.add(os.path.normcase(resolved))
        accepted.append({"frame": frame, "path": resolved, "sha256": digest,
                         "size": identity["size"], "width": output["width"],
                         "height": output["height"], "verified": True})
    if seen_frames != set(expected):
        raise FarmError("verification_failed", "Required verified images are missing.")
    return sorted(accepted, key=lambda output: output["frame"])
