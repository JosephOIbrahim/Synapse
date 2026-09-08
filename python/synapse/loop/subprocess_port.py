"""Bounded, local substrate IPC. No model calls or package installation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

from .ports import PortResult


class SubstrateWorker:
    """Run the configured source checkouts outside Houdini's Python namespace.

    Octavius currently exports a generic ``src`` package. Importing that into
    the artist's host would collide with other tools. The child uses the USD
    Python shipped with the artist's Houdini, explicitly configured by path.
    """

    def __init__(self, python=None, hanish_root=None, octavius_root=None, timeout=4.0):
        self.python = python or os.environ.get("SYNAPSE_LOOP_PYTHON")
        self.hanish_root = hanish_root or os.environ.get("SYNAPSE_HANISH_ROOT")
        self.octavius_root = octavius_root or os.environ.get("SYNAPSE_OCTAVIUS_ROOT")
        self.timeout = timeout

    def __call__(self, request):
        root = self.octavius_root if request["action"] == "compose" else self.hanish_root
        name = "Octavius" if request["action"] == "compose" else "Hanish"
        if not self.python or not root:
            return PortResult.unavailable(f"{name} worker is not configured")
        if not Path(self.python).is_file() or not Path(root).is_dir():
            return PortResult.unavailable(f"{name} worker paths are unavailable")
        request = dict(request, source_root=str(Path(root).resolve()))
        try:
            encoded = json.dumps(request, sort_keys=True, allow_nan=False)
            if len(encoded.encode("utf-8")) > 262144:
                return PortResult.blocked("Substrate request exceeds 256 KiB")
            process = subprocess.run(
                [self.python, "-I", "-B", str(Path(__file__).with_name("worker.py"))],
                input=encoded, capture_output=True, text=True, encoding="utf-8",
                timeout=self.timeout, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if process.returncode:
                return PortResult.unavailable(f"{name} worker failed: {process.stderr[-1200:]}")
            if len(process.stdout) > 1048576:
                return PortResult.unavailable(f"{name} response exceeds 1 MiB")
            result = json.loads(process.stdout)
            if result.get("status") not in {"SUCCESS", "UNAVAILABLE", "BLOCKED"}:
                raise ValueError("Invalid substrate response status")
            return PortResult(result["status"], result.get("payload"), result.get("error_message"))
        except Exception as exc:
            return PortResult.unavailable(f"{name} worker did not complete: {exc}")
