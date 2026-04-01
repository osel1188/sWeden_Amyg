import logging
from pathlib import Path

from utils.dag_config_handler import DagConfigHandler
from utils.task_executor import TaskExecutor
from utils.pipeline_monitor import PipelineMonitor

from scripts.primary import (
    run_split_log_by_day,
    run_task_two,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


def run_single_session_pipeline(
    dag_handler: DagConfigHandler,
    monitor: PipelineMonitor,
    block_name: str,
) -> dict:
    context = {
        # TODO: seed initial values from dag_handler.get_parameter() or filesystem
    }

    pipeline_stages = [
        {"name": "split_log_by_day",
         "func": run_split_log_by_day,
         "params": lambda: {
             # TODO: map context keys and config values to function parameters
             "input_items": context.get("..."),
             "output_dir": Path("..."),
         },
         "outputs": ["split_logs"]},

        {"name": "task_two",
         "func": run_task_two,
         "params": lambda: {
             # TODO: map context keys and config values to function parameters
             "input_path": context.get("split_logs"),
             "output_dir": Path("..."),
         },
         "outputs": ["task_two_output"]},
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
            monitor_opt = options.get("monitor")
            if force is not None:
                params["force_processing"] = force
            if monitor_opt is not None:
                params["monitor"] = monitor_opt
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
    dag_config_path = _REPO_ROOT / "config" / "primary_workflow_dag.yaml"

    if not dag_config_path.exists():
        logging.error(f"DAG config not found: {dag_config_path}")
        exit(1)

    dag_handler = DagConfigHandler(dag_config_path)
    monitor = PipelineMonitor(list(dag_handler.tasks.keys()))

    block_name = "TODO"  # TODO: resolve the actual block/session name

    result = run_single_session_pipeline(dag_handler, monitor, block_name)
    logging.info(f"Workflow complete. {result}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
