# ti_gui/page_set_amplitudes.py (MODIFIED)

import logging
from functools import partial
from typing import Dict, Optional, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QSpacerItem, QSizePolicy, QDoubleSpinBox,
    QPushButton, QHBoxLayout, QScrollArea, QFrame
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, Slot, QSize, QTimer

# Import API for type hinting
from temporal_interference.api import TIAPI

class _ChannelControlWidget(QFrame):
    # ... (content unchanged) ...
    def __init__(self, system_key: str, channel_key: str, parent=None):
        super().__init__(parent)
        self.system_key = system_key
        self.channel_key = channel_key
        
        self.setObjectName("ChannelControlFrame")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)
        
        self.name_label = QLabel(f"{system_key} / {channel_key}")
        font = self.name_label.font()
        font.setPointSize(11)
        self.name_label.setFont(font)
        self.name_label.setMinimumWidth(180)
        
        # --- Live voltage display ---
        self.current_voltage_label = QLabel("0.00 V")
        self.current_voltage_label.setObjectName("CurrentVoltageLabel")
        self.current_voltage_label.setMinimumWidth(70)
        self.current_voltage_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        current_label_text = QLabel("Current:")
        current_label_text.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.spinbox = QDoubleSpinBox()
        self.spinbox.setDecimals(2)
        self.spinbox.setRange(0.0, 20.0) # Example range: 0-20 V
        self.spinbox.setSingleStep(0.05)
        self.spinbox.setValue(0.0)
        self.spinbox.setSuffix(" V")
        self.spinbox.setFixedSize(120, 32)
        
        self.start_button = QPushButton("Start Ramp")
        self.start_button.setFixedSize(100, 32)
        self.start_button.setObjectName("StartRampButton") 
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.setFixedSize(80, 32)
        self.stop_button.setObjectName("StopButton") 
        self.stop_button.setEnabled(False) 
        
        self.save_button = QPushButton("Save")
        self.save_button.setFixedSize(80, 32)
        self.save_button.setObjectName("SaveButton") 
        
        layout.addWidget(self.name_label)
        layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        layout.addWidget(current_label_text)         
        layout.addWidget(self.current_voltage_label) 
        layout.addWidget(QLabel("Target:"))          
        layout.addWidget(self.spinbox)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.save_button)
        
        # Set initial state properties for QSS
        self.setProperty("active", False)
        self.setProperty("saved", False)

    def get_voltage(self) -> float:
        """Returns the current value from the spinbox."""
        return self.spinbox.value()

    def set_voltage(self, voltage: float):
        """Sets the value of the spinbox."""
        self.spinbox.setValue(voltage)

    def update_current_voltage(self, voltage: float):
        """Updates the live voltage display label."""
        self.current_voltage_label.setText(f"{voltage:.2f} V")

    def set_active(self, is_active: bool):
        """Updates the visual 'active' state."""
        self.setProperty("active", is_active)
        self.style().unpolish(self)
        self.style().polish(self)
        
        # Update stop button based on active state (only if not saved)
        if not self.property("saved"):
            self.stop_button.setEnabled(is_active)

    def set_saved(self, is_saved: bool):
        """Updates the visual 'saved' state."""
        self.setProperty("saved", is_saved)
        
        # Disable spinbox/start if saved, re-enable if unsaved
        self.spinbox.setEnabled(not is_saved)
        self.start_button.setEnabled(not is_saved)
        self.stop_button.setEnabled(False) # Stop is always disabled when saved/unsaved
        
        # Update save button text
        self.save_button.setText("Un-Save" if is_saved else "Save")
        
        # Ensure the save button is always enabled, regardless of state
        self.save_button.setEnabled(True)
        
        self.style().unpolish(self)
        self.style().polish(self)


class SetAmplitudesWidget(QWidget):
    """
    Widget for finding and setting individual channel amplitudes.
    
    Ensures only one channel is active at a time and allows
    saving the amplitude for each channel.
    """
    def __init__(self, ti_controller: TIAPI, parent=None):
        super().__init__(parent)
        self.ti_controller = ti_controller
        
        # (sys_key, chan_key) -> _ChannelControlWidget
        self.channel_controls: Dict[Tuple[str, str], _ChannelControlWidget] = {}
        
        # (sys_key, chan_key) -> float
        self.saved_amplitudes: Dict[Tuple[str, str], float] = {}
        
        # (sys_key, chan_key)
        self.active_channel_key: Optional[Tuple[str, str]] = None
        
        # --- Timer for live updates ---
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(250) # Poll 4 times/sec
        self.update_timer.timeout.connect(self._update_channel_statuses)
        
        self.init_ui()
        self.populate_channel_list()
        
    def init_ui(self):
        # ... (content unchanged) ...
        """Initialize the main widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        
        title_font = QFont()
        title_font.setPointSize(14)
        title_label = QLabel("2. Set Signal Amplitudes")
        title_label.setFont(title_font)
        
        info_label = QLabel(
            "Set the desired amplitude (voltage) for one channel and press 'Start Ramp' to test it.\n"
            "Only one channel can be active at a time. Press 'Save' to store the value and stop the ramp."
        )
        info_label.setWordWrap(True)
        
        layout.addWidget(title_label)
        layout.addWidget(info_label)
        layout.addSpacing(15)

        # Scroll area for channel list
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        scroll_widget = QWidget()
        scroll_widget.setObjectName("ScrollWidget")
        self.channel_list_layout = QVBoxLayout(scroll_widget)
        self.channel_list_layout.setContentsMargins(0, 0, 0, 0)
        self.channel_list_layout.setSpacing(5)
        
        scroll_area.setWidget(scroll_widget)
        
        layout.addWidget(scroll_area)
        
        # Add a final spacer to push everything up
        self.channel_list_layout.addSpacerItem(QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        ))
        
        self.setObjectName("MainPane")
        self.apply_stylesheet()

    def populate_channel_list(self):
        # ... (content unchanged) ...
        """
        Queries the TIAPI for all systems and channels
        and creates a _ChannelControlWidget for each.
        """
        try:
            summary = self.ti_controller.get_system_summary()
        except Exception as e:
            logging.error(f"Failed to get system summary: {e}")
            self.channel_list_layout.addWidget(QLabel(f"Error: Could not load system summary. {e}"))
            return
            
        if not summary.get("systems"):
            self.channel_list_layout.addWidget(QLabel("No TI systems were found."))
            return
            
        logging.info(f"Populating amplitude page with {len(summary['systems'])} systems.")
        
        # Insert widgets *before* the spacer
        spacer_index = self.channel_list_layout.count() - 1
        
        for system_key, system_data in summary["systems"].items():
            for channel_key in system_data["channels"].keys():
                key = (system_key, channel_key)
                
                widget = _ChannelControlWidget(system_key, channel_key)
                
                # Connect button signals to slots using partial
                widget.start_button.clicked.connect(partial(self.on_start_ramp, key))
                widget.stop_button.clicked.connect(partial(self.on_stop_ramp, key))
                widget.save_button.clicked.connect(partial(self.on_save_amplitude, key))
                
                self.channel_list_layout.insertWidget(spacer_index, widget)
                self.channel_controls[key] = widget
                spacer_index += 1

    # --- MODIFIED: Uses get_all_current_voltages() ---
    @Slot()
    def _update_channel_statuses(self):
        """Polls the controller for live status and updates all widgets."""
        try:
            # --- THIS IS THE CHANGE ---
            # Use the new, more efficient API method
            success, voltage_data = self.ti_controller.get_all_current_voltages()
            # --- END CHANGE ---
            
            if not success:
                logging.warning(f"Failed to get voltages for amplitude page: {voltage_data}")
                return
        except Exception as e:
            logging.error(f"Error getting voltages: {e}", exc_info=True)
            self.update_timer.stop() # Stop timer on critical error
            return

        any_channel_active = False
        active_keys_from_hw = set()
        all_channel_data: Dict[Tuple[str, str], float] = {}

        # 1. Parse all data and find active channels
        # --- THIS IS THE CHANGE ---
        # The parsing logic is now simpler as it iterates over the
        # specific voltage_data dict instead of the complex status dict
        if isinstance(voltage_data, dict):
            for system_key, system_voltages in voltage_data.items():
                if isinstance(system_voltages, dict):
                    for channel_key, voltage in system_voltages.items():
                        key = (system_key, channel_key)
                        all_channel_data[key] = voltage
                        
                        # Use an epsilon for float comparison
                        if voltage > 0.001:
                            active_keys_from_hw.add(key)
                            any_channel_active = True
        # --- END CHANGE ---
        
        # Update the class-level "active" key
        if len(active_keys_from_hw) == 1:
            self.active_channel_key = list(active_keys_from_hw)[0]
        else:
            self.active_channel_key = None # None if 0 or >1 active

        # 2. Update all widgets based on global state
        #    (This logic remains unchanged as it relies on all_channel_data)
        for key, widget in self.channel_controls.items():
            voltage = all_channel_data.get(key, 0.0)
            is_saved = key in self.saved_amplitudes
            is_this_one_active = key in active_keys_from_hw
            
            # Update live voltage display
            widget.update_current_voltage(voltage)
            # Update visual highlight
            widget.set_active(is_this_one_active)
            
            if is_saved:
                widget.set_saved(True)
            elif any_channel_active:
                # A channel is active, enforce lock
                widget.set_saved(False) 
                
                # Now, disable spinbox/start if this *isn't* the active one
                widget.spinbox.setEnabled(is_this_one_active)
                widget.start_button.setEnabled(is_this_one_active)
                widget.stop_button.setEnabled(is_this_one_active)
            else:
                # No channels active, not saved (idle state)
                widget.set_saved(False) 
                widget.stop_button.setEnabled(False) # Disable stop when idle
    # --- END MODIFICATION ---

    def start_updates(self):
        # ... (content unchanged) ...
        """Called by main window when this page becomes visible."""
        logging.debug("Starting amplitude page updates.")
        self._update_channel_statuses() # Run once immediately
        self.update_timer.start()

    def stop_updates(self):
        # ... (content unchanged) ...
        """Called by main window when this page is hidden."""
        logging.debug("Stopping amplitude page updates.")
        self.update_timer.stop()
        
        # Safety: Stop any active ramp when navigating away
        if self.active_channel_key:
            key_to_stop = self.active_channel_key
            self.active_channel_key = None # Clear immediately
            logging.info(f"Navigating away, stopping active channel {key_to_stop}")
            self.on_stop_ramp(key_to_stop)
        
        # Reset all widgets to idle (non-active) visual state
        for key, widget in self.channel_controls.items():
            widget.set_active(False)
            if not key in self.saved_amplitudes:
                 widget.stop_button.setEnabled(False)

    @Slot(tuple)
    def on_start_ramp(self, key: Tuple[str, str]):
        # ... (content unchanged) ...
        """
        Handles the 'Start Ramp' click for a channel.
        Enforces Constraint 1: Only one channel active.
        """
        system_key, channel_key = key
        
        # --- Constraint 1: Stop other active channel ---
        if self.active_channel_key is not None and self.active_channel_key != key:
            logging.info(f"Stopping active channel {self.active_channel_key} to start {key}")
            self.on_stop_ramp(self.active_channel_key)
        # -----------------------------------------------
        
        widget = self.channel_controls[key]
        target_voltage = widget.get_voltage()
        
        logging.info(f"Ramping channel {key} to {target_voltage}V")
        
        try:
            success, msg = self.ti_controller.ramp_single_channel(
                system_key=system_key,
                channel_key=channel_key,
                target_voltage=target_voltage
            )
            
            if success:
                self.active_channel_key = key
                # Timer will handle visual updates
            else:
                logging.error(f"Failed to ramp {key}: {msg}")
                # TODO: Show error on a status label
                
        except Exception as e:
            logging.error(f"Error during ramp {key}: {e}", exc_info=True)

    @Slot(tuple)
    def on_stop_ramp(self, key: Tuple[str, str]):
        # ... (content unchanged) ...
        """Handles the 'Stop' click for a channel."""
        system_key, channel_key = key
        logging.info(f"Stopping ramp for channel {key}")
        
        try:
            self.ti_controller.ramp_single_channel(
                system_key=system_key,
                channel_key=channel_key,
                target_voltage=0.0
            )
            
            if self.active_channel_key == key:
                self.active_channel_key = None
            
            # Timer will handle visual updates
                
        except Exception as e:
            logging.error(f"Error during stop {key}: {e}", exc_info=True)

    @Slot(tuple)
    def on_save_amplitude(self, key: Tuple[str, str]):
        # ... (content unchanged) ...
        """
        Handles the 'Save'/'Un-Save' click for a channel.
        This now calls the TIAPI to set the target voltage parameter.
        """
        widget = self.channel_controls[key]
        system_key, channel_key = key
        
        # Check if we are "unsaving"
        if key in self.saved_amplitudes:
            logging.info(f"Un-saving amplitude for {key}.")
            del self.saved_amplitudes[key]
            
            # --- THIS IS NEW ---
            # Reset the channel's target voltage parameter to 0.0
            try:
                success, msg = self.ti_controller.set_channel_target_voltage(
                    system_key, channel_key, 0.0
                )
                if not success:
                    logging.error(f"Failed to reset target voltage for {key}: {msg}")
                else:
                    logging.info(f"Reset target voltage for {key} to 0.0V.")
            except Exception as e:
                logging.error(f"Error resetting target voltage for {key}: {e}", exc_info=True)
            # --- END NEW ---
            
            widget.set_saved(False)
            return

        # --- This is the "Save" operation ---
        voltage = widget.get_voltage()
        logging.info(f"Saving amplitude for {key}: {voltage}V")

        # --- THIS IS NEW: Call API to set parameter ---
        try:
            success, msg = self.ti_controller.set_channel_target_voltage(
                system_key, channel_key, voltage
            )
            if not success:
                logging.error(f"Failed to set target voltage for {key}: {msg}")
                # Do not proceed with local save if API call fails
                return
        except Exception as e:
            logging.error(f"Error setting target voltage for {key}: {e}", exc_info=True)
            # Do not proceed with local save if API call fails
            return
        # --- END NEW ---

        # If API call was successful, update local state
        self.saved_amplitudes[key] = voltage
        
        # Stop the ramp (if active)
        if self.active_channel_key == key:
            self.on_stop_ramp(key)
        
        # Update visual state
        widget.set_saved(True)

    def get_saved_amplitudes(self) -> Dict[Tuple[str, str], float]:
        # ... (content unchanged) ...
        """
        Public method that could be called by another component
        (e.g., the 'Run Experiment' page) to retrieve the settings.
        """
        return self.saved_amplitudes

    def apply_stylesheet(self):
        # ... (content unchanged) ...
        """Apply local QSS for the new channel control widgets."""
        self.setStyleSheet("""
            #ChannelControlFrame {
                border: 1px solid #DDDDDD;
                border-radius: 4px;
                background-color: #FFFFFF;
            }
            #ChannelControlFrame[active="true"] {
                background-color: #FFFBEA; /* Light yellow */
                border-color: #F0A30A;
            }
            #ChannelControlFrame[saved="true"] {
                background-color: #F0FFF4; /* Light green */
                border-color: #4A8C1F;
            }
            #ChannelControlFrame[saved="true"] QLabel {
                font-weight: bold;
                color: #3A6F1F;
            }
            
            #CurrentVoltageLabel {
                font-size: 11pt;
                font-weight: bold;
                color: #005A83; /* Dark blue */
                padding-right: 5px;
            }
            #ChannelControlFrame[active="true"] #CurrentVoltageLabel {
                color: #D93025; /* Red when active */
            }
            #ChannelControlFrame[saved="true"] #CurrentVoltageLabel {
                color: #3A6F1F; /* Green when saved */
            }

            /* Start Ramp Button: Light Blue */
            #StartRampButton {
                background-color: #E6F3FF;
                border: 1px solid #0078D4;
                color: #004A83;
                font-weight: bold;
                border-radius: 4px;
            }
            #StartRampButton:hover {
                background-color: #D6E9FF;
            }

            /* Save Button: Neutral Color */
            #SaveButton {
                background-color: #EAEBEE;
                border: 1px solid #505050;
                color: #202020;
                border-radius: 4px;
            }
            #SaveButton:hover {
                background-color: #DCDDDE;
            }
            
            /* Style for the "Un-Save" state */
            #ChannelControlFrame[saved="true"] #SaveButton {
                background-color: #FFF2D6; /* Light Orange */
                border-color: #B37400;
                color: #805300;
            }

            /* Stop Button: Already has objectName, styled for consistency */
            #StopButton {
                background-color: #FEEBEE;
                border: 1px solid #D93025;
                color: #A52118;
                font-weight: bold;
                border-radius: 4px;
            }
            #StopButton:hover {
                background-color: #FEDDDF;
            }
            
            /* Applies to Start, Stop, and Save buttons when disabled */
            QPushButton:disabled {
                background-color: #F5F5F5;
                border-color: #D0D0D0;
                color: #B0B0B0;
                font-weight: normal;
            }
            
            /* Disabled state for SpinBox */
            QDoubleSpinBox:disabled {
                background-color: #F5F5F5;
                border-color: #D0D0D0;
                color: #B0B0B0;
            }
        """)