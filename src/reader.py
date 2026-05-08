import yaml
import logging
import polars as pl
from src.interfaces import ITelemetryReader

logger = logging.getLogger(__name__)

class CSVTelemetryReader(ITelemetryReader):
    def __init__(self, sensors_yaml_path: str = None, csv_path: str = None):
        self.sensors_config = self._load_yaml(sensors_yaml_path)
        self.csv_path = csv_path or "data/telemetry_stream.csv"
        
        # Buffer to solve the Polars "50k chunk" vs Pandas "exact row count" mismatch
        self._buffer = pl.DataFrame()
        
        self.schema = {
            "timestamp": pl.Utf8,
            "sensor_id": pl.Utf8,
            "value": pl.Utf8,  # Read as string first for strict NA/type handling like Pandas
            "priority": pl.Utf8
        }
        
        self._batched_reader = pl.read_csv_batched(
            self.csv_path,
            dtypes=self.schema,
            ignore_errors=True,
            null_values=["", "NA", "NaN", "null"]
        )
        logger.info(f"CSVTelemetryReader initialized. Target: {self.csv_path}")

    def _load_yaml(self, path: str) -> dict:
        path = path or "config/sensors.yaml"
        with open(path, 'r') as file:
            return yaml.safe_load(file)

    def _sanitize_batch(self, batch: pl.DataFrame) -> pl.DataFrame:
        initial_len = batch.height
        
        # 1. Mandatory columns check
        req_cols = ['timestamp', 'sensor_id', 'value']
        missing_cols = [c for c in req_cols if c not in batch.columns]
        if missing_cols:
            return pl.DataFrame(schema={"timestamp": pl.Utf8, "sensor_id": pl.Utf8, "value": pl.Float64, "priority": pl.Utf8})

        clean_batch = batch.drop_nulls(subset=req_cols)

        # 2. Priority Handling (Default to LOW, uppercase, strict valid list)
        if 'priority' not in clean_batch.columns:
            clean_batch = clean_batch.with_columns(pl.lit('LOW').alias('priority'))
        else:
            clean_batch = clean_batch.with_columns(
                pl.col('priority').fill_null('LOW').str.to_uppercase()
            ).filter(
                pl.col('priority').is_in(['LOW', 'MEDIUM', 'HIGH'])
            )

        # 3. Strict Type Checking (Values to Float, drop failures)
        clean_batch = clean_batch.with_columns(
            pl.col('value').cast(pl.Float64, strict=False)
        ).drop_nulls(subset=['value'])

        # Drop invalid datetimes but keep column as string (matching Pandas implementation)
        clean_batch = clean_batch.with_columns(
            pl.col("timestamp").str.to_datetime(strict=False).alias("parsed_time")
        ).filter(
            pl.col("parsed_time").is_not_null()
        ).drop("parsed_time")

        dropped = initial_len - clean_batch.height
        if dropped > 0:
            logger.debug(f"Dropped {dropped} records due to strict type corruption.")

        return clean_batch

    def extract_batch(self, batch_size: int) -> pl.DataFrame:
        """Extracts exactly 'batch_size' rows using an internal buffer."""
        # Fill buffer until it has enough rows or we hit EOF
        while self._buffer.height < batch_size:
            batches = self._batched_reader.next_batches(1)
            if not batches:
                break
            self._buffer = pl.concat([self._buffer, batches[0]])
            
        if self._buffer.height == 0:
            logger.info("End of CSV telemetry stream reached.")
            return pl.DataFrame()

        # Slice the exact required amount
        raw_chunk = self._buffer.head(batch_size)
        self._buffer = self._buffer.tail(self._buffer.height - batch_size)

        return self._sanitize_batch(raw_chunk)