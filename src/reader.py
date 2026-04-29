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
        
        for col in mandatory_fields:
            if col not in clean_batch.columns:
                clean_batch[col] = pd.NA
        
        clean_batch = clean_batch.dropna(subset=mandatory_fields)
        schema_drops = initial_len - len(clean_batch)
        if schema_drops > 0:
            logger.debug(f"Dropped {schema_drops} records due to missing mandatory schema fields.")

        # ==============================================
        # 2. Solving type errors (invalid types error)
        # ==============================================
        len_before_type_check = len(clean_batch)
        clean_batch['value'] = pd.to_numeric(clean_batch['value'], errors='coerce')
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



class StreamTelemetryReader(ITelemetryReader):
    """
    Implements the Strategy Pattern to read live telemetry from a digital twin
    REST API endpoint (Maho/astralog_collector) instead of a static CSV file.
    """
    
    def __init__(self, endpoint_url: str, sensors_yaml_path: str, time_window_ms: int = 1000):
        self.endpoint_url = endpoint_url
        self.time_window_ms = time_window_ms
        self.is_active = True
        
        self.sensors_config = self._load_yaml(sensors_yaml_path)
        logger.info(f"StreamTelemetryReader initialized. Target API: {self.endpoint_url} | Window: {self.time_window_ms}ms")

    def _load_yaml(self, path: str) -> dict:
        if not path:
            path = "config/sensors.yaml"
        try:
            with open(path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            logger.critical(f"Fatal Error: YAML configuration file not found at {path}")
            raise FileNotFoundError(f"Error: YAML file not found at {path}")

    def extract_batch(self, batch_size: int) -> pd.DataFrame:
        """
        Fetches telemetry packets from the network stream.
        We pass 'time_window_ms' to the API to gather the batch.
        """
        if not self.is_active:
            return pd.DataFrame()

        try:
            logger.debug(f"Polling Digital Twin API for the last {self.time_window_ms}ms of telemetry...")
            
            response = requests.get(f"{self.endpoint_url}?window_ms={self.time_window_ms}", timeout=5)
            response.raise_for_status() 
            
            raw_data = response.json()
            
            if not raw_data:
                logger.info("Telemetry stream returned empty payload. Assuming end of stream or simulation paused.")
                self.is_active = False
                return pd.DataFrame()

            df = pd.DataFrame(raw_data)
            initial_len = len(df)
            logger.debug(f"Fetched {initial_len} raw packets from stream.")
            
            mandatory_fields = ['timestamp', 'sensor_id', 'value', 'priority']
            for col in mandatory_fields:
                if col not in df.columns:
                    df[col] = pd.NA
                    
            df = df.dropna(subset=mandatory_fields)
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = df.dropna(subset=['value'])
            
            dropped = initial_len - len(df)
            if dropped > 0:
                logger.debug(f"Dropped {dropped} network packets due to schema/type corruption.")
            
            logger.debug(f"Successfully processed {len(df)} packets from stream.")
            return df

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout waiting for Digital Twin at {self.endpoint_url}. Retrying next cycle...")
            return pd.DataFrame()
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Failed to connect to Digital Twin. Is the collector running? Error: {e}")
            self.is_active = False
            return pd.DataFrame()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network stream error: {e}")
            self.is_active = False
            return pd.DataFrame()
