#!/usr/bin/env python
"""BP1 follow-up - G4 autopsy: dump the raw row(s), the full query payload, and
the authored USD text for one deposit->recall round trip on the main thread.

G4 measured (gui, main-thread, 2026-08-31): deposit SUCCESS, raw_row_count=1,
known_in_raw=False, recall SUCCESS count=1, known_recalled=False. This probe
discriminates the mechanism:
  (a) id-contract mismatch - the one raw row IS the deposit under another id
  (b) store-split          - deposit authored elsewhere; the row is meta/genesis
  (c) probe strictness     - claim_id lives at a different key/level

Read-only on product code. KEEPS its scratch store (prints the path) for
post-mortem. Run deferred on the main thread (host law: store init):

  import hdefereval, runpy; hdefereval.executeDeferred(lambda: runpy.run_path(
      r"C:\\Users\\User\\SYNAPSE\\harness\\battleplan\\notes\\probe_recall_rawdump.py",
      run_name="__main__"))
"""
from __future__ import annotations

import json
import sys
import tempfile
import uuid
from pathlib import Path


def _dump(tag, obj):
    print(f"### {tag}")
    try:
        print(json.dumps(obj, indent=2, default=repr, ensure_ascii=False))
    except Exception:
        print(repr(obj))


def _env_of(x):
    """Envelope -> plain dict without assuming its class."""
    return {k: getattr(x, k, None) for k in ("status", "error_message", "payload")}


def main():
    try:
        import hou
        print(f"# build={hou.applicationVersionString()} ui={hou.isUIAvailable()}")
    except Exception:
        print("# hou unavailable")

    # Same bootstrap contract as probe_silent_recall: the live package env's
    # synapse wins; the repo fallback fires only if it is not importable.
    try:
        import synapse  # noqa: F401
    except Exception:
        py = Path(r"C:/Users/User/SYNAPSE") / "python"
        if py.is_dir() and str(py) not in sys.path:
            sys.path.insert(0, str(py))

    import synapse.loop.ports as ports_mod
    from synapse.loop.ports import MemoryPort, MONETA_URI_SCHEME
    print(f"# ports module: {ports_mod.__file__}")

    tmp = tempfile.mkdtemp(prefix="bp1_rawdump_")
    uri = MONETA_URI_SCHEME + Path(tmp).as_posix()
    print(f"# store_dir={tmp}  (KEPT - not deleted)")
    MemoryPort.release(uri)
    port = MemoryPort(uri)

    if port.handle is None:
        probe = port.query_and_filter([], [])
        _dump("BIND REFUSED", _env_of(probe))
        return

    known = "BP1-RAWDUMP-known-" + uuid.uuid4().hex[:8]
    print(f"# known_claim_id={known}")
    dep = port.deposit_settlement(known, "HIT")
    _dump("DEPOSIT envelope (full)", _env_of(dep))

    try:
        raw = port._fetch_raw_memories([])
        print(f"# raw_row_count={len(raw)}")
        _dump("RAW rows (full)", raw)
    except Exception as e:
        print(f"# raw fetch error: {type(e).__name__}: {e}")

    rec = port.query_and_filter([], [])
    _dump("QUERY envelope (full)", _env_of(rec))

    moneta_dir = Path(tmp) / ".moneta"
    if moneta_dir.is_dir():
        names = sorted(p.relative_to(moneta_dir).as_posix()
                       for p in moneta_dir.rglob("*"))
        _dump(".moneta contents", names)
        cortex = moneta_dir / "cortex_root.usda"
        if cortex.is_file():
            print("### cortex_root.usda text")
            print(cortex.read_text(encoding="utf-8", errors="replace"))
        else:
            print("# no cortex_root.usda authored")
    else:
        print("# no .moneta dir authored")

    # Handle hygiene: release the handle, keep the files for post-mortem.
    MemoryPort.release(uri)
    print(f"# done. store kept at: {tmp}")


if __name__ == "__main__":
    main()
