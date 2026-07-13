#!/usr/bin/env python3
"""K.5 — one-command RAG refresh. Run this after ANY change to rag/ content
(edited/added reference files, changed topics) and on H22 drop day after the new
docs are authored into rag/. It brings every derived artifact back in sync with
the source so retrieval is provably fresh:

  1. rebuild the embedding index      (rag/semantic_index/  — the K.1 dense path)
  2. rebuild the scout lexical corpus (.synapse/scout_corpus — the BM25 path)
  3. refresh the K.0 baseline snapshot (harness/notes/knowledge_baseline.json)

After this, `check_semantic_index_fresh` (K.5) reads GREEN. Skipping it is the
failure mode the K.5 gate exists to catch — stale vectors silently answering
H21 content to H22 questions.

The embedding rebuild needs sentence-transformers (pip install -e .[semantic]);
the other two steps are pure-stdlib and always run. On a machine without the
embedder, step 1 is skipped with a loud warning and the gate stays RED until an
embedder-equipped machine runs it — by design (never fake freshness).

Usage:
    python scripts/refresh_knowledge.py
    python scripts/refresh_knowledge.py --model all-MiniLM-L6-v2
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "python"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="all-MiniLM-L6-v2")
    args = parser.parse_args()

    print("=" * 64)
    print("  RAG REFRESH (K.5) — resyncing derived artifacts to rag/ source")
    print("=" * 64)

    # 1. Embedding index (needs the optional embedder).
    print("\n[1/3] rebuilding embedding index...")
    rc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "build_semantic_index.py"),
         "--model", args.model],
        cwd=str(REPO_ROOT),
    ).returncode
    if rc != 0:
        print("  ! embedding rebuild FAILED or embedder missing — semantic_index_fresh "
              "will stay RED until an embedder-equipped machine runs this. "
              "Continuing with the stdlib steps.", file=sys.stderr)

    # 2. Scout lexical corpus (pure stdlib; force a rebuild rather than lazy drift).
    print("\n[2/3] rebuilding scout lexical corpus...")
    try:
        from synapse.cognitive.tools import scout_ingest
        info = scout_ingest.build_corpus()
        print(f"  corpus: {info.get('entries')} entries -> {info.get('store_root')}")
    except Exception as e:  # noqa: BLE001 — refresh must report, not crash
        print(f"  ! corpus rebuild error: {e}", file=sys.stderr)

    # 3. K.0 baseline snapshot.
    print("\n[3/3] refreshing baseline snapshot...")
    rc3 = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "knowledge_baseline.py")],
        cwd=str(REPO_ROOT),
    ).returncode

    ok = (rc == 0) and (rc3 == 0)
    print("\n" + "=" * 64)
    print("  DONE — verify with:")
    print("    python harness/verify/checks.py --task K.5 --worktree . --hython \"\" --mode A")
    print("=" * 64)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
