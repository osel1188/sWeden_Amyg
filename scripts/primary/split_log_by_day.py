"""Split TILA log files into per-day AM/PM segments.

Task contract:
    run_split_log_by_day(input_items, output_dir, force=False) -> list[Path]

input_items:  list of .log file Paths to split.
output_dir:   directory where split segment files are written.
force:        when True, re-split files whose segments already exist.

Returns a list of output segment file Paths produced across all inputs.
"""

import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import List

from utils.should_process_task import should_process_task, clean_task_outputs

log = logging.getLogger(__name__)

TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2},\d{3})")


# ---------------------------------------------------------------------------
# Core splitting logic
# ---------------------------------------------------------------------------


def segment_key(date: str, time: str) -> str:
    period = "AM" if int(time.split(":")[0]) < 13 else "PM"
    return f"{date}_{period}"


def split_log(input_path: Path, output_dir: Path) -> list[Path]:
    """Split *input_path* into AM/PM day-segments written to *output_dir*.

    Returns a list of the output file Paths that were written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    segments: dict[str, list[str]] = defaultdict(list)
    current_key = "no_timestamp"

    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = TIMESTAMP_RE.match(line)
            if m:
                current_key = segment_key(m.group(1), m.group(2))
            segments[current_key].append(line)

    written: list[Path] = []
    for key, lines in sorted(segments.items()):
        out_path = output_dir / f"{key}.log"
        out_path.write_text("".join(lines), encoding="utf-8")
        log.debug("  %s: %d lines", out_path.name, len(lines))
        written.append(out_path)

    return written


def _expected_segment_keys(input_path: Path) -> list[str]:
    """Do a first pass to collect which segment keys a log file would produce.

    Used for idempotency: if all expected output files exist, we can skip.
    """
    keys: set[str] = set()
    current_key = "no_timestamp"
    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = TIMESTAMP_RE.match(line)
            if m:
                current_key = segment_key(m.group(1), m.group(2))
            keys.add(current_key)
    return sorted(keys)


# ---------------------------------------------------------------------------
# Task function
# ---------------------------------------------------------------------------


def run_split_log_by_day(
    input_items: List[Path],
    output_dir: Path,
    force: bool = False,
) -> List[Path]:
    """Split each .log file in *input_items* into per-day AM/PM segments.

    Args:
        input_items:  Paths to .log files to process.
        output_dir:   Directory where split segment files are written.
        force:        Re-split even if output segments already exist.

    Returns:
        Flat list of all segment Paths produced (or already present).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results: List[Path] = []

    for input_path in input_items:
        if not input_path.is_file():
            log.warning("Skipping non-file input: %s", input_path)
            continue
        if input_path.suffix != ".log":
            log.warning("Skipping non-.log file: %s", input_path.name)
            continue

        # Determine expected output paths for idempotency check
        try:
            keys = _expected_segment_keys(input_path)
        except OSError as exc:
            log.error("Cannot read %s: %s", input_path, exc)
            continue

        expected_outputs: List[Path] = [Path(output_dir / f"{k}.log") for k in keys]

        if not should_process_task(
            input_paths=[input_path],
            output_paths=expected_outputs,
            force=force,
        ):
            results.extend(expected_outputs)
            continue

        clean_task_outputs(expected_outputs)
        log.info("Splitting '%s' -> '%s/'", input_path.name, output_dir)
        written = split_log(input_path, output_dir)
        results.extend(written)

    return results


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Split a TILA .log file by day and AM/PM (before/after 13:00)."
    )
    parser.add_argument("input", type=Path, help="Input .log file path")
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=None,
        help="Output directory (default: <input_dir>/split/)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-split even if output segments already exist.",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Error: file not found: {args.input}")

    output_dir = args.output_dir or args.input.parent / "split"
    results = run_split_log_by_day(
        input_items=[args.input],
        output_dir=output_dir,
        force=args.force,
    )
    print(f"Done. {len(results)} segment file(s) in {output_dir}")


if __name__ == "__main__":
    main()
