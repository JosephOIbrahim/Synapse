"""The ``VerifiedClaim`` Floor hook — "verified" is a reserved word (v5 §4a.2).

A claim may use the word "verified" ONLY when it names the rung AND the layer it
cleared, backed by a fired eval signal against a named build, with an in-repo
artifact. ``doc_only``/``V0_membership`` (existence/prose) may NOT back "verified."
This is the ``dir()``-hard-gate discipline generalised into a data structure.

Pure: stdlib only, zero ``hou``/``pxr``. Rung scale single-sourced from
:mod:`synapse.science.rungs`.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import List

from synapse.science.rungs import VERIFYING_RUNGS, LAYERS, migrate_verified_by


def _is_outside_vc(path: str) -> bool:
    """True if ``path`` is NOT an in-repo relative path → a rejection (v5 §4a.2).

    Cross-OS hard: normalizes separators (so a Windows ``..\\`` traversal is caught,
    not just POSIX ``../``), rejects absolute / drive-rooted / separator-rooted paths
    and any ``..`` parent-escape."""
    p = (path or "").strip()
    if not p:
        return True
    norm = os.path.normpath(p)
    parts = re.split(r"[\\/]", norm)
    drive_relative = len(p) > 1 and p[1] == ":"
    rooted = p.startswith("/") or p.startswith("\\")
    return os.path.isabs(p) or drive_relative or rooted or ".." in parts


class FloorViolation(ValueError):
    """Raised when something claims "verified" above the rung/layer it reached."""


@dataclass
class VerifiedClaim:
    """v5 §4a.2 — the reserved-word "verified" contract.

    ``verified_by`` is normalised through the rung shim; only a VERIFYING rung
    (V1_cook / V1_output / V1-degraded) may back a verified claim. ``against_build``
    is mandatory (Task B build-pinning). ``artifact_path`` must be an in-repo
    (relative) path — an outside-VC path is itself a rejection (v5 §4a.2)."""

    eval_signal_fired: bool = False
    eval_signal: str = ""
    verified_by: str = ""
    verified_layer: str = ""
    artifact_path: str = ""
    against_build: str = ""

    def reasons(self) -> List[str]:
        """Return every reason this is NOT a valid verified claim ([] = valid)."""
        out: List[str] = []
        if not self.eval_signal_fired:
            out.append("eval_signal_fired is False — no signal, no verification")
        rung = migrate_verified_by(self.verified_by)
        if rung not in VERIFYING_RUNGS:
            out.append(
                f"verified_by={self.verified_by!r} (→ {rung or 'unknown'!r}) may not "
                f"back 'verified' — only {VERIFYING_RUNGS} do (doc_only/V0_membership cannot)"
            )
        if self.verified_layer not in LAYERS:
            out.append(
                f"verified_layer={self.verified_layer!r} not in {LAYERS} — name the layer verified"
            )
        if not (self.against_build or "").strip():
            out.append("against_build is empty — every VerifiedClaim names its build (Task B)")
        path = (self.artifact_path or "").strip()
        if not path:
            out.append("artifact_path is empty — provenance or it didn't happen")
        elif _is_outside_vc(path):
            # Absolute / drive-rooted / traversal (either separator) == outside VC.
            out.append(f"artifact_path {path!r} is not an in-repo relative path (outside-VC = reject)")
        return out

    def is_valid(self) -> bool:
        return not self.reasons()


def assert_verified_claim(claim: VerifiedClaim) -> VerifiedClaim:
    """Fail-closed gate: raise :class:`FloorViolation` if ``claim`` cannot back the
    reserved word "verified". Returns the claim on success (chainable)."""
    problems = claim.reasons()
    if problems:
        raise FloorViolation(
            "Not a valid VerifiedClaim — cannot assert 'verified':\n  - "
            + "\n  - ".join(problems)
        )
    return claim
