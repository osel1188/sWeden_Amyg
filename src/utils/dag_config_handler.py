"""DAG configuration handler — loads YAML and manages task execution order."""

import copy
from pathlib import Path
from typing import Any, Dict, List, Set

import yaml


class DagConfigHandler:
    """
    Loads a DAG YAML config and tracks task completion for dependency-aware execution.

    Expected YAML structure::

        parameters:
          param_name: value

        tasks:
          task_name:
            enabled: true
            options:
              force_processing: false
            depends_on: [other_task]
    """

    def __init__(self, config_path: Path):
        if not config_path.exists():
            raise FileNotFoundError(f"DAG config not found: {config_path}")
        with open(config_path, "r") as f:
            self.config: Dict[str, Any] = yaml.safe_load(f)
        self.tasks: Dict[str, Any] = self.config.get("tasks", {})
        self.parameters: Dict[str, Any] = self.config.get("parameters", {})
        self.completed_tasks: Set[str] = set()

    def get_parameter(self, name: str, default: Any = None) -> Any:
        """Retrieve a global parameter from the config."""
        return self.parameters.get(name, default)

    def get_task_options(self, task_name: str) -> Dict[str, Any]:
        """Return the ``options`` dict for *task_name* (empty dict if absent)."""
        return self.tasks.get(task_name, {}).get("options", {})

    def can_run(self, task_name: str) -> bool:
        """True if *task_name* is enabled and all its dependencies are completed."""
        task_config = self.tasks.get(task_name)
        if not task_config:
            print(f"Warning: Task '{task_name}' not in DAG config. Skipping.")
            return False
        if not task_config.get("enabled", False):
            return False
        deps: List[str] = task_config.get("depends_on", [])
        return set(deps).issubset(self.completed_tasks)

    def mark_completed(self, task_name: str) -> None:
        """Mark *task_name* as completed so dependent tasks can run."""
        if task_name in self.tasks:
            self.completed_tasks.add(task_name)
            print(f"Task '{task_name}' completed.")
        else:
            print(f"Warning: Attempted to mark unknown task '{task_name}' as completed.")

    def copy(self) -> "DagConfigHandler":
        """Deep copy for independent per-session processing."""
        return copy.deepcopy(self)
