# Plan: Tag Voltage Stimulation Intervals

**Permanent Location:** `docs/development/plans/pending/tag-voltage-intervals.md`

**Objective:**
Create an intermediate analysis script to identify and tag two stimulation intervals (including ramp-up and ramp-down) for each channel in the session voltage data.

**Key Files & Context:**
- **Input:** `backlogs_local_data/TILA_DATA_1_processed/*/voltages.csv`
- **Output:** `backlogs_local_data/TILA_DATA_1_processed/*/voltages_tagged.csv`
- **Script:** `scripts/analysis/04_05_tag_voltage_intervals.py`

**Implementation Steps:**

1.  **Script Setup:**
    - Create `scripts/analysis/04_05_tag_voltage_intervals.py`.
    - Define constants for:
        - `THRESHOLD_ON = 3.0` (V)
        - `MIN_DURATION_MIN = 20.0` (minutes)
        - `ZERO_THRESHOLD = 0.01` (V)

2.  **Processing Logic (per session):**
    - Load `voltages.csv`.
    - For each channel (`A1`, `A2`, `B1`, `B2`):
        - Initialize `[Channel]_interval` column with 0.
        - **Step 1: Find Core Blocks:** Identify contiguous sequences where voltage > `THRESHOLD_ON`.
        - **Step 2: Filter by Duration:** Keep only blocks where `(end_timestamp - start_timestamp) >= MIN_DURATION_MIN`.
        - **Step 3: Expand Boundaries:** For each kept block:
            - **Left Bound:** From the block start, move backwards in the dataframe until voltage <= `ZERO_THRESHOLD` or start of file is reached.
            - **Right Bound:** From the block end, move forwards in the dataframe until voltage <= `ZERO_THRESHOLD` or end of file is reached.
            - **Tagging:** Assign interval ID (1, 2, etc.) to the range `[left_bound, right_bound]` in the `[Channel]_interval` column.
    - Save the result to `voltages_tagged.csv`.

3.  **Error Handling & Logging:**
    - Log a summary of how many intervals were found per channel per session.
    - Warn if a channel does not have exactly two intervals detected.

4.  **Integration:**
    - This script fits between `04_validate_session_metadata.py` and `05_plot_session_voltages.py` (though `05` currently reads `voltages.csv`, it could be updated later to use tagged data if needed).

**Verification & Testing:**

1.  **Dry Run:** Run on a single session and manually inspect `voltages_tagged.csv` to ensure the interval column starts at the first 0V before the >3V block and ends at the first 0V after it.
2.  **Batch Run:** Execute on all processed sessions.
3.  **Validation:**
    - Check the console output for any "unexpected interval count" warnings.
    - Use a spreadsheet or `05_plot_session_voltages.py` (modified temporarily) to visualize the tags if necessary.
