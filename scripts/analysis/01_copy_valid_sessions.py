"""Copy TILA_DATA folders whose participant ID appears in Excel_for_stimulators.xlsx.

Uses only stdlib (zipfile + xml.etree) to read the Excel file.
Copies matching folders into backlogs_local_data/TILA_DATA_VALID/.
"""

import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

BACKLOGS = Path(__file__).resolve().parent.parent / "backlogs_local_data"
EXCEL_PATH = BACKLOGS / "Excel_for_stimulators.xlsx"
TILA_DATA = BACKLOGS / "TILA_DATA"
TILA_DATA_VALID = BACKLOGS / "TILA_DATA_VALID"

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def extract_ids_from_excel(excel_path: Path) -> set[str]:
    """Extract unique IDs from column A of the first sheet."""
    with zipfile.ZipFile(excel_path) as zf:
        # Read shared strings
        shared_strings = []
        if "xl/sharedStrings.xml" in zf.namelist():
            tree = ET.parse(zf.open("xl/sharedStrings.xml"))
            root = tree.getroot()
            for si in root.findall("s:si", NS):
                # Handle both simple <t> and rich text <r><t> elements
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

        # Read sheet1
        tree = ET.parse(zf.open("xl/worksheets/sheet1.xml"))
        root = tree.getroot()

        ids = set()
        for row in root.findall(".//s:row", NS):
            for cell in row.findall("s:c", NS):
                ref = cell.get("r", "")
                # Only column A
                if not re.match(r"A\d+", ref):
                    continue
                cell_type = cell.get("t", "")
                val_elem = cell.find("s:v", NS)
                if val_elem is None or val_elem.text is None:
                    continue
                if cell_type == "s":
                    # Shared string index
                    idx = int(val_elem.text)
                    value = shared_strings[idx]
                else:
                    value = val_elem.text

                value = value.strip()
                # Accept IDs like T145, T81, etc. (skip header row)
                if re.match(r"T?\d+", value) and value.upper() != "ID":
                    # Normalize: ensure T prefix
                    if not value.startswith("T"):
                        value = "T" + value
                    ids.add(value)
        return ids


def extract_id_from_folder(folder_name: str) -> str | None:
    """Extract participant ID from folder name like 2025-06-04_T29 or 2025-12-05_112."""
    m = re.match(r"\d{4}-\d{2}-\d{2}_(T?\d+)$", folder_name)
    if not m:
        return None
    suffix = m.group(1)
    # Normalize: ensure T prefix
    if not suffix.startswith("T"):
        suffix = "T" + suffix
    return suffix


def main():
    # Step 1: Extract IDs from Excel
    excel_ids = extract_ids_from_excel(EXCEL_PATH)
    print(f"Extracted {len(excel_ids)} unique IDs from Excel")

    # Step 2: Match folders
    folders = sorted(p for p in TILA_DATA.iterdir() if p.is_dir())
    matched = []
    unmatched_folders = []
    matched_ids = set()

    for folder in folders:
        fid = extract_id_from_folder(folder.name)
        if fid is None:
            print(f"  Skipping (no valid ID): {folder.name}")
            continue
        if fid in excel_ids:
            matched.append(folder)
            matched_ids.add(fid)
        else:
            unmatched_folders.append((folder.name, fid))

    print(f"\nMatched {len(matched)} folders to Excel IDs")

    # Step 3: Copy
    TILA_DATA_VALID.mkdir(exist_ok=True)
    for folder in matched:
        dest = TILA_DATA_VALID / folder.name
        if dest.exists():
            print(f"  Already exists, skipping: {folder.name}")
            continue
        shutil.copytree(folder, dest)

    print(f"\nCopied to {TILA_DATA_VALID}")

    # Verification
    if unmatched_folders:
        print(f"\nFolders NOT in Excel ({len(unmatched_folders)}):")
        for name, fid in unmatched_folders:
            print(f"  {name} (ID: {fid})")

    missing_ids = excel_ids - matched_ids
    if missing_ids:
        print(f"\nExcel IDs with no folder ({len(missing_ids)}):")
        for mid in sorted(missing_ids, key=lambda x: int(x[1:])):
            print(f"  {mid}")

    # Final count
    valid_count = len(list(TILA_DATA_VALID.iterdir()))
    print(f"\nFinal: {valid_count} folders in TILA_DATA_VALID")


if __name__ == "__main__":
    main()
