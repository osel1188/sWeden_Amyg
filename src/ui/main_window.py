# ti_gui/main_window_modified.py

import logging
from functools import partial
from typing import Any

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QSpacerItem, QSizePolicy,
    QStackedWidget
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont

# Import controller and API classes for type hinting
from temporal_interference.api import TIAPI
from participant import ParticipantAssignerAPI

# --- Import Page Modules ---
from .page_participant_info import ParticipantInfoWidget
from .page_hardware_setup import HardwareSetupWidget
from .page_set_amplitudes import SetAmplitudesWidget
from .page_run_protocol import RunStimulationWidget

class ExperimentWindow(QMainWindow):
    """
    Main application window. Acts as a container for the
    navigation pane and the QStackedWidget that holds the modules.
    """
    def __init__(self, ti_api: TIAPI, participant_api: ParticipantAssignerAPI):
        super().__init__()
        self.ti_api = ti_api
        self.participant_api = participant_api
        
        # --- Page/Module Widgets ---
        # Pass the participant API to the participant page
        self.page_participant = ParticipantInfoWidget(self.participant_api)
        
        # --- MODIFIED: Pass controller and participant API to Hardware Setup page ---
        self.page_hardware_setup = HardwareSetupWidget(
            self.ti_api, 
            self.participant_api
        )
        
        # Pass ti_api to SetAmplitudesWidget
        self.page_amplitudes = SetAmplitudesWidget(self.ti_api)
        
        # Pass the TI controller to the run page
        self.page_run = RunStimulationWidget(self.ti_api)
        
        self.nav_buttons = [] # To manage styling

        self.init_ui()
        self.connect_signals()
        self.apply_stylesheet()
        
        # Set initial page
        self._change_page(0)
        
        self.hide_button.setChecked(True)

        logging.info("ExperimentWindow container initialized.")

        # --- MODIFIED: Show maximized and activate (non-permanent) ---
        # The Qt.WindowStaysOnTopHint flag was removed.
        # self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint) # REMOVED
        self.showMaximized()
        self.raise_()
        self.activateWindow()
        # --- END MODIFIED ---

    def init_ui(self):
        """Initialize the main UI layout and widgets."""
        self.setWindowTitle("Temporal Interference")
        self.setGeometry(100, 100, 1200, 700) # Initial geometry is still good practice

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 1. Navigation Pane (Left) ---
        nav_pane = self._create_nav_pane()
        main_layout.addWidget(nav_pane, 1)

        # --- 2. Main Content Pane (Right) ---
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.page_participant)    # index 0
        self.stacked_widget.addWidget(self.page_hardware_setup) # index 1
        self.stacked_widget.addWidget(self.page_amplitudes)     # index 2
        self.stacked_widget.addWidget(self.page_run)            # index 3
        
        main_layout.addWidget(self.stacked_widget, 4)

    def _create_nav_pane(self) -> QFrame:
        """Creates the static light blue navigation pane."""
        nav_frame = QFrame()
        nav_frame.setObjectName("NavPane")
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(20, 25, 20, 20)
        nav_layout.setSpacing(15)

        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)

        title_label = QLabel("TILA Experiment: TI controller")
        title_label.setFont(title_font)
        title_label.setObjectName("NavTitle")
        nav_layout.addWidget(title_label)
        
        nav_layout.addSpacing(20)

        self.hide_button = QPushButton("Hide Mode")
        self.hide_button.setObjectName("HideModeButton")
        self.hide_button.setCheckable(True)
        self.hide_button.setCursor(Qt.CursorShape.PointingHandCursor)
        nav_layout.addWidget(self.hide_button)
        
        nav_layout.addSpacing(25)

        nav_font = QFont()
        nav_font.setPointSize(11)

        # --- MODIFIED: Added nav_2, renamed 2->3, 3->4 ---
        self.nav_1 = QPushButton("PARTICIPANT INFO")
        self.nav_2 = QPushButton("HARDWARE SETUP")
        self.nav_3 = QPushButton("SET SIGNAL AMPLITUDES")
        self.nav_4 = QPushButton("RUN PROTOCOL")
        
        self.nav_buttons = [self.nav_1, self.nav_2, self.nav_3, self.nav_4]
        # --- END MODIFICATION ---

        for btn in self.nav_buttons:
            btn.setFont(nav_font)
            btn.setObjectName("NavItem")
            btn.setFlat(True)
            btn.setStyleSheet("text-align: left; padding-left: 5px;")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            nav_layout.addWidget(btn)

        nav_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        return nav_frame

    def connect_signals(self):
        """Connect all button clicks to their handler methods."""
        # --- MODIFIED: Updated indices ---
        self.nav_1.clicked.connect(partial(self._change_page, 0))
        self.nav_2.clicked.connect(partial(self._change_page, 1))
        self.nav_3.clicked.connect(partial(self._change_page, 2))
        self.nav_4.clicked.connect(partial(self._change_page, 3))
        # --- END MODIFICATION ---
        
        self.hide_button.toggled.connect(self.on_hide_toggled)

    @Slot(int)
    def _change_page(self, index: int):
        """
        Slot to change the visible page in the QStackedWidget and
        update the navigation button styling.
        """
        # --- MODIFIED: Start/Stop timers for both pages ---
        # Stop/Start Hardware Page Timer (Index 1)
        if index == 1: 
            self.page_hardware_setup.start_updates()
        else:
            self.page_hardware_setup.stop_updates()
        
        # Stop/Start Amplitude Page Timer (Index 2)
        if index == 2: 
            self.page_amplitudes.start_updates()
        else:
            self.page_amplitudes.stop_updates()
        # --- END MODIFICATION ---

        self.stacked_widget.setCurrentIndex(index)
        
        for i, btn in enumerate(self.nav_buttons):
            btn.setObjectName("NavItemSelected" if i == index else "NavItem")
            self.style().unpolish(btn)
            self.style().polish(btn)
            
    @Slot(bool)
    def on_hide_toggled(self, checked: bool):
        """
        Called when the 'Hide Mode' button is toggled.
        Signals the participant page to update visibility.
        'checked' is True if the button is pressed down (Green state).
        """
        is_visible = not checked
        self.page_participant.toggle_condition_visibility(is_visible)
        
        # --- NEW ---
        # Propagate the "hide" state (checked=True) to the hardware page
        self.page_hardware_setup.set_hide_mode(checked)
        # --- END NEW ---

    def apply_stylesheet(self):
        """Apply CSS styles to match the image."""
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #FFFFFF;
                color: #333333;
                font-family: "Segoe UI", "Calibri", "Arial";
            }
            #NavPane {
                background-color: #E6F3F8;
            }
            #NavTitle {
                color: #005A83;
            }
            QPushButton#NavItem {
                color: #333333;
                border: none;
                border-left: 3px solid transparent;
            }
            QPushButton#NavItem:hover {
                color: #0078D4;
            }
            QPushButton#NavItemSelected {
                color: #0078D4;
                font-weight: bold;
                border: none;
                border-left: 3px solid #0078D4;
            }
            #MainPane {
                background-color: #F9F9F9;
                border-left: 1px solid #E0E0E0;
            }
            #MonitorBox {
                background-color: #444444;
                border-radius: 5px;
            }
            #MonitorTitle, #PlotTitle, #PlotValue {
                color: #FFFFFF;
                font-size: 10pt;
            }
            #MonitorTitle {
                font-weight: bold;
                font-size: 11pt;
            }
            #PlotValue {
                font-family: "Consolas", "Courier New";
                font-size: 11pt;
            }
            QPushButton {
                font-size: 10pt;
                font-weight: bold;
                border: 1px solid #ADADAD;
                border-radius: 3px;
                padding: 5px;
                background-color: #F0F0F0;
            }
            QPushButton:hover {
                background-color: #E0E0E0;
                border-color: #0078D4;
            }
            QPushButton:pressed {
                background-color: #D0D0D0;
            }
            #StartButton {
                background-color: #64B42D;
                color: white;
                border-color: #4A8C1F;
                font-size: 12pt;
            }
            #StartButton:hover { background-color: #7BC943; }
            #StartButton:pressed { background-color: #5A9E24; }
            
            #StopButton {
                background-color: #D93025;
                color: white;
                border-color: #B0271E;
                font-size: 12pt;
            }
            #StopButton:hover { background-color: #E84C3D; }
            #StopButton:pressed { background-color: #C22A1E; }
            
            QPushButton#HideModeButton {
                background-color: #D93025; /* Red (unchecked/False) */
                color: white;
                border-color: #B0271E;
            }
            QPushButton#HideModeButton:hover {
                background-color: #E84C3D;
            }
            QPushButton#HideModeButton:pressed {
                background-color: #C22A1E;
            }
            QPushButton#HideModeButton:checked {
                background-color: #64B42D; /* Green (checked/True) */
                color: white;
                border-color: #4A8C1F;
            }
            QPushButton#HideModeButton:checked:hover {
                background-color: #7BC943;
            }
            QPushButton#HideModeButton:checked:pressed {
                background-color: #5A9E24;
            }
            
            QDoubleSpinBox {
                font-size: 11pt;
                padding: 5px;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
            }
            #StatusLabel {
                font-size: 10pt;
                color: #555555;
            }
            QTextEdit {
                font-family: "Consolas", "Courier New";
                font-size: 10pt;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                background-color: #FDFDFD;
            }
            /* --- NEW --- */
            QScrollArea {
                border: 1px solid #CCCCCC;
                border-radius: 3px;
            }
            #InfoFrame {
                background-color: #FDFDFD;
            }
            /* --- END NEW --- */
        """)

    def closeEvent(self, event):
        """
        Intercept the window close event to shut down hardware.
        """
        logging.info("Close event triggered. Shutting down controller.")
        
        self.page_run.update_timer.stop()
        self.page_amplitudes.stop_updates()
        
        # --- NEW: Stop hardware page timer ---
        self.page_hardware_setup.stop_updates()
        # --- END NEW ---
        
        try:
            # Use the stored ti_api
            success, message = self.ti_api.shutdown()
            logging.info(f"Shutdown status: {success}. Message: {message}")
        except Exception as e:
            logging.error(f"Exception during shutdown: {e}")
            
        event.accept()