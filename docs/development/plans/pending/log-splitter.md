# Plan: Log File Splitter Script

## Context

The project produces large `.log` files (e.g., `ti_gui_backup2026-02-26.log` at 37k+ lines) that
mix multiple experiment sessions. The user needs to break these into smaller, manageable files
split by calendar day and by AM/PM (before/after 13:00). This is a standalone utility script —
not part of the main TILA application.

---

## Overview

A single Python script (`scripts/analysis/02_split_log_by_day.py`) that reads a TILA `.log` file, groups lines by
`YYYY-MM-DD_AM` / `YYYY-MM-DD_PM` segments, and writes one output file per segment.

---

## Key Design Decisions

- **Timestamp detection**: regex `^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2},\d{3})` matches the
  standard Python logging format used throughout the project.
- **Continuation lines**: lines that do NOT match the timestamp regex are attached to the preceding
  timestamped line's segment (handles multi-line log entries / tracebacks).
- **AM/PM split**: `hour < 13` → `_AM`, `hour >= 13` → `_PM`.
- **Output naming**: `2025-11-07_AM.log`, `2025-11-07_PM.log`, etc.
- **Output directory**: defaults to `split/` subfolder next to the input file; overridable via `-o`.
- **Lines before first timestamp**: collected into a `no_timestamp.log` file so nothing is lost.

---

## Files

| Path | Action |
|------|--------|
| `scripts/analysis/02_split_log_by_day.py` | **Created** (new utility script) |
| `docs/development/plans/pending/log-splitter.md` | **Created** (this plan document) |

---

## Usage

```bash
# Split a log file (output goes to split/ next to the input file)
python scripts/analysis/02_split_log_by_day.py ti_gui_backup2026-02-26.log

# With explicit output directory
python scripts/analysis/02_split_log_by_day.py ti_gui_backup2026-02-26.log -o /tmp/log_split/
```

Expected output:

```
Splitting 'ti_gui_backup2026-02-26.log' → 'split/'
  2025-11-07_AM.log: 412 lines
  2025-11-07_PM.log: 1830 lines
  ...
Done.
```

Verify: `ls split/` shows one file per day-period; total line count matches original.
