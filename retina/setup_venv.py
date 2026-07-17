#!/usr/bin/env python
"""Create the RETINA worker venv from ``retina/requirements.txt``.

Portable twin of ``setup_venv.ps1``. The venv itself is NEVER committed
(``retina/.venv`` is ``.gitignored``); this script + the pinned requirements are
the reproducible recipe. A network pip install is expected.

Usage::

    python retina/setup_venv.py            # seed with the interpreter running this
    python retina/setup_venv.py --python C:/Houdini/22.0.368/bin/hython.exe

The abi3 OpenCV wheel spans cp37+, so any interpreter can seed the venv; a
hython-seeded venv additionally gets Houdini's native OpenImageIO for the EXR
ingest leg. On failure the script prints the sanctioned OpenCV fallback
(``opencv-python-headless>=4.13,<5``) and exits non-zero.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VENV = _HERE / ".venv"
_REQS = _HERE / "requirements.txt"


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def main() -> int:
    ap = argparse.ArgumentParser(description="Create the RETINA worker venv.")
    ap.add_argument(
        "--python",
        default=None,
        help="Interpreter to seed the venv (default: this one). Point at hython "
        "to inherit Houdini's native OpenImageIO.",
    )
    ap.add_argument("--recreate", action="store_true", help="Delete an existing .venv first.")
    args = ap.parse_args()

    if args.recreate and _VENV.exists():
        import shutil

        shutil.rmtree(_VENV)

    if args.python:
        # Seed with an external interpreter (e.g. hython) so it brings its own OIIO.
        subprocess.check_call([args.python, "-m", "venv", str(_VENV)])
    elif not _VENV.exists():
        print(f"Creating venv at {_VENV} (seed: {sys.executable})")
        venv.create(_VENV, with_pip=True)

    vpy = _venv_python(_VENV)
    if not vpy.exists():
        print(f"ERROR: venv python not found at {vpy}", file=sys.stderr)
        return 1

    subprocess.check_call([str(vpy), "-m", "pip", "install", "--upgrade", "pip"])
    try:
        subprocess.check_call([str(vpy), "-m", "pip", "install", "-r", str(_REQS)])
    except subprocess.CalledProcessError:
        print(
            "\npip install failed. If the OpenCV 5.0.0.93 pin is unavailable on "
            "this platform, the sanctioned fallback (blueprint §3/§8) is:\n"
            "    opencv-python-headless>=4.13,<5\n"
            "Edit retina/requirements.txt and re-run.",
            file=sys.stderr,
        )
        return 1

    print(f"\nRETINA worker venv ready: {vpy}")
    print("Run the pixel tests:")
    print(f"    {vpy} -m pytest tests/test_retina_t1.py tests/test_retina_ingest.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
