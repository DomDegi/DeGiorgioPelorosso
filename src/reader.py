import polars as pl
import yaml
import logging
from src.interfaces import ITelemetryReader

logger = logging.getLogger(__name__)

class CSVTelemetryReader(ITelemetryReader):
    def __init__(self, sensors_yaml_path: str = None, csv_path: str = None):
        self.sensors_config = self._load_yaml(sensors_yaml_path)
        self.csv_path = csv_path or "data/telemetry_stream.csv"
        
        # 1. Define Strict Schema
        # We define types upfront so Polars can enforce them at the Rust level 
        # during the disk read, completely avoiding slow Python 'isinstance' checks.
        self.schema = {
            "timestamp": pl.String,
            "sensor_id": pl.String,
            "value": pl.Float64,
            "priority": pl.String
        }
        
        # 2. Initialize Batched Reader
        # ignore_errors=True silently skips rows with corrupted extra commas or missing columns.
        self._batched_reader = pl.read_csv_batched(
            self.csv_path,
            schema_overrides=self.schema,
            ignore_errors=True,
            null_values=["", "NA", "NaN", "null"]
        )
        logger.info(f"CSVTelemetryReader initialized. Target: {self.csv_path}")

    def _load_yaml(self, path: str) -> dict:
        path = path or "config/sensors.yaml"
        with open(path, 'r') as file:
            return yaml.safe_load(file)

    def extract_batch(self, batch_size: int) -> pl.DataFrame:
        # 1. Fetch the next chunk from disk
        batches = self._batched_reader.next_batches(batch_size)
        if not batches:
            return pl.DataFrame()
            
        raw_chunk = pl.concat(batches)
        
        # 2. Native Vectorized Sanitization
        # Drop rows where schema enforcement resulted in Nulls (e.g. text in Float col)
        clean_batch = raw_chunk.drop_nulls(subset=["timestamp", "sensor_id", "value", "priority"])
        
        # 3. Timestamp Format Verification
        # We attempt to parse the string to a DateTime. If it fails (e.g. 'T1'), 
        # it becomes Null, which we then filter out to guarantee strict formatting.
        clean_batch = clean_batch.with_columns(
            pl.col("timestamp").str.to_datetime(strict=False).alias("parsed_time")
        ).filter(
            pl.col("parsed_time").is_not_null()
        ).drop("parsed_time")

        return clean_batch
