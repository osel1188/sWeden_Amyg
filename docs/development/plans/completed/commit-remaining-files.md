# Plan: Commit Remaining Uncommitted Files on dev

**Date:** 2026-04-01
**Author:** Basil
**Status:** Completed

---

## Overview

Organize and commit all uncommitted changes on `dev` into logical, well-scoped
commits following the project's `type(scope): description` convention. The branch
has accumulated 8 file changes across docs, config, and code that need clean
grouping before further work proceeds.

## Problem Statement

The `dev` branch has uncommitted changes spanning documentation rewrites, plan
housekeeping, export additions, and parameter tuning. Committing them as a single
blob would obscure intent; they need logical grouping to maintain a readable
git history.

## Goals

### In Scope
1. Commit all uncommitted changes on `dev` in logical groups
2. Follow the project's conventional-commit message style
3. Preserve the correct order (docs before code that references them)

### Out of Scope
- Pushing to remote
- Creating a PR
- Any code modifications beyond what's already changed

## Success Criteria

- [ ] `git status` shows a clean working tree
- [ ] Each commit has a clear, scoped message
- [ ] `git log --oneline -5` shows 5 well-organized commits
- [ ] `git diff HEAD~5` aggregate diff matches the current uncommitted changes

---

## Technical Design

### Approach

Group the 8 changed files into 5 commits by theme. Order docs-first so that
code commits can reference updated documentation.

### Uncommitted Changes Inventory

| File | Change Summary | Commit Group |
|------|---------------|--------------|
| `docs/development/plans/pending/log-splitter.md` | Deleted (completed) | 1 — Plan cleanup |
| `docs/development/plans/pending/tag-voltage-intervals.md` | Deleted (completed) | 1 — Plan cleanup |
| `docs/development/how-to-add-workflow-task.md` | Rewritten for new pure-processor contract | 2 — Workflow docs |
| `docs/development/plans/pending/align-analysis-task-contracts.md` | New plan (untracked) | 3 — New plan |
| `scripts/analysis/__init__.py` | Export `CSV_OUTPUT_NAMES`, `PNG_OUTPUT_NAMES` | 4 — Analysis exports |
| `config/analysis_workflow_dag.yaml` | `force_processing: true` for sex analysis | 5 — Param tweaks |
| `scripts/preprocessing/resample_voltages.py` | `monitor` default `True` → `False` | 5 — Param tweaks |
| `scripts/preprocessing/tag_voltage_intervals.py` | `min_gap_min` `7.0` → `5.0` | 5 — Param tweaks |

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| 5 thematic commits | Clear intent per commit, readable history | More commits | **Chosen** |
| 1 big commit | Quick | Obscures intent, hard to revert selectively | Rejected |
| 3 commits (docs / code / config) | Fewer commits | Mixes unrelated doc changes together | Rejected |

---

## Implementation Plan

### Phase 1: Commit Sequence

**Goal:** Execute 5 sequential commits, each with staged files and a scoped message.

**Commit 1 — Clean up completed plans:**
- [ ] `git rm` the two deleted plan files
- [ ] Commit: `docs(plans): remove completed log-splitter and tag-voltage-intervals plans`

**Files:**
- `docs/development/plans/pending/log-splitter.md` — delete
- `docs/development/plans/pending/tag-voltage-intervals.md` — delete

**Commit 2 — Rewrite workflow task guide:**
- [ ] Stage `how-to-add-workflow-task.md`
- [ ] Commit: `docs(workflow): rewrite task guide for pure-processor contract pattern`

**Files:**
- `docs/development/how-to-add-workflow-task.md` — rewritten

**Commit 3 — Add new plan:**
- [ ] Stage untracked `align-analysis-task-contracts.md`
- [ ] Commit: `docs(plans): add plan for aligning analysis tasks with new contract`

**Files:**
- `docs/development/plans/pending/align-analysis-task-contracts.md` — new file

**Commit 4 — Export analysis constants:**
- [ ] Stage `__init__.py`
- [ ] Commit: `refactor(analysis): export CSV_OUTPUT_NAMES and PNG_OUTPUT_NAMES`

**Files:**
- `scripts/analysis/__init__.py` — add constant exports

**Commit 5 — Tune parameters:**
- [ ] Stage 3 files
- [ ] Commit: `fix(config): adjust force_processing, monitor default, and min_gap_min`

**Files:**
- `config/analysis_workflow_dag.yaml` — enable `force_processing` for sex analysis
- `scripts/preprocessing/resample_voltages.py` — default `monitor` to `False`
- `scripts/preprocessing/tag_voltage_intervals.py` — reduce `min_gap_min` to `5.0`

**Dependencies:** None (all changes already exist in the working tree)

---

## Testing Plan

### Manual Verification
- [ ] `git status` shows clean working tree after all commits
- [ ] `git log --oneline -5` shows 5 well-scoped commits
- [ ] `git diff HEAD~5` aggregate diff matches the pre-commit state

---

## Documentation Plan

- [ ] No additional documentation needed — changes are self-documenting via commit messages

---

## Rollback Plan

1. `git reset --soft HEAD~5` to undo all 5 commits while keeping changes staged
2. No data migrations or breaking changes involved

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Staging wrong files | Low | Low | Explicit `git add` per file, verify with `git status` before each commit |
| Commit message typo | Low | Low | Use HEREDOC for multi-line messages |
