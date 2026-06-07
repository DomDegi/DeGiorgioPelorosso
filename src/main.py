"""
AstraLog-HPC CLI Entry Point.

This module initializes the application environment, configures the dual-output 
logger (console and file), parses command-line arguments, and invokes the main 
system Orchestrator.
"""

import os
import logging
import argparse
import time
import yaml
from src.orchestrator import orchestrator

from src.reader import CSVTelemetryReader
from src.rules_engine import PolarsRulesEngine
from src.writer import CSVOutputWriter
from src.state_memory import DictStateMemory

# Ensure the default output directory exists for the logger
os.makedirs("output", exist_ok=True)

# Configure the logger to write to BOTH the console and a dedicated file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("output/execution.log", mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AstraLog-Main")

def main() -> None:
    """
    Main execution script for AstraLog-HPC.
    
    Parses execution arguments from the command line, tracks the total execution time 
    for benchmarking purposes, and passes the configuration safely to the Orchestrator.
    
    Command Line Arguments:
        --batch_size (int): The maximum number of rows to process in memory at once.
        --input_path (str): The file path to the incoming telemetry CSV.
        --output_path (str): The directory where results will be saved.
        --rules_path (str): The file path to the JSON monitoring rules.
        --sensors_path (str): The file path to the YAML sensors configuration.
    """
    
    parser = argparse.ArgumentParser(description="AstraLog-HPC Main Execution Script")
    
    # Define arguments
    parser.add_argument('--batch_size', type=int, required=True, help="Batch size for RAM-safe processing.")
    parser.add_argument('--input_path', type=str, required=True, help="Path to the input telemetry CSV.")
    parser.add_argument('--output_path', type=str, required=True, help="Path to save output results and logs.")
    parser.add_argument('--rules_path', type=str, required=True, help="Path to the rules JSON configuration.")
    parser.add_argument('--sensors_path', type=str, required=True, help="Path to the sensors YAML configuration.")
    
    args = parser.parse_args()
    
    start_time = time.perf_counter()
    
    logger.info("Initializing AstraLog-HPC...")

    # Parse sensor config once to establish the total sensor count for safety bounds
    with open(args.sensors_path, 'r') as f:
        sensor_config = yaml.safe_load(f)
        total_sensors = len(sensor_config['sensors'])

    # Instantiate concrete classes (Composition Root)
    memory = DictStateMemory()
    reader = CSVTelemetryReader(sensors_yaml_path=args.sensors_path, csv_path=args.input_path)
    rules_engine = PolarsRulesEngine(rules_json_path=args.rules_path, memory=memory)
    writer = CSVOutputWriter(output_path=args.output_path, clean_start=True)
    
    # Call the orchestrator, passing ALL required dependencies (Dependency Injection)
    orchestrator(
        reader=reader,
        rules_engine=rules_engine,
        writer=writer,
        batch_size=args.batch_size, 
        total_sensors=total_sensors
    )
    
    end_time = time.perf_counter()
    logger.info(f"Total Execution Time: {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    main()