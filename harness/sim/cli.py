"""Command line for the SIM plane.

Phase 4 exposes one command: ``transfer``, which reads a ledger and prints the
work list for a change of setting. It writes nothing and runs nothing.

    python harness/sim/cli.py transfer --ledger harness/sim/ledger \
        --from-model claude-opus-5-5 --from-split bench-12/evo --from-harness <hash> \
        --to-model claude-sonnet-5-5   --to-split bench-12/evo --to-harness <hash>

Exit codes: 0 plan produced, 2 no setting change, 1 error (unreadable ledger).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from harness.sim.setting import SettingFingerprint  # noqa: E402
from harness.sim.store import SIMStore, StoreError  # noqa: E402
from harness.sim.transfer import TransferBoundaryController  # noqa: E402


def _setting(args: argparse.Namespace, side: str) -> SettingFingerprint:
    return SettingFingerprint(
        model_id=getattr(args, f"{side}_model"),
        eval_split_id=getattr(args, f"{side}_split"),
        harness_hash=getattr(args, f"{side}_harness"),
    )


def cmd_transfer(args: argparse.Namespace) -> int:
    ledger = Path(args.ledger)
    if not ledger.is_dir():
        # A missing directory and an empty ledger are different facts. Treating a
        # typo as "no inherited edits" would silently produce an empty plan.
        print(f"error: ledger directory does not exist: {ledger}", file=sys.stderr)
        return 1
    try:
        store = SIMStore(ledger)
        plan = TransferBoundaryController(store).plan(_setting(args, "from"), _setting(args, "to"))
    except (StoreError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not plan.is_transition:
        print("no setting change: nothing to re-validate")
        return 2

    if args.json:
        print(json.dumps(plan.as_dict(), indent=2, sort_keys=True))
        return 0

    print(f"transition: {', '.join(k for k, v in plan.transition.items() if v)}")
    # Both lines matter more than the per-item table: a harness-only change
    # reclassifies nothing but invalidates every measurement behind it, and a
    # reader who saw only ANCHOR/CARRIED rows would read that as a clean plan.
    print(f"comparison_invalidated: {plan.comparison_invalidated}")
    print(f"requires_revalidation: {plan.requires_revalidation}")
    print(f"{'disposition':<24}{'scope':<26}artifact")
    for item in plan.items:
        print(f"{item.disposition.value:<24}{item.edit_scope.value:<26}{item.target_artifact}")
        print(f"{'':<24}{item.reason}")
    if plan.superseded:
        print(f"superseded: {', '.join(plan.superseded)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    transfer = sub.add_parser("transfer", help="plan a model or split change")
    transfer.add_argument("--ledger", required=True, help="SIM ledger directory")
    for side in ("from", "to"):
        transfer.add_argument(f"--{side}-model", required=True)
        transfer.add_argument(f"--{side}-split", required=True)
        transfer.add_argument(f"--{side}-harness", required=True)
    transfer.add_argument("--json", action="store_true", help="machine-readable plan")
    transfer.set_defaults(func=cmd_transfer)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
