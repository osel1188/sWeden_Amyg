# Plan: Align Preprocessing Task Contracts with How-To Guide

**Date:** 2026-04-01
**Author:** Basil
**Status:** Draft
**Branch:** `feature/align-preprocessing-contracts`

---

## Overview

The five preprocessing task modules were migrated during the `reorganise-scripts-into-workflows` effort using an older convention (`input_items: List[Path]`, `force: bool`, `-> List[Path]`). The canonical how-to guide (`docs/development/how-to-add-workflow-task.md`) prescribes a stricter contract (`input_path: Path`, `force_processing: bool`, `-> Path`). This plan aligns all five tasks, extracts shared business logic into `src/preprocessing/`, and fixes the workflow script's force-injection mapping.

## Problem Statement

The preprocessing tasks deviate from the documented task contract in four ways:

1. **Generic `List[Path]` parameters** instead of explicit, domain-specific `Path` inputs
2. **`force` parameter** instead of the standard `force_processing`
3. **`List[Path]` returns** instead of `Path` or `tuple[Path, ...]`
4. **Missing `*` keyword-only separator** on 3 of 5 tasks

Additionally, `src/preprocessing/` is empty — all business logic (parsers, algorithms, dataclasses, CSV I/O helpers) lives inside `scripts/preprocessing/` task modules, violating the `src/` vs `scripts/` separation the guide requires.

## Goals

### In Scope
1. Refactor all 5 task function signatures to match the how-to guide contract
2. Extract shared business logic from `scripts/preprocessing/` into `src/preprocessing/`
3. Fix the `force` → `force_processing` injection in `preprocessing_workflow.py`
4. Update context wiring (lambdas, seed values, output keys) for `Path` returns
5. Update standalone `main()` entry points and module docstrings

### Out of Scope
- Changes to algorithm logic within any task
- Aligning analysis workflow tasks (separate plan)
- Adding new tasks or changing the DAG dependency order
- Changes to `correct_intervals_gui.py` (standalone, not part of DAG)

## Success Criteria

- [ ] All 5 `run_*` functions match the contract: `(input_dir: Path, output_dir: Path, *, force_processing: bool = False) -> Path`
- [ ] `src/preprocessing/` contains extracted business logic (parsers, algorithms, types, I/O helpers)
- [ ] `scripts/preprocessing/` task modules contain only orchestration, idempotency, and task-specific I/O
- [ ] `preprocessing_workflow.py` injects `force_processing` (not `force`)
- [ ] Full pipeline runs end-to-end without errors
- [ ] Each task's standalone `main()` works correctly
- [ ] No imports from `scripts/preprocessing/` inside `src/preprocessing/` (one-way dependency)
- [ ] `grep -r "force: bool" scripts/preprocessing/` returns zero matches

---

## Technical Design

### Approach

Two-phase refactor: first extract shared code into `src/preprocessing/` (pure move, no behavioral changes), then align all signatures and wiring in a single coordinated change.

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Big-bang: signatures + extraction in one pass | Single PR, fewer intermediate states | Large diff, harder to review | Rejected |
| Extract first, then align signatures | Each phase is independently testable | Two PRs, but clean separation | **Chosen** |
| Signatures only, skip extraction | Smaller scope | Leaves business logic in wrong layer | Rejected |

### Architecture Changes

**New modules in `src/preprocessing/`:**

```
src/preprocessing/
├── __init__.py              (re-exports)
├── io.py                    (CommentedCsvReader, CommentedCsvWriter)
├── types.py                 (TagConfig, ChannelResult, SessionResult, CHANNELS)
├── identifiers.py           (extract_ids_from_excel, extract_id_from_folder)
├── session_parser.py        (parse_log_file, parse_csv_session, build_voltage_df, helpers)
├── resampling.py            (compute_sampling_rate, resample_session)
├── validation.py            (load_conditions, extract_frequencies, is_valid)
├── interval_tagger.py       (IntervalTagger class)
└── interval_plot.py         (IntervalPlotSaver class)
```

**Signature change pattern (all 5 tasks):**

```python
# Before
def run_task(input_items: List[Path], output_dir: Path, force: bool = False) -> List[Path]:

# After
def run_task(input_dir: Path, output_dir: Path, *, force_processing: bool = False) -> Path:
```

Each task internally enumerates `input_dir` to find its expected files (e.g., `sorted(input_dir.glob("*/voltages.csv"))`).

---

## Implementation Plan

### Phase 1: Extract Shared Code to `src/preprocessing/`
**Goal:** Move all reusable business logic out of task modules. No signature changes. No behavioral changes.

- [ ] Task 1.1 — Create `src/preprocessing/io.py` with `CommentedCsvReader` and `CommentedCsvWriter` (from `tag_voltage_intervals.py` lines 76–104)
- [ ] Task 1.2 — Create `src/preprocessing/types.py` with `TagConfig`, `ChannelResult`, `SessionResult` (from `tag_voltage_intervals.py` lines 43–68) and `CHANNELS` constant
- [ ] Task 1.3 — Create `src/preprocessing/identifiers.py` with `extract_ids_from_excel`, `extract_id_from_folder` (from `filter_valid_sessions.py` lines 33–95)
- [ ] Task 1.4 — Create `src/preprocessing/session_parser.py` with log/CSV parsing functions and regex constants (from `extract_session_data.py` lines 31–585)
- [ ] Task 1.5 — Create `src/preprocessing/resampling.py` with `compute_sampling_rate`, `resample_session` (from `resample_voltages.py` lines 48–132)
- [ ] Task 1.6 — Create `src/preprocessing/validation.py` with `load_conditions`, `extract_frequencies`, `is_valid` (from `validate_session_metadata.py` lines 37–84)
- [ ] Task 1.7 — Create `src/preprocessing/interval_tagger.py` with `IntervalTagger` class (from `tag_voltage_intervals.py` lines 112–264)
- [ ] Task 1.8 — Create `src/preprocessing/interval_plot.py` with `IntervalPlotSaver` class (from `tag_voltage_intervals.py` lines 272–361)
- [ ] Task 1.9 — Update `src/preprocessing/__init__.py` with public re-exports
- [ ] Task 1.10 — Update all 5 task modules to import from `src/preprocessing/` instead of defining locally
- [ ] Task 1.11 — Update `resample_voltages.py` import of `CommentedCsvReader`/`Writer` (currently cross-imports from `tag_voltage_intervals`)
- [ ] Task 1.12 — Verify pipeline runs end-to-end, no behavioral change

**Files Created:**
- `src/preprocessing/io.py`
- `src/preprocessing/types.py`
- `src/preprocessing/identifiers.py`
- `src/preprocessing/session_parser.py`
- `src/preprocessing/resampling.py`
- `src/preprocessing/validation.py`
- `src/preprocessing/interval_tagger.py`
- `src/preprocessing/interval_plot.py`

**Files Modified:**
- `src/preprocessing/__init__.py` — add re-exports
- `scripts/preprocessing/filter_valid_sessions.py` — remove extracted functions, add imports
- `scripts/preprocessing/extract_session_data.py` — remove extracted functions, add imports
- `scripts/preprocessing/validate_session_metadata.py` — remove extracted functions, add imports
- `scripts/preprocessing/resample_voltages.py` — remove extracted functions, add imports
- `scripts/preprocessing/tag_voltage_intervals.py` — remove extracted classes, add imports

**Dependencies:** None

### Phase 2: Align Function Signatures
**Goal:** Update all 5 `run_*` signatures, the workflow script, and standalone `main()` functions to match the how-to guide contract.

- [ ] Task 2.1 — `filter_valid_sessions.py`: rename `input_items` → `input_dir`, `force` → `force_processing`, add `*` separator, return `Path` (output_dir)
- [ ] Task 2.2 — `extract_session_data.py`: rename `input_items` → `input_dir`, `force` → `force_processing`, add `*` separator, return `tuple[Path, Path]` → simplify to `Path` (output_dir)
- [ ] Task 2.3 — `validate_session_metadata.py`: rename `input_metadata_paths` → `input_dir`, `force` → `force_processing`, add `*` separator, return `Path` (report CSV path)
- [ ] Task 2.4 — `resample_voltages.py`: rename `input_items` → `input_dir`, `force` → `force_processing`, return `Path` (output_dir). Already has `*` separator.
- [ ] Task 2.5 — `tag_voltage_intervals.py`: rename `input_items` → `input_dir`, `force` → `force_processing`, add `*` separator, return `Path` (output_dir)
- [ ] Task 2.6 — Fix `preprocessing_workflow.py` line 95: `params["force"]` → `params["force_processing"]`
- [ ] Task 2.7 — Update `preprocessing_workflow.py` context seed: `"raw_session_dirs"` (list) → `"raw_data_dir"` (Path)
- [ ] Task 2.8 — Update all `pipeline_stages` params lambdas: `"input_items"` → `"input_dir"`, list values → Path values
- [ ] Task 2.9 — Update context output key storage to handle `Path` returns instead of `List[Path]`
- [ ] Task 2.10 — Update each module's standalone `main()` to pass renamed parameters
- [ ] Task 2.11 — Update module-level docstring contracts in all 5 task modules
- [ ] Task 2.12 — Add `save_plot: true` to `tag_voltage_intervals` options in `config/preprocessing_workflow_dag.yaml`
- [ ] Task 2.13 — Verify pipeline runs end-to-end with updated signatures

**Files Modified:**
- `scripts/preprocessing/filter_valid_sessions.py` — signature + main()
- `scripts/preprocessing/extract_session_data.py` — signature + main()
- `scripts/preprocessing/validate_session_metadata.py` — signature + main()
- `scripts/preprocessing/resample_voltages.py` — signature + main()
- `scripts/preprocessing/tag_voltage_intervals.py` — signature + main()
- `scripts/preprocessing_workflow.py` — force injection, lambdas, context
- `config/preprocessing_workflow_dag.yaml` — add save_plot option

**Dependencies:** Phase 1

---

## Testing Plan

### Integration Tests
- [ ] Run `python scripts/preprocessing_workflow.py` end-to-end on existing data — all 5 tasks succeed
- [ ] Run with `force_processing: true` in YAML — all tasks reprocess
- [ ] Run twice without force — second run skips all tasks (idempotency)

### Standalone Task Tests
- [ ] Each task's `main()` CLI entry point works independently
- [ ] `python scripts/preprocessing/resample_voltages.py --help` shows correct parameter names

### Structural Verification
- [ ] `grep -r "force: bool" scripts/preprocessing/` returns zero matches
- [ ] `grep -r "List\[Path\]" scripts/preprocessing/` returns zero matches in `run_*` signatures
- [ ] `grep -r "from scripts" src/preprocessing/` returns zero matches (one-way dependency)

### Existing Tests
- [ ] `pytest` — all existing tests pass

---

## Documentation Plan

- [ ] Update `docs/development/how-to-add-workflow-task.md` if any edge cases were discovered
- [ ] Update CLAUDE.md if architecture section needs updating

---

## Rollback Plan

1. **Phase 1 is independently revertable** — revert the extraction commit, task modules regain their local definitions
2. **Phase 2 must revert as a unit** — signatures and workflow script must stay in sync
3. **No data migration** — only code changes; output files are unchanged
4. **Git revert** — `git revert <phase-commit>` cleanly undoes either phase

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Cross-import between `resample_voltages` and `tag_voltage_intervals` breaks during extraction | Medium | Low | Task 1.11 explicitly handles this; both import from `src/preprocessing/io` after extraction |
| `extract_session_data` return type change breaks downstream context wiring | Medium | Medium | Phase 2 updates all consumers atomically; integration test catches mismatches |
| Standalone `main()` functions silently accept old parameter names | Low | Low | Structural grep verification catches leftover `force: bool` parameters |
| Active resample-voltages branch conflicts with this plan | Medium | Low | This plan supersedes the old convention; merge resample-voltages first, then align |

---

## References

- How-to guide: `docs/development/how-to-add-workflow-task.md`
- Completed reorganisation: `docs/development/plans/completed/reorganise-scripts-into-workflows.md`
- Active resample-voltages plan: `docs/development/plans/active/resample-voltages.md`
- Python standards: `docs/development/python-standards.md`
