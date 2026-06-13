"""
AstraLog-HPC Core Orchestrator.

This module contains the central execution loop. It binds the abstract interfaces 
to their concrete implementations and manages the lifecycle of the telemetry data 
from ingestion, through evaluation, to exportation.
"""

import polars as pl
import logging

MAX_SAFE_BATCH = 5_000_000

# 1. Import the Interfaces (Abstract Base Classes)
from src.interfaces import ITelemetryReader, IRulesEngine, IOutputWriter

logger = logging.getLogger(__name__)


def orchestrator(
    reader: ITelemetryReader,
    rules_engine: IRulesEngine,
    writer: IOutputWriter,
    batch_size: int,
    total_sensors: int,
) -> None:
    """
    Main orchestration loop that ties the system components together.

    It relies on injected components to process telemetry data and enforces
    critical safety constraints to ensure Out-Of-Memory (OOM) protection and prevents
    timestamp splitting across batches.

    Args:
        reader (ITelemetryReader): The injected telemetry reader component.
        rules_engine (IRulesEngine): The injected rules engine component.
        writer (IOutputWriter): The injected output writer component.
        batch_size (int): The user-requested maximum rows per batch.
        total_sensors (int): Total number of active sensors for safe chunk alignment.

    Notes:
        - **OOM Protection**: Hard-caps the batch size to 5,000,000 rows.
        - **Timestamp Integrity**: Auto-adjusts the batch size to the nearest multiple
          of the total sensor count to guarantee no single timestamp is split between batches.
    """

    logger.info("AstraLog-HPC Orchestrator Started")

    # ---------------------------------------------------------
    # STRICT SAFETY VALIDATION (OOM & Alignment)
    # ---------------------------------------------------------

    if batch_size <= 0:
        raise ValueError(f"batch_size must be strictly positive, got {batch_size}")
        
    if total_sensors <= 0:
        raise ValueError(f"total_sensors must be strictly positive, got {total_sensors}. Check your config file.")
        
    if total_sensors > MAX_SAFE_BATCH:
        raise ValueError(
            f"CRITICAL: total_sensors ({total_sensors}) exceeds the RAM safety limit MAX_SAFE_BATCH ({MAX_SAFE_BATCH}). "
            "Cannot process even a single timestamp without risking OOM."
        )

    # Max batch size cap to prevent OOM, with a warning to the user
    if batch_size > MAX_SAFE_BATCH:
        logger.warning(
            f"Requested batch_size ({batch_size}) exceeds RAM limits. Capping to {MAX_SAFE_BATCH}."
        )
        batch_size = MAX_SAFE_BATCH

    # Aline the batch to the sensors to avoid splitting timestamps
    safe_batch_size = (batch_size // total_sensors) * total_sensors
    
    if safe_batch_size == 0:
        raise ValueError(
            f"Requested batch_size ({batch_size}) after capping is smaller than one full timestamp "
            f"({total_sensors} sensors). Increase batch_size or reduce sensors."
        )

    if safe_batch_size != batch_size:
        logger.warning( # <-- Cambia "info" in "warning"
            f"Auto-adjusting batch_size from {batch_size} to safe multiple: {safe_batch_size}"
        )
        
    batch_size = safe_batch_size
    # ---------------------------------------------------------
    logger.info(f"Configuration loaded -> Batch Size: {batch_size}")

    batch_counter = 0
    total_alarms = 0

    # --- MAIN ORCHESTRATION LOOP ---
    while True:
        # 1. Extract the next batch of telemetry
        telemetry_batch: pl.DataFrame = reader.extract_batch(batch_size)

        # An empty batch means we hit the bottom of the file (Polars uses .is_empty() or .height == 0)
        if telemetry_batch.is_empty():
            logger.info("EOF reached. No more telemetry to process.")
            break

        batch_counter += 1

        # 2. Evaluate business logic
        valid_telemetry, alarm_telemetry = rules_engine.evaluate_rules(telemetry_batch)
        total_alarms += alarm_telemetry.height

        logger.info(
            f"Processing Batch #{batch_counter} | Rows: {telemetry_batch.height} | Alarms Found: {alarm_telemetry.height}"
        )

        # 3. Write outputs
        if not valid_telemetry.is_empty():
            writer.write_valid_batch(valid_telemetry)

        if not alarm_telemetry.is_empty():
            writer.write_alarms_batch(alarm_telemetry)

    logger.info("AstraLog-HPC Orchestrator Finished")
    logger.info(
        f"Total batches processed: {batch_counter} | Total alarms detected: {total_alarms}"
    )
