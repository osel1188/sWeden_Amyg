import pandas as pd
import os
from pathlib import Path
import datetime
from typing import List


class FileSystemError(Exception):
    """Errors related to reading or writing participant log files."""
    pass


# --- Concern 4: File System Logging ---

class ParticipantDataLogger:
    """
    Manages creation and retrieval of participant-specific log files/folders.
    """
    def create_participant_session_log(
        self,
        base_save_dir: Path,
        participant_id: str,
        selected_sex: str,
        assigned_row_data: pd.Series,
        assigned_row_index: int
    ) -> str:
        """
        Creates a new participant folder and summary .txt file.
        
        :param base_save_dir: The root directory to save in.
        :param participant_id: The participant's ID.
        :param selected_sex: The sex selected in the GUI.
        :param assigned_row_data: The pandas Series of the assigned row.
        :param assigned_row_index: The 0-based index from the Excel file.
        :raises FileSystemError: If folder/file creation fails.
        :return: The string path to the newly created subfolder.
        """
        try:
            now = datetime.datetime.now()
            timestamp = now.strftime("%Y-%m-%d")
            # Sanitize ID for folder name
            safe_participant_id = "".join(c if c.isalnum() or c in ('_','-') else '_' for c in participant_id)
            output_folder_name = f"{timestamp}_{safe_participant_id}"
            output_subfolder_path = base_save_dir / output_folder_name
            
            os.makedirs(output_subfolder_path, exist_ok=True)
            
            output_filename = f"{output_folder_name}.txt"
            filepath = output_subfolder_path / output_filename

            # MODIFIED: Updated log output to match new columns
            with open(filepath, "w") as f:
                f.write(f"Participant ID: {participant_id}\n")
                f.write(f"Selected Sex: {selected_sex}\n")
                f.write(f'Randomization Number: {assigned_row_data.get("randomization_number", "N/A")}\n')
                f.write(f"Assigned Row Index (in Excel, 0-based): {assigned_row_index}\n")
                f.write(f"Condition: {assigned_row_data.get('condition', 'N/A')}\n")
                f.write(f"Task1: {assigned_row_data.get('Task1', 'N/A')}\n")
                f.write(f"Task2: {assigned_row_data.get('Task2', 'N/A')}\n")
                f.write(f"Task3: {assigned_row_data.get('Task3', 'N/A')}\n")
                f.write(f"Task4: {assigned_row_data.get('Task4', 'N/A')}\n")
                f.write(f"Task5: {assigned_row_data.get('Task5', 'N/A')}\n")
                f.write(f"Task6: {assigned_row_data.get('Task6', 'N/A')}\n")
                f.write(f"EM version: {assigned_row_data.get('EM version', 'N/A')}\n")
                f.write(f"Stroop version: {assigned_row_data.get('Stroop version', 'N/A')}\n")
                
            return str(output_subfolder_path)
            
        except Exception as e:
            raise FileSystemError(f"Error saving participant data file: {e}")

    def find_participant_folders(self, base_save_dir: Path, participant_id: str) -> List[Path]:
        """
        Finds all folders within the base directory containing the participant ID.
        
        :param base_save_dir: The root directory to search in.
        :param participant_id: The participant ID string to search for.
        :return: A list of Path objects for all matching folders.
        """
        if not base_save_dir.is_dir():
            return []
            
        participant_id_clean = participant_id.strip()
        try:
            folders_found = [
                p for p in base_save_dir.iterdir() 
                if p.is_dir() and participant_id_clean in p.name
            ]
            return folders_found
        except Exception as e:
            raise FileSystemError(f"Error searching for participant folders: {e}")