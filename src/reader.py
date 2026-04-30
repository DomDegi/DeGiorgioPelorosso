import os
import yaml
import logging
import pandas as pd
import glob
import json
import csv
import time
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
        Cleans the data before it enters the system.
        Removes malformed rows, missing values, corrupted types, 
        and handles optional fields like priority.
        """
        initial_len = len(batch)
        logger.debug(f"Sanitizing raw batch of {initial_len} records...")
        
        clean_batch = batch.copy()
        
        # ============================================
        # 1. Solving schema errors (missing mandatory fields)
        # ============================================
        mandatory_fields = ['timestamp', 'sensor_id', 'value']
        
        for col in mandatory_fields:
            if col not in clean_batch.columns:
                clean_batch[col] = pd.NA 
                
        clean_batch = clean_batch.dropna(subset=mandatory_fields)

        # ==============================================
        # 2. Solving type/format errors (strict validation)
        # ==============================================
        # Check if value is strictly numeric
        clean_batch['value'] = pd.to_numeric(clean_batch['value'], errors='coerce')
        
        # Check if timestamp is a valid datetime string
        parsed_timestamps = pd.to_datetime(clean_batch['timestamp'], errors='coerce')
        
        # Drop rows where value became NaN OR timestamp became NaT
        clean_batch = clean_batch[clean_batch['value'].notna() & parsed_timestamps.notna()]

        # ==============================================
        # 3. Handling the Optional 'priority' Field
        # ==============================================
        valid_priorities = ['HIGH', 'MEDIUM', 'LOW']
        
        if 'priority' not in clean_batch.columns:
            clean_batch['priority'] = 'LOW'
        else:
            clean_batch['priority'] = clean_batch['priority'].astype(str).str.upper()
            clean_batch.loc[~clean_batch['priority'].isin(valid_priorities), 'priority'] = 'LOW'

        # ==============================================
        # 4. Final Logging
        # ==============================================
        dropped = initial_len - len(clean_batch)
        if dropped > 0:
            logger.debug(f"Dropped {dropped} records due to schema, type corruption, or malformed data.")

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


class StreamTelemetryReader(ITelemetryReader):
    """
    Reads live telemetry dumped by the standalone astralog_collector.py.
    Watches the output directory for new .txt files and processes them.
    """
    
    def __init__(self, directory_path: str = "output_collector", sensors_yaml_path: str = None):
        self.directory_path = directory_path
        self.sensors_config = self._load_yaml(sensors_yaml_path)
        
        os.makedirs(self.directory_path, exist_ok=True)
        logger.info(f"StreamTelemetryReader initialized. Watching directory: {self.directory_path}")

    def _load_yaml(self, path: str) -> dict:
        if not path:
            path = "config/sensors.yaml"
        try:
            with open(path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            logger.critical(f"Fatal Error: YAML configuration file not found at {path}")
            raise FileNotFoundError(f"Error: YAML file not found at {path}")

    def _sanitize_batch(self, batch: pd.DataFrame) -> pd.DataFrame:
        initial_len = len(batch)
        clean_batch = batch.copy()
        
        # 1. Schema check
        mandatory_fields = ['timestamp', 'sensor_id', 'value']
        for col in mandatory_fields:
            if col not in clean_batch.columns:
                clean_batch[col] = pd.NA
                
        clean_batch = clean_batch.dropna(subset=mandatory_fields)
        
        # 2. Type Check (Value & Timestamp)
        clean_batch['value'] = pd.to_numeric(clean_batch['value'], errors='coerce')
        parsed_timestamps = pd.to_datetime(clean_batch['timestamp'], errors='coerce')
        clean_batch = clean_batch[clean_batch['value'].notna() & parsed_timestamps.notna()]
        
        # 3. Priority check
        valid_priorities = ['HIGH', 'MEDIUM', 'LOW']
        if 'priority' not in clean_batch.columns:
            clean_batch['priority'] = 'LOW'
        else:
            clean_batch['priority'] = clean_batch['priority'].astype(str).str.upper()
            clean_batch.loc[~clean_batch['priority'].isin(valid_priorities), 'priority'] = 'LOW'
        
        dropped = initial_len - len(clean_batch)
        if dropped > 0:
            logger.debug(f"Dropped {dropped} network packets due to schema/type corruption.")
            
        return clean_batch

    def extract_batch(self, batch_size: int) -> pd.DataFrame:
        """
        Polls the directory for new files, parses the JSON, and deletes the files to prevent reprocessing.
        """
        files = sorted(glob.glob(os.path.join(self.directory_path, "*.txt")))
        
        if not files:
            time.sleep(1)
            return pd.DataFrame()

        all_data = []
        files_to_process = files[:5] 

        for file_path in files_to_process:
            try:
                with open(file_path, 'r') as f:
                    for line in f:
                        if not line.strip(): continue
                        try:
                            data = json.loads(line.strip())
                            all_data.append(data)
                        except json.JSONDecodeError:
                            pass 
                            
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")

        if not all_data:
            return pd.DataFrame()

        raw_chunk = pd.DataFrame(all_data)
        clean_batch = self._sanitize_batch(raw_chunk)
        
        return clean_batch.head(batch_size)