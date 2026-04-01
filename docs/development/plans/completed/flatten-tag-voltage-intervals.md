# Plan: Flatten tag_voltage_intervals.py

**Date:** 2026-04-01
**Author:** Basil
**Status:** Completed
**Completed:** 2026-04-01 12:10
**Branch:** `feature/flatten-tag-voltage-intervals`

---

## Overview

Refactor `scripts/preprocessing/tag_voltage_intervals.py` to replace processing classes with flat module-level functions. The file currently wraps logic in `IntervalTagger`, `IntervalPlotSaver`, `CommentedCsvReader`, and `CommentedCsvWriter` classes plus `ChannelResult`/`SessionResult` result dataclasses. Sibling preprocessing scripts use flat functions — this refactor aligns the file with that convention.

## Problem Statement

The script nests algorithm logic inside classes that hold config/state as instance attributes (`self._cfg`, `self._fs`). This makes the processing flow harder to follow: the reader must mentally track class instantiation, constructor parameters, and method dispatch rather than reading a linear sequence of function calls. The I/O classes are stateless wrappers around single functions. The result dataclasses exist only to shuttle data to a logging formatter.

## Goals

### In Scope
1. Replace all processing classes with module-level functions
2. Remove `ChannelResult` and `SessionResult` dataclasses
3. Update the sole external consumer (`resample_voltages.py`)

### Out of Scope
- Algorithm changes (detection logic, thresholds, consensus voting)
- Moving the I/O functions to a shared utility module
- Adding or modifying tests

## Success Criteria

- [ ] No classes remain except `TagConfig` (pure config dataclass)
- [ ] `resample_voltages.py` imports and calls the new function names
- [ ] All algorithm logic is preserved identically (structural refactor only)
- [ ] `pytest` passes with no regressions
- [ ] Grep for removed class names returns zero hits

---

## Technical Design

### Approach

Convert each class method to a module-level function. Replace `self._cfg`/`self._fs` with explicit `cfg`/`fs` parameters. Replace `SessionResult` with a plain `dict[str, int]` mapping channel names + `"consensus"` to interval counts. Move class constants to module level.

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Flat functions with explicit params | Matches project style, easy to read | Slightly more params per call | **Chosen** |
| Keep I/O classes, flatten only tagger | Less churn | Inconsistent — I/O classes are stateless | Rejected |
| Extract I/O to shared `utils/` module | DRY across scripts | Scope creep, separate concern | Out of scope |

### Architecture Changes

No new modules. Two files modified. Public API changes:

| Old (class-based) | New (function-based) |
|--------------------|----------------------|
| `CommentedCsvReader().read(path)` | `read_commented_csv(path)` |
| `CommentedCsvReader.parse_sampling_rate(c)` | `parse_sampling_rate(comments)` |
| `CommentedCsvWriter().write(df, c, p)` | `write_commented_csv(df, comments, path)` |
| `IntervalTagger(cfg, fs).tag(df)` | `tag_intervals(df, cfg, fs)` → `dict[str, int]` |
| `IntervalPlotSaver(cfg).save(df, n, p)` | `save_interval_plot(df, cfg, name, path)` |
| `ChannelResult`, `SessionResult` | Removed |
| `_format_result(result)` | `_log_tagging_results(name, counts, channels)` |

---

## Implementation Plan

### Phase 1: Refactor (single phase)
**Goal:** Flatten all classes into module-level functions, update consumer
**Started:** 2026-04-01
**Completed:** 2026-04-01

**Tasks:**
- [x] Task 1 — Replace `CommentedCsvReader`/`CommentedCsvWriter` with `read_commented_csv()`, `write_commented_csv()`, `parse_sampling_rate()`
- [x] Task 2 — Replace `IntervalTagger` with `tag_intervals()` + private helpers (`_tag_channel`, `_find_raw_on_blocks`, `_has_sustained_zero_gap`, `_merge_blocks_by_gap`, `_expand_to_zero`, `_compute_consensus`), all taking explicit `cfg`/`fs` params
- [x] Task 3 — Replace `IntervalPlotSaver` with `save_interval_plot()` + `_get_interval_spans()`, `_shade_intervals()`; move class constants to module level
- [x] Task 4 — Remove `ChannelResult`/`SessionResult`; replace `_format_result()` with `_log_tagging_results(session_name, counts, channels)`
- [x] Task 5 — Update `run_tag_voltage_intervals()` to call new functions directly
- [x] Task 6 — Update `resample_voltages.py`: change imports to `read_commented_csv, write_commented_csv`; replace `reader.read()`/`writer.write()` calls

**Files Modified:**
- `scripts/preprocessing/tag_voltage_intervals.py` — full rewrite (same sections, flat functions)
- `scripts/preprocessing/resample_voltages.py` — update imports (L33-36) + 4 call-sites

**Dependencies:** None

---

## Testing Plan

### Unit Tests
- [ ] `pytest` — confirm existing tests pass without modification

### Manual Verification
- [ ] Grep codebase for `CommentedCsvReader`, `CommentedCsvWriter`, `IntervalTagger`, `IntervalPlotSaver`, `ChannelResult`, `SessionResult` — zero hits outside plan docs
- [ ] Run `python scripts/preprocessing/tag_voltage_intervals.py --force` on test data — identical output

---

## Rollback Plan

Pure refactor of two files on a feature branch. Rollback = revert the branch.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Missed import consumer | Low | Med | Grep for all class names before starting |
| Algorithm drift during rewrite | Low | High | Copy method bodies verbatim, only remove `self` and replace `self._cfg`/`self._fs` |
