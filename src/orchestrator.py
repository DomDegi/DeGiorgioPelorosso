import pandas as pd
import yaml
import logging

# 1. Import the Interfaces (Abstract Base Classes)
# Assuming the provided abstract classes are saved in 'interfaces.py'
from src.interfaces import ITelemetryReader, IRulesEngine, IOutputWriter, IStateMemory

# 2. Import Concrete Implementations
from src.reader import CSVTelemetryReader
from src.rules_engine import PandasRulesEngine
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
    # SAFETY FIX: Ensure batch_size is a multiple of total sensors
    # ---------------------------------------------------------
    # Peek into the sensors.yaml to count the active sensors
    with open(sensors_path, 'r') as f:
        sensor_config = yaml.safe_load(f)
        total_sensors = len(sensor_config['sensors'])
    
    # Calculate the nearest safe multiple of active sensors. 
    # This prevents splitting a single timestamp across two different evaluation batches.
    safe_batch_size = (batch_size // total_sensors) * total_sensors
    
    if safe_batch_size == 0:
        safe_batch_size = total_sensors # Ensure it's at least one full timestamp
        
    if safe_batch_size != batch_size:
        logger.warning(f"Requested batch_size ({batch_size}) splits timestamps. Auto-adjusting to safe multiple: {safe_batch_size}")
        batch_size = safe_batch_size
    # ---------------------------------------------------------
    logger.info(f"Configuration loaded -> Batch Size: {batch_size} | Input: {input_path} | Output: {output_path}")

    # --- COMPONENT INSTANTIATION ---
    # Here we instantiate the concrete classes, but we type-hint them 
    # strictly as their Interfaces. This is the Python equivalent of Java's:
    # ITelemetryReader reader = new CSVTelemetryReader(input_path);
    memory: IStateMemory = DictStateMemory()
    
    reader: ITelemetryReader = CSVTelemetryReader(sensors_yaml_path=sensors_path, csv_path=input_path)
    rules_engine: IRulesEngine = PandasRulesEngine(rules_json_path=rules_path, memory=memory)
    writer: IOutputWriter = CSVOutputWriter(output_path=output_path, clean_start=True)
    
    batch_counter = 0
    total_alarms = 0
    
    # --- MAIN ORCHESTRATION LOOP ---
    while True:
        # 1. Extract the next batch of telemetry
        # The reader converts a physical chunk into a logical DataFrame batch
        telemetry_batch: pd.DataFrame = reader.extract_batch(batch_size)
        
        # An empty batch means we hit the bottom of the file
        if telemetry_batch.empty:
            logger.info("EOF reached. No more telemetry to process.")
            break
            
        batch_counter += 1
 
        # 2. Evaluate business logic
        # The Rules Engine separates nominal data from anomalies
        valid_telemetry, alarm_telemetry = rules_engine.evaluate_rules(telemetry_batch)
        total_alarms += len(alarm_telemetry)

        logger.info(f"Processing Batch #{batch_counter} | Rows: {len(telemetry_batch)} | Alarms Found: {len(alarm_telemetry)}")

        # 3. Write outputs
        # The Writer handles the physical I/O chunking to the disk
        if not valid_telemetry.empty:
            writer.write_valid_batch(valid_telemetry)

        if not alarm_telemetry.empty:
            writer.write_alarms_batch(alarm_telemetry)

    logger.info("AstraLog-HPC Orchestrator Finished")
    logger.info(f"Total batches processed: {batch_counter} | Total alarms detected: {total_alarms}")