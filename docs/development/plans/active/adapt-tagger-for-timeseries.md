# Plan: Adapt Interval Tagger for Regularly-Sampled Timeseries Input

**Date:** 2026-04-01
**Author:** Claude
**Status:** In Progress
**Branch:** `feature/flatten-tag-voltage-intervals`

---

## Overview

Refactor `IntervalTagger` in `tag_voltage_intervals.py` to leverage the known sampling rate from `voltages_resampled.csv`, replacing timestamp arithmetic with index arithmetic. Also fix `resample_voltages.py` which currently omits the `# sampling_rate_hz:` comment header from its output.

## Problem Statement

Commit `8847683` introduced `resample_voltages`, producing regularly-sampled `voltages_resampled.csv` files. The filename references and DAG wiring in `tag_voltage_intervals.py` were updated, but the algorithm internals still treat input as event-based data — using `df["timestamp"]` subtraction for durations and row-by-row timestamp iteration for gap detection. This is unnecessarily complex when the sampling rate is known and constant.

Additionally, `resample_voltages.py` line 248 writes `comments=[]`, discarding the `# sampling_rate_hz:` header that downstream tasks need.

## Goals

### In Scope
1. Fix `resample_voltages.py` to emit `# sampling_rate_hz: <value>` in output
2. Parse `sampling_rate_hz` from input file headers in the tagger
3. Replace timestamp-based duration and gap calculations with index arithmetic using known `fs`
4. Preserve `time_ms` column through the tagging pipeline
5. Update docstrings to reflect timeseries input semantics

### Out of Scope
- Changing the detection algorithm logic (thresholds, merge rules, consensus vote)
- Modifying DAG configuration or workflow wiring (already correct)
- Extracting shared code to `src/preprocessing/` (covered by `align-preprocessing-contracts` plan)
- Changes to `IntervalPlotSaver` (already index/timestamp agnostic)

## Success Criteria

- [ ] `voltages_resampled.csv` files contain `# sampling_rate_hz: <value>` header
- [ ] `tag_voltage_intervals` reads and uses `fs` from input header
- [ ] `IntervalTagger` methods use `(end - start) * sample_period` instead of timestamp subtraction
- [ ] `_has_sustained_zero_gap` uses sample counting instead of row-by-row timestamp comparison
- [ ] `voltages_tagged.csv` output preserves `time_ms` column and `# sampling_rate_hz:` header
- [ ] Same intervals are detected as before (no behavioural change)

---

## Technical Design

### Approach

Inject `fs` into `IntervalTagger` at construction time (one instance per session, since `fs` varies). Convert all timestamp-based duration calculations to `row_count * (1/fs)`. This follows the project's DI pattern — `fs` is parsed from the file header by the I/O layer and passed explicitly to the domain object.

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Inject `fs` via constructor (DI) | Clean separation of I/O and logic; testable; consistent with project patterns | New tagger instance per session | **Chosen** |
| Parse `fs` inside `IntervalTagger.tag()` | Self-contained | Couples I/O to domain logic; violates SRP | Rejected |
| Keep timestamp arithmetic, just update filenames | Zero refactoring | Misses simplification opportunity; keeps unnecessary `timestamps` parameter threading | Rejected |

### Architecture Changes

No new modules or classes. Changes are internal to existing classes:

```
CommentedCsvReader
  + parse_sampling_rate(comments) -> float   [new static method]

IntervalTagger.__init__(cfg, fs)             [add fs parameter]
  _tag_channel      — index arithmetic for duration filter
  _has_sustained_zero_gap — sample counting, drop timestamps param
  _merge_blocks_by_gap    — drop timestamps param
```

---

## Implementation Plan

### Phase 1: Fix Comment Header in `resample_voltages.py`
**Goal:** Ensure `voltages_resampled.csv` files contain the sampling rate metadata

**Tasks:**
- [x] Task 1.1 — Change line 248 from `writer.write(resampled_df, [], out_path)` to write `[f"# sampling_rate_hz: {fs}\n"]` as comments

**Files Modified:**
- `scripts/preprocessing/resample_voltages.py` — Pass sampling rate comment to writer

**Dependencies:** None

### Phase 2: Add Header Parsing to `CommentedCsvReader`
**Goal:** Provide a reusable way to extract `sampling_rate_hz` from comment headers

**Tasks:**
- [x] Task 2.1 — Add `@staticmethod parse_sampling_rate(comments: list[str]) -> float` that extracts the value or raises `ValueError`

**Files Modified:**
- `scripts/preprocessing/tag_voltage_intervals.py` — Add static method to `CommentedCsvReader`

**Dependencies:** None (independent of Phase 1)

### Phase 3: Refactor `IntervalTagger` for Index Arithmetic
**Goal:** Replace all timestamp-based duration calculations with `fs`-aware index arithmetic

**Tasks:**
- [x] Task 3.1 — Add `fs: float` parameter to `IntervalTagger.__init__`, store `self._fs` and `self._sample_period`
- [x] Task 3.2 — Refactor `_has_sustained_zero_gap`: remove `timestamps` parameter, compute `min_gap_samples = int(min_gap_min * 60 * fs)`, count consecutive near-zero rows with early return
- [x] Task 3.3 — Refactor `_merge_blocks_by_gap`: remove `timestamps` parameter, update call to `_has_sustained_zero_gap`
- [x] Task 3.4 — Refactor `_tag_channel`: replace timestamp subtraction in duration filter with `(e - s) * self._sample_period`, remove `df["timestamp"]` from `_merge_blocks_by_gap` call

**Files Modified:**
- `scripts/preprocessing/tag_voltage_intervals.py` — `IntervalTagger` class methods

**Dependencies:** None (independent of Phase 1-2, but must be wired in Phase 4)

### Phase 4: Wire `fs` Through the Task Function
**Goal:** Connect header parsing to tagger construction in `run_tag_voltage_intervals`

**Tasks:**
- [x] Task 4.1 — Move `IntervalTagger` construction inside the per-session loop
- [x] Task 4.2 — After `reader.read(csv_path)`, call `CommentedCsvReader.parse_sampling_rate(comments)` to get `fs`
- [x] Task 4.3 — Construct `IntervalTagger(cfg, fs=fs)` per session

**Files Modified:**
- `scripts/preprocessing/tag_voltage_intervals.py` — `run_tag_voltage_intervals` function

**Dependencies:** Phases 2 and 3

### Phase 5: Update Docstrings
**Goal:** Reflect timeseries input semantics in documentation

**Tasks:**
- [x] Task 5.1 — Update module docstring: clarify input is regularly-sampled timeseries
- [x] Task 5.2 — Remove "(unchanged from 04_05_tag_voltage_intervals.py)" comments
- [x] Task 5.3 — Update method docstrings for refactored methods

**Files Modified:**
- `scripts/preprocessing/tag_voltage_intervals.py` — Docstrings only

**Dependencies:** Phase 3

---

## Testing Plan

### Manual Verification
- [ ] Run `resample_voltages --force` on 2-3 sessions, confirm `# sampling_rate_hz:` header in output
- [ ] Run `tag_voltage_intervals --force` on same sessions, confirm:
  - `voltages_tagged.csv` has `time_ms` column
  - `# sampling_rate_hz:` header preserved
  - Same interval counts as before the refactor
- [ ] Run full `preprocessing_workflow.py` end-to-end

### Edge Cases
- [ ] Session with no existing `# sampling_rate_hz:` header — clear `ValueError` message directing user to re-run `resample_voltages --force`
- [ ] Session where `fs` yields fractional `min_gap_samples` — verify `int()` truncation doesn't miss a valid gap (at 10-20 Hz with 10-min gaps this is 6000-12000 samples, off-by-one is negligible)

---

## Documentation Plan

- [ ] No external documentation changes needed — internal refactor only

---

## Rollback Plan

1. Revert changes to `tag_voltage_intervals.py` and `resample_voltages.py`
2. No data migration needed — output file format is unchanged

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Existing `voltages_resampled.csv` files lack header | High (current bug) | Low | `parse_sampling_rate` raises clear error; user re-runs `resample_voltages --force` |
| `CommentedCsvReader` API change breaks `resample_voltages.py` | None | N/A | Only adding a new static method; `read()` signature unchanged |
| Integer rounding in `min_gap_samples` | Low | Low | At 10+ Hz, 10-min gaps are 6000+ samples; off-by-one negligible |

---

## References

- Related commit: `8847683` (feat: add resample_voltages preprocessing task)
- Related plans: `docs/development/plans/pending/tag-voltage-intervals.md` (original tagger plan)
- Related plans: `docs/development/plans/pending/align-preprocessing-contracts.md` (future extraction to `src/`)
