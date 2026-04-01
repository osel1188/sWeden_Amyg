# Idea: Fix Stale Trigger State on Quick Restart

**Date:** 2026-02-26
**Status:** Idea

## Summary

When channels are ON, turned OFF (stop protocol), and reactivated shortly after (within the 10s idle debounce), the hardware outputs remain OFF because `TriggerManager` holds two stale flags from the previous run. No actual signal is produced despite software-side ramp-up proceeding normally.

## Rough Approach

Two-line fix in `TriggerManager._threaded_monitor_task` at the RUNNING-to-IDLE transition (line ~167 in `src/temporal_interference/services/trigger_manager.py`):

1. Reset `self._hardware_enabled = False` so the next start re-enables channel outputs.
2. Call `self.hw_manager.trigger_event.clear()` so the next start's ramp thread blocks on `trigger_event.wait()` until a fresh trigger is sent, instead of returning immediately from the stale event.

## Notes

- Root cause is dual: `HardwareManager._trigger_event` stays set (only cleared by `abort()` after debounce), and `_hardware_enabled` stays `True` (the stop task turns off outputs directly, bypassing TriggerManager's bookkeeping).
- The 10s debounce timer and its cleanup (`disable_all_channels` / `abort`) are unaffected by this change.
- Pre-existing test suite has import failures (`ElectrodeGroup` rename, stale mock paths) unrelated to this fix.
