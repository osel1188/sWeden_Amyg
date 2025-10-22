import pandas as pd
from pathlib import Path
from typing import Union

class RepositoryError(Exception):
    """Errors related to Excel data reading or writing."""
    pass

# --- Concern 2: Data Repository (Excel) ---

class ConditionRepository:
    """
    Manages reading from and writing to the participant condition/assignment Excel file.
    """
    def __init__(self, excel_file_path: Union[str, Path]):
        self.excel_file_path = excel_file_path
        # MODIFIED: Updated required columns
        self.required_cols = [
            "ID", "Priority Order", "randomization_number", "sex", "condition",
            "Task1", "Task2", "Task3", "Task4", "Task5", "Task6",
            "EM version", "Stroop version"
        ]

    def load_data(self) -> pd.DataFrame:
        """
        Loads the participant data from the Excel file.
        
        :raises RepositoryError: If file not found, read error, or columns missing.
        :return: A pandas DataFrame with participant data.
        """
        try:
            df = pd.read_excel(self.excel_file_path)
        except FileNotFoundError:
            raise RepositoryError(f"Excel file not found at: {self.excel_file_path}")
        except Exception as e:
            raise RepositoryError(f"Error reading Excel file: {e}")
            
        # Validate columns
        missing_cols = [col for col in self.required_cols if col not in df.columns]
        if missing_cols:
            raise RepositoryError(f"Missing required columns in Excel: {', '.join(missing_cols)}")
            
        # Ensure 'sex' column is string type for comparison
        df['sex'] = df['sex'].astype(str)
        return df

    def find_by_id(self, df: pd.DataFrame, participant_id: str) -> pd.DataFrame:
        """
        Finds all rows matching a given participant ID (case-insensitive).
        
        :param df: The DataFrame to search.
        :param participant_id: The ID to find.
        :return: A DataFrame containing all matching rows (empty if none).
        """
        participant_id_clean = participant_id.strip().lower()
        if participant_id_clean == 'nan':
            return df[df['ID'].isna()]
            
        df_id_as_str = df['ID'].astype(str).str.strip().str.lower()
        existing_rows = df[df_id_as_str == participant_id_clean]
        return existing_rows

    def save_data(self, df: pd.DataFrame):
        """
        Saves the DataFrame back to the Excel file.
        
        :param df: The DataFrame to save.
        :raises RepositoryError: If permission is denied or write fails.
        """
        try:
            df.to_excel(self.excel_file_path, index=False)
        except PermissionError:
            raise RepositoryError(f"Permission denied. Cannot write to {self.excel_file_path}.")
        except Exception as e:
            raise RepositoryError(f"Error writing to Excel file: {e}")