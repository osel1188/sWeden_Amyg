# Plan: Stimulation Interval Analysis

**Date:** 2026-03-18
**Author:** Claude
**Status:** In Progress
**Branch:** `feature/interval-analysis`

---

## Overview

Create a script that extracts duration and median voltage for each channel (A1, A2, B1, B2) across the two main stimulation intervals per session, then generates cross-session comparison figures showing duration and voltage dispersion with mean and STD.

## Problem Statement

The 70 TILA sessions each produce voltage timeline plots (`plot_voltages.py`), but there is no quantitative extraction of the two stimulation blocks visible in each session. We need to measure how long each block lasted and at what voltage, then compare these across sessions to assess consistency. Currently this can only be done by visual inspection of 70 PNGs.

## Goals

### In Scope
1. Detect the two main stimulation intervals per session using a union approach across all 4 channels
2. Extract duration and time-weighted median voltage per channel per interval
3. Output a summary CSV with all extracted data
4. Generate two strip-plot figures (duration + voltage) with mean/STD overlay, split by interval

### Out of Scope
- Modifying `plot_voltages.py` or `extract_log_data.py`
- Per-session interval plots (already handled by `plot_voltages.py`)
- Statistical tests between conditions (active vs sham)
- Correlating intervals with metadata (protocol type, participant)

## Success Criteria

- [ ] Script processes all 70 sessions and produces `interval_summary.csv`
- [ ] CSV contains ~560 rows (70 sessions x 2 intervals x 4 channels) with edge cases flagged
- [ ] Duration figure shows strip plot + mean/STD for all 4 channels, split by Block 1 and Block 2
- [ ] Voltage figure shows same layout for median voltage
- [ ] Edge-case sessions (!=2 blocks) are handled gracefully with status flags

---

## Technical Design

### Approach

**Union-based interval detection**: compute `any_active = (A1 > 0.5) | (A2 > 0.5) | (B1 > 0.5) | (B2 > 0.5)`, detect transitions, filter out short intervals (<5 min), classify the two longest as Block 1 (shorter, ~20 min) and Block 2 (longer, ~55 min).

This was chosen over per-channel detection because channels behave in synchrony — the union approach avoids false block splits caused by brief single-channel dropouts.

**Time-weighted median**: since data is event-based (each row persists until next timestamp), resample to 1-second grid with forward-fill before computing median. This avoids over-counting rapidly-changing ramp values.

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Union across channels | Robust to single-channel dropouts; consistent block boundaries | May slightly extend boundaries if channels ramp at different times | Chosen |
| Per-channel independent detection | More granular; captures channel-specific blocks | Many edge cases (40% of sessions have !=2 blocks on some channel); harder to classify | Rejected |
| Mean of all channels > threshold | Simple | Fails when channels have different voltage levels; mean can stay above threshold during partial dropouts | Rejected |

### Architecture Changes

Single new standalone script following `plot_voltages.py` conventions:

```
scripts/analyse_intervals.py          # New script
backlogs_local_data/
  TILA_DATA_2_analysed/
    interval_analysis/                 # New output directory
      interval_summary.csv
      interval_duration_comparison.png
      interval_voltage_comparison.png
```

---

## Implementation Plan

### Phase 1: Core Detection and Extraction
**Goal:** Implement interval detection algorithm and per-channel stats extraction

**Tasks:**
- [ ] Task 1.1 — Implement `load_session(csv_path)`: read CSV, parse timestamps, return DataFrame
- [ ] Task 1.2 — Implement `detect_active_intervals(df, threshold=0.5)`: union approach, return list of `(start, end)` tuples filtered to >5 min
- [ ] Task 1.3 — Implement `classify_intervals(intervals)`: assign Block 1 (shorter) and Block 2 (longer); handle edge cases (merge <2 min gaps, handle 1 or 3+ blocks)
- [ ] Task 1.4 — Implement `extract_channel_stats(df, start, end, channels)`: per-channel duration above threshold + time-weighted median voltage via 1-second resampling

**Files Modified:**
- `scripts/analyse_intervals.py` — New file, all core functions

**Dependencies:** None

### Phase 2: Batch Processing and CSV Output
**Goal:** Run analysis across all 70 sessions and produce summary CSV

**Tasks:**
- [ ] Task 2.1 — Implement `analyse_all_sessions(preprocess_dir)`: iterate all `*/voltages.csv`, call core functions, collect results
- [ ] Task 2.2 — Implement `main()`: orchestrate analysis, create output directory, save CSV, print console summary with counts
- [ ] Task 2.3 — Handle edge cases: print warnings for sessions with !=2 blocks, set `status` column (ok/merged/single_block/skipped)

**Files Modified:**
- `scripts/analyse_intervals.py` — Add batch processing and main entry point

**Dependencies:** Phase 1

### Phase 3: Figure Generation
**Goal:** Generate cross-session comparison figures

**Tasks:**
- [ ] Task 3.1 — Implement `plot_strip_comparison(summary_df, metric, ylabel, title, output_path)`: reusable function for strip plot + mean line + shaded ±1 STD band, with 2 subplots (Block 1 left, Block 2 right), 4 channel groups per subplot
- [ ] Task 3.2 — Add text annotations showing `mean ± std` per channel group
- [ ] Task 3.3 — Call for both duration (`duration_min`, "Duration (min)") and voltage (`median_voltage`, "Median Voltage (V)")
- [ ] Task 3.4 — Add slight horizontal jitter on strip points to avoid overlap

**Files Modified:**
- `scripts/analyse_intervals.py` — Add plotting function and calls in `main()`

**Dependencies:** Phase 2

---

## Testing Plan

### Manual Verification
- [ ] Run script on all 70 sessions — confirm it completes without errors
- [ ] Check CSV row count (~560 expected for full coverage)
- [ ] Spot-check 3-4 sessions' durations against visual inspection of existing voltage PNGs (e.g., `2025-06-04_T29`: Block 1 ~18 min, Block 2 ~51 min on A1)
- [ ] Verify figures render with readable annotations, correct axis labels, and legend
- [ ] Check `status` column in CSV for edge-case sessions (e.g., `2026-01-26_T122` which had 0 long blocks on A1)

### Edge Cases
- [ ] Session with only 1 long block on some channels — should still produce data with `single_block` status
- [ ] Session with 3+ blocks due to brief interruptions — should merge close intervals and flag as `merged`
- [ ] Session with 0 blocks above threshold — should be skipped with warning

---

## Documentation Plan

- [ ] No documentation changes needed — standalone analysis script

---

## Rollback Plan

1. Delete `scripts/analyse_intervals.py`
2. Delete `backlogs_local_data/TILA_DATA_2_analysed/interval_analysis/` directory
3. No other files are modified

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Threshold 0.5V too low/high for some sessions | Low | Med | Threshold is configurable as constant; verified against 5 sample sessions during exploration |
| Event-based data causes incorrect duration/median | Med | Med | Resample to 1-second grid with forward-fill before computing stats |
| Merge logic creates false blocks | Low | Low | Only merge intervals with <2 min gap; log warnings for review |

---

## References

- Related Plans: `docs/development/plans/active/voltage-data-visualization.md`
- Related Plans: `docs/development/plans/active/fix-log-voltage-extraction.md`
- Data exploration: verified pattern across 70 sessions — Block 1 mean 20.4±8.6 min, Block 2 mean 54.1±12.5 min
