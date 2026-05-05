import os
import yaml
import logging
import pandas as pd
import glob
import json
import csv
import time
from typing import List, Dict
import numpy as np

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
        # ============================================
        # 1. Handling malformed CSV structure with on_bad_lines='skip'.
        # ============================================
        # quoting=csv.QUOTE_NONE prevents unclosed quotes at EOF from causing a ParserError.
        self._csv_iterator = pd.read_csv(
            csv_path,
            iterator=True,
            on_bad_lines='skip',
            quoting=csv.QUOTE_NONE
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
        Cleans the data before it enters the system using STRICT TYPE CHECKING.
        It does not attempt to convert or coerce malformed data; 
        if a value has the wrong type, the row is dropped.
        """
        initial_len = len(batch)
        logger.debug(f"Sanitizing raw batch of {initial_len} records...")
        
        # ============================================
        # 1. Schema Check (Mandatory columns)
        # ============================================
        # Based on your test, 'priority' is also considered a mandatory column.
        required_columns = ['timestamp', 'sensor_id', 'value', 'priority']
        
        # If even one column is missing, we drop the ENTIRE batch
        for col in required_columns:
            if col not in batch.columns:
                logger.debug(f"Batch rejected: missing mandatory column '{col}'.")
                return pd.DataFrame(columns=required_columns)
                
        clean_batch = batch.copy()
        
        # Immediately remove null values (NaN, pd.NA, None)
        clean_batch = clean_batch.dropna(subset=required_columns)

        # ==============================================
        # 2. Strict Type Checking (No conversion)
        # ==============================================
        
        # 1. Base type checks for strings
        is_valid_ts = clean_batch['timestamp'].apply(lambda x: isinstance(x, str))
        is_valid_id = clean_batch['sensor_id'].apply(lambda x: isinstance(x, str))
        is_valid_prio = clean_batch['priority'].apply(lambda x: isinstance(x, str))
        
        # 2. Specific check for NUMERIC format
        # pd.to_numeric with errors='coerce' returns NaN for things like 'SENSOR_BROKEN'.
        # .notna() turns this into a True/False mask. 
        # We are JUST testing the type here; we are not mutating the actual column yet!
        is_valid_val = pd.to_numeric(clean_batch['value'], errors='coerce').notna()
        
        # 3. Specific check for the timestamp FORMAT
        is_valid_date_format = pd.to_datetime(clean_batch['timestamp'], errors='coerce').notna()

        # Keep ONLY the rows that passed ALL checks
        clean_batch = clean_batch[is_valid_ts & is_valid_id & is_valid_prio & is_valid_val & is_valid_date_format]

        # ==============================================
        # 3. Final Type Assignment (Fix for test matching)
        # ==============================================
        # Now that all dirty data has been removed, we can safely set the proper 
        # column types for the surviving data to avoid 'object' dtype mismatches in Pandas.
        clean_batch['value'] = clean_batch['value'].astype(float)
        clean_batch['timestamp'] = clean_batch['timestamp'].astype(str)
        clean_batch['sensor_id'] = clean_batch['sensor_id'].astype(str)
        clean_batch['priority'] = clean_batch['priority'].astype(str)

        # ==============================================
        # 4. Final Logging
        # ==============================================
        dropped = initial_len - len(clean_batch)
        if dropped > 0:
            logger.debug(f"Dropped {dropped} records due to strict type corruption or malformed data.")

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
