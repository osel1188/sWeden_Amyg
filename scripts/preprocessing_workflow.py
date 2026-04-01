import logging
from pathlib import Path

from utils.dag_config_handler import DagConfigHandler
from utils.task_executor import TaskExecutor
from utils.pipeline_monitor import PipelineMonitor

from preprocessing import (
    run_filter_valid_sessions,
    run_extract_session_data,
    run_validate_session_metadata,
    run_resample_voltages,
    run_tag_voltage_intervals,
    run_correct_intervals,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


def run_single_session_pipeline(
    dag_handler: DagConfigHandler,
    monitor: PipelineMonitor,
    block_name: str,
) -> dict:
    backlogs = Path(dag_handler.get_parameter("project_root"))
    excel_path_raw = dag_handler.get_parameter("excel_path")
    excel_path = Path(excel_path_raw) if excel_path_raw else None

    tila_raw_data_dir = backlogs / "TILA_DATA"
    if tila_raw_data_dir.exists():
        initial_inputs = sorted(p for p in tila_raw_data_dir.iterdir() if p.is_dir())
    else:
        logging.warning(f"Input directory not found: {tila_raw_data_dir}. Running with empty input.")
        initial_inputs = []

    context = {
        "raw_session_dirs": initial_inputs,
        "excel_path": excel_path,
        "backlogs": backlogs,
    }

    pipeline_stages = [
        {"name": "filter_valid_sessions",
         "func": run_filter_valid_sessions,
         "params": lambda: {
             "input_items": context.get("raw_session_dirs"),
             "excel_path": context.get("excel_path"),
             "output_dir": context["backlogs"] / "TILA_DATA_0_primary",
         },
         "outputs": ["valid_sessions"]},

        {"name": "extract_session_data",
         "func": run_extract_session_data,
         "params": lambda: {
             "input_items": context.get("valid_sessions"),
             "output_dir": context["backlogs"] / "TILA_DATA_1_processed",
         },
         "outputs": ["extracted_voltages", "extracted_metadata"]},

        {"name": "validate_session_metadata",
         "func": run_validate_session_metadata,
         "params": lambda: {
             "input_metadata_paths": context.get("extracted_metadata"),
             "excel_path": context.get("excel_path"),
             "output_dir": context["backlogs"] / "TILA_DATA_1_processed",
         },
         "outputs": ["validated_report"]},

        {"name": "resample_voltages",
         "func": run_resample_voltages,
         "params": lambda: {
             "input_items": context.get("extracted_voltages"),
             "output_dir": context["backlogs"] / "TILA_DATA_1_processed",
         },
         "outputs": ["resampled_voltages"]},

        {"name": "tag_voltage_intervals",
         "func": run_tag_voltage_intervals,
         "params": lambda: {
             "input_items": context.get("resampled_voltages"),
             "output_dir": context["backlogs"] / "TILA_DATA_1_processed",
         },
         "outputs": ["tagged_sessions"]},

        {"name": "correct_intervals",
         "func": run_correct_intervals,
         "params": lambda: {
             "input_items": context.get("tagged_sessions"),
             "output_dir": context["backlogs"] / "TILA_DATA_1_processed",
         },
         "outputs": ["corrected_sessions"]},
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

        # Store outputs in context (only if the task succeeded)
        if "outputs" in stage and not executor.error_msg:
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
    dag_config_path = _REPO_ROOT / "config" / "preprocessing_workflow_dag.yaml"

    dag_handler = DagConfigHandler(dag_config_path)
    monitor = PipelineMonitor(list(dag_handler.tasks.keys()))

    block_name = "preprocessing"

    result = run_single_session_pipeline(dag_handler, monitor, block_name)
    logging.info(f"Workflow complete. {result}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
