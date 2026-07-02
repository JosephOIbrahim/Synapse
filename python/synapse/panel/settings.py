"""Panel settings — persisted engine/model picks + the Custom provider config.

One JSON file at ``<repo>/.synapse/panel_settings.json`` (install-scoped state;
``/.synapse/`` is gitignored). Repo root is resolved by package-absolute path
(the ``host/auth.py`` idiom) — Houdini launches from an unrelated CWD.

Schema v1::

    {"version": 1,
     "provider_id": "claude",
     "model_by_provider": {"claude": "claude-sonnet-4-6", ...},
     "custom": {"base_url": "", "model": "", "key_env": ""}}

``load_settings`` returns defaults on a missing/corrupt/unshaped file — it
never raises and never blocks boot (the ``_load_dotenv`` posture).
``save_settings`` writes atomically (tmp + ``os.replace``), best-effort.
Qt-free, hou-free.
"""
from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

SETTINGS_VERSION = 1

_DEFAULTS = {
    "version": SETTINGS_VERSION,
    "provider_id": "claude",
    "model_by_provider": {},
    "custom": {"base_url": "", "model": "", "key_env": ""},
}


def _repo_root() -> Path:
    """``settings.py`` lives at ``<root>/python/synapse/panel/settings.py`` →
    ``parents[3]`` is the repo root (the ``auth.py`` idiom)."""
    return Path(__file__).resolve().parents[3]


def settings_path() -> Path:
    return _repo_root() / ".synapse" / "panel_settings.json"


def default_settings() -> dict:
    return copy.deepcopy(_DEFAULTS)


def load_settings(path: Path | None = None) -> dict:
    """Read + sanitize the settings file; defaults on any failure."""
    out = default_settings()
    try:
        data = json.loads((path or settings_path()).read_text(encoding="utf-8"))
    except Exception:
        return out
    if not isinstance(data, dict):
        return out
    if isinstance(data.get("provider_id"), str) and data["provider_id"]:
        out["provider_id"] = data["provider_id"]
    mbp = data.get("model_by_provider")
    if isinstance(mbp, dict):
        out["model_by_provider"] = {
            k: v for k, v in mbp.items()
            if isinstance(k, str) and isinstance(v, str) and v
        }
    cust = data.get("custom")
    if isinstance(cust, dict):
        for key in ("base_url", "model", "key_env"):
            v = cust.get(key)
            if isinstance(v, str):
                out["custom"][key] = v.strip()
    return out


def save_settings(settings: dict, path: Path | None = None) -> bool:
    """Atomic write (tmp + ``os.replace``). Best-effort — returns False rather
    than raise (a locked/read-only disk must never break a provider switch)."""
    target = path or settings_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(settings, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, target)
        return True
    except Exception as exc:
        logger.debug("panel settings save skipped: %s", exc)
        return False


def merged_model_picks(settings: dict, defaults: dict) -> dict:
    """Persisted ``model_by_provider`` merged over the registry defaults —
    unknown provider ids are dropped (a retired engine never resurrects)."""
    out = dict(defaults)
    for pid, mid in (settings.get("model_by_provider") or {}).items():
        if pid in out and isinstance(mid, str) and mid:
            out[pid] = mid
    return out
