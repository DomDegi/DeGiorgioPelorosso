"""
Data Ingestion Component.

This module provides the concrete implementation for reading telemetry streams
from CSV files. It leverages Polars for high-speed batched reading while actively
sanitizing corrupted data to ensure schema compliance.
"""

import yaml
import logging
import polars as pl
from src.interfaces import ITelemetryReader

logger = logging.getLogger(__name__)


class CSVTelemetryReader(ITelemetryReader):
    """
    Concrete implementation of the ITelemetryReader for CSV files.

    Maintains an internal DataFrame buffer to reconcile the difference between
    Polars' native physical chunking and the exact logical batch sizes requested
    by the Orchestrator.
    """

    def __init__(self, sensors_yaml_path: str = None, csv_path: str = None):
        """
        Initializes the CSV Reader and loads the initial stream buffer.

        Args:
            sensors_yaml_path (str, optional): Path to the YAML sensor config. Defaults to None.
            csv_path (str, optional): Path to the telemetry CSV file. Defaults to None.
        """

        self.sensors_config = self._load_yaml(sensors_yaml_path)
        self.csv_path = csv_path or "data/telemetry_stream.csv"

        # Buffer to solve the Polars "50k chunk" vs Pandas "exact row count" mismatch
        self._buffer = pl.DataFrame()

        self.schema = {
            "timestamp": pl.Utf8,
            "sensor_id": pl.Utf8,
            "value": pl.Utf8,  # Read as string first for strict NA/type handling like Pandas
            "priority": pl.Utf8,
        }

        self._batched_reader = pl.read_csv_batched(
            self.csv_path,
            dtypes=self.schema,
            ignore_errors=True,
            null_values=["", "NA", "NaN", "null"],
        )
        logger.info(f"CSVTelemetryReader initialized. Target: {self.csv_path}")

    def _load_yaml(self, path: str) -> dict:
        """
        Private helper to load the YAML configuration.

        Args:
            path (str): Path to the YAML file.

        Returns:
            dict: The parsed YAML configuration.
        """

        path = path or "config/sensors.yaml"
        with open(path, "r") as file:
            return yaml.safe_load(file)

    def _sanitize_batch(self, batch: pl.DataFrame) -> pl.DataFrame:
        """
        Cleans the raw physical chunk to ensure strict schema compliance.

        Validates mandatory columns, normalizes priorities, enforces strict Float64
        types for values, and drops structurally corrupted rows safely.

        Args:
            batch (pl.DataFrame): The raw data chunk extracted from the CSV.

        Returns:
            pl.DataFrame: A sanitized DataFrame guaranteed to match the expected schema.
        """

        initial_len = batch.height

        # 1. Mandatory columns check
        req_cols = ["timestamp", "sensor_id", "value"]
        missing_cols = [c for c in req_cols if c not in batch.columns]
        if missing_cols:
            return pl.DataFrame(
                schema={
                    "timestamp": pl.Utf8,
                    "sensor_id": pl.Utf8,
                    "value": pl.Float64,
                    "priority": pl.Utf8,
                }
            )

        clean_batch = batch.drop_nulls(subset=req_cols)

        # 2. Priority Handling (Default to LOW, uppercase, strict valid list)
        if "priority" not in clean_batch.columns:
            clean_batch = clean_batch.with_columns(pl.lit("LOW").alias("priority"))
        else:
            clean_batch = clean_batch.with_columns(
                pl.col("priority").fill_null("LOW").str.to_uppercase()
            ).filter(pl.col("priority").is_in(["LOW", "MEDIUM", "HIGH"]))

        # 3. Strict Type Checking (Values to Float, drop failures)
        clean_batch = clean_batch.with_columns(
            pl.col("value").cast(pl.Float64, strict=False)
        ).drop_nulls(subset=["value"])

        # Drop invalid datetimes but keep column as string (matching Pandas implementation)
        clean_batch = (
            clean_batch.with_columns(
                pl.col("timestamp").str.to_datetime(strict=False).alias("parsed_time")
            )
            .filter(pl.col("parsed_time").is_not_null())
            .drop("parsed_time")
        )

        dropped = initial_len - clean_batch.height
        if dropped > 0:
            logger.debug(f"Dropped {dropped} records due to strict type corruption.")

        return clean_batch

    def extract_batch(self, batch_size: int) -> pl.DataFrame:
        """
        Extracts exactly 'batch_size' rows using an optimized internal list buffer.
        Handles EOF gracefully and skips entirely corrupted chunks without
        causing premature termination.
        """
        while True:
            # 1. Put the leftover buffer into a list
            batches_to_concat = [self._buffer] if self._buffer.height > 0 else []
            current_height = self._buffer.height
            reached_eof = False

            # 2. Append new batches to the list
            while current_height < batch_size:
                batches = self._batched_reader.next_batches(1)
                if not batches:
                    reached_eof = True
                    break
                batches_to_concat.append(batches[0])
                current_height += batches[0].height

            # If NOT really anything left to read and buffer is empty, return empty DataFrame with schema
            if current_height == 0:
                logger.info("End of CSV telemetry stream reached.")
                return pl.DataFrame(
                    schema={
                        "timestamp": pl.Utf8,
                        "sensor_id": pl.Utf8,
                        "value": pl.Float64,
                        "priority": pl.Utf8,
                    }
                )

            # 3. Concatenate everything exactly ONCE
            full_buffer = pl.concat(batches_to_concat)

            # 4. Slice the exact required amount safely
            take = min(batch_size, full_buffer.height)
            raw_chunk = full_buffer.head(take)

            self._buffer = full_buffer.slice(take, full_buffer.height - take)

            # 5. Sanitize and check for Empty DataFrame trap
            sanitized = self._sanitize_batch(raw_chunk)

            # If sanitization preserved at least one row, return the batch
            if sanitized.height > 0:
                return sanitized

            # Sanification dropped eveything, but we are at EOF, return
            if reached_eof and self._buffer.height == 0:
                return pl.DataFrame(
                    schema={
                        "timestamp": pl.Utf8,
                        "sensor_id": pl.Utf8,
                        "value": pl.Float64,
                        "priority": pl.Utf8,
                    }
                )
