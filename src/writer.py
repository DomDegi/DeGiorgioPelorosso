"""
Data Exportation Component.

Handles the physical writing of evaluated data frames to the local filesystem. 
Enforces the strict string formatting required by the project specifications.
"""

import os
import polars as pl
import logging
from src.interfaces import IOutputWriter

logger = logging.getLogger(__name__)


class CSVOutputWriter(IOutputWriter):
    """
    Concrete implementation of IOutputWriter for CSV and Log files.

    Transforms the vectorized Polars representations back into the highly specific,
    semicolon-separated string formats required for both Nominal and Alarm outputs.
    """

    def __init__(self, output_path: str, clean_start: bool = True):
        """
        Initializes the output paths and optionally clears previous execution logs.

        Args:
            output_path (str): The base directory where the output files will be created.
            clean_start (bool, optional): If True, deletes existing files in the output
                                          directory to prevent appending to old data. Defaults to True.
        """

        self.output_path = output_path
        os.makedirs(self.output_path, exist_ok=True)

        self.valid_file_path = os.path.join(self.output_path, "valid_data.csv")
        self.alarms_file_path = os.path.join(self.output_path, "alarms.log")

        if clean_start:
            if os.path.exists(self.valid_file_path):
                os.remove(self.valid_file_path)
            if os.path.exists(self.alarms_file_path):
                os.remove(self.alarms_file_path)

        logger.info(f"Output Writer initialized. Target: {self.output_path}")

    def write_valid_batch(self, valid_telemetry: pl.DataFrame) -> None:
        """
        Formats and writes nominal data to 'valid_data.csv'.

        Groups individual sensor readings by timestamp and concatenates them into
        the required specification format: 'TIMESTAMP;NOMINAL;S1:VAL|S2:VAL'.

        Args:
            valid_telemetry (pl.DataFrame): Data cleared of any rule violations.
        """

        if valid_telemetry.height == 0:
            return

        # Native Polars string formatting & grouping
        grouped = (
            valid_telemetry.sort(["timestamp", "sensor_id"])
            .with_columns(
                pl.concat_str(
                    [pl.col("sensor_id"), pl.lit(":"), pl.col("value").cast(pl.Utf8)]
                ).alias("sensor_string")
            )
            .group_by("timestamp", maintain_order=True)
            .agg(pl.col("sensor_string"))
            .with_columns(
                pl.col("sensor_string").list.join("|"),
                pl.lit("NOMINAL").alias("status"),
            )
            .select(["timestamp", "status", "sensor_string"])
        )

        with open(self.valid_file_path, "ab") as f:
            grouped.write_csv(f, separator=";", include_header=False, quote_style="never")

    def write_alarms_batch(self, alarm_telemetry: pl.DataFrame) -> None:
        """
        Formats and writes anomalous data to 'alarms.log'.

        Enforces column ordering and writes directly to the target file. Handles
        potential missing column exceptions gracefully to prevent pipeline crashes.

        Args:
            alarm_telemetry (pl.DataFrame): Data flagged as breaching rule thresholds.
        """

        if alarm_telemetry.height == 0:
            return

        expected_columns = ["timestamp", "rule_id", "priority", "sensor_id", "value"]
        try:
            formatted_alarms = alarm_telemetry.select(expected_columns)
        except pl.exceptions.ColumnNotFoundError as e:
            logger.error(
                f"OutputWriter missing columns. Check RulesEngine output. Details: {e}"
            )
            return

        with open(self.alarms_file_path, "ab") as f:
            formatted_alarms.write_csv(f, separator=";", include_header=False, quote_style="never")
