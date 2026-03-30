"""Validate that session metadata frequencies match expected condition patterns.

Reads participant conditions from Excel_for_stimulators.xlsx and each session's
metadata.json, then outputs a CSV report with validity checks.

Validation rules:
  active: A1 != A2 AND B1 != B2  (beat frequency present)
  sham:   A1 == A2 AND B1 == B2  (no beat frequency)

Output: backlogs_local_data/metadata_validation_report.csv
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd

BACKLOGS = Path(__file__).resolve().parent.parent / "backlogs_local_data"
EXCEL_PATH = BACKLOGS / "Excel_for_stimulators.xlsx"
PROCESSED_DIR = BACKLOGS / "TILA_DATA_1_processed"
OUTPUT_CSV = BACKLOGS / "condition_validation_report.csv"


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
    """Handle both flat and nested metadata formats.

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


def main():
    # Load condition map from Excel
    if not EXCEL_PATH.exists():
        sys.exit(f"Excel not found: {EXCEL_PATH}")
    conditions = load_conditions(EXCEL_PATH)
    print(f"Loaded {len(conditions)} participant conditions from Excel")

    # Glob metadata files
    metadata_files = sorted(PROCESSED_DIR.glob("*/metadata.json"))
    print(f"Found {len(metadata_files)} metadata files in {PROCESSED_DIR.name}")

    rows = []
    for meta_path in metadata_files:
        folder_name = meta_path.parent.name
        pid = extract_id_from_folder(folder_name)

        if pid is None:
            print(f"  WARNING: cannot parse ID from folder '{folder_name}', skipping")
            continue

        # Load JSON
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"  WARNING: JSON parse error in {folder_name}: {e}, skipping")
            continue

        # Extract frequencies
        freq_dict = meta.get("frequencies")
        if not freq_dict:
            print(f"  WARNING: no 'frequencies' key in {folder_name}, skipping")
            continue

        try:
            a1, a2, b1, b2 = extract_frequencies(freq_dict)
        except (KeyError, ValueError) as e:
            sys.exit(f"ERROR: {folder_name}: {e}")

        # Look up condition
        if pid not in conditions:
            print(f"  WARNING: {pid} not found in Excel, condition=UNKNOWN")
            condition = "UNKNOWN"
        else:
            condition = conditions[pid]

        valid = is_valid(condition, a1, a2, b1, b2)

        rows.append(
            {
                "session": folder_name,
                "participant_id": pid,
                "condition": condition,
                "A1": a1,
                "A2": a2,
                "B1": b1,
                "B2": b2,
                "is_valid": valid,
            }
        )

    # Write CSV
    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nReport written to {OUTPUT_CSV}")

    # Summary
    total = len(df)
    valid_count = df["is_valid"].sum()
    invalid_count = (df["is_valid"] == False).sum()  # noqa: E712
    unknown_count = df["is_valid"].isna().sum()
    print(f"\nSummary: {total} sessions | {valid_count} valid | {invalid_count} invalid | {unknown_count} unknown condition")

    if invalid_count > 0:
        print("\nInvalid sessions:")
        inv = df[df["is_valid"] == False]  # noqa: E712
        for _, r in inv.iterrows():
            print(f"  {r['session']}  condition={r['condition']}  A1={r['A1']} A2={r['A2']} B1={r['B1']} B2={r['B2']}")


if __name__ == "__main__":
    main()
