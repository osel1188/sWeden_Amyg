# Plan: Refactor Sex-Based Voltage Analysis

**Date:** 2026-04-01
**Author:** Claude
**Status:** Completed
**Completed:** 2026-04-01 16:30
**Branch:** `feature/refactor-sex-voltage-analysis`

---

## Overview

Refactor `run_sex_based_voltage_analysis` to remove stability/time-to-stable features, replace the voltage change counting algorithm with a plateau-based approach (signal constant for >= 60 s), unify Y-axes across multi-subplot figures, and ensure all plots show male-vs-female significance annotations.

## Problem Statement

The current sex-based voltage analysis has several issues:
1. **Stability and time-to-stable metrics** are not meaningful for the research question and add noise to the output.
2. **Voltage change counting** uses a sliding-window approach over 2-second gaps, which does not correspond to the actual definition of a voltage change (a ramp followed by a new plateau lasting >= 60 s).
3. **Multi-subplot figures** have independent Y-axes, making visual comparison across channels/conditions misleading.
4. **Two plots** (`change_counts`, `condition_sex_interaction`) lack male-vs-female significance annotations present on other plots.

## Goals

### In Scope
1. Remove stability metrics (`compute_stability_metrics`, `compute_time_to_first_stable`) and their plots/CSVs
2. Replace voltage change detection with plateau-based algorithm (>= 60 s constant, 0.01 V tolerance)
3. Aggregate voltage changes per participant (sum across all channels and blocks)
4. Unify Y-axes across subplots in all multi-subplot figures
5. Add p-value annotations to `plot_change_counts` and `plot_condition_sex_interaction`

### Out of Scope
- Changes to upstream tasks (`analyse_stim_intervals`, preprocessing)
- New statistical tests beyond existing Mann-Whitney U framework
- Changes to the DAG configuration or workflow wiring

## Success Criteria

- [x] Output directory contains exactly 6 CSVs and 4 PNGs (down from 7 + 6)
- [x] `voltage_change_counts.csv` has one row per participant with `n_voltage_changes` summed across channels and blocks
- [x] `statistical_tests_summary.csv` contains `n_voltage_changes` metric (channel=all), no `variance` or `time_to_first_stable` metrics
- [x] All 4 PNGs with multiple subplots share Y-axis limits across subplots
- [x] All 4 PNGs display p-value annotations comparing male vs female
- [x] Standalone execution succeeds: `python scripts/analysis/sex_based_voltage_analysis.py --force`

---

## Technical Design

### Approach

Modify `scripts/analysis/sex_based_voltage_analysis.py` in-place. Delete unused functions, replace the voltage change detection core, adjust statistical tests and plots, and update output constants. Supporting files (`__init__.py`, `analysis_workflow.py`) need no changes since they reference `CSV_OUTPUT_NAMES` and `PNG_OUTPUT_NAMES` dynamically.

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| In-place refactor | Minimal file churn, preserves git history | Larger diff on one file | **Chosen** |
| Rewrite as new module | Clean separation | Duplicates boilerplate, breaks workflow wiring | Rejected |

### New Plateau Detection Algorithm

`count_plateau_changes(df, start, end, channel, min_plateau_seconds=60, voltage_tolerance=0.01) -> int`

1. Extract block slice `df.loc[start:end, [channel]]`, ensure DatetimeIndex
2. Resample to 1 s with forward-fill
3. Round voltages: `(values / tolerance).round() * tolerance`
4. Label contiguous constant segments: `(rounded != rounded.shift()).cumsum()`
5. Filter segments with duration >= `min_plateau_seconds`
6. Count transitions between consecutive valid plateaus where voltage differs
7. Return count (first plateau is not a change; 0 if <= 1 valid plateau)

### Output Changes

| Before | After |
|--------|-------|
| 7 CSVs | 6 CSVs (remove `sliding_window_sensitivity.csv`) |
| 6 PNGs | 4 PNGs (remove `stability_comparison.png`, `time_to_stable.png`) |
| `n_change_events` per channel/block | `n_voltage_changes` per participant |

Final CSVs: `session_metadata`, `interval_summary_with_sex`, `participant_descriptive_stats`, `channel_asymmetry`, `voltage_change_counts`, `statistical_tests_summary`

Final PNGs: `descriptive_boxplots`, `change_counts`, `asymmetry_comparison`, `condition_sex_interaction`

---

## Implementation Plan

### Phase 1: Remove stability and time-to-stable
**Goal:** Strip unused metrics, functions, plots, and CSV outputs.

- [x] Delete `compute_stability_metrics` (lines 401-443)
- [x] Delete `compute_time_to_first_stable` (lines 446-474)
- [x] Delete `plot_stability_comparison` (lines 878-928)
- [x] Delete `plot_time_to_stable` (lines 996-1047)
- [x] Delete `detect_voltage_targets` (lines 329-368) and `count_changes_sliding_window` (lines 371-398) (replaced in Phase 2)
- [x] Remove `SENSITIVITY_WINDOWS` constant (line 81)
- [x] Remove `"sliding_window_sensitivity.csv"` from `CSV_OUTPUT_NAMES`
- [x] Remove `"stability_comparison.png"` and `"time_to_stable.png"` from `PNG_OUTPUT_NAMES`
- [x] Remove `stability_df` parameter from `run_all_statistical_tests`; remove `(stability_df, "variance")` and `(stability_df, "time_to_first_stable")` from `per_channel_specs`
- [x] Update `analyse_voltage_changes`: remove stability/sensitivity rows and return only `changes_df`
- [x] Update `run_sex_based_voltage_analysis` orchestrator: remove stability/sensitivity references, remove deleted plot calls, remove deleted CSV entries, renumber steps
- [x] Update module docstring output counts

**Files Modified:**
- `scripts/analysis/sex_based_voltage_analysis.py` — all changes above

**Dependencies:** None

### Phase 2: New plateau-based voltage change counting
**Goal:** Replace voltage change detection with plateau algorithm; aggregate per participant.

- [x] Add `count_plateau_changes(df, start, end, channel, min_plateau_seconds=60, voltage_tolerance=0.01) -> int` function
- [x] Restructure `analyse_voltage_changes` to call `count_plateau_changes` per channel/block and sum into per-participant totals
- [x] Return single DataFrame with columns: `participant_id`, `session`, `condition`, `sex`, `n_voltage_changes`
- [x] Move `(changes_df, "n_voltage_changes")` from `per_channel_specs` to `overall_specs` in `run_all_statistical_tests` (tested with `channel="all"`)

**Files Modified:**
- `scripts/analysis/sex_based_voltage_analysis.py` — new function + restructured `analyse_voltage_changes` + updated stats

**Dependencies:** Phase 1

### Phase 3: Significance annotations on all plots
**Goal:** Ensure every plot annotates male-vs-female p-values.

- [x] Redesign `plot_change_counts` as 1x2 subplots split by condition (active / sham), each showing boxplot of `n_voltage_changes` with scatter points, annotated with `_lookup_pvalue(stats_df, "n_voltage_changes", "all", condition_filter)`
- [x] Add `stats_df` parameter to `plot_condition_sex_interaction`; annotate each channel subplot with `_lookup_pvalue(stats_df, "mean_voltage", channel, "all")`
- [x] Update call site in orchestrator to pass `stats_df` to `plot_condition_sex_interaction`

**Files Modified:**
- `scripts/analysis/sex_based_voltage_analysis.py` — two plot functions + orchestrator call

**Dependencies:** Phase 2

### Phase 4: Shared Y-axes across subplots
**Goal:** Unify Y-axis limits within each multi-subplot figure.

- [x] After each subplot loop and before `plt.tight_layout()`, add shared-ylim block to:
  - `plot_descriptive_boxplots` (2x2)
  - `plot_change_counts` (1x2, after redesign)
  - `plot_asymmetry_comparison` (1x2)
  - `plot_condition_sex_interaction` (2x2)

Pattern (identical for all four):
```python
all_ylims = [ax.get_ylim() for ax in axes]
global_ymin = min(lo for lo, _ in all_ylims)
global_ymax = max(hi for _, hi in all_ylims)
for ax in axes:
    ax.set_ylim(global_ymin, global_ymax)
```

**Files Modified:**
- `scripts/analysis/sex_based_voltage_analysis.py` — four plot functions

**Dependencies:** Phase 3

---

## Testing Plan

### Manual Verification
- [x] Run standalone: `python scripts/analysis/sex_based_voltage_analysis.py --force`
- [x] Verify output directory contains exactly 6 CSVs + 4 PNGs (no extra files)
- [x] Open `voltage_change_counts.csv`: one row per participant, `n_voltage_changes` column present
- [x] Open `statistical_tests_summary.csv`: no `variance` or `time_to_first_stable` metrics; `n_voltage_changes` with `channel=all` present
- [x] Visually inspect each PNG: Y-axes match across subplots, p-value brackets visible

### Edge Cases
- [x] Sessions with no valid plateaus (all changes < 60 s) produce `n_voltage_changes = 0`
- [x] Sessions with only one plateau across all channels produce `n_voltage_changes = 0`
- [x] Missing voltage CSVs are skipped gracefully (existing behavior preserved)

---

## Rollback Plan

1. All changes are in a single file (`sex_based_voltage_analysis.py`); `git checkout` reverts everything
2. No database or external state changes
3. No breaking changes to the workflow contract (function signature unchanged)

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| 0.01 V tolerance too tight for noisy signals | Low | Med | Log plateau counts per session; adjust tolerance if needed |
| 60 s minimum filters out legitimate short plateaus | Low | Low | Parameterised default; easy to adjust |
| FDR correction pool shrinks (fewer tests) | Certain | Low | Statistically correct; document the change |
