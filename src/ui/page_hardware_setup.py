# ti_gui/page_hardware_setup.py (MODIFIED)

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit,
    QSizePolicy, QFrame, QScrollArea
)
# --- MODIFIED: Add QTimer ---
from PySide6.QtCore import Slot, Qt, QTimer
# --- END MODIFICATION ---
from PySide6.QtGui import QFont

# Import controller and page for type hinting
from temporal_interference.api import TIAPI
from participant import ParticipantAssignerAPI

class HardwareSetupWidget(QWidget):
    """
    Page for connecting to hardware and initializing the selected protocol.
    """
    def __init__(self, 
                 ti_controller: TIAPI, 
                 participant_api: ParticipantAssignerAPI, 
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.ti_controller = ti_controller
        self.participant_api = participant_api
        
        self.is_hide_mode = False 
        self.last_status_info = None 
        
        # --- NEW: Update timer for live status ---
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(500) # Poll 2 times/sec
        self.update_timer.timeout.connect(self._update_status_display)
        # --- END NEW ---
        
        self.init_ui()
        self.connect_signals()
        logging.info("HardwareSetupWidget initialized.")

    def init_ui(self):
        # ... (no changes in this method) ...
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)

        title = QLabel("Step 2: Hardware Connection and Protocol Initialization")
        title.setFont(title_font)
        title.setWordWrap(True)
        
        description = QLabel(
            "Press the button below to connect to the TI hardware and "
            "initialize the protocol based on the assigned participant condition."
        )
        description.setWordWrap(True)

        self.connect_button = QPushButton("Connect & Initialize Hardware")
        self.connect_button.setObjectName("StartButton") # Use green style
        self.connect_button.setMinimumHeight(40)
        
        self.info_scroll_area = QScrollArea()
        self.info_scroll_area.setWidgetResizable(True)
        self.info_scroll_area.setVisible(False) # Hide until connected
        
        self.info_frame = QFrame()
        self.info_frame.setObjectName("InfoFrame")
        self.info_layout = QVBoxLayout(self.info_frame)
        self.info_layout.setContentsMargins(15, 15, 15, 15)
        self.info_scroll_area.setWidget(self.info_frame)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Connection and initialization logs will appear here...")

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(10)
        layout.addWidget(self.connect_button, 0)
        
        # --- MODIFICATION: Changed stretch factor for info_scroll_area to 2 ---
        # This gives info_scroll_area twice the vertical space as log_output.
        layout.addWidget(self.info_scroll_area, 2) # Give info scroll stretch (2)
        # --- END MODIFICATION ---
        
        layout.addWidget(self.log_output, 1) # Give log output stretch (1)

    def connect_signals(self):
        # ... (no changes in this method) ...
        """Connect button signals to slots."""
        self.connect_button.clicked.connect(self._on_connect_clicked)

    def log(self, message: str):
        # ... (no changes in this method) ...
        """Appends a message to the log output."""
        logging.info(f"HardwarePage Log: {message}")
        self.log_output.append(message)

    @Slot(bool)
    def set_hide_mode(self, hide: bool):
        # ... (no changes in thisD method) ...
        """Public slot to update the hide mode from the main window."""
        self.is_hide_mode = hide
        # If info is already displayed, refresh it to hide/show frequencies
        if self.info_scroll_area.isVisible() and self.last_status_info:
            self.log(f"Hide mode set to {hide}. Refreshing system display.")
            self._build_system_info_display(self.last_status_info)
            
    def _build_system_info_display(self, info: dict):
        """
        Rebuilds the info display frame with data from get_status().
        Conditionally hides frequencies based on self.is_hide_mode.
        """
        # 1. Clear existing info
        while self.info_layout.count():
            child = self.info_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.last_status_info = info # Cache for refresh
        
        # --- MODIFICATION: Only show if not already visible ---
        #     (Prevents flicker if connect button is hit twice)
        if not self.info_scroll_area.isVisible():
            self.info_scroll_area.setVisible(True)
        # --- END MODIFICATION ---

        # 2. Build HTML content
        html_content = "<html><head><style>"
        html_content += "h3 { color: #005A83; margin-top: 10px; margin-bottom: 5px; border-bottom: 1px solid #E0E0E0; padding-bottom: 4px;}"
        html_content += "table { width: 100%; border-collapse: collapse; margin-bottom: 15px; }"
        html_content += "th, td { border: 1px solid #DDDDDD; padding: 6px; text-align: left; font-size: 10pt; }"
        html_content += "th { background-color: #E6F3F8; font-weight: bold; width: 30%; }"
        html_content += "td { font-family: 'Consolas', 'Courier New'; }"
        html_content += "td.name { font-family: 'Segoe UI', 'Arial'; font-weight: bold; }"
        # --- NEW: Added 'small' class for verbose electrode info ---
        html_content += "td.small { font-family: 'Consolas', 'Courier New'; font-size: 8pt; }"
        # --- NEW CSS CLASS: For active voltage ---
        html_content += "td.active_v { background-color: #D5F5D5; color: #004D00; font-weight: bold; }"
        # --- END NEW CSS CLASS ---
        html_content += "</style></head><body>"
        
        if not info:
            html_content += "<p>No system information returned from controller.</p>"
        
        for system_key, system_channels_dict in info.items():
            html_content += f"<h3>System: {system_key.upper()}</h3>"
            
            system_state = "UNKNOWN"
            is_ramping = "UNKNOWN"
            if system_channels_dict:
                first_channel_data = next(iter(system_channels_dict.values()))
                system_state = first_channel_data.get('system_state', 'UNKNOWN')
                is_ramping_bool = first_channel_data.get('is_system_ramping', False)
                is_ramping = "YES" if is_ramping_bool else "NO"
            
            html_content += "<table>"
            html_content += f"<tr><th>State</th><td>{system_state}</td></tr>"
            html_content += f"<tr><th>Is Ramping?</th><td>{is_ramping}</td></tr>"
            html_content += "</table>"

            if system_channels_dict:
                html_content += "<table>"
                # --- MODIFICATION: Added new columns ---
                html_content += "<tr><th>Channel</th>"
                html_content += "<th>Target V (Vp)</th>"
                if not self.is_hide_mode:
                    html_content += "<th>Frequency (Hz)</th>" 
                html_content += "<th>Current V (Vp)</th>"
                html_content += "<th>Generator ID</th>"
                html_content += "<th>Gen. Ch.</th>"
                html_content += "<th>Electrode Pair</th></tr>"
                # --- END MODIFICATION ---
                
                for ch_key, ch_data in system_channels_dict.items():
                    html_content += f"<tr><td class='name'>{ch_key.upper()}</td>"
                    
                    target_v_val = ch_data.get('target_voltage', 0.0)
                    target_v_str = f"{target_v_val:.2f}"
                    html_content += f"<td>{target_v_str}</td>"

                    if not self.is_hide_mode:
                        freq_val = ch_data.get('target_frequency', 0.0) 
                        freq_str = f"{freq_val:.1f}"
                        html_content += f"<td>{freq_str}</td>"
                    
                    # --- MODIFICATION: Added conditional formatting ---
                    current_v_val = ch_data.get('current_voltage', 0.0) 
                    current_v_str = f"{current_v_val:.2f}"
                    # Apply 'active_v' class if voltage is not 0
                    td_class = " class='active_v'" if current_v_val != 0.0 else ""
                    html_content += f"<td{td_class}>{current_v_str}</td>"
                    # --- END MODIFICATION ---
                    
                    # --- MODIFICATION: Added new data cells ---
                    wavegen_id_str = ch_data.get('wavegen_id', 'N/A')
                    wavegen_ch_str = ch_data.get('wavegen_channel', 'N/A')
                    electrode_pair_str = ch_data.get('electrode_pair', 'N/A')
                    
                    html_content += f"<td>{wavegen_id_str}</td>"
                    html_content += f"<td>{wavegen_ch_str}</td>"
                    html_content += f"<td class='small'>{electrode_pair_str}</td>"
                    # --- END MODIFICATION ---
                    
                    html_content += "</tr>"
                html_content += "</table>"
            else:
                html_content += "<p>No channel data available for this system.</p>"
        
        html_content += "</body></html>"
        
        info_label = QLabel(html_content)
        info_label.setWordWrap(True)
        info_label.setTextFormat(Qt.TextFormat.RichText)
        self.info_layout.addWidget(info_label)
        self.info_layout.addStretch()

    # --- NEW METHOD: Timer slot ---
    @Slot()
    def _update_status_display(self):
        """Periodically fetches status and updates the info display."""
        
        # Only update if the info box is visible (i.e., after initial connect)
        if not self.info_scroll_area.isVisible():
            return
            
        try:
            status_ok, info = self.ti_controller.get_status()
            if status_ok:
                # Rebuild the display with the new info
                self._build_system_info_display(info)
            else:
                logging.warning(f"Hardware page: Failed to get status update: {info}")
        except Exception as e:
            logging.error(f"Hardware page: Error getting status: {e}", exc_info=True)
            self.update_timer.stop() # Stop timer on critical error
    # --- END NEW METHOD ---

    # --- NEW METHOD: Public timer control ---
    def start_updates(self):
        """Called by main window when this page becomes visible."""
        logging.debug("Starting hardware page updates.")
        # Only run the immediate update if we've connected at least once
        if self.last_status_info is not None:
            self._update_status_display() # Run once immediately
        self.update_timer.start()
    # --- END NEW METHOD ---

    # --- NEW METHOD: Public timer control ---
    def stop_updates(self):
        """Called by main window when this page is hidden."""
        logging.debug("Stopping hardware page updates.")
        self.update_timer.stop()
    # --- END NEW METHOD ---

    @Slot()
    def _on_connect_clicked(self):
        # ... (method content is unchanged, but note that the
        #    _build_system_info_display call here will be the *first*
        #    time the display is built, which also sets
        #    self.last_status_info and makes the timer effective) ...
        """
        Handles the click event for the 'Connect & Initialize' button.
        """
        self.log_output.clear()
        self.info_scroll_area.setVisible(False) 
        self.last_status_info = None
        
        self.connect_button.setEnabled(False)
        self.connect_button.setText("Processing...")

        # --- 1. Get Condition from Participant API ---
        try:
            protocol_name = self.participant_api.get_last_participant_condition()
            
            if not protocol_name:
                self.log("Error: No condition assigned. Please process participant on 'Participant Info' page first.")
                self.connect_button.setEnabled(True)
                self.connect_button.setText("Connect & Initialize Hardware")
                return
            
            self.log(f"Condition found: '{protocol_name}'. Using as protocol.")
        
        except Exception as e:
            self.log(f"Error fetching condition: {e}")
            self.connect_button.setEnabled(True)
            self.connect_button.setText("Connect & Initialize Hardware")
            return

        # --- 2. Connect to Hardware ---
        self.log("Attempting to connect to hardware...")
        success, msg = self.ti_controller.connect_hardware()
        self.log(msg)
        
        if not success:
            self.log("Hardware connection failed. See logs for details.")
            self.connect_button.setEnabled(True)
            self.connect_button.setText("Retry Connection")
            return

        # --- 3. Initialize Protocol ---
        self.log(f"Hardware connected. Initializing protocol '{protocol_name}'...")
        success, msg = self.ti_controller.initialize_protocol(protocol_name)
        self.log(msg)

        if success:
            self.log("Fetching system status...")
            status_ok, info = self.ti_controller.get_status()
            if status_ok:
                self.log("Status received. Displaying system info.")
                self._build_system_info_display(info)
            else:
                self.log(f"Error fetching system status: {info}")
            
            self.log("\nSetup complete. Proceed to 'Set Signal Amplitudes'.")
            self.connect_button.setText("Initialized Successfully")
            # Keep button disabled on success
        else:
            self.log("Protocol initialization failed. See logs for details.")
            self.connect_button.setEnabled(True)
            self.connect_button.setText("Retry Initialization")