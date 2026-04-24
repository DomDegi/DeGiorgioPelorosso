import pandas as pd
import yaml
import os
from .interfaces import ITelemetryReader

class CSVTelemetryReader(ITelemetryReader):
    """
    Implementation of the ITelemetryReader interface that extracts and sanitizes 
    the data from CSV format as per project specifications. 
    """

    # Constructor (Fixed typo: __init__ instead of __init)
    def __init__(self, sensors_yaml_path: str = None, csv_path: str = None):
        self.sensors_config = self._load_yaml(sensors_yaml_path)
        
        # If csv_path is an empty string or None, default to:
        if not csv_path:
            csv_path = "data/telemetry_stream.csv"
            
        # Initialize the Pandas iterator. 
        # on_bad_lines='skip' should satisfy the "Malformed JSON/CSV" requirement.
        # Let's check with pytests later
        self._csv_iterator = pd.read_csv(csv_path,
                                         iterator=True,
                                         on_bad_lines='skip'
                                         )
    
    # method for loading the sensors.yaml (default dir: config/*.yaml)
    def _load_yaml(self, path: str) -> dict:
        """Private helper to load the sensors configuration."""
        # If path is an empty string or None, default to:
        if not path:
            path = "config/sensors.yaml"
            
        # The try block runs regardless of whether we used the default or input path)
        try:
            with open(path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Error: YAML file not found at {path}")
    
    def _sanitize_batch(self, batch: pd.DataFrame) -> pd.DataFrame:
        """
        Cleans the data before it enters the system.
        Removes malformed rows, missing values, or corrupted types.
        """
        # Creating a copy of the batch to avoid Pandas error
        clean_batch = batch.copy()
        
        # ============================================
        # 1. Solving schema errors (missing fields)
        # ============================================
        mandatory_fields = ['timestamp', 'sensor_id', 'value', 'priority']
        
        # If the file is missing a column we add it empty so to remove it later on without any errors
        for col in mandatory_fields:
            if col not in clean_batch.columns:
                clean_batch[col] = pd.NA
        
        # Deletes clean lines that have 'NaN' or null values in these columns
        clean_batch = clean_batch.dropna(subset=mandatory_fields)

        # ==============================================
        # 2. Solving type errors (invalid types error)
        # ==============================================
        # We force the value column to become numeric. If there is a string, it becomes NaN
        clean_batch['value'] = pd.to_numeric(clean_batch['value'], errors='coerce')
        
        # We must drop the rows that just became NaN
        clean_batch = clean_batch.dropna(subset=['value'])

        return clean_batch

    # (Fixed omission: Added the mandatory extract_batch method from the interface)
    def extract_batch(self, batch_size: int) -> pd.DataFrame:
        """
        Reads 'batch_size' rows from the CSV and discards malformed data.
        """
        try:
            raw_chunk = self._csv_iterator.get_chunk(batch_size)
            clean_batch = self._sanitize_batch(raw_chunk)
            return clean_batch
            
        except StopIteration:
            # Pandas throws this when the file is completely finished
            return pd.DataFrame()
