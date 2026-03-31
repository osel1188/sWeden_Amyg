"""Tag stimulation intervals per channel in voltage timeseries.

Task contract:
    run_tag_voltage_intervals(input_items, output_dir, force=False) -> list[Path]

input_items:  list of voltages.csv Paths to tag.  Session folders containing a
              voltages.csv are also accepted.
output_dir:   directory where voltages_tagged.csv and optional PNG files are written.
              Each session's outputs are written to output_dir/<session_name>/.
force:        when True, retag sessions whose outputs already exist.

Returns a list of voltages_tagged.csv Paths produced.

Algorithm (unchanged from 04_05_tag_voltage_intervals.py):
  1. Find all contiguous blocks where voltage > 3V.
  2. Merge adjacent blocks unless separated by a sustained near-zero gap
     (<=0.01V for >=10 min).
  3. Filter merged blocks by minimum duration (>=10 min).
  4. Expand boundaries left and right to the nearest 0V.
  5. Tag the range with interval index (1 or 2).
  6. Compute a 5th consensus ``interval`` column via binary majority vote.
"""

import logging
import pathlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from utils.should_process_task import should_process_task, clean_task_outputs

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TagConfig:
    """Immutable detection parameters passed explicitly to tag functions."""

    channels: list[str] = field(default_factory=lambda: ["A1", "A2", "B1", "B2"])
    threshold_on: float = 3.0
    min_duration_min: float = 10.0
    min_gap_min: float = 10.0
    zero_threshold: float = 0.01


@dataclass(frozen=True)
class ChannelResult:
    """Result of interval detection for a single channel."""

    channel: str
    interval_count: int


@dataclass(frozen=True)
class SessionResult:
    """Aggregated tagging result for a single session."""

    session_name: str
    channel_results: list[ChannelResult]
    consensus_count: int


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


class CommentedCsvReader:
    """Reads CSV files that contain leading ``#`` comment lines."""

    def read(self, csv_path: pathlib.Path) -> tuple[list[str], pd.DataFrame]:
        """Return (comment_lines, dataframe) from a commented CSV."""
        comments: list[str] = []
        with open(csv_path, "r") as f:
            for line in f:
                if line.startswith("#"):
                    comments.append(line)
                else:
                    break

        df = pd.read_csv(csv_path, comment="#", parse_dates=["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        return comments, df


class CommentedCsvWriter:
    """Writes a DataFrame to CSV, prepending preserved comment lines."""

    def write(
        self, df: pd.DataFrame, comments: list[str], out_path: pathlib.Path
    ) -> None:
        """Write *df* to *out_path* with *comments* as a header."""
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            for comment in comments:
                f.write(comment)
            df.to_csv(f, index=False)


# ---------------------------------------------------------------------------
# Core tagger (unchanged from 04_05_tag_voltage_intervals.py)
# ---------------------------------------------------------------------------


class IntervalTagger:
    """Detects and tags stimulation intervals in voltage timeseries data."""

    def __init__(self, cfg: TagConfig) -> None:
        self._cfg = cfg

    def tag(self, df: pd.DataFrame) -> SessionResult:
        """Tag all channel intervals and consensus on *df* (mutates in place)."""
        channel_results: list[ChannelResult] = []
        for ch in self._cfg.channels:
            count = self._tag_channel(df, ch)
            channel_results.append(ChannelResult(channel=ch, interval_count=count))

        consensus_count = self._compute_consensus(df)
        return SessionResult(
            session_name="",
            channel_results=channel_results,
            consensus_count=consensus_count,
        )

    def _tag_channel(self, df: pd.DataFrame, channel: str) -> int:
        col = f"{channel}_interval"
        df[col] = 0

        if channel not in df.columns:
            return 0

        raw_blocks = self._find_raw_on_blocks(df[channel])
        merged = self._merge_blocks_by_gap(raw_blocks, df[channel], df["timestamp"])

        min_seconds = self._cfg.min_duration_min * 60
        blocks = [
            (s, e)
            for s, e in merged
            if (df["timestamp"].iloc[e] - df["timestamp"].iloc[s]).total_seconds()
            >= min_seconds
        ]

        for idx, (s, e) in enumerate(blocks, start=1):
            left, right = self._expand_to_zero(df, channel, s, e)
            df.loc[left:right, col] = idx

        return len(blocks)

    def _find_raw_on_blocks(self, series: pd.Series) -> list[tuple[int, int]]:
        is_on = series > self._cfg.threshold_on
        transitions = is_on.astype(int).diff().fillna(0)
        starts = series.index[transitions == 1].tolist()
        ends = series.index[transitions == -1].tolist()

        if is_on.iloc[0]:
            starts = [0] + starts
        if is_on.iloc[-1]:
            ends = ends + [len(series) - 1]

        return list(zip(starts, ends))

    def _has_sustained_zero_gap(
        self,
        series: pd.Series,
        timestamps: pd.Series,
        gap_start: int,
        gap_end: int,
    ) -> bool:
        if gap_start >= gap_end:
            return False

        zero = self._cfg.zero_threshold
        min_gap_seconds = self._cfg.min_gap_min * 60

        run_start: int | None = None
        for i in range(gap_start, gap_end + 1):
            if series.iloc[i] <= zero:
                if run_start is None:
                    run_start = i
            else:
                if run_start is not None:
                    duration = (
                        timestamps.iloc[i] - timestamps.iloc[run_start]
                    ).total_seconds()
                    if duration >= min_gap_seconds:
                        return True
                    run_start = None

        if run_start is not None:
            end_ts = (
                timestamps.iloc[gap_end]
                if gap_end < len(series)
                else timestamps.iloc[len(series) - 1]
            )
            duration = (end_ts - timestamps.iloc[run_start]).total_seconds()
            if duration >= min_gap_seconds:
                return True

        return False

    def _merge_blocks_by_gap(
        self,
        blocks: list[tuple[int, int]],
        series: pd.Series,
        timestamps: pd.Series,
    ) -> list[tuple[int, int]]:
        if not blocks:
            return []

        merged = [blocks[0]]
        for s_j, e_j in blocks[1:]:
            s_i, e_i = merged[-1]
            if self._has_sustained_zero_gap(series, timestamps, e_i, s_j):
                merged.append((s_j, e_j))
            else:
                merged[-1] = (s_i, e_j)

        return merged

    def _expand_to_zero(
        self, df: pd.DataFrame, channel: str, start: int, end: int
    ) -> tuple[int, int]:
        zero = self._cfg.zero_threshold

        left = start
        while left > 0 and df.loc[left, channel] > zero:
            left -= 1

        right = end
        while right < len(df) - 1 and df.loc[right, channel] > zero:
            right += 1

        return left, right

    def _compute_consensus(self, df: pd.DataFrame) -> int:
        interval_cols = [
            f"{ch}_interval"
            for ch in self._cfg.channels
            if f"{ch}_interval" in df.columns
        ]
        binary = (df[interval_cols].values > 0).astype(int)
        active = (np.median(binary, axis=1) >= 0.5).astype(int)

        consensus = np.zeros(len(df), dtype=int)
        run_idx = 0
        in_run = False
        for i, val in enumerate(active):
            if val and not in_run:
                run_idx += 1
                in_run = True
            elif not val:
                in_run = False
            if in_run:
                consensus[i] = run_idx

        df["interval"] = consensus
        return run_idx


# ---------------------------------------------------------------------------
# Plot saver
# ---------------------------------------------------------------------------


class IntervalPlotSaver:
    """Saves a diagnostic figure showing per-channel intervals and consensus."""

    _INTERVAL_COLOURS: dict[int, str] = {1: "#ff7f0e", 2: "#1f77b4"}
    _INTERVAL_ALPHA = 0.25
    _CONSENSUS_COLOUR = "red"
    _CONSENSUS_OFFSET = 7.0
    _CONSENSUS_LINEWIDTH = 4.0

    def __init__(self, cfg: TagConfig) -> None:
        self._cfg = cfg

    def save(self, df: pd.DataFrame, session_name: str, out_path: pathlib.Path) -> None:
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt

        n_channels = len(self._cfg.channels)
        fig, axes = plt.subplots(
            n_channels, 1, figsize=(14, 2.5 * n_channels), sharex=True,
        )
        if n_channels == 1:
            axes = [axes]

        consensus_spans = self._get_interval_spans(df, "interval")
        y_bar = df[self._cfg.channels].max().max() + self._CONSENSUS_OFFSET

        for ax, ch in zip(axes, self._cfg.channels):
            if ch in df.columns:
                ax.plot(
                    df["timestamp"], df[ch],
                    color="black", drawstyle="steps-post", linewidth=0.6,
                )

            col = f"{ch}_interval"
            if col in df.columns:
                self._shade_intervals(ax, df, col)

            for span_start, span_end in consensus_spans:
                ax.hlines(
                    y_bar, span_start, span_end,
                    colors=self._CONSENSUS_COLOUR,
                    linewidth=self._CONSENSUS_LINEWIDTH,
                    label=None,
                )

            ax.set_ylabel(f"{ch} (V)")
            ax.set_ylim(0, y_bar + self._CONSENSUS_OFFSET * 0.5)

        axes[-1].set_xlabel("Time")
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        fig.suptitle(session_name, fontsize="large", fontweight="bold")
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(out_path, dpi=150)
        plt.close(fig)

    def _get_interval_spans(
        self, df: pd.DataFrame, col: str,
    ) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
        spans: list[tuple[pd.Timestamp, pd.Timestamp]] = []
        if col not in df.columns:
            return spans
        for interval_id in sorted(df[col].unique()):
            if interval_id == 0:
                continue
            mask = df[col] == interval_id
            indices = df.index[mask]
            spans.append((df.loc[indices[0], "timestamp"], df.loc[indices[-1], "timestamp"]))
        return spans

    def _shade_intervals(self, ax, df: pd.DataFrame, col: str) -> None:
        for interval_id in sorted(df[col].unique()):
            if interval_id == 0:
                continue
            colour = self._INTERVAL_COLOURS.get(interval_id, "gray")
            mask = df[col] == interval_id
            transitions = mask.astype(int).diff().fillna(0)
            starts = df.index[transitions == 1].tolist()
            ends = df.index[transitions == -1].tolist()
            if mask.iloc[0]:
                starts = [0] + starts
            if mask.iloc[-1]:
                ends = ends + [len(df) - 1]
            for i, (s, e) in enumerate(zip(starts, ends)):
                ax.axvspan(
                    df.loc[s, "timestamp"], df.loc[e, "timestamp"],
                    alpha=self._INTERVAL_ALPHA, color=colour,
                    label=f"Interval {interval_id}" if i == 0 else None,
                )


# ---------------------------------------------------------------------------
# Formatting helper
# ---------------------------------------------------------------------------


def _format_result(result: SessionResult) -> list[str]:
    lines: list[str] = []
    for cr in result.channel_results:
        status = "OK" if cr.interval_count == 2 else "WARNING"
        detail = (
            "tagged with 2 intervals"
            if cr.interval_count == 2
            else f"has {cr.interval_count} intervals (expected 2)"
        )
        lines.append(f"  {status} [{result.session_name}]: Channel {cr.channel} {detail}")

    status = "OK" if result.consensus_count == 2 else "WARNING"
    detail = (
        "has 2 intervals"
        if result.consensus_count == 2
        else f"has {result.consensus_count} interval(s) (expected 2)"
    )
    lines.append(f"  {status} [{result.session_name}]: consensus `interval` column {detail}")
    return lines


# ---------------------------------------------------------------------------
# Task function
# ---------------------------------------------------------------------------


def run_tag_voltage_intervals(
    input_items: List[Path],
    output_dir: Path,
    force: bool = False,
    save_plot: bool = True,
) -> List[Path]:
    """Tag stimulation intervals in each voltages.csv and write voltages_tagged.csv.

    Args:
        input_items:  voltages.csv Paths or session folder Paths containing a
                      voltages.csv.
        output_dir:   Root output directory.  Each session's outputs go to
                      output_dir/<session_name>/.  When a session folder is
                      passed as input the tagged file is written alongside the
                      source (output_dir/<session_name>/voltages_tagged.csv).
        force:        Retag even if voltages_tagged.csv already exists.
        save_plot:    When True, also save a diagnostic PNG alongside the CSV.

    Returns:
        List of voltages_tagged.csv Paths produced.
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

    cfg = TagConfig()
    tagger = IntervalTagger(cfg)
    reader = CommentedCsvReader()
    writer = CommentedCsvWriter()
    plotter = IntervalPlotSaver(cfg) if save_plot else None

    results: List[Path] = []

    for session_name, csv_path in csv_entries:
        session_out_dir = output_dir / session_name
        session_out_dir.mkdir(parents=True, exist_ok=True)

        tagged_csv = session_out_dir / "voltages_tagged.csv"
        extra_outputs = [session_out_dir / "voltages_tagged.png"] if save_plot else []

        if not should_process_task(
            input_paths=[csv_path],
            output_paths=[tagged_csv] + extra_outputs,
            force=force,
        ):
            results.append(tagged_csv)
            continue

        clean_task_outputs([tagged_csv] + extra_outputs)

        comments, df = reader.read(csv_path)
        result = tagger.tag(df)
        result = SessionResult(
            session_name=session_name,
            channel_results=result.channel_results,
            consensus_count=result.consensus_count,
        )

        for line in _format_result(result):
            log.info(line)

        writer.write(df, comments, tagged_csv)
        log.info("Saved: %s", tagged_csv)

        if plotter is not None:
            plot_path = session_out_dir / "voltages_tagged.png"
            plotter.save(df, session_name, plot_path)
            log.info("Saved plot: %s", plot_path)

        results.append(tagged_csv)

    return results


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

_DEFAULT_PREPROCESS_DIR = Path("backlogs_local_data/TILA_DATA_1_processed")


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Tag stimulation intervals in TILA voltage timeseries CSVs."
    )
    parser.add_argument(
        "input_dir", nargs="?", type=Path, default=_DEFAULT_PREPROCESS_DIR,
        help=f"Directory containing session folders with voltages.csv files (default: {_DEFAULT_PREPROCESS_DIR})",
    )
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=None,
        help="Output directory (default: same as input_dir, tagged files written in-place).",
    )
    parser.add_argument(
        "--no-plot", action="store_true",
        help="Skip saving the diagnostic PNG.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Retag even if voltages_tagged.csv already exists.",
    )
    args = parser.parse_args()

    if not args.input_dir.exists():
        raise SystemExit(f"Error: input directory not found: {args.input_dir}")

    output_dir = args.output_dir or args.input_dir
    input_items = sorted(args.input_dir.glob("*/voltages.csv"))

    if not input_items:
        raise SystemExit(f"Error: no voltages.csv files found in {args.input_dir}")

    results = run_tag_voltage_intervals(
        input_items=input_items,
        output_dir=output_dir,
        force=args.force,
        save_plot=not args.no_plot,
    )
    print(f"Done. {len(results)} session(s) tagged. Tagged CSVs in {output_dir}/")


if __name__ == "__main__":
    main()
