import logging
from pathlib import Path

from utils.dag_config_handler import DagConfigHandler
from utils.task_executor import TaskExecutor
from utils.pipeline_monitor import PipelineMonitor
from utils.should_process_task import should_process_task, clean_task_outputs

from analysis import (
    run_plot_session_voltages,
    run_analyse_stim_intervals,
    run_sex_based_voltage_analysis,
    CSV_OUTPUT_NAMES,
    PNG_OUTPUT_NAMES,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent

_VOLTAGE_CSV_PRIORITY = (
    "voltages_corrected.csv",
    "voltages_tagged.csv",
    "voltages.csv",
)


def _resolve_voltage_csv(session_dir: Path) -> Path | None:
    """Return the best available voltage CSV for a single session directory."""
    if (session_dir / "discarded.flag").exists():
        return None
    for filename in _VOLTAGE_CSV_PRIORITY:
        path = session_dir / filename
        if path.exists():
            return path
    return None


def _resolve_voltage_csvs(processed_dir: Path) -> list[Path]:
    """Find voltage CSVs across all sessions, preferring corrected > tagged > raw."""
    csv_files: list[Path] = []
    if not processed_dir.exists():
        return csv_files
    for session_dir in sorted(processed_dir.iterdir()):
        if not session_dir.is_dir():
            continue
        csv_path = _resolve_voltage_csv(session_dir)
        if csv_path is not None:
            csv_files.append(csv_path)
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

    context: dict = {
        "voltage_csvs": _resolve_voltage_csvs(processed_dir),
        "session_dirs": _resolve_session_dirs(processed_dir),
    }

    # ------------------------------------------------------------------
    # Stage 1: plot_session_voltages  (per-session loop)
    # ------------------------------------------------------------------
    task_name = "plot_session_voltages"
    executor = TaskExecutor(task_name, block_name, dag_handler, monitor, session_name=block_name)
    with executor:
        if executor.can_run:
            options = dag_handler.get_task_options(task_name)
            force = options.get("force_processing", False)
            plot_dir = analysed_dir / "voltage_tracker"

            for csv_path in context["voltage_csvs"]:
                session_name = csv_path.parent.name
                output_png = plot_dir / f"{session_name}_voltages.png"

                if not should_process_task(
                    input_paths=[csv_path],
                    output_paths=[output_png],
                    force=force,
                ):
                    continue

                clean_task_outputs([output_png])
                run_plot_session_voltages(input_csv=csv_path, output_png=output_png)

    if task_name in dag_handler.tasks and executor.error_msg:
        _skip_remaining(dag_handler, monitor, block_name, task_name)
        return {"status": "failed", "stage": 0, "error": executor.error_msg}

    # ------------------------------------------------------------------
    # Stages 2-3: batch tasks (analyse_stim_intervals, sex_based_voltage_analysis)
    # ------------------------------------------------------------------
    pipeline_stages = [
        {"name": "analyse_stim_intervals",
         "func": run_analyse_stim_intervals,
         "inputs": lambda: {
             "session_dirs": context["session_dirs"],
         },
         "outputs": lambda: {
             "output_csv": analysed_dir / "interval_analysis" / "interval_summary.csv",
             "output_duration_png": analysed_dir / "interval_analysis" / "interval_duration_comparison.png",
             "output_voltage_png": analysed_dir / "interval_analysis" / "interval_voltage_comparison.png",
         },
         "store": ["output_csv"]},

        {"name": "sex_based_voltage_analysis",
         "func": run_sex_based_voltage_analysis,
         "inputs": lambda: {
             "interval_summary_csv": context["output_csv"],
             "excel_path": backlogs / "Excel_for_stimulators.xlsx",
             "condition_report_csv": backlogs / "condition_validation_report.csv",
             "preprocess_dir": processed_dir,
         },
         "outputs": lambda: {
             "output_dir": analysed_dir / "sex_voltage_analysis",
         },
         "output_files": lambda: [
             analysed_dir / "sex_voltage_analysis" / name
             for name in CSV_OUTPUT_NAMES + PNG_OUTPUT_NAMES
         ],
         "store": []},
    ]

    for stage_idx, stage in enumerate(pipeline_stages, start=1):
        task_name = stage["name"]
        executor = TaskExecutor(task_name, block_name, dag_handler, monitor, session_name=block_name)
        with executor:
            if not executor.can_run:
                # Store output paths in context even when skipped by DAG
                for key in stage.get("store", []):
                    outputs = stage["outputs"]()
                    context[key] = outputs[key]
                continue

            inputs = stage["inputs"]()
            outputs = stage["outputs"]()

            # Resolve input/output paths for idempotency check
            input_paths = _flatten_paths(inputs.values())
            output_paths = (
                stage["output_files"]()
                if "output_files" in stage
                else list(outputs.values())
            )

            options = dag_handler.get_task_options(task_name)
            force = options.get("force_processing", False)

            if not should_process_task(
                input_paths=input_paths,
                output_paths=output_paths,
                force=force,
            ):
                for key in stage.get("store", []):
                    context[key] = outputs[key]
                continue

            clean_task_outputs(output_paths)
            stage["func"](**inputs, **outputs)

        # Store output paths in context for downstream stages
        for key in stage.get("store", []):
            outputs = stage["outputs"]()
            context[key] = outputs[key]

        # On error, skip remaining tasks
        if task_name in dag_handler.tasks and executor.error_msg:
            _skip_remaining(dag_handler, monitor, block_name, task_name)
            return {"status": "failed", "stage": stage_idx, "error": executor.error_msg}

    return {"status": "success", "completed_tasks": list(dag_handler.completed_tasks)}


def _flatten_paths(values) -> list[Path]:
    """Flatten a mix of Path and list[Path] values into a single list."""
    flat: list[Path] = []
    for v in values:
        if isinstance(v, list):
            flat.extend(v)
        elif isinstance(v, Path):
            flat.append(v)
    return flat


def _skip_remaining(
    dag_handler: DagConfigHandler,
    monitor: PipelineMonitor | None,
    block_name: str,
    failed_task: str,
) -> None:
    """Mark all tasks after *failed_task* as SKIPPED."""
    all_tasks = list(dag_handler.tasks.keys())
    idx = all_tasks.index(failed_task)
    for skipped_task in all_tasks[idx + 1:]:
        if monitor is not None:
            monitor.update(block_name, skipped_task, "SKIPPED", "Skipped due to prior failure.")


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
