# TILA: Temporal Interference amygdaLA

## 1.0 Project Overview

TILA is a Python-based graphical user interface (GUI) application designed for controlling Temporal Interference (TI) stimulation hardware and managing experiment participant data. The application uses `PySide6` for the user interface and provides a clear separation between hardware control, experiment logic, and the view.

## 2.0 Architectural Design

The software is structured into three primary packages: `src/temporal_interference`, `src/participant`, and `src/ui`.

### 2.1 Core Components

* `src/temporal_interference`: Manages all aspects of hardware interaction and stimulation.
    * **Hardware Abstraction**: Includes a `HardwareManager` and specific drivers for devices like the `KeysightEDU33212A` waveform generator.
    * **Core Model**: Defines the core concepts of the stimulation `System`, including `Electrode` and `Channel` configurations.
    * **Services**: A `TIManager` orchestrates the hardware and core logic.
    * **API**: A `TIAPI` serves as the controller interface for the GUI.
* `src/participant`: Manages experiment-related logic.
    * **API**: The `ParticipantAssignerAPI` handles logic for assigning participants to experimental conditions.
    * **Data Persistence**: `ParticipantRepository` and `ConditionRepository` manage storage.
    * **Logging**: A dedicated `ParticipantDataLogger` records experiment data.
* `src/ui`: Implements the `PySide6` user interface.
    * **Main Window**: `main_window.py` defines the main application window.
    * **Pages**: The UI is divided into tabbed pages for `page_hardware_setup.py`, `page_participant_info.py`, `page_run_protocol.py`, and `page_set_amplitudes.py`.

### 2.2 Design Pattern

The application follows a Model-View-Controller (MVC) pattern:

* **Model**: `TIManager` (manages hardware state) and `ParticipantAssignerAPI` (manages experiment state).
* **View**: `ExperimentWindow` (the main `PySide6` application window).
* **Controller**: The `TIAPI` and `ParticipantAssignerAPI` are injected into the View to mediate state changes and execute logic.

## 3.0 Key Features

* Hardware management for TI stimulation (e.g., `Keysight EDU33212A`).
* Mock hardware support for development and testing (`mock_visa.py`, `mockup_config.py`).
* Participant assignment and experimental condition management.
* Automated experiment data logging.
* Tabbed GUI for managing hardware setup, participant info, and running experiment protocols.

## 4.0 Setup and Execution

### 4.1 Prerequisites

* **Python**: Python 3.13 or newer is required.
* **Core Dependencies**:
    * `PySide6`
    * `pyvisa` (inferred for hardware control)

### 4.2 Installation

It is *recommended* to install the package in a virtual environment.

Create a virtual environment:
```bash
python -m venv venv
```

Activate the environment:
* On Windows (PowerShell): .\venv\Scripts\Activate.ps1
* On macOS/Linux (Bash): source venv/bin/activate

Install the package in editable mode:

From the root directory of this project (where this README is located), run:
```bash
# This command installs the project and its dependencies (like PySide6)
pip install -e .
```

### 4.3 Configuration
The application requires two configuration files, specified via command-line arguments.

TI Hardware Config: (Default: `config/ti_config.json`). Defines hardware connection parameters.

Participant API Config: (Default: `config/participant_config.txt`). Defines paths for the participant and condition repositories.

4.4 Execution
The application is launched using the main entry point script.

```bash
# Run with default config paths
python 03_00_TILA_TI-controller-GUI.py

# Run with custom config paths
python 03_00_TILA_TI-controller-GUI.py -c /path/to/ti_config.json -p /path/to/participant_config.txt
```

## 5.0 Logging
Application activity, warnings, and errors are logged to `ti_gui.log` in the root directory.