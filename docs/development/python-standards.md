# Python Programming Standards & Architecture Guidelines

## Code Style & Readability

- **PEP 8** — `snake_case` functions/variables, `PascalCase` classes, `UPPER_CASE` constants, 4-space indentation, line length limits
- **PEP 257** — docstring conventions (module, class, function)
- **Consistent formatting** — enforce with tools like `black`, `ruff`, or `autopep8`
- **Explicit imports** — avoid `from module import *`
- **Flat over nested** — use early returns and guard clauses to reduce nesting
- **No global variables** — pass state explicitly via function arguments, class attributes, or dependency injection; global mutable state creates hidden coupling, hinders testing, and makes code unpredictable

## Type Safety & Contracts

- **Type hints** (PEP 484/526) — annotate function signatures and key variables
- **Static type checking** — `mypy` or `pyright`
- **Dataclasses / NamedTuples** over raw dicts for structured data
- **`typing.Protocol`** (PEP 544) — structural subtyping for duck-type interfaces
- **ABCs** (PEP 3119) — for formal interface contracts

## SOLID Principles

- **Single Responsibility** — one class/module owns one reason to change
- **Open/Closed** — extend behavior without modifying existing code (strategy pattern, plugins)
- **Liskov Substitution** — subtypes must be drop-in replacements for their base
- **Interface Segregation** — small, focused interfaces over fat ones
- **Dependency Inversion** — depend on abstractions, not concretions; inject dependencies rather than constructing them internally

## Separation of Concerns

- **Isolate distinct responsibilities** — data access, business logic, presentation, and I/O should live in separate modules/classes, not be interleaved within the same function or file
- **No mixed layers** — a function that reads a file should not also transform data and plot results; split these into separate steps with clear boundaries
- **Pure logic vs side effects** — keep computation and decision-making in pure functions/methods; push I/O (file reads, network calls, user interaction) to the edges
- **One module, one job** — a module that handles CSV parsing should not also know about plotting or database access
- **Compose at the top** — scripts and entry points wire the pieces together; lower-level modules remain independent and unaware of each other

## Architectural Patterns

### Layered / Clean Architecture
- **Presentation → Application → Domain → Infrastructure**
- Each layer only depends inward; outer layers are replaceable

### MVC / MVP
- Separate data (Model), display (View), and logic (Controller/Presenter)

### Repository Pattern
- Abstract data access behind a repository interface
- Decouple domain logic from storage details

### Facade Pattern
- Simplify complex subsystems behind a single API surface
- Thin facade, thick service — facades delegate, services contain logic

### Strategy Pattern
- Swap algorithms/behaviors at runtime (e.g., real vs mock drivers)

### State Machine
- Explicit states and transitions instead of boolean flag soup

## Domain-Driven Design (DDD) Concepts

- **Entities** — objects with identity
- **Value Objects** — immutable, identity-less
- **Aggregates** — consistency boundaries; an aggregate root owns its children
- **Bounded Contexts** — separate domains with separate vocabularies and independent models

## API & Interface Design

- **Command-Query Separation (CQS)** — methods either change state or return data, not both
- **Fail fast** — validate at system boundaries, trust internals
- **Thin facade, thick service** — facades delegate, services contain logic

## Error Handling Architecture

- **Exception hierarchy** — domain-specific exceptions (e.g., `HardwareError`, `ProtocolError`)
- **Let it crash at the right layer** — catch at boundaries, not everywhere
- **Result types** for expected failures vs exceptions for unexpected ones

## Concurrency Architecture

- **Thread confinement** — own data in one thread, communicate via queues/signals
- **Lock hierarchy** — consistent ordering to avoid deadlocks
- **Immutable shared state** — if multiple threads read it, don't mutate it

## Project Structure

- **Package layout** with `__init__.py` and clear module boundaries
- **`pyproject.toml`** for project metadata, dependencies, and tool config
- **Separation of concerns** — `src/`, `tests/`, `scripts/`, `config/`, `docs/`

## Reusability & Shared Structures

- **Favor OOP for shared logic** — encapsulate data loading, transformation, and validation into classes that multiple scripts can import and reuse
- **Shared data models** — define common data structures (dataclasses, NamedTuples) in a shared module so all scripts work with the same representations
- **Service classes over standalone functions** — group related operations into cohesive classes (e.g., a `SessionLoader`, `VoltageExtractor`) rather than scattering loose functions across scripts
- **Scripts as thin orchestrators** — each script's `main()` should wire together shared classes and call their methods; the reusable logic lives in the classes, not in the script
- **Shared configuration objects** — pass structured config objects (not raw dicts or scattered variables) so scripts interpret configuration consistently

## Workflow & Process Scripts

- **`if __name__ == "__main__":`** guard on all scripts
- **Hardcoded defaults inside `main()` are acceptable** as a practical entry point (e.g., default file paths, output directories)
- **Numbered script prefixes** (e.g., `01_`, `02_`) for sequential workflows
- **Config-driven** — externalize paths, parameters, thresholds into config files
- **Idempotency** — re-running a script should not corrupt state

## Testing

- **`pytest`** as the test framework
- **Test naming**: `test_<unit>_<scenario>_<expected>`
- **Fixtures** for setup/teardown; avoid test interdependence
- **Coverage targets** for critical paths

## Version Control

- **Meaningful commits** — atomic, descriptive messages
- **Feature branches** with clear naming (`feature/`, `fix/`)
- **`.gitignore`** — keep generated/local files out of the repo

## Linting & Enforcement

- **`ruff`** — fast all-in-one linter replacing flake8/isort/pyflakes
- **Pre-commit hooks** to catch issues before they land
- **CI checks** to enforce standards automatically

## Key References

| Resource | Focus |
|----------|-------|
| *Clean Architecture* (Robert Martin) | Layered design, dependency rule |
| *Architecture Patterns with Python* (Percival & Gregory) | DDD, repository, unit of work in Python |
| *Design Patterns* (Gang of Four) | Classic patterns catalogue |
| *Cosmic Python* (cosmicpython.com) | Free — same as Percival & Gregory book |
| PEP 8 | Style guide |
| PEP 20 | Zen of Python (`import this`) |
| PEP 257 | Docstring conventions |
| PEP 484 | Type hints |
| PEP 544 | Structural subtyping (`Protocol`) |
| PEP 621 | `pyproject.toml` metadata |
| PEP 3119 | Abstract Base Classes |
