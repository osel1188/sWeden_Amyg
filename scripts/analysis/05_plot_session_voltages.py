"""Batch-generate voltage timeline plots for all session CSVs.

Reads voltages.csv from each session folder under
backlogs_local_data/TILA_DATA_preprocess/ and saves one PNG per session
to backlogs_local_data/TILA_DATA_analysis/.
"""

import pathlib
import sys

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

PREPROCESS_DIR = pathlib.Path(__file__).parent.parent / "backlogs_local_data" / "TILA_DATA_1_processed"
OUTPUT_DIR = pathlib.Path(__file__).parent.parent / "backlogs_local_data" / "TILA_DATA_2_analysed" / "voltage_tracker"

CHANNELS = ["A1", "A2", "B1", "B2"]
Y_MIN, Y_MAX = 0, 8


def plot_session(csv_path: pathlib.Path, output_dir: pathlib.Path) -> None:
    session_name = csv_path.parent.name
    df = pd.read_csv(csv_path, comment="#", parse_dates=["timestamp"])

    fig, ax = plt.subplots(figsize=(12, 5))
    for channel in CHANNELS:
        if channel in df.columns:
            ax.plot(df["timestamp"], df[channel], label=channel, drawstyle="steps-post")

    ax.set_ylim(Y_MIN, Y_MAX)
    ax.set_xlabel("Time")
    ax.set_ylabel("Voltage (V)")
    ax.set_title(session_name)
    ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    fig.autofmt_xdate()

    out_path = output_dir / f"{session_name}_voltages.png"
    fig.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {out_path.name}")


def main() -> None:
    if not PREPROCESS_DIR.exists():
        print(f"ERROR: preprocess directory not found: {PREPROCESS_DIR}", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(PREPROCESS_DIR.glob("*/voltages.csv"))
    if not csv_files:
        print(f"No voltages.csv files found under {PREPROCESS_DIR}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(csv_files)} session(s). Generating plots...")
    for csv_path in csv_files:
        plot_session(csv_path, OUTPUT_DIR)

    print(f"\nDone. {len(csv_files)} PNG(s) saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
