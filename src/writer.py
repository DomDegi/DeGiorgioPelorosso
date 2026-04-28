import os
import pandas as pd
from src.interfaces import IOutputWriter

class CSVOutputWriter(IOutputWriter):
    """
    Concrete implementation of the Output Writer.
    Handles the custom text formatting for both nominal telemetry and alarms.
    """

    def __init__(self, output_path: str, clean_start: bool = True):
        """
        Initializes the writer and ensures the output directory exists.
        
        Args:
            output_path (str): The directory where the output files will be saved.
            clean_start (bool): If True, deletes existing output files to guarantee 
                                idempotency across different HPC job runs.
        """
        self.output_path = output_path
        os.makedirs(self.output_path, exist_ok=True)
        
        self.valid_file_path = os.path.join(self.output_path, "valid_data.csv")
        self.alarms_file_path = os.path.join(self.output_path, "alarms.log")

        # Guarantee idempotency: remove old files from previous crashed/old runs
        if clean_start:
            if os.path.exists(self.valid_file_path):
                os.remove(self.valid_file_path)
            if os.path.exists(self.alarms_file_path):
                os.remove(self.alarms_file_path)

    def write_valid_batch(self, valid_telemetry: pd.DataFrame) -> None:
        """
        Formats and appends nominal telemetry to valid_data.csv.
        Expects a Long format DataFrame: ['timestamp', 'sensor_id', 'value']
        
        Target Format: TIMESTAMP;NOMINAL;[SENSOR_1]:[VALUE_1]|[SENSOR_2]:[VALUE_2]|...
        """
        if valid_telemetry.empty:
            return

        # Work on a copy to avoid SettingWithCopyWarning
        valid_df = valid_telemetry.copy()

        # ---------------------------------------------------------
        # DETERMINISM
        # Sort rigorously by timestamp and sensor name alphabetically.
        # This guarantees the concatenated string output is exactly the 
        # same in every run, satisfying the "verifiability" requirement.
        # ---------------------------------------------------------
        valid_df = valid_df.sort_values(by=['timestamp', 'sensor_id'])

        # 1. Create the base string for each row: "TEMP-01:25.5"
        valid_df['sensor_string'] = valid_df['sensor_id'].astype(str) + ":" + valid_df['value'].astype(str)

        # 2. Fast C-backend pivot: Group by timestamp and join strings with '|'
        grouped = valid_df.groupby('timestamp', as_index=False)['sensor_string'].agg('|'.join)

        # 3. Insert the required 'NOMINAL' status column
        grouped.insert(1, 'status', 'NOMINAL')

        # 4. Append directly to disk. 
        # The DataFrame is now exactly in the shape: [timestamp, status, sensor_string]
        grouped.to_csv(
            self.valid_file_path,
            mode='a',
            sep=';',
            index=False,
            header=False
        )

    def write_alarms_batch(self, alarm_telemetry: pd.DataFrame) -> None:
        """
        Formats and appends anomalies to alarms.log.
        Expects a DataFrame with specific lowercase columns.
        
        Target Format: TIMESTAMP;RULE_ID;PRIORITY;VIOLATED_SENSOR(S);CURRENT_VALUE(S)
        """
        if alarm_telemetry.empty:
            return

        # Expecting the exact column names produced by the RulesEngine
        expected_columns = ['timestamp', 'rule_id', 'priority', 'sensor_id', 'value']
        
        try:
            formatted_alarms = alarm_telemetry[expected_columns]
        except KeyError as e:
            print(f"[ERROR] OutputWriter missing columns. Check RulesEngine output. Missing: {e}")
            return

        # Append directly as a standard CSV with semicolon separator
        formatted_alarms.to_csv(
            self.alarms_file_path, 
            mode='a', 
            sep=';', 
            header=False, 
            index=False
        )
