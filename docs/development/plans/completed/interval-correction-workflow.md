# Plan: Unified Interval Column + Correction GUI Rewire

**Date:** 2026-03-30
**Author:** Claude
**Status:** Completed
**Completed:** 2026-04-01
**Branch:** `feature/interval-correction-workflow`

---

## Overview

Add a median-based consensus `interval` column to the voltage tagging script (04_05) and rewire the correction GUI (06b) to be a manual correction workflow for that output. Currently the two scripts are disconnected — 06b uses script 06's output, not 04_05's.

## Problem Statement

Script 04_05 tags each channel independently, producing 4 interval columns with slightly different boundaries. There is no single "consensus" interval column for downstream use. Meanwhile, 06b is wired to a completely separate detection system (script 06's `interval_summary.csv`), making it impossible to manually correct the per-channel tagging output.

## Goals

### In Scope
1. Add a 5th `interval` column to `voltages_tagged.csv` using median consensus across the 4 per-channel columns
2. Rewire 06b to read `voltages_tagged.csv` and allow manual correction of the `interval` column boundaries
3. Output corrected intervals as `voltages_corrected.csv` (separate from auto-detected file)

### Out of Scope
- Modifying the per-channel detection algorithm in 04_05
- Updating downstream scripts (05, 07) to prefer `voltages_corrected.csv` (future work)
- Changing script 06's independent gap-based detection
- Adding new statistical output columns to the corrected file

## Success Criteria

- [ ] `voltages_tagged.csv` contains an `interval` column with values 0/1/2 representing median consensus
- [ ] Running 06b opens a GUI showing voltage traces with draggable block boundaries from the `interval` column
- [ ] Dragging a boundary and clicking Continue produces `voltages_corrected.csv` with updated `interval` column
- [ ] Clicking Skip on a session writes no corrected file for that session
- [ ] 06b has no dependency on script 06

---

## Technical Design

### Approach

**Median consensus** — row-wise `median(axis=1).astype(int)` over the 4 `{ch}_interval` columns. Truncation to int is conservative: a row is only tagged when >= 3 of 4 channels agree (median of `[0,0,1,1]` = 0.5 truncates to 0). This naturally unifies slightly different per-channel boundaries into a single consensus.

**Separate output file** — `voltages_corrected.csv` sits alongside `voltages_tagged.csv`. Auto-detected output remains reproducible; manual corrections are preserved separately.

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Row-wise median (truncated) | Simple, conservative, correct for 4-channel vote | 2-2 splits default to "not in interval" | **Chosen** — conservative is correct; GUI handles edge cases |
| Row-wise mode | Handles ties explicitly | Mode of `[0,0,1,1]` is ambiguous; more complex | Rejected |
| Row-wise round (instead of truncate) | Includes boundary rows on 2-2 splits | Can create single-sample noise artifacts | Rejected |
| Overwrite `voltages_tagged.csv` in 06b | Simpler file management | Destroys reproducible auto-detection | Rejected |

### Architecture Changes

No new modules. Two existing scripts modified:
- `04_05_tag_voltage_intervals.py` — small addition after tagging loop
- `06b_correct_intervals_gui.py` — medium rewrite: remove script 06 dependency, new input/output logic

---

## Implementation Plan

### Phase 1: Add `interval` column to 04_05
**Goal:** Produce a unified consensus interval column in `voltages_tagged.csv`

- [x] Task 1.1 — Add median computation after the per-channel tagging loop (after line 89)
- [x] Task 1.2 — Add validation: count distinct nonzero values in `interval`, warn if != 2
- [x] Task 1.3 — Update script docstring to mention the 5th column

**Files Modified:**
- `scripts/analysis/04_05_tag_voltage_intervals.py` — Add ~8 lines after tagging loop

**Dependencies:** None

### Phase 2: Rewire 06b to use 04_05 output
**Goal:** Make 06b a correction workflow for `voltages_tagged.csv`

- [x] Task 2.1 — Remove `importlib` block importing from script 06 (lines 20-33)
- [x] Task 2.2 — Define `CHANNELS` locally, inline CSV loading (replace `load_session`)
- [x] Task 2.3 — Replace `OUTPUT_DIR` / `SUMMARY_CSV` constants; scan for `*/voltages_tagged.csv`
- [x] Task 2.4 — Add `extract_boundaries(df)` helper: extract `(start, end, "Block N")` from `interval` column
- [x] Task 2.5 — Add `apply_corrections(df, corrected_intervals)` helper: reset and rewrite `interval` column
- [x] Task 2.6 — Add comment-preserving CSV write helper (reusable from 04_05 pattern)
- [x] Task 2.7 — Rewrite `main()`: loop over tagged files, extract boundaries, show GUI, save `voltages_corrected.csv`
- [x] Task 2.8 — Update script docstring

**Files Modified:**
- `scripts/analysis/04_05b_correct_intervals_gui.py` — Medium rewrite (renamed from 06b)

**Dependencies:** Phase 1 (needs `interval` column to exist)

**Unchanged code:**
- `DraggableVLine` class — works as-is
- `launch_correction_gui()` — works as-is (accepts `(start, end, label)` tuples)

---

## Testing Plan

### Manual Verification
- [ ] Run `python scripts/analysis/04_05_tag_voltage_intervals.py` — confirm `voltages_tagged.csv` files now contain the `interval` column
- [ ] Spot-check a `voltages_tagged.csv`: the `interval` column should match majority vote of 4 per-channel columns
- [ ] Run `python scripts/analysis/06b_correct_intervals_gui.py` — verify GUI opens with correct block boundaries
- [ ] Drag a boundary, click Continue — verify `voltages_corrected.csv` is written with updated `interval` column
- [ ] Click Skip — verify no `voltages_corrected.csv` is written for that session
- [ ] Verify per-channel `{ch}_interval` columns are preserved unchanged in corrected output

### Edge Cases
- [ ] Session with only 1 interval detected — GUI should show 1 block, correction should work
- [ ] Session with 0 intervals — GUI should skip with a message
- [ ] Session where channels disagree at boundaries — median column should show conservative consensus

---

## Documentation Plan

- [ ] Update script docstrings (covered in implementation tasks)

---

## Rollback Plan

1. Both scripts are standalone analysis tools — reverting is simply `git revert` on the commit
2. No data migration needed — `voltages_corrected.csv` is a new file, `voltages_tagged.csv` format is additive (new column)
3. No downstream scripts depend on the `interval` column yet

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Median produces unexpected values at noisy boundaries | Low | Low | Truncation is conservative; GUI allows manual correction |
| Existing `voltages_tagged.csv` files lack `interval` column | Med | Low | Re-run 04_05 to regenerate; 06b should check column exists |
