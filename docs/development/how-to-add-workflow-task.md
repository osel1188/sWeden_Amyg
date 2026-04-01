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
4. **`should_process_task()`** — file-level idempotency called by the **workflow**
   before invoking a task. Returns `False` when all outputs already exist and are
   newer than all inputs, so the task can be skipped.
5. **`PipelineMonitor`** — records per-dataset, per-stage status
   (`RUNNING` / `SUCCESS` / `FAILURE`) for reporting.
6. **`context` dict** — shared state that wires tasks together. The workflow stores
   resolved output paths under named keys; downstream stages pull values via
   `context.get("key")` in their `inputs` lambda.

## The Task Philosophy

**Tasks are pure processors that receive orders.** A task is a box with named
input and output connectors. It reads from the paths it is given, processes the
data, and writes to the paths it is given. That is all.

The workflow is the single source of truth for:
- **File discovery** — scanning directories, globbing for files
- **Path construction** — building output filenames and directory structures
- **Looping** — iterating over items, calling the task once per input/output pair
- **Idempotency** — deciding whether the task needs to run (`should_process_task`)
- **Force processing** — the `force_processing` flag is a workflow-level concern

## The Task Contract

Every pipeline task function follows this pattern:

```python
def run_task_name(
    input_path: Path,
    output_path: Path,
) -> None:
```

- **Explicit named parameters**: each task declares the specific inputs and
  outputs it needs. Parameter names are domain-specific.
- **Fully resolved paths**: every input and output is an exact file path
  provided by the workflow. No directory scanning, no filename construction.
- **Returns `None`**: the workflow already knows the output paths (it provided
  them), so the task does not need to return them.
- **No idempotency**: the task does not call `should_process_task()`. The
  workflow handles this before invoking the task.
- **No force flag**: the task has no `force_processing` parameter. When
  called, it always processes.
- **Multiple outputs** (2 typical, 3 exceptional): each output is a separate
  named parameter.

## The Pipeline Stages Pattern

The workflow script wires tasks together using a `context` dict and a
`pipeline_stages` list. Each stage separates **inputs** (paths to read) from
**outputs** (paths to write):

```python
context = {
    # Seed values — initial inputs before any task runs
    "source_csv": Path("..."),
}

pipeline_stages = [
    {"name": "task_one",
     "func": run_task_one,
     "inputs": lambda: {
         "input_csv": context["source_csv"],
     },
     "outputs": lambda: {
         "output_csv": output_dir / session_name / "task_one_result.csv",
     },
     "store": ["output_csv"]},

    {"name": "task_two",
     "func": run_task_two,
     "inputs": lambda: {
         "input_csv": context["output_csv"],
     },
     "outputs": lambda: {
         "result_csv": output_dir / session_name / "task_two_result.csv",
     },
     "store": ["result_csv"]},
]
```

Each entry has:
- **`name`** — must match the task name in the DAG YAML.
- **`func`** — the task's `run_*` function.
- **`inputs`** — a **lambda** returning a dict of input parameter names to
  resolved Paths. Read from `context` to wire upstream outputs.
- **`outputs`** — a **lambda** returning a dict of output parameter names to
  resolved Paths. The workflow constructs these paths.
- **`store`** — list of output parameter names whose resolved paths should be
  stored in the `context` dict for downstream stages. The parameter name
  becomes the context key.

The executor loop handles the rest: idempotency checks, dependency enforcement,
error propagation, and context storage.

## The Executor Loop

The executor loop calls `should_process_task()` before invoking each task,
using the input and output paths declared in the stage:

```python
for stage_idx, stage in enumerate(pipeline_stages):
    task_name = stage["name"]
    executor = TaskExecutor(task_name, block_name, dag_handler, monitor)
    with executor:
        if not executor.can_run:
            continue

        inputs = stage["inputs"]()
        outputs = stage["outputs"]()
        input_paths = list(inputs.values())
        output_paths = list(outputs.values())

        options = dag_handler.get_task_options(task_name)
        force = options.get("force_processing", False)

        if not should_process_task(
            input_paths=input_paths,
            output_paths=output_paths,
            force=force,
        ):
            # Store output paths in context even when skipped
            for key in stage.get("store", []):
                context[key] = outputs[key]
            continue

        clean_task_outputs(output_paths)
        stage["func"](**inputs, **outputs)

    # Store output paths in context for downstream stages
    for key in stage.get("store", []):
        outputs = stage["outputs"]()
        context[key] = outputs[key]
```

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

Create `scripts/<workflow>/your_new_task.py` as a pure processor:

```python
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def run_your_new_task(
    input_csv: Path,
    output_csv: Path,
) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    # TODO: implement processing logic
    log.info("Processing %s -> %s", input_csv.name, output_csv.name)
```

The task receives fully resolved paths and has no knowledge of idempotency,
force flags, or filename construction.

### 3. Wire into the workflow script

In the workflow script's `pipeline_stages` list, add the new stage:

```python
pipeline_stages = [
    # ... existing stages ...
    {"name": "your_new_task",
     "func": run_your_new_task,
     "inputs": lambda: {
         "input_csv": context["previous_task_output"],
     },
     "outputs": lambda: {
         "output_csv": output_dir / session_name / "your_new_task_result.csv",
     },
     "store": ["output_csv"]},
]
```

The `inputs` lambda reads from `context` to wire upstream outputs.
The `outputs` lambda constructs fully resolved output paths.
`store` lists which output paths to save in `context` for downstream stages.

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
- The `run_*` function — reads inputs, processes, writes outputs
- Task-specific processing logic

**What does NOT belong in the task module:**
- `should_process_task()` or `clean_task_outputs()` — workflow's concern
- `force_processing` parameter — workflow's concern
- Output filename construction — workflow's concern
- File discovery or directory scanning — workflow's concern

## Important Rules

- **No Prefect** — do not use `@flow` decorators or prefect imports.
- **Tasks are pure processors** — they read inputs, process, write outputs.
  No idempotency, no force flag, no path construction.
- **Tasks receive fully resolved paths** — every input and output is an exact
  file path. No directory scanning, no glob, no `name_baseline`.
- **Tasks return `None`** — the workflow already knows the output paths.
- **Workflow owns orchestration** — file discovery, path construction, looping,
  idempotency, and force processing all live in the workflow.
- **Separate inputs from outputs** — use `inputs` and `outputs` lambdas in
  `pipeline_stages`, not a single `params` dict.
- **Linear dependency chain** by default — each task depends on the previous one.
  Override with custom `depends_on` lists for parallel branches.
