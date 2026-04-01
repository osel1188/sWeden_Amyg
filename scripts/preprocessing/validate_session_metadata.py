"""Validate that session metadata frequencies match expected condition patterns.

Task contract:
    run_validate_session_metadata(input_items, output_dir, force=False) -> list[Path]

input_items:  list of metadata.json Paths (one per session) to validate.
output_dir:   directory where the validation report CSV is written.
force:        when True, regenerate the report even if it already exists.

Returns a one-element list containing the report CSV Path.

Validation rules:
  active: A1 != A2 AND B1 != B2  (beat frequency present)
  sham:   A1 == A2 AND B1 == B2  (no beat frequency)
"""

import json
import logging
import re
from pathlib import Path
from typing import List

import pandas as pd

from utils.should_process_task import should_process_task, clean_task_outputs

log = logging.getLogger(__name__)

REPORT_FILENAME = "condition_validation_report.csv"


# ---------------------------------------------------------------------------
# Helpers (unchanged logic from 04_validate_session_metadata.py)
# ---------------------------------------------------------------------------


def load_conditions(excel_path: Path) -> dict[str, str]:
    """Return {participant_id: condition} from the Excel file."""
    df = pd.read_excel(excel_path, usecols=["ID", "condition"])
    conditions = {}
    for _, row in df.iterrows():
        pid = str(row["ID"]).strip()
        cond = str(row["condition"]).strip().lower()
        if pid and pid != "nan":
            conditions[pid] = cond
    return conditions


def extract_id_from_folder(folder_name: str) -> str | None:
    """Extract participant ID from folder name like 2025-06-04_T29."""
    m = re.match(r"\d{4}-\d{2}-\d{2}_(T?\d+)$", folder_name)
    if not m:
        return None
    suffix = m.group(1)
    if not suffix.startswith("T"):
        suffix = "T" + suffix
    return suffix


def extract_frequencies(freq_dict: dict) -> tuple[float, float, float, float]:
    """Handle both flat and nested metadata frequency formats.

    Flat:   {"A1": 7000, "A2": 7130, "B1": 9000, "B2": 9130}
    Nested: {"left": {"A1": 7000, "A2": 7130}, "right": {"B1": 9000, "B2": 9130}}
    """
    if "left" in freq_dict:
        return (
            freq_dict["left"]["A1"],
            freq_dict["left"]["A2"],
            freq_dict["right"]["B1"],
            freq_dict["right"]["B2"],
        )
    elif "A1" in freq_dict:
        return freq_dict["A1"], freq_dict["A2"], freq_dict["B1"], freq_dict["B2"]
    else:
        raise ValueError(f"Unrecognised frequency format: {list(freq_dict.keys())}")


def is_valid(condition: str, a1, a2, b1, b2) -> bool | None:
    if condition == "active":
        return a1 != a2 and b1 != b2
    elif condition == "sham":
        return a1 == a2 and b1 == b2
    return None


# ---------------------------------------------------------------------------
# Task function
# ---------------------------------------------------------------------------


def run_validate_session_metadata(
    input_metadata_paths: List[Path],
    excel_path: Path,
    output_dir: Path,
    force: bool = False,
) -> List[Path]:
    """Validate frequency metadata for each session and write a CSV report.

    Args:
        input_items:  metadata.json Paths.  Session folders containing a
                      metadata.json are also accepted.
        output_dir:   Directory where condition_validation_report.csv is written.
        force:        Regenerate the report even if it already exists.
        excel_path:   Path to Excel_for_stimulators.xlsx.  When omitted the
                      function looks for the file relative to output_dir's
                      parent (backlogs_local_data/).

    Returns:
        One-element list with the report CSV Path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = output_dir / REPORT_FILENAME

    # Resolve metadata.json paths
    metadata_files: list[Path] = []
    for item in sorted(input_metadata_paths):
        if item.is_file() and item.name == "metadata.json":
            metadata_files.append(item)
        elif item.is_dir():
            meta = item / "metadata.json"
            if meta.exists():
                metadata_files.append(meta)
            else:
                log.warning("No metadata.json in: %s", item)

    if not metadata_files:
        log.warning("No metadata.json files found in input_items.")
        return []

    # Idempotency: use all metadata files as inputs
    if not should_process_task(
        input_paths=metadata_files,
        output_paths=[output_csv],
        force=force,
    ):
        return [output_csv]

    clean_task_outputs([output_csv])

    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    conditions = load_conditions(excel_path)
    log.info("Loaded %d participant conditions from Excel", len(conditions))

    rows = []
    for meta_path in metadata_files:
        folder_name = meta_path.parent.name
        pid = extract_id_from_folder(folder_name)

        if pid is None:
            log.warning("Cannot parse ID from folder '%s', skipping", folder_name)
            continue

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            log.warning("JSON parse error in %s: %s, skipping", folder_name, e)
            continue

        freq_dict = meta.get("frequencies")
        if not freq_dict:
            log.warning("No 'frequencies' key in %s, skipping", folder_name)
            continue

        try:
            a1, a2, b1, b2 = extract_frequencies(freq_dict)
        except (KeyError, ValueError) as e:
            raise RuntimeError(f"Error extracting frequencies from {folder_name}: {e}") from e

        if pid not in conditions:
            log.warning("%s not found in Excel, condition=UNKNOWN", pid)
            condition = "UNKNOWN"
        else:
            condition = conditions[pid]

        valid = is_valid(condition, a1, a2, b1, b2)

        rows.append({
            "session": folder_name,
            "participant_id": pid,
            "condition": condition,
            "A1": a1,
            "A2": a2,
            "B1": b1,
            "B2": b2,
            "is_valid": valid,
        })

    df = pd.DataFrame(rows)
    df.to_csv(output_csv, index=False)
    log.info("Report written to %s", output_csv)

    total = len(df)
    valid_count = int(df["is_valid"].sum()) if total > 0 else 0
    invalid_count = int((df["is_valid"] == False).sum()) if total > 0 else 0  # noqa: E712
    unknown_count = int(df["is_valid"].isna().sum()) if total > 0 else 0
    log.info(
        "Summary: %d sessions | %d valid | %d invalid | %d unknown condition",
        total, valid_count, invalid_count, unknown_count,
    )

    if invalid_count > 0:
        inv = df[df["is_valid"] == False]  # noqa: E712
        for _, r in inv.iterrows():
            log.warning(
                "INVALID: %s  condition=%s  A1=%s A2=%s B1=%s B2=%s",
                r["session"], r["condition"], r["A1"], r["A2"], r["B1"], r["B2"],
            )

    return [output_csv]


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

_DEFAULT_PROCESSED = Path("backlogs_local_data/TILA_DATA_1_processed")
_DEFAULT_OUTPUT = Path("backlogs_local_data")


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Validate session metadata frequencies against participant conditions."
    )
    parser.add_argument(
        "input_dir", nargs="?", type=Path, default=_DEFAULT_PROCESSED,
        help=f"Directory containing session folders with metadata.json files (default: {_DEFAULT_PROCESSED})",
    )
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=_DEFAULT_OUTPUT,
        help=f"Output directory for the report CSV (default: {_DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--excel", type=Path, default=None,
        help="Path to Excel_for_stimulators.xlsx (default: output_dir/Excel_for_stimulators.xlsx).",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Regenerate the report even if it already exists.",
    )
    args = parser.parse_args()

    if not args.input_dir.exists():
        raise SystemExit(f"Error: input directory not found: {args.input_dir}")

    input_items = sorted(args.input_dir.glob("*/metadata.json"))
    if not input_items:
        raise SystemExit(f"Error: no metadata.json files found in {args.input_dir}")

    results = run_validate_session_metadata(
        input_metadata_paths=input_items,
        excel_path=args.excel,
        output_dir=args.output_dir,
        force=args.force
    )
    if results:
        print(f"Done. Report written to {results[0]}")


if __name__ == "__main__":
    main()
