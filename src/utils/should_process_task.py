"""Idempotency utilities — skip processing when outputs are up-to-date."""

from pathlib import Path
from typing import List, Sequence, Union

PathLike = Union[str, Path]
PathInput = Union[PathLike, Sequence[PathLike]]


def _normalize_to_paths(targets: PathInput) -> List[Path]:
    if isinstance(targets, (str, Path)):
        return [Path(targets)]
    return [Path(p) for p in targets]


def clean_task_outputs(output_paths: PathInput) -> None:
    """Delete stale output files before reprocessing."""
    for p in _normalize_to_paths(output_paths):
        if p is not None and p.exists() and p.is_file():
            try:
                p.unlink()
                print(f"  Cleaned stale output: '{p.name}'")
            except PermissionError:
                print(f"  Could not delete '{p}' (locked). Proceeding anyway.")


def should_process_task(
    *,
    output_paths: PathInput,
    input_paths: PathInput,
    force: bool = False,
    keep_stale: bool = False,
) -> bool:
    """
    Determine whether a task should run based on file existence and timestamps.

    Returns True if processing is required, False if outputs are up-to-date.

    Raises ``FileNotFoundError`` if any input file is missing.
    """
    outputs = _normalize_to_paths(output_paths)
    inputs = _normalize_to_paths(input_paths)

    # Check inputs exist
    for p in inputs:
        if not p.exists():
            raise FileNotFoundError(f"Input file missing: {p}")

    # Force overrides everything
    if force:
        print(f"  Forced processing for: {[p.name for p in outputs]}")
        return True

    # Missing outputs require processing
    for p in outputs:
        if not p.exists():
            print(f"  Output '{p.name}' missing. Processing required.")
            return True

    # Staleness check: newest input vs oldest output
    try:
        oldest_output = min(p.stat().st_mtime for p in outputs)
        newest_input = max(p.stat().st_mtime for p in inputs)
    except ValueError:
        return True

    if newest_input > oldest_output:
        if keep_stale:
            print("  Stale but keep_stale=True. Touching outputs.")
            for p in outputs:
                try:
                    p.touch()
                except PermissionError:
                    return True
            return False
        print("  Stale outputs detected. Reprocessing.")
        return True

    print("  Outputs up-to-date. Skipping.")
    return False
