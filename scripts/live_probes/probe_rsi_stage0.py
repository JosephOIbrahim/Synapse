"""Capture one real Stage 0 lookdev outcome in a disposable H22.0.400 process.

The caller must isolate preferences and enforce a subprocess timeout. This
probe refuses GUI use and a nonempty Solaris network. It performs no render,
export, memory initialization, or connection to an artist's running session.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "python"), str(ROOT)]

import hou
from synapse.memory.experience import capture_environment, make_experience
from synapse.server.handlers_solaris_graph import SolarisGraphMixin
from synapse.server.main_thread import run_on_main


def capture():
    is_main = threading.get_ident() == threading.main_thread().ident
    ui_available = hou.isUIAvailable()
    build = hou.applicationVersionString()
    if not is_main or ui_available or build != "22.0.400":
        raise RuntimeError("A disposable, headless Houdini 22.0.400 main thread is required")
    stage = hou.node("/stage")
    if stage is None or stage.children():
        raise RuntimeError("The rehearsal requires a fresh empty Solaris network")
    request = {
        "parent": "/stage", "template": "copernicus_lookdev", "layout": "vertical",
        "template_params": {"name": "rsi_stage0_rehearsal", "base_color": [0.18, 0.04, 0.01],
                            "noise_type": "perlin", "frequency": 4.0, "octaves": 3},
    }
    result = SolarisGraphMixin()._handle_solaris_build_graph(request)
    if len(result.get("dependencies", [])) != 1:
        raise RuntimeError("Expected the fixed lookdev dependency")
    environment = capture_environment(build, result["dependencies"][0])
    report = {
        "origin": "native_hython_rehearsal", "main_thread": is_main, "ui_available": ui_available,
        "source_id": "lookdev-" + uuid.uuid4().hex,
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "environment": environment, "request": request, "result": result,
    }
    make_experience(report, "Fixed Solaris and Copernicus lookdev setup")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = run_on_main(capture, label="probe:rsi_stage0")
    with Path(args.output).open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": "CAPTURED", "source_id": report["source_id"],
                      "environment": report["environment"], "output": args.output}, sort_keys=True))


if __name__ == "__main__":
    main()
