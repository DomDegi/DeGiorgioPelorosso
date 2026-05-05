import os
import logging
import argparse
import time
from src.orchestrator import orchestrator

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

def main():
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
    
    # Call the orchestrator, passing ALL required arguments
    orchestrator(
        batch_size=args.batch_size, 
        input_path=args.input_path,
        output_path=args.output_path,
        rules_path=args.rules_path,
        sensors_path=args.sensors_path
    )
    
    end_time = time.perf_counter()
    logger.info(f"Total Execution Time: {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    main()
