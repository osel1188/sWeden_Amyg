# ti_gui/page_run_experiment.py (MODIFIED)

import logging
import random
import math  # <-- MODIFIED: Added import
from typing import Dict, Any, Tuple, List

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QDoubleSpinBox, QSpacerItem, QSizePolicy,
    QGroupBox, QScrollArea, QComboBox
)
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QFont, QPalette

# Import the controller *class* for type hinting
from temporal_interference.api import TIAPI

# --- Hard-coded assumptions ---
PLOT_POINTS = 200  # Number of data points to show on the plots
UPDATE_INTERVAL_MS = 250  # Poll controller 4 times per second (4Hz)
# --- End assumptions ---


class RunStimulationWidget(QWidget):
    """
    This widget contains the entire 'Run Experiment' view,
    including its own plots, buttons, and update timer.
    """
    def __init__(self, controller: TIAPI, parent=None):
        super().__init__(parent)
        self.controller = controller

        # --- MODIFIED: Dynamic channel data storage ---
        # (sys_key, ch_key) -> { "buffer_v": np.array,
        #                       "plot_line": pg.PlotDataItem,
        #                       "label_val": QLabel }
        self.channel_data: Dict[Tuple[str, str], Dict[str, Any]] = {}
        
        # --- NEW: Predefined plot colors ---
        self.plot_colors: List[pg.Qt.QtGui.QPen] = [
            pg.mkPen('#00AEEF', width=2), # Blue
            pg.mkPen('#7AC943', width=2), # Green
            pg.mkPen('#ED1C24', width=2), # Red
            pg.mkPen('#F0A30A', width=2), # Yellow
            pg.mkPen('#9F28B5', width=2), # Purple
            pg.mkPen('#30C7B5', width=2), # Teal
            pg.mkPen('#FFFFFF', width=2), # White
            pg.mkPen('#FF8C00', width=2), # Orange
        ]
        # --- END MODIFIED ---

        # --- Data buffers removed; they are now in self.channel_data ---

        # --- MODIFIED: Init order changed ---
        self.init_ui() # Creates self.plot_widget and self.adv_channel_combo
        self._discover_channels() # Populates self.plot_widget and self.adv_channel_combo
        self.connect_signals()
        # --- END MODIFIED ---
        
        # --- Update Timer ---
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_status)
        
        # --- MODIFICATION: Start timer on init ---
        self.update_timer.start(UPDATE_INTERVAL_MS)
        # --- END MODIFICATION ---

        logging.info("RunStimulationWidget initialized.")

    # --- MODIFIED: Replaces _discover_and_build_map ---
    def _discover_channels(self):
        """
        Fetches system/channel data from the controller and builds the
        mapping for all discovered channels.
        """
        try:
            summary = self.controller.get_system_summary()
            all_channels: List[Tuple[str, str]] = [] # List of (system_key, channel_key)
            
            # Use sorted keys to ensure deterministic ordering
            system_keys = sorted(summary.get("systems", {}).keys()) 
            
            for sys_key in system_keys:
                system_data = summary["systems"][sys_key]
                channel_keys = sorted(system_data.get("channels", {}).keys())
                for ch_key in channel_keys:
                    all_channels.append((sys_key, ch_key))

            # Map the discovered channels to our static GUI slots
            for i, (sys_key, ch_key) in enumerate(all_channels):
                key = (sys_key, ch_key)
                name = f"{sys_key} / {ch_key}"
                color = self.plot_colors[i % len(self.plot_colors)]
                
                logging.info(f"Mapping GUI channel: {name}")

                # 1. Create plot line on the single plot
                plot_line = self.plot_widget.plot(pen=color, name=name)
                
                # 2. Create data buffer
                buffer_v = np.zeros(PLOT_POINTS)
                
                # 3. Create label row
                # MODIFICATION: Changed label to only show Voltage
                label_row, value_label = self._create_channel_label_row(name, color, "0.00 V")
                self.channel_labels_layout.addWidget(label_row)

                # 4. Store references
                self.channel_data[key] = {
                    "buffer_v": buffer_v,
                    "plot_line": plot_line,
                    "label_val": value_label
                }
                
                # --- NEW: Add to advanced controls combo box ---
                self.adv_channel_combo.addItem(name, userData=key)
                # --- END NEW ---
            
            if not all_channels:
                logging.warning("No channels found by _discover_channels.")
                self.channel_labels_layout.addWidget(QLabel("No channels found."))
                self.adv_channel_combo.setEnabled(False)
                self.adv_voltage_spinbox.setEnabled(False)
                self.adv_update_button.setEnabled(False)
            
            # Add spacer to push labels up
            self.channel_labels_layout.addSpacerItem(QSpacerItem(
                20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            ))

        except Exception as e:
            msg = f"Failed to discover channels: {e}. GUI will be non-functional."
            logging.error(msg, exc_info=True)
            if hasattr(self, "channel_labels_layout"):
                 self.channel_labels_layout.addWidget(QLabel(msg))
            else:
                # Fallback if UI hasn't been built
                logging.critical("Channel discovery failed before UI initialization.")
    # --- END NEW METHOD ---

    def init_ui(self):
        """Initialize the UI for this specific page."""
        self.setObjectName("MainPane") # Use same style as main pane
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(20)

        title_font = QFont()
        title_font.setPointSize(14)
        title_label = QLabel("Experiment Procedure")
        title_label.setFont(title_font)
        main_layout.addWidget(title_label)

        # --- 1. Monitoring Box ---
        # --- MODIFIED: Call new UI builder ---
        monitor_box = self._create_monitoring_ui()
        # --- END MODIFIED ---
        main_layout.addWidget(monitor_box)

        # --- 2. Update Controls (REMOVED) ---
        
        # --- 3. Main Controls (Start/Stop) ---
        control_box = QFrame()
        control_layout = QHBoxLayout(control_box)
        control_layout.setContentsMargins(0, 10, 0, 0)
        
        self.btn_start = QPushButton("START EXPERIMENT")
        self.btn_start.setObjectName("StartButton")
        self.btn_start.setMinimumHeight(50)
        
        self.btn_stop = QPushButton("STOP EXPERIMENT")
        self.btn_stop.setObjectName("StopButton")
        self.btn_stop.setMinimumHeight(50)
        
        control_layout.addWidget(self.btn_start)
        control_layout.addWidget(self.btn_stop)
        main_layout.addWidget(control_box)
        
        # --- 3b. NEW: Advanced Controls (Manual Ramp) ---
        self.advanced_controls_group = QGroupBox("Advanced Controls")
        self.advanced_controls_group.setCheckable(True)
        self.advanced_controls_group.setChecked(False) # Start collapsed/hidden
        
        # --- MODIFIED: Added stylesheet for visibility ---
        self.advanced_controls_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #4A4A4A;
                margin-top: 10px;
            }
            QGroupBox::title {
                color: #E0E0E0;
                padding: 2px 5px;
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding-left: 10px;
            }
            QGroupBox::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #AAAAAA;
                background-color: #3C3C3C;
                margin-left: 10px;
            }
            QGroupBox::indicator:checked {
                background-color: #00AEEF;
                border: 1px solid #FFFFFF;
            }
            QGroupBox::indicator:disabled {
                border: 1px solid #666666;
                background-color: #333333;
            }
        """)
        # --- END MODIFIED ---
        
        # --- MODIFIED: Create container widget for toggling visibility ---
        self.adv_controls_widget = QWidget()
        adv_layout = QHBoxLayout(self.adv_controls_widget)
        # --- END MODIFIED ---
        
        adv_layout.setContentsMargins(10, 10, 10, 10)
        adv_layout.setSpacing(10)
        
        adv_layout.addWidget(QLabel("Channel:"))
        
        self.adv_channel_combo = QComboBox()
        self.adv_channel_combo.setMinimumWidth(180)
        
        self.adv_voltage_spinbox = QDoubleSpinBox()
        self.adv_voltage_spinbox.setDecimals(2)
        self.adv_voltage_spinbox.setRange(0.0, 20.0) # Example range
        self.adv_voltage_spinbox.setSingleStep(0.05)
        self.adv_voltage_spinbox.setValue(0.0)
        self.adv_voltage_spinbox.setSuffix(" V")
        self.adv_voltage_spinbox.setMinimumWidth(100)
        
        self.adv_update_button = QPushButton("UPDATE CHANNEL")
        # Use a neutral style, similar to "Save" on amplitude page
        self.adv_update_button.setObjectName("SaveButton") 
        
        # --- MODIFICATION: Start button disabled ---
        self.adv_update_button.setEnabled(False)
        # --- END MODIFICATION ---
        
        adv_layout.addWidget(self.adv_channel_combo)
        adv_layout.addWidget(QLabel("Target Voltage:"))
        adv_layout.addWidget(self.adv_voltage_spinbox)
        adv_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        adv_layout.addWidget(self.adv_update_button)
        
        # --- MODIFIED: Add container widget to groupbox layout ---
        group_box_layout = QVBoxLayout(self.advanced_controls_group)
        group_box_layout.setContentsMargins(0, 5, 0, 0) # Layout on groupbox
        group_box_layout.addWidget(self.adv_controls_widget)

        # --- MODIFIED: Hide widget by default ---
        self.adv_controls_widget.setVisible(False)
        # --- END MODIFIED ---
        
        main_layout.addWidget(self.advanced_controls_group)
        # --- END NEW ---

        # --- 4. Status Bar ---
        self.status_label = QLabel("Status: Ready")
        self.status_label.setObjectName("StatusLabel")
        main_layout.addWidget(self.status_label)
        
        main_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

    # --- MODIFIED: Replaces _create_monitoring_box ---
    def _create_monitoring_ui(self) -> QFrame:
        """Creates the dark grey box with a single plot and value labels."""
        monitor_frame = QFrame()
        monitor_frame.setObjectName("MonitorBox")
        monitor_layout = QVBoxLayout(monitor_frame)
        monitor_layout.setContentsMargins(20, 15, 20, 20)

        title = QLabel("REAL-TIME SIGNAL MONITORING")
        title.setObjectName("MonitorTitle")
        monitor_layout.addWidget(title)

        # 1. Single Plot Widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(None)
        
        # Configure axes
        axis_pen = pg.mkPen(color=(200, 200, 200))
        
        # --- MODIFICATION: Define color value separately ---
        text_color = (220, 220, 220) # Define the color
        text_pen = pg.mkPen(color=text_color) # Create pen from color
        # --- END MODIFICATION ---
        
        self.plot_widget.getAxis('left').setPen(axis_pen)
        self.plot_widget.getAxis('bottom').setPen(axis_pen)
        self.plot_widget.getAxis('left').setTextPen(text_pen)
        self.plot_widget.getAxis('bottom').setTextPen(text_pen)
        self.plot_widget.setLabel('left', 'Amplitude (Vp)', color='#CCC')
        self.plot_widget.setLabel('bottom', 'Time (samples)', color='#CCC')
        
        self.plot_widget.setMouseEnabled(x=False, y=True) # Allow Y-pan/zoom
        self.plot_widget.setMinimumHeight(200) # Give plot space
        
        # --- MODIFICATION: Pass the 'text_color' value, not the 'text_pen' object ---
        self.plot_widget.addLegend(pen=axis_pen, labelTextColor=text_color)
        # --- END MODIFICATION ---
        
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # <-- MODIFIED: Set initial Y range -->
        self.plot_widget.setYRange(0, 6)
        # <-- END MODIFIED -->
        
        monitor_layout.addWidget(self.plot_widget)
        
        # 2. Scroll Area for labels
        labels_scroll_area = QScrollArea()
        labels_scroll_area.setWidgetResizable(True)
        labels_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        labels_scroll_area.setStyleSheet("background-color: transparent; border: none;")
        labels_scroll_area.setMinimumHeight(120)
        
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: transparent;")
        self.channel_labels_layout = QVBoxLayout(scroll_widget)
        self.channel_labels_layout.setContentsMargins(0, 5, 0, 0)
        self.channel_labels_layout.setSpacing(4)
        
        labels_scroll_area.setWidget(scroll_widget)
        monitor_layout.addWidget(labels_scroll_area)

        return monitor_frame
    # --- END MODIFIED ---

    # --- MODIFIED: Replaces _create_plot_row ---
    def _create_channel_label_row(self, title: str, color_pen: pg.Qt.QtGui.QPen,
                                  default_text: str) -> Tuple[QWidget, QLabel]:
        """Helper to create one text value label row."""
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(5, 2, 5, 2)

        title_label = QLabel(title)
        title_label.setObjectName("PlotTitle")
        title_label.setMinimumWidth(180) # Increased width for longer labels
        # Set text color from pen
        title_label.setStyleSheet(f"color: {color_pen.color().name()}; font-weight: bold; background-color: transparent;")
        
        row_layout.addWidget(title_label)
        row_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        value_label = QLabel(default_text)
        value_label.setObjectName("PlotValue")
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value_label.setMinimumWidth(100)
        row_layout.addWidget(value_label)

        return row_widget, value_label
    # --- END MODIFIED ---

    def connect_signals(self):
        """Connect all button clicks to their handler methods."""
        self.btn_start.clicked.connect(self._start_experiment)
        self.btn_stop.clicked.connect(self._stop_experiment)
        
        # --- Connect advanced controls ---
        self.advanced_controls_group.toggled.connect(self._on_advanced_group_toggled)
        self.adv_channel_combo.currentIndexChanged.connect(self._on_advanced_channel_selected)
        self.adv_update_button.clicked.connect(self._on_advanced_update)
        
    def showEvent(self, event):
        """
        Called when the widget is shown (e.g., QStackedWidget switches to it).
        Starts the update timer.
        """
        logging.info("RunStimulationWidget shown.")        
        super().showEvent(event)

    def hideEvent(self, event):
        """
        Called when the widget is hidden (e.g., QStackedWidget switches away).
        Stops the update timer.
        """
        logging.info("RunStimulationWidget hidden.")
        super().hideEvent(event)

    # --- Controller Slots ---
    
    @Slot()
    def _start_experiment(self):
        self.status_label.setText("Status: Issuing start command...")
        success, message = self.controller.start_protocol()
        self.status_label.setText(f"Status: {message}")

    @Slot()
    def _stop_experiment(self):
        self.status_label.setText("Status: Issuing stop command...")
        success, message = self.controller.stop_protocol()
        self.status_label.setText(f"Status: {message}")

    # --- NEW SLOT ---
    @Slot(bool)
    def _on_advanced_group_toggled(self, checked: bool):
        """
        Handles toggling the advanced controls group box.
        Shows/hides the controls and refreshes the voltage spinbox
        when the box is shown.
        """
        self.adv_controls_widget.setVisible(checked)
        if checked:
            # Refresh the voltage value to match the current selection
            self._on_advanced_channel_selected()
    # --- END NEW SLOT ---

    # --- MODIFIED: Slot logic changed to fetch TARGET voltage ---
    @Slot()
    def _on_advanced_channel_selected(self):
        """
        Updates the advanced voltage spinbox to match the
        currently selected channel's *target* voltage.
        """
        # --- MODIFIED: Use correct 'currentData' method ---
        key = self.adv_channel_combo.currentData()
        # --- END MODIFIED ---

        if not isinstance(key, tuple) or len(key) != 2:
            self.adv_voltage_spinbox.setValue(0.0) # Reset on invalid
            return # No valid channel selected

        sys_key, ch_key = key
        
        # --- MODIFIED: Fetch target voltage from controller ---
        # This method is assumed to exist on the TIAPI,
        # symmetric to 'set_channel_target_voltage'.
        success, data = self.controller.get_channel_target_voltage(
            system_key=sys_key,
            channel_key=ch_key
        )
        
        if success and isinstance(data, (float, int)):
            self.adv_voltage_spinbox.setValue(data)
        else:
            # Fallback: Log error and set to 0.
            # Using the last measured value would be misleading,
            # as the user explicitly wants the *target*.
            logging.warning(f"Failed to get target voltage for {key}: {data}. "
                            f"Setting spinbox to 0.0.")
            self.adv_voltage_spinbox.setValue(0.0)

    @Slot()
    def _on_advanced_update(self):
        """
        Handles the 'UPDATE' button click in the advanced controls.
        Sets the target voltage parameter AND initiates a ramp.
        """
        key = self.adv_channel_combo.currentData()

        if not isinstance(key, tuple) or len(key) != 2:
            logging.warning("Advanced update clicked but no valid channel is selected.")
            self.status_label.setText("Status: ERROR (No channel selected)")
            return

        sys_key, ch_key = key
        voltage = self.adv_voltage_spinbox.value()
        
        logging.info(f"Advanced Update: Setting target for {key} to {voltage}V...")
        self.status_label.setText(f"Status: Setting {sys_key}/{ch_key} target to {voltage:.2f}V...")

        # 1. Set the target voltage parameter (for future protocol runs)
        set_success, set_msg = self.controller.set_channel_target_voltage(
            system_key=sys_key,
            channel_key=ch_key,
            target_voltage=voltage
        )
        
        if not set_success:
            logging.error(f"Failed to set target voltage for {key}: {set_msg}")
            self.status_label.setText(f"Status: ERROR (Set target failed: {set_msg})")
            return

        # 2. Initiate the ramp (for immediate effect)
        logging.info(f"Advanced Update: Ramping {key} to {voltage}V...")
        self.status_label.setText(f"Status: Ramping {sys_key}/{ch_key} to {voltage:.2f}V...")
        
        ramp_success, ramp_msg = self.controller.ramp_single_channel(
            system_key=sys_key,
            channel_key=ch_key,
            target_voltage=voltage
        )
        
        if ramp_success:
            self.status_label.setText(f"Status: Ramp initiated for {sys_key}/{ch_key}.")
        else:
            logging.error(f"Failed to ramp {key}: {ramp_msg}")
            self.status_label.setText(f"Status: ERROR (Ramp failed: {ramp_msg})")

    # --- MODIFIED: Switched to use new granular API methods ---
    @Slot()
    def _update_status(self):
        """
        Polls the controller using the new granular API methods for
        voltages (for plots) and overall status (for the text label).
        """
        try:
            # 1. Get plot data (voltages) using the new API method
            v_success, v_data = self.controller.get_all_current_voltages()
            
            if not v_success:
                logging.warning(f"Failed to get voltages: {v_data}")
                self._update_plots(None) # Call with None to zero plots
            else:
                self._update_plots(v_data) # Pass voltage map to plots

            # 2. Get overall status text using the new API method
            s_success, s_data = self.controller.get_overall_status()
            
            # --- MODIFICATION: Enable/Disable advanced update button ---
            # Button should only be active if all systems are at target
            if s_success and s_data == "RUNNING_AT_TARGET":
                self.adv_update_button.setEnabled(True)
            else:
                self.adv_update_button.setEnabled(False)
            # --- END MODIFICATION ---
            
            if not s_success:
                logging.warning(f"Failed to get overall status: {s_data}")
                self.status_label.setText("Status: ERROR (poll failed)")
            else:
                # Only update label if not in the middle of a command
                # (This check prevents overwriting "Issuing start..." immediately)
                current_text = self.status_label.text()
                if not current_text.startswith("Status: Issuing") and \
                   not current_text.startswith("Status: Setting") and \
                   not current_text.startswith("Status: Ramping"):
                     self.status_label.setText(f"Status: {s_data}")

        except Exception as e:
            logging.error(f"Error in update_status: {e}", exc_info=True)
            self._update_plots(None)
            self.status_label.setText("Status: ERROR (exception)")
    # --- END MODIFIED ---

    # --- MODIFIED: Logic rewritten to handle new voltage_map and set Y-range ---
    def _update_plots(self, voltage_map: Dict[str, Dict[str, float]] | None):
        """
        Updates all channel plot lines and text labels based on
        the voltage map from the controller.
        
        Also dynamically adjusts the Y-axis range.
        """
        
        global_max_v = 0.0 # Track max voltage for auto-ranging
        
        for key, ch_data in self.channel_data.items():
            sys_key, ch_key = key
            v = 0.0 # Default to 0
            
            if voltage_map:
                # Get the specific voltage for this channel
                # The new API method returns a simple nested dict
                v = voltage_map.get(sys_key, {}).get(ch_key, 0.0)

            # --- Update buffer ---
            buffer_v = ch_data["buffer_v"]
            buffer_v = np.roll(buffer_v, -1)
            buffer_v[-1] = v
            ch_data["buffer_v"] = buffer_v # Store rolled buffer back
            
            # --- Update plot line ---
            ch_data["plot_line"].setData(buffer_v)
            
            # --- Update text label ---
            # NOTE: The new API method only provides voltage.
            # Current (A) is no longer available via this path.
            ch_data["label_val"].setText(f"{v:.2f} V")
            
            # <-- MODIFIED: Check max of this buffer -->
            buffer_max = np.max(buffer_v)
            global_max_v = max(global_max_v, buffer_max)
            # <-- END MODIFIED -->

        # <-- MODIFIED: Set dynamic Y-axis range -->
        target_y_max = max(6.0, math.ceil(global_max_v))
        self.plot_widget.setYRange(0, target_y_max)
        # <-- END MODIFIED -->
    # --- END MODIFIED ---