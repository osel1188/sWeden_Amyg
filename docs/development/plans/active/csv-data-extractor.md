# Plan: CSV Data Extractor (keysight_edu_comms.csv)

**Date:** 2026-03-18
**Author:** Claude Code
**Status:** In Progress
**Branch:** `feature/log-data-extractor` (same branch — extends existing script)

---

## Overview

Extend `scripts/extract_log_data.py` to also parse the older `keysight_edu_comms.csv` format used by 22 pre-November 2025 sessions, producing the same output (`voltages.csv` + `metadata.json`) as the existing `.log` parser. This enables unified batch processing of all ~70 experiment sessions regardless of source format.

## Problem Statement

22 older sessions (June–November 2025) logged raw SCPI commands to `keysight_edu_comms.csv` instead of the Python `.log` format used by later sessions. The current `extract_log_data.py` only handles `.log` files, leaving nearly a third of valid experiment data inaccessible to the extraction pipeline. No sessions have both formats — the transition was clean.

## Goals

### In Scope
1. Parse `keysight_edu_comms.csv` files and extract voltage timeseries into wide-format `voltages.csv`
2. Extract available metadata (frequencies, serials, timing, target voltages) into `metadata.json`
3. Auto-detect format per session in batch mode — no manual format selection needed
4. Supplement metadata from companion `gui_status_messages.csv` and `.txt` files when present

### Out of Scope
- Inferring protocol type (active/sham) from CSV data — requires the conditions Excel which is outside this script's scope
- Inferring ramp rate from step timing — unreliable, left as null
- Aggregating CSV voltage steps into ramp-boundary summaries — full step data is preserved as-is
- Modifying the output schema — same `voltages.csv` + `metadata.json` structure

## Success Criteria

- [ ] Single CSV session produces correct `voltages.csv` and `metadata.json` for reference session `2025-06-19_T27`
- [ ] Batch mode processes all ~70 sessions (both formats) without errors
- [ ] Existing `.log` session output is unchanged (no regression)
- [ ] Frequencies match SCPI `APPLy:SINusoid` commands (A1=7000, A2=7130, B1=9000, B2=9130 for T27)
- [ ] Serial numbers correctly extracted from ResourceName (CN64050087, CN62490141 for T27)
- [ ] Target voltages populated from `gui_status_messages.csv` when available

---

## Technical Design

### Approach

Extend the existing `extract_log_data.py` with a new `parse_csv_session()` function that returns the same `{"metadata": {...}, "ramp_events": [...]}` structure as `parse_log_file()`. Generalize `collect_log_files()` into `collect_sessions()` with per-session format auto-detection. The output writing and DataFrame building logic remain shared.

### CSV Format

**`keysight_edu_comms.csv`** — Header: `Timestamp,Command,KeysightName,ResourceName`
```
2025-06-19_14-21-47-550,:SOURce2:VOLTage 0.0100,slave_1,USB0::0x2A8D::0x8D01::CN62490141::0::INSTR
```

- Timestamp: `YYYY-MM-DD_HH-MM-SS-mmm` (dashes everywhere, no colons)
- Command: raw SCPI, sometimes quoted (e.g., `":SOURce1:APPLy:SINusoid 7000,0.0000"`)
- KeysightName: `master` or `slave_1`
- ResourceName: USB VISA string containing serial number

**Channel mapping** (consistent across all 22 sessions):

| KeysightName | SOURce | Logical Channel |
|---|---|---|
| master | SOURce1 | A1 |
| master | SOURce2 | A2 |
| slave_1 | SOURce1 | B1 |
| slave_1 | SOURce2 | B2 |

**Key difference from `.log` format**: CSV logs every individual voltage step (~14,000 rows at ~100ms intervals per session), while `.log` only logs ramp initiation events (~78 per session). The output `voltages.csv` preserves this full granularity at 4dp precision.

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Extend `extract_log_data.py` | Single CLI, shared output logic, simple | Larger file | **Chosen** |
| Separate `extract_csv_data.py` | Clean separation | Duplicated output logic, two scripts to run | Rejected |
| Shared module (`scripts/log_extraction/`) | Clean architecture | Over-engineering for 22 sessions that won't grow | Rejected |
| Aggregate CSV to ramp boundaries | Matches log output row count | Discards the CSV format's unique per-step data | Rejected |

---

## Implementation Plan

### Phase 1: CSV Parsing Functions
**Goal:** Add CSV-specific parsing capability to `extract_log_data.py`

**Tasks:**
- [x] Task 1.1 — Add `import csv` to imports
- [x] Task 1.2 — Add CSV-specific regex constants after existing regexes (after line 63):
  ```python
  CSV_CHANNEL_MAP = {
      ("master", "1"): "A1", ("master", "2"): "A2",
      ("slave_1", "1"): "B1", ("slave_1", "2"): "B2",
  }
  CSV_VOLTAGE_RE = re.compile(r":?SOURce(\d):VOLTage\s+([\d.]+)")
  CSV_APPLY_RE = re.compile(r":?SOURce(\d):APPLy:SINusoid\s+([\d.]+),([\d.]+)")
  CSV_SERIAL_RE = re.compile(r"::(\w{10,})::0::INSTR")
  ```
- [x] Task 1.3 — Implement `parse_csv_session(session_dir: Path) -> dict` (~80 lines):
  - Single-pass over `keysight_edu_comms.csv` using `csv.reader` (handles quoted SCPI commands)
  - Parse timestamp `YYYY-MM-DD_HH-MM-SS-mmm` → `{date: "YYYY-MM-DD", time: "HH:MM:SS.mmm"}`
  - Match `CSV_VOLTAGE_RE` → append `{date, time, channel, voltage}` to ramp_events
  - Match `CSV_APPLY_RE` → store frequency per logical channel (first occurrence)
  - Extract serial from ResourceName via `CSV_SERIAL_RE` (first per KeysightName)
  - Call companion file parsers (Tasks 1.4, 1.5) for supplementary metadata
  - Return same `{"metadata": {...}, "ramp_events": [...]}` structure as `parse_log_file()`
- [x] Task 1.4 — Implement `_parse_gui_status(path: Path) -> dict` (~20 lines):
  - Parse `gui_status_messages.csv` for target voltages: `r"Target voltages set: \[([\d. ]+)\]"`
  - Extract condition string from "Condition X selected" line
- [x] Task 1.5 — Implement `_parse_participant_txt(path: Path) -> dict` (~15 lines):
  - Parse `YYYY-MM-DD_TXX.txt` key-value pairs → `{participant_id, sex, randomization_number}`

**Files Modified:**
- `scripts/extract_log_data.py` — Add ~130 lines (new functions + constants)

**Dependencies:** None

### Phase 2: Format Auto-Detection and Integration
**Goal:** Wire CSV parsing into the existing CLI and batch processing

**Tasks:**
- [x] Task 2.1 — Refactor `collect_log_files()` → `collect_sessions()`:
  - Change return type from `list[tuple[str, Path]]` to `list[tuple[str, str, Path]]`
  - Tuple: `(session_name, format_type, path)` where format_type is `"log"` or `"csv"`
  - For `"csv"`: path = session directory (needs multiple files)
  - Detection logic: `.log` files → `"log"`, else `*keysight_edu_comms.csv` → `"csv"`, else skip
  - Keep backward compat: single `.log` file input still works
- [x] Task 2.2 — Add `round_digits` parameter to `build_voltage_df()`:
  - Log events are pre-rounded to 1dp in parser — pass `round_digits=None`
  - CSV events have raw 4dp values — pass `round_digits=4`
- [x] Task 2.3 — Update `main()` with format dispatch:
  - Dispatch to `parse_log_file()` or `parse_csv_session()` based on format_type
  - Generalize `out_meta` dict: rename `"log_file"` → `"source_file"`, add `"source_format"`
  - For CSV sessions: `warning_count`/`error_count` set to `None`
  - Update docstring and CLI help text to mention CSV support
  - Update "no files found" error message for both formats

**Files Modified:**
- `scripts/extract_log_data.py` — Modify ~30 lines in existing functions

**Dependencies:** Phase 1

### Phase 3: Plan Documentation Update
**Goal:** Update the parent plan to reflect CSV support

**Tasks:**
- [x] Task 3.1 — Update `docs/development/plans/active/log-data-extractor.md`:
  - Remove "Out of Scope" bullet about CSV format (line 27)
  - Add reference to this plan as Phase 2

**Files Modified:**
- `docs/development/plans/active/log-data-extractor.md` — Minor edit (~3 lines)

**Dependencies:** Phase 2

---

## Testing Plan

### Manual Verification
- [ ] Run on single CSV session: `python scripts/extract_log_data.py backlogs_local_data/TILA_DATA_VALID/2025-06-19_T27/`
  - `voltages.csv`: 5 columns, ~14,000+ rows, voltages at 4dp precision
  - `metadata.json`: frequencies A1=7000, A2=7130, B1=9000, B2=9130; serials CN64050087, CN62490141; target voltages [4.9, 4.6, 5.0, 4.8] from gui file
- [ ] Run on existing log session (regression test): `python scripts/extract_log_data.py backlogs_local_data/TILA_DATA_VALID/2026-01-26_T122/`
  - Output identical to before changes
- [ ] Run batch mode: `python scripts/extract_log_data.py`
  - Processes all ~70 sessions (both formats) without errors
  - Summary shows both log and CSV sessions processed
- [ ] Spot-check: compare peak voltages in CSV-derived `voltages.csv` against gui_status_messages "Ramp finished" values

### Edge Cases
- [ ] Session with no `gui_status_messages.csv` — metadata has null target_voltages, no crash
- [ ] Sessions T38, T69, T75 (txt only, no CSV or log) — skipped with warning
- [ ] Quoted SCPI commands in CSV (e.g., `":SOURce1:APPLy:SINusoid 7000,0.0000"`) — `csv.reader` strips quotes
- [ ] Multiple ramp cycles per session — all voltage steps captured chronologically
- [ ] Session with single channel ramping vs all 4 channels interleaved

---

## Rollback Plan

1. All changes are in a single file (`scripts/extract_log_data.py`) on the existing feature branch
2. The CSV parsing is additive — removing the new functions and reverting `collect_sessions()` back to `collect_log_files()` restores original behavior
3. No database, config, or external state changes

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Channel mapping differs across sessions | Low | High | Verified: master/slave_1 naming is consistent in all 22 CSV sessions |
| CSV timestamp format varies | Low | Low | Regex is strict; mismatches will surface as parse errors in batch run |
| `gui_status_messages.csv` format varies | Med | Low | Parser is defensive — returns nulls for missing fields |
| Large CSV files slow batch processing | Low | Low | ~14K rows is trivial; pandas handles this in milliseconds |

---

## References

- Parent plan: `docs/development/plans/active/log-data-extractor.md`
- Reference CSV session: `backlogs_local_data/TILA_DATA_VALID/2025-06-19_T27/`
- SCPI command reference: `src/temporal_interference/hardware/keysight_edu33212A.py`
- Style reference: `scripts/split_log.py`, `scripts/copy_valid_tila_data.py`
