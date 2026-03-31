# Plan: Fix .log Voltage Extraction

**Date:** 2026-03-18
**Author:** Claude Code
**Status:** In Progress
**Branch:** `feature/log-data-extractor`

---

## Overview

Fix the `.log` parsing in `scripts/extract_log_data.py` so that protocol start/stop ramps and all single-channel ramps are captured as voltage events. Currently only manager-level `ramp_channel_voltage()` calls are parsed, missing the most important data: the full-protocol ramps and system-level ramp details.

## Problem Statement

The `.log` extraction produces ~31 sparse voltage events per session vs ~15,000 for CSV sessions. The output `voltages.csv` is missing:

1. **Protocol start ramps** — when `start_protocol()` ramps all channels from 0V to target (~4.5V) over 60s, no voltage events are captured because the code path (`system.start()` -> `_execute_ramp()`) does not produce the manager-level "Ramping channel" log line that `RAMP_RE` matches.
2. **Protocol stop ramps** — same issue; `stop_protocol()` ramps all channels to 0V without manager-level log lines.
3. **Accurate voltage snapshots** — the "Ramp finished" lines (e.g., `Final Voltages: [A1: 4.50V, A2: 4.60V]`) provide ground-truth voltage states but are not parsed.

The data that IS captured (individual channel adjustments via `ramp_channel_voltage()`) is correct but represents only a fraction of the session's voltage timeline.

## Goals

### In Scope
1. Parse "Ramp finished" lines from `system.py` as definitive voltage snapshot events
2. Parse "Ramping X from YV to ZV" lines from `system.py` as ramp-start events (with held channel voltages)
3. Produce a `voltages.csv` that captures all voltage state changes throughout a session
4. Keep existing `RAMP_RE` parsing as a complementary source

### Out of Scope
- Interpolating intermediate voltage steps between ramp start and finish
- Modifying the application's logging to add more detail
- Changes to CSV session extraction (already working correctly)

## Success Criteria

- [ ] `voltages.csv` for a .log session contains protocol start ramp events (0V -> target)
- [ ] `voltages.csv` contains protocol stop ramp events (target -> 0V)
- [ ] `voltages.csv` contains individual channel adjustment events (already working)
- [ ] Event count increases significantly (from ~31 to ~60+ for a typical session)
- [ ] All 4 channel voltages are accurate at each snapshot point (verified against raw log)

---

## Technical Design

### Approach

Add two new regex patterns to parse system-level log lines that the script currently ignores. These lines are produced by `system.py` during all ramp types (protocol start, protocol stop, single-channel adjustments) and provide rich voltage data including start/end voltages, durations, and the state of non-ramping channels.

### New Log Lines to Parse

**1. "Ramp finished" lines** (highest value — ground-truth voltage snapshots):
```
2026-03-05 10:52:21,527 - ... - amygdala's right side: Ramp finished in 60.55s. Final Voltages: [B1: 4.70V, B2: 4.70V]
```
Source: `system.py` `_execute_ramp()` completion block (~line 680+).

**2. "Ramping from/to" lines** (ramp-start events with held channel state):
```
2026-03-05 10:53:53,032 - ... - Region amygdala's left side: Ramping A2 from 4.60V to 4.70V (1.00s). Holding: [A1 at 4.50V].
```
Source: `system.py:477` `_threaded_ramp_single_channel_task()`.

### New Regex Patterns

```python
# system.py _execute_ramp completion: all-channel voltage snapshot
RAMP_FINISHED_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2},\d{3}) .+ "
    r"Ramp finished in [\d.]+s\. Final Voltages: \[(.+?)\]"
)

# system.py:477 single-channel ramp start with holding state
RAMP_DETAIL_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2},\d{3}) .+ "
    r"Region .+?: Ramping (\w+) from ([\d.]+)V to ([\d.]+)V "
    r"\(([\d.]+)s\)\. Holding: \[(.+?)\]\."
)
```

### Event Generation Logic

**From `RAMP_FINISHED_RE`:**
- Parse `Final Voltages: [A1: 4.50V, A2: 4.60V]` into channel->voltage pairs
- Emit one ramp event per channel with the snapshot voltage
- This captures protocol start completion, protocol stop completion, and every single-channel ramp finish

**From `RAMP_DETAIL_RE`:**
- Emit a ramp event for the ramping channel at its FROM voltage (state at ramp start)
- Also emit events for held channels with their current voltages
- This captures the moment before each ramp begins

**Deduplication:**
- Multiple sources may produce events at nearby timestamps for the same channel
- `build_voltage_df()` already handles this via state tracking (last-write-wins per timestamp)
- No explicit dedup needed; chronological ordering handles it

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Parse "Ramp finished" + "Ramping from/to" | Captures all ramp events with accurate voltages | Requires 2 new regexes | **Chosen** |
| Only parse "Ramp finished" | Simpler, fewer regexes | Misses ramp-start state | Rejected |
| Add logging to `_execute_ramp()` loop | Would give per-step data like CSV | Requires app code changes, affects all users | Rejected |

### Architecture Changes

No new modules or classes. Changes are limited to:
- Adding 2 regex constants
- Adding 2 match blocks in `parse_log_file()`
- Minor adjustment to event generation in the parsing loop

---

## Implementation Plan

### Phase 1: Add new parsers to `extract_log_data.py`
**Goal:** Parse system-level ramp lines and produce complete voltage timeseries

- [x] Task 1.1 — Add `RAMP_FINISHED_RE` regex constant
- [x] Task 1.2 — Add `RAMP_DETAIL_RE` regex constant
- [x] Task 1.3 — Add parsing block for "Ramp finished" lines in `parse_log_file()`: extract `Final Voltages` pairs, append ramp events for each channel
- [x] Task 1.4 — Add parsing block for "Ramping from/to" lines in `parse_log_file()`: extract ramping channel FROM voltage + held channel voltages, append ramp events
- [x] Task 1.5 — Ensure ramp events are sorted chronologically before passing to `build_voltage_df()` (events from different sources may interleave)
- [x] Task 1.6 — Round voltages from new sources consistently (1dp for .log, matching existing behavior)

**Files Modified:**
- `scripts/extract_log_data.py` — Add ~40 lines (2 regexes + 2 parsing blocks + sort)

**Dependencies:** None

---

## Testing Plan

### Manual Verification
- [ ] Run on known session: `python scripts/extract_log_data.py backlogs_local_data/log-split-global/2026-03-05_AM.log -o /tmp/test_fix/`
  - Old output: ~31 events. New output: should be 60+ events.
  - `voltages.csv` should show protocol start ramp (all channels going to ~4.5-4.7V around 10:52)
  - `voltages.csv` should show protocol stop (all channels returning to 0V)
  - Individual amplitude adjustments should still appear
- [ ] Run batch mode: `python scripts/extract_log_data.py` — no errors
- [ ] Spot-check: compare 5 "Ramp finished" events in `voltages.csv` against raw log lines
- [ ] Run `python scripts/plot_voltages.py` on output — voltage plots should now show full protocol ramp profiles

### Edge Cases
- [ ] Sessions where protocol was never started (only impedance tests) — should still work with existing RAMP_RE events
- [ ] "Ramp finished" lines with single-channel systems — regex should handle variable channel counts
- [ ] Log files from older app versions that may lack "Ramp finished" lines — existing RAMP_RE provides fallback

---

## Documentation Plan

- [ ] No external docs needed — internal script fix

---

## Rollback Plan

1. Revert changes to `scripts/extract_log_data.py`
2. Re-run extraction to restore previous output

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| "Ramp finished" format varies across app versions | Low | Med | Regex is flexible; tested against logs spanning Nov 2025 - Mar 2026 |
| Duplicate events from overlapping regex matches | Med | Low | State-tracking in `build_voltage_df()` handles this naturally |
| New events break downstream `plot_voltages.py` | Low | Low | Plot script reads CSV generically; more rows is fine |

---

## References

- Source of "Ramp finished" log: `src/temporal_interference/core/system.py` `_execute_ramp()` completion
- Source of "Ramping from/to" log: `src/temporal_interference/core/system.py:477`
- Source of existing RAMP_RE log: `src/temporal_interference/services/manager.py:307`
- Example log with all line types: `backlogs_local_data/arthur_github/log-split/2026-03-05_AM.log`
