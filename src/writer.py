import os
import pandas as pd
from interfaces import IOutputWriter

class CSVOutputWriter(IOutputWriter):
    """
    Concrete implementation of the Output Writer.
    Handles the custom text formatting for both nominal telemetry and alarms,
    appending them to their respective files.
    """

    def __init__(self, output_path: str):
        """
        Initializes the writer and ensures the output directory exists.
        
        Args:
            output_path (str): The directory where the output files will be saved.
        """
        self.output_path = output_path
        
        # Ensure the directory exists
        os.makedirs(self.output_path, exist_ok=True)
        
        # Define the specific file paths
        self.valid_file_path = os.path.join(self.output_path, "valid_data.csv")
        self.alarms_file_path = os.path.join(self.output_path, "alarms.log")

    def write_valid_batch(self, valid_telemetry: pd.DataFrame) -> None:
        """
        Formats and appends nominal telemetry to valid_data.csv.
        
        Expected Format:
        TIMESTAMP;NOMINAL;[SENSOR_1]:[VALUE_1]|[SENSOR_2]:[VALUE_2]|...
        """
        if valid_telemetry.empty:
            return

        # 1. Identify sensor columns (everything except the TIMESTAMP)
        # Assuming the DataFrame has a 'TIMESTAMP' column.
        sensor_cols = [col for col in valid_telemetry.columns if col.upper() != 'TIMESTAMP']
        
        if not sensor_cols:
            return # Nothing to write if there are no sensors

        # 2. Vectorized construction of the payload: "[SENSOR_1]:[VALUE_1]|[SENSOR_2]:[VALUE_2]"
        # We build this column by column to avoid slow iterrows() loops
        sensor_parts = []
        for col in sensor_cols:
            # Create a Series of strings like "TEMP-01:25.5" for this specific column
            formatted_col = f"{col}:" + valid_telemetry[col].astype(str)
            sensor_parts.append(formatted_col)

        # Join the sensor strings together with the pipe '|' separator
        sensor_payload = sensor_parts[0]
        for part in sensor_parts[1:]:
            sensor_payload = sensor_payload.str.cat(part, sep='|')

        # 3. Prepend the TIMESTAMP and NOMINAL tags
        timestamp_col = valid_telemetry['TIMESTAMP'] if 'TIMESTAMP' in valid_telemetry.columns else valid_telemetry.iloc[:, 0]
        final_output_series = timestamp_col.astype(str) + ";NOMINAL;" + sensor_payload

        # 4. Append to the file
        with open(self.valid_file_path, 'a') as f:
            # Join all rows with a newline character and write
            f.write('\n'.join(final_output_series) + '\n')

    def write_alarms_batch(self, alarm_telemetry: pd.DataFrame) -> None:
        """
        Formats and appends anomalies to alarms.log.
        
        Expected Format:
        TIMESTAMP;RULE_ID;PRIORITY;VIOLATED_SENSOR(S);CURRENT_VALUE(S)
        """
        if alarm_telemetry.empty:
            return

        # Ensure the columns are in the exact order requested by the format.
        # This assumes the IRulesEngine returns a DataFrame with these specific column names.
        expected_columns = [
            'TIMESTAMP', 
            'RULE_ID', 
            'PRIORITY', 
            'VIOLATED_SENSORS', 
            'CURRENT_VALUES'
        ]
        
        # Filter and reorder the DataFrame to match the log format
        try:
            formatted_alarms = alarm_telemetry[expected_columns]
        except KeyError as e:
            print(f"[ERROR] Writer could not find expected alarm columns. Missing: {e}")
            return

        # Because the format is a standard semicolon-separated structure, 
        # we can leverage Pandas' native to_csv for maximum efficiency.
        formatted_alarms.to_csv(
            self.alarms_file_path, 
            mode='a', 
            sep=';', 
            header=False, # We don't write headers to a continuous log
            index=False   # No row numbers
        )