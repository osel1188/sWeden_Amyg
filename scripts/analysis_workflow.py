import logging
from pathlib import Path

from utils.dag_config_handler import DagConfigHandler
from utils.task_executor import TaskExecutor
from utils.pipeline_monitor import PipelineMonitor

from scripts.analysis import (
    run_plot_session_voltages,
    run_analyse_stim_intervals,
    run_sex_based_voltage_analysis,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _resolve_voltage_csvs(processed_dir: Path) -> list[Path]:
    """Find voltage CSVs, preferring corrected versions."""
    csv_files = sorted(processed_dir.glob("*/voltages_corrected.csv"))
    if not csv_files:
        csv_files = sorted(processed_dir.glob("*/voltages.csv"))
    return csv_files


def _resolve_session_dirs(processed_dir: Path) -> list[Path]:
    """Find session directories under processed data."""
    if processed_dir.exists():
        return sorted(p for p in processed_dir.iterdir() if p.is_dir())
    return []


def run_single_session_pipeline(
    dag_handler: DagConfigHandler,
    monitor: PipelineMonitor,
    block_name: str,
) -> dict:
    backlogs = Path(dag_handler.get_parameter("project_root"))
    processed_dir = backlogs / "TILA_DATA_1_processed"
    analysed_dir = backlogs / "TILA_DATA_2_analysed"

    context = {
        "voltage_csvs": _resolve_voltage_csvs(processed_dir),
        "session_dirs": _resolve_session_dirs(processed_dir),
        "analysed_dir": analysed_dir,
    }

    pipeline_stages = [
        {"name": "plot_session_voltages",
         "func": run_plot_session_voltages,
         "params": lambda: {
             "input_items": context.get("voltage_csvs"),
             "output_dir": context["analysed_dir"] / "voltage_tracker",
         },
         "outputs": ["voltage_plots"]},

        {"name": "analyse_stim_intervals",
         "func": run_analyse_stim_intervals,
         "params": lambda: {
             "input_items": context.get("session_dirs"),
             "output_dir": context["analysed_dir"] / "interval_analysis",
         },
         "outputs": ["interval_results"]},

        {"name": "sex_based_voltage_analysis",
         "func": run_sex_based_voltage_analysis,
         "params": lambda: {
             "input_items": context.get("interval_results", context.get("session_dirs")),
             "output_dir": context["analysed_dir"] / "sex_voltage_analysis",
         },
         "outputs": ["sex_voltage_results"]},
    ]

    for stage_idx, stage in enumerate(pipeline_stages):
        task_name = stage["name"]
        executor = TaskExecutor(task_name, block_name, dag_handler, monitor, session_name=block_name)
        with executor:
            if not executor.can_run:
                continue
            options = dag_handler.get_task_options(task_name)
            params = stage["params"]()
            force = options.get("force_processing")
            if force is not None:
                params["force"] = force
            result = stage["func"](**params)

        # Store outputs in context
        if "outputs" in stage:
            outputs = stage["outputs"]
            if not isinstance(result, tuple):
                result = (result,)
            for i, key in enumerate(outputs):
                if key and i < len(result):
                    context[key] = result[i]

        # On error, skip remaining tasks
        if task_name in dag_handler.tasks and executor.error_msg:
            all_tasks = list(dag_handler.tasks.keys())
            current_task_index = all_tasks.index(task_name)
            for skipped_task in all_tasks[current_task_index + 1:]:
                if monitor is not None:
                    monitor.update(block_name, skipped_task, "SKIPPED", "Skipped due to prior failure.")
            return {"status": "failed", "stage": stage_idx, "error": executor.error_msg}

    return {"status": "success", "completed_tasks": list(dag_handler.completed_tasks)}


def main():
    dag_config_path = _REPO_ROOT / "config" / "analysis_workflow_dag.yaml"

    dag_handler = DagConfigHandler(dag_config_path)
    monitor = PipelineMonitor(list(dag_handler.tasks.keys()))

    block_name = "analysis"

    result = run_single_session_pipeline(dag_handler, monitor, block_name)
    logging.info(f"Workflow complete. {result}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
