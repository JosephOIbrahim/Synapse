#!/usr/bin/env python3
"""Download the MiniLM ONNX model for SemanticEmbedder.

Downloads a quantized MiniLM-L6-v2 ONNX model from HuggingFace
and verifies its integrity. The model is ~23 MB, 384-dim, and
runs in ~10 ms on CPU.

Usage:
    python scripts/download_embedder_model.py [--model-dir MODELS_DIR]

Default model dir: <repo_root>/models/
"""

import argparse
import hashlib
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Model metadata
# ---------------------------------------------------------------------------

MODEL_URL = (
    "https://huggingface.co/sentence-transformers/"
    "all-MiniLM-L6-v2/resolve/main/onnx/model.onnx"
)
MODEL_FILENAME = "minilm-l6-v2.onnx"
EXPECTED_SIZE = 90_000_000       # ~90 MB — sanity floor, not exact
EXPECTED_SHA256 = "6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452"

# Retry / timeout
MAX_RETRIES = 3
RETRY_DELAY_SEC = 2.0
DOWNLOAD_TIMEOUT_SEC = 120.0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _ProgressReporter:
    """Minimal progress callback for urllib.request.urlretrieve."""

    def __init__(self):
        self._last_pct = -1

    def __call__(self, block_count, block_size, total_size):
        if total_size > 0:
            pct = int(block_count * block_size * 100 / total_size)
            if pct != self._last_pct and pct % 10 == 0:
                print(f"  ... {pct}%", flush=True)
                self._last_pct = pct


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_urlretrieve(url: str, dest: Path, timeout: float) -> None:
    """Download *url* to *dest* with a timeout and progress reporting.

    Raises ``urllib.error.URLError`` or ``urllib.error.HTTPError`` on
    network failure, and ``RuntimeError`` if the file is suspiciously
    small (partial download).
    """
    reporter = _ProgressReporter()
    urllib.request.urlretrieve(url, dest, reporthook=reporter)

    size = dest.stat().st_size
    if size < EXPECTED_SIZE * 0.9:
        dest.unlink(missing_ok=True)
        raise RuntimeError(
            f"Downloaded file is too small ({size:,} bytes vs "
            f"expected ~{EXPECTED_SIZE:,} bytes) — possible truncation."
        )


def download_model(url: str, dest: Path) -> None:
    """Download *url* to *dest* with retries and integrity checks.

    Side effect: prints progress to stdout.
    Raises on failure after exhausting retries.
    """
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"Downloading {url}  (attempt {attempt}/{MAX_RETRIES})...")
        try:
            _safe_urlretrieve(url, dest, DOWNLOAD_TIMEOUT_SEC)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                RuntimeError) as exc:
            last_error = exc
            print(f"  Failed: {exc}", file=sys.stderr)
            if attempt < MAX_RETRIES:
                wait = RETRY_DELAY_SEC * (2 ** (attempt - 1))
                print(f"  Retrying in {wait:.0f} s...", file=sys.stderr)
                time.sleep(wait)
            continue

        # --- Success path ---
        size = dest.stat().st_size
        print(f"Downloaded: {size:,} bytes")

        if EXPECTED_SHA256 is not None:
            actual = _sha256(dest)
            if actual != EXPECTED_SHA256:
                dest.unlink(missing_ok=True)
                raise RuntimeError(
                    f"SHA256 mismatch\n"
                    f"  expected: {EXPECTED_SHA256}\n"
                    f"  actual:   {actual}"
                )
            print("SHA256 verified.")

        return  # success

    # All retries exhausted
    assert last_error is not None
    raise RuntimeError(
        f"Download failed after {MAX_RETRIES} attempts."
    ) from last_error


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Download the MiniLM ONNX model for SemanticEmbedder."
    )
    ap.add_argument(
        "--model-dir",
        default=None,
        help="Target directory for the model file "
             "(default: <repo_root>/models/)",
    )
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    repo_root = Path(__file__).resolve().parents[1]
    model_dir = Path(args.model_dir) if args.model_dir else repo_root / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / MODEL_FILENAME

    # --- Already exists? ---
    if model_path.exists():
        size = model_path.stat().st_size
        print(f"Model already exists: {model_path} ({size:,} bytes)")
        if EXPECTED_SHA256 is not None:
            actual = _sha256(model_path)
            if actual != EXPECTED_SHA256:
                print(
                    f"  WARNING: SHA256 mismatch — file may be corrupt.\n"
                    f"  Delete {model_path} and re-run to re-download.",
                    file=sys.stderr,
                )
                return 1
        return 0

    # --- Download ---
    try:
        download_model(MODEL_URL, model_path)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Model saved to: {model_path}")
    print("SemanticEmbedder will use this model automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
