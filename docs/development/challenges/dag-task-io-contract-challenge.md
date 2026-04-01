=== CHALLENGE: DAG Task I/O Contract Design ===
Source: free-text concept

## Your Position

- Redesign the DAG workflow so tasks are "boxes with connectors": they receive fully resolved file paths and process a single item, while the workflow owns all file discovery, path construction, looping, and wiring.
- Proposition 1 (idempotency): Evaluate whether skip logic (should_process_task) belongs in the workflow layer, the task layer, or both.
- Proposition 2 (multiple outputs): Evaluate whether tasks with multiple outputs should use named parameters (one per output path) or an output dataclass/dict that groups them.
- The current architecture already has tasks calling should_process_task internally and owning their own loops; the redesign would strip tasks to pure single-item processors.
- The goal is cleaner separation of concerns, easier testing, and composability.

## Opposition

### 1. The problem may be misdiagnosed

The current architecture --- where tasks own their loops, path construction, and idempotency checks --- is not inherently broken. It follows the "Functional Data Engineering" paradigm articulated by Maxime Beauchemin (creator of Airflow and Superset), which holds that pure tasks should be "fully independent in their execution" and able to be "written, tested, reasoned-about and debugged in isolation, without the need to understand external context" ([Beauchemin, Medium](https://maximebeauchemin.medium.com/functional-data-engineering-a-modern-paradigm-for-batch-data-processing-2327ec32c42a)).

The desire to centralize path resolution and looping in the workflow may be solving the wrong problem. If tasks are hard to test or compose today, the root cause is more likely:

- **Inconsistent naming conventions** across tasks (not a structural issue).
- **Implicit coupling through the context dict**, where typos in string keys silently produce None values.
- **Lack of type safety** in the pipeline_stages wiring (lambdas returning dicts with no schema validation).

These are fixable without a fundamental architectural shift. Adding typed dataclasses for context keys and a validation layer on the pipeline_stages wiring would address testability and composability without the cost and risk of moving responsibility between layers.

### 2. Critical assumptions that may not hold

**Assumption: Tasks that receive single items are easier to test and reason about.**

This is true in the simple case but breaks down for tasks with cross-item dependencies. Consider a task that must normalize voltages relative to the full dataset, or one that needs to detect duplicates across sessions. A single-item processor cannot do this without the workflow pre-computing and injecting aggregated context --- which means the workflow must understand the task's domain logic to prepare the right inputs. You have not eliminated complexity; you have relocated it.

Airflow learned this lesson the hard way. Its XCom mechanism for passing data between tasks created "one of the most common but subtle and difficult-to-debug classes of Airflow bugs" because the orchestrator must understand data shapes to wire tasks correctly, yet "Airflow has no way of knowing" about implicit data dependencies between tasks ([Prefect Blog](https://medium.com/the-prefect-blog/why-not-airflow-4cfa423299c4)). The more knowledge you push into the workflow's wiring layer, the more you recreate this problem.

**Assumption: The workflow layer can own looping without becoming a "god orchestrator."**

Microsoft's Azure Architecture Center explicitly warns against centralized orchestrators that accumulate domain logic: "Adding or removing services might break existing logic because you need to rewire portions of the communication path. This dependency makes orchestrator implementation complex and hard to maintain" ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/architecture/patterns/choreography)). Ben Morris's analysis of workflow patterns echoes this: centralized orchestrators that absorb too much responsibility become the "enterprise service bus" anti-pattern --- "an arcane platform that nobody understands, and everybody is too scared to change for fear of breaking something" ([Ben Morris](https://www.ben-morris.com/orchestration-vs-choreography-for-microservice-workflows/)).

In your proposed design, the workflow script must know: which files exist on disk, how to construct output paths for each task, how many items to loop over, and how to wire outputs to downstream inputs. That is a substantial amount of domain knowledge concentrated in one layer. Today, adding a task means writing a self-contained module and a 5-line entry in pipeline_stages. After the redesign, adding a task may require modifying the workflow's discovery logic, its loop structure, and its path-construction rules --- a larger surface area for errors.

**Assumption: Idempotency can be cleanly separated from task logic.**

The should_process_task function currently compares input/output timestamps. This works for simple cases but is fragile even now --- it cannot detect: changes to task code logic (same inputs, different algorithm), changes to configuration parameters, or partial writes from crashed tasks. Moving this check to the workflow layer does not solve these problems; it merely moves the fragility. Worse, it separates the check from the code that knows what "correct output" means.

Dagster's "software-defined assets" approach tackles this differently: assets declare their own materialization logic and staleness conditions as metadata, keeping domain knowledge co-located with computation rather than in an external orchestrator ([Dagster Blog](https://dagster.io/blog/software-defined-assets)). This is the opposite of centralizing skip logic in the workflow.

### 3. Stronger alternatives exist

**For Proposition 1 (idempotency): Option B (task-level) is the strongest, with a thin workflow-level cache as an optimization.**

Rather than choosing between centralized and task-level checks, the better architecture is:

- Tasks own their idempotency as they do today. This keeps them self-contained, testable in isolation, and safe for standalone execution via `if __name__ == "__main__"`.
- The workflow maintains a lightweight **result cache** (not a skip-check): if a task has already been called with identical inputs in this run, return the cached result without re-invoking. This is a performance optimization, not a correctness mechanism.

This avoids Option C's "both layers" redundancy while preserving standalone safety. The task is the single source of truth for "should I run?", and the workflow is purely an efficiency layer.

**For Proposition 2 (multiple outputs): Neither option as stated is ideal. Use a typed NamedTuple.**

Option A (named parameters) suffers from the well-documented "Long Parameter List" code smell. Refactoring.guru and the broader software engineering literature agree that "more than three or four parameters" constitute a code smell because they "become contradictory and hard to use as they grow longer" ([Refactoring.guru](https://refactoring.guru/smells/long-parameter-list)). A function like `run_extract(log_path, voltages_output, metadata_output, events_output, summary_output)` is fragile: parameter ordering errors are silent, and adding an output requires changing every call site.

Option B (output dict/dataclass) is better but underspecified. A plain dict has no type safety; a dataclass works but mixes concerns if it bundles input and output paths. The strongest pattern is:

```python
class ExtractOutputs(NamedTuple):
    voltages: Path
    metadata: Path

def run_extract(log_path: Path, output_dir: Path, *, force: bool = False) -> ExtractOutputs:
    ...
```

This keeps the function signature clean (input + output_dir + options), gives the return value named fields with full type-checking, and preserves tuple unpacking for context storage. The task constructs its own output paths from output_dir (maintaining the name_baseline convention), and the workflow receives a typed, destructurable result. Output paths are an implementation detail of the task, not something the workflow should construct and inject.

### 4. What this position ignores

**Testing without integration.** The proposal assumes that tasks receiving pre-resolved paths are easier to unit test. But the current architecture already supports this: you can call `run_task(input_path=Path("test_input.csv"), output_dir=Path("tmp/"))` directly. The task is already a pure function of its arguments. Moving path construction to the workflow does not make the task more testable --- it makes the *workflow* harder to test, because the workflow now contains path-construction logic that must be tested against real directory structures.

**The cost of the migration.** Every existing task must be refactored: loops removed, path construction extracted, idempotency calls relocated or duplicated. Every workflow script must be rewritten to add discovery and looping logic. During the migration, both patterns coexist, increasing cognitive load. This is a high-cost change with uncertain benefits for a pipeline that processes ~70 neurostimulation sessions --- not a scale that demands architectural optimization.

**Standalone execution.** The current tasks work as standalone scripts (`if __name__ == "__main__"`). If idempotency moves to the workflow, standalone execution loses skip logic unless you duplicate it (Option C), which the proposal rightly identifies as redundant. But "redundant" and "robust" are not the same thing --- defense-in-depth is a legitimate engineering strategy when the cost of reprocessing is high (as it can be with large voltage timeseries files).

**The Dagster lesson.** The broader data engineering ecosystem is moving *away* from task-centric DAGs toward asset-centric models precisely because centralizing wiring logic in orchestrators proved brittle at scale. Dagster's software-defined assets encode "what persistent objects result" rather than "what work is done," keeping materialization logic co-located with the asset definition rather than in an external DAG ([Dagster Blog](https://dagster.io/blog/software-defined-assets)). Your proposed redesign moves in the opposite direction --- toward a more powerful orchestrator that owns more knowledge about task internals.

### 5. The strongest case against

The strongest argument against this redesign is that **it centralizes knowledge that should be distributed**.

Today, each task is a self-contained unit that knows: what it needs (parameters), what it produces (return value), whether it should run (idempotency), and how to name its outputs (name_baseline convention). The workflow script is thin: it declares ordering and wires context keys. This is a healthy separation.

The proposed redesign inverts this: the workflow must know what files exist, how to construct every task's output paths, how many items to process, and whether each task should be skipped. The task becomes a thin computation kernel that cannot function without the orchestrator. You gain uniformity but lose autonomy.

This is the classic "inner platform" anti-pattern: you are building a mini-framework (the workflow's discovery/looping/path-construction layer) that replicates what the tasks already do, except now there is one place that must understand every task's I/O contract instead of each task understanding its own.

The pragmatic path forward is incremental: add type safety to the context dict (typed keys or a dataclass), validate pipeline_stages wiring at startup, and standardize the task contract more strictly --- without moving responsibilities between layers. This captures 80% of the benefit at 20% of the cost and risk.

## Sources

- [Functional Data Engineering --- Maxime Beauchemin (Medium)](https://maximebeauchemin.medium.com/functional-data-engineering-a-modern-paradigm-for-batch-data-processing-2327ec32c42a)
- [Why Not Airflow? --- Prefect Blog (Medium)](https://medium.com/the-prefect-blog/why-not-airflow-4cfa423299c4)
- [Choreography Pattern --- Azure Architecture Center (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/architecture/patterns/choreography)
- [Orchestration vs choreography for microservice workflows --- Ben Morris](https://www.ben-morris.com/orchestration-vs-choreography-for-microservice-workflows/)
- [What Are Software-Defined Assets? --- Dagster Blog](https://dagster.io/blog/software-defined-assets)
- [Long Parameter List code smell --- Refactoring.guru](https://refactoring.guru/smells/long-parameter-list)
- [Introduce Parameter Object --- Refactoring.guru](https://refactoring.guru/introduce-parameter-object)
- [DAG Best Practices --- Astronomer Documentation](https://www.astronomer.io/docs/learn/dag-best-practices)

## Assessment

The "box with connectors" metaphor is appealing and the intent is sound: cleaner task boundaries, better testability, more explicit contracts. These are real engineering values.

However, the specific proposal overcorrects. It solves problems that have cheaper solutions (type-safe context wiring, startup validation) while creating new problems (god orchestrator, loss of standalone execution, migration cost, centralized path knowledge). The idempotency question (Proposition 1) has a clear best answer: tasks own their skip logic (self-contained, testable, standalone-safe), with an optional workflow-level cache for performance. The multiple-outputs question (Proposition 2) is best served by neither option as stated: a typed NamedTuple return keeps the function signature clean while giving outputs named, type-checked fields.

The most productive path is not the proposed redesign but rather hardening the existing architecture: typed context keys, validated wiring, stricter contract enforcement, and NamedTuple returns for multi-output tasks. This delivers the clarity and safety benefits without the risk of centralizing too much knowledge in the workflow layer.
