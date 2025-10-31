# TILA: Temporal Interference amygdaLA

## 1.0 Project Overview

TILA is a Python-based graphical user interface (GUI) application designed for controlling Temporal Interference (TI) stimulation hardware and managing experiment participant data. The application uses PySide6 for the user interface and provides a clear separation between hardware control, experiment logic, and the view.

## 2.0 Architectural Design

The software is structured into three primary packages: `src/temporal_interference`, `src/participant`, and `src/ui`.

### 2.1 Core Components

* **`src/temporal_interference`**: Manages all aspects of hardware interaction and stimulation.
    * **Hardware Abstraction**: Includes a `HardwareManager`  and specific drivers for devices like the `KeysightEDU33212A`  waveform generator.
    * [cite_start]**Core Model**: Defines the core concepts of the stimulation `System` [cite: 233][cite_start], including `Electrode`  [cite_start]and `Channel`  configurations.
    * [cite_start]**Services**: A `TIManager`  orchestrates the hardware and core logic.
    * **API**: A `TIAPI`  serves as the controller interface for the GUI.

* **`src/participant`**: Manages experiment-related logic.
    * **API**: The `ParticipantAssignerAPI`  handles logic for assigning participants to experimental conditions.
    * [cite_start]**Data Persistence**: `ParticipantRepository`  [cite_start]and `ConditionRepository`  manage storage.
    * **Logging**: A dedicated `ParticipantDataLogger`  records experiment data.

* **`src/ui`**: Implements the PySide6 user interface.
    * **Main Window**: `main_window.py`  defines the main application window.
    * [cite_start]**Pages**: The UI is divided into tabbed pages for `page_hardware_setup.py` [cite: 1337][cite_start], `page_participant_info.py` [cite: 1367][cite_start], `page_run_protocol.py` [cite: 1393][cite_start], and `page_set_amplitudes.py`[cite: 1438].

### 2.2 Design Pattern

The application follows a Model-View-Controller (MVC) pattern:

* **Model**: `TIManager` (manages hardware state) and `ParticipantAssignerAPI` (manages experiment state).
* **View**: `ExperimentWindow` (the main PySide6 application window).
* **Controller**: The `TIAPI` and `ParticipantAssignerAPI` are injected into the View to mediate state changes and execute logic.

## 3.0 Key Features

* [cite_start]Hardware management for TI stimulation (e.g., Keysight EDU33212A).
* [cite_start]Mock hardware support for development and testing (`mock_visa.py` [cite: 469][cite_start], `mockup_config.py` ).
* [cite_start]Participant assignment and experimental condition management[cite: 25, 9].
* Automated experiment data logging.
* [cite_start]Tabbed GUI for managing hardware setup, participant info, and running experiment protocols[cite: 1337, 1367, 1393].

## 4.0 Setup and Execution

### 4.1 Dependencies

This project requires Python and the PySide6 library. Hardware control likely requires `pyvisa` or a similar instrumentation library.

* `PySide6`
* `pyvisa` (inferred)

### 4.2 Configuration

The application requires two configuration files, specified via command-line arguments.

* **TI Hardware Config**: (Default: `config/ti_config.json`). Defines hardware connection parameters.
* **Participant API Config**: (Default: `config/participant_config.txt`). Defines paths for the participant and condition repositories.

### 4.3 Execution

The application is launched using the main entry point script.

```bash
# Run with default config paths
python 03_00_TILA_TI-controller-GUI.py

# Run with custom config paths
python 03_00_TILA_TI-controller-GUI.py -c /path/to/ti_config.json -p /path/to/participant_config.txt