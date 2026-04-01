# Plan: Align Analysis Task Contracts with New Workflow Pattern

**Date:** 2026-04-01
**Author:** Basil
**Status:** Draft
**Branch:** `feature/align-analysis-task-contracts`

---

## Overview

The analysis workflow (`scripts/analysis_workflow.py`) and its three task modules
still use the old task contract: tasks own idempotency, accept a `force` flag,
construct output paths internally, and return lists of paths.  This plan refactors
them to the new pure-processor contract documented in
`docs/development/how-to-add-workflow-task.md`, where the workflow owns file
discovery, path construction, idempotency, and looping.

Additionally, the workflow's `_resolve_voltage_csvs` helper is missing
`voltages_tagged.csv` in its fallback chain (corrected > **tagged** > raw).

## Problem Statement

The preprocessing workflow tasks have already been moving toward the new contract.
The analysis workflow lags behind, creating two competing patterns in the same
codebase.  This causes confusion about where responsibilities live (idempotency,
path construction, force flags) and makes the workflow harder to extend.

## Goals

### In Scope
1. Refactor `plot_session_voltages`, `analyse_stim_intervals`, and
   `sex_based_voltage_analysis` to pure-processor signatures (no idempotency,
   no force flag, return `None`)
2. Update `analysis_workflow.py` to the new executor loop pattern with
   `inputs`/`outputs` lambdas, `store` keys, and workflow-owned
   `should_process_task`
3. Add `voltages_tagged.csv` to the voltage CSV fallback chain
4. Keep standalone `main()` entry points working in each task module

### Out of Scope
- Refactoring `preprocessing_workflow.py` to the new contract (separate effort)
- Changing the analysis logic or output format of any task
- Modifying the DAG YAML config (dependencies are already correct)
- Domain-level improvements to `sex_based_voltage_analysis` (sensitivity analysis,
  FDR correction, operator-mediated framing)

## Success Criteria

- [ ] All three task `run_*` functions accept explicit named paths and return `None`
- [ ] No task module imports `should_process_task` or `clean_task_outputs`
- [ ] `analysis_workflow.py` uses `inputs`/`outputs` lambdas with `store` keys
- [ ] `_resolve_voltage_csvs` includes `voltages_tagged.csv` in the fallback chain
- [ ] Standalone `main()` in each task module still works (`--help` exits cleanly)
- [ ] `pytest` passes with no regressions
- [ ] End-to-end `python scripts/analysis_workflow.py` produces the same outputs

---

## Technical Design

### Approach

Follow the executor loop pattern from `how-to-add-workflow-task.md` exactly.
Each task becomes a pure processor with fully-resolved path parameters.  The
workflow handles discovery, path construction, idempotency, and (for
`plot_session_voltages`) per-session looping.

For `sex_based_voltage_analysis` (13 outputs), passing all outputs as named
parameters is impractical.  Instead, pass `output_dir: Path` to the task and
provide a separate `output_files` lambda in the workflow stage for the
idempotency check.

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Full refactor to new contract | Consistent codebase, matches docs | More files to change | **Chosen** |
| Minimal fix (tagged CSV only) | Small diff | Leaves two competing patterns | Rejected |
| NamedTuple return for multi-output tasks | Type-safe outputs | Rejected by contract (tasks return `None`, workflow owns paths) | Rejected |
| Pass all 13 sex-analysis outputs as named params | Fully explicit | Long parameter list code smell | Rejected; use `output_dir` + `output_files` lambda |

### Architecture Changes

No new modules.  Existing files are modified to shift responsibilities from
tasks to the workflow.

```
BEFORE                                  AFTER
------                                  -----
Task owns:                              Workflow owns:
  - should_process_task()                 - should_process_task()
  - clean_task_outputs()                  - clean_task_outputs()
  - output path construction              - output path construction
  - force flag                            - force flag
  - per-session looping                   - per-session looping
  - returns List[Path]                  Task owns:
                                          - pure processing logic
                                          - returns None
```

---

## Implementation Plan

### Phase 1: Task Module Refactoring

**Goal:** Convert all three task `run_*` functions to pure-processor signatures.

#### 1a. `plot_session_voltages.py`

- [ ] Change `plot_session()` to accept `output_path: Path` instead of
      `output_dir: Path` (remove internal filename construction at line 161)
- [ ] Rewrite `run_plot_session_voltages` to new per-session signature:
      ```python
      def run_plot_session_voltages(input_csv: Path, output_png: Path) -> None
      ```
- [ ] Remove `should_process_task`, `clean_task_outputs` imports and calls
- [ ] Remove `force` parameter and `List` return
- [ ] Update standalone `main()` to do its own loop + idempotency

**Files Modified:**
- `scripts/analysis/plot_session_voltages.py` — signature change, remove orchestration

#### 1b. `analyse_stim_intervals.py`

- [ ] Rewrite `run_analyse_stim_intervals` to new batch signature:
      ```python
      def run_analyse_stim_intervals(
          session_dirs: list[Path],
          output_csv: Path,
          output_duration_png: Path,
          output_voltage_png: Path,
      ) -> None
      ```
- [ ] Refactor `analyse_all_sessions()` to accept `session_dirs: list[Path]`
      instead of `preprocess_dir: Path` (remove internal globbing at line 296-298)
- [ ] Remove `should_process_task`, `clean_task_outputs` imports and calls
- [ ] Remove `force` parameter, input-resolution logic (lines 473-488),
      and `List` return
- [ ] Keep `detect_active_intervals` and `classify_intervals` as public exports
- [ ] Update standalone `main()` to do its own discovery + idempotency

**Files Modified:**
- `scripts/analysis/analyse_stim_intervals.py` — signature change, remove orchestration

#### 1c. `sex_based_voltage_analysis.py`

- [ ] Rewrite `run_sex_based_voltage_analysis` to new signature:
      ```python
      def run_sex_based_voltage_analysis(
          interval_summary_csv: Path,
          excel_path: Path,
          condition_report_csv: Path,
          preprocess_dir: Path,
          output_dir: Path,
      ) -> None
      ```
- [ ] Rename `_CSV_NAMES` / `_PNG_NAMES` to `CSV_OUTPUT_NAMES` / `PNG_OUTPUT_NAMES`
      (public constants for workflow idempotency)
- [ ] Remove `should_process_task`, `clean_task_outputs` imports and calls
- [ ] Remove `force` parameter, input-sniffing logic (lines 1158-1172),
      and `List` return
- [ ] Update standalone `main()` to do its own discovery + idempotency

**Files Modified:**
- `scripts/analysis/sex_based_voltage_analysis.py` — signature change, remove orchestration

**Dependencies:** None

---

### Phase 2: Workflow Orchestrator Refactoring

**Goal:** Update `analysis_workflow.py` to the new executor loop pattern.

- [ ] Fix `_resolve_voltage_csvs` to add `voltages_tagged.csv` as middle
      priority: `corrected > tagged > raw`
- [ ] Add a per-session `_resolve_voltage_csv(session_dir) -> Path | None`
      helper for the plot loop
- [ ] Import `should_process_task`, `clean_task_outputs` from
      `utils.should_process_task`
- [ ] Rewrite the `plot_session_voltages` invocation as an explicit per-session
      loop (workflow loops over sessions, calls task once per CSV/PNG pair,
      with `should_process_task` check per pair)
- [ ] Rewrite `analyse_stim_intervals` stage with `inputs`/`outputs` lambdas
      and `store: ["output_csv"]`
- [ ] Rewrite `sex_based_voltage_analysis` stage with `inputs`/`outputs` lambdas
      and an `output_files` lambda for the idempotency check
- [ ] Replace old executor loop (lines 73-103) with new pattern from
      `how-to-add-workflow-task.md` (lines 130-164)

**Files Modified:**
- `scripts/analysis_workflow.py` — executor loop, helper functions, stage definitions

**Dependencies:** Phase 1

---

### Phase 3: Exports and Verification

**Goal:** Update exports and verify everything works.

- [ ] Update `scripts/analysis/__init__.py` to add
      `CSV_OUTPUT_NAMES`, `PNG_OUTPUT_NAMES` exports
- [ ] Run import check:
      `python -c "from scripts.analysis import run_plot_session_voltages, run_analyse_stim_intervals, run_sex_based_voltage_analysis"`
- [ ] Verify standalone entry points: `--help` for each task module
- [ ] Run `pytest`
- [ ] End-to-end run of `python scripts/analysis_workflow.py`

**Files Modified:**
- `scripts/analysis/__init__.py` — add constant exports

**Dependencies:** Phase 2

---

## Testing Plan

### Unit Tests
- [ ] Existing `pytest` suite passes without modification
- [ ] (No new unit tests — this is a contract refactor, not new logic)

### Integration Tests
- [ ] `python scripts/analysis/plot_session_voltages.py --help` exits cleanly
- [ ] `python scripts/analysis/analyse_stim_intervals.py --help` exits cleanly
- [ ] `python scripts/analysis/sex_based_voltage_analysis.py --help` exits cleanly

### Manual Verification
- [ ] Run `python scripts/analysis_workflow.py` end-to-end against real data
- [ ] Confirm output files match previous run (same CSVs and PNGs produced)
- [ ] Confirm `voltages_tagged.csv` is now picked up when
      `voltages_corrected.csv` is absent

### Edge Cases
- [ ] Session directory with only `voltages_tagged.csv` (no corrected, no raw)
- [ ] Empty session directory list (no sessions to process)
- [ ] `sex_based_voltage_analysis` with missing optional inputs (falls back to defaults in `main()`)

---

## Documentation Plan

- [ ] No README/CLAUDE.md changes needed (architecture section still accurate)
- [ ] The task contract is already documented in `how-to-add-workflow-task.md`
- [ ] Inline docstrings updated on refactored `run_*` functions

---

## Rollback Plan

1. All changes are on a feature branch — revert by not merging
2. No data migrations or schema changes
3. Git revert of the merge commit if issues found post-merge

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Standalone `main()` breaks | Medium | Low | Test each `--help` explicitly |
| Idempotency behavior changes subtly | Low | Medium | End-to-end test with force=false then force=true |
| `sex_based_voltage_analysis` input resolution breaks | Medium | Medium | Explicit named params eliminate ambiguity; test with real data |
| Per-session plot loop is slower than batch | Low | Low | `should_process_task` skips up-to-date sessions as before |
