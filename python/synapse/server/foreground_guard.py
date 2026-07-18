"""Foreground-render guard — the refusal half of the Indie render fix.

An in-process render CAPTURES Houdini's main thread for its entire duration
(handlers_render.py node.render() — the confirmed freeze site). On licenses
where the out-of-process husk path cannot load the Karma delegate (Indie —
verified live 2026-07-17: ``Unable to load render plugin: karma``, zero
output, ``--indie`` flag included), the render must stay in-process. The only
real protections are therefore: refuse to START a foreground render that
would hold the main thread too long, and bound the bridge-side wait so the
panel/bridge stay alive (handlers_render._handle_render_bounded).

This module is the refusal half. Pure Python — no ``hou`` import — so it is
CI-testable and callable from any thread.

Design notes (solution-wave crucible, 2026-07-17):

- A resolution x samples budget is honest for Karma CPU / Mantra: render time
  scales with pixels x samples with no fixed floor.
- It is DISHONEST for Karma XPU: the first render after a Houdini install or
  NVIDIA driver update pays a fixed OptiX kernel-compile cost (documented up
  to ~2 minutes — solaris/karma_xpu.html) INDEPENDENT of resolution. The live
  freeze incident was a 64x64 sphere, which passes any sane pixel budget. The
  only sound XPU gate is cache WARMTH, so that is what we probe: the OptiX
  cache directory is per-major-release (karma_precompile.html:
  %LOCALAPPDATA%/NVIDIA/OptixCache/Houdini<major>) and empty exactly when the
  compile cost is pending.
"""

from __future__ import annotations

import os
from typing import Dict, Optional

# Env override for the OptiX cache dir — used by tests and non-standard
# installs. When unset, the documented per-major default is probed.
OPTIX_CACHE_ENV = "SYNAPSE_OPTIX_CACHE_DIR"

# Houdini major.minor the cache dir is keyed on. The live build is 22.0.368;
# a point release keeps the same major dir, a major upgrade re-colds it.
HOUDINI_MAJOR = "22.0"

# Per-engine foreground budgets: (allow_pixels, deny_pixels, allow_samples).
# Between allow and deny -> "warn" (allowed, advisory attached). Above deny ->
# refused unless force_foreground. Rationale per row:
#   karma_xpu  WARM cache: pathtrace on the device; 512^2 warm completes in
#              seconds on a 4090. (A COLD cache never reaches this table —
#              it is refused outright above.)
#   karma_cpu  256^2 x 16 completes in a few seconds on the 7965WX (48
#              cores); a foreground 1080p CPU pathtrace holds the UI minutes.
#   karma      unknown Karma variant — CPU-conservative numbers.
#   mantra     slowest per-AA-sample renderer here; tiny sample budget.
#   opengl     GL grab, near-instant; the risk is VRAM not main-thread time.
_BUDGETS: Dict[str, tuple] = {
    "karma_xpu": (512 * 512, 1024 * 1024, 64),
    "karma_cpu": (256 * 256, 1024 * 1024, 16),
    "karma": (256 * 256, 1024 * 1024, 16),
    "mantra": (256 * 256, 1024 * 1024, 3),
    "opengl": (1024 * 1024, 4096 * 4096, None),
}


def optix_cache_state(houdini_major: str = HOUDINI_MAJOR) -> Dict:
    """Probe the Karma XPU OptiX kernel-cache directory.

    warm=True means at least one cache file exists — the fixed first-render
    compile cost has already been paid on this install+driver combination.
    Never raises; an unreadable dir reports cold (the honest default: cold
    means "expect the compile stall").
    """
    override = os.environ.get(OPTIX_CACHE_ENV)
    if override:
        path = override
    else:
        local = os.environ.get("LOCALAPPDATA") or os.path.expanduser(
            os.path.join("~", "AppData", "Local")
        )
        path = os.path.join(
            local, "NVIDIA", "OptixCache", "Houdini" + houdini_major
        )

    exists = os.path.isdir(path)
    warm = False
    if exists:
        try:
            for _root, _dirs, files in os.walk(path):
                if files:
                    warm = True
                    break
        except OSError:
            warm = False
    return {"path": path, "exists": exists, "warm": warm}


def _refuse(verdict: Dict, force: bool, reason: str, suggestion: str) -> None:
    """Mark a refusal on the verdict; force downgrades it to a carried warning."""
    verdict["reason"] = reason
    verdict["suggestion"] = suggestion
    if force:
        verdict["allow"] = True
        verdict["level"] = "forced"
        verdict["forced"] = True
    else:
        verdict["allow"] = False
        verdict["level"] = "deny"


def assess_foreground_render(
    engine: Optional[str],
    width: Optional[int] = None,
    height: Optional[int] = None,
    samples: Optional[int] = None,
    force: bool = False,
    cache_state: Optional[Dict] = None,
) -> Dict:
    """Assess whether a FOREGROUND in-process render is safe to start.

    Returns a verdict dict:
        allow (bool)    — False means refuse (caller raises with the reason).
        level (str)     — "allow" | "warn" | "forced" | "deny".
        reason / suggestion (str) — populated for warn/forced/deny.
        engine (str)    — normalized engine key the budgets used.
        optix_cache     — attached for karma_xpu only.

    Unknown engine or unknown resolution -> silent allow (the budget is a
    best-effort net, not a gate on paths it cannot see). The ONE exception is
    a cold-cache karma_xpu, which is refused regardless of resolution — the
    compile cost does not care about pixels, so blindness is no excuse.
    """
    key = (engine or "").lower()
    # F1 (crucible): _detect_karma_engine can return delegate-flavored ids —
    # a usdrender ROP's 'renderer' parm evals to Hydra delegate ids like
    # BRAY_HdKarma, yielding "karma_bray_hdkarma". Unknown karma_* variants
    # take the conservative generic-karma budget row instead of silently
    # missing every row (which would wave a 4K foreground render through).
    # Explicit xpu/cpu substrings were already resolved upstream.
    budget_key = key if key in _BUDGETS else (
        "karma" if key.startswith("karma") else key)
    verdict: Dict = {
        "allow": True,
        "level": "allow",
        "engine": key,
        "reason": "",
        "suggestion": "",
        "forced": False,
    }

    if key == "karma_xpu":
        cache = cache_state if cache_state is not None else optix_cache_state()
        verdict["optix_cache"] = {"path": cache["path"], "warm": cache["warm"]}
        if not cache["warm"]:
            _refuse(
                verdict,
                force,
                reason=(
                    "the Karma XPU OptiX kernel cache is COLD (%s) — the "
                    "first XPU render compiles kernels for up to ~2 minutes "
                    "REGARDLESS of resolution, holding Houdini's whole UI "
                    "(the live 64x64 freeze was exactly this)." % cache["path"]
                ),
                suggestion=(
                    "Warm it once at a moment you choose "
                    "(scripts/prewarm_xpu.py, or Render menu > Pre-compile "
                    "Karma XPU Render Kernels), switch the Karma engine to "
                    "cpu, or pass force_foreground=true to proceed anyway."
                ),
            )
            if not verdict["allow"]:
                return verdict

    if budget_key in _BUDGETS and width and height:
        allow_px, deny_px, allow_samples = _BUDGETS[budget_key]
        px = int(width) * int(height)
        over_samples = bool(
            samples is not None
            and allow_samples is not None
            and int(samples) > allow_samples
        )
        if px > deny_px:
            _refuse(
                verdict,
                force,
                reason=(
                    "a %dx%d foreground %s render would hold Houdini's main "
                    "thread (and the whole UI) for its full duration."
                    % (int(width), int(height), key)
                ),
                suggestion=(
                    "Reduce the resolution (<=%d px total for %s), or pass "
                    "force_foreground=true to accept the UI freeze "
                    "deliberately." % (allow_px, key)
                ),
            )
        elif verdict["level"] == "allow" and (px > allow_px or over_samples):
            verdict["level"] = "warn"
            verdict["reason"] = (
                "%dx%d%s exceeds the comfortable foreground budget for %s — "
                "expect the UI to pause for the render's duration."
                % (
                    int(width),
                    int(height),
                    (" @ %d samples" % int(samples)) if over_samples else "",
                    key,
                )
            )
            verdict["suggestion"] = (
                "The bridge stays responsive (bounded wait), but the Houdini "
                "UI will freeze until the render completes."
            )

    return verdict
