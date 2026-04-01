"""Workflow task: analyse stimulation intervals across all sessions.

Task contract
-------------
``run_analyse_stim_intervals(session_dirs, output_csv, output_duration_png,
output_voltage_png)`` is a pure processor: receives session directories and
fully resolved output paths, writes the summary CSV and comparison PNGs, and
returns ``None``.  The workflow owns idempotency and path construction.

The task prefers ``voltages_corrected.csv`` (human-verified boundaries),
falls back to ``voltages_tagged.csv`` (auto-detected consensus), then to
``voltages.csv`` with gap-based re-detection.

Standalone use
--------------
    python scripts/analysis/analyse_stim_intervals.py
    python scripts/analysis/analyse_stim_intervals.py \\
        --preprocess-dir /path/to/processed --output-dir /path/to/analysed
"""

import argparse
import logging
import pathlib
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

CHANNELS = ["A1", "A2", "B1", "B2"]
THRESHOLD = 0.5  # V — voltage above which a channel is considered active
MIN_GAP_DURATION = 10  # minutes — minimum 0 V gap to split into two blocks


# ---------------------------------------------------------------------------
# Phase 1: Core Detection and Extraction
# (logic unchanged from 06_analyse_stim_intervals.py)
# ---------------------------------------------------------------------------


def load_session(csv_path: pathlib.Path) -> pd.DataFrame:
    """Read voltages CSV, parse timestamps, return DataFrame sorted by time."""
    df = pd.read_csv(csv_path, parse_dates=["timestamp"], comment="#")
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def find_long_gap(
    df: pd.DataFrame,
    threshold: float = THRESHOLD,
    min_gap_min: float = MIN_GAP_DURATION,
) -> tuple[str, pd.Timestamp | None, pd.Timestamp | None]:
    """Find the longest inactive gap >= *min_gap_min* minutes.

    Returns (status, gap_start, gap_end).
    Status is ``'ok'`` when a qualifying gap is found, ``'single_block'``
    when no gap long enough exists, or ``'skipped'`` when there is no
    activity at all.
    """
    any_active = df[CHANNELS].max(axis=1) > threshold

    if not any_active.any():
        return "skipped", None, None

    # Label contiguous runs of active / inactive
    run_id = (any_active != any_active.shift()).cumsum()

    # Keep only inactive runs
    inactive_mask = ~any_active
    if not inactive_mask.any():
        return "single_block", None, None

    inactive_runs = df[inactive_mask].groupby(run_id[inactive_mask])["timestamp"]
    gap_candidates: list[tuple[pd.Timedelta, pd.Timestamp, pd.Timestamp]] = []

    for _gid, ts_group in inactive_runs:
        gap_start = ts_group.iloc[0]
        gap_end = ts_group.iloc[-1]
        duration = gap_end - gap_start
        if duration >= pd.Timedelta(minutes=min_gap_min):
            gap_candidates.append((duration, gap_start, gap_end))

    if not gap_candidates:
        return "single_block", None, None

    # Pick the longest qualifying gap
    gap_candidates.sort(reverse=True)
    _, best_start, best_end = gap_candidates[0]
    return "ok", best_start, best_end


def _mode_or_median(timestamps: list[pd.Timestamp]) -> pd.Timestamp:
    """Return the mode of *timestamps*, falling back to the median.

    Timestamps are rounded to the nearest second before computing the
    mode so that sub-second jitter across channels doesn't prevent a match.
    """
    if not timestamps:
        raise ValueError("empty timestamp list")
    rounded = pd.Series([t.round("s") for t in timestamps])
    mode_vals = rounded.mode()
    if len(mode_vals) == 1:
        return mode_vals.iloc[0]
    # Tie or all-different → use median of original timestamps
    numeric = pd.Series([t.value for t in timestamps])
    return pd.Timestamp(int(numeric.median()))


def refine_interval_boundaries(
    df: pd.DataFrame,
    region_start: pd.Timestamp,
    region_end: pd.Timestamp,
    threshold: float = THRESHOLD,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Compute unified (start, end) for the active region using mode."""
    mask = (df["timestamp"] >= region_start) & (df["timestamp"] <= region_end)
    region = df.loc[mask]

    start_candidates: list[pd.Timestamp] = []
    end_candidates: list[pd.Timestamp] = []

    for ch in CHANNELS:
        active = region[region[ch] > threshold]
        if active.empty:
            continue
        start_candidates.append(active["timestamp"].iloc[0])
        end_candidates.append(active["timestamp"].iloc[-1])

    if not start_candidates:
        return region_start, region_end

    return _mode_or_median(start_candidates), _mode_or_median(end_candidates)


def detect_and_classify(
    df: pd.DataFrame,
    threshold: float = THRESHOLD,
    min_gap_min: float = MIN_GAP_DURATION,
) -> tuple[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]]:
    """Detect stimulation blocks by finding the long 0 V gap.

    Returns (status, [(start, end, block_label), ...]).
    """
    status, gap_start, gap_end = find_long_gap(df, threshold, min_gap_min)

    if status == "skipped":
        return "skipped", []

    if status == "single_block":
        any_active = df[CHANNELS].max(axis=1) > threshold
        first_active = df.loc[any_active, "timestamp"].iloc[0]
        last_active = df.loc[any_active, "timestamp"].iloc[-1]
        start, end = refine_interval_boundaries(df, first_active, last_active, threshold)
        return "single_block", [(start, end, "Block 1")]

    block1_start, block1_end = refine_interval_boundaries(
        df, df["timestamp"].iloc[0], gap_start, threshold
    )
    block2_start, block2_end = refine_interval_boundaries(
        df, gap_end, df["timestamp"].iloc[-1], threshold
    )
    return "ok", [
        (block1_start, block1_end, "Block 1"),
        (block2_start, block2_end, "Block 2"),
    ]


# ---------------------------------------------------------------------------
# Backward-compatible wrappers (used by sex_based_voltage_analysis.py)
# ---------------------------------------------------------------------------


def detect_active_intervals(
    df: pd.DataFrame, threshold: float = THRESHOLD
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return (start, end) tuples for each stimulation block."""
    _status, classified = detect_and_classify(df, threshold)
    return [(s, e) for s, e, _label in classified]


def classify_intervals(
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> tuple[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]]:
    """Classify intervals by temporal order (Block 1 first, Block 2 second)."""
    if not intervals:
        return "skipped", []

    if len(intervals) == 1:
        s, e = intervals[0]
        return "single_block", [(s, e, "Block 1")]

    ordered = sorted(intervals, key=lambda t: t[0])
    labelled = [(s, e, f"Block {i + 1}") for i, (s, e) in enumerate(ordered)]
    status = "ok" if len(ordered) == 2 else "extra_blocks"
    return status, labelled


# ---------------------------------------------------------------------------
# Interval-column extraction (preferred over gap-based detection)
# ---------------------------------------------------------------------------


def resolve_session_csv(
    session_dir: pathlib.Path,
) -> tuple[pathlib.Path | None, str]:
    """Find the best available voltage CSV for a session."""
    if (session_dir / "discarded.flag").exists():
        return None, "discarded"
    for filename, source in [
        ("voltages_corrected.csv", "corrected"),
        ("voltages_tagged.csv", "tagged"),
        ("voltages.csv", "raw"),
    ]:
        path = session_dir / filename
        if path.exists():
            return path, source
    return None, "missing"


def extract_blocks_from_interval_column(
    df: pd.DataFrame,
) -> tuple[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]]:
    """Extract block boundaries from the ``interval`` column."""
    if "interval" not in df.columns:
        return "no_interval_column", []

    blocks: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []
    for block_num in (1, 2):
        mask = df["interval"] == block_num
        if mask.any():
            start = df.loc[mask, "timestamp"].iloc[0]
            end = df.loc[mask, "timestamp"].iloc[-1]
            if start != end:
                blocks.append((start, end, f"Block {block_num}"))

    if not blocks:
        return "skipped", []
    if len(blocks) == 1:
        return "single_block", blocks
    return "ok", blocks


# ---------------------------------------------------------------------------
# Channel statistics extraction
# ---------------------------------------------------------------------------


def extract_channel_stats(
    df: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    channels: list[str] = CHANNELS,
) -> dict[str, dict]:
    """Extract per-channel stats within [start, end]."""
    mask = (df["timestamp"] >= start) & (df["timestamp"] <= end)
    segment = df.loc[mask, ["timestamp"] + channels].copy()

    if segment.empty:
        return {ch: {"duration_min": 0.0, "median_voltage": 0.0} for ch in channels}

    segment = segment.set_index("timestamp")[channels]
    segment = segment[~segment.index.duplicated(keep="last")]

    time_index = pd.date_range(start=start.ceil("s"), end=end.floor("s"), freq="1s")
    if time_index.empty:
        time_index = pd.date_range(start=start, periods=1, freq="1s")

    combined_index = segment.index.union(time_index)
    resampled = segment.reindex(combined_index).ffill().bfill().reindex(time_index)

    stats = {}
    for ch in channels:
        if ch not in resampled.columns:
            stats[ch] = {"duration_min": 0.0, "median_voltage": 0.0}
            continue
        col = resampled[ch]
        active = col[col > THRESHOLD]
        stats[ch] = {
            "duration_min": round(len(active) / 60.0, 2),
            "median_voltage": round(float(active.median()), 4) if len(active) > 0 else 0.0,
        }

    return stats


# ---------------------------------------------------------------------------
# Phase 2: Batch Processing and CSV Output
# ---------------------------------------------------------------------------


def analyse_all_sessions(session_dirs: list[pathlib.Path]) -> pd.DataFrame:
    """Iterate *session_dirs* and extract interval stats."""
    if not session_dirs:
        logging.warning("No session directories provided — nothing to analyse.")
        return pd.DataFrame()

    rows = []
    counts = {"ok": 0, "single_block": 0, "skipped": 0}

    for session_dir in session_dirs:
        session_name = session_dir.name
        csv_path, source = resolve_session_csv(session_dir)

        if csv_path is None:
            print(f"  WARNING [{session_name}]: no voltage CSV found — skipping")
            counts["skipped"] += 1
            continue

        df = load_session(csv_path)
        print(f"  [{session_name}]: using {csv_path.name}")

        if source in ("corrected", "tagged"):
            status, classified = extract_blocks_from_interval_column(df)
            if status == "no_interval_column":
                print(f"    no 'interval' column in {csv_path.name} — falling back to gap detection")
                raw_path = session_dir / "voltages.csv"
                df = load_session(raw_path)
                status, classified = detect_and_classify(df)
        else:
            status, classified = detect_and_classify(df)

        if status == "skipped":
            print(f"    WARNING: no blocks detected — skipping")
            counts["skipped"] += 1
            continue
        if status == "single_block":
            print(f"    WARNING: only 1 block detected")
            counts["single_block"] += 1
        else:
            counts["ok"] += 1

        for start, end, block_label in classified:
            channel_stats = extract_channel_stats(df, start, end)
            for ch, ch_stats in channel_stats.items():
                rows.append(
                    {
                        "session": session_name,
                        "block": block_label,
                        "channel": ch,
                        "status": status,
                        "block_start": start,
                        "block_end": end,
                        "duration_min": ch_stats["duration_min"],
                        "median_voltage": ch_stats["median_voltage"],
                    }
                )

    print(
        f"\nSession summary: "
        f"{counts['ok']} ok | "
        f"{counts['single_block']} single_block | "
        f"{counts['skipped']} skipped"
    )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Phase 3: Figure Generation
# ---------------------------------------------------------------------------


def plot_strip_comparison(
    summary_df: pd.DataFrame,
    metric: str,
    ylabel: str,
    title: str,
    output_path: pathlib.Path,
) -> None:
    """Strip plot with mean line and ±1 STD band, split by Block 1 / Block 2."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
    fig.suptitle(title, fontsize=14, fontweight="bold")

    x_positions = {ch: i for i, ch in enumerate(CHANNELS)}

    for ax, block_label in zip(axes, ["Block 1", "Block 2"]):
        block_df = summary_df[summary_df["block"] == block_label]

        for ch in CHANNELS:
            x = x_positions[ch]
            ch_data = block_df[block_df["channel"] == ch][metric].dropna()
            if ch_data.empty:
                continue

            jitter = np.random.uniform(-0.15, 0.15, size=len(ch_data))
            ax.scatter(x + jitter, ch_data.values, s=20, alpha=0.6, color=f"C{x}", zorder=3)

            mean_val = ch_data.mean()
            std_val = ch_data.std()

            ax.plot([x - 0.3, x + 0.3], [mean_val, mean_val], color="black", lw=2, zorder=4)
            ax.fill_between(
                [x - 0.3, x + 0.3],
                mean_val - std_val,
                mean_val + std_val,
                alpha=0.2,
                color="black",
                zorder=2,
            )
            ax.text(
                x,
                mean_val + std_val,
                f"{mean_val:.1f}±{std_val:.1f}",
                ha="center",
                va="bottom",
                fontsize=7,
                color="black",
            )

        ax.set_title(block_label, fontsize=12)
        ax.set_xticks(list(x_positions.values()))
        ax.set_xticklabels(CHANNELS)
        ax.set_xlabel("Channel")
        ax.set_ylabel(ylabel if block_label == "Block 1" else "")
        ax.grid(axis="y", linestyle="--", alpha=0.4)

    plt.tight_layout()
    fig.savefig(output_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    logging.info(f"  saved {output_path.name}")


# ---------------------------------------------------------------------------
# Task contract
# ---------------------------------------------------------------------------


def run_analyse_stim_intervals(
    session_dirs: list[pathlib.Path],
    output_csv: pathlib.Path,
    output_duration_png: pathlib.Path,
    output_voltage_png: pathlib.Path,
) -> None:
    """Analyse stimulation intervals across all sessions.

    Pure processor: receives fully resolved paths, returns ``None``.
    The workflow owns idempotency and path construction.

    Parameters
    ----------
    session_dirs:
        Session directories to analyse (each should contain a voltage CSV).
    output_csv:
        Path where ``interval_summary.csv`` is written.
    output_duration_png:
        Path where the duration comparison PNG is written.
    output_voltage_png:
        Path where the voltage comparison PNG is written.
    """
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    logging.info("Analysing %d session(s)...", len(session_dirs))
    summary_df = analyse_all_sessions(session_dirs)

    if summary_df.empty:
        logging.warning("[analyse_stim_intervals] No data extracted — outputs not written.")
        return

    summary_df.to_csv(output_csv, index=False)
    logging.info("Saved %d rows to %s", len(summary_df), output_csv.name)

    logging.info("Generating figures...")
    np.random.seed(42)

    plot_strip_comparison(
        summary_df,
        metric="duration_min",
        ylabel="Duration (min)",
        title="Stimulation Block Duration by Channel",
        output_path=output_duration_png,
    )
    plot_strip_comparison(
        summary_df,
        metric="median_voltage",
        ylabel="Median Voltage (V)",
        title="Stimulation Block Median Voltage by Channel",
        output_path=output_voltage_png,
    )


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyse stimulation intervals across all sessions."
    )
    parser.add_argument(
        "--preprocess-dir",
        type=pathlib.Path,
        default=_PROJECT_ROOT / "backlogs_local_data" / "TILA_DATA_1_processed",
        help="Directory containing per-session subdirectories.",
    )
    parser.add_argument(
        "--output-dir",
        type=pathlib.Path,
        default=(
            _PROJECT_ROOT / "backlogs_local_data" / "TILA_DATA_2_analysed" / "interval_analysis"
        ),
        help="Directory where CSV and PNG outputs are written.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rerun even if outputs are already up-to-date.",
    )
    return parser


def main() -> None:
    from utils.should_process_task import should_process_task, clean_task_outputs

    parser = _build_arg_parser()
    args = parser.parse_args()

    if not args.preprocess_dir.exists():
        print(f"ERROR: preprocess directory not found: {args.preprocess_dir}", file=sys.stderr)
        sys.exit(1)

    session_dirs = sorted(
        d for d in args.preprocess_dir.iterdir()
        if d.is_dir() and (d / "voltages.csv").exists()
    )
    if not session_dirs:
        print("No session directories with voltages.csv found under", args.preprocess_dir, file=sys.stderr)
        sys.exit(1)

    output_csv = args.output_dir / "interval_summary.csv"
    duration_png = args.output_dir / "interval_duration_comparison.png"
    voltage_png = args.output_dir / "interval_voltage_comparison.png"
    all_outputs = [output_csv, duration_png, voltage_png]

    # Resolve input CSVs for idempotency check
    input_csv_paths = []
    for d in session_dirs:
        csv_path, _source = resolve_session_csv(d)
        if csv_path is not None:
            input_csv_paths.append(csv_path)

    if not should_process_task(
        input_paths=input_csv_paths,
        output_paths=all_outputs,
        force=args.force,
    ):
        print("All outputs up-to-date — skipping.")
        return

    clean_task_outputs(all_outputs)
    run_analyse_stim_intervals(session_dirs, output_csv, duration_png, voltage_png)

    if not output_csv.exists():
        print("No outputs produced.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
