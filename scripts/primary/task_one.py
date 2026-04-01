import logging
from pathlib import Path

from utils.should_process_task import should_process_task, clean_task_outputs

# Shared package — import domain types, classes, and utilities from here:
# from src.primary import MyClass, my_utility


def run_task_one(
    input_path: Path,
    output_dir: Path,
    *,
    force_processing: bool = False,
) -> Path:
    """
    Process the task_one task.

    Parameters
    ----------
    input_path : Path
        Primary input file path.
        NOTE: Rename to a domain-specific name (e.g. ``video_path``,
        ``tracking_csv``). Add more input parameters as needed — each
        task declares exactly the inputs it requires.
    output_dir : Path
        Directory for output files.
    force_processing : bool
        If True, bypass idempotency checks and reprocess.

    Returns
    -------
    Path or tuple[Path, ...]
        Path(s) to generated output file(s). When a task produces
        multiple outputs, return a tuple and list matching keys in
        the ``pipeline_stages`` ``outputs`` list.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    name_baseline = input_path.stem
    output_path = output_dir / (name_baseline + "_task_one_output.csv")

    # Idempotency: skip if output is up-to-date
    if not should_process_task(
        input_paths=[input_path],
        output_paths=[output_path],
        force=force_processing,
    ):
        return output_path

    # Clean stale output before processing
    clean_task_outputs(output_path)

    # TODO: implement processing logic here
    # Example:
    #   df = pd.read_csv(input_path)
    #   result_df = process(df)
    #   result_df.to_csv(output_path, index=False)
    logging.info(f"[task_one] Processing {input_path.name}")
    raise NotImplementedError("task_one logic not yet implemented")

    return output_path
