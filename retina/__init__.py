"""RETINA — the perception co-processor (worker tree).

SYNAPSE_RETINA_BLUEPRINT §3 splits RETINA into two trees:

* **host hooks** — thin, in-process, live in ``python/synapse/host``. They
  export scene truth (the manifest) and drop a ``.done`` sentinel when pixels
  land. They may import ``hou``; they may **never** import ``cv2`` (P5, pinned
  by ``tests/test_retina_boundary.py``).
* **the worker** — THIS tree, at the repo root, OUTSIDE every host surface. It
  runs in its own venv, host-ABI-independent by construction, and judges the
  render from disk. At M1 it carries only **T0 (file truth)**: pure-python, zero
  ``hou``, and — crucially at M1 — **zero ``cv2``** (T0 reads EXR *headers*, it
  never touches pixels, so it needs neither Houdini nor OpenCV). OpenCV/OIIO/ONNX
  land with the T1+ tiers in M2, at which point ``cv2`` belongs here and here
  only.

The M0 boundary test's twin assertion
(``test_retina_worker_tree_is_not_in_host_scope``) enforces that this tree stays
outside ``python/synapse``, ``shared`` and ``houdini`` — do not move it inside
them, and do not add this tree to the zero-cv2 host lint's ``_HOST_SURFACES``.
"""

from __future__ import annotations

__version__ = "0.1.0"

# Perception event channel + schema version — the versioned shape every tier
# publishes (blueprint §3 event contract; §7 persistence rule). T0 verdicts are
# ``{"ch": PERCEPTION_CHANNEL, "v": EVENT_VERSION, "tier": 0, ...}``.
PERCEPTION_CHANNEL = "perception"
EVENT_VERSION = 1
