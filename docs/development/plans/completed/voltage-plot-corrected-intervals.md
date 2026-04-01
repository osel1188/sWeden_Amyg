# Plan: Update Voltage Plot to Use Corrected Intervals

**Date:** 2026-03-30
**Author:** Basil
**Status:** Completed
**Completed:** 2026-04-01
**Branch:** `feature/interval-correction-workflow`

---

## Overview

Update `scripts/analysis/05_plot_session_voltages.py` to prefer `voltages_corrected.csv` as its
input source, shade the background using the consensus `interval` column (not per-channel
columns), and default to a single combined axes showing all four channels.

## Problem Statement

The GUI correction workflow (`04_05b_correct_intervals_gui.py`) produces `voltages_corrected.csv`
with a manually-validated `interval` column. The plotting script still reads `voltages_tagged.csv`
and uses per-channel `{ch}_interval` columns for shading, so the human corrections are never
reflected in the output PNGs. The default 2×2 split layout is also less useful for quick review
than a single combined axes.

## Goals

### In Scope
1. Prefer `voltages_corrected.csv`; fall back to `voltages_tagged.csv`, then `voltages.csv`
2. Replace per-channel shading with consensus-`interval` shading (Block 1 / Block 2 colours)
3. Default to combined single-axes layout (`SPLIT_CHANNELS = False`)

### Out of Scope
- Changes to any upstream scripts (`04_05`, `04_05b`, `06_analyse_stim_intervals.py`, etc.)
- New output directories or file-naming conventions
- Interactive/live-preview mode

## Success Criteria

- [ ] Generated PNGs reflect boundaries from `voltages_corrected.csv` where available
- [ ] Background shading shows two distinct block colours derived from the `interval` column
- [ ] All four channels appear on a single axes by default
- [ ] Sessions without a corrected file still produce a PNG (graceful fallback)
- [ ] `SPLIT_CHANNELS = True` still produces a working 2×2 layout

---

## Technical Design

### Approach

Minimal targeted changes to the single script file. No new modules. Reuse the existing
`_plot_combined` / `_plot_split` structure; only replace the shading helper and the
file-resolution logic.

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Replace per-channel shading with consensus shading | Simple, one function | Per-channel detail lost | Chosen — detail is in the line colours anyway |
| Add a second shading layer (keep both) | More information | Cluttered, ambiguous | Rejected |
| Separate script for corrected files | No risk to existing users | Duplication, divergence | Rejected |

### Architecture Changes

Single file modified: `scripts/analysis/05_plot_session_voltages.py`

- Add `BLOCK_COLOURS` constant
- Remove `_shade_intervals(ax, df, channel, colour)`
- Add `_shade_consensus_intervals(ax, df)`
- Update `_plot_combined` and `_plot_split` to call the new helper
- Update `plot_session` file-resolution fallback chain
- Update `main()` status line reporting

---

## Implementation Plan

### Phase 1: Single-phase implementation

**Goal:** Apply all changes in one pass — the scope is small and changes are interdependent.

- [x] Change `SPLIT_CHANNELS = True` → `False`
- [x] Add `BLOCK_COLOURS = {1: "#1f77b4", 2: "#ff7f0e"}` constant
- [x] Remove `_shade_intervals`; add `_shade_consensus_intervals(ax, df)`:
  - Guard on `"interval" not in df.columns`
  - Iterate `interval_id` in `(1, 2)`, shade contiguous runs using run-length logic
  - Label only the first span of each block for the legend
- [x] Update `_plot_combined`: replace four `_shade_intervals` calls with one `_shade_consensus_intervals(ax, df)`
- [x] Update `_plot_split`: replace per-subplot `_shade_intervals` calls with `_shade_consensus_intervals(ax, df)` (one call per subplot is fine — same column, same result)
- [x] Update `plot_session` file resolution:
  ```python
  corrected_path = csv_path.parent / "voltages_corrected.csv"
  tagged_path    = csv_path.parent / "voltages_tagged.csv"
  src_path = (
      corrected_path if corrected_path.exists() else
      tagged_path    if tagged_path.exists()    else
      csv_path
  )
  ```
- [x] Update `main()` reporting to count corrected and tagged sessions separately

**Files Modified:**
- `scripts/analysis/05_plot_session_voltages.py` — all changes above

**Dependencies:** None

---

## Testing Plan

### Manual Verification
- [ ] Run `python scripts/analysis/05_plot_session_voltages.py` — no errors
- [ ] Open a PNG for a session that has `voltages_corrected.csv` — confirm single axes, four channel lines, two shaded regions in blue/orange
- [ ] Confirm shaded boundaries match what was confirmed in the correction GUI
- [ ] Open a PNG for a session that has only `voltages_tagged.csv` — shading still appears (from `interval` column written by `04_05`)
- [ ] Open a PNG for a session with only `voltages.csv` — no shading, no crash

### Edge Cases
- [ ] Session where `interval` column is all zeros (no blocks detected) — no shading, no crash
- [ ] Session with a single block only — one shaded region, second colour absent from legend
- [ ] Temporarily set `SPLIT_CHANNELS = True` — 2×2 layout renders without error

---

## Documentation Plan

- [x] Update module docstring in `05_plot_session_voltages.py` to reflect new source priority and shading behaviour

---

## Rollback Plan

Single file change; revert via `git checkout scripts/analysis/05_plot_session_voltages.py`.
Output PNGs are regenerated artefacts — no data loss risk.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `interval` column absent in tagged CSVs (older format) | Low | Low | Guard already in new helper |
| Consensus block spans overlap (block 1 end > block 2 start) | Low | Low | Later block overwrites shading — same behaviour as `apply_corrections` |

---

## References

- Upstream tagging script: `scripts/analysis/04_05_tag_voltage_intervals.py`
- Correction GUI: `scripts/analysis/04_05b_correct_intervals_gui.py`
- Related plan: `docs/development/plans/active/interval-correction-workflow.md`
