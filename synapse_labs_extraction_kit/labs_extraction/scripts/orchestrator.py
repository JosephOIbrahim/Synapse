#!/usr/bin/env python3
"""
SideFXLabs → SYNAPSE RAG Extraction Orchestrator

Runs all extraction phases sequentially or individually.
Usage:
    python orchestrator.py              # Run all phases
    python orchestrator.py --phase 1    # Run specific phase
    python orchestrator.py --phase 1 3  # Run phases 1 and 3
    python orchestrator.py --dry-run    # Show what would run
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# Fix Windows cp1252 encoding for Unicode output
if sys.stdout.encoding and sys.stdout.encoding.lower().startswith("cp"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ──────────────────────────────────────────────────────────────
# Configuration — edit these paths for your environment
# ──────────────────────────────────────────────────────────────
STAGING_ROOT = Path(r"G:\SYNAPSE_STAGING\SideFXLabs")
CORPUS_ROOT = Path(r"G:\HOUDINI21_RAG_SYSTEM\corpus\sidefxlabs")
INDEX_ROOT = Path(r"G:\HOUDINI21_RAG_SYSTEM\semantic_index")
REPO_URL = "https://github.com/sideeffects/SideFXLabs.git"
REPO_BRANCH = "Development"

SCRIPTS_DIR = Path(__file__).parent

# ──────────────────────────────────────────────────────────────
# Phase definitions
# ──────────────────────────────────────────────────────────────
PHASES = {
    0: {
        "name": "Clone & Stage",
        "script": "phase0_clone.py",
        "description": "Clone SideFXLabs repo and create attribution",
        "critical": True,
    },
    1: {
        "name": "Parameter Schemas",
        "script": "phase1_params.py",
        "description": "Extract parameter definitions from all HDAs",
        "critical": True,
    },
    2: {
        "name": "VEX Patterns",
        "script": "phase2_vex.py",
        "description": "Extract VEX functions and inline wrangle patterns",
        "critical": False,
    },
    3: {
        "name": "Python Patterns",
        "script": "phase3_python.py",
        "description": "Extract hou.* API usage patterns",
        "critical": False,
    },
    4: {
        "name": "Help Intent Pairs",
        "script": "phase4_help.py",
        "description": "Extract natural language → operation mappings from help docs",
        "critical": False,
    },
    5: {
        "name": "HDA Conventions",
        "script": "phase5_hda_conventions.py",
        "description": "Analyze HDA structural and naming conventions",
        "critical": False,
    },
    6: {
        "name": "PDG Patterns",
        "script": "phase6_pdg.py",
        "description": "Extract PDG/TOP workflow patterns",
        "critical": False,
    },
    7: {
        "name": "RAG Merge",
        "script": "phase7_merge.py",
        "description": "Merge all extracted data into SYNAPSE semantic index",
        "critical": True,
    },
}


def run_phase(phase_num: int, dry_run: bool = False) -> bool:
    """Run a single extraction phase. Returns True on success."""
    phase = PHASES[phase_num]
    script_path = SCRIPTS_DIR / phase["script"]

    print(f"\n{'='*60}")
    print(f"  Phase {phase_num}: {phase['name']}")
    print(f"  {phase['description']}")
    print(f"  Script: {script_path}")
    if phase["critical"]:
        print(f"  ⚠  CRITICAL PATH")
    print(f"{'='*60}")

    if not script_path.exists():
        print(f"  ❌ Script not found: {script_path}")
        return False

    if dry_run:
        print(f"  [DRY RUN] Would execute: python {script_path}")
        return True

    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            env={
                **dict(os.environ),
                "STAGING_ROOT": str(STAGING_ROOT),
                "CORPUS_ROOT": str(CORPUS_ROOT),
                "INDEX_ROOT": str(INDEX_ROOT),
                "REPO_URL": REPO_URL,
                "REPO_BRANCH": REPO_BRANCH,
            },
        )

        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                print(f"  │ {line}")

        if result.returncode != 0:
            print(f"  ❌ FAILED (exit code {result.returncode})")
            if result.stderr:
                for line in result.stderr.strip().split("\n")[:10]:
                    print(f"  │ ERR: {line}")
            return False

        elapsed = time.time() - start
        print(f"  ✅ Complete ({elapsed:.1f}s)")
        return True

    except Exception as e:
        print(f"  ❌ Exception: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="SideFXLabs → SYNAPSE RAG Extraction"
    )
    parser.add_argument(
        "--phase",
        type=int,
        nargs="*",
        help="Run specific phase(s). Omit to run all.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would run without executing.",
    )
    parser.add_argument(
        "--skip-clone",
        action="store_true",
        help="Skip phase 0 (repo already cloned).",
    )
    args = parser.parse_args()

    print("╔════════════════════════════════════════════════════════╗")
    print("║  SideFXLabs → SYNAPSE RAG Extraction                 ║")
    print("║  BSD 2-Clause Licensed | Attribution Required         ║")
    print("╚════════════════════════════════════════════════════════╝")
    print(f"\n  Staging:  {STAGING_ROOT}")
    print(f"  Corpus:   {CORPUS_ROOT}")
    print(f"  Index:    {INDEX_ROOT}")

    # Determine which phases to run
    if args.phase is not None:
        phases_to_run = args.phase
    else:
        phases_to_run = sorted(PHASES.keys())
        if args.skip_clone:
            phases_to_run = [p for p in phases_to_run if p != 0]

    # Validate
    for p in phases_to_run:
        if p not in PHASES:
            print(f"\n  ❌ Unknown phase: {p}")
            print(f"  Valid phases: {sorted(PHASES.keys())}")
            sys.exit(1)

    # Check phase 0 prerequisite
    if 0 not in phases_to_run and not STAGING_ROOT.exists():
        print(f"\n  ❌ Staging directory not found: {STAGING_ROOT}")
        print(f"  Run phase 0 first, or use --skip-clone if repo is elsewhere.")
        sys.exit(1)

    # Execute
    results = {}
    for phase_num in phases_to_run:
        success = run_phase(phase_num, dry_run=args.dry_run)
        results[phase_num] = success

        # Abort on critical failure
        if not success and PHASES[phase_num]["critical"]:
            print(f"\n  🛑 Critical phase {phase_num} failed. Aborting.")
            break

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for phase_num, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} Phase {phase_num}: {PHASES[phase_num]['name']}")

    failed = [p for p, s in results.items() if not s]
    if failed:
        print(f"\n  {len(failed)} phase(s) failed: {failed}")
        sys.exit(1)
    else:
        print(f"\n  All {len(results)} phase(s) complete.")


if __name__ == "__main__":
    main()
