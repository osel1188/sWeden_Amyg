import pandas as pd
import random
from typing import Optional, Tuple


class AssignmentError(Exception):
    """Errors related to the business logic of assignment."""
    pass


# --- Concern 3: Assignment Logic (Business Logic) ---

class AssignmentService:
    """
    Contains the core business logic for finding an available assignment row.
    """
    def find_available_row(self, df: pd.DataFrame, selected_sex: str) -> Optional[Tuple[int, pd.Series]]:
        """
        Finds an available row for a new participant based on sex and priority.
        
        :param df: The DataFrame of all participants.
        :param selected_sex: The sex to filter by ("Male" or "Female").
        :return: A tuple of (original_index, row_data_series) or None if no row.
        """
        df_sex_filtered = df[df['sex'].astype(str).str.lower() == selected_sex.lower()]

        if df_sex_filtered.empty:
            return None # No rows for this sex at all

        df_sorted_by_priority = df_sex_filtered.sort_values(by="Priority Order")
        
        for priority_level in sorted(df_sorted_by_priority["Priority Order"].unique()):
            priority_group_df = df_sorted_by_priority[
                df_sorted_by_priority["Priority Order"] == priority_level
            ]
            
            # Find rows in this priority group with blank IDs
            blank_id_mask = (priority_group_df["ID"].isna()) | (priority_group_df["ID"].astype(str).str.strip() == '')
            potential_rows: pd.DataFrame = priority_group_df[blank_id_mask]
            
            if not potential_rows.empty:
                # Randomly select one available row from this priority group
                selected_original_index = random.choice(potential_rows.index)
                
                # Return the index and data from the *original* DataFrame
                assigned_row_data = df.loc[selected_original_index].copy()
                return selected_original_index, assigned_row_data
        
        return None # No available rows found in any priority group
