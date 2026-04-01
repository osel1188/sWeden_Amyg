# Plan: Fix .log Voltage Extraction

**Date:** 2026-03-18
**Author:** Claude Code
**Status:** Completed
**Completed:** 2026-04-01
**Branch:** `feature/log-data-extractor`

---

## Overview

Revise `.log` voltage extraction in `scripts/analysis/03_extract_session_data.py` to use **only** "Ramp finished" lines as the voltage data source. The current implementation uses three regex sources (`RAMP_RE`, `RAMP_FINISHED_RE`, `RAMP_DETAIL_RE`) which produces incorrect/noisy voltage timeseries. Only "Ramp finished" lines contain ground-truth voltage snapshots.

## Problem Statement

The current parser adds voltage events from three sources, but only "Ramp finished" lines provide accurate post-ramp voltage snapshots. The other two sources (`RAMP_RE` manager commands, `RAMP_DETAIL_RE` ramp-start states) inject target/intermediate voltages that don't represent actual measured state, polluting the output.

## Goals

### In Scope
1. Use only `RAMP_FINISHED_RE` matches for voltage event extraction
2. Keep `RAMP_RE` matching for metadata only (ramp rate) — stop adding its events to `ramp_events`
3. Remove `RAMP_DETAIL_RE` voltage event generation from `ramp_events`

### Out of Scope
- Changes to CSV session extraction
- Modifying the application's logging

## Success Criteria

- [ ] `voltages.csv` contains only events from "Ramp finished" lines
- [ ] No voltage events from `RAMP_RE` or `RAMP_DETAIL_RE` in output
- [ ] `metadata.json` still captures `ramp_rate_v_per_s` (from `RAMP_RE`)
- [ ] Batch run on all sessions completes without errors

---

## Technical Design

### Approach

Simplify `parse_log_file()` to use a single voltage source. Each "Ramp finished in Xs. Final Voltages: [...]" line already contains the definitive channel voltages after a ramp completes. The duplicate "TISystem (...): Ramp finished. Voltages: [...]" line (without "Final") is excluded by the current regex, avoiding duplicates.

### Changes to `parse_log_file()` (lines 143–190)

**1. `RAMP_RE` block (lines 144–158):** Keep the match for `ramp_rate_v_per_s` metadata extraction. Remove the `ramp_events.append(...)` call.

**2. `RAMP_DETAIL_RE` block (lines 174–190):** Remove the entire block — it only contributed voltage events, no metadata.

**3. `RAMP_FINISHED_RE` block (lines 161–171):** Already correct — keep as-is. This is now the sole source of voltage events.

**4. Cleanup:** Remove `RAMP_DETAIL_RE` regex constant and `_parse_holding_list()` helper if no longer referenced.

---

## Implementation Plan

### Phase 1: Restrict voltage extraction to "Ramp finished" only
**Goal:** Clean, accurate voltage timeseries from a single source
**Started:** 2026-03-18
**Completed:** 2026-03-18

- [x] Task 1.1 — In `RAMP_RE` match block: remove `ramp_events.append(...)`, keep metadata extraction
- [x] Task 1.2 — Remove `RAMP_DETAIL_RE` match block from parsing loop
- [x] Task 1.3 — Remove `RAMP_DETAIL_RE` regex constant and `_parse_holding_list()` helper
- [x] Task 1.4 — Verify `RAMP_FINISHED_RE` block is unchanged (sole voltage source)

**Files Modified:**
- `scripts/analysis/03_extract_session_data.py` — Net deletion of ~20 lines

**Dependencies:** None

---

## Testing Plan

### Manual Verification
- [ ] Run: `python scripts/analysis/03_extract_session_data.py backlogs_local_data/TILA_DATA_0_primary/2025-11-24_T77/2025-11-24_PM.log`
- [ ] Check `voltages.csv` — every row should correspond to a "Ramp finished in Xs. Final Voltages:" line in the log
- [ ] Verify `metadata.json` still has `ramp_rate_v_per_s`
- [ ] Run batch: `python scripts/analysis/03_extract_session_data.py` — no errors across all sessions

---

## Rollback Plan

1. `git revert` the commit
2. Re-run extraction

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Fewer events than before (only snapshots, no ramp-starts) | Expected | None — this is the desired behavior | Ground-truth snapshots are what we want |
| Sessions with no "Ramp finished" lines | Low | Med | These would produce empty voltages.csv — acceptable for edge cases |

---

## References

- `RAMP_FINISHED_RE` regex: `scripts/analysis/03_extract_session_data.py:40-43`
- `_parse_voltage_list()`: `scripts/analysis/03_extract_session_data.py:315-322`
- Example log: `backlogs_local_data/TILA_DATA_0_primary/2025-11-24_T77/2025-11-24_PM.log`
