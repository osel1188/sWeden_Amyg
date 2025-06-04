import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import os
from pathlib import Path
import datetime
import random

class ParticipantAssigner:
    def __init__(self, master, on_data_processed_callback=None):
        self.master = master
        master.title("Participant Assigner")
        master.geometry("480x240") # Increased height for the new dropdown

        self.excel_file_path = os.path.join(os.getcwd(), "metadata", "Excel_for_stimulators.xlsx")
        self.default_save_dir = Path.home() / "Documents" / "TILA_DATA"

        self.on_data_processed_callback = on_data_processed_callback
        self.last_processed_row_data = None

        input_frame = ttk.Frame(master, padding="10")
        input_frame.pack(expand=True, fill="both")

        # Base Save Folder
        tk.Label(input_frame, text="Base Save Folder:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.folder_path_var = tk.StringVar(value=str(self.default_save_dir))
        self.folder_path_entry = ttk.Entry(input_frame, textvariable=self.folder_path_var, width=40)
        self.folder_path_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.browse_button = ttk.Button(input_frame, text="Browse", command=self.browse_folder)
        self.browse_button.grid(row=0, column=2, padx=5, pady=5)

        # Participant ID
        tk.Label(input_frame, text="Participant ID:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.participant_id_var = tk.StringVar()
        self.participant_id_entry = ttk.Entry(input_frame, textvariable=self.participant_id_var, width=40)
        self.participant_id_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # Sex Selection Dropdown
        tk.Label(input_frame, text="Sex:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.sex_var = tk.StringVar()
        self.sex_options = ["Select Sex", "Male", "Female"]
        self.sex_combobox = ttk.Combobox(input_frame, textvariable=self.sex_var, values=self.sex_options, state="readonly", width=38) # Matched width roughly
        self.sex_combobox.set(self.sex_options[0]) # Default to "Select Sex"
        self.sex_combobox.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        self.sex_var.trace_add('write', self._check_inputs) # Add trace to enable/disable button

        input_frame.grid_columnconfigure(1, weight=1)

        self.start_button = ttk.Button(master, text="Start Assignment / Load ID", command=self.process_assignment, style="Accent.TButton", state="disabled") # Initially disabled
        style = ttk.Style()
        style.configure("Accent.TButton", font=('Arial', 12, 'bold'), padding=5)
        self.start_button.pack(padx=10, pady=15, ipady=5, fill="x")

        # Initial check, in case participant ID is pre-filled (though not typical here)
        self._check_inputs()

    def _check_inputs(self, *args):
        """Enable start button only if a sex is selected."""
        sex_selected = self.sex_var.get() != self.sex_options[0]
        if sex_selected:
            self.start_button.config(state="normal")
        else:
            self.start_button.config(state="disabled")

    def browse_folder(self):
        directory = filedialog.askdirectory(initialdir=self.folder_path_var.get())
        if directory:
            self.folder_path_var.set(directory)

    def process_assignment(self):
        self.last_processed_row_data = None
        base_save_folder = self.folder_path_var.get()
        participant_id = self.participant_id_var.get().strip()
        selected_sex = self.sex_var.get()

        # Initial input validations
        if not participant_id:
            messagebox.showerror("Input Error", "Participant ID cannot be empty.")
            if self.on_data_processed_callback: self.on_data_processed_callback(None)
            return
        if not base_save_folder:
            messagebox.showerror("Input Error", "Base save folder path cannot be empty.")
            if self.on_data_processed_callback: self.on_data_processed_callback(None)
            return
        if selected_sex == self.sex_options[0]: # "Select Sex"
            messagebox.showerror("Input Error", "Please select the participant's sex.")
            if self.on_data_processed_callback: self.on_data_processed_callback(None)
            return

        df = None
        try:
            df = pd.read_excel(self.excel_file_path)
        except FileNotFoundError:
            messagebox.showerror("File Error", f"Excel file not found at: {self.excel_file_path}\nPlease ensure the path is correct and the file exists.")
            if self.on_data_processed_callback: self.on_data_processed_callback(None)
            return
        except Exception as e:
            messagebox.showerror("Excel Read Error", f"Error reading Excel file: {e}")
            if self.on_data_processed_callback: self.on_data_processed_callback(None)
            return

        # Added 'sex' to required columns
        required_excel_cols = ["ID", "Priority Order", "FC_version", "TA_version", "EM_version", "Stroop_version", "sex"]
        missing_excel_cols = [col for col in required_excel_cols if col not in df.columns]
        if missing_excel_cols:
            messagebox.showerror("Excel Error", f"Missing required columns in Excel: {', '.join(missing_excel_cols)}")
            if self.on_data_processed_callback: self.on_data_processed_callback(None)
            return

        # Ensure 'sex' column exists and handle potential errors if it contains unexpected data types before .str accessor
        if 'sex' in df.columns:
            df['sex'] = df['sex'].astype(str) # Ensure 'sex' is string for comparison
        else: # This case should be caught by missing_excel_cols, but as a safeguard:
            messagebox.showerror("Excel Error", "Column 'sex' is missing in the Excel file.")
            if self.on_data_processed_callback: self.on_data_processed_callback(None)
            return


        df_id_as_str = df['ID'].astype(str).str.strip()
        participant_id_stripped_lower = participant_id.lower()
        existing_rows = df[df_id_as_str.str.lower() == participant_id_stripped_lower]
        if participant_id_stripped_lower == 'nan': # Handling 'nan' as a string if it's entered
            existing_rows = existing_rows[df['ID'].notna()]

        # --- Scenario 1: Existing ID Found ---
        if not existing_rows.empty:
            if len(existing_rows) > 1:
                messagebox.showwarning("Duplicate ID", f"Participant ID '{participant_id}' found multiple times. Loading the first instance.")
            
            existing_data_row = existing_rows.iloc[0].copy()
            # Check if required task version columns are present for the existing ID
            missing_version_cols_in_row = [col for col in ["FC_version", "TA_version", "EM_version", "Stroop_version"] if col not in existing_data_row or pd.isna(existing_data_row[col])]

            if missing_version_cols_in_row :
                messagebox.showerror("Data Error", f"Required version columns ({', '.join(missing_version_cols_in_row)}) are missing or empty for existing ID '{participant_id}'.")
                if self.on_data_processed_callback: self.on_data_processed_callback(None)
                return

            fc_version = existing_data_row["FC_version"]
            ta_version = existing_data_row["TA_version"]
            em_version = existing_data_row["EM_version"]
            stroop_version = existing_data_row["Stroop_version"]
            
            messagebox.showinfo("ID Found", f"Participant ID '{participant_id}' already exists. Displaying their information.")
            self.show_assigned_info(participant_id, fc_version, ta_version, em_version, stroop_version, is_existing=True)
            
            self.last_processed_row_data = existing_data_row
            if self.on_data_processed_callback:
                self.on_data_processed_callback(self.last_processed_row_data)
            
            self.master.destroy()
            return

        # --- Scenario 2: New Assignment ---
        # Filter DataFrame by selected sex BEFORE looking for an available row
        df_sex_filtered = df[df['sex'].astype(str).str.lower() == selected_sex.lower()]

        if df_sex_filtered.empty:
            messagebox.showinfo("No Rows for Sex", f"No rows available for assignment for the selected sex: {selected_sex}.")
            if self.on_data_processed_callback: self.on_data_processed_callback(None)
            self.master.destroy()
            return

        df_sorted_by_priority_and_sex = df_sex_filtered.sort_values(by="Priority Order")
        assigned_row_details = None
        for priority_level in sorted(df_sorted_by_priority_and_sex["Priority Order"].unique()):
            priority_group_df = df_sorted_by_priority_and_sex[df_sorted_by_priority_and_sex["Priority Order"] == priority_level]
            blank_id_mask = (priority_group_df["ID"].isna()) | (priority_group_df["ID"].astype(str).str.strip() == '')
            potential_rows_for_assignment = priority_group_df[blank_id_mask]
            if not potential_rows_for_assignment.empty:
                # Get the original index from the main DataFrame 'df'
                selected_row_original_index = random.choice(potential_rows_for_assignment.index)
                # Retrieve the full data series from the original 'df' using this index
                assigned_row_data_series = df.loc[selected_row_original_index].copy()
                assigned_row_details = (selected_row_original_index, assigned_row_data_series)
                break

        if not assigned_row_details: # --- Scenario 3: No Rows for Assignment (after sex and priority filtering) ---
            messagebox.showinfo("No Rows", f"No available rows for assignment for participant ID '{participant_id}' with sex '{selected_sex}'. All suitable rows might be taken or do not exist.")
            if self.on_data_processed_callback:
                self.on_data_processed_callback(None)
            self.master.destroy()
            return
            
        # --- Continue with New Assignment ---
        assigned_row_index, assigned_row_data = assigned_row_details # assigned_row_index is from the original df
        
        # Update ID in the original DataFrame 'df'
        df.loc[assigned_row_index, "ID"] = participant_id
        # Also update the copied series (though it's mainly for immediate use)
        assigned_row_data["ID"] = participant_id
        # We could also update 'sex' if we wanted to store the GUI selected sex, but typically it should match
        # df.loc[assigned_row_index, "Sex_Assigned_By_GUI"] = selected_sex # Optional: if you want to record this

        try:
            df.to_excel(self.excel_file_path, index=False)
        except PermissionError:
            messagebox.showerror("File Error", f"Permission denied for {self.excel_file_path}.")
            if self.on_data_processed_callback: self.on_data_processed_callback(None)
            return
        except Exception as e:
            messagebox.showerror("Excel Write Error", f"Error writing to Excel: {e}")
            if self.on_data_processed_callback: self.on_data_processed_callback(None)
            return

        fc_version = assigned_row_data["FC_version"]
        ta_version = assigned_row_data["TA_version"]
        em_version = assigned_row_data["EM_version"]
        stroop_version = assigned_row_data["Stroop_version"]

        self.show_assigned_info(participant_id, fc_version, ta_version, em_version, stroop_version, is_existing=False)

        try:
            now = datetime.datetime.now()
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            safe_participant_id = "".join(c if c.isalnum() or c in ('_','-') else '_' for c in participant_id)
            output_folder_name = f"{timestamp}_{safe_participant_id}"
            output_subfolder_path = os.path.join(base_save_folder, output_folder_name)
            os.makedirs(output_subfolder_path, exist_ok=True)
            output_filename = f"{output_folder_name}.txt"
            filepath = os.path.join(output_subfolder_path, output_filename)

            with open(filepath, "w") as f:
                f.write(f"Participant ID: {participant_id}\n")
                f.write(f"Selected Sex: {selected_sex}\n") # Added selected sex to output
                f.write(f"Assigned Row Index (in Excel, 0-based): {assigned_row_index}\n")
                f.write(f"FC_version: {fc_version}\n")
                f.write(f"TA_version: {ta_version}\n")
                f.write(f"EM_version: {em_version}\n")
                f.write(f"Stroop_version: {stroop_version}\n")
            
            self.participant_id_var.set("")
            self.sex_var.set(self.sex_options[0]) # Reset sex dropdown
            self.last_processed_row_data = assigned_row_data
            if self.on_data_processed_callback:
                self.on_data_processed_callback(self.last_processed_row_data)
        except Exception as e:
            messagebox.showerror("Save Error", f"Error saving participant data file: {e}")
            if self.on_data_processed_callback:
                self.on_data_processed_callback(assigned_row_data if 'assigned_row_data' in locals() else None)
            return
        
        self.master.destroy()


    def show_assigned_info(self, p_id, fc, ta, em, stroop, is_existing=False):
        info_window = tk.Toplevel(self.master)
        title_prefix = "Existing Data for" if is_existing else "Newly Assigned Conditions for"
        info_window.title(f"{title_prefix} {p_id}")
        info_window.geometry("420x250")
        info_window.transient(self.master)
        info_window.grab_set()
        info_window.resizable(False, False)

        main_frame = ttk.Frame(info_window, padding="15")
        main_frame.pack(expand=True, fill="both")

        status_text = "Displaying previously recorded data." if is_existing else "New conditions have been assigned and saved."
        ttk.Label(main_frame, text=status_text, font=('Arial', 9, 'italic')).grid(row=0, column=0, columnspan=2, pady=(0,10))

        ttk.Label(main_frame, text=f"Participant ID: {p_id}", font=('Arial', 12, 'bold')).grid(row=1, column=0, columnspan=2, pady=(0,10))
        
        labels_texts = ["FC_version:", "TA_version:", "EM_version:", "Stroop_version:"]
        values_texts = [str(fc), str(ta), str(em), str(stroop)]

        for i, (label_text, value_text) in enumerate(zip(labels_texts, values_texts)):
            ttk.Label(main_frame, text=label_text, font=('Arial', 10, 'bold')).grid(row=i+2, column=0, sticky="e", padx=5, pady=3)
            ttk.Label(main_frame, text=value_text, font=('Arial', 10)).grid(row=i+2, column=1, sticky="w", padx=5, pady=3)
        
        ttk.Button(main_frame, text="OK", command=info_window.destroy, style="Accent.TButton").grid(row=len(labels_texts)+2, column=0, columnspan=2, pady=(15,0))
        
        self.master.wait_window(info_window)


def create_dummy_excel_if_not_exists(excel_file_path_param="Excel_for_stimulators.xlsx"): # Renamed param to avoid conflict
    metadata_dir = Path("metadata")
    metadata_dir.mkdir(exist_ok=True) # Ensure metadata directory exists
    full_excel_path = metadata_dir / excel_file_path_param

    if not full_excel_path.exists():
        print(f"Creating dummy Excel: {full_excel_path} for testing purposes.")
        data = {
            'ID': ['P001', None, 'EXISTING_ID_02', None, None, None, 'P003', None, 'TestID_004', None, None, None, None, None, None],
            'randomization_number': [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115],
            'sex': ['female', 'male', 'female', 'male', 'female', 'male', 'female', 'male', 'female', 'male', 'female', 'male', 'female', 'male', 'female'], # Ensure enough diverse data
            'condition': ['active', 'control', 'active', 'control', 'active', 'control', 'active', 'active', 'control', 'active', 'control', 'active', 'control', 'active', 'control'],
            'FC_version': [1, 2, 11, 2, 1, 2, 1, 1, 22, 1, 2, 1, 2, 1, 2],
            'TA_version': [1, 1, 12, 2, 1, 1, 2, 2, 23, 2, 1, 1, 2, 1, 2],
            'FE': ['A', 'B', 'C', 'B', 'A', 'B', 'A', 'B', 'D', 'B', 'A', 'B', 'A', 'B', 'A'],
            'AI': ['X', 'Y', 'Z', 'Y', 'X', 'Y', 'X', 'Y', 'W', 'Y', 'X', 'Y', 'X', 'Y', 'X'],
            'EM_version': [1, 2, 13, 1, 1, 2, 2, 1, 24, 1, 2, 1, 2, 1, 2],
            'Stroop_version': [1, 1, 14, 2, 2, 2, 1, 2, 25, 2, 1, 1, 2, 1, 2],
            'Priority Order': [1, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3], # Adjusted priorities for more testing options
            'Randomization number GUI': [49,45,50,51,52,53,54, 55, 56, 57, 58, 59, 60, 61, 62],
            'pure random number': [0.7,0.6,0.7,0.8,0.9,0.1,0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.1]
        }
        df_test = pd.DataFrame(data)
        df_test['ID'] = df_test['ID'].astype(object) # Ensure ID column can hold NaNs properly
        # Explicitly set some IDs to None/NaN for testing new assignments
        none_indices = [1, 3, 5, 7, 9, 11, 13] # More None IDs for testing
        for idx in none_indices:
            if idx < len(df_test):
                 df_test.loc[idx, 'ID'] = None

        # Ensure some IDs are pre-filled for testing existing ID lookup
        df_test.loc[4, 'ID'] = 'Another_Filled_ID'
        df_test.loc[4, 'sex'] = 'male' # Assign sex to existing ID

        try:
            df_test.to_excel(full_excel_path, index=False)
            print(f"Dummy Excel '{full_excel_path}' created. IDs like 'P001', 'EXISTING_ID_02' can be used for testing.")
            print("Ensure 'sex' column contains 'male' or 'female' (case-insensitive).")
        except Exception as e:
            print(f"Could not create dummy excel: {e}")
    # else: # Optional: print if file already exists
    #     print(f"Dummy Excel '{full_excel_path}' already exists. Using existing file.")


if __name__ == "__main__":
    # Create dummy excel in the 'metadata' subdirectory relative to the script's location
    excel_filename = "Excel_for_stimulators.xlsx"
    create_dummy_excel_if_not_exists(excel_filename) # Will create in ./metadata/

    processed_data_holder = []

    def my_data_handler_callback(row_data_series):
        print("\n--- Callback: Data Received by Script ---")
        if row_data_series is not None:
            print("Type of received data:", type(row_data_series))
            print("Entire row data (Pandas Series):")
            print(row_data_series.to_string())
            processed_data_holder.append(row_data_series)
        else:
            print("No data was successfully processed in this operation, or an error occurred.")
        print("--- Callback: End of Data ---")

    root = tk.Tk()
    app = ParticipantAssigner(root, on_data_processed_callback=my_data_handler_callback)

    print("Starting Tkinter mainloop...")
    print("The GUI will perform one operation (assign/load) and then close itself.")
    
    try:
        root.mainloop()
    except tk.TclError as e:
        print(f"Tkinter mainloop exited, possibly due to window destruction: ({e})")
    
    print("\nTkinter mainloop has finished (GUI was closed by the app instance).")

    if processed_data_holder:
        print("\nData captured by callback during the GUI operation:")
        for i, data_item in enumerate(processed_data_holder):
            print(f"\n--- Item {i+1} ---")
            print(data_item.to_string())
    else:
        print("\nNo data was captured by the callback in the holder.")
    
    print("Script execution complete.")