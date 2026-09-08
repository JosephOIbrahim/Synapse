"""Private JSON worker entry point; deliberately does not import SYNAPSE/hou."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


def compose(request):
    from pxr import Sdf, Usd
    from src.stage.topology import create_stage
    from src.stage.composer import add_sublayer, compose_stage

    context = request["context"]
    # Reconstruct a private context view from data the host allowlisted. No
    # production layer, payload, reference, customData or script enters it.
    stage = create_stage()
    layer = Sdf.Layer.CreateAnonymous("synapse_context")
    view = Usd.Stage.Open(layer)
    prim = view.DefinePrim("/octavius/artifact/context")
    encoded = json.dumps(context, sort_keys=True, separators=(",", ":"), allow_nan=False)
    prim.CreateAttribute("synapse:context", Sdf.ValueTypeNames.String).Set(encoded)
    add_sublayer(stage, layer)
    before = layer.ExportToString()
    compose_stage(stage)
    result = stage.GetPrimAtPath(prim.GetPath()).GetAttribute("synapse:context").Get()
    if before != layer.ExportToString() or result != encoded:
        raise RuntimeError("Octavius context composition changed its source")
    return {"status": "SUCCESS", "error_message": None, "payload": {
        "context": json.loads(result), "source": "octavius_private_context_stage",
        "sanitization": "synapse_allowlisted_context_v1", "scope": "context_only",
        "coordination": "not_run", "production_stage_written": False,
        "context_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
        "composer_file": str(Path(sys.modules["src.stage.composer"].__file__).resolve()),
        "composer_sha256": hashlib.sha256(Path(sys.modules["src.stage.composer"].__file__).read_bytes()).hexdigest(),
        "anonymous_stage": stage.GetRootLayer().anonymous,
    }}


def main():
    request = json.loads(sys.stdin.read(262145))
    sys.path.insert(0, request.pop("source_root"))
    try:
        if request["action"] == "compose":
            result = compose(request)
        else:
            sys.path.insert(0, str(Path(__file__).parent))
            from hanish_worker import handle
            result = handle(request)
    except Exception as exc:
        result = {"status": "UNAVAILABLE", "payload": None,
                  "error_message": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
