# Plan: Integrate correct_intervals_gui into Preprocessing Pipeline

**Date:** 2026-04-01
**Author:** Claude
**Status:** In Progress
**Branch:** `feature/integrate-correct-intervals-gui`

---

## Overview

- **What:** Add `correct_intervals_gui` as the 6th (final) DAG task with a new "Discard" button and flag-file validation
- **Why:** Enable separation of good vs bad session data directly in the preprocessing pipeline, and ensure every session is human-reviewed before analysis
- **How:** Refactor the GUI script into a proper task function, add Discard button + flag files, wire into DAG, update downstream resolvers

## Problem Statement

`correct_intervals_gui.py` is a standalone matplotlib GUI for manually correcting auto-detected interval boundaries in `voltages_tagged.csv`. It currently sits outside the DAG — users must run it manually after the pipeline. There is no mechanism to mark sessions as having bad data, so all sessions flow into downstream analysis regardless of data quality.

## Goals

### In Scope
1. Add `run_correct_intervals()` matching existing task contract
2. Add orange **Discard** button to mark sessions as bad data
3. Write `validated.flag` / `discarded.flag` JSON files per session
4. Wire as 6th DAG task depending on `tag_voltage_intervals`
5. Update downstream analysis resolvers to skip discarded sessions

### Out of Scope
- Changing the existing task contract pattern (that's `align-preprocessing-contracts`)
- Adding batch/headless auto-validation mode
- Modifying the DraggableVLine interaction model

## Success Criteria

- [ ] `run_correct_intervals()` callable from pipeline with same contract as other tasks
- [ ] Validate writes `voltages_corrected.csv` + `validated.flag`
- [ ] Discard writes `discarded.flag` and removes any existing `voltages_corrected.csv`
- [ ] Sessions with existing flags are skipped (unless `force=True`)
- [ ] Downstream analysis skips discarded sessions
- [ ] Standalone `main()` entry point still works

---

## Technical Design

### Approach

Follow the existing task contract (`input_items, output_dir, force`) used by all 5 current tasks. The GUI is inherently blocking (waits for user input), which is acceptable as the final pipeline task. Flag files provide a lightweight, filesystem-based mechanism to track session validation state.

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| JSON flag files (`validated.flag`, `discarded.flag`) | Auditable (timestamp), simple existence check, per-session | Two files to manage | **Chosen** |
| Empty sentinel files (`.validated`, `.discarded`) | Simpler | No metadata, less discoverable | Rejected |
| Central CSV report (like `condition_validation_report.csv`) | Single file to check | Must parse CSV for each session, harder to keep in sync | Rejected |

### Flag Files

JSON files in each session directory:

```json
{"timestamp": "2026-04-01T14:23:05", "source": "correct_intervals_gui"}
```

- `validated.flag` — session approved, `voltages_corrected.csv` is authoritative
- `discarded.flag` — session rejected, exclude from all downstream analysis
- Both cleared on `force=True` re-run

### GUI Button Layout (New)

```
[Reset Block 1]  [Reset Block 2]  [  Validate  ]  [  Discard  ]
   (blue)           (orange)         (green)         (orange)
```

- **Validate** (renamed from Continue): saves corrections + `validated.flag`. ENTER shortcut preserved.
- **Discard** (new, orange): writes `discarded.flag`, removes corrected CSV, closes figure
- **Window X close**: skip session — no flag written, no output

### `launch_correction_gui` Return Change

Currently returns `list[tuple]`. Change to return `tuple[list[tuple], str]` where the second element is the action: `"validate"`, `"discard"`, or `"closed"`.

### Downstream Filter

`_resolve_voltage_csv()` in `analysis_workflow.py` and `resolve_session_csv()` in `analyse_stim_intervals.py` both gain a `discarded.flag` existence check — return `None` early if present.

### Architecture Changes

```
Preprocessing DAG (after):
  filter_valid_sessions
      ↓
  extract_session_data
      ├→ validate_session_metadata ──┐
      └→ resample_voltages ──────────┤
                                     ↓
                            tag_voltage_intervals
                                     ↓
                            correct_intervals       ← NEW (6th task)
```

---

## Implementation Plan

### Phase 1: Refactor GUI Script
**Goal:** Transform standalone script into a pipeline-compatible task with validation/discard features

**Started:** 2026-04-01
**Completed:** 2026-04-01

**Tasks:**
- [x] 1.1 — Add flag-file constants and helpers: `VALIDATED_FLAG`, `DISCARDED_FLAG`, `write_flag()`, `has_flag()`, `clear_flags()`
- [x] 1.2 — Add **Discard** button (orange) to GUI layout; rename Continue to **Validate** (green)
- [x] 1.3 — Change `launch_correction_gui()` return type to `tuple[list[tuple], str]` with action string
- [x] 1.4 — Handle window-close (X button) as `"closed"` action (currently unhandled)
- [x] 1.5 — Add `run_correct_intervals(input_items, output_dir, force=False) -> list[Path]` with per-session loop, flag-based skip logic, and summary logging
- [x] 1.6 — Refactor `main()` to use `run_correct_intervals()` with argparse (remove hardcoded `PREPROCESS_DIR`)
- [x] 1.7 — Update module docstring

**Files Modified:**
- `scripts/preprocessing/correct_intervals_gui.py` — all changes above

**Dependencies:** None

### Phase 2: Wire into Pipeline
**Goal:** Register as 6th DAG task

**Started:** 2026-04-01
**Completed:** 2026-04-01

**Tasks:**
- [x] 2.1 — Add `correct_intervals` entry to `config/preprocessing_workflow_dag.yaml` (`depends_on: [tag_voltage_intervals]`, `force_processing: false`)
- [x] 2.2 — Add `run_correct_intervals` import to `scripts/preprocessing/__init__.py`
- [x] 2.3 — Append 6th stage to `pipeline_stages` in `scripts/preprocessing_workflow.py` consuming `tagged_sessions` context key, outputting `corrected_sessions`

**Files Modified:**
- `config/preprocessing_workflow_dag.yaml` — new task entry
- `scripts/preprocessing/__init__.py` — new export
- `scripts/preprocessing_workflow.py` — new import + pipeline stage

**Dependencies:** Phase 1

### Phase 3: Update Downstream Analysis
**Goal:** Discarded sessions excluded from analysis

**Started:** 2026-04-01
**Completed:** 2026-04-01

**Tasks:**
- [x] 3.1 — Add `discarded.flag` check to `_resolve_voltage_csv()` in `scripts/analysis_workflow.py` (return `None` early)
- [x] 3.2 — Add `discarded.flag` check to `resolve_session_csv()` in `scripts/analysis/analyse_stim_intervals.py` (return `(None, "discarded")` early)

**Files Modified:**
- `scripts/analysis_workflow.py` — early return `None` if `discarded.flag` exists
- `scripts/analysis/analyse_stim_intervals.py` — early return `(None, "discarded")` if flag exists

**Dependencies:** Phase 1 (flag constant names)

---

## Testing Plan

### Manual Verification
- [ ] Run pipeline end-to-end — GUI opens after `tag_voltage_intervals` completes
- [ ] Click **Validate** on a session — confirm `voltages_corrected.csv` + `validated.flag` written
- [ ] Click **Discard** on a session — confirm `discarded.flag` written, no corrected CSV
- [ ] Close window via X — confirm no flag, no output, session skipped
- [ ] Re-run without force — confirm flagged sessions are skipped
- [ ] Re-run with `force_processing: true` — confirm all sessions re-reviewed, old flags cleared
- [ ] Run analysis workflow — confirm discarded sessions excluded
- [ ] Run standalone `python scripts/preprocessing/correct_intervals_gui.py` — still works

### Edge Cases
- [ ] Session with 0 intervals detected (should skip, no GUI shown)
- [ ] Session previously validated, now discarded on force re-run (corrected CSV removed)
- [ ] Session with missing `interval` column (should skip with warning)

---

## Documentation Plan

- [ ] Update module docstring in `correct_intervals_gui.py` (no longer standalone-only)
- [ ] Update `docs/development/how-to-add-workflow-task.md` if the interactive-task pattern warrants a note

---

## Rollback Plan

1. Remove `correct_intervals` entry from YAML — pipeline reverts to 5 tasks
2. Revert `__init__.py` and `preprocessing_workflow.py` imports
3. Flag files in session dirs are inert (no other code reads them without the feature)

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| GUI blocks pipeline in headless env | Low | Med | `enabled: false` in YAML skips the task |
| User closes all windows (KeyboardInterrupt) | Med | Low | Existing try/except handles this; unreviewed sessions have no flag |
| Stale flags after re-running upstream tasks | Low | Low | `should_process_task` timestamp check triggers re-review |

---

## References

- Completed plan: `docs/development/plans/completed/interval-correction-workflow.md`
- Pending plan: `docs/development/plans/pending/align-preprocessing-contracts.md`
