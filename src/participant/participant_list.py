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
        Loads the main participants list from the 'T-participants' sheet
        in the Excel file.
        
        Filters the list based on two rules:
        1. Removes rows where the last character of 'ID' (sex) is not 'M' or 'F' 
           (case-insensitive).
        2. Removes rows where the ID prefix (e.g., "T123") starts with 'T' 
           but the following number is less than 50.

        Parses the single 'ID' column into separate 'ID' (prefix) and 'sex' columns.
        
        :raises ParticipantsListError: If file not found, read error, 
                                     'T-participants' sheet missing, 
                                     or 'ID' column missing.
        :return: A filtered pandas DataFrame with 'ID' and 'sex' columns.
        """
        try:
            # Load the specific sheet 'T-participants'
            df = pd.read_excel(
                self.excel_file_path, 
                sheet_name="T-participants", 
                engine='openpyxl'
            )
        except FileNotFoundError:
            raise ParticipantsListError(f"Participants list file not found at: {self.excel_file_path}")
        except ValueError as e:
            # Catch errors if 'T-participants' sheet does not exist
            if "Worksheet 'T-participants' does not exist" in str(e):
                 raise ParticipantsListError(f"Sheet 'T-participants' not found in file: {self.excel_file_path}")
            raise ParticipantsListError(f"Error reading participants list file: {e}")
        except Exception as e:
            raise ParticipantsListError(f"Error reading participants list file: {e}")
            
        # Validate required 'ID' column
        missing_cols = [col for col in self.required_cols if col not in df.columns]
        if missing_cols:
            raise ParticipantsListError(f"Missing required 'ID' column in 'T-participants' sheet.")
            
        # Ensure ID column is string type and store in a temporary column
        df['original_ID'] = df['ID'].astype(str)

        # Extract sex (last character) and normalize to uppercase
        df['sex'] = df['original_ID'].str[-1].str.upper()
        
        # Extract the actual ID prefix (everything except the last character)
        df['ID'] = df['original_ID'].str[:-1]
        
        # --- Rule 1: Filter by Sex ---
        # Keep only rows where sex is 'M' or 'F'
        # .copy() prevents SettingWithCopyWarning on subsequent filtering
        df = df[df['sex'].isin(['M', 'F'])].copy()
        
        # --- Rule 2: Filter by ID Number (for 'T' prefixed IDs) ---
        
        # Identify rows where ID starts with 'T'
        starts_with_T = df['ID'].str.startswith('T')
        
        # Extract numeric part for 'T' rows, converting non-numeric to NaN
        # This applies the operation to the entire 'ID' column;
        # non-T rows will likely result in NaN, which is handled by the logic.
        id_numeric_part = pd.to_numeric(df['ID'].str[1:], errors='coerce')
        
        # Condition 1: ID number is valid (not NaN) AND >= 50
        is_valid_T_number = (id_numeric_part.notna()) & (id_numeric_part >= 50)
        
        # Condition 2: ID does not start with 'T' (keep these)
        does_not_start_with_T = ~starts_with_T
        
        # Combine conditions: Keep if (does_not_start_with_T) OR (is_valid_T_number)
        keep_condition = does_not_start_with_T | is_valid_T_number
        
        df = df[keep_condition]
        
        # Return only the required 'ID' (prefix) and 'sex' columns
        return df[['ID', 'sex']]