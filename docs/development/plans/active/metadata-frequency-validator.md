# Plan: Metadata Frequency Validator Script

**Date:** 2026-03-18
**Status:** In Progress
**Branch:** `feature/metadata-validator`

---

## Context

We have 70 processed sessions in `backlogs_local_data/TILA_DATA_1_processed/`, each with a `metadata.json` containing frequency values for channels A1, A2, B1, B2. The participant conditions (active/sham) are defined in `backlogs_local_data/Excel_for_stimulators.xlsx`. We need to cross-validate that the frequencies in each session's metadata match the expected pattern for the assigned condition:
- **Active**: A1 ≠ A2 and B1 ≠ B2 (beat frequency present, typically 130 Hz offset)
- **Sham**: A1 = A2 and B1 = B2 (no beat frequency)

This helps catch configuration errors in past sessions.

## Overview

Create a standalone Python script that reads the Excel condition assignments and each session's metadata, extracts frequencies, and outputs a CSV report with validity checks.

## Goals

### In Scope
1. Read participant conditions from `Excel_for_stimulators.xlsx` (columns: ID, condition)
2. Read frequency values from each session's `metadata.json` (handling both early flat format and modern nested format)
3. Output a CSV with: participant_id, condition, A1, A2, B1, B2, is_valid
4. Validation rule: active → A1≠A2 AND B1≠B2; sham → A1=A2 AND B1=B2

### Out of Scope
- Validating voltage values or ramp durations
- Modifying any metadata files
- Handling sessions not present in the Excel file (skip with warning)

## Technical Design

### Approach

Single script `scripts/validate_metadata.py` using pandas + openpyxl (already in requirements.txt). The script:

1. Loads Excel → builds a `{participant_id: condition}` dict
2. Globs `TILA_DATA_1_processed/*/metadata.json`
3. For each metadata file:
   - Extracts participant ID from session folder name (e.g., `2025-06-04_T29` → `T29`)
   - Extracts frequencies handling two formats:
     - **Flat format** (early CSV sessions): `frequencies.A1`, `frequencies.A2`, etc.
     - **Nested format** (modern log sessions): `frequencies.left.A1`, `frequencies.right.B1`, etc.
   - Looks up condition from Excel dict
4. Applies validation logic per row
5. Writes CSV output to `backlogs_local_data/metadata_validation_report.csv`

### Frequency extraction logic

```python
def extract_frequencies(freq_dict):
    """Handle both flat and nested metadata formats."""
    if "left" in freq_dict:
        # Nested: {"left": {"A1": 7000, "A2": 7130}, "right": {"B1": 9000, "B2": 9130}}
        return freq_dict["left"]["A1"], freq_dict["left"]["A2"], freq_dict["right"]["B1"], freq_dict["right"]["B2"]
    else:
        # Flat: {"A1": 7000, "A2": 7130, "B1": 9000, "B2": 9130}
        return freq_dict["A1"], freq_dict["A2"], freq_dict["B1"], freq_dict["B2"]
```

### Validation logic

```python
def is_valid(condition, a1, a2, b1, b2):
    if condition == "active":
        return a1 != a2 and b1 != b2
    elif condition == "sham":
        return a1 == a2 and b1 == b2
    else:
        return None  # Unknown condition
```

### Key files to reuse
- `scripts/copy_valid_tila_data.py` — already reads participant IDs from the same Excel file (uses zipfile+xml approach, but we'll use pandas/openpyxl for simplicity since it's already a dependency)

## Implementation Plan

### Phase 1: Single script
**Goal:** Complete working script

- [x] Create `scripts/validate_metadata.py`
- [x] Read Excel with pandas, extract ID and condition columns
- [x] Glob metadata files, parse JSON, extract frequencies (both formats)
- [x] Match participants between Excel and metadata by ID
- [x] Apply validation rules
- [x] Output CSV report
- [x] Print summary (total, valid, invalid counts)

**Files Created:**
- `scripts/validate_metadata.py` — The validation script

**Output file:**
- `backlogs_local_data/metadata_validation_report.csv`

## Testing Plan

### Manual Verification
- [ ] Run script and inspect output CSV
- [ ] Spot-check a known active session (e.g., T81: A1=7000, A2=7130 → valid)
- [ ] Spot-check a known sham session (e.g., T145: A1=7000, A2=7000 → valid)
- [ ] Verify sessions with protocol "X" or null are handled gracefully
- [ ] Confirm all 70 sessions appear in the output

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Some sessions missing from Excel | Med | Low | Log warning, include in CSV with condition="UNKNOWN" |
| Metadata format variations beyond the two known formats | Low | Med | Fail loudly with clear error message pointing to the problematic file |
