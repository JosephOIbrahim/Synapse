"""
host/capture_perception_baseline.py  —  Mile-5 perception-baseline CAPTURE (HOST LAYER)
=======================================================================================

Freeze the perception channel. ``harness/state/leg0_baselines.json`` covers the
connectivity / symbol-table / quarantine / test-pass channels but NOT the stream
of typed PDG events the agent perceives from inside Houdini
(``synapse.host.tops_bridge.TopsEventBridge`` → ``TopsEvent``). This script
captures that stream (or the well-formed EMPTY case when there is no live
session) and writes a timestamped ``perception_baseline/v1`` artifact.

RUN IT INSIDE Houdini (the interpreter the agent perceives from):

    "C:/Program Files/Side Effects Software/Houdini 21.0.671/bin/hython.exe" \
        host/capture_perception_baseline.py [OUTPUT_PATH]

Why a host script (not the cognitive layer): it touches ``hou`` (TOP-network
discovery) and ``pdg`` (event registration) — the cognitive boundary lint
forbids ``import hou`` under ``synapse.cognitive.*``. The pure envelope shape
lives in ``synapse.host.perception_baseline`` (zero-``hou``); this script owns
the clock (``captured_at`` is generated HERE and passed in) and the live
``hou``/``pdg`` surface. It is NOT imported by ``agent_loop.py`` and adds no
``hou`` import to it (G-5 boundary).

Headless / no-live-session behaviour
------------------------------------
``TopsEventBridge.warm_all()`` returns ``[]`` when ``hou`` is unavailable
(headless) — no TOP networks to subscribe to. In that case (and on any bridge
error, e.g. ``pdg`` missing) this script still writes a well-formed EMPTY
baseline (``count`` 0, ``events`` ``[]``) so the artifact always exists as the
LEFT SIDE of a future drop-week diff.
"""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

# Make ``synapse`` importable when run as a bare host script (hython may or may
# not have the editable install on its path). repo root = parents[1] of host/.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_PYTHON_DIR = _REPO_ROOT / "python"
if str(_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(_PYTHON_DIR))

from synapse.host.perception_baseline import build_perception_baseline  # noqa: E402


def _runtime_label() -> str:
    """Best-effort runtime string; never raises, works headless."""
    try:
        import hou  # local import — keeps module import zero-hou for tooling
        return "H" + hou.applicationVersionString()
    except Exception:
        return "headless"


def _default_output_path(captured_at: str) -> Path:
    # Filesystem-safe stamp (drop ':' from the ISO timestamp).
    stamp = captured_at.replace(":", "").replace("-", "").replace("+0000", "Z")
    return _REPO_ROOT / "harness" / "notes" / f"perception_baseline_{stamp}.json"


def capture(*, drain_seconds: float = 0.0) -> dict:
    """Capture the current perception stream into a ``perception_baseline/v1`` dict.

    Warms every live TOP network, collects whatever typed events the bridge has
    already delivered to the callback, then cools. Triggers NO cook — it freezes
    the ambient perception state, not a synthesized one. Returns the envelope.

    Headless (or any ``TopsBridgeError``): returns the well-formed EMPTY
    baseline. ``captured_at`` is generated here and passed to the pure builder.
    """
    captured_at = datetime.now(timezone.utc).isoformat()
    runtime = _runtime_label()

    collected: list = []
    lock = threading.Lock()

    def _on_event(event) -> None:
        # PDG callbacks may fire on a worker thread — append under a lock.
        with lock:
            collected.append(event)

    subscriptions = []
    bridge = None
    try:
        from synapse.host.tops_bridge import TopsBridgeError, TopsEventBridge

        bridge = TopsEventBridge(_on_event)
        try:
            subscriptions = bridge.warm_all()
        except TopsBridgeError as exc:  # pdg missing under a live hou, etc.
            sys.stderr.write(f"[capture] warm_all skipped: {exc}\n")
            subscriptions = []

        # Optional short drain window for in-flight events (default: none).
        if subscriptions and drain_seconds > 0:
            import time

            time.sleep(drain_seconds)
    except Exception as exc:  # pragma: no cover - defensive, headless-safe
        sys.stderr.write(f"[capture] bridge unavailable, empty baseline: {exc!r}\n")
    finally:
        if bridge is not None:
            for sub in subscriptions:
                try:
                    bridge.cool(sub)
                except Exception:
                    pass

    with lock:
        events = list(collected)

    return build_perception_baseline(
        events, runtime=runtime, captured_at=captured_at
    )


def main(argv: list[str]) -> int:
    envelope = capture()

    if len(argv) > 1:
        out_fp = Path(argv[1])
    else:
        out_fp = _default_output_path(envelope["captured_at"])
    out_fp.parent.mkdir(parents=True, exist_ok=True)
    out_fp.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    sys.stdout.write(
        f"PERCEPTION BASELINE: runtime={envelope['runtime']} "
        f"count={envelope['count']} captured_at={envelope['captured_at']} "
        f"-> {out_fp}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
