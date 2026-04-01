"""Resample event-based voltage timeseries to a regular time grid.

Task contract
─────────────
Consumes : voltages.csv          (event-based voltage timeseries)
Produces : voltages_resampled.csv (regularly-sampled timeseries)
Depends  : extract_session_data

run_resample_voltages(input_items, output_dir, force=False) -> list[Path]

input_items:  list of voltages.csv Paths to resample.  Session folders
              containing a voltages.csv are also accepted.
output_dir:   directory where voltages_resampled.csv files are written.
              Each session's output is written to output_dir/<session_name>/.
force:        when True, reprocess sessions whose outputs already exist.

Returns a list of voltages_resampled.csv Paths produced.

Algorithm:
  1. Compute the natural sampling rate from per-channel minimum non-zero
     time deltas between consecutive voltage changes.
  2. Build a regular timestamp grid at that rate spanning the full session.
  3. Forward-fill (zero-order hold) all channel values onto the grid.
"""

import logging
from pathlib import Path
from typing import List

import pandas as pd

from utils.should_process_task import should_process_task, clean_task_outputs
from preprocessing.tag_voltage_intervals import (
    CommentedCsvReader,
    CommentedCsvWriter,
)

log = logging.getLogger(__name__)

CHANNELS = ["A1", "A2", "B1", "B2"]


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def compute_sampling_rate(df: pd.DataFrame, channels: list[str], Fs_max: int) -> float:
    """Derive the natural sampling rate from minimum inter-change deltas.

    For each channel, find rows where the voltage value changes, compute the
    timestamp deltas between consecutive changes, discard zero deltas, and
    record the minimum.  The global minimum across all channels gives the
    finest temporal resolution, and Fs = 1 / min_delta.

    Args:
        df:       DataFrame with a ``timestamp`` column and one column per
                  channel.
        channels: List of channel column names to inspect.

    Returns:
        Sampling rate in Hz.

    Raises:
        ValueError: If no voltage changes are found in any channel.
    """
    min_delta_seconds: float | None = None

    for ch in channels:
        if ch not in df.columns:
            continue

        diffs = df[ch].diff().abs()
        change_mask = diffs > 0
        change_indices = df.index[change_mask]

        if len(change_indices) < 2:
            continue

        ts_at_changes = df.loc[change_indices, "timestamp"]
        deltas = ts_at_changes.diff().dropna().dt.total_seconds()
        nonzero_deltas = deltas[deltas > 0]

        if nonzero_deltas.empty:
            continue

        ch_min = nonzero_deltas.min()
        if (min_delta_seconds is None or ch_min < min_delta_seconds) and 1/Fs_max <= ch_min:
            min_delta_seconds = ch_min

    if min_delta_seconds is None:
        raise ValueError(
            "No voltage changes found in any channel — cannot compute "
            "sampling rate."
        )

    fs = 1.0 / min_delta_seconds

    if fs < 10 or fs > 200:
        log.warning(
            "Computed sampling rate %.2f Hz is outside the expected "
            "[10, 200] Hz range.",
            fs,
        )

    return fs


def resample_session(df: pd.DataFrame, fs: float) -> pd.DataFrame:
    """Resample *df* onto a regular time grid at *fs* Hz using forward-fill.

    Args:
        df: DataFrame with a ``timestamp`` column and channel value columns.
        fs: Sampling rate in Hz.

    Returns:
        A new DataFrame with regularly-spaced timestamps and forward-filled
        channel values.
    """
    start = df["timestamp"].iloc[0]
    end = df["timestamp"].iloc[-1]
    period = pd.Timedelta(seconds=1.0 / fs)

    new_index = pd.date_range(start=start, end=end, freq=period, name="timestamp")

    resampled = (
        df.set_index("timestamp")
        .loc[lambda x: ~x.index.duplicated(keep="last")]
        .reindex(new_index, method="ffill")
        .reset_index()
    )

    return resampled


# ---------------------------------------------------------------------------
# Task function
# ---------------------------------------------------------------------------


def _plot_resampled(session_name: str, df: pd.DataFrame, channels: list[str]) -> None:
    import matplotlib.pyplot as plt

    available = [ch for ch in channels if ch in df.columns]
    fig, axes = plt.subplots(len(available), 1, sharex=True, figsize=(12, 2 * len(available)))
    if len(available) == 1:
        axes = [axes]

    for ax, ch in zip(axes, available):
        ax.plot(df["timestamp"], df[ch], drawstyle="steps-post", linewidth=0.8)
        ax.set_ylabel(ch)
        ax.grid(True, alpha=0.3)

    axes[-1].set_xlabel("Time")
    fig.suptitle(f"{session_name} — resampled voltages")
    fig.tight_layout()
    plt.show(block=True)


def run_resample_voltages(
    input_items: List[Path],
    output_dir: Path,
    *,
    Fs_max: int = 20,
    force: bool = False,
    monitor: bool = True,
) -> List[Path]:
    """Resample each voltages.csv to a regular grid and write voltages_resampled.csv.

    Args:
        input_items:  voltages.csv Paths or session folder Paths containing a
                      voltages.csv.
        output_dir:   Root output directory.  Each session's output goes to
                      output_dir/<session_name>/.
        Fs_max:       Fs max cap at 20 Hz
        force:        Reprocess even if voltages_resampled.csv already exists.

    Returns:
        List of voltages_resampled.csv Paths produced.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve input paths to (session_name, csv_path) pairs
    csv_entries: list[tuple[str, Path]] = []
    for item in sorted(input_items):
        if item.is_file() and item.name == "voltages.csv":
            csv_entries.append((item.parent.name, item))
        elif item.is_dir():
            csv_path = item / "voltages.csv"
            if csv_path.exists():
                csv_entries.append((item.name, csv_path))
            else:
                log.warning("No voltages.csv in: %s", item)

    if not csv_entries:
        log.warning("No voltages.csv files found in input_items.")
        return []

    reader = CommentedCsvReader()
    writer = CommentedCsvWriter()
    results: List[Path] = []

    for session_name, csv_path in csv_entries:
        session_out_dir = output_dir / session_name
        session_out_dir.mkdir(parents=True, exist_ok=True)

        out_path = session_out_dir / "voltages_resampled.csv"

        if not should_process_task(
            input_paths=[csv_path],
            output_paths=[out_path],
            force=force,
        ):
            results.append(out_path)
            continue

        clean_task_outputs([out_path])

        comments, df = reader.read(csv_path)

        try:
            fs = compute_sampling_rate(df, CHANNELS, Fs_max=Fs_max)
        except ValueError:
            log.warning(
                "Skipping session '%s': no voltage changes found — "
                "cannot determine sampling rate.",
                session_name,
            )
            continue

        log.info(
            "Session '%s': computed sampling rate = %.2f Hz", session_name, fs
        )

        resampled_df = resample_session(df, fs)

        if monitor:
            _plot_resampled(session_name, resampled_df, CHANNELS)

        # Prepend sampling rate comment to existing comments
        rate_comment = f"# sampling_rate_hz: {fs}\n"
        out_comments = [rate_comment] + comments

        writer.write(resampled_df, out_comments, out_path)
        log.info("Saved: %s (%d rows)", out_path, len(resampled_df))

        results.append(out_path)

    return results


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

_DEFAULT_PREPROCESS_DIR = Path("backlogs_local_data/TILA_DATA_1_processed")


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Resample event-based voltage CSVs to a regular time grid."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        type=Path,
        default=_DEFAULT_PREPROCESS_DIR,
        help=(
            "Directory containing session folders with voltages.csv files "
            f"(default: {_DEFAULT_PREPROCESS_DIR})"
        ),
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: same as input_dir).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess even if voltages_resampled.csv already exists.",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Plot each session's resampled channels after processing.",
    )
    args = parser.parse_args()

    if not args.input_dir.exists():
        raise SystemExit(f"Error: input directory not found: {args.input_dir}")

    output_dir = args.output_dir or args.input_dir
    input_items = sorted(args.input_dir.glob("*/voltages.csv"))

    if not input_items:
        raise SystemExit(
            f"Error: no voltages.csv files found in {args.input_dir}"
        )

    results = run_resample_voltages(
        input_items=input_items,
        output_dir=output_dir,
        force=args.force,
        monitor=args.monitor,
    )
    print(
        f"Done. {len(results)} session(s) resampled. "
        f"Output CSVs in {output_dir}/"
    )


if __name__ == "__main__":
    main()
