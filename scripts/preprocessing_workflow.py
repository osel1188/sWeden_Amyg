import logging
from pathlib import Path
from typing import List

from utils.dag_config_handler import DagConfigHandler
from utils.task_executor import TaskExecutor
from utils.pipeline_monitor import PipelineMonitor

from scripts.preprocessing import (
    run_filter_valid_sessions,
    run_split_log_by_day,
    run_extract_session_data,
    run_validate_session_metadata,
    run_tag_voltage_intervals,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BACKLOGS = _PROJECT_ROOT / "backlogs_local_data"

_TASK_OUTPUT_DIRS = {
    "filter_valid_sessions":    _BACKLOGS / "TILA_DATA_0_valid",
    "split_log_by_day":         _BACKLOGS / "TILA_DATA_0_split",
    "extract_session_data":     _BACKLOGS / "TILA_DATA_1_processed",
    "validate_session_metadata": _BACKLOGS / "TILA_DATA_1_processed",
    "tag_voltage_intervals":    _BACKLOGS / "TILA_DATA_1_processed",
}

_TASK_FUNCS = {
    "filter_valid_sessions":    run_filter_valid_sessions,
    "split_log_by_day":         run_split_log_by_day,
    "extract_session_data":     run_extract_session_data,
    "validate_session_metadata": run_validate_session_metadata,
    "tag_voltage_intervals":    run_tag_voltage_intervals,
}

_AVAILABLE_TASKS = [
    "filter_valid_sessions",
    "split_log_by_day",
    "extract_session_data",
    "validate_session_metadata",
    "tag_voltage_intervals",
]


def run_batch(
    input_items: List[Path],
    dag_handler: DagConfigHandler,
    monitor: PipelineMonitor,
) -> dict:
    results = {}
    current_items = input_items

    for task_name in _AVAILABLE_TASKS:
        if task_name not in dag_handler.tasks or not dag_handler.tasks[task_name].get("enabled", False):
            continue

        task_func = _TASK_FUNCS[task_name]
        output_dir = _TASK_OUTPUT_DIRS[task_name]
        executor = TaskExecutor(task_name, task_name, dag_handler, monitor)
        with executor:
            if executor.can_run:
                options = dag_handler.get_task_options(task_name)
                force = options.get("force_processing", False)
                output_paths = task_func(current_items, output_dir=output_dir, force=force)
                results[task_name] = output_paths
                if output_paths:
                    current_items = output_paths

    return results


def main():
    dag_config_path = Path("F:/GitHub/sWeden_Amyg/config/preprocessing_workflow_dag.yaml")

    if not dag_config_path.exists():
        logging.error(f"DAG config not found: {dag_config_path}")
        exit(1)

    dag_handler = DagConfigHandler(dag_config_path)
    monitor = PipelineMonitor(_AVAILABLE_TASKS)

    # Resolve initial inputs: all session folders under TILA_DATA/
    tila_data_dir = _BACKLOGS / "TILA_DATA"
    if tila_data_dir.exists():
        input_items: List[Path] = sorted(p for p in tila_data_dir.iterdir() if p.is_dir())
    else:
        logging.warning(f"Input directory not found: {tila_data_dir}. Running with empty input.")
        input_items = []

    results = run_batch(input_items, dag_handler, monitor)
    logging.info(f"Workflow complete. Results: {results}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
