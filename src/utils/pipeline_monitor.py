"""Pipeline monitor — simple status tracker for batch workflows."""

import logging
from typing import List


class PipelineMonitor:
    """
    Tracks task execution status across datasets.

    Logs status updates to the console. Extend this class to add
    Excel reporting, live plotting, or other monitoring backends.
    """

    def __init__(self, stages: List[str]):
        self.stages = stages
        self._status: dict = {}

    def update(
        self, dataset: str, stage: str, status: str, message: str = ""
    ) -> None:
        """Record a status update for a (dataset, stage) pair."""
        self._status[(dataset, stage)] = status
        log_msg = f"[Monitor] {dataset} / {stage}: {status}"
        if message:
            log_msg += f" — {message}"

        if status == "FAILURE":
            logging.error(log_msg)
        else:
            logging.info(log_msg)

    def summary(self) -> dict:
        """Return the current status map."""
        return dict(self._status)
