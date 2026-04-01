# Plan: Downstream Scripts Use Corrected Interval Boundaries

**Date:** 2026-03-30
**Author:** Claude
**Status:** Completed
**Completed:** 2026-04-01
**Branch:** `feature/downstream-interval-source`

---

## Overview

Update scripts 06 and 07 to read stimulation block boundaries from the `interval` column in `voltages_corrected.csv` (or `voltages_tagged.csv`) instead of re-detecting blocks from raw voltage data. This connects the human-verified correction workflow (04_05b) to all downstream analysis.

## Problem Statement

Scripts 06 and 07 independently re-detect stimulation blocks from raw `voltages.csv` using gap-based heuristics. Meanwhile, the 04_05 → 04_05b pipeline produces human-verified block boundaries in `voltages_corrected.csv` (with an `interval` column containing values 0/1/2). The downstream scripts ignore this corrected data entirely, so manual corrections have no effect on the final analysis output.

## Goals

### In Scope
1. Script 06 reads block boundaries from the `interval` column instead of re-detecting via gap analysis
2. Script 07 reads block boundaries from the `interval` column instead of importing script 06's detection functions
3. Both scripts prefer `voltages_corrected.csv`, fall back to `voltages_tagged.csv`, then fall back to gap-based re-detection from `voltages.csv`
4. Script 07 no longer needs `_import_script_06()` for block detection

### Out of Scope
- Modifying the correction GUI (04_05b) or the tagging script (04_05)
- Changing the `interval_summary.csv` output schema (columns stay the same)
- Changing script 06's plotting or stats extraction logic
- Changing script 07's statistical tests, figures, or output schema
- Removing script 06's detection functions (they remain as the last-resort fallback)

## Success Criteria

- [ ] Script 06 produces `interval_summary.csv` using boundaries from `voltages_corrected.csv` when available
- [ ] Script 07's voltage change analysis uses boundaries from corrected/tagged CSV when available
- [ ] Both scripts fall back gracefully: corrected → tagged → re-detect from raw
- [ ] Console output indicates which source was used per session (e.g. `[session]: using voltages_corrected.csv`)
- [ ] `interval_summary.csv` output schema is unchanged (same columns, same semantics)
- [ ] Script 07 no longer calls `_import_script_06()` for block detection

---

## Technical Design

### Approach

**Fallback chain with `interval` column extraction** — a shared helper function resolves the best available CSV per session:

1. `voltages_corrected.csv` — human-verified boundaries (preferred)
2. `voltages_tagged.csv` — auto-detected consensus boundaries
3. `voltages.csv` — raw data, requires gap-based re-detection (existing logic)

When option 1 or 2 is used, block boundaries are extracted directly from the `interval` column (values 1 and 2 mark Block 1 and Block 2). When option 3 is used, the existing `detect_and_classify` logic runs as before.

This approach avoids breaking any sessions that haven't been processed through the 04_05 → 04_05b pipeline yet.

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Fallback chain (corrected → tagged → re-detect) | Handles all sessions; graceful degradation; no workflow breakage | Slightly more complex resolution logic | **Chosen** |
| Require corrected files only | Simple; guarantees human review | Blocks analysis if GUI hasn't been run on all sessions | Rejected |
| Skip tagged, fallback directly to re-detect | Simpler two-step chain | Wastes the auto-detected consensus column from 04_05 | Rejected |
| Keep detection as primary, use corrected as override | Minimal code change | Defeats the purpose — detection errors persist unless manually caught | Rejected |

### Architecture Changes

No new modules. Two existing scripts modified. One shared helper pattern (duplicated in each script since these are standalone analysis scripts, not a package).

```
scripts/analysis/
  06_analyse_stim_intervals.py   — Modified: new CSV resolution + interval extraction
  07_sex_based_voltage_analysis.py — Modified: new CSV resolution, drop _import_script_06 for detection
```

---

## Implementation Plan

### Phase 1: Add interval-column extraction to script 06
**Goal:** Script 06 reads block boundaries from the `interval` column when available

- [x] Task 1.1 — Add `resolve_session_csv(session_dir)` helper: returns `(csv_path, source)` where source is `"corrected"`, `"tagged"`, or `"raw"`; checks for `voltages_corrected.csv` first, then `voltages_tagged.csv`, then `voltages.csv`
- [x] Task 1.2 — Add `extract_blocks_from_interval_column(df)` helper: reads the `interval` column, returns `(status, [(start, end, "Block N"), ...])` in the same format as `detect_and_classify`; uses first/last timestamp per interval value (same logic as 04_05b's `extract_boundaries`)
- [x] Task 1.3 — Update `analyse_all_sessions`: use `resolve_session_csv` instead of hardcoded `voltages.csv` glob; when source is `"corrected"` or `"tagged"`, call `extract_blocks_from_interval_column`; when source is `"raw"`, call existing `detect_and_classify` as fallback
- [x] Task 1.4 — Add console output indicating source per session (e.g. `[session]: using voltages_corrected.csv`)
- [x] Task 1.5 — Update script docstring to document the new input preference

**Files Modified:**
- `scripts/analysis/06_analyse_stim_intervals.py` — Add ~30 lines (two helpers + updated loop)

**Dependencies:** None

### Phase 2: Update script 07 to use interval column directly
**Goal:** Script 07 reads block boundaries from the `interval` column without importing script 06's detection functions

- [ ] Task 2.1 — Add `resolve_session_csv(session_dir)` helper (same logic as script 06, duplicated since these are standalone scripts)
- [ ] Task 2.2 — Add `extract_blocks_from_interval_column(df)` helper (same as script 06)
- [ ] Task 2.3 — Update `analyse_voltage_changes`: replace the `_import_script_06()` + `detect_active_intervals` + `classify_intervals` block with `resolve_session_csv` + `extract_blocks_from_interval_column`; keep `load_session` inline (it's just `pd.read_csv` with comment/timestamp parsing)
- [ ] Task 2.4 — Remove or mark as unused: `_import_script_06()` function, the `detect_active_intervals` / `classify_intervals` backward-compat wrappers in script 06 (if no other callers exist)
- [ ] Task 2.5 — Update script docstring: change "Inputs" section to list `voltages_corrected.csv` / `voltages_tagged.csv` as primary inputs, `voltages.csv` as fallback
- [ ] Task 2.6 — Update methodology note: block detection now reads pre-computed `interval` column rather than re-detecting via gap analysis

**Files Modified:**
- `scripts/analysis/07_sex_based_voltage_analysis.py` — Modify `analyse_voltage_changes` (~20 lines changed), remove `_import_script_06` (~40 lines removed)
- `scripts/analysis/06_analyse_stim_intervals.py` — Remove backward-compat wrappers `detect_active_intervals` and `classify_intervals` (~30 lines removed)

**Dependencies:** Phase 1

### Phase 3: Clean up dead code in script 06
**Goal:** Remove detection functions that are no longer the primary path, keeping only what's needed for the raw-data fallback

- [ ] Task 3.1 — Verify no other scripts import `detect_active_intervals` or `classify_intervals` from script 06
- [ ] Task 3.2 — Remove backward-compat wrappers (`detect_active_intervals`, `classify_intervals`) and their docstring references to script 07
- [ ] Task 3.3 — Update the "Backward-compatible wrappers" section header comment (remove it or rename to "Fallback detection")

**Files Modified:**
- `scripts/analysis/06_analyse_stim_intervals.py` — Remove ~30 lines of wrapper code

**Dependencies:** Phase 2

---

## Testing Plan

### Manual Verification
- [ ] Run script 06 on sessions that have `voltages_corrected.csv` — confirm console says "using voltages_corrected.csv" and `interval_summary.csv` reflects the corrected boundaries
- [ ] Run script 06 on sessions that only have `voltages_tagged.csv` — confirm fallback to tagged
- [ ] Run script 06 on sessions with only `voltages.csv` — confirm fallback to gap-based re-detection
- [ ] Run script 07 — confirm it completes without importing script 06's detection functions
- [ ] Compare `interval_summary.csv` before/after for sessions where corrected boundaries differ from auto-detected: durations and median voltages should change to match the corrected blocks
- [ ] Verify script 07's output CSVs and PNGs are generated without errors

### Edge Cases
- [ ] Session with `voltages_corrected.csv` but `interval` column has only 1 block — should produce single_block status
- [ ] Session with `voltages_tagged.csv` where `interval` column has 0 blocks (all zeros) — should fall back to re-detection or skip
- [ ] Session where `voltages_corrected.csv` exists but is malformed — should warn and fall back

---

## Documentation Plan

- [ ] Update script docstrings (covered in implementation tasks)

---

## Rollback Plan

1. Both scripts are standalone analysis tools — reverting is `git revert` on the commit(s)
2. No data files are modified — only analysis outputs change
3. The `interval_summary.csv` schema is unchanged, so any downstream consumers are unaffected

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Some sessions lack `voltages_corrected.csv` or `voltages_tagged.csv` | High | Low | Fallback chain handles this — gap-based re-detection still works |
| `interval` column has unexpected values (e.g. 3, 4 from fragmented detection) | Low | Low | `extract_blocks_from_interval_column` only looks for values 1 and 2, matching 04_05b's output |
| Removing `_import_script_06` breaks other code that imports script 07 | Very Low | Med | Script 07 is a standalone analysis script, not imported by anything; verify with grep before removing |
| Corrected boundaries produce different stats than before | Expected | Low | This is the desired behavior — human corrections should propagate to analysis |

---

## References

- Related Plans: `docs/development/plans/active/interval-correction-workflow.md` (produces the corrected files this plan consumes)
- Related Plans: `docs/development/plans/active/interval-analysis.md` (created script 06)
- Related Plans: `docs/development/plans/active/sex-based-voltage-analysis.md` (created script 07)
