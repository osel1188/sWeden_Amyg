import pandas as pd
from pathlib import Path
from typing import Union

class RepositoryError(Exception):
    """Errors related to Excel data reading or writing."""
    pass

# --- Repository for the full Participants List ---

class ParticipantsListRepository:
    """
    Manages reading the main participants list Excel file.
    """
    def __init__(self, excel_file_path: Union[str, Path]):
        self.excel_file_path = excel_file_path
        # Required columns for the participants list
        self.required_cols = ["ID", "age", "sex"]

    def load_participants_list(self) -> pd.DataFrame:
        """
        Loads the main participants list from the Excel file.
        
        :raises RepositoryError: If file not found, read error, or columns missing.
        :return: A pandas DataFrame with participants list data.
        """
        try:
            df = pd.read_excel(self.excel_file_path)
        except FileNotFoundError:
            raise RepositoryError(f"Participants list file not found at: {self.excel_file_path}")
        except Exception as e:
            raise RepositoryError(f"Error reading participants list file: {e}")
            
        # Validate columns
        missing_cols = [col for col in self.required_cols if col not in df.columns]
        if missing_cols:
            raise RepositoryError(f"Missing required columns in participants list: {', '.join(missing_cols)}")
            
        # Ensure ID and sex columns are string type for comparison
        df['ID'] = df['ID'].astype(str)
        df['sex'] = df['sex'].astype(str)
        return df