# Plan: Align Analysis Tasks with `correct_intervals` Output

**Date:** 2026-04-01
**Author:** Basil
**Status:** Completed
**Completed:** 2026-04-01 13:41
**Branch:** `feature/integrate-correct-intervals-gui`

---

## Overview

The preprocessing pipeline now ends with `correct_intervals` (task 6), which
produces `voltages_corrected.csv` + `validated.flag` for human-validated sessions
and `discarded.flag` for bad data.  The analysis workflow orchestrator already
consumes these correctly, but individual analysis task modules still hardcode
`voltages.csv` references that bypass human corrections and discard markers.

## Problem Statement

`sex_based_voltage_analysis.py` line 496 hardcodes `voltages.csv` and uses
gap-based interval detection, completely ignoring human-corrected boundaries
from `correct_intervals`.  Discarded sessions are also processed because
`discarded.flag` is never checked.  The standalone `main()` entry points of
`plot_session_voltages.py` and `analyse_stim_intervals.py` have similar
(lower-severity) issues with the CSV priority chain.

## Goals

### In Scope
1. Make `analyse_voltage_changes()` in `sex_based_voltage_analysis.py` use the
   CSV priority chain (`corrected > tagged > raw`) and respect `discarded.flag`
2. Use interval-column-based block extraction when source is `corrected` or
   `tagged`, falling back to gap-based detection only for raw CSVs
3. Fix standalone `main()` in `plot_session_voltages.py` to use the priority
   chain instead of globbing only `voltages_corrected.csv`
4. Fix standalone `main()` in `analyse_stim_intervals.py` to filter sessions
   via `resolve_session_csv()` instead of checking for `voltages.csv`

### Out of Scope
- Workflow orchestrator changes (`analysis_workflow.py` is already correct)
- Full contract refactoring (covered by pending `align-analysis-task-contracts`)
- Pre-filtering discarded sessions in `_resolve_session_dirs()` (works correctly)
- Changing analysis logic or output format

## Success Criteria

- [ ] `analyse_voltage_changes()` resolves CSVs via `resolve_session_csv()`
- [ ] `analyse_voltage_changes()` uses `extract_blocks_from_interval_column()`
      for corrected/tagged sources, gap-based detection only for raw
- [ ] `analyse_voltage_changes()` skips sessions with `discarded.flag`
- [ ] `plot_session_voltages.py` standalone `main()` uses priority chain and
      skips discarded sessions
- [ ] `analyse_stim_intervals.py` standalone `main()` uses `resolve_session_csv()`
      for session filtering
- [ ] `pytest` passes with no regressions
- [ ] Standalone `--help` exits cleanly for all three task modules

---

## Technical Design

### Approach

Reuse two existing helpers already defined in `analyse_stim_intervals.py`:

- **`resolve_session_csv(session_dir)`** (line 205-219) — returns the best
  available CSV path using priority `corrected > tagged > raw`, returns `None`
  for discarded sessions
- **`extract_blocks_from_interval_column(df)`** (line 222-242) — extracts block
  boundaries from the `interval` column present in corrected/tagged CSVs

No new modules or helpers are needed.  The fix wires existing code paths
through these helpers instead of bypassing them.

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Reuse existing helpers from `analyse_stim_intervals` | Zero new code, consistent behavior | Cross-module import | **Chosen** |
| Duplicate `resolve_session_csv` into `sex_based_voltage_analysis` | No cross-dependency | Code duplication, drift risk | Rejected |
| Defer entirely to `align-analysis-task-contracts` | Smaller scope now | Leaves critical bug (ignoring human corrections) unfixed | Rejected |

### Architecture Changes

No new modules.  Existing cross-module imports are extended:

```
sex_based_voltage_analysis.py
  └── already imports from analyse_stim_intervals:
        load_session, detect_active_intervals, classify_intervals
      adds:
        resolve_session_csv, extract_blocks_from_interval_column
```

---

## Implementation Plan

### Phase 1: Fix `analyse_voltage_changes()` in `sex_based_voltage_analysis.py`
**Goal:** Make the voltage change analysis respect `correct_intervals` output

- [x] Add `resolve_session_csv` and `extract_blocks_from_interval_column` to
      the existing import block from `analyse_stim_intervals` (line 49-53)
- [x] Replace hardcoded `voltages.csv` lookup (lines 496-499) with
      `resolve_session_csv(preprocess_dir / session)` call; skip when result
      is `None` (discarded or missing)
- [x] Replace gap-based block detection (lines 508-509) with
      interval-column-aware logic: use `extract_blocks_from_interval_column(df)`
      when source is `corrected` or `tagged`; fall back to
      `detect_active_intervals` + `classify_intervals` only for `raw` source
      or when no `interval` column exists
- [x] Update module docstring (line 22) to reflect the CSV priority chain

**Files Modified:**
- `scripts/analysis/sex_based_voltage_analysis.py` — import, CSV resolution,
  block detection, docstring

**Dependencies:** None

### Phase 2: Fix standalone `main()` entry points
**Goal:** Align secondary entry points with the priority chain

- [x] `plot_session_voltages.py`: replace `glob("*/voltages_corrected.csv")`
      (line 226) with directory iteration + `resolve_session_csv()` per session;
      import `resolve_session_csv` from `analyse_stim_intervals`; update error
      message (line 228)
- [x] `analyse_stim_intervals.py`: replace `(d / "voltages.csv").exists()`
      filter (line 525) with `resolve_session_csv(d)[0] is not None`
      (function already defined in the same file)

**Files Modified:**
- `scripts/analysis/plot_session_voltages.py` — standalone `main()`, new import
- `scripts/analysis/analyse_stim_intervals.py` — standalone `main()` filter

**Dependencies:** None (independent of Phase 1, but logically ordered after)

---

## Testing Plan

### Unit Tests
- [ ] Existing `pytest` suite passes without modification

### Integration Tests
- [ ] `python scripts/analysis/plot_session_voltages.py --help` exits cleanly
- [ ] `python scripts/analysis/analyse_stim_intervals.py --help` exits cleanly
- [ ] `python scripts/analysis/sex_based_voltage_analysis.py --help` exits cleanly

### Manual Verification
- [ ] Run `python scripts/analysis_workflow.py` end-to-end against real data
- [ ] Confirm `voltages_corrected.csv` is used where available
- [ ] Confirm discarded sessions are skipped (check console warnings)
- [ ] Confirm output files are produced (same set of CSVs and PNGs as before)

### Edge Cases
- [ ] Session with `discarded.flag` — verify skipped in all three tasks
- [ ] Session with only `voltages_tagged.csv` (no corrected) — verify tagged
      is used with interval-column extraction
- [ ] Session with only `voltages.csv` (no corrected, no tagged) — verify
      gap-based detection fallback works
- [ ] Corrected CSV missing `interval` column — verify fallback to gap detection

---

## Documentation Plan

- [ ] Update module docstring in `sex_based_voltage_analysis.py` (line 22)
- [ ] No README/CLAUDE.md changes needed

---

## Rollback Plan

1. All changes are on the existing `feature/integrate-correct-intervals-gui` branch
2. No data migrations or schema changes
3. Git revert of the relevant commits if issues found

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `sex_based_voltage_analysis` output changes due to different interval boundaries | High (expected) | Low — change is desired | Compare outputs before/after; difference reflects human corrections being applied |
| Cross-module import from `analyse_stim_intervals` creates coupling | Low | Low — import already exists (4 symbols) | Adding 2 more to an existing import block |
| Standalone `main()` breaks for `plot_session_voltages` | Low | Low — secondary entry point | Smoke test with `--help` |
