# Plan: Encode Zero-Order-Hold Semantics in Voltage Timeseries Files

**Date:** 2026-03-30
**Status:** In Progress
**Branch:** `feature/encode-timeseries-interpolation`

---

## Overview

Make the implicit zero-order-hold / forward-fill semantic of `voltages.csv` explicit in the data artefacts themselves. Currently the plotting script encodes this correctly (`drawstyle="steps-post"`), but nothing in the files states that voltage values are held constant until the next row. A future reader loading the CSV without context could plausibly interpolate linearly, corrupting any downstream analysis.

## Problem Statement

`voltages.csv` is an event log: each row records the system voltage state after a ramp completes, and that state persists until the next row changes it. This is a zero-order-hold (step-function) timeseries. The interpretation is only visible in the plotting script's `drawstyle="steps-post"` argument — not in the data files themselves. Any tool that loads the CSV naively (Excel, a new analysis script, a collaborator) has no signal that linear interpolation would be wrong.

## Goals

### In Scope
1. Add a machine-readable `"timeseries_interpolation"` field to every `metadata.json` produced by `03_extract_session_data.py`.
2. Prepend a human-readable `# interpolation: zero_order_hold` comment to every `voltages.csv` produced by the same script.
3. Update `05_plot_session_voltages.py` to skip the comment header when loading CSVs.

### Out of Scope
- Retroactively rewriting already-produced `voltages.csv` / `metadata.json` files (existing data in `backlogs_local_data/`).
- Changing the CSV format, column names, or timestamp representation.
- Converting to HDF5, Parquet, or any other binary format.

## Success Criteria

- [ ] `metadata.json` for every newly extracted session contains `"timeseries_interpolation": "zero_order_hold"`.
- [ ] `voltages.csv` for every newly extracted session has `# interpolation: zero_order_hold` as its first line.
- [ ] `05_plot_session_voltages.py` produces identical plots before and after this change (comment line is transparently skipped).
- [ ] `pd.read_csv(path, comment='#')` on a new `voltages.csv` returns the same DataFrame as before.

---

## Technical Design

### Approach

Two complementary changes, both minimal and additive:

1. **`# comment` header in the CSV** — Write `# interpolation: zero_order_hold\n` as the first line before the column header. This is a well-established convention in scientific Python (NumPy `savetxt`, astropy tables, many instrument data formats). It makes the file self-describing without breaking any pandas reader that passes `comment='#'`.

2. **Field in companion JSON** — Add `"timeseries_interpolation": "zero_order_hold"` to the metadata dict in `03_extract_session_data.py`. The field sits alongside existing protocol and hardware metadata, is machine-readable by any downstream code that loads `metadata.json`, and requires no CSV change.

Both changes apply to the same production point: the `build_voltage_df` / write step in `03_extract_session_data.py`.

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|---|---|---|---|
| `# comment` header in CSV + JSON field | Self-contained in CSV; also machine-readable in JSON; no format change | pandas needs `comment='#'` parameter | **Chosen** |
| JSON field only | Purely machine-readable; zero CSV change | CSV is not self-describing without companion file | Rejected (insufficient) |
| Frictionless Data `datapackage.json` sidecar | Full open standard; encodes column types and constraints | Extra dependency; overkill for this project | Rejected |
| Column naming convention (`A1_hold`) | Zero extra files | Weak signal; not machine-enforceable | Rejected |
| HDF5 / Parquet with dataset attributes | Gold standard for scientific timeseries | Major format migration; heavy dependencies | Rejected |

### Architecture Changes

No new modules. Two existing files modified, one existing file updated to stay compatible.

---

## Implementation Plan

### Phase 1: Update the extractor

**Goal:** Emit the comment header and JSON field from `03_extract_session_data.py`.

- [x] Task 1.1 — In the function that writes `voltages.csv`, prepend `# interpolation: zero_order_hold\n` before calling `df.to_csv()`. Use `f.write(...)` then `df.to_csv(f, ...)` on an open file handle, or write the header line separately and then append.
- [x] Task 1.2 — In the metadata dict construction (both `log` and `csv` format branches), add `"timeseries_interpolation": "zero_order_hold"`.

**Files Modified:**
- `scripts/analysis/03_extract_session_data.py` — comment header in CSV write; new field in metadata dict

**Dependencies:** None

### Phase 2: Update the plotter

**Goal:** Ensure `05_plot_session_voltages.py` handles the comment header transparently.

- [x] Task 2.1 — Add `comment='#'` to the `pd.read_csv()` call in `plot_session()`.

**Files Modified:**
- `scripts/analysis/05_plot_session_voltages.py` — `comment='#'` parameter

**Dependencies:** Phase 1

---

## Testing Plan

### Manual Verification
- [ ] Run `03_extract_session_data.py` on one session; open the output `voltages.csv` and confirm line 1 is `# interpolation: zero_order_hold`.
- [ ] Open the output `metadata.json` and confirm it contains `"timeseries_interpolation": "zero_order_hold"`.
- [ ] Run `05_plot_session_voltages.py`; confirm plots generate without error and are visually identical to pre-change plots.

### Edge Cases
- [ ] Load the new `voltages.csv` with plain `pd.read_csv(path, comment='#')` in an interactive session and verify the DataFrame shape and dtypes are unchanged.
- [ ] Confirm that `pd.read_csv(path)` without `comment='#'` would fail (or misparse), documenting why the parameter is now required.

---

## Documentation Plan

- [ ] No README or CLAUDE.md changes required — the change is internal to two analysis scripts.

---

## Rollback Plan

Both changes are additive (extra line in CSV, extra field in JSON). To revert:
1. Remove the `f.write(comment_line)` call in `03_extract_session_data.py`.
2. Remove `"timeseries_interpolation"` from the metadata dict.
3. Remove `comment='#'` from the `pd.read_csv()` call in `05_plot_session_voltages.py`.

No data migration required; existing files in `backlogs_local_data/` are unaffected.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Downstream scripts load `voltages.csv` without `comment='#'` and get a garbled first row | Low | Medium | Audit all other scripts that call `pd.read_csv` on `voltages.csv` before merging |
| `df.to_csv()` on an open file handle behaves differently across pandas versions | Low | Low | Test on the `ti` conda env (Python 3.13, pinned versions in `requirements.txt`) |

---

## References

- Plotting script: `scripts/analysis/05_plot_session_voltages.py`
- Extractor script: `scripts/analysis/03_extract_session_data.py`
- Related active plan: `docs/development/plans/active/fix-log-voltage-extraction.md`
