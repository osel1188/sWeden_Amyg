# Plan: Reorganise Numbered Scripts into Workflow Packages

**Date:** 2026-03-31
**Author:** Basil
**Status:** Completed
**Completed:** 2026-03-31 11:32
**Branch:** `feature/reorganise-scripts-into-workflows`

---

## Overview

Nine numbered scripts in `scripts/analysis/` cover two concerns: six preprocess raw
data (filtering, extraction, validation, interval detection) and three perform analysis
(visualisation, statistics, sex-based comparison). Both workflow packages
(`scripts/preprocessing/`, `scripts/analysis/`) exist but contain only empty stubs.
This plan migrates each script into its correct package as a proper workflow task,
wires it into the DAG, and removes the stubs and numbered files.

## Problem Statement

All numbered scripts live in `scripts/analysis/`, regardless of whether they
transform data (preprocessing) or derive insights (analysis). The two workflow
packages have placeholder stubs that do nothing. This means:
- the DAG workflows are completely non-functional
- discoverability is poor (preprocessing logic mixed with analysis logic)
- idempotency, dependency tracking, and pipeline monitoring are unused

## Goals

### In Scope
1. Classify and relocate each numbered script to `scripts/preprocessing/` or `scripts/analysis/`
2. Refactor each script into the task contract (`run_*(input_items, output_dir, force) -> List[Path]`)
3. Wire all tasks into their workflow scripts and YAML DAG configs
4. Delete stubs and numbered scripts once migrated

### Out of Scope
- Changes to the underlying algorithm logic within any script
- Adding new analysis tasks beyond those that already exist
- Integrating the interactive GUI (`04_05b`) into the automated DAG

## Success Criteria

- [ ] Each numbered script's logic lives in a properly named task module in the correct package
- [ ] `scripts/preprocessing_workflow.py` runs all 5 preprocessing tasks via the DAG
- [ ] `scripts/analysis_workflow.py` runs all 3 analysis tasks via the DAG
- [ ] Both `__init__.py` files export the real `run_*` functions
- [ ] Both YAML configs declare real task names with correct `depends_on` chains
- [ ] No `task_one` / `task_two` stubs remain anywhere
- [ ] No numbered scripts remain in `scripts/analysis/`
- [ ] `correct_intervals_gui.py` runs standalone from `scripts/preprocessing/`

---

## Technical Design

### Approach

Refactor each numbered script's body into a `run_*` function that follows the task
contract defined in `docs/development/how-to-add-workflow-task.md`. The function
takes `input_items: List[Path]`, `output_dir: Path`, `force: bool` and returns
`List[Path]`. Idempotency is added via `should_process_task` / `clean_task_outputs`.
The file is placed in the correct package. The workflow script and YAML are updated
to register the new task. The original numbered script is then deleted.

The interactive GUI (`04_05b_correct_intervals_gui.py`) cannot follow this contract
(it blocks on user input), so it is moved to `scripts/preprocessing/` as a
standalone helper without a DAG entry.

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Thin wrappers that call the old scripts' `main()` | Fast to implement | Duplicate code paths; numbered scripts remain | Rejected |
| Move files only, no refactoring | Minimal change | Stubs stay; workflows still non-functional | Rejected |
| Full refactor into task contract | Clean, functional DAG | More effort | **Chosen** |

### Architecture Changes

```
scripts/
├── preprocessing_workflow.py        # updated: imports real task funcs, 5 tasks
├── analysis_workflow.py             # updated: imports real task funcs, 3 tasks
├── preprocessing/
│   ├── __init__.py                  # updated: exports 5 run_* functions
│   ├── filter_valid_sessions.py     # new (from 01_copy_valid_sessions.py)
│   ├── split_log_by_day.py          # new (from 02_split_log_by_day.py)
│   ├── extract_session_data.py      # new (from 03_extract_session_data.py)
│   ├── validate_session_metadata.py # new (from 04_validate_session_metadata.py)
│   ├── tag_voltage_intervals.py     # new (from 04_05_tag_voltage_intervals.py)
│   └── correct_intervals_gui.py     # moved (from 04_05b_), standalone only
└── analysis/
    ├── __init__.py                  # updated: exports 3 run_* functions
    ├── plot_session_voltages.py     # new (from 05_plot_session_voltages.py)
    ├── analyse_stim_intervals.py    # new (from 06_analyse_stim_intervals.py)
    └── sex_based_voltage_analysis.py # new (from 07_sex_based_voltage_analysis.py)

config/
├── preprocessing_workflow_dag.yaml  # updated: 5 real tasks + depends_on chain
└── analysis_workflow_dag.yaml       # updated: 3 real tasks + depends_on chain

DELETED:
  scripts/preprocessing/task_one.py
  scripts/preprocessing/task_two.py
  scripts/analysis/task_one.py
  scripts/analysis/task_two.py
  scripts/analysis/01_copy_valid_sessions.py
  scripts/analysis/02_split_log_by_day.py
  scripts/analysis/03_extract_session_data.py
  scripts/analysis/04_validate_session_metadata.py
  scripts/analysis/04_05_tag_voltage_intervals.py
  scripts/analysis/04_05b_correct_intervals_gui.py
  scripts/analysis/05_plot_session_voltages.py
  scripts/analysis/06_analyse_stim_intervals.py
  scripts/analysis/07_sex_based_voltage_analysis.py
```

---

## Implementation Plan

### Phase 1: Preprocessing task modules
**Goal:** Create 5 task modules in `scripts/preprocessing/` and move the GUI helper

- [x] Create `filter_valid_sessions.py` — `run_filter_valid_sessions` wrapping logic from `01_copy_valid_sessions.py`
- [x] Create `split_log_by_day.py` — `run_split_log_by_day` wrapping logic from `02_split_log_by_day.py`
- [x] Create `extract_session_data.py` — `run_extract_session_data` wrapping logic from `03_extract_session_data.py`
- [x] Create `validate_session_metadata.py` — `run_validate_session_metadata` wrapping logic from `04_validate_session_metadata.py`
- [x] Create `tag_voltage_intervals.py` — `run_tag_voltage_intervals` wrapping logic from `04_05_tag_voltage_intervals.py`
- [x] Move `04_05b_correct_intervals_gui.py` → `scripts/preprocessing/correct_intervals_gui.py` (no task contract, standalone)

**Files Modified:**
- `scripts/preprocessing/filter_valid_sessions.py` — new
- `scripts/preprocessing/split_log_by_day.py` — new
- `scripts/preprocessing/extract_session_data.py` — new
- `scripts/preprocessing/validate_session_metadata.py` — new
- `scripts/preprocessing/tag_voltage_intervals.py` — new
- `scripts/preprocessing/correct_intervals_gui.py` — moved/renamed

**Dependencies:** None

**Started:** 2026-03-31
**Completed:** 2026-03-31

### Phase 2: Analysis task modules
**Goal:** Create 3 task modules in `scripts/analysis/`

- [x] Create `plot_session_voltages.py` — `run_plot_session_voltages` wrapping logic from `05_plot_session_voltages.py`
- [x] Create `analyse_stim_intervals.py` — `run_analyse_stim_intervals` wrapping logic from `06_analyse_stim_intervals.py`
- [x] Create `sex_based_voltage_analysis.py` — `run_sex_based_voltage_analysis` wrapping logic from `07_sex_based_voltage_analysis.py`

**Files Modified:**
- `scripts/analysis/plot_session_voltages.py` — new
- `scripts/analysis/analyse_stim_intervals.py` — new
- `scripts/analysis/sex_based_voltage_analysis.py` — new

**Dependencies:** None (parallel with Phase 1)

**Started:** 2026-03-31
**Completed:** 2026-03-31

### Phase 3: Wire workflows and configs
**Goal:** Update workflow scripts, `__init__.py` files, and YAML DAGs; delete stubs and numbered scripts

- [x] Update `scripts/preprocessing/__init__.py` — export 5 `run_*` functions, remove stub exports
- [x] Update `scripts/analysis/__init__.py` — export 3 `run_*` functions, remove stub exports
- [x] Update `scripts/preprocessing_workflow.py` — import real funcs, 5-task `available_tasks`, correct `PipelineMonitor` list, resolve inputs in `main()`
- [x] Update `scripts/analysis_workflow.py` — import real funcs, 3-task `available_tasks`, correct `PipelineMonitor` list, resolve inputs in `main()`
- [x] Update `config/preprocessing_workflow_dag.yaml` — 5 real task entries with `depends_on` chain
- [x] Update `config/analysis_workflow_dag.yaml` — 3 real task entries with correct `depends_on`
- [x] Delete `scripts/preprocessing/task_one.py` and `task_two.py`
- [x] Delete `scripts/analysis/task_one.py` and `task_two.py`
- [x] Delete the 9 numbered scripts from `scripts/analysis/`

**Files Modified:**
- `scripts/preprocessing/__init__.py`
- `scripts/analysis/__init__.py`
- `scripts/preprocessing_workflow.py`
- `scripts/analysis_workflow.py`
- `config/preprocessing_workflow_dag.yaml`
- `config/analysis_workflow_dag.yaml`

**Files Deleted:** 4 stubs + 9 numbered scripts (see Architecture Changes above)

**Dependencies:** Phase 1 and Phase 2

**Started:** 2026-03-31
**Completed:** 2026-03-31

---

## DAG Dependency Chains

**Preprocessing:**
```
filter_valid_sessions
  → split_log_by_day
    → extract_session_data
      → validate_session_metadata
        → tag_voltage_intervals
```

**Analysis** (`plot_session_voltages` and `analyse_stim_intervals` are independent and can run in parallel):
```
plot_session_voltages  ─────────────────────────────────┐
                                                         ├── (no dependency between these two)
analyse_stim_intervals ──→ sex_based_voltage_analysis   ┘
```

---

## Testing Plan

### Manual Verification
- [ ] `python -c "from scripts.preprocessing import *"` — no import errors, 5 symbols
- [ ] `python -c "from scripts.analysis import *"` — no import errors, 3 symbols
- [ ] `python scripts/preprocessing_workflow.py` — runs without crashing (may skip tasks if no input data)
- [ ] `python scripts/analysis_workflow.py` — runs without crashing
- [ ] `python scripts/preprocessing/correct_intervals_gui.py` — GUI launches

### Edge Cases
- [ ] Running a workflow with `force_processing: true` in YAML — tasks re-run even if outputs exist
- [ ] Running with missing input data — `FileNotFoundError` surfaced cleanly, not silently swallowed

---

## Documentation Plan

- [ ] No CLAUDE.md changes needed (workflow architecture already documented there)

---

## Rollback Plan

All changes are local file operations (create/move/delete). Rollback:
1. `git checkout -- scripts/analysis/` to restore numbered scripts
2. `git checkout -- scripts/preprocessing/` to restore stubs
3. Delete new task modules manually or via `git clean -f`

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Numbered script logic uses `argparse` / `__main__` blocks incompatible with task contract | Med | Med | Extract core function; keep optional `__main__` block in new module for standalone use |
| Scripts have hard-coded paths that break when moved | Med | Med | Replace with `output_dir` parameter during refactor |
| `correct_intervals_gui` imports from scripts that were deleted | Low | Med | Check imports before deleting source scripts |
