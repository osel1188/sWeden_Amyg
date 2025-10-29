# ti_gui/page_participant_info.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QSpacerItem, QSizePolicy, QFormLayout,
    QGroupBox, QComboBox, QLineEdit, QPushButton, QTextEdit, QMessageBox
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Slot
import pandas as pd
from typing import Optional

# Import the controller and API error types
from participant import ParticipantAssignerAPI, AssignmentError, RepositoryError 

class ParticipantInfoWidget(QWidget):
    """
    Interactive widget for participant validation, lookup, and assignment.
    """
    def __init__(self, participant_api: ParticipantAssignerAPI, parent=None):
        super().__init__(parent)
        
        # Store controller and API instance
        self.api = participant_api
        
        # State for validated data
        self.participant_data: pd.Series = None
        self.participant_folder: str = None
        
        # --- NEW: State for hiding condition ---
        self.hide_condition_mode: bool = False
        # --- End New ---

        self.init_ui()
        self.connect_signals()
        self.populate_available_participants()
        self.setObjectName("MainPane") # Use same style as main pane

    def init_ui(self):
        """Initialize the widget's UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        
        title_font = QFont()
        title_font.setPointSize(14)
        title_label = QLabel("1. Participant Information")
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # --- 1. Entry Form Group ---
        self.entry_group = QGroupBox("Participant Selection")
        form_layout = QFormLayout(self.entry_group)
        form_layout.setSpacing(10)

        self.available_combo = QComboBox()
        self.available_combo.setToolTip(
            "Select a participant from the pre-defined list (not yet participated)."
        )
        form_layout.addRow("Available (Not Participated):", self.available_combo)

        self.id_input = QLineEdit()
        self.id_input.setToolTip(
            "Enter ID manually for lookup or to assign a new (off-list) participant."
        )
        form_layout.addRow("Participant ID:", self.id_input)

        self.sex_combo = QComboBox()
        self.sex_combo.addItems(["Male", "Female"])
        self.sex_combo.setToolTip("Select sex. Required *only* for new assignments.")
        form_layout.addRow("Sex (for new assignment):", self.sex_combo)
        
        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(60)
        self.notes_input.setPlaceholderText("Optional notes...")
        form_layout.addRow("Notes:", self.notes_input)

        layout.addWidget(self.entry_group)
        
        self.validate_button = QPushButton("Validate and Save Participant")
        self.validate_button.setObjectName("StartButton") # Use green style
        layout.addWidget(self.validate_button)
        
        # --- 2. Validated Info Group (Initially Hidden) ---
        self.info_group = QGroupBox("Validated Participant Details")
        info_layout = QFormLayout(self.info_group)
        
        self.info_id_label = QLabel("N/A")
        self.info_sex_label = QLabel("N/A")
        self.info_rand_num_label = QLabel("N/A")
        
        # Store row label for condition to allow hiding
        self.condition_row_label = QLabel("Condition:")
        self.info_condition_label = QLabel("N/A")
        
        self.info_task1_label = QLabel("N/A")
        self.info_task2_label = QLabel("N/A")
        self.info_task3_label = QLabel("N/A")
        self.info_task4_label = QLabel("N/A")
        self.info_task5_label = QLabel("N/A")
        self.info_task6_label = QLabel("N/A")
        self.info_em_label = QLabel("N/A")
        self.info_stroop_label = QLabel("N/A")
        self.info_folder_label = QLabel("N/A")
        
        info_layout.addRow("ID:", self.info_id_label)
        info_layout.addRow("Sex:", self.info_sex_label)
        info_layout.addRow("Randomization #:", self.info_rand_num_label)
        
        # Add condition row using the stored labels
        info_layout.addRow(self.condition_row_label, self.info_condition_label)
        
        info_layout.addRow("Task1:", self.info_task1_label)
        info_layout.addRow("Task2:", self.info_task2_label)
        info_layout.addRow("Task3:", self.info_task3_label)
        info_layout.addRow("Task4:", self.info_task4_label)
        info_layout.addRow("Task5:", self.info_task5_label)
        info_layout.addRow("Task6:", self.info_task6_label)
        info_layout.addRow("EM Version:", self.info_em_label)
        info_layout.addRow("Stroop Version:", self.info_stroop_label)
        
        info_layout.addRow("Data Folder:", self.info_folder_label)
        
        self.info_group.setVisible(False)
        layout.addWidget(self.info_group)

        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

    def connect_signals(self):
        """Connect UI signals to their slots."""
        self.available_combo.currentTextChanged.connect(self.on_combo_select)
        self.validate_button.clicked.connect(self.on_validate)
        # --- MODIFICATION: Connect Enter key in ID input to validate ---
        self.id_input.returnPressed.connect(self.on_validate)
        # --- END MODIFICATION ---

    def populate_available_participants(self):
        """Fetches and populates the dropdown with non-participated IDs."""
        try:
            df = self.api.get_not_participated_list()
            
            self.available_combo.blockSignals(True) # Prevent signal emission
            self.available_combo.clear()
            self.available_combo.addItem("--- Enter New ID / Lookup ---", None)
            
            for row in df.itertuples():
                # Store the full row (as a NamedTuple) in the item's UserData
                self.available_combo.addItem(f"{row.ID} ({row.sex})", row)
                
            self.available_combo.blockSignals(False)
            self.on_combo_select(self.available_combo.currentText())

        except Exception as e:
            QMessageBox.critical(
                self, 
                "Error Loading Participants",
                f"Could not load available participants list: {e}"
            )
            self.entry_group.setEnabled(False) # Disable on critical error

    @Slot(str)
    def on_combo_select(self, text: str):
        """
        Slot triggered when the QComboBox selection changes.
        Auto-fills the ID and Sex fields.
        """
        user_data = self.available_combo.currentData()
        
        if user_data is not None:
            # A participant row was selected
            self.id_input.setText(user_data.ID)
            self.sex_combo.setCurrentText(user_data.sex)
            self.id_input.setReadOnly(True)
            self.sex_combo.setEnabled(False)
        else:
            # "--- Enter New ID ---" was selected
            self.id_input.clear()
            self.id_input.setReadOnly(False)
            self.sex_combo.setEnabled(True)

    @Slot()
    def on_validate(self):
        """
        Slot triggered by the 'Validate' button or Enter key.
        Calls the API to process the participant.
        """
        participant_id = self.id_input.text().strip()
        selected_sex = self.sex_combo.currentText()
        
        if not participant_id:
            QMessageBox.warning(self, "Input Error", "Participant ID cannot be empty.")
            return

        try:
            # This is the main API call
            result = self.api.process_participant(participant_id, selected_sex)
            
            status = result['status']
            data = result['data']     # This is a pd.Series
            folder = result['folder'] # This is a str
            
            if status == 'new_assignment':
                # --- MODIFIED: Conditionally show condition in pop-up ---
                message = f"New participant '{participant_id}' assigned successfully."
                if not self.hide_condition_mode:
                    message += f"\nCondition: {data.get('condition', 'N/A')}"
                
                QMessageBox.information(
                    self, 
                    "Success", 
                    message
                )
                # --- End Modified Pop-up ---
                self.display_participant_info(data, folder)
                self.set_fields_locked(True) # Lock form after success

            elif status == 'existing' or status == 'duplicate_id':
                QMessageBox.information(
                    self, 
                    "Existing Participant", 
                    f"Found existing data for participant '{participant_id}'."
                )
                self.display_participant_info(data, folder)
                self.set_fields_locked(True) # Lock form after lookup

            elif status == 'no_rows_available':
                QMessageBox.critical(
                    self, 
                    "Assignment Error", 
                    f"No available assignment rows found for sex: '{selected_sex}'."
                )

        except (AssignmentError, RepositoryError) as e:
            QMessageBox.critical(self, "API Error", f"A processing error occurred: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Unexpected Error", f"An unexpected error occurred: {e}")

    def display_participant_info(self, data: pd.Series, folder: str):
        """Updates the 'Validated Participant Details' group box."""
        self.participant_data = data
        self.participant_folder = str(folder)
        
        # Convert to string to handle potential NaN/None values gracefully
        self.info_id_label.setText(str(data.get('ID', 'N/A')))
        self.info_sex_label.setText(str(data.get('sex', 'N/A')))
        self.info_rand_num_label.setText(str(data.get('randomization_number', 'N/A')))
        self.info_condition_label.setText(str(data.get('condition', 'N/A')))
        self.info_task1_label.setText(str(data.get('Task1', 'N/A')))
        self.info_task2_label.setText(str(data.get('Task2', 'N/A')))
        self.info_task3_label.setText(str(data.get('Task3', 'N/A')))
        self.info_task4_label.setText(str(data.get('Task4', 'N/A')))
        self.info_task5_label.setText(str(data.get('Task5', 'N/A')))
        self.info_task6_label.setText(str(data.get('Task6', 'N/A')))
        self.info_em_label.setText(str(data.get('EM version', 'N/A')))
        self.info_stroop_label.setText(str(data.get('Stroop version', 'N/A')))
        self.info_folder_label.setText(self.participant_folder)
        
        self.info_group.setVisible(True)

    def set_fields_locked(self, locked: bool):
        """Disables or enables the entry form."""
        self.entry_group.setEnabled(not locked)
        self.validate_button.setEnabled(not locked)

    def get_participant_data(self) -> tuple[Optional[pd.Series], Optional[str]]:
        """
        Public method for other modules (like the main window or run page)
        to retrieve the validated participant's data and folder.
        """
        return self.participant_data, self.participant_folder
        
    # --- MODIFIED: Public Slot for Hiding Condition ---
    @Slot(bool)
    def toggle_condition_visibility(self, visible: bool):
        """
        Public slot to show or hide the condition row.
        Called by the main window.
        Also updates the internal state for pop-ups.
        """
        # Store the state for use in on_validate pop-ups
        self.hide_condition_mode = not visible
        
        # Update the UI labels
        self.condition_row_label.setVisible(visible)
        self.info_condition_label.setVisible(visible)
    # --- End Modified Slot ---