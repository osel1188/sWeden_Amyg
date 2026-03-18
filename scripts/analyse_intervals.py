"""Analyse stimulation intervals across all sessions.

Detects the two main stimulation blocks per session using a union approach
across all 4 channels, extracts duration and time-weighted median voltage
per channel per interval, and generates cross-session comparison figures.
"""

import pathlib
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PREPROCESS_DIR = (
    pathlib.Path(__file__).parent.parent / "backlogs_local_data" / "TILA_DATA_1_processed"
)
OUTPUT_DIR = (
    pathlib.Path(__file__).parent.parent
    / "backlogs_local_data"
    / "TILA_DATA_2_analysed"
    / "interval_analysis"
)

CHANNELS = ["A1", "A2", "B1", "B2"]
THRESHOLD = 0.5  # V — voltage above which a channel is considered active
MIN_BLOCK_DURATION = 5  # minutes — minimum duration to count as a block
MERGE_GAP = 2  # minutes — gaps shorter than this are merged into the adjacent block


# ---------------------------------------------------------------------------
# Phase 1: Core Detection and Extraction
# ---------------------------------------------------------------------------


def load_session(csv_path: pathlib.Path) -> pd.DataFrame:
    """Read voltages CSV, parse timestamps, return DataFrame sorted by time."""
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def detect_active_intervals(
    df: pd.DataFrame, threshold: float = THRESHOLD
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return (start, end) tuples where any channel is above threshold.

    Merges gaps < MERGE_GAP minutes and filters out intervals shorter than
    MIN_BLOCK_DURATION minutes.
    """
    any_active = (
        (df["A1"] > threshold)
        | (df["A2"] > threshold)
        | (df["B1"] > threshold)
        | (df["B2"] > threshold)
    )

    # Detect rising (+1) and falling (-1) edges
    transitions = any_active.astype(int).diff().fillna(0)
    starts = df.loc[transitions == 1, "timestamp"].tolist()
    ends = df.loc[transitions == -1, "timestamp"].tolist()

    # Session starts already active
    if any_active.iloc[0]:
        starts = [df["timestamp"].iloc[0]] + starts

    # Session ends still active
    if any_active.iloc[-1]:
        ends = ends + [df["timestamp"].iloc[-1]]

    if not starts or not ends:
        return []

    intervals = list(zip(starts, ends))

    # Merge intervals whose gap is below MERGE_GAP
    merge_gap_td = pd.Timedelta(minutes=MERGE_GAP)
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= merge_gap_td:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    # Drop intervals shorter than MIN_BLOCK_DURATION
    min_dur_td = pd.Timedelta(minutes=MIN_BLOCK_DURATION)
    merged = [(s, e) for s, e in merged if e - s >= min_dur_td]

    return merged


def classify_intervals(
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> tuple[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]]:
    """Classify intervals as Block 1 (shorter) and Block 2 (longer).

    Returns (status, [(start, end, block_label), ...]).

    Status values:
      'ok'           — exactly 2 blocks found
      'single_block' — only 1 block found; labelled Block 1
      'extra_blocks' — >2 blocks found; two longest chosen
      'skipped'      — 0 blocks found
    """
    if not intervals:
        return "skipped", []

    if len(intervals) == 1:
        start, end = intervals[0]
        return "single_block", [(start, end, "Block 1")]

    if len(intervals) == 2:
        # Sort ascending by duration: shorter → Block 1, longer → Block 2
        durations = sorted((e - s, s, e) for s, e in intervals)
        _, s1, e1 = durations[0]
        _, s2, e2 = durations[1]
        return "ok", [(s1, e1, "Block 1"), (s2, e2, "Block 2")]

    # More than 2 blocks — take the two longest
    durations = sorted(((e - s, s, e) for s, e in intervals), reverse=True)
    top2 = sorted(durations[:2])  # ascending so shorter → Block 1
    _, s1, e1 = top2[0]
    _, s2, e2 = top2[1]
    return "extra_blocks", [(s1, e1, "Block 1"), (s2, e2, "Block 2")]


def extract_channel_stats(
    df: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    channels: list[str] = CHANNELS,
) -> dict[str, dict]:
    """Extract per-channel stats within [start, end].

    Resamples data to a 1-second grid with forward-fill so that
    time-weighted median correctly accounts for the event-based format.

    Returns dict: channel -> {duration_min, median_voltage}.
    """
    mask = (df["timestamp"] >= start) & (df["timestamp"] <= end)
    segment = df.loc[mask, ["timestamp"] + channels].copy()

    if segment.empty:
        return {ch: {"duration_min": 0.0, "median_voltage": 0.0} for ch in channels}

    segment = segment.set_index("timestamp")[channels]
    # Drop duplicate timestamps (keep last reading per timestamp)
    segment = segment[~segment.index.duplicated(keep="last")]

    # Build 1-second grid and forward-fill
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


def analyse_all_sessions(preprocess_dir: pathlib.Path) -> pd.DataFrame:
    """Iterate all session voltages.csv files and extract interval stats."""
    csv_files = sorted(preprocess_dir.glob("*/voltages.csv"))
    if not csv_files:
        print(f"No voltages.csv files found under {preprocess_dir}", file=sys.stderr)
        return pd.DataFrame()

    rows = []
    counts = {"ok": 0, "merged": 0, "single_block": 0, "extra_blocks": 0, "skipped": 0}

    for csv_path in csv_files:
        session_name = csv_path.parent.name
        df = load_session(csv_path)
        intervals = detect_active_intervals(df)
        status, classified = classify_intervals(intervals)

        if status == "skipped":
            print(f"  WARNING [{session_name}]: no blocks detected — skipping")
            counts["skipped"] += 1
            continue
        if status == "single_block":
            print(f"  WARNING [{session_name}]: only 1 block detected")
            counts["single_block"] += 1
        elif status == "extra_blocks":
            print(
                f"  WARNING [{session_name}]: {len(intervals)} blocks detected"
                " — using 2 longest"
            )
            counts["extra_blocks"] += 1
        else:
            counts[status] += 1

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
        f"{counts['ok']} ok | {counts['merged']} merged | "
        f"{counts['single_block']} single_block | "
        f"{counts['extra_blocks']} extra_blocks | "
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

            # Jittered strip points
            jitter = np.random.uniform(-0.15, 0.15, size=len(ch_data))
            ax.scatter(x + jitter, ch_data.values, s=20, alpha=0.6, color=f"C{x}", zorder=3)

            mean_val = ch_data.mean()
            std_val = ch_data.std()

            # Mean line
            ax.plot([x - 0.3, x + 0.3], [mean_val, mean_val], color="black", lw=2, zorder=4)

            # ±1 STD shaded band
            ax.fill_between(
                [x - 0.3, x + 0.3],
                mean_val - std_val,
                mean_val + std_val,
                alpha=0.2,
                color="black",
                zorder=2,
            )

            # mean ± std annotation
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
    print(f"  saved {output_path.name}")


def main() -> None:
    if not PREPROCESS_DIR.exists():
        print(f"ERROR: preprocess directory not found: {PREPROCESS_DIR}", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Analysing sessions under {PREPROCESS_DIR}...")
    summary_df = analyse_all_sessions(PREPROCESS_DIR)

    if summary_df.empty:
        print("No data extracted — nothing to save.", file=sys.stderr)
        sys.exit(1)

    csv_out = OUTPUT_DIR / "interval_summary.csv"
    summary_df.to_csv(csv_out, index=False)
    print(f"\nSaved {len(summary_df)} rows to {csv_out.name}")

    print("\nGenerating figures...")
    np.random.seed(42)

    plot_strip_comparison(
        summary_df,
        metric="duration_min",
        ylabel="Duration (min)",
        title="Stimulation Block Duration by Channel",
        output_path=OUTPUT_DIR / "interval_duration_comparison.png",
    )
    plot_strip_comparison(
        summary_df,
        metric="median_voltage",
        ylabel="Median Voltage (V)",
        title="Stimulation Block Median Voltage by Channel",
        output_path=OUTPUT_DIR / "interval_voltage_comparison.png",
    )

    print(f"\nDone. Output in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
