import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any, Union

from .assignment_service import AssignmentService, AssignmentError
from .config_loader import ConfigLoader
from .participant_data_logger import ParticipantDataLogger
from .condition_repository import ConditionRepository
from .participant_repository import ParticipantsListRepository


# --- Concern 5: The Public API Facade ---

class ParticipantAssignerAPI:
    """
    Orchestrates the participant assignment and lookup process.
    This is the primary entry point for any client (GUI, web, etc.).
    """
    
    def __init__(self, config_file_path: Union[str, Path]):
        """
        Initializes all required services.
        
        :param config_file_path: Path to the main configuration file.
        :raises ConfigError: If configuration loading fails.
        :raises RepositoryError: If data files cannot be loaded.
        """
        self.config_loader = ConfigLoader(config_file_path)
        self.config = self.config_loader.load_config()
        
        self.condition_path = self.config_loader.get_condition_path()
        self.default_save_dir = self.config_loader.get_save_dir()
        # MODIFIED: Get participants list path
        self.participants_list_path = self.config_loader.get_participants_list_path()
        
        # MODIFIED: Use ConditionRepository
        self.condition_repository = ConditionRepository(self.condition_path)
        # MODIFIED: Initialize ParticipantsListRepository
        self.participants_list_repo = ParticipantsListRepository(self.participants_list_path)
        self.service = AssignmentService()
        self.logger = ParticipantDataLogger()

        # NEW: State for Mod 1 (Last Result)
        self.last_result: Optional[Dict[str, Any]] = None
        
        # NEW: State for Mod 2 (Participant Lists)
        # MODIFIED: Load participants list once
        self.df_participants_list = self.participants_list_repo.load_participants_list()
        self.participated_list: pd.DataFrame = pd.DataFrame()
        self.not_participated_list: pd.DataFrame = pd.DataFrame()
        
        # Perform initial synchronization
        self.refresh_participation_status()


    def refresh_participation_status(self):
        """
        Reloads the condition file and updates the participated/not_participated lists
        by comparing against the main participants list.
        :raises RepositoryError: If the condition file cannot be read.
        """
        # Load the *current* state of the condition file
        df_conditions = self.condition_repository.load_data()
        
        # Get unique, clean IDs of those who have participated
        participated_ids = df_conditions['ID'].dropna().astype(str).str.strip().str.lower()
        participated_ids_unique = set(participated_ids)
        
        # MODIFIED: Get normalized IDs from the main participants list
        participants_list_ids_normalized = self.df_participants_list['ID'].astype(str).str.strip().str.lower()
        
        # Find masks
        participated_mask = participants_list_ids_normalized.isin(participated_ids_unique)
        
        self.participated_list = self.df_participants_list[participated_mask].copy()
        self.not_participated_list = self.df_participants_list[~participated_mask].copy()

    # --- NEW: Public Getters ---
    
    def get_last_result(self) -> Optional[Dict[str, Any]]:
        """Returns the result of the last process_participant call."""
        return self.last_result

    def get_participated_list(self) -> pd.DataFrame:
        """Returns a DataFrame of participants list subjects who have participated."""
        return self.participated_list
        
    def get_not_participated_list(self) -> pd.DataFrame:
        """Returns a DataFrame of participants list subjects who have NOT participated."""
        return self.not_participated_list

    # --- NEW METHOD ---
    def get_last_participant_condition(self) -> Optional[Any]:
        """
        Returns the 'condition' value for the last processed participant.
        
        :return: The value of the 'condition' column (e.g., 'A', 'B') or None
                 if no participant has been processed or if the last
                 operation resulted in no data (e.g., 'no_rows_available').
        """
        if self.last_result and self.last_result.get("data") is not None:
            # 'data' is the pd.Series of the participant's row
            participant_data: pd.Series = self.last_result["data"]
            # 'condition' is guaranteed by ConditionRepository required_cols
            return participant_data.get("condition")
        
        return None

    # --- Main API Method ---

    def process_participant(
        self, 
        participant_id: str, 
        selected_sex: str,
        base_save_folder_override: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """
        Main API method to process a participant assignment or lookup.
        
        :param participant_id: The ID entered by the user.
        :param selected_sex: The sex selected by the user ("Male" or "Female").
        :param base_save_folder_override: (Optional) A different save directory
                                            path if not using the config default.
        
        :raises AssignmentError: For invalid inputs.
        :raises RepositoryError: For Excel I/O issues.
        :raises FileSystemError: For log file I/O issues.
        
        :return: A dictionary result object with:
                 'status': (str) 'existing', 'duplicate_id', 'new_assignment', 'no_rows_available'
                 'data': (pd.Series) The participant's data row (if found/assigned).
                 'folder': (str or None) The path to the participant's session folder.
        """
        
        # --- 1. Input Validation ---
        if not participant_id or not participant_id.strip():
            raise AssignmentError("Participant ID cannot be empty.")
        if selected_sex not in ["Male", "Female"]:
            raise AssignmentError("Sex must be 'Male' or 'Female'.")
            
        active_save_dir = Path(base_save_folder_override) if base_save_folder_override else self.default_save_dir
        if not active_save_dir:
            raise AssignmentError("Base save folder path cannot be empty.")
        
        participant_id = participant_id.strip()

        # --- 2. Load Data ---
        df = self.condition_repository.load_data()
        
        # Note: We don't refresh participation status here, as this load
        # might be for a lookup. We only refresh *after* a new assignment.

        # --- 3. Scenario 1: Existing ID Found ---
        existing_rows = self.condition_repository.find_by_id(df, participant_id)
        
        if not existing_rows.empty:
            status = "existing"
            if len(existing_rows) > 1:
                status = "duplicate_id" # Client can choose to warn
            
            existing_data = existing_rows.iloc[0].copy()
            
            # Find associated folder
            found_folders = self.logger.find_participant_folders(active_save_dir, participant_id)
            participant_folder = None
            if len(found_folders) == 1:
                participant_folder = str(found_folders[0])
            
            # MODIFIED: Store result before returning
            result = {
                "status": status,
                "data": existing_data,
                "folder": participant_folder
            }
            self.last_result = result
            return result

        # --- 4. Scenario 2: New Assignment ---
        assignment_result = self.service.find_available_row(df, selected_sex)
        
        if not assignment_result:
            # --- Scenario 3: No Rows for Assignment ---
            # MODIFIED: Store result before returning
            result = {
                "status": "no_rows_available",
                "data": None,
                "folder": None
            }
            self.last_result = result
            return result
            
        # --- 5. Continue New Assignment ---
        assigned_index, assigned_data = assignment_result
        
        # Update DataFrame in memory
        df.loc[assigned_index, "ID"] = participant_id
        assigned_data["ID"] = participant_id # Update the copy we will return
        
        # Save updated DataFrame back to Excel
        self.condition_repository.save_data(df)
        
        # Create the participant log file
        new_folder_path = self.logger.create_participant_session_log(
            base_save_dir=active_save_dir,
            participant_id=participant_id,
            selected_sex=selected_sex,
            assigned_row_data=assigned_data,
            assigned_row_index=assigned_index
        )
        
        # NEW: Refresh the lists *after* a successful save
        self.refresh_participation_status()
        
        # MODIFIED: Store result before returning
        result = {
            "status": "new_assignment",
            "data": assigned_data,
            "folder": new_folder_path
        }
        self.last_result = result
        return result