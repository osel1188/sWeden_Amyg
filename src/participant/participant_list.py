import pandas as pd
from pathlib import Path
from typing import Union

class ParticipantsListError(Exception):
    """Errors related to Excel data reading or writing."""
    pass

# --- Repository for the full Participants List ---

class ParticipantsList:
    """
    Manages reading the main participants list Excel file.
    Assumes the file has one column 'ID' where the last character
    indicates sex (e.g., "ID123F" or "ID456m").
    """
    def __init__(self, excel_file_path: Union[str, Path]):
        self.excel_file_path = excel_file_path
        # Required column for the participants list (new format)
        self.required_cols = ["ID"]

    def load_participants_list(self) -> pd.DataFrame:
        """
        Loads the main participants list from the Excel file.
        Parses the single 'ID' column into separate 'ID' and 'sex' columns.
        
        :raises ParticipantsListError: If file not found, read error, or 'ID' column missing.
        :return: A pandas DataFrame with 'ID' and 'sex' columns.
        """
        try:
            df = pd.read_excel(self.excel_file_path)
        except FileNotFoundError:
            raise ParticipantsListError(f"Participants list file not found at: {self.excel_file_path}")
        except Exception as e:
            raise ParticipantsListError(f"Error reading participants list file: {e}")
            
        # Validate required 'ID' column
        missing_cols = [col for col in self.required_cols if col not in df.columns]
        if missing_cols:
            raise ParticipantsListError(f"Missing required 'ID' column in participants list.")
            
        # Ensure ID column is string type for processing
        df['ID'] = df['ID'].astype(str)

        # Extract sex (last character) and normalize to uppercase
        df['sex'] = df['ID'].str[-1].str.upper()
        
        # Extract the actual ID (everything except the last character)
        df['ID'] = df['ID'].str[:-1]
        
        return df