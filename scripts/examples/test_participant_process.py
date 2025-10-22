import pandas as pd
from pathlib import Path
from typing import Union

from participant import (
    ParticipantAssignerAPI, 
    ConfigError, 
    AssignmentError,
    RepositoryError
)

# --- Example API Usage (replaces the original __main__) ---

def create_dummy_config_if_not_exists(
    config_filename="api_config.txt", 
    condition_filename="condition_for_stimulators_API.xlsx",
    participants_list_list_filename="participants_list_list_API.xlsx"
):
    """Helper to create dummy config and excel for API testing."""
    cfg_dir = Path("cfg")
    cfg_dir.mkdir(exist_ok=True)
    
    config_path = cfg_dir / config_filename
    condition_path = cfg_dir / condition_filename
    participants_list_list_path = cfg_dir / participants_list_list_filename
    save_dir = Path.home() / "Documents" / "TILA_DATA_API_TEST"
    save_dir.mkdir(exist_ok=True)
    
    # Create config file
    if not config_path.exists():
        print(f"Creating dummy config: {config_path}")
        with open(config_path, 'w') as f:
            f.write(f"condition_file_path = {condition_path}\n")
            f.write(f"save_dir_base_path = {save_dir}\n")
            f.write(f"participants_list_file_path = {participants_list_list_path}\n")
            
    # Create dummy condition excel
    if not condition_path.exists():
        print(f"Creating dummy Excel: {condition_path}")
        
        # MODIFIED: Updated dictionary to match ConditionRepository.required_cols
        data = {
            'ID': ['P001', None, 'EXISTING_ID_02', None, None, None],
            'randomization_number': [101, 102, 103, 104, 105, 106],
            'sex': ['Female', 'Male', 'Female', 'Male', 'Female', 'Male'],
            'Priority Order': [1, 1, 1, 2, 2, 2],
            'condition': ['A', 'B', 'A', 'B', 'A', 'B'],
            'Task1': ['T1_v1', 'T1_v2', 'T1_v1', 'T1_v2', 'T1_v1', 'T1_v2'],
            'Task2': ['T2_vA', 'T2_vB', 'T2_vA', 'T2_vB', 'T2_vA', 'T2_vB'],
            'Task3': ['T3_v1', 'T3_v2', 'T3_v1', 'T3_v2', 'T3_v1', 'T3_v2'],
            'Task4': ['T4_vA', 'T4_vB', 'T4_vA', 'T4_vB', 'T4_vA', 'T4_vB'],
            'Task5': ['T5_v1', 'T5_v2', 'T5_v1', 'T5_v2', 'T5_v1', 'T5_v2'],
            'Task6': ['T6_vA', 'T6_vB', 'T6_vA', 'T6_vB', 'T6_vA', 'T6_vB'],
            'EM version': [1, 2, 13, 1, 1, 2],
            'Stroop version': [1, 1, 14, 2, 2, 2],
        }
        df_test = pd.DataFrame(data)
        df_test['ID'] = df_test['ID'].astype(object)
        try:
            df_test.to_excel(condition_path, index=False)
        except Exception as e:
            print(f"Could not create dummy excel: {e}")

    # NEW: Create dummy master list excel
    if not participants_list_list_path.exists():
        print(f"Creating dummy master list: {participants_list_list_path}")
        participants_list_data = {
            'ID': ['P001', 'P100', 'P101', 'P999_NOT_PARTICIPATING', 'EXISTING_ID_02'],
            'age': [25, 30, 35, 40, 45],
            'sex': ['Female', 'Male', 'Female', 'Male', 'Female']
        }
        df_master = pd.DataFrame(participants_list_data)
        try:
            df_master.to_excel(participants_list_list_path, index=False)
        except Exception as e:
            print(f"Could not create dummy master list: {e}")
            
    return config_path

if __name__ == "__main__":
    
    # 1. Setup dummy files for testing
    CONFIG_FILE = create_dummy_config_if_not_exists()
    
    print(f"--- Initializing API with config: {CONFIG_FILE} ---")
    
    try:
        # 2. Initialize the API
        # This will load both Excel files and run the initial sync
        api = ParticipantAssignerAPI(CONFIG_FILE)
        print(f"Default save directory set to: {api.default_save_dir}")
        print(f"Condition file set to: {api.condition_path}")
        print(f"Participant list file set to: {api.participants_list_path}")

        # --- Test Case 0: Check initial participant lists ---
        print("\n--- TEST CASE 0: Initial Participant Lists ---")
        print("Initial 'Not Participated' List:")
        print(api.get_not_participated_list())
        print("\nInitial 'Participated' List:")
        print(api.get_participated_list())
        
        # --- Test Case 1: Assign a new 'Male' participant ---
        print("\n--- TEST CASE 1: New 'Male' Participant 'P100' ---")
        try:
            # P100 is in the master list, but not in the condition file
            result_new = api.process_participant(
                participant_id="P100", 
                selected_sex="Male"
            )
            print(f"API Result Status: {result_new['status']}")
            print(f"Assigned Folder: {result_new['folder']}")
            
            # Test Mod 1: Check get_last_result()
            print(f"get_last_result() status: {api.get_last_result()['status']}")

        except Exception as e:
            print(f"API Error: {e}")

        # --- Test Case 2: Check updated participant lists ---
        print("\n--- TEST CASE 2: Updated Participant Lists (Post-P100) ---")
        # P100 should now be in the 'participated' list
        print("Updated 'Not Participated' List:")
        print(api.get_not_participated_list())
        print("\nUpdated 'Participated' List:")
        print(api.get_participated_list())

        # --- Test Case 3: Look up the participant just created ---
        print("\n--- TEST CASE 3: Lookup Existing Participant 'P100' ---")
        try:
            result_existing = api.process_participant(
                participant_id="P100", 
                selected_sex="Male"
            )
            print(f"API Result Status: {result_existing['status']}")
            print(f"Found Folder: {result_existing['folder']}")
            
            # Check last_result was updated
            print(f"get_last_result() status: {api.get_last_result()['status']}")
            
        except Exception as e:
            print(f"API Error: {e}")

    except (ConfigError, RepositoryError) as e:
        print(f"Failed to initialize API: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    
    print("\n--- API script execution complete. ---")