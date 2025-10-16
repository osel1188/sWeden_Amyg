SWEDEN_AMYG/
├── code/
│   ├── scripts/
│   │   ├── 00_00_TILA_TI-controller-GUI.py
│   │   ├── 00_00_TILA_TI-controller.py
│   │   ├── 01_00_TILA_TI-controller-GUI.py
│   │   └── simplest_comm.py
│   └── src/
│       ├── device_comm/
│       │   ├── keysight_edu_mockup.py
│       │   ├── keysight_edu.py
│       │   └── UI_device_control/
│       ├── GUI/
│       │   ├── individual_channel_popup/
│       │   │   ├── ChannelControlFrame.py
│       │   │   └── TargetVoltageSettings_Popup.py
│       │   ├── stim_controller_gui.py
│       │   ├── stim_controller_with_gui.py
│       │   └── stim_controller.py
│       ├── configurable_csv_logger.py
│       └── participant_assigner.py
├── config/
│   ├── keysight_config.json
│   └── participant_conditions_path.txt.template
└── logs/



--------------------
novel approach:
--------------------
SWEDEN_AMYG/
├── .gitignore          # Specifies intentionally untracked files to ignore.
├── pyproject.toml      # Poetry's config file for dependencies and project settings.
├── README.md           # Project documentation entry point.
├── config/
│   ├── keysight_config.json
│   └── participant_conditions.yml.template # YAML is more readable than .txt for structured data.
├── logs/               # Unchanged. For runtime log output.
├── scripts/            # Repurposed for utility/automation scripts (e.g., data processing).
│   └── process_log_data.py
├── src/
│   └── sweden_amyg/    # The installable Python package.
│       ├── __init__.py
│       ├── __main__.py   # Enables running the package with 'python -m sweden_amyg'.
│       ├── cli.py        # Defines the command-line interface (e.g., using Typer).
│       ├── core/         # Core application logic, decoupled from UI.
│       │   ├── __init__.py
│       │   ├── stim_controller.py
│       │   └── participant_manager.py
│       ├── devices/      # Replaces 'device_comm' for clarity.
│       │   ├── __init__.py
│       │   ├── keysight_edu.py
│       │   └── mock/
│       │       └── keysight_edu_mock.py
│       ├── gui/          # All GUI-specific code.
│       │   ├── __init__.py
│       │   ├── main_window.py
│       │   └── widgets/
│       │       └── individual_channel_popup.py
│       └── utils/        # Shared utilities.
│           ├── __init__.py
│           └── configurable_csv_logger.py
└── tests/
    ├── __init__.py
    ├── test_stim_controller.py
    └── test_device_comm.py