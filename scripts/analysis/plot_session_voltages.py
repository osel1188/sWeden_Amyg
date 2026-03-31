"""Workflow task: batch-generate voltage timeline plots for all session CSVs.

Task contract
-------------
``run_plot_session_voltages(input_items, output_dir, force)`` follows the DAG
task contract: receives a list of ``voltages_corrected.csv`` (or any voltage
CSV) paths, writes one PNG per session to *output_dir*, and returns the list
of PNG paths produced.

Standalone use
--------------
Run directly to regenerate all plots under the default data directories::

    python scripts/analysis/plot_session_voltages.py
    python scripts/analysis/plot_session_voltages.py \\
        --input-dir /path/to/processed --output-dir /path/to/analysed
"""

import argparse
import logging
import pathlib
import sys
from dataclasses import dataclass, field
from typing import List

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from utils.should_process_task import should_process_task, clean_task_outputs

_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlotConfig:
    """Immutable plotting parameters passed explicitly to plot functions."""

    channels: list[str] = field(default_factory=lambda: ["A1", "A2", "B1", "B2"])
    channel_colours: dict[str, str] = field(
        default_factory=lambda: {
            "A1": "tab:blue",
            "A2": "tab:orange",
            "B1": "tab:green",
            "B2": "tab:red",
        }
    )
    block_colours: dict[int, str] = field(
        default_factory=lambda: {1: "#1f77b4", 2: "#ff7f0e"}
    )
    interval_alpha: float = 0.10
    split_channels: bool = False
    y_min: float = 0
    y_max: float = 8


# ---------------------------------------------------------------------------
# Plotting helpers (unchanged from 05_plot_session_voltages.py)
# ---------------------------------------------------------------------------


def _shade_consensus_intervals(
    ax, df: pd.DataFrame, cfg: PlotConfig
) -> None:
    """Shade background spans using the consensus ``interval`` column."""
    if "interval" not in df.columns:
        return

    for interval_id in (1, 2):
        colour = cfg.block_colours[interval_id]
        mask = df["interval"] == interval_id
        if not mask.any():
            continue
        transitions = mask.astype(int).diff().fillna(0)
        starts = df.index[transitions == 1].tolist()
        ends = df.index[transitions == -1].tolist()
        if mask.iloc[0]:
            starts = [0] + starts
        if mask.iloc[-1]:
            ends = ends + [len(df) - 1]
        for i, (s, e) in enumerate(zip(starts, ends)):
            ax.axvspan(
                df.loc[s, "timestamp"],
                df.loc[e, "timestamp"],
                alpha=cfg.interval_alpha,
                color=colour,
                label=f"Block {interval_id}" if i == 0 else None,
            )


def _setup_axes(
    ax, session_name: str, cfg: PlotConfig, channel_label: str | None = None
) -> None:
    """Apply common formatting to an axes."""
    ax.set_ylim(cfg.y_min, cfg.y_max)
    ax.set_ylabel("Voltage (V)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    title = session_name if channel_label is None else f"{session_name} — {channel_label}"
    ax.set_title(title, fontsize="medium")
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), fontsize="small", ncol=2)


def _plot_combined(
    df: pd.DataFrame, session_name: str, cfg: PlotConfig
) -> plt.Figure:
    """All channels on a single axes."""
    fig, ax = plt.subplots(figsize=(12, 5))
    _shade_consensus_intervals(ax, df, cfg)
    for ch in cfg.channels:
        if ch in df.columns:
            ax.plot(
                df["timestamp"], df[ch], label=ch,
                color=cfg.channel_colours[ch], drawstyle="steps-post",
            )
    ax.set_xlabel("Time")
    _setup_axes(ax, session_name, cfg)
    fig.autofmt_xdate()
    return fig


def _plot_split(
    df: pd.DataFrame, session_name: str, cfg: PlotConfig
) -> plt.Figure:
    """Each channel on its own subplot in a 2x2 grid."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 8), sharex=True)
    for ax, ch in zip(axes.flat, cfg.channels):
        _shade_consensus_intervals(ax, df, cfg)
        if ch in df.columns:
            ax.plot(
                df["timestamp"], df[ch], label=ch,
                color=cfg.channel_colours[ch], drawstyle="steps-post",
            )
        _setup_axes(ax, session_name, cfg, channel_label=ch)
    for ax in axes[1]:
        ax.set_xlabel("Time")
    fig.suptitle(session_name, fontsize="large", fontweight="bold")
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def plot_session(
    csv_path: pathlib.Path, output_dir: pathlib.Path, cfg: PlotConfig
) -> pathlib.Path:
    """Read a single session CSV and save a voltage timeline PNG.

    Returns the path to the saved PNG.
    """
    session_name = csv_path.parent.name
    df = pd.read_csv(csv_path, comment="#", parse_dates=["timestamp"])

    fig = _plot_split(df, session_name, cfg) if cfg.split_channels else _plot_combined(df, session_name, cfg)

    out_path = output_dir / f"{session_name}_voltages.png"
    fig.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    logging.info(f"  saved {out_path.name}")
    return out_path


# ---------------------------------------------------------------------------
# Task contract
# ---------------------------------------------------------------------------


def run_plot_session_voltages(
    input_items: List[pathlib.Path],
    output_dir: pathlib.Path,
    force: bool = False,
) -> List[pathlib.Path]:
    """Generate voltage timeline PNG for each session CSV in *input_items*.

    Parameters
    ----------
    input_items:
        List of voltage CSV paths (e.g. ``voltages_corrected.csv``).  Each
        CSV is expected to live inside a session directory; the session
        directory name is used as the plot title and output filename stem.
    output_dir:
        Directory where PNG files are written.
    force:
        When ``True``, regenerate even if the PNG is already up-to-date.

    Returns
    -------
    list of Path
        Paths to the PNG files produced (or already present when skipped).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    cfg = PlotConfig()
    results: List[pathlib.Path] = []

    for csv_path in input_items:
        session_name = csv_path.parent.name
        out_path = output_dir / f"{session_name}_voltages.png"

        if not should_process_task(
            input_paths=[csv_path],
            output_paths=[out_path],
            force=force,
        ):
            results.append(out_path)
            continue

        clean_task_outputs(out_path)

        try:
            produced = plot_session(csv_path, output_dir, cfg)
            results.append(produced)
        except Exception as exc:
            logging.error(f"[plot_session_voltages] Failed for {csv_path}: {exc}")

    return results


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch-generate voltage timeline plots for all session CSVs."
    )
    parser.add_argument(
        "--input-dir",
        type=pathlib.Path,
        default=_PROJECT_ROOT / "backlogs_local_data" / "TILA_DATA_1_processed",
        help="Directory containing per-session subdirectories with voltage CSVs.",
    )
    parser.add_argument(
        "--output-dir",
        type=pathlib.Path,
        default=_PROJECT_ROOT / "backlogs_local_data" / "TILA_DATA_2_analysed" / "voltage_tracker",
        help="Directory where PNG files are written.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate plots even if they are already up-to-date.",
    )
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    if not args.input_dir.exists():
        print(f"ERROR: preprocess directory not found: {args.input_dir}", file=sys.stderr)
        sys.exit(1)

    csv_files = sorted(args.input_dir.glob("*/voltages_corrected.csv"))
    if not csv_files:
        print("No voltages_corrected.csv files found under", args.input_dir, file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(csv_files)} corrected session(s). Generating plots...")
    produced = run_plot_session_voltages(csv_files, args.output_dir, force=args.force)
    print(f"\nDone. {len(produced)} PNG(s) in {args.output_dir}")


if __name__ == "__main__":
    main()
