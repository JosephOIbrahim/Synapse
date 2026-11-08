#!/usr/bin/env python
"""Create the RETINA worker venv, CPU profile, from ``retina/requirements.txt``.

Portable twin of ``setup_venv.ps1``. The venv itself is NEVER committed
(``retina/.venv`` is ``.gitignored``); this script + the pinned requirements are
the reproducible recipe. A network pip install is expected.

Worker runtime (owner ruling R4, 2026-11-07; ADR-0002): CPython 3.12.10 with the
isolated cp312 win_amd64 OpenImageIO wheel. The seed must be CPython 3.12. The
script refuses a hython seed (by file name, before anything runs it) and any
interpreter that is not CPython 3.12, exits 2 and creates nothing. R4 names
3.12.10; another 3.12 micro version seeds with a warning. An existing
``retina/.venv`` that is not a 3.12 venv is refused too: re-run with
``--recreate``.

Usage::

    <CPython 3.12> retina/setup_venv.py                      # seed with this interpreter
    python retina/setup_venv.py --python <CPython 3.12 exe>  # seed with another one

This is the CPU profile: it installs the stock ``opencv-python-headless`` wheel
and only ever writes ``retina/.venv``. The GPU worker profile is separate
(``harness/vision/gpu_worker_env/``): its cv2 is the custom OpenCV 5.1 CUDA
build, so it never installs any ``opencv-python*`` package. On a pip failure the
script prints the sanctioned OpenCV fallback (``opencv-python-headless>=4.13,<5``)
and exits 1.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VENV = _HERE / ".venv"
_REQS = _HERE / "requirements.txt"

# Owner ruling R4 (2026-11-07): the worker interpreter is CPython 3.12.10.
R4_PYTHON = (3, 12, 10)
# Space-separated output, so the PowerShell twin can run the same probe without
# nested quotes.
_PROBE = "import sys; print(sys.implementation.name, *sys.version_info[:3])"


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def hython_refusal(seed: str) -> str | None:
    """Why ``seed`` is refused as a hython interpreter, or None. Reads the name only."""
    if Path(seed).name.lower().startswith("hython"):
        return (
            f"refusing seed {seed}: R4 rules out a hython-seeded worker venv; "
            "seed from a CPython 3.12 interpreter"
        )
    return None


def version_refusal(name: str, version: tuple[int, ...]) -> str | None:
    """Why an interpreter identity is refused under R4, or None for CPython 3.12."""
    if name == "cpython" and tuple(version[:2]) == R4_PYTHON[:2]:
        return None
    shown = ".".join(str(v) for v in version)
    return (
        f"refusing seed {name} {shown}: R4 rules the worker runtime to CPython "
        "3.12.10; seed from a CPython 3.12 interpreter"
    )


def _running_identity() -> tuple[str, tuple[int, ...]]:
    return sys.implementation.name, tuple(sys.version_info[:3])


def _probe(seed: str) -> tuple[str, tuple[int, ...]]:
    out = subprocess.run(
        [seed, "-I", "-c", _PROBE], capture_output=True, text=True, timeout=120, check=True
    ).stdout.split()
    return out[0], tuple(int(p) for p in out[1:4])


def _venv_version(venv_dir: Path) -> tuple[int, ...] | None:
    """The interpreter version an existing venv records in pyvenv.cfg, or None."""
    try:
        lines = (venv_dir / "pyvenv.cfg").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        key, sep, value = line.partition("=")
        if sep and key.strip().lower() in ("version", "version_info"):
            try:
                return tuple(int(p) for p in value.strip().split(".")[:3])
            except ValueError:
                return None
    return None


def _refuse(why: str) -> int:
    print(f"ERROR: {why}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Create the RETINA worker venv (CPU profile; R4: CPython 3.12)."
    )
    ap.add_argument(
        "--python",
        default=None,
        help="CPython 3.12 interpreter to seed the venv (default: this one). "
        "A hython seed is refused (R4).",
    )
    ap.add_argument("--recreate", action="store_true", help="Delete an existing .venv first.")
    args = ap.parse_args(argv)

    # R4 gate, before anything is created or deleted. The name check runs first,
    # so a hython path is refused without ever being executed.
    why = hython_refusal(args.python or sys.executable)
    if why:
        return _refuse(why)
    if args.python:
        try:
            name, version = _probe(args.python)
        except (OSError, subprocess.SubprocessError, ValueError, IndexError) as exc:
            return _refuse(f"could not probe seed {args.python}: {exc}")
    else:
        name, version = _running_identity()
    why = version_refusal(name, version)
    if why:
        return _refuse(f"{why} (seed: {args.python or sys.executable})")
    if tuple(version[:3]) != R4_PYTHON:
        shown = ".".join(str(v) for v in version)
        print(f"WARNING: R4 names CPython 3.12.10; seeding from {shown}.", file=sys.stderr)

    if args.recreate and _VENV.exists():
        shutil.rmtree(_VENV)

    if _VENV.exists():
        have = _venv_version(_VENV)
        if have is None or tuple(have[:2]) != R4_PYTHON[:2]:
            return _refuse(
                f"existing {_VENV} is not a CPython 3.12 venv (pyvenv.cfg version: "
                f"{have}); re-run with --recreate"
            )

    if args.python:
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
            "\npip install failed (see pip's output above). If the failing requirement "
            "is the OpenCV 5.0.0.93 pin, the sanctioned fallback (blueprint sections 3 "
            "and 8) is:\n"
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
