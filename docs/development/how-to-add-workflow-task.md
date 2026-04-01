# How to Add a Task to a DAG Workflow

## Directory Layout

```
scripts/
├── <workflow>_workflow.py             # workflow script (orchestration)
├── <workflow>/                        # task modules (one per DAG task)
│   ├── __init__.py
│   ├── task_one.py
│   └── task_two.py
src/<workflow>/                        # shared package (types, classes, utilities)
│   ├── __init__.py
│   └── ...
```

- **Task modules** (`scripts/<workflow>/`) contain the per-task processing logic.
- **Shared package** (`src/<workflow>/`) holds domain types, data classes, constants,
  and reusable utilities that any task module can import.

## Architecture Overview

Each workflow follows a 6-component architecture:

1. **DAG config** (YAML) — declares tasks with `enabled` flag, `options` dict, and
   `depends_on` list that defines the execution order.
2. **`DagConfigHandler`** — loads the YAML config, tracks which tasks have completed,
   and exposes `can_run()` to enforce the dependency chain.
3. **`TaskExecutor`** — context manager that wraps each task: checks dependencies via
   `DagConfigHandler.can_run()`, logs status, catches errors, and marks completion.
4. **`should_process_task()`** — file-level idempotency: returns `False` when all
   outputs already exist and are newer than all inputs, so the task can be skipped.
5. **`PipelineMonitor`** — records per-dataset, per-stage status
   (`RUNNING` / `SUCCESS` / `FAILURE`) for reporting.
6. **`context` dict** — shared state that wires tasks together. Each task's return
   values are stored under named keys; downstream tasks pull values via
   `context.get("key")` in their `params` lambda.

## The Task Contract

Every pipeline task function follows this pattern:

```python
def run_task_name(
    input_path: Path,
    output_dir: Path,
    *,
    force_processing: bool = False,
) -> Path:
```

- **Explicit named parameters**: each task declares the specific inputs it needs
  (not a generic `List[Path]`). Parameter names are domain-specific.
- **Keyword-only after `output_dir`**: use `*` to enforce named arguments for options.
- **Returns `Path` or `tuple[Path, ...]`**: return values are stored in the context dict.
- **`name_baseline`**: derive output file names from input stems
  (e.g. `name_baseline = input_path.stem`, then `output_dir / (name_baseline + "_output.csv")`).
- **`force_processing` and `monitor`**: injected by the executor loop from DAG options —
  do not hardcode these in the `pipeline_stages` params lambda.

## The Pipeline Stages Pattern

The workflow script wires tasks together using a `context` dict and a
`pipeline_stages` list:

```python
context = {
    # Seed values — initial inputs before any task runs
    "source_path": Path("..."),
}

pipeline_stages = [
    {"name": "task_one",
     "func": run_task_one,
     "params": lambda: {
         "input_path": context.get("source_path"),
         "output_dir": Path("output/task_one"),
     },
     "outputs": ["task_one_output"]},

    {"name": "task_two",
     "func": run_task_two,
     "params": lambda: {
         "input_path": context.get("task_one_output"),
         "output_dir": Path("output/task_two"),
     },
     "outputs": ["task_two_output"]},
]
```

Each entry has:
- **`name`** — must match the task name in the DAG YAML.
- **`func`** — the task's `run_*` function.
- **`params`** — a **lambda** that reads from `context` and returns a kwargs dict.
  Using a lambda ensures values are resolved at call time, not at definition time.
- **`outputs`** — list of context keys where return values are stored. Use `None`
  to discard a positional return value (e.g. `["keep_this", None]`).

The executor loop handles the rest: dependency checks, option injection,
error propagation, and context storage.

## Step-by-Step: Adding a New Task

### 1. Add a YAML entry in the DAG config

```yaml
tasks:
  your_new_task:
    enabled: true
    options:
      force_processing: false
    depends_on: [previous_task]
```

Set `depends_on` to the task(s) that must complete first.

### 2. Create a pipeline module

Create `scripts/<workflow>/your_new_task.py` with the idempotency pattern:

```python
import logging
from pathlib import Path

from utils.should_process_task import should_process_task, clean_task_outputs


def run_your_new_task(
    input_path: Path,
    output_dir: Path,
    *,
    force_processing: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    name_baseline = input_path.stem
    output_path = output_dir / (name_baseline + "_your_new_task_output.csv")

    if not should_process_task(
        input_paths=[input_path],
        output_paths=[output_path],
        force=force_processing,
    ):
        return output_path

    clean_task_outputs(output_path)

    # TODO: implement processing logic
    logging.info(f"Processing {input_path.name}")

    return output_path
```

### 3. Wire into the workflow script

In the workflow script's `pipeline_stages` list, add the new stage:

```python
pipeline_stages = [
    # ... existing stages ...
    {"name": "your_new_task",
     "func": run_your_new_task,
     "params": lambda: {
         "input_path": context.get("previous_task_output"),
         "output_dir": Path("output/your_new_task"),
     },
     "outputs": ["your_new_task_output"]},
]
```

The `params` lambda reads from `context` — use the output key of the
upstream task as the input. `outputs` names the key where the return
value will be stored for downstream tasks.

For tasks that return multiple values (tuples), list multiple output keys:
```python
"outputs": ["first_output", "second_output"]
```

Use `None` to discard a positional value:
```python
"outputs": ["keep_this", None]
```

### 4. Export from `__init__.py`

Add to `scripts/<workflow>/__init__.py`:

```python
from .your_new_task import run_your_new_task
```

## Using the Shared Package

The shared package at `src/<workflow>/` is where domain types, data classes,
constants, and reusable processing utilities live. Task modules import from it:

```python
from <workflow> import MyDataClass, my_utility_function
```

**What belongs in the shared package:**
- Data classes and type definitions used across multiple tasks
- Constants and configuration values
- Reusable processing functions (parsing, formatting, validation)
- Domain models

**What stays in the task module:**
- Task-specific orchestration logic (the `run_*` function)
- Idempotency checks (`should_process_task` / `clean_task_outputs`)
- File I/O specific to that task's inputs and outputs

## Idempotency Pattern

Every task must use `should_process_task()` and `clean_task_outputs()`:

```python
# Skip if output is up-to-date
if not should_process_task(
    input_paths=[input_path],
    output_paths=[output_path],
    force=force_processing,
):
    return output_path

# Clean stale output before reprocessing
clean_task_outputs(output_path)

# ... do actual processing ...

return output_path
```

- `should_process_task()` returns `False` when all outputs exist and are newer
  than all inputs.
- `clean_task_outputs()` deletes stale output files before reprocessing to
  avoid partial or corrupt artifacts.

## Important Rules

- **No Prefect** — do not use `@flow` decorators or prefect imports.
- **Tasks have explicit named parameters** — domain-specific signatures,
  not generic `List[Path]`.
- **Tasks return `Path` or `tuple[Path, ...]`** — stored in context dict.
- **Wire through context** — use `context.get()` in `params` lambdas,
  not direct variable passing.
- **Use `name_baseline`** for output file naming — derive from input stems.
- **Linear dependency chain** by default — each task depends on the previous one.
  Override with custom `depends_on` lists for parallel branches.
- **Always include idempotency** — `should_process_task()` + `clean_task_outputs()`
  in every pipeline module.
