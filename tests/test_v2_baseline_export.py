"""Pins the reconstructed producer for the harness/v2-20260913 baseline.csv.

The v2-baseline run's manifest records a "host-script" evidence-export action
(manifest steps n=8 and n=53) that emitted baseline.csv, but that script was
never checked in -- only its output was.  ``export_baseline_csv.py`` is the
reconstruction; this test pins its column order and its field mapping so the
CSV-aggregation logic is auditable rather than folklore.

The fixture is synthetic on purpose: the real artifact directory is untracked,
so a test that read it would skip in CI, and a skip proves nothing.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / "harness"
    / "v2-20260913"
    / "artifacts"
    / "v2-baseline"
    / "export_baseline_csv.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("export_baseline_csv", SCRIPT)
    assert spec is not None and spec.loader is not None, f"cannot load {SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _manifest() -> dict:
    return {
        "baseline_tasks": [
            {
                "id": "aa-01",
                "measurement_kind": "proxy",
                "model_round_trips": 11,
                "task_input_tokens": 357418,
                "task_output_tokens": 5407,
                # no first_call_input_tokens: that first call was missed
                "cache_read": "UNKNOWN",
                "wall_ms": "UNKNOWN",
                "independent_observation": 'Bound box: 8 points, "6" polygons.',
            },
            {
                "id": "aa-02",
                "measurement_kind": "proxy",
                "model_round_trips": 8,
                "task_input_tokens": 358524,
                "task_output_tokens": 5131,
                "first_call_input_tokens": 40108,
                "cache_read": "UNKNOWN",
                "wall_ms": "UNKNOWN",
                "independent_observation": "Copy output: 8000 points.",
            },
        ]
    }


def test_header_is_the_archived_column_order() -> None:
    module = _load_module()
    assert module.COLUMNS == [
        "task",
        "measurement_kind",
        "model_round_trips",
        "input_tokens",
        "output_tokens",
        "first_call_input_tokens",
        "cache_read",
        "cost",
        "wall_ms",
        "validation",
    ]


def test_export_maps_manifest_fields_onto_csv_columns(tmp_path: Path) -> None:
    module = _load_module()
    artifact_dir = tmp_path / "run"
    artifact_dir.mkdir()
    (artifact_dir / "manifest.json").write_text(
        json.dumps(_manifest()), encoding="utf-8"
    )
    out = tmp_path / "out.csv"

    module.export(artifact_dir, out)

    with out.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    assert rows[0] == module.COLUMNS
    assert rows[1] == [
        "aa-01",
        "proxy",
        "11",
        "357418",
        "5407",
        "UNKNOWN",  # absent first_call_input_tokens degrades honestly
        "UNKNOWN",
        "UNKNOWN",  # cost has no per-task producer in the manifest
        "UNKNOWN",
        'Bound box: 8 points, "6" polygons.',
    ]
    assert rows[2][0] == "aa-02"
    assert rows[2][5] == "40108"
    assert len(rows) == 3


def test_first_call_column_falls_back_to_first_call_last_prompt(
    tmp_path: Path,
) -> None:
    """Five of the ten archived tasks carry only ``first_call_last_prompt``.

    Where both fields exist in the archived manifest they agree (4 of 4), so
    the CSV column cannot distinguish them; the fallback chain reproduces all
    ten archived cells while keeping the column's own name as first choice.
    """
    module = _load_module()
    artifact_dir = tmp_path / "run"
    artifact_dir.mkdir()
    manifest = {
        "baseline_tasks": [
            {"id": "bb-01", "first_call_last_prompt": 51661},
            {"id": "bb-02", "first_call_last_prompt": "UNKNOWN"},
            {
                "id": "bb-03",
                "first_call_input_tokens": 40108,
                "first_call_last_prompt": 40108,
            },
        ]
    }
    (artifact_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    out = tmp_path / "out.csv"

    module.export(artifact_dir, out)

    with out.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    column = module.COLUMNS.index("first_call_input_tokens")
    assert [row[column] for row in rows[1:]] == ["51661", "UNKNOWN", "40108"]


def test_missing_field_never_becomes_a_fabricated_zero(tmp_path: Path) -> None:
    module = _load_module()
    artifact_dir = tmp_path / "run"
    artifact_dir.mkdir()
    manifest = {"baseline_tasks": [{"id": "aa-03"}]}
    (artifact_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    out = tmp_path / "out.csv"

    module.export(artifact_dir, out)

    with out.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    assert rows[1][0] == "aa-03"
    assert set(rows[1][1:]) == {"UNKNOWN"}
