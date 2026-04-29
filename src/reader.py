import os
import yaml
import logging
import pandas as pd
import requests
from typing import List, Dict

from src.interfaces import ITelemetryReader

logger = logging.getLogger(__name__)

class CSVTelemetryReader(ITelemetryReader):
    """
    Implementation of the ITelemetryReader interface that extracts and sanitizes 
    the data from CSV format as per project specifications. 
    """

    def __init__(self, sensors_yaml_path: str = None, csv_path: str = None):
        self.sensors_config = self._load_yaml(sensors_yaml_path)
        
        if not csv_path:
            csv_path = "data/telemetry_stream.csv"
            logger.debug(f"No CSV path provided. Defaulting to: {csv_path}")
            
        # Initialize the Pandas iterator. 
        # on_bad_lines='skip' satisfies the "Malformed JSON/CSV" requirement.
        self._csv_iterator = pd.read_csv(
            csv_path,
            iterator=True,
            on_bad_lines='skip'
        )
        logger.info(f"CSVTelemetryReader initialized successfully. Target file: {csv_path}")
    
    def _load_yaml(self, path: str) -> dict:
        """Private helper to load the sensors configuration."""
        if not path:
            path = "config/sensors.yaml"
            
        try:
            with open(path, 'r') as file:
                config = yaml.safe_load(file)
                logger.debug(f"Successfully loaded sensor configuration from {path}")
                return config
        except FileNotFoundError:
            logger.critical(f"Fatal Error: YAML configuration file not found at {path}")
            raise FileNotFoundError(f"Error: YAML file not found at {path}")
    
    def _sanitize_batch(self, batch: pd.DataFrame) -> pd.DataFrame:
        """
        Cleans the data before it enters the system.
        Removes malformed rows, missing values, or corrupted types.
        """
        initial_len = len(batch)
        logger.debug(f"Sanitizing raw batch of {initial_len} records...")
        
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
        schema_drops = initial_len - len(clean_batch)
        if schema_drops > 0:
            logger.debug(f"Dropped {schema_drops} records due to missing mandatory schema fields.")

        # ==============================================
        # 2. Solving type errors (invalid types error)
        # ==============================================
        # We force the value column to become numeric. If there is a string, it becomes NaN
        clean_batch['value'] = pd.to_numeric(clean_batch['value'], errors='coerce')
        
        # We must drop the rows that just became NaN
        clean_batch = clean_batch.dropna(subset=['value'])
        
        type_drops = len_before_type_check - len(clean_batch)
        if type_drops > 0:
            logger.debug(f"Dropped {type_drops} records due to invalid data types (non-numeric values).")

        logger.debug(f"Sanitization complete. {len(clean_batch)} valid records extracted.")
        return clean_batch

    def extract_batch(self, batch_size: int) -> pd.DataFrame:
        """
        Reads 'batch_size' rows from the CSV and discards malformed data.
        """
        try:
            logger.debug(f"Extracting next chunk of {batch_size} rows from CSV...")
            raw_chunk = self._csv_iterator.get_chunk(batch_size)
            clean_batch = self._sanitize_batch(raw_chunk)
            return clean_batch
            
        except StopIteration:
            logger.info("End of CSV telemetry stream reached. No more data to extract.")
            return pd.DataFrame()
        except pd.errors.ParserError as e:
            logger.warning(f"Found corruption near EOF or malformed line. Ignoring trash data. Details: {e}")
            return pd.DataFrame()
            return pd.DataFrame()
