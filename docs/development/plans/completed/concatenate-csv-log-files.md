# Plan: Concatenate Multiple CSV Log Files in parse_csv_session

**Date:** 2026-04-01
**Author:** Claude Code
**Status:** Completed
**Completed:** 2026-04-01 13:33
**Branch:** `feature/concatenate-csv-log-files`

---

## Overview

Fix `parse_csv_session` to process all `*keysight_edu_comms.csv` and `*gui_status_messages.csv` files in a session directory, treating them as one concatenated log ordered by filename datetime prefix. Currently only the first file is used, silently discarding data from subsequent log files.

## Problem Statement

Some sessions contain multiple CSV log files (e.g. when the GUI was restarted mid-session or logging rolled over). `parse_csv_session` globs and sorts these files correctly but then only opens `csv_files[0]`, discarding all other files. The same issue affects `*gui_status_messages.csv`. This causes incomplete voltage timeseries and potentially missing metadata for affected sessions.

## Goals

### In Scope
1. Process all `*keysight_edu_comms.csv` files per session as one concatenated log
2. Process all `*gui_status_messages.csv` files per session, merging metadata
3. Track all contributing source files in output metadata

### Out of Scope
- Deduplication of overlapping timestamps across files
- Changes to `.log` format parsing (log sessions are always single-file)
- Changes to the output schema beyond `source_file` becoming a list for CSV sessions

## Success Criteria

- [ ] Sessions with multiple CSV files produce a `voltages.csv` containing data from all files
- [ ] Timestamps in output span the full time range of all source files
- [ ] `metadata.json` lists all contributing CSV filenames
- [ ] Single-file sessions produce identical output to before (no regression)
- [ ] `pytest` passes

---

## Technical Design

### Approach

Wrap the existing single-file processing in a loop over all sorted files. The accumulation variables (`ramp_events`, `frequencies`, `serials`) are already initialized before the file-reading block, so a loop naturally concatenates data in chronological order (filenames sort lexicographically = chronologically due to `YYYY-MM-DD_HH-MM-SS` prefix).

For GUI status files, iterate at the call site and merge with "last non-null wins" semantics.

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Loop over files in-place | Minimal change, no new abstractions | None significant | **Chosen** |
| Concatenate files to temp file first | Single open() call | Unnecessary I/O, temp file cleanup | Rejected |
| Change `_parse_gui_status` signature to accept list | Cleaner API | Over-engineering for a 2-line call site | Rejected |

### Architecture Changes

None. No new modules, classes, or interfaces. Three localized edits in one file.

---

## Implementation Plan

### Phase 1: Multi-file Processing
**Goal:** Process all CSV files per session instead of just the first

**Tasks:**
- [x] Task 1.1 — Wrap keysight CSV `open()` block in a `for csv_path in csv_files:` loop
- [x] Task 1.2 — Replace single-file `_parse_gui_status(gui_files[0])` call with a loop merging results from all GUI files
- [x] Task 1.3 — Add `source_files` list to CSV metadata, update `_process_session` to use it

**Files Modified:**
- `scripts/preprocessing/extract_session_data.py` — 3 localized edits (~15 lines changed)

**Dependencies:** None

---

## Testing Plan

### Manual Verification
- [ ] Run on a session with multiple CSV files — `voltages.csv` contains data from all files
- [ ] Run on a single-CSV-file session — output identical to before
- [ ] Inspect `metadata.json` — `source_file` lists all contributing filenames
- [ ] Spot-check: timestamps span full time range of all source files

### Automated Tests
- [ ] Run `pytest` — no regressions

### Edge Cases
- [ ] Session with one CSV file — behaves identically to current code
- [ ] Session with no `gui_status_messages.csv` — metadata has null target_voltages (unchanged)
- [ ] Session with multiple GUI CSVs where only the second has a condition — condition is captured

---

## Documentation Plan

- [ ] No documentation changes needed — this is a bug fix, not a feature

---

## Rollback Plan

1. Single file modified — revert the one commit
2. No schema changes, no config changes, no external state

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Duplicate rows from overlapping CSV files | Low | Low | Files are sequential logs, not overlapping; if it occurs, downstream dedup handles it |
| Changing `source_file` from string to list breaks downstream | Low | Med | Check all readers of `metadata.json` for `source_file` usage |

---

## References

- Parent plan: `docs/development/plans/completed/csv-data-extractor.md`
- Implementation file: `scripts/preprocessing/extract_session_data.py` (lines 321-411)
