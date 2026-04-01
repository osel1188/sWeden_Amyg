# Plan: Log Data Extractor Script

**Date:** 2026-03-18
**Author:** Claude Code
**Status:** Completed
**Completed:** 2026-04-01
**Branch:** `feature/log-data-extractor`

---

## Overview

A Python script (`scripts/analysis/03_extract_session_data.py`) that parses TILA `.log` files and produces **two files per session** in an output folder: a wide-format voltage timeseries CSV and a JSON metadata file containing session overview, hardware config, frequencies, and protocol parameters. This complements the existing `02_split_log_by_day.py` and `01_copy_valid_sessions.py` scripts.

## Problem Statement

Experiment log files in `backlogs_local_data/TILA_DATA_VALID/` contain valuable structured data (frequency settings, voltage ramp commands, hardware configuration, protocol type) buried in verbose Python logging output. There is no tool to extract this data into analysis-ready formats. Researchers need per-session voltage timeseries and metadata for downstream analysis.

## Goals

### In Scope
1. Extract voltage ramp commands into a wide-format timeseries CSV (timestamp, A1, A2, B1, B2)
2. Extract session metadata (protocol, frequencies, hardware, timing) into a JSON file
3. Support single-file, single-session, and batch processing modes
4. Process all 50+ log files across `TILA_DATA_VALID`

### Out of Scope
- Reconstructing actual instantaneous voltages during ramps (only target voltages are logged)
- Generating SESSION_OVERVIEW.md files (those are manually curated)
- Aggregating data across sessions into a single file

## Success Criteria

- [ ] Script produces correct `voltages.csv` and `metadata.json` for the reference session `2026-01-26_T122`
- [ ] Batch mode processes all log files without errors
- [ ] Voltage values match raw log after rounding (e.g., `4.299999999999999` → `4.3`)
- [ ] Metadata JSON contains all fields: protocol, frequencies, generator SNs, safety limit, timing, counts

**Phase 2:** CSV format support added in `docs/development/plans/active/csv-data-extractor.md`

---

## Technical Design

### Approach

Single-pass line-by-line parsing with compiled regexes. Each log file is read once; lines are matched against multiple patterns to extract both ramp events (for the voltage CSV) and metadata fields (for the JSON). Channel voltage state is tracked to produce the wide-format output.

### Output Structure

```
output_dir/
├── 2025-11-07_T81/
│   ├── voltages.csv
│   └── metadata.json
├── 2026-01-26_T122/
│   ├── voltages.csv
│   └── metadata.json
└── ...
```

#### `voltages.csv` — Wide format, one row per ramp command

```csv
timestamp,A1,A2,B1,B2
2026-01-26 11:09:12.306,1.0,0.0,0.0,0.0
2026-01-26 11:09:27.524,0.0,0.0,0.0,0.0
2026-01-26 11:09:40.244,0.0,1.0,0.0,0.0
```

- Each row = a ramp command event; all 4 channels shown with current target voltage
- Channels that didn't change repeat their last known value
- Voltages rounded to 1 decimal place (removes float artifacts)
- Channel state initialized at 0.0, updated on each ramp command

#### `metadata.json` — Session info and parameters

```json
{
  "session": "2026-01-26_T122",
  "participant": "T122",
  "date": "2026-01-26",
  "time_start": "09:58:03",
  "time_end": "12:37:xx",
  "protocol": "active",
  "beat_frequency_hz": 130,
  "generators": {
    "generator_A": {
      "serial": "CN64050087",
      "channels": ["A1", "A2"],
      "system": "ti_A",
      "region": "amygdala's left side"
    },
    "generator_B": {
      "serial": "CN62490141",
      "channels": ["B1", "B2"],
      "system": "ti_B",
      "region": "amygdala's right side"
    }
  },
  "safety_limit_vp": 8.0,
  "ramp_rate_v_per_s": 0.1,
  "frequencies": {
    "left": {"A1": 7000, "A2": 7130},
    "right": {"B1": 9000, "B2": 9130}
  },
  "default_target_voltages": {
    "left": {"A1": 1.0, "A2": 1.0},
    "right": {"B1": 1.0, "B2": 1.0}
  },
  "ramp_durations_s": {
    "left": {"A1": 60, "A2": 60},
    "right": {"B1": 60, "B2": 60}
  },
  "log_file": "2026-01-26_AM.log",
  "total_lines": 946,
  "warning_count": 42,
  "error_count": 0,
  "ramp_event_count": 78
}
```

### Regex Patterns

**Ramp commands** (source: `src/temporal_interference/services/manager.py:307`):
```python
RAMP_RE = re.compile(
    r'^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2},\d{3}) .+ '
    r"Ramping channel '(\w+)' in system '(\w+)' to "
    r'([\d.]+(?:e[+-]?\d+)?)V at ([\d.]+) V/s\.'
)
```

**Frequency settings** (source: `src/temporal_interference/core/system.py:191`):
```python
FREQ_RE = re.compile(
    r"Region (.+?)'s (\w+) side frequencies set to: "
    r'(\w+)=(\d+(?:\.\d+)?) Hz, (\w+)=(\d+(?:\.\d+)?) Hz\.'
)
```

**Target voltages**:
```python
TARGET_V_RE = re.compile(
    r"Region (.+?)'s (\w+) side target voltages set to: "
    r'(\w+)=([\d.]+) V(?:, (\w+)=([\d.]+) V)?'
)
```

**Ramp durations**:
```python
RAMP_DUR_RE = re.compile(
    r"Region (.+?)'s (\w+) side ramp durations set to: "
    r'(\w+)=(\d+)s(?:, (\w+)=(\d+)s)?'
)
```

**Protocol**: `r"Condition found: '(\w+)'\. Using as protocol\."` and `r"Initializing protocol '(\w+)': (.+?)\."`

**Generator serial**: `r"Successfully connected to: Keysight Technologies,EDU33212A,(\w+),"`

**Safety limit**: `r"Safety limit .+: Max amplitude set to ([\d.]+) Vp\."`

**Channel mapping**: `r"Mapped logical channel '(\w+)' to driver '(\w+)' \(Phys Ch (\d+)\)"`

**System region**: `r"Found system: '(\w+)' targeting '(.+?)'"`

Only the `manager` logger ramp lines are captured (not the `root` logger duplicates which lack system/rate info).

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Per-session output (2 files each) | Matches experiment structure, easy to find data for a session | More files on disk | **Chosen** |
| Aggregated CSVs (one big file) | Single file to load | Loses session boundaries, harder to browse | Rejected |
| Long-format ramp CSV | Simpler to generate | Harder to plot/compare channels side by side | Rejected |
| Wide-format voltage CSV | Easy to plot, shows all channels at each event | Requires state tracking | **Chosen** |

---

## Implementation Plan

### Phase 1: Create `scripts/analysis/03_extract_session_data.py`
**Goal:** Complete working script with all extraction and output logic

**Started:** 2026-03-18
**Completed:** 2026-03-18

**Tasks:**
- [x] Task 1.1 — Imports and module-level regex constants
- [x] Task 1.2 — `parse_log_file(path) -> dict`: single-pass line parser returning `{"metadata": {...}, "ramp_events": [...]}`
- [x] Task 1.3 — `build_voltage_df(ramp_events) -> pd.DataFrame`: convert ramp events to wide-format with channel state tracking
- [x] Task 1.4 — `collect_log_files(input_path) -> list[tuple[str, Path]]`: resolve input to (session_name, log_path) pairs, filter "copy" files
- [x] Task 1.5 — `main()`: argparse, iterate sessions, write `voltages.csv` + `metadata.json` per session, print summary
- [x] Task 1.6 — Timestamp formatting (`,` → `.`), voltage rounding to 1dp

**Files Modified:**
- `scripts/analysis/03_extract_session_data.py` — **NEW** (~250 lines)

**Dependencies:** None

---

## Testing Plan

### Manual Verification
- [ ] Run on single file: `python scripts/analysis/03_extract_session_data.py backlogs_local_data/TILA_DATA_VALID/2026-01-26_T122/2026-01-26_AM.log -o /tmp/test/`
  - `voltages.csv`: 5 columns (timestamp + 4 channels), ~78 rows, voltages rounded cleanly
  - `metadata.json`: protocol=active, A1=7000Hz, A2=7130Hz, B1=9000Hz, B2=9130Hz, SNs present
- [ ] Run batch: `python scripts/analysis/03_extract_session_data.py`
  - Output folders created for all sessions with log files
  - No errors or crashes
- [ ] Spot-check: compare 5 random rows from `voltages.csv` against raw log timestamps and voltage values

### Edge Cases
- [ ] Sessions with no ramp events (if any) — should produce empty CSV with headers and metadata still populated
- [ ] Files with "copy" in the name — should be skipped
- [ ] Sessions without a "Condition found" line — protocol field should be null/empty

---

## CLI Interface

```bash
python scripts/analysis/03_extract_session_data.py                                         # batch: all TILA_DATA_VALID
python scripts/analysis/03_extract_session_data.py path/to/file.log                        # single file
python scripts/analysis/03_extract_session_data.py path/to/session_folder/                 # single session
python scripts/analysis/03_extract_session_data.py -o custom_output/                       # custom output dir
```

- `input` (positional, optional): `.log` file, session folder, or omit for batch. Default: `backlogs_local_data/TILA_DATA_VALID/`
- `-o, --output-dir`: output directory. Default: `backlogs_local_data/TILA_DATA_EXTRACTED/`

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Log format changes in future app versions | Low | Med | Regexes reference source code lines in comments; easy to update |
| Some sessions lack expected log lines | Med | Low | Metadata fields default to null; voltage CSV can be empty |
| Float precision edge cases in voltage parsing | Low | Low | Round to 1dp covers all observed artifacts |

---

## References

- Source of frequency log: `src/temporal_interference/core/system.py:191`
- Source of ramp log: `src/temporal_interference/services/manager.py:307`
- Style reference: `scripts/analysis/02_split_log_by_day.py`, `scripts/analysis/01_copy_valid_sessions.py`
- Example session: `backlogs_local_data/TILA_DATA_VALID/2026-01-26_T122/`
