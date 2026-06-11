"""
Show configuration -- per-show/per-scene pipeline conventions (M2-I).

File-based, layered JSON config for the conventions that were hardcoded
across the render/compose handlers (default resolutions, output roots,
frame padding, naming). Sources, strongest first (per-key -- the first
layer that defines a dotted key wins):

    1. env:  SYNAPSE_SHOW_CONFIG = path to a JSON file
    2. hip:  <hip_dir>/.synapse/show.json   (scene -- most specific)
    3. job:  <job_dir>/.synapse/show.json   (show)
    4. built-in DEFAULTS (exactly today's hardcoded values)

Precedence is env > $HIP > $JOB > defaults: scene-specific overrides
show-wide, matching the three-tier memory hierarchy and the VFX
shot-overrides-show convention. Tokens in values ($HIP, $F...) stay
UNEXPANDED here -- consumers expand at use time.

Loader shape mirrors sessions.load_deploy_config: a malformed file
degrades to defaults with a warning, never raises.

Scope: file-based only. Recording the effective show config into
agent.usd (and any prim-name/sanitizer interaction) is the D-3/Gold RFC
lane (docs/RFC_agent_usd_ledger.md) -- deliberately not done here, and
$JOB/claude/ (the memory lane) is deliberately not used for machine
config.
"""

import copy
import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import hou
    _HOU_AVAILABLE = True
except ImportError:
    hou = None  # type: ignore[assignment]
    _HOU_AVAILABLE = False

_ENV_VAR = "SYNAPSE_SHOW_CONFIG"
_MISSING = object()

# Built-in defaults -- EXACTLY today's hardcoded values, so that with no
# config files present every constructed path/resolution is byte-identical
# to the pre-M2-I behavior. Every key is individually optional in files.
# color.* are forward keys for M2-G ("" = use $OCIO / Houdini defaults).
DEFAULTS = {
    "resolution": {
        "render": [1920, 1080],
        "preview": [1280, 720],
        "capture": [800, 600],
    },
    "output": {
        "render_root": "$HIP/.synapse/renders",
        "report_root": "$HIP/.synapse/render_reports",
        "sequence_root": "$HIP/render",
        "cache_root": "$HIP/cache",
    },
    "frames": {
        "padding": 4,
        "fps": 24.0,
    },
    "naming": {
        "render_basename": "render",
        "versioning": "timestamp",
    },
    "color": {
        "ocio": "",
        "display": "",
        "view": "",
    },
}


def _load_json(path) -> Optional[dict]:
    """Load a JSON object from *path*; None on missing/unreadable/malformed.

    Missing file is the normal case (silent). Malformed/unreadable files
    warn and degrade to None -- the sessions.load_deploy_config idiom.
    No value validation/coercion: call sites keep their existing int()/list
    coercions.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(
            "Couldn't load show config %s: %s -- using defaults", path, e
        )
        return None
    if not isinstance(data, dict):
        logger.warning(
            "Show config %s is not a JSON object -- using defaults", path
        )
        return None
    return data


def _walk(data: dict, dotted_key: str):
    """Resolve a dotted key against a nested dict; _MISSING when absent."""
    cur = data
    for part in dotted_key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return _MISSING
        cur = cur[part]
    return cur


def _deep_merge(dst: dict, src: dict) -> None:
    for key, val in src.items():
        if isinstance(val, dict) and isinstance(dst.get(key), dict):
            _deep_merge(dst[key], val)
        else:
            dst[key] = copy.deepcopy(val)


class ShowConfig:
    """Ordered config layers (strongest first) + the files they came from."""

    def __init__(self, layers, source_files):
        self._layers = list(layers)
        self.source_files: Dict[str, str] = dict(source_files)

    def lookup(self, dotted_key: str, default=_MISSING):
        """Return (value, source_name) for the first layer defining the key.

        Source names: "env" / "hip" / "job" / "default". Raises KeyError
        when the key is defined nowhere and no *default* was given.
        """
        for name, data in self._layers:
            val = _walk(data, dotted_key)
            if val is not _MISSING:
                return val, name
        if default is _MISSING:
            raise KeyError(dotted_key)
        return default, "default"

    def get(self, dotted_key: str, default=None):
        """Value only -- lookup() without the source."""
        return self.lookup(dotted_key, default)[0]

    def as_dict(self) -> dict:
        """Effective config: deep merge weakest -> strongest."""
        merged: dict = {}
        for _name, data in reversed(self._layers):
            _deep_merge(merged, data)
        return merged


def resolve_show_dirs() -> Tuple[Optional[str], Optional[str]]:
    """Resolve ($HIP dir, $JOB dir) from the live Houdini session.

    CONTRACT: main-thread only when hou is live. Off-main handlers must
    marshal it -- ``get_show_config(*run_on_main(resolve_show_dirs))`` --
    or pass dirs explicitly. Returns (None, None) headless, so
    get_show_config() then serves env + DEFAULTS only.
    """
    if not _HOU_AVAILABLE or hou is None:
        return None, None
    try:
        hip = hou.text.expandString("$HIP")
    except Exception:
        hip = None
    if not isinstance(hip, str) or not hip or hip == "$HIP":
        hip = None
    try:
        job = hou.getenv("JOB", hip)
    except Exception:
        job = hip
    if not isinstance(job, str) or not job:
        job = hip
    return hip, job


# Cache keyed by the resolved (env_path, hip_file, job_file) tuple --
# switching scenes changes the key, so it self-invalidates. No mtime
# polling; reload_show_config() is the explicit refresh.
_cache: Dict[tuple, ShowConfig] = {}


def get_show_config(hip_dir: Optional[str] = None,
                    job_dir: Optional[str] = None) -> ShowConfig:
    """Cached show config for the given (or live-session) hip/job dirs.

    When both dirs are None, resolves them via resolve_show_dirs() --
    inheriting its main-thread contract.
    """
    if hip_dir is None and job_dir is None:
        hip_dir, job_dir = resolve_show_dirs()
    env_path = os.environ.get(_ENV_VAR, "") or None
    hip_file = str(Path(hip_dir) / ".synapse" / "show.json") if hip_dir else None
    job_file = str(Path(job_dir) / ".synapse" / "show.json") if job_dir else None
    key = (env_path, hip_file, job_file)
    cfg = _cache.get(key)
    if cfg is None:
        layers = []
        source_files = {}
        for name, path in (("env", env_path), ("hip", hip_file), ("job", job_file)):
            if not path:
                continue
            data = _load_json(path)
            if data is not None:
                layers.append((name, data))
                source_files[name] = str(path)
        layers.append(("default", DEFAULTS))
        cfg = ShowConfig(layers, source_files)
        _cache[key] = cfg
    return cfg


def reload_show_config() -> None:
    """Drop all cached configs -- next get_show_config() re-reads the files."""
    _cache.clear()


_VERSION_DIR_RE = re.compile(r"^v(\d+)$")


def next_version_dir(root: str) -> str:
    """Next vNNN child of *root* (v001 when root is missing or has none).

    Pure Python, no mkdir -- the caller's existing directory creation
    handles that.
    """
    highest = 0
    try:
        for entry in os.listdir(root):
            m = _VERSION_DIR_RE.match(entry)
            if m and os.path.isdir(os.path.join(root, entry)):
                highest = max(highest, int(m.group(1)))
    except OSError:
        pass
    return os.path.join(root, f"v{highest + 1:03d}")
