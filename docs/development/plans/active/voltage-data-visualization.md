# Plan: Voltage Data Visualization

**Date:** 2026-03-18
**Author:** Basil
**Status:** In Progress
**Branch:** `feature/log-data-extractor`

---

## Overview

Create a script that generates per-session voltage timeline plots from the preprocessed CSV files in `backlogs_local_data/TILA_DATA_preprocess/`. Each plot shows the 4 electrode channels (A1, A2, B1, B2) over time with a fixed 8V Y-axis scale. This extends the log-data-extractor pipeline with a visualization step.

## Problem Statement

The `extract_log_data.py` script (Phase 1 of log-data-extractor) produces `voltages.csv` files per session, but there is no way to visually inspect the voltage profiles across sessions. A batch visualization script is needed to generate figures for all 48+ sessions for quality checks and analysis.

## Goals

### In Scope
1. Batch-generate one PNG figure per session CSV
2. Plot all 4 voltage channels (A1, A2, B1, B2) over time on a single axes
3. Fixed Y-axis range of 0–8V
4. All output PNGs saved flat in `backlogs_local_data/TILA_DATA_analysis/`

### Out of Scope
- Interactive plots or GUI integration
- Statistical analysis or aggregation across sessions
- Plotting metadata.json fields

## Success Criteria

- [ ] Script runs without errors on all 48 existing session CSVs
- [ ] 48 PNG files generated in `backlogs_local_data/TILA_DATA_analysis/`
- [ ] Each figure shows 4 labeled voltage traces with legend
- [ ] Y-axis fixed at 0–8V on all figures
- [ ] Figures are titled with the session folder name (e.g., `2026-02-26_T148`)

---

## Technical Design

### Approach

Single standalone script using `pandas` for CSV reading and `matplotlib` for plotting. Iterates over all `voltages.csv` files, generates one figure each, saves as PNG.

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| matplotlib static PNGs | Simple, no extra deps, batch-friendly | Not interactive | **Chosen** |
| pyqtgraph (already in project) | Interactive, consistent with GUI stack | Overkill for batch output, harder to save PNGs | Rejected |
| plotly HTML | Interactive output | Extra dependency, heavier files | Rejected |

### Architecture Changes

No architectural changes. Single new script file.

---

## Implementation Plan

### Phase 1: Create visualization script
**Goal:** Batch-generate voltage timeline plots for all session CSVs

- [ ] Create `scripts/plot_voltages.py`
- [ ] Read all `voltages.csv` files from `backlogs_local_data/TILA_DATA_preprocess/*/`
- [ ] For each CSV: parse timestamps, plot A1/A2/B1/B2 vs time
- [ ] Configure plot: Y-axis 0–8V, legend, title = folder name, axis labels
- [ ] Save each figure to `backlogs_local_data/TILA_DATA_analysis/{folder_name}_voltages.png`
- [ ] Create output directory if it doesn't exist

**Files Created:**
- `scripts/plot_voltages.py` — Main visualization script

**Dependencies:** None (uses pandas + matplotlib, both available in the `ti` conda env)

**Key details:**
- Figure size: ~12×5 inches for readability of timestamp axis
- 4 colored lines with legend (A1, A2, B1, B2)
- X-axis: auto-formatted datetime ticks via `matplotlib.dates`
- Close each figure after saving to avoid memory buildup over 48 iterations

---

## Testing Plan

### Manual Verification
- [ ] Run `python scripts/plot_voltages.py` — completes without errors
- [ ] Verify 48 PNG files exist in `backlogs_local_data/TILA_DATA_analysis/`
- [ ] Open 2–3 PNGs and confirm: 4 traces visible, legend correct, Y-axis is 0–8V, title matches session
- [ ] Check that voltage values in the plot visually match the CSV data (spot-check one session)

### Edge Cases
- [ ] Sessions with very few data points (some have ~44 rows) still produce readable plots
- [ ] Timestamps spanning different durations render correctly

---

## Documentation Plan

- [ ] No external docs needed — standalone utility script

---

## Rollback Plan

1. Delete `scripts/plot_voltages.py`
2. Delete `backlogs_local_data/TILA_DATA_analysis/` directory

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| matplotlib not installed in conda env | Low | Med | `pip install matplotlib` in ti env |
| Timestamp parsing issues on edge-case CSVs | Low | Low | pandas `parse_dates` handles ISO 8601 reliably |
