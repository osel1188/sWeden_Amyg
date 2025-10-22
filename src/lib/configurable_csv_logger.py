import csv
import os
from datetime import datetime
import logging

# Configure basic logging if you want to see messages from this logger itself
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ConfigurableCsvLogger:
    """
    Logs data entries to a CSV file with a creation timestamp in its name,
    storing it in the specified log folder. The log structure (filename prefix
    and data columns) is configurable.
    """

    def __init__(self, log_folder_path: str, filename_prefix: str, data_header_columns: list[str]):
        """
        Initializes the ConfigurableCsvLogger.
        A new log file with a timestamp in its name will be created in log_folder_path.

        Args:
            log_folder_path (str): The path to the folder where the log file will be stored.
            filename_prefix (str): The prefix for the log filename (e.g., "device_comms", "event_log").
            data_header_columns (list[str]): A list of strings representing the header
                                             for the data columns. A 'Timestamp' column
                                             will automatically be prepended to this header.
                                             Example: ['Command', 'DeviceID', 'Response']
        """
        self.log_folder_path = log_folder_path
        self.filename_prefix = filename_prefix
        self.user_defined_header_columns = data_header_columns
        self.full_header = ['Timestamp'] + self.user_defined_header_columns

        # Ensure the log folder exists
        try:
            os.makedirs(self.log_folder_path, exist_ok=True)
        except OSError as e:
            logging.error(f"Error creating log directory {self.log_folder_path}: {e}")
            # Depending on requirements, you might want to re-raise or handle differently
            raise 

        # Generate filename with creation timestamp
        creation_timestamp_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        self.current_log_filename = f"{creation_timestamp_str}_{self.filename_prefix}.csv"
        self.log_file_path = os.path.join(self.log_folder_path, self.current_log_filename)

        try:
            with open(self.log_file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(self.full_header)
            logging.info(f"Log file created: {self.log_file_path} with header: {self.full_header}")
        except IOError as e:
            logging.error(f"Failed to create or write header to log file {self.log_file_path}: {e}")
            # Depending on requirements, you might want to re-raise or handle differently
            raise

    def _get_formatted_timestamp(self) -> str:
        """
        Generates a timestamp string for log entries in the format: year-month-date_HH-mm-ss-millisecond.
        """
        return datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')[:-3]

    def log_entry(self, *data_values: any):
        """
        Logs a data entry (a row) to the CSV file.

        Args:
            *data_values: A sequence of values to log. The number and order of these values
                          must correspond to the 'data_header_columns' provided during
                          initialization.
                          For example, if data_header_columns was ['Action', 'User', 'Details'],
                          you would call log_entry("Login", "admin", "Successful login from IP X").
        """
        if len(data_values) != len(self.user_defined_header_columns):
            error_msg = (
                f"Data logging error in {self.current_log_filename}: "
                f"Expected {len(self.user_defined_header_columns)} data values "
                f"(for columns: {self.user_defined_header_columns}), "
                f"but received {len(data_values)} (values: {data_values})."
            )
            logging.error(error_msg)
            # Optionally, raise an error to make the caller aware:
            # raise ValueError(error_msg)
            return

        timestamp = self._get_formatted_timestamp()
        log_row_data = [timestamp] + list(data_values)

        try:
            with open(self.log_file_path, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(log_row_data)
        except IOError as e:
            logging.error(f"Failed to write to log file {self.log_file_path}: {e}")
        except Exception as ex:
            logging.error(f"An unexpected error occurred during logging to {self.log_file_path}: {ex}")