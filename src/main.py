import os
import logging
import argparse
import time
from src.orchestrator import orchestrator

# Ensure the output directory exists before the logger tries to create a file there
os.makedirs("output", exist_ok=True)

# Configure the logger to write to BOTH the console and a dedicated file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("output/execution.log", mode='w'), # Saves to a file (overwrites old runs)
        logging.StreamHandler()                                # Prints to the terminal
    ]
)
logger = logging.getLogger("AstraLog-Main")

def main():
    input_path = "csv_input/export_sat_alpha_custom_no_corruption.csv"
    output_path = "output/"
    rules_path = "config/Current_rules_sat_alpha.json"
    sensors_path = "config/Current_sensors_sat_alpha.yaml"

    parser = argparse.ArgumentParser(description="AstraLog-HPC Main Execution Script")
    
    # Arguments
    parser.add_argument('--batch_size', type=int, required=True, help="Batch size for RAM-safe processing.")
    parser.add_argument('--mode', type=str, choices=['csv', 'stream'], default='csv', 
                        help="Data ingestion mode: 'csv' for static files, 'stream' for directory polling.")
    parser.add_argument('--input_path', type=str, default=input_path, 
                        help="Path to input CSV (used only in 'csv' mode).")
    
    args = parser.parse_args()

    start_time = time.perf_counter()

    # Call the orchestrator passing ALL required arguments
    orchestrator(
        batch_size=args.batch_size, 
        input_path=args.input_path,
        output_path=output_path,
        rules_path=rules_path,
        sensors_path=sensors_path,
        mode=args.mode
    )
    
    end_time = time.perf_counter()
    logger.info(f"Total Execution Time: {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    main()