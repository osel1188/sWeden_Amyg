"""Interactive GUI for manual correction of consensus interval boundaries.

Reads the ``voltages_tagged.csv`` files produced by tag_voltage_intervals.py
(which contain a consensus ``interval`` column), then for each session displays
a matplotlib plot with draggable vertical lines marking Block 1 / Block 2 start
and end.  The user can drag the markers then press *Continue* or ENTER to
confirm.  Every session must be reviewed — there is no Skip.  Each session is
saved as ``voltages_corrected.csv`` alongside the input file, with the
``interval`` column rewritten to reflect the confirmed (or unmodified)
boundaries.  Per-channel ``{ch}_interval`` columns are preserved unchanged.

Standalone helper — not part of the automated DAG.  Run directly:
    python scripts/preprocessing/correct_intervals_gui.py
"""

import pathlib
import sys

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch
from matplotlib.widgets import Button

CHANNELS = ["A1", "A2", "B1", "B2"]

PREPROCESS_DIR = (
    pathlib.Path(__file__).resolve().parent.parent.parent
    / "backlogs_local_data"
    / "TILA_DATA_1_processed"
)

CHANNEL_COLOURS = {
    "A1": "tab:blue",
    "A2": "tab:orange",
    "B1": "tab:green",
    "B2": "tab:red",
}
BLOCK_COLOURS = {"Block 1": "#1f77b4", "Block 2": "#ff7f0e"}


# ---------------------------------------------------------------------------
# Draggable vertical line
# ---------------------------------------------------------------------------


class DraggableVLine:
    """A vertical line on a matplotlib axes that can be dragged horizontally.

    On mouse release the line snaps to the nearest timestamp in *ts_num*
    (a sorted numpy array of matplotlib float ordinals).
    """

    def __init__(self, ax, x_date, color, label, ts_num: np.ndarray):
        self.ax = ax
        self.canvas = ax.figure.canvas
        self._ts_num = ts_num
        self.line = ax.axvline(
            mdates.date2num(x_date), color=color, linestyle="--", linewidth=2, label=label, picker=5
        )
        self._pressed = False
        self._cid_pick = self.canvas.mpl_connect("pick_event", self._on_pick)
        self._cid_motion = self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self._cid_release = self.canvas.mpl_connect(
            "button_release_event", self._on_release
        )

    def _snap(self, x_num: float) -> float:
        """Return the nearest value in *_ts_num* to *x_num*."""
        idx = np.searchsorted(self._ts_num, x_num)
        idx = np.clip(idx, 0, len(self._ts_num) - 1)
        if idx > 0 and abs(self._ts_num[idx - 1] - x_num) < abs(self._ts_num[idx] - x_num):
            idx -= 1
        return self._ts_num[idx]

    # -- event handlers -----------------------------------------------------

    def _on_pick(self, event):
        if event.artist is not self.line:
            return
        self._pressed = True

    def _on_motion(self, event):
        if not self._pressed or event.inaxes is not self.ax:
            return
        self.line.set_xdata([event.xdata, event.xdata])
        self.canvas.draw_idle()

    def _on_release(self, event):
        if self._pressed:
            x_num = self.line.get_xdata()[0]
            snapped = self._snap(x_num)
            self.line.set_xdata([snapped, snapped])
            self.canvas.draw_idle()
        self._pressed = False

    # -- public API ---------------------------------------------------------

    @property
    def value(self) -> pd.Timestamp:
        """Current position as a pandas Timestamp."""
        x_num = self.line.get_xdata()[0]
        return pd.Timestamp(mdates.num2date(x_num)).tz_localize(None)

    def disconnect(self):
        self.canvas.mpl_disconnect(self._cid_pick)
        self.canvas.mpl_disconnect(self._cid_motion)
        self.canvas.mpl_disconnect(self._cid_release)


# ---------------------------------------------------------------------------
# Correction GUI for one session
# ---------------------------------------------------------------------------


def launch_correction_gui(
    session_name: str,
    df: pd.DataFrame,
    intervals: list[tuple[pd.Timestamp, pd.Timestamp, str]],
) -> list[tuple[pd.Timestamp, pd.Timestamp, str]]:
    """Show interactive plot for *session_name* and return corrected intervals.

    The user must press Continue (or ENTER) to proceed — there is no Skip.
    """
    result = {"intervals": intervals, "done": False}

    fig, ax = plt.subplots(figsize=(14, 6))
    fig.subplots_adjust(bottom=0.2)

    channel_handles = []
    for ch in CHANNELS:
        if ch in df.columns:
            (h,) = ax.plot(
                df["timestamp"],
                df[ch],
                label=ch,
                color=CHANNEL_COLOURS[ch],
                drawstyle="steps-post",
                alpha=0.8,
            )
            channel_handles.append(h)

    ax.set_ylim(0, 8)
    ax.set_ylabel("Voltage (V)")
    ax.set_xlabel("Time")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax.set_title(f"{session_name}  —  drag lines to adjust, then press Continue or ENTER")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    fig.autofmt_xdate()

    ts_num = np.sort(mdates.date2num(df["timestamp"].values))

    n = len(df)
    ts = df["timestamp"]
    _default_positions = {
        "Block 1": (ts.iloc[0],      ts.iloc[n // 4]),
        "Block 2": (ts.iloc[n // 2], ts.iloc[-1]),
    }

    present = {lbl for _, _, lbl in intervals}
    for lbl, (ds, de) in _default_positions.items():
        if lbl not in present:
            intervals.append((ds, de, lbl))

    draggables: list[tuple[DraggableVLine, DraggableVLine, str, object]] = []
    for start, end, label in intervals:
        colour = BLOCK_COLOURS.get(label, "gray")
        vl_start = DraggableVLine(ax, start, colour, f"{label} start", ts_num)
        vl_end = DraggableVLine(ax, end, colour, f"{label} end", ts_num)
        span = ax.axvspan(start, end, alpha=0.08, color=colour)
        draggables.append((vl_start, vl_end, label, span))

    block_patches = [
        Patch(facecolor=colour, alpha=0.6, label=label)
        for label, colour in BLOCK_COLOURS.items()
    ]
    ax.legend(handles=channel_handles + block_patches, fontsize="small", ncol=6, loc="upper right")

    ax_b1 = fig.add_axes([0.18, 0.04, 0.13, 0.05])
    ax_b2 = fig.add_axes([0.33, 0.04, 0.13, 0.05])
    ax_continue = fig.add_axes([0.50, 0.04, 0.12, 0.05])
    btn_b1 = Button(ax_b1, "Reset Block 1", color=BLOCK_COLOURS["Block 1"], hovercolor=BLOCK_COLOURS["Block 1"])
    btn_b2 = Button(ax_b2, "Reset Block 2", color=BLOCK_COLOURS["Block 2"], hovercolor=BLOCK_COLOURS["Block 2"])
    btn_continue = Button(ax_continue, "Continue")

    btn_b1.label.set_color("white")
    btn_b2.label.set_color("white")

    def _reset_block(block_label: str) -> None:
        colour = BLOCK_COLOURS.get(block_label, "gray")
        default_start, default_end = _default_positions[block_label]
        for i, (vl_s, vl_e, lbl, span) in enumerate(draggables):
            if lbl == block_label:
                vl_s.line.set_xdata([mdates.date2num(default_start)] * 2)
                vl_e.line.set_xdata([mdates.date2num(default_end)] * 2)
                span.remove()
                new_span = ax.axvspan(default_start, default_end, alpha=0.08, color=colour)
                draggables[i] = (vl_s, vl_e, lbl, new_span)
                break
        else:
            vl_start = DraggableVLine(ax, default_start, colour, f"{block_label} start", ts_num)
            vl_end   = DraggableVLine(ax, default_end,   colour, f"{block_label} end",   ts_num)
            new_span = ax.axvspan(default_start, default_end, alpha=0.08, color=colour)
            draggables.append((vl_start, vl_end, block_label, new_span))
        fig.canvas.draw()

    def _on_b1(event=None):
        _reset_block("Block 1")

    def _on_b2(event=None):
        _reset_block("Block 2")

    def _on_continue(event=None):
        corrected = []
        for vl_start, vl_end, label, _span in draggables:
            corrected.append((vl_start.value, vl_end.value, label))
        result["intervals"] = corrected
        result["done"] = True
        plt.close(fig)

    btn_b1.on_clicked(_on_b1)
    btn_b2.on_clicked(_on_b2)
    btn_continue.on_clicked(_on_continue)

    def _on_key(event):
        if event.key == "enter":
            _on_continue()

    fig.canvas.mpl_connect("key_press_event", _on_key)

    plt.show()

    for vl_start, vl_end, _label, _span in draggables:
        vl_start.disconnect()
        vl_end.disconnect()

    return result["intervals"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_boundaries(
    df: pd.DataFrame,
) -> list[tuple[pd.Timestamp, pd.Timestamp, str]]:
    """Return (start_ts, end_ts, label) for Block 1 and Block 2."""
    intervals = []
    for block_num in (1, 2):
        mask = df["interval"] == block_num
        if mask.any():
            start = df.loc[mask, "timestamp"].iloc[0]
            end   = df.loc[mask, "timestamp"].iloc[-1]
            if start != end:
                intervals.append((start, end, f"Block {block_num}"))
    return intervals


def apply_corrections(
    df: pd.DataFrame,
    corrected_intervals: list[tuple[pd.Timestamp, pd.Timestamp, str]],
) -> pd.DataFrame:
    """Return a copy of *df* with the `interval` column rewritten from *corrected_intervals*."""
    df = df.copy()
    df["interval"] = 0
    for start, end, label in corrected_intervals:
        try:
            interval_idx = int(label.split()[-1])
        except (ValueError, IndexError):
            interval_idx = 1
        mask = (df["timestamp"] >= start) & (df["timestamp"] <= end)
        df.loc[mask, "interval"] = interval_idx
    return df


def write_csv_with_comments(
    df: pd.DataFrame, out_path: pathlib.Path, comments: list[str]
) -> None:
    """Write *df* to *out_path*, prepending any header comment lines."""
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        for comment in comments:
            f.write(comment)
        df.to_csv(f, index=False)


# ---------------------------------------------------------------------------
# Main batch loop
# ---------------------------------------------------------------------------


def main() -> None:
    if not PREPROCESS_DIR.exists():
        print(
            f"ERROR: preprocess directory not found: {PREPROCESS_DIR}",
            file=sys.stderr,
        )
        sys.exit(1)

    tagged_files = sorted(PREPROCESS_DIR.glob("*/voltages_tagged.csv"))
    if not tagged_files:
        print(
            f"No voltages_tagged.csv files found under {PREPROCESS_DIR}\n"
            "Run tag_voltage_intervals.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Found {len(tagged_files)} session(s) to review. Close the window or press Ctrl+C to quit early.\n")

    for csv_path in tagged_files:
        session_name = csv_path.parent.name

        comments = []
        with open(csv_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("#"):
                    comments.append(line)
                else:
                    break

        df = pd.read_csv(csv_path, comment="#", parse_dates=["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        if "interval" not in df.columns:
            print(f"  SKIP [{session_name}]: no `interval` column — re-run tag_voltage_intervals.py first")
            continue

        intervals = extract_boundaries(df)

        if not intervals:
            print(f"  SKIP [{session_name}]: 0 intervals detected in `interval` column")
            continue

        print(f"  [{session_name}]: {len(intervals)} interval(s) detected")

        try:
            corrected_intervals = launch_correction_gui(session_name, df, intervals)
        except KeyboardInterrupt:
            print("\nInterrupted — stopping.")
            break

        corrected_df = apply_corrections(df, corrected_intervals)
        out_path = csv_path.parent / "voltages_corrected.csv"
        write_csv_with_comments(corrected_df, out_path, comments)
        print(f"  SAVED [{session_name}]: {out_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
