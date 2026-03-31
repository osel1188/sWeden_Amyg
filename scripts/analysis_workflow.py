import logging
from pathlib import Path
from typing import List

from utils.dag_config_handler import DagConfigHandler
from utils.task_executor import TaskExecutor
from utils.pipeline_monitor import PipelineMonitor

from scripts.analysis import (
    run_plot_session_voltages,
    run_analyse_stim_intervals,
    run_sex_based_voltage_analysis,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BACKLOGS = _PROJECT_ROOT / "backlogs_local_data"
_PROCESSED_DIR = _BACKLOGS / "TILA_DATA_1_processed"
_ANALYSED_DIR = _BACKLOGS / "TILA_DATA_2_analysed"

_TASK_OUTPUT_DIRS = {
    "plot_session_voltages":    _ANALYSED_DIR / "voltage_tracker",
    "analyse_stim_intervals":   _ANALYSED_DIR / "interval_analysis",
    "sex_based_voltage_analysis": _ANALYSED_DIR / "sex_voltage_analysis",
}

_TASK_FUNCS = {
    "plot_session_voltages":    run_plot_session_voltages,
    "analyse_stim_intervals":   run_analyse_stim_intervals,
    "sex_based_voltage_analysis": run_sex_based_voltage_analysis,
}

_AVAILABLE_TASKS = [
    "plot_session_voltages",
    "analyse_stim_intervals",
    "sex_based_voltage_analysis",
]


def _resolve_inputs(task_name: str, task_results: dict) -> List[Path]:
    """Resolve input items for each task.

    - ``plot_session_voltages``: voltage CSVs from processed sessions.
    - ``analyse_stim_intervals``: session directories from processed data.
    - ``sex_based_voltage_analysis``: interval_summary.csv from analyse_stim_intervals.
    """
    if task_name == "plot_session_voltages":
        csv_files = sorted(_PROCESSED_DIR.glob("*/voltages_corrected.csv"))
        if not csv_files:
            csv_files = sorted(_PROCESSED_DIR.glob("*/voltages.csv"))
        return csv_files

    if task_name == "analyse_stim_intervals":
        if _PROCESSED_DIR.exists():
            return sorted(p for p in _PROCESSED_DIR.iterdir() if p.is_dir())
        return []

    if task_name == "sex_based_voltage_analysis":
        # Prefer output from analyse_stim_intervals if available in this run
        prior = task_results.get("analyse_stim_intervals", [])
        if prior:
            return prior
        # Fall back to default location
        summary = _ANALYSED_DIR / "interval_analysis" / "interval_summary.csv"
        return [summary] if summary.exists() else []

    return []


def run_batch(
    dag_handler: DagConfigHandler,
    monitor: PipelineMonitor,
) -> dict:
    results = {}

    for task_name in _AVAILABLE_TASKS:
        if task_name not in dag_handler.tasks or not dag_handler.tasks[task_name].get("enabled", False):
            continue

        task_func = _TASK_FUNCS[task_name]
        output_dir = _TASK_OUTPUT_DIRS[task_name]
        input_items = _resolve_inputs(task_name, results)

        executor = TaskExecutor(task_name, task_name, dag_handler, monitor)
        with executor:
            if executor.can_run:
                options = dag_handler.get_task_options(task_name)
                force = options.get("force_processing", False)
                output_paths = task_func(input_items, output_dir=output_dir, force=force)
                results[task_name] = output_paths

    return results


def main():
    dag_config_path = Path("F:/GitHub/sWeden_Amyg/config/analysis_workflow_dag.yaml")

    if not dag_config_path.exists():
        logging.error(f"DAG config not found: {dag_config_path}")
        exit(1)

    dag_handler = DagConfigHandler(dag_config_path)
    monitor = PipelineMonitor(_AVAILABLE_TASKS)

    results = run_batch(dag_handler, monitor)
    logging.info(f"Workflow complete. Results: {results}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
