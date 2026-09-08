"""Developer entry point for explicit native-experience import and recall.

Run in a standalone process with an existing development project directory.
No public tool, panel hook, automatic recording, or procedure execution.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from synapse.memory.experience import ExperienceMemory, TASK, make_experience, validate_environment


def read_json(path, limit=128 * 1024):
    with Path(path).open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Input exceeds the development import size limit")
    return json.loads(data.decode("utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable", action="store_true", help="Enable this explicit development operation")
    parser.add_argument("--project-dir", required=True, help="Existing isolated development project directory")
    commands = parser.add_subparsers(dest="command", required=True)
    record = commands.add_parser("record", help="Import a developer-controlled, retained native result")
    record.add_argument("--native-report", required=True)
    record.add_argument("--summary", required=True)
    recall = commands.add_parser("recall", help="Find prior experience without executing it")
    recall.add_argument("--environment", required=True, help="Observed environment JSON or a native report containing it")
    recall.add_argument("--task", default=TASK)
    args = parser.parse_args(argv)
    owner = None
    try:
        if not args.enable:
            result = {"status": "UNAVAILABLE", "reason": "Checked experience is disabled; no inputs or storage opened"}
        elif os.environ.get("SYNAPSE_MEMORY_BACKEND", "").strip().lower() != "moneta":
            result = {"status": "UNAVAILABLE", "reason": "Select the existing Moneta backend for this development process"}
        else:
            project = Path(args.project_dir).resolve(strict=True)
            if not project.is_dir():
                raise ValueError("An existing development project directory is required")
            # Validate import/input before initializing the one process owner.
            if args.command == "record":
                experience = make_experience(read_json(args.native_report), args.summary)
            else:
                payload = read_json(args.environment)
                environment = payload.get("environment", payload) if isinstance(payload, dict) else payload
                validate_environment(environment)
                if args.task != TASK:
                    raise ValueError("Unsupported task")
            from synapse.memory.moneta_store import MonetaBackedStore

            # This standalone process owns exactly one existing store facade.
            # Avoid the high-level project's migration/fallback initialization.
            owner = MonetaBackedStore.from_storage_dir(
                project / ".synapse", require_compatible_snapshot=True)
            adapter = ExperienceMemory(owner, enabled=True)
            if args.command == "record":
                result = adapter.record(experience)
            else:
                result = adapter.recall(args.task, environment, requested=True)
    except Exception as exc:
        result = {"status": "UNAVAILABLE", "reason": str(exc)}
    finally:
        if owner is not None:
            close = getattr(owner, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as exc:
                    result["teardown_warning"] = str(exc)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] in {"STORED", "DUPLICATE", "HIT", "NO_MATCH"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
