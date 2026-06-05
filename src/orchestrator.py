import polars as pl
import yaml
import logging

# 1. Import the Interfaces (Abstract Base Classes)
from src.interfaces import ITelemetryReader, IRulesEngine, IOutputWriter, IStateMemory

# 2. Import Concrete Implementations
from src.reader import CSVTelemetryReader
from src.rules_engine import PolarsRulesEngine
from src.writer import CSVOutputWriter
from src.state_memory import DictStateMemory

logger = logging.getLogger(__name__)

def orchestrator(batch_size: int, input_path: str, output_path: str, rules_path: str, sensors_path: str) -> None:
    """
    Main orchestration loop that ties the system components together.
    It relies entirely on interfaces to interact with the underlying components.
    """
    logger.info("AstraLog-HPC Orchestrator Started")

    # ---------------------------------------------------------
    # SAFETY FIX 1: Prevent Out-Of-Memory (OOM) Crashes
    # ---------------------------------------------------------
    # Based on our benchmarking, 5,000,000 rows should be a safe upper limit for batch processing on a typical machine with 8GB RAM.
    # This is a conservative cap to prevent users from accidentally crashing the system by requesting an excessively large batch size. 
    MAX_SAFE_BATCH = 5_000_000
    if batch_size > MAX_SAFE_BATCH:
        logger.warning(f"Requested batch_size ({batch_size}) may exceeds RAM safety limits. Capping to {MAX_SAFE_BATCH}.")
        batch_size = MAX_SAFE_BATCH
    
    # ---------------------------------------------------------
    # SAFETY FIX 2: Ensure batch_size is a multiple of total sensors
    # ---------------------------------------------------------
    with open(sensors_path, 'r') as f:
        sensor_config = yaml.safe_load(f)
        total_sensors = len(sensor_config['sensors'])
    
    safe_batch_size = (batch_size // total_sensors) * total_sensors
    
    if safe_batch_size == 0:
        safe_batch_size = total_sensors # Ensure it's at least one full timestamp
        
    if safe_batch_size != batch_size:
        logger.warning(f"Requested batch_size ({batch_size}) splits timestamps. Auto-adjusting to safe multiple: {safe_batch_size}")
        batch_size = safe_batch_size
    # ---------------------------------------------------------
    logger.info(f"Configuration loaded -> Batch Size: {batch_size} | Input: {input_path} | Output: {output_path}")

    # --- COMPONENT INSTANTIATION ---
    memory: IStateMemory = DictStateMemory()
    
    # Notice we use the original argument names mapped to our correct Polars classes
    reader: ITelemetryReader = CSVTelemetryReader(sensors_yaml_path=sensors_path, csv_path=input_path)
    rules_engine: IRulesEngine = PolarsRulesEngine(rules_json_path=rules_path, memory=memory)
    writer: IOutputWriter = CSVOutputWriter(output_path=output_path, clean_start=True)
    
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

        logger.info(f"Processing Batch #{batch_counter} | Rows: {telemetry_batch.height} | Alarms Found: {alarm_telemetry.height}")

        # 3. Write outputs
        if not valid_telemetry.is_empty():
            writer.write_valid_batch(valid_telemetry)

        if not alarm_telemetry.is_empty():
            writer.write_alarms_batch(alarm_telemetry)

    logger.info("AstraLog-HPC Orchestrator Finished")
    logger.info(f"Total batches processed: {batch_counter} | Total alarms detected: {total_alarms}")