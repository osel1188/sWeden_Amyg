"""Workflow task: sex-stratified voltage analysis across all TILA sessions.

Task contract
-------------
``run_sex_based_voltage_analysis(input_items, output_dir, force)`` follows the
DAG task contract.  *input_items* should be the output paths from the
``analyse_stim_intervals`` task (i.e. the ``interval_summary.csv`` path) plus
any additional data files needed (Excel participant list, condition report).
The function writes 7 CSVs and 6 PNGs to *output_dir* and returns all 13 paths.

Standalone use
--------------
    python scripts/analysis/sex_based_voltage_analysis.py
    python scripts/analysis/sex_based_voltage_analysis.py \\
        --output-dir /path/to/sex_analysis

Inputs (resolved from default locations when not passed via *input_items*)
--------------------------------------------------------------------------
- backlogs_local_data/Excel_for_stimulators.xlsx
- backlogs_local_data/condition_validation_report.csv
- backlogs_local_data/TILA_DATA_2_analysed/interval_analysis/interval_summary.csv
- backlogs_local_data/TILA_DATA_1_processed/*/voltages.csv

Outputs
-------
CSVs (7): session_metadata, interval_summary_with_sex, participant_descriptive_stats,
          channel_asymmetry, voltage_change_counts, sliding_window_sensitivity,
          statistical_tests_summary
PNGs (6): descriptive_boxplots, change_counts, stability_comparison,
          asymmetry_comparison, time_to_stable, condition_sex_interaction
"""

import argparse
import logging
import math
import pathlib
import re
import sys
import warnings
from typing import List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Import block-detection helpers from the workflow task module directly
# (replaces the importlib/sys.path gymnastics used in 07_)
from scripts.analysis.analyse_stim_intervals import (
    load_session,
    detect_active_intervals,
    classify_intervals,
)

from utils.should_process_task import should_process_task, clean_task_outputs

# Optional scipy import
try:
    from scipy import stats as _scipy_stats
    _SCIPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _scipy_stats = None  # type: ignore[assignment]
    _SCIPY_AVAILABLE = False
    warnings.warn(
        "scipy is not installed — Mann-Whitney U tests will be skipped and "
        "u_stat / p_value will be NaN in the statistical summary.",
        ImportWarning,
        stacklevel=1,
    )

_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
_BACKLOGS = _PROJECT_ROOT / "backlogs_local_data"

_DEFAULT_EXCEL_PATH = _BACKLOGS / "Excel_for_stimulators.xlsx"
_DEFAULT_CONDITION_REPORT_PATH = _BACKLOGS / "condition_validation_report.csv"
_DEFAULT_INTERVAL_SUMMARY_PATH = (
    _BACKLOGS / "TILA_DATA_2_analysed" / "interval_analysis" / "interval_summary.csv"
)
_DEFAULT_PREPROCESS_DIR = _BACKLOGS / "TILA_DATA_1_processed"

_PARTICIPANT_ID_PATTERN = re.compile(r"_(T?\d+)$")
SENSITIVITY_WINDOWS = [1, 1.5, 2, 3, 5]
THRESHOLD = 0.5
CHANNELS = ["A1", "A2", "B1", "B2"]

# Output file names (relative to output_dir)
_CSV_NAMES = [
    "session_metadata.csv",
    "interval_summary_with_sex.csv",
    "participant_descriptive_stats.csv",
    "channel_asymmetry.csv",
    "voltage_change_counts.csv",
    "sliding_window_sensitivity.csv",
    "statistical_tests_summary.csv",
]
_PNG_NAMES = [
    "descriptive_boxplots.png",
    "change_counts.png",
    "stability_comparison.png",
    "asymmetry_comparison.png",
    "time_to_stable.png",
    "condition_sex_interaction.png",
]


# ---------------------------------------------------------------------------
# Phase 1 helpers: data loading
# (logic unchanged from 07_sex_based_voltage_analysis.py)
# ---------------------------------------------------------------------------


def load_sex_mapping(excel_path: pathlib.Path) -> dict[str, str]:
    """Read participant sex mapping from Excel file."""
    if not excel_path.exists():
        print(f"ERROR: Excel file not found: {excel_path}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_excel(excel_path, usecols=["ID", "sex"])

    nan_id_mask = df["ID"].isna()
    if nan_id_mask.any():
        n = nan_id_mask.sum()
        warnings.warn(
            f"load_sex_mapping: {n} row(s) with NaN ID in {excel_path.name} — excluded.",
            stacklevel=2,
        )
    df = df[~nan_id_mask].copy()

    df["ID"] = df["ID"].astype(str).str.strip()
    df["sex"] = df["sex"].astype(str).str.strip().str.lower()
    df["sex"] = df["sex"].replace("nan", pd.NA)

    return dict(zip(df["ID"], df["sex"]))


def load_session_metadata(
    condition_report_path: pathlib.Path,
    sex_mapping: dict[str, str],
) -> pd.DataFrame:
    """Load session metadata and join with participant sex."""
    if not condition_report_path.exists():
        print(f"ERROR: condition validation report not found: {condition_report_path}", file=sys.stderr)
        sys.exit(1)

    report_df = pd.read_csv(condition_report_path)

    session_col = None
    for candidate in ("session", "session_name", "Session", "Session Name"):
        if candidate in report_df.columns:
            session_col = candidate
            break
    if session_col is None:
        session_col = report_df.columns[0]

    condition_col = None
    for candidate in ("condition", "Condition", "validated_condition"):
        if candidate in report_df.columns:
            condition_col = candidate
            break
    if condition_col is None:
        condition_col = report_df.columns[1] if len(report_df.columns) > 1 else None

    rows = []
    for _, row in report_df.iterrows():
        session_name = str(row[session_col]).strip()
        match = _PARTICIPANT_ID_PATTERN.search(session_name)
        participant_id = match.group(1) if match else None
        condition = str(row[condition_col]).strip() if condition_col else pd.NA
        sex = sex_mapping.get(participant_id, pd.NA) if participant_id else pd.NA
        rows.append(
            {
                "session": session_name,
                "participant_id": participant_id,
                "condition": condition,
                "sex": sex,
            }
        )

    metadata_df = pd.DataFrame(rows)

    unmatched = metadata_df["participant_id"].isna().sum()
    if unmatched:
        warnings.warn(
            f"load_session_metadata: {unmatched} session(s) had no extractable "
            "participant ID — sex will be NaN for those rows.",
            stacklevel=2,
        )

    no_sex = metadata_df["sex"].isna().sum()
    if no_sex:
        no_sex_sessions = metadata_df.loc[metadata_df["sex"].isna(), "session"].tolist()
        warnings.warn(
            f"load_session_metadata: {no_sex} session(s) have no sex mapping — "
            "they will be excluded from sex-stratified analyses.\n"
            f"  Sessions: {no_sex_sessions}",
            stacklevel=2,
        )

    return metadata_df


def load_interval_summary(
    interval_summary_path: pathlib.Path,
    metadata_df: pd.DataFrame,
) -> pd.DataFrame:
    """Load pre-computed interval summary and merge with sex/condition metadata."""
    if not interval_summary_path.exists():
        print(
            f"ERROR: interval summary not found: {interval_summary_path}\n"
            "       Run analyse_stim_intervals first to generate interval_summary.csv.",
            file=sys.stderr,
        )
        sys.exit(1)

    summary_df = pd.read_csv(interval_summary_path)
    merged = summary_df.merge(
        metadata_df[["session", "participant_id", "condition", "sex"]],
        on="session",
        how="left",
    )

    total_rows = len(merged)
    nan_sex_mask = merged["sex"].isna()
    n_excluded = nan_sex_mask.sum()

    if n_excluded:
        excluded_sessions = merged.loc[nan_sex_mask, "session"].unique().tolist()
        warnings.warn(
            f"load_interval_summary: {n_excluded} row(s) across "
            f"{len(excluded_sessions)} session(s) have no sex data and will be "
            "excluded from sex-stratified analyses.",
            stacklevel=2,
        )

    filtered = merged[~nan_sex_mask].copy()
    print(
        f"  interval summary: {total_rows} rows loaded, "
        f"{n_excluded} excluded (no sex), "
        f"{len(filtered)} retained"
    )
    return filtered


# ---------------------------------------------------------------------------
# Phase 2: Descriptive statistics and asymmetry
# ---------------------------------------------------------------------------


def compute_descriptive_stats(interval_df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-participant descriptive voltage statistics grouped by channel."""
    grouped = interval_df.groupby(["participant_id", "channel"], sort=False)
    records = []
    for (participant_id, channel), grp in grouped:
        sex = grp["sex"].iloc[0]
        condition = grp["condition"].iloc[0]
        voltages = grp["median_voltage"].dropna()
        durations = grp["duration_min"].dropna()
        records.append(
            {
                "participant_id": participant_id,
                "channel": channel,
                "sex": sex,
                "condition": condition,
                "mean_voltage": voltages.mean() if len(voltages) > 0 else float("nan"),
                "median_voltage": voltages.median() if len(voltages) > 0 else float("nan"),
                "std_voltage": (
                    voltages.std(ddof=1) if len(voltages) > 1 else float("nan")
                ),
                "mean_duration_min": durations.mean() if len(durations) > 0 else float("nan"),
                "block_count": len(grp),
            }
        )
    return pd.DataFrame(records)


def compute_channel_asymmetry(interval_df: pd.DataFrame) -> pd.DataFrame:
    """Compute channel-pair asymmetry per session per block."""
    pivot = interval_df.pivot_table(
        index=["session", "block"],
        columns="channel",
        values="median_voltage",
        aggfunc="first",
    ).reset_index()

    meta = (
        interval_df.groupby(["session", "block"], sort=False)[
            ["participant_id", "sex", "condition"]
        ]
        .first()
        .reset_index()
    )

    pivot = pivot.merge(meta, on=["session", "block"], how="left")
    pivot.columns.name = None

    def _abs_diff(a, b):
        return (a - b).abs()

    def _ratio(a, b):
        if pd.isna(a) or pd.isna(b):
            return float("nan")
        max_val = max(a, b)
        if max_val == 0:
            return float("nan")
        return min(a, b) / max_val

    a1 = pivot.get("A1", pd.Series(float("nan"), index=pivot.index))
    a2 = pivot.get("A2", pd.Series(float("nan"), index=pivot.index))
    b1 = pivot.get("B1", pd.Series(float("nan"), index=pivot.index))
    b2 = pivot.get("B2", pd.Series(float("nan"), index=pivot.index))

    pivot["abs_diff_A"] = _abs_diff(a1, a2)
    pivot["abs_diff_B"] = _abs_diff(b1, b2)
    pivot["ratio_A"] = [_ratio(ra, ra2) for ra, ra2 in zip(a1, a2)]
    pivot["ratio_B"] = [_ratio(rb, rb2) for rb, rb2 in zip(b1, b2)]

    result_cols = [
        "session", "block", "participant_id", "sex", "condition",
        "abs_diff_A", "abs_diff_B", "ratio_A", "ratio_B",
    ]
    result_cols = [c for c in result_cols if c in pivot.columns]
    return pivot[result_cols].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Phase 3: Voltage change analysis
# ---------------------------------------------------------------------------


def detect_voltage_targets(
    df: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    channel: str,
) -> list:
    """Detect settled voltage targets for one channel within a stimulation block."""
    if channel not in df.columns:
        return []

    if not isinstance(df.index, pd.DatetimeIndex):
        if "timestamp" in df.columns:
            df = df.set_index("timestamp")
        else:
            return []

    df = df[~df.index.duplicated(keep="last")]
    block = df.loc[start:end, [channel]].dropna()
    if block.empty:
        return []

    targets = []
    timestamps = block.index
    gaps = pd.Series(
        (timestamps[1:] - timestamps[:-1]).total_seconds().values,
        index=timestamps[1:],
    )

    stable_end_mask = gaps > 2.0
    for ts, is_stable_end in stable_end_mask.items():
        if is_stable_end:
            voltage = float(block.at[ts, channel])
            targets.append((ts, voltage))

    last_ts = timestamps[-1]
    last_voltage = float(block.iloc[-1][channel])
    if not targets or targets[-1][0] != last_ts:
        targets.append((last_ts, last_voltage))

    return targets


def count_changes_sliding_window(targets: list, window_minutes: float) -> int:
    """Count distinct voltage change events using a sliding-window approach."""
    if not targets:
        return 1

    sorted_targets = sorted(targets, key=lambda t: t[0])
    window_td = pd.Timedelta(minutes=window_minutes)

    n_changes = 0
    prior_voltage = None
    i = 0

    while i < len(sorted_targets):
        ts, voltage = sorted_targets[i]

        if prior_voltage is None:
            n_changes += 1
        else:
            if voltage != prior_voltage:
                n_changes += 1

        prior_voltage = voltage
        window_end = ts + window_td
        i += 1
        while i < len(sorted_targets) and sorted_targets[i][0] <= window_end:
            i += 1

    return max(n_changes, 1)


def compute_stability_metrics(
    df: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict:
    """Compute per-channel voltage stability metrics for a stimulation block."""
    if not isinstance(df.index, pd.DatetimeIndex):
        if "timestamp" in df.columns:
            df = df.set_index("timestamp")
        else:
            return {ch: {"variance": float("nan"), "cv": float("nan"), "range": float("nan")} for ch in CHANNELS}

    df = df[~df.index.duplicated(keep="last")]
    result = {}

    for channel in CHANNELS:
        nan_result = {"variance": float("nan"), "cv": float("nan"), "range": float("nan")}

        if channel not in df.columns:
            result[channel] = nan_result
            continue

        block = df.loc[start:end, [channel]]
        if block.empty:
            result[channel] = nan_result
            continue

        resampled = block.resample("1s").ffill()
        active = resampled[resampled[channel] > THRESHOLD][channel].dropna()

        if active.empty:
            result[channel] = nan_result
            continue

        variance = float(active.var(ddof=1)) if len(active) > 1 else float("nan")
        mean_val = float(active.mean())
        std_val = float(active.std(ddof=1)) if len(active) > 1 else float("nan")
        cv = (std_val / mean_val) if (mean_val != 0 and not pd.isna(std_val)) else float("nan")
        range_v = float(active.max() - active.min())

        result[channel] = {"variance": variance, "cv": cv, "range": range_v}

    return result


def compute_time_to_first_stable(
    df: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    channel: str,
) -> float:
    """Compute seconds from block start to the first stable voltage plateau."""
    if channel not in df.columns:
        return float("nan")

    if not isinstance(df.index, pd.DatetimeIndex):
        if "timestamp" in df.columns:
            df = df.set_index("timestamp")
        else:
            return float("nan")

    df = df[~df.index.duplicated(keep="last")]
    block = df.loc[start:end, [channel]].dropna()

    if len(block) < 2:
        return float("nan")

    timestamps = block.index
    for i in range(len(timestamps) - 1):
        gap_seconds = (timestamps[i + 1] - timestamps[i]).total_seconds()
        if gap_seconds > 10.0:
            return (timestamps[i] - start).total_seconds()

    return float("nan")


def analyse_voltage_changes(
    metadata_df: pd.DataFrame,
    preprocess_dir: pathlib.Path,
) -> tuple:
    """Batch voltage change analysis across all sessions."""
    _DEFAULT_WINDOW = 2
    changes_rows = []
    sensitivity_rows = []
    stability_rows = []

    for _, meta_row in metadata_df.iterrows():
        session = meta_row["session"]
        participant_id = meta_row["participant_id"]
        condition = meta_row["condition"]
        sex = meta_row["sex"]

        if str(condition).lower() == "skipped":
            continue

        csv_path = preprocess_dir / session / "voltages.csv"
        if not csv_path.exists():
            print(f"  WARNING [{session}]: voltages.csv not found at {csv_path} — skipping")
            continue

        try:
            df = load_session(csv_path)
        except Exception as exc:
            print(f"  WARNING [{session}]: failed to load voltages.csv — {exc}")
            continue

        try:
            intervals = detect_active_intervals(df, threshold=THRESHOLD)
            status, labelled = classify_intervals(intervals)
        except Exception as exc:
            print(f"  WARNING [{session}]: block detection failed — {exc}")
            continue

        if status == "skipped" or not labelled:
            continue

        for start, end, block_label in labelled:
            block_stability = compute_stability_metrics(df, start, end)

            for channel in CHANNELS:
                targets = detect_voltage_targets(df, start, end, channel)

                n_default = count_changes_sliding_window(targets, _DEFAULT_WINDOW)
                changes_rows.append(
                    {
                        "session": session,
                        "participant_id": participant_id,
                        "condition": condition,
                        "sex": sex,
                        "block": block_label,
                        "channel": channel,
                        "n_change_events": n_default,
                    }
                )

                for window in SENSITIVITY_WINDOWS:
                    n_win = count_changes_sliding_window(targets, window)
                    sensitivity_rows.append(
                        {
                            "session": session,
                            "participant_id": participant_id,
                            "condition": condition,
                            "sex": sex,
                            "block": block_label,
                            "channel": channel,
                            "window_minutes": window,
                            "n_change_events": n_win,
                        }
                    )

                ch_stability = block_stability.get(
                    channel,
                    {"variance": float("nan"), "cv": float("nan"), "range": float("nan")},
                )
                ttfs = compute_time_to_first_stable(df, start, end, channel)
                stability_rows.append(
                    {
                        "session": session,
                        "participant_id": participant_id,
                        "condition": condition,
                        "sex": sex,
                        "block": block_label,
                        "channel": channel,
                        "variance": ch_stability["variance"],
                        "cv": ch_stability["cv"],
                        "range_v": ch_stability["range"],
                        "time_to_first_stable": ttfs,
                    }
                )

    return pd.DataFrame(changes_rows), pd.DataFrame(sensitivity_rows), pd.DataFrame(stability_rows)


# ---------------------------------------------------------------------------
# Phase 4: Statistical tests
# ---------------------------------------------------------------------------


def mann_whitney_comparison(
    data: pd.DataFrame,
    metric: str,
    group_col: str = "sex",
) -> dict:
    """Run a Mann-Whitney U test and compute Cohen's d for one metric."""
    _nan = float("nan")
    base = {"metric": metric, "group_col": group_col}

    subset = data[[group_col, metric]].dropna()
    groups = subset[group_col].unique().tolist()
    group_data: dict[str, pd.Series] = {}

    male_label = next((g for g in groups if str(g).lower() == "male"), None)
    female_label = next((g for g in groups if str(g).lower() == "female"), None)

    if male_label is None or female_label is None:
        if len(groups) != 2:
            return {
                **base,
                "n_male": 0, "n_female": 0,
                "median_male": _nan, "median_female": _nan,
                "u_stat": _nan, "p_value": _nan, "cohens_d": _nan,
            }
        male_label, female_label = groups[0], groups[1]

    a = subset.loc[subset[group_col] == male_label, metric].dropna()
    b = subset.loc[subset[group_col] == female_label, metric].dropna()
    n_a, n_b = len(a), len(b)

    result = {
        **base,
        "n_male": n_a, "n_female": n_b,
        "median_male": float(a.median()) if n_a > 0 else _nan,
        "median_female": float(b.median()) if n_b > 0 else _nan,
        "u_stat": _nan, "p_value": _nan, "cohens_d": _nan,
    }

    if n_a < 2 or n_b < 2:
        return result

    mean_a, mean_b = float(a.mean()), float(b.mean())
    std_a, std_b = float(a.std(ddof=1)), float(b.std(ddof=1))
    pooled_var = ((n_a - 1) * std_a**2 + (n_b - 1) * std_b**2) / (n_a + n_b - 2)
    pooled_std = math.sqrt(pooled_var) if pooled_var >= 0 else _nan
    if not math.isnan(pooled_std) and pooled_std > 0:
        result["cohens_d"] = (mean_a - mean_b) / pooled_std
    else:
        result["cohens_d"] = _nan

    if _SCIPY_AVAILABLE:
        u_stat, p_value = _scipy_stats.mannwhitneyu(a.values, b.values, alternative="two-sided")
        result["u_stat"] = float(u_stat)
        result["p_value"] = float(p_value)

    return result


def run_all_statistical_tests(
    desc_df: pd.DataFrame,
    asymmetry_df: pd.DataFrame,
    changes_df: pd.DataFrame,
    stability_df: pd.DataFrame,
) -> pd.DataFrame:
    """Run all sex-group comparisons and apply Benjamini-Hochberg FDR correction."""
    _CONDITION_FILTERS = [("all", None), ("active", "active"), ("sham", "sham")]
    rows = []

    def _filter(df: pd.DataFrame, cond_value) -> pd.DataFrame:
        if cond_value is None:
            return df
        if "condition" not in df.columns:
            return df
        return df[df["condition"].str.lower() == cond_value]

    per_channel_specs = [
        (desc_df, "mean_voltage"),
        (changes_df, "n_change_events"),
        (stability_df, "variance"),
        (stability_df, "time_to_first_stable"),
    ]

    for source_df, metric in per_channel_specs:
        if source_df.empty or metric not in source_df.columns:
            continue
        if "channel" not in source_df.columns:
            continue
        channels = source_df["channel"].dropna().unique().tolist()
        for channel in sorted(channels):
            ch_data = source_df[source_df["channel"] == channel]
            for filter_label, filter_value in _CONDITION_FILTERS:
                subset = _filter(ch_data, filter_value)
                result = mann_whitney_comparison(subset, metric, group_col="sex")
                rows.append(
                    {
                        "metric": metric, "channel": channel, "condition_filter": filter_label,
                        "n_male": result["n_male"], "n_female": result["n_female"],
                        "median_male": result["median_male"], "median_female": result["median_female"],
                        "u_stat": result["u_stat"], "p_value": result["p_value"],
                        "cohens_d": result["cohens_d"],
                    }
                )

    overall_specs = [(asymmetry_df, "abs_diff_A"), (asymmetry_df, "abs_diff_B")]
    for source_df, metric in overall_specs:
        if source_df.empty or metric not in source_df.columns:
            continue
        for filter_label, filter_value in _CONDITION_FILTERS:
            subset = _filter(source_df, filter_value)
            result = mann_whitney_comparison(subset, metric, group_col="sex")
            rows.append(
                {
                    "metric": metric, "channel": "all", "condition_filter": filter_label,
                    "n_male": result["n_male"], "n_female": result["n_female"],
                    "median_male": result["median_male"], "median_female": result["median_female"],
                    "u_stat": result["u_stat"], "p_value": result["p_value"],
                    "cohens_d": result["cohens_d"],
                }
            )

    summary = pd.DataFrame(rows)

    if summary.empty:
        summary["p_adjusted"] = pd.Series(dtype=float)
        return summary

    # Benjamini-Hochberg FDR correction
    p_values = summary["p_value"].values.tolist()
    n_tests = len(p_values)
    valid_idx = [i for i, p in enumerate(p_values) if not (p != p)]
    valid_idx.sort(key=lambda i: p_values[i])

    p_adjusted = [float("nan")] * n_tests

    if valid_idx:
        n_valid = len(valid_idx)
        bh_values = []
        for rank_0based, orig_idx in enumerate(valid_idx):
            rank = rank_0based + 1
            adj = min(p_values[orig_idx] * n_valid / rank, 1.0)
            bh_values.append((orig_idx, adj))

        running_min = 1.0
        for k in range(len(bh_values) - 1, -1, -1):
            orig_idx, adj = bh_values[k]
            running_min = min(running_min, adj)
            p_adjusted[orig_idx] = running_min

    summary["p_adjusted"] = p_adjusted
    return summary


# ---------------------------------------------------------------------------
# Phase 5: Figure helpers
# ---------------------------------------------------------------------------


def _pvalue_label(p: float) -> str:
    if p != p:
        return "p=n/a"
    if p < 0.001:
        return "p<0.001***"
    if p < 0.01:
        stars = "**"
    elif p < 0.05:
        stars = "*"
    else:
        stars = ""
    return f"p={p:.3f}{stars}"


def _lookup_pvalue(
    stats_df: pd.DataFrame, metric: str, channel: str, condition_filter: str = "all"
) -> float:
    if stats_df is None or stats_df.empty:
        return float("nan")
    mask = (
        (stats_df["metric"] == metric)
        & (stats_df["channel"] == channel)
        & (stats_df["condition_filter"] == condition_filter)
    )
    rows = stats_df[mask]
    if rows.empty:
        return float("nan")
    return float(rows.iloc[0]["p_adjusted"])


def _annotate_pvalue(ax, p: float, x0: float, x1: float, y: float, fontsize: int = 8) -> None:
    label = _pvalue_label(p)
    ax.plot([x0, x0, x1, x1], [y, y + 0.02, y + 0.02, y], lw=0.8, color="black")
    ax.text((x0 + x1) / 2, y + 0.03, label, ha="center", va="bottom", fontsize=fontsize)


# ---------------------------------------------------------------------------
# Phase 6: Figure generation
# ---------------------------------------------------------------------------


def plot_descriptive_boxplots(
    desc_df: pd.DataFrame, stats_df: pd.DataFrame, output_dir: pathlib.Path
) -> pathlib.Path:
    channels = ["A1", "A2", "B1", "B2"]
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    axes = axes.flatten()
    male_color = "#4C72B0"
    female_color = "#DD8452"

    for idx, channel in enumerate(channels):
        ax = axes[idx]
        ch_data = desc_df[desc_df["channel"] == channel] if not desc_df.empty else pd.DataFrame()
        male_vals = (
            ch_data.loc[ch_data["sex"] == "male", "mean_voltage"].dropna().values
            if not ch_data.empty else np.array([])
        )
        female_vals = (
            ch_data.loc[ch_data["sex"] == "female", "mean_voltage"].dropna().values
            if not ch_data.empty else np.array([])
        )

        bp = ax.boxplot(
            [male_vals, female_vals], positions=[1, 2], widths=0.5, patch_artist=True,
            medianprops={"color": "black", "linewidth": 1.5},
            whiskerprops={"linewidth": 1}, capprops={"linewidth": 1},
            flierprops={"marker": "o", "markersize": 3, "alpha": 0.5},
        )
        bp["boxes"][0].set_facecolor(male_color)
        bp["boxes"][0].set_alpha(0.7)
        if len(bp["boxes"]) > 1:
            bp["boxes"][1].set_facecolor(female_color)
            bp["boxes"][1].set_alpha(0.7)

        p = _lookup_pvalue(stats_df, "mean_voltage", channel, "all")
        if not (p != p):
            all_vals = np.concatenate([male_vals, female_vals]) if len(male_vals) + len(female_vals) > 0 else np.array([0])
            y_top = float(np.nanmax(all_vals)) if len(all_vals) > 0 else 1.0
            y_ann = y_top * 1.05 if y_top > 0 else 0.1
            _annotate_pvalue(ax, p, 1, 2, y_ann)

        ax.set_xticks([1, 2])
        ax.set_xticklabels(["Male", "Female"])
        ax.set_title(f"Channel {channel}")
        ax.set_ylabel("Mean Voltage (V)")
        ax.set_xlim(0.5, 2.5)

    fig.suptitle("Per-Channel Mean Voltage: Male vs Female", fontsize=13, fontweight="bold")
    plt.tight_layout()
    out_path = output_dir / "descriptive_boxplots.png"
    fig.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    logging.info("  saved descriptive_boxplots.png")
    return out_path


def plot_change_counts(
    changes_df: pd.DataFrame, stats_df: pd.DataFrame, output_dir: pathlib.Path
) -> pathlib.Path:
    blocks = ["block_1", "block_2"]
    block_labels = ["Block 1", "Block 2"]
    channels = ["A1", "A2", "B1", "B2"]
    male_color = "#4C72B0"
    female_color = "#DD8452"

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for ax_idx, (block, blabel) in enumerate(zip(blocks, block_labels)):
        ax = axes[ax_idx]
        x_positions = np.arange(len(channels))
        bar_width = 0.35

        block_data = changes_df[changes_df["block"] == block] if not changes_df.empty else pd.DataFrame()
        male_means, male_sems, female_means, female_sems = [], [], [], []

        for ch in channels:
            ch_data = block_data[block_data["channel"] == ch] if not block_data.empty else pd.DataFrame()
            m_vals = ch_data.loc[ch_data["sex"] == "male", "n_change_events"].dropna() if not ch_data.empty else pd.Series(dtype=float)
            f_vals = ch_data.loc[ch_data["sex"] == "female", "n_change_events"].dropna() if not ch_data.empty else pd.Series(dtype=float)
            male_means.append(m_vals.mean() if len(m_vals) > 0 else 0)
            male_sems.append(m_vals.sem() if len(m_vals) > 1 else 0)
            female_means.append(f_vals.mean() if len(f_vals) > 0 else 0)
            female_sems.append(f_vals.sem() if len(f_vals) > 1 else 0)

        ax.bar(x_positions - bar_width / 2, male_means, bar_width, yerr=male_sems, capsize=4, label="Male", color=male_color, alpha=0.8, error_kw={"linewidth": 1})
        ax.bar(x_positions + bar_width / 2, female_means, bar_width, yerr=female_sems, capsize=4, label="Female", color=female_color, alpha=0.8, error_kw={"linewidth": 1})

        ax.set_xticks(x_positions)
        ax.set_xticklabels(channels)
        ax.set_title(blabel)
        ax.set_ylabel("Mean N Change Events")
        ax.legend(fontsize=8)

    fig.suptitle("Voltage Change Event Counts: Male vs Female", fontsize=13, fontweight="bold")
    plt.tight_layout()
    out_path = output_dir / "change_counts.png"
    fig.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    logging.info("  saved change_counts.png")
    return out_path


def plot_stability_comparison(
    stability_df: pd.DataFrame, output_dir: pathlib.Path
) -> pathlib.Path:
    blocks = ["block_1", "block_2"]
    block_labels = ["Block 1", "Block 2"]
    metrics = ["variance", "cv"]
    metric_labels = ["Variance (V²)", "CV (std/mean)"]
    male_color = "#4C72B0"
    female_color = "#DD8452"

    fig, axes = plt.subplots(2, 2, figsize=(10, 8))

    for row_idx, (block, blabel) in enumerate(zip(blocks, block_labels)):
        for col_idx, (metric, mlabel) in enumerate(zip(metrics, metric_labels)):
            ax = axes[row_idx][col_idx]
            block_data = stability_df[stability_df["block"] == block] if not stability_df.empty else pd.DataFrame()

            male_vals = block_data.loc[block_data["sex"] == "male", metric].dropna().values if not block_data.empty else np.array([])
            female_vals = block_data.loc[block_data["sex"] == "female", metric].dropna().values if not block_data.empty else np.array([])

            bp = ax.boxplot(
                [male_vals, female_vals], positions=[1, 2], widths=0.4, patch_artist=True,
                medianprops={"color": "black", "linewidth": 1.5},
                whiskerprops={"linewidth": 1}, capprops={"linewidth": 1},
                flierprops={"marker": ""},
            )
            bp["boxes"][0].set_facecolor(male_color)
            bp["boxes"][0].set_alpha(0.3)
            if len(bp["boxes"]) > 1:
                bp["boxes"][1].set_facecolor(female_color)
                bp["boxes"][1].set_alpha(0.3)

            rng = np.random.default_rng(42)
            for pos, vals, color in [(1, male_vals, male_color), (2, female_vals, female_color)]:
                if len(vals) > 0:
                    jitter = rng.uniform(-0.12, 0.12, size=len(vals))
                    ax.scatter(pos + jitter, vals, color=color, alpha=0.6, s=18, zorder=3, linewidths=0)

            ax.set_xticks([1, 2])
            ax.set_xticklabels(["Male", "Female"])
            ax.set_title(f"{blabel} — {mlabel}")
            ax.set_ylabel(mlabel)
            ax.set_xlim(0.5, 2.5)

    fig.suptitle("Voltage Stability Metrics: Male vs Female", fontsize=13, fontweight="bold")
    plt.tight_layout()
    out_path = output_dir / "stability_comparison.png"
    fig.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    logging.info("  saved stability_comparison.png")
    return out_path


def plot_asymmetry_comparison(
    asymmetry_df: pd.DataFrame, stats_df: pd.DataFrame, output_dir: pathlib.Path
) -> pathlib.Path:
    pairs = [("abs_diff_A", "A-pair |A1−A2|"), ("abs_diff_B", "B-pair |B1−B2|")]
    male_color = "#4C72B0"
    female_color = "#DD8452"

    fig, axes = plt.subplots(1, 2, figsize=(10, 5))

    for ax_idx, (metric, title) in enumerate(pairs):
        ax = axes[ax_idx]
        if asymmetry_df.empty or metric not in asymmetry_df.columns:
            male_vals = np.array([])
            female_vals = np.array([])
        else:
            male_vals = asymmetry_df.loc[asymmetry_df["sex"] == "male", metric].dropna().values
            female_vals = asymmetry_df.loc[asymmetry_df["sex"] == "female", metric].dropna().values

        data_for_violin, positions, colors = [], [], []
        if len(male_vals) >= 2:
            data_for_violin.append(male_vals)
            positions.append(1)
            colors.append(male_color)
        if len(female_vals) >= 2:
            data_for_violin.append(female_vals)
            positions.append(2)
            colors.append(female_color)

        if data_for_violin:
            parts = ax.violinplot(data_for_violin, positions=positions, showmedians=True, widths=0.6)
            for body, color in zip(parts["bodies"], colors):
                body.set_facecolor(color)
                body.set_alpha(0.5)
            for part_name in ("cmedians", "cbars", "cmins", "cmaxes"):
                if part_name in parts:
                    parts[part_name].set_color("black")
                    parts[part_name].set_linewidth(1)

        rng = np.random.default_rng(42)
        for pos, vals, color in [(1, male_vals, male_color), (2, female_vals, female_color)]:
            if len(vals) > 0:
                jitter = rng.uniform(-0.08, 0.08, size=len(vals))
                ax.scatter(pos + jitter, vals, color=color, alpha=0.7, s=20, zorder=4, linewidths=0)

        p = _lookup_pvalue(stats_df, metric, "all", "all")
        if not (p != p) and len(male_vals) > 0 and len(female_vals) > 0:
            y_top = max(float(np.nanmax(male_vals)) if len(male_vals) > 0 else 0, float(np.nanmax(female_vals)) if len(female_vals) > 0 else 0)
            y_ann = y_top * 1.05 if y_top > 0 else 0.1
            _annotate_pvalue(ax, p, 1, 2, y_ann)

        ax.set_xticks([1, 2])
        ax.set_xticklabels(["Male", "Female"])
        ax.set_title(title)
        ax.set_ylabel("Absolute Difference (V)")
        ax.set_xlim(0.5, 2.5)

    fig.suptitle("Channel-Pair Asymmetry: Male vs Female", fontsize=13, fontweight="bold")
    plt.tight_layout()
    out_path = output_dir / "asymmetry_comparison.png"
    fig.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    logging.info("  saved asymmetry_comparison.png")
    return out_path


def plot_time_to_stable(
    stability_df: pd.DataFrame, stats_df: pd.DataFrame, output_dir: pathlib.Path
) -> pathlib.Path:
    channels = ["A1", "A2", "B1", "B2"]
    male_color = "#4C72B0"
    female_color = "#DD8452"

    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    axes = axes.flatten()

    for idx, channel in enumerate(channels):
        ax = axes[idx]
        if stability_df.empty or "time_to_first_stable" not in stability_df.columns:
            male_vals = np.array([])
            female_vals = np.array([])
        else:
            ch_data = stability_df[stability_df["channel"] == channel]
            male_vals = ch_data.loc[ch_data["sex"] == "male", "time_to_first_stable"].dropna().values
            female_vals = ch_data.loc[ch_data["sex"] == "female", "time_to_first_stable"].dropna().values

        bp = ax.boxplot(
            [male_vals, female_vals], positions=[1, 2], widths=0.5, patch_artist=True,
            medianprops={"color": "black", "linewidth": 1.5},
            whiskerprops={"linewidth": 1}, capprops={"linewidth": 1},
            flierprops={"marker": "o", "markersize": 3, "alpha": 0.5},
        )
        bp["boxes"][0].set_facecolor(male_color)
        bp["boxes"][0].set_alpha(0.7)
        if len(bp["boxes"]) > 1:
            bp["boxes"][1].set_facecolor(female_color)
            bp["boxes"][1].set_alpha(0.7)

        p = _lookup_pvalue(stats_df, "time_to_first_stable", channel, "all")
        if not (p != p):
            all_vals = np.concatenate([male_vals, female_vals]) if len(male_vals) + len(female_vals) > 0 else np.array([0])
            y_top = float(np.nanmax(all_vals)) if len(all_vals) > 0 else 1.0
            y_ann = y_top * 1.05 if y_top > 0 else 5.0
            _annotate_pvalue(ax, p, 1, 2, y_ann)

        ax.set_xticks([1, 2])
        ax.set_xticklabels(["Male", "Female"])
        ax.set_title(f"Channel {channel}")
        ax.set_ylabel("Time to First Stable (s)")
        ax.set_xlim(0.5, 2.5)

    fig.suptitle("Time to First Stable Voltage: Male vs Female", fontsize=13, fontweight="bold")
    plt.tight_layout()
    out_path = output_dir / "time_to_stable.png"
    fig.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    logging.info("  saved time_to_stable.png")
    return out_path


def plot_condition_sex_interaction(
    desc_df: pd.DataFrame, output_dir: pathlib.Path
) -> pathlib.Path:
    channels = ["A1", "A2", "B1", "B2"]
    conditions = ["active", "sham"]
    condition_colors = {"active": "#2ca02c", "sham": "#d62728"}
    sex_order = ["male", "female"]

    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    axes = axes.flatten()

    for idx, channel in enumerate(channels):
        ax = axes[idx]
        ch_data = desc_df[desc_df["channel"] == channel] if not desc_df.empty else pd.DataFrame()

        for cond in conditions:
            cond_data = (
                ch_data[ch_data["condition"].str.lower() == cond]
                if not ch_data.empty and "condition" in ch_data.columns
                else pd.DataFrame()
            )
            means, cis, x_positions = [], [], []

            for xi, sex in enumerate(sex_order):
                sex_vals = (
                    cond_data.loc[cond_data["sex"] == sex, "mean_voltage"].dropna().values
                    if not cond_data.empty else np.array([])
                )
                if len(sex_vals) > 0:
                    mean_v = float(np.mean(sex_vals))
                    sem_v = float(np.std(sex_vals, ddof=1) / np.sqrt(len(sex_vals))) if len(sex_vals) > 1 else 0.0
                    ci_v = 1.96 * sem_v
                else:
                    mean_v = float("nan")
                    ci_v = 0.0
                means.append(mean_v)
                cis.append(ci_v)
                x_positions.append(xi)

            valid = [i for i, m in enumerate(means) if not (m != m)]
            if len(valid) >= 1:
                xs = [x_positions[i] for i in valid]
                ys = [means[i] for i in valid]
                errs = [cis[i] for i in valid]
                color = condition_colors.get(cond, "grey")
                ax.plot(xs, ys, marker="o", color=color, label=cond.capitalize(), linewidth=1.5, markersize=6)
                ax.errorbar(xs, ys, yerr=errs, fmt="none", color=color, capsize=4, linewidth=1)

        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Male", "Female"])
        ax.set_title(f"Channel {channel}")
        ax.set_ylabel("Mean Voltage (V)")
        ax.legend(fontsize=8)
        ax.set_xlim(-0.5, 1.5)

    fig.suptitle("Condition × Sex Interaction: Mean Voltage", fontsize=13, fontweight="bold")
    plt.tight_layout()
    out_path = output_dir / "condition_sex_interaction.png"
    fig.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    logging.info("  saved condition_sex_interaction.png")
    return out_path


# ---------------------------------------------------------------------------
# Task contract
# ---------------------------------------------------------------------------


def run_sex_based_voltage_analysis(
    input_items: List[pathlib.Path],
    output_dir: pathlib.Path,
    force: bool = False,
) -> List[pathlib.Path]:
    """Run the full sex-based voltage analysis pipeline.

    Parameters
    ----------
    input_items:
        Paths to input data files.  The function looks for these specific
        file names among *input_items* (matched by ``name``):

        - ``interval_summary.csv``    — from ``run_analyse_stim_intervals``
        - ``Excel_for_stimulators.xlsx`` — participant sex mapping
        - ``condition_validation_report.csv`` — session-to-condition map

        Any item that is a *directory* is treated as the preprocessed data
        directory (``TILA_DATA_1_processed``).  Unrecognised items are ignored.

        Missing files fall back to their default locations under
        ``backlogs_local_data/``.

    output_dir:
        Directory where all 7 CSV and 6 PNG outputs are written.
    force:
        When ``True``, rerun even if all outputs are already up-to-date.

    Returns
    -------
    list of Path
        Paths to all 13 output files (7 CSVs + 6 PNGs).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    all_outputs = [output_dir / name for name in _CSV_NAMES + _PNG_NAMES]

    # Resolve special input files from input_items or fall back to defaults
    interval_summary_path = _DEFAULT_INTERVAL_SUMMARY_PATH
    excel_path = _DEFAULT_EXCEL_PATH
    condition_report_path = _DEFAULT_CONDITION_REPORT_PATH
    preprocess_dir = _DEFAULT_PREPROCESS_DIR

    for item in input_items:
        if item.is_dir():
            preprocess_dir = item
        elif item.name == "interval_summary.csv":
            interval_summary_path = item
        elif item.name.endswith(".xlsx"):
            excel_path = item
        elif item.name == "condition_validation_report.csv":
            condition_report_path = item

    # Collect input files that exist for idempotency check
    idempotency_inputs = [p for p in [interval_summary_path, excel_path, condition_report_path] if p.exists()]
    if not idempotency_inputs:
        logging.warning("[sex_based_voltage_analysis] No valid input files found for idempotency check.")
        return []

    if not should_process_task(
        input_paths=idempotency_inputs,
        output_paths=all_outputs,
        force=force,
    ):
        return all_outputs

    for p in all_outputs:
        clean_task_outputs(p)

    print("=" * 60)
    print("Sex-Based Voltage Analysis")
    print("=" * 60)

    print("\n[1/9] Loading sex mapping from Excel...")
    sex_map = load_sex_mapping(excel_path)
    print(f"  {len(sex_map)} participant sex entries loaded")

    print("\n[2/9] Loading session metadata...")
    metadata_df = load_session_metadata(condition_report_path, sex_map)
    print(f"  {len(metadata_df)} sessions in condition report")

    print("\n[3/9] Loading interval summary...")
    interval_df = load_interval_summary(interval_summary_path, metadata_df)

    print("\n[4/9] Computing descriptive stats and channel asymmetry...")
    desc_df = compute_descriptive_stats(interval_df)
    asymmetry_df = compute_channel_asymmetry(interval_df)
    print(f"  descriptive stats: {len(desc_df)} rows")
    print(f"  asymmetry: {len(asymmetry_df)} rows")

    print("\n[5/9] Analysing raw voltage CSVs (changes, stability)...")
    metadata_with_sex = metadata_df[metadata_df["sex"].notna()].copy()
    print(f"  processing {len(metadata_with_sex)} sessions with known sex")
    changes_df, sensitivity_df, stability_df = analyse_voltage_changes(metadata_with_sex, preprocess_dir)
    print(f"  changes: {len(changes_df)} rows")
    print(f"  sensitivity: {len(sensitivity_df)} rows")
    print(f"  stability: {len(stability_df)} rows")

    print("\n[6/9] Running statistical tests...")
    stats_df = run_all_statistical_tests(desc_df, asymmetry_df, changes_df, stability_df)
    print(f"  {len(stats_df)} tests run")
    if not stats_df.empty and "p_adjusted" in stats_df.columns:
        n_sig = (stats_df["p_adjusted"] < 0.05).sum()
        print(f"  {n_sig} tests significant at FDR q < 0.05")

    print("\n[7/9] Generating figures...")
    plot_descriptive_boxplots(desc_df, stats_df, output_dir)
    plot_change_counts(changes_df, stats_df, output_dir)
    plot_stability_comparison(stability_df, output_dir)
    plot_asymmetry_comparison(asymmetry_df, stats_df, output_dir)
    plot_time_to_stable(stability_df, stats_df, output_dir)
    plot_condition_sex_interaction(desc_df, output_dir)

    print("\n[8/9] Saving CSV outputs...")
    csv_map = {
        "session_metadata.csv": metadata_df,
        "interval_summary_with_sex.csv": interval_df,
        "participant_descriptive_stats.csv": desc_df,
        "channel_asymmetry.csv": asymmetry_df,
        "voltage_change_counts.csv": changes_df,
        "sliding_window_sensitivity.csv": sensitivity_df,
        "statistical_tests_summary.csv": stats_df,
    }
    for filename, df in csv_map.items():
        out_path = output_dir / filename
        df.to_csv(out_path, index=False)
        logging.info(f"  saved {filename}")

    print("\n[9/9] Summary")
    print("-" * 40)
    total_sessions = len(metadata_df)
    n_male = int((metadata_df["sex"] == "male").sum())
    n_female = int((metadata_df["sex"] == "female").sum())
    n_excluded = int(metadata_df["sex"].isna().sum())
    print(f"  Total sessions        : {total_sessions}")
    print(f"  Male sessions         : {n_male}")
    print(f"  Female sessions       : {n_female}")
    print(f"  Excluded (no sex data): {n_excluded}")
    print("\nDone.")
    print("=" * 60)

    return all_outputs


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sex-stratified voltage analysis across all TILA stimulation sessions."
    )
    parser.add_argument(
        "--output-dir",
        type=pathlib.Path,
        default=_BACKLOGS / "TILA_DATA_2_analysed" / "sex_voltage_analysis",
        help="Directory where CSV and PNG outputs are written.",
    )
    parser.add_argument(
        "--interval-summary",
        type=pathlib.Path,
        default=_DEFAULT_INTERVAL_SUMMARY_PATH,
        help="Path to interval_summary.csv from analyse_stim_intervals.",
    )
    parser.add_argument(
        "--excel",
        type=pathlib.Path,
        default=_DEFAULT_EXCEL_PATH,
        help="Path to Excel_for_stimulators.xlsx.",
    )
    parser.add_argument(
        "--condition-report",
        type=pathlib.Path,
        default=_DEFAULT_CONDITION_REPORT_PATH,
        help="Path to condition_validation_report.csv.",
    )
    parser.add_argument(
        "--preprocess-dir",
        type=pathlib.Path,
        default=_DEFAULT_PREPROCESS_DIR,
        help="Directory containing per-session subdirectories with voltages.csv.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rerun even if all outputs are already up-to-date.",
    )
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    input_items = [
        args.interval_summary,
        args.excel,
        args.condition_report,
        args.preprocess_dir,
    ]

    produced = run_sex_based_voltage_analysis(input_items, args.output_dir, force=args.force)
    if not produced:
        print("No outputs produced.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
