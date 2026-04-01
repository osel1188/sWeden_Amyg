"""Filter TILA_DATA session folders to only those whose participant ID appears in Excel.

Task contract:
    run_filter_valid_sessions(input_items, output_dir, force=False) -> list[Path]

input_items:  list of session folder Paths to evaluate (must be directories).
output_dir:   destination directory — valid session folders are *copied* here.
force:        when True, re-copy folders that already exist in output_dir.

Returns a list of destination folder Paths (one per matched/copied session).
"""

import logging
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import List

from utils.should_process_task import should_process_task, clean_task_outputs

log = logging.getLogger(__name__)

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


# ---------------------------------------------------------------------------
# Excel ID extraction
# ---------------------------------------------------------------------------


def extract_ids_from_excel(excel_path: Path) -> set[str]:
    """Extract unique participant IDs from column A of the first sheet."""
    with zipfile.ZipFile(excel_path) as zf:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            tree = ET.parse(zf.open("xl/sharedStrings.xml"))
            root = tree.getroot()
            for si in root.findall("s:si", NS):
                texts = []
                t_elem = si.find("s:t", NS)
                if t_elem is not None and t_elem.text:
                    texts.append(t_elem.text)
                else:
                    for r in si.findall("s:r", NS):
                        t = r.find("s:t", NS)
                        if t is not None and t.text:
                            texts.append(t.text)
                shared_strings.append("".join(texts))

        tree = ET.parse(zf.open("xl/worksheets/sheet1.xml"))
        root = tree.getroot()

        ids: set[str] = set()
        for row in root.findall(".//s:row", NS):
            for cell in row.findall("s:c", NS):
                ref = cell.get("r", "")
                if not re.match(r"A\d+", ref):
                    continue
                cell_type = cell.get("t", "")
                val_elem = cell.find("s:v", NS)
                if val_elem is None or val_elem.text is None:
                    continue
                if cell_type == "s":
                    value = shared_strings[int(val_elem.text)]
                else:
                    value = val_elem.text
                value = value.strip()
                if re.match(r"T?\d+", value) and value.upper() != "ID":
                    if not value.startswith("T"):
                        value = "T" + value
                    ids.add(value)
    return ids


# ---------------------------------------------------------------------------
# Folder ID extraction
# ---------------------------------------------------------------------------


def extract_id_from_folder(folder_name: str) -> str | None:
    """Extract participant ID from folder name like 2025-06-04_T29 or 2025-12-05_112."""
    m = re.match(r"\d{4}-\d{2}-\d{2}_(T?\d+)$", folder_name)
    if not m:
        return None
    suffix = m.group(1)
    if not suffix.startswith("T"):
        suffix = "T" + suffix
    return suffix


# ---------------------------------------------------------------------------
# Task function
# ---------------------------------------------------------------------------


def run_filter_valid_sessions(
    input_items: List[Path],
    excel_path: Path,
    output_dir: Path,
    force: bool = False
) -> List[Path]:
    """Copy session folders whose participant ID appears in *excel_path* to *output_dir*.

    Args:
        input_items:  Session folder Paths to evaluate.
        output_dir:   Destination for valid session folders.
        force:        Re-copy folders that already exist in *output_dir*.
        excel_path:   Path to Excel_for_stimulators.xlsx.  When omitted the
                      function tries to locate the file relative to output_dir's
                      parent (backlogs_local_data/).

    Returns:
        List of destination folder Paths for all matched sessions.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    excel_ids = extract_ids_from_excel(excel_path)
    log.info("Extracted %d unique IDs from Excel", len(excel_ids))

    results: List[Path] = []
    matched_ids: set[str] = set()
    unmatched: list[tuple[str, str]] = []

    for folder in sorted(input_items):
        if not folder.is_dir():
            log.debug("Skipping non-directory input: %s", folder)
            continue

        fid = extract_id_from_folder(folder.name)
        if fid is None:
            log.debug("Skipping (no valid ID): %s", folder.name)
            continue

        if fid not in excel_ids:
            unmatched.append((folder.name, fid))
            continue

        matched_ids.add(fid)
        dest = output_dir / folder.name

        # Idempotency: use a sentinel file (the folder itself) to detect prior runs.
        # For directory copies we check existence directly rather than use
        # should_process_task (which expects files, not directories).
        if dest.exists() and not force:
            log.info("Already exists, skipping: %s", folder.name)
            results.append(dest)
            continue

        if dest.exists() and force:
            log.info("Forced re-copy — removing existing: %s", folder.name)
            shutil.rmtree(dest)

        shutil.copytree(folder, dest)
        log.info("Copied: %s -> %s", folder.name, dest)
        results.append(dest)

    if unmatched:
        log.warning(
            "%d folder(s) not in Excel: %s",
            len(unmatched),
            [name for name, _ in unmatched],
        )

    missing_ids = excel_ids - matched_ids
    if missing_ids:
        log.warning(
            "%d Excel ID(s) with no matching folder: %s",
            len(missing_ids),
            sorted(missing_ids, key=lambda x: int(x[1:])),
        )

    log.info("filter_valid_sessions complete. %d folders in output_dir.", len(results))
    return results


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Copy valid TILA session folders (ID in Excel) to output_dir."
    )
    parser.add_argument(
        "input_dir", type=Path,
        help="Directory containing TILA_DATA session folders (e.g. TILA_DATA/).",
    )
    parser.add_argument(
        "-o", "--output-dir", type=Path, required=True,
        help="Destination directory for valid sessions (e.g. TILA_DATA_VALID/).",
    )
    parser.add_argument(
        "--excel", type=Path, default=None,
        help="Path to Excel_for_stimulators.xlsx (default: output_dir/../Excel_for_stimulators.xlsx).",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-copy folders that already exist in output_dir.",
    )
    args = parser.parse_args()

    if not args.input_dir.exists():
        raise SystemExit(f"Error: input directory not found: {args.input_dir}")

    input_items = sorted(p for p in args.input_dir.iterdir() if p.is_dir())
    results = run_filter_valid_sessions(
        input_items=input_items,
        output_dir=args.output_dir,
        force=args.force,
        excel_path=args.excel,
    )
    print(f"Done. {len(results)} valid session folder(s) in {args.output_dir}")


if __name__ == "__main__":
    main()
