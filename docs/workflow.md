# TILA Workflow Documentation

**TILA** (Temporal Interference amygdaLA) — PySide6 GUI application for controlling Temporal Interference (TI) neuromodulation hardware and managing experiment participant data.

**Version**: 3.0.0 | **Python**: 3.13+ | **Hardware**: Keysight EDU33212A waveform generators

---

## Table of Contents

1. [High-Level Overview](#1-high-level-overview)
2. [Architecture](#2-architecture)
3. [Package Structure](#3-package-structure)
4. [Configuration](#4-configuration)
5. [Application Startup](#5-application-startup)
6. [Experiment Session Workflow](#6-experiment-session-workflow)
7. [Hardware Control Subsystem](#7-hardware-control-subsystem)
8. [Participant Management Subsystem](#8-participant-management-subsystem)
9. [User Interface](#9-user-interface)
10. [Threading and Concurrency](#10-threading-and-concurrency)
11. [Mock Hardware Mode](#11-mock-hardware-mode)
12. [Testing](#12-testing)

---

## 1. High-Level Overview

TILA controls a Temporal Interference (TI) neuromodulation experiment end-to-end. In a single session the operator:

1. **Assigns a participant** — looks up or registers a subject in Excel-based records and creates a session folder.
2. **Connects to hardware** — establishes communication with Keysight EDU33212A waveform generators over USB/VISA and initialises the appropriate protocol (active or sham).
3. **Sets signal amplitudes** — fine-tunes per-channel voltages with live feedback.
4. **Runs the protocol** — starts a coordinated ramp-up across all channels, monitors live voltage traces, and performs a graceful ramp-down when finished.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Experiment Session                       │
│                                                                 │
│  ┌────────────┐  ┌────────────┐  ┌──────────┐  ┌────────────┐  │
│  │  Page 0    │  │  Page 1    │  │ Page 2   │  │  Page 3    │  │
│  │ Participant│→ │ Hardware   │→ │ Set      │→ │ Run        │  │
│  │ Info       │  │ Setup      │  │ Amplitude│  │ Protocol   │  │
│  └────────────┘  └────────────┘  └──────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture

The application follows **Model-View-Controller (MVC) with Dependency Injection**.

```
┌─────────────────────────────────────────────────────────────────┐
│ VIEW (PySide6)                                                  │
│  ExperimentWindow → 4 Page Widgets                              │
│                        │                  │                     │
│                   uses TIAPI         uses ParticipantAssignerAPI │
└────────────────────────┼──────────────────┼─────────────────────┘
                         │                  │
┌────────────────────────┼──────────────────┼─────────────────────┐
│ CONTROLLER (Facades)   │                  │                     │
│                   ┌────▼────┐    ┌────────▼──────────┐          │
│                   │  TIAPI  │    │ParticipantAssigner │          │
│                   │         │    │       API          │          │
│                   └────┬────┘    └────────┬──────────┘          │
└────────────────────────┼──────────────────┼─────────────────────┘
                         │                  │
┌────────────────────────┼──────────────────┼─────────────────────┐
│ MODEL / SERVICES       │                  │                     │
│                   ┌────▼─────┐   ┌────────▼──────────┐          │
│                   │TIManager │   │AssignmentService   │          │
│                   │          │   │ConditionRepository │          │
│                   │TIConfig  │   │ParticipantsList    │          │
│                   │TISystems │   │ParticipantDataLogger│         │
│                   └────┬─────┘   └───────────────────┘          │
│                        │                                        │
│                   ┌────▼──────────┐                              │
│                   │HardwareManager│                              │
│                   │  (HAL)        │                              │
│                   └────┬──────────┘                              │
│                        │                                        │
│                   ┌────▼──────────────┐                          │
│                   │KeysightEDU33212A  │                          │
│                   │  (SCPI / PyVISA)  │                          │
│                   └───────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

**Key design principles:**

- **Dependency Injection** — Both API facades are constructed outside the UI and injected into `ExperimentWindow`. Pages receive only the APIs they need.
- **Facade pattern** — `TIAPI` and `ParticipantAssignerAPI` provide simplified interfaces. All methods return consistent `Tuple[bool, str/data]` pairs for uniform error handling.
- **State Machine** — Each `TISystem` manages its own logic state (IDLE → RAMPING_UP → RUNNING_AT_TARGET → RAMPING_DOWN).
- **Factory pattern** — `AbstractWaveformGenerator` uses `__init_subclass__` auto-registration so drivers are pluggable at runtime.
- **Repository pattern** — `ConditionRepository` and `ParticipantsList` abstract Excel-based persistence.

---

## 3. Package Structure

```
src/
├── temporal_interference/          # Hardware control & stimulation
│   ├── api.py                      # TIAPI — controller facade for the GUI
│   ├── config.py                   # TIConfig — loads ti_config.json, creates systems
│   ├── core/
│   │   ├── system.py               # TISystem — state machine per stimulation region
│   │   ├── channel.py              # TIChannel — single-channel voltage/frequency manager
│   │   └── electrode.py            # Electrode, ElectrodePair — data models
│   ├── hardware/
│   │   ├── hardware_manager.py     # HardwareManager — HAL coordinating all drivers
│   │   ├── waveform_generator.py   # AbstractWaveformGenerator — base class
│   │   ├── keysight_edu33212A.py   # Real Keysight driver (SCPI over PyVISA)
│   │   ├── mock_visa.py            # Mock VISA layer for development
│   │   └── mockup_config.py        # Mock/real toggle
│   └── services/
│       ├── manager.py              # TIManager — orchestrates systems & protocols
│       ├── system_monitor.py       # SystemMonitor — read-only state polling
│       └── trigger_manager.py      # TriggerManager — background hardware trigger control
│
├── participant/                    # Experiment participant management
│   ├── participant_assigner_api.py # ParticipantAssignerAPI — facade
│   ├── assignment_service.py       # Business logic for row assignment
│   ├── condition_repository.py     # Excel CRUD for conditions file
│   ├── participant_list.py         # Reads participants Excel, filters by rules
│   ├── participant_data_logger.py  # Creates session folders and metadata files
│   └── config_loader.py            # Parses participant_config.txt
│
└── ui/                             # PySide6 GUI
    ├── main_window.py              # ExperimentWindow — tabbed container
    ├── page_participant_info.py    # Page 0 — participant lookup/assignment
    ├── page_hardware_setup.py      # Page 1 — hardware connection & protocol init
    ├── page_set_amplitudes.py      # Page 2 — per-channel amplitude control
    ├── page_run_protocol.py        # Page 3 — protocol execution with live graphs
    └── flexible_spinbox.py         # Custom numeric input (locale-agnostic)
```

---

## 4. Configuration

### 4.1 Hardware Configuration (`config/ti_config.json`)

Defines hardware connections, electrode mappings, TI system topology, safety limits, and protocol parameters.

**Top-level sections:**

| Section | Purpose |
|---------|---------|
| `hardware.waveform_generators` | USB resource names and model IDs for each generator |
| `hardware.electrodes` | Physical electrode IDs and names |
| `hardware.ti_systems` | Logical TI systems (e.g. `ti_A`, `ti_B`) mapping target brain regions to channels and electrode pairs |
| `waveform_generator_config` | Default waveform settings, preset assignments, safety limits (e.g. `max_amplitude_vp: 8.0`), trigger configuration |
| `protocols.active` | Per-system channel settings for the active protocol (frequencies, target voltages, ramp durations) |
| `protocols.sham` | Same structure for the sham protocol |

**Protocol example:**

```
Active protocol:
  ti_A (left amygdala):  7000 Hz / 7130 Hz  →  130 Hz beat frequency
  ti_B (right amygdala): 9000 Hz / 9130 Hz  →  130 Hz beat frequency

Sham protocol:
  ti_A (left amygdala):  7000 Hz / 7000 Hz  →  0 Hz beat (no interference)
  ti_B (right amygdala): 9000 Hz / 9000 Hz  →  0 Hz beat (no interference)
```

### 4.2 Participant Configuration (`config/participant_config.txt`)

A simple key-value file specifying paths to data resources:

```
participants_list_file_path = <path to participant_infos.xlsx>
condition_file_path = <path to Excel_for_stimulators.xlsx>
save_dir_base_path = <path to data output directory>
```

Parsed by `ConfigLoader` with UTF-8 and BOM support.

---

## 5. Application Startup

**Entry point:** `scripts/03_00_TILA_TI-controller-GUI.py`

```
Command line:
  python scripts/03_00_TILA_TI-controller-GUI.py \
    -c config/ti_config.json \
    -p config/participant_config.txt
```

**Startup sequence:**

```
1. Parse CLI arguments (--config, --participant_config)
         │
2. Load ti_config.json → TIConfig
         │
3. TIConfig creates:
   ├── HardwareManager (with waveform generator drivers)
   ├── TIChannels (A1, A2, B1, B2) wired to hardware
   └── TISystems (ti_A, ti_B) containing channels
         │
4. TIManager wraps config, systems, hardware
         │
5. TIAPI wraps TIManager (controller facade)
         │
6. ParticipantAssignerAPI loads:
   ├── participant_config.txt paths
   ├── ConditionRepository → conditions Excel
   └── ParticipantsList → participants Excel
         │
7. QApplication created
         │
8. ExperimentWindow(ti_api, participant_api) launched
         │
9. Qt event loop runs
```

---

## 6. Experiment Session Workflow

A complete experiment session proceeds through four sequential stages, each mapped to a GUI page.

### Stage 1 — Participant Assignment (Page 0)

```
Operator enters participant ID (or selects from list)
  → selects sex (Male / Female)
  → clicks "Validate and Save Participant"
        │
ParticipantAssignerAPI.process_participant(id, sex)
        │
    ┌───┴────────────────────────────────────────┐
    │ Lookup in Conditions Excel by ID           │
    │                                             │
    │ ┌─ Found → status: "existing"              │
    │ │  Return existing row data + session folder│
    │ │                                           │
    │ └─ Not found → AssignmentService            │
    │    ├─ Filter by sex                         │
    │    ├─ Sort by Priority Order                │
    │    ├─ Find first group with blank IDs       │
    │    ├─ Randomly select one row               │
    │    ├─ Write ID to Excel (archive previous)  │
    │    └─ Create session folder + metadata file │
    │       status: "new_assignment"              │
    └─────────────────────────────────────────────┘
        │
UI displays: ID, sex, randomization_number, condition, tasks
  (condition hidden if Hide Mode is enabled for blinding)
```

**Session folder structure:**

```
data/
└── YYYY-MM-DD_<participant_id>/
    └── YYYY-MM-DD_<participant_id>.txt    # Metadata file
```

The metadata file records: participant ID, sex, randomization number, assigned condition, task assignments, EM version, and Stroop version.

### Stage 2 — Hardware Setup (Page 1)

```
Operator clicks "Connect & Initialize Hardware"
        │
TIAPI.connect_hardware()
  → HardwareManager.connect_all()
    → Each KeysightEDU33212A driver opens a PyVISA session
        │
TIAPI.initialize_protocol(condition)
  → TIManager applies protocol settings to all systems
    → Each TIChannel receives: frequency, target voltage, ramp duration
        │
TriggerManager daemon thread started
  (monitors system states in background)
        │
UI displays per-system info:
  ├── System name and target brain region
  ├── Channel electrode pairs
  ├── Frequencies (hidden if Hide Mode on)
  ├── Target voltages
  └── Current status (refreshed every 500ms)
```

### Stage 3 — Set Amplitudes (Page 2)

This optional stage allows the operator to individually test and calibrate channel voltages before running the full protocol.

```
For each channel (A1, A2, B1, B2):
  ┌──────────────────────────────────────────────┐
  │  [Channel Label]  Current: 0.000 V           │
  │  Target: [___0.0___] V                       │
  │  [Start Ramp]  [Stop]  [Save]                │
  └──────────────────────────────────────────────┘

Operator adjusts target voltage via spinbox (0–8 V, step 0.1 V)
  → clicks "Start Ramp"
    → TIAPI.ramp_single_channel(system, channel, target, rate)
      → TISystem spawns ramp thread
      → Voltage increases linearly toward target
      → Current voltage display updates in real time (~250ms)
  → clicks "Save" to lock the amplitude

Constraint: only one channel may ramp at a time.
```

### Stage 4 — Run Protocol (Page 3)

```
Operator clicks "Start Protocol"
        │
TIAPI.start_protocol()
  → TIManager.start_protocol()
    → For each TISystem: spawn ramp-up thread
      → All channels ramp in parallel
        │
    State transitions per system:
      IDLE → WAITING_FOR_TRIGGER → RAMPING_UP → RUNNING_AT_TARGET
        │
TriggerManager (background thread) detects transition:
  1. Enables all hardware channel outputs
  2. Waits trigger_delay_s (1.0 s)
  3. Sends software trigger → generators enter burst mode
  4. Waveforms output at configured frequencies
        │
RunProtocolWidget displays:
  ├── Real-time pyqtgraph plot (200-point rolling buffer, 250ms refresh)
  ├── Per-channel voltage traces (up to 8 channels, colour-coded)
  └── Current voltage readout for selected channel
        │
        ↓  (stimulation runs for desired duration)
        │
Operator clicks "Stop Protocol"
        │
TIAPI.stop_protocol()
  → TIManager.stop_protocol()
    → For each TISystem: spawn ramp-down thread
      → Voltage decreases linearly to 0 V
        │
    State transitions per system:
      RUNNING_AT_TARGET → RAMPING_DOWN → IDLE
        │
TriggerManager detects RUNNING → IDLE:
  1. Waits idle_debounce_s (10.0 s)
  2. Disables all channel outputs
  3. Sends abort command
        │
All hardware stopped. Session complete.
```

### Emergency Stop

At any point the operator can trigger an **Emergency Stop** (dark red button on Page 3), which:

1. Immediately sets all channels to 0 V (no ramp).
2. Disables all hardware outputs.
3. Transitions all systems to IDLE.

### Shutdown

When the operator closes the window:

1. All timers are stopped.
2. `TIAPI.shutdown()` is called — stops TriggerManager, ramps down any active channels, disconnects hardware.
3. Application exits.

---

## 7. Hardware Control Subsystem

### 7.1 Layer Diagram

```
TIAPI (facade)
  │
  ▼
TIManager (orchestrator)
  │
  ├── TISystem (state machine) ──── per stimulation region
  │     │
  │     ├── TIChannel ──── per electrode pair
  │     │     │
  │     │     └── HardwareManager.set_amplitude(), set_frequency(), etc.
  │     │
  │     └── Ramp threads (spawned per system)
  │
  ├── SystemMonitor (read-only state polling)
  │
  └── TriggerManager (background daemon)
        │
        └── HardwareManager.enable_all_channels(), send_software_trigger()
              │
              └── KeysightEDU33212A (SCPI over PyVISA)
```

### 7.2 TISystem State Machine

```
            ┌──────────────────────────────┐
            │                              │
            ▼                              │
         ┌──────┐   start_ramp_up()   ┌────────────────────┐
         │ IDLE │ ──────────────────→ │ WAITING_FOR_TRIGGER │
         └──────┘                     └─────────┬──────────┘
            ▲                                   │
            │                                   ▼
    ┌───────────────┐                    ┌─────────────┐
    │ RAMPING_DOWN  │                    │ RAMPING_UP  │
    └───────┬───────┘                    └──────┬──────┘
            │                                   │
            │                                   ▼
            │                        ┌────────────────────┐
            └─────────────────────── │ RUNNING_AT_TARGET  │
               stop_protocol()       └────────────────────┘
```

Additional intermediate states (`RAMPING_INTERMEDIATE`, `RUNNING_INTERMEDIATE`) handle per-channel ramp adjustments from Page 2. An `ERROR` state exists for fault conditions.

There are two state enums per system:

| Enum | Description |
|------|-------------|
| `TISystemLogicState` | The *intended* state based on commands (IDLE, RAMPING_UP, etc.) |
| `TISystemHardwareState` | The *actual* state derived from cached voltages (IDLE, RUNNING, ERROR) |

### 7.3 HardwareManager

The Hardware Abstraction Layer (HAL) maps logical channel IDs to physical `(driver_instance, physical_channel_number)` tuples. It provides:

- `connect_all()` / `disconnect_all()` — lifecycle management
- `set_frequency()`, `set_amplitude()`, `enable_output()`, `disable_output()` — per-channel control
- `send_software_trigger()` — synchronised trigger across all generators
- `trigger_event` property — threading event for coordination

No global I/O lock; each driver instance is individually thread-safe.

### 7.4 KeysightEDU33212A Driver

- Communicates via SCPI commands over PyVISA (USB).
- Thread-safe: per-resource `RLock` protects all I/O.
- Maintains **shadow state** — an internal cache of all device parameters to enable fast reads without hardware queries.
- 2 physical channels per device.
- Supports burst mode with software trigger.

### 7.5 TriggerManager

A background daemon thread that automates hardware enable/disable based on system state:

| Transition | Action |
|------------|--------|
| Overall IDLE → RUNNING | Enable all channel outputs → wait `trigger_delay_s` → send software trigger |
| Overall RUNNING → IDLE | Wait `idle_debounce_s` → disable all outputs → send abort |

Configurable timing: `poll_interval_s`, `idle_debounce_s`, `trigger_delay_s`.

---

## 8. Participant Management Subsystem

### 8.1 Data Sources

| File | Purpose |
|------|---------|
| `participant_infos.xlsx` | Master list of all eligible participants (sheet: "T-participants") |
| `Excel_for_stimulators.xlsx` | Condition assignment table (randomisation, sex, tasks) |

### 8.2 ParticipantsList

Reads the master participants list and applies filters:

1. Sex must be 'M' or 'F'.
2. If ID starts with 'T', the numeric part must be >= 50.
3. Extracts sex from the last character of the raw ID (e.g. `T88F` → ID=`T88`, sex=`F`).

Returns a DataFrame with columns: `ID`, `sex`.

### 8.3 ConditionRepository

Manages the conditions Excel file:

- **Required columns**: ID, Priority Order, randomization_number, sex, condition, Task1–6, EM version, Stroop version.
- `find_by_id(df, participant_id)` — case-insensitive search.
- `save_data(df, participant_id)` — writes back to Excel preserving formatting (openpyxl). Archives the previous version with a timestamp before each save.

### 8.4 AssignmentService

Finds the next available row for a new participant:

1. Filter the conditions DataFrame by the participant's sex.
2. Sort by Priority Order.
3. Find the first priority group that still has blank IDs.
4. Randomly select one row within that group.
5. Return the row index and data.

### 8.5 ParticipantDataLogger

Creates the file-system record for each session:

- **Folder**: `<save_dir_base_path>/YYYY-MM-DD_<participant_id>/`
- **Metadata file**: `YYYY-MM-DD_<participant_id>.txt` containing participant ID, sex, randomisation number, condition, task list, and version info.
- `find_participant_folders()` — locates existing sessions for a given participant.

### 8.6 ParticipantAssignerAPI

The facade orchestrating the above components. Primary method:

```python
process_participant(participant_id, selected_sex) → Dict
```

Returns:

| Status | Meaning |
|--------|---------|
| `"existing"` | Participant already assigned — returns existing data and folder path |
| `"duplicate_id"` | ID collision detected |
| `"new_assignment"` | Successfully assigned — row written to Excel, session folder created |
| `"no_rows_available"` | No unassigned rows left for the given sex |

Also provides:

- `get_participated_list()` / `get_not_participated_list()` — partitioned participant lists.
- `get_last_participant_condition()` — the condition assigned to the most recently processed participant (used by Page 1 to initialise the correct protocol).

---

## 9. User Interface

### 9.1 ExperimentWindow (Main Container)

```
┌────────────────────────────────────────────────────────┐
│  [☐ Hide Mode]                                         │
├──────────────┬─────────────────────────────────────────┤
│              │                                         │
│  PARTICIPANT │                                         │
│  INFO        │      ┌───────────────────────────────┐  │
│              │      │                               │  │
│  HARDWARE    │      │    Active Page Content        │  │
│  SETUP       │      │    (QStackedWidget)           │  │
│              │      │                               │  │
│  SET SIGNAL  │      │                               │  │
│  AMPLITUDES  │      └───────────────────────────────┘  │
│              │                                         │
│  RUN         │                                         │
│  PROTOCOL    │                                         │
│              │                                         │
├──────────────┴─────────────────────────────────────────┤
│  Navigation pane (light blue)  │  Content pane         │
└────────────────────────────────────────────────────────┘
```

- **Navigation pane**: Four buttons on the left switch between pages.
- **Hide Mode checkbox**: Toggles visibility of the assigned condition (active/sham) for experimenter blinding.
- **`closeEvent()`**: Graceful shutdown — stops timers, calls `ti_api.shutdown()`.

### 9.2 Page 0 — Participant Info

**Inputs:**
- Combo box of available (not yet participated) subjects.
- Text field for manual ID entry.
- Sex selector (Male / Female).
- Optional notes text area.

**Action:** "Validate and Save Participant" button triggers `ParticipantAssignerAPI.process_participant()`.

**Outputs:** Displays the participant's ID, sex, randomisation number, condition, task assignments, and version info. The condition field respects Hide Mode.

### 9.3 Page 1 — Hardware Setup

**Action:** "Connect & Initialize Hardware" button connects to generators and initialises the protocol matching the participant's condition.

**Display:** Scrollable info panel (initially hidden) showing per-system/channel details — electrode pairs, frequencies (hidden in Hide Mode), target and current voltages. Status refreshes every 500ms while the page is visible.

### 9.4 Page 2 — Set Signal Amplitudes

Dynamically creates a control widget for each channel:

- Channel label and live current voltage readout.
- Target voltage spinbox (0–8 V, step 0.1 V) using `FlexibleDoubleSpinBox` (accepts both `.` and `,` as decimal separator).
- Start Ramp / Stop / Save buttons.

Only one channel may ramp at a time. "Save" locks the control; "Un-Save" unlocks it.

### 9.5 Page 3 — Run Protocol

- **Start / Stop / Emergency Stop** buttons.
- **Real-time plot** (pyqtgraph): rolling 200-point voltage traces for all channels, updated every 250ms, colour-coded with legend.
- **Channel selector** combo box for detailed voltage readout.

---

## 10. Threading and Concurrency

### 10.1 Thread Map

| Thread | Purpose | Lifetime |
|--------|---------|----------|
| Main (GUI) | Qt event loop, UI rendering and user interaction | Entire application |
| Ramp threads | Linear voltage ramp-up or ramp-down per TISystem | Spawned per start/stop, terminates when ramp finishes |
| TriggerManager | Background state monitoring, hardware enable/disable/trigger | Daemon — from hardware init to shutdown |
| PyVISA I/O | Implicit — SCPI communication over USB | Per command |

### 10.2 Synchronisation Mechanisms

| Mechanism | Where Used |
|-----------|-----------|
| `threading.RLock` | TISystem (state transitions), TIChannel (voltage cache), KeysightEDU33212A (all SCPI I/O) |
| `threading.Event` | TriggerManager stop signalling |
| Shadow state (driver) | Cached device parameters allow fast GUI reads without I/O contention |

### 10.3 Design Rationale

- No global I/O lock — each driver instance has its own lock, allowing parallel communication with multiple generators.
- GUI reads "cached" (shadow) voltages, never directly blocking on hardware queries.
- Ramp threads independently update cached voltages, which the GUI polls at a fixed interval.
- The TriggerManager daemon monitors system state without modifying it; it only issues hardware commands when state transitions are detected.

---

## 11. Mock Hardware Mode

For development and testing without physical hardware:

1. Create a file named `MOCK_DEVICE_ENABLED` in the project root.
2. `KeysightEDU33212A` detects this marker and imports `mock_visa` instead of the real `pyvisa` module.
3. `mock_visa` simulates a PyVISA `ResourceManager` and instrument responses so the full application workflow can be exercised.

Remove the file to switch back to real hardware.

---

## 12. Testing

Tests live in `tests/` and use **pytest** with **pytest-mock** for VISA mocking.

| Test File | Scope |
|-----------|-------|
| `test_electrodes.py` | Electrode and ElectrodePair construction and validation |
| `test_keysight_edu33212A.py` | SCPI command correctness against mock VISA |
| `test_ti_manager.py` | System initialisation and configuration loading |

**Commands:**

```bash
pytest                                          # Run all tests
pytest tests/test_ti_manager.py -v              # Single file
pytest tests/test_ti_manager.py::test_name -v   # Single test
```

No CI/CD pipeline or linter/formatter is currently configured.

---

## Data Flow Summary

```
                    ┌────────────────────┐
                    │  participant_config │
                    │  .txt              │
                    └────────┬───────────┘
                             │
                    ┌────────▼───────────┐
                    │ParticipantAssigner  │    ┌──────────────────┐
       ┌───────────→│       API          │───→│ Excel files      │
       │            └────────────────────┘    │ Session folders   │
       │                                      └──────────────────┘
  ┌────┴────┐
  │  GUI    │
  │ (Pages) │
  └────┬────┘
       │            ┌────────────────────┐
       │            │    ti_config.json   │
       │            └────────┬───────────┘
       │                     │
       │            ┌────────▼───────────┐
       └───────────→│      TIAPI         │
                    │                    │
                    │  TIManager         │
                    │   ├── TISystems    │
                    │   ├── SystemMonitor│
                    │   └── TriggerMgr   │
                    └────────┬───────────┘
                             │
                    ┌────────▼───────────┐
                    │  HardwareManager   │
                    │  (HAL)             │
                    └────────┬───────────┘
                             │
                    ┌────────▼───────────┐
                    │ Keysight EDU33212A │
                    │ Waveform Generators│
                    └────────────────────┘
```
