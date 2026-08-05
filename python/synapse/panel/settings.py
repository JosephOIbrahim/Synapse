"""Panel settings — persisted engine/model picks + the Custom provider config.

One JSON file at ``<repo>/.synapse/panel_settings.json`` (install-scoped state;
``/.synapse/`` is gitignored). Repo root is resolved by package-absolute path
(the ``host/auth.py`` idiom) — Houdini launches from an unrelated CWD.

Schema v3::

    {"version": 3,
     "profile": "expert",              # curious | expert | ml — exactly three
     "fresh_install": true,            # picker flag; see load_settings
     "provider_id": "claude",
     "model_by_provider": {"claude": "claude-sonnet-4-6", ...},
     "model_choice": {"mode": "exact", "value": "claude-sonnet-4-6"},
     "custom": {"base_url": "", "model": "", "key_env": ""},
     "composer_height": null}          # int, the artist's dragged composer
                                       # height; null = never dragged → the
                                       # panel opens it centred (L5-22)

``model_choice`` is the profile-aware pick: ``curious`` writes ``semantic``
(``free_local`` | ``balanced`` | ``best``), ``expert``/``ml`` write ``exact``
model ids. A semantic value becomes a concrete id ONLY at compose time
(:func:`resolve_model_choice`, reading the L4-2a catalog) — never at write
time, so the pick tracks the catalog as it changes.

v1 files (no ``profile`` key) migrate at load: profile ``expert``, and the
active provider's ``model_by_provider`` pick carries over as an ``exact``
``model_choice``. v2 files (no ``composer_height`` key) migrate at load the
same way: the key reads ``None`` — never dragged — so the panel opens the
composer centred (L5-22); a grip drag persists on release and is restored
in preference to the centred default thereafter.

``load_settings`` returns defaults on a missing/corrupt/unshaped file — it
never raises and never blocks boot (the ``_load_dotenv`` posture).
``save_settings`` writes atomically (tmp + ``os.replace``), best-effort.
Qt-free, hou-free.

``SwitcherState`` (L5-4) is the Qt-free state core of the panel's profile
tab strip: restore-on-construct, validated write-through select.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

SETTINGS_VERSION = 3    # v3 (L5-22): + composer_height

PROFILES = ("curious", "expert", "ml")
"""Exactly three. The write-side rule the panel enforces: ``curious`` picks
semantically, ``expert``/``ml`` pick exact model ids."""

SEMANTIC_VALUES = ("free_local", "balanced", "best")

_DEFAULTS = {
    "version": SETTINGS_VERSION,
    "profile": "expert",
    "fresh_install": True,
    "provider_id": "claude",
    "model_by_provider": {},
    "model_choice": {"mode": "exact", "value": ""},
    "custom": {"base_url": "", "model": "", "key_env": ""},
    "composer_height": None,    # None = never dragged → centred (L5-22)
}

_SIZE_HINT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*b\b", re.IGNORECASE)


def _repo_root() -> Path:
    """``settings.py`` lives at ``<root>/python/synapse/panel/settings.py`` →
    ``parents[3]`` is the repo root (the ``auth.py`` idiom)."""
    return Path(__file__).resolve().parents[3]


def settings_path() -> Path:
    return _repo_root() / ".synapse" / "panel_settings.json"


def default_settings() -> dict:
    return copy.deepcopy(_DEFAULTS)


def _sanitized_choice(mc: object) -> dict | None:
    """``model_choice`` if well-shaped, else ``None``. Semantic values are a
    closed set (``SEMANTIC_VALUES``); an exact value is any string, ``""``
    included (no pick made yet)."""
    if not isinstance(mc, dict):
        return None
    mode, value = mc.get("mode"), mc.get("value")
    if mode not in ("semantic", "exact") or not isinstance(value, str):
        return None
    value = value.strip()
    if mode == "semantic" and value not in SEMANTIC_VALUES:
        return None
    return {"mode": mode, "value": value}


def load_settings(path: Path | None = None) -> dict:
    """Read + sanitize the settings file; defaults on any failure.

    ``fresh_install`` answers "may the panel show the (skippable) profile
    picker?": ``True`` until a well-shaped file is read. A file without the
    key (v1) reads ``False`` — a configured install predates the picker.
    Skipping the picker keeps the default profile, ``expert``.
    """
    out = default_settings()
    try:
        data = json.loads((path or settings_path()).read_text(encoding="utf-8"))
    except Exception:
        return out
    if not isinstance(data, dict):
        return out
    out["fresh_install"] = data.get("fresh_install") is True
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
    if data.get("profile") in PROFILES:
        out["profile"] = data["profile"]
    # else: v1 file or unknown value — expert by definition
    choice = _sanitized_choice(data.get("model_choice"))
    if choice is None:
        # v1 migration (and the bad-shape fallback): the active provider's
        # pick carries over as an exact id
        choice = {"mode": "exact",
                  "value": out["model_by_provider"].get(out["provider_id"], "")}
    out["model_choice"] = choice
    ch = data.get("composer_height")
    if isinstance(ch, int) and not isinstance(ch, bool) and ch > 0:
        out["composer_height"] = ch
    # else: v2 file or junk value — None keeps the centred first run (L5-22)
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


COMPOSER_FLOOR = 64
"""Composer height rails, mirroring the panel's own (the values the resize
grip already enforces). The panel passes ITS rails into
:func:`composer_start_height`; these defaults serve headless callers."""
COMPOSER_MAX = 600


def composer_start_height(persisted, shared_h,
                          floor=COMPOSER_FLOOR, max_h=COMPOSER_MAX):
    """The height the composer opens at (L5-22).

    The artist's persisted drag (``composer_height``) wins whenever it is a
    positive int — the panel keeps THEIR answer, never re-imposes its own
    (L6). Otherwise first run: half of ``shared_h``, the space the chat and
    the composer share, so the divider lands equidistant between prompt and
    chat instead of at the old 132 constant. Both answers clamp to
    ``floor``..``max_h`` so a short pane still leaves room to type and a
    tall one never swallows the chat. Pure and Qt-free: the panel measures,
    this decides, the artist overrides.
    """
    if (isinstance(persisted, int) and not isinstance(persisted, bool)
            and persisted > 0):
        h = persisted
    else:
        h = int(shared_h) // 2
    return max(floor, min(max_h, h))


def _size_hint(model_id: str) -> float:
    """Parameter-count hint from the model id (``qwen3:32b`` → 32.0); 0.0
    when the id carries none — unhinted models rank smallest, never error."""
    m = _SIZE_HINT_RE.search(model_id)
    return float(m.group(1)) if m else 0.0


def resolve_model_choice(settings: dict,
                         catalog_path: str | os.PathLike | None = None) -> str:
    """Concrete model id for the persisted ``model_choice`` — compose-time only.

    ``exact`` returns the stored id verbatim (no catalog read). ``semantic``
    reads the L4-2a catalog (one local file, no network) and ranks by the
    parameter-size hint in the id: ``free_local`` = fastest local entry,
    ``balanced`` = median size, ``best`` = largest. Returns ``""`` when
    nothing qualifies — a determinate "no model", never an exception. This is
    the ONLY place a semantic value becomes concrete; write paths persist the
    token untouched so the pick tracks the catalog as it changes.
    """
    choice = _sanitized_choice(settings.get("model_choice"))
    if choice is None:
        return ""
    if choice["mode"] == "exact":
        return choice["value"]
    try:
        from .providers.catalog import load_catalog
    except Exception as exc:  # pragma: no cover — packaging breakage only
        logger.debug("catalog unavailable for semantic resolve: %s", exc)
        return ""
    entries = list(load_catalog(catalog_path))
    if not entries:
        return ""
    want = choice["value"]
    if want == "free_local":
        local = [e for e in entries if e.local]
        if not local:
            return ""
        local.sort(key=lambda e: (
            e.latency_ms if e.latency_ms is not None else float("inf"),
            _size_hint(e.id), e.id))
        return local[0].id
    ranked = sorted(entries, key=lambda e: (_size_hint(e.id), e.id))
    if want == "best":
        return ranked[-1].id
    return ranked[len(ranked) // 2].id    # balanced — the median-size entry


class SwitcherState:
    """State core of the panel's profile tab strip (L5-4).

    Qt-free on purpose: the tab strip delegates selection + persistence here
    so the logic tests headless; the panel owns the Qt recompose half.

    * **restore** — construction reads the persisted profile
      (missing/corrupt file → ``expert``, the ``load_settings`` posture).
    * **select** — validates against ``PROFILES``, persists write-through
      (read-modify-write, so sibling keys survive), and returns ``True``
      only when the selection changed — the caller's cue to recompose.
      Persistence stays best-effort (``save_settings``): a failed write
      still switches the live session, and ``persist_ok`` records the
      failure so the panel can say so instead of pretending it saved.
    """

    def __init__(self, path: Path | None = None):
        self._path = path
        self.profile = load_settings(path)["profile"]
        self.persist_ok = True

    def select(self, profile: str) -> bool:
        if profile not in PROFILES or profile == self.profile:
            return False
        st = load_settings(self._path)
        st["profile"] = profile
        self.persist_ok = save_settings(st, self._path)
        self.profile = profile
        return True


def merged_model_picks(settings: dict, defaults: dict) -> dict:
    """Persisted ``model_by_provider`` merged over the registry defaults —
    unknown provider ids are dropped (a retired engine never resurrects)."""
    out = dict(defaults)
    for pid, mid in (settings.get("model_by_provider") or {}).items():
        if pid in out and isinstance(mid, str) and mid:
            out[pid] = mid
    return out
