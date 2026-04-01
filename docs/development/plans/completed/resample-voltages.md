# Plan: Resample Voltages Timeseries

**Date:** 2026-03-31
**Author:** Claude
**Status:** Completed
**Completed:** 2026-04-01 09:29
**Branch:** `feature/resample-voltages`

---

## Overview

Add a `resample_voltages` preprocessing task that converts event-based voltage data (`voltages.csv`) into a regularly-sampled timeseries (`voltages_resampled.csv`) using zero-order hold interpolation. This requires first preserving the millisecond timestamp precision that the extraction step currently discards.

## Problem Statement

`voltages.csv` stores one row per voltage-change event with irregular timestamps. The `# interpolation: zero_order_hold` comment tells consumers to forward-fill between events, but every downstream task must implement this interpretation itself. A regularly-sampled timeseries with explicit samples is simpler to reason about, analyse, and plot. Additionally, millisecond precision is currently truncated to whole seconds, losing temporal resolution needed for accurate resampling.

## Goals

### In Scope
1. Preserve millisecond timestamp precision in `extract_session_data`
2. New task that computes per-session sampling rate from the data and resamples to a regular grid
3. Wire the new task into the preprocessing pipeline between `extract_session_data` and `tag_voltage_intervals`
4. Update `tag_voltage_intervals` to consume the resampled file

### Out of Scope
- Configurable/user-specified sampling rate (future enhancement)
- Restructuring `validate_session_metadata` placement in the pipeline
- Changes to the analysis workflow or plotting scripts

## Success Criteria

- [ ] `voltages.csv` timestamps include millisecond precision (e.g. `2024-01-15 10:30:45.123`)
- [ ] `voltages_resampled.csv` produced per session with regular timestamp spacing
- [ ] `voltages_resampled.csv` contains `# sampling_rate_hz: <value>` comment header
- [ ] Sampling rate derived from data falls within expected 10-200 Hz range
- [ ] `tag_voltage_intervals` reads `voltages_resampled.csv` and produces correct tagged output
- [ ] Full pipeline runs end-to-end without errors
- [ ] Resampling skips on second run without `force` (idempotency)

---

## Technical Design

### Approach

Compute the natural sampling rate from the data itself: for each channel, find the minimum non-zero time delta between consecutive voltage changes, then take the global minimum across all four channels. This gives the finest temporal resolution present in any channel. Resample all channels onto a regular grid at that rate using pandas `reindex` with `method="ffill"` (zero-order hold).

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Auto Fs from data (min delta) | Adapts per session; no config needed | May yield unexpected Fs from noise | **Chosen** — sanity-check warning mitigates risk |
| Fixed Fs (e.g. 100 Hz) | Simple, predictable | Doesn't match actual data rate; may over/under-sample | Rejected |
| User-configurable Fs via YAML | Flexible | Adds complexity; user must know correct value per session | Out of scope for now |

### Architecture Changes

- **New module**: `scripts/preprocessing/resample_voltages.py` — follows existing task contract pattern
- **Reuses**: `CommentedCsvReader` / `CommentedCsvWriter` from `tag_voltage_intervals.py` (imported directly)
- **Reuses**: `should_process_task()` / `clean_task_outputs()` from `utils/should_process_task.py`

```
Pipeline flow (after change):

filter_valid_sessions
  → extract_session_data        → voltages.csv (event-based, ms timestamps)
    → resample_voltages          → voltages_resampled.csv (regular grid)
      → tag_voltage_intervals    → voltages_tagged.csv
  → validate_session_metadata   (parallel, reads metadata only)
```

---

## Implementation Plan

### Phase 1: Preserve Millisecond Timestamps
**Goal:** Stop discarding sub-second precision so resampling can compute meaningful Fs.

- [x] Task 1.1 — Remove `.split(".")[0]` truncation in `build_voltage_df()`

**Files Modified:**
- `scripts/preprocessing/extract_session_data.py` — Line 424: change `ts = f"{ev['date']} {ev['time']}".replace(",", ".").split(".")[0]` to `ts = f"{ev['date']} {ev['time']}".replace(",", ".")`

**Dependencies:** None

### Phase 2: Create Resample Task Module
**Goal:** Implement the core resampling logic as a standalone task module.

- [x] Task 2.1 — Create `resample_voltages.py` with task contract docstring
- [x] Task 2.2 — Implement `compute_sampling_rate(df, channels)`:
  - Per channel: find rows where value changes (`diff().abs() > 0`), compute timestamp deltas, filter zeros, record min
  - Global min across channels → Fs
  - Warn if Fs outside [10, 200] Hz
  - Raise `ValueError` if no changes found (skip session upstream)
- [x] Task 2.3 — Implement `resample_session(df, fs)`:
  - Build `pd.date_range(start, end, freq=period)` regular grid
  - `df.set_index("timestamp").reindex(new_index, method="ffill").reset_index()`
- [x] Task 2.4 — Implement `run_resample_voltages(input_items, output_dir, force)`:
  - Resolve inputs (accept `voltages.csv` paths or session dirs)
  - Per session: idempotency check, compute Fs, resample, write with `# sampling_rate_hz: <value>` header
  - Return list of `voltages_resampled.csv` paths
- [x] Task 2.5 — Add standalone `main()` CLI entry point (argparse, same pattern as `tag_voltage_intervals`)

**Files Modified:**
- `scripts/preprocessing/resample_voltages.py` — **New file**

**Dependencies:** Phase 1

### Phase 3: Pipeline Integration
**Goal:** Wire the new task into the workflow and update downstream consumers.

- [x] Task 3.1 — Add `run_resample_voltages` export to `scripts/preprocessing/__init__.py`
- [x] Task 3.2 — Add `resample_voltages` entry to `config/preprocessing_workflow_dag.yaml` with `depends_on: [extract_session_data]`; update `tag_voltage_intervals` dependency to include `resample_voltages`
- [x] Task 3.3 — Insert `resample_voltages` stage in `scripts/preprocessing_workflow.py`; change `tag_voltage_intervals` to read `context["resampled_voltages"]`
- [x] Task 3.4 — Update `tag_voltage_intervals.py` file resolution: `voltages.csv` → `voltages_resampled.csv` (lines 420, 423, 427, 431, standalone glob ~519)

**Files Modified:**
- `scripts/preprocessing/__init__.py` — Add import/export
- `config/preprocessing_workflow_dag.yaml` — Add task + update dependency
- `scripts/preprocessing_workflow.py` — Add import, insert stage, rewire context
- `scripts/preprocessing/tag_voltage_intervals.py` — Change filename references

**Dependencies:** Phase 2

---

## Testing Plan

### Unit Tests
- [ ] `compute_sampling_rate` with known 100ms intervals → Fs = 10 Hz
- [ ] `compute_sampling_rate` with zero deltas mixed in → zeros filtered, correct Fs returned
- [ ] `compute_sampling_rate` with single-event session → `ValueError` raised
- [ ] `resample_session` with 3-row irregular df → output has regular spacing, values forward-filled

### Integration Tests
- [ ] Full pipeline on a test session → `voltages.csv` has ms timestamps, `voltages_resampled.csv` exists with regular grid, `voltages_tagged.csv` produced correctly

### Manual Verification
- [ ] Run pipeline on real data; inspect `voltages_resampled.csv` row count and timestamp spacing
- [ ] Compare `voltages_tagged.csv` output before/after to confirm interval detection still works

### Edge Cases
- [ ] Session with no voltage changes → skipped with warning, no output file
- [ ] Session with all events at same millisecond → all deltas are zero → `ValueError`, session skipped
- [ ] Very high Fs from noise (>200 Hz) → warning logged, file still produced
- [ ] Long session (2h at 100 Hz = 720k rows) → memory and file size are manageable (~30 MB)

---

## Documentation Plan

- [ ] Update `CLAUDE.md` if pipeline description changes significantly
- [ ] Update `docs/development/how-to-add-workflow-task.md` only if new patterns introduced (unlikely)

---

## Rollback Plan

1. Revert the `.split(".")[0]` removal in `extract_session_data.py` to restore second-precision timestamps
2. Remove `resample_voltages.py` and its `__init__.py` export
3. Revert `preprocessing_workflow.py` to wire `tag_voltage_intervals` back to `extracted_voltages`
4. Revert `tag_voltage_intervals.py` filename references back to `voltages.csv`
5. Remove `resample_voltages` entry from DAG YAML

No data migrations needed — `voltages_resampled.csv` files can simply be deleted.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Computed Fs outside 10-200 Hz range | Medium | Low | Log warning; file still produced; user can inspect |
| Sub-second timestamps break downstream plotting scripts | Low | Low | Pandas handles both formats; `drawstyle="steps-post"` unaffected |
| Large resampled files for long sessions | Low | Low | 720k rows at 100 Hz for 2h is ~30 MB — acceptable |
| Importing `CommentedCsvReader/Writer` from `tag_voltage_intervals` creates coupling | Low | Low | Classes are simple, stable, and side-effect-free; extract to shared utility later if needed |

---

## References

- Workflow task guide: `docs/development/how-to-add-workflow-task.md`
- Existing task patterns: `scripts/preprocessing/tag_voltage_intervals.py`
- Pipeline orchestrator: `scripts/preprocessing_workflow.py`
