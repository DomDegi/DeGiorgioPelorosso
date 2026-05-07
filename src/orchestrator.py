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
    # SAFETY FIX: Ensure batch_size is a multiple of total sensors
    # ---------------------------------------------------------
    with open(sensors_path, 'r') as f:
        sensor_config = yaml.safe_load(f)
        total_sensors = len(sensor_config['sensors'])
    
    safe_batch_size = (batch_size // total_sensors) * total_sensors
    
    if safe_batch_size == 0:
        safe_batch_size = total_sensors 
        
    if safe_batch_size != batch_size:
        logger.warning(f"Requested batch_size ({batch_size}) splits timestamps. Auto-adjusting to safe multiple: {safe_batch_size}")
        batch_size = safe_batch_size
    # ---------------------------------------------------------
    logger.info(f"Configuration loaded -> Batch Size: {batch_size} | Input: {input_path} | Output: {output_path}")

    # --- COMPONENT INSTANTIATION ---
    memory: IStateMemory = DictStateMemory()
    
    reader: ITelemetryReader = CSVTelemetryReader(sensors_yaml_path=sensors_path, csv_path=input_path)
    rules_engine: IRulesEngine = PolarsRulesEngine(rules_path=rules_path)
    writer: IOutputWriter = CSVOutputWriter(output_dir=output_path)
    
    batch_counter = 0
    total_alarms = 0
    
    # =========================================================
    # SETUP HEADER TABELLA LOG
    # =========================================================
    logger.info("=" * 60)
    logger.info(f"{'BATCH':>8} | {'ROWS PROCESSED':>16} | {'ALARMS DETECTED':>17} | {'STATUS':>9}")
    logger.info("-" * 60)
    
    # --- MAIN ORCHESTRATION LOOP ---
    while True:
        # 1. Extract the next batch of telemetry
        telemetry_batch: pl.DataFrame = reader.extract_batch(batch_size)
        
        # An empty batch means we hit the bottom of the file
        if telemetry_batch.height == 0:
            break
            
        batch_counter += 1
 
        # 2. Evaluate business logic
        valid_telemetry, alarm_telemetry = rules_engine.evaluate_rules(telemetry_batch, memory)
        total_alarms += alarm_telemetry.height

        # --- STAMPA RIGA TABELLA ---
        # L'uso di :>n allinea il testo a destra riempiendo con spazi fino a 'n' caratteri
        status = "[ ALARM ]" if alarm_telemetry.height > 0 else "[  OK  ]"
        logger.info(f"{batch_counter:>8} | {telemetry_batch.height:>16} | {alarm_telemetry.height:>17} | {status:>9}")

        # 3. Write outputs
        if valid_telemetry.height > 0:
            writer.write_valid_batch(valid_telemetry)

        if alarm_telemetry.height > 0:
            writer.write_alarms_batch(alarm_telemetry)

    # =========================================================
    # SETUP FOOTER TABELLA LOG
    # =========================================================
    logger.info("=" * 60)
    logger.info("EOF reached. No more telemetry to process.")
    logger.info(f"FINAL SUMMARY -> Total Batches: {batch_counter} | Total Alarms: {total_alarms}")
    logger.info("AstraLog-HPC Orchestrator Finished")