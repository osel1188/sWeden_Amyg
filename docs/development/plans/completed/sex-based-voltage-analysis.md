# Plan: Sex-Based Voltage Analysis

**Date:** 2026-03-30
**Author:** Claude
**Status:** Completed
**Completed:** 2026-04-01
**Branch:** `feature/sex-voltage-analysis`

---

## Overview

- **What:** A new analysis script (`07_sex_based_voltage_analysis.py`) that splits stimulation voltage data by participant sex and compares descriptive statistics, voltage change behavior, and advanced metrics between male and female groups.
- **Why:** The project has ~70 sessions of voltage data but no sex-stratified analysis. Understanding whether operator-mediated voltage patterns differ by participant sex could inform protocol design and reveal impedance/comfort-related differences.
- **How:** Merge sex data from the Excel file with existing interval summaries and raw voltage CSVs; compute per-participant statistics, sliding-window change counts, and stability/asymmetry metrics; generate comparison figures with statistical tests (Mann-Whitney U, FDR-corrected).

## Problem Statement

The existing analysis pipeline (scripts 01–06) processes raw logs into voltage CSVs, validates metadata, detects stimulation blocks, and generates per-session figures. However, no script examines whether voltage characteristics differ by participant demographics. The Excel file contains a `sex` column that has not been leveraged in any analysis. This gap prevents understanding of sex-associated patterns in stimulation parameters — information relevant for protocol standardization and reporting in publications.

## Goals

### In Scope
1. Merge participant sex from Excel with session-level voltage data
2. Compute per-participant descriptive voltage statistics (mean, median, STD) and compare between sexes
3. Count distinct voltage change events per block using sliding-window deduplication, compare between sexes
4. Compute creative metrics: channel-pair asymmetry, voltage stability (CV), time-to-first-stable
5. Run Mann-Whitney U tests with FDR correction and Cohen's d effect sizes
6. Stratify all analyses by condition (active/sham) to control for protocol confound
7. Include sliding-window sensitivity analysis (1, 1.5, 2, 3, 5 min windows)
8. Generate 6 comparison figures and 7 CSV output files

### Out of Scope
- Mixed-effects modeling (potential follow-up if exploratory results warrant it)
- Anatomical covariates (skull thickness, impedance — data not available)
- Operator identity as a variable (not tracked in current data)
- Multi-session within-participant analysis (most participants have single sessions)
- Bayesian estimation (consider if frequentist tests are uninformative)

## Success Criteria

- [ ] Script runs end-to-end on all ~70 sessions without errors
- [ ] Handles edge cases: missing sex data, single-block sessions, skipped sessions
- [ ] Produces 7 CSV files and 6 PNG figures in `TILA_DATA_2_analysed/sex_voltage_analysis/`
- [ ] `statistical_tests_summary.csv` contains FDR-corrected p-values and effect sizes
- [ ] `sliding_window_sensitivity.csv` shows change counts across 5 window sizes
- [ ] Results correctly stratified by condition (active/sham subgroups)
- [ ] Participant counts match Excel (no silent data loss)

---

## Technical Design

### Approach

Build a single standalone script that:
1. Loads sex mapping from Excel and session metadata from `condition_validation_report.csv`
2. For descriptive stats and asymmetry: operates on pre-computed `interval_summary.csv` (no raw data re-processing)
3. For change counts, stability, and time-to-stable: iterates raw `voltages.csv` files in a single pass, reusing block detection from script 06
4. Runs statistical tests on all computed metrics
5. Generates figures and saves CSVs

This avoids re-implementing block detection logic and leverages the existing processed data where possible.

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Single script importing from 06 | DRY, reuses block detection | Requires `sys.path` hack for import | **Chosen** — pragmatic, avoids ~90 lines of duplication |
| Fully standalone (copy functions) | No import dependency | Code duplication, divergence risk | Rejected |
| Mixed-effects model instead of Mann-Whitney | Handles nested structure, controls confounds simultaneously | Requires `statsmodels`, more complex to interpret for exploratory analysis | Rejected for now — flagged as follow-up |
| Adaptive sliding window (data-driven) | More principled change detection | Complex, harder to explain, no clear benefit without validation data | Rejected — sensitivity analysis over fixed windows is more transparent |

### Architecture Changes

**New file:** `scripts/analysis/07_sex_based_voltage_analysis.py`

**No existing files modified.**

**Integration points:**
- Imports `load_session`, `detect_active_intervals`, `classify_intervals` from `06_analyse_stim_intervals.py` via `sys.path` + `importlib`
- Reads `backlogs_local_data/Excel_for_stimulators.xlsx` (column `ID`, `sex`)
- Reads `backlogs_local_data/condition_validation_report.csv`
- Reads `backlogs_local_data/TILA_DATA_2_analysed/interval_analysis/interval_summary.csv`
- Reads raw `backlogs_local_data/TILA_DATA_1_processed/*/voltages.csv`
- Writes to `backlogs_local_data/TILA_DATA_2_analysed/sex_voltage_analysis/`

---

## Implementation Plan

### Phase 1: Data Loading and Merging
**Goal:** Build the central metadata lookup table joining session, participant, condition, and sex.

**Tasks:**
- [x] Task 1.1 — Module scaffold: constants, imports, path setup, `_import_script_06()` helper
- [x] Task 1.2 — `load_sex_mapping(excel_path)`: read Excel → `{participant_id: sex}` dict, lowercase/strip sex values, warn on NaN IDs
- [x] Task 1.3 — `load_session_metadata()`: load `condition_validation_report.csv`, extract participant ID from session name via regex `r"_(T?\d+)$"`, join with sex mapping → DataFrame (session, participant_id, condition, sex)
- [x] Task 1.4 — `load_interval_summary()`: load `interval_summary.csv`, merge with metadata → DataFrame with sex/condition columns; filter rows where sex is NaN

**Files Modified:**
- `scripts/analysis/07_sex_based_voltage_analysis.py` — new file

**Dependencies:** None

### Phase 2: Descriptive Stats and Asymmetry (from pre-computed data)
**Goal:** Compute per-participant voltage statistics and channel-pair asymmetry without re-processing raw data.

**Tasks:**
- [x] Task 2.1 — `compute_descriptive_stats(interval_df)`: group by (participant_id, channel), compute mean/median/STD of median_voltage, mean duration, block count → DataFrame with sex/condition
- [x] Task 2.2 — `compute_channel_asymmetry(interval_df)`: pivot interval data to get per-session per-block channel voltages, compute |A1-A2|, |B1-B2|, min/max ratios → DataFrame with sex/condition

**Files Modified:**
- `scripts/analysis/07_sex_based_voltage_analysis.py`

**Dependencies:** Phase 1

### Phase 3: Voltage Change Counting (from raw data)
**Goal:** Detect operator voltage adjustments and count distinct change events using sliding-window deduplication.

**Tasks:**
- [x] Task 3.1 — `detect_voltage_targets(df, start, end, channel)`: extract single-channel data within block, compute time gaps, identify ramp events (gap > 2s = stable period ended, new data = ramp start), return list of (timestamp, settled_voltage) tuples
- [x] Task 3.2 — `count_changes_sliding_window(targets, window_minutes)`: iterate targets, group within 2-min windows → count of distinct change events
- [x] Task 3.3 — `analyse_voltage_changes(metadata_df)`: loop sessions, load raw CSVs, detect blocks (via imported script 06), call 3.1+3.2 per block/channel → DataFrame with sex/condition
- [x] Task 3.4 — Sensitivity analysis: repeat change counting with window_minutes in [1, 1.5, 2, 3, 5], save comparison table

**Files Modified:**
- `scripts/analysis/07_sex_based_voltage_analysis.py`

**Dependencies:** Phase 1

### Phase 4: Advanced Metrics (from raw data, same session loop)
**Goal:** Compute voltage stability and time-to-first-stable metrics.

**Tasks:**
- [x] Task 4.1 — `compute_stability_metrics(df, start, end)`: resample to 1s grid with forward-fill, compute per-channel variance, CV (std/mean), range of active values
- [x] Task 4.2 — `compute_time_to_first_stable(df, start, end, channel)`: find first gap > 10s in raw data after block start (first plateau) → seconds from block start
- [x] Task 4.3 — Integrate 4.1+4.2 into the session loop from Phase 3 to avoid loading each CSV twice

**Files Modified:**
- `scripts/analysis/07_sex_based_voltage_analysis.py`

**Dependencies:** Phase 1, Phase 3 (shared session loop)

### Phase 5: Statistical Tests
**Goal:** Run group comparisons with proper correction for multiple testing.

**Tasks:**
- [x] Task 5.1 — `mann_whitney_comparison(data, metric, group_col)`: Mann-Whitney U, p-value, Cohen's d, group counts and medians
- [x] Task 5.2 — `run_all_statistical_tests(...)`: run tests per channel for mean_voltage, n_change_events, voltage_variance, time_to_first_stable; overall for A/B asymmetry; stratified by condition (active-only, sham-only); apply Benjamini-Hochberg FDR correction → summary DataFrame

**Files Modified:**
- `scripts/analysis/07_sex_based_voltage_analysis.py`

**Dependencies:** Phases 2, 3, 4

### Phase 6: Figures and CSV Output
**Goal:** Generate all visual and tabular outputs.

**Tasks:**
- [x] Task 6.1 — `plot_descriptive_boxplots()`: 2x2 grid (one per channel), side-by-side box plots male vs female, annotated with p-value
- [x] Task 6.2 — `plot_change_counts()`: 1x2 (Block 1/2), grouped bars male/female per channel with SEM error bars
- [x] Task 6.3 — `plot_stability_comparison()`: 2x2 (condition x block), strip + box overlay
- [x] Task 6.4 — `plot_asymmetry_comparison()`: 1x2 (A-pair, B-pair), violin + swarm
- [x] Task 6.5 — `plot_time_to_stable()`: 2x2 (one per channel), box plots male vs female
- [x] Task 6.6 — `plot_condition_sex_interaction()`: 2x2 line plots, sex on x-axis, lines = active/sham, y = mean voltage +/- 95% CI
- [x] Task 6.7 — `save_csv_outputs()`: save all 7 CSVs
- [x] Task 6.8 — `main()`: orchestrate full pipeline, print summary with participant counts

**Files Modified:**
- `scripts/analysis/07_sex_based_voltage_analysis.py`

**Dependencies:** Phase 5

---

## Testing Plan

### Unit Tests
- [ ] Not applicable — analysis script, no unit test infrastructure for analysis pipeline (consistent with scripts 01–06)

### Manual Verification
- [ ] Run `python scripts/analysis/07_sex_based_voltage_analysis.py` end-to-end
- [ ] Verify output directory contains 7 CSVs and 6 PNGs
- [ ] Spot-check one participant's descriptive stats against manual calculation from `interval_summary.csv`
- [ ] Verify participant counts in output match Excel (male + female + excluded = total)
- [ ] Confirm `statistical_tests_summary.csv` has p_adjusted column (FDR-corrected)
- [ ] Confirm `sliding_window_sensitivity.csv` has rows for all 5 window sizes
- [ ] Verify no crashes on edge cases: check sessions with `status=single_block` and `status=skipped` are handled

### Edge Cases
- [ ] Participant ID in session not found in Excel → logged warning, sex=NaN, excluded from grouped analyses
- [ ] Single-block session → included as Block 1 only; Block 2 metrics = NaN
- [ ] Skipped session (no blocks detected) → excluded entirely
- [ ] No voltage changes within a block → n_change_events = 1 (initial ramp)
- [ ] Division by zero in asymmetry ratio (max voltage = 0) → ratio = NaN
- [ ] `scipy` not installed → try/except import, skip statistical tests with warning

---

## Documentation Plan

- [ ] No README/CLAUDE.md changes needed (standalone analysis script)
- [ ] Script docstring explains purpose, inputs, outputs, and methodology
- [ ] Challenge analysis already written at `docs/development/challenges/sex-based-voltage-analysis-challenge.md`

---

## Rollback Plan

1. Delete `scripts/analysis/07_sex_based_voltage_analysis.py`
2. Delete output directory `backlogs_local_data/TILA_DATA_2_analysed/sex_voltage_analysis/`
3. No other files are modified — zero risk to existing pipeline

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Sample too small for meaningful sex comparisons (~35/group) | High | Med | Frame as exploratory; report effect sizes alongside p-values; FDR correction |
| 2-minute sliding window is arbitrary | Med | Med | Sensitivity analysis across 5 window sizes; report robustness |
| Condition (active/sham) confounds sex comparison | Med | High | Stratify all tests by condition; include interaction plot |
| Operator identity confounds results | Med | Med | Cannot control (data not tracked); acknowledge in script output |
| Multiple comparisons inflate false positives (~96 tests) | High | High | Benjamini-Hochberg FDR correction; label analyses as exploratory |
| `sys.path` import from script 06 is fragile | Low | Low | Fail-fast with clear error message if import fails |

---

## References

- Challenge analysis: `docs/development/challenges/sex-based-voltage-analysis-challenge.md`
- Related active plan: `docs/development/plans/active/interval-analysis.md`
- Related active plan: `docs/development/plans/active/voltage-data-visualization.md`
- Key dependency: `scripts/analysis/06_analyse_stim_intervals.py`

---
