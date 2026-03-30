#!/usr/bin/env python3
"""
    Split a TILA log file into per-day AM/PM segments.
    Use example:
        python scripts/split_log.py ti_gui_backup2026-02-26.log
        python scripts/split_log.py ti_gui_backup2026-02-26.log --output-dir log-split/

"""

import re
import argparse
from pathlib import Path
from collections import defaultdict

TIMESTAMP_RE = re.compile(r'^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2},\d{3})')


def segment_key(date: str, time: str) -> str:
    period = "AM" if int(time.split(":")[0]) < 13 else "PM"
    return f"{date}_{period}"


def split_log(input_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    segments: dict[str, list[str]] = defaultdict(list)
    current_key = "no_timestamp"

    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = TIMESTAMP_RE.match(line)
            if m:
                current_key = segment_key(m.group(1), m.group(2))
            segments[current_key].append(line)

    for key, lines in sorted(segments.items()):
        out_path = output_dir / f"{key}.log"
        out_path.write_text("".join(lines), encoding="utf-8")
        print(f"  {out_path.name}: {len(lines)} lines")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split a TILA .log file by day and AM/PM (before/after 13:00)."
    )
    parser.add_argument("input", type=Path, help="Input .log file path")
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=None,
        help="Output directory (default: <input_dir>/split/)"
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Error: file not found: {args.input}")

    output_dir = args.output_dir or args.input.parent / "split"
    print(f"Splitting '{args.input.name}' → '{output_dir}/'")
    split_log(args.input, output_dir)
    print("Done.")


if __name__ == "__main__":
    main()
